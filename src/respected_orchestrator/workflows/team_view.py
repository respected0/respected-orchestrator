"""Read model for the team screen (B4-02.04): the team, who can run right now, and the handoff/recovery history, all derived from
signed or verified records. It is a projection of the event store, not a second database; nothing here writes."""
from collections.abc import Callable, Mapping
from typing import Any

from ..context import EngineContext
from ..engine.journal import Journal, mask
from . import handoff, team_commands, team_profiles

MAX_EVENTS = 100
KINDS = (handoff.EVENT, team_commands.ESCALATED, "recovery.case_opened", "recovery.operator_action")


def view(ctx: EngineContext, settings: Mapping[str, Any], tools: list[str], available: Callable[[str], bool]) -> dict[str, Any]:
    try:
        team = team_profiles.load(ctx.data_root, tools, settings)
    except team_profiles.ProfileError as error:
        return {"ok": False, "problem": {"code": error.code, "message": error.message}, "team": None, "history": []}
    state = {s["id"]: s for s in team_profiles.check(team, available)}
    members = [{"id": m["id"], "name": m["name"], "role": m["role"], "rev": m["rev"], "tool": m["assignment"]["tool"], "profile": m["assignment"]["profile"],
                "capabilities": m["capabilities"], "status": state[m["id"]]["status"], "reason": state[m["id"]]["reason"]} for m in team["members"]]
    history, rejected = [], 0
    names = {m["id"]: m["name"] for m in team["members"]}
    for record in Journal(ctx.state_dir / "events.log").scan():
        if record["type"] not in KINDS:
            continue
        body = record["p"]
        if record["type"] == handoff.EVENT:
            env = body.get("envelope") if isinstance(body, Mapping) else None
            if not isinstance(env, Mapping) or body.get("sig") != handoff.signature(ctx, dict(env)):
                rejected += 1  # never shown as history
                continue
            history.append({"seq": record["seq"], "kind": "handoff", "from": names.get(env["from"]["profile_id"], env["from"]["profile_id"]),
                            "to": names.get(env["to"]["profile_id"], env["to"]["profile_id"]), "action": env["next_action"], "reason": env["reason"], "hop": env["hop"],
                            "max_hops": env["max_hops"], "note": env.get("note", ""), "handoff_id": env["handoff_id"], "run": record.get("run") or None})
        else:
            clean = mask(body) if isinstance(body, Mapping) else {}
            history.append({"seq": record["seq"], "kind": record["type"].split(".", 1)[1], "run": record.get("run"), "detail": clean})
    return {"ok": True, "team": {"id": team["id"], "name": team["name"]}, "members": members, "history": history[-MAX_EVENTS:], "rejected_records": rejected,
            "stale_note": "history is read from the event store each time; refresh to see new handoffs"}
