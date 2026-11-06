"""Role / tool / profile editor model (B3-07.02).

Three things stay separate: the *role* (implementer, reviewer, ...), the *tool* (a CLI) and the *profile* (a model name).
This module only reads and proposes. It never writes settings: `plan_edit` returns the exact diff and the candidate
`default_roles` text, which the operator applies through the normal settings call. Precedence is the resolver's own
(task request > configured default > auto suggestion) and every row says where its value comes from. A suggestion is
shown next to the assignment and is never copied into it.
"""
from __future__ import annotations

import copy
import json

from . import roles

STANDARD_ROLES = ("implementer", "reviewer", "tester", "planner", "debugger", "deep_reviewer")
MAX_EDITS = 20
_FORBIDDEN_KEYS = {"source", "fallback_of", "reason"}  # provenance is the resolver's to write, never the editor's
_DISCOVERY_NAME = {"agy": "antigravity"}


def _configured(settings):
    return roles._json_setting(settings, "default_roles", dict)


def _origin(role, settings, configured):
    if role in configured:
        return "default_roles"
    if role == "implementer":
        return "default_worker" if settings.get("default_worker") else "built_in_default_tool"
    if role == "reviewer" and settings.get("default_reviewer_profile"):
        return "default_reviewer_profile"
    return None


def _tool_state(tool, discovery):
    if discovery is None:
        return {"status": "unknown", "reason": "no discovery result supplied", "version_state": "unknown"}
    found = discovery.get(_DISCOVERY_NAME.get(tool, tool))
    if found is None:
        return {"status": "unknown", "reason": "tool not covered by discovery", "version_state": "unknown"}
    return {"status": found["status"], "reason": found["reason"], "version_state": found.get("version_state", "unknown")}


def _warnings(role, assignment, settings, tools, discovery, resolved_peers):
    out = []
    for label, entry in (("primary", assignment), *((f"fallback {i + 1}", f) for i, f in enumerate(assignment["fallbacks"]))):
        tool = entry.get("tool") or assignment["tool"]
        state = _tool_state(tool, discovery)
        if state["status"] == "unavailable":
            out.append({"kind": "tool_unavailable", "where": label, "message": f"{tool}: {state['reason']}"})
        elif state["status"] in ("installed", "configured"):
            out.append({"kind": "tool_not_verified", "where": label, "message": f"{tool} is {state['status']}, not verified: {state['reason']}"})
        elif state["status"] == "unknown":
            out.append({"kind": "tool_unchecked", "where": label, "message": f"{tool}: {state['reason']}"})
        if state["version_state"] == "older_than_verified":
            out.append({"kind": "stale_version", "where": label, "message": f"{tool} is older than the version this app was verified against"})
        try:
            roles.refuse_blocked(settings, entry.get("profile"))
        except roles.RoleError as error:
            out.append({"kind": "profile_blocked", "where": label, "message": error.message})
        if label != "primary" and tool != assignment["tool"]:
            out.append({"kind": "fallback_changes_tool", "where": label,
                        "message": f"fallback runs on {tool} instead of {assignment['tool']}: its sandbox and permissions differ"})
        if role in roles.WRITE_ROLES and tool not in roles.WRITE_TOOLS:
            out.append({"kind": "tool_cannot_write", "where": label, "message": f"{tool} cannot change files, but {role} must"})
        if role in ("reviewer", "deep_reviewer") and tool == "custom":
            out.append({"kind": "tool_cannot_review", "where": label, "message": "custom commands cannot do review work"})
    implementer = resolved_peers.get("implementer")
    if implementer is not None and role in ("reviewer", "deep_reviewer") and roles._same(assignment, implementer):
        kind = "independence_violation" if settings.get("require_independent_review") else "same_profile_as_implementer"
        out.append({"kind": kind, "where": "primary", "message": f"{role} uses the same profile as the implementer"})
    return out


