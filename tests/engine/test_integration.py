"""SCH-03: deterministic, fail-closed integration of two verified worker results."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import evidence, integration, processes, runner
from respected_orchestrator.engine.runner import check_result, create_task, execute_task


class IntegrationFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in (("init", "-b", "main"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")):
            self.git(*args)
        (self.repo / "a.txt").write_text("base-a\n", encoding="utf8")
        (self.repo / "b.txt").write_text("base-b\n", encoding="utf8")
        self.git("add", ".")
        self.git("commit", "-m", "baseline")
        self.ctx = EngineContext(self.root / "data")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True).stdout

    def snapshot(self):
        head = self.git("rev-parse", "HEAD").decode("ascii").strip()
        return head, runner.project_fingerprint(self.repo)

    def write_task(self, name, content):
        code = f"from pathlib import Path; Path({name!r}).write_text({content!r}, encoding='utf8')"
        check = (f"from pathlib import Path; "
                 f"assert Path({name!r}).read_text(encoding='utf8') == {content!r}")
        return create_task(self.ctx, {
            "project_root": str(self.repo), "task": f"write {name}", "worker": "custom",
            "kind": "write", "ownership": [name], "command": [sys.executable, "-c", code],
            "acceptance": [[sys.executable, "-c", check]], "timeout_seconds": 30,
        })

    def delete_task(self, name):
        code = f"from pathlib import Path; Path({name!r}).unlink()"
        check = f"from pathlib import Path; assert not Path({name!r}).exists()"
        return create_task(self.ctx, {
            "project_root": str(self.repo), "task": f"delete {name}", "worker": "custom",
            "kind": "write", "ownership": [name], "command": [sys.executable, "-c", code],
            "acceptance": [[sys.executable, "-c", check]], "timeout_seconds": 30,
        })

    def run_task(self, task):
        result = execute_task(self.ctx, task["run_id"])
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(check_result(self.ctx, task["run_id"])["status"], "verified")
        return task["run_id"]

    def request(self, run_ids, *commands):
        return {
            "project_root": str(self.repo),
            "run_ids": run_ids,
            "verification": [
                {"command": [sys.executable, "-c", command], "timeout_seconds": 60}
                for command in commands
            ],
        }

    def assert_real_repo_unchanged(self, before):
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.git("status", "--porcelain=v1").decode("utf8"), "")

    def assert_no_integration_evidence(self):
        directory = self.ctx.state_dir / "integrations"
        self.assertEqual(list(directory.rglob("integration.json")) if directory.exists() else [], [])

    def assert_no_staging_worktree(self):
        directory = self.ctx.state_dir / "integrations"
        self.assertEqual(list(directory.rglob("worktree")) if directory.exists() else [], [])
        self.assertEqual(len(self.git("worktree", "list").decode("utf8").strip().splitlines()), 1)


class IntegrationScenarios(IntegrationFixture):
    def test_01_same_line_conflict_is_rejected_without_real_repo_change(self):
        first = self.run_task(self.write_task("a.txt", "first\n"))
        second = self.run_task(self.write_task("a.txt", "second\n"))
        before = self.snapshot()

        result = integration.integrate(
            self.ctx,
            self.request([first, second], "from pathlib import Path; assert Path('a.txt').read_text() == 'base-a\\n'"),
        )

        self.assertEqual(result["status"], "integration_conflict", result)
        self.assert_real_repo_unchanged(before)
        self.assert_no_integration_evidence()
        self.assert_no_staging_worktree()
        self.assertEqual((self.repo / "a.txt").read_text(encoding="utf8"), "base-a\n")
        self.assertEqual(list(self.ctx.state_dir.glob("run-*/applied.json")), [])

    def test_02_independent_patches_run_one_combined_verification_and_are_ready(self):
        first = self.run_task(self.write_task("a.txt", "first\n"))
        second = self.run_task(self.write_task("b.txt", "second\n"))
        before = self.snapshot()
        verification = (
            "from pathlib import Path; "
            "assert Path('a.txt').read_text() == 'first\\n'; "
            "assert Path('b.txt').read_text() == 'second\\n'"
        )

        with mock.patch.object(integration.processes, "execute",
                               wraps=processes.execute) as run_verification:
            result = integration.integrate(
                self.ctx, self.request([first, second], verification))

        self.assertEqual(result["status"], "ready_for_decision", result)
        self.assertEqual(result["verification_count"], 1)
        self.assertEqual(len(result["verification"]), 1)
        self.assertEqual(result["verification"][0]["returncode"], 0)
        self.assertEqual(run_verification.call_count, 1)
        self.assertEqual(result["changed_files"], ["a.txt", "b.txt"])
        self.assert_real_repo_unchanged(before)
        self.assert_no_staging_worktree()

        saved = evidence.load_signed(self.ctx, Path(result["evidence"]))
        self.assertEqual(saved["status"], "ready_for_decision")
        combined = Path(saved["combined_patch"])
        self.assertTrue(combined.is_file())
        self.assertIn(b"first", combined.read_bytes())
        self.assertIn(b"second", combined.read_bytes())
        subprocess.run(["git", "apply", "--check", "--binary", str(combined)],
                       cwd=self.repo, check=True)
        self.assertEqual(list(self.ctx.state_dir.glob("run-*/applied.json")), [])

    def test_03_head_drift_is_rejected_before_staging(self):
        first = self.run_task(self.write_task("a.txt", "first\n"))
        second = self.run_task(self.write_task("b.txt", "second\n"))
        (self.repo / "unrelated.txt").write_text("new head\n", encoding="utf8")
        self.git("add", "unrelated.txt")
        self.git("commit", "-m", "head moved")
        before = self.snapshot()

        result = integration.integrate(
            self.ctx, self.request([first, second], "raise SystemExit(0)"))

        self.assertEqual(result["status"], "head_drift", result)
        self.assert_real_repo_unchanged(before)
        self.assert_no_integration_evidence()
        self.assert_no_staging_worktree()

    def test_04_first_patch_applies_and_second_fails_without_partial_real_apply(self):
        first = self.run_task(self.delete_task("a.txt"))
        second = self.run_task(self.write_task("a.txt", "replacement\n"))
        before = self.snapshot()

        result = integration.integrate(
            self.ctx, self.request([first, second], "raise SystemExit(0)"))

        self.assertEqual(result["status"], "integration_conflict", result)
        self.assert_real_repo_unchanged(before)
        self.assertEqual((self.repo / "a.txt").read_text(encoding="utf8"), "base-a\n")
        self.assert_no_integration_evidence()
        self.assert_no_staging_worktree()
        self.assertEqual(list(self.ctx.state_dir.glob("run-*/applied.json")), [])

    def test_05_combined_verification_failure_publishes_no_decision_evidence(self):
        first = self.run_task(self.write_task("a.txt", "first\n"))
        second = self.run_task(self.write_task("b.txt", "second\n"))
        before = self.snapshot()

        block = "from pathlib import Path; assert Path('a.txt').read_text() == 'first\\n'"
        failure = "raise SystemExit(7)"
        with mock.patch.object(integration.processes, "execute",
                               wraps=processes.execute) as run_verification:
            result = integration.integrate(
                self.ctx, self.request([first, second], block, failure))

        self.assertEqual(result["status"], "verification_failed", result)
        self.assertEqual(run_verification.call_count, 2)
        self.assertEqual([item["returncode"] for item in result.get("verification", [])], [0, 7])
        self.assert_real_repo_unchanged(before)
        self.assert_no_integration_evidence()
        self.assert_no_staging_worktree()
        self.assertEqual((self.repo / "a.txt").read_text(encoding="utf8"), "base-a\n")
        self.assertEqual((self.repo / "b.txt").read_text(encoding="utf8"), "base-b\n")


if __name__ == "__main__":
    unittest.main()
