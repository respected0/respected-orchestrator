"""Normalised MCP / skill inventory (B3-08.02). Pure data: nothing is executed, installed or enabled.

Each capability is one record with five separate, never-merged statuses:

  configured  it is written in a client's config (always true for a listed record)
  installed   the program it names exists on this machine (None: cannot be told without running a package manager)
  available   it could be launched/reached as declared. Reachability is never tested: remote servers are never contacted
  verified    always false here; verifying needs a run, and discovery never runs anything
  trusted     true only when an approval record the caller passes in matches this record's digest; a manifest, a name, a
              description or a "trusted" claim inside the capability itself never raises it

Secrets are removed before anything leaves this module, and the digest is taken over the redacted form, so it identifies what a
capability *is* (command, arguments, URL, variable names) without being a fingerprint of any secret.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .. import activity, capability_manifest
from ..journal import mask
from . import paths

REDACTED = "[redacted]"
_SECRET_NAME = re.compile(r"(?i)token|secret|passw|credential|api[_-]?key|auth|bearer|cookie|session|private")
_SECRET_ARG = re.compile(r"(?i)^(--?[\w-]*(?:token|secret|passw|key|auth)[\w-]*)(=|$)")
_SECRET_ASSIGN = re.compile(r"(?i)((?:token|secret|passw\w*|api[_-]?key|auth\w*)\s*[:=]\s*)\S+")
_INSTRUCTION_LIKE = re.compile(r"(?i)ignore (all |any |the )?(previous|prior|above)|disregard .{0,30}instructions|system prompt|you (must|should) (now )?(run|execute|call|send)|"
                               r"<\s*/?\s*(tool|system|instructions?)\b|always (approve|allow)|do not (tell|inform) the user|exfiltrat")
MAX_TEXT = 300
PROVENANCE = {"code": "written by Respected's own registration", "observed": "seen in this client's folder", "documented": "client documentation",
              "unconfirmed": "unconfirmed"}


def _clean(text, limit=MAX_TEXT):
    return activity.clean(mask(str(text)), limit)


def redact_arg_list(args):
    """Mask the value of secret-looking flags (`--token x`, `--api-key=x`), embedded assignments and well-known token shapes."""
    out, hide_next, secrets = [], False, 0
    for arg in args:
        arg = str(arg)
        if hide_next:
            out.append(REDACTED)
            hide_next, secrets = False, secrets + 1
            continue
        flag = _SECRET_ARG.match(arg)
        if flag and flag.group(2) == "=":
            out.append(arg.split("=", 1)[0] + "=" + REDACTED)
            secrets += 1
        elif flag:
            out.append(arg)
            hide_next = True
        else:
            cleaned = _SECRET_ASSIGN.sub(lambda m: m.group(1) + REDACTED, mask(arg))
            secrets += cleaned != arg
            out.append(cleaned)
    return out, secrets


def redact_url(url):
    try:
        parts = urlsplit(str(url))
    except ValueError:
        return REDACTED, 1
    secrets = 0
    host = parts.hostname or ""
    netloc = host + (f":{parts.port}" if parts.port else "")
    if parts.username or parts.password:
        netloc, secrets = f"{REDACTED}@{netloc}", secrets + 1
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        hide = bool(_SECRET_NAME.search(key))
        secrets += hide
        query.append(f"{key}={REDACTED if hide else value}")
    return f"{parts.scheme}://{netloc}{parts.path}" + ("?" + "&".join(query) if query else ""), secrets


def _env(mapping):
    if not isinstance(mapping, dict):
        return [], 0
    return sorted(str(k) for k in mapping)[:100], sum(1 for v in mapping.values() if v not in (None, ""))


def _server(kind_client, name, raw):
    """(redacted entry, declared permissions, secrets removed) for one MCP server definition, whatever the client's dialect."""
    if not isinstance(raw, dict):
        return None
    secrets = 0
    command = raw.get("command")
    args = raw.get("args") or []
    if isinstance(command, list):  # opencode keeps the program and its arguments in one array
        command, args = (command[0] if command else None), [*command[1:], *args]
    if not isinstance(args, list):
        args = []
    url = raw.get("url") or raw.get("httpUrl")
    transport = str(raw.get("type") or raw.get("transport") or ("stdio" if command else "http" if url else "unknown")).lower()
    red_args, n = redact_arg_list(args)
    secrets += n
    entry = {"transport": transport, "command": _clean(command, 200) if isinstance(command, str) else None, "args": [_clean(a, 200) for a in red_args][:50]}
    if isinstance(url, str):
        entry["url"], n = redact_url(url)
        secrets += n
    env_names, env_set = _env(raw.get("env") or raw.get("environment"))
    header_names, header_set = _env(raw.get("headers"))
    entry.update(env_names=env_names, header_names=header_names)
    secrets += env_set + header_set
    declared = {"launches_local_process": bool(command), "network": entry.get("url") or ("none declared" if command else "unknown"),
                "env_variables": env_names, "headers": header_names,
                "tools": "not declared by the config; unknown until the server is run, which discovery never does"}
    return entry, declared, secrets


