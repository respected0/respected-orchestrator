"""A4: hard per-lane token budget that survives retries, and usage that is UNKNOWN when it is unknown (never zero)."""
import json
from pathlib import Path
import unittest
from unittest import mock

from respected_orchestrator.engine import budget, runner

from respected_orchestrator.workflows import campaign, project
from respected_orchestrator.context import EngineContext
from respected_orchestrator.workflows.maf_workflow import run_maf_coding_task
from respected_orchestrator.engine.runner import _load, _save, create_task, execute_task
from tests.test_reviewer_reliability import CodingFixture, outcome


class BudgetModuleTests(unittest.TestCase):
    def test_a_launched_step_without_usage_is_unknown_and_a_never_launched_step_is_nothing(self):
        known = {"estimated_weighted_tokens": 100, "cached_input_tokens": 2000}
        self.assertEqual(budget.worker_step({"usage": known}), known)
        self.assertEqual(budget.worker_step({"status": "timed_out", "workspace": "w", "worker_incomplete": "no_turn_completed"}), {})
        self.assertIsNone(budget.worker_step({"status": "failed", "reason": "stale_project"}))  # refused before launch
        self.assertEqual(budget.worker_step({"usage": {"estimated_weighted_tokens": None}, "workspace": "w"}), {})

    def test_summary_status_and_the_explicit_assumed_charge(self):
        known = {"estimated_weighted_tokens": 100}
        self.assertEqual(budget.summarize([])["usage_status"], "NONE")
        self.assertEqual(budget.summarize([known, None])["usage_status"], "KNOWN")
        self.assertEqual(budget.summarize([{}])["usage_status"], "UNKNOWN")
        mixed = budget.summarize([known, {}, {}])
        self.assertEqual((mixed["usage_status"], mixed["unknown_steps"], mixed["usage"]["estimated_weighted_tokens"]), ("PARTIAL", 2, 100))
        self.assertEqual(budget.committed(mixed, 1000), 100 + 2 * 1000)  # unknown is charged for the budget, not reported as spend

    def test_cached_input_share_of_the_weighted_cost(self):
        # 2,000 cached tokens weigh 60 of a 100 weighted total: re-reading is 60 % of what this step cost
        self.assertEqual(budget.cached_cost_share({"estimated_weighted_tokens": 100, "cached_input_tokens": 2000}), 0.6)
        self.assertIsNone(budget.cached_cost_share({}))
        self.assertIn("Token discipline", runner.SELF_CHECK)  # the worker brief tells the agent not to re-read or dump output

    def test_workflow_budget_validation(self):
        for good in ({"max_weighted_tokens": 1000}, {"max_weighted_tokens": 50_000_000}, {"unknown_step_tokens": 0}, {}):
            runner._workflow(good)
        for bad in ({"max_weighted_tokens": 999}, {"max_weighted_tokens": True}, {"max_weighted_tokens": "5000"},
                    {"max_weighted_tokens": 50_000_001}, {"unknown_step_tokens": -1}, {"unknown_step_tokens": 1.5}):
            with self.assertRaises(ValueError, msg=bad):
                runner._workflow(bad)


