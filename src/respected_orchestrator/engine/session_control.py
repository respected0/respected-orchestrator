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
import time

from . import chat_session, winproc
from .session_store import SessionStore, title_of, usage_of
from .authority import Action, authorize

MAX_RETRIES = 2
MAX_INPUT = 8000
MAX_SESSIONS = 20
TURN_TIMEOUT = 180
MODELS_TTL = 300
PAGE_TURNS, MAX_PAGE_TURNS = 50, 200
# What a subscriber is told (ADR-034): one event of the running turn as it arrives; a session's new state (turn started, finished, stopped);
# an agent terminal that was started or ended (ADR-035; its output never travels here).
NOTIFICATIONS = ("session.event", "session.state", "terminal.state")
_UNSAFE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")  # tabs and newlines pass; ESC, CR, NUL and C1 do not
_SESSION = re.compile(r"^(ses|loc)_[A-Za-z0-9]{8,64}$")

# command -> authority class. `approve` is deliberately absent from this table.
CLASSES = {"defaults": Action.READ, "set_defaults": Action.SETTINGS, "transcript": Action.READ, "history": Action.READ, "forget": Action.TASK, "register": Action.TASK, "start": Action.TASK, "send": Action.TASK, "retry": Action.TASK, "interrupt": Action.TASK,
           "cancel": Action.TASK, "resume": Action.TASK, "view": Action.READ, "events": Action.READ, "models": Action.READ,
           "set_mode": Action.TERMINAL}  # a mode that lets the agent write or run commands is the person's choice alone (KALAN_ISLER 4.6)


