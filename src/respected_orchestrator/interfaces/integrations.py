"""RPP ``integrations.*``: register the Orchestrator MCP server in AI-client configs (Safe Integration Layer).

Discover -> Inspect -> Plan -> approve -> Apply -> Verify -> Rollback. Only the one entry named ``respected-orchestrator`` is ever
touched; every other server/setting is preserved. Ownership (a digest of the entry we wrote) is recorded in the data root; an
entry we do not own, or one the user edited since, is refused rather than overwritten. Apply needs the digest of the plan the
user approved, so a config that changed in between is never written blindly.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from ..context import atomic_write_json, safe_path
from .installation import OperationError, _atomic_write_text, _now, _read_receipt, _receipt_path

NAME = "respected-orchestrator"
_TOML_HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")


def _home():
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())


def _clients():
    home = _home()
    appdata = Path(os.environ.get("APPDATA") or home / "AppData/Roaming")
    table = {"claude-code": ("json", home / ".claude.json", home / ".claude"),
             "codex": ("toml", home / ".codex/config.toml", home / ".codex"),
             "cursor": ("json", home / ".cursor/mcp.json", home / ".cursor"),
             "gemini": ("json", home / ".gemini/settings.json", home / ".gemini"),
             "windsurf": ("json", home / ".codeium/windsurf/mcp_config.json", home / ".codeium/windsurf")}
    if sys.platform == "win32":
        table["claude-desktop"] = ("json", appdata / "Claude/claude_desktop_config.json", appdata / "Claude")
    return table


def _fail(code, message, hint=""):
    return OperationError(code, message, hint)


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---- entry <-> text -------------------------------------------------------------------------------------------------
def _entry(client, launcher):
    command, args = launcher.get("command"), launcher.get("args", [])
    if not isinstance(command, str) or not command or not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise _fail("BAD_REQUEST", "launcher needs a command string and an args string list.", "Pass {command, args}.")
    entry = {"command": command, "args": args}
    return {"type": "stdio", **entry} if client == "claude-code" else entry


def _canon(entry):
    return json.dumps(entry, sort_keys=True, ensure_ascii=True)


def _toml_block(entry):
    return (f"[mcp_servers.{NAME}]\ncommand = {json.dumps(entry['command'])}\nargs = {json.dumps(entry['args'])}\n")


def _toml_span(text):
    """(start, end) line indexes of our table (plus its sub-tables), or None."""
    lines, start, end = text.splitlines(keepends=True), None, None
    for index, line in enumerate(lines):
        match = _TOML_HEADER.match(line)
        if not match:
            continue
        ours = match.group(1).replace('"', "").replace("'", "").split(".")[:2] == ["mcp_servers", NAME]
        if start is None and ours:
            start = index
        elif start is not None and not ours:
            end = index
            break
    return None if start is None else (start, len(lines) if end is None else end, lines)


def _read(kind, path):
    """(text or None, entry-text or None); entry-text is the canonical form used for ownership digests."""
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        return None, None
    except (OSError, UnicodeDecodeError) as error:
        raise _fail("LIFECYCLE_CONFLICT", f"Cannot read {path}: {error}", "Fix the file or leave this client off.")
    if kind == "json":
        if not text.strip():
            return text, None
        try:
            document = json.loads(text)
        except ValueError:
            raise _fail("LIFECYCLE_CONFLICT", f"{path} is not valid JSON; nothing was changed.", "Repair the file or leave this client off.")
        servers = document.get("mcpServers", {}) if isinstance(document, dict) else None
        if not isinstance(servers, dict):
            raise _fail("LIFECYCLE_CONFLICT", f"{path} has an unexpected shape; nothing was changed.", "Leave this client off.")
        return text, (_canon(servers[NAME]) if NAME in servers else None)
    span = _toml_span(text)
    return text, (None if span is None else "".join(span[2][span[0]:span[1]]).strip())


def _write(kind, path, text, entry):
    """Return the new file text with our entry set (entry dict) or removed (None); everything else is preserved."""
    if kind == "json":
        document = json.loads(text) if text and text.strip() else {}
        servers = document.setdefault("mcpServers", {})
        if entry is None:
            servers.pop(NAME, None)  # an emptied mcpServers stays: the client may own it
        else:
            servers[NAME] = entry
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    text = text or ""
    span = _toml_span(text)
    if span:
        lines = span[2]
        before, after = "".join(lines[:span[0]]), "".join(lines[span[1]:])
    else:
        before, after = text, ""
        if before and not before.endswith("\n"):
            before += "\n"
    if entry is None:
        return before + after
    block = _toml_block(entry)
    return before + (("\n" if before.strip() and not span else "") + block) + (("\n" + after) if after.strip() else "")


def _parse(kind, canon):
    """Inverse of the canonical entry text (what _read returned) -> entry dict or None."""
    if not canon:
        return None
    if kind == "json":
        return json.loads(canon)
    return {"command": json.loads(canon.split("command = ", 1)[1].splitlines()[0]),
            "args": json.loads(canon.split("args = ", 1)[1].splitlines()[0])}


def _check_toml(text):
    try:
        import tomllib
    except ImportError:  # shortcut: Python 3.10 cannot self-check the TOML result, 3.11+ does
        return
    try:
        tomllib.loads(text)
    except ValueError as error:
        raise _fail("INTERNAL", f"Refused to write invalid TOML: {error}", "Nothing was changed.")


# ---- ownership --------------------------------------------------------------------------------------------------------
def _owned_path(ctx):
    return safe_path(ctx.data_root / "integrations.json")


def _owned(ctx):
    path = _owned_path(ctx)
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


# ---- plan -----------------------------------------------------------------------------------------------------------------
def _desired(raw, clients):
    if not isinstance(raw, dict) or any(not isinstance(v, bool) for v in raw.values()):
        raise _fail("BAD_REQUEST", "desired must map client ids to booleans.", "Use {\"claude-code\": true}.")
    unknown = sorted(set(raw) - set(clients))
    if unknown:
        raise _fail("BAD_REQUEST", f"Unknown client(s): {', '.join(unknown)}.", "Use: " + ", ".join(clients) + ".")
    return raw


def plan(ctx, payload):
    clients = _clients()
    desired = _desired(payload.get("desired", {}), clients)
    launcher = payload.get("launcher")
    owned, rows = _owned(ctx), []
    for client, (kind, path, marker) in clients.items():
        try:
            text, current = _read(kind, path)
        except Exception:
            if desired.get(client) is not None:
                raise  # the user asked about this client: say why it cannot be handled
            # an unparsable config of a client nobody touched must not block the others (audit P1 #17)
            rows.append({"client": client, "config": str(path), "detected": path.is_file() or marker.is_dir(), "state": "unreadable",
                         "action": "unchanged", "reason": "Config could not be read; left alone."})
            continue
        record = owned.get(client)
        if current is None:
            state = "absent"
        elif record and record.get("sha256") == _digest(current) and record.get("path") == str(path):
            state = "owned"
        else:
            state = "modified" if record else "foreign"
        row = {"client": client, "config": str(path), "detected": path.is_file() or marker.is_dir(), "state": state,
               "action": "unchanged", "reason": ""}
        want = desired.get(client)
        if want is not None:
            if want and not row["detected"]:
                row.update(action="refuse", reason="Client not detected on this computer.")
            elif state in ("foreign", "modified"):
                row.update(action="refuse", reason="An entry named respected-orchestrator exists that Respected does not own"
                           if state == "foreign" else "Respected's entry was edited since it was written; leaving it alone")
            elif want:
                new = _entry(client, launcher or {})
                new_text = _canon(new) if kind == "json" else _toml_block(new).strip()
                row.update(action="create" if state == "absent" else ("unchanged" if current == new_text else "update"),
                           entry=new)
            elif state == "owned":
                row.update(action="remove")
        rows.append(row)
    digest = _digest(json.dumps([{k: r[k] for k in ("client", "config", "action", "state")} | {"entry": r.get("entry")} for r in rows],
                                sort_keys=True))
    return {"clients": rows, "plan_digest": digest, "writes_nothing": True}


# ---- apply / rollback ---------------------------------------------------------------------------------------------------
def _set_entry(client, entry):
    kind, path, _ = _clients()[client]
    text, _current = _read(kind, path)
    new = _write(kind, path, text, entry)
    if kind == "toml":
        _check_toml(new)
    _atomic_write_text(path, new)
    return path, text


def _verify(client, entry):
    kind, path, _ = _clients()[client]
    _text, current = _read(kind, path)
    expected = None if entry is None else (_canon(entry) if kind == "json" else _toml_block(entry).strip())
    if current != expected:
        raise _fail("INTERNAL", f"Read-back of {path} does not match what was written.", "Roll back this operation.")


def apply(ctx, operation_id, payload):
    receipt_path = _receipt_path(ctx, operation_id)
    existing = _read_receipt(receipt_path)
    if existing is not None:
        if existing.get("op") != "integrations.apply":
            raise _fail("LIFECYCLE_CONFLICT", "operation_id was already used by another operation.", "Use a new operation_id.")
        return existing
    planned = plan(ctx, payload)
    if payload.get("plan_digest") != planned["plan_digest"]:
        raise _fail("PLAN_CHANGED", "The configuration changed since the plan the user approved.", "Plan again and approve the new plan.")
    refused = [r for r in planned["clients"] if r["action"] == "refuse"]
    if refused:
        raise _fail("LIFECYCLE_CONFLICT", "; ".join(f"{r['client']}: {r['reason']}" for r in refused), "Resolve it or leave that client off.")
    owned, backups = _owned(ctx), safe_path(ctx.data_root / "integration-backups" / operation_id)
    receipt = {"operation_id": operation_id, "op": "integrations.apply", "status": "in_progress", "started_at": _now(), "changes": []}
    done = []
    try:
        for row in planned["clients"]:
            if row["action"] not in ("create", "update", "remove"):
                continue
            client, kind = row["client"], _clients()[row["client"]][0]
            _text, before = _read(kind, Path(row["config"]))
            new_entry = row.get("entry") if row["action"] != "remove" else None
            _path, prior_text = _set_entry(client, new_entry)
            if prior_text is not None:  # whole-file backup for manual recovery; rollback itself is entry-surgical
                backup = backups / f"{client}.bak"
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_text(prior_text, encoding="utf-8", newline="")
            _verify(client, new_entry)
            done.append((client, before))
            after = None if new_entry is None else (_canon(new_entry) if kind == "json" else _toml_block(new_entry).strip())
            receipt["changes"].append({"client": client, "config": row["config"], "action": row["action"],
                                       "before": before, "after": after, "entry": new_entry,
                                       "file_existed": prior_text is not None})
            if after is None:
                owned.pop(client, None)
            else:
                owned[client] = {"path": row["config"], "sha256": _digest(after)}
    except Exception:
        for client, before in reversed(done):  # undo what this call wrote; foreign content was never touched
            try:
                _set_entry(client, _parse(_clients()[client][0], before))
            except Exception:
                pass
        raise
    atomic_write_json(_owned_path(ctx), owned)
    receipt.update(status="applied", finished_at=_now())
    atomic_write_json(receipt_path, receipt)
    return receipt


def rollback(ctx, operation_id):
    path = _receipt_path(ctx, operation_id)
    receipt = _read_receipt(path)
    if receipt is None or receipt.get("op") != "integrations.apply":
        raise _fail("ROLLBACK_UNAVAILABLE", "No integrations receipt for that operation_id.", "Check the operation_id.")
    if receipt.get("status") == "rolled_back":
        return receipt
    owned, clients = _owned(ctx), _clients()
    for change in receipt["changes"]:  # check everything first: roll back all or none
        kind, config, _ = clients[change["client"]]
        if _read(kind, config)[1] != change["after"]:
            raise _fail("ROLLBACK_UNAVAILABLE", f"{change['client']}: the entry changed since this operation; leaving it alone.",
                        "Edit or remove it by hand.")
    for change in reversed(receipt["changes"]):
        client, kind = change["client"], clients[change["client"]][0]
        before = change["before"]
        _set_entry(client, _parse(kind, before))
        if before:
            owned[client] = {"path": change["config"], "sha256": _digest(before)}
        else:
            owned.pop(client, None)
    atomic_write_json(_owned_path(ctx), owned)
    receipt.update(status="rolled_back", rolled_back_at=_now())
    atomic_write_json(path, receipt)
    return receipt
