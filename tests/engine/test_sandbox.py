"""FIX-04 / ADR-018: acceptance and project verify run in the network-denied AppContainer, fail closed.

The control runs the same connection script unsandboxed against a local listener, so a "denied" below means the boundary
and not a broken script. Windows only.
"""
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import appcontainer, sandbox
from respected_orchestrator.engine.evidence import key_path
from respected_orchestrator.engine.processes import execute
from respected_orchestrator.engine.worker_policy import SandboxStartError

CONNECT = """import socket, subprocess, sys
def go(host, port):
    try:
        socket.create_connection((host, int(port)), 3).close()
        return "connected"
    except OSError:
        return "denied"
mode = sys.argv[1]
if mode == "dns":
    try:
        socket.getaddrinfo("example.com", 443)
        print("connected")
    except OSError:
        print("denied")
elif mode == "child":
    print(subprocess.run([sys.executable, sys.argv[0], "tcp", sys.argv[2], sys.argv[3]], capture_output=True, text=True).stdout.strip())
else:
    print(go(sys.argv[2], sys.argv[3]))
"""

PROBE = """import sys
for path, mode in ((sys.argv[1], "rb"), (sys.argv[2] + "/planted", "w")):
    try:
        open(path, mode)
        print("ALLOWED")
    except OSError:
        print("denied")
open("ok.txt", "w").write("x")
"""


@unittest.skipUnless(os.name == "nt", "AppContainer is Windows only")
class VerifyIsolationTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="orch-sbx-")).resolve()
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        self.ctx = EngineContext(self.root / "data")
        self.ctx.data_root.mkdir(parents=True)
        self.key = key_path(self.ctx)
        self.worktree = self.ctx.data_root / "workspaces" / "lane"
        self.worktree.mkdir(parents=True)
        (self.worktree / "connect.py").write_text(CONNECT, encoding="utf-8")
        (self.worktree / "probe.py").write_text(PROBE, encoding="utf-8")
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(8)
        self.addCleanup(self.listener.close)
        threading.Thread(target=self.accept_forever, daemon=True).start()
        self.port = self.listener.getsockname()[1]

    def accept_forever(self):
        try:
            while True:
                self.listener.accept()
        except OSError:
            pass

    def run_script(self, script, *args, task="run-1"):
        return sandbox.run_check(self.ctx, [sys.executable, script, *map(str, args)], self.worktree, 60,
                                 task_id=task, scratch=self.root / "scratch")

    def test_control_the_same_script_connects_without_the_boundary(self):
        done = execute([sys.executable, "connect.py", "tcp", "127.0.0.1", str(self.port)], self.worktree, 60)
        self.assertEqual(done.stdout.strip(), "connected")

    def test_ip_dns_loopback_and_child_process_egress_are_denied(self):
        for args in (("tcp", "127.0.0.1", self.port), ("tcp", "1.1.1.1", 443), ("dns",), ("child", "127.0.0.1", self.port)):
            with self.subTest(args=args):
                done, network = self.run_script("connect.py", *args)
                self.assertEqual((done.stdout.strip(), network), ("denied", "deny"), done.stderr)

    def test_network_exception_is_per_task_and_recorded(self):
        # AppContainer loopback stays blocked even with internetClient, so assert the mode handed to the container.
        real = appcontainer.spawn
        modes = []
        def spy(*args, **kwargs):
            modes.append(kwargs["network_mode"])
            return real(*args, **kwargs)
        with mock.patch.dict(os.environ, {"RESPECTED_VERIFY_NETWORK_TASKS": "run-allowed, other"}), mock.patch.object(appcontainer, "spawn", spy):
            _, allowed = self.run_script("connect.py", "dns", task="run-allowed")
            _, denied = self.run_script("connect.py", "dns", task="run-2")
        self.assertEqual((allowed, denied, modes), ("allow", "deny", ["allow", "deny"]))

    def test_engine_key_and_data_root_are_unreachable_and_the_worktree_works(self):
        done, _ = self.run_script("probe.py", self.key, self.ctx.data_root)
        self.assertEqual(done.stdout.split(), ["denied", "denied"], done.stderr)
        self.assertEqual((self.worktree / "ok.txt").read_text("utf-8"), "x")
        self.assertFalse((self.ctx.data_root / "planted").exists())

    def test_tool_under_program_files_runs_without_editing_its_acl(self):
        git = shutil.which("git")
        if not git or "program files" not in git.casefold():
            self.skipTest("git is not under Program Files here")
        real_grant = appcontainer._grant
        edited = []
        with mock.patch.object(appcontainer, "_grant", side_effect=lambda path, sid, rights: (edited.append(str(path)), real_grant(path, sid, rights))[1]):
            done, _ = sandbox.run_check(self.ctx, [git, "--version"], self.worktree, 60, task_id="run-1", scratch=self.root / "scratch")
        # hosted git 2.56 cannot open /dev/null inside the container (rc=128, FIX-01/ADR-018): the claim here is only "started, ACL untouched"
        self.assertIn(done.returncode, (0, 128), done.stderr)
        self.assertFalse([path for path in edited if "program files" in path.casefold()], edited)

    def test_fails_closed_without_a_container_and_ignores_the_off_switch(self):
        with mock.patch.dict(os.environ, {"RESPECTED_ORCH_SANDBOX": "off"}), \
                mock.patch.object(appcontainer, "spawn", side_effect=SandboxStartError("unsupported_elevated")):
            with self.assertRaises(sandbox.SandboxError):
                self.run_script("connect.py", "dns")
        (self.worktree / "x.cmd").write_text("@echo hi", encoding="utf-8")
        with self.assertRaises(sandbox.SandboxError):
            sandbox.run_check(self.ctx, [str(self.worktree / "x.cmd")], self.worktree, 60, task_id="run-1", scratch=self.root / "scratch")
        with mock.patch.object(sandbox.os, "name", "posix"), self.assertRaises(sandbox.SandboxError):
            self.run_script("connect.py", "dns")


if __name__ == "__main__":
    unittest.main()