def kill_tree(proc):
    """End the process and its children (the agent CLI is often a launcher shim that spawns the real process)."""
    if os.name == "nt" and proc.poll() is None:
        winproc.run([winproc.system_tool("taskkill.exe"), "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False)
    if proc.poll() is None:
        proc.terminate()


def run_killable(argv, on_start=None, timeout=TURN_TIMEOUT, cwd=None, env=None, on_line=None, **_ignored):
    """Run one turn so that another thread can end it: the process is handed to `on_start` before we wait for it.
    Each line the process prints goes to `on_line` as it arrives (the live stream, ADR-034); the whole output is still returned at the end."""
    proc = winproc.popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                         encoding="utf-8", errors="replace", shell=False)
    if on_start:
        on_start(proc)
    lines = []

    def read():
        with proc.stdout:
            for line in proc.stdout:
                lines.append(line)
                if on_line:
                    on_line(line)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        proc.wait()
        reader.join(5)
        raise
    reader.join(5)  # a grandchild that kept the pipe open does not hold the finished turn back
    return subprocess.CompletedProcess(argv, proc.returncode, "".join(lines), "")


class SessionApprovalRefused(PermissionError):
    pass


class SessionError(ValueError):
    """`reason` is a stable machine code the screen turns into words; the message stays for logs and operators."""

    def __init__(self, message, reason=None):
        super().__init__(message)
        self.reason = reason


def check_input(text):
    if not isinstance(text, str) or not text.strip():
        raise SessionError("Message is empty", "TEXT_EMPTY")
    if len(text) > MAX_INPUT:
        raise SessionError("Message is too long", "TEXT_TOO_LONG")
    if _UNSAFE.search(text):
        raise SessionError("Message contains control or escape characters", "TEXT_UNSAFE")
    return text


class SessionController:
    def __init__(self, binary=None, runner=None, store=None):
        """`runner=None` means the real agent CLI is spawned, as the engine's own user."""
        self._binary, self._runner = binary, runner or run_killable
        self._real = runner is None
        self._sessions, self._lock = {}, threading.RLock()
        self.store = store or SessionStore()
        self._known = {}  # agent -> (time, model ids): the CLI is asked at most once in MODELS_TTL seconds
        self._listeners = []  # fn(project_id, name, data), called for every notification; must not block

    def listen(self, fn):
        self._listeners.append(fn)

    def unlisten(self, fn):
        self._listeners.remove(fn)

    def notify(self, project_id, name, data):
        for fn in list(self._listeners):
            fn(project_id, name, data)

    def _emit(self, session, name, data):
        self.notify(session["project_id"], name, data)

    def _changed(self, session):
        self._emit(session, "session.state", {"session": self._dto(session)})

    def busy(self):
        """True while any session is working on a turn (the persistent engine does not leave then; idle sessions are saved and can resume)."""
        with self._lock:
            return any(s["state"] == "running" for s in self._sessions.values())

    def _get(self, session_id, project_id):
        found = self._sessions.get(session_id) if isinstance(session_id, str) else None
        if found is None or found["project_id"] != project_id or found["state"] == "ended":
            raise SessionError("Unknown or ended session", "SESSION_UNKNOWN")  # one answer for all three, so nothing can be probed
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
                                          "mode": "default", "cwd": str(cwd), "state": "running" if handle else "idle", "handle": handle, "retries": 0,
                                          "last": None, "last_text": None, "gen": 0, "turn": 0, "result": None, "turns": []}
        return self._dto(self._sessions[session_id])

    def _check_mode(self, origin, mode):
        if mode not in chat_session.MODES:
            raise SessionError("Unknown permission mode", "MODE_INVALID")
        if mode != "default":
            authorize(origin, CLASSES["set_mode"])

    def set_mode(self, origin, session_id, project_id, mode):
        """The session's permission mode from the next turn on. Only between turns."""
        authorize(origin, CLASSES["set_mode"])
        if mode not in chat_session.MODES:
            raise SessionError("Unknown permission mode", "MODE_INVALID")
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] == "running":
                raise SessionError("A turn is running; wait for it or stop it first", "TURN_RUNNING")
            session["mode"] = mode
            if session["turns"] or self.store.get(session["id"]):
                self._persist(session)
            self._changed(session)
            return self._dto(session)

    def start(self, origin, project_id, agent, model, cwd, text, wait=True, resume=None, mode=None):
        """A new session: the first turn runs without --session; the CLI's own session id is learned from its stream. `resume` is such an id from
        an earlier session (the CLI keeps its sessions on disk): the first turn then continues that conversation instead of starting one.
        `mode=None` keeps a saved conversation's own mode; otherwise the caller's explicit mode wins."""
        authorize(origin, CLASSES["start"])
        text = check_input(text)
        if resume is not None and not (isinstance(resume, str) and chat_session._SESSION.match(resume)):
            raise SessionError("Invalid session to continue", "RESUME_INVALID")
        if agent not in chat_session.SUPPORTED:
            raise chat_session.Unsupported(f"{agent}: no verified structured-stream adapter")
        self._check_model(agent, model)
        with self._lock:
            adopted = next((r for r in self.store.all() if resume and r.get("cli") == resume and r["id"] not in self._sessions), None)
            if mode is None:
                mode = adopted.get("mode", "default") if adopted else "default"
            self._check_mode(origin, mode)
            if sum(1 for s in self._sessions.values() if s["state"] != "ended") >= MAX_SESSIONS:
                raise SessionError("Too many open sessions", "TOO_MANY_SESSIONS")
            sid = "loc_" + secrets.token_hex(8)
            self._sessions[sid] = {"id": sid, "cli_id": resume, "project_id": project_id, "agent": agent, "model": model, "cwd": str(cwd), "mode": mode,
                                   "state": "idle", "handle": None, "retries": 0, "last": None, "last_text": None, "gen": 0, "turn": 0, "result": None, "turns": []}
            if adopted:  # the saved conversation continues here: its record moves to the new session
                self._sessions[sid]["turns"] = list(adopted["turns"])
            try:
                result = self._turn(self._sessions[sid], text, wait)
            except Exception:
                del self._sessions[sid]
                raise
            if adopted:
                self.store.delete(adopted["id"])
            return result

    def models(self, origin, agent):
        """The agent CLI's own model list (read only). Spawns the CLI, so it is gated exactly like a turn."""
        authorize(origin, CLASSES["models"])
        if agent not in chat_session.SUPPORTED:
            raise chat_session.Unsupported(f"{agent}: no verified structured-stream adapter")
        binary = self._binary or chat_session.native_binary(agent)
        if not binary:
            raise SessionError("The agent CLI is not installed (a .cmd shim alone is never run)", "AGENT_NOT_INSTALLED")
        return {"agent": agent, "models": self._model_ids(agent, binary), "default": self.store.defaults()["model"]}

    def _model_ids(self, agent, binary):
        with self._lock:
            hit = self._known.get(agent)
            if hit and time.monotonic() - hit[0] < MODELS_TTL:
                return hit[1]
        try:
            ids = chat_session.list_models(binary, None if self._real else self._runner)
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            raise SessionError(str(error)[:200], "MODELS_UNAVAILABLE") from None
        with self._lock:
            self._known[agent] = (time.monotonic(), ids)
        return ids

    def _check_model(self, agent, model):
        """A model that is not on the agent's own list is refused, whatever its shape."""
        binary = self._binary or chat_session.native_binary(agent)
        if not binary:
            raise SessionError("The agent CLI is not installed (a .cmd shim alone is never run)", "AGENT_NOT_INSTALLED")
        if not isinstance(model, str) or model not in self._model_ids(agent, binary):
            raise SessionError("Model is not on the agent's list", "MODEL_INVALID")

    def defaults(self, origin):
        authorize(origin, CLASSES["defaults"])
        return {"agents": list(chat_session.SUPPORTED), "modes": list(chat_session.MODES), **self.store.defaults()}

    def set_defaults(self, origin, agent, model):
        authorize(origin, CLASSES["set_defaults"])
        if agent not in chat_session.SUPPORTED:
            raise chat_session.Unsupported(f"{agent}: no verified structured-stream adapter")
        self._check_model(agent, model)
        self.store.set_defaults(agent, model)
        return self.defaults(origin)

    def _persist(self, session):
        turns = session["turns"]
        self.store.put({"id": session["id"], "project_root": session["cwd"], "agent": session["agent"], "model": session["model"],
                        "cli": session["cli_id"], "mode": session.get("mode", "default"), "turns": turns,
                        "title": title_of(turns, f"{session['agent']} · {session['model'].split('/')[-1]}")})

    def transcript(self, origin, session_id, before=None, limit=PAGE_TURNS):
        """One page of a conversation, newest by default: the `limit` turns that end just before turn index `before`. `first` is the index of
        the first turn returned (0: nothing older); send it back as `before` for the page above. `live`: the running turn's events so far."""
        authorize(origin, CLASSES["transcript"])
        with self._lock:
            record = self.store.get(session_id) if isinstance(session_id, str) else None
            if record is None:
                raise SessionError("Unknown conversation", "SESSION_UNKNOWN")
            turns = record["turns"]
            end = len(turns) if before is None else before
            if type(end) is not int or not 0 <= end <= len(turns) or type(limit) is not int or not 1 <= limit <= MAX_PAGE_TURNS:
                raise SessionError("before and limit must be whole numbers in range", "PAGE_INVALID")
            # shortcut: the cursor is a position in the saved list, which drops its oldest turn past MAX_TURNS; use a stable turn id if pages must survive that
            first = max(0, end - limit)
            session = self._sessions.get(session_id)
            live = {"turn": session["turn"], "events": list(session.get("live", ()))} if session and session["state"] == "running" else None
            return {"id": record["id"], "title": record["title"], "project_root": record["project_root"], "agent": record["agent"],
                    "model": record["model"], "resumable": bool(record.get("cli")), "turns": turns[first:end], "first": first, "total": len(turns),
                    "usage": usage_of(turns), "live": live}

    def history(self, origin):
        """Saved conversations that no session of this run owns (after a restart: all of them), newest first."""
        authorize(origin, CLASSES["history"])
        with self._lock:
            return [{"id": r["id"], "title": r["title"], "project_root": r["project_root"], "agent": r["agent"], "model": r["model"],
                     "updated": r["updated"], "resumable": bool(r.get("cli"))} for r in self.store.all() if r["id"] not in self._sessions]

    def conversations(self, origin, project_id):
        """Everything the sidebar lists, newest first: this run's sessions and the saved conversations nobody owns now."""
        authorize(origin, CLASSES["history"])
        with self._lock:
            live = []
            for s in self._sessions.values():
                if s["project_id"] != project_id:
                    continue
                record = self.store.get(s["id"])
                live.append({"id": s["id"], "title": title_of(s["turns"], f"{s['agent']} \u00b7 {s['model'].split('/')[-1]}"), "state": s["state"],
                             "project_root": s["cwd"], "updated": record["updated"] if record else time.time(), "saved": False})
            old = [{"id": h["id"], "title": h["title"], "state": "ended", "project_root": h["project_root"], "updated": h["updated"], "saved": True}
                   for h in self.history(origin)]
        return sorted(live + old, key=lambda c: c["updated"], reverse=True)

    def forget(self, origin, session_id):
        authorize(origin, CLASSES["forget"])
        with self._lock:
            if session_id in self._sessions and self._sessions[session_id]["state"] != "ended":
                raise SessionError("End the session before deleting its record", "SESSION_LIVE")
            self._sessions.pop(session_id, None)
        self.store.delete(session_id)
        return {"deleted": session_id}

    def _turn(self, session, text, wait=True, new_message=True):
        """Start one turn. wait=True blocks and returns the parsed result; wait=False returns the session view at once and the turn
        finishes on its own thread. Either way the lock is NOT needed to end it: interrupt/cancel bump `gen`, so a late result is dropped."""
        binary = self._binary or chat_session.native_binary(session["agent"])
        if not binary:
            raise SessionError("The agent CLI is not installed (a .cmd shim alone is never run)", "AGENT_NOT_INSTALLED")
        argv = chat_session.command(session["agent"], model=session["model"], prompt=text, binary=binary, session_id=session["cli_id"])
        session["state"], session["last_text"], session["result"] = "running", text, None
        if new_message:
            session["turns"].append({"n": None, "user": text, "result": None})
        self._persist(session)
        session["gen"] += 1
        session["turn"] += 1  # a client tells two equally-shaped results apart by this, never by their content
        gen, turn = session["gen"], session["turn"]
        live = session["live"] = []  # this turn's events so far; a stopped turn's late lines land in its own list, never in the next turn's
        self._changed(session)

        def line(text):  # no lock: with wait=True the caller holds it for the whole turn
            for event in chat_session.normalize(text):
                event["seq"] = len(live)  # the same numbering parse_stream gives the finished turn
                live.append(event)
                if session["gen"] == gen:
                    self._emit(session, "session.event", {"session_id": session["id"], "turn": turn, "event": event})

        def adopt(proc):
            session["handle"] = proc
            if session["gen"] != gen:  # interrupted before the process existed
                kill_tree(proc)

        def work():
            try:
                done = self._runner(argv, cwd=session["cwd"], timeout=TURN_TIMEOUT, on_start=adopt, on_line=line,
                                    env=chat_session.turn_environment(session["cwd"], mode=session.get("mode", "default")))
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
                turns = session["turns"]
                if turns and turns[-1]["result"] is None:
                    turns[-1]["n"], turns[-1]["result"] = session["turn"], result
                else:
                    turns.append({"n": session["turn"], "user": None, "result": result})
                self._persist(session)
                self._changed(session)
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
            return self._turn(session, session["last_text"], wait, new_message=False)

    def events(self, origin, session_id, project_id):
        """The last finished turn of a session (untrusted stream events, already normalised), or None while one runs; then `live` holds
        the running turn's events so far."""
        authorize(origin, CLASSES["events"])
        with self._lock:
            session = self._get(session_id, project_id)
            return {"state": session["state"], "turn": session["turn"], "result": session["result"], "usage": usage_of(session["turns"]),
                    "live": list(session.get("live", ())) if session["state"] == "running" else None}

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
            self._changed(session)
            return self._dto(session)

    def cancel(self, origin, session_id, project_id):
        authorize(origin, CLASSES["cancel"])
        with self._lock:
            session = self._get(session_id, project_id)
            self._stop(session)
            session["state"] = "ended"
            self._changed(session)
            return self._dto(session)

    def resume(self, origin, session_id, project_id):
        """Re-attach to a known session of this project that is not running. An ended session is final."""
        authorize(origin, CLASSES["resume"])
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] == "running":
                raise SessionError("Session is already running")
            session["state"] = "idle"
            self._changed(session)
            return self._dto(session)

    def handoff(self, origin, session_id, project_id):
        """What another interface needs to continue this session (ADR-035): its folder, agent and the agent's own session id. Only a session
        that is not working and that the agent has given an id can be handed over."""
        authorize(origin, CLASSES["cancel"])
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] == "running":
                raise SessionError("A turn is running; wait for it or stop it first", "TURN_RUNNING")
            if not session["cli_id"]:
                raise SessionError("The agent has not given this session an id yet", "RESUME_INVALID")
            return {"conversation": session["id"], "agent": session["agent"], "project_root": session["cwd"], "resume": session["cli_id"],
                    "mode": session.get("mode", "default")}

    def release(self, origin, session_id, project_id):
        """The session leaves this engine's live set and stays as a saved conversation (it can be continued later). Used after a handoff."""
        authorize(origin, CLASSES["cancel"])
        with self._lock:
            session = self._get(session_id, project_id)
            if session["state"] == "running":
                raise SessionError("A turn is running; wait for it or stop it first", "TURN_RUNNING")
            session["state"] = "ended"
            del self._sessions[session_id]
            self._changed(session)
            return self._dto(session)

    def approve(self, *_args, **_kwargs):
        raise SessionApprovalRefused("A session cannot be approved here; permission decisions belong to the approval center")

    def view(self, origin, project_id):
        authorize(origin, CLASSES["view"])
        return [self._dto(s) for s in self._sessions.values() if s["project_id"] == project_id]

    @staticmethod
    def _dto(s):
        state = s["state"]
        why = {"running": "TURN_RUNNING", "failed": "LAST_TURN_FAILED", "ended": "SESSION_ENDED"}
        enabled = {
            "send": state == "idle", "retry": state == "failed" and s["retries"] < MAX_RETRIES and s.get("last_state") != "rate_limited",
            "interrupt": state == "running", "cancel": state != "ended", "resume": state in ("idle", "failed"),
        }
        return {"id": s["id"], "project_id": s["project_id"], "agent": s["agent"], "model": s["model"], "mode": s.get("mode", "default"), "state": state,
                "retries": s["retries"], "last_state": s.get("last_state"),
                "turn": s["turn"], "project_root": s["cwd"], "title": title_of(s["turns"], f"{s['agent']} · {s['model'].split('/')[-1]}"),
                "commands": {k: {"enabled": v, "reason": None if v else why.get(state, "NOT_AVAILABLE")} for k, v in enabled.items()}}
