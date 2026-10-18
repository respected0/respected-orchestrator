"""Autonomous projects: dependent phases apply, verify and continue with no new prompt (fake workers only)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator import campaign, project
from respected_orchestrator.context import EngineContext
from respected_orchestrator.maf_workflow import run_maf_coding_task
from respected_orchestrator.runner import _load

PY = sys.executable


def write_if(required, name, text):
    return [PY, "-c", f"from pathlib import Path\nassert {required!r} == '' or Path({required!r}).read_text() == 'new\\n'\n"
                      f"Path({name!r}).write_text({text!r})"]


def check_file(name, text):
    return [PY, "-c", f"from pathlib import Path; assert Path({name!r}).read_text() == {text!r}"]


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        self.source = self.root / "src"
        self.source.mkdir()
        (self.source / "f.txt").write_text("old\n")
        patcher = mock.patch("respected_orchestrator.runner._stdin_is_tty", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.runs = []

    def runner(self, ctx, campaign_id, timeout, cancel):
        self.runs.append(campaign_id)
        campaign.run_campaign(ctx, campaign_id, lane_runner=lambda lane_ctx, run_id: run_maf_coding_task(
            ctx=lane_ctx, run_id=run_id, reviewer=lambda results: {"decision": "APPROVED"}))

    def phase(self, name, owned, command, accept, after=(), verify=None, auto_apply=True):
        lane = {"name": name, "after": [], "request": {
            "project_root": str(self.source), "task": f"{name} task", "worker": "custom", "kind": "write",
            "ownership": [owned], "command": command, "acceptance": [accept], "timeout_seconds": 30,
            "workflow": {"max_corrections": 0}}}
        return {"name": name, "after": list(after), "workstreams": [lane], "auto_apply": auto_apply,
                "verify": [{"command": verify or check_file(owned, "new\n"), "cwd": str(self.source)}]}

    def create(self, phases, **extra):
        project_id, _ = project.create_project(self.ctx, dict(goal="demo", phases=phases, **extra))
        return project_id

    def state(self, project_id):
        return _load(self.ctx, project.project_dir(self.ctx, project_id) / "project.json")

    def test_two_dependent_phases_finish_without_a_new_prompt(self):
        one = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        # phase two only succeeds if phase one's applied change is already in the source it was built from
        two = self.phase("two", "g.txt", write_if("f.txt", "g.txt", "new\n"), check_file("g.txt", "new\n"), after=["one"])
        project_id = self.create([two, one])  # declared out of order: dependencies, not order, decide
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual((self.source / "f.txt").read_text(), "new\n")
        self.assertEqual((self.source / "g.txt").read_text(), "new\n")
        self.assertEqual(len(self.runs), 2)
        self.assertEqual(len({a["campaign_id"] for p in state["phases"].values() for a in p["attempts"]}), 2)
        self.assertFalse((self.source / ".git").exists())
        self.assertEqual(project.run_project(self.ctx, project_id, campaign_runner=self.runner)["status"], "completed")
        self.assertEqual(len(self.runs), 2)  # re-running a finished project launches nothing

    def test_failed_verification_is_retried_a_bounded_number_of_times_then_blocks(self):
        bad = [PY, "-c", "raise SystemExit(1)"]
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"), verify=bad)
        project_id = self.create([phase, self.phase("two", "g.txt", write_if("", "g.txt", "new\n"),
                                                    check_file("g.txt", "new\n"), after=["one"])])
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(len(state["phases"]["one"]["attempts"]), 2)  # budget default
        self.assertEqual(state["phases"]["two"]["status"], "pending")
        self.assertFalse((self.source / "g.txt").exists())

    def test_apply_needs_preauthorization_and_leaves_source_untouched(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"), auto_apply=False)
        state = project.run_project(self.ctx, self.create([phase]), campaign_runner=self.runner)
        self.assertEqual(state["status"], "blocked")
        self.assertIn("preauthorized", state["reason"])
        self.assertEqual((self.source / "f.txt").read_text(), "old\n")

    def test_lock_cancel_and_time_budget(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase])
        directory = project.project_dir(self.ctx, project_id)
        (directory / "run.lock").write_text(str(os.getppid()))  # a live foreign owner
        with self.assertRaisesRegex(ValueError, "already"):
            project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        (directory / "run.lock").write_text("99999999")  # dead owner: stale
        project.cancel_project(self.ctx, project_id)
        self.assertEqual(project.run_project(self.ctx, project_id, campaign_runner=self.runner)["status"], "cancelled")  # stale lock replaced
        self.assertEqual(self.runs, [])
        late = self.create([phase])
        state = project.run_project(self.ctx, late, campaign_runner=self.runner, clock=lambda: 1e18)
        self.assertEqual((state["status"], state["reason"]), ("blocked", "time budget exceeded"))

    def test_resume_continues_the_recorded_attempt_without_a_duplicate_campaign(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase])
        with mock.patch.object(project, "_verify", side_effect=KeyboardInterrupt):  # supervisor dies after apply
            with self.assertRaises(KeyboardInterrupt):
                project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        self.assertEqual((self.source / "f.txt").read_text(), "new\n")
        self.assertFalse((project.project_dir(self.ctx, project_id) / "run.lock").exists())
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len(self.runs), 1)

    def test_invalid_projects_are_rejected(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        for bad in ({}, {"phases": []}, {"phases": [dict(phase, after=["one"])]}, {"phases": [phase, phase]},
                    {"phases": [phase], "budget": {"max_phase_attempts": 9}},
                    {"phases": [dict(phase, verify=[{"command": "rm -rf /", "cwd": str(self.source)}])]}):
            with self.assertRaises(ValueError, msg=str(bad)):
                project._spec(bad)


    def test_final_review_passes_already_applied_lanes_and_project_verdict(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase], final_review={"command": [PY, "-c", "pass"]})
        with mock.patch.object(campaign, "_start_final_master") as master:
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        self.assertEqual(state["status"], "completed", state)
        lanes = master.call_args.args[3]
        self.assertEqual([(lane["name"], lane["applied"], lane["verified"]) for lane in lanes], [("one", True, True)])
        self.assertTrue(master.call_args.kwargs["project_review"])


if __name__ == "__main__":
    unittest.main()
