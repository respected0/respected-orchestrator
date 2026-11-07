"""Loop-limited team coordination (B4-02.03): may this verified handoff be delivered?

Pure decision over the already-verified chain of earlier handoffs (handoff.inbox) and the sessions running now. It never
starts, stops or applies anything: it returns `deliver`, `duplicate`, `reject` or `escalate`, plus the sessions a caller must
stop when the loop budget is spent. There is no `apply` action here, so a handoff can never apply a patch.
Checks, in order: duplicate operation, hop budget, retry budget, recipient availability, ownership conflict, reviewer
independence, and a no-progress cycle (the same edge repeated without any new evidence)."""
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from . import recovery, roles, team_profiles


def _overlap(a: str, b: str) -> bool:
    return a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/")


def _out(action: str, reasons: list[str], envelope: Mapping[str, Any], stop: Sequence[str] = ()) -> dict[str, Any]:
    return {"accept": action == "deliver", "action": action, "reasons": reasons, "stop_sessions": sorted(stop),
            "waiting_on": envelope["to"]["profile_id"] if action == "deliver" else None, "to_operator": action == "escalate"}


def evaluate(team: Mapping[str, Any], chain: Sequence[Mapping[str, Any]], envelope: Mapping[str, Any], *, active: Mapping[str, Mapping[str, Any]] = {},
             require_independent_review: bool = False, available: Callable[[str], bool] | None = None,
             lim: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """`chain`: earlier verified envelopes of this task, oldest first. `active`: {session_id: {profile_id, paths}} running now."""
    limits = recovery.limits(lim)
    if any(e["operation_id"] == envelope["operation_id"] for e in chain):
        return _out("duplicate", ["operation_id already delivered; nothing new is started"], envelope)
    members = {m["id"]: m for m in team["members"]}
    chain_sessions = {e["from"]["session_id"] for e in chain} | {envelope["from"]["session_id"]}
    running = [s for s in active if s in chain_sessions]
    hops = len(chain) + 1
    if hops > min(envelope["max_hops"], limits["max_handoffs"]):
        return _out("escalate", [f"hop budget spent ({hops} > {min(envelope['max_hops'], limits['max_handoffs'])}); a person decides"], envelope, running)
    retries = sum(e["next_action"] == "implement" for e in chain)
    if envelope["next_action"] == "implement" and retries >= envelope["retry_budget"]:
        return _out("escalate", [f"retry budget spent ({retries} of {envelope['retry_budget']} rework handoffs used)"], envelope, running)
    if available is not None:
        state = next(s for s in team_profiles.check(team, available) if s["id"] == envelope["to"]["profile_id"])
        if state["status"] != "ok":
            return _out("reject", ["recipient unavailable: " + state["reason"]], envelope)
    reasons = []
    mine = set(envelope["scope"]["paths"])
    for session, info in active.items():
        if session == envelope["from"]["session_id"] or info.get("profile_id") == envelope["to"]["profile_id"]:
            continue
        clash = sorted(p for p in mine for q in info.get("paths", []) if _overlap(p, q))
        if clash:
            reasons.append(f"ownership conflict with running session {session}: {', '.join(clash[:3])}")
    if envelope["next_action"] == "review":
        author = members.get(envelope["from"]["profile_id"])
        reviewer = members.get(envelope["to"]["profile_id"])
        if author and reviewer and roles._same(author["assignment"], reviewer["assignment"]) and (
                require_independent_review or envelope["from"]["profile_id"] == envelope["to"]["profile_id"]):
            reasons.append("reviewer uses the same tool/profile as the author and independent review is required")
    seen = {(e["from"]["profile_id"], e["to"]["profile_id"], e["next_action"]): {(r["run_id"], r["sha256"]) for r in e["evidence"]} for e in chain}
    edge = (envelope["from"]["profile_id"], envelope["to"]["profile_id"], envelope["next_action"])
    new_evidence = {(r["run_id"], r["sha256"]) for r in envelope["evidence"]}
    if edge in seen and not (new_evidence - seen[edge]):
        reasons.append("same handoff repeated without new evidence (cycle)")
    return _out("reject" if reasons else "deliver", reasons, envelope)
