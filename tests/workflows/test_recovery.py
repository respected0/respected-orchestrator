import unittest

from respected_orchestrator.engine import failures
from respected_orchestrator.workflows import recovery as rc

# one engine "reason" per failure class (the strings the engine really writes)
REASONS = {"test_failure": "test_failed", "policy_denied": "scope_violation", "timeout": "timed_out", "quota": "limit_exhausted",
           "auth": "auth_required", "infrastructure": "worker_failed", "stale_patch": "stale_project", "reviewer_reject": "needs_changes"}


def run_until_done(reason, provider=None, lim=None, per_try_seconds=1.0, per_try_tokens=10, cap=50):
    """Feed the same failure forever; returns the list of actions. A policy that loops would hit `cap`."""
    state, actions = dict(rc.FRESH), []
    for _ in range(cap):
        d = rc.decide(reason, provider, state, lim)
        actions.append(d["action"])
        if d["action"] != "retry":
            return actions, d
        state = rc.advance(state, d, elapsed_seconds=per_try_seconds, spent_tokens=per_try_tokens)
    raise AssertionError("did not terminate")


class RecoveryTests(unittest.TestCase):
    def test_every_class_terminates_within_the_attempt_limit(self):
        for klass, reason in REASONS.items():
            actions, last = run_until_done(reason)
            self.assertLessEqual(actions.count("retry"), rc.DEFAULT_LIMITS["max_attempts"], klass)
            self.assertNotEqual(last["action"], "retry")
            self.assertFalse(last["auto_resume"], klass)

    def test_never_auto_retried(self):
        for klass in ("policy_denied", "auth", "quota"):
            actions, last = run_until_done(REASONS[klass])
            self.assertEqual(actions.count("retry"), 0, klass)
        self.assertEqual(run_until_done(REASONS["policy_denied"])[1]["action"], "stop")
        self.assertEqual(run_until_done(REASONS["auth"])[1]["action"], "operator")
        self.assertEqual(run_until_done(REASONS["quota"])[1]["action"], "pause")
        self.assertEqual(rc.decide("x", "SCOPE_VIOLATION", rc.FRESH)["action"], "stop")  # a provider status classifies too

    def test_429_style_quota_never_retries_even_with_budget_left(self):
        d = rc.decide("limit_exhausted", None, rc.FRESH, {"max_attempts": 5})
        self.assertEqual((d["action"], d["auto_resume"]), ("pause", False))
        self.assertEqual(rc.decide("token_budget_exceeded", None, rc.FRESH)["action"], "pause")

    def test_per_class_caps_open_the_breaker(self):
        actions, last = run_until_done("test_failed", lim={"max_attempts": 5})
        self.assertEqual((actions, last["why"]), (["retry", "retry", "pause"], "same_failure_class_keeps_failing_breaker_open"))
        self.assertEqual(run_until_done("timed_out", lim={"max_attempts": 5})[0], ["retry", "pause"])

    def test_delay_grows_and_mode_is_reported(self):
        first = rc.decide("worker_failed", None, rc.FRESH)
        second = rc.decide("worker_failed", None, {"attempts": 1, "by_class": {"infrastructure": 1}})
        self.assertEqual((first["delay_seconds"], second["delay_seconds"]), (0, 30))
        self.assertEqual(rc.decide("stale_project", None, rc.FRESH)["mode"], "new_patch")
        self.assertEqual(rc.decide("needs_changes", None, rc.FRESH)["mode"], "correction")

    def test_final_reviewer_rejection_is_a_person_decision(self):
        self.assertEqual(rc.decide("reviewer_reject", None, rc.FRESH)["action"], "operator")

    def test_unclassified_failure_is_operator_not_retry(self):
        for reason in (None, "", "something new", "WORKER_OK"):
            self.assertEqual(rc.decide(reason, None, rc.FRESH)["action"], "operator", reason)

    def test_resource_limits_come_first_and_fail_closed(self):
        base = dict(rc.FRESH)
        self.assertEqual(rc.decide("test_failed", None, {**base, "attempts": 3})["why"], "attempt_limit_reached")
        self.assertEqual(rc.decide("test_failed", None, {**base, "handoffs": 3})["why"], "handoff_limit_reached")
        self.assertEqual(rc.decide("test_failed", None, {**base, "elapsed_seconds": 3600})["why"], "time_limit_reached")
        self.assertEqual(rc.decide("test_failed", None, {**base, "spent_tokens": 100}, {"max_tokens": 100})["why"], "token_budget_exhausted")
        self.assertEqual(rc.decide("test_failed", None, {**base, "spent_tokens": None}, {"max_tokens": 100})["action"], "pause")
        self.assertEqual(rc.decide("scope_violation", None, {**base, "attempts": 3})["why"], "attempt_limit_reached")  # limit beats class
        self.assertEqual(rc.decide("test_failed", None, {**base, "spent_tokens": None})["action"], "retry")  # no token budget: unknown is not a stop

    def test_time_and_token_budget_bound_a_slow_expensive_loop(self):
        actions, last = run_until_done("worker_failed", lim={"max_attempts": 5, "max_seconds": 50}, per_try_seconds=30)
        self.assertEqual(last["why"], "time_limit_reached")
        actions, last = run_until_done("worker_failed", lim={"max_attempts": 5, "max_tokens": 15}, per_try_tokens=10)
        self.assertEqual(last["why"], "token_budget_exhausted")
        _, last = run_until_done("worker_failed", lim={"max_attempts": 5, "max_tokens": 15}, per_try_tokens=None)
        self.assertEqual(last["why"], "usage_unknown_under_token_budget")  # a try that reports no usage stops the loop

    def test_limits_are_validated_not_defaulted(self):
        for bad in ({"max_attempts": 0}, {"max_attempts": 6}, {"max_seconds": True}, {"max_handoffs": "3"}, {"surprise": 1}, {"max_tokens": 0}):
            with self.assertRaises(ValueError, msg=str(bad)):
                rc.decide("test_failed", None, rc.FRESH, bad)

    def test_remaining_is_reported_and_state_is_not_mutated(self):
        state = {**rc.FRESH, "by_class": {"test_failure": 1}}
        d = rc.decide("test_failed", None, state, {"max_tokens": 1000})
        self.assertEqual(d["remaining"], {"attempts": 3, "handoffs": 3, "seconds": 3600.0, "tokens": 1000})
        new = rc.advance(state, d, elapsed_seconds=5, spent_tokens=20)
        self.assertEqual((new["attempts"], new["by_class"], new["spent_tokens"], state["attempts"], state["by_class"]),
                         (1, {"test_failure": 2}, 20, 0, {"test_failure": 1}))
        self.assertEqual(rc.advance(state, d, spent_tokens=None)["spent_tokens"], None)
        stop = rc.advance(state, {"action": "stop"}, elapsed_seconds=1)
        self.assertEqual(stop["attempts"], 0)  # only a retry counts as an attempt

    def test_table_covers_every_engine_class(self):
        self.assertEqual({c.value for c in failures.FailureClass}, set(REASONS))


if __name__ == "__main__":
    unittest.main()
