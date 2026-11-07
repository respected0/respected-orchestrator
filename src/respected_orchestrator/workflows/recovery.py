"""Recovery decision table with hard resource limits (B4-08.01).

Pure function of (failure, state, limits): it returns what to do next and never does it. Actions are `retry` (bounded, may
carry a delay), `pause` (wait for a person to look; never resumed by itself), `operator` (a person must decide) and `stop`
(final). The failure taxonomy is the engine's own (failures.py); this adds the decision and the limits. Rules, in order:
1. Resource limits first (attempts, handoffs, wall time, tokens). Over a limit, or a limit that cannot be checked because the
   measurement is unknown, is `stop` / `pause`: fail closed, never "keep going".
2. A security/policy rejection is `stop`; auth and quota are `pause` and `operator`: no automatic resume, ever.
3. Only test failure, timeout, infrastructure, stale patch and a reviewer's correction request may `retry`, each under its own
   per-class cap, and the same class failing repeatedly opens the breaker (`pause`).
4. An unclassified failure is `operator`. There is no branch that returns `retry` without a counted attempt, so every loop ends.
Applying a patch is never an action of this module."""
from collections.abc import Mapping
from typing import Any

from ..engine import failures
from ..engine.failures import FailureClass

CEILING = {"max_attempts": 5, "max_handoffs": 8, "max_seconds": 86_400, "max_tokens": 50_000_000}
DEFAULT_LIMITS = {"max_attempts": 3, "max_handoffs": 3, "max_seconds": 3_600, "max_tokens": None}  # 3 attempts = retry_task's own rule
CLASS_CAP = {FailureClass.TEST_FAILURE: 2, FailureClass.TIMEOUT: 1, FailureClass.INFRASTRUCTURE: 2, FailureClass.STALE_PATCH: 1,
             FailureClass.REVIEWER_REJECT: 2}  # retries allowed per class within one task
BACKOFF = (0, 30, 120)
FRESH = {"attempts": 0, "handoffs": 0, "elapsed_seconds": 0.0, "spent_tokens": 0, "by_class": {}}


def limits(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Defaults plus validated overrides; anything invalid or above the ceiling raises (no silent default)."""
    out = {**DEFAULT_LIMITS, **(overrides or {})}
    for key, ceiling in CEILING.items():
        value = out.get(key)
        if value is None and key == "max_tokens":
            continue
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError(f"{key} must be an integer from 1 to {ceiling}")
    unknown = set(out) - set(CEILING)
    if unknown:
        raise ValueError("unknown limit: " + ", ".join(sorted(unknown)))
    return out


def _result(action: str, why: str, state: Mapping[str, Any], lim: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    left = {"attempts": lim["max_attempts"] - state["attempts"], "handoffs": lim["max_handoffs"] - state["handoffs"],
            "seconds": round(lim["max_seconds"] - state["elapsed_seconds"], 3),
            "tokens": None if lim["max_tokens"] is None or state["spent_tokens"] is None else lim["max_tokens"] - state["spent_tokens"]}
    return {"action": action, "why": why, "auto_resume": False, "remaining": left, **extra}


def decide(reason: str | None, provider_status: str | None, state: Mapping[str, Any], lim: Mapping[str, Any] | None = None, *,
           operator_resume: bool = False) -> dict[str, Any]:
    """Next step for one failure. `state`: attempts, handoffs, elapsed_seconds, spent_tokens (None = unknown), by_class.

    `operator_resume` is set only by operator.act after a person confirmed in their own dialog. It lifts the pause-type stops (auth,
    quota, a tripped class breaker, an unclassified failure, a final reviewer rejection) but never the resource limits above and never
    a policy denial: those stay stops."""
    lim = limits(lim)
    state = {**FRESH, **state}
    if state["attempts"] >= lim["max_attempts"]:
        return _result("stop", "attempt_limit_reached", state, lim)
    if state["handoffs"] >= lim["max_handoffs"]:
        return _result("stop", "handoff_limit_reached", state, lim)
    if state["elapsed_seconds"] >= lim["max_seconds"]:
        return _result("stop", "time_limit_reached", state, lim)
    if lim["max_tokens"] is not None:
        if state["spent_tokens"] is None:
            return _result("pause", "usage_unknown_under_token_budget", state, lim)
        if state["spent_tokens"] >= lim["max_tokens"]:
            return _result("stop", "token_budget_exhausted", state, lim)
    described = failures.describe(reason, provider_status)
    if not described:
        return _result("retry", "operator_resumed_unclassified_failure", state, lim, mode="operator_resume", delay_seconds=0) if operator_resume else             _result("operator", "unclassified_failure", state, lim)
    klass = FailureClass(described["failure_class"])
    if klass is FailureClass.POLICY_DENIED:
        return _result("stop", "policy_denied_is_never_retried", state, lim, failure_class=klass.value)
    resumed = {"mode": "operator_resume", "delay_seconds": 0, "failure_class": klass.value}
    if klass is FailureClass.AUTH:
        return _result("retry", "operator_resumed_after_authentication", state, lim, **resumed) if operator_resume else             _result("operator", "authentication_needed", state, lim, failure_class=klass.value)
    if klass is FailureClass.QUOTA:
        return _result("retry", "operator_resumed_after_quota", state, lim, **resumed) if operator_resume else             _result("pause", "quota_or_budget_exhausted_wait_for_a_person", state, lim, failure_class=klass.value)
    if not described["retryable"] and described["retry_policy"] == "manual":
        return _result("retry", "operator_resumed_after_reviewer_rejection", state, lim, **resumed) if operator_resume else             _result("operator", "final_decision_needs_a_person", state, lim, failure_class=klass.value)
    used = state["by_class"].get(klass.value, 0)
    if used >= CLASS_CAP[klass]:
        return _result("retry", "operator_resumed_past_the_class_breaker", state, lim, **resumed) if operator_resume else             _result("pause", "same_failure_class_keeps_failing_breaker_open", state, lim, failure_class=klass.value)
    delay = BACKOFF[min(used, len(BACKOFF) - 1)]
    mode = "new_patch" if described["retry_policy"] == "new_patch" else "correction" if described["retry_policy"] == "bounded_correction" else "retry"
    return _result("retry", f"{klass.value}_within_caps", state, lim, failure_class=klass.value, mode=mode, delay_seconds=delay)


def advance(state: Mapping[str, Any], decision: Mapping[str, Any], *, elapsed_seconds: float = 0.0, spent_tokens: int | None = 0) -> dict[str, Any]:
    """State after a decision. A retry counts one attempt and one failure of its class; elapsed/spent are what the failed try used."""
    new = {**FRESH, **state, "by_class": dict(state.get("by_class", {}))}
    new["elapsed_seconds"] = new["elapsed_seconds"] + max(0.0, elapsed_seconds)
    new["spent_tokens"] = None if spent_tokens is None or new["spent_tokens"] is None else new["spent_tokens"] + max(0, spent_tokens)
    if decision["action"] == "retry":
        new["attempts"] += 1
        new["by_class"][decision["failure_class"]] = new["by_class"].get(decision["failure_class"], 0) + 1
    return new
