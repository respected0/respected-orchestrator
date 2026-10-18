"""Adversarial review tests for the autonomous project supervisor (fake workers only)."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator import campaign, project
from respected_orchestrator.context import EngineContext
from respected_orchestrator.maf_workflow import run_maf_coding_task
from respected_orchestrator.processes import ProcessStopped
from respected_orchestrator.runner import _load, _save

PY = sys.executable


def write_if(required, name, text):
    return [PY, "-c", f"from pathlib import Path\nassert {required!r} == '' or Path({required!r}).read_text() == 'new\\n'\n"
                      f"Path({name!r}).write_text({text!r})"]


def check_file(name, text):
    return [PY, "-c", f"from pathlib import Path; assert Path({name!r}).read_text() == {text!r}"]


class ProjectAdversarialTests(unittest.TestCase):
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

    def test_crash_right_after_apply_resumes_without_a_second_apply(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase])
        real = project.apply_task
        calls = []

        def apply_then_die(lane_ctx, run_id, **kwargs):
            real(lane_ctx, run_id, **kwargs)
            calls.append(run_id)
            raise KeyboardInterrupt

        with mock.patch.object(project, "apply_task", side_effect=apply_then_die):
            with self.assertRaises(KeyboardInterrupt):
                project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        self.assertFalse((project.project_dir(self.ctx, project_id) / "run.lock").exists())
        self.assertEqual((self.source / "f.txt").read_text(), "new\n")
        self.assertEqual(len(calls), 1)
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(len(calls), 1)  # the on-disk applied.json guard prevents a double apply
        self.assertEqual(len(self.runs), 1)  # and the recorded attempt reuses its campaign

    def test_apply_conflict_blocks_the_phase_and_is_never_retried(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase])
        with mock.patch.object(project, "apply_task", side_effect=ValueError("stale context")):
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner)
        self.assertEqual(state["status"], "blocked", state)
        self.assertIn("refused", state["reason"])
        self.assertEqual(len(state["phases"]["one"]["attempts"]), 1)  # a refused apply needs a human
        self.assertEqual((self.source / "f.txt").read_text(), "old\n")
        self.assertEqual(len(self.runs), 1)

    def test_process_stopped_is_a_bounded_failed_attempt_then_blocks(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase])

        def stopped(ctx, campaign_id, timeout, cancel):
            raise ProcessStopped("killed by operator")

        state = project.run_project(self.ctx, project_id, campaign_runner=stopped)
        attempts = state["phases"]["one"]["attempts"]
        self.assertEqual(state["status"], "blocked", state)
        self.assertEqual(len(attempts), 2)  # default max_phase_attempts
        self.assertTrue(all(a.get("outcome") == "failed" for a in attempts))
        self.assertIn("stopped", attempts[-1]["note"])

    def test_cancel_during_a_phase_stops_before_the_next_phase_runs(self):
        one = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        two = self.phase("two", "g.txt", write_if("", "g.txt", "new\n"), check_file("g.txt", "new\n"), after=["one"])
        project_id = self.create([one, two])
        base = self.runner

        def cancelling(ctx, campaign_id, timeout, cancel):
            base(ctx, campaign_id, timeout, cancel)
            Path(cancel).write_text("stop")

        state = project.run_project(self.ctx, project_id, campaign_runner=cancelling)
        self.assertEqual(state["status"], "cancelled", state)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(state["phases"]["two"]["status"], "pending")
        self.assertEqual((self.source / "f.txt").read_text(), "new\n")  # phase one's apply is kept
        self.assertEqual(project.run_project(self.ctx, project_id, campaign_runner=self.runner)["status"], "cancelled")
        self.assertEqual(len(self.runs), 1)  # cancelled is terminal

    def test_token_budget_blocks_before_any_campaign_is_launched(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase], budget={"max_weighted_tokens": 5})
        directory = project.project_dir(self.ctx, project_id)
        state = self.state(project_id)
        state["weighted_tokens"] = 6
        _save(self.ctx, directory / "project.json", state)
        called = []
        result = project.run_project(self.ctx, project_id, campaign_runner=lambda *a: called.append(a))
        self.assertEqual((result["status"], result["reason"]), ("blocked", "token budget exceeded"))
        self.assertEqual(called, [])
        self.assertEqual(self.runs, [])

    def test_persisted_deadline_and_a_corrupt_lock(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        late = self.create([phase])
        directory = project.project_dir(self.ctx, late)
        state = self.state(late)
        state["deadline_epoch"] = 1.0
        _save(self.ctx, directory / "project.json", state)
        blocked = project.run_project(self.ctx, late, campaign_runner=self.runner)
        self.assertEqual((blocked["status"], blocked["reason"]), ("blocked", "time budget exceeded"))
        self.assertEqual(self.runs, [])
        other = self.create([phase])
        (project.project_dir(self.ctx, other) / "run.lock").write_text("not-a-pid")  # corrupt => stale
        done = project.run_project(self.ctx, other, campaign_runner=self.runner)
        self.assertEqual(done["status"], "completed", done)

    def test_spec_rejects_malformed_inputs_with_valueerror(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        many = [dict(phase, name=f"p{i}") for i in range(13)]
        bad = [
            {"phases": [phase], "budget": {"max_seconds": 30}},
            {"phases": [phase], "budget": {"max_phase_attempts": 0}},
            {"phases": [phase], "engine_source": str(self.root / "nope")},
            {"phases": [dict(phase, after=["ghost"])]},
            {"phases": [dict(phase, name="Bad Name")]},
            {"phases": many},
            {"phases": [dict(phase, verify=[{"command": check_file("f.txt", "new\\n"), "cwd": str(self.root / "missing")}])]},
        ]
        for spec in bad:
            with self.assertRaises(ValueError, msg=str(spec)):
                project._spec(spec)

    def test_a_rejected_lane_is_retried_then_blocks_without_touching_source(self):
        lane = {"name": "one", "after": [], "request": {
            "project_root": str(self.source), "task": "one task", "worker": "custom", "kind": "write",
            "ownership": ["f.txt"], "command": write_if("", "f.txt", "new\n"),
            "acceptance": [check_file("f.txt", "new\n")], "timeout_seconds": 30,
            "workflow": {"max_corrections": 0}}}
        phase = {"name": "one", "after": [], "workstreams": [lane], "auto_apply": True,
                 "verify": [{"command": check_file("f.txt", "new\n"), "cwd": str(self.source)}]}
        project_id = self.create([phase])

        def rejecting(ctx, campaign_id, timeout, cancel):
            self.runs.append(campaign_id)
            campaign.run_campaign(ctx, campaign_id, lane_runner=lambda lane_ctx, run_id: run_maf_coding_task(
                ctx=lane_ctx, run_id=run_id, reviewer=lambda results: {"decision": "REJECTED", "reason": "no"}))

        state = project.run_project(self.ctx, project_id, campaign_runner=rejecting)
        self.assertEqual(state["status"], "blocked", state)
        self.assertEqual(len(state["phases"]["one"]["attempts"]), 2)
        self.assertEqual((self.source / "f.txt").read_text(), "old\n")  # unapproved work is never applied
        self.assertEqual(len(self.runs), 2)


    def test_spec_rejects_non_dict_budget_and_verify_with_valueerror(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        for bad in ({"phases": [phase], "budget": "x"}, {"phases": [dict(phase, verify=["x"])]}):
            with self.assertRaises(ValueError, msg=str(bad)):
                project._spec(bad)

    def test_spec_rejects_non_slug_after_entries_with_valueerror(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        for after in ([["one"]], "one", [1]):
            with self.assertRaises(ValueError, msg=repr(after)):
                project._spec({"phases": [dict(phase, after=after)]})

    def test_an_unaccounted_campaign_blocks_the_phase(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase])

        def unaccounted(ctx, campaign_id, timeout, cancel):
            self.runs.append(campaign_id)

            def lane(lane_ctx, run_id):
                result = run_maf_coding_task(ctx=lane_ctx, run_id=run_id, reviewer=lambda results: {"decision": "APPROVED"})
                result.pop("token_usage", None)  # the campaign spent budget but recorded none
                return result

            campaign.run_campaign(ctx, campaign_id, lane_runner=lane)

        with mock.patch.object(project, "apply_task"):  # never reached: no accounting means no apply
            state = project.run_project(self.ctx, project_id, campaign_runner=unaccounted)
        self.assertEqual(state["status"], "blocked", state)
        self.assertIn("token usage unknown for lane one", state["reason"])
        self.assertEqual(len(state["phases"]["one"]["attempts"]), 1)  # fail closed: no further spending
        self.assertEqual(state["phases"]["one"]["attempts"][-1]["unaccounted"], ["one"])
        self.assertEqual((self.source / "f.txt").read_text(), "old\n")

    def test_an_unexpected_attempt_error_blocks_instead_of_leaving_running(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase])

        def exploding(ctx, campaign_id, timeout, cancel):
            raise RuntimeError("runner bug")

        state = project.run_project(self.ctx, project_id, campaign_runner=exploding)
        self.assertEqual(state["status"], "blocked", state)
        attempts = state["phases"]["one"]["attempts"]
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all(a.get("outcome") == "failed" for a in attempts))
        self.assertIn("runner bug", attempts[-1]["note"])

    def test_a_completed_project_still_runs_final_review_on_rerun(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase], final_review={"command": [PY, "-c", "pass"]})
        with mock.patch.object(project, "final_review") as review:
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner)
            self.assertEqual(state["status"], "completed", state)
            self.assertEqual(review.call_count, 1)
            again = project.run_project(self.ctx, project_id, campaign_runner=self.runner)
            self.assertEqual(again["status"], "completed", again)
            self.assertEqual(review.call_count, 2)

    def test_lock_race_retries_then_reports_already_being_executed(self):
        directory = self.root / "lockdir"
        directory.mkdir()
        lock = directory / "run.lock"
        real_open = os.open

        def open_or_raced(path, flags, *args, **kwargs):
            if str(path) == str(lock):
                raise FileExistsError  # a racing supervisor keeps recreating the lock in our unlink->create window
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(project.os, "open", side_effect=open_or_raced):
            with self.assertRaisesRegex(ValueError, "already being executed"):
                project._acquire(directory)

    def test_final_review_is_validated_with_a_placeholder_not_a_phase(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        seen = []
        real = campaign._spec

        def spy(payload, *settings):
            seen.append(payload.get("workstreams"))
            return real(payload, *settings)

        with mock.patch.object(project.campaign, "_spec", side_effect=spy):
            spec = project._spec({"phases": [phase], "final_review": {"command": [PY, "-c", "pass"]}})
        self.assertFalse(spec["final_review"]["allow_apply"])
        self.assertEqual(seen[-1], [{"name": "review", "after": [], "request": {}}])

    def test_a_failed_lane_reports_its_reason_instead_of_missing_accounting(self):
        phase = self.phase("one", "f.txt", write_if("", "f.txt", "new\n"), check_file("f.txt", "new\n"))
        project_id = self.create([phase])

        def failing(ctx, campaign_id, timeout, cancel):
            self.runs.append(campaign_id)
            campaign.run_campaign(ctx, campaign_id, lane_runner=lambda lane_ctx, run_id: {"status": "FAILED", "reason": "boom"})

        state = project.run_project(self.ctx, project_id, campaign_runner=failing)
        self.assertEqual(state["status"], "blocked", state)
        self.assertIn("boom", state["reason"])
        self.assertNotIn("accounting", state["reason"])


if __name__ == "__main__":
    unittest.main()
