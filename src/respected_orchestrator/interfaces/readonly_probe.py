"""EXT-02: read-only MCP context probing behind the EXT-01 capability manifest."""
import re
from pathlib import PurePosixPath

from ..engine.capability_manifest import CapabilityError, authorize

_READ_ONLY = frozenset({"mcp.context"})
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


def query_via_stdio(manifest, tool, *, approved_tools, query, command, args=(), mcp_tool=None, build_args=None,
                    expected_digest=None, expected_provenance=None, timeout=20.0, max_bytes=1_000_000):
    """Run the approved probe through a real MCP stdio server; its result stays inert, redacted data."""
    from .mcp_client import McpError, StdioMcpClient

    def provider(text):
        try:
            with StdioMcpClient(command, args, timeout=timeout, max_bytes=max_bytes) as client:
                client.initialize()
                result = client.call_tool(mcp_tool or tool, (build_args or (lambda value: {"query": value}))(text))
        except McpError as error:
            raise CapabilityError("PROVIDER_FAILED", str(error)) from None
        if result.get("isError"):
            raise CapabilityError("PROVIDER_FAILED", "MCP tool returned an error")
        content = result.get("content") or []
        texts = [item.get("text", "") for item in content
                 if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)]
        structured = result.get("structuredContent")
        paths = structured.get("paths") if isinstance(structured, dict) else result.get("paths")
        return {"text": "\n".join(texts), "paths": paths if isinstance(paths, list) else []}

    return query_repo(manifest, tool, approved_tools=approved_tools, query=query, provider=provider,
                      expected_digest=expected_digest, expected_provenance=expected_provenance)