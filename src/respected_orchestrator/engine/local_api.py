"""Typed local IPC for the desktop shell (B3-01.02, ADR-022). Wraps RPP; never changes it.

One request in, one response out. Only allowlisted commands are reachable, every call needs the session
token and is checked against the authority matrix, and every response carries the caller's correlation id.
"""
import hashlib
import hmac
import json
import re

from ..interfaces import rpp
from .authority import Action, Origin, authorize

IPC = "1"
MAX_REQUEST_BYTES = 64 * 1024
_ID = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_CACHE_LIMIT = 256

# command -> (RPP op, authority class). Anything not listed does not exist for the shell.
COMMANDS = {
    "hello": (None, Action.READ),
    "engine.manifest": ("manifest", Action.READ),
    "engine.health": ("health", Action.READ),
    "settings.schema": ("settings.schema", Action.READ),
    "settings.readback": ("settings.readback", Action.READ),
    "settings.validate": ("settings.validate", Action.READ),
    "settings.apply": ("settings.apply", Action.SETTINGS),
    "evidence.view": ("evidence.view", Action.READ),
    "memory.status": ("memory.status", Action.READ),
}
ERRORS = ("BAD_REQUEST", "UNSUPPORTED_VERSION", "UNAUTHENTICATED", "UNKNOWN_COMMAND", "FORBIDDEN",
          "PAYLOAD_TOO_LARGE", "REPLAY_CONFLICT", "ENGINE_ERROR")


def _reply(corr, ok, result=None, code=None, message=""):
    error = None if ok else {"code": code, "message": message}
    return {"ipc": IPC, "id": corr, "ok": ok, "result": result, "error": error}


class LocalApi:
    def __init__(self, ctx, token, origin=Origin.RENDERER):
        if not isinstance(token, str) or len(token) < 16:
            raise ValueError("session token must be at least 16 characters")
        self.ctx, self._token, self.origin = ctx, token, origin
        self._seen = {}  # id -> (request digest, response)

    def handle_raw(self, raw):
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if len(raw) > MAX_REQUEST_BYTES:
            return _reply(None, False, code="PAYLOAD_TOO_LARGE", message="Request exceeds the size limit.")
        try:
            request = json.loads(raw)
        except (ValueError, RecursionError):
            return _reply(None, False, code="BAD_REQUEST", message="Request is not valid JSON.")
        return self.handle(request)

    def handle(self, request):
        corr = request.get("id") if isinstance(request, dict) else None
        corr = corr if isinstance(corr, str) and _ID.fullmatch(corr) else None
        if not isinstance(request, dict) or corr is None:
            return _reply(None, False, code="BAD_REQUEST", message="Request needs an object with a valid id.")
        if request.get("ipc") != IPC:
            return _reply(corr, False, code="UNSUPPORTED_VERSION", message=f"Send ipc '{IPC}'.")
        token = request.get("session")
        if not isinstance(token, str) or not hmac.compare_digest(token.encode(), self._token.encode()):
            return _reply(corr, False, code="UNAUTHENTICATED", message="Missing or wrong session token.")
        command = request.get("cmd")
        if not isinstance(command, str) or command not in COMMANDS:
            return _reply(corr, False, code="UNKNOWN_COMMAND", message="Unknown command.")
        payload = request.get("payload", {})
        if not isinstance(payload, dict):
            return _reply(corr, False, code="BAD_REQUEST", message="payload must be an object.")
        op, action = COMMANDS[command]
        try:
            authorize(self.origin, action)
        except PermissionError:
            return _reply(corr, False, code="FORBIDDEN", message="Not allowed for this origin.")
        digest = hashlib.sha256(json.dumps([command, payload], sort_keys=True).encode()).hexdigest()
        if corr in self._seen:  # same id: idempotent retry of the same call, never a different one
            if self._seen[corr][0] != digest:
                return _reply(corr, False, code="REPLAY_CONFLICT", message="id was already used for a different request.")
            return self._seen[corr][1]
        if op is None:
            response = _reply(corr, True, {"ipc": IPC, "commands": sorted(COMMANDS), "max_request_bytes": MAX_REQUEST_BYTES})
        else:
            answer = rpp.handle_request({"rpp": rpp.RPP, "op": op, "operation_id": corr, "payload": payload}, self.ctx)
            if answer["ok"]:
                response = _reply(corr, True, answer["result"])
            else:
                response = _reply(corr, False, code="ENGINE_ERROR", message=answer["error"]["message"])
        if len(self._seen) >= _CACHE_LIMIT:
            self._seen.pop(next(iter(self._seen)))
        self._seen[corr] = (digest, response)
        return response
