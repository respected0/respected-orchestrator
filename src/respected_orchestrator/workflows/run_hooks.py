"""Thin connectors that put the Beta.4 decision modules into the run path (create_task / retry_task) without changing what they decide.

  apply_profile   a request may name a team profile (`profile`); it becomes an *explicit* assignment for its engine role unless the
                  request states that role itself (explicit > profile, never the reverse). The run stores the profile's frozen
                  snapshot and a fresh session id, so editing the profile later cannot rewrite old evidence.
  route           when (and only when) the implementer came from the automatic path, routing_policy.decide is consulted. Default mode
                  is shadow: it only logs. `active` may replace the automatic pick; an explicit or configured assignment never changes.
  retry_guard     retry_task asks recovery.decide before it claims anything; a refusal carries the table's reason.
Everything here is a function of its inputs plus files under the data root; nothing starts a process."""
from collections.abc import Callable, Mapping
from typing import Any

import datetime as dt

from ..context import EngineContext
from . import recovery, roles, routing_policy, team_profiles
from ..engine import failures, task_classifier


def apply_profile(ctx: EngineContext, request: Mapping[str, Any], explicit: dict[str, Any], workflow: dict[str, Any],
                  settings: Mapping[str, Any], tools: list[str]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """(explicit roles with the profile merged in, profile reference to store). Raises ValueError for an unusable profile."""
    wanted = request.get("profile")
    if wanted is None:
        return explicit, None
    if not isinstance(wanted, str):
        raise ValueError("profile must be a team profile id")
    try:
        team = team_profiles.load(ctx.data_root, tools, settings)
    except team_profiles.ProfileError as error:
        raise ValueError(f"Team profiles unreadable: {error.message}") from error
    member = next((m for m in team["members"] if m["id"] == wanted), None)
    if member is None:
        raise ValueError(f"Unknown team profile {wanted!r}")
    kind = request.get("kind", "write")
    if kind == "write" and member["role"] not in ("implementer", "designer"):
        raise ValueError(f"Profile {wanted!r} has role {member['role']}; only implementer or designer profiles can run a write task")
    if kind == "write" and "write" not in member["capabilities"]:
        raise ValueError(f"Profile {wanted!r} is not allowed to write")
    if kind == "read" and "read" not in member["capabilities"]:
        raise ValueError(f"Profile {wanted!r} is not allowed to read")
    merged = dict(explicit)
    merged.setdefault("implementer", {k: member["assignment"][k] for k in ("tool", "profile") if member["assignment"].get(k) is not None})
    cap = (member.get("budget") or {}).get("max_weighted_tokens")
    if cap is not None:
        current = workflow.get("max_weighted_tokens")
        workflow["max_weighted_tokens"] = cap if current is None else min(current, cap)  # a profile budget only ever lowers a lane budget
    return merged, team_profiles.new_session(member)


def route(ctx: EngineContext, settings: Mapping[str, Any], request: Mapping[str, Any], assigned: dict[str, Any], tools: list[str],
          available: Callable[[str], bool], history: Callable[[], Mapping], ownership: list[str], acceptance: list[Any]) -> list[dict[str, Any]] | None:
    """Consult the routing policy for every role the automatic path chose (an explicit or configured role is never looked at).
    Returns what to store (one entry per such role) or None when nothing applies."""
    mode = routing_policy.mode_of(settings)
    auto_roles = [role for role, value in assigned.items() if isinstance(value, dict) and value.get("source") == "auto"]
    if mode == "off" or not auto_roles:
        return None
    try:
        pool = [roles.normalize("reviewer", item, tools=tools) for item in roles._json_setting(settings, "auto_pool", list)]
    except (ValueError, TypeError, roles.RoleError):
        return None
    risk = task_classifier.classify({"kind": request.get("kind", "write"), "task": request.get("task"), "ownership": ownership, "acceptance": acceptance})
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    ctx.data_root.mkdir(parents=True, exist_ok=True)  # the log lives beside the runs; the first task may be the first thing written
    out = []
    for role in auto_roles:
        current = assigned[role]
        candidates = [{"tool": c["tool"] or current["tool"], "profile": c["profile"] or "", "available": available(c["tool"] or current["tool"]),
                       "quota": "unknown"} for c in pool]
        decision = routing_policy.decide(settings, role, risk, candidates, actual=current, history=history, at=now)
        routing_policy.record(ctx.data_root, decision, role, current, now)
        suggestion = decision["suggestion"] or {}
        entry = {"role": role, "mode": decision["mode"], "risk": risk["level"], "differs": decision["differs"],
                 "suggested": suggestion.get("selection"), "basis": suggestion.get("basis")}
        if decision["effective"]:
            assigned[role] = {**decision["effective"], "fallbacks": [], "source": "auto", "basis": "routing_policy", "reason": suggestion["reason"]}
            entry["applied"] = True
        out.append(entry)
    return out


def retry_guard(ctx: EngineContext, run_id: str, request: Mapping[str, Any], status: Mapping[str, Any], inspect_run: Callable[[EngineContext, str], Mapping],
                operator_resume: bool = False) -> None:
    """Raise ValueError unless the recovery table allows one more automatic retry of this run."""
    chain: dict[str, int] = {}
    parent = request.get("retry_of")
    while parent and len(chain) < 5:  # earlier attempts of the same task: their failure classes feed the per-class cap
        try:
            earlier = inspect_run(ctx, parent)
        except (OSError, ValueError, KeyError):
            break
        klass = failures.describe(earlier.get("reason"), earlier.get("provider_status")).get("failure_class")
        if klass:
            chain[klass] = chain.get(klass, 0) + 1
        parent = (earlier.get("request") or {}).get("retry_of")
    state = {"attempts": request.get("retry_depth", 0) + 1, "by_class": chain}
    decision = recovery.decide(status.get("reason"), status.get("provider_status"), state, {"max_attempts": 3}, operator_resume=operator_resume)
    if decision["action"] != "retry" and decision["why"] != "unclassified_failure":  # unclassified keeps the engine's older behaviour
        raise ValueError(f"Recovery policy: {decision['action']} ({decision['why']}); a person decides")
