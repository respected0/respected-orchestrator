"""Respected Product Protocol (RPP) v1.0/1.1: one JSON request in, one JSON response line out.

Private module used by the Hub and tests; it is not a daemon and opens no network
listener. Every failure is returned as a structured error, never raised.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile

from .. import __version__
from . import lifecycle
from . import memory
from ..workflows import roles
from ..engine import runner
from ..context import atomic_write_json, safe_path

PROTOCOL_MIN = "1.0"
PROTOCOL_MAX = "1.1"
PRODUCT_ID = "respected-orchestrator"
CAPABILITIES = [
    "task.create", "task.inspect", "task.cancel", "task.retry",
    "campaign.start", "campaign.status", "maf.workflow", "apply.verified-patch",
]

_OPERATION_ID = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_WORKER_CHOICES = [agent for agent in runner.SUPPORTED_AGENTS if agent != "custom"]

_SETTINGS_FIELDS = [
    {"key": "default_worker", "type": "enum", "label": "Default worker CLI",
     "default": "codex", "secret": False, "enum": _WORKER_CHOICES},
    {"key": "default_worker_profile", "type": "string", "label": "Default worker profile",
     "default": "", "secret": False},
    {"key": "default_reviewer_profile", "type": "string", "label": "Default reviewer profile",
     "default": "", "secret": False},
    {"key": "default_timeout_seconds", "type": "integer", "label": "Default timeout (seconds)",
     "default": 900, "secret": False, "min": 60, "max": 3600},
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


def _response(ok, operation_id, result, error, version=PROTOCOL_MIN):
    return {"rpp": version, "ok": ok, "operation_id": operation_id, "result": result, "error": error}


def _ok(operation_id, result, version=PROTOCOL_MIN):
    return _response(True, operation_id, result, None, version)


def _fail(operation_id, code, message, hint, version=PROTOCOL_MIN):
    return _response(False, operation_id, None, {"code": code, "message": message, "hint": hint}, version)


def _version_tuple(value):
    if not isinstance(value, str):
        return None
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return None


def _supported(value):
    parsed = _version_tuple(value)
    return parsed is not None and _version_tuple(PROTOCOL_MIN) <= parsed <= _version_tuple(PROTOCOL_MAX)


def _capability_details():
    details = [{"id": capability, "since": "1.0", "ops": [capability]} for capability in CAPABILITIES]
    details.append({"id": "lifecycle", "since": "1.1",
                    "ops": ["lifecycle.plan", "lifecycle.apply", "lifecycle.status", "lifecycle.rollback"]})
    details.append({"id": "operation.receipt", "since": "1.1", "ops": ["operation.receipt"]})
    details.append({"id": "integrations", "since": "1.1", "ops": ["integrations.plan", "integrations.apply", "integrations.rollback"]})
    return details


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


def _redact(settings, fields=None):
    """Blank secret fields; secrets are accepted but never returned."""
    fields = _SETTINGS_FIELDS if fields is None else fields
    redacted = dict(settings)
    for field in fields:
        key = field["key"]
        if field.get("secret") and redacted.get(key) not in (None, ""):
            redacted[key] = "***set***"
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


def _manifest(ctx, operation_id, payload):
    state = lifecycle.verify(ctx.app_root)
    return {
        "product_id": PRODUCT_ID,
        "product_version": __version__,
        "protocol": {"min": PROTOCOL_MIN, "max": PROTOCOL_MAX},
        "capabilities": list(CAPABILITIES),
        "settings_supported": True,
        "installed": state["installed"],
        "install_state": state["install_state"],
        "roots": {"data": str(ctx.data_root), "app": str(ctx.app_root), "vault": None},
        "capability_details": _capability_details(),
    }


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


def _health(ctx, operation_id, payload):
    workers = [agent for agent in _WORKER_CHOICES if runner.get_cli_command(agent)]
    git = runner.shutil.which("git")
    writable = _data_root_writable(ctx)
    key_ok = _engine_key_ok(ctx)
    checks = [
        {"name": "data_root_writable", "ok": writable,
         "detail": "data root accepts writes" if writable else "data root is not writable"},
        {"name": "git_available", "ok": bool(git), "detail": git or "git not found on PATH"},
        {"name": "worker_cli", "ok": bool(workers),
         "detail": ", ".join(workers) if workers else "no supported worker CLI resolved"},
        {"name": "engine_key", "ok": key_ok,
         "detail": "engine key present and readable" if key_ok else "engine key missing or unreadable"},
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
        raise RppError("BAD_REQUEST", "settings.apply requires an operation_id.",
                       "Send an operation_id of 8-64 characters.")
    settings = payload.get("settings")
    errors = validate_settings(settings, ctx)
    if errors:
        raise RppError("INVALID_SETTINGS", "Settings failed validation.",
                       "Fix the reported fields and retry; nothing was written.")
    # Merge: defaults < stored settings.json < incoming keys, so partial applies keep unrelated keys.
    normalized = _normalize({**_stored_settings(ctx), **settings})
    incoming = settings.get("memory_token", memory.REDACTED)
    token = memory.load_token(ctx.data_root) if incoming == memory.REDACTED else (incoming or None)
    # the digest changes with the token without containing it
    digest = _settings_digest({**normalized, "memory_token_sha256": hashlib.sha256(token.encode()).hexdigest() if token else ""})
    receipt_path = _receipt_path(ctx, operation_id)
    if receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text("utf-8"))
        except (OSError, ValueError):
            raise RppError("INTERNAL", "Stored receipt is unreadable.",
                           "Inspect the receipts directory for this operation_id.")
        if receipt.get("settings_sha256") == digest:
            return {"status": "applied", "applied_at": receipt.get("applied_at"), "settings_sha256": digest}
        raise RppError("OPERATION_ID_CONFLICT", "operation_id was already used with different settings.",
                       "Use a new operation_id for different settings.")
    applied_at = _now()
    receipt = {"operation_id": operation_id, "op": "settings.apply", "status": "applied",
               "applied_at": applied_at, "settings_sha256": digest}
    if incoming == "":
        memory.clear_token(ctx.data_root)
    elif incoming != memory.REDACTED:
        memory.store_token(ctx.data_root, incoming)
    atomic_write_json(_settings_path(ctx), normalized)
    atomic_write_json(receipt_path, receipt)
    return {"status": "applied", "applied_at": applied_at, "settings_sha256": digest}


def _settings_readback(ctx, operation_id, payload):
    path = _settings_path(ctx)
    if path.is_file():
        try:
            stored = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            raise RppError("INTERNAL", "Stored settings are unreadable.",
                           "Fix or remove settings.json in the data root.")
        if not isinstance(stored, dict):
            raise RppError("INTERNAL", "Stored settings are malformed.",
                           "Fix or remove settings.json in the data root.")
        source = "file"
    else:
        stored, source = {}, "defaults"
    effective = _defaults()
    for key in effective:
        if key in stored:
            effective[key] = stored[key]
    effective["memory_token"] = memory.REDACTED if memory.token_set(ctx.data_root) else ""
    return {"settings": _redact(effective), "source": source}


def _lifecycle(call):
    try:
        return call()
    except lifecycle.LifecycleError as error:
        raise RppError(error.code, error.message, error.hint)


def _lifecycle_plan(ctx, operation_id, payload):
    if not isinstance(payload.get("target"), dict):
        raise RppError("BAD_REQUEST", "lifecycle.plan requires a target object.",
                       'Send {"action": ..., "target": {...}}.')
    return _lifecycle(lambda: lifecycle.plan(payload.get("action"), payload["target"]))


def _lifecycle_apply(ctx, operation_id, payload):
    if not operation_id:
        raise RppError("BAD_REQUEST", "lifecycle.apply requires an operation_id.",
                       "Send an operation_id of 8-64 characters.")
    if not isinstance(payload.get("target"), dict):
        raise RppError("BAD_REQUEST", "lifecycle.apply requires a target object.",
                       'Send {"action": ..., "target": {...}}.')
    return _lifecycle(lambda: lifecycle.apply(ctx, operation_id, payload.get("action"), payload["target"]))


def _receipt_op(ctx, operation_id, payload):
    target = payload.get("operation_id") or operation_id
    if not isinstance(target, str) or not _OPERATION_ID.fullmatch(target):
        raise RppError("BAD_REQUEST", "An operation_id of 8-64 characters is required.",
                       "Send the operation_id whose receipt you want.")
    return _lifecycle(lambda: lifecycle.receipt(ctx, target))


def _lifecycle_rollback(ctx, operation_id, payload):
    target = payload.get("operation_id") or operation_id
    if not isinstance(target, str) or not _OPERATION_ID.fullmatch(target):
        raise RppError("BAD_REQUEST", "lifecycle.rollback requires an operation_id.",
                       "Send the operation_id of the apply to roll back.")
    return _lifecycle(lambda: lifecycle.rollback(ctx, target))


def _integrations(call):
    from . import integrations
    try:
        return call(integrations)
    except lifecycle.LifecycleError as error:
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


_OPS = {
    "manifest": _manifest,
    "health": _health,
    "settings.schema": _settings_schema,
    "settings.validate": _settings_validate,
    "settings.apply": _settings_apply,
    "settings.readback": _settings_readback,
    "lifecycle.plan": _lifecycle_plan,
    "lifecycle.apply": _lifecycle_apply,
    "lifecycle.status": _receipt_op,
    "lifecycle.rollback": _lifecycle_rollback,
    "operation.receipt": _receipt_op,
    "integrations.plan": _integrations_plan,
    "integrations.apply": _integrations_apply,
    "integrations.rollback": _integrations_rollback,
}


_OP_SINCE = {
    "lifecycle.plan": "1.1",
    "lifecycle.apply": "1.1",
    "lifecycle.status": "1.1",
    "lifecycle.rollback": "1.1",
    "operation.receipt": "1.1",
    "integrations.plan": "1.1",
    "integrations.apply": "1.1",
    "integrations.rollback": "1.1",
}


def handle_request(request, ctx):
    """Dispatch one parsed request. Always returns a full response dict."""
    operation_id = None
    version = PROTOCOL_MIN
    try:
        if not isinstance(request, dict):
            raise RppError("BAD_REQUEST", "Request must be a JSON object.",
                           "Send a single JSON object with rpp, op and payload.")
        raw_id = request.get("operation_id")
        if raw_id is not None:
            if not isinstance(raw_id, str) or not _OPERATION_ID.fullmatch(raw_id):
                raise RppError("BAD_REQUEST", "operation_id must be 8-64 characters of [A-Za-z0-9_-].",
                               "Fix the operation_id and retry.")
            operation_id = raw_id
        if "rpp" not in request:
            raise RppError("BAD_REQUEST", "Request is missing the rpp version.",
                           "Include rpp set to '1.0' or '1.1'.")
        if not _supported(request.get("rpp")):
            raise RppError("PROTOCOL_UNSUPPORTED", f"Protocol version {request.get('rpp')!r} is not supported.",
                           "Use rpp '1.0' or '1.1'.")
        version = request["rpp"]
        op = request.get("op")
        handler = _OPS.get(op)
        if handler is None:
            raise RppError("UNKNOWN_OP", f"Unknown op {op!r}.",
                           "Use one of: " + ", ".join(sorted(_OPS)) + ".")
        required = _OP_SINCE.get(op, "1.0")
        if _version_tuple(required) > _version_tuple(version):
            raise RppError("UNSUPPORTED_OP", f"Op {op!r} requires rpp '{required}'.",
                           f"Raise rpp to '{required}' to use this op.")
        payload = request.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        return _ok(operation_id, handler(ctx, operation_id, payload), version)
    except RppError as error:
        return _fail(operation_id, error.code, error.message, error.hint, version)
    except Exception:
        return _fail(operation_id, "INTERNAL", "The request could not be completed.",
                     "Retry; if it persists, inspect the product data root.", version)


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
