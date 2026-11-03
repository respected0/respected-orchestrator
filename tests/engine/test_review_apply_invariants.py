"""QUA-04: adversarial review/apply invariants and one legitimate check -> apply flow.

Every adversarial test proves both halves of the contract: the operation is rejected
and no applied marker or project mutation is produced as a side effect.
"""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from respected_orchestrator.engine import lanes, runner
from respected_orchestrator.engine.evidence import load_signed, save_signed
from respected_orchestrator.engine.runner import apply_task, check_result, create_task, execute_task
from respected_orchestrator.workflows import roles
from respected_orchestrator.workflows.maf_workflow import run_maf_coding_task
from tests.workflows.test_reviewer_reliability import CodingFixture


class RejectedReviewApplyInvariantTests(CodingFixture):
    """Twelve independent rejection cases: 12/12 rejected, zero automatic apply."""

    def executed(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        result = execute_task(self.ctx, run_id)
        self.assertEqual(result["status"], "completed", result)
        return run_id

    def assert_no_apply(self, run_id=None, expected="value = 0\n"):
        if run_id is not None:
            self.assertFalse((self.ctx.run_dir(run_id) / "applied.json").exists())
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), expected)

    def test_01_same_reviewer_profile_is_rejected_when_independence_is_required(self):
        request = self.request(reviewer_profile="shared-model", require_independent_review=True)
        request["worker_profile"] = "shared-model"
        with self.assertRaises(roles.RoleError) as caught:
            create_task(self.ctx, request)
        self.assertEqual(caught.exception.code, "ROLE_INDEPENDENCE")
        self.assertEqual(list(self.ctx.state_dir.glob("run-*")), [])
        self.assert_no_apply()

    def test_02_forged_evidence_signature_is_rejected(self):
        run_id = self.executed()
        path = self.ctx.run_dir(run_id) / "result.json"
        envelope = json.loads(path.read_text(encoding="utf8"))
        envelope["payload"]["changed_files"] = ["attacker-controlled.txt"]
        envelope["signature"] = "0" * 64
        path.write_text(json.dumps(envelope), encoding="utf8")
        with self.assertRaisesRegex(ValueError, "tampered"):
            check_result(self.ctx, run_id)
        with self.assertRaisesRegex(ValueError, "tampered"):
            apply_task(self.ctx, run_id)
        self.assert_no_apply(run_id)

    def test_03_changed_head_makes_the_result_stale(self):
        run_id = self.executed()
        (self.repo / "unrelated.txt").write_text("head moved\n", encoding="utf8")
        subprocess.run(["git", "add", "unrelated.txt"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "head moved"], cwd=self.repo, check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "stale"):
            check_result(self.ctx, run_id)
        with self.assertRaisesRegex(ValueError, "stale"):
            apply_task(self.ctx, run_id)
        self.assert_no_apply(run_id)

    def test_04_apply_race_after_precheck_writes_nothing(self):
        run_id = self.executed()
        real_git = lanes._git

        def raced_git(project, *args, **kwargs):
            result = real_git(project, *args, **kwargs)
            if args[:2] == ("apply", "--check"):
                (self.repo / "calculator.py").write_text("raced source\n", encoding="utf8")
            return result

        with mock.patch.object(lanes, "_git", side_effect=raced_git):
            with self.assertRaises((lanes.LaneError, subprocess.CalledProcessError)):
                apply_task(self.ctx, run_id)
        self.assert_no_apply(run_id, expected="raced source\n")

    def test_05_token_retry_limit_stops_before_another_paid_review(self):
        run_id = create_task(self.ctx, self.request(max_weighted_tokens=1000, max_fix_rounds=2))["run_id"]
        completed = {
            "run_id": run_id,
            "status": "completed",
            "changed_files": ["calculator.py"],
            "patch_sha256": "0" * 64,
            "checks": [{"command": ["fixture"], "returncode": 0}],
            "workspace": str(self.root),
            "duration_seconds": 0.1,
            "usage": {"estimated_weighted_tokens": 1100},
        }
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", return_value=completed), \
             mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call") as paid_review:
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id)
        self.assertEqual((output["status"], output["reason"]), ("FAILED", "token_budget_exceeded"))
        paid_review.assert_not_called()
        self.assert_no_apply(run_id)

    def test_06_human_approval_required_flow_is_rejected_without_approval(self):
        run_id = self.executed()
        result = load_signed(self.ctx, self.ctx.run_dir(run_id) / "result.json")
        save_signed(self.ctx, self.ctx.run_dir(run_id) / "maf-result.json",
                    {"root_run_id": run_id, "status": "HUMAN_APPROVAL_REQUIRED",
                     "patch_sha256": result["patch_sha256"]})
        with self.assertRaisesRegex(ValueError, "MAF approval"):
            check_result(self.ctx, run_id)
        with self.assertRaisesRegex(ValueError, "MAF approval"):
            apply_task(self.ctx, run_id)
        self.assert_no_apply(run_id)

    def test_07_patch_sha_mismatch_is_rejected(self):
        run_id = self.executed()
        patch = self.ctx.run_dir(run_id) / "worker.patch"
        patch.write_bytes(patch.read_bytes() + b"tampered patch bytes\n")
        with self.assertRaisesRegex(ValueError, "Patch tampered"):
            check_result(self.ctx, run_id)
        with self.assertRaisesRegex(ValueError, "Patch tampered"):
            apply_task(self.ctx, run_id)
        self.assert_no_apply(run_id)

    def test_08_approval_bound_to_a_different_patch_is_rejected(self):
        run_id = self.executed()
        save_signed(self.ctx, self.ctx.run_dir(run_id) / "maf-result.json",
                    {"root_run_id": run_id, "status": "HUMAN_APPROVAL_REQUIRED",
                     "patch_sha256": "0" * 64})
        save_signed(self.ctx, self.ctx.run_dir(run_id) / "maf-approval.json",
                    {"run_id": run_id, "root_run_id": run_id, "patch_sha256": "f" * 64,
                     "approved_by": "fixture", "approved_at": "2026-11-01T00:00:00+00:00"})
        with self.assertRaisesRegex(ValueError, "not bound"):
            check_result(self.ctx, run_id)
        with self.assertRaisesRegex(ValueError, "not bound"):
            apply_task(self.ctx, run_id)
        self.assert_no_apply(run_id)

    def test_09_second_apply_is_rejected(self):
        run_id = self.executed()
        self.assertEqual(apply_task(self.ctx, run_id)["status"], "applied")
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 1\n")
        with self.assertRaisesRegex(ValueError, "already applied"):
            apply_task(self.ctx, run_id)
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 1\n")

    def test_10_reviewer_cannot_be_the_implementer(self):
        request = self.request(require_independent_review=True)
        request["roles"] = {
            "implementer": {"tool": "custom", "profile": "same-model"},
            "reviewer": {"tool": "custom", "profile": "same-model"},
        }
        with self.assertRaises(roles.RoleError) as caught:
            create_task(self.ctx, request)
        self.assertEqual(caught.exception.code, "ROLE_INDEPENDENCE")
        self.assertEqual(list(self.ctx.state_dir.glob("run-*")), [])
        self.assert_no_apply()

    def test_11_tester_is_report_only_and_cannot_supply_commands(self):
        marker = self.root / "tester-command-ran.txt"
        request = self.request()
        request["roles"] = {"tester": {"tool": "custom", "profile": "qa", "command": [
            sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"
        ]}}
        with self.assertRaises(roles.RoleError) as caught:
            create_task(self.ctx, request)
        self.assertEqual(caught.exception.code, "BAD_ASSIGNMENT")
        self.assertFalse(marker.exists())
        self.assertEqual(list(self.ctx.state_dir.glob("run-*")), [])
        self.assert_no_apply()

    def test_12_apply_before_check_or_execution_is_rejected(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        with self.assertRaisesRegex(ValueError, "Unsuccessful or pending"):
            apply_task(self.ctx, run_id)
        self.assert_no_apply(run_id)


class LegitimateReviewApplyTests(CodingFixture):
    """The existing green path survives: one verified patch applies exactly once."""

    def test_verified_check_then_apply_succeeds_once(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        self.assertEqual(execute_task(self.ctx, run_id)["status"], "completed")
        verified = check_result(self.ctx, run_id)
        self.assertEqual(verified["status"], "verified")
        applied = apply_task(self.ctx, run_id)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 1\n")
        marker = load_signed(self.ctx, self.ctx.run_dir(run_id) / "applied.json")
        self.assertEqual(marker["patch_sha256"], load_signed(self.ctx, self.ctx.run_dir(run_id) / "result.json")["patch_sha256"])


if __name__ == "__main__":
    unittest.main()
