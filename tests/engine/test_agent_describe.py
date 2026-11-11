import datetime as dt
import tempfile
import time
import unittest
from pathlib import Path

from respected_orchestrator.engine import agent_adapters, agent_describe as ad, chat_session
from tests.engine.test_agent_discovery import CODEX_OK, FakeProbe

NOW = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.timezone.utc)
CODEX = {**CODEX_OK, ("exec", "--help"): (0, "Usage: codex exec [--json] resume --model <M>\n"),
         ("--help",): (0, "  -a, --ask-for-approval <POLICY>\n      --dangerously-bypass-approvals-and-sandbox\n")}
OPENCODE = {("--version",): (0, "opencode v2.2.3\n"), ("run", "--help"): (0, "--format choice\n--session id\n--auto\n--model, -m string\n"),
            ("auth", "list"): (0, "1 stored credential\n")}
CLAUDE = {("--version",): (0, "2.1.319 (Claude Code)\n"), ("auth", "status"): (0, '{"loggedIn": false}'),
          ("--help",): (0, '--output-format stream-json --input-format --resume --permission-prompts --model <model>\n'
                           '--permission-mode <mode> (choices: "acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan")\n')}


class DescribeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def describe(self, agent, table, binary):
        path = self.dir / f"{binary}.exe"
        path.write_bytes(b"MZ")
        return ad.describe(agent, probe=FakeProbe(table), which=lambda b: str(path) if b == binary else None, now=NOW)

    def assert_contract(self, d):
        """The shape every adapter row must keep (the counterpart of a registry contract test)."""
        self.assertEqual(set(d), {"agent", "checked_at", "version", "readiness", "interfaces", "capabilities", "modes", "chat_modes", "chat_permissions", "models", "commands", "context", "extra"})
        self.assertEqual(set(d["interfaces"]), set(ad.INTERFACES))
        self.assertLessEqual(set(d["capabilities"]), set(ad.FLAGS.values()))
        fields = [*d["interfaces"].values(), *d["capabilities"].values(), d["modes"], d["models"], d["commands"], d["context"]]
        for field in fields:
            self.assertIn(field["status"], ad.STATUSES, d["agent"])
            self.assertIn(field["source"], ad.SOURCES, d["agent"])
            self.assertEqual(field["status"] == "native", field["source"] == "probe", (d["agent"], field))  # native only when seen on this machine
            self.assertTrue(field["note"], (d["agent"], field))
        self.assertIn(d["readiness"]["effective"], ("ready", "not_ready", "unknown"))
        self.assertIn(d["readiness"]["installation"]["state"], ("installed", "not_installed", "unknown"))
        self.assertIn(d["readiness"]["authentication"]["state"], ("authorized", "unauthorized", "unknown", "not_applicable", "configured"))
        self.assertEqual(d["interfaces"]["terminal"]["status"] == "native", d["readiness"]["installation"]["state"] == "installed")  # ADR-035: an installed program runs in a terminal host
        if d["interfaces"]["handoff"]["status"] == "native":
            self.assertEqual((d["agent"], d["interfaces"]["chat"]["status"]), ("opencode", "native"))  # the one CLI with a verified chat and a documented way to continue a session
        self.assertEqual(d["commands"]["items"], [])  # only a live session can list them
        if d["modes"]["status"] != "native":
            self.assertEqual(d["modes"]["items"], [])

    def test_every_adapter_keeps_the_contract_with_nothing_installed_and_claims_nothing(self):
        for d in ad.describe_all(probe=FakeProbe({}), which=lambda b: None, now=NOW):
            self.assert_contract(d)
            self.assertNotEqual(d["readiness"]["effective"], "ready")
            self.assertEqual(d["capabilities"], {})
            self.assertNotIn("native", [f["status"] for f in (*d["interfaces"].values(), d["modes"], d["models"])])
        self.assertEqual([d["agent"] for d in ad.describe_all(probe=FakeProbe({}), which=lambda b: None, now=NOW)], list(agent_adapters.ADAPTERS))

    def test_the_agent_with_a_verified_chat_stream_is_ready_and_native(self):
        d = self.describe("opencode", OPENCODE, "opencode")
        self.assert_contract(d)
        self.assertEqual((d["readiness"]["effective"], d["readiness"]["authentication"]["state"]), ("ready", "configured"))
        self.assertEqual(d["interfaces"]["chat"]["status"], "native")
        self.assertEqual(d["modes"]["items"], [{"id": "default", "native": ""}, {"id": "auto", "native": "--auto"}])  # the bypass flag is not in this help
        self.assertEqual(d["chat_modes"], ["default", "accept-edits", "bypass-permissions"])
        self.assertEqual(d["chat_permissions"]["modes"], {mode: list(actions) for mode, actions in chat_session.MODES.items()})
        self.assertEqual(d["chat_permissions"]["always_denied"], list(chat_session.ALWAYS_DENIED))
        self.assertEqual((d["chat_permissions"]["project_config"], d["chat_permissions"]["source"]), ("disabled", "engine policy"))
        self.assertEqual((d["models"]["status"], d["models"]["selection"]), ("native", "catalog"))
        self.assertEqual((d["version"], d["checked_at"]), ("opencode v2.2.3", NOW.isoformat()))

    def test_a_chat_flag_alone_is_not_a_verified_chat_and_help_proves_only_what_it_shows(self):
        d = self.describe("codex", CODEX, "codex")
        self.assert_contract(d)
        self.assertEqual(d["readiness"]["effective"], "ready")
        self.assertEqual(d["interfaces"]["chat"]["status"], "unverified")
        self.assertIn("never verified", d["interfaces"]["chat"]["note"])
        self.assertEqual({k: v["status"] for k, v in d["capabilities"].items()},
                         {"steer": "unverified", "interrupt": "unverified", "resume": "native", "usage": "unverified", "approvals": "native"})
        self.assertEqual([m["id"] for m in d["modes"]["items"]], ["default", "bypass-permissions"])
        self.assertEqual(d["chat_modes"], [])  # codex has no chat adapter here
        self.assertEqual(d["chat_permissions"], {})
        self.assertEqual(d["models"]["selection"], "text")

    def test_common_mode_ids_keep_the_agents_own_names_and_a_missing_login_is_not_ready(self):
        d = self.describe("claude", CLAUDE, "claude")
        self.assert_contract(d)
        self.assertEqual((d["readiness"]["effective"], d["readiness"]["authentication"]["state"]), ("not_ready", "unauthorized"))
        self.assertIn({"id": "accept-edits", "native": "acceptEdits"}, d["modes"]["items"])
        self.assertIn({"id": "plan", "native": "plan"}, d["modes"]["items"])  # the agent's own mode, outside the four common ids
        self.assertEqual((d["commands"]["status"], d["context"]["status"]), ("unverified", "unverified"))

    def test_an_old_version_or_a_vanished_flag_is_never_native(self):
        old = self.describe("codex", {**CODEX, ("--version",): (0, "codex-cli 0.1.0\n")}, "codex")
        self.assert_contract(old)
        self.assertNotIn("native", [f["status"] for f in (*old["capabilities"].values(), old["modes"], old["models"], old["interfaces"]["chat"])])
        gone = self.describe("codex", {**CODEX, ("exec", "--help"): (0, "Usage: codex exec\n"), ("--help",): (0, "nothing\n")}, "codex")
        self.assert_contract(gone)
        self.assertEqual((gone["capabilities"]["resume"]["status"], gone["modes"]["status"], gone["models"]["status"]), ("unverified",) * 3)

    def test_api_is_read_only_refuses_workers_and_unknown_agents_and_fakes_are_not_cached(self):
        from respected_orchestrator.context import EngineContext
        from respected_orchestrator.engine.authority import Origin
        from respected_orchestrator.engine.local_api import LocalApi
        ad._cache.clear()
        self.addCleanup(ad._cache.clear)
        cached = self.describe("codex", CODEX, "codex")
        self.assertEqual(ad._cache, {})
        for agent in agent_adapters.ADAPTERS:  # the real view is cached, so no process starts below
            ad._cache[agent] = (time.monotonic(), {**cached, "agent": agent})
        call = lambda api, payload: api.handle({"ipc": "1", "id": "agd-00001", "session": "t" * 32, "cmd": "agent.describe", "payload": payload})
        for origin, ok in ((Origin.RENDERER, True), (Origin.MCP, True), (Origin.WORKER, False)):
            self.assertEqual(call(LocalApi(EngineContext(self.dir / "d"), "t" * 32, origin=origin), {"agent": "codex"})["ok"], ok, origin)
        api = LocalApi(EngineContext(self.dir / "d"), "t" * 32, origin=Origin.RENDERER)
        self.assertEqual(call(api, {"agent": "codex"})["result"]["agent"], "codex")
        api = LocalApi(EngineContext(self.dir / "d"), "t" * 32, origin=Origin.RENDERER)
        self.assertEqual([d["agent"] for d in call(api, {})["result"]["agents"]], list(agent_adapters.ADAPTERS))
        for bad in ("nope", 7):
            api = LocalApi(EngineContext(self.dir / "d"), "t" * 32, origin=Origin.RENDERER)
            self.assertEqual(call(api, {"agent": bad})["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
