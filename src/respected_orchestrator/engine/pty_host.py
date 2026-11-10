"""The terminal host (ADR-035): one detached process per agent terminal. It owns the pseudo console, so the terminal lives on when the
engine or the desktop goes away, and it talks to nobody but the persistent engine of its data root.

The way in is a per-user named pipe (no port). Each connection sends one JSON line first:
  {"op": "attach"}                      -> the connection becomes one-way: {"data": base64} lines (what is kept of the output first, then
                                           live), {"exit": code} when the program ends, {"ping": true} every PING_SECONDS
  {"op": "input", "data": base64} | {"op": "resize", "cols", "rows"} | {"op": "status"} | {"op": "kill"}   -> one JSON line back
"""
from __future__ import annotations

import base64
import json
import os
import queue
import threading
import time

RING_BYTES = 256 * 1024  # shortcut: the raw tail is replayed, not a rendered screen; the viewer resizes after attaching so a full-screen program repaints
PING_SECONDS = 2
LINGER_SECONDS = 30  # after the program ended and the last viewer left
VIEWER_QUEUE = 512
ENGINE_PID_TTL = 5


def pipe_name(terminal_id: str) -> str:
    return f"rorch-pty-{terminal_id}"


def pipe_path(terminal_id: str) -> str:
    return "\\\\.\\pipe\\" + pipe_name(terminal_id)


class Host:
    def __init__(self, ctx, spec):
        from .conpty import Pty
        self.ctx, self.id = ctx, spec["id"]
        self.cols, self.rows = spec["cols"], spec["rows"]
        # the program is marked like every process the engine starts: it can never act as the human approver
        self.pty = Pty(spec["argv"], spec["cwd"], {**os.environ, "RESPECTED_ORCH_CHILD": "1"}, self.cols, self.rows)
        self.ring, self.viewers, self.exit = bytearray(), set(), None
        self.lock, self.stop_event = threading.Lock(), threading.Event()
        self._engine = (0.0, None)

    def _tell(self, note):
        for viewer in list(self.viewers):
            try:
                viewer.put_nowait(note)
            except queue.Full:  # a viewer that stopped reading is dropped; it attaches again and gets the kept output
                self.viewers.discard(viewer)
                viewer.lost = True

    def _pump(self):
        while True:
            data = self.pty.read()
            if not data:
                return
            with self.lock:
                self.ring += data
                del self.ring[:-RING_BYTES]
                self._tell({"data": base64.b64encode(data).decode("ascii")})

    def _watch(self):
        code = self.pty.exit_code(0xFFFFFFFF)
        time.sleep(0.3)  # what the program printed last is still on its way through the pseudo console
        with self.lock:
            self.exit = code
            self._tell({"exit": code})
        quiet = time.monotonic()
        while not self.stop_event.wait(1):
            if self.viewers:
                quiet = time.monotonic()
            elif time.monotonic() - quiet >= LINGER_SECONDS:
                break
        self.shutdown()

    def shutdown(self):
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        self.pty.close()
        try:  # wake the blocked accept
            open(pipe_path(self.id), "r+b", buffering=0).close()
        except OSError:
            pass

    def _from_engine(self, pid):
        """True when `pid` is the persistent engine of this data root, as that engine itself reports on its own pipe."""
        from . import daemon_client
        at, known = self._engine
        if known != pid or time.monotonic() - at > ENGINE_PID_TTL:
            status = daemon_client.status(self.ctx)
            known = status["pid"] if status else None
            self._engine = (time.monotonic(), known)
        return known == pid

    def run(self) -> int:
        from .daemon import accept_loop
        threading.Thread(target=self._pump, daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()
        accept_loop(pipe_path(self.id), self.stop_event, self._connection)
        return 0

    def _connection(self, handle):
        import pywintypes
        import win32file
        import win32pipe

        def send(message):
            win32file.WriteFile(handle, json.dumps(message).encode("ascii") + b"\n")

        viewer = None
        try:
            if not self._from_engine(win32pipe.GetNamedPipeClientProcessId(handle)):
                return
            buffer = b""
            while b"\n" not in buffer and len(buffer) < (1 << 20):
                buffer += win32file.ReadFile(handle, 1 << 16)[1]
            request = json.loads(buffer.split(b"\n", 1)[0])
            op = request.get("op")
            if op == "attach":
                viewer = queue.Queue(VIEWER_QUEUE)
                viewer.lost = False
                with self.lock:  # nothing is drawn between the kept output and the first live line
                    kept, ended = bytes(self.ring), self.exit
                    self.viewers.add(viewer)
                if kept:
                    send({"data": base64.b64encode(kept).decode("ascii")})
                if ended is not None:
                    send({"exit": ended})
                while not self.stop_event.is_set() and not viewer.lost:
                    try:
                        send(viewer.get(timeout=PING_SECONDS))
                    except queue.Empty:
                        send({"ping": True})  # a viewer that has gone is found out here
                return
            if op == "input":
                self.pty.write(base64.b64decode(request["data"], validate=True))
            elif op == "resize":
                self.cols, self.rows = int(request["cols"]), int(request["rows"])
                self.pty.resize(self.cols, self.rows)
            elif op == "kill":
                send({"ok": True})
                win32file.FlushFileBuffers(handle)
                self.shutdown()
                return
            elif op != "status":
                send({"ok": False, "message": "unknown op"})
                return
            send({"ok": True, "alive": self.exit is None, "exit": self.exit, "pid": self.pty.pid, "cols": self.cols, "rows": self.rows})
        except (pywintypes.error, OSError, ValueError, KeyError, TypeError) as error:
            try:
                send({"ok": False, "message": str(error)[:200]})
            except pywintypes.error:
                pass
        finally:
            self.viewers.discard(viewer)
            try:
                win32file.FlushFileBuffers(handle)
                win32pipe.DisconnectNamedPipe(handle)
                win32file.CloseHandle(handle)
            except pywintypes.error:
                pass


def run(ctx, spec_json: str) -> int:
    """`rorch _pty-host SPEC`: started by the engine only (terminals.py). SPEC: {"id", "argv", "cwd", "cols", "rows"}."""
    return Host(ctx, json.loads(spec_json)).run()
