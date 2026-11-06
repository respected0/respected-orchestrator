import shutil
import unittest

from respected_orchestrator.engine import agent_adapters as aa


def fake(helps, version="codex-cli 0.160.1", auth=(0, "Logged in using ChatGPT")):
    def run(argv):
        tail = argv[1:]
        if tail == ["--version"]:
            return 0, version
        if tail in (["login", "status"], ["auth", "status"], ["status"], ["auth", "list"]):
            return auth
        return 0, helps.get(tuple(tail), "")
    return run


FULL = {("exec", "--help"): "--json resume", ("--help",): "--ask-for-approval"}
where = lambda name: "C:/bin/" + name


class MatrixTests(unittest.TestCase):
    def test_every_agent_gets_every_capability_with_an_explicit_state(self):
        rows = aa.matrix(fake({}), lambda n: None)
        self.assertEqual(set(rows), {"codex", "claude", "cursor", "opencode", "antigravity", "custom"})
        for row in rows.values():
            self.assertEqual(set(row["caps"]), set(aa.CAPABILITIES))
            for cap in row["caps"].values():
                self.assertIn(cap["status"], {"verified", "source", "advertised_missing", "unsupported"})

    def test_binary_missing_is_unsupported_everywhere_and_never_usable(self):
        row = aa.verify("codex", fake(FULL), lambda n: None)
        self.assertFalse(row["found"])
        self.assertTrue(all(c["status"] == "unsupported" for c in row["caps"].values()))
        self.assertFalse(aa.usable(row, "chat"))

    def test_advertised_mode_whose_flag_is_gone_is_not_verified(self):
        row = aa.verify("codex", fake({("exec", "--help"): "resume only", ("--help",): "--ask-for-approval"}), where)
        self.assertEqual(row["caps"]["chat"]["status"], "advertised_missing")
        self.assertEqual(row["caps"]["resume"]["status"], "verified")
        self.assertFalse(aa.usable(row, "chat"))

    def test_older_version_downgrades_verified_to_source(self):
        row = aa.verify("codex", fake(FULL, version="codex-cli 0.100.0"), where)
        self.assertEqual(row["version_state"], "older_than_verified")
        self.assertEqual(row["caps"]["chat"]["status"], "source")
        self.assertFalse(aa.usable(row, "chat"))

    def test_login_required_closes_the_mode(self):
        row = aa.verify("codex", fake(FULL, auth=(1, "Not logged in")), where)
        self.assertEqual(row["auth"], "needs_login")
        self.assertEqual(row["caps"]["chat"]["status"], "verified")
        self.assertFalse(aa.usable(row, "chat"))

    def test_verified_present_logged_in_is_usable_and_pty_never_is(self):
        row = aa.verify("codex", fake(FULL), where)
        self.assertTrue(aa.usable(row, "chat"))
        self.assertEqual(row["caps"]["pty"]["status"], "unsupported")
        self.assertFalse(aa.usable(row, "pty"))
        self.assertEqual(row["caps"]["send_input"]["status"], "source")  # documented, not proven: never counted as usable

    def test_timeout_or_crash_of_a_probe_is_reported_not_raised(self):
        row = aa.verify("codex", lambda argv: (None, "timeout"), where)
        self.assertEqual(row["caps"]["chat"]["status"], "advertised_missing")
        self.assertEqual(row["auth"], "unknown")

    def test_custom_and_antigravity_make_no_claims(self):
        for name in ("custom", "antigravity"):
            row = aa.verify(name, fake(FULL), where)
            self.assertTrue(all(c["status"] == "unsupported" for c in row["caps"].values()))


@unittest.skipUnless(shutil.which("codex") or shutil.which("claude") or shutil.which("opencode") or shutil.which("cursor-agent"),
                     "no agent CLI installed here")
class LiveMatrixTests(unittest.TestCase):
    def test_installed_clis_match_the_declared_matrix(self):
        rows = aa.matrix()
        present = [r for r in rows.values() if r["found"]]
        self.assertTrue(present)
        for row in present:
            self.assertIsNotNone(row["version"], row["agent"])
            self.assertNotEqual(row["caps"]["chat"]["status"], "advertised_missing", f"{row['agent']}: {row['caps']['chat']}")
        for name in ("antigravity", "custom"):
            self.assertTrue(all(c["status"] == "unsupported" for c in rows[name]["caps"].values()))


if __name__ == "__main__":
    unittest.main()
