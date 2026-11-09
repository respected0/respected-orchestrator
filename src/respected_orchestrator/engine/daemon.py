"""The persistent engine (ADR-030, slice 1): one process per data root that other front ends connect to.

Ownership is the OS file lock `daemon.lock` (a crash releases it). The only way in is a per-user named pipe whose access list
names the current user alone; there is no port. The wire protocol is local_api's line-delimited JSON, unchanged.

Who is calling is decided here, never by the client: a connection whose process descends from one of the engine's own
running workers is CHILD (no rights); the installed desktop program, recognised by its image path and the hash the package
manifest records, is RENDERER-level (read, task and settings commands); every other connection is MCP-level (read and task).
Approve and apply commands are in no catalog this process serves, whatever the origin: they stay on the native shell's
private channel and on the terminal (ADR-030 section 3).
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import secrets
import sys
import threading
import time
from pathlib import Path

from .. import __version__
from . import winproc
from .authority import Action, Origin
from .journal import Journal
from .local_api import COMMANDS, IPC, MAX_REQUEST_BYTES, LocalApi, _ID, _reply, session_controller
from .supervisor import Supervisor, SupervisorBusy

IDLE_SECONDS = 30 * 60  # nothing connected, no run working: the daemon leaves (ADR-030 D2)
CONTROL = ("daemon.status", "daemon.stop")
SERVED = frozenset(name for name, (_op, action) in COMMANDS.items() if action in (Action.READ, Action.TASK))
SERVED_DESKTOP = SERVED | frozenset(name for name, (_op, action) in COMMANDS.items() if action is Action.SETTINGS)
DESKTOP_EXE = "respected-orchestrator-desktop.exe"


class DaemonLock(Supervisor):
    LOCK_NAME = "daemon.lock"


def pipe_name(ctx) -> str:
    """One pipe per user and data root, so two data roots (tests, side-by-side installs) never meet."""
    digest = hashlib.sha256(str(ctx.data_root).lower().encode("utf-8")).hexdigest()[:12]
    return f"rorch-{''.join(c for c in getpass.getuser() if c.isalnum()) or 'user'}-{digest}"


def pipe_path(ctx) -> str:
    return "\\\\.\\pipe\\" + pipe_name(ctx)


_hashed: dict = {}


def is_desktop(pid: int, app_dir: Path | None = None) -> bool:
    """True when `pid` runs the desktop program of this installation: the very file next to the engine launcher, byte-for-byte the one
    the package manifest (distribution.json) lists. Without a packaged install nobody qualifies. Same-user code injection is not covered."""
    app = app_dir if app_dir is not None else (Path(sys.executable).parent if getattr(sys, "frozen", False) else None)
    image = winproc.process_image(pid)
    if app is None or not image:
        return False
    expected = app / DESKTOP_EXE
    if os.path.normcase(os.path.realpath(image)) != os.path.normcase(os.path.realpath(expected)):
        return False
    try:
        listed = json.loads((app / "distribution.json").read_text(encoding="utf-8"))["files"][DESKTOP_EXE]
        stat = expected.stat()
        key = (str(expected), stat.st_mtime_ns, stat.st_size)
        if key not in _hashed:
            _hashed[key] = hashlib.sha256(expected.read_bytes()).hexdigest()
        return isinstance(listed, str) and _hashed[key] == listed.lower()
    except (OSError, ValueError, KeyError, TypeError):
        return False


def classify(ctx, pid: int) -> Origin:
    """CHILD when `pid` is, or descends from, a process that is working on a run right now; RENDERER for the installed desktop program;
    otherwise MCP-level."""
    from . import maintenance
    working = {int(p) for p in maintenance.run_pids(ctx).values()}
    if working & {pid, *winproc.ancestors(pid)}:
        return Origin.CHILD
    return Origin.RENDERER if is_desktop(pid) else Origin.MCP


class Daemon:
    def __init__(self, ctx, idle_seconds: float = IDLE_SECONDS):
        self.ctx, self.idle_seconds = ctx, idle_seconds
        self.stop_event = threading.Event()
        self.started_at = time.time()
        self._connections, self._last_activity = 0, time.monotonic()
        self._origins: dict = {}  # origin name -> open connections, for `daemon status`
        self._guard = threading.Lock()
        self.sessions = session_controller(ctx)  # the one set of live chat sessions every connection shares

    def busy(self) -> bool:
        from . import maintenance
        with self._guard:
            if self._connections:
                return True
        return self.sessions.busy() or bool(maintenance.run_pids(self.ctx))

    def status(self) -> dict:
        return {"pid": os.getpid(), "version": __version__, "data_root": str(self.ctx.data_root), "started_at": self.started_at,
                "pipe": pipe_name(self.ctx), "idle_seconds": self.idle_seconds, "connections": self._connections,
                "origins": dict(self._origins)}

    def run(self) -> int:
        if os.name != "nt":
            raise RuntimeError("The persistent engine is Windows-only for now (ADR-030: Unix socket comes later).")
        try:
            lock = DaemonLock(self.ctx).acquire()
        except SupervisorBusy:
            print(json.dumps({"daemon": "busy", "pid": os.getpid()}), flush=True)
            return 1
        try:
            self._complete_install()
            winproc.contain_children()
            threading.Thread(target=self._watch_idle, daemon=True).start()
            print(json.dumps({"daemon": "started", **self.status()}), flush=True)
            self._serve_pipe()
        finally:
            lock.release()
        print(json.dumps({"daemon": "stopped", "pid": os.getpid()}), flush=True)
        return 0

    def _complete_install(self):
        """The installer only copies files (ADR-031): the first start after a copy or an update records the verified build and migrates old data.
        A folder whose files do not match its distribution.json is not recorded (the engine still runs; `health` and `repair` say what is wrong)."""
        if not getattr(sys, "frozen", False):
            return
        from ..interfaces import installation
        try:
            if installation.verify(self.ctx.app_root)["install_state"] != "installed":
                print(json.dumps({"daemon": "setup", **installation.setup(self.ctx)}), flush=True)
        except installation.OperationError as error:
            print(json.dumps({"daemon": "setup_failed", "code": error.code, "message": error.message}), flush=True)

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
        origin = None
        with self._guard:
            self._connections += 1
        try:
            origin = classify(self.ctx, win32pipe.GetNamedPipeClientProcessId(handle))
            with self._guard:
                self._origins[origin.value] = self._origins.get(origin.value, 0) + 1
            token = secrets.token_hex(16)  # local_api insists on one; the pipe's access list is the real gate
            api = self.api(origin, token)
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
                if origin is not None:
                    self._origins[origin.value] -= 1
                    if not self._origins[origin.value]:
                        del self._origins[origin.value]
            self._last_activity = time.monotonic()
            try:
                win32file.FlushFileBuffers(handle)  # DisconnectNamedPipe drops whatever the client has not read yet
                win32pipe.DisconnectNamedPipe(handle)
                win32file.CloseHandle(handle)
            except pywintypes.error:
                pass

    def api(self, origin, token):
        """One connection's view of the engine: the served catalog only, the sessions every connection shares."""
        return LocalApi(self.ctx, token, origin=origin, journal=Journal(self.ctx.state_dir / "events.log"),
                        only=SERVED_DESKTOP if origin is Origin.RENDERER else SERVED, sessions=self.sessions)

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
