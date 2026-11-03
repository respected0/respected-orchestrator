"""Worker policy and real AppContainer boundary: fail closed, deny outside access."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import appcontainer, lanes
from respected_orchestrator.engine.processes import execute, ProcessStopped
from respected_orchestrator.engine.worker_policy import (
    SandboxStartError, WorkerPolicy, WorkerPolicyError, default_policy,
)
from respected_orchestrator.engine import runner
from respected_orchestrator.workflows import maf_workflow


WINDOWS = os.name == "nt"


def wait_dead(pid, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not lanes._pid_is_alive(pid):
            return True
        time.sleep(0.1)
    return not lanes._pid_is_alive(pid)


class PolicyValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "work"
        self.workspace.mkdir()
        self.readonly = self.root / "read"
        self.readonly.mkdir()

    def test_empty_and_missing_roots_are_refused(self):
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=())
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(self.root / "missing",))
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(self.workspace,), readonly_roots=(self.root / "missing",))

    def test_overlapping_roots_are_refused(self):
        child = self.workspace / "sub"
        child.mkdir()
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(self.workspace,), readonly_roots=(child,))
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(child,), readonly_roots=(self.workspace,))

    def test_unknown_network_mode_and_bad_ttl_are_refused(self):
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(self.workspace,), network_mode="maybe")
        for ttl in (0, -1, True, "600"):
            with self.assertRaises(WorkerPolicyError):
                WorkerPolicy(allowed_roots=(self.workspace,), ttl=ttl)

    def test_data_root_and_signing_key_are_protected(self):
        data = self.root / "data"
        data.mkdir()
        (data / ".engine-key").write_text("secret", encoding="utf8")
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(data,)).protect(data)
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(self.root,)).protect(data)
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(self.workspace,), readonly_roots=(data,)).protect(data)
        # A worker workspace nested below the data root is the supported shape.
        nested = data / "runs" / "x"
        nested.mkdir(parents=True)
        self.assertIsNotNone(WorkerPolicy(allowed_roots=(nested,)).protect(data))

    def test_executable_allowlist_and_shell_shims(self):
        python = Path(sys.executable).resolve()
        policy = WorkerPolicy(allowed_roots=(self.workspace,), executable_allowlist=(python,))
        self.assertEqual(policy.resolve([sys.executable, "-V"])[0], str(python))
        other = WorkerPolicy(allowed_roots=(self.workspace,), executable_allowlist=(self.readonly,))
        with self.assertRaises(WorkerPolicyError):
            other.resolve([sys.executable, "-V"])
        shim = self.workspace / "fake.cmd"
        shim.write_text("echo nope", encoding="utf8")
        with self.assertRaises(WorkerPolicyError):
            WorkerPolicy(allowed_roots=(self.workspace,), executable_allowlist=(shim,)).resolve([str(shim)])

    def test_timeout_above_ttl_is_refused(self):
        policy = WorkerPolicy(allowed_roots=(self.workspace,), ttl=5)
        policy.check_timeout(5)
        with self.assertRaises(WorkerPolicyError):
            policy.check_timeout(5.1)

    def test_environment_scrubs_secrets_and_redirects_temp(self):
        tmp = self.workspace / "tmp"
        tmp.mkdir()
        env = {"MY_SENTINEL_SECRET": "do-not-leak", "AWS_SECRET_ACCESS_KEY": "aws", "PATH": "keep"}
        policy = WorkerPolicy(allowed_roots=(self.workspace,), temp_root=tmp, secrets=("MY_SENTINEL_SECRET",))
        cleaned = policy.environment(env)
        self.assertNotIn("MY_SENTINEL_SECRET", cleaned)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", cleaned)
        self.assertEqual(cleaned["PATH"], "keep")
        self.assertEqual(cleaned["TEMP"], str(tmp))
        self.assertEqual(cleaned["TMP"], str(tmp))


class FailClosedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "work"
        self.workspace.mkdir()

    def test_spawn_failure_raises_and_creates_no_worker_output(self):
        marker = self.workspace / "worker-ran.txt"
        policy = WorkerPolicy(allowed_roots=(self.workspace,), executable_allowlist=(Path(sys.executable).resolve(),))
        command = [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"]
        with mock.patch.object(appcontainer, "spawn", side_effect=SandboxStartError("forced")):
            with self.assertRaises(SandboxStartError):
                execute(command, self.workspace, 10, policy=policy)
        self.assertFalse(marker.exists())

    def test_elevated_session_never_starts_the_container(self):
        marker = self.workspace / "elevated-ran.txt"
        command = [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"]
        with mock.patch.object(appcontainer, "_is_elevated", return_value=True), \
             mock.patch.object(appcontainer._userenv, "CreateAppContainerProfile") as profile, \
             mock.patch.object(appcontainer._kernel, "CreateProcessW") as process:
            with self.assertRaisesRegex(SandboxStartError, "unsupported_elevated"):
                appcontainer.spawn(command, self.workspace, {}, allowed_roots=(self.workspace,),
                                   readonly_roots=(), network_mode="deny", job=None)
        profile.assert_not_called()
        process.assert_not_called()
        self.assertFalse(marker.exists())

    def test_unverifiable_session_never_starts_the_container(self):
        marker = self.workspace / "unverifiable-ran.txt"
        command = [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')"]
        with mock.patch.object(appcontainer, "_is_elevated", side_effect=SandboxStartError("cannot inspect token")), \
             mock.patch.object(appcontainer._userenv, "CreateAppContainerProfile") as profile, \
             mock.patch.object(appcontainer._kernel, "CreateProcessW") as process:
            with self.assertRaisesRegex(SandboxStartError, "session cannot be verified"):
                appcontainer.spawn(command, self.workspace, {}, allowed_roots=(self.workspace,),
                                   readonly_roots=(), network_mode="deny", job=None)
        profile.assert_not_called()
        process.assert_not_called()
        self.assertFalse(marker.exists())

    def test_runner_marks_sandbox_unavailable_and_leaves_project_untouched(self):
        repo = self.root / "repo"
        repo.mkdir()
        for args in (("init", "-b", "main"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")):
            subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)
        (repo / "owned.txt").write_text("base\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, capture_output=True, check=True)
        ctx = EngineContext(self.root / "data")
        task = runner.create_task(ctx, dict(
            project_root=str(repo), task="sandbox failure", worker="custom", kind="write",
            ownership=["owned.txt"], forbidden=[], timeout_seconds=10,
            command=[sys.executable, "-c", "from pathlib import Path; Path('owned.txt').write_text('changed\\n')"],
            acceptance=[[sys.executable, "-c", "from pathlib import Path; assert Path('owned.txt').read_text() == 'changed\\n'"]],
        ))
        with mock.patch.object(appcontainer, "spawn", side_effect=SandboxStartError("forced")):
            result = runner.execute_task(ctx, task["run_id"])
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["reason"], "sandbox_unavailable", result)
        self.assertEqual((repo / "owned.txt").read_text(encoding="utf8"), "base\n")

    def test_maf_reviewer_is_fail_closed_when_the_sandbox_cannot_start(self):
        # SEC-03: the review-only path uses the same policy and AppContainer launcher as the worker path.
        data = self.root / "data"
        run_root = data / "state" / "run-20260101000000-review"
        run_root.mkdir(parents=True)
        ctx = EngineContext(data)
        command = [sys.executable, "-c", "print('{}')"]
        with mock.patch.object(maf_workflow, "command_for", return_value=command), \
             mock.patch.object(appcontainer, "spawn", side_effect=SandboxStartError("forced")):
            outcome = maf_workflow._run_tool_call("claude", "profile", "prompt", run_root, 10, ctx=ctx)
        self.assertEqual((outcome.status, outcome.cause), ("FAILED", "sandbox_unavailable"))
        self.assertEqual((run_root / "stdout.log").read_text(encoding="utf8"), "")


@unittest.skipUnless(WINDOWS, "AppContainer is Windows-only")
class RealSandboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "work"
        self.workspace.mkdir()
        self.tmp = self.workspace / "tmp"
        self.tmp.mkdir()
        self.outside = self.root / "outside"
        self.outside.mkdir()
        (self.outside / "private.txt").write_text("private", encoding="utf8")

    def policy(self, *, network_mode="deny", data_root=None, secrets=()):
        ctx = EngineContext(data_root) if data_root is not None else None
        policy = default_policy(ctx, self.workspace, [sys.executable], temp_root=self.tmp,
                                network_mode=network_mode, ttl=30)
        if secrets:
            policy = WorkerPolicy(policy.allowed_roots, policy.readonly_roots, policy.network_mode,
                                  policy.executable_allowlist, secrets, policy.temp_root, policy.ttl)
        return policy

    def run_code(self, code, *, policy=None, timeout=20):
        return execute([sys.executable, "-c", code], self.workspace, timeout, policy=policy or self.policy())

    def test_allowed_write_and_read_still_work(self):
        result = self.run_code("from pathlib import Path; Path('ok.txt').write_text('ok'); print(Path('ok.txt').read_text())")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ok")
        self.assertEqual((self.workspace / "ok.txt").read_text(encoding="utf8"), "ok")

    def test_outside_read_is_denied(self):
        target = self.outside / "private.txt"
        code = (
            "import sys\n"
            "from pathlib import Path\n"
            f"p=Path({str(target)!r})\n"
            "try:\n"
            "    p.read_text(encoding='utf8')\n"
            "except (PermissionError, OSError):\n"
            "    print('DENIED'); sys.exit(0)\n"
            "print('LEAKED'); sys.exit(3)\n"
        )
        result = self.run_code(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DENIED", result.stdout)
        self.assertNotIn("LEAKED", result.stdout)

    def test_outside_write_is_denied(self):
        target = self.outside / "planted.txt"
        code = (
            "import sys\n"
            "from pathlib import Path\n"
            f"p=Path({str(target)!r})\n"
            "try:\n"
            "    p.write_text('x', encoding='utf8')\n"
            "except (PermissionError, OSError):\n"
            "    print('DENIED'); sys.exit(0)\n"
            "print('WROTE'); sys.exit(3)\n"
        )
        result = self.run_code(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DENIED", result.stdout)
        self.assertFalse(target.exists())

    def test_engine_key_and_data_root_are_not_reachable_from_worker(self):
        data = self.root / "data"
        data.mkdir()
        key = data / ".engine-key"
        key.write_text("signing-secret", encoding="utf8")
        policy = self.policy(data_root=data)
        code = (
            "import sys\n"
            "from pathlib import Path\n"
            f"p=Path({str(key)!r})\n"
            "try:\n"
            "    p.read_text(encoding='utf8')\n"
            "except (PermissionError, OSError):\n"
            "    print('DENIED'); sys.exit(0)\n"
            "print('LEAKED'); sys.exit(3)\n"
        )
        result = self.run_code(code, policy=policy)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DENIED", result.stdout)
        self.assertNotIn("signing-secret", result.stdout + result.stderr)

    def test_network_is_denied_by_default(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        self.addCleanup(listener.close)
        port = listener.getsockname()[1]
        code = (
            "import socket, sys\n"
            "s=socket.socket(); s.settimeout(2)\n"
            f"try:\n"
            f"    s.connect(('127.0.0.1', {port}))\n"
            "except OSError:\n"
            "    print('DENIED'); sys.exit(0)\n"
            "print('CONNECTED'); sys.exit(3)\n"
        )
        result = self.run_code(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DENIED", result.stdout)

    def test_child_process_inherits_the_boundary(self):
        target = self.outside / "private.txt"
        inner = (
            "import sys\n"
            "from pathlib import Path\n"
            f"p=Path({str(target)!r})\n"
            "try:\n"
            "    p.read_text(encoding='utf8')\n"
            "except (PermissionError, OSError):\n"
            "    print('DENIED'); sys.exit(0)\n"
            "print('LEAKED'); sys.exit(3)\n"
        )
        code = (
            "import subprocess, sys\n"
            f"r=subprocess.run([sys.executable,'-c',{inner!r}], capture_output=True, text=True)\n"
            "print(r.stdout.strip()); sys.exit(r.returncode)\n"
        )
        result = self.run_code(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DENIED", result.stdout)
        self.assertNotIn("LEAKED", result.stdout)

    def test_timeout_leaves_no_child_process(self):
        parent_pid = self.workspace / "parent.pid"
        child_pid = self.workspace / "child.pid"
        grandchild = (
            "from pathlib import Path; import time; "
            f"Path({str(child_pid)!r}).write_text(str(__import__('os').getpid())); time.sleep(60)"
        )
        parent = (
            "import subprocess, sys, time\n"
            "from pathlib import Path\n"
            f"Path({str(parent_pid)!r}).write_text(str(__import__('os').getpid()))\n"
            f"subprocess.Popen([sys.executable,'-c',{grandchild!r}])\n"
            f"end=time.time()+10\n"
            f"while not Path({str(child_pid)!r}).exists() and time.time()<end: time.sleep(0.05)\n"
            "time.sleep(60)\n"
        )
        with self.assertRaises(ProcessStopped) as raised:
            self.run_code(parent, timeout=4)
        self.assertEqual(raised.exception.reason, "timed_out")
        self.assertTrue(parent_pid.exists())
        self.assertTrue(wait_dead(int(parent_pid.read_text()), 10))
        if child_pid.exists():
            self.assertTrue(wait_dead(int(child_pid.read_text()), 10))

    def test_sentinel_secret_never_appears_in_output(self):
        sentinel = "SENTINEL-DO-NOT-LEAK-9f3c"
        policy = self.policy(secrets=("MY_SENTINEL_SECRET",))
        code = "import os; print(repr(os.environ.get('MY_SENTINEL_SECRET'))); print(repr(os.environ.get('AWS_SECRET_ACCESS_KEY')))"
        env = dict(os.environ, MY_SENTINEL_SECRET=sentinel, AWS_SECRET_ACCESS_KEY=sentinel)
        result = execute([sys.executable, "-c", code], self.workspace, 20, policy=policy, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["None", "None"])
        self.assertNotIn(sentinel, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
