"""Recovery of the autonomous project supervisor: staged phases, token accounting and bounded retries (fakes only)."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.workflows import campaign, project
from respected_orchestrator.context import EngineContext
from respected_orchestrator.workflows.maf_workflow import run_maf_coding_task
from respected_orchestrator.engine.evidence import load_signed, save_signed

PY = sys.executable


def write_if(required, name, text):
    return [PY, "-c", f"from pathlib import Path\nassert {required!r} == '' or Path({required!r}).read_text() == 'new\\n'\n"
                      f"Path({name!r}).write_text({text!r})"]


def check_file(name, text):
    return [PY, "-c", f"from pathlib import Path; assert Path({name!r}).read_text() == {text!r}"]


class ProjectRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        self.source = self.root / "src"
        self.source.mkdir()
        (self.source / "f.txt").write_text("old\n")
        patcher = mock.patch("respected_orchestrator.engine.runner._stdin_is_tty", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.runs = []

    def lane(self, name, owned, command, accept, after=()):
        return {"name": name, "after": list(after), "request": {
            "project_root": str(self.source), "task": f"{name} task", "worker": "custom", "kind": "write",
            "ownership": [owned], "command": command, "acceptance": [accept], "timeout_seconds": 30,
            "workflow": {"max_corrections": 0}}}

    def phase(self, name, lanes, after=(), verify=None, auto_apply=True):
        return {"name": name, "after": list(after), "workstreams": lanes, "auto_apply": auto_apply,
                "verify": verify or []}

    def create(self, phases, **extra):
        project_id, _ = project.create_project(self.ctx, dict(goal="demo", phases=phases, **extra))
        return project_id

    def state(self, project_id):
        return load_signed(self.ctx, project.project_dir(self.ctx, project_id) / "project.json")

    def approve(self, lane_ctx, run_id):
        return run_maf_coding_task(ctx=lane_ctx, run_id=run_id, reviewer=lambda results: {"decision": "APPROVED"})

    def runner(self, lane_runner):
        def run(ctx, campaign_id, timeout, cancel):
            self.runs.append(campaign_id)
            campaign.run_campaign(ctx, campaign_id, lane_runner=lane_runner)
        return run

    def staged_phase(self, name="p"):
        # c has no dependency; d only succeeds if c's applied change is already in the source mirror it is built from
        c = self.lane("c", "c.txt", write_if("", "c.txt", "new\n"), check_file("c.txt", "new\n"))
        d = self.lane("d", "d.txt", [PY, "-c", "from pathlib import Path\nassert Path('c.txt').read_text() == 'new\\n'\n"
                                                "Path('d.txt').write_text('new\\n')"], check_file("d.txt", "new\n"), after=["c"])
        return self.phase(name, [c, d])

    def test_a_failed_attempt_with_a_skipped_lane_still_accounts_and_persists_tokens(self):
        a = self.lane("a", "a.txt", write_if("", "a.txt", "new\n"), check_file("a.txt", "new\n"))
        b = self.lane("b", "b.txt", write_if("", "b.txt", "new\n"), check_file("b.txt", "new\n"))

        def lane_runner(ctx, campaign_id, timeout, cancel):
            self.runs.append(campaign_id)
            save_signed(ctx, campaign.campaign_dir(ctx, campaign_id) / "result.json", dict(status="LANES_NEED_REVIEW", lanes=[
                {"name": "a", "status": "FAILED", "reason": "timed_out/no_turn_completed",
                 "final_run_id": "run-20260101000000-aaaa1111", "token_usage": {"estimated_weighted_tokens": 7},
                 "lane_data_root": str(ctx.data_root), "changed_files": []},
                {"name": "b", "status": "SKIPPED", "reason": "dependency a not approved", "final_run_id": None,
                 "token_usage": None, "lane_data_root": str(self.root / "unstarted"), "changed_files": []},
            ]))

        project_id = self.create([self.phase("p", [a, b])])
        state = project.run_project(self.ctx, project_id, campaign_runner=lane_runner)
        self.assertEqual(state["status"], "blocked", state)
        self.assertNotIn("accounting", state["reason"])
        attempt = state["phases"]["p"]["attempts"][0]
        self.assertEqual(attempt["outcome"], "failed")
        self.assertEqual(attempt["weighted_tokens"], 7)  # the started lane's spend; the skipped lane counts 0
        self.assertGreaterEqual(state["weighted_tokens"], 7)  # persisted before the early return
        self.assertEqual([lane["name"] for lane in attempt["lanes"] if lane["status"] == "SKIPPED"], ["b"])

    def test_a_started_lane_without_usage_blocks_the_whole_project_fail_closed(self):
        a = self.lane("a", "a.txt", write_if("", "a.txt", "new\n"), check_file("a.txt", "new\n"))

        def lane_runner(lane_ctx, run_id):
            result = self.approve(lane_ctx, run_id)
            result.pop("token_usage", None)  # started but its usage cannot be determined
            return result

        project_id = self.create([self.phase("p", [a])])
        with mock.patch.object(project, "apply_task") as apply:
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner(lane_runner))
        self.assertEqual(state["status"], "blocked", state)
        self.assertIn("token usage unknown for lane a", state["reason"])
        self.assertEqual(len(state["phases"]["p"]["attempts"]), 1)  # never continues spending
        self.assertEqual(state["phases"]["p"]["attempts"][0]["unaccounted"], ["a"])
        apply.assert_not_called()
        self.assertEqual((self.source / "a.txt").exists(), False)

    def test_a_dependent_lane_sees_its_dependency_applied_output(self):
        project_id = self.create([self.staged_phase()])
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner(self.approve))
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual((self.source / "c.txt").read_text(), "new\n")
        self.assertEqual((self.source / "d.txt").read_text(), "new\n")
        self.assertEqual(len(self.runs), 2)  # one fresh campaign per stage
        stages = state["phases"]["p"]["attempts"][0]["stages"]
        self.assertEqual(len(stages), 2)
        self.assertEqual([stage["applied"] for stage in stages], [["c"], ["d"]])
        self.assertEqual({stage["campaign_id"] for stage in stages}, set(self.runs))

    def test_retry_skips_applied_lanes_and_corrects_only_failed_lanes(self):
        a = self.lane("a", "a.txt", write_if("", "a.txt", "new\n"), check_file("a.txt", "new\n"))
        b = self.lane("b", "b.txt", write_if("", "b.txt", "new\n"), check_file("b.txt", "new\n"))
        seen, calls = [], {"b": 0}

        def lane_runner(lane_ctx, run_id):
            name = Path(lane_ctx.data_root).name
            task = load_signed(lane_ctx, lane_ctx.run_dir(run_id) / "request.json")["task"]
            seen.append((name, task))
            if name == "a":
                return self.approve(lane_ctx, run_id)
            calls["b"] += 1
            if calls["b"] == 1:
                return {"status": "FAILED", "reason": "boom", "final_run_id": "run-20260101000000-bbfeed00",
                        "token_usage": {"estimated_weighted_tokens": 1}, "attempts": []}
            return self.approve(lane_ctx, run_id)

        project_id = self.create([self.phase("p", [a, b])])
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner(lane_runner))
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual([name for name, _ in seen].count("a"), 1)  # applied lane is not re-run
        self.assertEqual([name for name, _ in seen].count("b"), 2)
        b_tasks = [task for name, task in seen if name == "b"]
        self.assertNotIn("CORRECTION", b_tasks[0])
        self.assertIn("CORRECTION", b_tasks[1])
        self.assertIn("boom", b_tasks[1])
        attempts = state["phases"]["p"]["attempts"]
        retry_campaigns = {stage["campaign_id"] for stage in attempts[1]["stages"]}
        self.assertNotIn(attempts[0]["stages"][0]["campaign_id"], retry_campaigns)  # a's campaign is not reused
        self.assertEqual(attempts[1]["stages"][0]["lanes"], ["b"])

    def test_a_kill_mid_stage_resumes_without_a_duplicate_campaign_or_apply(self):
        project_id = self.create([self.staged_phase()])
        real_create, calls = campaign.create_campaign, {"n": 0}
        applies, real_apply = [], project.apply_task

        def exploding_create(ctx, request):
            calls["n"] += 1
            if calls["n"] == 2:  # die right after stage one is applied, before stage two's campaign exists
                raise KeyboardInterrupt
            return real_create(ctx, request)

        def counted_apply(lane_ctx, run_id, **kwargs):
            applies.append(run_id)
            return real_apply(lane_ctx, run_id, **kwargs)

        with mock.patch.object(project.campaign, "create_campaign", side_effect=exploding_create):
            with mock.patch.object(project, "apply_task", side_effect=counted_apply):
                with self.assertRaises(KeyboardInterrupt):
                    project.run_project(self.ctx, project_id, campaign_runner=self.runner(self.approve))
        self.assertEqual((self.source / "c.txt").read_text(), "new\n")
        with mock.patch.object(project, "apply_task", side_effect=counted_apply):
            state = project.run_project(self.ctx, project_id, campaign_runner=self.runner(self.approve))
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(len(self.runs), 2)  # c's campaign is not re-run
        stages = state["phases"]["p"]["attempts"][0]["stages"]
        self.assertEqual(len(stages), 2)
        self.assertEqual({stage["campaign_id"] for stage in stages}, set(self.runs))
        self.assertEqual(len(applies), 2)  # c applied once, d applied once
        self.assertEqual(len(set(applies)), 2)

    def test_a_timed_out_lane_reports_a_non_null_reason(self):
        lane_ctx = EngineContext(self.root / "lane")
        run_id = "run-20260101000000-time0out"
        save_signed(lane_ctx, lane_ctx.run_dir(run_id) / "status.json",
              {"run_id": run_id, "status": "timed_out", "worker_incomplete": "no_turn_completed"})
        summary = campaign._lane_summary("one", lane_ctx, {"status": "FAILED", "reason": None, "final_run_id": run_id})
        self.assertEqual(summary["reason"], "timed_out/no_turn_completed")
        self.assertEqual(summary["status"], "FAILED")
        self.assertIsNone(summary["token_usage"])

    def test_a_scope_violation_is_not_reported_as_the_generic_worker_failed(self):
        lane_ctx = EngineContext(self.root / "lane")
        run_id = "run-20260101000000-scope000"
        save_signed(lane_ctx, lane_ctx.run_dir(run_id) / "status.json",
              {"run_id": run_id, "status": "failed", "reason": "scope_violation"})
        summary = campaign._lane_summary("one", lane_ctx, {"status": "FAILED", "reason": "worker_failed", "final_run_id": run_id})
        self.assertEqual(summary["reason"], "scope_violation")
        bare = campaign._lane_summary("one", lane_ctx, {"status": "FAILED", "reason": "worker_failed", "final_run_id": "run-20260101000000-missing0"})
        self.assertEqual(bare["reason"], "worker_failed")  # no signed status: keep the generic label

    def test_a_signed_worker_failure_keeps_worker_failed(self):
        lane_ctx = EngineContext(self.root / "lane")
        run_id = "run-20260101000000-genuine0"
        save_signed(lane_ctx, lane_ctx.run_dir(run_id) / "status.json",
              {"run_id": run_id, "status": "failed", "reason": "worker_failed"})
        summary = campaign._lane_summary("one", lane_ctx, {"status": "FAILED", "reason": "worker_failed", "final_run_id": run_id})
        self.assertEqual(summary["reason"], "worker_failed")

    def test_invalid_or_misbound_signed_status_keeps_generic_worker_failed(self):
        lane_ctx = EngineContext(self.root / "lane")
        run_id = "run-20260101000000-bound000"
        status_path = lane_ctx.run_dir(run_id) / "status.json"
        payload = {"run_id": run_id, "status": "failed", "reason": "scope_violation"}
        save_signed(lane_ctx, status_path, payload)
        status_path.write_text(json.dumps({"payload": payload, "signature": "tampered"}), encoding="utf8")
        tampered = campaign._lane_summary("one", lane_ctx, {"status": "FAILED", "reason": "worker_failed", "final_run_id": run_id})
        self.assertEqual(tampered["reason"], "worker_failed")

        save_signed(lane_ctx, status_path, {"run_id": "run-20260101000000-other00", "status": "failed", "reason": "scope_violation"})
        misbound = campaign._lane_summary("one", lane_ctx, {"status": "FAILED", "reason": "worker_failed", "final_run_id": run_id})
        self.assertEqual(misbound["reason"], "worker_failed")

    def test_the_token_budget_after_stage_one_stops_stage_two(self):
        def lane_runner(lane_ctx, run_id):
            result = self.approve(lane_ctx, run_id)
            result["token_usage"] = {"estimated_weighted_tokens": 100}
            return result

        project_id = self.create([self.staged_phase()], budget={"max_weighted_tokens": 1})
        state = project.run_project(self.ctx, project_id, campaign_runner=self.runner(lane_runner))
        self.assertEqual(state["status"], "blocked", state)
        self.assertIn("token budget exceeded", state["reason"])
        self.assertEqual(len(self.runs), 1)  # stage two's campaign is never launched
        self.assertEqual(len(state["phases"]["p"]["attempts"][0]["stages"]), 1)


if __name__ == "__main__":
    unittest.main()
