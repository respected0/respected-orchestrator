"""Connecting to SecondBrain's memory without the Hub: SecondBrain grants, the Orchestrator stores the grant.

`connect` asks the installed SecondBrain (its own `rpp` server at its standard place) for a grant and writes the
Orchestrator's memory settings through the same code as `config set`; `disconnect` revokes it and clears them.
The grant token exists only between the two calls and is never returned or logged.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from ..engine import winproc
from .installation import OperationError


def brain_exe():
    """SecondBrain's program at its standard place (the one its installer uses)."""
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Respected/RespectedBrain/app/respectedbrain.exe"
    if sys.platform == "darwin":
        return Path.home() / "Applications/RespectedBrain.app/Contents/MacOS/respectedbrain"
    return Path.home() / ".local/lib/respectedbrain/respectedbrain"


def _call(exe, op, payload=None, *, operation=False):
    request = {"rpp": "1", "op": op, "payload": payload or {}}
    if operation:
        request["operation_id"] = "orch-" + uuid.uuid4().hex[:16]
    try:
        done = winproc.run([str(exe), "rpp"], input=json.dumps(request).encode("utf-8"), capture_output=True, timeout=60,
                           cwd=tempfile.gettempdir())
        lines = [line for line in done.stdout.decode("utf-8", "replace").splitlines() if line.strip().startswith("{")]
        return json.loads(lines[-1])
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        return {"ok": False, "error": {"code": "BRAIN_UNREACHABLE", "message": "SecondBrain yanıt vermedi.", "hint": "SecondBrain kurulumunu onarın."}}


def _failure(reply, what):
    error = reply.get("error") or {}
    return OperationError(error.get("code") or "BRAIN_FAILED", f"{what}: {error.get('message') or 'yanıt yok'}", error.get("hint") or "")


def _settings(ctx):
    from .rpp import read_settings
    return read_settings(ctx)


def _apply(ctx, values):
    from .rpp import RppError, apply_settings
    try:
        apply_settings(ctx, values)
    except RppError as error:
        raise OperationError(error.code, error.message, error.hint) from None


def status(ctx):
    current = _settings(ctx)
    return {"connected": current["memory_enabled"] is True, "write": current["memory_write"] is True,
            "grant_id": current["memory_grant_id"] or None, "brain": str(brain_exe())}


def connect(ctx, *, write=False, exe=None):
    exe = Path(exe or brain_exe())
    if not exe.is_file():
        raise OperationError("NOT_INSTALLED", "SecondBrain bu bilgisayarda kurulu değil.", "Önce SecondBrain'i kurun.")
    current = _settings(ctx)
    if current["memory_enabled"] is True and current["memory_grant_id"] and current["memory_write"] is write:
        return status(ctx)
    if current["memory_grant_id"]:  # an earlier grant (another mode, or a disconnect that could not revoke) closes first
        _call(exe, "memory.revoke", {"grant_id": current["memory_grant_id"]})
    granted = _call(exe, "memory.grant", {"label": "Orchestrator", "write": write}, operation=True)
    if granted.get("ok") is not True:
        raise _failure(granted, "SecondBrain izin vermedi")
    grant_id, token = granted["result"].get("grant_id"), granted["result"].get("token")
    try:
        _apply(ctx, {"memory_enabled": True, "memory_write": write, "memory_grant_id": grant_id, "memory_token": token,
                     "memory_command": json.dumps({"argv": [str(exe), "rpp"], "env": {}})})
    except OperationError:
        _call(exe, "memory.revoke", {"grant_id": grant_id})  # no half-made connection
        raise
    return status(ctx)


def disconnect(ctx, *, exe=None):
    exe = Path(exe or brain_exe())
    current = _settings(ctx)
    revoked = True
    if current["memory_grant_id"] and exe.is_file():
        revoked = _call(exe, "memory.revoke", {"grant_id": current["memory_grant_id"]}).get("ok") is True
    values = {"memory_enabled": False, "memory_write": False, "memory_command": "", "memory_token": ""}
    if revoked or not exe.is_file():  # keep the grant id while SecondBrain is there but could not revoke, so it can be retried
        values["memory_grant_id"] = ""
    _apply(ctx, values)
    return {**status(ctx), "revoked": revoked}
