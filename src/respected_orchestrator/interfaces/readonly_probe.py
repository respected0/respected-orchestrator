"""EXT-02: read-only Serena/context probing behind the EXT-01 capability manifest."""
import re
from pathlib import PurePosixPath

from ..engine.capability_manifest import CapabilityError, authorize

_READ_ONLY = frozenset({"mcp.serena", "mcp.context"})
MAX_TEXT = 20_000
_SECRET = re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)\S+")


def _relative(path):
    text = str(path).replace("\\", "/")
    drive = re.match(r"^[A-Za-z]:", text)
    if not text or text.startswith("/") or drive or text.startswith("//"):
        raise CapabilityError("PATH_INVALID", f"provider path escapes the repo: {path!r}")
    pure = PurePosixPath(text)
    if pure.is_absolute() or ".." in pure.parts:
        raise CapabilityError("PATH_INVALID", f"provider path escapes the repo: {path!r}")
    return text


def query_repo(manifest, tool, *, approved_tools, query, provider, expected_digest=None, expected_provenance=None):
    """Run one approved read-only probe; response is untrusted data, never authority or a command."""
    authorize(manifest, [tool], approved_tools=approved_tools, expected_digest=expected_digest,
              expected_provenance=expected_provenance)
    if tool not in _READ_ONLY or manifest["tools"].get(tool) != ["read"]:
        raise CapabilityError("NOT_READ_ONLY", f"{tool} is not an approved read-only probe")
    if not callable(provider):
        raise CapabilityError("PROVIDER_MISSING", f"no provider is installed for {tool}")
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise CapabilityError("QUERY_INVALID", "query must be 1-500 characters")
    response = provider(query)
    if not isinstance(response, dict):
        raise CapabilityError("RESPONSE_INVALID", "provider response must be an object")
    text = response.get("text", "")
    if not isinstance(text, str):
        raise CapabilityError("RESPONSE_INVALID", "provider text must be a string")
    paths = response.get("paths", [])
    if not isinstance(paths, list):
        raise CapabilityError("RESPONSE_INVALID", "provider paths must be a list")
    cleaned = _SECRET.sub(r"\1[REDACTED]", text)[:MAX_TEXT]
    return {"tool": tool, "untrusted": True, "text": cleaned, "paths": [_relative(path) for path in paths],
            "truncated": len(text) > MAX_TEXT}