"""PermissionInspector and risk cards (B4-03.03). Read-only: nothing is run, fetched, installed or enabled.

A card keeps four things apart, because they answer different questions and must never be merged into one green light:
  execution    would the existing fail-closed gate (capability_manifest) let it run? No manifest, an invalid one, or one without a
               matching approval record is "denied" with the gate's own code
  trust        "approved" only when an approval record passed in by the caller matches; a `trust: trusted` written inside the
               manifest is shown as `self_claimed` and counts for nothing
  availability whether the program is present (the inventory's own installed state); says nothing about safety or trust
  risks        what it could touch: command, network, secrets, files, roots, and over-broad combinations
Risk levels are low / medium / high / unknown; unknown is never shown as low."""
import ipaddress
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from .. import capability_manifest as cm

LEVELS = ("low", "medium", "high")
_SECRET_NAME_HINT = ("token", "secret", "passw", "key", "credential", "auth", "cookie")
_BROAD_PATHS = {".", "./", "*", "**", "/", "~"}


def _risk(area: str, level: str, detail: str) -> dict[str, str]:
    return {"area": area, "level": level, "detail": detail}


def _loopback(host: str | None) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _gate(manifest: Any, approvals: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The existing gate, unchanged: structural check first, then a matching approval record (by manifest digest + provenance)."""
    try:
        actual = cm.verify_manifest(manifest)
    except cm.CapabilityError as error:
        return {"allowed": False, "code": error.code, "detail": str(error)}
    approved = any(isinstance(a, Mapping) and str(a.get("manifest_digest", "")).upper() == actual and a.get("provenance") == manifest["provenance"] for a in approvals)
    if not approved:
        return {"allowed": False, "code": "NO_APPROVAL_RECORD", "detail": "the manifest is well-formed but no approval record matches its digest and provenance"}
    return {"allowed": True, "code": None, "detail": "manifest verified and approved; the task plan must still approve each tool"}


def inspect(record: Mapping[str, Any], manifest: Any = None, approvals: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """Risk card for one inventory record, optionally with the manifest it ships/was installed with."""
    entry, declared, status = record.get("entry") or {}, record.get("declared_permissions") or {}, record.get("status") or {}
    risks: list[dict[str, str]] = []
    if declared.get("launches_local_process"):
        risks.append(_risk("command", "medium", "starts a local program with your privileges"))
    elif record.get("kind") == "mcp":
        risks.append(_risk("command", "unknown", "no local command is declared"))
    url = entry.get("url")
    if isinstance(url, str) and url:
        host = urlsplit(url).hostname
        risks.append(_risk("network", "low" if _loopback(host) else "high", f"talks to {host or 'an unparseable address'}" + ("" if _loopback(host) else " (external)")))
    elif declared.get("network") == "none declared":
        risks.append(_risk("network", "low", "no network address declared (the program itself may still use the network)"))
    else:
        risks.append(_risk("network", "unknown", "network use is not declared"))
    secrets = record.get("secrets_removed") or 0
    if secrets:
        risks.append(_risk("secrets", "high", f"{secrets} secret value(s) are stored in the client config"))
    names = [n for n in (entry.get("env_names") or []) + (entry.get("header_names") or []) if any(h in str(n).casefold() for h in _SECRET_NAME_HINT)]
    if names:
        risks.append(_risk("secrets", "medium", "expects secret-like variables: " + ", ".join(sorted(map(str, names))[:5])))
    tools = declared.get("allowed_tools")
    if isinstance(tools, str) and tools != "not declared":
        risky = [t for t in ("bash", "write", "edit", "webfetch", "shell") if t in tools.casefold()]
        risks.append(_risk("command" if "bash" in risky or "shell" in risky else "files", "medium" if risky else "low", f"skill asks for tools: {tools[:100]}"))
    elif record.get("kind") == "skill":
        risks.append(_risk("files", "unknown", "the skill does not declare which tools it uses"))
    scope = record.get("scope")
    risks.append(_risk("roots", "medium" if scope == "user" else "low" if scope == "project" else "unknown",
                       "applies to every project of this user" if scope == "user" else "limited to one project" if scope == "project" else "scope unknown"))
    gate: dict[str, Any]
    self_claimed = None
    if manifest is None:
        gate = {"allowed": False, "code": "MANIFEST_MISSING", "detail": "a skill or MCP tool without a manifest is denied"}
    else:
        gate = _gate(manifest, approvals)
        if isinstance(manifest, Mapping):
            self_claimed = manifest.get("trust")
            read, write = manifest.get("read") or [], manifest.get("write") or []
            scopes = manifest.get("data_scope") or []
            if isinstance(scopes, list) and any(str(s).strip().replace("\\", "/") in _BROAD_PATHS for s in scopes):
                risks.append(_risk("files", "high", "data scope covers the whole workspace"))
            elif isinstance(write, list) and write:
                risks.append(_risk("files", "medium", "may write inside the workspace"))
            elif isinstance(read, list) and read:
                risks.append(_risk("files", "low", "reads only"))
            net = manifest.get("net")
            if net == "allowlist":
                risks.append(_risk("network", "medium", "manifest asks for allow-listed network access"))
            tool_map = manifest.get("tools")
            ops = {op for ops in (tool_map.values() if isinstance(tool_map, Mapping) else []) if isinstance(ops, list) for op in ops}
            if len(ops & {"read", "write", "net", "exec"}) >= 3 or "exec" in ops:
                risks.append(_risk("breadth", "high", "declares a very broad combination of operations: " + ", ".join(sorted(ops))))
    trusted = bool(status.get("trusted", {}).get("state"))
    rank = {"unknown": -1, "low": 0, "medium": 1, "high": 2}
    worst = max((r["level"] for r in risks), key=lambda lv: rank[lv], default="unknown")
    level = "high" if worst == "high" else "unknown" if any(r["level"] == "unknown" for r in risks) else worst
    return {"id": record.get("id"), "execution": gate,
            "trust": {"state": "approved" if trusted else "unknown", "self_claimed": self_claimed,
                      "note": "approval record matched" if trusted else "no approval record for this digest; a claim inside the capability is not one"},
            "availability": {"installed": (status.get("installed") or {}).get("state"), "reason": (status.get("installed") or {}).get("reason")},
            "risks": risks, "level": level, "side_effects": "none"}
