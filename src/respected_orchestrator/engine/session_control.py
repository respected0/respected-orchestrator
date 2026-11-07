"""Session intervention commands (B3-03.04): send input, interrupt, cancel, retry, resume - and the one that does not exist, approve.

Each command has its own authority class (authority.py) and is checked before anything else. A session is addressed by
(session id, project id): an unknown, ended or other-project session is refused the same way, so ids cannot be probed or
reused. Text for a session comes only from the caller of `send`, never from a stream: stream events are untrusted data
(chat_session) and there is no code path that turns one into input, a decision or a grant. A session's own permission
prompts are not answerable here; `approve` refuses for every origin including HUMAN - approvals live in approval.py.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import threading

from . import chat_session, winproc
from .authority import Action, authorize

MAX_RETRIES = 2
MAX_INPUT = 8000
_UNSAFE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # tabs and newlines pass; ESC, CR, NUL and C1 do not
_SESSION = re.compile(r"^ses_[A-Za-z0-9]{8,64}$")

# command -> authority class. `approve` is deliberately absent from this table.
CLASSES = {"register": Action.TASK, "send": Action.TASK, "retry": Action.TASK, "interrupt": Action.TASK,
           "cancel": Action.TASK, "resume": Action.TASK, "view": Action.READ}


class SessionApprovalRefused(PermissionError):
    pass


class SessionError(ValueError):
    pass


def check_input(text):
    if not isinstance(text, str) or not text.strip():
        raise SessionError("Message is empty")
    if len(text) > MAX_INPUT:
        raise SessionError("Message is too long")
    if _UNSAFE.search(text):
        raise SessionError("Message contains control or escape characters")
    return text


class SessionController:
    def __init__(self, binary=None, runner=None):
        self._binary, self._runner = binary, runner or winproc.run
        self._sessions, self._lock = {}, threading.Lock()

    def _get(self, session_id, project_id):
        found = self._sessions.get(session_id) if isinstance(session_id, str) else None
        if found is None or found["project_id"] != project_id or found["state"] == "ended":
            raise SessionError("Unknown or ended session")  # one answer for all three, so nothing can be probed
        return found

    def register(self, origin, session_id, project_id, agent, model, cwd, handle=None):
        authorize(origin, CLASSES["register"])
        if not _SESSION.match(session_id or ""):
            raise SessionError("Invalid session id")
        if agent not in chat_session.SUPPORTED:
            raise chat_session.Unsupported(f"{agent}: no verified structured-stream adapter")
        with self._lock:
            if session_id in self._sessions:
                raise SessionError("Session already registered")
            self._sessions[session_id] = {"id": session_id, "project_id": project_id, "agent": agent, "model": model, "cwd": str(cwd),
                                          "state": "running" if handle else "idle", "handle": handle, "retries": 0, "last": None,
                                          "last_text": None}
        return self._dto(self._sessions[session_id])

    def _turn(self, session, text):
        binary = self._binary or shutil.which("opencode")
        if not binary:
            raise SessionError("The agent CLI is not installed")
        argv = chat_session.command(session["agent"], model=session["model"], prompt=text, binary=binary, session_id=session["id"])
        session["state"], session["last_text"] = "running", text
        try:
            done = self._runner(argv, cwd=session["cwd"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=180, stdin=subprocess.DEVNULL, shell=False)
            result = chat_session.parse_stream(done.stdout.splitlines())
            if done.returncode != 0 and result["complete"]:
                result["state"], result["complete"] = "error", False
        except (OSError, subprocess.TimeoutExpired) as exc:
            result = {"state": "error", "complete": False, "events": [], "error": str(exc)[:200]}
        session["state"] = "idle" if result["complete"] else "failed"
        session["last_state"] = result["state"]
        return result

    def send(self, origin, session_id, project_id, text):
        authorize(origin, CLASSES["send"])
        text = check_input(text)
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] != "idle":
                raise SessionError(f"Session is {session['state']}; wait or use retry/cancel")
            session["retries"] = 0
            return self._turn(session, text)

    def retry(self, origin, session_id, project_id):
        authorize(origin, CLASSES["retry"])
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] != "failed":
                raise SessionError("Only a failed turn can be retried")
            if session.get("last_state") == "rate_limited":
                raise SessionError("Rate limited: not retried automatically")
            if session["retries"] >= MAX_RETRIES:
                raise SessionError("Retry limit reached")
            session["retries"] += 1
            return self._turn(session, session["last_text"])

    def _stop(self, session):
        handle, session["handle"] = session["handle"], None
        if handle is not None:
            handle.terminate()

    def interrupt(self, origin, session_id, project_id):
        """Stop the running turn; the session stays and can take another message. (The CLI has no softer interrupt: process end.)"""
        authorize(origin, CLASSES["interrupt"])
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] != "running":
                raise SessionError("Nothing is running")
            self._stop(session)
            session["state"] = "failed" if session["last_text"] else "idle"
            session["last_state"] = "interrupted"
            return self._dto(session)

    def cancel(self, origin, session_id, project_id):
        authorize(origin, CLASSES["cancel"])
        with self._lock:
            session = self._get(session_id, project_id)
            self._stop(session)
            session["state"] = "ended"
            return self._dto(session)

    def resume(self, origin, session_id, project_id):
        """Re-attach to a known session of this project that is not running. An ended session is final."""
        authorize(origin, CLASSES["resume"])
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] == "running":
                raise SessionError("Session is already running")
            session["state"] = "idle"
            return self._dto(session)

    def approve(self, *_args, **_kwargs):
        raise SessionApprovalRefused("A session cannot be approved here; permission decisions belong to the approval center")

    def view(self, origin, project_id):
        authorize(origin, CLASSES["view"])
        return [self._dto(s) for s in self._sessions.values() if s["project_id"] == project_id]

    @staticmethod
    def _dto(s):
        state = s["state"]
        why = {"running": "a turn is running", "failed": "last turn failed", "ended": "session ended"}
        enabled = {
            "send": state == "idle", "retry": state == "failed" and s["retries"] < MAX_RETRIES and s.get("last_state") != "rate_limited",
            "interrupt": state == "running", "cancel": state != "ended", "resume": state in ("idle", "failed"),
        }
        return {"id": s["id"], "project_id": s["project_id"], "agent": s["agent"], "model": s["model"], "state": state,
                "retries": s["retries"], "last_state": s.get("last_state"),
                "commands": {k: {"enabled": v, "reason": None if v else why.get(state, "not available in this state")} for k, v in enabled.items()}}
