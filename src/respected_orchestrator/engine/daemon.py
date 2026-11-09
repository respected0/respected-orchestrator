"""The persistent engine (ADR-030, slice 1): one process per data root that other front ends connect to.

Ownership is the OS file lock `daemon.lock` (a crash releases it). The only way in is a per-user named pipe whose access list
names the current user alone; there is no port. The wire protocol is local_api's line-delimited JSON, unchanged.

Who is calling is decided here, never by the client: a connection whose process descends from one of the engine's own
running workers is CHILD (no rights); every other connection is MCP-level (read and task commands). Approve, apply and
settings commands are not in the catalog this process serves, whatever the origin: they stay on the native shell's private
channel and on the terminal (ADR-030 section 3).
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import secrets
import threading
import time

from .. import __version__
from . import winproc
from .authority import Action, Origin
from .journal import Journal
from .local_api import COMMANDS, IPC, MAX_REQUEST_BYTES, LocalApi, _ID, _reply
from .supervisor import Supervisor, SupervisorBusy

IDLE_SECONDS = 30 * 60  # nothing connected, no run working: the daemon leaves (ADR-030 D2)
CONTROL = ("daemon.status", "daemon.stop")
SERVED = frozenset(name for name, (_op, action) in COMMANDS.items() if action in (Action.READ, Action.TASK))


class DaemonLock(Supervisor):
    LOCK_NAME = "daemon.lock"


def pipe_name(ctx) -> str:
    """One pipe per user and data root, so two data roots (tests, side-by-side installs) never meet."""
    digest = hashlib.sha256(str(ctx.data_root).lower().encode("utf-8")).hexdigest()[:12]
    return f"rorch-{''.join(c for c in getpass.getuser() if c.isalnum()) or 'user'}-{digest}"


def pipe_path(ctx) -> str:
    return "\\\\.\\pipe\\" + pipe_name(ctx)


def classify(ctx, pid: int) -> Origin:
    """CHILD when `pid` is, or descends from, a process that is working on a run right now; otherwise MCP-level."""
    from . import maintenance
    working = {int(p) for p in maintenance.run_pids(ctx).values()}
    return Origin.CHILD if working & {pid, *winproc.ancestors(pid)} else Origin.MCP


class Daemon:
    def __init__(self, ctx, idle_seconds: float = IDLE_SECONDS):
        self.ctx, self.idle_seconds = ctx, idle_seconds
        self.stop_event = threading.Event()
        self.started_at = time.time()
        self._connections, self._last_activity = 0, time.monotonic()
        self._guard = threading.Lock()

    def busy(self) -> bool:
        from . import maintenance
        with self._guard:
            if self._connections:
                return True
        return bool(maintenance.run_pids(self.ctx))

    def status(self) -> dict:
        return {"pid": os.getpid(), "version": __version__, "data_root": str(self.ctx.data_root), "started_at": self.started_at,
                "pipe": pipe_name(self.ctx), "idle_seconds": self.idle_seconds, "connections": self._connections}

    def run(self) -> int:
        if os.name != "nt":
            raise RuntimeError("The persistent engine is Windows-only for now (ADR-030: Unix socket comes later).")
        try:
            lock = DaemonLock(self.ctx).acquire()
        except SupervisorBusy:
            print(json.dumps({"daemon": "busy", "pid": os.getpid()}), flush=True)
            return 1
        try:
            threading.Thread(target=self._watch_idle, daemon=True).start()
            print(json.dumps({"daemon": "started", **self.status()}), flush=True)
            self._serve_pipe()
        finally:
            lock.release()
        print(json.dumps({"daemon": "stopped", "pid": os.getpid()}), flush=True)
        return 0

    def stop(self):
        self.stop_event.set()
        try:  # wake the blocked accept
            open(pipe_path(self.ctx), "r+b", buffering=0).close()
        except OSError:
            pass

    def _watch_idle(self):
        while not self.stop_event.wait(5):
            if self.busy():
                self._last_activity = time.monotonic()
            elif time.monotonic() - self._last_activity >= self.idle_seconds:
                self.stop()

    def _serve_pipe(self):
        import pywintypes
        import win32file
        import win32pipe
        security = _own_user_only()
        flags = win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT | win32pipe.PIPE_REJECT_REMOTE_CLIENTS
        first = 0x00080000  # FILE_FLAG_FIRST_PIPE_INSTANCE (not exported by pywin32): nobody else may have created this name before us
        while not self.stop_event.is_set():
            handle = win32pipe.CreateNamedPipe(pipe_path(self.ctx), win32pipe.PIPE_ACCESS_DUPLEX | first, flags,
                                               win32pipe.PIPE_UNLIMITED_INSTANCES, 1 << 16, 1 << 16, 0, security)
            first = 0
            try:
                win32pipe.ConnectNamedPipe(handle, None)
            except pywintypes.error as error:
                if error.winerror != 535:  # ERROR_PIPE_CONNECTED: the client was faster than us
                    win32file.CloseHandle(handle)
                    continue
            if self.stop_event.is_set():
                win32file.CloseHandle(handle)
                break
            threading.Thread(target=self._connection, args=(handle,), daemon=True).start()

    def _connection(self, handle):
        import pywintypes
        import win32file
        import win32pipe
        with self._guard:
            self._connections += 1
        try:
            origin = classify(self.ctx, win32pipe.GetNamedPipeClientProcessId(handle))
            token = secrets.token_hex(16)  # local_api insists on one; the pipe's access list is the real gate
            api = LocalApi(self.ctx, token, origin=origin, journal=Journal(self.ctx.state_dir / "events.log"), only=SERVED)
            buffer = b""
            while not self.stop_event.is_set():
                try:
                    _code, data = win32file.ReadFile(handle, 1 << 16)
                except pywintypes.error:
                    return
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    reply = self._answer(api, origin, token, line)
                    win32file.WriteFile(handle, json.dumps(reply, ensure_ascii=True).encode("ascii") + b"\n")
                if len(buffer) > MAX_REQUEST_BYTES:
                    win32file.WriteFile(handle, json.dumps(_reply(None, False, code="PAYLOAD_TOO_LARGE", message="Request exceeds the size limit.")).encode() + b"\n")
                    return
        except pywintypes.error:
            return
        finally:
            with self._guard:
                self._connections -= 1
            self._last_activity = time.monotonic()
            try:
                win32file.FlushFileBuffers(handle)  # DisconnectNamedPipe drops whatever the client has not read yet
                win32pipe.DisconnectNamedPipe(handle)
                win32file.CloseHandle(handle)
            except pywintypes.error:
                pass

    def _answer(self, api, origin, token, line):
        try:
            request = json.loads(line)
        except (ValueError, RecursionError):
            return _reply(None, False, code="BAD_REQUEST", message="Request is not valid JSON.")
        if not isinstance(request, dict) or not isinstance(request.get("id"), str) or not _ID.fullmatch(request["id"]):
            return _reply(None, False, code="BAD_REQUEST", message="Request needs an object with a valid id.")
        corr = request["id"]
        if request.get("cmd") in CONTROL:
            if request.get("ipc") != IPC:
                return _reply(corr, False, code="UNSUPPORTED_VERSION", message=f"Send ipc '{IPC}'.")
            if origin is Origin.CHILD:
                return _reply(corr, False, code="FORBIDDEN", message="Not allowed for this origin.")
            if request["cmd"] == "daemon.stop":
                threading.Timer(0.2, self.stop).start()  # the reply goes out first
                return _reply(corr, True, {"stopping": True})
            return _reply(corr, True, self.status())
        request["session"] = token
        return api.handle(request)


def _own_user_only():
    import win32api
    import win32con
    import win32security
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    acl = win32security.ACL()
    acl.AddAccessAllowedAce(win32security.ACL_REVISION, win32con.GENERIC_READ | win32con.GENERIC_WRITE, sid)
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorDacl(1, acl, 0)
    attributes = win32security.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    return attributes


def run(ctx) -> int:
    return Daemon(ctx, float(os.environ.get("RESPECTED_DAEMON_IDLE_SECONDS", IDLE_SECONDS))).run()
