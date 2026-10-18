"""Adversarial checks of the worker-code trust boundary (sandbox.py / sandbox_exec.py). Windows only."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator import runner, sandbox
from respected_orchestrator.context import EngineContext
from respected_orchestrator.processes import execute

# Everything an attacker-controlled acceptance command would try. Each entry is "name: outcome".
PROBE = r'''
import json, os, subprocess, sys
data, key, worktree = sys.argv[1:4]
out = {}
def attempt(name, action):
    try:
        action(); out[name] = "ALLOWED"
    except Exception as error:
        out[name] = "denied:" + type(error).__name__
attempt("read_key", lambda: open(key, "rb").read())
attempt("read_settings", lambda: open(os.path.join(data, "settings.json")).read())
attempt("read_evidence", lambda: open(os.path.join(data, "state", "run-1", "result.json")).read())
attempt("forge_approval", lambda: open(os.path.join(data, "state", "run-1", "maf-approval.json"), "w").write("{}"))
attempt("overwrite_evidence", lambda: open(os.path.join(data, "state", "run-1", "result.json"), "w").write("{}"))
attempt("delete_evidence", lambda: os.remove(os.path.join(data, "state", "run-1", "result.json")))
attempt("new_file_in_state", lambda: open(os.path.join(data, "state", "x.json"), "w").write("{}"))
attempt("new_file_in_data_root", lambda: open(os.path.join(data, "planted.json"), "w").write("{}"))
def regrant():
    r = subprocess.run(["icacls", key, "/grant", "Everyone:F"], capture_output=True, text=True)
    if r.returncode: raise PermissionError(r.stdout + r.stderr)
attempt("rewrite_key_acl", regrant)
def drop_deny():
    r = subprocess.run(["icacls", os.path.join(data, "state"), "/remove:d", sys.argv[4]], capture_output=True, text=True)
    if r.returncode: raise PermissionError(r.stdout + r.stderr)
attempt("remove_deny_ace", drop_deny)
attempt("read_key_via_long_path_prefix", lambda: open("\\\\?\\" + key, "rb").read())
attempt("hardlink_key_into_worktree", lambda: os.link(key, os.path.join(worktree, "stolen-key")))
def junction():
    r = subprocess.run(["cmd", "/c", "mklink", "/J", os.path.join(worktree, "j"), data], capture_output=True, text=True)
    if r.returncode: raise PermissionError(r.stdout + r.stderr)
    open(os.path.join(worktree, "j", ".engine-key"), "rb").read()
attempt("read_key_via_junction", junction)
def setowner():
    r = subprocess.run(["icacls", key, "/setowner", os.environ.get("USERNAME", "x")], capture_output=True, text=True)
    if r.returncode: raise PermissionError(r.stdout + r.stderr)
attempt("take_ownership", setowner)
attempt("write_worktree", lambda: open(os.path.join(worktree, "ok.txt"), "w").write("x"))
attempt("read_worktree", lambda: open(os.path.join(worktree, "ok.txt")).read())
attempt("spawn_child", lambda: subprocess.run([sys.executable, "-c", "print(1)"], check=True, capture_output=True))
print(json.dumps(out))
'''


@unittest.skipUnless(os.name == "nt", "restricted tokens are a Windows mechanism")
class SandboxBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="orch-sbx-"))
        self.ctx = EngineContext(self.root / "data")
        self.ctx.data_root.mkdir(parents=True)
        (self.ctx.data_root / "settings.json").write_text('{"memory_token": "rbm_secret"}', encoding="utf-8")
        run = self.ctx.data_root / "state" / "run-1"
        run.mkdir(parents=True)
        (run / "result.json").write_text('{"status": "ok"}', encoding="utf-8")
        self.key_path = self.ctx.data_root / ".engine-key"
        runner._key(self.ctx)                      # created the way the engine does (private ACL)
        self.worktree = self.ctx.data_root / "workspaces" / "lane"
        self.worktree.mkdir(parents=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))

    def probe(self):
        command = sandbox.wrap(self.ctx.data_root, self.key_path, [sys.executable, "-c", PROBE, str(self.ctx.data_root), str(self.key_path),
                                                                    str(self.worktree), "*" + sandbox.sandbox_sid(self.ctx.data_root)])
        done = execute(command, self.worktree, 120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_sandboxed_code_cannot_reach_the_key_the_evidence_or_the_acls(self):
        result = self.probe()
        for name in ("read_key", "read_settings", "read_evidence", "forge_approval", "overwrite_evidence", "delete_evidence",
                     "new_file_in_state", "new_file_in_data_root", "rewrite_key_acl", "remove_deny_ace",
                     "read_key_via_long_path_prefix", "hardlink_key_into_worktree", "read_key_via_junction", "take_ownership"):
            self.assertTrue(result[name].startswith("denied"), f"{name}: {result[name]}")
        # untouched afterwards, and the engine itself (no restricting SID) still works as before
        self.assertEqual(len(runner._key(self.ctx)), 32)
        self.assertEqual(json.loads((self.ctx.data_root / "state" / "run-1" / "result.json").read_text("utf-8")), {"status": "ok"})
        self.assertFalse((self.ctx.data_root / "state" / "run-1" / "maf-approval.json").exists())
        self.assertFalse((self.ctx.data_root / "planted.json").exists())
        self.assertFalse((self.worktree / "stolen-key").exists())

    def test_control_the_same_probe_without_the_sandbox_gets_everywhere(self):
        """Negative control: proves the probes are real attacks (they succeed as the plain user), so 'denied' above means the boundary."""
        done = execute([sys.executable, "-c", PROBE, str(self.ctx.data_root), str(self.key_path), str(self.worktree), "*S-1-1-0"], self.worktree, 120)
        result = json.loads(done.stdout.strip().splitlines()[-1])
        for name in ("read_key", "read_settings", "read_evidence", "forge_approval", "overwrite_evidence", "new_file_in_state",
                     "new_file_in_data_root", "read_key_via_long_path_prefix", "hardlink_key_into_worktree", "read_key_via_junction"):
            self.assertEqual(result[name], "ALLOWED", f"{name}: {result[name]}")

    def test_the_worker_area_and_ordinary_tools_keep_working(self):
        result = self.probe()
        for name in ("write_worktree", "read_worktree", "spawn_child"):
            self.assertEqual(result[name], "ALLOWED", f"{name}: {result[name]}")
        self.assertEqual((self.worktree / "ok.txt").read_text("utf-8"), "x")

    def test_signed_evidence_cannot_be_forged_without_the_key(self):
        payload = {"run_id": "run-1", "status": "approved"}
        genuine = runner._signature(self.ctx, payload)
        self.assertEqual(len(genuine), 64)
        script = ("import sys; sys.path.insert(0, sys.argv[1]); from respected_orchestrator import runner;"
                  "from respected_orchestrator.context import EngineContext; from pathlib import Path;"
                  "runner._signature(EngineContext(Path(sys.argv[2])), {'x': 1})")
        src = str(Path(runner.__file__).resolve().parents[1])
        command = sandbox.wrap(self.ctx.data_root, self.key_path, [sys.executable, "-c", script, src, str(self.ctx.data_root)])
        done = execute(command, self.worktree, 120)
        self.assertNotEqual(done.returncode, 0, "the sandboxed engine call must not obtain the signing key")

    def test_setup_is_idempotent_and_off_switch_is_explicit(self):
        first = sandbox.protect(self.ctx.data_root, self.key_path)
        self.assertEqual(sandbox.protect(self.ctx.data_root, self.key_path), first)
        self.assertEqual(first, sandbox.sandbox_sid(self.ctx.data_root))
        os.environ["RESPECTED_ORCH_SANDBOX"] = "off"
        try:
            self.assertEqual(sandbox.wrap(self.ctx.data_root, self.key_path, ["x"]), ["x"])
        finally:
            del os.environ["RESPECTED_ORCH_SANDBOX"]


if __name__ == "__main__":
    unittest.main()
