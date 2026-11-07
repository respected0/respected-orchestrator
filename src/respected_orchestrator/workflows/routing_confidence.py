"""Routing confidence from real-agent benchmark reports (B4-01.04).

Reads reports written by `python -m tests.evals.bench run` (schema respected.eval.bench.v1) and answers three questions
without inventing anything: (1) can this report be used at all, (2) how sure is the orchestrated-vs-direct comparison
(Wilson intervals; "no detectable difference" is a result, not a win), (3) what measured history may routing use. The gate
fails when there is no valid real report: an unmeasured benchmark is a failed gate, never a pass. A report is never pooled
with another; same agent+model on a different version, or on different tasks/timeout/repeat, is flagged instead of merged.
Synthetic (`harness-test`) reports and the synthetic compare.py output are rejected here."""
import math
from collections.abc import Mapping, Sequence
from typing import Any

SCHEMA = "respected.eval.bench.v1"
UNKNOWN = "unknown"
MIN_TASKS, MIN_REPEAT = 10, 3  # same release floor as tests/evals/bench.py (10 tasks x 3 repeats x 2 arms)


def wilson(passed: int, n: int, z: float = 1.96) -> list[float] | None:
    """95% Wilson score interval for a rate, or None without samples."""
    if n <= 0:
        return None
    p = passed / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def problems(report: Any) -> list[str]:
    """Why a report cannot count as routing evidence. Empty = usable."""
    if not isinstance(report, Mapping) or report.get("schema") != SCHEMA:
        return ["wrong schema"]
    out, runs = [], report.get("runs")
    if not isinstance(runs, list) or not all(isinstance(r, Mapping) for r in runs):
        return ["runs missing or malformed"]
    if report.get("kind") != "real":
        out.append("not a real-agent report")
    if report.get("status") != "complete":
        out.append(f"status is {report.get('status')!r}")
    if report.get("golden_used") is not False or any(r.get("status") == "invalid" for r in runs):
        out.append("golden fix reached an agent or a run is invalid")
    if any(r.get("status") == "agent_error" for r in runs):
        out.append("agent_error runs present")
    if not report.get("commit") or report.get("commit") == UNKNOWN:
        out.append("commit not recorded")
    agent = report.get("agent")
    if not isinstance(agent, Mapping) or not all(agent.get(k) not in (None, "", UNKNOWN) for k in ("name", "model", "version")):
        out.append("agent name, model and version must all be recorded")
    tasks, repeat = report.get("task_ids"), report.get("repeat")
    if not isinstance(tasks, list) or type(repeat) is not int or len(tasks) < MIN_TASKS or repeat < MIN_REPEAT \
            or len(runs) != len(tasks) * repeat * 2:
        out.append("fewer than 10 tasks x 3 repeats x 2 arms")
    if any(r.get("tokens") == 0 or r.get("cost") == 0 for r in runs):
        out.append("unmeasured value written as 0")
    return out


def _arm(runs: Sequence[Mapping[str, Any]], arm: str) -> dict[str, Any]:
    rows = [r for r in runs if r.get("arm") == arm]
    passed = sum(r.get("status") == "passed" for r in rows)
    tokens = [r.get("tokens") for r in rows]
    return {"n": len(rows), "passed": passed, "rate": round(passed / len(rows), 4) if rows else None, "interval": wilson(passed, len(rows)),
            "tokens": sum(tokens) if tokens and all(type(t) is int for t in tokens) else UNKNOWN,
            "security_violations": sum(r.get("security_violation") is True for r in rows) if arm == "orchestrated" else UNKNOWN}


def _verdict(direct: Mapping[str, Any], orch: Mapping[str, Any]) -> str:
    if not direct["n"] or not orch["n"]:
        return "insufficient_sample"
    a, b = direct["interval"], orch["interval"]
    if b[0] > a[1]:
        return "orchestrated_better"
    if a[0] > b[1]:
        return "orchestrated_worse"
    return "no_detectable_difference"  # overlapping intervals are not evidence either way


def evaluate(reports: Sequence[Any]) -> dict[str, Any]:
    """One entry per report (never pooled), with usability problems, drift/confound flags and the comparison."""
    entries = []
    for index, report in enumerate(reports):
        bad = problems(report)
        entry: dict[str, Any] = {"index": index, "problems": bad, "usable": not bad}
        if isinstance(report, Mapping) and isinstance(report.get("agent"), Mapping) and isinstance(report.get("runs"), list):
            direct, orch = _arm(report["runs"], "direct"), _arm(report["runs"], "orchestrated")
            entry.update(agent=dict(report["agent"]), commit=report.get("commit"), direct=direct, orchestrated=orch, verdict=_verdict(direct, orch))
        entries.append(entry)
    for e in entries:
        e["flags"] = []
        for o in entries:
            if o is e or "agent" not in e or "agent" not in o:
                continue
            a, b = e["agent"], o["agent"]
            if (a.get("name"), a.get("model")) == (b.get("name"), b.get("model")):
                if a.get("version") != b.get("version"):
                    e["flags"].append("same_model_version_drift")
                else:
                    r1, r2 = reports[e["index"]], reports[o["index"]]
                    if any(r1.get(k) != r2.get(k) for k in ("task_ids", "timeout", "repeat")):
                        e["flags"].append("confounded_runs")
        e["flags"] = sorted(set(e["flags"]))
    return {"schema": 1, "entries": entries}


def routing_history(reports: Sequence[Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """track_record-shaped table ({(family, tool, profile): {runs, ok, avg_tokens, avg_seconds}}) from usable reports' orchestrated arm.

    Reports flagged for version drift or confounding are left out; a profile seen in two reports is summed only when both are
    usable and unflagged and share the same version. `suggest(history=...)` can take `lambda: table`."""
    ev = evaluate(reports)
    table: dict[tuple[str, str, str], dict[str, Any]] = {}
    versions: dict[tuple[str, str, str], str] = {}
    for entry in ev["entries"]:
        if not entry["usable"] or entry["flags"]:
            continue
        a = entry["agent"]
        key = ("write", a["name"], a["model"])
        if versions.setdefault(key, a["version"]) != a["version"]:
            continue
        row = table.setdefault(key, {"runs": 0, "ok": 0, "avg_tokens": None, "avg_seconds": None})
        row["runs"] += entry["orchestrated"]["n"]
        row["ok"] += entry["orchestrated"]["passed"]
    return table


def gate(reports: Sequence[Any]) -> dict[str, Any]:
    """B4-GATE-01 (benchmark part): passes only with >=1 usable real report, no orchestrated security violation and no
    detectable orchestrated-worse result. Unknown cost stays unknown; it does not fail the gate and is never counted as 0."""
    ev = evaluate(reports)
    usable = [e for e in ev["entries"] if e["usable"]]
    reasons = []
    if not usable:
        reasons.append("no usable real-agent benchmark report")
    for e in usable:
        if e["orchestrated"]["security_violations"] not in (0,):
            reasons.append(f"report {e['index']}: worker security violations {e['orchestrated']['security_violations']}")
        if e["verdict"] == "orchestrated_worse":
            reasons.append(f"report {e['index']}: orchestrated success is detectably lower than direct")
    return {"ok": not reasons, "reasons": reasons, "usable_reports": len(usable), "evaluation": ev}
