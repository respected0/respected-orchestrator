"""Config-location matrix and safe, side-effect-free scan (B3-08.01).

Nothing here starts a process, writes a file or follows a link. A location is only ever *looked at*: whether it exists, whether it can be
read and parsed, how big it is, its SHA-256 and the names of its top-level keys. Values (which is where tokens live) are never returned.
Every row says where its path comes from: `code` (the registration code already writes there), `observed` (seen on a real machine) or
`documented` (the client's docs, not yet seen here). A client whose location is not confirmed is listed as such, not guessed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from pathlib import Path

MAX_CONFIG_BYTES = 2 * 1024 * 1024
MAX_SKILLS = 500
_SENSITIVE = re.compile(r"(?i)token|oauth|credential|secret|passw|auth\.json|\.pem$|\.key$")
_SKILL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,79}\Z")
ERROR_CLASSES = ("not_found", "unreadable", "link_refused", "outside_root", "too_large", "sensitive_file", "bad_encoding", "malformed_json",
                 "malformed_toml", "unsupported_shape", "location_unknown")


def matrix(home, project=None):
    """Every place a supported client keeps MCP servers or skills, for the user and (optionally) one project."""
    h, rows = Path(home), []

    def add(client, kind, scope, fmt, path, key, source):
        rows.append({"client": client, "kind": kind, "scope": scope, "format": fmt, "path": path, "key": key, "source": source})
    add("claude-code", "mcp", "user", "json", h / ".claude.json", "mcpServers", "code")
    add("claude-code", "skill", "user", "skill-dir", h / ".claude" / "skills", None, "observed")
    add("codex", "mcp", "user", "toml", h / ".codex" / "config.toml", "mcp_servers", "code")
    add("codex", "skill", "user", "skill-dir", h / ".codex" / "skills", None, "observed")
    add("cursor", "mcp", "user", "json", h / ".cursor" / "mcp.json", "mcpServers", "code")
    add("cursor", "skill", "user", "skill-dir", h / ".cursor" / "skills-cursor", None, "observed")
    add("opencode", "mcp", "user", "json", h / ".config" / "opencode" / "opencode.json", "mcp", "code")
    add("shared", "skill", "user", "skill-dir", h / ".agents" / "skills", None, "observed")
    add("antigravity", "mcp", "user", "unknown", None, None, "unconfirmed")  # per-server folders exist under ~/.gemini, no config file confirmed
    if project is not None:
        p = Path(project)
        add("claude-code", "mcp", "project", "json", p / ".mcp.json", "mcpServers", "documented")
        add("claude-code", "skill", "project", "skill-dir", p / ".claude" / "skills", None, "documented")
        add("codex", "mcp", "project", "toml", p / ".codex" / "config.toml", "mcp_servers", "documented")
        add("cursor", "mcp", "project", "json", p / ".cursor" / "mcp.json", "mcpServers", "documented")
        add("opencode", "mcp", "project", "json", p / "opencode.json", "mcp", "documented")
    return rows


def _link(info):
    return info.st_file_attributes & 0x400 if hasattr(info, "st_file_attributes") else False


def _checked(root, path):
    """The path itself, after proving no component below `root` is a link/reparse point and nothing leaves `root`."""
    root_real = Path(os.path.realpath(root))
    rel = Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
    current = root_real
    for part in rel.parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return current, "not_found"
        if current.is_symlink() or _link(info):
            return current, "link_refused"
    if not str(Path(os.path.realpath(current))).casefold().startswith(str(root_real).casefold()):
        return current, "outside_root"
    return current, None


def _read_config(path, fmt, key):
    if _SENSITIVE.search(path.name):
        return {"state": "refused", "error_class": "sensitive_file"}
    size = path.stat().st_size
    if size > MAX_CONFIG_BYTES:
        return {"state": "refused", "error_class": "too_large", "bytes": size}
    raw = path.read_bytes()
    out = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {**out, "state": "unreadable_content", "error_class": "bad_encoding"}
    try:
        doc = json.loads(text) if fmt == "json" else tomllib.loads(text)
    except (ValueError, RecursionError) as error:
        return {**out, "state": "unreadable_content", "error_class": "malformed_json" if fmt == "json" else "malformed_toml", "detail": str(error)[:120]}
    if not isinstance(doc, dict):
        return {**out, "state": "unreadable_content", "error_class": "unsupported_shape"}
    section = doc.get(key) if key else None
    if section is not None and not isinstance(section, dict):
        return {**out, "state": "unreadable_content", "error_class": "unsupported_shape", "detail": f"{key} is not a table"}
    return {**out, "state": "ok", "top_level_keys": sorted(str(k) for k in doc)[:100], "entry_names": sorted(str(k) for k in (section or {}))[:200]}


def _read_skills(directory):
    names, truncated = [], False
    for entry in sorted(directory.iterdir(), key=lambda e: e.name):
        if len(names) >= MAX_SKILLS:
            truncated = True
            break
        try:
            info = entry.lstat()
        except OSError:
            continue
        if entry.is_symlink() or _link(info) or not entry.is_dir() or not _SKILL_NAME.fullmatch(entry.name):
            continue  # a linked or oddly named folder is not offered, and never followed
        names.append({"name": entry.name, "has_skill_md": (entry / "SKILL.md").is_file() and not (entry / "SKILL.md").is_symlink()})
    return {"state": "ok", "skills": names, "truncated": truncated}


def scan(home, project=None):
    """One result per matrix row. Errors are values with a class from ERROR_CLASSES; nothing is raised for a bad file."""
    results = []
    for row in matrix(home, project):
        out = {**{k: row[k] for k in ("client", "kind", "scope", "format", "key", "source")}, "path": str(row["path"]) if row["path"] else None}
        root = Path(project) if row["scope"] == "project" else Path(home)
        if row["path"] is None:
            results.append({**out, "state": "unknown", "error_class": "location_unknown"})
            continue
        try:
            path, problem = _checked(root, row["path"])
            if problem:
                results.append({**out, "state": "absent" if problem == "not_found" else "refused", "error_class": problem})
                continue
            body = _read_skills(path) if row["format"] == "skill-dir" else _read_config(path, row["format"], row["key"])
            results.append({**out, **body})
        except NotADirectoryError:
            results.append({**out, "state": "unreadable_content", "error_class": "unsupported_shape"})
        except PermissionError:
            results.append({**out, "state": "refused", "error_class": "unreadable"})
        except (OSError, ValueError):
            results.append({**out, "state": "refused", "error_class": "unreadable"})
    return {"home": str(home), "project": str(project) if project else None, "locations": results}
