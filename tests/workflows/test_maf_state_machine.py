import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.evidence import load_signed
from respected_orchestrator.engine.runner import cancel_task, create_task, inspect_task
from respected_orchestrator.workflows.maf_workflow import run_maf_coding_task


class MafStateMachineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in (("init", "-b", "main"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")):
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        (self.repo / "calculator.py").write_text("value = 0\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "fixture baseline"], cwd=self.repo,
                       capture_output=True, check=True)
        self.ctx = EngineContext(self.root / "data")

    def request(self, **workflow) -> dict[str, object]:
        request = {
            "project_root": str(self.repo),
            "task": "fixture coding task",
            "worker": "custom",
            "kind": "write",
            "ownership": ["calculator.py"],
            "forbidden": ["outside.txt"],
            "command": [sys.executable, "-c", "print('fixture worker')"],
            "acceptance": [[sys.executable, "-c", "assert True"]],
            "timeout_seconds": 10,
        }
        if workflow:
            request["workflow"] = workflow
        return request

    def create_run(self, **workflow) -> str:
        run_id = create_task(self.ctx, self.request(**workflow))["run_id"]
        (self.ctx.run_dir(run_id) / "worker.patch").write_text("+value = 1\n", encoding="utf8")
        return run_id

    @staticmethod
    def completed(run_id: str) -> dict[str, object]:
        return {
            "run_id": run_id,
            "status": "completed",
            "changed_files": ["calculator.py"],
            "checks": [{"command": ["python", "-m", "unittest"], "returncode": 0}],
            "patch_sha256": "a" * 64,
            "workspace": f"workspace-{run_id}",
            "duration_seconds": 0.1,
        }

    @staticmethod
    def failed_result(run_id: str) -> dict[str, object]:
        return {
            "run_id": run_id,
            "status": "failed",
            "reason": "test_failed",
            "changed_files": ["calculator.py"],
            "checks": [{"command": ["python", "-m", "unittest"], "returncode": 1}],
            "error": "RAW-SECRET-STDERR",
            "stdout": "RAW-SECRET-STDOUT",
            "duration_seconds": 0.1,
        }

    def test_a_test_failure_is_fixed_from_sanitized_evidence_and_approved(self) -> None:
        run_id = self.create_run(max_fix_rounds=2)
        reviewer = mock.Mock(return_value={"decision": "APPROVED"})
        outcomes = iter([self.failed_result(run_id), self.completed(run_id)])

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        side_effect=lambda ctx, current: next(outcomes)):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["state"], "MASTER_APPROVED")
        self.assertEqual(output["reason"], "approved")
        self.assertEqual(len(output["attempts"]), 2)
        self.assertEqual(output["fix_rounds"], {"limit": 2, "used": 1, "remaining": 1})
        self.assertEqual(reviewer.call_count, 1)
        child_request = inspect_task(self.ctx, output["final_run_id"])["request"]
        evidence = child_request["fix_evidence"]
        self.assertEqual(set(evidence), {"run_id", "checks", "reason", "failure_class", "evidence_paths"})
        self.assertEqual(evidence["run_id"], run_id)
        self.assertEqual(evidence["failure_class"], "test_failure")
        self.assertTrue(evidence["evidence_paths"])
        serialized = json.dumps(evidence, sort_keys=True) + child_request["task"]
        self.assertNotIn("RAW-SECRET", serialized)
        self.assertNotIn("stdout", serialized.casefold())
        self.assertNotIn("stderr", serialized.casefold())
        self.assertIsNone(child_request["inherited_patch_run_id"])
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")
        saved = load_signed(self.ctx, self.ctx.run_dir(output["final_run_id"]) / "maf-result.json")
        for field in ("state", "reason", "fix_rounds", "transitions", "evidence",
                      "failure_class", "retryable"):
            self.assertIn(field, saved)
        self.assertEqual(saved["state"], "MASTER_APPROVED")
        self.assertEqual(saved["transitions"][-1]["to"], "MASTER_APPROVED")

    def test_the_same_normalized_test_failure_stops_before_the_reviewer(self) -> None:
        run_id = self.create_run(max_fix_rounds=3)
        reviewer = mock.Mock(return_value={"decision": "APPROVED"})
        outcomes = iter([self.failed_result(run_id), self.failed_result(run_id)])

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        side_effect=lambda ctx, current: next(outcomes)):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["state"], "REPEATED_TEST_FAILURE")
        self.assertEqual(output["reason"], "repeated_test_failure")
        self.assertEqual(output["failure_class"], "test_failure")
        self.assertFalse(output["retryable"])
        self.assertEqual(len(output["attempts"]), 2)
        self.assertEqual(output["fix_rounds"], {"limit": 3, "used": 1, "remaining": 2})
        reviewer.assert_not_called()
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")

    def test_a_reviewer_rejection_is_terminal_and_never_fixed(self) -> None:
        run_id = self.create_run(max_fix_rounds=2)
        reviewer = mock.Mock(return_value={"decision": "REJECTED", "reason": "unsafe"})
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        return_value=self.completed(run_id)):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["state"], "REJECTED")
        self.assertEqual(output["reason"], "reviewer_reject")
        self.assertEqual(output["failure_class"], "reviewer_reject")
        self.assertFalse(output["retryable"])
        self.assertEqual(len(output["attempts"]), 1)
        self.assertEqual(output["fix_rounds"]["used"], 0)

    def test_cancellation_before_a_fix_is_reported_without_starting_it(self) -> None:
        run_id = self.create_run(max_fix_rounds=2)
        reviewer = mock.Mock(return_value={"decision": "APPROVED"})

        def cancelled_failure(ctx, current):
            cancel_task(ctx, current)
            return self.failed_result(current)

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        side_effect=cancelled_failure):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["state"], "CANCELLED")
        self.assertEqual(output["reason"], "cancellation_requested")
        self.assertFalse(output["retryable"])
        self.assertEqual(len(output["attempts"]), 1)
        self.assertEqual(output["fix_rounds"]["used"], 0)
        reviewer.assert_not_called()

    def test_fix_rounds_are_bounded_and_a_review_correction_inherits_verified_patch(self) -> None:
        run_id = self.create_run(max_fix_rounds=1)
        reviewer = mock.Mock(return_value={
            "decision": "NEEDS_CHANGES", "corrections": {"coding": "address the finding"}})

        def completed(ctx, current):
            return self.completed(current)

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", side_effect=completed):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["state"], "FIX_ROUNDS_EXHAUSTED")
        self.assertEqual(output["reason"], "fix_rounds_exhausted")
        self.assertEqual(output["fix_rounds"], {"limit": 1, "used": 1, "remaining": 0})
        self.assertEqual(len(output["attempts"]), 2)
        self.assertEqual(reviewer.call_count, 2)
        child_request = inspect_task(self.ctx, output["final_run_id"])["request"]
        self.assertEqual(child_request["inherited_patch_run_id"], run_id)
        self.assertEqual(child_request["inherited_patch_sha256"], "a" * 64)
        self.assertEqual(child_request["fix_evidence"]["failure_class"], "reviewer_reject")
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")

    def test_a_stale_project_blocks_the_fix_before_it_starts(self) -> None:
        run_id = self.create_run(max_fix_rounds=2)
        reviewer = mock.Mock(return_value={"decision": "APPROVED"})

        def stale_failure(ctx, current):
            (self.repo / "unrelated.txt").write_text("changed meanwhile\n", encoding="utf8")
            return self.failed_result(current)

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        side_effect=stale_failure):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["state"], "STALE_PATCH")
        self.assertEqual(output["failure_class"], "stale_patch")
        self.assertFalse(output["retryable"])
        self.assertEqual(len(output["attempts"]), 1)
        self.assertEqual(output["fix_rounds"]["used"], 0)
        reviewer.assert_not_called()
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")

    def test_max_fix_rounds_is_canonical_and_bounded(self) -> None:
        default = create_task(self.ctx, self.request())["run_id"]
        self.assertEqual(inspect_task(self.ctx, default)["request"]["workflow"]["max_fix_rounds"], 2)
        maximum = create_task(self.ctx, self.request(max_fix_rounds=5))["run_id"]
        self.assertEqual(inspect_task(self.ctx, maximum)["request"]["workflow"]["max_fix_rounds"], 5)
        with self.assertRaisesRegex(ValueError, "max_fix_rounds"):
            create_task(self.ctx, self.request(max_fix_rounds=6))
        with self.assertRaisesRegex(ValueError, "max_fix_rounds"):
            create_task(self.ctx, self.request(max_corrections=0))
