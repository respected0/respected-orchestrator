import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import context_map as cm


class ContextMapTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "F"), ("config", "user.email", "f@example.invalid")]:
            self.git(*args)
        self.ctx = EngineContext(self.root / "data")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)

    def put(self, rel, content, binary=False):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content) if binary else path.write_text(content, encoding="utf-8")

    def commit(self, message="c"):
        self.git("add", "-A")
        self.git("commit", "-m", message)

    def names(self, built, key="files"):
        return [f["path"] for f in built[key]]

    def test_symbols_scope_and_owned_flag(self):
        self.put("src/a.py", "def alpha():\n    pass\n\nclass Beta:\n    def method(self):\n        pass\n")
        self.put("src/ui.js", "export function render() {}\nclass Panel {}\n")
        self.put("docs/readme.md", "# Title\n## Part\n")
        self.put("other/x.py", "def x(): pass\n")
        self.commit()
        built = cm.build(self.repo, allowed=["src", "docs"], forbidden=[])
        self.assertEqual(self.names(built), ["docs/readme.md", "src/a.py", "src/ui.js"])  # other/ is outside the scope: not even named
        py = next(f for f in built["files"] if f["path"] == "src/a.py")
        self.assertEqual([(s["kind"], s["name"], s["line"]) for s in py["symbols"]], [("function", "alpha", 1), ("class", "Beta", 4), ("function", "method", 5)])
        js = next(f for f in built["files"] if f["path"] == "src/ui.js")
        self.assertEqual([s["name"] for s in js["symbols"]], ["render", "Panel"])
        self.assertTrue(all(f["in_task_scope"] for f in built["files"]))
        self.assertEqual(len(py["sha256"]), 64)

    def test_forbidden_secret_generated_binary_and_big_files_are_skipped_with_a_reason(self):
        self.put("src/ok.py", "x = 1\n")
        self.put("src/private/key.py", "SECRET = 1\n")
        self.put("src/.env", "TOKEN=abc\n")
        self.put("src/server.pem", "-----BEGIN-----\n")
        self.put("src/node_modules/pkg/index.js", "function a() {}\n")
        self.put("src/bin.dat", b"\xff\xfe\x00\x80binary", binary=True)
        self.put("src/huge.txt", "a" * (cm.MAX_FILE_BYTES + 1))
        self.commit()
        built = cm.build(self.repo, allowed=["src"], forbidden=["src/private"])
        self.assertEqual(self.names(built), ["src/ok.py"])
        reasons = {s["path"]: s["reason"] for s in built["skipped"]}
        self.assertEqual(reasons, {"src/private/key.py": "forbidden", "src/.env": "secret_like_name", "src/server.pem": "secret_like_name",
                                   "src/node_modules/pkg/index.js": "generated_or_cache", "src/bin.dat": "not_utf8_text", "src/huge.txt": "too_large"})
        self.assertNotIn("TOKEN", str(built))  # contents are never stored

    def test_symlink_is_never_followed(self):
        self.put("src/real.py", "def r(): pass\n")
        outside = self.root / "outside.py"
        outside.write_text("def leaked(): pass\n", encoding="utf-8")
        try:
            os.symlink(outside, self.repo / "src" / "link.py")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks need privilege on this machine")
        self.commit()
        built = cm.build(self.repo, allowed=["src"])
        self.assertEqual(self.names(built), ["src/real.py"])
        self.assertIn(("src/link.py", "link_or_not_a_file"), [(s["path"], s["reason"]) for s in built["skipped"]])
        self.assertNotIn("leaked", str(built))

    def test_a_link_is_skipped_even_when_this_machine_cannot_create_one(self):
        self.put("src/real.py", "def r(): pass\n")
        self.put("src/other.py", "def o(): pass\n")
        self.commit()
        from unittest import mock
        with mock.patch.object(Path, "is_symlink", lambda self: self.name == "real.py"):
            built = cm.build(self.repo, allowed=["src"])
        self.assertEqual(self.names(built), ["src/other.py"])
        self.assertEqual(built["skipped"], [{"path": "src/real.py", "reason": "link_or_not_a_file"}])

    def test_broken_python_and_empty_repo(self):
        self.put("src/bad.py", "def (:\n")
        self.commit()
        built = cm.build(self.repo, allowed=["src"])
        self.assertEqual(built["files"][0]["symbols"][0]["kind"], "unparsed")
        empty = self.root / "empty"
        empty.mkdir()
        for args in [("init", "-b", "main")]:
            subprocess.run(["git", *args], cwd=empty, capture_output=True, check=True)
        built = cm.build(empty, allowed=[])
        self.assertEqual((built["files"], built["key"]["head"]), ([], "no-commit"))

    def test_large_repo_is_bounded(self):
        for i in range(60):
            self.put(f"src/m{i:02}.py", f"def f{i}(): pass\n")
        self.commit()
        built = cm.build(self.repo, allowed=["src"], max_files=25)
        self.assertEqual((len(built["files"]), built["truncated"]), (25, True))
        self.assertFalse(cm.build(self.repo, allowed=["src"])["truncated"])

    def test_cache_hits_and_follows_git_drift(self):
        self.put("src/a.py", "def a(): pass\n")
        self.commit()
        first, how = cm.load_or_build(self.ctx, self.repo, allowed=["src"])
        self.assertEqual(how, "rebuilt:no_valid_cache")
        again, how = cm.load_or_build(self.ctx, self.repo, allowed=["src"])
        self.assertEqual((how, again), ("hit", first))
        self.put("src/a.py", "def a(): pass\ndef b(): pass\n")  # uncommitted edit
        edited, how = cm.load_or_build(self.ctx, self.repo, allowed=["src"])
        self.assertEqual(how, "rebuilt:dirty")
        self.assertEqual([s["name"] for s in edited["files"][0]["symbols"]], ["a", "b"])
        self.commit("edit")  # HEAD moved
        _, how = cm.load_or_build(self.ctx, self.repo, allowed=["src"])
        self.assertEqual(how, "rebuilt:head")
        _, how = cm.load_or_build(self.ctx, self.repo, allowed=["src"], forbidden=["src/a.py"])
        self.assertEqual(how, "rebuilt:scope")
        self.put("src/new.py", "def n(): pass\n")  # a new untracked file is drift too
        _, how = cm.load_or_build(self.ctx, self.repo, allowed=["src"], forbidden=["src/a.py"])
        self.assertEqual(how, "rebuilt:dirty")

    def test_damaged_cache_is_rebuilt(self):
        self.put("src/a.py", "def a(): pass\n")
        self.commit()
        cm.load_or_build(self.ctx, self.repo, allowed=["src"])
        cache = next((self.ctx.data_root / "context-cache").glob("*.json"))
        cache.write_text("{broken", encoding="utf-8")
        built, how = cm.load_or_build(self.ctx, self.repo, allowed=["src"])
        self.assertEqual((how, built["counts"]["files"]), ("rebuilt:no_valid_cache", 1))

    def test_the_map_never_writes_into_the_project(self):
        self.put("src/a.py", "def a(): pass\n")
        self.commit()
        before = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True).stdout
        cm.load_or_build(self.ctx, self.repo, allowed=["src"])
        after = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True).stdout
        self.assertEqual((before, after), ("", ""))


if __name__ == "__main__":
    unittest.main()
