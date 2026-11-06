import datetime as dt
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.engine import capability_matrix as cm
from tests.engine.test_agent_discovery import CODEX_OK, FakeProbe

NOW = dt.datetime(2026, 11, 6, 12, 0, tzinfo=dt.timezone.utc)
CODEX_FULL = {**CODEX_OK, ("exec", "--help"): (0, "Usage: codex exec [--json] resume --model <M>\n")}


class MatrixTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def build(self, table, binary="codex.exe", only="codex"):
        path = self.dir / binary
        path.write_bytes(b"MZ")
        which = lambda b: str(path) if (binary and b in (binary.split(".")[0],)) else None
        m = cm.build(probe=FakeProbe(table), which=which, now=NOW)
        return m["agents"][only]

    def assert_invariants(self, matrix):
        for agent, row in matrix["agents"].items():
            self.assertEqual(set(row["modes"]), set(cm.MODES))
            for mode, cell in row["modes"].items():
                self.assertEqual(cell["enabled"], cell["status"] == "verified", (agent, mode))  # a button is live only when proven
                self.assertIn(cell["status"], ("verified", "unverified", "unsupported"))
                self.assertTrue(cell["reason"] and cell["checked_at"], (agent, mode))
            self.assertFalse(row["modes"]["terminal"]["enabled"], agent)  # no PTY until a production broker exists

    def test_verified_tool_enables_only_what_its_own_help_proves(self):
        row = self.build(CODEX_FULL)
        modes = row["modes"]
        self.assertTrue(modes["chat"]["enabled"] and modes["resume"]["enabled"] and modes["model_switch"]["enabled"])
        self.assertEqual(modes["interactive_input"]["status"], "unverified")  # documented, never probed
        self.assertEqual(modes["usage"]["status"], "unverified")
        self.assertEqual(modes["terminal"]["status"], "unsupported")
        self.assertEqual(modes["chat"]["version"], "codex-cli 0.160.1")
        self.assertEqual(modes["chat"]["checked_at"], NOW.isoformat())

    def test_false_capability_claim_is_unverified_with_the_reason(self):
        row = self.build({**CODEX_FULL, ("exec", "--help"): (0, "Usage: codex exec\n")})
        self.assertEqual(row["modes"]["chat"]["status"], "unverified")
        self.assertIn("not found in the CLI", row["modes"]["chat"]["reason"])
        self.assertEqual(row["modes"]["model_switch"]["status"], "unverified")
        self.assertIn("absent from", row["modes"]["model_switch"]["reason"])

    def test_out_of_date_tool_does_not_enable_anything(self):
        row = self.build({**CODEX_FULL, ("--version",): (0, "codex-cli 0.1.0\n")})
        self.assertEqual(row["version_state"], "older_than_verified")
        self.assertFalse(any(c["enabled"] for c in row["modes"].values()))

    def test_unavailable_login_keeps_every_mode_closed(self):
        row = self.build({**CODEX_FULL, ("login", "status"): (1, "Not logged in")})
        self.assertEqual(row["tool_status"], "installed")
        self.assertFalse(any(c["enabled"] for c in row["modes"].values()))
        self.assertIn("flag present, but the tool is installed", row["modes"]["chat"]["reason"])

    def test_offline_matrix_with_nothing_installed_is_all_closed_and_still_complete(self):
        m = cm.build(probe=FakeProbe({}), which=lambda b: None, now=NOW)
        self.assert_invariants(m)
        self.assertFalse(any(c["enabled"] for a in m["agents"].values() for c in a["modes"].values()))

    def test_found_tool_without_contract_does_not_claim_binary_not_found(self):
        row = self.build({("--version",): (0, "agy 1.5.0\n")}, binary="agy.exe", only="antigravity")
        self.assertNotIn("binary not found", row["modes"]["chat"]["reason"])
        self.assertEqual(row["modes"]["chat"]["status"], "unsupported")

    def test_invariants_hold_for_every_scenario(self):
        for table in (CODEX_FULL, {}, {**CODEX_FULL, ("login", "status"): (1, "no")}, {**CODEX_FULL, ("--version",): (0, "garbage")}):
            path = self.dir / "codex.exe"
            path.write_bytes(b"MZ")
            self.assert_invariants(cm.build(probe=FakeProbe(table), which=lambda b, p=str(path): p if b == "codex" else None, now=NOW))

    def test_markdown_artifact_lists_reasons_for_everything_not_verified(self):
        path = self.dir / "codex.exe"
        path.write_bytes(b"MZ")
        m = cm.build(probe=FakeProbe(CODEX_FULL), which=lambda b: str(path) if b == "codex" else None, now=NOW)
        md = cm.to_markdown(m)
        self.assertIn("| codex | verified codex-cli 0.160.1 | - | V | ? | ? | V | V |", md)
        self.assertIn("- codex/terminal: unsupported", md)
        self.assertNotIn("codex/chat:", md)  # verified cells need no excuse
        self.assertIn("Only `V` enables a button", md)

    def test_fake_matrices_are_not_cached_and_ipc_is_read_only(self):
        from respected_orchestrator.context import EngineContext
        from respected_orchestrator.engine.authority import Origin
        from respected_orchestrator.engine.local_api import LocalApi
        cm._cache.clear()
        cm.build(probe=FakeProbe({}), which=lambda b: None, now=NOW)
        self.assertEqual(cm._cache, [])
        cm._cache[:] = [(__import__("time").monotonic(), {"checked_at": "x", "agents": {}, "modes": []})]  # the real view is cached; no processes start
        for origin, ok in ((Origin.RENDERER, True), (Origin.MCP, True), (Origin.WORKER, False)):
            api = LocalApi(EngineContext(self.dir / "d"), "t" * 32, origin=origin)
            r = api.handle({"ipc": "1", "id": "cap-00001", "session": "t" * 32, "cmd": "capabilities.matrix", "payload": {}})
            self.assertEqual(r["ok"], ok, origin)
        cm._cache.clear()


if __name__ == "__main__":
    unittest.main()
