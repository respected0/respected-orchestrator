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
from . import read_model
from ..workflows import dag_view, plan_draft, project_control
from .journal import Journal
from .lanes import _pid_is_alive
from .supervisor import Supervisor

IPC = "1"
MAX_REQUEST_BYTES = 64 * 1024
MAX_EVENTS_PER_CALL = 500
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
    "events.snapshot": (None, Action.READ),
    "events.since": (None, Action.READ),
    "runs.active": (None, Action.READ),
    "runs.list": (None, Action.READ),
    "projects.list": (None, Action.READ),
    "plan.view": (None, Action.READ),
    "plan.create": (None, Action.TASK),
    "plan.edit": (None, Action.TASK),
    "plan.start": (None, Action.TASK),
    "project.status": (None, Action.READ),
    "project.cancel": (None, Action.TASK),
    "project.resume": (None, Action.TASK),
}
ERRORS = ("BAD_REQUEST", "UNSUPPORTED_VERSION", "UNAUTHENTICATED", "UNKNOWN_COMMAND", "FORBIDDEN",
          "PAYLOAD_TOO_LARGE", "REPLAY_CONFLICT", "ENGINE_ERROR")


def _reply(corr, ok, result=None, code=None, message=""):
    error = None if ok else {"code": code, "message": message}
    return {"ipc": IPC, "id": corr, "ok": ok, "result": result, "error": error}


class LocalApi:
    def __init__(self, ctx, token, origin=Origin.RENDERER, journal=None):
        if not isinstance(token, str) or len(token) < 16:
            raise ValueError("session token must be at least 16 characters")
        self.ctx, self._token, self.origin = ctx, token, origin
        self.journal = journal
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

    def _project(self, corr, command, payload):
        pid = payload.get("project_id")
        try:
            if command == "project.status":
                return _reply(corr, True, project_control.status(self.ctx, pid))
            action = project_control.cancel if command == "project.cancel" else project_control.resume
            return _reply(corr, True, action(self.ctx, pid, corr))
        except (ValueError, TypeError, KeyError, OSError) as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=str(error)[:300])

    def _plan(self, corr, command, payload):
        """Draft editing and the separate start action. Every rule is enforced by plan_draft from the stored draft."""
        try:
            if command == "plan.create":
                result = plan_draft.create_draft(self.ctx, payload.get("spec"), payload.get("project_root"))
            elif command == "plan.edit":
                result = plan_draft.edit_draft(self.ctx, payload.get("draft_id"), payload.get("revision"), payload.get("edits"))
            else:
                if self.origin not in (Origin.HUMAN, Origin.RENDERER):  # MCP and orchestrated processes edit nothing into a running plan
                    return _reply(corr, False, code="FORBIDDEN", message="Only the operator may start a plan.")
                result = plan_draft.start_draft(self.ctx, payload.get("draft_id"), payload.get("revision"), payload.get("confirm_hash"),
                                                origin=self.origin)
            return _reply(corr, True, result)
        except PermissionError:
            return _reply(corr, False, code="FORBIDDEN", message="Not allowed for this origin.")
        except (ValueError, TypeError, KeyError) as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=str(error)[:300])

    def _board(self, corr, command, payload):
        """Read-only board pages from the engine's own files; malformed filters are refused, never guessed."""
        states, query, order = payload.get("states"), payload.get("query"), payload.get("order", "newest")
        cursor, limit = payload.get("cursor"), payload.get("limit", 50)
        if (states is not None and not (isinstance(states, list) and all(isinstance(x, str) for x in states)))                 or (query is not None and not isinstance(query, str)) or order not in ("newest", "oldest")                 or (cursor is not None and not isinstance(cursor, str)) or type(limit) is not int:
            return _reply(corr, False, code="BAD_REQUEST", message="Bad filter, order, cursor or limit.")
        try:
            if command == "runs.list":
                return _reply(corr, True, read_model.runs_page(self.ctx, states=states, query=query, newest_first=order == "newest",
                                                               cursor=cursor, limit=limit))
            return _reply(corr, True, read_model.projects_page(self.ctx, cursor=cursor, limit=limit))
        except ValueError as error:
            return _reply(corr, False, code="BAD_REQUEST", message=str(error))

    def _events(self, corr, command, payload):
        if self.journal is None:
            return _reply(corr, False, code="ENGINE_ERROR", message="No event journal.")
        if command == "events.snapshot":
            return _reply(corr, True, self.journal.snapshot())
        after, limit = payload.get("after", 0), payload.get("limit", MAX_EVENTS_PER_CALL)
        if not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in (after, limit)):
            return _reply(corr, False, code="BAD_REQUEST", message="after and limit must be non-negative integers.")
        limit = min(limit or MAX_EVENTS_PER_CALL, MAX_EVENTS_PER_CALL)  # bounded page: a slow consumer just pulls again
        last = self.journal.last_seq
        events = self.journal.replay(after=after, limit=limit)
        # gap: the cursor is ahead of the journal (rotated/reset) or the first event is not the next one; the UI must resnapshot.
        gap = after > last or (bool(events) and events[0]["seq"] != after + 1)
        return _reply(corr, True, {"events": events, "last_seq": last, "gap": gap, "has_more": bool(events) and events[-1]["seq"] < last})

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
        if command == "runs.active":
            claims = Supervisor(self.ctx).claims()
            response = _reply(corr, True, {"runs": {run: pid for run, pid in claims.items() if _pid_is_alive(int(pid))}})
        elif command.startswith("project."):
            response = self._project(corr, command, payload)
        elif command in ("plan.create", "plan.edit", "plan.start"):
            response = self._plan(corr, command, payload)
        elif command == "plan.view":
            spec, root = payload.get("spec"), payload.get("project_root")
            if not isinstance(spec, dict) or not isinstance(root, str) or not root:
                response = _reply(corr, False, code="BAD_REQUEST", message="plan.view needs spec (object) and project_root (string).")
            else:
                response = _reply(corr, True, dag_view.dag_view(spec, root))
        elif command in ("runs.list", "projects.list"):
            response = self._board(corr, command, payload)
        elif command.startswith("events."):
            response = self._events(corr, command, payload)
        elif op is None:
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


def serve(ctx, stdin, stdout, environ):
    """Line-delimited loop over the parent's own pipes: only the process that spawned us can talk to us.

    The token arrives in RESPECTED_IPC_TOKEN (never argv) and is dropped from the environment so children cannot inherit it.
    """
    token = environ.pop("RESPECTED_IPC_TOKEN", "")
    api = LocalApi(ctx, token, journal=Journal(ctx.state_dir / "events.log"))
    for line in stdin:
        if line.strip():
            stdout.write(json.dumps(api.handle_raw(line.encode("utf-8")), ensure_ascii=True) + "\n")
            stdout.flush()
    return 0
