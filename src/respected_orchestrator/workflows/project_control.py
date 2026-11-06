"""Operator controls for a started project: status with a plain explanation, cancel, resume (B3-04.04).

Thin and exact: the state machine stays in `project.py`. This adds (1) an explanation of why a project is where it is and
what, if anything, the operator can do, (2) idempotent cancel/resume keyed by an operation id so a repeated click or a
retried IPC call moves the state once, (3) an append-only audit event for each accepted transition, and (4) a refusal to
resume when a role/agent the plan needs is no longer available (zero workers started).
"""
from __future__ import annotations

from ..engine.journal import Journal
from ..engine.runner import tool_available
from . import project
from .project import _TERMINAL

_EXPLAIN = {
    "created": ("Proje oluşturuldu, henüz çalışmıyor.", False, "resume"),
    "running": ("Proje çalışıyor.", False, "wait"),
    "completed": ("Proje tamamlandı.", False, "none"),
    "cancelled": ("Proje iptal edildi.", False, "none"),
    "blocked": ("Proje durdu ve bir karar bekliyor; yeniden denemek yeni bir proje gerektirir.", False, "none"),
}


def explain(state):
    """Never claims more than the stored state: unknown states are reported as such, not as healthy."""
    status = state.get("status")
    text, retryable, nxt = _EXPLAIN.get(status, (f"Bilinmeyen durum: {status!r}.", False, "none"))
    alive = bool(state.get("alive"))
    if status in ("created", "running") and not alive:
        text, retryable, nxt = ("Proje çalışıyor görünüyor ama süpervizör yaşamıyor; devam ettirilebilir.", True, "resume")
    elif status == "running" and alive:
        text, retryable, nxt = (_EXPLAIN["running"])
    if state.get("cancel_requested") and status not in _TERMINAL:
        text, retryable, nxt = ("İptal istendi; süpervizör kapanışı bekleniyor.", False, "wait")
    return {"state": status, "alive": alive, "summary": text, "reason": state.get("reason"), "retryable": retryable, "next_action": nxt}


def status(ctx, project_id):
    state = project.project_status(ctx, project_id)
    if (project.project_dir(ctx, project_id) / "cancel").is_file():
        state["cancel_requested"] = True
    return {"project": {k: state.get(k) for k in ("project_id", "status", "reason", "alive", "created_at", "weighted_tokens")},
            "explanation": explain(state)}


def _audit(ctx, operation_id, event, project_id, payload=None):
    return Journal(ctx.state_dir / "events.log").append(operation_id, event, None, {"project_id": project_id, **(payload or {})})


def cancel(ctx, project_id, operation_id):
    state = project.project_status(ctx, project_id)
    if state["status"] in _TERMINAL:
        raise ValueError(f"Project is {state['status']}; nothing to cancel")
    if (project.project_dir(ctx, project_id) / "cancel").is_file():
        return {"project_id": project_id, "status": "cancel_requested", "repeat": True}  # same effect, no second transition
    result = project.cancel_project(ctx, project_id)
    _audit(ctx, operation_id, "project.cancel_requested", project_id)
    return {**result, "repeat": False}


def resume(ctx, project_id, operation_id):
    directory = project.project_dir(ctx, project_id)
    from ..engine.evidence import load_signed
    state = load_signed(ctx, directory / "project.json")
    if state["status"] not in _TERMINAL:
        for phase in state["spec"]["phases"]:
            for lane in phase["workstreams"]:
                worker = (lane.get("request") or {}).get("worker")
                if worker not in (None, "custom") and not tool_available(worker):
                    raise ValueError(f"Role unavailable: worker '{worker}' ({phase['name']}/{lane['name']}) is not installed; nothing was started")
    result = project.resume_project(ctx, project_id)  # refuses terminal, already-running, and stale checkpoints without approval
    _audit(ctx, operation_id, "project.resumed", project_id, {"pid": result.get("pid")})
    return result
