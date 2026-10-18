"""Per-lane token budget and honest usage accounting (A4).

Provider usage arrives only when a turn completes. A step that ran but reported nothing (timeout, disconnect, killed
worker) is UNKNOWN, never zero: it is reported as such and, for the budget check only, charged an explicit assumed
amount. A step that never started (refused before launch) costs nothing and is not counted at all."""
from collections.abc import Iterable, Mapping
from typing import Any

UNKNOWN_STEP_TOKENS_DEFAULT = 50_000  # assumed charge per unknown step; reported separately, never merged into usage
MAX_BUDGET = 50_000_000
FIELDS = ("raw_input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "estimated_weighted_tokens")
CACHED_WEIGHT = 0.03  # same weighting as the engine's estimated_weighted_tokens


def _known(usage: Any) -> bool:
    value = usage.get("estimated_weighted_tokens") if isinstance(usage, Mapping) else None
    return isinstance(value, int) and not isinstance(value, bool)


def worker_step(engine_result: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """usage dict (KNOWN), {} (UNKNOWN: the worker was launched but reported no usage) or None (never launched)."""
    usage = engine_result.get("usage")
    if _known(usage):
        return usage
    return {} if engine_result.get("workspace") else None


def review_step(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    usage = entry.get("usage")
    return usage if _known(usage) else {}  # a review call that was made and reported nothing is UNKNOWN


def summarize(steps: Iterable[Mapping[str, Any] | None]) -> dict[str, Any]:
    totals = {field: 0 for field in FIELDS}
    known = unknown = 0
    for usage in steps:
        if usage is None:
            continue
        if _known(usage):
            known += 1
            for field in FIELDS:
                value = usage.get(field)
                if isinstance(value, int) and not isinstance(value, bool):
                    totals[field] += value
        else:
            unknown += 1
    status = "NONE" if not (known or unknown) else "KNOWN" if not unknown else "UNKNOWN" if not known else "PARTIAL"
    return {"usage": totals, "usage_status": status, "known_steps": known, "unknown_steps": unknown}


def committed(summary: Mapping[str, Any], unknown_step_tokens: int) -> int:
    """Budget basis: known weighted tokens plus an explicit assumed charge for every unknown step."""
    return summary["usage"]["estimated_weighted_tokens"] + summary["unknown_steps"] * unknown_step_tokens


def cached_cost_share(usage: Mapping[str, int]) -> float | None:
    """Share of the weighted tokens that is cached-input re-reading (what a long tool-heavy turn pays again each step)."""
    weighted = usage.get("estimated_weighted_tokens") or 0
    return round(round(usage.get("cached_input_tokens", 0) * CACHED_WEIGHT) / weighted, 3) if weighted else None
