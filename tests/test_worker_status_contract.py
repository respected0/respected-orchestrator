import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from respected_orchestrator.engine import lanes


class WorkerStatusContractTest(unittest.TestCase):
    def test_default_and_custom_templates_enforce_status_contract(self):
        for custom in (False, True):
            with self.subTest(custom=custom):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)

                    if custom:
                        template_dir = root / ".orchestration" / "templates"
                        template_dir.mkdir(parents=True)
                        (template_dir / "write-worker.md").write_text(
                            "Custom template: {{OBJECTIVE}}",
                            encoding="utf-8",
                        )

                    request = SimpleNamespace(
                        kind=lanes.TaskKind.WRITE,
                        objective="Update smoke.txt",
                        known_context="",
                        ownership=("smoke.txt",),
                        forbidden=(),
                        acceptance=(),
                    )
                    lane = SimpleNamespace(repo_root=root, worktree=root)

                    brief = lanes.render_brief(request, lane)

                    self.assertIn("MACHINE-READABLE STATUS CONTRACT", brief)
                    self.assertIn('"status": "success"', brief)
                    self.assertIn('"status": "failed"', brief)
                    self.assertIn("never the apply_patch tool", brief)
                    self.assertIn("immediately emit the final JSON", brief)