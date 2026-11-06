import sys
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.engine import agent_discovery as d

CODEX_OK = {
    ("--version",): (0, "codex-cli 0.160.1\n"),
    ("exec", "--help"): (0, "Usage: codex exec [--json] resume\n"),
    ("--help",): (0, "  -a, --ask-for-approval <POLICY>\n"),
    ("login", "status"): (0, "Logged in using ChatGPT\n"),
}


class FakeProbe(d.Probe):
    def __init__(self, table, timeout_on=None):
        super().__init__(environ={})
        self.table, self.timeout_on = table, timeout_on

    def __call__(self, argv, timeout=None):
        key = tuple(argv[1:])
        if key == self.timeout_on:
            self.timed_out = True
            return None, "timeout"
        rc, text = self.table.get(key, (1, "unknown command"))
        self.outputs.append(text)
        return rc, text


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def binary(self, name="codex.exe"):
        path = self.dir / name
        path.write_bytes(b"MZ")
        return str(path)

    def run_agent(self, agent="codex", table=None, name="codex.exe", **kw):
        path = self.binary(name) if name else None
        probe = FakeProbe(CODEX_OK if table is None else table, **kw)
        return d.discover(agent, probe=probe, which=lambda b: path)

    def test_verified_needs_login_flag_and_a_known_executable_and_says_it_is_not_a_model_session(self):
        r = self.run_agent()
        self.assertEqual((r["status"], r["chat"]), ("verified", "verified"))
        self.assertIn("no model session", r["proof"])
        self.assertEqual(r["version"], "codex-cli 0.160.1")

    def test_missing_binary_is_unavailable_with_the_names_searched(self):
        r = d.discover("codex", probe=FakeProbe({}), which=lambda b: None)
        self.assertEqual(r["status"], "unavailable")
        self.assertTrue(r["reason"].startswith("not_found") and "codex" in r["reason"])

    def test_binary_moved_after_path_was_resolved(self):
        r = d.discover("codex", probe=FakeProbe(CODEX_OK), which=lambda b: str(self.dir / "gone" / "codex.exe"))
        self.assertEqual(r["status"], "unavailable")
        self.assertTrue(r["reason"].startswith("binary_missing_on_disk"))

    def test_renamed_executable_is_not_trusted(self):
        r = self.run_agent(name="totally-different.exe")
        self.assertEqual((r["status"], r["reason"].split(":")[0]), ("unavailable", "renamed_executable"))

    def test_timeout_is_its_own_reason_and_never_a_pass(self):
        r = self.run_agent(table={}, timeout_on=("--version",))
        self.assertEqual((r["status"], r["reason"].split(":")[0]), ("unavailable", "timeout"))

    def test_unexpected_or_empty_version_output(self):
        r = self.run_agent(table={**CODEX_OK, ("--version",): (0, "hello world\n")})
        self.assertEqual((r["status"], r["reason"].split(":")[0]), ("unavailable", "unexpected_output"))
        r = self.run_agent(table={**CODEX_OK, ("--version",): (0, "")})
        self.assertEqual((r["status"], r["reason"].split(":")[0]), ("unavailable", "version_probe_failed"))
        r = self.run_agent(table={**CODEX_OK, ("--version",): (1, "boom")})
        self.assertEqual(r["status"], "unavailable")

    def test_not_logged_in_and_unreadable_login_are_installed_not_verified(self):
        r = self.run_agent(table={**CODEX_OK, ("login", "status"): (1, "Not logged in")})
        self.assertEqual((r["status"], r["reason"].split(":")[0]), ("installed", "auth_required"))
        r = self.run_agent(agent="antigravity", table={("--version",): (0, "agy 1.5.0\n")}, name="agy.exe")
        self.assertEqual((r["status"], r["reason"].split(":")[0]), ("installed", "auth_unknown"))

    def test_enterprise_policy_blocks_even_a_working_cli(self):
        r = self.run_agent(table={**CODEX_OK, ("login", "status"): (1, "This CLI is disabled by your organization policy")})
        self.assertEqual((r["status"], r["reason"].split(":")[0]), ("unavailable", "enterprise_policy"))

    def test_missing_chat_flag_or_old_version_caps_at_configured(self):
        r = self.run_agent(table={**CODEX_OK, ("exec", "--help"): (0, "Usage: codex exec\n")})
        self.assertEqual(r["status"], "configured")
        self.assertIn("chat mode is advertised_missing", r["reason"])
        r = self.run_agent(table={**CODEX_OK, ("--version",): (0, "codex-cli 0.1.0\n")})
        self.assertEqual(r["status"], "configured")
        self.assertIn("older", r["reason"])

    def test_stored_credentials_alone_never_reach_verified(self):
        table = {("--version",): (0, "opencode v2.2.3\n"), ("run", "--help"): (0, "--format --session --auto\n"),
                 ("auth", "list"): (0, "1 credentials stored\n")}
        r = self.run_agent(agent="opencode", table=table, name="opencode.exe")
        self.assertEqual(r["status"], "configured")
        self.assertIn("validity", r["reason"])

    def test_custom_is_configured_and_probes_nothing(self):
        probe = FakeProbe({})
        r = d.discover("custom", probe=probe, which=lambda b: None)
        self.assertEqual((r["status"], probe.outputs), ("configured", []))

    def test_antigravity_is_found_under_its_real_name_agy(self):
        r = self.run_agent(agent="antigravity", table={("--version",): (0, "1.5.0\n")}, name="agy.exe")
        self.assertNotEqual(r["status"], "unavailable")

    def test_every_result_has_a_status_from_the_closed_set_and_a_reason(self):
        for agent in d.agent_adapters.ADAPTERS:
            r = d.discover(agent, probe=FakeProbe({}), which=lambda b: None)
            self.assertIn(r["status"], d.STATUSES)
            self.assertTrue(r["reason"])

    def test_unknown_agent_is_an_error_and_fakes_are_never_cached(self):
        with self.assertRaises(ValueError):
            d.discover("nonexistent")
        d._cache.clear()
        self.run_agent()
        self.assertEqual(d._cache, {})

    def test_ledger_lists_every_agent_with_its_reason(self):
        text = d.ledger({"codex": self.run_agent()})
        self.assertIn("codex", text)
        self.assertIn("verified", text)


