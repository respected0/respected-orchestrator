import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import runner
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.workflows import operator as op

HUMAN = Origin.HUMAN


def code_of(fn, *a, **k):
    try:
        fn(*a, **k)
    except op.OperatorError as error:
        return error.code


class OperatorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "F"), ("config", "user.email", "f@example.invalid")]:
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        (self.repo / "owned.txt").write_text("base\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.repo, capture_output=True, check=True)
        self.ctx = EngineContext(self.root / "data")
        for target in ("sync_credentials", "clear_worker_home"):
            p = mock.patch.object(runner.opencode_auth, target)
            p.start()
            self.addCleanup(p.stop)
        for name, value in (("tool_available", True), ("get_cli_command", "x.exe")):
            p = mock.patch.object(runner, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def new_run(self):
        return runner.create_task(self.ctx, dict(project_root=str(self.repo), task="t", kind="write", ownership=["owned.txt"],
                                                 acceptance=[[sys.executable, "-c", "pass"]], timeout_seconds=10), settings={})["run_id"]

    def fail(self, run_id, reason, provider=None):
        save_signed(self.ctx, self.ctx.run_dir(run_id) / "status.json",
                    {"run_id": run_id, "status": "failed", "reason": reason, "updated_at": f"2026-11-08T00:00:0{len(reason) % 9}+00:00",
                     **({"provider_status": provider} if provider else {}), **runner.failures.describe(reason, provider)})

    def case(self, run_id, **kw):
        return op.case(self.ctx, run_id, inspect_run=runner.inspect_task, **kw)

    def act(self, run_id, action, binding, origin=HUMAN, **kw):
        return op.act(self.ctx, run_id, action, binding, origin=origin, inspect_run=runner.inspect_task, retry=runner.retry_task, **kw)

    def test_case_explains_the_problem_the_step_the_budget_and_the_choices(self):
        run = self.new_run()
        self.fail(run, "test_failed")
        card = self.case(run)
        self.assertEqual((card["problem"]["class"], card["actions"], card["automatic"]["action"]), ("test_failure", ["retry", "dismiss"], "retry"))
        self.assertIn("acceptance checks", card["problem"]["plain"])
        self.assertEqual(card["remaining"]["attempts"], 2)
        self.assertIn("apply a patch", card["never"])
        self.assertNotIn("apply", card["actions"])

    def test_only_a_terminal_failure_has_a_case(self):
        run = self.new_run()
        with self.assertRaisesRegex(ValueError, "unsuccessful terminal"):
            self.case(run)

    def test_only_a_human_acts_and_nothing_else_may(self):
        run = self.new_run()
        self.fail(run, "test_failed")
        binding = self.case(run)["binding"]
        for origin in (Origin.RENDERER, Origin.MCP, Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                self.act(run, "retry", binding, origin=origin)

    def test_retry_queues_a_new_run_and_the_timeline_tells_the_story(self):
        run = self.new_run()
        self.fail(run, "test_failed")
        card = self.case(run)
        out = self.act(run, "retry", card["binding"])
        self.assertEqual(out["outcome"], "queued")
        self.assertTrue(out["new_run"].startswith("run-"))
        types = [e["type"] for e in op.timeline(self.ctx, run)]
        self.assertEqual(types, [op.OPENED, op.ACTED])
        self.assertEqual(op.timeline(self.ctx, run)[1]["new_run"], out["new_run"])

    def test_stale_approval_after_the_run_changed(self):
        run = self.new_run()
        self.fail(run, "test_failed")
        shown = self.case(run)["binding"]
        self.fail(run, "worker_failed")  # the run's own record moved after the dialog was opened
        self.assertEqual(code_of(self.act, run, "retry", shown), "STALE_OR_FOREIGN")

    def test_wrong_run_escalation(self):
        a, b = self.new_run(), self.new_run()
        self.fail(a, "test_failed")
        self.fail(b, "test_failed")
        self.assertEqual(code_of(self.act, b, "retry", self.case(a)["binding"]), "STALE_OR_FOREIGN")  # a's approval cannot move b
        self.assertEqual(code_of(self.act, a, "retry", "0" * 64), "STALE_OR_FOREIGN")

    def test_quota_is_a_pause_and_a_person_can_resume_it(self):
        run = self.new_run()
        self.fail(run, "limit_exhausted")
        card = self.case(run)
        self.assertEqual((card["automatic"]["action"], card["actions"]), ("pause", ["resume", "dismiss"]))
        with self.assertRaisesRegex(ValueError, "manual resolution"):
            runner.retry_task(self.ctx, run)  # nothing automatic can resume it
        self.assertEqual(code_of(self.act, run, "retry", card["binding"]), "ACTION_NOT_ALLOWED")  # the plain retry button is not offered
        out = self.act(run, "resume", card["binding"])
        self.assertEqual(out["outcome"], "queued")

    def test_quota_resumed_without_auth_needs_an_acknowledgement(self):
        first = self.new_run()
        self.fail(first, "auth_required")
        second = runner.retry_task(self.ctx, first, operator_resume=True)["run_id"]
        self.fail(second, "limit_exhausted")
        card = self.case(second)
        self.assertTrue(card["cautions"])
        self.assertEqual(code_of(self.act, second, "resume", card["binding"]), "ACK_REQUIRED")
        self.assertEqual(self.act(second, "resume", card["binding"], acknowledge=("auth_checked",))["outcome"], "queued")

    def test_policy_denial_has_no_way_forward_but_dismiss(self):
        run = self.new_run()
        self.fail(run, "scope_violation")
        card = self.case(run)
        self.assertEqual((card["actions"], card["automatic"]["action"]), (["dismiss"], "stop"))
        self.assertEqual(code_of(self.act, run, "resume", card["binding"]), "ACTION_NOT_ALLOWED")
        self.assertEqual(self.act(run, "dismiss", card["binding"])["outcome"], "dismissed")

    def test_crash_loop_ends_at_the_attempt_limit_which_no_person_can_lift(self):
        first = self.new_run()
        self.fail(first, "worker_failed")
        second = runner.retry_task(self.ctx, first)["run_id"]
        self.fail(second, "worker_failed")
        third = runner.retry_task(self.ctx, second)["run_id"]
        self.fail(third, "worker_failed")
        card = self.case(third)  # third attempt of three: the attempt limit, which no person can lift
        self.assertEqual((card["automatic"]["why"], card["actions"]), ("attempt_limit_reached", ["dismiss"]))

    def test_bad_action(self):
        run = self.new_run()
        self.fail(run, "test_failed")
        self.assertEqual(code_of(self.act, run, "apply", self.case(run)["binding"]), "BAD_ACTION")


if __name__ == "__main__":
    unittest.main()
