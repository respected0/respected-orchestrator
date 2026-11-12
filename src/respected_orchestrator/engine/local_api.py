"""Typed local IPC for the desktop shell (B3-01.02, ADR-022). Wraps RPP; never changes it.

One request in, one response out. Only allowlisted commands are reachable, every call needs the session
token and is checked against the authority matrix, and every response carries the caller's correlation id.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

from ..interfaces import rpp
from .evidence import load_signed
from .authority import Action, Origin, authorize, effective_origin
from .capabilities import normalize as capability_normalize, paths as capability_paths
from . import catalog, runner, session_control, supervisor
from .session_store import SessionStore
from .terminals import TerminalError, Terminals, mode_supported
from . import activity, agent_describe, agent_discovery, approval, artifact_view, read_model, review_model
from ..workflows import dag_view, plan_draft, project_control, role_editor, roles
from .runner import SUPPORTED_AGENTS, tool_available
from .journal import Journal
from .lanes import _pid_is_alive
from .supervisor import Supervisor

IPC = "1"
MAX_REQUEST_BYTES = 64 * 1024
MAX_EVENTS_PER_CALL = 500
_ID = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
_CACHE_LIMIT = 256
_RUN = re.compile(r"run-[A-Za-z0-9-]{1,80}\Z")
_LOG_TAIL = 3000

# command -> (RPP op, authority class), from the one table (ADR-032). Anything not listed does not exist for the shell.
COMMANDS = {entry.name: (entry.op, entry.action) for entry in catalog.ENTRIES}
ERRORS = ("BAD_REQUEST", "UNSUPPORTED_VERSION", "UNAUTHENTICATED", "UNKNOWN_COMMAND", "FORBIDDEN",
          "PAYLOAD_TOO_LARGE", "REPLAY_CONFLICT", "ENGINE_ERROR", *sorted(runner.PERMISSION_CODES))
_PERMISSION_MESSAGES = {
    "PERMISSION_NOT_FOUND": "Bekleyen bir izin isteği bulunamadı.",
    "PERMISSION_CLOSED": "Görev artık izin beklemiyor.",
    "PERMISSION_ALREADY_ANSWERED": "Bu izin zaten yanıtlandı.",
    "PERMISSION_EXPIRED": "İzin isteğinin süresi doldu.",
    "PERMISSION_OPTION_INVALID": "Bu seçenek izin isteğine ait değil.",
    "PERMISSION_REQUEST_INVALID": "İzin isteği bozuk; yanıtlanamaz.",
    "FORBIDDEN": "Bu kaynaktan izin yanıtlanamaz.",
}


def _reply(corr, ok, result=None, code=None, message="", reason=None):
    error = None if ok else {"code": code, "message": message, **({"reason": reason} if reason else {})}
    return {"ipc": IPC, "id": corr, "ok": ok, "result": result, "error": error}


def session_controller(ctx):
    """The chat sessions of one data root: live in memory, saved under `chat/sessions.json`."""
    data_root = getattr(ctx, "data_root", None)
    store = SessionStore(Path(data_root) / "chat" / "sessions.json") if data_root else None
    return session_control.SessionController(store=store)


class LocalApi:
    def __init__(self, ctx, token, origin=Origin.RENDERER, journal=None, only=None, sessions=None, subscribe=None, terminals=None, attach=None):
        if not isinstance(token, str) or len(token) < 16:
            raise ValueError("session token must be at least 16 characters")
        self.ctx, self._token, self.origin = ctx, token, origin
        self.journal = journal
        self.only = only  # a connection that may use just these commands (the native approval pipe)
        self.subscribe = subscribe  # fn(project_id): the transport turns this connection into a notification stream (persistent engine only)
        self.attach = attach  # fn((terminal_id, source)): the transport turns this connection into that terminal's output stream
        self.terminals = terminals or Terminals(ctx)
        self._seen = {}  # id -> (request digest, response)
        self._voice_api = None
        self._attach_api = None
        self.sessions = sessions or session_controller(ctx)  # the persistent engine hands every connection the one it owns (ADR-030)

    def _may(self, entry):
        """True when this connection could run the command: the same two checks `handle` makes."""
        if self.only is not None and entry.name not in self.only:
            return False
        try:
            authorize(self.origin, entry.action)
        except PermissionError:
            return False
        return True

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

    def _task(self, corr, command, payload):
        """One isolated task run. Anyone but the operator at a terminal gets the MCP rules: no custom worker or command, and
        acceptance commands only from the user's own list (setting mcp_acceptance_allow)."""
        try:
            if command == "task.start":
                if self.origin is not Origin.HUMAN:
                    from ..interfaces import mcp_server  # the one place these two rules live
                    mcp_server._refuse_privileged(payload, False)
                    mcp_server._refuse_unlisted_commands(self.ctx, payload, False)
                created = runner.create_task(self.ctx, payload)
                return _reply(corr, True, dict(created, **runner.start_task(self.ctx, created["run_id"])))
            run_id = payload.get("run_id")
            if not isinstance(run_id, str) or not _RUN.fullmatch(run_id):
                return _reply(corr, False, code="BAD_REQUEST", message="run_id must be a run-* identity.")
            if command == "task.cancel":
                return _reply(corr, True, runner.cancel_task(self.ctx, run_id))
            if command == "task.retry":
                retried = runner.retry_task(self.ctx, run_id)
                return _reply(corr, True, dict(retried, **runner.start_task(self.ctx, retried["run_id"])) if "run_id" in retried else retried)
            if command == "task.permission.answer":
                try:
                    answered = runner.answer_permission(self.ctx, run_id, payload.get("request_id"),
                                                        payload.get("option_id"), origin=self.origin)
                except runner.PermissionAnswerError as error:
                    return _reply(corr, False, code=error.code,
                                  message=_PERMISSION_MESSAGES.get(error.code, "İzin yanıtlanamadı."))
                return _reply(corr, True, answered)
            entry = dict(runner.inspect_task(self.ctx, run_id))
            entry["logs"] = {name: text[-_LOG_TAIL:] for name, text in entry.get("logs", {}).items()}
            entry["patch_preview"] = entry.get("patch_preview", "")[:_LOG_TAIL]
            return _reply(corr, True, entry)
        except FileNotFoundError:  # its message would carry a path of the data folder
            return _reply(corr, False, code="ENGINE_ERROR", message="Unknown run.")
        except (ValueError, TypeError, KeyError, OSError) as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=str(error)[:300])

    def _approval(self, corr, command, payload):
        """The approval protocol; the origin check in handle() already kept every non-human origin away from decide/apply."""
        try:
            if command == "approval.open":
                result = approval.open_challenge(self.ctx, payload.get("run_id"), origin=self.origin)
            elif command == "approval.decide":
                result = approval.decide(self.ctx, payload.get("challenge_id"), payload.get("decision"), payload.get("binding"), origin=self.origin)
            else:
                result = approval.apply_with_grant(self.ctx, payload.get("token"), payload.get("run_id"), origin=self.origin)
            return _reply(corr, True, result)
        except PermissionError:
            return _reply(corr, False, code="FORBIDDEN", message="Not allowed for this origin.")
        except (ValueError, TypeError, KeyError, OSError) as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=str(error)[:300])

    def _voice(self, corr, command, payload):
        """Push-to-talk. Every refusal wipes the audio (voice.py); the answer is a draft that nothing consumes without a person's edit."""
        from . import voice, voice_api
        if self._voice_api is None:
            self._voice_api = voice_api.VoiceApi(lambda: roles.read_settings(self.ctx.data_root))
        api = self._voice_api
        try:
            if command == "voice.status":
                return _reply(corr, True, api.status())
            if command == "voice.start":
                return _reply(corr, True, api.start(payload.get("permission")))
            if command == "voice.feed":
                return _reply(corr, True, api.feed(payload.get("token"), payload.get("chunk"), payload.get("permission")))
            if command == "voice.stop":
                return _reply(corr, True, api.stop(payload.get("token"), payload.get("language"), payload.get("vocabulary")))
            return _reply(corr, True, api.cancel())
        except voice.VoiceError as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=f"{error.code}: {error.message}"[:300])

    def _attachment(self, corr, command, payload):
        """Screenshot attachments. Commit/share/revoke exist only on the native presence connection (PRIVILEGED); everything else the renderer may do."""
        from . import attachment, attachment_api
        if self._attach_api is None:
            self._attach_api = attachment_api.AttachApi(self.ctx, lambda: roles.read_settings(self.ctx.data_root))
        api, name = self._attach_api, command.split(".", 1)[1]
        try:
            if name == "status":
                result = api.status()
            elif name == "arm":
                result = api.arm(payload.get("permission"))
            elif name == "part":
                result = api.part(payload.get("token"), payload.get("seq"), payload.get("chunk"))
            elif name == "stage":
                result = api.stage(payload.get("token"), payload.get("monitor"), payload.get("dpi_scale"))
            elif name == "preview":
                result = api.preview(payload.get("stage_id"))
            elif name == "describe":
                result = api.describe(payload.get("stage_id"))
            elif name == "list":
                result = api.records(payload.get("run_id"))
            elif name == "cancel":
                result = api.cancel(payload.get("stage_id"))
            elif name == "delete":
                result = api.delete_run(payload.get("run_id"))
            elif name == "commit":
                result = attachment_api.commit(self.ctx, payload.get("stage_id"), payload.get("run_id"), payload.get("sha256"), payload.get("redacted_regions", 0), self.origin)
            elif name == "share":
                result = attachment_api.share(self.ctx, payload.get("run_id"), payload.get("attachment_id"), payload.get("provider"), self.origin)
            else:
                result = attachment_api.revoke(self.ctx, payload.get("run_id"), payload.get("attachment_id"), self.origin)
            return _reply(corr, True, result)
        except attachment.AttachError as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=f"{error.code}: {error.message}"[:300])

    def _session(self, corr, command, payload):
        """Session commands; the controller checks the authority class again and never has an approve path."""
        pid, sid = payload.get("project_id"), payload.get("session_id")
        try:
            if command == "sessions.list":
                return _reply(corr, True, {"sessions": self.sessions.view(self.origin, pid),
                                           "conversations": self.sessions.conversations(self.origin, pid, payload.get("query"),
                                                                                         bool(payload.get("include_archived", False)))})
            name = command.split(".", 1)[1]
            if name == "models":
                return _reply(corr, True, self.sessions.models(self.origin, payload.get("agent", self.sessions.store.defaults()["agent"])))
            if name == "defaults":
                return _reply(corr, True, self.sessions.defaults(self.origin))
            if name == "defaults.set":
                return _reply(corr, True, self.sessions.set_defaults(self.origin, payload.get("agent", self.sessions.store.defaults()["agent"]), payload.get("model")))
            if name == "mode.set":
                return _reply(corr, True, self.sessions.set_mode(self.origin, sid, pid, payload.get("mode")))
            if name == "transcript":
                return _reply(corr, True, self.sessions.transcript(self.origin, sid, payload.get("before"), payload.get("limit", session_control.PAGE_TURNS)))
            if name == "forget":
                return _reply(corr, True, self.sessions.forget(self.origin, sid))
            if name == "rename":
                return _reply(corr, True, self.sessions.rename(self.origin, sid, payload.get("title")))
            if name == "pin":
                return _reply(corr, True, self.sessions.pin(self.origin, sid, payload.get("pinned")))
            if name == "archive":
                return _reply(corr, True, self.sessions.archive(self.origin, sid, payload.get("archived")))
            if name == "export":
                return _reply(corr, True, self.sessions.export(self.origin, sid, payload.get("format", "markdown")))
            if name == "start":
                root = payload.get("project_root")
                chosen = self.sessions.store.defaults()
                agent, model = payload.get("agent", chosen["agent"]), payload.get("model", chosen["model"])
                resume = payload.get("resume_session")
                if payload.get("continue_conversation") is not None:  # a saved conversation carries its own folder, agent, model and agent-side session
                    saved = self.sessions.store.get(payload["continue_conversation"])
                    if not saved or not saved.get("cli"):
                        return _reply(corr, False, code="ENGINE_ERROR", message="That conversation cannot be continued.", reason="RESUME_INVALID")
                    root, agent, model, resume = saved["project_root"], saved["agent"], saved["model"], saved["cli"]
                if not (isinstance(root, str) and os.path.isabs(root) and os.path.isdir(root)):
                    return _reply(corr, False, code="BAD_REQUEST", message="project_root must be an existing absolute directory.", reason="ROOT_INVALID")
                if not (isinstance(agent, str) and isinstance(model, str)):
                    return _reply(corr, False, code="BAD_REQUEST", message="agent and model must be strings.", reason="MODEL_INVALID")
                return _reply(corr, True, self.sessions.start(self.origin, pid, agent, model, root, payload.get("text"), wait=False, resume=resume,
                                                              mode=payload.get("mode")))
            args = (self.origin, sid, pid) + ((payload.get("text"),) if name == "send" else ())
            # A turn can take minutes and this loop answers one request at a time: turns run on their own thread (wait=False)
            # so interrupt/cancel stay reachable; the result is read with session.events.
            kwargs = {"wait": False} if name in ("send", "retry") else {}
            return _reply(corr, True, getattr(self.sessions, name)(*args, **kwargs))
        except PermissionError:
            return _reply(corr, False, code="FORBIDDEN", message="Not allowed for this origin.")
        except (ValueError, TypeError, KeyError, OSError, RuntimeError) as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=str(error)[:300], reason=getattr(error, "reason", None))

    def _terminal(self, corr, command, payload):
        """Agent terminals (ADR-035). The origin check in handle() already kept everyone but the recognised desktop away from all but the list."""
        pid, tid = payload.get("project_id"), payload.get("terminal_id")
        try:
            if command == "terminal.list":
                return _reply(corr, True, {"terminals": self.terminals.list(pid)})
            if command == "terminal.start":
                cols, rows = payload.get("cols", 120), payload.get("rows", 30)
                if payload.get("session_id") is not None:  # switch a chat session over: same folder, agent and agent-side session; the chat side is released after the terminal is up
                    sid = payload["session_id"]
                    source = self.sessions.handoff(self.origin, sid, pid)
                    mode = source["mode"] if mode_supported(source["agent"], source["mode"]) else None
                    started = self.terminals.start(pid, source["project_root"], source["agent"], cols, rows, resume=source["resume"],
                                                   conversation=source["conversation"], mode=mode)
                    self.sessions.release(self.origin, sid, pid)
                    return _reply(corr, True, started)
                return _reply(corr, True, self.terminals.start(pid, payload.get("project_root"), payload.get("agent", self.sessions.store.defaults()["agent"]), cols, rows,
                                                               mode=payload.get("mode")))
            if command == "terminal.input":
                return _reply(corr, True, self.terminals.input(tid, pid, payload.get("data")))
            if command == "terminal.resize":
                return _reply(corr, True, self.terminals.resize(tid, pid, payload.get("cols"), payload.get("rows")))
            if command == "terminal.kill":
                return _reply(corr, True, self.terminals.kill(tid, pid))
            if self.attach is None:
                return _reply(corr, False, code="ENGINE_ERROR", message="A terminal is watched over a connection to the persistent engine.")
            self.attach((tid, self.terminals.attach(tid, pid)))
            return _reply(corr, True, {"attached": tid})
        except (TerminalError, session_control.SessionError) as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=str(error)[:300], reason=error.reason)
        except PermissionError:
            return _reply(corr, False, code="FORBIDDEN", message="Not allowed for this origin.")
        except OSError as error:
            return _reply(corr, False, code="ENGINE_ERROR", message=str(error)[:300], reason="TERMINAL_UNREACHABLE")

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
        if command == "events.subscribe":  # ADR-034: after this reply the connection only carries notifications of that project's sessions
            project = payload.get("project_id")
            if not isinstance(project, str) or not project:
                return _reply(corr, False, code="BAD_REQUEST", message="events.subscribe needs project_id.")
            if self.subscribe is None:
                return _reply(corr, False, code="ENGINE_ERROR", message="Notifications need a connection to the persistent engine.")
            self.subscribe(project)
            return _reply(corr, True, {"subscribed": True, "events": list(session_control.NOTIFICATIONS)})
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

    def _beta4_read(self, corr, command, payload):
        """Read-only views for the Beta.4 screens. Each one only reads this installation's own data and the client configs."""
        try:
            settings = roles.read_settings(self.ctx.data_root)
            if command == "team.view":
                from ..workflows import team_view
                return _reply(corr, True, team_view.view(self.ctx, settings, list(SUPPORTED_AGENTS), tool_available))
            if command == "analytics.summary":
                from . import analytics
                limit = payload.get("limit", 400)
                if type(limit) is not int or not 1 <= limit <= 2000:
                    raise ValueError("limit must be an integer from 1 to 2000")
                return _reply(corr, True, analytics.summary(self.ctx, settings, limit=limit))
            task, root, client = payload.get("task"), payload.get("project_root"), payload.get("target_client", "claude-code")
            if not isinstance(task, str) or not 1 <= len(task) <= 2000 or not isinstance(client, str):
                raise ValueError("capabilities.recommend needs task (1-2000 characters) and optionally target_client")
            if root is not None and not (isinstance(root, str) and os.path.isabs(root) and os.path.isdir(root)):
                raise ValueError("project_root must be an existing absolute directory.")
            from .capabilities import recommendation
            home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
            approvals_file = self.ctx.data_root / "capability-approvals.json"
            try:
                approvals = load_signed(self.ctx, approvals_file).get("approvals", []) if approvals_file.is_file() else []
            except (ValueError, OSError, AttributeError):
                approvals = []
            inventory = capability_normalize.build(home, root, approvals=approvals if isinstance(approvals, list) else [])
            risk = {"level": "unknown"}  # a sentence alone carries no scope or acceptance, so its risk is honestly unknown (and untrusted items stay blocked)
            return _reply(corr, True, recommendation.recommend(task, risk, inventory, client, project=root))
        except (ValueError, TypeError) as error:
            return _reply(corr, False, code="BAD_REQUEST", message=str(error)[:300])

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
        if self.only is not None and command not in self.only:
            return _reply(corr, False, code="FORBIDDEN", message="Not available on this connection.")
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
        if command == "catalog.list":
            response = _reply(corr, True, {"commands": catalog.listing(self._may)})
        elif command == "runs.active":
            response = _reply(corr, True, {"runs": supervisor.run_pids(self.ctx)})  # real liveness, not only supervisor claims
        elif command.startswith("project."):
            response = self._project(corr, command, payload)
        elif command.startswith("task."):
            response = self._task(corr, command, payload)
        elif command in ("plan.create", "plan.edit", "plan.start"):
            response = self._plan(corr, command, payload)
        elif command == "plan.view":
            spec, root = payload.get("spec"), payload.get("project_root")
            if not isinstance(spec, dict) or not isinstance(root, str) or not root:
                response = _reply(corr, False, code="BAD_REQUEST", message="plan.view needs spec (object) and project_root (string).")
            else:
                response = _reply(corr, True, dag_view.dag_view(spec, root))
        elif command.startswith("approval."):
            response = self._approval(corr, command, payload)
        elif command.startswith("attachment."):
            response = self._attachment(corr, command, payload)
            if command == "attachment.preview":
                return response  # up to 8 MB of image: never held in the replay cache
        elif command.startswith("voice."):
            response = self._voice(corr, command, payload)
        elif command.startswith("session"):
            response = self._session(corr, command, payload)
        elif command.startswith("terminal."):
            response = self._terminal(corr, command, payload)
            if command in ("terminal.input", "terminal.attach"):
                return response  # keystrokes are not kept in the replay cache, and an attach is never replayed
        elif command == "activity.list":
            if self.journal is None:
                response = _reply(corr, False, code="ENGINE_ERROR", message="No event journal.")
            else:
                try:
                    response = _reply(corr, True, activity.timeline(
                        self.journal, cursor=payload.get("cursor", 0), limit=payload.get("limit", 50), run=payload.get("run"),
                        op=payload.get("op"), stages=payload.get("stages"), types=payload.get("types"),
                        agent=payload.get("agent"), query=payload.get("query")))
                except (ValueError, TypeError) as error:
                    response = _reply(corr, False, code="BAD_REQUEST", message=str(error)[:200])
        elif command in ("artifact.list", "artifact.read"):
            try:
                if command == "artifact.list":
                    response = _reply(corr, True, artifact_view.list_artifacts(self.ctx, payload.get("run_id")))
                else:
                    response = _reply(corr, True, artifact_view.read_chunk(self.ctx, payload.get("run_id"), payload.get("name"), payload.get("offset", 0),
                                                                          payload.get("length", artifact_view.MAX_CHUNK), journal=self.journal))
            except (ValueError, TypeError, OSError) as error:
                response = _reply(corr, False, code="ENGINE_ERROR", message=str(error)[:200])
        elif command == "agents.discover":
            agent = payload.get("agent")
            try:
                if agent is None:
                    response = _reply(corr, True, {"agents": agent_discovery.discover_all()})
                elif isinstance(agent, str):
                    response = _reply(corr, True, {"agents": {agent: agent_discovery.discover(agent)}})
                else:
                    raise ValueError("agent must be a string")
            except ValueError as error:
                response = _reply(corr, False, code="BAD_REQUEST", message=str(error)[:200])
        elif command in ("roles.view", "roles.plan_edit"):
            try:
                settings, tools = roles.read_settings(self.ctx.data_root), list(SUPPORTED_AGENTS)
                found = agent_discovery.discover_all() if payload.get("discover") is True else None
                if command == "roles.view":
                    result = role_editor.view(settings, tools, discovery=found, available=tool_available)
                else:
                    result = role_editor.plan_edit(settings, payload.get("edits"), tools, discovery=found)
                response = _reply(corr, True, result)
            except (ValueError, TypeError) as error:
                response = _reply(corr, False, code="BAD_REQUEST", message=str(error)[:300])
        elif command == "agent.describe":
            try:
                agent = payload.get("agent")
                response = _reply(corr, True, {"agents": agent_describe.describe_all()} if agent is None else agent_describe.describe(agent))
            except ValueError as error:
                response = _reply(corr, False, code="BAD_REQUEST", message=str(error)[:200])
        elif command == "capabilities.scan":
            root = payload.get("project_root")
            if root is not None and not (isinstance(root, str) and os.path.isabs(root) and os.path.isdir(root)):
                response = _reply(corr, False, code="BAD_REQUEST", message="project_root must be an existing absolute directory.")
            else:
                home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
                response = _reply(corr, True, capability_paths.scan(home, root))
        elif command == "capabilities.inventory":
            root = payload.get("project_root")
            if root is not None and not (isinstance(root, str) and os.path.isabs(root) and os.path.isdir(root)):
                response = _reply(corr, False, code="BAD_REQUEST", message="project_root must be an existing absolute directory.")
            else:
                home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
                approvals, error = [], None
                approvals_file = self.ctx.data_root / "capability-approvals.json"
                if approvals_file.is_file():
                    try:
                        approvals = load_signed(self.ctx, approvals_file).get("approvals", [])
                    except (ValueError, OSError, AttributeError):
                        error = "the approvals file failed verification and was ignored; nothing is trusted"
                result = capability_normalize.build(home, root, approvals=approvals if isinstance(approvals, list) else [])
                response = _reply(corr, True, {**result, "approvals_error": error})
        elif command in ("team.view", "analytics.summary", "capabilities.recommend"):
            response = self._beta4_read(corr, command, payload)
        elif command == "review.view":
            run_id = payload.get("run_id")
            if not isinstance(run_id, str) or not re.fullmatch(r"run-\d{14}-[0-9a-f]{12}", run_id):
                response = _reply(corr, False, code="BAD_REQUEST", message="review.view needs a valid run_id.")
            else:
                response = _reply(corr, True, review_model.review_dto(self.ctx, run_id))
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


HUMAN_COMMANDS = frozenset({"hello", "engine.manifest", "review.view", "approval.decide", "approval.apply", "attachment.commit", "attachment.share", "attachment.revoke"})


def serve(ctx, stdin, stdout, environ, human=False):
    """Line-delimited loop over the parent's own pipes: only the process that spawned us can talk to us.

    The token arrives in RESPECTED_IPC_TOKEN (never argv) and is dropped from the environment so children cannot inherit it.
    `human` is the native presence connection: the shell starts a second engine for it and never hands it to the renderer.
    An orchestrated process (RESPECTED_ORCH_CHILD) is never a human, whatever it asks for.
    """
    token = environ.pop("RESPECTED_IPC_TOKEN", "")
    if human:
        api = LocalApi(ctx, token, origin=effective_origin(Origin.HUMAN, environ), only=HUMAN_COMMANDS)
    else:
        api = LocalApi(ctx, token, journal=Journal(ctx.state_dir / "events.log"))
    for line in stdin:
        if line.strip():
            stdout.write(json.dumps(api.handle_raw(line.encode("utf-8")), ensure_ascii=True) + "\n")
            stdout.flush()
    return 0