class DiscoveryIpcTests(unittest.TestCase):
    def call(self, origin, payload, n=1):
        from respected_orchestrator.context import EngineContext
        from respected_orchestrator.engine.local_api import LocalApi
        with tempfile.TemporaryDirectory() as tmp:
            api = LocalApi(EngineContext(Path(tmp) / "data"), "t" * 32, origin=origin)
            return api.handle({"ipc": "1", "id": f"agd-{n:05d}", "session": "t" * 32, "cmd": "agents.discover", "payload": payload})

    def test_read_only_for_every_origin_and_validates_the_agent(self):
        from respected_orchestrator.engine.authority import Origin
        for origin in (Origin.RENDERER, Origin.MCP):
            r = self.call(origin, {"agent": "custom"})
            self.assertTrue(r["ok"] and r["result"]["agents"]["custom"]["status"] == "configured", r)
        for bad in ({"agent": "nope"}, {"agent": 5}):
            self.assertEqual(self.call(Origin.RENDERER, bad)["error"]["code"], "BAD_REQUEST")
        for origin in (Origin.WORKER, Origin.CHILD):
            self.assertEqual(self.call(origin, {"agent": "custom"})["error"]["code"], "FORBIDDEN")


class RealProcessProbeTests(unittest.TestCase):
    def test_probe_environment_carries_no_secret_looking_variables(self):
        probe = d.Probe(environ={"OPENAI_API_KEY": "sk-should-never-be-seen", "MY_TOKEN": "t0k", "PATH": "x", "SystemRoot": "C:\\Windows"})
        code = "import os; print(sorted(k for k in os.environ if 'KEY' in k.upper() or 'TOKEN' in k.upper()))"
        rc, text = probe([sys.executable, "-c", code])
        self.assertEqual(rc, 0)
        self.assertEqual(text.strip(), "[]")
        self.assertNotIn("sk-should-never-be-seen", " ".join(probe.outputs))

    def test_a_hanging_cli_times_out_without_hanging_us(self):
        probe = d.Probe(environ={"SystemRoot": "C:\\Windows"}, timeout=1)
        rc, text = probe([sys.executable, "-c", "import time; time.sleep(30)"])
        self.assertEqual((rc, text, probe.timed_out), (None, "timeout", True))

    def test_missing_executable_is_an_error_value_not_an_exception(self):
        probe = d.Probe(environ={})
        rc, text = probe([str(Path(tempfile.gettempdir()) / "definitely-not-here.exe")])
        self.assertIsNone(rc)
        self.assertTrue(probe.failed)


if __name__ == "__main__":
    unittest.main()
