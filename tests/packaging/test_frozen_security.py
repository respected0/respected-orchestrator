"""SEC-04 frozen-executable coverage: the packaged engine enforces the same worker boundary."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from respected_orchestrator.engine import appcontainer
from tests.engine.security_cases import ALLOWED_CASES, PROBE, PROBE_NEGATIVE_CASES


ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get("RESPECTED_ORCH_DIST") or ROOT / "dist" / "RespectedOrchestrator")
EXE = DIST / ("respected-orchestrator.exe" if os.name == "nt" else "respected-orchestrator")
SENTINEL = "SEC04-SENTINEL-DO-NOT-LEAK"

PROBE_WORKER = (
    "import contextlib, io, json, os\n"
    f"PROBE = {PROBE!r}\n"
    "scope = {'__name__': '__main__'}\n"
    "with contextlib.redirect_stdout(io.StringIO()):\n"
    "    exec(PROBE, scope)\n"
    "for name in ('junction-data', 'junction-outside'):\n"
    "    try:\n"
    "        os.rmdir(os.path.join(os.getcwd(), name))\n"
    "    except OSError:\n"
    "        pass\n"
    "print(json.dumps({'status': 'success', 'security': scope['results']}, sort_keys=True))\n"
)


@unittest.skipUnless(os.name == "nt", "the packaged worker boundary is Windows-only")
class FrozenSecurityTest(unittest.TestCase):
    def setUp(self):
        if not EXE.is_file():
            if os.environ.get("CI"):
                self.fail(f"packaged build missing: {EXE}")
            self.skipTest("no packaged build in dist/ (python packaging/build_dist.py)")
        temporary = tempfile.TemporaryDirectory(prefix="orch-sec04-frozen-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.data = self.root / "data"
        self.outside = self.root / "outside"
        self.outside.mkdir()
        (self.outside / "private.txt").write_text("outside-private\n", encoding="utf-8")
        git = Path(shutil.which("git")).parent
        system = Path(os.environ["SystemRoot"]) / "System32"
        self.env = {
            **os.environ,
            "PATH": os.pathsep.join([str(system), str(git)]),
            "PYTHONPATH": "",
            "PYTHONHOME": "",
            "MY_SENTINEL_SECRET": SENTINEL,
        }
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.addCleanup(self.listener.close)
        self.port = self.listener.getsockname()[1]

    def engine(self, *args, stdin=None, timeout=90):
        return subprocess.run(
            [str(EXE), "--data-root", str(self.data), *args],
            input=stdin, cwd=self.root, env=self.env, capture_output=True, text=True,
            encoding="utf-8", timeout=timeout,
        )

    def json_call(self, *args, stdin=None):
        completed = self.engine(*args, stdin=stdin)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def repo(self, name="project"):
        repo = self.root / name
        repo.mkdir()
        for args in (("init", "-b", "main"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")):
            subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
        (repo / "src").mkdir()
        (repo / "src" / "owned.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
        return repo

    def wait(self, run_id, timeout=120):
        deadline = time.monotonic() + timeout
        while True:
            state = self.json_call("inspect", run_id)
            if state.get("status") not in ("queued", "running", "starting", None):
                return state
            self.assertLess(time.monotonic(), deadline, state)
            time.sleep(1)

    def wait_for_workspace(self, run_id, timeout=60):
        deadline = time.monotonic() + timeout
        while True:
            state = self.json_call("inspect", run_id)
            workspace = state.get("workspace")
            if workspace and Path(workspace).is_dir():
                return Path(workspace), state
            if state.get("status") not in ("queued", "running", "starting", None):
                self.fail(state)
            self.assertLess(time.monotonic(), deadline, state)
            time.sleep(0.1)

    def create(self, repo, command, *, ownership=("src",)):
        request = dict(
            project_root=str(repo), task="SEC-04 frozen adversarial matrix",
            worker="custom", kind="write", ownership=list(ownership), command=command,
            acceptance=[[sys.executable, "-c", "pass"]], timeout_seconds=90,
        )
        return self.json_call("create", stdin=json.dumps(request))["run_id"]

    def run_task(self, repo, command, *, ownership=("src",)):
        run_id = self.create(repo, command, ownership=ownership)
        self.json_call("start", run_id)
        return run_id, self.wait(run_id)

    def skip_if_elevated(self):
        # Elevated sessions are refused by design; only an explicit opt-in may skip (hosted CI runners are elevated).
        if os.environ.get("ORCH_ALLOW_ELEVATED_SKIP") == "1" and appcontainer._is_elevated():
            self.skipTest("elevated session; the worker boundary is refused")

    def test_frozen_worker_denies_every_registered_attack_and_allows_normal_work(self):
        self.skip_if_elevated()
        repo = self.repo()
        key = self.data / ".engine-key"
        run_id = self.create(repo, [
            sys.executable, "-c", PROBE_WORKER, str(self.data), str(key), str(self.outside),
            str(self.port), "MY_SENTINEL_SECRET",
        ])
        self.assertTrue(key.is_file(), "create must materialize the protected signing key")
        (self.data / "settings.json").write_text('{"memory_token": "secret"}', encoding="utf-8")
        evidence = self.data / "state" / "run-1"
        evidence.mkdir(parents=True)
        (evidence / "result.json").write_text('{"status": "ok"}', encoding="utf-8")
        self.json_call("start", run_id)
        state = self.wait(run_id)
        run_log = self.data / "state" / run_id / "stdout.log"
        output = run_log.read_text(encoding="utf-8") if run_log.is_file() else ""
        self.assertEqual(state["status"], "completed", state | {"stdout": output[-2000:]})
        payload = json.loads(output.strip().splitlines()[-1])
        self.assertEqual(payload["status"], "success")
        results = payload["security"]
        for name in PROBE_NEGATIVE_CASES:
            with self.subTest(case=name):
                self.assertTrue(results[name].startswith("denied:"), f"{name}: {results[name]}")
        for name in ALLOWED_CASES:
            with self.subTest(case=name):
                self.assertEqual(results[name], "ALLOWED")
        self.assertNotIn(SENTINEL, output)
        self.assertFalse((self.data / "planted.json").exists())
        self.assertFalse((self.outside / "planted.txt").exists())
        self.assertEqual((evidence / "result.json").read_text(encoding="utf-8"), '{"status": "ok"}')

    def test_frozen_engine_rejects_a_symlink_mode_patch_staged_without_symlink_privilege(self):
        self.skip_if_elevated()
        repo = self.repo("symlink-project")
        marker = ".sec04-staged.ready"
        target = "../../outside/private.txt"
        worker = (
            "import json, time\n"
            "from pathlib import Path\n"
            f"marker = Path({marker!r})\n"
            "deadline = time.time() + 60\n"
            "while not marker.exists():\n"
            "    if time.time() > deadline:\n"
            "        raise SystemExit(2)\n"
            "    time.sleep(0.1)\n"
            f"Path('src/escape').write_text({target!r}, encoding='utf-8')\n"
            "marker.unlink(missing_ok=True)\n"
            "print(json.dumps({'status': 'success'}))\n"
        )
        run_id = self.create(repo, [sys.executable, "-c", worker])
        self.json_call("start", run_id)
        workspace, _ = self.wait_for_workspace(run_id)
        # The AppContainer worker cannot reach the linked worktree's .git metadata.
        # Stage the adversarial index mode from the harness, then let the worker
        # mask it with a regular file: this is the exact no-symlink-privilege attack.
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"], cwd=workspace, input=target,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-index", "--add", "--cacheinfo", f"120000,{blob},src/escape"],
            cwd=workspace, check=True, capture_output=True,
        )
        (workspace / marker).write_text("staged\n", encoding="utf-8")
        state = self.wait(run_id)
        self.assertEqual(state["status"], "failed", state)
        self.assertEqual(state.get("reason"), "scope_violation", state)
        self.assertIn("src/escape", state.get("changed_files", []), state)
        self.assertFalse((self.data / "state" / run_id / "worker.patch").exists())

    def test_frozen_mcp_refuses_recursive_delegation(self):
        lines = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "sec04-frozen", "version": "1"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "orchestrator_status", "arguments": {}}},
        ]
        env = dict(self.env, RESPECTED_ORCH_CHILD="1")
        completed = subprocess.run(
            [str(EXE), "--data-root", str(self.data), "mcp"],
            input="\n".join(json.dumps(line) for line in lines) + "\n",
            cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        replies = {reply["id"]: reply for reply in map(json.loads, completed.stdout.splitlines())
                   if reply.get("id") is not None}
        self.assertEqual(replies[2]["result"]["tools"], [])
        self.assertIn("cannot delegate", replies[3]["error"]["message"])


if __name__ == "__main__":
    unittest.main()
