"""Activity timeline over the event journal (B3-06.01).

A read model only: the journal stays the one source. Pages are keyed by `seq` (monotonic, survives rotation), so a
reconnecting UI resumes exactly where it was and is told when events before its cursor no longer exist. Event types this
code does not know are shown, not dropped (`stage: "unknown"`), with every string cleaned of terminal control codes and
bounded, so a hostile payload can neither flood nor steer the screen.
"""
from __future__ import annotations

import json
import re

MAX_PAGE = 200
STAGES = ("queued", "running", "review", "approval", "done", "failed", "cancelled", "other", "unknown")
_KEYWORDS = (("queue", "queued"), ("cancel", "cancelled"), ("fail", "failed"), ("error", "failed"), ("timeout", "failed"),
             ("approv", "approval"), ("apply", "approval"), ("applied", "approval"), ("review", "review"),
             ("complet", "done"), ("done", "done"), ("start", "running"), ("resum", "running"), ("run", "running"))
_CONTROL = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # whole CSI/OSC sequences first, then stray controls
_SKEW = 5.0  # seconds a timestamp may trail the previous event before it is flagged


def stage_of(event_type):
    if not isinstance(event_type, str):
        return "unknown"
    if event_type.startswith("journal."):
        return "other"
    low = event_type.casefold()
    return next((stage for word, stage in _KEYWORDS if word in low), "unknown")


def clean(value, limit=300, depth=0):
    if isinstance(value, str):
        return _CONTROL.sub("", value)[:limit]
    if isinstance(value, dict) and depth < 4:
        return {clean(str(k), 80): clean(v, limit, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list) and depth < 4:
        return [clean(v, limit, depth + 1) for v in value[:40]]
    return value if isinstance(value, (int, float, bool)) or value is None else clean(str(value), limit)


def _entry(record, previous_ts):
    ts = record.get("ts")
    payload = record.get("p") if isinstance(record.get("p"), dict) else {}
    return {"seq": record["seq"], "ts": ts if isinstance(ts, (int, float)) else None, "op": clean(str(record.get("op")), 80),
            "run": clean(str(record["run"]), 80) if record.get("run") else None, "type": clean(str(record.get("type")), 80),
            "stage": stage_of(record.get("type")), "payload": clean(payload),
            "out_of_order": isinstance(ts, (int, float)) and previous_ts is not None and ts < previous_ts - _SKEW}


def _matches(entry, run, op, stages, types, agent, needle):
    if run and entry["run"] != run or op and entry["op"] != op:
        return False
    if stages and entry["stage"] not in stages:
        return False
    if types and not any(entry["type"] == t or entry["type"].startswith(t.rstrip("*")) and t.endswith("*") for t in types):
        return False
    if agent and agent not in (str(entry["payload"].get("agent")), str(entry["payload"].get("worker"))):
        return False
    return not needle or needle in json.dumps(entry, ensure_ascii=False).casefold()


def timeline(journal, *, cursor=0, limit=50, run=None, op=None, stages=None, types=None, agent=None, query=None):
    """Oldest-first page of matching events after `cursor`. `next_cursor` is the last scanned seq (also when nothing matched)."""
    if type(limit) is not int or type(cursor) is not int or cursor < 0:
        raise ValueError("cursor and limit must be non-negative integers")
    limit = max(1, min(limit, MAX_PAGE))
    stages = set(stages or ())
    if not stages <= set(STAGES):
        raise ValueError("Unknown stage filter")
    if any(not isinstance(v, str) for v in (run, op, agent, query) if v is not None) or any(not isinstance(t, str) for t in types or ()):
        raise ValueError("Filters must be strings")
    needle = clean(query).casefold() if query else ""
    entries, first_seq, last_scanned, previous_ts, more = [], None, cursor, None, False
    for record in journal.scan(0):  # a cheap decode-only pass; the cursor skips below it without building entries
        if first_seq is None:
            first_seq = record["seq"]
        if record["seq"] <= cursor:
            previous_ts = record.get("ts") if isinstance(record.get("ts"), (int, float)) else previous_ts
            continue
        entry = _entry(record, previous_ts)
        previous_ts = entry["ts"] if entry["ts"] is not None else previous_ts
        if len(entries) >= limit:
            more = True
            break
        last_scanned = record["seq"]
        if _matches(entry, run, op, stages, types, agent, needle):
            entries.append(entry)
    return {"events": entries, "next_cursor": last_scanned, "has_more": more, "last_seq": journal.last_seq, "first_seq": first_seq,
            "missing_before": bool(first_seq and cursor and cursor < first_seq - 1),  # events the cursor expected were rotated away
            "corrupt": journal.corrupt}
