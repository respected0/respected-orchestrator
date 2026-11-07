import copy
import json
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.engine import capability_manifest as cm
from respected_orchestrator.engine.capabilities import normalize as nz, permissions as pm

which = lambda name: f"C:/bin/{Path(name).name}.exe" if Path(name).name.casefold().removesuffix(".exe") in {"gh"} else None


def manifest(**over):
    m = {"name": "m", "version": "1", "provenance": "local:test", "trust": "trusted", "tools": {"repo.search": ["read"]},
         "read": ["repo"], "write": [], "net": "none", "data_scope": ["src"], **over}
    m["sha256"] = cm.digest(m)
    return m


class PermissionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = Path(tmp.name) / "home"
        home.mkdir()
        (home / ".claude/skills/t").mkdir(parents=True)
        (home / ".claude/skills/t/SKILL.md").write_text("---\nname: t\ndescription: x\n---\n", encoding="utf-8")
        (home / ".claude.json").write_text(json.dumps({"mcpServers": {
            "local": {"command": "gh", "args": ["mcp"], "env": {"GITHUB_TOKEN": "ghp_" + "A" * 30}},
            "plain": {"command": "gh", "env": {"GITHUB_TOKEN": ""}},
            "loop": {"type": "http", "url": "http://127.0.0.1:9000/mcp"},
            "ext": {"type": "http", "url": "https://evil.example/mcp"}}}), encoding="utf-8")
        skill = home / ".claude/skills/s"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: s\ndescription: x\nallowed-tools: Bash, Write\n---\n", encoding="utf-8")
        self.inv = nz.build(home, None, which=which)
        self.rec = {r["name"]: r for r in self.inv["capabilities"]}

    def areas(self, card, area):
        return [(r["level"], r["detail"]) for r in card["risks"] if r["area"] == area]

    def test_missing_manifest_is_denied_and_trust_is_a_separate_question(self):
        card = pm.inspect(self.rec["local"])
        self.assertEqual((card["execution"]["allowed"], card["execution"]["code"]), (False, "MANIFEST_MISSING"))
        self.assertEqual(card["trust"]["state"], "unknown")
        self.assertEqual(card["availability"]["installed"], True)  # present on disk says nothing about trust or safety
        self.assertEqual(card["side_effects"], "none")

    def test_false_trusted_flag_inside_the_manifest_counts_for_nothing(self):
        card = pm.inspect(self.rec["local"], manifest())
        self.assertEqual((card["trust"]["state"], card["trust"]["self_claimed"]), ("unknown", "trusted"))
        self.assertEqual((card["execution"]["allowed"], card["execution"]["code"]), (False, "NO_APPROVAL_RECORD"))

    def test_approval_record_opens_the_gate_only_for_the_exact_digest_and_provenance(self):
        m = manifest()
        good = [{"manifest_digest": cm.digest(m), "provenance": "local:test"}]
        self.assertTrue(pm.inspect(self.rec["local"], m, good)["execution"]["allowed"])
        self.assertFalse(pm.inspect(self.rec["local"], manifest(version="2"), good)["execution"]["allowed"])  # a different manifest
        self.assertFalse(pm.inspect(self.rec["local"], m, [{"manifest_digest": cm.digest(m), "provenance": "elsewhere"}])["execution"]["allowed"])
        self.assertFalse(pm.inspect(self.rec["local"], m, ["junk", None, {"manifest_digest": 5}])["execution"]["allowed"])

    def test_malicious_manifests_are_denied_with_the_gates_own_code(self):
        cases = {"MANIFEST_UNDECLARED_FIELD": {**manifest(), "allow_everything": True}, "DATA_SCOPE_INVALID": manifest(data_scope=["../../etc"]),
                 "TOOL_UNKNOWN": manifest(tools={"shell.run": ["exec"]}), "EXCESS_PERMISSION": manifest(tools={"repo.patch": ["write"]}),
                 "NET_INVALID": manifest(net="open"), "MANIFEST_HASH_CHANGED": {**manifest(), "name": "changed-after-hash"},
                 "MANIFEST_INVALID": "not an object", "MANIFEST_INCOMPLETE": {"name": "x"}}
        for code, bad in cases.items():
            card = pm.inspect(self.rec["local"], bad, [{"manifest_digest": "X", "provenance": "local:test"}])
            self.assertEqual((card["execution"]["allowed"], card["execution"]["code"]), (False, code), code)

    def test_risks_by_area(self):
        local = pm.inspect(self.rec["local"])
        self.assertEqual(self.areas(local, "command")[0][0], "medium")
        self.assertEqual(self.areas(local, "secrets")[0][0], "high")  # a real token sits in the client config; its value is never shown
        self.assertEqual(self.areas(pm.inspect(self.rec["plain"]), "secrets")[0][0], "medium")  # only the variable name is declared
        self.assertNotIn("ghp_", json.dumps(local))
        self.assertEqual(self.areas(pm.inspect(self.rec["loop"]), "network")[0][0], "low")
        ext = self.areas(pm.inspect(self.rec["ext"]), "network")[0]
        self.assertEqual(ext[0], "high")
        self.assertIn("external", ext[1])
        self.assertEqual(self.areas(pm.inspect(self.rec["s"]), "command")[0][0], "medium")  # skill asks for Bash
        self.assertEqual(self.areas(local, "roots")[0][0], "medium")  # user scope reaches every project

    def test_overall_level_never_hides_unknown_or_high(self):
        self.assertEqual(pm.inspect(self.rec["ext"])["level"], "high")
        self.assertEqual(pm.inspect(self.rec["local"])["level"], "high")  # a stored secret dominates
        self.assertEqual(pm.inspect(self.rec["t"])["level"], "unknown")  # a skill that declares no tools is unknown, not low
        self.assertEqual(pm.inspect(self.rec["plain"])["level"], "medium")

    def test_too_broad_and_whole_workspace(self):
        broad = manifest(tools={"repo.search": ["read"], "repo.patch": ["write"], "test.run": ["net"]}, write=["workspace"], net="allowlist")
        card = pm.inspect(self.rec["local"], broad)
        self.assertEqual(self.areas(card, "breadth")[0][0], "high")
        self.assertEqual(card["level"], "high")
        whole = pm.inspect(self.rec["local"], manifest(data_scope=["."]))
        self.assertEqual(self.areas(whole, "files")[0], ("high", "data scope covers the whole workspace"))
        self.assertEqual(self.areas(pm.inspect(self.rec["local"], manifest()), "files")[0][0], "low")

    def test_inspection_changes_nothing(self):
        before, m = copy.deepcopy(self.rec["local"]), manifest()
        pm.inspect(self.rec["local"], m)
        self.assertEqual(self.rec["local"], before)
        self.assertEqual(m["sha256"], cm.digest(m))

    def test_malformed_inputs_do_not_crash(self):
        for rec in ({}, {"kind": "mcp", "entry": None, "status": None, "declared_permissions": None}):
            card = pm.inspect(rec, {"read": 5, "data_scope": "x", "tools": 3})
            self.assertFalse(card["execution"]["allowed"])
            self.assertIn(card["level"], ("unknown", "low", "medium", "high"))


if __name__ == "__main__":
    unittest.main()
