"""A/B evidence for context preparation (B4-05.03): when may anyone say "this saved tokens"?

Two parts, kept apart on purpose:
  shadow_sizes   no agent is called. It only measures how much smaller the prepared bundle is than the naive prompt (every in-scope
                 file whole). The result is labelled `prompt_size_only`: it proves nothing about success, never about tokens an agent used.
  compare        two real-agent benchmark reports (routing_confidence.problems must accept both): the same agent, model, version, tasks,
                 repeat and timeout, one run with context preparation and one without. A saving is claimed only if every measured
                 token count is known, both arms have enough runs, the prepared arm is not detectably worse on success and has no worker
                 security violation; otherwise the answer is `no_claim` with the reasons, and context preparation stays in shadow mode.
Nothing here switches the feature on or off."""
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..engine import context_map, context_prep
from . import routing_confidence as rc

MIN_RUNS_PER_ARM = 30
SAME = ("agent", "task_ids", "repeat", "timeout")


def shadow_sizes(project: Path, tasks: Sequence[Mapping[str, Any]], *, budget_tokens: int = 4000) -> dict[str, Any]:
    """tasks: [{id, task, allowed:[paths], forbidden?:[paths]}]. Per task: naive vs prepared estimated tokens."""
    rows = []
    for item in tasks:
        built = context_map.build(project, allowed=item["allowed"], forbidden=item.get("forbidden", []))
        naive = 0
        for entry in built["files"]:
            try:
                naive += context_prep.estimate_tokens((Path(project) / entry["path"]).read_text("utf-8", errors="replace"))
            except OSError:
                continue
        prepared = context_prep.prepare(project, built, item["task"], budget_tokens=budget_tokens)
        used = prepared["tokens"]["estimated"]
        rows.append({"id": item["id"], "naive_tokens": naive, "prepared_tokens": used, "saved_fraction": round(1 - used / naive, 4) if naive else None,
                     "critical_tokens": prepared["tokens"]["critical"], "dropped": len(prepared["dropped"])})
    measured = [r["saved_fraction"] for r in rows if r["saved_fraction"] is not None]
    return {"kind": "prompt_size_only", "unit": "chars/4 estimate", "claims": "none: no agent was called, success and real token use are unmeasured",
            "tasks": rows, "mean_saved_fraction": round(sum(measured) / len(measured), 4) if measured else None}


def _tokens(report: Mapping[str, Any]) -> int | None:
    values = [r.get("tokens") for r in report["runs"] if r.get("arm") == "orchestrated"]
    return sum(values) if values and all(type(v) is int and v > 0 for v in values) else None


def compare(baseline: Any, prepared: Any) -> dict[str, Any]:
    """Decide whether the prepared-context report supports a token-saving claim over the baseline report."""
    reasons: list[str] = []
    for label, report in (("baseline", baseline), ("prepared", prepared)):
        reasons += [f"{label}: {p}" for p in rc.problems(report)]
    if not reasons and (baseline.get("context_prep") is True or prepared.get("context_prep") is not True):
        reasons.append("the baseline must be a run without context preparation and the prepared report must say context_prep: true")
    if reasons:
        return {"claim": "no_claim", "reasons": reasons, "mode": "shadow"}
    for field in SAME:
        if baseline.get(field) != prepared.get(field):
            reasons.append(f"incomparable: {field} differs")
    if reasons:
        return {"claim": "no_claim", "reasons": reasons, "mode": "shadow"}
    a, b = rc.evaluate([baseline])["entries"][0]["orchestrated"], rc.evaluate([prepared])["entries"][0]["orchestrated"]
    base_tokens, prep_tokens = _tokens(baseline), _tokens(prepared)
    if a["n"] < MIN_RUNS_PER_ARM or b["n"] < MIN_RUNS_PER_ARM:
        reasons.append(f"fewer than {MIN_RUNS_PER_ARM} runs per arm")
    if base_tokens is None or prep_tokens is None:
        reasons.append("token counts are not known for every run: a saving cannot be measured, and unknown is never counted as zero")
    if b["security_violations"] not in (0,):
        reasons.append(f"prepared arm has worker security violations: {b['security_violations']}")
    if a["interval"] and b["interval"] and a["interval"][0] > b["interval"][1]:
        reasons.append("prepared arm succeeds detectably less often than the baseline")
    saving = round(1 - prep_tokens / base_tokens, 4) if base_tokens and prep_tokens is not None else None
    if saving is not None and saving <= 0:
        reasons.append("the prepared arm did not use fewer tokens")
    out = {"success": {"baseline": a, "prepared": b}, "tokens": {"baseline": base_tokens, "prepared": prep_tokens, "saved_fraction": saving}}
    if reasons:
        return {"claim": "no_claim", "reasons": reasons, "mode": "shadow", **out}
    return {"claim": "token_saving", "reasons": [], "mode": "eligible_for_opt_in", **out}


def manifest(baseline: Mapping[str, Any], prepared: Mapping[str, Any], verdict: Mapping[str, Any]) -> dict[str, Any]:
    """The reproducible experiment record: what was compared and what was concluded. Raw runs stay in the two reports."""
    return {"schema": "respected.eval.contextab.v1", "agent": baseline.get("agent"), "commit": {"baseline": baseline.get("commit"), "prepared": prepared.get("commit")},
            "task_ids": baseline.get("task_ids"), "repeat": baseline.get("repeat"), "timeout": baseline.get("timeout"),
            "verdict": verdict["claim"], "reasons": verdict["reasons"], "tokens": verdict.get("tokens"), "mode": verdict["mode"]}
