"""ADR-005 failure taxonomy is closed and retry policy is explicit."""
import unittest

from respected_orchestrator.engine import failures


class FailureTaxonomyTests(unittest.TestCase):
    def test_every_class_has_one_policy(self):
        self.assertEqual(len(failures.FailureClass), 8)
        self.assertEqual(set(failures.POLICIES), set(failures.FailureClass))

    def test_reasons_map_to_classes_and_policies(self):
        expected = {
            "test_failed": ("test_failure", True),
            "scope_violation": ("policy_denied", False),
            "timed_out": ("timeout", True),
            "token_budget_exceeded": ("quota", False),
            "auth_required": ("auth", False),
            "worker_failed": ("infrastructure", True),
            "stale_project": ("stale_patch", False),
            "needs_changes": ("reviewer_reject", True),
            "reviewer_reject": ("reviewer_reject", False),
        }
        for reason, (name, retryable) in expected.items():
            fields = failures.describe(reason)
            self.assertEqual(fields["failure_class"], name, reason)
            self.assertEqual(fields["retryable"], retryable, reason)

    def test_provider_status_wins_over_generic_worker_failure(self):
        self.assertEqual(failures.describe("worker_failed", "LIMIT_EXHAUSTED")["failure_class"], "quota")
        self.assertEqual(failures.describe("worker_failed", "AUTH_REQUIRED")["failure_class"], "auth")

    def test_unknown_reason_adds_no_fields(self):
        self.assertEqual(failures.describe("not-a-class"), {})


if __name__ == "__main__":
    unittest.main()
