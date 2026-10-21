import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest import mock

from respected_orchestrator.interfaces import integrations as sil, rpp
from respected_orchestrator.context import EngineContext

LAUNCH = {"command": "cmd", "args": ["/c", "C:/x/launch.cmd"]}
CLAUDE = {"numStartups": 7, "projects": {"C:/p": {"allowedTools": []}}, "mcpServers": {"other": {"command": "x", "args": ["1"]}}}
CODEX = '# my config\nmodel = "gpt"\n\n[mcp_servers.other]\ncommand = "y"\n\n[profiles.fast]\nmodel = "m"\n'


class IntegrationsTest(unittest.TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp())
        self.home = root / "home"
        (self.home / ".codex").mkdir(parents=True)
        self.claude, self.codex = self.home / ".claude.json", self.home / ".codex/config.toml"
        self.claude.write_text(json.dumps(CLAUDE, indent=2), encoding="utf-8")
        self.codex.write_text(CODEX, encoding="utf-8")
        patch = mock.patch.dict(os.environ, {"USERPROFILE": str(self.home), "HOME": str(self.home), "APPDATA": str(self.home / "AppData")})
        patch.start()
        self.addCleanup(patch.stop)
        self.ctx = EngineContext(root / "data")
        self.n = 0

    def go(self, desired, op=None):
        planned = sil.plan(self.ctx, {"desired": desired, "launcher": LAUNCH})
        self.n += 1
        return sil.apply(self.ctx, op or f"op-test-{self.n:04d}", {"desired": desired, "launcher": LAUNCH, "plan_digest": planned["plan_digest"]})

    def test_enable_preserves_foreign_content_and_disable_restores_it(self):
        self.go({"claude-code": True, "codex": True})
        servers = json.loads(self.claude.read_text("utf-8"))
        self.assertEqual(servers["mcpServers"]["respected-orchestrator"]["args"], LAUNCH["args"])
        self.assertEqual({k: v for k, v in servers.items() if k != "mcpServers"}, {k: v for k, v in CLAUDE.items() if k != "mcpServers"})
        self.assertEqual(servers["mcpServers"]["other"], CLAUDE["mcpServers"]["other"])
        parsed = tomllib.loads(self.codex.read_text("utf-8"))
        self.assertEqual(parsed["mcp_servers"]["respected-orchestrator"]["args"], LAUNCH["args"])
        self.assertEqual(parsed["mcp_servers"]["other"], {"command": "y"})
        self.assertIn("# my config", self.codex.read_text("utf-8"))
        self.go({"claude-code": False, "codex": False})
        self.assertEqual(json.loads(self.claude.read_text("utf-8")), CLAUDE)
        self.assertEqual(self.codex.read_text("utf-8").strip(), CODEX.strip())

    def test_an_unreadable_config_of_an_untouched_client_does_not_block_the_others(self):
        (self.home / ".gemini").mkdir()
        (self.home / ".gemini/settings.json").write_text('{ // comments are fine for gemini\n}', encoding="utf-8")
        self.go({"claude-code": True})
        self.assertIn("respected-orchestrator", self.claude.read_text("utf-8"))
        rows = {r["client"]: r for r in sil.plan(self.ctx, {"desired": {}, "launcher": LAUNCH})["clients"]}
        self.assertEqual(rows["gemini"]["state"], "unreadable")
        with self.assertRaises(sil.LifecycleError):
            sil.plan(self.ctx, {"desired": {"gemini": True}, "launcher": LAUNCH})

    def test_apply_is_idempotent_and_needs_the_approved_digest(self):
        first = self.go({"codex": True}, "op-test-idem1")
        self.assertEqual(self.go({"codex": True}, "op-test-idem1"), first)
        with self.assertRaises(sil.LifecycleError) as caught:
            sil.apply(self.ctx, "op-test-stale", {"desired": {"claude-code": True}, "launcher": LAUNCH, "plan_digest": "0" * 64})
        self.assertEqual(caught.exception.code, "PLAN_CHANGED")
        self.assertNotIn("respected-orchestrator", self.claude.read_text("utf-8"))

    def test_foreign_or_edited_entries_are_refused_and_nothing_is_written(self):
        doc = dict(CLAUDE, mcpServers={"respected-orchestrator": {"command": "mine"}})
        self.claude.write_text(json.dumps(doc), encoding="utf-8")
        before = self.codex.read_bytes()
        with self.assertRaises(sil.LifecycleError) as caught:
            self.go({"claude-code": True, "codex": True})
        self.assertEqual(caught.exception.code, "LIFECYCLE_CONFLICT")
        self.assertEqual(self.codex.read_bytes(), before)  # all-or-nothing
        self.claude.write_text(json.dumps(CLAUDE), encoding="utf-8")
        self.go({"claude-code": True})
        edited = json.loads(self.claude.read_text("utf-8"))
        edited["mcpServers"]["respected-orchestrator"]["command"] = "user-edit"
        self.claude.write_text(json.dumps(edited), encoding="utf-8")
        with self.assertRaises(sil.LifecycleError):
            self.go({"claude-code": False})
        self.assertEqual(json.loads(self.claude.read_text("utf-8"))["mcpServers"]["respected-orchestrator"]["command"], "user-edit")

    def test_invalid_config_is_never_touched_and_missing_client_is_refused(self):
        self.claude.write_text("{not json", encoding="utf-8")
        with self.assertRaises(sil.LifecycleError):
            sil.plan(self.ctx, {"desired": {"claude-code": True}, "launcher": LAUNCH})
        self.claude.write_text("{}", encoding="utf-8")
        rows = {r["client"]: r for r in sil.plan(self.ctx, {"desired": {"cursor": True}, "launcher": LAUNCH})["clients"]}
        self.assertEqual(rows["cursor"]["action"], "refuse")
        self.assertFalse(rows["cursor"]["detected"])

    def test_rollback_reverts_only_our_entry_and_refuses_after_user_edits(self):
        self.go({"claude-code": True, "codex": True}, "op-test-roll1")
        sil.rollback(self.ctx, "op-test-roll1")
        self.assertEqual(json.loads(self.claude.read_text("utf-8")), CLAUDE)
        self.assertEqual(self.codex.read_text("utf-8").strip(), CODEX.strip())
        self.go({"codex": True}, "op-test-roll2")
        self.codex.write_text(self.codex.read_text("utf-8").replace("launch.cmd", "other.cmd"), encoding="utf-8")
        with self.assertRaises(sil.LifecycleError):
            sil.rollback(self.ctx, "op-test-roll2")

    def test_rpp_ops_are_v11_only_and_listed(self):
        reply = rpp.handle_request({"rpp": "1.0", "op": "integrations.plan", "payload": {}}, self.ctx)
        self.assertEqual(reply["error"]["code"], "UNSUPPORTED_OP")
        reply = rpp.handle_request({"rpp": "1.1", "op": "integrations.plan", "payload": {"desired": {}}}, self.ctx)
        self.assertTrue(reply["ok"], reply)


if __name__ == "__main__":
    unittest.main()
