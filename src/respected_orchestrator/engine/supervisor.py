"""Single-instance supervisor ownership (B3-02.01).

Ownership is an OS file lock held for the life of the process: a crash releases it, so there is no stale-PID
guesswork and no PID-reuse hole. Runs the supervisor started are recorded as claims; a claim is honoured while
its worker is alive, so two windows (or a restarted supervisor) can never start the same run twice. Closing a
window never touches a run: runs are detached processes (lanes._spawn_detached) and the lock only gates *starting*.
Existing campaign/project code stays the single source of truth for what a run does.
"""
import json
import os

from ..context import atomic_write_json
from .winproc import is_elevated
from .lanes import _pid_is_alive

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class SupervisorBusy(RuntimeError):
    pass


class RunAlreadyClaimed(RuntimeError):
    pass


class Supervisor:
    LOCK_NAME = "supervisor.lock"

    def __init__(self, ctx):
        self.ctx = ctx
        self._file = None
        self._claims = ctx.state_dir / "supervisor-claims.json"

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()

    def acquire(self):
        if is_elevated():
            raise PermissionError("The supervisor does not run elevated; start it as a normal user.")
        self.ctx.state_dir.mkdir(parents=True, exist_ok=True)
        handle = open(self.ctx.state_dir / self.LOCK_NAME, "a+b")
        try:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise SupervisorBusy("Another supervisor already owns this data root") from None
        self._file = handle
        return self

    def release(self):
        if self._file is None:
            return
        try:
            if os.name == "nt":
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._file.close()
            self._file = None

    def claims(self):
        try:
            return json.loads(self._claims.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def claim_run(self, run_id, pid):
        """Record that `pid` runs `run_id`. Refuses while a live worker already holds it."""
        if self._file is None:
            raise SupervisorBusy("Not the owner")
        claims = self.claims()
        holder = claims.get(run_id)
        if holder is not None and holder != pid and _pid_is_alive(int(holder)):
            raise RunAlreadyClaimed(f"Run {run_id} is already running (pid {holder})")
        claims[run_id] = pid
        atomic_write_json(self._claims, claims)

    def release_run(self, run_id):
        claims = self.claims()
        if claims.pop(run_id, None) is not None:
            atomic_write_json(self._claims, claims)


RUN_SCAN_LIMIT = 500  # newest run folders examined (ids embed their creation time); older runs are finished or long interrupted


def _alive(pid):
    return isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 and _pid_is_alive(pid)


def run_pids(ctx):
    """run id -> pid of the process that is working on it right now. Same facts `runner.effective_status` uses: a `running` status whose
    pid is alive, or a `queued` run whose detached starter (`supervisor.json`) is alive; plus any live supervisor claim."""
    from .evidence import load_signed
    found = {}
    for run, pid in Supervisor(ctx).claims().items():
        if _alive(int(pid) if str(pid).isdigit() else -1):
            found[run] = int(pid)
    root = ctx.state_dir
    if root.is_dir():
        for directory in sorted((p for p in root.glob("run-*") if p.is_dir()), reverse=True)[:RUN_SCAN_LIMIT]:
            try:
                status = load_signed(ctx, directory / "status.json")
                if status.get("status") == "running" and _alive(status.get("pid")):
                    found[directory.name] = status["pid"]
                elif status.get("status") == "queued" and (directory / "supervisor.json").is_file():
                    pid = load_signed(ctx, directory / "supervisor.json").get("pid")
                    if _alive(pid):
                        found[directory.name] = pid
            except (ValueError, OSError, KeyError):
                continue  # a damaged run record is reported by its own status, it is not "running"
    return found
