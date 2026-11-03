"""UX-03: the Decision Center cannot widen the human approval boundary."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import runner
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.runner import approve_maf_task


class HumanApprovalContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = EngineContext(Path(self.temp.name).resolve() / "data")
        self.run_id = "run-approval"
        self.directory = self.ctx.run_dir(self.run_id)
        self.directory.mkdir(parents=True)
        self.patch = self.directory / "worker.patch"
        self.patch.write_bytes(b"diff --git a/owned.txt b/owned.txt\n")
        save_signed(self.ctx, self.directory / "request.json", {"run_id": self.run_id})
        save_signed(self.ctx, self.directory / "status.json", {"run_id": self.run_id, "status": "completed"})
        result = {"run_id": self.run_id, "status": "completed",
                  "patch_sha256": hashlib.sha256(self.patch.read_bytes()).hexdigest()}
        save_signed(self.ctx, self.directory / "result.json", result)
        save_signed(self.ctx, self.directory / "maf-result.json",
                    {"root_run_id": self.run_id, "status": "HUMAN_APPROVAL_REQUIRED"})

    def approve(self, tty=True):
        with mock.patch.object(runner, "_stdin_is_tty", return_value=tty):
            return approve_maf_task(self.ctx, self.run_id)

    def test_agent_or_mcp_cannot_self_approve(self):
        with mock.patch.dict(os.environ, {"RESPECTED_ORCH_CHILD": "1"}), \
                self.assertRaisesRegex(ValueError, "operator"):
            self.approve()

    def test_approval_requires_an_interactive_human_terminal(self):
        with self.assertRaisesRegex(ValueError, "interactive terminal"):
            self.approve(tty=False)
        self.assertFalse((self.directory / "maf-approval.json").exists())

    def test_confirmed_approval_is_recorded_and_bound_to_the_patch(self):
        approval = self.approve()
        self.assertEqual(approval["patch_sha256"], hashlib.sha256(self.patch.read_bytes()).hexdigest())
        self.assertTrue(approval["approved_by"])
        self.assertTrue((self.directory / "maf-approval.json").is_file())

    def test_replayed_approval_is_rejected(self):
        self.approve()
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.approve()

    def test_screen_drift_after_patch_change_is_rejected(self):
        self.patch.write_bytes(b"changed after review\n")
        with self.assertRaisesRegex(ValueError, "intact"):
            self.approve()

    def test_cancel_or_interrupt_leaves_no_approval(self):
        with mock.patch.object(runner, "save_signed", side_effect=KeyboardInterrupt), \
                self.assertRaises(KeyboardInterrupt):
            self.approve()
        self.assertFalse((self.directory / "maf-approval.json").exists())

    def test_outdated_result_is_rejected(self):
        result = {"run_id": self.run_id, "status": "failed",
                  "patch_sha256": hashlib.sha256(self.patch.read_bytes()).hexdigest()}
        save_signed(self.ctx, self.directory / "result.json", result)
        with self.assertRaisesRegex(ValueError, "intact"):
            self.approve()


if __name__ == "__main__":
    unittest.main()