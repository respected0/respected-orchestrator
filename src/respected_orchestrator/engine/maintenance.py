"""Update window: stop accepting new work, let running work finish, never guess about work that was cut off (B3-09.03, ADR-026).

The installer (or an operator) calls `begin` before replacing the program folder and `end` after. While the window is open, anything that
would *start* work (a new task, a start, a project or campaign start/resume, an apply) is refused with a plain message; processes that were
accepted before the window (supervisors, `maf` runs) keep going so a running project is not broken by the update. `drain` waits for them and
reports what is still running. The window expires on its own (a crashed installer must not lock the product out): an expired marker is shown as
expired and refuses nothing. Work that is killed anyway is not lost or misread: its status becomes `interrupted` (see `runner.effective_status`),
and an interrupted run is never applied automatically.
"""
from __future__ import annotations

import os
import time

from ..context import safe_path
from .evidence import load_signed, save_signed

MARKER = "maintenance.json"
DEFAULT_TTL = 1800  # seconds; the window of one update, not a lock
MAX_TTL = 3600
_ADMITTED = False  # a process that was accepted before the window opened (a supervisor, a running maf) may finish its own work


class MaintenanceError(ValueError):
    pass


def admit():
    """Mark this process as work that was accepted already; it is not refused by an update window that opens later."""
    global _ADMITTED
    _ADMITTED = True


def _path(ctx):
    return safe_path(ctx.data_root / MARKER)


def _read(ctx):
    path = _path(ctx)
    if not path.is_file():
        return None
    try:
        return load_signed(ctx, path)
    except (ValueError, OSError):
        return {"state": "unreadable"}


def current(ctx, now=None):
    """The window as it is now: {active, expired, reason, since, expires_at} (active only while it has not expired)."""
    marker = _read(ctx)
    if marker is None:
        return {"active": False, "expired": False, "reason": None, "since": None, "expires_at": None}
    if marker.get("state") != "updating":  # a damaged marker never silently locks or unlocks anything: it is reported
        return {"active": False, "expired": False, "damaged": True, "reason": None, "since": None, "expires_at": None}
    expired = (now if now is not None else time.time()) >= marker["expires_at"]
    return {"active": not expired, "expired": expired, "reason": marker.get("reason"), "since": marker.get("since"),
            "expires_at": marker.get("expires_at"), "engine_version": marker.get("engine_version")}


def begin(ctx, *, reason="update", ttl=DEFAULT_TTL):
    if not isinstance(ttl, int) or isinstance(ttl, bool) or not 60 <= ttl <= MAX_TTL:
        raise MaintenanceError(f"ttl 60 ile {MAX_TTL} saniye arasında olmalı")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 80:
        raise MaintenanceError("reason kısa bir metin olmalı")
    from .. import __version__
    now = time.time()
    save_signed(ctx, _path(ctx), {"state": "updating", "reason": reason.strip(), "since": now, "expires_at": now + ttl,
                                  "engine_version": __version__})
    return current(ctx)


def end(ctx):
    _path(ctx).unlink(missing_ok=True)
    return current(ctx)


def refuse_if_active(ctx, what):
    if _ADMITTED:
        return
    window = current(ctx)
    if window["active"]:
        raise MaintenanceError(f"Güncelleme sürüyor; {what} şimdi kabul edilmiyor. Güncelleme bitince yeniden deneyin "
                               f"(en geç {max(1, int((window['expires_at'] - time.time()) / 60) + 1)} dakika içinde kendiliğinden açılır).")


def _alive(pid):
    from . import lanes
    return isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 and lanes._pid_is_alive(pid)


versions = {}  # id -> the engine version recorded by the supervisor that is running it (None: recorded before versions existed)


RUN_SCAN_LIMIT = 500  # newest run folders examined (ids embed their creation time); older runs are finished or long interrupted


def run_pids(ctx):
    """run id -> pid of the process that is working on it right now. Same facts `runner.effective_status` uses: a `running` status whose
    pid is alive, or a `queued` run whose detached starter (`supervisor.json`) is alive; plus any live supervisor claim."""
    from .supervisor import Supervisor
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


def running(ctx):
    """Work that is still running: runs, project supervisors and campaign supervisors (ids only; versions of supervisors in `versions`)."""
    found = {"runs": sorted(run_pids(ctx)), "projects": [], "campaigns": []}
    versions.clear()
    for key, folder in (("projects", "projects"), ("campaigns", "campaigns")):
        root = ctx.data_root / folder
        if not root.is_dir():
            continue
        for directory in sorted(p for p in root.iterdir() if p.is_dir()):
            marker = directory / "supervisor.json"
            try:
                record = load_signed(ctx, marker) if marker.is_file() else {}
                if _alive(record.get("pid")):
                    found[key].append(directory.name)
                    versions[directory.name] = record.get("engine_version")
            except (ValueError, OSError):
                continue  # a damaged supervisor record is not "running"; effective_status reports it elsewhere
    return found


def total(found):
    return sum(len(v) for v in found.values())


def drain(ctx, seconds, *, poll=1.0, sleep=time.sleep, clock=time.monotonic):
    """Wait up to `seconds` for running work to finish. Never stops anything: what is left is reported for a person (or the installer) to decide."""
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not 0 <= seconds <= 3600:
        raise MaintenanceError("seconds 0 ile 3600 arasında olmalı")
    deadline = clock() + seconds
    found = running(ctx)
    while total(found) and clock() < deadline:
        sleep(min(poll, max(0.0, deadline - clock())))
        found = running(ctx)
    return {"drained": total(found) == 0, "remaining": found, "other_version": other_versions(),
            "waited_seconds": round(seconds - max(0.0, deadline - clock()), 1)}


def other_versions():
    """Running supervisors that were started by a different engine version than this one: the update must not replace their files unnoticed."""
    from .. import __version__
    return sorted(i for i, v in versions.items() if v != __version__)


def status(ctx):
    found = running(ctx)
    return {"window": current(ctx), "running": found, "other_version": other_versions()}
