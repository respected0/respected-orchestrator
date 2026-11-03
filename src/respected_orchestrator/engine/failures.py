"""Closed failure taxonomy shared by the engine and MAF (ADR-005)."""
from enum import Enum


class FailureClass(str, Enum):
    TEST_FAILURE = "test_failure"
    POLICY_DENIED = "policy_denied"
    TIMEOUT = "timeout"
    QUOTA = "quota"
    AUTH = "auth"
    INFRASTRUCTURE = "infrastructure"
    STALE_PATCH = "stale_patch"
    REVIEWER_REJECT = "reviewer_reject"


class RetryPolicy(str, Enum):
    BOUNDED_RETRY = "bounded_retry"
    BOUNDED_CORRECTION = "bounded_correction"
    NEW_PATCH = "new_patch"
    MANUAL = "manual"


SYNONYMS = {
    "test_failed": FailureClass.TEST_FAILURE,
    "test_failure": FailureClass.TEST_FAILURE,
    "scope_violation": FailureClass.POLICY_DENIED,
    "policy_denied": FailureClass.POLICY_DENIED,
    "timed_out": FailureClass.TIMEOUT,
    "timeout": FailureClass.TIMEOUT,
    "reviewer_timeout": FailureClass.TIMEOUT,
    "limit_exhausted": FailureClass.QUOTA,
    "quota": FailureClass.QUOTA,
    "token_budget_exceeded": FailureClass.QUOTA,
    "auth_required": FailureClass.AUTH,
    "auth": FailureClass.AUTH,
    "stale_project": FailureClass.STALE_PATCH,
    "stale_patch": FailureClass.STALE_PATCH,
    "inherited_patch_conflict": FailureClass.STALE_PATCH,
    "integration_conflict": FailureClass.STALE_PATCH,
    "reviewer_reject": FailureClass.REVIEWER_REJECT,
    "rejected": FailureClass.REVIEWER_REJECT,
    "needs_changes": FailureClass.REVIEWER_REJECT,
    "worker_failed": FailureClass.INFRASTRUCTURE,
    "invalid_worker_result": FailureClass.INFRASTRUCTURE,
    "engine_error": FailureClass.INFRASTRUCTURE,
    "sandbox_unavailable": FailureClass.INFRASTRUCTURE,
    "reviewer_execution_failed": FailureClass.INFRASTRUCTURE,
    "reviewer_disconnected": FailureClass.INFRASTRUCTURE,
    "invalid_review_result": FailureClass.INFRASTRUCTURE,
    "supervisor_exited": FailureClass.INFRASTRUCTURE,
}

PROVIDER_SYNONYMS = {
    "AUTH_REQUIRED": FailureClass.AUTH,
    "LIMIT_EXHAUSTED": FailureClass.QUOTA,
    "TIMEOUT": FailureClass.TIMEOUT,
    "TEST_FAILED": FailureClass.TEST_FAILURE,
    "SCOPE_VIOLATION": FailureClass.POLICY_DENIED,
    "INTEGRATION_CONFLICT": FailureClass.STALE_PATCH,
    "WORKER_FAILED": FailureClass.INFRASTRUCTURE,
}

POLICIES = {
    FailureClass.TEST_FAILURE: RetryPolicy.BOUNDED_RETRY,
    FailureClass.POLICY_DENIED: RetryPolicy.MANUAL,
    FailureClass.TIMEOUT: RetryPolicy.BOUNDED_RETRY,
    FailureClass.QUOTA: RetryPolicy.MANUAL,
    FailureClass.AUTH: RetryPolicy.MANUAL,
    FailureClass.INFRASTRUCTURE: RetryPolicy.BOUNDED_RETRY,
    FailureClass.STALE_PATCH: RetryPolicy.NEW_PATCH,
    FailureClass.REVIEWER_REJECT: RetryPolicy.BOUNDED_CORRECTION,
}


def as_failure_class(value):
    if isinstance(value, FailureClass):
        return value
    try:
        return FailureClass(str(value))
    except ValueError:
        return None


def classify(reason=None, provider_status=None):
    provider = as_failure_class(PROVIDER_SYNONYMS.get(str(provider_status).upper())) if provider_status else None
    if provider is not None:
        return provider
    return as_failure_class(SYNONYMS.get(str(reason).casefold())) if reason else None


def fields(value, reason=None):
    failure = as_failure_class(value)
    if failure is None:
        return {}
    # A reviewer rejection is final; NEEDS_CHANGES is the bounded-correction path.
    policy = RetryPolicy.MANUAL if str(reason).casefold() in {"reviewer_reject", "rejected"} else POLICIES[failure]
    return {
        "failure_class": failure.value,
        "retryable": policy in {RetryPolicy.BOUNDED_RETRY, RetryPolicy.BOUNDED_CORRECTION},
        "retry_policy": policy.value,
    }


def describe(reason=None, provider_status=None):
    return fields(classify(reason, provider_status), reason=reason)
