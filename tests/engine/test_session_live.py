"""Opt-in live session against a real FREE model (kept apart from the P0 gate groups so its skip is not a gate skip).

    RESPECTED_TEST_SANDBOX=real RESPECTED_LIVE_CHAT=1 python -m unittest tests.engine.test_session_live
"""
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from respected_orchestrator.engine import chat_session
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.session_control import SessionController

PID = "proj-1"
MODEL = "opencode/deepseek-v4.1-flash-free"


def wait_for(cond, seconds=120):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.25)
    return False


def descendants(pid):
    """Every live process below `pid` (Windows): the agent CLI is a launcher that starts the real process."""
    script = (f"$all = Get-CimInstance Win32_Process; $q = @({pid}); $out = @(); "
              "while ($q.Count) { $p = $q[0]; $q = $q[1..($q.Count)]; foreach ($c in ($all | Where-Object ParentProcessId -eq $p)) { $out += $c.ProcessId; $q += $c.ProcessId } }; "
              "$out | ConvertTo-Json -Compress")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True).stdout.strip()
    value = json.loads(out) if out else []
    return value if isinstance(value, list) else [value]


def alive(pid):
    return str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout


@unittest.skipUnless(os.environ.get("RESPECTED_LIVE_CHAT") == "1", "live free-model session: set RESPECTED_LIVE_CHAT=1 and RESPECTED_TEST_SANDBOX=real")
class LiveFreeSessionTests(unittest.TestCase):
    """Real opencode, free model only (opencode/*-free, cost field must be 0). Five small calls in total."""

    def test_real_start_then_follow_up_turn_through_the_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = SessionController(unsandboxed=True)
            view = ctl.start(Origin.HUMAN, PID, "opencode", MODEL, tmp, "Remember the word PINEAPPLE. Reply OK. No tools.", wait=False)
            sid = view["id"]
            self.assertEqual(view["state"], "running")
            self.assertTrue(wait_for(lambda: ctl.events(Origin.HUMAN, sid, PID)["result"] is not None), "first turn never finished")
            first = ctl.events(Origin.HUMAN, sid, PID)["result"]
            self.assertTrue(first["complete"], first["state"])
            costs = [e["cost"] for e in first["events"] if e["kind"] == "usage"]
            self.assertTrue(costs and all(c == 0 for c in costs), costs)
            self.assertEqual(ctl._sessions[sid]["cli_id"], first["session_id"])  # learned from the stream, not invented
            ctl.send(Origin.HUMAN, sid, PID, "Which word did I ask you to remember? One word. No tools.", wait=False)
            self.assertTrue(wait_for(lambda: ctl.events(Origin.HUMAN, sid, PID)["result"] is not None), "second turn never finished")
            second = ctl.events(Origin.HUMAN, sid, PID)["result"]
            self.assertTrue(second["complete"], second["state"])
            self.assertTrue(all(e["cost"] == 0 for e in second["events"] if e["kind"] == "usage"))
            self.assertIn("PINEAPPLE", " ".join(e["text"] for e in second["events"] if e["kind"] == "message").upper())
            print("LIVE-START:", [e["text"] for e in second["events"] if e["kind"] == "message"], [e for e in second["events"] if e["kind"] == "usage"])

    def test_real_interrupt_leaves_no_process_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = SessionController(unsandboxed=True)
            view = ctl.start(Origin.HUMAN, PID, "opencode", MODEL, tmp, "Write a 1500 word essay about rivers. No tools.", wait=False)
            sid = view["id"]
            self.assertTrue(wait_for(lambda: ctl._sessions[sid]["handle"] is not None, 30), "the CLI never started")
            time.sleep(4)  # let the launcher spawn the real process
            root = ctl._sessions[sid]["handle"].pid
            tree = [root] + descendants(root)
            print("LIVE-INTERRUPT: process tree before interrupt:", len(tree), "processes")
            started = time.monotonic()
            ctl.interrupt(Origin.HUMAN, sid, PID)
            self.assertLess(time.monotonic() - started, 15)
            self.assertTrue(wait_for(lambda: not any(alive(p) for p in tree), 20), [p for p in tree if alive(p)])
            self.assertEqual(ctl._sessions[sid]["state"], "failed")
            self.assertEqual(ctl._sessions[sid]["last_state"], "interrupted")
            self.assertEqual(ctl.view(Origin.HUMAN, PID)[0]["commands"]["retry"]["enabled"], True)

    def test_denied_tools_block_a_shell_request_and_the_control_shows_it_would_have_run(self):
        prompt = "Use your shell tool to run exactly: echo hi > MARKER.txt . If that is not allowed, try the write tool to create MARKER.txt containing hi. Do nothing else."
        ran = {}
        for denied in (True, False):
            with tempfile.TemporaryDirectory() as tmp:
                env = chat_session.turn_environment(tmp)
                if not denied:
                    env.pop("OPENCODE_CONFIG_CONTENT")  # the control: identical turn without the deny list
                argv = chat_session.command("opencode", model=MODEL, prompt=prompt, binary=chat_session.native_binary("opencode"))
                done = subprocess.run(argv, cwd=tmp, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=150, stdin=subprocess.DEVNULL)
                result = chat_session.parse_stream(done.stdout.splitlines())
                self.assertTrue(all(e["cost"] == 0 for e in result["events"] if e["kind"] == "usage"))
                ran[denied] = (Path(tmp) / "MARKER.txt").exists(), [e["tool"] for e in result["events"] if e["kind"] == "tool_call"]
        print("LIVE-DENY:", ran)
        if not ran[False][0]:
            self.skipTest("the control did not trigger the shell tool, so the denied run proves nothing this time")
        self.assertFalse(ran[True][0], "a denied tool still ran")


if __name__ == "__main__":
    unittest.main()
