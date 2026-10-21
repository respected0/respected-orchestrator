import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
import io
from unittest import mock

from agent_framework import InMemoryCheckpointStorage

from respected_orchestrator.context import EngineContext
from respected_orchestrator.__main__ import main
from respected_orchestrator.workflows.maf_workflow import run_maf_coding_task
from respected_orchestrator.engine.runner import approve_maf_task, check_result, create_task, inspect_task
from respected_orchestrator.engine.codex import CodexOutcome


class MafCodingTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")]:
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        (self.repo / "calculator.py").write_text("value = 0\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "fixture baseline"], cwd=self.repo,
                       capture_output=True, check=True)
        self.ctx = EngineContext(self.root / "data")
        # Hub-configured default (priority 2): fixtures that state no reviewer get this one.
        (self.root / "data").mkdir()
        (self.root / "data" / "settings.json").write_text(json.dumps({"default_reviewer_profile": "deepseek"}), encoding="utf8")
        patcher = mock.patch("respected_orchestrator.engine.runner._stdin_is_tty", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create_run(self, *, command=None, acceptance=None, **workflow) -> str:
        request = {
            "project_root": str(self.repo),
            "task": "fixture coding task",
            "worker": "custom",
            "kind": "write",
            "ownership": ["calculator.py"],
            "forbidden": ["outside.txt"],
            "command": command or [sys.executable, "-c", "print('fixture worker')"],
            "acceptance": acceptance or [[sys.executable, "-c", "assert True"]],
            "timeout_seconds": 10,
        }
        if workflow:
            request["workflow"] = workflow
        run_id = create_task(self.ctx, request)["run_id"]
        (self.ctx.run_dir(run_id) / "worker.patch").write_text("+value = 1\n", encoding="utf8")
        return run_id

    def completed_result(self, run_id: str) -> dict[str, object]:
        return {
            "run_id": run_id,
            "status": "completed",
            "changed_files": ["calculator.py"],
            "checks": [{"command": ["python", "-m", "unittest"], "returncode": 0}],
            "patch_sha256": "0" * 64,
            "workspace": str(self.root / "workspace"),
            "duration_seconds": 0.1,
        }

    def test_completed_coding_task_returns_master_approval(self) -> None:
        run_id = self.create_run()
        result = self.completed_result(run_id)
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        return_value=result) as execute:
            output = run_maf_coding_task(
                ctx=self.ctx, run_id=run_id,
                reviewer=lambda results: {"decision": "APPROVED"},
            )

        self.assertEqual(output["status"], "MASTER_APPROVED")
        self.assertEqual(output["final_run_id"], run_id)
        self.assertEqual(output["attempts"][0]["engine_result"], result)
        execute.assert_called_once_with(self.ctx, run_id)

    def test_failed_coding_task_is_not_approved(self) -> None:
        run_id = self.create_run()
        result = {"status": "failed", "reason": "test_failed", "changed_files": [],
                  "checks": [{"returncode": 1}]}
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", return_value=result):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id)

        self.assertEqual(output["status"], "FAILED")
        self.assertEqual(output["reason"], "worker_failed")

    def test_checkpoint_resume_does_not_duplicate_completed_execution(self) -> None:
        run_id = self.create_run()
        storage = InMemoryCheckpointStorage()
        calls: list[str] = []

        def fake_execute(ctx, current_run_id):
            calls.append(current_run_id)
            return self.completed_result(current_run_id)

        approve = lambda results: {"decision": "APPROVED"}

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        side_effect=fake_execute):
            first = run_maf_coding_task(ctx=self.ctx, run_id=run_id,
                                        checkpoint_storage=storage,
                                        reviewer=approve)
            second = run_maf_coding_task(ctx=self.ctx, run_id=run_id,
                                         checkpoint_storage=storage,
                                         resume_checkpoint_id=first["checkpoint_id"],
                                         reviewer=approve)

        self.assertEqual(first["status"], "MASTER_APPROVED")
        self.assertEqual(second["status"], "MASTER_APPROVED")
        self.assertEqual(calls, [run_id])
        self.assertEqual(second["attempts"], first["attempts"])

    def test_correction_uses_a_new_isolated_run_and_re_review_approves(self) -> None:
        run_id = self.create_run(max_corrections=1)

        def fake_execute(ctx, current_run_id):
            return self.completed_result(current_run_id)

        def reviewer(results):
            if results["coding"].get("correction"):
                return {"decision": "APPROVED"}
            return {"decision": "NEEDS_CHANGES",
                    "corrections": {"coding": "fix the failing assertion"}}

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        side_effect=fake_execute):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["status"], "MASTER_APPROVED")
        self.assertEqual(len(output["attempts"]), 2)
        self.assertNotEqual(output["final_run_id"], run_id)
        child = inspect_task(self.ctx, output["final_run_id"])["request"]
        self.assertEqual(child["correction_of"], run_id)
        self.assertEqual(child["correction_round"], 1)
        self.assertIn("Independent reviewer correction: fix the failing assertion", child["task"])
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")

    def test_correction_inherits_verified_patch_in_new_worktrees(self) -> None:
        command = [sys.executable, "-c",
                   "from pathlib import Path; Path('calculator.py').write_text('value = 1\\n', encoding='utf8')"]
        acceptance = [[sys.executable, "-c",
                       "from pathlib import Path; assert Path('calculator.py').read_text(encoding='utf8') == 'value = 1\\n'"]]
        run_id = self.create_run(max_corrections=2, command=command, acceptance=acceptance)
        reviews = 0

        def reviewer(results):
            nonlocal reviews
            reviews += 1
            if reviews < 3:
                return {"decision": "NEEDS_CHANGES", "corrections": {"coding": "keep prior work"}}
            return {"decision": "APPROVED"}

        output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["status"], "MASTER_APPROVED")
        self.assertEqual(len(output["attempts"]), 3)
        attempts = output["attempts"]
        self.assertNotEqual(attempts[0]["run_id"], attempts[1]["run_id"])
        self.assertNotEqual(attempts[1]["run_id"], attempts[2]["run_id"])
        first_child = inspect_task(self.ctx, attempts[1]["run_id"])["request"]
        second_child = inspect_task(self.ctx, attempts[2]["run_id"])["request"]
        self.assertEqual(first_child["inherited_patch_run_id"], run_id)
        self.assertEqual(second_child["inherited_patch_run_id"], attempts[1]["run_id"])
        workspaces = [attempt["engine_result"]["workspace"] for attempt in attempts]
        self.assertEqual(len(workspaces), len(set(workspaces)))
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")
        verified = check_result(self.ctx, output["final_run_id"])
        self.assertEqual(verified["changed_files"], ["calculator.py"])

    def test_escalation_hands_code_to_glm_and_deepseek_reviews_it(self) -> None:
        command = [sys.executable, "-c",
                   "from pathlib import Path; Path('calculator.py').write_text('value = 1\\n', encoding='utf8')"]
        acceptance = [[sys.executable, "-c",
                       "from pathlib import Path; assert Path('calculator.py').read_text(encoding='utf8') == 'value = 1\\n'"]]
        run_id = create_task(self.ctx, {
            "project_root": str(self.repo), "task": "t", "worker": "custom", "kind": "write",
            "ownership": ["calculator.py"], "command": command, "acceptance": acceptance, "timeout_seconds": 20,
            "worker_profile": "deepseek",
            "workflow": {"reviewer_profile": "glm", "escalate_profile": "glm", "max_corrections": 2},
        })["run_id"]
        seen = []

        def fake_review(**kwargs):
            seen.append(kwargs["profile"])
            if len(seen) < 3:
                return {"decision": "NEEDS_CHANGES", "corrections": {"coding": "again"}, "stage": "fast",
                        "profile": kwargs["profile"]}
            return {"decision": "APPROVED", "stage": "fast", "profile": kwargs["profile"]}

        with mock.patch("respected_orchestrator.workflows.maf_workflow._run_codex_review", side_effect=fake_review):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id)

        self.assertEqual(output["status"], "MASTER_APPROVED")
        self.assertEqual(seen, ["glm", "glm", "deepseek"])
        self.assertEqual([a["implementer"] for a in output["attempts"]], ["deepseek", "deepseek", "glm"])
        final = inspect_task(self.ctx, output["final_run_id"])["request"]
        self.assertEqual(final["worker_profile"], "glm")
        self.assertEqual(final["workflow"]["reviewer_profile"], "deepseek")
        self.assertEqual(final["correction_of"], run_id)

    def test_assigned_debugger_takes_the_correction_round(self) -> None:
        command = [sys.executable, "-c",
                   "from pathlib import Path; Path('calculator.py').write_text('value = 1\\n', encoding='utf8')"]
        acceptance = [[sys.executable, "-c",
                       "from pathlib import Path; assert Path('calculator.py').read_text(encoding='utf8') == 'value = 1\\n'"]]
        run_id = create_task(self.ctx, {
            "project_root": str(self.repo), "task": "t", "worker": "custom", "kind": "write",
            "ownership": ["calculator.py"], "command": command, "acceptance": acceptance, "timeout_seconds": 20,
            "worker_profile": "impl", "roles": {"debugger": {"tool": "custom", "profile": "dbg"}},
            "workflow": {"reviewer_profile": "rev", "max_corrections": 1},
        })["run_id"]
        answers = iter([{"decision": "NEEDS_CHANGES", "corrections": {"coding": "again"}, "stage": "fast", "profile": "rev"},
                        {"decision": "APPROVED", "stage": "fast", "profile": "rev"}])
        with mock.patch("respected_orchestrator.workflows.maf_workflow._run_codex_review", side_effect=lambda **kw: next(answers)):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id)
        self.assertEqual(output["status"], "MASTER_APPROVED")
        self.assertEqual([a["implementer"] for a in output["attempts"]], ["impl", "dbg"])
        self.assertEqual(inspect_task(self.ctx, output["final_run_id"])["request"]["worker_profile"], "dbg")

    def test_approval_refuses_non_interactive_callers(self) -> None:
        run_id = self.approvable_run()
        with mock.patch("respected_orchestrator.engine.runner._stdin_is_tty", return_value=False), \
                self.assertRaisesRegex(ValueError, "interactive"):
            approve_maf_task(self.ctx, run_id)

    def test_correction_rejects_tampered_previous_patch(self) -> None:
        command = [sys.executable, "-c",
                   "from pathlib import Path; Path('calculator.py').write_text('value = 1\\n', encoding='utf8')"]
        acceptance = [[sys.executable, "-c", "assert True"]]
        run_id = self.create_run(max_corrections=1, command=command, acceptance=acceptance)

        def reviewer(results):
            patch_path = self.ctx.run_dir(run_id) / "worker.patch"
            patch_path.write_bytes(patch_path.read_bytes() + b"tampered\n")
            return {"decision": "NEEDS_CHANGES", "corrections": {"coding": "fix safely"}}

        output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["status"], "FAILED")
        final = output["attempts"][-1]
        self.assertEqual(final["engine_result"]["reason"], "engine_error")
        self.assertIn("tampered", final["engine_result"]["error"])

    def test_correction_retry_limit_is_bounded_at_two(self) -> None:
        run_id = self.create_run(max_corrections=2)

        def reviewer(results):
            return {"decision": "NEEDS_CHANGES", "corrections": {"coding": "try again"}}

        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        side_effect=lambda ctx, current: self.completed_result(current)):
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=reviewer)

        self.assertEqual(output["status"], "NEEDS_CHANGES")
        self.assertEqual(len(output["attempts"]), 3)
        self.assertEqual(output["review_decisions"], ["NEEDS_CHANGES"] * 3)

    def test_token_usage_sums_worker_and_reviewer_without_double_counting_cache(self) -> None:
        run_id = self.create_run()
        result = self.completed_result(run_id)
        result["usage"] = {"raw_input_tokens": 100, "cached_input_tokens": 100,
                           "output_tokens": 20, "reasoning_tokens": 5,
                           "estimated_weighted_tokens": 23}
        review_usage = {"raw_input_tokens": 110, "cached_input_tokens": 10,
                        "output_tokens": 15, "reasoning_tokens": 5,
                        "estimated_weighted_tokens": 115}
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", return_value=result):
            output = run_maf_coding_task(
                ctx=self.ctx, run_id=run_id,
                reviewer=lambda results: {"decision": "APPROVED", "usage": review_usage},
            )

        self.assertEqual(output["token_usage"], {
            "raw_input_tokens": 210,
            "cached_input_tokens": 110,
            "output_tokens": 35,
            "reasoning_tokens": 10,
            "estimated_weighted_tokens": 138,
        })

    def _codex_outcome(self, payload: dict[str, object]) -> CodexOutcome:
        return CodexOutcome(
            status="COMPLETE", output=json.dumps(payload), usage={},
            events_path=self.root / "events.jsonl", stdout_path=self.root / "stdout.log",
            stderr_path=self.root / "stderr.log",
        )

    def test_reviewer_prompt_includes_bounded_patch_preview(self) -> None:
        run_id = self.create_run(max_corrections=0)
        (self.ctx.run_dir(run_id) / "worker.patch").write_text("+MARKER\n" + "x" * 9000, encoding="utf8")
        outcome = self._codex_outcome({"decision": "APPROVED", "reason": "ok"})
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        return_value=self.completed_result(run_id)), \
             mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call", return_value=outcome) as codex_call:
            run_maf_coding_task(ctx=self.ctx, run_id=run_id)
        prompt = codex_call.call_args.args[0].prompt
        self.assertIn("+MARKER", prompt)
        self.assertLess(len(prompt), 9000)

    def test_review_requires_deterministic_evidence_and_states_criteria(self) -> None:
        for bad_checks in ([], [{"command": ["x"], "returncode": 1}]):
            run_id = self.create_run(max_corrections=0)  # a re-invoked run resumes its history, so each case is its own run
            bad = dict(self.completed_result(run_id), checks=bad_checks)
            with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task", return_value=bad),                  mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call") as codex_call:
                output = run_maf_coding_task(ctx=self.ctx, run_id=run_id)
            self.assertEqual(output["status"], "FAILED")
            codex_call.assert_not_called()
        run_id = self.create_run(max_corrections=0)
        outcome = self._codex_outcome({"decision": "APPROVED", "reason": "ok"})
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        return_value=self.completed_result(run_id)),              mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call", return_value=outcome) as codex_call:
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id)
        self.assertEqual(output["status"], "MASTER_APPROVED")
        prompt = codex_call.call_args.args[0].prompt
        self.assertIn("returncode 0", prompt)
        self.assertIn("Do not demand evidence about how the worker worked", prompt)

    def test_stalled_reviewer_is_capped_and_never_approves(self) -> None:
        run_id = self.create_run(max_corrections=0, review_timeout_seconds=7)
        stalled = CodexOutcome(status="TIMEOUT", output="", usage={}, events_path=self.root / "e.jsonl",
                               stdout_path=self.root / "o.log", stderr_path=self.root / "s.log")
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        return_value=self.completed_result(run_id)), \
             mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call", return_value=stalled) as codex_call:
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id)
        self.assertEqual(output["status"], "FAILED")
        self.assertEqual(output["reason"], "reviewer_timeout")
        first, retry = (call.kwargs["timeout_seconds"] for call in codex_call.call_args_list)
        self.assertLessEqual(first, 7)  # the explicit ceiling caps the first attempt
        self.assertLessEqual(retry, 7 * 1.5 + 0.5)  # one bounded retry with slightly more room, never unbounded
        for bad in (0, 3601, "5", True):
            with self.assertRaises(ValueError):
                self.create_run(review_timeout_seconds=bad)

    def test_optional_deep_review_routes_before_approval(self) -> None:
        run_id = self.create_run(deep_review="always", reviewer_profile="independent",
                                 deep_review_profile="deep", max_corrections=0)
        outcomes = [
            self._codex_outcome({"decision": "APPROVED", "reason": "fast evidence is bounded"}),
            self._codex_outcome({"decision": "APPROVED", "reason": "deep evidence is bounded"}),
        ]
        with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                        return_value=self.completed_result(run_id)), \
             mock.patch("respected_orchestrator.workflows.maf_workflow.run_codex_call",
                        side_effect=outcomes) as codex_call:
            output = run_maf_coding_task(ctx=self.ctx, run_id=run_id)

        self.assertEqual(output["status"], "MASTER_APPROVED")
        self.assertEqual(codex_call.call_count, 2)
        self.assertEqual(output["reviews"][0]["stage"], "fast")
        self.assertEqual(output["reviews"][0]["deep_review"]["stage"], "deep")
        self.assertEqual(output["reviews"][0]["deep_review"]["profile"], "deep")

    def test_human_approval_is_not_automatically_accepted(self) -> None:
        run_id = self.create_run(human_approval=True, max_corrections=0)
        output = run_maf_coding_task(
            ctx=self.ctx, run_id=run_id,
            reviewer=lambda results: {"decision": "APPROVED"},
        )

        self.assertEqual(output["status"], "HUMAN_APPROVAL_REQUIRED")
        with self.assertRaisesRegex(ValueError, "MAF approval"):
            check_result(self.ctx, run_id)
        approval = approve_maf_task(self.ctx, run_id)
        self.assertEqual(approval["root_run_id"], run_id)
        self.assertEqual(check_result(self.ctx, run_id)["status"], "verified")

    def test_invalid_human_approvals_are_rejected(self) -> None:
        run_id = self.create_run(human_approval=True, max_corrections=0)
        run_maf_coding_task(ctx=self.ctx, run_id=run_id,
                            reviewer=lambda results: {"decision": "APPROVED"})
        path = self.ctx.run_dir(run_id) / "maf-approval.json"
        valid = approve_maf_task(self.ctx, run_id)
        signed = json.loads(path.read_text(encoding="utf8"))
        tampered = json.loads(json.dumps(signed))
        tampered["payload"]["approved_at"] = "2000-01-01"
        wrong_run = {"payload": {**valid, "root_run_id": "other"}, "signature": signed["signature"]}
        for body in ("not signed", "{", "[]", json.dumps({"payload": valid}),
                     json.dumps({"payload": valid, "signature": "bad"}),
                     json.dumps(tampered), json.dumps(wrong_run)):
            path.write_text(body, encoding="utf8")
            with self.assertRaises(ValueError, msg=body):
                check_result(self.ctx, run_id)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "MAF approval"):
            check_result(self.ctx, run_id)

    def test_cross_run_approval_is_rejected(self) -> None:
        run_id = self.create_run(human_approval=True, max_corrections=0)
        run_maf_coding_task(ctx=self.ctx, run_id=run_id,
                            reviewer=lambda results: {"decision": "APPROVED"})
        approve_maf_task(self.ctx, run_id)
        path = self.ctx.run_dir(run_id) / "maf-approval.json"
        from respected_orchestrator.engine.evidence import save_signed
        save_signed(self.ctx, path, dict(run_id="run-other", root_run_id=run_id, approved_at="x"))
        with self.assertRaisesRegex(ValueError, "does not belong"):
            check_result(self.ctx, run_id)

    def approvable_run(self) -> str:
        run_id = self.create_run(human_approval=True, max_corrections=0)
        run_maf_coding_task(ctx=self.ctx, run_id=run_id, reviewer=lambda results: {"decision": "APPROVED"})
        return run_id

    def test_approval_is_bound_to_patch_immutable_and_operator_only(self) -> None:
        run_id = self.approvable_run()
        with mock.patch.dict("os.environ", {"RESPECTED_ORCH_CHILD": "1"}), \
                self.assertRaisesRegex(ValueError, "operator"):
            approve_maf_task(self.ctx, run_id)
        approval = approve_maf_task(self.ctx, run_id)
        self.assertEqual(len(approval["patch_sha256"]), 64)
        self.assertTrue(approval["approved_by"])
        with self.assertRaisesRegex(ValueError, "immutable"):
            approve_maf_task(self.ctx, run_id)

    def test_approval_without_patch_binding_or_for_tampered_result_is_rejected(self) -> None:
        from respected_orchestrator.engine.evidence import save_signed
        run_id = self.approvable_run()
        path = self.ctx.run_dir(run_id) / "maf-approval.json"
        save_signed(self.ctx, path, dict(run_id=run_id, root_run_id=run_id, approved_at="x"))
        with self.assertRaisesRegex(ValueError, "not bound"):
            check_result(self.ctx, run_id)
        path.unlink()
        (self.ctx.run_dir(run_id) / "worker.patch").write_text("+value = 2\n", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "intact"):
            approve_maf_task(self.ctx, run_id)

    def test_budget_reserves_review_room_and_honours_explicit_hard_cap(self) -> None:
        for workflow, total, source in (
                (dict(reviewer_profile="glm", max_corrections=0), 10 + 900 + 1350, "derived"),  # first attempt + one longer retry
                (dict(reviewer_profile="deepseek", max_corrections=1), (10 + 600 + 900) * 2, "derived"),
                (dict(max_corrections=0, timeout_seconds=40), 40, "explicit")):
            run_id = self.create_run(**workflow)
            with mock.patch("respected_orchestrator.workflows.maf_workflow.execute_task",
                            return_value=self.completed_result(run_id)):
                output = run_maf_coding_task(ctx=self.ctx, run_id=run_id,
                                             reviewer=lambda results: {"decision": "APPROVED"})
            self.assertEqual((output["budget"]["total_seconds"], output["budget"]["total_source"]), (total, source))

    def test_invalid_reviewer_output_blocks_deterministic_acceptance(self) -> None:
        run_id = self.create_run(max_corrections=0)
        output = run_maf_coding_task(
            ctx=self.ctx, run_id=run_id,
            reviewer=lambda results: {"decision": "SHIP_IT"},
        )

        self.assertEqual(output["status"], "FAILED")
        self.assertEqual(output["reason"], "invalid_review_result")
        with self.assertRaisesRegex(ValueError, "MAF approval"):
            check_result(self.ctx, run_id)

    def test_private_json_entrypoint_routes_maf_and_human_approval(self) -> None:
        output = io.StringIO()
        with mock.patch("respected_orchestrator.workflows.maf_workflow.run_maf_coding_task",
                        return_value={"status": "MASTER_APPROVED"}) as maf, \
             redirect_stdout(output):
            exit_code = main(["--data-root", str(self.ctx.data_root), "maf", "run-fake-coding"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), {"status": "MASTER_APPROVED"})
        maf.assert_called_once_with(ctx=self.ctx, run_id="run-fake-coding")

        output = io.StringIO()
        approval = {"run_id": "run-fake-coding", "root_run_id": "run-fake-coding"}
        with mock.patch("respected_orchestrator.engine.runner.approve_maf_task",
                        return_value=approval) as approve, \
             redirect_stdout(output):
            exit_code = main(["--data-root", str(self.ctx.data_root),
                              "maf-approve", "run-fake-coding"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue()), approval)
        approve.assert_called_once_with(self.ctx, "run-fake-coding")


if __name__ == "__main__":
    unittest.main()
