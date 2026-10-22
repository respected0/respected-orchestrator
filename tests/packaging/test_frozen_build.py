"""The packaged engine works with no Python on PATH: RPP, MCP, and a real write task through its detached supervisor
and the restricted-token acceptance sandbox (the two paths that start the engine again from inside itself).

Needs a build in dist/ (python packaging/build_dist.py) or RESPECTED_ORCH_DIST; skipped locally without one, required in CI.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
DIST = Path(os.environ.get("RESPECTED_ORCH_DIST") or ROOT / "dist" / "RespectedOrchestrator")
EXE = DIST / ("respected-orchestrator.exe" if os.name == "nt" else "respected-orchestrator")


@unittest.skipUnless(os.name == "nt", "the packaged build is Windows-only for now")
class FrozenBuildTest(unittest.TestCase):
    def setUp(self):
        if not EXE.is_file():
            if os.environ.get("CI"):
                self.fail(f"packaged build missing: {EXE}")
            self.skipTest("no packaged build in dist/ (python packaging/build_dist.py)")
        temporary = tempfile.TemporaryDirectory(prefix="orch-frozen-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.data = self.root / "data"
        git = Path(shutil.which("git")).parent
        system = Path(os.environ["SystemRoot"]) / "System32"
        # no Python anywhere on PATH: only the engine's own executable can serve these commands
        self.env = {**os.environ, "PATH": os.pathsep.join([str(system), str(git)]), "PYTHONPATH": "", "PYTHONHOME": ""}

    def engine(self, *args, stdin=None, timeout=60):
        done = subprocess.run([str(EXE), "--data-root", str(self.data), *args], input=stdin, cwd=self.root, env=self.env,
                              capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return done.returncode, done.stdout, done.stderr

    def json_call(self, *args, stdin=None):
        code, out, err = self.engine(*args, stdin=stdin)
        self.assertEqual(code, 0, out + err)
        return json.loads(out)

    def test_selfcheck_and_status_without_python(self):
        self.assertEqual(self.json_call("_selfcheck")["status"], "ok")
        status = self.json_call("status")
        self.assertEqual(status["data_root"], str(self.data))

    def test_rpp_manifest_and_health(self):
        for op in ("manifest", "health"):
            code, out, err = self.engine("rpp", stdin=json.dumps({"rpp": "1", "op": op, "payload": {}}))
            reply = json.loads(out)
            self.assertTrue(reply["ok"], out + err)

    def test_mcp_lists_tools(self):
        lines = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                  "clientInfo": {"name": "test", "version": "1"}}},
                 {"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
        code, out, err = self.engine("mcp", stdin="\n".join(json.dumps(line) for line in lines) + "\n")
        replies = [json.loads(line) for line in out.splitlines() if line.strip().startswith("{")]
        tools = next(reply for reply in replies if reply.get("id") == 2)["result"]["tools"]
        self.assertTrue(tools, err)

    def test_write_task_runs_detached_and_passes_sandboxed_acceptance(self):
        repo = self.root / "project"
        repo.mkdir()
        for args in (("init", "-b", "main"), ("config", "user.name", "Fixture"), ("config", "user.email", "fixture@example.invalid")):
            subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
        (repo / "owned.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=repo, check=True, capture_output=True)
        worker = [sys.executable, "-c", "from pathlib import Path; Path('owned.txt').write_text('changed\\n')"]
        accept = [sys.executable, "-c", "from pathlib import Path; assert Path('owned.txt').read_text() == 'changed\\n'"]
        request = dict(project_root=str(repo), task="frozen smoke", worker="custom", kind="write", ownership=["owned.txt"],
                       command=worker, acceptance=[accept], timeout_seconds=60)
        run_id = self.json_call("create", stdin=json.dumps(request))["run_id"]
        self.json_call("start", run_id)
        deadline = time.monotonic() + 120
        while True:
            state = self.json_call("inspect", run_id)
            if state.get("status") not in ("queued", "running", "starting", None):
                break
            self.assertLess(time.monotonic(), deadline, state)
            time.sleep(1)
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(self.json_call("check", run_id)["status"], "verified")
        self.assertEqual((repo / "owned.txt").read_text(encoding="utf-8"), "base\n", "nothing is applied without approval")


if __name__ == "__main__":
    unittest.main()
