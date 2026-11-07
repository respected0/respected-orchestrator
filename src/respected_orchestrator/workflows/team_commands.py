"""Operations behind the `team`, `handoff` and `inbox` commands: the first path where a handoff really travels between runs.

Who is handing over is never taken from the message. A handoff is proposed *for a run*: the engine reads that run's own signed
request, which holds the frozen profile snapshot and the run's session id (written by create_task), and uses the run's
ownership as the sender's granted scope. The chain of earlier handoffs is rebuilt from signed `parent` links, `team_loop`
decides, and only a `deliver` decision is written to the event store. An `escalate` decision is recorded as an event for a
person (`handoff.escalated`) and nothing is delivered. Nothing here starts a worker, stops one or applies a patch."""
from collections.abc import Callable, Mapping
from typing import Any

from ..context import EngineContext
from ..engine.evidence import load_signed
from ..engine.journal import Journal
from . import handoff, team_loop, team_profiles

ESCALATED = "handoff.escalated"


def show(ctx: EngineContext, settings: Mapping[str, Any], tools: list[str]) -> dict[str, Any]:
    return team_profiles.load(ctx.data_root, tools, settings)


def save(ctx: EngineContext, request: Any, settings: Mapping[str, Any], tools: list[str]) -> dict[str, Any]:
    """stdin {team: {...}}. `rev` of each changed profile is bumped against what is stored now."""
    if not isinstance(request, Mapping) or set(request) != {"team"}:
        raise ValueError('team save expects {"team": {...}}')
    try:
        stored = (ctx.data_root / team_profiles.FILE).is_file()  # a team derived from settings is not a stored version to bump against
        previous = team_profiles.load(ctx.data_root, tools, settings) if stored else None
        return team_profiles.save(ctx.data_root, request["team"], tools, previous=previous)
    except team_profiles.ProfileError as error:
        raise ValueError(f"{error.code}: {error.message}") from error


def active_sessions(ctx: EngineContext, limit: int = 200) -> dict[str, dict[str, Any]]:
    """{session_id: {profile_id, paths}} for runs that carry a profile reference and have not finished."""
    out: dict[str, dict[str, Any]] = {}
    for index, directory in enumerate(sorted((ctx.data_root / "state").glob("run-*"), reverse=True)):
        if index >= limit:
            break
        try:
            request, status = load_signed(ctx, directory / "request.json"), load_signed(ctx, directory / "status.json")
        except (OSError, ValueError):
            continue
        ref = request.get("profile_ref")
        if ref and status.get("status") in ("queued", "running"):
            out[ref["session_id"]] = {"profile_id": ref["profile"]["profile_id"], "paths": list(request.get("ownership", []))}
    return out


def post(ctx: EngineContext, request: Any, settings: Mapping[str, Any], tools: list[str], available: Callable[[str], bool]) -> dict[str, Any]:
    """stdin {run_id, message}. Returns the loop decision and, when delivered, the handoff id."""
    if not isinstance(request, Mapping) or set(request) != {"run_id", "message"} or not isinstance(request["message"], Mapping):
        raise ValueError('handoff expects {"run_id": "...", "message": {...}}')
    run = load_signed(ctx, ctx.run_dir(request["run_id"]) / "request.json")
    ref = run.get("profile_ref")
    if not ref:
        raise ValueError("This run was not started from a team profile, so it cannot hand work over")
    team = team_profiles.load(ctx.data_root, tools, settings)
    parent = (run.get("handoff_ref") or {}).get("handoff_id")
    try:
        chain = handoff.chain_of(ctx, parent)
        message = {**request["message"], "hop": len(chain) + 1}  # the position in the chain is the engine's count, not the sender's claim
        sender = {"profile_id": ref["profile"]["profile_id"], "session_id": ref["session_id"]}
        envelope = handoff.parse(ctx, team, message, sender=sender, granted_scope=run.get("ownership", []), parent=parent)
    except handoff.HandoffError as error:
        if error.code == "MAX_HOP_EXCEEDED":  # the chain is already at the sender's own limit: that is an escalation, not a typo
            running = sorted(s for s in active_sessions(ctx) if s in {e["from"]["session_id"] for e in chain} | {ref["session_id"]})
            Journal(ctx.state_dir / "events.log").append(f"esc-{request['run_id']}-{len(chain) + 1}", ESCALATED, request["run_id"],
                                                         {"handoff_id": None, "from": ref["profile"]["profile_id"], "to": (request["message"].get("to") if isinstance(request["message"].get("to"), str) else None),
                                                          "reasons": [f"hop budget spent: {error.message}"], "stop_sessions": running})
            return {"accept": False, "action": "escalate", "reasons": [f"hop budget spent: {error.message}"], "stop_sessions": running, "waiting_on": None, "to_operator": True}
        return {"accept": False, "action": "invalid", "code": error.code, "reasons": [error.message], "stop_sessions": [], "to_operator": False}
    decision = team_loop.evaluate(team, chain, envelope, active=active_sessions(ctx),
                                  require_independent_review=bool(settings.get("require_independent_review")), available=available)
    if decision["action"] == "deliver":
        record = handoff.post(ctx, envelope)
        return {**decision, "handoff_id": envelope["handoff_id"], "stored": record is not None}
    if decision["action"] == "escalate":
        Journal(ctx.state_dir / "events.log").append(f"esc-{envelope['operation_id']}", ESCALATED, request["run_id"],
                                                     {"handoff_id": envelope["handoff_id"], "from": envelope["from"]["profile_id"],
                                                      "to": envelope["to"]["profile_id"], "reasons": decision["reasons"], "stop_sessions": decision["stop_sessions"]})
    return decision


def inbox(ctx: EngineContext, profile_id: str, settings: Mapping[str, Any], tools: list[str]) -> dict[str, Any]:
    team = team_profiles.load(ctx.data_root, tools, settings)
    if profile_id not in {m["id"] for m in team["members"]}:
        raise ValueError(f"Unknown team profile {profile_id!r}")
    return handoff.inbox(ctx, team["id"], profile_id)


def link(ctx: EngineContext, request: Mapping[str, Any]) -> dict[str, Any] | None:
    """create_task helper: a run that continues a handoff must name a verified handoff addressed to its own profile."""
    wanted = request.get("handoff")
    if wanted is None:
        return None
    if not isinstance(wanted, str) or not request.get("profile"):
        raise ValueError("handoff needs a handoff id and the profile that received it")
    envelope = handoff.find(ctx, wanted)
    if envelope is None:
        raise ValueError(f"Unknown or unverifiable handoff {wanted!r}")
    if envelope["to"]["profile_id"] != request["profile"]:
        raise ValueError("That handoff is addressed to a different profile")
    return {"handoff_id": envelope["handoff_id"], "from": envelope["from"]["profile_id"], "hop": envelope["hop"], "next_action": envelope["next_action"]}