class LaneBudgetTests(CodingFixture):
    """Mocked worker and codex calls; only the budget behaviour is under test."""

    def create_run(self, **workflow):
        run_id = create_task(self.ctx, self.request(**workflow))["run_id"]
        (self.ctx.run_dir(run_id) / "worker.patch").write_text("+value = 1\n", encoding="utf8")
        return run_id

    def completed(self, run_id, weighted=100, cached=0):
        return {"run_id": run_id, "status": "completed", "changed_files": ["calculator.py"], "patch_sha256": "0" * 64,
                "checks": [{"command": ["x"], "returncode": 0}], "workspace": str(self.root), "duration_seconds": 0.1,
                "usage": {"estimated_weighted_tokens": weighted, "cached_input_tokens": cached}}

    def run_with(self, run_id, calls, weighted=100, cached=0):
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", return_value=self.completed(run_id, weighted, cached)), \
             mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call", side_effect=calls) as codex:
            return run_maf_coding_task(ctx=self.ctx, run_id=run_id), codex

    @staticmethod
    def approved(weighted=7):
        return outcome("COMPLETE", output=json.dumps({"decision": "APPROVED", "reason": "ok"}), usage={"estimated_weighted_tokens": weighted})

    def test_a_worker_that_spends_the_budget_stops_the_lane_before_any_review_and_nothing_is_approved(self):
        run_id = self.create_run(max_weighted_tokens=1000)
        output, codex = self.run_with(run_id, [self.approved()], weighted=1200)
        self.assertEqual((output["status"], output["reason"]), ("FAILED", "token_budget_exceeded"))
        codex.assert_not_called()  # no paid review is started once the budget is gone
        self.assertTrue(output["token_budget"]["exceeded"])
        self.assertEqual(output["token_budget"]["known_weighted_tokens"], 1200)
        self.assertNotEqual(_load(self.ctx, self.ctx.run_dir(run_id) / "maf-result.json")["status"], "MASTER_APPROVED")

    def test_within_budget_the_lane_completes_and_reports_the_spend(self):
        run_id = self.create_run(max_weighted_tokens=100_000)
        output, _ = self.run_with(run_id, [self.approved()])
        self.assertEqual(output["status"], "MASTER_APPROVED")
        self.assertEqual((output["token_budget"]["limit"], output["token_budget"]["exceeded"], output["usage_status"]), (100_000, False, "KNOWN"))

    def test_the_fast_and_deep_review_tokens_are_both_reported(self):
        # found by the independent reviewer: an approved deep review used to be missing from token_usage
        run_id = self.create_run(deep_review="always", reviewer_profile="independent", deep_review_profile="deep")
        fast = outcome("COMPLETE", output=json.dumps({"decision": "APPROVED", "reason": "ok"}), usage={"estimated_weighted_tokens": 11})
        deep = outcome("COMPLETE", output=json.dumps({"decision": "APPROVED", "reason": "ok"}), usage={"estimated_weighted_tokens": 13})
        output, codex = self.run_with(run_id, [fast, deep])
        self.assertEqual((codex.call_count, output["status"]), (2, "MASTER_APPROVED"))
        self.assertEqual(output["token_usage"]["estimated_weighted_tokens"], 100 + 11 + 13)
        self.assertEqual(output["token_budget"]["known_weighted_tokens"], 100 + 11 + 13)  # and the lifetime ledger agrees

    def test_unknown_review_usage_is_reported_unknown_charged_for_the_budget_and_stops_retries(self):
        run_id = self.create_run(reviewer_profile="deepseek", max_weighted_tokens=1000, unknown_step_tokens=200, review_retries=2)
        silent = outcome("TIMEOUT", cause="timeout_no_output")  # a timed-out review reports no usage at all
        output, codex = self.run_with(run_id, [silent, silent, silent], weighted=700)
        self.assertEqual(output["reason"], "token_budget_exceeded")
        self.assertEqual(codex.call_count, 2)  # 700 + 2 x 200 assumed >= 1000: the third attempt is never started
        self.assertEqual(len(output["review_failure"]["attempts"]), 2)
        self.assertEqual((output["usage_status"], output["unknown_usage_steps"]), ("PARTIAL", 2))
        self.assertEqual(output["token_usage"]["estimated_weighted_tokens"], 700)  # reported spend: only what is known
        self.assertEqual(output["token_budget"]["basis"], 700 + 2 * 200)  # assumed charge is shown apart from the spend
        self.assertEqual(output["token_budget"]["unknown_steps"], 2)

    def test_a_retry_does_not_reset_the_lane_budget(self):
        # a REAL coded run (so the re-invocation can verify and reuse it); only usage and the codex review are faked
        run_id = create_task(self.ctx, self.request(reviewer_profile="deepseek", max_weighted_tokens=1000, unknown_step_tokens=250,
                                                    review_retries=1))["run_id"]
        silent = outcome("TIMEOUT", cause="timeout_no_output")

        def spending(ctx, current):
            return dict(execute_task(ctx, current), usage={"estimated_weighted_tokens": 600})

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", side_effect=spending),              mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call", side_effect=[silent, silent]):
            first = run_maf_coding_task(ctx=self.ctx, run_id=run_id)
        self.assertEqual(first["reason"], "reviewer_timeout")  # 600 + 250 = 850 < 1000 when the retry started
        self.assertEqual(self.worker_runs(), 1)
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", side_effect=AssertionError("worker re-executed")),              mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call", side_effect=[self.approved()]) as codex:
            second = run_maf_coding_task(ctx=self.ctx, run_id=run_id)  # re-invocation of the same run
        codex.assert_not_called()  # 600 + 2 x 250 = 1100 >= 1000 across invocations: no review is started
        self.assertEqual((second["status"], second["reason"]), ("FAILED", "token_budget_exceeded"))
        self.assertEqual(second["token_budget"]["unknown_steps"], 2)
        self.assertEqual((len(second["attempts"]), self.worker_runs()), (1, 1))  # the verified worker run is not repeated

    def test_the_cached_input_share_is_reported_per_invocation(self):
        run_id = self.create_run(reviewer_profile="deepseek")
        output, _ = self.run_with(run_id, [self.approved()], weighted=100, cached=2000)
        self.assertEqual(output["cached_cost_share"], round(60 / 107, 3))  # 60 of (100 worker + 7 review) weighted tokens
        ledger = _load(self.ctx, self.ctx.run_dir(run_id) / "maf-usage.json")["invocations"][-1]
        self.assertEqual(ledger["cached_cost_share"], output["cached_cost_share"])

    def test_signed_history_is_not_rewritten_by_a_budget_stop(self):
        run_id = self.create_run(max_weighted_tokens=1000)
        self.run_with(run_id, [self.approved()], weighted=500)
        attempts_path = self.ctx.run_dir(run_id) / "maf-attempts.json"
        before = attempts_path.read_bytes()
        self.run_with(run_id, [self.approved()], weighted=500)
        self.assertEqual(attempts_path.read_bytes(), before)  # a re-invocation appends nothing to the attempt history


