"""A1 reviewer reliability and A2 review-only retry.

Fakes only (no provider is called). The real failure records of 2026-10-12 are replayed as fixtures: the codex
models-refresh stderr line that made every timeout look like a disconnect, and the 300 s DeepSeek review timeouts."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.workflows import campaign, project
from respected_orchestrator.context import EngineContext
from respected_orchestrator.workflows.maf_workflow import (ReviewerDisconnectedError, ReviewerTimeoutError, review_attempt_timeouts,
                                                 review_timeout_default, run_maf_coding_task)
from respected_orchestrator.engine.processes import ProcessStopped
from respected_orchestrator.engine.runner import apply_task, check_result, create_task, execute_task
from respected_orchestrator.engine.evidence import load_signed
from respected_orchestrator.engine.codex import CodexCall, CodexOutcome, diagnose, run_codex_call

PY = sys.executable
# verbatim from stderr.log of the real runs: printed every ~4.5 min by every codex process, whatever the turn is doing
MODELS_NOISE = ("2026-10-12T13:30:09.254126Z ERROR codex_models_manager::manager: failed to refresh available models: "
                "stream disconnected before completion: failed to decode models response: Data at line 1 column 8387 "
                "(body: 8387 bytes)\n")
PARTIAL_STDOUT = "\n".join([
    json.dumps({"type": "thread.started"}), json.dumps({"type": "turn.started"}),
    json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Found the worker workspace. Reading the patch."}}),
]) + "\n"
RECONNECT = json.dumps({"type": "error", "message": "Reconnecting... 1/5 (stream disconnected before completion)"})


def outcome(status, *, cause="", usage=None, output=""):
    return CodexOutcome(status=status, output=output, usage=usage or {}, events_path=Path("e.jsonl"), stdout_path=Path("o.log"),
                        stderr_path=Path("s.log"), cause=cause)


def timeout_review(results):
    raise ReviewerTimeoutError("fast reviewer status: TIMEOUT (timeout_active_at_deadline)", cause="timeout_active_at_deadline",
                               usage={"estimated_weighted_tokens": 5})


def approve_review(results):
    return {"decision": "APPROVED", "reason": "ok"}


class DiagnosisAndPolicyTests(unittest.TestCase):
    def test_the_models_refresh_line_is_not_evidence_of_a_disconnect(self):
        active = diagnose([{"type": "item.completed"}], MODELS_NOISE, status="TIMEOUT", had_output=True, last_output_age=4.0)
        self.assertEqual(active["cause"], "timeout_active_at_deadline")  # still working when the ceiling hit
        stalled = diagnose([{"type": "item.completed"}], MODELS_NOISE, status="TIMEOUT", had_output=True, last_output_age=200.0)
        self.assertEqual(stalled["cause"], "timeout_stalled_after_output")
        silent = diagnose([], MODELS_NOISE, status="TIMEOUT", had_output=False, last_output_age=None)
        self.assertEqual(silent["cause"], "timeout_no_output")

    def test_real_disconnect_evidence_is_still_a_disconnect(self):
        structured = diagnose([json.loads(RECONNECT)], "", status="TIMEOUT", had_output=True, last_output_age=4.0)
        self.assertEqual((structured["cause"], structured["confidence"]), ("provider_disconnected", "structured"))
        heuristic = diagnose([], "error sending request for url\n" + MODELS_NOISE, status="TIMEOUT", had_output=False, last_output_age=None)
        self.assertEqual(heuristic["cause"], "provider_disconnected")

    def test_a_real_timed_out_review_is_recorded_as_a_timeout_not_a_disconnect(self):
        stopped = ProcessStopped("timeout", stdout=PARTIAL_STDOUT, stderr=MODELS_NOISE, had_output=True, last_output_age=3.0)
        with tempfile.TemporaryDirectory() as temporary, mock.patch("respected_orchestrator.engine.codex.execute", side_effect=stopped):
            root = Path(temporary) / "review-fast-1"
            result = run_codex_call(CodexCall("fast", "deepseek", None, "prompt", root), cwd=Path(temporary), timeout_seconds=1)
            process = json.loads((root / "process.json").read_text(encoding="utf8"))
        self.assertEqual((result.status, result.cause), ("TIMEOUT", "timeout_active_at_deadline"))
        self.assertEqual((process["state"], process["cause"], process["returncode"]), ("TIMEOUT", "timeout_active_at_deadline", 124))

    def test_review_deadlines_are_provider_aware_scaled_by_patch_and_bounded(self):
        self.assertEqual(review_timeout_default("deepseek"), 600)  # the old fixed 300 s expired on real DeepSeek reviews
        self.assertEqual(review_timeout_default("glm-5.3"), 900)
        self.assertEqual(review_timeout_default("some-new-model"), 450)
        self.assertEqual(review_timeout_default("deepseek", patch_bytes=50_000), 600 + 250)
        self.assertEqual(review_timeout_default("deepseek", patch_bytes=10_000_000), 600 + 600)  # scaling is capped
        self.assertEqual(review_attempt_timeouts(600, 1), [600, 900])
        self.assertEqual(review_attempt_timeouts(3000, 2), [3000, 3600, 3600])  # never above the 3600 s ceiling
        self.assertEqual(review_attempt_timeouts(600, 0), [600])


class CodingFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "Fixture"), ("config", "user.email", "fixture@example.invalid")]:
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        (self.repo / "calculator.py").write_text("value = 0\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=self.repo, capture_output=True, check=True)
        self.ctx = EngineContext(self.root / "data")
        (self.root / "data").mkdir()  # Hub-configured default reviewer (priority 2) for fixtures that state none
        (self.root / "data" / "settings.json").write_text('{"default_reviewer_profile": "deepseek"}', encoding="utf8")
        self.counter = self.root / "worker-runs.txt"
        patcher = mock.patch("respected_orchestrator.engine.runner._stdin_is_tty", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def request(self, project_root=None, **workflow):
        code = f"from pathlib import Path; Path('calculator.py').write_text('value = 1' + chr(10)); open({str(self.counter)!r}, 'a').write('x')"
        check = "from pathlib import Path; assert Path('calculator.py').read_text() == 'value = 1' + chr(10)"
        return {"project_root": str(project_root or self.repo), "task": "set value to 1", "worker": "custom", "kind": "write",
                "ownership": ["calculator.py"], "command": [PY, "-c", code], "acceptance": [[PY, "-c", check]],
                "timeout_seconds": 30, "workflow": dict({"max_corrections": 0}, **workflow)}

    def worker_runs(self):
        return len(self.counter.read_text()) if self.counter.exists() else 0


class MockedReviewTests(CodingFixture):
    """Review retries against a mocked codex call: the worker result is mocked too, only review behaviour is under test."""

    def create_run(self, **workflow):
        run_id = create_task(self.ctx, self.request(**workflow))["run_id"]
        (self.ctx.run_dir(run_id) / "worker.patch").write_text("+value = 1\n", encoding="utf8")
        return run_id

    def completed(self, run_id):
        return {"run_id": run_id, "status": "completed", "changed_files": ["calculator.py"], "patch_sha256": "0" * 64,
                "checks": [{"command": ["x"], "returncode": 0}], "workspace": str(self.root), "duration_seconds": 0.1,
                "usage": {"estimated_weighted_tokens": 100}}

    def run_with(self, run_id, calls, **kwargs):
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", return_value=self.completed(run_id)), \
             mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call", side_effect=calls) as codex:
            return run_maf_coding_task(ctx=self.ctx, run_id=run_id, **kwargs), codex

    def approved(self):
        return outcome("COMPLETE", output=json.dumps({"decision": "APPROVED", "reason": "ok"}), usage={"estimated_weighted_tokens": 7})

    def test_a_review_timeout_is_retried_once_with_more_room_and_then_approved(self):
        run_id = self.create_run(reviewer_profile="deepseek")
        timeout = outcome("TIMEOUT", cause="timeout_active_at_deadline", usage={"estimated_weighted_tokens": 5})
        output, codex = self.run_with(run_id, [timeout, self.approved()])
        self.assertEqual(output["status"], "MASTER_APPROVED")
        first, second = (call.kwargs["timeout_seconds"] for call in codex.call_args_list)
        self.assertEqual((first, second), (600, 900))
        attempts = load_signed(self.ctx, self.ctx.run_dir(run_id) / "review-attempts.json")["attempts"]
        self.assertEqual([a["status"] for a in attempts], ["reviewer_timeout", "COMPLETE"])
        self.assertEqual(len({a["evidence"] for a in attempts}), 2)  # a retry never overwrites the failed review's evidence
        self.assertEqual(output["token_usage"]["estimated_weighted_tokens"], 100 + 5 + 7)  # worker + failed review + review

    def test_two_timeouts_end_as_reviewer_timeout_with_every_attempt_recorded(self):
        run_id = self.create_run(reviewer_profile="deepseek")
        timeout = outcome("TIMEOUT", cause="timeout_stalled_after_output", usage={"estimated_weighted_tokens": 5})
        output, codex = self.run_with(run_id, [timeout, timeout])
        self.assertEqual((output["status"], output["reason"]), ("FAILED", "reviewer_timeout"))
        self.assertEqual(codex.call_count, 2)  # bounded: one retry, never an endless loop
        failure = output["review_failure"]
        self.assertEqual((failure["cause"], failure["retryable"], len(failure["attempts"])), ("timeout_stalled_after_output", True, 2))
        self.assertEqual(output["token_usage"]["estimated_weighted_tokens"], 100 + 5 + 5)  # failed reviews still cost tokens
        saved = load_signed(self.ctx, self.ctx.run_dir(run_id) / "maf-result.json")
        self.assertEqual((saved["status"], saved["reason"]), ("FAILED", "reviewer_timeout"))

    def test_a_lost_connection_is_a_distinct_retryable_failure(self):
        run_id = self.create_run(reviewer_profile="deepseek")
        lost = outcome("TIMEOUT", cause="provider_disconnected")
        output, codex = self.run_with(run_id, [lost, lost])
        self.assertEqual((output["status"], output["reason"]), ("FAILED", "reviewer_disconnected"))
        self.assertEqual(codex.call_count, 2)
        recovered, _ = self.run_with(self.create_run(reviewer_profile="deepseek"), [lost, self.approved()])
        self.assertEqual(recovered["status"], "MASTER_APPROVED")

    def test_a_failed_review_that_is_not_a_timeout_or_disconnect_is_not_retried(self):
        run_id = self.create_run(reviewer_profile="deepseek")
        output, codex = self.run_with(run_id, [outcome("FAILED", cause="failed")])
        self.assertEqual((output["status"], output["reason"]), ("FAILED", "reviewer_execution_failed"))
        self.assertEqual(codex.call_count, 1)
        self.assertFalse(output["review_failure"]["retryable"])

    def test_retries_are_configurable_and_zero_means_one_attempt(self):
        run_id = self.create_run(reviewer_profile="deepseek", review_retries=0)
        output, codex = self.run_with(run_id, [outcome("TIMEOUT", cause="timeout_no_output")])
        self.assertEqual((output["reason"], codex.call_count), ("reviewer_timeout", 1))
        for bad in (-1, 3, "1", True):
            with self.assertRaises(ValueError):
                create_task(self.ctx, self.request(review_retries=bad))

    def test_a_rejection_is_final_and_never_retried_as_if_it_were_a_failure(self):
        run_id = self.create_run(reviewer_profile="deepseek")
        rejected = outcome("COMPLETE", output=json.dumps({"decision": "REJECTED", "reason": "wrong"}))
        output, codex = self.run_with(run_id, [rejected])
        self.assertEqual(output["status"], "REJECTED")
        self.assertEqual(codex.call_count, 1)


class ReviewOnlyRetryTests(CodingFixture):
    """A2 with REAL worker runs: after a review failure the coded, verified work is reviewed again, not coded again."""

    failing_review = staticmethod(timeout_review)
    approve = staticmethod(approve_review)

    def coded_and_review_failed(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        real = execute_task

        def counted(ctx, current):
            result = real(ctx, current)
            return dict(result, usage={"estimated_weighted_tokens": 100})  # a worker that spent tokens

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", side_effect=counted):
            first = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=self.failing_review)
        self.assertEqual((first["status"], first["reason"]), ("FAILED", "reviewer_timeout"))
        self.assertEqual(self.worker_runs(), 1)
        return run_id, first

    def test_review_only_retry_does_not_run_the_worker_again_and_keeps_history_and_tokens(self):
        run_id, first = self.coded_and_review_failed()
        patch_before = (self.ctx.run_dir(run_id) / "worker.patch").read_bytes()
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", side_effect=AssertionError("worker re-executed")) as worker:
            second = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=self.approve)
        worker.assert_not_called()
        self.assertEqual(second["status"], "MASTER_APPROVED")
        self.assertEqual(self.worker_runs(), 1)  # the coding was done exactly once
        self.assertEqual(len(second["attempts"]), 1)  # no duplicate attempt record
        self.assertEqual((self.ctx.run_dir(run_id) / "worker.patch").read_bytes(), patch_before)
        self.assertEqual(check_result(self.ctx, run_id)["status"], "verified")
        history = sorted((self.ctx.run_dir(run_id) / "maf-history").glob("*.json"))
        self.assertEqual(len(history), 1)  # the failed outcome is kept, not overwritten
        self.assertEqual(load_signed(self.ctx, history[0])["reason"], "reviewer_timeout")
        self.assertEqual(first["token_usage"]["estimated_weighted_tokens"], 100)  # the invocation that coded it
        self.assertEqual(second["token_usage"]["estimated_weighted_tokens"], 0)  # the retry spent no worker tokens
        self.assertEqual(second["token_usage_lifetime"]["estimated_weighted_tokens"], 100)  # and nothing is counted twice

    def test_the_retried_and_approved_patch_is_applied_once(self):
        run_id, _ = self.coded_and_review_failed()
        run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=self.approve)
        apply_task(self.ctx, run_id)
        self.assertEqual((self.repo / "calculator.py").read_text(), "value = 1\n")
        with self.assertRaisesRegex(ValueError, "already applied"):
            apply_task(self.ctx, run_id)

    def test_a_failed_review_never_makes_an_unapproved_patch_acceptable(self):
        run_id, _ = self.coded_and_review_failed()
        with self.assertRaisesRegex(ValueError, "MAF approval is required"):
            check_result(self.ctx, run_id)

    def test_a_tampered_patch_is_not_reused_and_not_approved(self):
        run_id, _ = self.coded_and_review_failed()
        patch = self.ctx.run_dir(run_id) / "worker.patch"
        patch.write_bytes(patch.read_bytes() + b"tampered")
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", side_effect=AssertionError("worker re-executed")):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=self.approve)
        self.assertEqual((output["status"], output["reason"]), ("FAILED", "reuse_verification_failed"))
        self.assertEqual(self.worker_runs(), 1)
        saved = load_signed(self.ctx, self.ctx.run_dir(run_id) / "maf-result.json")
        self.assertNotEqual(saved["status"], "MASTER_APPROVED")

    def test_a_project_that_changed_meanwhile_is_not_reused(self):
        run_id, _ = self.coded_and_review_failed()
        (self.repo / "unrelated.txt").write_text("someone else's edit\n", encoding="utf8")
        output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=self.approve)
        self.assertEqual((output["status"], output["reason"]), ("FAILED", "reuse_verification_failed"))
        self.assertEqual(self.worker_runs(), 1)

    def test_a_failed_worker_is_not_pretended_to_be_reusable(self):
        request = self.request()
        request["acceptance"] = [[PY, "-c", "raise SystemExit(1)"]]
        run_id = create_task(self.ctx, request)["run_id"]
        first = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=self.approve)
        second = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=self.approve)
        self.assertEqual((first["reason"], second["reason"]), ("worker_failed", "worker_failed"))
        self.assertEqual(self.worker_runs(), 1)  # the terminal failed run is not executed again either


class ProjectReviewOnlyRetryTests(CodingFixture):
    """The supervisor: a lane whose review failed is continued in place on the next attempt."""

    def test_the_second_attempt_resumes_the_lane_and_the_worker_runs_once(self):
        lane = {"name": "lane", "after": [], "request": self.request(project_root=self.repo)}
        phase = {"name": "p", "after": [], "workstreams": [lane], "auto_apply": True, "verify": []}
        project_id, _ = project.create_project(self.ctx, dict(goal="demo", phases=[phase], budget={"max_phase_attempts": 2}))
        roots = []

        def lane_runner(lane_ctx, run_id):
            roots.append(str(lane_ctx.data_root))
            return run_maf_coding_task(ctx=lane_ctx, run_id=run_id, reviewer=timeout_review if len(roots) == 1 else approve_review)

        def run(ctx, campaign_id, timeout, cancel):
            campaign.run_campaign(ctx, campaign_id, lane_runner=lane_runner)

        state = project.run_project(self.ctx, project_id, campaign_runner=run)
        self.assertEqual(state["status"], "completed", state)
        attempts = state["phases"]["p"]["attempts"]
        self.assertEqual([a["outcome"] for a in attempts], ["failed", "done"])
        self.assertIn("reviewer_timeout", attempts[0]["note"])
        self.assertEqual(roots[0], roots[1])  # the same lane data root: its run, patch and evidence were continued
        self.assertEqual(self.worker_runs(), 1)  # coded once across both attempts
        self.assertEqual((self.repo / "calculator.py").read_text(), "value = 1\n")
        self.assertEqual(state["weighted_tokens"], sum(a["weighted_tokens"] for a in attempts))  # tokens counted once each

    def test_a_resume_root_outside_this_data_root_is_refused(self):
        lane = {"name": "lane", "after": [], "resume_lane_data_root": str(self.root / "elsewhere"),
                "request": self.request(project_root=self.repo)}
        campaign_id, _ = campaign.create_campaign(self.ctx, {"goal": "x", "workstreams": [lane], "final": {"skip": True}})
        called = []
        result = campaign.run_campaign(self.ctx, campaign_id, lane_runner=lambda *args: called.append(args))
        self.assertEqual(called, [])
        self.assertEqual((result["lanes"][0]["status"], result["lanes"][0]["reason"]), ("FAILED", "lane_error"))


if __name__ == "__main__":
    unittest.main()
