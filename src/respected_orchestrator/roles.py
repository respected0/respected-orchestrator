"""Vendor-neutral role assignment (docs/decisions/ROLE_ASSIGNMENT.md).

Roles (implementer, reviewer, planner, ...) name a job. A profile names a model/provider configuration. A tool names
the CLI that executes it. No code here (or anywhere that calls it) may tie a model to a role: every profile is eligible
for every role. Priority: explicit task assignment > Hub-configured default > automatic recommendation (opt-in).
An explicit assignment is never replaced silently; an unusable one is an error unless it lists its own fallbacks."""
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .context import safe_path

ROLE_RE = re.compile(r"[a-z][a-z0-9_]{0,39}\Z")
KNOWN_ROLES = ("master", "planner", "implementer", "reviewer", "deep_reviewer", "debugger", "tester", "coordinator")
SOURCES = ("explicit", "hub_default", "auto")
DEFAULT_TOOL = "codex"
DEFAULT_BLOCKED = "mimo"  # a user-editable deny list for whole profiles, never a model-to-role rule


class RoleError(ValueError):
    def __init__(self, code: str, message: str, hint: str = ""):
        super().__init__(message)
        self.code, self.message, self.hint = code, message, hint


def settings_fields(tools: list[str]) -> list[dict[str, Any]]:
    """Hub-visible settings owned by role assignment (appended to the RPP settings schema)."""
    return [
        {"key": "default_reviewer_tool", "type": "enum", "label": "Default reviewer tool", "default": DEFAULT_TOOL,
         "secret": False, "enum": tools},
        {"key": "default_roles", "type": "string", "secret": False, "default": "",
         "label": "Default assignments for any role (JSON: {\"planner\": {\"tool\": \"claude\", \"profile\": \"...\"}})"},
        {"key": "auto_assign", "type": "boolean", "label": "Recommend assignments when none exists",
         "default": False, "secret": False},
        {"key": "auto_pool", "type": "string", "secret": False, "default": "",
         "label": "Automatic assignment pool (JSON list of {\"tool\": ..., \"profile\": ...})"},
        {"key": "require_independent_review", "type": "boolean", "label": "Reviewer must differ from implementer",
         "default": False, "secret": False},
        {"key": "mcp_acceptance_allow", "type": "string", "secret": False, "default": "",
         "label": "Acceptance/verify commands an AI client may add over MCP (JSON list of command prefixes, e.g. [[\"python\", \"-m\", \"pytest\"]])"},
        {"key": "blocked_profiles", "type": "string", "label": "Blocked profile names (comma separated)",
         "default": DEFAULT_BLOCKED, "secret": False},
    ]


def read_settings(data_root: Path) -> dict[str, Any]:
    path = safe_path(data_root / "settings.json")
    try:
        stored = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def blocked_profiles(settings: Mapping[str, Any]) -> list[str]:
    raw = settings.get("blocked_profiles", DEFAULT_BLOCKED)
    return [part.strip().casefold() for part in str(raw).split(",") if part.strip()] if isinstance(raw, str) else []


def refuse_blocked(settings: Mapping[str, Any], *profiles: str | None) -> None:
    blocked = blocked_profiles(settings)
    for profile in profiles:
        if profile and any(name in profile.casefold() for name in blocked):
            raise RoleError("PROFILE_BLOCKED", f"Profile {profile!r} is blocked by the blocked_profiles setting",
                            "Choose another profile or edit blocked_profiles in the Orchestrator settings.")


def _json_setting(settings: Mapping[str, Any], key: str, kind: type) -> Any:
    raw = settings.get(key)
    if raw in (None, ""):
        return kind()
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, kind):
        raise ValueError(f"{key} must be a JSON {kind.__name__}")
    return value