def _is_installed(command, which):
    if not command:
        return None, "no local program is named (remote or malformed)"
    name = Path(command).name
    if name.casefold().removesuffix(".exe") in {"npx", "uvx", "pnpm", "bunx", "pipx", "docker", "node", "python", "python3", "deno", "bun", "uv"}:
        found = which(command)
        return (None, f"{name} is a package runner or interpreter: it {'is present' if found else 'is not on PATH'}, what it would run cannot be checked without running it")
    found = which(command) if not Path(command).is_absolute() else (command if Path(command).is_file() else None)
    return (True, f"program found: {Path(found).name}") if found else (False, f"program not found: {_clean(command, 80)}")


def _record(kind, client, scope, name, origin, entry, declared, secrets, installed, approvals, extra=None):
    digest = capability_manifest.digest({"kind": kind, "client": client, "scope": scope, "name": name, "entry": entry})
    trusted = any(isinstance(a, dict) and str(a.get("digest", "")).upper() == digest and a.get("provenance") == origin["path"] for a in approvals)
    return {"kind": kind, "id": f"{client}:{scope}:{kind}:{name}", "name": _clean(name, 80), "client": client, "scope": scope, "origin": origin,
            "entry": entry, "declared_permissions": declared, "digest": digest, "secrets_removed": secrets,
            "status": {
                "configured": {"state": True, "reason": f"present in {Path(origin['path']).name}"},
                "installed": {"state": installed[0], "reason": installed[1]},
                "available": {"state": installed[0],
                            "reason": "reachability is never tested; remote servers are not contacted" if kind == "mcp" else "files are present"},
                "verified": {"state": False, "reason": "discovery never runs or contacts anything, so nothing can be verified here"},
                "trusted": {"state": trusted, "reason": "approval record matches this digest and source" if trusted else "no approval record for this digest"},
            }, "warnings": [], "project_path": None, **(extra or {})}