def view(settings, tools, *, discovery=None, available=None, history=None):
    configured = _configured(settings)
    defaults = roles._hub_defaults(settings, tools)
    names = list(dict.fromkeys([*STANDARD_ROLES, *configured]))
    peers = {r: {k: v for k, v in a.items() if k != "configured"} for r, a in defaults.items()}
    rows = []
    for role in names:
        assignment = defaults.get(role)
        row = {"role": role, "origin": _origin(role, settings, configured), "assignment": None, "warnings": [], "suggestion": None}
        if assignment is not None:
            clean = {k: v for k, v in assignment.items() if k != "configured"}
            row["assignment"] = {"tool": clean.get("tool"), "profile": clean.get("profile") or "", "fallbacks": clean.get("fallbacks", []),
                                 "source": "hub_default"}
            row["warnings"] = _warnings(role, clean, settings, tools, discovery, peers)
        if settings.get("auto_assign") and available is not None:
            pool = [roles.normalize("reviewer", item, tools=tools) for item in roles._json_setting(settings, "auto_pool", list)]
            fallback = (assignment or {}).get("tool") or settings.get("default_worker") or roles.DEFAULT_TOOL
            suggestion = roles.recommend(role, pool, settings, available, fallback, [v for k, v in peers.items() if k != role], history)
            row["suggestion"] = suggestion and {**suggestion, "applied": False, "note": "a suggestion; it changes nothing until you set it"}
        rows.append(row)
    return {"roles": rows, "auto_assign": bool(settings.get("auto_assign")), "require_independent_review": bool(settings.get("require_independent_review")),
            "precedence": ["task request (explicit)", "configured default (hub_default)", "auto suggestion (auto)"]}


def plan_edit(settings, edits, tools, *, discovery=None):
    """Validate edits against a copy and return the diff and candidate settings. Roles not named stay byte-identical."""
    if not isinstance(edits, list) or not 1 <= len(edits) <= MAX_EDITS:
        raise ValueError(f"Send 1..{MAX_EDITS} edits")
    before = copy.deepcopy(_configured(settings))
    after = copy.deepcopy(before)
    errors = []
    for index, edit in enumerate(edits):
        try:
            if not isinstance(edit, dict) or edit.get("op") not in ("set", "clear"):
                raise roles.RoleError("BAD_EDIT", "Unknown edit operation")
            role = edit.get("role")
            if edit["op"] == "clear":
                roles.normalize(role, {}, tools=tools)  # validates the role name only
                after.pop(role, None)
                continue
            value = edit.get("assignment")
            stack = [value]
            while stack:  # provenance keys may not be smuggled in at any depth
                item = stack.pop()
                if isinstance(item, dict):
                    if _FORBIDDEN_KEYS & set(item):
                        raise roles.RoleError("BAD_ASSIGNMENT", "source, fallback_of and reason are written by the resolver, not by an edit")
                    stack.extend(item.get("fallbacks", []) if isinstance(item.get("fallbacks"), list) else [])
            normalized = roles.normalize(role, value, tools=tools)
            if not normalized["tool"]:
                raise roles.RoleError("BAD_ASSIGNMENT", f"Choose a tool for {role}: an assignment never guesses one")
            roles.refuse_blocked(settings, normalized["profile"], *(f.get("profile") for f in normalized["fallbacks"]))
            after[role] = {k: v for k, v in normalized.items() if k != "source" and (k != "fallbacks" or v)}
        except roles.RoleError as error:
            errors.append({"edit": index, "code": error.code, "message": error.message})
        except (TypeError, ValueError) as error:
            errors.append({"edit": index, "code": "BAD_EDIT", "message": str(error)[:200]})
    candidate = dict(settings)
    candidate["default_roles"] = json.dumps(after, sort_keys=True) if after else ""
    diff = []
    for role in sorted({*before, *after}):
        if role not in before:
            diff.append({"role": role, "change": "added", "before": None, "after": after[role]})
        elif role not in after:
            diff.append({"role": role, "change": "removed", "before": before[role], "after": None})
        elif before[role] != after[role]:
            diff.append({"role": role, "change": "changed", "before": before[role], "after": after[role]})
    warnings = []
    if not errors:
        try:
            resolved = {r: {k: v for k, v in a.items() if k != "configured"} for r, a in roles._hub_defaults(candidate, tools).items()}
            for role, entry in resolved.items():
                if role in {d["role"] for d in diff}:
                    warnings += [{**w, "role": role} for w in _warnings(role, entry, candidate, tools, discovery, resolved)]
            if candidate.get("require_independent_review"):
                roles.check_independence(resolved, True)
        except roles.RoleError as error:
            errors.append({"edit": None, "code": error.code, "message": error.message})
    return {"valid": not errors, "errors": errors, "diff": diff, "warnings": warnings,
            "candidate_settings": {"default_roles": candidate["default_roles"]} if not errors else None,
            "applied": False, "how_to_apply": "Apply candidate_settings with the normal settings call; nothing was saved."}
