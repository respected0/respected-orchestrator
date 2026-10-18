"""Replay Windows sandbox failures without Git, a sandbox refresh or an AI call."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from respected_orchestrator import antigravity_orchestrator as agy, runner
from respected_orchestrator.context import EngineContext


def codex_stream(status="blocked"):
    # Shape observed in run-20261009214208-56fa8b626e7e; no private paths.
    return "\n".join(json.dumps(event) for event in [
        {"type": "thread.started", "thread_id": "fixture"},
        {"type": "item.completed", "item": {"type": "error", "message": "Model metadata not found"}},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Inspect the worktree"}},
        *[{"type": "item.completed", "item": {"type": "command_execution", "exit_code": -1,
           "aggregated_output": "helper_unknown_error: setup refresh had errors"}} for _ in range(2)],
        {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps({
            "status": status, "root_cause": "PowerShell process creation failed twice",
            "files_changed": [], "checks": [{"result": "not run"}],
        })}},
        {"type": "turn.completed"},
    ])


class CodexResultTests(unittest.TestCase):
    def test_explicit_failure_overrides_zero_exit(self):
        for payload in ({"status": "blocked"}, {"status": "failed"}, {"status": "pending"},
                        {"status": "ok", "error": "runtime failure"}):
            with self.subTest(payload=payload):
                self.assertIs(agy.classify_worker_exit(0, json.dumps(payload), "", False),
                              agy.RunStatus.WORKER_FAILED)

    def test_provider_errors_and_success_keep_their_classification(self):
        for payload, expected in [
            ({"status": "blocked", "error": "rate limit"}, agy.RunStatus.LIMIT_EXHAUSTED),
            ({"status": "failed", "error": "login required"}, agy.RunStatus.AUTH_REQUIRED),
            ({"status": "success", "remaining_risks": ["quota authentication required"]}, agy.RunStatus.COMPLETE),
        ]:
            with self.subTest(payload=payload):
                self.assertIs(agy.classify_worker_exit(0, json.dumps(payload), "", False), expected)
        self.assertIs(agy.classify_worker_exit(1, '{"status":"success"}', "", False), agy.RunStatus.WORKER_FAILED)
        self.assertIs(agy.classify_worker_exit(0, '{"status":"success"}', "", True), agy.RunStatus.TIMEOUT)

    def test_metadata_warning_does_not_override_final_result(self):
        self.assertEqual(runner._codex_payload(codex_stream())["status"], "blocked")
        self.assertEqual(runner._codex_payload(codex_stream("success"))["status"], "success")

    def test_incomplete_or_failed_stream_is_rejected(self):
        for stream in ("", "not json", "[]", codex_stream().rsplit("\n", 1)[0],
                       '{"type":"error"}\n' + codex_stream("success"),
                       codex_stream("success") + '\n{"type":"turn.failed"}'):
            with self.subTest(stream=stream):
                self.assertEqual(runner._codex_payload(stream)["status"], "failed")

    def test_transient_reconnect_notice_does_not_invalidate_a_completed_turn(self):
        notice = '{"type":"error","message":"Reconnecting... 1/5 (stream disconnected before completion)"}' + "\n"
        self.assertEqual(runner._codex_payload(notice + codex_stream("success"))["status"], "success")
        before_completion = codex_stream("success").rsplit("\n", 1)[0]
        self.assertEqual(runner._codex_payload(
            notice + before_completion + "\n" + '{"type":"turn.completed"}')["status"], "success")
        fatal = '{"type":"error","message":"fatal"}' + "\n"
        failed = "\n" + '{"type":"turn.failed"}'
        non_string = '{"type":"error","message":["Reconnecting..."]}' + "\n"
        variant = '{"type":"error","message":" reconnecting... 1/5"}' + "\n"
        for stream in (notice + fatal + codex_stream("success"),
                       notice + codex_stream("success") + failed,
                       notice + codex_stream().rsplit("\n", 1)[0],
                       codex_stream("success") + notice,
                       non_string + codex_stream("success"),
                       variant + codex_stream("success"),
                       notice + codex_stream("success") + "\n" + '{"type":"turn.completed"}'):
            with self.subTest(stream=stream):
                self.assertEqual(runner._codex_payload(stream)["status"], "failed")

    def test_blocked_worker_is_signed_and_never_reaches_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            ctx = EngineContext(root / "data")
            run_id = "run-blocked-fixture"
            directory = ctx.run_dir(run_id)
            directory.mkdir(parents=True)
            workspace = ctx.workspace_root / run_id
            workspace.mkdir(parents=True)
            lane = agy.Lane(project, workspace, "fixture", directory, "fixture-baseline")
            runner._save(ctx, directory / "request.json", dict(
                run_id=run_id, project_root=str(project), project_fingerprint="fixture",
                timeout_seconds=10, kind="write", task="Implement add", worker="custom",
                command=["codex.exe", "exec", "--json", "{prompt}"],
                ownership=["calculator.py"], forbidden=["secret.txt"],
                acceptance=[["acceptance-must-not-run"]], include_untracked=[],
            ))
            runner._save(ctx, directory / "status.json", {"status": "queued"})
            with mock.patch.object(runner, "project_fingerprint", return_value="fixture"), \
                    mock.patch.object(agy, "create_lane", return_value=lane), \
                    mock.patch.object(agy, "overlay_dirty_inputs"), \
                    mock.patch.object(agy, "commit_lane_baseline"), \
                    mock.patch.object(runner, "execute", return_value=subprocess.CompletedProcess(
                        ["codex.exe"], 0, codex_stream(), "failed to decode models response")) as execute, \
                    mock.patch.object(agy, "collect_worker_changes") as collect:
                result = runner.execute_task(ctx, run_id)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["reason"], "worker_failed")
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["provider_status"], "WORKER_FAILED")
            self.assertEqual(runner._load(ctx, directory / "status.json"), result)
            execute.assert_called_once()
            collect.assert_not_called()
            self.assertEqual(execute.call_args.args[1], workspace)
            self.assertEqual(execute.call_args.args[0][-1], (directory / "brief.md").read_text(encoding="utf8"))
            self.assertFalse((directory / "check-1.log").exists())
            self.assertFalse((directory / "result.json").exists())
            self.assertFalse((directory / "worker.patch").exists())
            self.assertFalse((ctx.state_dir / ".write-worker.lock.json").exists())

    def test_windows_codex_prefers_project_runtime_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "codex.exe"
            executable.touch()
            with mock.patch.object(runner, "LOCAL_CODEX", executable), \
                    mock.patch.object(runner.sys, "platform", "win32"), \
                    mock.patch.object(runner.shutil, "which", return_value="installed-codex"):
                self.assertEqual(runner.get_cli_command("codex"), [str(executable)])
                self.assertEqual(runner.get_cli_command("claude"), ["installed-codex"])
            with mock.patch.object(runner, "LOCAL_CODEX", Path(temporary) / "absent.exe"), \
                    mock.patch.object(runner.sys, "platform", "win32"), \
                    mock.patch.object(runner.shutil, "which", return_value="installed-codex"):
                self.assertEqual(runner.get_cli_command("codex"), ["installed-codex"])
            with mock.patch.object(runner.sys, "platform", "linux"), \
                    mock.patch.object(runner.shutil, "which", return_value="installed-codex"):
                self.assertEqual(runner.get_cli_command("codex"), ["installed-codex"])


if __name__ == "__main__":
    unittest.main()
