"""Cost and quality ledger (B4-04.02): deterministic, offline, and honest about what it cannot compute.

Input is a list of run records (see `run_record`) holding the run's UsageEvents and its quality facts, plus a price catalog.
The catalog is frozen into a digested snapshot so a later price edit cannot change an old report. Cost per event needs an
API-metered call, a fully known token count, a catalog price that exists, is effective and is not stale, and a single
currency; otherwise that run is "uncomputable" with the reason and the group total is None (the part that could be priced is
reported separately as `known_part`). Cached tokens are priced at the full input rate, so a cost involving cache is flagged
`upper_bound`. Reasoning tokens are assumed to be inside output tokens. Cost per accepted task counts the spend of ALL runs
(failed ones too) over the accepted ones. Nothing is ever turned into 0."""
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from . import pricing, usage_event

SCHEMA = 1
STALE_DAYS = 90
KINDS = ("synthetic", "real")


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def snapshot(catalog: Iterable[Mapping[str, Any]], at: str) -> dict[str, Any]:
    """Price entries effective at `at`, frozen with a digest."""
    stamp = datetime.fromisoformat(at)
    entries = sorted((dict(e) for e in catalog if datetime.fromisoformat(e["effective_from"]) <= stamp),
                     key=lambda e: (e["model"], e["effective_from"]))
    return {"at": at, "entries": entries, "digest": hashlib.sha256(_canon(entries).encode()).hexdigest()[:16]}


def run_record(*, run_id: str, task_class: str, accepted: bool, elapsed_seconds: float | None, fix_rounds: int | None,
               worker_violations: int | None, events: Sequence[Mapping[str, Any]], eval_kind: str | None = None,
               eval_manifest: str | None = None) -> dict[str, Any]:
    """One ledger row. Quality facts that were not measured stay None."""
    if eval_kind is not None and eval_kind not in KINDS:
        raise ValueError("eval_kind must be synthetic or real")
    return {"run_id": run_id, "task_class": task_class, "accepted": bool(accepted), "elapsed_seconds": elapsed_seconds,
            "fix_rounds": fix_rounds, "worker_violations": worker_violations, "events": list(events),
            "eval": {"kind": eval_kind, "manifest": eval_manifest}}


def effective_events(events: Iterable[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], list[str]]:
    """Deduplicate, then let a later event carrying `corrects: <event_id>` replace its target (a usage correction)."""
    unique, conflicts = usage_event.dedupe(events)
    fixes = {e["corrects"]: e for e in unique if e.get("corrects")}
    return [fixes.get(e["event_id"], e) for e in unique if not e.get("corrects")], conflicts


def event_cost(event: Mapping[str, Any], snap: Mapping[str, Any], max_age_days: int = STALE_DAYS) -> dict[str, Any]:
    """{amount, currency, upper_bound} or {amount: None, reason}."""
    def no(reason: str) -> dict[str, Any]:
        return {"amount": None, "currency": None, "reason": reason}
    if not event.get("cost_eligible"):
        return no("not_api_metered")
    if event.get("status") != "known":
        return no("usage_incomplete")
    if not event.get("model"):
        return no("model_unknown")
    cached = [event.get("cache_read_tokens"), event.get("cache_write_tokens")]
    tokens_in = event["fresh_input_tokens"] + sum(c or 0 for c in cached)
    quote = pricing.quote(snap["entries"], event["model"], tokens_in, event["output_tokens"], at=event["at"])
    if quote["amount"] is None:
        return no(quote.get("reason", "price_unknown"))
    age = datetime.fromisoformat(event["at"]) - datetime.fromisoformat(quote["effective_from"])
    if age.days > max_age_days:
        return no("price_stale")
    return {"amount": quote["amount"], "currency": quote["currency"], "upper_bound": bool(event.get("cache_read_tokens"))}


