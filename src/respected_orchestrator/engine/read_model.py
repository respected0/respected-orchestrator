"""Read-only DTOs for the desktop Project/Run board (B3-04.01).

Everything is derived from the engine's own signed files on every call (never from UI memory), with the same status
decision the CLI uses (`runner.effective_status`). A damaged or inconsistent record becomes an explicit `invalid` row
with a reason; it never raises and never looks like a healthy run.
"""
from __future__ import annotations

import re

from . import runner
from .evidence import load_signed
from ..context import safe_path

MAX_PAGE = 200
STATE_OF = {"queued": "queued", "running": "in_progress", "completed": "done", "failed": "failed", "timed_out": "failed",
            "error": "failed", "cancelled": "cancelled", "interrupted": "stale"}
STATES = frozenset(STATE_OF.values()) | {"invalid"}
_RUN = re.compile(r"run-\d{14}-[0-9a-f]{12}\Z")
_PROJECT = re.compile(r"proj-[a-z0-9-]{1,60}\Z")


def _title(text, limit=160):
    return " ".join(str(text or "").split())[:limit]


def run_dto(ctx, run_id):
    base = {"run_id": run_id, "state": "invalid", "status": None, "reason": None, "task": "", "kind": None, "agent": None,
            "project_root": None, "created_at": None, "updated_at": None, "dependencies": {}, "evidence": {}, "error": None}
    try:
        directory = ctx.run_dir(run_id)
        request = load_signed(ctx, directory / "request.json")
        status = runner.effective_status(ctx, directory)
    except (ValueError, OSError, KeyError) as error:
        return {**base, "error": f"unreadable: {str(error)[:160]}"}
    if request.get("run_id") != run_id or status.get("run_id") != run_id:
        return {**base, "error": "identity_mismatch"}
    raw = status.get("status")
    dto = {**base, "status": raw if isinstance(raw, str) else None, "reason": status.get("reason"),
           "task": _title(request.get("task")), "kind": request.get("kind"), "agent": request.get("worker"),
           "project_root": request.get("project_root"), "created_at": request.get("created_at"),
           "updated_at": status.get("updated_at"),
           "dependencies": {k: request[k] for k in ("retry_of", "correction_of", "inherited_patch_run_id") if request.get(k)},
           "evidence": {"patch": (directory / "worker.patch").is_file(),
                        "logs": sorted(p.name for p in directory.glob("*.log"))}}
    if raw not in STATE_OF:
        return {**dto, "error": "unknown_status"}
    return {**dto, "state": STATE_OF[raw]}


def runs_page(ctx, *, states=None, query=None, newest_first=True, cursor=None, limit=50):
    """Keyset pagination over run ids (they embed their creation time, so the order is stable and total)."""
    limit = max(1, min(int(limit), MAX_PAGE))
    wanted = set(states) if states else None
    if wanted is not None and not wanted <= STATES:
        raise ValueError("Unknown state filter")
    needle = _title(query).casefold() if query else ""
    if cursor is not None and not _RUN.fullmatch(str(cursor)):
        raise ValueError("Bad cursor")
    root = safe_path(ctx.state_dir)
    names = sorted((p.name for p in root.glob("run-*") if p.is_dir()), reverse=newest_first) if root.is_dir() else []
    rows, more = [], False
    for name in names:
        if cursor is not None and ((name >= cursor) if newest_first else (name <= cursor)):
            continue
        if not _RUN.fullmatch(name):
            dto = {"run_id": name, "state": "invalid", "error": "bad_run_id"}
        else:
            dto = run_dto(ctx, name)
        if wanted is not None and dto["state"] not in wanted:
            continue
        if needle and needle not in f"{dto['run_id']} {dto.get('task', '')} {dto.get('agent') or ''}".casefold():
            continue
        if len(rows) == limit:
            more = True
            break
        rows.append(dto)
    return {"runs": rows, "next_cursor": rows[-1]["run_id"] if more else None}


def projects_page(ctx, *, cursor=None, limit=50):
    limit = max(1, min(int(limit), MAX_PAGE))
    if cursor is not None and not _PROJECT.fullmatch(str(cursor)):
        raise ValueError("Bad cursor")
    root = safe_path(ctx.data_root / "projects")
    names = sorted((p.name for p in root.glob("proj-*") if p.is_dir()), reverse=True) if root.is_dir() else []
    rows, more = [], False
    for name in names:
        if cursor is not None and name >= cursor:
            continue
        if len(rows) == limit:
            more = True
            break
        rows.append(project_dto(ctx, name))
    return {"projects": rows, "next_cursor": rows[-1]["project_id"] if more else None}


def project_dto(ctx, project_id):
    base = {"project_id": project_id, "state": "invalid", "goal": "", "created_at": None, "alive": False, "stages": [], "error": None}
    try:
        from ..workflows import project as projects
        directory = projects.project_dir(ctx, project_id)
        state = load_signed(ctx, directory / "project.json")
        alive = projects._supervisor_alive(ctx, directory)
        spec_phases = {p["name"]: p for p in state["spec"]["phases"]}
        stages = [{"name": name, "status": record.get("status"), "after": list(spec_phases.get(name, {}).get("after", [])),
                   "attempts": len(record.get("attempts") or [])} for name, record in state["phases"].items()]
    except (ValueError, OSError, KeyError, TypeError) as error:
        return {**base, "error": f"unreadable: {str(error)[:160]}"}
    if state.get("project_id") != project_id:
        return {**base, "error": "identity_mismatch"}
    return {**base, "state": state.get("status") if isinstance(state.get("status"), str) else "invalid",
            "goal": _title(state["spec"].get("goal"), 200), "created_at": state.get("created_at"), "alive": alive, "stages": stages,
            "error": None}
