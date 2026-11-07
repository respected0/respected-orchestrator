"""Session intervention commands (B3-03.04): send input, interrupt, cancel, retry, resume - and the one that does not exist, approve.

Each command has its own authority class (authority.py) and is checked before anything else. A session is addressed by
(session id, project id): an unknown, ended or other-project session is refused the same way, so ids cannot be probed or
reused. Text for a session comes only from the caller of `send`, never from a stream: stream events are untrusted data
(chat_session) and there is no code path that turns one into input, a decision or a grant. A session's own permission
prompts are not answerable here; `approve` refuses for every origin including HUMAN - approvals live in approval.py.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import threading

from . import chat_session, winproc
from .authority import Action, authorize

MAX_RETRIES = 2
MAX_INPUT = 8000
MAX_SESSIONS = 20
TURN_TIMEOUT = 180
DISABLED = ("Chat sessions are disabled: the agent CLI cannot run inside the sandbox yet, so the engine starts it only when the "
            "operator sets RESPECTED_CHAT_UNSANDBOXED=allow (tools that change files or run commands stay denied)")
_UNSAFE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # tabs and newlines pass; ESC, CR, NUL and C1 do not
_SESSION = re.compile(r"^(ses|loc)_[A-Za-z0-9]{8,64}$")

# command -> authority class. `approve` is deliberately absent from this table.
CLASSES = {"register": Action.TASK, "start": Action.TASK, "send": Action.TASK, "retry": Action.TASK, "interrupt": Action.TASK,
           "cancel": Action.TASK, "resume": Action.TASK, "view": Action.READ, "events": Action.READ}


def kill_tree(proc):
    """End the process and its children (the agent CLI is often a launcher shim that spawns the real process)."""
    if os.name == "nt" and proc.poll() is None:
        winproc.run([winproc.system_tool("taskkill.exe"), "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
    if proc.poll() is None:
        proc.terminate()


def run_killable(argv, on_start=None, timeout=TURN_TIMEOUT, cwd=None, env=None, **_ignored):
    """Run one turn so that another thread can end it: the process is handed to `on_start` before we wait for it."""
    proc = winproc.popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", errors="replace", shell=False)
    if on_start:
        on_start(proc)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        proc.communicate()
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


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
    def __init__(self, binary=None, runner=None, unsandboxed=False):
        """`runner=None` means the real agent CLI is spawned, as the engine's own user and outside the AppContainer: that only
        happens with `unsandboxed=True` (the operator's explicit switch, see DISABLED). Injected runners (tests) are not gated."""
        self._binary, self._runner = binary, runner or run_killable
        self._real, self._unsandboxed = runner is None, unsandboxed
        self._sessions, self._lock = {}, threading.RLock()

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
            self._sessions[session_id] = {"id": session_id, "cli_id": session_id, "project_id": project_id, "agent": agent, "model": model,
                                          "cwd": str(cwd), "state": "running" if handle else "idle", "handle": handle, "retries": 0,
                                          "last": None, "last_text": None, "gen": 0, "turn": 0, "result": None}
        return self._dto(self._sessions[session_id])

    def start(self, origin, project_id, agent, model, cwd, text, wait=True):
        """A new session: the first turn runs without --session; the CLI's own session id is learned from its stream."""
        authorize(origin, CLASSES["start"])
        text = check_input(text)
        if agent not in chat_session.SUPPORTED:
            raise chat_session.Unsupported(f"{agent}: no verified structured-stream adapter")
        with self._lock:
            if sum(1 for s in self._sessions.values() if s["state"] != "ended") >= MAX_SESSIONS:
                raise SessionError("Too many open sessions")
            sid = "loc_" + secrets.token_hex(8)
            self._sessions[sid] = {"id": sid, "cli_id": None, "project_id": project_id, "agent": agent, "model": model, "cwd": str(cwd),
                                   "state": "idle", "handle": None, "retries": 0, "last": None, "last_text": None, "gen": 0, "turn": 0, "result": None}
            try:
                return self._turn(self._sessions[sid], text, wait)
            except Exception:
                del self._sessions[sid]
                raise

    def _turn(self, session, text, wait=True):
        """Start one turn. wait=True blocks and returns the parsed result; wait=False returns the session view at once and the turn
        finishes on its own thread. Either way the lock is NOT needed to end it: interrupt/cancel bump `gen`, so a late result is dropped."""
        if self._real and not self._unsandboxed:
            raise SessionError(DISABLED)
        binary = self._binary or chat_session.native_binary(session["agent"])
        if not binary:
            raise SessionError("The agent CLI is not installed (a .cmd shim alone is never run)")
        argv = chat_session.command(session["agent"], model=session["model"], prompt=text, binary=binary, session_id=session["cli_id"])
        session["state"], session["last_text"], session["result"] = "running", text, None
        session["gen"] += 1
        session["turn"] += 1  # a client tells two equally-shaped results apart by this, never by their content
        gen = session["gen"]

        def adopt(proc):
            session["handle"] = proc
            if session["gen"] != gen:  # interrupted before the process existed
                kill_tree(proc)

        def work():
            try:
                done = self._runner(argv, cwd=session["cwd"], timeout=TURN_TIMEOUT, on_start=adopt, env=chat_session.turn_environment(session["cwd"]))
                result = chat_session.parse_stream(done.stdout.splitlines())
                if done.returncode != 0 and result["complete"]:
                    result["state"], result["complete"] = "error", False
            except (OSError, subprocess.TimeoutExpired) as exc:
                result = {"state": "error", "complete": False, "events": [], "error": str(exc)[:200]}
            with self._lock:
                if session["gen"] != gen:
                    return result
                session["handle"] = None
                session["state"] = "idle" if result["complete"] else "failed"
                session["last_state"], session["result"] = result["state"], result
                if session["cli_id"] is None and result.get("session_id"):
                    session["cli_id"] = result["session_id"]
            return result

        if wait:
            return work()
        threading.Thread(target=work, daemon=True, name=f"session-{session['id']}").start()
        return self._dto(session)

    def send(self, origin, session_id, project_id, text, wait=True):
        authorize(origin, CLASSES["send"])
        text = check_input(text)
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] != "idle":
                raise SessionError(f"Session is {session['state']}; wait or use retry/cancel")
            session["retries"] = 0
            return self._turn(session, text, wait)

    def retry(self, origin, session_id, project_id, wait=True):
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
            return self._turn(session, session["last_text"], wait)

    def events(self, origin, session_id, project_id):
        """The last finished turn of a session (untrusted stream events, already normalised), or None while one runs."""
        authorize(origin, CLASSES["events"])
        with self._lock:
            session = self._get(session_id, project_id)
            return {"state": session["state"], "turn": session["turn"], "result": session["result"]}

    def _stop(self, session):
        session["gen"] += 1  # whatever the turn's thread reports from now on is discarded
        handle, session["handle"] = session["handle"], None
        if handle is not None:
            kill_tree(handle)

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
