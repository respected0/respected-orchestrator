"""ADR-034: the live stream. A turn's events reach listeners while the turn still runs, a subscriber gets them over the engine's pipe,
and a conversation is read one page of turns at a time."""
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import chat_session, daemon, daemon_client, local_api
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.session_control import NOTIFICATIONS, SessionController, SessionError, run_killable

OK_STREAM = (Path(__file__).resolve().parents[1] / "fixtures" / "chat" / "opencode_ok_text.jsonl").read_text(encoding="utf-8")
EXPECTED = chat_session.parse_stream(OK_STREAM.splitlines())["events"]
MODEL = "opencode/deepseek-v4.1-flash-free"
PID = "proj-1"


class HeldRunner:
    """Feeds the stream line by line like the real runner, then keeps the turn open until `release` is set."""

    def __init__(self):
        self.fed, self.release = threading.Event(), threading.Event()

    def __call__(self, argv, **kw):
        if argv[1:2] == ["models"]:
            return subprocess.CompletedProcess(argv, 0, MODEL + "\n", "")
        for line in OK_STREAM.splitlines():
            kw["on_line"](line)
        self.fed.set()
        self.release.wait(20)
        return subprocess.CompletedProcess(argv, 0, OK_STREAM, "")


def wait_for(cond, seconds=10):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


class LiveTurnTests(unittest.TestCase):
    def test_events_are_told_while_the_turn_runs_and_the_state_change_closes_it(self):
        runner, notes = HeldRunner(), []
        ctl = SessionController(binary="oc", runner=runner)
        ctl.listen(lambda project, name, data: notes.append((project, name, data)))
        sid = ctl.start(Origin.RENDERER, PID, "opencode", MODEL, tempfile.gettempdir(), "merhaba", wait=False)["id"]
        self.assertTrue(runner.fed.wait(10))
        mid = ctl.events(Origin.RENDERER, sid, PID)
        self.assertEqual((mid["state"], mid["result"], mid["live"]), ("running", None, EXPECTED))  # readable before the turn has ended
        self.assertEqual(ctl.transcript(Origin.RENDERER, sid)["live"], {"turn": 1, "events": EXPECTED})
        self.assertEqual([n[1] for n in notes], ["session.state"] + ["session.event"] * len(EXPECTED))
        self.assertEqual(notes[0][2]["session"]["state"], "running")
        self.assertEqual([n[2]["event"]["seq"] for n in notes[1:]], list(range(len(EXPECTED))))
        self.assertTrue(all(n[0] == PID and n[2]["session_id"] == sid and n[2]["turn"] == 1 for n in notes[1:]))
        runner.release.set()
        self.assertTrue(wait_for(lambda: notes[-1][1] == "session.state" and notes[-1][2]["session"]["state"] == "idle"))
        done = ctl.events(Origin.RENDERER, sid, PID)
        self.assertEqual((done["live"], done["result"]["events"]), (None, EXPECTED))  # the finished turn is exactly what was streamed
        self.assertIsNone(ctl.transcript(Origin.RENDERER, sid)["live"])
        self.assertTrue(set(n[1] for n in notes) <= set(NOTIFICATIONS))

    def test_a_stopped_turn_tells_its_state_and_nothing_after(self):
        runner, notes = HeldRunner(), []
        ctl = SessionController(binary="oc", runner=runner)
        sid = ctl.start(Origin.RENDERER, PID, "opencode", MODEL, tempfile.gettempdir(), "merhaba", wait=False)["id"]
        self.assertTrue(runner.fed.wait(10))
        ctl.listen(lambda project, name, data: notes.append((name, data)))
        ctl.interrupt(Origin.RENDERER, sid, PID)
        runner.release.set()
        time.sleep(0.3)  # the abandoned turn's thread ends now; its result is dropped
        self.assertEqual([(name, data["session"]["state"]) for name, data in notes], [("session.state", "failed")])

    def test_the_real_runner_hands_over_each_line_when_it_is_printed(self):
        seen = []
        code = "import time; print('bir', flush=True); time.sleep(1.5); print('iki', flush=True)"
        done = run_killable([sys.executable, "-c", code], on_line=lambda line: seen.append((line, time.monotonic())), timeout=30)
        end = time.monotonic()
        self.assertEqual((done.returncode, done.stdout, [line for line, _ in seen]), (0, "bir\niki\n", ["bir\n", "iki\n"]))
        self.assertGreater(end - seen[0][1], 1.0)  # the first line arrived long before the process ended


