"""Respected Product Protocol (RPP) 1: one JSON request in, one JSON response line out.

Not a daemon and no network listener. Settings go through `apply_settings`/`read_settings`, the same code as the
`config` command. Installing, repairing and removing are the installer's work, not protocol operations. Every failure is
returned as a structured error, never raised.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile

from .. import __version__
from . import installation
from . import memory
from ..workflows import roles
from ..engine import runner
from ..context import atomic_write_json, safe_path
from . import RPP

PRODUCT_ID = "respected-orchestrator"

_OPERATION_ID = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_WORKER_CHOICES = [agent for agent in runner.SUPPORTED_AGENTS if agent != "custom"]

_SETTINGS_FIELDS = [
    {"key": "default_worker", "type": "enum", "label": "Varsayılan çalışan", "default": "codex", "secret": False,
     "enum": _WORKER_CHOICES, "help": "Görevleri yapan AI aracı (komut satırı aracı kurulu olmalı)."},
    {"key": "default_worker_profile", "type": "string", "label": "Çalışan profili", "default": "", "secret": False,
     "help": "Çalışan aracın kullanacağı profil adı; boş: aracın varsayılanı."},
    {"key": "default_reviewer_profile", "type": "string", "label": "Gözden geçirici profili", "default": "", "secret": False,
     "help": "Gözden geçiren aracın profil adı; boş: aracın varsayılanı."},
    {"key": "default_timeout_seconds", "type": "integer", "label": "Görev zaman aşımı (saniye)", "default": 900, "secret": False,
     "min": 60, "max": 3600, "help": "Bir görevin en uzun çalışma süresi."},
    *roles.settings_fields(list(runner.SUPPORTED_AGENTS)),
    *memory.settings_fields(),
]


class RppError(Exception):
    """Expected failure carrying the protocol error triple."""

    def __init__(self, code, message, hint=""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _response(ok, operation_id, result, error):
    return {"rpp": RPP, "ok": ok, "operation_id": operation_id, "result": result, "error": error}


def _fail(operation_id, code, message, hint):
    return _response(False, operation_id, None, {"code": code, "message": message, "hint": hint})


def schema_fields():
    return [dict(field) for field in _SETTINGS_FIELDS]


def _defaults():
    return {field["key"]: field["default"] for field in _SETTINGS_FIELDS}


def _settings_path(ctx):
    return safe_path(ctx.data_root / "settings.json")


def _receipt_path(ctx, operation_id):
    return safe_path(ctx.data_root / "receipts" / f"{operation_id}.json")


def _settings_digest(settings):
    return hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


def _redact(settings):
    """Blank secret fields; secrets are accepted but never returned."""
    redacted = dict(settings)
    for field in _SETTINGS_FIELDS:
        key = field["key"]
        if field.get("secret") and redacted.get(key) not in (None, ""):
            redacted[key] = memory.REDACTED
    return redacted


def _stored_settings(ctx):
    known = {field["key"] for field in _SETTINGS_FIELDS} - {"memory_token"}
    return {key: value for key, value in roles.read_settings(ctx.data_root).items() if key in known}


def _memory_cross_errors(ctx, settings):
    """memory_enabled needs a command and a token once the incoming keys are merged over the stored ones."""
    effective = {**_stored_settings(ctx), **settings}
    if effective.get("memory_enabled") is not True:
        return []
    token = settings.get("memory_token", memory.REDACTED)
    has_token = memory.token_set(ctx.data_root) if token == memory.REDACTED else bool(token)
    command = effective.get("memory_command")
    if isinstance(command, str) and command.strip() and has_token:
        return []
    return [{"key": "memory_enabled", "message": "requires a memory command and a memory token"}]


def validate_settings(settings, ctx=None):
    if not isinstance(settings, dict):
        return [{"key": "", "message": "settings must be an object"}]
    errors = []
    known = {field["key"]: field for field in _SETTINGS_FIELDS}
    for key in settings:
        if key not in known:
            errors.append({"key": key, "message": "unknown settings key"})
    for key, field in known.items():
        if key not in settings:
            continue
        value = settings[key]
        kind = field["type"]
        if kind == "string":
            if not isinstance(value, str):
                errors.append({"key": key, "message": "expected a string"})
                continue
        elif kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append({"key": key, "message": "expected an integer"})
                continue
            if value < field["min"] or value > field["max"]:
                errors.append({"key": key, "message": f"must be between {field['min']} and {field['max']}"})
                continue
        elif kind == "boolean":
            if not isinstance(value, bool):
                errors.append({"key": key, "message": "expected true or false"})
                continue
        elif kind == "enum":
            if value not in field.get("enum", []):
                errors.append({"key": key, "message": "must be one of: " + ", ".join(field.get("enum", []))})
                continue
        if key.endswith("profile") and isinstance(value, str):
            try:
                roles.refuse_blocked(settings, value)
            except roles.RoleError as error:
                errors.append({"key": key, "message": error.message})
    errors += roles.validate_settings(settings, list(runner.SUPPORTED_AGENTS)) + memory.validate_settings(settings)
    if ctx is not None and not errors:
        errors += _memory_cross_errors(ctx, settings)
    return errors


def _normalize(settings):
    normalized = _defaults()
    for key in normalized:
        if key in settings:
            normalized[key] = settings[key]
    normalized.pop("memory_token", None)  # write-only: lives in the token file, never in settings.json
    return normalized


def _merged(ctx, settings):
    """defaults < stored settings.json < incoming keys (partial changes keep unrelated keys), plus the token digest."""
    normalized = _normalize({**_stored_settings(ctx), **settings})
    incoming = settings.get("memory_token", memory.REDACTED)
    token = memory.load_token(ctx.data_root) if incoming == memory.REDACTED else (incoming or None)
    # the digest changes with the token without containing it
    digest = _settings_digest({**normalized, "memory_token_sha256": hashlib.sha256(token.encode()).hexdigest() if token else ""})
    return normalized, incoming, digest


def apply_settings(ctx, settings):
    """Validate and store; the `config set` command and RPP settings.apply both come here."""
    errors = validate_settings(settings, ctx)
    if errors:
        raise RppError("INVALID_SETTINGS", "; ".join(f"{error['key']}: {error['message']}" for error in errors),
                       "Fix the reported fields and retry; nothing was written.")
    normalized, incoming, digest = _merged(ctx, settings)
    if incoming == "":
        memory.clear_token(ctx.data_root)
    elif incoming != memory.REDACTED:
        memory.store_token(ctx.data_root, incoming)
    atomic_write_json(_settings_path(ctx), normalized)
    return digest


def read_settings(ctx):
    path = _settings_path(ctx)
    stored = {}
    if path.is_file():
        try:
            stored = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            raise RppError("INTERNAL", "Stored settings are unreadable.", "Fix or remove settings.json in the data root.")
        if not isinstance(stored, dict):
            raise RppError("INTERNAL", "Stored settings are malformed.", "Fix or remove settings.json in the data root.")
    effective = _defaults()
    for key in effective:
        if key in stored:
            effective[key] = stored[key]
    effective["memory_token"] = memory.REDACTED if memory.token_set(ctx.data_root) else ""
    return _redact(effective)


def _manifest(ctx, operation_id, payload):
    state = installation.verify(ctx.app_root)
    return {"product_id": PRODUCT_ID, "product_version": __version__, "rpp": RPP, "capabilities": sorted(_OPS),
            "installed": state["installed"], "install_state": state["install_state"],
            "roots": {"app": str(ctx.app_root), "data": str(ctx.data_root), "vault": None}}


def _data_root_writable(ctx):
    try:
        ctx.data_root.mkdir(parents=True, exist_ok=True)
        descriptor, probe = tempfile.mkstemp(dir=ctx.data_root, prefix=".health-")
        os.close(descriptor)
        os.unlink(probe)
        return True
    except OSError:
        return False


def _engine_key_ok(ctx):
    path = ctx.data_root / ".engine-key"
    try:
        return path.is_file() and os.access(path, os.R_OK)
    except OSError:
        return False


def health(ctx, operation_id=None, payload=None):
    workers = [agent for agent in _WORKER_CHOICES if runner.get_cli_command(agent)]
    git = runner.shutil.which("git")
    writable = _data_root_writable(ctx)
    key_ok = _engine_key_ok(ctx)
    checks = [
        {"name": "data_root_writable", "ok": writable, "detail": "data root accepts writes" if writable else "data root is not writable"},
        {"name": "git_available", "ok": bool(git), "detail": git or "git not found on PATH"},
        {"name": "worker_cli", "ok": bool(workers), "detail": ", ".join(workers) if workers else "no supported worker CLI resolved"},
        {"name": "engine_key", "ok": key_ok, "detail": "engine key present and readable" if key_ok else "engine key missing or unreadable"},
    ]
    if not checks[0]["ok"]:
        status = "unhealthy"
    elif all(check["ok"] for check in checks):
        status = "healthy"
    else:
        status = "degraded"
    return {"status": status, "version": __version__, "checks": checks}


def _settings_schema(ctx, operation_id, payload):
    return {"fields": schema_fields()}


def _settings_validate(ctx, operation_id, payload):
    errors = validate_settings(payload.get("settings"), ctx)
    return {"valid": not errors, "errors": errors}


def _settings_apply(ctx, operation_id, payload):
    if not operation_id:
        raise RppError("BAD_REQUEST", "settings.apply requires an operation_id.", "Send an operation_id of 8-64 characters.")
    settings = payload.get("settings")
    errors = validate_settings(settings, ctx)
    if errors:
        raise RppError("INVALID_SETTINGS", "Settings failed validation.", "Fix the reported fields and retry; nothing was written.")
    receipt_path = _receipt_path(ctx, operation_id)
    if receipt_path.is_file():  # the same request again is answered from its receipt, never applied twice
        try:
            receipt = json.loads(receipt_path.read_text("utf-8"))
        except (OSError, ValueError):
            raise RppError("INTERNAL", "Stored receipt is unreadable.", "Inspect the receipts directory for this operation_id.")
        if receipt.get("settings_sha256") == _merged(ctx, settings)[2]:
            return {key: receipt.get(key) for key in ("status", "applied_at", "settings_sha256")}
        raise RppError("OPERATION_ID_CONFLICT", "operation_id was already used with different settings.",
                       "Use a new operation_id for different settings.")
    receipt = {"status": "applied", "applied_at": _now(), "settings_sha256": apply_settings(ctx, settings)}
    atomic_write_json(receipt_path, receipt)
    return receipt


def _settings_readback(ctx, operation_id, payload):
    return {"settings": read_settings(ctx)}


def _integrations(call):
    from . import integrations
    try:
        return call(integrations)
    except installation.OperationError as error:
        raise RppError(error.code, error.message, error.hint)


def _integrations_plan(ctx, operation_id, payload):
    return _integrations(lambda m: m.plan(ctx, payload))


def _integrations_apply(ctx, operation_id, payload):
    if not operation_id:
        raise RppError("BAD_REQUEST", "integrations.apply requires an operation_id.", "Send an operation_id of 8-64 characters.")
    return _integrations(lambda m: m.apply(ctx, operation_id, payload))


def _integrations_rollback(ctx, operation_id, payload):
    target = payload.get("operation_id") or operation_id
    if not isinstance(target, str) or not _OPERATION_ID.fullmatch(target):
        raise RppError("BAD_REQUEST", "integrations.rollback requires an operation_id.", "Send the operation_id to roll back.")
    return _integrations(lambda m: m.rollback(ctx, target))


def _memory_link(call):
    from . import memory_link
    try:
        return call(memory_link)
    except installation.OperationError as error:
        raise RppError(error.code, error.message, error.hint)


def _memory_connect(ctx, operation_id, payload):
    write = payload.get("write", False)
    if not isinstance(write, bool):
        raise RppError("BAD_REQUEST", "write must be true or false.", "Send {\"write\": false}.")
    return _memory_link(lambda m: m.connect(ctx, write=write))


def _memory_disconnect(ctx, operation_id, payload):
    return _memory_link(lambda m: m.disconnect(ctx))


def _memory_status(ctx, operation_id, payload):
    return _memory_link(lambda m: m.status(ctx))


_OPS = {
    "manifest": _manifest,
    "health": health,
    "settings.schema": _settings_schema,
    "settings.validate": _settings_validate,
    "settings.apply": _settings_apply,
    "settings.readback": _settings_readback,
    "integrations.plan": _integrations_plan,
    "integrations.apply": _integrations_apply,
    "integrations.rollback": _integrations_rollback,
    "memory.connect": _memory_connect,
    "memory.disconnect": _memory_disconnect,
    "memory.status": _memory_status,
}


def handle_request(request, ctx):
    """Dispatch one parsed request. Always returns a full response dict."""
    operation_id = None
    try:
        if not isinstance(request, dict):
            raise RppError("BAD_REQUEST", "Request must be a JSON object.", "Send a single JSON object with rpp, op and payload.")
        raw_id = request.get("operation_id")
        if raw_id is not None:
            if not isinstance(raw_id, str) or not _OPERATION_ID.fullmatch(raw_id):
                raise RppError("BAD_REQUEST", "operation_id must be 8-64 characters of [A-Za-z0-9_-].", "Fix the operation_id and retry.")
            operation_id = raw_id
        if request.get("rpp") != RPP:
            raise RppError("UNSUPPORTED_VERSION", "Unsupported protocol version.", f"Send rpp '{RPP}'.")
        op = request.get("op")
        handler = _OPS.get(op)
        if handler is None:
            raise RppError("UNKNOWN_OP", f"Unknown op {op!r}.", "Use one of: " + ", ".join(sorted(_OPS)) + ".")
        payload = request.get("payload")
        return _response(True, operation_id, handler(ctx, operation_id, payload if isinstance(payload, dict) else {}), None)
    except RppError as error:
        return _fail(operation_id, error.code, error.message, error.hint)
    except Exception:
        return _fail(operation_id, "INTERNAL", "The request could not be completed.", "Retry; if it persists, inspect the product data root.")


def handle_raw(text, ctx):
    """Parse raw stdin text; malformed JSON becomes a BAD_REQUEST, not a traceback."""
    try:
        request = json.loads(text)
    except (ValueError, TypeError):
        return _fail(None, "BAD_REQUEST", "Request is not valid JSON.", "Send one JSON object on stdin.")
    return handle_request(request, ctx)


def run(ctx, stream=None):
    raw = (stream or sys.stdin.buffer).read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    response = handle_raw(raw, ctx)
    print(json.dumps(response, ensure_ascii=True))
    return 0 if response["ok"] else 1
