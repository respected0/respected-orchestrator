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

    def test_the_session_command_starts_the_engine_and_asks_it(self):
        def cli(*args):
            return subprocess.run(engine_command("--data-root", str(self.ctx.data_root), *args), capture_output=True, text=True, timeout=90, stdin=subprocess.DEVNULL)
        listed = cli("session", "list")
        self.assertEqual((listed.returncode, json.loads(listed.stdout)), (0, {"sessions": [], "conversations": []}))
        self.assertIsNotNone(daemon_client.status(self.ctx))  # asking started it (D4)
        self.assertEqual(cli("session", "nope").returncode, 2)
        stopped = cli("daemon", "stop")
        self.assertEqual(json.loads(stopped.stdout), {"running": False, "stopped": True})
        self.assertEqual(json.loads(cli("daemon", "status").stdout), {"running": False})  # and nothing answers for it afterwards

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

    def test_an_engine_of_another_build_of_the_same_version_is_refused(self):
        self.assertIsNone(daemon_client.start(self.ctx)["build"])  # not a packaged install: no build identity on either side
        with mock.patch.object(daemon_client, "build_id", return_value="a" * 64):
            with self.assertRaisesRegex(daemon_client.DaemonVersionMismatch, "another build"):
                daemon_client.start(self.ctx)

    def test_a_large_engine_log_is_set_aside_before_the_next_start(self):
        log = self.ctx.state_dir / "daemon.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_bytes(b"x" * 50)
        with mock.patch.object(daemon_client, "LOG_LIMIT", 10):
            daemon_client.start(self.ctx)
        self.assertEqual(log.with_name("daemon.log.1").read_bytes(), b"x" * 50)
        self.assertNotIn(b"x" * 50, log.read_bytes())  # the new engine writes to a fresh file

    def test_an_idle_engine_leaves(self):
        with mock.patch.dict(os.environ, {"RESPECTED_DAEMON_IDLE_SECONDS": "1"}):
            pid = daemon_client.start(self.ctx)["pid"]
        deadline = time.monotonic() + 30  # no polling through the pipe: asking would count as activity
        while lanes._pid_is_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.5)
        self.assertFalse(lanes._pid_is_alive(pid))


class DaemonSessionTests(unittest.TestCase):
    """ADR-030 slice 2: the sessions belong to the engine, not to a connection."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ctx = EngineContext(Path(self.temporary.name).resolve())
        self.engine = daemon.Daemon(self.ctx)

    def ask(self, api, token, cmd, payload):
        return api.handle({"ipc": "1", "id": "t-" + cmd.replace(".", "-") + "-1", "session": token, "cmd": cmd, "payload": payload})

    def test_a_session_one_connection_has_is_listed_by_every_other(self):
        self.engine.sessions.register(Origin.MCP, "ses_abcdefgh12", "p1", "opencode", "opencode/x-free", self.temporary.name)
        first, second = self.engine.api(Origin.MCP, "a" * 32), self.engine.api(Origin.MCP, "b" * 32)
        for api, token in ((first, "a" * 32), (second, "b" * 32)):
            reply = self.ask(api, token, "sessions.list", {"project_id": "p1"})
            self.assertEqual([s["id"] for s in reply["result"]["sessions"]], ["ses_abcdefgh12"])
        self.assertIs(first.sessions, second.sessions)

    def test_the_default_agent_cannot_be_changed_over_the_shared_pipe(self):
        reply = self.ask(self.engine.api(Origin.MCP, "a" * 32), "a" * 32, "session.defaults.set", {"agent": "opencode", "model": "opencode/x-free"})
        self.assertEqual(reply["error"]["code"], "FORBIDDEN")

    def test_the_engine_stays_while_a_session_works_and_may_leave_when_none_does(self):
        self.engine.sessions.register(Origin.MCP, "ses_abcdefgh12", "p1", "opencode", "opencode/x-free", self.temporary.name, handle=object())
        self.assertTrue(self.engine.busy())
        self.engine.sessions._sessions["ses_abcdefgh12"]["state"] = "idle"  # an idle session is saved and can resume: it does not hold the engine
        self.assertFalse(self.engine.busy())

    def test_the_first_start_of_a_packaged_engine_records_the_install_and_a_bad_folder_is_only_reported(self):
        from respected_orchestrator.interfaces import installation
        with mock.patch.object(daemon.sys, "frozen", True, create=True),                 mock.patch.object(installation, "verify", return_value={"install_state": "absent"}),                 mock.patch.object(installation, "setup", return_value={"status": "installed"}) as setup:
            self.engine._complete_install()
            setup.assert_called_once()
        with mock.patch.object(daemon.sys, "frozen", True, create=True),                 mock.patch.object(installation, "verify", return_value={"install_state": "repair-needed"}),                 mock.patch.object(installation, "setup", side_effect=installation.OperationError("VERIFY_FAILED", "mismatch", "reinstall")):
            self.engine._complete_install()  # reported, does not raise
        with mock.patch.object(daemon.sys, "frozen", True, create=True),                 mock.patch.object(installation, "verify", return_value={"install_state": "installed"}),                 mock.patch.object(installation, "setup") as setup:
            self.engine._complete_install()
            setup.assert_not_called()
        with mock.patch.object(installation, "setup") as setup:  # running from source: nothing to record
            self.engine._complete_install()
            setup.assert_not_called()

    def test_a_session_start_with_a_bad_folder_is_refused_by_the_engine(self):
        reply = self.ask(self.engine.api(Origin.MCP, "a" * 32), "a" * 32, "session.start", {"project_id": "p1", "project_root": "C:\nowhere", "text": "hi"})
        self.assertEqual((reply["ok"], reply["error"]["reason"]), (False, "ROOT_INVALID"))


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
        with mock.patch("respected_orchestrator.engine.supervisor.run_pids", return_value={"run-1": os.getpid()}):
            self.assertIs(daemon.classify(self.ctx, os.getpid()), Origin.CHILD)
            self.assertIs(daemon.classify(self.ctx, child.pid), Origin.CHILD)  # a descendant, however deep
        with mock.patch("respected_orchestrator.engine.supervisor.run_pids", return_value={"run-1": 4}):
            self.assertIs(daemon.classify(self.ctx, child.pid), Origin.MCP)  # unrelated: read and task only
        with mock.patch("respected_orchestrator.engine.supervisor.run_pids", return_value={}):
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

    def test_agents_die_with_the_engine_but_a_detached_run_does_not(self):
        script = """
