"""SEC-04: the worker security matrix, red-team control, symlink patch and recursive MCP.

The probe runs in the production AppContainer path (``execute(..., policy=...)``)
and every negative case must report a denial. The unsandboxed control proves
the same probe would succeed without the policy, so a broken probe cannot make
the matrix green by accident.
"""
import dataclasses
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import appcontainer, lanes
from respected_orchestrator.engine.evidence import key_path
from respected_orchestrator.engine.processes import execute
from respected_orchestrator.engine.worker_policy import default_policy
from tests.engine.security_cases import (
    ALLOWED_CASES,
    EXTERNAL_NEGATIVE_CASES,
    PROBE,
    PROBE_NEGATIVE_CASES,
)


WINDOWS = os.name == "nt"
SENTINEL = "SEC04-SENTINEL-DO-NOT-LEAK"


def git(cwd, *args, input=None):
    return subprocess.run(
        ["git", *args], cwd=cwd, input=input, capture_output=True, text=True,
        encoding="utf-8", check=True,
    )


@unittest.skipUnless(WINDOWS, "the worker boundary is a Windows AppContainer")
class WorkerSecurityMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="orch-sec04-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.data = self.root / "data"
        self.data.mkdir()
        self.ctx = EngineContext(self.data)
        self.key = key_path(self.ctx)
        (self.data / "settings.json").write_text('{"memory_token": "secret"}', encoding="utf-8")
        run = self.data / "state" / "run-1"
        run.mkdir(parents=True)
        (run / "result.json").write_text('{"status": "ok"}', encoding="utf-8")
        self.worktree = self.data / "workspaces" / "lane"
        self.worktree.mkdir(parents=True)
        (self.worktree / "owned.txt").write_text("baseline\n", encoding="utf-8")
        self.scratch = self.data / "worker-tmp"
        self.scratch.mkdir()
        self.outside = self.root / "outside"
        self.outside.mkdir()
        (self.outside / "private.txt").write_text("outside-private\n", encoding="utf-8")

        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.addCleanup(self.listener.close)
        self.port = self.listener.getsockname()[1]

        self._junction(self.worktree / "junction-data", self.data)
        self._junction(self.worktree / "junction-outside", self.outside)
        self.addCleanup(self._remove_junctions)
        self.env = dict(os.environ, MY_SENTINEL_SECRET=SENTINEL)

    @staticmethod
    def _junction(link, target):
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True, text=True,
        )
        if completed.returncode:
            raise AssertionError("junction setup failed: " + completed.stdout + completed.stderr)

    def _remove_junctions(self):
        for link in (self.worktree / "junction-data", self.worktree / "junction-outside"):
            try:
                os.rmdir(link)
            except OSError:
                pass

    def policy(self):
        policy = default_policy(
            self.ctx, self.worktree, [sys.executable, "-c", "pass"],
            temp_root=self.scratch, ttl=300,
        )
        return dataclasses.replace(policy, secrets=("MY_SENTINEL_SECRET",))

    def probe(self, policy):
        # Elevated sessions are refused by design; only an explicit opt-in may skip, so the matrix never goes quietly unrun.
        if policy is not None and os.environ.get("ORCH_ALLOW_ELEVATED_SKIP") == "1" and appcontainer._is_elevated():
            self.skipTest("elevated session; the matrix runs in the de-elevated CI step")
        command = [
            sys.executable, "-c", PROBE,
            str(self.data), str(self.key), str(self.outside),
            str(self.port), "MY_SENTINEL_SECRET",
        ]
        completed = execute(
            command, self.worktree, 180, env=self.env, policy=policy,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertNotIn(SENTINEL, completed.stdout + completed.stderr)
        lines = [line for line in completed.stdout.splitlines() if line.strip().startswith("{")]
        self.assertTrue(lines, completed.stdout + completed.stderr)
        return json.loads(lines[-1])

    def test_every_registered_negative_is_denied_and_every_allowed_case_passes(self):
        results = self.probe(self.policy())
        for name in PROBE_NEGATIVE_CASES:
            with self.subTest(case=name):
                self.assertIn(name, results)
                self.assertTrue(
                    results[name].startswith("denied:"),
                    f"{name} was not denied: {results[name]}",
                )
        for name in ALLOWED_CASES:
            with self.subTest(case=name):
                self.assertEqual(results[name], "ALLOWED")
        self.assertFalse((self.data / "planted.json").exists())
        self.assertFalse((self.outside / "planted.txt").exists())
        self.assertFalse((self.outside / "junction-planted.txt").exists())
        self.assertEqual((self.data / "state" / "run-1" / "result.json").read_text(encoding="utf-8"),
                         '{"status": "ok"}')

    def test_unsandboxed_control_proves_the_attacks_are_real(self):
        results = self.probe(None)
        for name in (
            "read_engine_key",
            "read_settings",
            "read_evidence",
            "env_secret_visible",
            "network_egress",
            "child_process_read_key",
            "read_outside_file",
            "write_outside_file",
        ):
            with self.subTest(case=name):
                self.assertEqual(results[name], "ALLOWED")

    def test_recursive_mcp_has_no_tools_and_rejects_tools_call(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "sec04", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "orchestrator_status", "arguments": {}}},
        ]
        replies = self._mcp(messages, delegated=True)
        self.assertEqual(replies[2]["result"]["tools"], [])
        self.assertNotIn("result", replies[3])
        self.assertIn("cannot delegate", replies[3]["error"]["message"])

        # Positive control: the same server without a worker identity does expose tools.
        replies = self._mcp(messages, delegated=False)
        self.assertTrue(replies[2]["result"]["tools"])
        self.assertFalse(replies[3]["result"]["isError"])

    def _mcp(self, messages, *, delegated):
        env = dict(os.environ)
        env.pop("RESPECTED_ORCH_DELEGATED", None)
        env.pop("RESPECTED_ORCH_CHILD", None)
        if delegated:
            env["RESPECTED_ORCH_CHILD"] = "1"
        payload = "\n".join(json.dumps(message) for message in messages) + "\n"
        completed = subprocess.run(
            [sys.executable, "-m", "respected_orchestrator", "--data-root", str(self.data), "mcp"],
            input=payload, capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        replies = {}
        for line in completed.stdout.splitlines():
            if line.strip().startswith("{"):
                reply = json.loads(line)
                if reply.get("id") is not None:
                    replies[reply["id"]] = reply
        self.assertIn(1, replies)
        self.assertIn(2, replies)
        self.assertIn(3, replies)
        return replies

    def test_symlink_mode_patch_is_rejected_before_export_or_apply(self):
        repo = self.root / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "SEC-04")
        git(repo, "config", "user.email", "sec04@example.invalid")
        (repo / "src").mkdir()
        (repo / "src" / "owned.txt").write_text("base\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "baseline")
        baseline = git(repo, "rev-parse", "HEAD").stdout.strip()

        # A worker without the Windows symlink privilege can still stage mode 120000
        # with git update-index and then put the link text in a regular worktree file.
        blob = git(repo, "hash-object", "-w", "--stdin", input="../../outside/private.txt").stdout.strip()
        git(repo, "update-index", "--add", "--cacheinfo", "120000", blob, "src/escape")
        (repo / "src" / "escape").write_text("../../outside/private.txt", encoding="utf-8")

        lane = lanes.Lane(repo_root=repo, worktree=repo, branch="", run_root=self.root / "lane",
                          baseline_commit=baseline)
        changes = lanes.collect_worker_changes(lane)
        self.assertIn("src/escape", changes.unsafe_paths)
        scope = lanes.validate_change_scope(changes, ("src",), ())
        self.assertFalse(scope.allowed)
        self.assertIn("src/escape", scope.violations)
        with self.assertRaises(lanes.LaneError):
            lanes.export_worker_patch(lane, self.root / "blocked.patch", ("src",))

        patch = self.root / "symlink.patch"
        patch.write_bytes(subprocess.run(
            ["git", "diff", "--binary", "--full-index", "HEAD"],
            cwd=repo, capture_output=True, check=True,
        ).stdout)
        self.assertIn(b"new file mode 120000", patch.read_bytes())
        self.assertEqual(
            lanes.check_patch_against_master(repo, patch),
            lanes.RunStatus.INTEGRATION_CONFLICT,
        )
        self.assertFalse((repo / "src" / "escape").is_symlink())


if __name__ == "__main__":
    unittest.main()
