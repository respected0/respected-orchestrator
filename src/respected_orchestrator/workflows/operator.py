"""Operator escalation and explainable recovery (B4-08.02).

When a run stops, `case()` explains why in plain terms, what the recovery table decided, what budget is left and which controlled
actions a person may choose. `act()` carries out one of them, but only for a human (authority.PRIVILEGED), only against the exact
case that was shown (a binding digest over run, status time, decision and action list: a stale or foreign binding is refused), and
only inside the same hard limits as an automatic retry: attempts, time, tokens and policy denials are never lifted. There is no
action that applies a patch; the strongest action starts a *new queued run* through retry_task, which re-validates the project from
scratch. Every opening and every action is written to the event store, so the timeline shows who did what and why."""
import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from ..context import EngineContext
from ..engine import failures
from ..engine.authority import Action, Origin, authorize
from ..engine.evidence import load_signed
from ..engine.journal import Journal
from . import recovery

OPENED, ACTED = "recovery.case_opened", "recovery.operator_action"
ACTIONS = ("retry", "resume", "dismiss")
PLAIN = {
    "test_failure": "The acceptance checks failed.", "policy_denied": "The worker tried something the policy forbids.",
    "timeout": "The run ran out of time.", "quota": "The provider reports a quota or usage limit.",
    "auth": "The provider needs you to sign in again.", "infrastructure": "The worker or its sandbox failed, not the task itself.",
    "stale_patch": "The project moved on, so the patch no longer fits.", "reviewer_reject": "The reviewer rejected or asked for changes."}
STEPS = {
    "test_failure": "Read the failing check output, then retry once.", "policy_denied": "Review what was attempted; this is never retried automatically.",
    "timeout": "Raise the deadline or split the task, then retry.", "quota": "Wait for the limit to reset (or switch profile), then resume.",
    "auth": "Sign in again in the provider's own tool, confirm it works, then resume.", "infrastructure": "Check the tool is installed and the sandbox is available, then retry.",
    "stale_patch": "Retry: it starts a new run from the current project state.", "reviewer_reject": "Read the review, then retry or write a correction task."}


class OperatorError(PermissionError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _chain(ctx: EngineContext, run_id: str, inspect_run: Callable[..., Mapping]) -> tuple[Mapping[str, Any], dict[str, int]]:
    inspected = inspect_run(ctx, run_id)
    by_class: dict[str, int] = {}
    parent = (inspected.get("request") or {}).get("retry_of")
    while parent and sum(by_class.values()) < 5:
        earlier = inspect_run(ctx, parent)
        klass = failures.describe(earlier.get("reason"), earlier.get("provider_status")).get("failure_class")
        if klass:
            by_class[klass] = by_class.get(klass, 0) + 1
        parent = (earlier.get("request") or {}).get("retry_of")
    return inspected, by_class


def _decisions(inspected: Mapping[str, Any], by_class: Mapping[str, int]) -> tuple[dict[str, Any], dict[str, Any]]:
    state = {"attempts": (inspected.get("request") or {}).get("retry_depth", 0) + 1, "by_class": dict(by_class)}
    auto = recovery.decide(inspected.get("reason"), inspected.get("provider_status"), state, {"max_attempts": 3})
    manual = recovery.decide(inspected.get("reason"), inspected.get("provider_status"), state, {"max_attempts": 3}, operator_resume=True)
    return auto, manual


def case(ctx: EngineContext, run_id: str, *, inspect_run: Callable[..., Mapping], record: bool = True) -> dict[str, Any]:
    """The explanation card for a stopped run. Raises ValueError for a run that has not failed."""
    inspected, by_class = _chain(ctx, run_id, inspect_run)
    if inspected.get("status") not in {"failed", "timed_out", "cancelled", "interrupted"}:
        raise ValueError("Only unsuccessful terminal runs have an escalation case")
    described = failures.describe(inspected.get("reason"), inspected.get("provider_status"))
    klass = described.get("failure_class")
    auto, manual = _decisions(inspected, by_class)
    actions = ["dismiss"]
    if auto["action"] == "retry":
        actions.insert(0, "retry")
    elif manual["action"] == "retry":
        actions.insert(0, "resume")  # only a person may lift this stop; the limits still apply
    cautions = []
    if "auth" in by_class and klass != "auth":
        cautions.append("An earlier attempt in this chain failed on authentication; resuming needs your acknowledgement that sign-in was checked (auth_checked).")
    body = {"run_id": run_id, "status": inspected["status"], "updated_at": inspected.get("updated_at"), "decision": auto["why"], "actions": actions}
    binding = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    card = {**body, "binding": binding, "problem": {"class": klass, "reason": inspected.get("reason"), "plain": PLAIN.get(klass, "The failure is not one the engine knows how to classify.")},
            "recommended_step": STEPS.get(klass, "Read the run's evidence, then decide."), "automatic": {"action": auto["action"], "why": auto["why"]},
            "remaining": auto["remaining"], "cautions": cautions, "needs_acknowledgement": ["auth_checked"] if cautions else [],
            "never": ["apply a patch", "lift a policy denial", "exceed the attempt, time or token limits"]}
    if record:
        Journal(ctx.state_dir / "events.log").append(f"case-{run_id}-{binding[:12]}", OPENED, run_id,
                                                     {"problem": card["problem"]["class"], "decision": card["decision"], "actions": actions})
    return card


def act(ctx: EngineContext, run_id: str, action: str, binding: str, *, origin: Origin, inspect_run: Callable[..., Mapping],
        retry: Callable[..., Mapping], acknowledge: tuple[str, ...] = ()) -> dict[str, Any]:
    """Carry out one action from the case. `retry(ctx, run_id, operator_resume=bool)` is runner.retry_task."""
    authorize(origin, Action.PRIVILEGED)
    if action not in ACTIONS:
        raise OperatorError("BAD_ACTION", f"action must be one of {', '.join(ACTIONS)}")
    current = case(ctx, run_id, inspect_run=inspect_run, record=False)
    if binding != current["binding"]:
        # Distinguish the two ways a binding goes wrong, so the message tells a person what to do next.
        raise OperatorError("STALE_OR_FOREIGN", "this approval is not about the case as it is now (another run, or the run changed); open the case again")
    if action not in current["actions"]:
        raise OperatorError("ACTION_NOT_ALLOWED", f"{action} is not available for this case; available: {', '.join(current['actions'])}")
    if current["needs_acknowledgement"] and set(current["needs_acknowledgement"]) - set(acknowledge) and action in ("retry", "resume"):
        raise OperatorError("ACK_REQUIRED", current["cautions"][0])
    journal = Journal(ctx.state_dir / "events.log")
    operation = f"act-{run_id}-{action}-{current['binding'][:12]}"
    if action == "dismiss":
        journal.append(operation, ACTED, run_id, {"action": action, "outcome": "dismissed"})
        return {"run_id": run_id, "action": action, "outcome": "dismissed"}
    created = retry(ctx, run_id, operator_resume=(action == "resume"))
    journal.append(operation, ACTED, run_id, {"action": action, "outcome": "queued", "new_run": created["run_id"]})
    return {"run_id": run_id, "action": action, "outcome": "queued", "new_run": created["run_id"]}


def timeline(ctx: EngineContext, run_id: str) -> list[dict[str, Any]]:
    """Recovery and handoff events about this run, oldest first."""
    return [{"seq": r["seq"], "type": r["type"], "at": r["ts"], **{k: v for k, v in r["p"].items() if k != "envelope"}}
            for r in Journal(ctx.state_dir / "events.log").scan() if r.get("run") == run_id and r["type"].split(".")[0] in ("recovery", "handoff")]