def _run_cost(run: Mapping[str, Any], snap: Mapping[str, Any], max_age_days: int) -> dict[str, Any]:
    events, conflicts = effective_events(run["events"])
    if conflicts:
        return {"amount": None, "currency": None, "reason": "conflicting_duplicate_events"}
    if not events:
        return {"amount": None, "currency": None, "reason": "no_usage_events"}
    costs = [event_cost(e, snap, max_age_days) for e in events]
    bad = next((c for c in costs if c["amount"] is None), None)
    if bad:
        return bad
    if len({c["currency"] for c in costs}) > 1:
        return {"amount": None, "currency": None, "reason": "currency_mismatch"}
    return {"amount": round(sum(c["amount"] for c in costs), 6), "currency": costs[0]["currency"],
            "upper_bound": any(c["upper_bound"] for c in costs)}


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def report(runs: Sequence[Mapping[str, Any]], snap: Mapping[str, Any], *, task_class: str | None = None,
           max_age_days: int = STALE_DAYS) -> dict[str, Any]:
    """Per-task-class groups; `task_class` filters to one. Same input gives byte-identical output (`digest`)."""
    groups: dict[str, dict[str, Any]] = {}
    for run in runs:
        if task_class is not None and run["task_class"] != task_class:
            continue
        g = groups.setdefault(run["task_class"], {"runs": 0, "accepted": 0, "costs": [], "elapsed": [], "fix_rounds": [],
                                                  "violations": [], "kinds": set(), "uncomputable": {}})
        g["runs"] += 1
        g["accepted"] += run["accepted"]
        cost = _run_cost(run, snap, max_age_days)
        g["costs"].append(cost)
        if cost["amount"] is None:
            g["uncomputable"][cost["reason"]] = g["uncomputable"].get(cost["reason"], 0) + 1
        for key, src in (("elapsed", "elapsed_seconds"), ("fix_rounds", "fix_rounds"), ("violations", "worker_violations")):
            if run[src] is not None:
                g[key].append(run[src])
        g["kinds"].add(run["eval"]["kind"])
    out_groups = {}
    for name in sorted(groups):
        g = groups[name]
        priced = [c for c in g["costs"] if c["amount"] is not None]
        currencies = {c["currency"] for c in priced}
        complete = len(priced) == g["runs"] and len(currencies) == 1
        total = round(sum(c["amount"] for c in priced), 6) if complete else None
        known_part = round(sum(c["amount"] for c in priced), 6) if len(currencies) == 1 and priced else None
        if len(currencies) > 1:
            g["uncomputable"]["currency_mismatch"] = len(priced)
        kinds = g["kinds"] - {None}
        out_groups[name] = {
            "runs": g["runs"], "accepted": g["accepted"], "acceptance_rate": round(g["accepted"] / g["runs"], 4),
            "currency": next(iter(currencies)) if complete else None, "total_cost": total, "known_part": known_part,
            "upper_bound": any(c.get("upper_bound") for c in priced), "uncomputable": dict(sorted(g["uncomputable"].items())),
            "cost_per_accepted": round(total / g["accepted"], 6) if total is not None and g["accepted"] else None,
            "cost_per_accepted_reason": None if total is not None and g["accepted"] else
            ("no_accepted_runs" if total is not None else "cost_not_computable"),
            "mean_elapsed_seconds": _mean(g["elapsed"]), "mean_fix_rounds": _mean(g["fix_rounds"]),
            "worker_violations": sum(g["violations"]) if g["violations"] else None,
            "measured": {"elapsed": len(g["elapsed"]), "fix_rounds": len(g["fix_rounds"]), "violations": len(g["violations"])},
            "evidence": "none" if not kinds else next(iter(kinds)) if len(kinds) == 1 else "mixed"}
    body = {"schema": SCHEMA, "price_snapshot": snap["digest"], "price_at": snap["at"], "max_price_age_days": max_age_days,
            "groups": out_groups}
    return {**body, "digest": hashlib.sha256(_canon(body).encode()).hexdigest()[:16]}


def diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Per-group change between two reports. A delta exists only when both sides have the number (and, for cost, the same
    currency and the same price snapshot); otherwise it is None with the reason."""
    out: dict[str, Any] = {}
    for name in sorted(set(before["groups"]) | set(after["groups"])):
        a, b = before["groups"].get(name), after["groups"].get(name)
        if a is None or b is None:
            out[name] = {"status": "only_in_" + ("after" if a is None else "before")}
            continue
        cost_ok = a["cost_per_accepted"] is not None and b["cost_per_accepted"] is not None and a["currency"] == b["currency"]
        if cost_ok and before["price_snapshot"] != after["price_snapshot"]:
            cost_ok, why = False, "price_snapshot_differs"
        else:
            why = None if cost_ok else "cost_not_comparable"
        va, vb = a["worker_violations"], b["worker_violations"]
        out[name] = {"status": "compared",
                     "acceptance_rate_delta": round(b["acceptance_rate"] - a["acceptance_rate"], 4),
                     "cost_per_accepted_delta": round(b["cost_per_accepted"] - a["cost_per_accepted"], 6) if cost_ok else None,
                     "cost_reason": why,
                     "worker_violations_delta": vb - va if va is not None and vb is not None else None}
    return out
