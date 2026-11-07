"""Handoff envelope and mailbox (B4-02.02).

An agent that wants to pass work on proposes a small, closed-shape message. The engine turns it into a signed envelope and
appends it to the event store; nothing in it is a permission. The recipient's authority is whatever its own profile
(team_profiles.py) and the normal role resolver already allow, and a handoff can only narrow scope, never widen it:
every path must lie inside what the sender itself was granted. The sender is taken from the engine's own knowledge of the
acting session, never from the message; evidence references must verify against this installation's signed run evidence;
free text (`note`) is stored masked and never interpreted; `next_action` is a closed enum that must suit the recipient's role.
Raw transcripts are not carried: only ids, hashes, paths and one short note. This module posts and reads; the hop and retry
limits that stop loops are enforced by the coordinator (B4-02.03)."""
import hashlib
import json
import posixpath
import re
from collections.abc import Collection, Mapping
from typing import Any

from ..context import EngineContext
from ..engine.evidence import load_signed, signature
from ..engine.journal import Journal, mask

SCHEMA = 1
EVENT = "handoff.posted"
REASONS = ("work_done", "needs_review", "needs_test", "blocked", "out_of_scope", "retry_exhausted")
ACTIONS = {"implement": {"implementer", "designer"}, "review": {"reviewer"}, "test": {"qa"}, "design": {"designer"},
           "escalate": {"lead"}, "stop": {"lead", "implementer", "reviewer", "qa", "designer"}}
