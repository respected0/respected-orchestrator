import json
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.engine.capabilities import compatibility as cp, normalize as nz

FOUND = {"python", "gh"}
which = lambda name: f"C:/bin/{Path(name).name}.exe" if Path(name).name.casefold().removesuffix(".exe") in FOUND | {"npx"} else None


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.project = self.home / "app"
        self.project.mkdir(parents=True)
        self.put(self.home / ".claude.json", {"mcpServers": {
            "local": {"command": "gh", "args": ["mcp"]}, "ghost": {"command": "no-such-program-xyz"},
            "pkg": {"command": "npx", "args": ["-y", "p"]}, "remote": {"type": "http", "url": "https://x.example/mcp"}, "empty": {"env": {"A": "b"}}},
            "projects": {str(self.project): {"mcpServers": {"mine": {"command": "gh"}}}, "C:/elsewhere": {"mcpServers": {"theirs": {"command": "gh"}}}}})
        self.put(self.home / ".claude/skills/good/SKILL.md", "---\nname: good\ndescription: Formats Python.\n---\n")
        (self.home / ".claude/skills/bare").mkdir(parents=True)
        (self.home / ".claude/skills/bare/readme.txt").write_text("x")
        inv = nz.build(self.home, self.project, which=which)
        self.rec = {r["name"] + ":" + r["kind"]: r for r in inv["capabilities"]}
        self.inv = inv

    def put(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content), encoding="utf-8")

    def verdict(self, name, client="claude-code", project=None):
        r = cp.resolve(self.rec[name], client, project=project or str(self.project))
        return r["verdict"], {x["code"] for x in r["reasons"]}

    def test_known_clients_come_from_the_discovery_matrix(self):
        known = cp.clients()
        self.assertEqual(set(known["opencode"]), {"mcp"})
        self.assertNotIn("shared", known)
        self.assertEqual(known["codex"], {"mcp", "skill"})

    def test_compatible_local_stdio_server_whose_program_exists(self):
        self.assertEqual(self.verdict("local:mcp"), ("compatible", {"all_checks_passed"}))

    def test_missing_binary_is_incompatible(self):
        self.assertEqual(self.verdict("ghost:mcp"), ("incompatible", {"missing_binary"}))

    def test_package_runner_cannot_be_told_so_unknown(self):
        self.assertEqual(self.verdict("pkg:mcp"), ("unknown", {"binary_unverifiable"}))

    def test_wrong_transport_is_unknown_not_a_guess(self):
        verdict, codes = self.verdict("remote:mcp")
        self.assertEqual((verdict, "transport_unconfirmed" in codes), ("unknown", True))
        self.assertEqual(self.verdict("empty:mcp")[0], "incompatible")  # neither command nor URL

    def test_unsupported_client_and_kind(self):
        self.assertEqual(self.verdict("local:mcp", client="notepad"), ("incompatible", {"client_unsupported"}))
        self.assertEqual(self.verdict("good:skill", client="opencode")[1], {"kind_unsupported"})
        self.assertEqual(self.verdict("good:skill")[0], "compatible")
        self.assertEqual(self.verdict("bare:skill"), ("incompatible", {"skill_file_missing"}))

    def test_project_scope_must_match_the_task_project(self):
        self.assertEqual(self.verdict("mine:mcp")[0], "compatible")
        self.assertEqual(self.verdict("theirs:mcp"), ("incompatible", {"wrong_project"}))
        self.assertEqual(cp.resolve(self.rec["mine:mcp"], "claude-code")["verdict"], "unknown")  # no project given: cannot judge
        self.assertEqual(cp.resolve(self.rec["local:mcp"], "claude-code")["verdict"], "compatible")  # user scope needs none

    def test_duplicates_that_differ_are_unknown(self):
        self.put(self.project / ".mcp.json", {"mcpServers": {"local": {"command": "gh", "args": ["other"]}}})
        inv = nz.build(self.home, self.project, which=which)
        verdicts = {cp.resolve(r, "claude-code", project=str(self.project))["verdict"] for r in inv["capabilities"] if r["name"] == "local"}
        self.assertEqual(verdicts, {"unknown"})

    def test_matrix_over_whole_inventory_explains_every_decision(self):
        out = cp.resolve_all(self.inv, "claude-code", project=str(self.project))
        self.assertEqual(sum(out["counts"].values()), len(self.inv["capabilities"]))
        self.assertTrue(all(r["reasons"] and all(x["detail"] for x in r["reasons"]) for r in out["results"]))

    def test_compatibility_never_touches_trust_or_the_record(self):
        before = json.dumps(self.rec["local:mcp"], sort_keys=True)
        cp.resolve(self.rec["local:mcp"], "claude-code", project=str(self.project))
        self.assertEqual(json.dumps(self.rec["local:mcp"], sort_keys=True), before)
        self.assertFalse(self.rec["local:mcp"]["status"]["trusted"]["state"])  # compatible is not trusted
        self.assertNotIn("trusted", cp.resolve(self.rec["local:mcp"], "claude-code", project=str(self.project)))

    def test_malformed_record_is_incompatible_not_a_crash(self):
        self.assertEqual(cp.resolve({}, "claude-code")["verdict"], "incompatible")
        self.assertEqual(cp.resolve({"kind": "mcp", "entry": None, "status": None}, "claude-code")["verdict"], "unknown")


if __name__ == "__main__":
    unittest.main()