class ReasonClassificationTests(CodingFixture):
    def test_budget_and_scope_reasons_survive_into_the_lane_summary(self):
        lane_ctx = EngineContext(self.root / "lane")
        run_id = "run-20260101000000-budget00"
        _save(lane_ctx, lane_ctx.run_dir(run_id) / "status.json", {"run_id": run_id, "status": "failed", "reason": "scope_violation"})
        kept = campaign._lane_summary("a", lane_ctx, {"status": "FAILED", "reason": "token_budget_exceeded", "final_run_id": run_id,
                                                      "usage_status": "PARTIAL", "unknown_usage_steps": 2})
        self.assertEqual((kept["reason"], kept["token_usage_status"], kept["unknown_usage_steps"]), ("token_budget_exceeded", "PARTIAL", 2))
        generic = campaign._lane_summary("a", lane_ctx, {"status": "FAILED", "reason": "worker_failed", "final_run_id": run_id})
        self.assertEqual(generic["reason"], "scope_violation")  # the signed run reason beats the generic MAF label


class ProjectBudgetTests(CodingFixture):
    def lane(self):
        return {"name": "lane", "after": [], "request": self.request()}

    def phase(self, **extra):
        return dict({"name": "p", "after": [], "workstreams": [self.lane()], "auto_apply": True, "verify": []}, **extra)

    def failing_runner(self, spend, unknown=0, requests=None):
        def run(ctx, campaign_id, timeout, cancel):
            cdir = campaign.campaign_dir(ctx, campaign_id)
            if requests is not None:
                requests.append(_load(ctx, cdir / "campaign.json")["workstreams"][0]["request"]["workflow"].get("max_weighted_tokens"))
            _save(ctx, cdir / "result.json", {"campaign_id": campaign_id, "status": "LANES_NEED_REVIEW", "lanes": [
                {"name": "lane", "status": "FAILED", "reason": "test_failed", "final_run_id": "run-20260101000000-aaaa1111",
                 "token_usage": {"estimated_weighted_tokens": spend}, "unknown_usage_steps": unknown,
                 "lane_data_root": str(ctx.data_root), "changed_files": []}]})
        return run

    def test_a_new_attempt_gets_what_is_left_of_the_lane_budget_not_a_fresh_one(self):
        project_id, _ = project.create_project(self.ctx, {"goal": "g", "phases": [self.phase(lane_token_budget=5000)],
                                                          "budget": {"max_phase_attempts": 2}})
        seen = []
        state = project.run_project(self.ctx, project_id, campaign_runner=self.failing_runner(3000, requests=seen))
        self.assertEqual(seen, [5000, 2000])  # the second worker run may spend only the remaining 2000
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["weighted_tokens"], 6000)  # both attempts are accounted

    def test_an_exhausted_lane_budget_blocks_before_anything_new_is_launched(self):
        project_id, _ = project.create_project(self.ctx, {"goal": "g", "phases": [self.phase(lane_token_budget=5000)],
                                                          "budget": {"max_phase_attempts": 3}})
        seen = []
        state = project.run_project(self.ctx, project_id, campaign_runner=self.failing_runner(4500, requests=seen))
        self.assertEqual(seen, [5000])  # 500 left is below the 1000 minimum: no second campaign is created
        self.assertEqual(state["status"], "blocked")
        self.assertIn("exhausted its token budget", state["reason"])

    def test_unknown_usage_is_charged_for_the_project_budget_not_assumed_zero(self):
        project_id, _ = project.create_project(self.ctx, {"goal": "g", "phases": [self.phase()],
                                                          "budget": {"max_weighted_tokens": 100_000, "unknown_step_tokens": 60_000,
                                                                     "max_phase_attempts": 2}})
        state = project.run_project(self.ctx, project_id, campaign_runner=self.failing_runner(10_000, unknown=2))
        self.assertEqual((state["weighted_tokens"], state["unknown_usage_steps"]), (10_000, 2))  # spend stays what is known
        self.assertEqual(state["status"], "blocked")
        self.assertIn("token budget exceeded", state["reason"])  # 10k + 2 x 60k > 100k

    def test_invalid_budget_settings_are_rejected(self):
        for bad in ({"phases": [self.phase(lane_token_budget=10)]}, {"phases": [self.phase(lane_token_budget=True)]},
                    {"phases": [self.phase()], "budget": {"unknown_step_tokens": -5}}):
            with self.assertRaises(ValueError):
                project.create_project(self.ctx, dict({"goal": "g"}, **bad))


if __name__ == "__main__":
    unittest.main()
