"""Local budget and success read model for the desktop screen (B4-04.03). Privacy-first: it reads this installation's own signed run evidence,
sends nothing anywhere, and `usage_collection=false` turns it off completely.

Honesty rules the screen relies on:
  * actual (reported by a tool), estimate (priced from a catalog) and unknown are three separate columns, never summed into one number;
  * a percentage appears only when its denominator is meaningful (`MIN_SAMPLE` runs); otherwise the rate is None with the reason;
  * the budget status is `ok` only when every run in the window reported its usage; any unknown run makes it `unknown_possible_overrun`,
    so a missing measurement can never look green;
  * quota stops (provider limits, 429 bursts) are counted on their own and raised as a warning."""
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import failures, ledger_source

MIN_SAMPLE = 5
NEAR = 0.8
MAX_ROWS = 50


def _bucket(runs: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        groups.setdefault(str(run.get(key) or "unknown"), []).append(run)
    return [dict(name=name, **_stats(items)) for name, items in sorted(groups.items())]


def _stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = sum(r["accepted"] for r in runs)
    known = [e for r in runs for e in r["events"][:1] if e["status"] == "known"]  # one worker event per run is the run's own usage
    tokens = sum((e["fresh_input_tokens"] or 0) + (e["cache_read_tokens"] or 0) + (e["output_tokens"] or 0) for e in known)
    quota = sum(1 for r in runs if r.get("failure_class") == "quota")
    return {"runs": len(runs), "accepted": accepted,
            "acceptance_rate": round(accepted / len(runs), 4) if len(runs) >= MIN_SAMPLE else None,
            "rate_note": None if len(runs) >= MIN_SAMPLE else f"fewer than {MIN_SAMPLE} runs: no percentage is shown",
            "tokens_actual": tokens if known else None, "runs_with_usage": len(known), "runs_without_usage": len(runs) - len(known),
            "quota_stops": quota}


def summary(ctx: Any, settings: Mapping[str, Any], *, limit: int = 400) -> dict[str, Any]:
    if settings.get("usage_collection") is False:
        return {"enabled": False, "reason": "usage_collection is off: nothing was read or computed"}
    runs = ledger_source.runs(Path(ctx.data_root), limit=limit)
    stats = _stats(runs)
    budget = settings.get("budget_weighted_tokens")
    budget = budget if type(budget) is int and budget > 0 else None
    if budget is None:
        status, why = "no_budget", "no token budget is set"
    elif stats["runs_without_usage"]:
        status = "over" if (stats["tokens_actual"] or 0) >= budget else "unknown_possible_overrun"
        why = f"{stats['runs_without_usage']} run(s) reported no usage, so the real total may be higher"
    else:
        used = stats["tokens_actual"] or 0
        status = "over" if used >= budget else "near" if used >= NEAR * budget else "ok"
        why = f"{used} of {budget} tokens reported"
    warnings = []
    if stats["quota_stops"]:
        warnings.append({"kind": "quota_stops", "message": f"{stats['quota_stops']} run(s) stopped on a provider limit"})
    if stats["runs_without_usage"]:
        warnings.append({"kind": "unknown_usage", "message": f"{stats['runs_without_usage']} of {stats['runs']} run(s) did not report token usage"})
    rows = [{"run_id": r["run_id"], "agent": r.get("agent"), "accepted": r["accepted"], "tokens_actual": _stats([r])["tokens_actual"],
             "failure_class": r.get("failure_class")} for r in runs[:MAX_ROWS]]
    return {"enabled": True, "window_runs": len(runs), "totals": stats,
            "by_agent": _bucket(runs, "agent"), "by_project": _bucket(runs, "project"),
            "estimate": {"status": "not_computed", "reason": "no price catalog is configured; costs are unknown, never zero"},
            "budget": {"limit": budget, "status": status, "why": why}, "warnings": warnings, "runs": rows,
            "counts_by_failure": dict(Counter(r.get("failure_class") or "none" for r in runs))}
