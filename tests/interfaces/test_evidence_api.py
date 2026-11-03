"""UX-02: RPP and CLI expose the same read-only evidence view; failures stay structured."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from respected_orchestrator.__main__ import main
from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.runner import project_fingerprint
from respected_orchestrator.interfaces import rpp


class EvidenceApiTests(unittest.TestCase):
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
        directory = self.ctx.run_dir("run-api")
        directory.mkdir(parents=True)
        fingerprint = project_fingerprint(self.repo)
        save_signed(self.ctx, directory / "request.json", {
            "run_id": "run-api", "project_root": str(self.repo), "project_fingerprint": fingerprint,
            "role_assignments": {"reviewer": {"tool": "codex", "profile": "reviewer"}},
        })
        save_signed(self.ctx, directory / "status.json", {"run_id": "run-api", "status": "completed"})
        patch = b"fixture patch\n"
        (directory / "worker.patch").write_bytes(patch)
        save_signed(self.ctx, directory / "result.json", {
            "run_id": "run-api", "status": "completed", "project_fingerprint": fingerprint,
            "patch_sha256": hashlib.sha256(patch).hexdigest(), "changed_files": ["owned.txt"],
            "checks": [{"command": ["test"], "returncode": 0}],
        })

    def request(self, op, payload):
        return rpp.handle_request({"rpp": rpp.RPP, "op": op, "payload": payload}, self.ctx)

    def test_rpp_and_cli_return_the_same_view_without_changing_evidence(self):
        directory = self.ctx.run_dir("run-api")
        before = {name: (directory / name).read_bytes() for name in ("request.json", "status.json", "result.json")}
        response = self.request("evidence.view", {"run_id": "run-api"})
        self.assertTrue(response["ok"], response)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--data-root", str(self.ctx.data_root), "evidence", "run-api"]), 0)
        self.assertEqual(json.loads(out.getvalue()), response["result"])
        self.assertEqual(before, {name: (directory / name).read_bytes() for name in before})

    def test_missing_task_is_structured(self):
        response = self.request("evidence.view", {"run_id": "run-missing"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "EVIDENCE_UNAVAILABLE")

    def test_traversal_is_denied(self):
        response = self.request("evidence.view", {"run_id": "../run-api"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "BAD_REQUEST")

    def test_tampered_or_locked_evidence_is_unavailable(self):
        path = self.ctx.run_dir("run-api") / "status.json"
        envelope = json.loads(path.read_text())
        envelope["payload"]["status"] = "failed"
        path.write_text(json.dumps(envelope), encoding="utf8")
        response = self.request("evidence.view", {"run_id": "run-api"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "EVIDENCE_UNAVAILABLE")

    def test_schema_mismatch_is_rejected(self):
        response = rpp.handle_request({"rpp": "9.9", "op": "evidence.view", "payload": {"run_id": "run-api"}}, self.ctx)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "UNSUPPORTED_VERSION")


if __name__ == "__main__":
    unittest.main()