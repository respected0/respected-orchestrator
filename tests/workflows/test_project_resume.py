"""RES-02: controlled project resume after a kill, with an exact human approval boundary."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.evidence import load_signed, save_signed
from respected_orchestrator.interfaces import mcp_server, memory
from respected_orchestrator.workflows import campaign, checkpoint, project
from respected_orchestrator.workflows.maf_workflow import ReviewerTimeoutError, run_maf_coding_task

PY = sys.executable


def write_if(required, name, text):
    return [PY, "-c", f"from pathlib import Path\nassert {required!r} == '' or Path({required!r}).read_text() == 'new\\n'\n"
                      f"Path({name!r}).write_text({text!r})"]


def check_file(name, text):
    return [PY, "-c", f"from pathlib import Path; assert Path({name!r}).read_text() == {text!r}"]


def timeout_review(results):
    raise ReviewerTimeoutError("review timed out", cause="timeout_active_at_deadline")


class ProjectResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        self.source = self.root / "src"
        self.source.mkdir()
        (self.source / "f.txt").write_text("old\n")
        for target in ("respected_orchestrator.workflows.project._stdin_is_tty",
                       "respected_orchestrator.engine.runner._stdin_is_tty"):
            patcher = mock.patch(target, return_value=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.runs = []
        brain = mock.patch.object(memory, "winproc", mock.Mock(run=mock.Mock()))
        self.brain = brain.start()
        self.addCleanup(brain.stop)

    def lane(self, name="one", owned="f.txt", command=None, accept=None, after=()):
        return {"name": name, "after": list(after), "request": {
            "project_root": str(self.source), "task": f"{name} task", "worker": "custom", "kind": "write",
            "ownership": [owned], "command": command or write_if("", owned, "new\n"),
            "acceptance": [accept or check_file(owned, "new\n")], "timeout_seconds": 30,
            "workflow": {"max_fix_rounds": 0}}}

    def phase(self, lanes=None, *, auto_apply=True, verify=None):
        return {"name": "p", "after": [], "workstreams": lanes or [self.lane()], "auto_apply": auto_apply,
                "verify": verify or [{"command": check_file("f.txt", "new\n"), "cwd": str(self.source)}]}

    def create(self, phases=None, **extra):
        project_id, _ = project.create_project(self.ctx, dict(goal="resume", phases=phases or [self.phase()], **extra))
        return project_id

    def state(self, project_id):
        return load_signed(self.ctx, project.project_dir(self.ctx, project_id) / "project.json")

    def saved_checkpoint(self, project_id):
        return load_signed(self.ctx, checkpoint.checkpoint_path(self.ctx, "project", project_id))

    def approval_path(self, project_id):
        return project.project_dir(self.ctx, project_id) / project._RESUME_APPROVAL

    def runner(self, lane_runner=None):
        lane_runner = lane_runner or (lambda lane_ctx, run_id: run_maf_coding_task(
            ctx=lane_ctx, run_id=run_id, reviewer=lambda results: {"decision": "APPROVED"}))

        def run(ctx, campaign_id, timeout, cancel):
            self.runs.append(campaign_id)
            campaign.run_campaign(ctx, campaign_id, lane_runner=lane_runner)
        return run

    def counted_apply(self, calls):
        real = project.apply_task

        def apply(lane_ctx, run_id, **kwargs):
            calls.append(run_id)
            return real(lane_ctx, run_id, **kwargs)
        return apply

    def test_kill_before_campaign_resumes_once_and_keeps_one_operation_id(self):
        project_id = self.create()
        with mock.patch.object(project.campaign, "create_campaign", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        first = self.saved_checkpoint(project_id)
        self.assertEqual(first["operation_id"], project_id)
        self.assertEqual(first["next_action"]["step"], "campaign")
        applies = []
        with mock.patch.object(project, "apply_task", side_effect=self.counted_apply(applies)):
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(len(applies), 1)
        self.assertEqual((self.source / "f.txt").read_text(), "new\n")
        final = self.saved_checkpoint(project_id)
        self.assertEqual((final["operation_id"], final["next_action"]["step"]), (project_id, "complete"))
        self.brain.run.assert_not_called()  # RES-03 disconnected resume 1/3: campaign boundary
        paths = list((self.ctx.data_root / "checkpoints" / "project").glob("*.json"))
        self.assertEqual(len(paths), 1)  # every replay overwrote the same operation record atomically

    def test_kill_after_campaign_result_before_accounting_does_not_rerun_the_campaign(self):
        project_id = self.create()
        real_after = project._after_campaign_result

        def after_then_die(ctx, state, phase, stage):
            real_after(ctx, state, phase, stage)
            raise KeyboardInterrupt

        with mock.patch.object(project, "_after_campaign_result", side_effect=after_then_die):
            with self.assertRaises(KeyboardInterrupt):
                project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(self.saved_checkpoint(project_id)["next_action"]["step"], "apply")
        self.assertEqual((self.source / "f.txt").read_text(), "old\n")
        applies = []
        with mock.patch.object(project, "apply_task", side_effect=self.counted_apply(applies)):
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(len(applies), 1)
        stage = state["phases"]["p"]["attempts"][0]["stages"][0]
        self.assertIn("weighted_tokens", stage)
        self.assertEqual(stage["applied"], ["one"])

    def test_kill_after_accounting_reuses_the_charge_and_applies_once(self):
        project_id = self.create()

        def die_before_apply(*args, **kwargs):
            raise KeyboardInterrupt

        with mock.patch.object(project, "_merge_lanes", side_effect=die_before_apply):
            with self.assertRaises(KeyboardInterrupt):
                project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        interrupted = self.state(project_id)
        charged = project._budget_used(interrupted, interrupted["spec"])
        self.assertGreater(charged, 0)
        self.assertEqual((self.source / "f.txt").read_text(), "old\n")
        applies = []
        with mock.patch.object(project, "apply_task", side_effect=self.counted_apply(applies)):
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(project._budget_used(state, state["spec"]), charged)  # one signed stage is charged exactly once
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(len(applies), 1)
        self.assertEqual(len(list((self.ctx.data_root / "checkpoints" / "project").glob("*.json"))), 1)
        self.brain.run.assert_not_called()  # RES-03 disconnected resume 2/3: apply boundary

    def test_kill_after_apply_is_explained_by_the_signed_marker_without_reapplying(self):
        project_id = self.create()
        calls = []
        real_apply = project.apply_task

        def apply_then_die(lane_ctx, run_id, **kwargs):
            real_apply(lane_ctx, run_id, **kwargs)
            calls.append(run_id)
            raise KeyboardInterrupt

        with mock.patch.object(project, "apply_task", side_effect=apply_then_die):
            with self.assertRaises(KeyboardInterrupt):
                project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual((self.source / "f.txt").read_text(), "new\n")
        self.assertFalse(self.approval_path(project_id).exists())
        with mock.patch.object(project, "apply_task", side_effect=self.counted_apply(calls)):
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(self.saved_checkpoint(project_id)["next_action"]["step"], "complete")

    def test_kill_after_verify_restarts_at_verify_then_completes_review(self):
        project_id = self.create(final_review={"command": [PY, "-c", "pass"]})
        real_verify = project._verify
        verifications = []

        def verify_then_die(ctx, phase, cancel):
            verifications.append(phase["name"])
            real_verify(ctx, phase, cancel)
            raise KeyboardInterrupt

        applies = []
        with mock.patch.object(project, "apply_task", side_effect=self.counted_apply(applies)):
            with mock.patch.object(project, "_verify", side_effect=verify_then_die):
                with self.assertRaises(KeyboardInterrupt):
                    project.run_project(self.ctx, project_id, campaign_runner=self.runner())
            self.assertEqual(self.saved_checkpoint(project_id)["next_action"]["step"], "verify")
            with mock.patch.object(campaign, "_start_final_master") as master:
                state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(len(verifications), 1)
        master.assert_called_once()
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(len(applies), 1)
        self.assertEqual(self.saved_checkpoint(project_id)["next_action"]["step"], "complete")
        self.brain.run.assert_not_called()  # RES-03 disconnected resume 3/3: verify boundary

    def test_an_old_patch_needs_approval_and_is_still_refused_as_stale(self):
        project_id = self.create()
        real_after = project._after_campaign_result

        def after_then_die(ctx, state, phase, stage):
            real_after(ctx, state, phase, stage)
            raise KeyboardInterrupt

        with mock.patch.object(project, "_after_campaign_result", side_effect=after_then_die):
            with self.assertRaises(KeyboardInterrupt):
                project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        (self.source / "f.txt").write_text("conflict\n")
        with self.assertRaisesRegex(ValueError, "human approval"):
            project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        project.approve_project_resume(self.ctx, project_id)
        calls = []
        with mock.patch.object(project, "apply_task", side_effect=self.counted_apply(calls)):
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "blocked", state)
        self.assertIn("refused", state["reason"])
        self.assertIn("stale", state["reason"])
        self.assertEqual(len(calls), 1)
        self.assertEqual((self.source / "f.txt").read_text(), "conflict\n")

    def test_reviewer_completion_retries_the_same_lane_and_runs_the_worker_once(self):
        roots = []

        def lane_runner(lane_ctx, run_id):
            roots.append(str(lane_ctx.data_root))
            reviewer = timeout_review if len(roots) == 1 else (lambda results: {"decision": "APPROVED"})
            return run_maf_coding_task(ctx=lane_ctx, run_id=run_id, reviewer=reviewer)

        project_id = self.create(budget={"max_phase_attempts": 2})
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner(lane_runner))
        self.assertEqual(state["status"], "completed", state)
        attempts = state["phases"]["p"]["attempts"]
        self.assertEqual([item["outcome"] for item in attempts], ["failed", "done"])
        self.assertIn("reviewer_timeout", attempts[0]["note"])
        self.assertEqual(roots[0], roots[1])
        self.assertEqual(len(roots), 2)
        self.assertEqual(state["weighted_tokens"], sum(item["weighted_tokens"] for item in attempts))

    def test_source_drift_needs_approval_and_then_runs_on_the_new_source(self):
        project_id = self.create()
        (self.source / "unrelated.txt").write_text("operator change\n")
        with self.assertRaisesRegex(ValueError, "human approval"):
            project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(self.runs, [])
        approval = project.approve_project_resume(self.ctx, project_id)
        self.assertEqual(approval["reason"], "source_changed")
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual((self.source / "unrelated.txt").read_text(), "operator change\n")
        self.assertEqual((self.source / "f.txt").read_text(), "new\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.source), *args], check=True, capture_output=True, text=True,
                              encoding="utf8", errors="replace")

    def test_repo_head_drift_needs_approval_and_the_approval_is_bound_to_it(self):
        self.git("init", "-q")
        self.git("config", "user.email", "resume@example.invalid")
        self.git("config", "user.name", "Resume Test")
        self.git("add", "f.txt")
        self.git("commit", "-q", "-m", "initial")
        project_id = self.create()
        self.git("commit", "-q", "--allow-empty", "-m", "operator moved HEAD")
        with self.assertRaisesRegex(ValueError, "human approval"):
            project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        approval = project.approve_project_resume(self.ctx, project_id)
        self.assertEqual(approval["reason"], "repo_head_changed")
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "completed", state)

    def test_unknown_checkpoint_action_needs_approval_and_launches_nothing(self):
        project_id = self.create()
        path = checkpoint.checkpoint_path(self.ctx, "project", project_id)
        document = load_signed(self.ctx, path)
        document["next_action"]["step"] = "unknown-step"
        save_signed(self.ctx, path, document)
        with self.assertRaisesRegex(ValueError, "human approval.*unknown_step"):
            project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(self.runs, [])
        self.assertFalse(self.approval_path(project_id).exists())

    def test_resume_clears_only_a_dead_lock_and_refuses_a_live_one(self):
        project_id = self.create()
        directory = project.project_dir(self.ctx, project_id)
        (directory / "run.lock").write_text("not-a-pid")
        with mock.patch.object(project, "_spawn", return_value=4321) as spawn:
            result = project.resume_project(self.ctx, project_id)
        self.assertEqual(result["status"], "resumed")
        spawn.assert_called_once()
        self.assertFalse((directory / "run.lock").exists())

        other = self.create()
        other_dir = project.project_dir(self.ctx, other)
        (other_dir / "run.lock").write_text(str(os.getppid()))
        with mock.patch.object(project, "_spawn") as refused_spawn:
            with self.assertRaisesRegex(ValueError, "already"):
                project.resume_project(self.ctx, other)
        refused_spawn.assert_not_called()
        self.assertTrue((other_dir / "run.lock").exists())

    def test_auto_apply_false_stays_blocked_even_after_resume_approval(self):
        project_id = self.create(phases=[self.phase(auto_apply=False)])
        (self.source / "unrelated.txt").write_text("operator change\n")
        project.approve_project_resume(self.ctx, project_id)
        with mock.patch.object(project, "apply_task") as apply:
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner())
        self.assertEqual(state["status"], "blocked", state)
        self.assertIn("preauthorized", state["reason"])
        apply.assert_not_called()
        self.assertEqual((self.source / "f.txt").read_text(), "old\n")

    def test_approval_is_not_available_to_children_or_mcp(self):
        project_id = self.create()
        (self.source / "unrelated.txt").write_text("operator change\n")
        for env in ({"RESPECTED_ORCH_CHILD": "1"}, {"RESPECTED_ORCH_DELEGATED": "1"}):
            with self.subTest(env=env), mock.patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(ValueError, "operator"):
                    project.approve_project_resume(self.ctx, project_id)
        self.assertFalse(self.approval_path(project_id).exists())
        listing = mcp_server.handle(self.ctx, {"id": 1, "method": "tools/list"})["result"]["tools"]
        self.assertFalse(any("approve" in item["name"] for item in listing))
        reply = mcp_server.handle(self.ctx, {"id": 2, "method": "tools/call", "params": {
            "name": "orchestrator_resume", "arguments": {"id": project_id}}})
        self.assertTrue(reply["result"]["isError"])
        self.assertIn("human approval", reply["result"]["content"][0]["text"])
        self.assertEqual(self.runs, [])


if __name__ == "__main__":
    unittest.main()