def _skill_info(skill_dir):
    """Name and description from SKILL.md front matter (first 8 KB, text only). The text is data and is never authority."""
    md = skill_dir / "SKILL.md"
    try:
        if md.is_symlink() or not md.is_file():
            return None
        head = md.read_bytes()[:8192].decode("utf-8", errors="replace")
    except OSError:
        return None
    meta = {}
    if head.startswith("---"):
        for line in head.split("\n---", 1)[0].splitlines()[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip().strip("\"'")
    return meta


def build(home, project=None, *, approvals=(), which=shutil.which):
    records = []
    for row, meta, doc in paths.load_entries(home, project):
        origin = {"path": str(row["path"]), "source": row["source"], "provenance": PROVENANCE[row["source"]], "file_sha256": meta.get("sha256")}
        scopes = [(row["scope"], None, doc.get(row["key"]))]
        if row["client"] == "claude-code" and isinstance(doc.get("projects"), dict):  # Claude keeps per-project servers inside the user file
            scopes += [("project", project_path, (cfg or {}).get("mcpServers")) for project_path, cfg in doc["projects"].items() if isinstance(cfg, dict)]
        for scope, project_path, section in scopes:
            if not isinstance(section, dict):
                continue
            if row["client"] == "opencode" and isinstance(section.get("servers"), dict):  # the nesting Respected's own registration writes
                section = {**{k: v for k, v in section.items() if k != "servers"}, **section["servers"]}
            for name, raw in section.items():
                parsed = _server(row["client"], name, raw)
                if parsed is None:
                    continue
                entry, declared, secrets = parsed
                rec = _record("mcp", row["client"], scope, str(name), origin, entry, declared, secrets, _is_installed(entry["command"], which), approvals,
                              {"project_path": _clean(project_path, 200) if project_path else None})
                if declared["launches_local_process"]:
                    rec["warnings"].append({"kind": "launches_local_process", "message": "enabling this would start a local program with your privileges"})
                if secrets:
                    rec["warnings"].append({"kind": "secrets_in_config", "message": f"{secrets} secret value(s) are stored in the client config and were removed from this view"})
                if entry.get("transport") == "unknown":
                    rec["warnings"].append({"kind": "unknown_transport", "message": "neither a command nor a URL is declared"})
                records.append(rec)
    skill_rows = [r for r in paths.matrix(home, project) if r["format"] == "skill-dir"]
    for row in skill_rows:
        root = Path(project) if row["scope"] == "project" else Path(home)
        try:
            directory, problem = paths._checked(root, row["path"])
            listing = None if problem else paths._read_skills(directory)
        except (OSError, ValueError):
            listing = None
        for skill in (listing or {}).get("skills", []):
            meta = _skill_info(directory / skill["name"]) if skill["has_skill_md"] else None
            description = _clean((meta or {}).get("description", ""), MAX_TEXT)
            entry = {"has_skill_md": skill["has_skill_md"], "declared_name": _clean((meta or {}).get("name", ""), 80), "description": description}
            origin = {"path": str(directory / skill["name"]), "source": row["source"], "provenance": PROVENANCE[row["source"]], "file_sha256": None}
            declared = {"launches_local_process": False, "network": "not declared", "allowed_tools": _clean((meta or {}).get("allowed-tools", "not declared"), 200),
                        "tools": "a skill is instructions for the model; its text is untrusted data"}
            rec = _record("skill", row["client"], row["scope"], skill["name"], origin, entry, declared, 0,
                          (skill["has_skill_md"], "SKILL.md present" if skill["has_skill_md"] else "no SKILL.md in this folder"), approvals)
            if _INSTRUCTION_LIKE.search(description) or (meta and _INSTRUCTION_LIKE.search(" ".join(map(str, meta.values())))):
                rec["warnings"].append({"kind": "instruction_like_text", "message": "its description reads like instructions to a model; it is shown as text only"})
            if (directory / skill["name"] / "manifest.json").is_file():
                rec["warnings"].append({"kind": "self_declared_manifest", "message": "a manifest.json inside the skill is ignored: trust only comes from an approval record"})
            records.append(rec)
    seen = {}
    for rec in records:  # two definitions can share client+scope+name (a project entry inside ~/.claude.json and a .mcp.json); ids stay unique and stable
        seen[rec["id"]] = seen.get(rec["id"], 0) + 1
        if seen[rec["id"]] > 1:
            rec["id"] = f"{rec['id']}~{seen[rec['id']]}"
    by_name = {}
    for rec in records:
        by_name.setdefault((rec["kind"], rec["name"].casefold()), []).append(rec)
    for group in by_name.values():
        if len(group) > 1:
            same = len({r["digest"] for r in group}) == 1
            for rec in group:
                rec["warnings"].append({"kind": "duplicate_name", "message": f"{len(group)} definitions share this name" + ("" if same else " and they differ"),
                                        "others": [r["id"] for r in group if r is not rec][:10], "same_definition": same})
    return {"home": str(home), "project": str(project) if project else None, "capabilities": records,
            "counts": {"mcp": sum(r["kind"] == "mcp" for r in records), "skill": sum(r["kind"] == "skill" for r in records),
                       "trusted": sum(r["status"]["trusted"]["state"] for r in records), "verified": 0}}
