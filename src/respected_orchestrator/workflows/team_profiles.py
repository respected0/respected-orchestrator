"""Versioned team and agent-profile data contract (B4-02.01).

A *profile* is a durable identity (id, display name, team role, tool/model assignment, budget, allowed capabilities). A
*session* is one live run of it and has its own id: a profile is never a session. Editing a profile bumps its `rev` and
changes its `digest`; a run records the frozen `snapshot()` it started with, so a later edit cannot rewrite old evidence.
A profile only names what the existing role resolver (roles.py) may be asked for: `requested()` turns a team into the
`requested` argument of `roles.resolve`, so explicit > default > auto precedence, blocked profiles and "unusable stays an
error" are unchanged. Nothing here starts a process, widens a permission or substitutes a missing tool.

Unknown keys are refused, which keeps raw secrets and ad-hoc privilege fields out of the file; string values that look like a
credential are refused too. Capabilities must agree with the role and tool (a reviewer or QA profile can never be given
"write")."""
import hashlib
import json
import re
import secrets
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..context import atomic_write_json, safe_path
from ..engine.task_classifier import _SECRET_TEXT
from . import roles

SCHEMA = 1
FILE = "teams.json"
TEAM_ROLES = ("lead", "implementer", "reviewer", "qa", "designer")
ENGINE_ROLE = {"lead": "coordinator", "implementer": "implementer", "reviewer": "reviewer", "qa": "tester", "designer": "designer"}
CAPABILITIES = ("read", "write", "review", "test")
ROLE_CAPS = {"lead": {"read"}, "implementer": {"read", "write", "test"}, "reviewer": {"read", "review"},
             "qa": {"read", "test"}, "designer": {"read", "write"}}  # ceiling per role; a profile may hold a subset
ID_RE = re.compile(r"[a-z][a-z0-9-]{1,39}\Z")
MAX_BUDGET = 50_000_000
MEMBER_KEYS = {"id", "role", "name", "assignment", "capabilities", "budget", "rev"}


class ProfileError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:16]


def _no_secret(value: Any, where: str) -> None:
    for item in value.values() if isinstance(value, Mapping) else value if isinstance(value, list) else [value]:
        if isinstance(item, (Mapping, list)):
            _no_secret(item, where)
        elif isinstance(item, str) and _SECRET_TEXT.search(item):
            raise ProfileError("SECRET_IN_PROFILE", f"{where} looks like it contains a credential; profiles never store secrets")


def validate_member(raw: Any, tools: list[str]) -> dict[str, Any]:
    """Normalised profile or ProfileError. `rev` defaults to 1 for a new profile."""
    if not isinstance(raw, Mapping) or set(raw) - MEMBER_KEYS:
        extra = sorted(set(raw) - MEMBER_KEYS) if isinstance(raw, Mapping) else []
        raise ProfileError("BAD_PROFILE", "profile must be an object with only " + ", ".join(sorted(MEMBER_KEYS)) + (f" (unknown: {', '.join(extra)})" if extra else ""))
    pid, role = raw.get("id"), raw.get("role")
    if not isinstance(pid, str) or not ID_RE.fullmatch(pid) or pid.startswith("ss-"):
        raise ProfileError("BAD_ID", "profile id must be a lowercase slug of 2-40 characters and must not look like a session id (ss-...)")
    if role not in TEAM_ROLES:
        raise ProfileError("BAD_ROLE", f"role must be one of {', '.join(TEAM_ROLES)}")
    name = raw.get("name", pid)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60 or any(ord(c) < 32 for c in name):
        raise ProfileError("BAD_NAME", "name must be 1-60 printable characters")
    caps = raw.get("capabilities", sorted(ROLE_CAPS[role]))
    if not isinstance(caps, list) or any(c not in CAPABILITIES for c in caps) or len(set(caps)) != len(caps):
        raise ProfileError("BAD_CAPABILITY", "capabilities must be a list of unique values from " + ", ".join(CAPABILITIES))
    if set(caps) - ROLE_CAPS[role]:
        raise ProfileError("PRIVILEGE_ESCALATION", f"role {role} may not hold: {', '.join(sorted(set(caps) - ROLE_CAPS[role]))}")
    try:
        assignment = roles.normalize(ENGINE_ROLE[role], raw.get("assignment", {}), tools=tools)
    except roles.RoleError as error:
        raise ProfileError("BAD_ASSIGNMENT", error.message) from error
    if "write" in caps and assignment["tool"] not in roles.WRITE_TOOLS | {None}:
        raise ProfileError("PRIVILEGE_ESCALATION", f"tool {assignment['tool']!r} cannot edit files, so the profile cannot hold write")
    budget = raw.get("budget")
    if budget is not None and (not isinstance(budget, Mapping) or set(budget) - {"max_weighted_tokens"}
                               or type(budget.get("max_weighted_tokens")) is not int or not 1 <= budget["max_weighted_tokens"] <= MAX_BUDGET):
        raise ProfileError("BAD_BUDGET", f"budget must be {{\"max_weighted_tokens\": 1..{MAX_BUDGET}}}")
    rev = raw.get("rev", 1)
    if type(rev) is not int or rev < 1:
        raise ProfileError("BAD_REV", "rev must be a positive integer")
    member = {"id": pid, "role": role, "name": name.strip(), "assignment": {k: assignment[k] for k in ("tool", "profile", "fallbacks")},
              "capabilities": sorted(caps), "budget": dict(budget) if budget else None, "rev": rev}
    _no_secret({k: v for k, v in member.items() if k != "id"}, f"profile {pid}")
    return member


