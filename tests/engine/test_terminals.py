"""ADR-035: the agent's own terminal. A real terminal host process with a real pseudo console, on a temporary data root; the program in
it is a small Python script, never an agent. Windows only (ConPTY, named pipe)."""
import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import catalog, daemon, daemon_client, lanes, local_api, pty_host
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.terminals import TerminalError, Terminals

PID = "proj-1"
PROGRAM = ("import os, sys\n"
           "print('hazir', os.environ.get('RESPECTED_ORCH_CHILD'), sys.stdout.isatty(), flush=True)\n"
           "line = input()\n"
           "print('yanit', line, os.get_terminal_size().columns, flush=True)\n"
           "sys.exit(3)\n")


def b64(text):
    return base64.b64encode(text.encode()).decode()


def wait_for(cond, seconds=15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class Watcher:
    """Collects one attach stream on a thread: the bytes drawn so far and the exit code once it came."""

    def __init__(self, lines, pick=lambda note: note):
        self.data, self.exit, self.lines = b"", None, lines

        def read():
            for note in lines:
                note = pick(note)
                if "data" in note:
                    self.data += base64.b64decode(note["data"])
                if "exit" in note:
                    self.exit = note["exit"]
                    return

        self.thread = threading.Thread(target=read, daemon=True)
        self.thread.start()


@unittest.skipUnless(os.name == "nt", "ConPTY and the named pipe are Windows-only for now")
class TerminalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temporary.cleanup)
        self.root = str(Path(temporary.name).resolve())
        self.ctx = EngineContext(Path(self.root))
        self.engine = daemon.Daemon(self.ctx)  # the terminal host only talks to the engine that answers on this data root's pipe: this process
        self.notes = []
        self.terminals = self.engine.terminals = Terminals(self.ctx, lambda *note: self.notes.append(note), command=lambda agent: [sys.executable, "-c", PROGRAM])
        server = threading.Thread(target=self.engine._serve_pipe, daemon=True)
        server.start()
        self.addCleanup(lambda: (self.engine.stop(), server.join(10)))
        self.addCleanup(self.end_all)
        self.assertTrue(wait_for(lambda: daemon_client.status(self.ctx) is not None))

    def end_all(self):
        for record in self.terminals._records().values():
            try:
                self.terminals.kill(record["id"], record["project_id"])
            except (TerminalError, OSError):
                pass

    def test_a_program_runs_in_a_real_terminal_takes_input_and_outlives_its_viewers(self):
        started = self.terminals.start(PID, self.root, "opencode", cols=100, rows=30)
        tid = started["id"]
        self.assertEqual((started["alive"], started["cols"], started["agent"], started["project_root"]), (True, 100, "opencode", self.root))
        self.assertEqual(self.notes[0][:2], (PID, "terminal.state"))
        first = Watcher(self.terminals.attach(tid, PID))
        self.assertTrue(wait_for(lambda: b"hazir 1 True" in first.data), first.data)  # a real terminal, and the program is marked as a child
        self.assertEqual(self.terminals.resize(tid, PID, 90, 25), {"cols": 90, "rows": 25})
        # a second engine object (as after a restart) finds the terminal in the record and a late viewer gets what was already drawn
        again = Terminals(self.ctx)
        self.assertEqual([t["id"] for t in again.list(PID)], [tid])
        late = Watcher(again.attach(tid, PID))
        self.assertTrue(wait_for(lambda: b"hazir" in late.data))
        self.assertEqual(self.terminals.input(tid, PID, b64("selam\r")), {"sent": True})
        self.assertTrue(wait_for(lambda: first.exit == 3 and late.exit == 3))
        self.assertIn(b"yanit selam 90", first.data)
        self.assertIn(b"yanit selam 90", late.data)
        listed = self.terminals.list(PID)[0]
        self.assertEqual((listed["alive"], listed["exit"]), (False, 3))  # the host stays so the result can still be read
        # only the engine may talk to the host: another process of the same user gets no answer
        probe = ("import sys\n"
                 f"h = open({pty_host.pipe_path(tid)!r}, 'r+b', buffering=0)\n"
                 "h.write(b'{\"op\": \"status\"}\\n')\n"
                 "try:\n    print(repr(h.read(100)))\nexcept OSError:\n    print('closed')\n")
        answer = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=30).stdout.strip()
        self.assertIn(answer, ("closed", "b''"))
        # addressed by (terminal, project): the wrong project and an unknown id are refused the same way
        for bad in ((tid, "other"), ("term_0000000000000000", PID), (None, PID)):
            with self.assertRaises(TerminalError) as refused:
                self.terminals.input(*bad, b64("x"))
            self.assertEqual(refused.exception.reason, "TERMINAL_UNKNOWN")
        with self.assertRaises(TerminalError) as refused:
            self.terminals.input(tid, PID, "not base64!")
        self.assertEqual(refused.exception.reason, "INPUT_INVALID")
        host = self.terminals._records()[tid]["host_pid"]
        self.assertEqual(self.terminals.kill(tid, PID), {"killed": tid})
        self.assertTrue(wait_for(lambda: not lanes._pid_is_alive(host)))
        self.assertEqual((self.terminals.list(PID), self.notes[-1][1], self.notes[-1][2]["terminal"]["alive"]), ([], "terminal.state", False))

    def test_a_start_is_checked_before_anything_runs(self):
        for kwargs, reason in (({"project_root": "relative"}, "ROOT_INVALID"), ({"cols": 5}, "SIZE_INVALID"), ({"rows": "30"}, "SIZE_INVALID")):
            with self.assertRaises(TerminalError) as refused:
                self.terminals.start(PID, **{"project_root": self.root, "agent": "opencode", **kwargs})
            self.assertEqual(refused.exception.reason, reason)
        with self.assertRaises(TerminalError) as refused:
            Terminals(self.ctx).start(PID, self.root, "no-such-agent")
        self.assertEqual(refused.exception.reason, "AGENT_UNKNOWN")
        self.assertEqual(self.terminals._records(), {})

    def ask(self, cmd, payload):
        return daemon_client.request(self.ctx, cmd, {"project_id": PID, **payload}, timeout=30)

    def test_only_the_recognised_desktop_may_start_type_and_watch_and_the_stream_comes_over_the_engine_pipe(self):
        # every other caller of the shared pipe (MCP level) sees the list and nothing else
        self.assertEqual(self.ask("terminal.list", {})["result"], {"terminals": []})
        for cmd in ("terminal.start", "terminal.input", "terminal.resize", "terminal.kill", "terminal.attach"):
            self.assertEqual(self.ask(cmd, {"project_root": self.root})["error"]["code"], "FORBIDDEN", cmd)
        offered = {row["name"] for row in self.ask("catalog.list", {})["result"]["commands"]}
        self.assertEqual({name for name in offered if name.startswith("terminal.")}, {"terminal.list"})
        self.assertEqual(catalog.desktop("terminal"), ["terminal.list", "terminal.start", "terminal.input", "terminal.resize", "terminal.kill"])
        child = local_api.LocalApi(self.ctx, "t" * 32, origin=Origin.CHILD)
        self.assertEqual(child.handle({"ipc": "1", "id": "term-0000001", "session": "t" * 32, "cmd": "terminal.list", "payload": {}})["error"]["code"], "FORBIDDEN")
        with mock.patch.object(daemon, "classify", return_value=Origin.RENDERER):
            started = self.ask("terminal.start", {"project_root": self.root, "cols": 80, "rows": 24})
            self.assertTrue(started["ok"], started)
            tid = started["result"]["id"]
            self.assertEqual(self.ask("terminal.attach", {"terminal_id": "term_0000000000000000"})["error"]["reason"], "TERMINAL_UNKNOWN")
            handle = daemon_client._open(daemon.pipe_path(self.ctx))
            handle.write(json.dumps({"ipc": "1", "id": "attach-0001", "session": "-", "cmd": "terminal.attach", "payload": {"project_id": PID, "terminal_id": tid}}).encode() + b"\n")
            lines = daemon_client._lines(handle)
            self.assertEqual(next(lines)["result"], {"attached": tid})
            seen = []

            def pick(note):
                seen.append(note["event"])
                self.assertEqual((note["ipc"], note["data"]["terminal_id"], "id" in note), ("1", tid, False))
                return note["data"]

            watcher = Watcher(lines, pick)
            self.assertTrue(wait_for(lambda: b"hazir" in watcher.data))
            self.assertTrue(self.ask("terminal.input", {"terminal_id": tid, "data": b64("pipe\r")})["ok"])
            self.assertTrue(wait_for(lambda: watcher.exit == 3))
            self.assertIn(b"yanit pipe 80", watcher.data)
            self.assertTrue(set(seen) <= {"terminal.data", "terminal.exit", "terminal.ping"})
            self.assertEqual(self.ask("terminal.kill", {"terminal_id": tid})["result"], {"killed": tid})


if __name__ == "__main__":
    unittest.main()
