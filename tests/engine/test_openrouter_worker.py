import io
import subprocess
import sys
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import openrouter_worker, runner
from respected_orchestrator.engine.provider import ProviderError
from respected_orchestrator.engine.provider_policy import ProviderDenied
from respected_orchestrator.workflows import roles


def run_main(argv, complete):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(openrouter_worker.ProviderClient, "complete", complete), \
            mock.patch.object(openrouter_worker, "vault", return_value=None), \
            redirect_stdout(out), redirect_stderr(err):
        code = openrouter_worker.main(argv)
    return code, out.getvalue(), err.getvalue()


class OpenRouterWorkerTests(unittest.TestCase):
    def test_success_prints_the_envelope_that_tool_result_reads(self):
        reply = {"content": "APPROVED", "model": "x/y:free", "usage": {"prompt_tokens": 10, "completion_tokens": 4,
                                                                      "prompt_tokens_details": {"cached_tokens": 2}}}
        seen = {}

        def complete(self, **kwargs):
            seen.update(kwargs)
            return reply
        code, out, _ = run_main(["x/y:free", "hello"], complete)
        self.assertEqual((code, seen["model"], seen["messages"]), (0, "x/y:free", [{"role": "user", "content": "hello"}]))
        text, usage, model, error = runner.tool_result("openrouter", out)
        self.assertEqual((text, model, error), ("APPROVED", "x/y:free", None))
        self.assertEqual((usage["raw_input_tokens"], usage["cached_input_tokens"], usage["output_tokens"]), (10, 2, 4))

    def test_unknown_usage_stays_unknown(self):
        text, usage, _, _ = runner.tool_result("openrouter", json.dumps({"type": "openrouter", "content": "ok", "model": "m", "usage": None}))
        self.assertEqual((text, usage), ("ok", None))

    def test_failures_exit_1_without_a_success_envelope(self):
        for error in (ProviderDenied("provider network opt-in is off"), ProviderError("rate_limited", status=429, retryable=True)):
            def complete(self, **kwargs):
                raise error
            code, out, err = run_main(["m", "p"], complete)
            self.assertEqual((code, out), (1, ""))
            self.assertTrue(err.strip())

    def test_rate_limits_are_retried_a_bounded_number_of_times_and_never_denials(self):
        calls = []

        def flaky(self, **kwargs):
            calls.append(1)
            if len(calls) < 3:
                raise ProviderError("rate_limited", status=429, retryable=True)
            return {"content": "ok", "model": "m", "usage": None}
        with mock.patch.object(openrouter_worker.time, "sleep") as sleep:
            code, out, _ = run_main(["m", "p"], flaky)
        self.assertEqual((code, len(calls), sleep.call_count), (0, 3, 2))
        calls.clear()

        def always(self, **kwargs):
            calls.append(1)
            raise ProviderError("rate_limited", status=429, retryable=True)
        with mock.patch.object(openrouter_worker.time, "sleep"):
            code, out, err = run_main(["m", "p"], always)
        self.assertEqual((code, len(calls), out), (1, 3, ""))
        self.assertIn("rate_limited", err)
        calls.clear()

        def denied(self, **kwargs):
            calls.append(1)
            raise ProviderDenied("off")
        self.assertEqual((run_main(["m", "p"], denied)[0], len(calls)), (1, 1))

    def test_bad_usage_is_exit_2(self):
        self.assertEqual(run_main(["only-a-model"], lambda self, **k: {})[0], 2)
        self.assertEqual(run_main(["", "p"], lambda self, **k: {})[0], 2)


class OpenRouterWiringTests(unittest.TestCase):
    def test_available_only_with_a_stored_key_and_command_carries_model_and_prompt(self):
        with tempfile.TemporaryDirectory() as root:
            store = mock.Mock(path=Path(root) / "provider-key.dpapi")
            with mock.patch("respected_orchestrator.engine.openrouter_worker.vault", return_value=store):
                self.assertIsNone(runner.get_cli_command("openrouter"))
                self.assertFalse(runner.tool_available("openrouter"))
                store.path.write_bytes(b"x")
                self.assertTrue(runner.tool_available("openrouter"))
                command = runner.command_for("openrouter", "the prompt", profile="m/n:free")
        self.assertEqual(command[-3:], ["_openrouter", "m/n:free", "the prompt"])
        with mock.patch.object(runner, "get_cli_command", return_value=["tool"]):
            with self.assertRaises(runner.lanes.WorkerUnavailableError):
                runner.command_for("openrouter", "p")

    def test_health_resolution_counts_openrouter_only_with_a_key(self):
        from respected_orchestrator.engine import clis
        with tempfile.TemporaryDirectory() as root:
            store = mock.Mock(path=Path(root) / "provider-key.dpapi")
            with mock.patch("respected_orchestrator.engine.openrouter_worker.vault", return_value=store):
                self.assertNotIn("openrouter", clis.resolve(["openrouter"])[0])
                store.path.write_bytes(b"x")
                self.assertIn("openrouter", clis.resolve(["openrouter", "custom"])[0])

    def test_free_model_filter_needs_every_price_to_be_zero(self):
        from respected_orchestrator.engine.provider import ProviderClient
        catalog = {"data": [{"id": "a:free", "pricing": {"prompt": "0", "completion": "0"}},
                            {"id": "b", "pricing": {"prompt": "0", "completion": "0.000001"}},
                            {"id": "c", "pricing": {"prompt": "x"}}, {"id": "d"}]}
        client = ProviderClient(environ={"RESPECTED_PROVIDER_NETWORK": "allow", "RESPECTED_PROVIDER_CODE_GATE": "1"},
                                transport=lambda *a: (200, json.dumps(catalog).encode()))
        self.assertEqual(client.models(free_only=True), ["a:free"])
        self.assertEqual(client.models(), ["a:free", "b", "c", "d"])

    def test_a_model_name_is_required_and_it_counts_as_a_writer(self):
        self.assertIn("openrouter", roles.WRITE_TOOLS)
        with tempfile.TemporaryDirectory() as root:
            project = Path(root).resolve() / "p"
            project.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            with self.assertRaises(ValueError) as caught:
                runner.create_task(EngineContext(Path(root) / "data"),
                                   {"task": "t", "worker": "openrouter", "kind": "write", "project_root": str(project)})
        self.assertIn("model name", str(caught.exception))


