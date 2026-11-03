"""Fail-closed skill/MCP capability manifests (EXT-01).

A manifest is data, never authority. A tool runs only when the manifest declares
it, the digest still matches, provenance matches the approved install record and
the task plan explicitly approved that tool. Everything else is denied.
"""

from __future__ import annotations

import hashlib
import json

REQUIRED = ("name", "version", "provenance", "trust", "tools", "read", "write", "net", "data_scope")
OPTIONAL = ("description", "sha256")
TOOL_OPS = frozenset({"read", "write", "net", "exec"})
ALLOWED_TOOLS = frozenset({"repo.search", "repo.patch", "test.run", "mcp.serena", "mcp.context"})
READ_SCOPES = frozenset({"repo", "docs", "evidence"})
WRITE_SCOPES = frozenset({"workspace"})
NET_SCOPES = frozenset({"none", "loopback", "allowlist"})
TRUST_LEVELS = frozenset({"trusted"})
MAX_DESCRIPTION = 2000


class CapabilityError(PermissionError):
    """Raised before a skill or MCP tool is allowed to act."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _fail(code, message):
    raise CapabilityError(code, message)


def canonical(manifest):
    """Canonical bytes body; the stored digest itself is excluded."""
    body = {key: manifest[key] for key in manifest if key != "sha256"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(manifest):
    return hashlib.sha256(canonical(manifest).encode("utf-8")).hexdigest().upper()


def _string_set(value, code):
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in value):
        _fail(code, f"{code.lower()}: expected a list of non-empty strings")
    return set(value)


def _check_scope(scope):
    values = _string_set(scope, "DATA_SCOPE_INVALID")
    if not values:
        _fail("DATA_SCOPE_MISSING", "data_scope must name at least one relative path")
    for item in values:
        if item.startswith(("/", "\\")) or ".." in item.replace("\\", "/").split("/") or ":" in item:
            _fail("DATA_SCOPE_INVALID", f"data_scope escapes the workspace: {item}")


def verify_manifest(manifest, *, expected_digest=None, expected_provenance=None):
    """Validate a manifest and return its verified digest or raise."""
    if manifest is None:
        _fail("MANIFEST_MISSING", "a skill or MCP tool without a manifest is denied")
    if not isinstance(manifest, dict):
        _fail("MANIFEST_INVALID", "manifest must be an object")
    missing = [key for key in REQUIRED if key not in manifest]
    if missing:
        _fail("MANIFEST_INCOMPLETE", "manifest is missing: " + ", ".join(missing))
    extra = set(manifest) - set(REQUIRED) - set(OPTIONAL)
    if extra:
        _fail("MANIFEST_UNDECLARED_FIELD", "manifest carries undeclared fields: " + ", ".join(sorted(extra)))

    stored = manifest.get("sha256")
    if not isinstance(stored, str) or not stored.strip():
        _fail("MANIFEST_HASH_MISSING", "manifest must carry its own SHA-256")
    actual = digest(manifest)
    if stored.strip().upper() != actual:
        _fail("MANIFEST_HASH_CHANGED", "manifest content does not match its recorded hash")
    if expected_digest is not None and str(expected_digest).strip().upper() != actual:
        _fail("MANIFEST_HASH_CHANGED", "manifest hash does not match the approval record")

    if manifest["trust"] not in TRUST_LEVELS:
        _fail("UNTRUSTED_SKILL", f"trust level is not accepted: {manifest['trust']!r}")
    provenance = manifest["provenance"]
    if not isinstance(provenance, str) or not provenance.strip():
        _fail("PROVENANCE_MISSING", "manifest must name its provenance")
    if expected_provenance is not None and provenance != expected_provenance:
        _fail("PROVENANCE_MISMATCH", "manifest provenance does not match the approval record")

    description = manifest.get("description", "")
    if not isinstance(description, str) or len(description) > MAX_DESCRIPTION:
        _fail("DESCRIPTION_INVALID", "description must be bounded text and is never authority")

    read = _string_set(manifest["read"], "READ_INVALID")
    write = _string_set(manifest["write"], "WRITE_INVALID")
    if read - READ_SCOPES:
        _fail("READ_EXCESS", "read scope is not allowed: " + ", ".join(sorted(read - READ_SCOPES)))
    if write - WRITE_SCOPES:
        _fail("WRITE_EXCESS", "write scope is not allowed: " + ", ".join(sorted(write - WRITE_SCOPES)))
    if manifest["net"] not in NET_SCOPES:
        _fail("NET_INVALID", f"net scope is not allowed: {manifest['net']!r}")
    _check_scope(manifest["data_scope"])

    tools = manifest["tools"]
    if not isinstance(tools, dict):
        _fail("TOOLS_INVALID", "tools must be an object")
    for tool, ops in tools.items():
        if tool not in ALLOWED_TOOLS:
            _fail("TOOL_UNKNOWN", f"tool is not in the allowlist: {tool!r}")
        declared = _string_set(ops, "TOOL_OPS_INVALID")
        if not declared or declared - TOOL_OPS:
            _fail("TOOL_OPS_INVALID", f"{tool} declares unsupported operations")
        if "read" in declared and not read:
            _fail("EXCESS_PERMISSION", f"{tool} reads without a declared read scope")
        if "write" in declared and not write:
            _fail("EXCESS_PERMISSION", f"{tool} writes without a declared write scope")
        if "net" in declared and manifest["net"] == "none":
            _fail("EXCESS_PERMISSION", f"{tool} uses the network while net is none")
        if "exec" in declared:
            _fail("EXCESS_PERMISSION", "exec is not available to skills or MCP tools")
    return actual


def authorize(manifest, requested_tools, *, approved_tools, expected_digest=None, expected_provenance=None):
    """Return (digest, tools) only when plan approval covers every requested tool."""
    actual = verify_manifest(manifest, expected_digest=expected_digest, expected_provenance=expected_provenance)
    requested = _string_set(list(requested_tools), "REQUEST_INVALID")
    approved = _string_set(list(approved_tools), "APPROVAL_INVALID")
    declared = set(manifest["tools"])
    if requested - declared:
        _fail("CAPABILITY_NOT_DECLARED", "requested tool is not declared: " + ", ".join(sorted(requested - declared)))
    if approved - declared:
        _fail("CAPABILITY_NOT_DECLARED", "approved tool is not declared: " + ", ".join(sorted(approved - declared)))
    if requested - approved:
        _fail("CAPABILITY_NOT_APPROVED", "requested tool lacks plan approval: " + ", ".join(sorted(requested - approved)))
    return actual, tuple(sorted(requested))