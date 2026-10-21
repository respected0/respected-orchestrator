import threading
import time
import unittest

from agent_framework import InMemoryCheckpointStorage

from respected_orchestrator.workflows.maf_workflow import run_maf_slice


class MafWorkflowTest(unittest.TestCase):
    def test_two_fake_workers_execute_concurrently(self) -> None:
        lock = threading.Lock()
        active = 0
        peak = 0

        def worker(correction: str = "") -> dict[str, object]:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.15)
            with lock:
                active -= 1
            return {"status": "COMPLETE", "evidence": "done"}

        result = run_maf_slice(
            goal="demo",
            workers={"fast": worker, "complex": worker},
            reviewer=lambda results: {"decision": "APPROVED"},
        )

        self.assertEqual(result["status"], "MASTER_APPROVED")
        self.assertEqual(peak, 2)

    def test_master_review_can_request_one_bounded_correction(self) -> None:
        calls: list[tuple[str, str]] = []

        def fast(correction: str = "") -> dict[str, object]:
            calls.append(("fast", correction))
            return {"status": "COMPLETE", "evidence": "fast"}

        def complex_worker(correction: str = "") -> dict[str, object]:
            calls.append(("complex", correction))
            return {"status": "COMPLETE", "evidence": "complex"}

        def reviewer(results) -> dict[str, object]:
            if any(correction for _, correction in calls):
                return {"decision": "APPROVED"}
            return {
                "decision": "NEEDS_CHANGES",
                "corrections": {"fast": "fix it"},
            }

        result = run_maf_slice(
            goal="demo",
            workers={"fast": fast, "complex": complex_worker},
            reviewer=reviewer,
            max_corrections=1,
        )

        self.assertEqual(result["status"], "MASTER_APPROVED")
        self.assertEqual(calls.count(("fast", "")), 1)
        self.assertEqual(calls.count(("fast", "fix it")), 1)
        self.assertEqual(calls.count(("complex", "")), 1)
        self.assertEqual(result["corrections"], {"fast": "fix it"})

    def test_worker_failure_fails_closed(self) -> None:
        def worker(correction: str = "") -> dict[str, object]:
            return {"status": "FAILED", "evidence": "boom"}

        def reviewer(results) -> dict[str, object]:
            raise AssertionError("reviewer must not run after worker failure")

        result = run_maf_slice(
            goal="demo",
            workers={"fast": worker, "complex": worker},
            reviewer=reviewer,
        )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["reason"], "worker_failed")

    def test_rejection_is_not_treated_as_failure_or_approval(self) -> None:
        result = run_maf_slice(
            goal="demo",
            workers={"fast": lambda correction="": {"status": "COMPLETE"}},
            reviewer=lambda results: {"decision": "REJECTED", "reason": "unsafe change"},
        )

        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["review_decisions"], ["REJECTED"])

    def test_invalid_reviewer_output_fails_closed(self) -> None:
        result = run_maf_slice(
            goal="demo",
            workers={"fast": lambda correction="": {"status": "COMPLETE"}},
            reviewer=lambda results: {"decision": "SHIP_IT"},
        )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["reason"], "invalid_review_result")

    def test_reviewer_execution_failure_is_distinct_from_invalid_output(self) -> None:
        def reviewer(results):
            raise RuntimeError("provider unavailable")

        result = run_maf_slice(
            goal="demo",
            workers={"fast": lambda correction="": {"status": "COMPLETE"}},
            reviewer=reviewer,
        )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["reason"], "reviewer_execution_failed")

    def test_needs_changes_without_correction_payload_is_invalid(self) -> None:
        result = run_maf_slice(
            goal="demo",
            workers={"fast": lambda correction="": {"status": "COMPLETE"}},
            reviewer=lambda results: {"decision": "NEEDS_CHANGES"},
        )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["reason"], "invalid_review_result")

    def test_checkpoint_recovery_restores_completed_worker_steps(self) -> None:
        storage = InMemoryCheckpointStorage()
        calls: list[str] = []

        def worker(correction: str = "") -> dict[str, object]:
            calls.append(correction)
            return {"status": "COMPLETE", "evidence": "done"}

        workers = {"fast": worker, "complex": worker}

        def reviewer(results) -> dict[str, object]:
            return {"decision": "APPROVED"}

        first = run_maf_slice(
            goal="demo",
            workers=workers,
            reviewer=reviewer,
            checkpoint_storage=storage,
        )
        self.assertEqual(len(calls), 2)

        second = run_maf_slice(
            goal="demo",
            workers=workers,
            reviewer=reviewer,
            checkpoint_storage=storage,
            resume_checkpoint_id=first["checkpoint_id"],
        )

        self.assertEqual(second["status"], first["status"])
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