def validate_team(raw: Any, tools: list[str]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or raw.get("schema") != SCHEMA or set(raw) - {"schema", "id", "name", "members"}:
        raise ProfileError("BAD_TEAM", f"team must be schema {SCHEMA} with id, name, members")
    if not isinstance(raw.get("id"), str) or not ID_RE.fullmatch(raw["id"]) or not isinstance(raw.get("name", ""), str):
        raise ProfileError("BAD_ID", "team id must be a lowercase slug of 2-40 characters")
    members = [validate_member(m, tools) for m in raw.get("members", [])] if isinstance(raw.get("members", []), list) else None
    if members is None or len(members) > 20:
        raise ProfileError("BAD_TEAM", "members must be a list of at most 20 profiles")
    ids = [m["id"] for m in members]
    if len(set(ids)) != len(ids):
        raise ProfileError("DUPLICATE_ID", "profile ids must be unique within a team")
    return {"schema": SCHEMA, "id": raw["id"], "name": raw.get("name") or raw["id"], "members": members}


def migrate(raw: Any, tools: list[str], settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Current-schema team from: a v1 team (validated), nothing (a team derived from the existing role settings), or refuses a
    newer/unknown schema instead of guessing."""
    if raw is None:
        return from_settings(settings or {}, tools)
    if isinstance(raw, Mapping) and raw.get("schema") == SCHEMA:
        return validate_team(raw, tools)
    raise ProfileError("UNSUPPORTED_SCHEMA", f"teams file schema {raw.get('schema') if isinstance(raw, Mapping) else raw!r} is not supported (expected {SCHEMA})")


def from_settings(settings: Mapping[str, Any], tools: list[str]) -> dict[str, Any]:
    """The default team a person already has: implementer/reviewer (and any default_roles entry for a team role) lifted from settings."""
    configured = roles._configured_defaults(settings, tools)
    members = []
    for role in TEAM_ROLES:
        cfg = configured.get(ENGINE_ROLE[role])
        if cfg is not None:
            members.append(validate_member({"id": role, "role": role, "name": role.capitalize(),
                                            "assignment": {k: cfg.get(k) for k in ("tool", "profile")}}, tools))
    return {"schema": SCHEMA, "id": "default", "name": "Default", "members": members}


def load(data_root: Path, tools: list[str], settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    path = safe_path(Path(data_root) / FILE)
    try:
        raw = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        raw = None
    except (OSError, ValueError) as error:
        raise ProfileError("UNREADABLE", f"{FILE} is unreadable: {error}") from error
    return migrate(raw, tools, settings)


def save(data_root: Path, team: Mapping[str, Any], tools: list[str], previous: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate, bump `rev` of every profile whose content changed versus `previous`, write atomically. Returns what was written."""
    new = validate_team(team, tools)
    old = {m["id"]: m for m in (previous or {}).get("members", [])}
    for m in new["members"]:
        before = old.get(m["id"])
        if before is not None:
            same = {k: v for k, v in m.items() if k != "rev"} == {k: v for k, v in before.items() if k != "rev"}
            m["rev"] = before["rev"] if same else before["rev"] + 1
    atomic_write_json(Path(data_root) / FILE, new)
    return new


def snapshot(member: Mapping[str, Any]) -> dict[str, Any]:
    """Frozen reference a run stores: profile id, rev and a digest of the whole profile. Later edits never touch it."""
    return {"profile_id": member["id"], "rev": member["rev"], "digest": _digest(member), "role": member["role"],
            "assignment": json.loads(json.dumps(member["assignment"]))}


def new_session(member: Mapping[str, Any]) -> dict[str, Any]:
    """A fresh session identity for a profile. The session id never equals, nor is derived from, the profile id."""
    return {"session_id": "ss-" + secrets.token_hex(8), "profile": snapshot(member)}


def requested(team: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Engine role -> assignment, for `roles.resolve(requested=...)`. Only the assignment travels; capabilities and budget stay here."""
    return {ENGINE_ROLE[m["role"]]: {k: m["assignment"][k] for k in ("tool", "profile", "fallbacks")} for m in team["members"]}


def check(team: Mapping[str, Any], available: Callable[[str], bool]) -> list[dict[str, Any]]:
    """Per profile: ok, or why it is unusable now (tool removed/uninstalled). Never swaps in another tool."""
    out = []
    for m in team["members"]:
        tool = m["assignment"]["tool"]
        ok = tool is None or available(tool)
        out.append({"id": m["id"], "role": m["role"], "status": "ok" if ok else "tool_missing",
                    "reason": None if ok else f"tool {tool!r} is not installed; nothing was substituted"})
    return out
