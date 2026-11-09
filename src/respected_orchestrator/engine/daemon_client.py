"""Talking to the persistent engine (ADR-030): find it, start it on demand, ask it, stop it. No fallback: if it cannot be reached
the caller gets DaemonUnavailable and reports it; nothing is answered from a local copy of the engine."""
from __future__ import annotations

import json
import os
import secrets
import threading
import time

from .. import __version__
from ..context import engine_command
from .daemon import pipe_path

START_TIMEOUT = 15
ERROR_PIPE_BUSY = 231


class DaemonUnavailable(RuntimeError):
    pass


class DaemonVersionMismatch(DaemonUnavailable):
    pass


def _exchange(path: str, line: bytes, timeout: float) -> dict:
    result: dict = {}

    def work():
        deadline = time.monotonic() + 2
        while True:
            try:
                handle = open(path, "r+b", buffering=0)
                break
            except FileNotFoundError:
                result["error"] = DaemonUnavailable("The engine is not running.")
                return
            except OSError as error:
                if getattr(error, "winerror", None) != ERROR_PIPE_BUSY or time.monotonic() > deadline:
                    result["error"] = DaemonUnavailable(f"The engine could not be reached: {error}")
                    return
                time.sleep(0.05)
        with handle:
            try:
                handle.write(line)
                data = b""
                while not data.endswith(b"\n"):
                    chunk = handle.read(1 << 16)
                    if not chunk:
                        raise OSError("The engine closed the connection.")
                    data += chunk
                result["reply"] = json.loads(data)
            except (OSError, ValueError) as error:
                result["error"] = DaemonUnavailable(f"The engine did not answer: {error}")

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise DaemonUnavailable("The engine did not answer in time.")
    if "error" in result:
        raise result["error"]
    return result["reply"]


def request(ctx, cmd: str, payload: dict | None = None, timeout: float = 10) -> dict:
    """One command, the engine's own reply (`ok`/`result`/`error`). Raises DaemonUnavailable when there is no engine."""
    message = {"ipc": "1", "id": "c-" + secrets.token_hex(8), "session": "-", "cmd": cmd, "payload": payload or {}}
    return _exchange(pipe_path(ctx), json.dumps(message).encode("utf-8") + b"\n", timeout)


def status(ctx) -> dict | None:
    """The running engine's status, or None when none runs."""
    try:
        reply = request(ctx, "daemon.status", timeout=5)
    except DaemonUnavailable:
        return None
    return reply["result"] if reply.get("ok") else None


def start(ctx) -> dict:
    """The running engine's status, starting one first when needed. A running engine of another version is refused, not reused."""
    from .lanes import _spawn_detached
    current = status(ctx)
    if current is None:
        ctx.state_dir.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if k not in ("RESPECTED_ORCH_CHILD", "RESPECTED_ORCH_DELEGATED")}
        _spawn_detached(engine_command("--data-root", str(ctx.data_root), "_daemon"), ctx.data_root, ctx.state_dir / "daemon.log", env=env)
        deadline = time.monotonic() + START_TIMEOUT
        while current is None and time.monotonic() < deadline:
            time.sleep(0.2)
            current = status(ctx)
        if current is None:
            raise DaemonUnavailable(f"The engine did not start; see {ctx.state_dir / 'daemon.log'}.")
    if current["version"] != __version__:
        raise DaemonVersionMismatch(f"The running engine is {current['version']}, this program is {__version__}: restart it with `rorch daemon restart`.")
    return current


def stop(ctx, wait: float = 10) -> bool:
    """True when an engine was running and has stopped; False when none was running."""
    from .lanes import _pid_is_alive
    current = status(ctx)
    if current is None:
        return False
    try:
        request(ctx, "daemon.stop", timeout=5)
    except DaemonUnavailable:
        pass
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if not _pid_is_alive(current["pid"]):  # the process itself is gone, not just its pipe
            return True
        time.sleep(0.1)
    raise DaemonUnavailable("The engine did not stop in time.")
