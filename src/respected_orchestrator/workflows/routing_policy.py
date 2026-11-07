"""Policy-based candidate choice for a role (B4-01.02). A suggestion only: nothing here starts, changes or applies anything.

Sits on top of the role resolver (roles.py): an explicit user assignment is returned untouched, so there is no silent
override. For everything else each candidate is checked (tool can do the work, available, quota, price, budget, history)
and every rejected candidate says why. Cost is never invented: no catalog entry or no expected usage means "unknown",
and under a budget an unknown cost excludes the candidate instead of counting as zero. A risk of high or unknown demands
measured history; a lower risk may rank on little data and the reason says so."""
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..engine import pricing
from ..engine.task_classifier import LEVELS
from ..engine.track_record import MIN_RUNS
from .roles import WRITE_ROLES, WRITE_TOOLS, _smoothed

SCHEMA = 1
STRICT = ("high", "unknown")  # risk levels that need measured history before a candidate is suggested


def _cost(candidate: Mapping[str, Any], catalog: Sequence[Mapping[str, Any]], usage: Mapping[str, Any] | None, at: str) -> dict[str, Any]:
    model = candidate.get("price_model")
    if not model or not usage:
        return {"status": pricing.UNKNOWN, "amount": None, "currency": None, "reason": "model_or_usage_unknown"}
    try:
        quoted = pricing.quote(catalog, model, usage.get("input"), usage.get("output"), at=at)
    except (ValueError, KeyError, TypeError):
        return {"status": pricing.UNKNOWN, "amount": None, "currency": None, "reason": "price_invalid"}
    return {k: quoted.get(k) for k in ("status", "amount", "currency", "reason")}


def suggest(role: str, risk: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], *, explicit: Mapping[str, Any] | None = None,
            history: Callable[[], Mapping] | None = None, catalog: Sequence[Mapping[str, Any]] = (), expected_usage: Mapping[str, Any] | None = None,
            budget: Mapping[str, Any] | None = None, at: str) -> dict[str, Any]:
    """Suggestion for `role`. candidates: {tool, profile, available, quota?: "ok"|"exhausted"|"unknown", price_model?, model_version?,
    history_version?}. budget: {max_amount, currency}. `risk` is a task_classifier result."""
    level = risk.get("level") if isinstance(risk, Mapping) and risk.get("level") in LEVELS else "unknown"
    base = {"schema": SCHEMA, "role": role, "risk_level": level, "applied": False}
    if explicit is not None:  # manual lock: the policy cannot change or even rank around it
        return {**base, "selection": dict(explicit), "basis": "explicit", "excluded": [], "ranking": [],
                "reason": "explicit assignment kept; the policy suggests nothing else"}
    family = "write" if role in WRITE_ROLES else "read"
    table = history() if history else {}
    rows, excluded = [], []
    for index, candidate in enumerate(candidates):
        tool, profile = candidate.get("tool"), candidate.get("profile") or ""
        stat = table.get((family, tool, profile))
        no = []
        if not candidate.get("available"):
            no.append("tool_unavailable")
        if (family == "write" and tool not in WRITE_TOOLS) or (family == "read" and tool == "custom"):
            no.append("tool_cannot_do_role")
        if candidate.get("quota") == "exhausted":
            no.append("quota_exhausted")
        drifted = bool(candidate.get("model_version") and candidate.get("model_version") != candidate.get("history_version"))
        if drifted:
            stat = None  # a different model version has not earned the old record
        runs = stat["runs"] if stat else 0
        if level in STRICT and runs < MIN_RUNS:
            no.append("version_changed_no_history" if drifted else "insufficient_history_for_risk")
        cost = _cost(candidate, catalog, expected_usage, at)
        if budget:
            if cost["amount"] is None:
                no.append("cost_unknown_under_budget")
            elif cost["currency"] != budget.get("currency") or cost["amount"] > budget.get("max_amount", 0):
                no.append("over_budget")
        if no:
            excluded.append({"tool": tool, "profile": profile, "reasons": no})
            continue
        rows.append({"tool": tool, "profile": profile, "runs": runs, "ok": stat["ok"] if stat else 0, "score": round(_smoothed(stat), 3),
                     "cost": cost, "index": index})
    if not rows:
        return {**base, "selection": None, "basis": "none", "ranking": [], "excluded": excluded,
                "reason": "no usable candidate" + ("" if candidates else " (candidate list is empty)")}
    informed = any(r["runs"] >= MIN_RUNS for r in rows)
    rows.sort(key=lambda r: (-r["score"] if informed else 0, r["cost"]["amount"] is None, r["cost"]["amount"] or 0, r["index"]))
    best = rows[0]
    reason = (f"best measured record among {len(rows)} candidate(s): {best['ok']}/{best['runs']} {family} runs completed" if informed else
              f"fewer than {MIN_RUNS} recorded {family} runs for every candidate: ordered by cost then list order, not a measured recommendation")
    if best["cost"]["amount"] is None:
        reason += "; cost unknown"
    ranking = [{k: r[k] for k in ("tool", "profile", "runs", "ok", "score", "cost")} for r in rows]
    return {**base, "selection": {"tool": best["tool"], "profile": best["profile"]}, "basis": "history" if informed else "list_order",
            "reason": reason, "ranking": ranking, "excluded": excluded}


MODES = ("off", "shadow", "active")
LOG_NAME = "routing-log.jsonl"


def mode_of(settings: Mapping[str, Any]) -> str:
    """The routing mode from settings. Default and any unreadable value is "shadow" (suggest only); "off" is the kill switch."""
    value = settings.get("routing_mode")
    return value if value in MODES else "shadow"


def decide(settings: Mapping[str, Any], role: str, risk: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]], *,
           explicit: Mapping[str, Any] | None = None, actual: Mapping[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
    """Suggestion kept apart from execution. `effective` is what routing wants used instead of the existing resolver's choice
    (`actual`): None unless mode is "active" and the policy found a candidate. Mode is read on every call, so switching it off
    mid-task takes effect on the next decision; an explicit assignment is never replaced in any mode."""
    mode = mode_of(settings)
    if mode == "off":
        return {"mode": mode, "suggestion": None, "effective": None, "differs": False}
    suggestion = suggest(role, risk, candidates, explicit=explicit, **kw)
    chosen = suggestion["selection"]
    effective = dict(chosen) if mode == "active" and chosen and suggestion["basis"] != "explicit" else None
    compared = chosen if suggestion["basis"] != "explicit" else None
    differs = bool(compared and actual and (compared["tool"], compared["profile"]) != (actual.get("tool"), actual.get("profile") or ""))
    return {"mode": mode, "suggestion": suggestion, "effective": effective, "differs": differs}


def record(data_root: Any, decision: Mapping[str, Any], role: str, actual: Mapping[str, Any] | None, at: str) -> None:
    """Append one line per decision so suggestion/execution differences can be audited later. Never raises into the task."""
    import json
    suggestion = decision.get("suggestion") or {}
    line = {"at": at, "role": role, "mode": decision["mode"], "suggested": suggestion.get("selection"), "basis": suggestion.get("basis"),
            "actual": {"tool": actual.get("tool"), "profile": actual.get("profile") or ""} if actual else None,
            "effective": decision["effective"], "differs": decision["differs"]}
    try:
        with open(Path(data_root) / LOG_NAME, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(line, separators=(",", ":")) + "\n")
    except OSError:
        pass