def normalize(role: str, raw: Any, *, tools: list[str]) -> dict[str, Any]:
    """{tool, profile, fallbacks, source?} from a profile string or an object; tool/profile None = unspecified.

    `source` is only present on assignments this module resolved earlier (a stored task being retried or re-checked)."""
    if not isinstance(role, str) or not ROLE_RE.fullmatch(role):
        raise RoleError("BAD_ROLE", f"Invalid role name {role!r}", "Roles are lowercase words like reviewer or debugger.")
    if isinstance(raw, str):
        raw = {"profile": raw}
    if not isinstance(raw, Mapping) or set(raw) - {"tool", "profile", "fallbacks", "source", "fallback_of", "reason"}:
        raise RoleError("BAD_ASSIGNMENT", f"Assignment for {role} must be a profile name or an object with tool/profile/fallbacks")
    tool, profile = raw.get("tool"), raw.get("profile")
    if tool is not None and (not isinstance(tool, str) or tool not in tools):
        raise RoleError("BAD_ASSIGNMENT", f"Unsupported tool {tool!r} for role {role}", "Supported tools: " + ", ".join(tools))
    if profile is not None and (not isinstance(profile, str) or not re.fullmatch(r"[A-Za-z0-9._:/@+ -]{0,100}", profile) or profile.strip().startswith("-")):
        raise RoleError("BAD_ASSIGNMENT", f"Profile for role {role} must be a plain model/profile name (letters, digits, . _ : / @ + -)")
    fallbacks = raw.get("fallbacks", [])
    if not isinstance(fallbacks, list) or len(fallbacks) > 5:
        raise RoleError("BAD_ASSIGNMENT", f"Fallbacks for role {role} must be a list of at most 5 assignments")
    entry = {"tool": tool, "profile": profile.strip() if profile is not None else None,
             "fallbacks": [normalize(role, item, tools=tools) for item in fallbacks]}
    if raw.get("source") in SOURCES:
        entry["source"] = raw["source"]
    return entry


def acceptance_allowed(settings: Mapping[str, Any], command: Any) -> bool:
    """Is `command` (an argv list) covered by a prefix the user listed in `mcp_acceptance_allow`? Empty list = nothing is."""
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        return False
    try:
        prefixes = _json_setting(settings, "mcp_acceptance_allow", list)
    except (ValueError, TypeError):
        return False
    return any(isinstance(p, list) and p and all(isinstance(x, str) for x in p) and command[:len(p)] == p for p in prefixes)


def validate_settings(settings: Mapping[str, Any], tools: list[str]) -> list[dict[str, str]]:
    errors = []
    try:
        for index, prefix in enumerate(_json_setting(settings, "mcp_acceptance_allow", list)):
            if not isinstance(prefix, list) or not prefix or not all(isinstance(part, str) and part for part in prefix):
                raise ValueError(f"entry {index} must be a non-empty list of command words")
    except (ValueError, TypeError) as error:
        errors.append({"key": "mcp_acceptance_allow", "message": str(error)})
    try:
        for role, value in _json_setting(settings, "default_roles", dict).items():
            normalize(role, value, tools=tools)
    except (ValueError, TypeError) as error:
        errors.append({"key": "default_roles", "message": str(error)})
    try:
        for index, value in enumerate(_json_setting(settings, "auto_pool", list)):
            if not isinstance(value, Mapping) or not isinstance(value.get("tool"), str) or not isinstance(value.get("profile", ""), str):
                raise ValueError(f"entry {index} must be {{\"tool\": ..., \"profile\": ...}}")
            normalize("reviewer", value, tools=tools)
    except (ValueError, TypeError) as error:
        errors.append({"key": "auto_pool", "message": str(error)})
    return errors


def _hub_defaults(settings: Mapping[str, Any], tools: list[str]) -> dict[str, dict[str, Any]]:
    """Role -> assignment configured in the Hub. Legacy keys map to implementer/reviewer; default_roles wins."""
    defaults = {
        "implementer": {"tool": settings.get("default_worker") or DEFAULT_TOOL,
                        "profile": settings.get("default_worker_profile") or "", "fallbacks": []},
    }
    if settings.get("default_reviewer_profile"):
        defaults["reviewer"] = {"tool": settings.get("default_reviewer_tool") or DEFAULT_TOOL,
                                "profile": settings["default_reviewer_profile"], "fallbacks": []}
    for role, value in _json_setting(settings, "default_roles", dict).items():
        # An object the user wrote for this role is an assignment even with an empty profile (= the tool's own model).
        defaults[role] = {**normalize(role, value, tools=tools), "configured": True}
    return defaults


