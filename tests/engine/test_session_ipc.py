"""The chat commands the desktop relies on, over the real IPC dispatcher: defaults, model checks, conversations, transcript, forget, continue."""
import json
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import local_api
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.session_control import SessionController
from respected_orchestrator.engine.session_store import SessionStore
from tests.engine.test_session_control import MODEL, PID, FakeRunner, wait_for

OTHER = "opencode/big-pickle"
LISTED = f"{MODEL}\n{OTHER}\n"


class SessionIpcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.store = SessionStore(self.tmp / "sessions.json")
        self.n = 0

    def api(self, origin=Origin.RENDERER, store=None):
        api = local_api.LocalApi(EngineContext(self.tmp / "data"), "t" * 32, origin=origin)
        api.sessions = SessionController(binary="oc", runner=FakeRunner(models=LISTED), store=store or self.store)
        return api

    def call(self, api, cmd, payload=None):
        self.n += 1
        return api.handle({"ipc": "1", "id": f"ipc-s-{self.n:04d}", "session": "t" * 32, "cmd": cmd, "payload": {"project_id": PID, **(payload or {})}})

    def started(self, api, **extra):
        r = self.call(api, "session.start", {"project_root": str(self.tmp), "text": "Merhaba dünya. Devam", **extra})
        self.assertTrue(r["ok"], r)
        sid = r["result"]["id"]
        self.assertTrue(wait_for(lambda: self.call(api, "session.events", {"session_id": sid})["result"]["state"] == "idle"))
        return sid

    def test_defaults_come_from_the_engine_and_a_choice_is_checked_then_kept(self):
        api = self.api()
        got = self.call(api, "session.defaults")["result"]
        self.assertEqual((got["agents"], got["agent"], got["model"]), (["opencode"], "opencode", MODEL))
        bad = self.call(api, "session.defaults.set", {"model": "x/not-listed"})
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["error"]["reason"], "MODEL_INVALID")
        self.assertEqual(self.call(api, "session.defaults")["result"]["model"], MODEL)  # a refused choice changes nothing
        self.assertTrue(self.call(api, "session.defaults.set", {"model": OTHER})["ok"])
        self.assertEqual(self.call(self.api(store=SessionStore(self.tmp / "sessions.json")), "session.defaults")["result"]["model"], OTHER)
        self.assertEqual(self.call(api, "session.models", {})["result"]["default"], OTHER)

    def test_changing_the_default_is_a_settings_action_an_mcp_caller_does_not_have(self):
        r = self.call(self.api(origin=Origin.MCP), "session.defaults.set", {"model": OTHER})
        self.assertEqual((r["ok"], r["error"]["code"]), (False, "FORBIDDEN"))
        self.assertTrue(self.call(self.api(origin=Origin.MCP), "session.defaults")["ok"])  # reading is allowed

    def test_start_uses_the_saved_default_and_refuses_unlisted_models_and_bad_folders(self):
        api = self.api()
        self.call(api, "session.defaults.set", {"model": OTHER})
        sid = self.started(api)  # no agent, no model: the engine's default
        self.assertEqual(self.call(api, "sessions.list")["result"]["sessions"][0]["model"], OTHER)
        r = self.call(api, "session.start", {"project_root": str(self.tmp), "model": "a/not-listed", "text": "x"})
        self.assertEqual((r["ok"], r["error"]["reason"]), (False, "MODEL_INVALID"))
        r = self.call(api, "session.start", {"project_root": "relative", "text": "x"})
        self.assertEqual((r["error"]["code"], r["error"]["reason"]), ("BAD_REQUEST", "ROOT_INVALID"))
        r = self.call(api, "session.start", {"project_root": str(self.tmp), "text": "   "})
        self.assertEqual(r["error"]["reason"], "TEXT_EMPTY")
        self.assertTrue(sid)

    def test_the_permission_mode_is_the_persons_choice_and_reaches_the_agent_from_the_next_turn(self):
        api = self.api()
        self.assertEqual(self.call(api, "session.defaults")["result"]["modes"], ["default", "accept-edits", "bypass-permissions"])
        sid = self.started(api)
        runner = api.sessions._runner
        def effect(n, action):
            rules = json.loads(runner.kwargs[n]["env"]["OPENCODE_CONFIG_CONTENT"])["permissions"]
            return next(r["effect"] for r in reversed(rules) if r["action"] in (action, "*"))
        self.assertEqual((self.call(api, "sessions.list")["result"]["sessions"][0]["mode"], effect(0, "edit")), ("default", "deny"))
        self.assertEqual(self.call(api, "session.mode.set", {"session_id": sid, "mode": "plan"})["error"]["reason"], "MODE_INVALID")
        self.assertEqual(self.call(api, "session.mode.set", {"session_id": sid, "mode": "accept-edits"})["result"]["mode"], "accept-edits")
        self.assertTrue(self.call(api, "session.send", {"session_id": sid, "text": "düzenle"})["ok"])
        self.assertTrue(wait_for(lambda: self.call(api, "session.events", {"session_id": sid})["result"]["state"] == "idle"))
        self.assertEqual((effect(1, "edit"), effect(1, "shell"), effect(1, "execute")), ("allow", "deny", "deny"))
        opened = self.started(api, mode="bypass-permissions")
        self.assertEqual((effect(2, "shell"), effect(2, "execute")), ("allow", "deny"))
        self.assertEqual(self.call(api, "sessions.list")["result"]["sessions"][-1]["id"], opened)
        # an agent (MCP level) can neither start a session with an opening mode nor change one; a plain start still works for it
        other = self.api(origin=Origin.MCP)
        refused = self.call(other, "session.start", {"project_root": str(self.tmp), "text": "selam", "mode": "accept-edits"})
        self.assertEqual(refused["error"]["code"], "FORBIDDEN")
        self.assertEqual(self.call(other, "session.mode.set", {"session_id": sid, "mode": "default"})["error"]["code"], "FORBIDDEN")
        self.assertTrue(self.call(other, "session.start", {"project_root": str(self.tmp), "text": "selam"})["ok"])

    def test_list_transcript_and_totals_are_the_engines(self):
        api = self.api()
        sid = self.started(api)
        listed = self.call(api, "sessions.list")["result"]
        row = listed["conversations"][0]
        self.assertEqual((row["id"], row["title"], row["project_root"], row["saved"]), (sid, "Merhaba dünya", str(self.tmp), False))
        moved = self.call(api, "session.transcript", {"session_id": sid})["result"]
        self.assertEqual(moved["turns"][0]["user"], "Merhaba dünya. Devam")
        self.assertIsNotNone(moved["turns"][0]["result"])
        self.assertTrue(moved["resumable"])
        self.assertEqual(self.call(api, "session.transcript", {"session_id": "loc_unknownunknown"})["error"]["reason"], "SESSION_UNKNOWN")

    def test_a_saved_conversation_survives_a_restart_and_continues_by_id_alone(self):
        sid = self.started(self.api())
        fresh = self.api(store=SessionStore(self.tmp / "sessions.json"))  # engine restarted
        row = self.call(fresh, "sessions.list")["result"]["conversations"][0]
        self.assertEqual((row["id"], row["saved"], row["state"]), (sid, True, "ended"))
        r = self.call(fresh, "session.start", {"continue_conversation": sid, "text": "devam"})
        self.assertTrue(r["ok"], r)
        again = self.call(fresh, "sessions.list")["result"]["conversations"]
        self.assertEqual(len(again), 1)
        self.assertNotEqual(again[0]["id"], sid)
        missing = self.call(fresh, "session.start", {"continue_conversation": "loc_unknownunknown", "text": "x"})
        self.assertEqual(missing["error"]["reason"], "RESUME_INVALID")

    def test_forget_removes_a_record_but_not_a_live_session(self):
        api = self.api()
        sid = self.started(api)
        self.assertEqual(self.call(api, "session.forget", {"session_id": sid})["error"]["reason"], "SESSION_LIVE")
        self.assertTrue(self.call(api, "session.cancel", {"session_id": sid})["ok"])
        self.assertTrue(self.call(api, "session.forget", {"session_id": sid})["ok"])
        self.assertEqual(self.call(api, "sessions.list")["result"]["conversations"], [])


if __name__ == "__main__":
    unittest.main()
