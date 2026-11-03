"""Redacted evidence view fixtures: valid, stale, failed, tampered, missing signature, secret env."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.runner import project_fingerprint
from respected_orchestrator.interfaces.evidence_view import view


class EvidenceViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in (("init", "-b", "main"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")):
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        (self.repo / "owned.txt").write_text("base\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=self.repo, capture_output=True, check=True)
        self.ctx = EngineContext(self.root / "data")

    def fixture(self, run_id="run-valid", status="completed", result=True, reason=None):
        directory = self.ctx.run_dir(run_id)
        directory.mkdir(parents=True)
        fingerprint = project_fingerprint(self.repo)
        save_signed(self.ctx, directory / "request.json", {
            "run_id": run_id, "project_root": str(self.repo), "project_fingerprint": fingerprint,
            "role_assignments": {"reviewer": {"tool": "codex", "profile": "reviewer"}},
        })
        payload = {"run_id": run_id, "status": status}
        if reason:
            payload["reason"] = reason
        save_signed(self.ctx, directory / "status.json", payload)
        if result:
            patch = directory / "worker.patch"
            patch.write_bytes(b"fixture patch\n")
            save_signed(self.ctx, directory / "result.json", {
                "run_id": run_id, "status": "completed", "project_fingerprint": fingerprint,
                "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
                "changed_files": ["owned.txt"], "checks": [{"command": ["test"], "returncode": 0}],
                "tester": {"status": "passed", "commands": [{"command": ["test"], "returncode": 0}]},
                "remaining_risks": ["password=topsecretvalue"],
            })
        return directory

    def test_valid_stale_failed_and_tampered(self):
        valid = self.fixture()
        before = ((valid / "status.json").read_bytes(), (valid / "result.json").read_bytes())
        shown = view(self.ctx, "run-valid")
        self.assertEqual((shown["status"], shown["reason"]), ("completed", "completed"))
        self.assertEqual(shown["patch_summary"]["changed_files"], ["owned.txt"])
        self.assertEqual(shown["reviewer"]["tool"], "codex")
        self.assertFalse(shown["cost"]["known"])
        self.assertEqual(shown["cost"]["estimated"], "bilinmiyor")
        self.assertEqual(before, ((valid / "status.json").read_bytes(), (valid / "result.json").read_bytes()))

        (self.repo / "untracked.txt").write_text("changed\n", encoding="utf8")
        self.assertEqual(view(self.ctx, "run-valid")["status"], "stale")

        self.fixture("run-failed", status="failed", result=False, reason="worker_failed")
        self.assertEqual((view(self.ctx, "run-failed")["status"], view(self.ctx, "run-failed")["reason"]),
                         ("failed", "worker_failed"))

        tampered = self.fixture("run-tampered")
        envelope = json.loads((tampered / "status.json").read_text())
        envelope["payload"]["status"] = "completed"
        envelope["signature"] = "0" * 64
        (tampered / "status.json").write_text(json.dumps(envelope), encoding="utf8")
        with self.assertRaisesRegex(ValueError, "tampered"):
            view(self.ctx, "run-tampered")

        missing = self.fixture("run-missing")
        payload = json.loads((missing / "status.json").read_text())["payload"]
        (missing / "status.json").write_text(json.dumps({"payload": payload}), encoding="utf8")
        with self.assertRaises(ValueError):
            view(self.ctx, "run-missing")

    def test_env_secret_is_redacted(self):
        directory = self.fixture("run-secret")
        secret = "sk-live-very-secret-value"
        status = json.loads((directory / "status.json").read_text())
        status["payload"]["detail"] = f"API_KEY={secret}"
        with mock.patch.dict(os.environ, {"RESPECTED_TEST_API_TOKEN": secret}):
            save_signed(self.ctx, directory / "status.json", status["payload"])
            shown = view(self.ctx, "run-secret")
        rendered = json.dumps(shown)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("topsecretvalue", rendered)
        self.assertIn("[REDACTED]", rendered)


if __name__ == "__main__":
    unittest.main()