KEYS = {"from", "to", "scope", "evidence", "reason", "note", "next_action", "hop", "max_hops", "retry_budget", "operation_id"}
MAX_RAW_BYTES, MAX_ENVELOPE_BYTES, MAX_PATHS, MAX_EVIDENCE, MAX_NOTE, HOP_CAP, RETRY_CAP = 8192, 4096, 50, 10, 200, 8, 5
_OP = re.compile(r"[A-Za-z0-9._:-]{1,80}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RUN = re.compile(r"run-[A-Za-z0-9_-]{1,80}\Z")


class HandoffError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _path(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise HandoffError("BAD_SCOPE", "scope paths must be non-empty strings")
    text = value.strip().replace("\\", "/")
    if text.startswith("/") or re.match(r"[A-Za-z]:", text) or ".." in text.split("/"):
        raise HandoffError("BAD_SCOPE", f"scope path must be relative and stay inside the project: {value!r}")
    return posixpath.normpath(text)


def _inside(path: str, granted: Collection[str]) -> bool:
    return any(path == g or path.startswith(g.rstrip("/") + "/") for g in granted)


def parse(ctx: EngineContext, team: Mapping[str, Any], raw: Any, *, sender: Mapping[str, Any], granted_scope: Collection[str],
          parent: str | None = None) -> dict[str, Any]:
    """Validated envelope from an untrusted proposal. `sender` = {profile_id, session_id} as known to the engine;
    `granted_scope` = the paths the sending run owns. Raises HandoffError with a stable code."""
    if not isinstance(raw, Mapping) or len(json.dumps(raw, default=str)) > MAX_RAW_BYTES:
        raise HandoffError("TOO_LARGE" if isinstance(raw, Mapping) else "BAD_MESSAGE", "handoff must be a small JSON object")
    if set(raw) - KEYS:
        raise HandoffError("BAD_MESSAGE", "unknown fields: " + ", ".join(sorted(set(raw) - KEYS)))
    members = {m["id"]: m for m in team["members"]}
    me = members.get(sender.get("profile_id"))
    session = sender.get("session_id")
    if me is None or not isinstance(session, str) or not session.startswith("ss-"):
        raise HandoffError("UNKNOWN_SENDER", "the acting profile or session is not known to the team")
    claimed = raw.get("from")
    if claimed is not None and claimed != {"profile_id": me["id"], "session_id": session}:
        raise HandoffError("SPOOFED_SENDER", "the message claims a different sender than the acting session")
    to = (raw.get("to") or {}).get("profile_id") if isinstance(raw.get("to"), Mapping) else raw.get("to")
    if not isinstance(to, str) or to not in members:
        raise HandoffError("UNKNOWN_RECIPIENT", "recipient is missing or not a profile of this team")
    if to == me["id"]:
        raise HandoffError("SELF_HANDOFF", "a profile cannot hand work to itself")
    action = raw.get("next_action")
    if action not in ACTIONS or members[to]["role"] not in ACTIONS[action]:
        raise HandoffError("ACTION_ROLE_MISMATCH", f"next_action {action!r} does not suit a {members[to]['role']} recipient")
    reason = raw.get("reason")
    if reason not in REASONS:
        raise HandoffError("BAD_REASON", "reason must be one of " + ", ".join(REASONS))
    note = raw.get("note", "")
    if not isinstance(note, str) or len(note) > MAX_NOTE or any(ord(c) < 32 and c not in "\n\t" for c in note):
        raise HandoffError("BAD_NOTE", f"note must be text of at most {MAX_NOTE} characters")
    paths = (raw.get("scope") or {}).get("paths", []) if isinstance(raw.get("scope", {}), Mapping) else None
    if not isinstance(paths, list) or len(paths) > MAX_PATHS:
        raise HandoffError("BAD_SCOPE", f"scope.paths must be a list of at most {MAX_PATHS} paths")
    paths = sorted({_path(p) for p in paths})
    granted = {_path(g) for g in granted_scope}
    outside = [p for p in paths if not _inside(p, granted)]
    if outside:
        raise HandoffError("SCOPE_WIDENING", f"a handoff cannot grant paths the sender does not own: {', '.join(outside[:3])}")
    evidence = raw.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE:
        raise HandoffError("BAD_EVIDENCE", f"evidence must be a list of at most {MAX_EVIDENCE} references")
    refs = []
    for ref in evidence:
        if not isinstance(ref, Mapping) or set(ref) != {"run_id", "sha256"} or not _RUN.fullmatch(str(ref["run_id"])) or not _SHA.fullmatch(str(ref["sha256"])):
            raise HandoffError("BAD_EVIDENCE", "each evidence reference is {run_id, sha256}")
        try:
            actual = load_signed(ctx, ctx.run_dir(ref["run_id"]) / "result.json").get("patch_sha256")
        except (OSError, ValueError, KeyError):
            actual = None
        if actual != ref["sha256"]:
            raise HandoffError("FORGED_EVIDENCE", f"{ref['run_id']}: no signed result with that patch hash")
        refs.append({"run_id": ref["run_id"], "sha256": ref["sha256"]})
    ints = {}
    for key, low, high in (("hop", 1, HOP_CAP), ("max_hops", 1, HOP_CAP), ("retry_budget", 0, RETRY_CAP)):
        value = raw.get(key, 1 if key == "hop" else 3 if key == "max_hops" else 2)
        if type(value) is not int or not low <= value <= high:
            raise HandoffError("BAD_LIMIT", f"{key} must be an integer from {low} to {high}")
        ints[key] = value
    if ints["hop"] > ints["max_hops"]:
        raise HandoffError("MAX_HOP_EXCEEDED", "hop is already beyond max_hops")
    op = raw.get("operation_id")
    if op is None:
        op = "ho-" + hashlib.sha256(json.dumps([session, to, action, paths, refs, ints["hop"], parent], sort_keys=True).encode()).hexdigest()[:20]
    elif not isinstance(op, str) or not _OP.fullmatch(op):
        raise HandoffError("BAD_OPERATION_ID", "operation_id must be 1-80 of letters, digits . _ : -")
    envelope = {"schema": SCHEMA, "handoff_id": "ho-" + hashlib.sha256(op.encode()).hexdigest()[:16], "operation_id": op, "team_id": team["id"],
                "from": {"profile_id": me["id"], "rev": me["rev"], "session_id": session},
                "to": {"profile_id": to, "role": members[to]["role"]}, "scope": {"paths": paths}, "evidence": refs,
                "reason": reason, "note": note, "next_action": action, **ints, "parent": parent, "authority": "none"}
    envelope = mask(envelope)  # masked BEFORE signing, so the stored copy verifies
    if len(json.dumps(envelope)) > MAX_ENVELOPE_BYTES:
        raise HandoffError("TOO_LARGE", f"envelope exceeds {MAX_ENVELOPE_BYTES} bytes")
    return envelope


def post(ctx: EngineContext, envelope: Mapping[str, Any], *, journal: Journal | None = None) -> dict[str, Any] | None:
    """Sign and append to the event store. Returns the stored record, or None when this operation_id was already posted."""
    store = journal or Journal(ctx.state_dir / "events.log")
    return store.append(envelope["operation_id"], EVENT, None, {"envelope": dict(envelope), "sig": signature(ctx, dict(envelope))})


def inbox(ctx: EngineContext, team_id: str, profile_id: str, *, journal: Journal | None = None, after: int = 0) -> dict[str, Any]:
    """Verified envelopes addressed to `profile_id`, oldest first. Records whose signature fails are counted, never returned."""
    store = journal or Journal(ctx.state_dir / "events.log")
    messages, rejected = [], 0
    for record in store.scan(after):
        if record["type"] != EVENT:
            continue
        body = record["p"]
        env = body.get("envelope") if isinstance(body, Mapping) else None
        if not isinstance(env, Mapping) or body.get("sig") != signature(ctx, dict(env)):
            rejected += 1
            continue
        if env.get("team_id") == team_id and (env.get("to") or {}).get("profile_id") == profile_id:
            messages.append({"seq": record["seq"], **env})
    return {"messages": messages, "rejected": rejected}


def find(ctx: EngineContext, handoff_id: str, *, journal: Journal | None = None) -> dict[str, Any] | None:
    """The verified envelope with this id, or None (unknown id or a record whose signature fails)."""
    store = journal or Journal(ctx.state_dir / "events.log")
    for record in store.scan():
        body = record["p"]
        env = body.get("envelope") if record["type"] == EVENT and isinstance(body, Mapping) else None
        if isinstance(env, Mapping) and env.get("handoff_id") == handoff_id and body.get("sig") == signature(ctx, dict(env)):
            return {"seq": record["seq"], **env}
    return None


def chain_of(ctx: EngineContext, handoff_id: str | None, *, limit: int = 20) -> list[dict[str, Any]]:
    """Verified envelopes from the first handoff of a task chain up to `handoff_id`, following `parent` links (oldest first)."""
    out: list[dict[str, Any]] = []
    while handoff_id and len(out) < limit:
        env = find(ctx, handoff_id)
        if env is None:
            raise HandoffError("BROKEN_CHAIN", f"handoff {handoff_id} is unknown or its record does not verify")
        out.append(env)
        handoff_id = env.get("parent")
    return list(reversed(out))
