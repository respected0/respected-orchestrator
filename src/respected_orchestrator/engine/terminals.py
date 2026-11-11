"""Agent terminals as the engine sees them (ADR-035): it starts a terminal host per terminal, remembers the live ones in
`state/terminals.json` (so a restarted engine finds them again) and passes input, size changes and the output stream between a client
and the host. A terminal is addressed by (terminal id, project id), like a session.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

from ..context import atomic_write_json, engine_command
from . import agent_adapters, chat_session, pty_host

MAX_TERMINALS = 8
MAX_INPUT_BYTES = 64 * 1024
START_TIMEOUT = 15
_ID = re.compile(r"term_[0-9a-f]{16}\Z")
# agent -> the arguments that make its terminal interface continue a session it already has. Only what the CLI's own help shows
# (opencode: `--session, -s  Session ID to continue`, read 2026-11-10); an agent that is not here cannot be switched from chat to terminal.
RESUME_ARGS = {"opencode": lambda session: ["--session", session]}


class TerminalError(ValueError):
    """`reason` is a stable machine code the screen turns into words."""

    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


def agent_command(agent):
    """The agent's own program, started with no arguments: its interactive terminal interface. Never a `.cmd` shim."""
    if agent not in agent_adapters.ADAPTERS:
        raise TerminalError("Unknown agent", "AGENT_UNKNOWN")
    binary = chat_session.native_binary(agent)
    if not binary:
        raise TerminalError("The agent CLI is not installed (a .cmd shim alone is never run)", "AGENT_NOT_INSTALLED")
    return [binary]


def mode_flag(agent, mode):
    """The flag `agent.describe` published for a CLI mode; `default` is the CLI's own baseline and passes nothing."""
    if mode in (None, "default"):
        return []
    spec = agent_adapters.ADAPTERS.get(agent, {}).get("modes")
    for item in (spec[1] if spec else ()):
        if isinstance(mode, str) and item[0] == mode:
            return [item[1]]
    raise TerminalError("This agent's terminal has no such mode", "MODE_UNSUPPORTED")


def mode_supported(agent, mode):
    try:
        mode_flag(agent, mode)
        return True
    except TerminalError:
        return False


def _size(cols, rows):
    if type(cols) is not int or type(rows) is not int or not 20 <= cols <= 500 or not 5 <= rows <= 200:
        raise TerminalError("cols must be 20-500 and rows 5-200", "SIZE_INVALID")
    return cols, rows