class PagedTranscriptTests(unittest.TestCase):
    def test_a_conversation_is_read_newest_page_first_and_older_pages_by_cursor(self):
        ctl = SessionController(binary="oc", runner=HeldRunner())
        ctl._runner.release.set()
        ctl.start(Origin.HUMAN, PID, "opencode", MODEL, tempfile.gettempdir(), "tur 0")
        sid = next(iter(ctl._sessions))
        for n in range(1, 5):
            ctl.send(Origin.HUMAN, sid, PID, f"tur {n}")
        users = lambda page: [t["user"] for t in page["turns"]]
        newest = ctl.transcript(Origin.HUMAN, sid, limit=2)
        self.assertEqual((users(newest), newest["first"], newest["total"]), (["tur 3", "tur 4"], 3, 5))
        above = ctl.transcript(Origin.HUMAN, sid, before=newest["first"], limit=2)
        self.assertEqual((users(above), above["first"]), (["tur 1", "tur 2"], 1))
        top = ctl.transcript(Origin.HUMAN, sid, before=above["first"], limit=2)
        self.assertEqual((users(top), top["first"]), (["tur 0"], 0))
        self.assertEqual(len(ctl.transcript(Origin.HUMAN, sid)["turns"]), 5)  # the default page holds a short conversation whole
        self.assertIsNotNone(newest["usage"])  # totals are of the whole conversation, whatever the page
        for bad in ({"before": 6}, {"before": -1}, {"before": "2"}, {"limit": 0}, {"limit": 201}, {"limit": True}):
            with self.assertRaises(SessionError) as refused:
                ctl.transcript(Origin.HUMAN, sid, **bad)
            self.assertEqual(refused.exception.reason, "PAGE_INVALID")


class SubscriberTests(unittest.TestCase):
    def test_a_subscriber_hears_its_own_project_only_and_is_cut_off_when_it_falls_behind(self):
        mine = daemon.Subscriber("p1")
        mine("p2", "session.state", {})
        self.assertTrue(mine.pending.empty())
        for n in range(daemon.MAX_PENDING):
            mine("p1", "session.event", {"n": n})
        self.assertFalse(mine.lost.is_set())
        self.assertEqual(mine.pending.get_nowait(), {"ipc": "1", "event": "session.event", "data": {"n": 0}})
        mine("p1", "session.event", {})
        mine("p1", "session.event", {})
        self.assertTrue(mine.lost.is_set())

    def test_subscribing_needs_a_project_a_stream_capable_connection_and_rights(self):
        ctx = EngineContext(Path(tempfile.mkdtemp()))
        ask = lambda api, payload: api.handle({"ipc": "1", "id": "sub-00000001", "session": "t" * 32, "cmd": "events.subscribe", "payload": payload})
        asked = []
        self.assertEqual(ask(local_api.LocalApi(ctx, "t" * 32, origin=Origin.MCP), {"project_id": "p1"})["error"]["code"], "ENGINE_ERROR")
        self.assertEqual(ask(local_api.LocalApi(ctx, "t" * 32, origin=Origin.MCP, subscribe=asked.append), {})["error"]["code"], "BAD_REQUEST")
        self.assertEqual(ask(local_api.LocalApi(ctx, "t" * 32, origin=Origin.CHILD, subscribe=asked.append), {"project_id": "p1"})["error"]["code"], "FORBIDDEN")
        self.assertEqual(asked, [])
        ok = ask(local_api.LocalApi(ctx, "t" * 32, origin=Origin.MCP, subscribe=asked.append), {"project_id": "p1"})
        self.assertEqual((ok["result"], asked), ({"subscribed": True, "events": list(NOTIFICATIONS)}, ["p1"]))


@unittest.skipUnless(os.name == "nt", "named pipe transport is Windows-only for now")
class PipeStreamTests(unittest.TestCase):
    def test_a_subscriber_gets_the_turn_over_the_pipe_and_leaving_frees_the_connection(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        engine = daemon.Daemon(EngineContext(Path(temporary.name).resolve()))
        runner = HeldRunner()
        engine.sessions = SessionController(binary="oc", runner=runner)
        server = threading.Thread(target=engine._serve_pipe, daemon=True)
        server.start()
        self.addCleanup(lambda: (engine.stop(), server.join(10)))
        self.assertTrue(wait_for(lambda: daemon_client.status(engine.ctx) is not None))
        with self.assertRaises(daemon_client.DaemonUnavailable):
            daemon_client.subscribe(engine.ctx, "")
        stream, notes = daemon_client.subscribe(engine.ctx, PID), []

        def collect():
            for note in stream:
                notes.append(note)
                if note["event"] == "session.state" and note["data"]["session"]["state"] == "idle":
                    break
            stream.close()

        reader = threading.Thread(target=collect, daemon=True)
        reader.start()
        sid = engine.sessions.start(Origin.MCP, PID, "opencode", MODEL, temporary.name, "merhaba", wait=False)["id"]
        self.assertTrue(wait_for(lambda: len(notes) == 1 + len(EXPECTED)))  # all of it while the turn is still open
        self.assertEqual(engine.sessions.events(Origin.MCP, sid, PID)["state"], "running")
        self.assertEqual([n["data"]["event"] for n in notes[1:]], EXPECTED)
        self.assertTrue(all(n["ipc"] == "1" and "id" not in n for n in notes))
        runner.release.set()
        reader.join(10)
        self.assertFalse(reader.is_alive())
        self.assertEqual(notes[-1]["data"]["session"]["id"], sid)
        self.assertTrue(wait_for(lambda: engine._connections == 0 and not engine.sessions._listeners, 8))  # the closed stream is noticed without an event


if __name__ == "__main__":
    unittest.main()
