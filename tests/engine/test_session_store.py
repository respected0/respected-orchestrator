"""The engine keeps the chat defaults, the saved conversations, their titles and token totals (the desktop keeps none of it)."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.engine import chat_session
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.session_control import SessionController, SessionError
from respected_orchestrator.engine.session_store import DEFAULT_MODEL, SessionStore, title_of, usage_of

OK = ('{"type":"step_start","sessionID":"ses_aaaaaaaa1111"}\n'
      '{"type":"text","sessionID":"ses_aaaaaaaa1111","part":{"text":"merhaba"}}\n'
      '{"type":"step_finish","sessionID":"ses_aaaaaaaa1111","part":{"reason":"stop","tokens":{"input":100,"output":5},"cost":0.25}}\n')
OTHER = "opencode/big-pickle"


def runner(argv, **kw):
    if argv[1:2] == ["models"]:
        return subprocess.CompletedProcess(argv, 0, f"{DEFAULT_MODEL}\n{OTHER}\n", "")
    return subprocess.CompletedProcess(argv, 0, OK, "")


class StoreTests(unittest.TestCase):
    def test_title_follows_the_first_sentence_and_falls_back(self):
        self.assertEqual(title_of([{"user": "iyi bir plan yap. sonra uygula"}], "x"), "İyi bir plan yap")
        self.assertEqual(title_of([{"user": None}], "yedek"), "yedek")
        self.assertLessEqual(len(title_of([{"user": "kelime " * 30}], "x")), 52)

    def test_usage_adds_what_steps_reported(self):
        step = lambda **k: {"result": {"events": [{"kind": "usage", **k}]}}  # noqa: E731
        got = usage_of([step(input=1500, output=20, reasoning=5, cache_read=100, cost=0.25), step(input=1200, output=30, cost=0.25)])
        self.assertEqual((got["input"], got["output"], got["last_input"], got["cost"], got["steps"]), (2700, 50, 1200, 0.5, 2))
        self.assertIsNone(usage_of([step(input=None)]))
        self.assertIsNone(usage_of([{"result": None}]))

    def test_defaults_and_conversations_survive_a_restart_and_a_broken_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chat" / "sessions.json"
            store = SessionStore(path)
            self.assertEqual(store.defaults(), {"agent": "opencode", "model": DEFAULT_MODEL})
            store.set_defaults("opencode", OTHER)
            store.put({"id": "loc_1", "turns": [{"n": 1, "user": "a", "result": None}], "title": "A"})
            again = SessionStore(path)
            self.assertEqual(again.defaults()["model"], OTHER)
            self.assertEqual(again.get("loc_1")["title"], "A")
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(SessionStore(path).all(), [])


class ControllerTests(unittest.TestCase):
    def make(self, tmp):
        return SessionController(binary="oc", runner=runner, store=SessionStore(Path(tmp) / "s.json"))

    def test_a_model_off_the_agents_list_is_refused_even_when_well_formed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = self.make(tmp)
            with self.assertRaises(SessionError) as caught:
                ctl.start(Origin.HUMAN, "p", "opencode", "x/not-on-the-list", tmp, "hi")
            self.assertEqual(caught.exception.reason, "MODEL_INVALID")
            with self.assertRaises(SessionError):
                ctl.set_defaults(Origin.HUMAN, "opencode", "x/not-on-the-list")
            self.assertEqual(ctl.defaults(Origin.HUMAN)["model"], DEFAULT_MODEL)

    def test_the_chosen_default_is_remembered_and_listed_with_the_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = self.make(tmp)
            got = ctl.set_defaults(Origin.HUMAN, "opencode", OTHER)
            self.assertEqual((got["agents"], got["model"]), (list(chat_session.SUPPORTED), OTHER))
            self.assertEqual(ctl.models(Origin.HUMAN, "opencode")["default"], OTHER)
            self.assertEqual(self.make(tmp).defaults(Origin.HUMAN)["model"], OTHER)

    def test_a_conversation_is_saved_titled_totalled_and_continued_after_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = self.make(tmp)
            sid = ctl.start(Origin.HUMAN, "p", "opencode", DEFAULT_MODEL, tmp, "Dosyayı oku. Sonra özetle", wait=True)["state"] and next(iter(ctl._sessions))
            view = ctl.view(Origin.HUMAN, "p")[0]
            self.assertEqual((view["title"], view["project_root"]), ("Dosyayı oku", str(Path(tmp))))
            moved = ctl.transcript(Origin.HUMAN, sid)
            self.assertEqual((moved["turns"][0]["user"], moved["turns"][0]["n"], moved["usage"]["input"], moved["resumable"]), ("Dosyayı oku. Sonra özetle", 1, 100, True))
            fresh = self.make(tmp)  # the engine restarted: nothing live, everything still there
            self.assertEqual([c["id"] for c in fresh.conversations(Origin.HUMAN, "p")], [sid])
            self.assertTrue(fresh.conversations(Origin.HUMAN, "p")[0]["saved"])
            fresh.start(Origin.HUMAN, "p", "opencode", DEFAULT_MODEL, tmp, "devam", resume="ses_aaaaaaaa1111")
            rows = fresh.conversations(Origin.HUMAN, "p")
            self.assertEqual(len(rows), 1)  # the old record moved to the new session
            self.assertNotEqual(rows[0]["id"], sid)
            self.assertEqual(fresh.transcript(Origin.HUMAN, rows[0]["id"])["turns"][0]["user"], "Dosyayı oku. Sonra özetle")

    def test_forget_deletes_a_record_but_not_a_live_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = self.make(tmp)
            ctl.start(Origin.HUMAN, "p", "opencode", DEFAULT_MODEL, tmp, "hi")
            sid = next(iter(ctl._sessions))
            with self.assertRaises(SessionError) as caught:
                ctl.forget(Origin.HUMAN, sid)
            self.assertEqual(caught.exception.reason, "SESSION_LIVE")
            ctl.cancel(Origin.HUMAN, sid, "p")
            ctl.forget(Origin.HUMAN, sid)
            self.assertEqual(ctl.conversations(Origin.HUMAN, "p"), [])

    def test_refusals_carry_a_stable_reason_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctl = self.make(tmp)
            for text, reason in (("  ", "TEXT_EMPTY"), ("x" * 8001, "TEXT_TOO_LONG"), ("a\x1b[31m", "TEXT_UNSAFE")):
                with self.assertRaises(SessionError) as caught:
                    ctl.start(Origin.HUMAN, "p", "opencode", DEFAULT_MODEL, tmp, text)
                self.assertEqual(caught.exception.reason, reason)


if __name__ == "__main__":
    unittest.main()