class Terminals:
    def __init__(self, ctx, notify=None, command=agent_command):
        self.ctx, self._notify, self._command = ctx, notify or (lambda *_: None), command
        self._path, self._lock = Path(ctx.state_dir) / "terminals.json", threading.RLock()

    def _records(self):
        """The recorded terminals whose host process still runs; the others are dropped from the file."""
        from .lanes import _pid_is_alive
        try:
            saved = json.loads(self._path.read_text(encoding="utf-8"))
            saved = saved if isinstance(saved, dict) else {}
        except (OSError, ValueError):
            saved = {}
        live = {k: v for k, v in saved.items() if isinstance(v, dict) and _ID.match(k) and _pid_is_alive(v.get("host_pid") or 0)}
        if live != saved and self._path.exists():
            atomic_write_json(self._path, live)
        return live

    def _get(self, terminal_id, project_id):
        record = self._records().get(terminal_id) if isinstance(terminal_id, str) else None
        if record is None or record["project_id"] != project_id:
            raise TerminalError("Unknown or ended terminal", "TERMINAL_UNKNOWN")  # one answer for both, so ids cannot be probed
        return record

    def _ask(self, terminal_id, message):
        """One request to the terminal host, its one-line answer. OSError when the host is not there."""
        from . import daemon_client
        try:
            handle = daemon_client._open(pty_host.pipe_path(terminal_id))
        except daemon_client.DaemonUnavailable as error:
            raise OSError(str(error)) from None
        with handle:
            handle.write(json.dumps(message).encode("ascii") + b"\n")
            data = b""
            while not data.endswith(b"\n"):
                chunk = handle.read(1 << 16)
                if not chunk:
                    raise OSError("The terminal host closed the connection.")
                data += chunk
        reply = json.loads(data)
        if not reply.get("ok"):
            raise OSError(reply.get("message") or "The terminal host refused.")
        return reply

    def _dto(self, record, status=None):
        return {"id": record["id"], "project_id": record["project_id"], "project_root": record["project_root"], "agent": record["agent"],
                "conversation": record.get("conversation"),  # the chat conversation this terminal continues, when it was switched over from one
                "mode": record.get("mode", "default"),
                "started": record["started"], "alive": status["alive"] if status else None, "exit": status["exit"] if status else None,
                "cols": status["cols"] if status else None, "rows": status["rows"] if status else None}

    def start(self, project_id, project_root, agent, cols=120, rows=30, resume=None, conversation=None, mode=None):
        """`resume`: the agent's own session id to continue in the terminal (a switch from chat); `conversation`: the chat record it came from."""
        from .lanes import _spawn_detached
        if not isinstance(project_id, str) or not project_id:
            raise TerminalError("project_id is required", "PROJECT_INVALID")
        if not (isinstance(project_root, str) and os.path.isabs(project_root) and os.path.isdir(project_root)):
            raise TerminalError("project_root must be an existing absolute directory", "ROOT_INVALID")
        cols, rows = _size(cols, rows)
        argv = self._command(agent) + mode_flag(agent, mode)
        if resume is not None:
            if agent not in RESUME_ARGS or not isinstance(resume, str) or not chat_session._SESSION.match(resume):
                raise TerminalError("This agent's session cannot be continued in a terminal", "HANDOFF_UNSUPPORTED")
            argv = argv + RESUME_ARGS[agent](resume)
        with self._lock:
            records = self._records()
            if len(records) >= MAX_TERMINALS:
                raise TerminalError("Too many open terminals", "TOO_MANY_TERMINALS")
            terminal_id = "term_" + secrets.token_hex(8)
            spec = {"id": terminal_id, "argv": argv, "cwd": project_root, "cols": cols, "rows": rows}
            self.ctx.state_dir.mkdir(parents=True, exist_ok=True)
            env = {k: v for k, v in os.environ.items() if k not in ("RESPECTED_ORCH_CHILD", "RESPECTED_ORCH_DELEGATED")}
            host_pid = _spawn_detached(engine_command("--data-root", str(self.ctx.data_root), "_pty-host", json.dumps(spec)),
                                       self.ctx.data_root, self.ctx.state_dir / "pty-host.log", env=env)
            deadline, status = time.monotonic() + START_TIMEOUT, None
            while status is None:
                try:
                    status = self._ask(terminal_id, {"op": "status"})
                except OSError:
                    if time.monotonic() > deadline:
                        raise TerminalError(f"The terminal did not start; see {self.ctx.state_dir / 'pty-host.log'}", "TERMINAL_START_FAILED") from None
                    time.sleep(0.1)
            record = {"id": terminal_id, "project_id": project_id, "project_root": project_root, "agent": agent, "host_pid": host_pid, "started": time.time(),
                      "conversation": conversation, "mode": mode or "default"}
            atomic_write_json(self._path, {**records, terminal_id: record})
        view = self._dto(record, status)
        self._notify(project_id, "terminal.state", {"terminal": view})
        return view

    def list(self, project_id):
        out = []
        for record in self._records().values():
            if record["project_id"] != project_id:
                continue
            try:
                out.append(self._dto(record, self._ask(record["id"], {"op": "status"})))
            except OSError:
                out.append(self._dto(record))  # recorded and its process runs, but it does not answer: shown as unknown, not as alive
        return sorted(out, key=lambda t: t["started"])

    def input(self, terminal_id, project_id, data):
        """`data`: base64 of the bytes a terminal would send for what was typed or pasted."""
        self._get(terminal_id, project_id)
        try:
            if not isinstance(data, str) or len(base64.b64decode(data, validate=True)) > MAX_INPUT_BYTES:
                raise ValueError
        except (ValueError, binascii.Error):
            raise TerminalError("data must be base64 of at most 64 KiB", "INPUT_INVALID") from None
        self._ask(terminal_id, {"op": "input", "data": data})
        return {"sent": True}

    def resize(self, terminal_id, project_id, cols, rows):
        self._get(terminal_id, project_id)
        cols, rows = _size(cols, rows)
        status = self._ask(terminal_id, {"op": "resize", "cols": cols, "rows": rows})
        return {"cols": status["cols"], "rows": status["rows"]}

    def kill(self, terminal_id, project_id):
        """Ends the terminal and the program in it; its record goes with it."""
        with self._lock:
            record = self._get(terminal_id, project_id)
            try:
                self._ask(terminal_id, {"op": "kill"})
            except OSError:
                pass  # already on its way out; the record is dropped either way
            records = self._records()
            records.pop(terminal_id, None)
            atomic_write_json(self._path, records)
        self._notify(project_id, "terminal.state", {"terminal": {**self._dto(record), "alive": False}})
        return {"killed": terminal_id}

    def attach(self, terminal_id, project_id):
        """The terminal's output from now on, as the host's own lines ({"data"} / {"exit"} / {"ping"}), kept output first. Close it to leave."""
        from . import daemon_client
        self._get(terminal_id, project_id)
        try:
            handle = daemon_client._open(pty_host.pipe_path(terminal_id))
        except daemon_client.DaemonUnavailable as error:
            raise OSError(str(error)) from None
        handle.write(b'{"op": "attach"}\n')
        return daemon_client._lines(handle)
