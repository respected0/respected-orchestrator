"""Feeds the cost ledger from this installation's own signed run evidence (B4-04.02 wiring).

Nothing new is written: `UsageEvent`s are derived on every call from `status.json` / `review-attempts.json` of each run, with
the same signature checks and traversal as track_record. Unsigned, tampered, running or custom-worker runs are skipped.
Task class is the request kind (write|read) only; billing is whatever the caller states per tool (default unknown, so no run
becomes an API cost by assumption). Without a price catalog every run is simply "uncomputable"."""
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ..context import EngineContext
from . import cost_ledger, failures, usage_event
from .evidence import load_signed
from .track_record import _roots


def _event(usage: Any, *, tool: str, run_id: str, step: str, at: str, model: Any, billing: Mapping[str, str]) -> dict[str, Any]:
    return usage_event.from_engine_usage(usage if isinstance(usage, Mapping) else None, tool=tool, run_id=run_id, step=step, at=at,
                                         model=model if isinstance(model, str) and model else None, billing=billing.get(tool, "unknown"))


def runs(data_root: Path, *, billing: Mapping[str, str] = {}, limit: int = 400) -> list[dict[str, Any]]:
    """Ledger run records for the newest `limit` finished, non-custom runs."""
    out, seen = [], 0
    for root in _roots(data_root):
        ctx = EngineContext(root)
        for directory in sorted((root / "state").glob("run-*"), reverse=True):
            if seen >= limit:
                break
            seen += 1
            try:
                request, status = load_signed(ctx, directory / "request.json"), load_signed(ctx, directory / "status.json")
                if status.get("status") in ("queued", "running") or request.get("worker") == "custom":
                    continue
                done = status.get("status") == "completed"
                result = load_signed(ctx, directory / "result.json") if (directory / "result.json").is_file() else {}
                at = status.get("updated_at") or request.get("created_at") or ""
                tool = request.get("worker") or "unknown"
                events = [_event(status.get("usage") or result.get("usage"), tool=tool, run_id=directory.name, step="worker", at=at,
                                 model=status.get("model") or result.get("model"), billing=billing)]
                reviews = directory / "review-attempts.json"
                if reviews.is_file():
                    for index, entry in enumerate(load_signed(ctx, reviews).get("attempts", [])):
                        rtool = entry.get("tool") or "codex"
                        events.append(_event(entry.get("usage"), tool=rtool, run_id=directory.name, step=f"review-{index}", at=at,
                                             model=entry.get("profile"), billing=billing))
                seconds = result.get("duration_seconds")
                record = (cost_ledger.run_record(
                    run_id=directory.name, task_class=str(request.get("kind") or "unknown"), accepted=done,
                    elapsed_seconds=seconds if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else None,
                    fix_rounds=None,  # not recorded per run; MAF rounds are not summed here
                    worker_violations=1 if status.get("reason") == "scope_violation" else 0, events=events))
                record["agent"], record["project"] = tool, request.get("project_root")  # extra facts for the read model; the ledger itself ignores them
                record["failure_class"] = None if done else failures.describe(status.get("reason"), status.get("provider_status")).get("failure_class")
                out.append(record)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue  # unsigned, tampered or partial evidence is not counted
    return out


def report(data_root: Path, catalog: Iterable[Mapping[str, Any]], at: str, *, billing: Mapping[str, str] = {},
           task_class: str | None = None, limit: int = 400) -> dict[str, Any]:
    """The ledger report over this installation's evidence, priced with `catalog` as of `at`."""
    return cost_ledger.report(runs(data_root, billing=billing, limit=limit), cost_ledger.snapshot(catalog, at), task_class=task_class)


def from_request(data_root: Path, request: Any, now: str) -> dict[str, Any]:
    """The `ledger` command: stdin {catalog?, at?, billing?, task_class?, limit?} -> report. Bad input is a ValueError, nothing is guessed."""
    if not isinstance(request, Mapping) or set(request) - {"catalog", "at", "billing", "task_class", "limit"}:
        raise ValueError("ledger request must be an object with catalog, at, billing, task_class, limit")
    catalog, billing = request.get("catalog", []), request.get("billing", {})
    if not isinstance(catalog, list) or not all(isinstance(e, Mapping) for e in catalog):
        raise ValueError("catalog must be a list of price entries")
    if not isinstance(billing, Mapping) or not all(isinstance(k, str) and v in usage_event.BILLING for k, v in billing.items()):
        raise ValueError("billing must map tool names to " + "|".join(usage_event.BILLING))
    limit = request.get("limit", 400)
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("limit must be an integer from 1 to 2000")
    task_class = request.get("task_class")
    if task_class is not None and not isinstance(task_class, str):
        raise ValueError("task_class must be a string")
    try:
        return report(data_root, catalog, request.get("at") or now, billing=billing, task_class=task_class, limit=limit)
    except (KeyError, TypeError) as error:  # a price entry missing a field or a non-ISO date
        raise ValueError(f"invalid price catalog or date: {error}") from error


def from_bench(bench: Any, *, billing: Mapping[str, str] = {}) -> list[dict[str, Any]]:
    """Ledger rows from a benchmark report (`tests/evals/bench.py`), one class per arm (`bench:direct`, `bench:orchestrated`), labelled with the
    report's own provenance (kind real|synthetic, agent@version:commit). A benchmark records total tokens only, never the input/output split,
    so its usage is built as unknown and cost is honestly "uncomputable": the ledger links quality evidence to the run set, it does not invent a price."""
    if not isinstance(bench, Mapping) or bench.get("schema") != "respected.eval.bench.v1" or not isinstance(bench.get("runs"), list):
        raise ValueError("not a benchmark report")
    agent = bench.get("agent") if isinstance(bench.get("agent"), Mapping) else {}
    manifest = f"{agent.get('name')}@{agent.get('version')}:{str(bench.get('commit'))[:12]}"
    kind = "real" if bench.get("kind") == "real" else "synthetic"
    out = []
    for index, run in enumerate(bench["runs"]):
        if not isinstance(run, Mapping) or run.get("arm") not in ("direct", "orchestrated"):
            continue
        seconds = run.get("duration_seconds")
        event = usage_event.from_engine_usage(None, tool=str(agent.get("name") or "unknown"), run_id=f"bench-{index}", step="worker", at="", model=agent.get("model"),
                                              billing=billing.get(str(agent.get("name")), "unknown"))
        violations = (1 if run.get("security_violation") is True else 0) if run["arm"] == "orchestrated" and run.get("security_violation") is not None else None
        record = cost_ledger.run_record(run_id=f"bench-{run.get('task_id')}-{run['arm']}-{run.get('repeat')}", task_class=f"bench:{run['arm']}", accepted=run.get("status") == "passed",
                                        elapsed_seconds=seconds if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) else None, fix_rounds=None,
                                        worker_violations=violations, events=[event], eval_kind=kind, eval_manifest=manifest)
        record["agent"], record["project"], record["failure_class"] = agent.get("name"), None, None
        out.append(record)
    return out