import subprocess, sys, time
from respected_orchestrator.engine import winproc
winproc.contain_children()
sleeper = [sys.executable, "-c", "import time; time.sleep(120)"]
agent = subprocess.Popen(sleeper)
run = subprocess.Popen(sleeper, creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB)
print(agent.pid, run.pid, flush=True)
time.sleep(120)
"""
        engine = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
        agent, run = map(int, engine.stdout.readline().split())
        self.addCleanup(lambda: subprocess.run(["taskkill", "/PID", str(run), "/F"], capture_output=True))
        self.addCleanup(engine.stdout.close)
        self.assertTrue(lanes._pid_is_alive(agent) and lanes._pid_is_alive(run))
        subprocess.run(["taskkill", "/PID", str(engine.pid), "/F"], capture_output=True)  # a crash: nothing gets to clean up
        engine.wait()
        deadline = time.monotonic() + 10
        while lanes._pid_is_alive(agent) and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertFalse(lanes._pid_is_alive(agent))
        self.assertTrue(lanes._pid_is_alive(run))

    def test_only_the_installed_desktop_program_is_recognised_and_gets_settings(self):
        app = Path(self.temporary.name) / "app"
        app.mkdir()
        exe = app / daemon.DESKTOP_EXE
        exe.write_bytes(b"desktop v1")
        import hashlib
        (app / "distribution.json").write_text(json.dumps({"files": {daemon.DESKTOP_EXE: hashlib.sha256(b"desktop v1").hexdigest()}}), encoding="utf-8")
        with mock.patch.object(winproc, "process_image", return_value=str(exe)):
            self.assertTrue(daemon.is_desktop(1, app))
        with mock.patch.object(winproc, "process_image", return_value=str(app / "other.exe")):
            self.assertFalse(daemon.is_desktop(1, app))  # another program, even in the same folder
        with mock.patch.object(winproc, "process_image", return_value=None):
            self.assertFalse(daemon.is_desktop(1, app))
        exe.write_bytes(b"desktop v1 + implant")  # replaced after packaging: no longer the listed file
        with mock.patch.object(winproc, "process_image", return_value=str(exe)):
            self.assertFalse(daemon.is_desktop(1, app))
        (app / "distribution.json").write_text("{}", encoding="utf-8")
        with mock.patch.object(winproc, "process_image", return_value=str(exe)):
            self.assertFalse(daemon.is_desktop(1, app))
        self.assertFalse(daemon.is_desktop(1))  # not a packaged engine: nobody qualifies
        self.assertIn("session.defaults.set", daemon.SERVED_DESKTOP)
        self.assertTrue({"approval.decide", "approval.apply", "attachment.commit"}.isdisjoint(daemon.SERVED_DESKTOP))

    def test_each_data_root_has_its_own_pipe(self):
        other = EngineContext(Path(self.temporary.name).resolve() / "other")
        self.assertNotEqual(daemon.pipe_name(self.ctx), daemon.pipe_name(other))


if __name__ == "__main__":
    unittest.main()
