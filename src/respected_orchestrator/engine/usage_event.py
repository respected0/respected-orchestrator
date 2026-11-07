"""Typed usage events with provenance (B4-04.01).

One `UsageEvent` per model call, built from what a provider or CLI actually reported. A value the tool did not report (or
reported as something other than a non-negative integer) is None and its provenance says "absent" or "invalid": it is
never coerced to zero and never filled in. Whether cached tokens are part of the input count differs by tool, so the
event records the semantics it was built under; fresh input is derived only when they are known to be included.
`billing` says how the call is paid for: a subscription call never becomes an API cost (`cost_eligible` is False).
Events carry counts and ids only, no prompt, output or credential text."""
import hashlib
from collections.abc import Iterable, Mapping
from typing import Any

SCHEMA = 1
COUNTS = ("fresh_input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens")
BILLING = ("api_metered", "subscription", "unknown")
CACHE_SEMANTICS = ("included_in_input", "separate", "unknown")


def _count(value: Any) -> tuple[int | None, str]:
    if value is None:
        return None, "absent"
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None, "invalid"
    return value, "reported"


def make(*, tool: str, run_id: str, step: str, at: str, counts: Mapping[str, Any], model: str | None = None,
         model_version: str | None = None, billing: str = "unknown", cache_semantics: str = "unknown", source: str = "cli") -> dict[str, Any]:
    """Build one event from raw per-field counts (keys from COUNTS; anything else is ignored)."""
    if billing not in BILLING or cache_semantics not in CACHE_SEMANTICS:
        raise ValueError("billing or cache_semantics is not a known value")
    values, provenance = {}, {}
    for field in COUNTS:
        values[field], provenance[field] = _count(counts.get(field))
    reported = [f for f in COUNTS if provenance[f] == "reported"]
    status = "unknown" if not reported else "known" if (values["fresh_input_tokens"] is not None and values["output_tokens"] is not None) else "partial"
    ident = hashlib.sha256(f"{run_id}|{step}|{tool}".encode()).hexdigest()[:16]
    return {"schema": SCHEMA, "event_id": ident, "run_id": run_id, "step": step, "at": at, "tool": tool, "source": source,
            "model": model, "model_version": model_version, **values, "provenance": provenance, "status": status,
            "cache_semantics": cache_semantics, "billing": billing, "cost_eligible": billing == "api_metered"}


def from_engine_usage(usage: Mapping[str, Any] | None, **meta: Any) -> dict[str, Any]:
    """Adapter for the engine's usage dict (runner._usage / codex): raw_input_tokens INCLUDES cached_input_tokens, so fresh input is
    raw minus cached; None / {} (a launched worker that reported nothing) gives a status "unknown" event."""
    usage = usage if isinstance(usage, Mapping) else {}
    raw, _ = _count(usage.get("raw_input_tokens"))
    cached, cached_state = _count(usage.get("cached_input_tokens"))
    fresh = raw - cached if raw is not None and cached is not None and raw >= cached else None
    counts = {"fresh_input_tokens": fresh, "cache_read_tokens": cached, "output_tokens": usage.get("output_tokens"),
              "reasoning_tokens": usage.get("reasoning_tokens")}
    event = make(counts=counts, cache_semantics="included_in_input", **meta)
    if raw is not None and cached is not None and raw < cached:
        event["provenance"]["fresh_input_tokens"] = "invalid"  # cached larger than the whole input: contradictory report
    elif fresh is not None:
        event["provenance"]["fresh_input_tokens"] = "derived"
    return event


def from_chat_event(chat: Mapping[str, Any], **meta: Any) -> dict[str, Any]:
    """Adapter for a normalised chat_session `usage` event. Its input/cache relation is not verified, so semantics stay "unknown"
    and nothing is derived; the stream's own `cost` is deliberately ignored (price comes from the catalog, see pricing.py)."""
    counts = {"fresh_input_tokens": chat.get("input"), "cache_read_tokens": chat.get("cache_read"), "cache_write_tokens": chat.get("cache_write"),
              "output_tokens": chat.get("output"), "reasoning_tokens": chat.get("reasoning")}
    return make(counts=counts, source="session", cache_semantics="unknown", **meta)


def dedupe(events: Iterable[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], list[str]]:
    """(events with each event_id once, ids whose repeat carried different numbers). The first copy wins, so a replay never double counts."""
    kept: dict[str, Mapping[str, Any]] = {}
    conflicts: list[str] = []
    for event in events:
        old = kept.setdefault(event["event_id"], event)
        if old is not event and any(old[f] != event[f] for f in COUNTS) and event["event_id"] not in conflicts:
            conflicts.append(event["event_id"])
    return list(kept.values()), conflicts


def totals(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-field sums over deduplicated events. A field no event reported is None, not 0; `unknown_events` counts events missing it."""
    unique, conflicts = dedupe(events)
    out: dict[str, Any] = {"events": len(unique), "conflicts": conflicts, "fields": {}}
    for field in COUNTS:
        known = [e[field] for e in unique if e[field] is not None]
        out["fields"][field] = {"total": sum(known) if known else None, "events_missing": len(unique) - len(known)}
    out["status"] = "none" if not unique else "known" if all(e["status"] == "known" for e in unique) else \
        "unknown" if all(e["status"] == "unknown" for e in unique) else "partial"
    return out