def reply(payload):
    return {"content": payload if isinstance(payload, str) else json.dumps(payload), "model": "m:free",
            "usage": {"prompt_tokens": 50, "completion_tokens": 20}}


class InLaneTests(unittest.TestCase):
    """Whole tasks: the engine shows the owned files, the model answers with whole files, the engine checks and writes."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "F"), ("config", "user.email", "f@example.invalid")]:
            subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)
        (self.repo / "owned.txt").write_text("base\n", encoding="utf8")
        (self.repo / "outside.txt").write_text("private\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.repo, check=True, capture_output=True)
        self.ctx = EngineContext(self.root / "data")
        for target, name, extra in ((runner.opencode_auth, "sync_credentials", {}), (runner.opencode_auth, "clear_worker_home", {}),
                                    (runner, "tool_available", {"side_effect": lambda tool: True}),
                                    (runner, "get_cli_command", {"side_effect": lambda tool: ["stored-key"]})):  # a stored key stands in
            patcher = mock.patch.object(target, name, **extra)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_task(self, answer, kind="write", **extra):
        request = dict(project_root=str(self.repo), task="make owned.txt say changed", worker="openrouter",
                       worker_profile="m:free", kind=kind, ownership=["owned.txt"], forbidden=["outside.txt"],
                       acceptance=[[sys.executable, "-c", "from pathlib import Path; assert Path('owned.txt').read_text() == 'changed\\n'"]],
                       timeout_seconds=30)
        request.update(extra)
        task = runner.create_task(self.ctx, request)
        seen = []

        def fake(model, prompt, timeout=0, sleep=None):
            seen.append((model, prompt))
            if isinstance(answer, Exception):
                raise answer
            return answer
        with mock.patch.object(openrouter_worker, "call", fake):
            result = runner.execute_task(self.ctx, task["run_id"])
        return task, result, seen

    def test_a_valid_answer_is_written_verified_and_checked_like_any_worker(self):
        task, result, seen = self.run_task(reply({"status": "success", "summary": "ok",
                                                  "files": [{"path": "owned.txt", "content": "changed\n"}]}))
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual((self.repo / "owned.txt").read_text(), "base\n")  # the real project waits for apply
        self.assertEqual(runner.check_result(self.ctx, task["run_id"])["status"], "verified")
        self.assertEqual(result["model"], "m:free")
        self.assertEqual(result["usage"]["output_tokens"], 20)
        self.assertEqual(seen[0][0], "m:free")
        self.assertIn("base", seen[0][1])  # the owned file travelled in the prompt
        self.assertNotIn("private", seen[0][1])  # a forbidden file never does

    def test_out_of_scope_traversal_and_malformed_answers_write_nothing_and_fail(self):
        for files in ([{"path": "outside.txt", "content": "x"}], [{"path": "../escape.txt", "content": "x"}],
                      [{"path": "C:/Windows/x.txt", "content": "x"}], [{"path": ".git/config", "content": "x"}],
                      [{"path": "owned.txt", "content": "changed\n"}, {"path": "other.txt", "content": "x"}],
                      [{"path": "owned.txt"}], "nope", []):
            task, result, _ = self.run_task(reply({"status": "success", "files": files}))
            self.assertEqual(result["status"], "failed", files)
            self.assertEqual(result["reason"], "worker_failed", files)
            self.assertEqual((self.repo / "outside.txt").read_text(), "private\n")
            self.assertFalse((self.root / "escape.txt").exists())

    def test_a_reply_that_is_not_json_or_says_failed_is_a_failure(self):
        for text in ("I changed the file for you.", {"status": "failed", "reason": "cannot"}):
            self.assertEqual(self.run_task(reply(text))[1]["status"], "failed", text)

    def test_provider_failures_fail_the_task_without_touching_files(self):
        for error in (ProviderError("rate_limited", status=429, retryable=True), ProviderDenied("provider network opt-in is off")):
            task, result, _ = self.run_task(error)
            self.assertEqual((result["status"], result["reason"]), ("failed", "worker_failed"))
            self.assertEqual((self.repo / "owned.txt").read_text(), "base\n")

    def test_a_read_task_reports_and_changes_nothing(self):
        task, result, _ = self.run_task(reply({"status": "success", "report": "looks fine"}), kind="read", acceptance=[])
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["changed_files"], [])
        task, result, _ = self.run_task(reply({"status": "success", "files": [{"path": "owned.txt", "content": "x"}]}),
                                        kind="read", acceptance=[])
        self.assertEqual(result["changed_files"], [])  # a read task never writes, whatever the model returns


if __name__ == "__main__":
    unittest.main()
