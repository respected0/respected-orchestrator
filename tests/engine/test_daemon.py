"""ADR-030 slice 1: the persistent engine. Real daemon processes on a temporary data root; Windows only (named pipe)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator import __version__
from respected_orchestrator.context import EngineContext, engine_command
from respected_orchestrator.engine import daemon, daemon_client, lanes, local_api, winproc
from respected_orchestrator.engine.authority import Action, Origin

WINDOWS = os.name == "nt"


@unittest.skipUnless(WINDOWS, "named pipe transport is Windows-only for now")
class DaemonProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ctx = EngineContext(Path(self.temporary.name).resolve())
        self.addCleanup(self.stop_quietly)

    def stop_quietly(self):
        try:
            daemon_client.stop(self.ctx)
        except daemon_client.DaemonUnavailable:
            pass

    def test_start_status_restart_stop(self):
        self.assertIsNone(daemon_client.status(self.ctx))
        first = daemon_client.start(self.ctx)
        self.assertEqual((first["version"], first["data_root"]), (__version__, str(self.ctx.data_root)))
        self.assertEqual(daemon_client.start(self.ctx)["pid"], first["pid"])  # already running: reused, not started twice
        daemon_client.stop(self.ctx)
        self.assertIsNone(daemon_client.status(self.ctx))
        self.assertFalse(daemon_client.stop(self.ctx))  # stopping nothing is not an error
        self.assertNotEqual(daemon_client.start(self.ctx)["pid"], first["pid"])

    def test_a_second_engine_on_the_same_data_root_refuses_to_run(self):
        daemon_client.start(self.ctx)
        done = subprocess.run(engine_command("--data-root", str(self.ctx.data_root), "_daemon"), capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 1)
        self.assertEqual(json.loads(done.stdout.splitlines()[0])["daemon"], "busy")
        self.assertIsNotNone(daemon_client.status(self.ctx))  # the owner is untouched

    def test_the_engine_answers_read_commands_and_never_serves_approval_or_settings_changes(self):
        daemon_client.start(self.ctx)
        self.assertTrue(daemon_client.request(self.ctx, "engine.health")["ok"])
        for command in ("approval.decide", "approval.apply", "settings.apply", "attachment.commit"):
            reply = daemon_client.request(self.ctx, command, {})
            self.assertEqual((reply["ok"], reply["error"]["code"]), (False, "FORBIDDEN"), command)

    def test_a_request_without_an_end_is_cut_off(self):
        daemon_client.start(self.ctx)
        reply = daemon_client._exchange(daemon.pipe_path(self.ctx), b"x" * (local_api.MAX_REQUEST_BYTES + 10), 10)
        self.assertEqual(reply["error"]["code"], "PAYLOAD_TOO_LARGE")

    def test_an_engine_of_another_version_is_refused_not_reused(self):
        daemon_client.start(self.ctx)
        with mock.patch.object(daemon_client, "__version__", "9.9.9"):
            with self.assertRaises(daemon_client.DaemonVersionMismatch):
                daemon_client.start(self.ctx)

    def test_an_idle_engine_leaves(self):
        with mock.patch.dict(os.environ, {"RESPECTED_DAEMON_IDLE_SECONDS": "1"}):
            pid = daemon_client.start(self.ctx)["pid"]
        deadline = time.monotonic() + 30  # no polling through the pipe: asking would count as activity
        while lanes._pid_is_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.5)
        self.assertFalse(lanes._pid_is_alive(pid))


@unittest.skipUnless(WINDOWS, "Windows process and security APIs")
class DaemonSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ctx = EngineContext(Path(self.temporary.name).resolve())

    def test_the_served_catalog_has_no_privileged_or_settings_command(self):
        actions = {local_api.COMMANDS[name][1] for name in daemon.SERVED}
        self.assertEqual(actions - {Action.READ, Action.TASK}, set())
        self.assertTrue({"approval.decide", "approval.apply", "settings.apply"}.isdisjoint(daemon.SERVED))

    def test_a_process_working_on_a_run_and_everything_below_it_gets_no_rights(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        with mock.patch("respected_orchestrator.engine.maintenance.run_pids", return_value={"run-1": os.getpid()}):
            self.assertIs(daemon.classify(self.ctx, os.getpid()), Origin.CHILD)
            self.assertIs(daemon.classify(self.ctx, child.pid), Origin.CHILD)  # a descendant, however deep
        with mock.patch("respected_orchestrator.engine.maintenance.run_pids", return_value={"run-1": 4}):
            self.assertIs(daemon.classify(self.ctx, child.pid), Origin.MCP)  # unrelated: read and task only
        with mock.patch("respected_orchestrator.engine.maintenance.run_pids", return_value={}):
            self.assertIs(daemon.classify(self.ctx, child.pid), Origin.MCP)

    def test_the_ancestor_chain_stops_at_a_reused_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        self.assertEqual(winproc.ancestors(child.pid)[0], os.getpid())
        self.assertEqual(winproc.ancestors(0), [])

    def test_the_pipe_is_open_to_the_current_user_alone(self):
        import win32api
        import win32con
        import win32security
        attributes = daemon._own_user_only()
        acl = attributes.SECURITY_DESCRIPTOR.GetSecurityDescriptorDacl()
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        me = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        self.assertEqual(acl.GetAceCount(), 1)
        self.assertEqual(acl.GetAce(0)[2], me)

    def test_each_data_root_has_its_own_pipe(self):
        other = EngineContext(Path(self.temporary.name).resolve() / "other")
        self.assertNotEqual(daemon.pipe_name(self.ctx), daemon.pipe_name(other))


if __name__ == "__main__":
    unittest.main()
