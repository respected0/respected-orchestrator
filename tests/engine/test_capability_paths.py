import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.capabilities import paths
from respected_orchestrator.engine.local_api import LocalApi


def tree(root):
    """Everything observable about a tree: names, sizes, mtimes, content hashes."""
    out = {}
    for p in sorted(Path(root).rglob("*")):
        rel = str(p.relative_to(root))
        out[rel] = (p.stat().st_size, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir")
    return out


class PathsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "kullanıcı-ünlü"  # non-ASCII profile folder
        self.home.mkdir()
        self.project = self.home / "proje-çalışma"
        self.project.mkdir()

    def put(self, rel, content, root=None, binary=False):
        path = (root or self.home) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if binary else content.encode("utf-8"))
        return path

    def row(self, result, client, kind="mcp", scope="user"):
        return next(r for r in result["locations"] if (r["client"], r["kind"], r["scope"]) == (client, kind, scope))

    def test_matrix_covers_every_supported_client_with_honest_sources(self):
        rows = paths.matrix(self.home, self.project)
        self.assertEqual({r["client"] for r in rows}, {"claude-code", "codex", "cursor", "opencode", "shared", "antigravity"})
        self.assertEqual({r["scope"] for r in rows}, {"user", "project"})
        self.assertTrue(all(r["source"] in ("code", "observed", "documented", "unconfirmed") for r in rows))
        ag = next(r for r in rows if r["client"] == "antigravity")
        self.assertEqual((ag["path"], ag["source"]), (None, "unconfirmed"))  # not guessed
        self.assertNotIn("project", {r["scope"] for r in paths.matrix(self.home)})

    def test_valid_configs_report_names_not_values(self):
        self.put(".claude.json", json.dumps({"mcpServers": {"ctx": {"command": "npx", "env": {"API_KEY": "sk-VERYSECRETVALUE123456"}}}, "other": 1}))
        self.put(".codex/config.toml", '[mcp_servers.github]\ncommand = "gh"\n[mcp_servers.github.env]\nTOKEN = "ghp_SECRETSECRETSECRETSECRET12"\n')
        r = paths.scan(self.home)
        claude, codex = self.row(r, "claude-code"), self.row(r, "codex")
        self.assertEqual((claude["state"], claude["entry_names"], claude["top_level_keys"]), ("ok", ["ctx"], ["mcpServers", "other"]))
        self.assertEqual(codex["entry_names"], ["github"])
        blob = json.dumps(r)
        for secret in ("VERYSECRET", "SECRETSECRET", "npx", "API_KEY"):
            self.assertNotIn(secret, blob)
        self.assertEqual(claude["sha256"], hashlib.sha256((self.home / ".claude.json").read_bytes()).hexdigest())

    def test_absent_is_absent_not_an_error(self):
        r = paths.scan(self.home)
        self.assertTrue(all(x["state"] in ("absent", "unknown") for x in r["locations"]))
        self.assertEqual(self.row(r, "cursor")["error_class"], "not_found")
        self.assertEqual(self.row(r, "antigravity")["error_class"], "location_unknown")

    def test_malformed_files_give_a_named_error_class_and_never_raise(self):
        self.put(".claude.json", "{ not json ")
        self.put(".codex/config.toml", "[broken\nx = ")
        self.put(".cursor/mcp.json", b"\xff\xfe\x00bad".decode("latin-1"), binary=False)
        self.put(".config/opencode/opencode.json", "[1, 2, 3]")
        r = paths.scan(self.home)
        self.assertEqual(self.row(r, "claude-code")["error_class"], "malformed_json")
        self.assertEqual(self.row(r, "codex")["error_class"], "malformed_toml")
        self.assertEqual(self.row(r, "opencode")["error_class"], "unsupported_shape")
        self.assertIn(self.row(r, "cursor")["error_class"], ("bad_encoding", "malformed_json"))
        for x in r["locations"]:
            self.assertTrue(x.get("error_class") is None or x["error_class"] in paths.ERROR_CLASSES)

    def test_wrong_shapes_and_bom_and_unicode_content(self):
        self.put(".claude.json", '{"mcpServers": ["not", "a", "table"]}')
        self.assertEqual(self.row(paths.scan(self.home), "claude-code")["error_class"], "unsupported_shape")
        self.put(".claude.json", "﻿" + json.dumps({"mcpServers": {"ünlü-sunucu": {}}}, ensure_ascii=False))
        r = self.row(paths.scan(self.home), "claude-code")
        self.assertEqual((r["state"], r["entry_names"]), ("ok", ["ünlü-sunucu"]))
        self.put(".claude.json", "x", binary=False)
        (self.home / ".claude.json").unlink()
        (self.home / ".claude.json").mkdir()  # a directory where a file is expected
        self.assertIn(self.row(paths.scan(self.home), "claude-code")["state"], ("refused", "unreadable_content"))

    def test_oversized_and_sensitive_files_are_not_read(self):
        self.put(".claude.json", "{" + " " * (paths.MAX_CONFIG_BYTES + 5) + "}")
        self.assertEqual(self.row(paths.scan(self.home), "claude-code")["error_class"], "too_large")
        with mock.patch.object(paths, "_SENSITIVE", __import__("re").compile("mcp\\.json")):
            self.put(".cursor/mcp.json", '{"mcpServers": {}}')
            with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("a sensitive file was read")):
                r = paths.scan(self.home)
            self.assertEqual(self.row(r, "cursor")["error_class"], "sensitive_file")

    def test_permission_errors_are_a_class_not_a_crash(self):
        self.put(".claude.json", "{}")
        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError("denied")):
            r = paths.scan(self.home)
        self.assertEqual(self.row(r, "claude-code")["error_class"], "unreadable")

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows reparse point")
    def test_junctions_are_refused_and_never_followed(self):
        outside = Path(self.home.parent) / "dis-klasor"
        outside.mkdir()
        (outside / "config.toml").write_text('[mcp_servers.stolen]\ncommand = "x"\n', encoding="utf-8")
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.home / ".codex"), str(outside)], capture_output=True)
        self.assertEqual(made.returncode, 0, "junction could not be created; the protection is untested")
        r = paths.scan(self.home)
        codex = self.row(r, "codex")
        self.assertEqual((codex["state"], codex["error_class"]), ("refused", "link_refused"))
        self.assertNotIn("stolen", json.dumps(r))
        self.assertEqual(self.row(r, "codex", "skill")["error_class"], "link_refused")
        subprocess.run(["cmd", "/c", "rmdir", str(self.home / ".codex")], capture_output=True)

    @unittest.skipUnless(os.name == "nt", "junctions are a Windows reparse point")
    def test_linked_skill_folders_are_skipped_and_odd_names_ignored(self):
        outside = Path(self.home.parent) / "dis-beceri"
        outside.mkdir()
        (outside / "SKILL.md").write_text("x", encoding="utf-8")
        self.put(".claude/skills/guzel/SKILL.md", "# ok")
        self.put(".claude/skills/yarim/readme.txt", "no skill file")
        (self.home / ".claude/skills/..hidden").mkdir()
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.home / ".claude/skills/linked"), str(outside)], capture_output=True)
        self.assertEqual(made.returncode, 0)
        skills = {s["name"]: s["has_skill_md"] for s in self.row(paths.scan(self.home), "claude-code", "skill")["skills"]}
        self.assertEqual(skills, {"guzel": True, "yarim": False})
        subprocess.run(["cmd", "/c", "rmdir", str(self.home / ".claude/skills/linked")], capture_output=True)

    def test_skill_listing_is_bounded(self):
        for i in range(paths.MAX_SKILLS + 20):
            (self.home / ".agents/skills" / f"s{i:04d}").mkdir(parents=True)
        r = self.row(paths.scan(self.home), "shared", "skill")
        self.assertEqual((len(r["skills"]), r["truncated"]), (paths.MAX_SKILLS, True))

    def test_project_scope_is_confined_to_the_project(self):
        self.put(".mcp.json", json.dumps({"mcpServers": {"proj": {}}}), root=self.project)
        r = paths.scan(self.home, self.project)
        self.assertEqual(self.row(r, "claude-code", "mcp", "project")["entry_names"], ["proj"])
        self.assertEqual(self.row(r, "claude-code", "mcp", "project")["path"], str(self.project / ".mcp.json"))

    def test_scanning_writes_nothing_and_starts_nothing(self):
        marker = self.home / "MARKER-must-not-exist"
        self.put(".claude.json", json.dumps({"mcpServers": {"evil": {"command": "python", "args": ["-c", f"open(r'{marker}', 'w').write('x')"]}}}))
        self.put(".codex/config.toml", f'[mcp_servers.evil]\ncommand = "cmd"\nargs = ["/c", "echo x > {marker}"]\n')
        self.put(".claude/skills/s/SKILL.md", "# skill")
        before = tree(self.home)
        boom = AssertionError("a process was started")
        with mock.patch.object(subprocess, "Popen", side_effect=boom), mock.patch.object(subprocess, "run", side_effect=boom), \
                mock.patch.object(os, "system", side_effect=boom), mock.patch.object(os, "startfile", side_effect=boom, create=True):
            paths.scan(self.home, self.project)
        self.assertEqual(tree(self.home), before)
        self.assertFalse(marker.exists())

    def test_module_cannot_start_processes_or_write(self):
        source = Path(paths.__file__).read_text(encoding="utf-8")
        for forbidden in ("subprocess", "os.system", "Popen", ".write_text", ".write_bytes", "open(", "unlink", "os.remove", "shutil"):
            self.assertNotIn(forbidden, source, forbidden)


class ScanIpcTests(unittest.TestCase):
    def call(self, origin, payload, home):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"USERPROFILE": str(home), "HOME": str(home)}):
            api = LocalApi(EngineContext(Path(tmp) / "data"), "t" * 32, origin=origin)
            return api.handle({"ipc": "1", "id": "scn-00001", "session": "t" * 32, "cmd": "capabilities.scan", "payload": payload})

    def test_read_only_and_validates_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude.json").write_text(json.dumps({"mcpServers": {"a": {}}}), encoding="utf-8")
            ok = self.call(Origin.MCP, {}, home)
            self.assertTrue(ok["ok"], ok)
            self.assertEqual(next(l for l in ok["result"]["locations"] if l["client"] == "claude-code" and l["kind"] == "mcp")["entry_names"], ["a"])
            for bad in ({"project_root": "relative/dir"}, {"project_root": str(home / "nope")}, {"project_root": 5}):
                self.assertEqual(self.call(Origin.RENDERER, bad, home)["error"]["code"], "BAD_REQUEST")
            self.assertEqual(self.call(Origin.WORKER, {}, home)["error"]["code"], "FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
