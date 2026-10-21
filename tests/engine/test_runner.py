"""Real task execution in temporary repositories; never uses the source checkout."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.runner import create_task, execute_task, inspect_task, cancel_task, check_result, start_task, retry_task
from respected_orchestrator.engine import runner
from respected_orchestrator.engine import lanes
from respected_orchestrator.engine.processes import execute, ProcessStopped
from respected_orchestrator.engine.evidence import RESTRICTED_KEYS, signing_key
from respected_orchestrator.engine import evidence


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")]:
            self.git(*args)
        (self.repo / "owned.txt").write_text("base\n", encoding="utf8")
        (self.repo / "outside.txt").write_text("private\n", encoding="utf8")
        self.git("add", ".")
        self.git("commit", "-m", "fixture baseline")
        self.ctx = EngineContext(self.root / "data")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True).stdout

    def task(self, code="from pathlib import Path; Path('owned.txt').write_text('changed\\n')", **extra):
        request = dict(project_root=str(self.repo), task="fixture task", worker="custom", kind="write",
                       ownership=["owned.txt"], forbidden=["outside.txt"],
                       command=[sys.executable, "-c", code],
                       acceptance=[[sys.executable, "-c", "from pathlib import Path; assert Path('owned.txt').read_text() == 'changed\\n'"]],
                       timeout_seconds=10)
        request.update(extra)
        return create_task(self.ctx, request)

    def test_write_is_independent_isolated_verified_and_inspectable(self):
        task = self.task()
        result = execute_task(self.ctx, task["run_id"])
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual((self.repo / "owned.txt").read_text(), "base\n")
        self.assertEqual(check_result(self.ctx, task["run_id"])["status"], "verified")
        inspected = inspect_task(self.ctx, task["run_id"])
        self.assertIn("changed", inspected["patch_preview"])
        self.assertNotIn("vault_id", json.dumps(inspected))
        self.assertEqual(inspected['request']['master'], 'user')

    def test_failed_worker_is_never_accepted(self):
        task = self.task("raise SystemExit(7)")
        self.assertEqual(execute_task(self.ctx, task["run_id"])["status"], "failed")
        with self.assertRaises(ValueError):
            check_result(self.ctx, task["run_id"])

    def test_failed_acceptance_is_never_completed(self):
        task = self.task(acceptance=[[sys.executable, "-c", "raise SystemExit(2)"]])
        self.assertEqual(execute_task(self.ctx, task["run_id"])["status"], "failed")

    def test_scope_violation_and_acceptance_mutation_are_rejected(self):
        task = self.task("from pathlib import Path; Path('outside.txt').write_text('oops')")
        self.assertEqual(execute_task(self.ctx, task["run_id"])["reason"], "scope_violation")
        task = self.task(acceptance=[[sys.executable, "-c", "from pathlib import Path; Path('outside.txt').write_text('oops')"]])
        self.assertEqual(execute_task(self.ctx, task["run_id"])["reason"], "scope_violation")

    def test_untracked_owned_inputs_can_be_auto_included_so_the_patch_integrates(self):
        (self.repo / "extra.txt").write_text("user work\n", encoding="utf8")  # untracked, inside the lane's ownership
        code = "from pathlib import Path; p = Path('extra.txt'); p.write_text(p.read_text() + 'lane\\n')"
        acceptance = [[sys.executable, "-c", "from pathlib import Path; assert Path('extra.txt').read_text() == 'user work\\nlane\\n'"]]
        extra = dict(ownership=["owned.txt", "extra.txt"], acceptance=acceptance)
        without = self.task(code, **extra)
        self.assertEqual(execute_task(self.ctx, without["run_id"])["status"], "failed")  # a HEAD-only lane has no extra.txt
        task = self.task(code, include_untracked_owned=True, **extra)
        result = execute_task(self.ctx, task["run_id"])
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(check_result(self.ctx, task["run_id"])["status"], "verified")
        self.assertEqual((self.repo / "extra.txt").read_text(), "user work\n")  # real source untouched until apply
        forbidden = self.task(code, include_untracked_owned=True, **dict(extra, forbidden=["extra.txt"]))
        self.assertEqual(execute_task(self.ctx, forbidden["run_id"])["status"], "failed")  # forbidden files are never auto-included

    def test_untracked_owned_auto_include_filters_paths_and_supports_unicode(self):
        (self.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf8")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "fixture ignore rules")
        (self.repo / "ignored.txt").write_text("secret\n", encoding="utf8")
        name = "owned \U0001f600 file.txt"
        (self.repo / name).write_text("user work\n", encoding="utf8")
        code = "from pathlib import Path; Path('owned \U0001f600 file.txt').write_text('changed\\n')"
        acceptance = [[sys.executable, "-c", "from pathlib import Path; assert Path('owned \U0001f600 file.txt').read_text() == 'changed\\n'"]]
        task = self.task(code, ownership=[name], acceptance=acceptance, include_untracked_owned=True)
        self.assertEqual(inspect_task(self.ctx, task["run_id"])["request"]["include_untracked"], [name])

    def test_read_task_cannot_change_files(self):
        task = self.task(kind="read", acceptance=[])
        self.assertEqual(execute_task(self.ctx, task["run_id"])["reason"], "scope_violation")

    def test_cancel_before_start_and_timeout(self):
        task = self.task()
        cancel_task(self.ctx, task["run_id"])
        self.assertEqual(execute_task(self.ctx, task["run_id"])["status"], "cancelled")
        task = self.task("import time; time.sleep(30)", timeout_seconds=1)
        self.assertEqual(execute_task(self.ctx, task["run_id"])["status"], "timed_out")

    def test_stale_or_tampered_results_are_rejected(self):
        task = self.task()
        execute_task(self.ctx, task["run_id"])
        (self.repo / "outside.txt").write_text("user edit\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            check_result(self.ctx, task["run_id"])
        (self.repo / "outside.txt").write_text("private\n")
        patch = self.ctx.run_dir(task["run_id"]) / "worker.patch"
        patch.write_bytes(patch.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "tamper"):
            check_result(self.ctx, task["run_id"])

    def test_explicit_scopes_commands_and_separate_roots(self):
        for overrides in [dict(ownership=[]), dict(ownership=["../escape"]),
                          dict(acceptance=[]), dict(timeout_seconds=0),
                          dict(command=["fake", "--dangerously-skip-permissions"]),
                          dict(project_root=str(self.root)), dict(worker="unknown")]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.task(**overrides)

    def wait_terminal(self, run_id, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = inspect_task(self.ctx, run_id)
            if status["status"] in runner.TERMINAL:
                return status
            time.sleep(0.05)
        self.fail("Detached task did not finish within bounded test time")

    def test_detached_supervisor_survives_submission_process_exit(self):
        task = self.task()
        env = dict(os.environ, PYTHONPATH=str(Path(runner.__file__).resolve().parents[2]))
        submission = subprocess.run([sys.executable, "-m", "respected_orchestrator", "--data-root", str(self.ctx.data_root),
                                     "start", task["run_id"]], env=env, cwd=self.root, capture_output=True, text=True, timeout=5)
        self.assertEqual(submission.returncode, 0, submission.stdout + submission.stderr)
        result = self.wait_terminal(task["run_id"])
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(check_result(self.ctx, task["run_id"])["status"], "verified")

    def test_live_cancel_stops_worker_and_retains_logs(self):
        task = self.task("import time; print('worker ready', flush=True); time.sleep(30)")
        start_task(self.ctx, task["run_id"])
        self.addCleanup(lambda: (cancel_task(self.ctx, task['run_id']), self.wait_terminal(task['run_id'])))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if 'worker ready' in inspect_task(self.ctx, task["run_id"]).get('logs', {}).get('stdout.log', ''):
                break
            time.sleep(0.05)
        self.assertIn('worker ready', inspect_task(self.ctx, task['run_id']).get('logs', {}).get('stdout.log', ''))
        cancel_task(self.ctx, task["run_id"])
        self.assertEqual(self.wait_terminal(task["run_id"])["status"], "cancelled")

    def test_result_and_request_envelopes_refuse_tampering(self):
        task = self.task()
        execute_task(self.ctx, task["run_id"])
        result_path = self.ctx.run_dir(task["run_id"]) / "result.json"
        envelope = json.loads(result_path.read_text())
        envelope["payload"]["changed_files"] = []
        result_path.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(ValueError, "tampered"):
            check_result(self.ctx, task["run_id"])
        request_path = self.ctx.run_dir(task["run_id"]) / "request.json"
        envelope = json.loads(request_path.read_text())
        envelope["payload"]["command"] = ["other-executable"]
        request_path.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(ValueError, "tampered"):
            execute_task(self.ctx, task["run_id"])

    def test_failed_retry_budget_is_bounded(self):
        task = self.task("raise SystemExit(3)")
        for attempt in range(3):
            execute_task(self.ctx, task["run_id"])
            if attempt < 2:
                task = retry_task(self.ctx, task["run_id"])
        with self.assertRaisesRegex(ValueError, "budget"):
            retry_task(self.ctx, task["run_id"])

    def test_retry_cannot_branch_to_reset_the_attempt_budget(self):
        task = self.task('raise SystemExit(3)')
        execute_task(self.ctx, task['run_id'])
        retry_task(self.ctx, task['run_id'])
        with self.assertRaisesRegex(ValueError, 'already retried'):
            retry_task(self.ctx, task['run_id'])

    def test_zero_exit_provider_failure_or_pending_is_not_completed(self):
        for output in [{"status": "failed"}, {"status": "pending"}, {"error": "quota limit exhausted"}]:
            task = self.task(f"print({json.dumps(json.dumps(output))})")
            self.assertEqual(execute_task(self.ctx, task["run_id"])["status"], "failed")

    def test_codex_jsonl_failure_never_reaches_acceptance(self):
        started = {"type": "thread.started", "thread_id": "fixture"}
        success = {"type": "item.completed", "item": {"type": "agent_message", "text": '{"status":"success"}'}}
        completed = {"type": "turn.completed", "usage": {}}
        cases = [
            [started, {"type": "turn.failed", "error": {"message": "sandbox unavailable"}}],
            [started, {"type": "error", "message": "sandbox unavailable"}, success, completed],
            [started, success],
            [started, completed],
            [started, {"type": "item.completed", "item": {"type": "agent_message", "text": "Blocked: Access denied"}}, completed],
            [started, {"type": "item.completed", "item": {"type": "agent_message", "text": '{"status":"failed"}'}}, completed],
            [started, {"type": "item.completed", "item": {"type": "agent_message", "text": '{"error":"blocked"}'}}, completed],
            [started, {"type": "item.completed", "item": {"type": "agent_message", "text": '{"status":"success","error":"blocked"}'}}, completed],
            [started, {"type": "item.completed", "item": {"type": "agent_message", "text": 42}}, completed],
        ]
        outputs = ['\n'.join(json.dumps(event) for event in events) for events in cases]
        outputs.append('\n'.join([json.dumps(started), 'malformed JSON', json.dumps(success), json.dumps(completed)]))
        outputs.extend(["", "{}", "null", "[]"])
        for output in outputs:
            with self.subTest(output=output):
                task = self.task(command=["codex", "exec", "--json", "{prompt}"],
                                 acceptance=[[sys.executable, "-c", "raise SystemExit(99)"]])
                def fake_cli(command, cwd, *args, **kwargs):
                    if command[0] == "codex":
                        return subprocess.CompletedProcess(command, 0, output, "")
                    return execute(command, cwd, *args, **kwargs)
                with mock.patch.object(runner, "execute", side_effect=fake_cli):
                    result = execute_task(self.ctx, task["run_id"])
                self.assertEqual(result.get("reason"), "worker_failed", result)
                self.assertFalse((self.ctx.run_dir(task["run_id"]) / "check-1.log").exists())

    def test_codex_jsonl_uses_last_agent_result_and_preserves_verification(self):
        events = [
            {"type": "thread.started", "thread_id": "fixture"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Inspecting the workspace."}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": '{"status":"success"}'}},
            {"type": "turn.completed", "usage": {}},
        ]
        task = self.task(command=["codex", "exec", "--json", "{prompt}"])
        def fake_cli(command, cwd, *args, **kwargs):
            if command[0] == "codex":
                self.assertIn("fixture task", command[-1])
                self.assertIn(str(cwd), command[-1])
                (cwd / "owned.txt").write_text("changed\n")
                return subprocess.CompletedProcess(command, 0, '\n'.join(json.dumps(event) for event in events), "")
            return execute(command, cwd, *args, **kwargs)
        with mock.patch.object(runner, "execute", side_effect=fake_cli):
            result = execute_task(self.ctx, task["run_id"])
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["changed_files"], ["owned.txt"])
        self.assertEqual(check_result(self.ctx, task["run_id"])["status"], "verified")

    def test_codex_timeout_after_edit_without_turn_completed_is_never_success(self):
        task = self.task(command=["codex", "exec", "--json", "{prompt}"],
                         acceptance=[[sys.executable, "-c", "pass"]])
        partial = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": '{"status":"success"}'}})
        def fake_cli(command, cwd, *args, **kwargs):
            if command[0] == "codex":
                (cwd / "owned.txt").write_text("changed\n")
                raise ProcessStopped("timed_out", partial, "")
            return execute(command, cwd, *args, **kwargs)
        with mock.patch.object(runner, "execute", side_effect=fake_cli):
            result = execute_task(self.ctx, task["run_id"])
        directory = self.ctx.run_dir(task["run_id"])
        self.assertEqual(result["status"], "timed_out", result)
        self.assertEqual(result["worker_incomplete"], "no_turn_completed")
        self.assertFalse((directory / "result.json").exists())
        self.assertFalse((directory / "check-1.log").exists())

    def test_codex_task_specific_status_marker_is_rejected(self):
        events = [{"type": "item.completed", "item": {"type": "agent_message", "text": '{"status":"WORKER_OK"}'}},
                  {"type": "turn.completed", "usage": {}}]
        task = self.task(command=["codex", "exec", "--json", "{prompt}"])
        def fake_cli(command, cwd, *args, **kwargs):
            if command[0] == "codex":
                return subprocess.CompletedProcess(command, 0, '\n'.join(json.dumps(e) for e in events), "")
            return execute(command, cwd, *args, **kwargs)
        with mock.patch.object(runner, "execute", side_effect=fake_cli):
            result = execute_task(self.ctx, task["run_id"])
        self.assertEqual(result.get("reason"), "worker_failed", result)

    def test_codex_final_message_fenced_json_is_accepted_only_when_unambiguous(self):
        done = '{"status":"success","summary":"ok"}'
        fence = "```"
        accepted = [done, f"Done.\n{fence}json\n{done}\n{fence}\nThanks.", f"{fence}JSON\r\n{done}\r\n{fence}"]
        rejected = [f"{fence}json\n{done}\n{fence}\n{fence}json\n{done}\n{fence}",
                    f'{fence}json\n{done}\n{fence}\n{fence}\n{{"status":"failed"}}\n{fence}',
                    f"{fence}json\n{done}", f"{fence}json\n{{bad json}}\n{fence}", f"{fence}json\n[1]\n{fence}",
                    f"prose {done} prose", f'{fence}json\n{{"summary":"no status"}}\n{fence}']
        def stdout(text, completed=True):
            events = [{"type": "item.completed", "item": {"type": "agent_message", "text": text}}]
            events += [{"type": "turn.completed", "usage": {}}] if completed else []
            return "\n".join(json.dumps(e) for e in events)
        for text in accepted:
            self.assertEqual(runner._codex_payload(stdout(text))["status"], "success", text)
        for text in rejected:
            self.assertEqual(runner._codex_payload(stdout(text))["status"], "failed", text)
        self.assertEqual(runner._codex_payload(stdout(accepted[1], completed=False))["status"], "failed")

    def test_codex_command_keeps_unicode_multiline_brief_as_one_json_argument(self):
        prompt = '# Brief\nGörev: "toplamı" hesapla\n*** Begin Patch\n'
        with mock.patch.object(runner, "get_cli_command", return_value=["codex.exe"]):
            command = runner.command_for("codex", prompt)
        self.assertEqual(command, ["codex.exe", "exec", "--sandbox", "workspace-write", "-c",
                                   'approval_policy="never"', "--json", prompt])
        self.assertEqual(runner.command_for("codex", "p", profile="glm")[-4:-1], ["-p", "glm", "--json"])

    def test_worker_environment_drops_secrets_unless_allowed(self):
        from respected_orchestrator.engine.processes import scrub_environment
        env = {"PATH": "x", "ANTHROPIC_API_KEY": "s", "GH_TOKEN": "s", "SSH_AUTH_SOCK": "s", "KEEP_TOKEN": "s",
               "RESPECTED_WORKER_ENV_ALLOW": "keep_token"}
        self.assertEqual(set(scrub_environment(env)), {"PATH", "KEEP_TOKEN", "RESPECTED_WORKER_ENV_ALLOW"})

    def test_same_model_may_hold_every_role_unless_independence_is_required_and_blocked_profiles_are_refused(self):
        same = self.task(command=[sys.executable, "-c", "1"], worker_profile="deepseek",
                         workflow={"reviewer_profile": "DeepSeek"})
        request = inspect_task(self.ctx, same["run_id"])["request"]
        self.assertEqual(request["role_assignments"]["reviewer"]["source"], "explicit")  # never silently replaced
        self.assertEqual(request["workflow"]["reviewer_profile"], "DeepSeek")
        self.assertEqual(request["role_notes"], ["reviewer_same_profile_as_implementer", "deep_reviewer_same_profile_as_implementer"])
        with self.assertRaisesRegex(ValueError, "differ"):
            self.task(command=[sys.executable, "-c", "1"], worker_profile="deepseek",
                      workflow={"reviewer_profile": "DeepSeek", "require_independent_review": True})
        with self.assertRaisesRegex(ValueError, "blocked"):
            self.task(command=[sys.executable, "-c", "1"], workflow={"reviewer_profile": "mimo"})
        with self.assertRaisesRegex(ValueError, "blocked"):
            self.task(command=[sys.executable, "-c", "1"], roles={"implementer": {"profile": "MiMo-x"}})

    def test_engine_key_is_restricted_to_current_user(self):
        if os.name != "nt":
            self.skipTest("ACL check is Windows specific")
        RESTRICTED_KEYS.clear()
        signing_key(self.ctx)
        acl = subprocess.run(["icacls", str(self.ctx.data_root / ".engine-key")], capture_output=True, text=True).stdout
        self.assertNotIn("BUILTIN\\Users", acl)
        self.assertNotIn("Authenticated Users", acl)

    def test_engine_key_is_restricted_before_secret_is_written(self):
        seen = []
        RESTRICTED_KEYS.clear()
        with mock.patch.object(evidence, "restrict_key", lambda path: seen.append(Path(path).read_bytes())):
            key = signing_key(self.ctx)
        self.assertEqual(seen[0], b"")  # ACL is closed while the temp file is still empty
        self.assertEqual((self.ctx.data_root / ".engine-key").read_bytes(), key)
        self.assertEqual(len(key), 32)
        self.assertEqual([p.name for p in self.ctx.data_root.glob(".engine-key*")], [".engine-key"])

    def test_apply_requires_verified_result_and_applies_once(self):
        task = self.task()
        execute_task(self.ctx, task["run_id"])
        with mock.patch.dict(os.environ, {"RESPECTED_ORCH_CHILD": "1"}), self.assertRaisesRegex(ValueError, "worker"):
            runner.apply_task(self.ctx, task["run_id"])
        self.assertEqual(runner.apply_task(self.ctx, task["run_id"])["status"], "applied")
        self.assertEqual((self.repo / "owned.txt").read_text(), "changed\n")
        with self.assertRaisesRegex(ValueError, "already"):
            runner.apply_task(self.ctx, task["run_id"])
        failed = self.task("raise SystemExit(7)")
        execute_task(self.ctx, failed["run_id"])
        with self.assertRaises(ValueError):
            runner.apply_task(self.ctx, failed["run_id"])

    def test_dirty_inputs_and_untracked_binary_are_preserved(self):
        (self.repo / "owned.txt").write_text("dirty baseline\n")
        (self.repo / "new.bin").write_bytes(bytes(range(256)))
        task = self.task("from pathlib import Path; Path('owned.txt').write_text('changed\\n'); Path('new.bin').write_bytes(bytes(range(255)))",
                         ownership=["owned.txt", "new.bin"], include_untracked=["new.bin"])
        self.assertEqual(execute_task(self.ctx, task["run_id"])["status"], "completed")
        self.assertEqual((self.repo / "owned.txt").read_text(), "dirty baseline\n")
        self.assertEqual((self.repo / "new.bin").read_bytes(), bytes(range(256)))
        self.assertEqual(check_result(self.ctx, task["run_id"])["status"], "verified")

    def test_timeout_kills_worker_descendants(self):
        pid_file = self.root / "descendant.pid"
        code = "import subprocess,sys,time; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)"
        with self.assertRaises(ProcessStopped):
            execute([sys.executable, "-c", code, str(pid_file)], self.repo, 1)
        pid = int(pid_file.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and lanes._pid_is_alive(pid):
            time.sleep(0.05)
        self.assertFalse(lanes._pid_is_alive(pid), f"Orphaned descendant {pid}")

    @unittest.skipUnless(os.name == "nt", "Windows Job Object crash recovery")
    def test_supervisor_crash_kills_owned_descendants(self):
        pid_file = self.root / "crash-descendant.pid"
        code = "import subprocess,sys,time; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(30)"
        task = self.task(code=f"import subprocess,sys; subprocess.run([sys.executable,'-c',{code!r},{str(pid_file)!r}])", timeout_seconds=20)
        submission = start_task(self.ctx, task["run_id"])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not pid_file.exists():
            time.sleep(0.05)
        self.assertTrue(pid_file.exists())
        pid = int(pid_file.read_text())
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(1, False, submission["pid"])
        self.assertTrue(handle)
        try:
            self.assertTrue(api.TerminateProcess(handle, 1))
        finally:
            api.CloseHandle(handle)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and lanes._pid_is_alive(pid):
            time.sleep(0.05)
        self.assertFalse(lanes._pid_is_alive(pid))
        self.assertEqual(inspect_task(self.ctx, task["run_id"])["status"], "interrupted")

    def test_new_ignored_file_outside_scope_is_rejected(self):
        (self.repo / '.gitignore').write_text('.env\n')
        self.git('add', '.gitignore')
        self.git('commit', '-m', 'fixture ignores')
        task = self.task("from pathlib import Path; Path('owned.txt').write_text('changed\\n'); Path('.env').write_text('secret')")
        self.assertEqual(execute_task(self.ctx, task['run_id'])['reason'], 'scope_violation')

    def test_private_json_submission_status_inspection_and_check(self):
        env = dict(os.environ, PYTHONPATH=str(Path(runner.__file__).resolve().parents[2]))
        command = [sys.executable, '-m', 'respected_orchestrator', '--data-root', str(self.ctx.data_root)]
        request = dict(project_root=str(self.repo), task='JSON bridge read task', kind='read', worker='custom',
                       ownership=['owned.txt'], forbidden=['outside.txt'], acceptance=[], timeout_seconds=10,
                       command=[sys.executable, '-c', "from pathlib import Path; print(Path('owned.txt').read_text())"])
        def call(action, *args, payload=None):
            result = subprocess.run([*command, action, *args], env=env, cwd=self.root,
                                    input=json.dumps(payload) if payload else None, text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)
        run_id = call('create', payload=request)['run_id']
        call('start', run_id)
        self.assertEqual(self.wait_terminal(run_id)['status'], 'completed')
        self.assertEqual(call('inspect', run_id)['request']['task'], request['task'])
        self.assertEqual(call('check', run_id)['status'], 'verified')
        self.assertEqual(call('list')['runs'][0]['run_id'], run_id)


if __name__ == "__main__":
    unittest.main()