def _usable(candidate: Mapping[str, Any], available: Callable[[str], bool], settings: Mapping[str, Any]) -> str | None:
    """None when usable, else the reason it is not."""
    try:
        refuse_blocked(settings, candidate["profile"])
    except RoleError as error:
        return error.message
    return None if available(candidate["tool"]) else f"tool {candidate['tool']!r} is not installed"


def _same(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if left.get("profile") or right.get("profile"):
        return (left.get("profile") or "").casefold() == (right.get("profile") or "").casefold()
    return left.get("tool") == right.get("tool")


WRITE_ROLES = {"implementer", "debugger"}
WRITE_TOOLS = {"codex", "claude", "gemini", "agy", "antigravity"}  # tools command_for can let edit files headlessly


def _smoothed(row: Mapping[str, Any] | None) -> float:
    return ((row["ok"] + 1) / (row["runs"] + 2)) if row else 0.5  # Laplace: few runs stay near "unknown"


def recommend(role, pool, settings, available, fallback_tool, peers, history):
    """Rank the auto_pool for `role` by measured track record (track_record.stats) and explain the result.

    Capability filter: write roles need a tool that can edit headlessly, read roles cannot use `custom`. Ranking key:
    smoothed success rate, then using a profile no other role already uses (soft), then lower average tokens, then pool
    order. With fewer than MIN_RUNS recorded runs for every candidate there is no evidence: the first candidate is
    returned and the reason says it is only the first listed, not a recommendation."""
    from .track_record import MIN_RUNS
    family = "write" if role in WRITE_ROLES else "read"
    table = history() if history else {}
    rows, excluded = [], []
    for index, entry in enumerate(pool):
        candidate = {"tool": entry["tool"] or fallback_tool, "profile": entry["profile"] or ""}
        problem = _usable(candidate, available, settings)
        if problem is None and ((family == "write" and candidate["tool"] not in WRITE_TOOLS)
                                or (family == "read" and candidate["tool"] == "custom")):
            problem = f"tool {candidate['tool']!r} cannot do {role} work"
        if problem is not None:
            excluded.append({**candidate, "excluded": problem})
            continue
        stat = table.get((family, candidate["tool"], candidate["profile"]))
        rows.append({**candidate, "runs": stat["runs"] if stat else 0, "ok": stat["ok"] if stat else 0,
                     "avg_tokens": stat["avg_tokens"] if stat else None, "score": round(_smoothed(stat), 3),
                     "shared": any(_same(candidate, peer) for peer in peers), "index": index})
    if not rows:
        return None
    informed = any(row["runs"] >= MIN_RUNS for row in rows)
    rows.sort(key=lambda r: (-r["score"] if informed else 0, r["shared"], r["avg_tokens"] if r["avg_tokens"] is not None else 1 << 60, r["index"]))
    best = rows[0]
    if informed:
        reason = (f"best measured record among {len(rows)} usable candidate(s): {best['ok']}/{best['runs']} {family} runs completed"
                  f" (smoothed {best['score']})" + ("; profile also used by another role (no unshared one ranked higher)" if best["shared"] else ""))
    else:
        reason = (f"no candidate has {MIN_RUNS}+ recorded {family} runs: this is the first usable entry of auto_pool, "
                  "not a measured recommendation")
    ranking = [{k: row[k] for k in ("tool", "profile", "runs", "ok", "avg_tokens", "score")} for row in rows]
    return {"tool": best["tool"], "profile": best["profile"], "fallbacks": [], "source": "auto", "basis": "history" if informed else "pool_order",
            "reason": reason, "ranking": ranking, "excluded": excluded}


def resolve(settings: Mapping[str, Any], requested: Mapping[str, Any], needed: list[str], *, tools: list[str],
            available: Callable[[str], bool], check_roles: set[str] | None = None, optional: list[str] = (),
            history: Callable[[], Mapping] | None = None) -> dict[str, dict[str, Any]]:
    """Resolve every needed role to {tool, profile, source[, reason, fallback_of]} or raise one RoleError.

    `requested` holds the task prompt's explicit assignments (profile string or {tool, profile, fallbacks}). Extra
    requested roles beyond `needed` are validated and kept so any role can be represented.
    Tool availability is enforced only for `check_roles` (None = all): a reviewer's CLI is checked when its review is
    about to run, not when the task is created. Blocked profiles are always refused."""
    explicit = {role: normalize(role, value, tools=tools) for role, value in requested.items()}
    defaults = _hub_defaults(settings, tools)
    auto = bool(settings.get("auto_assign"))
    pool = [normalize("reviewer", item, tools=tools) for item in _json_setting(settings, "auto_pool", list)]
    resolved: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for role in dict.fromkeys([*needed, *optional, *explicit]):
        asked = explicit.get(role)
        hub = defaults.get(role)
        fallback_tool = (hub or {}).get("tool") or settings.get("default_reviewer_tool" if "review" in role else "default_worker") or DEFAULT_TOOL
        if asked is not None:  # explicit: a partial assignment is completed only with a tool default, never another model
            chosen = {"tool": asked["tool"] or fallback_tool, "profile": asked["profile"] or "",
                      "fallbacks": asked["fallbacks"], "source": asked.get("source", "explicit")}
        elif hub is not None and (hub["profile"] or role == "implementer" or hub.get("configured")):
            chosen = {**{k: v for k, v in hub.items() if k != "configured"}, "tool": hub["tool"] or fallback_tool, "profile": hub["profile"] or "", "source": "hub_default"}
        else:
            chosen = None
        if chosen is None and auto and role not in explicit:
            chosen = recommend(role, pool, settings, available, fallback_tool,
                               [v for k, v in resolved.items() if k != role], history)
        if chosen is None:
            if role in needed:
                missing.append(role)
            continue
        enforce = available if check_roles is None or role in check_roles else (lambda _tool: True)
        problem = _usable(chosen, enforce, settings)
        if problem is not None:
            for option in chosen["fallbacks"]:  # fallbacks are the user's own authorization; used in order
                candidate = {"tool": option["tool"] or chosen["tool"], "profile": option["profile"] or ""}
                if _usable(candidate, enforce, settings) is None:
                    chosen = {**candidate, "fallbacks": [], "source": chosen["source"], "fallback_of": problem}
                    problem = None
                    break
            if problem is not None:
                raise RoleError("ROLE_UNAVAILABLE", f"Role {role} is assigned ({chosen['source']}) but unusable: {problem}",
                                "Fix the assignment, install the tool, or list explicit fallbacks for this role. "
                                "Nothing was substituted.")
        resolved[role] = {k: v for k, v in chosen.items() if k != "fallbacks" or v}
    if missing:
        raise RoleError("ROLE_UNASSIGNED", "No assignment for role(s): " + ", ".join(missing),
                        "Assign them in the task, set Hub defaults, or enable auto_assign with an auto_pool.")
    return resolved


def check_independence(roles: Mapping[str, Mapping[str, Any]], required: bool) -> list[str]:
    """Reviewers sharing the implementer's model are allowed (explicit choice) unless independence is required."""
    implementer = roles.get("implementer")
    warnings = []
    if implementer is not None:
        for role in ("reviewer", "deep_reviewer"):
            if role in roles and _same(roles[role], implementer):
                if required:
                    raise RoleError("ROLE_INDEPENDENCE", f"{role} must differ from the implementer when independent review is required",
                                    "Assign another profile or turn off require_independent_review.")
                warnings.append(f"{role}_same_profile_as_implementer")
    return warnings
