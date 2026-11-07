"""Opt-in live session against a real FREE model (kept apart from the P0 gate groups so its skip is not a gate skip).

    RESPECTED_TEST_SANDBOX=real RESPECTED_LIVE_CHAT=1 python -m unittest tests.engine.test_session_live
"""
import os
import tempfile
import unittest

from respected_orchestrator.engine import chat_session
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.session_control import SessionController

PID = "proj-1"
MODEL = "opencode/deepseek-v4.1-flash-free"


@unittest.skipUnless(os.environ.get("RESPECTED_LIVE_CHAT") == "1", "live free-model session: set RESPECTED_LIVE_CHAT=1 and RESPECTED_TEST_SANDBOX=real")
class LiveFreeSessionTests(unittest.TestCase):
    """Real opencode, free model only (opencode/*-free, cost field must be 0). Two small calls."""

    def test_real_follow_up_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = chat_session.run_turn("opencode", model=MODEL, prompt="Remember the word PINEAPPLE. Reply OK. No tools.", cwd=tmp)
            self.assertTrue(first["complete"], first["state"])
            costs = [e["cost"] for e in first["events"] if e["kind"] == "usage"]
            self.assertTrue(costs and all(c == 0 for c in costs), costs)
            ctl = SessionController()
            ctl.register(Origin.HUMAN, first["session_id"], PID, "opencode", MODEL, tmp)
            second = ctl.send(Origin.HUMAN, first["session_id"], PID, "Which word did I ask you to remember? One word. No tools.")
            self.assertTrue(second["complete"], second["state"])
            self.assertTrue(all(e["cost"] == 0 for e in second["events"] if e["kind"] == "usage"))
            self.assertIn("PINEAPPLE", " ".join(e["text"] for e in second["events"] if e["kind"] == "message").upper())
            print("LIVE:", [e["text"] for e in second["events"] if e["kind"] == "message"], [e for e in second["events"] if e["kind"] == "usage"])


if __name__ == "__main__":
    unittest.main()
