import json
from pathlib import Path
import tempfile
import unittest

from respected_orchestrator.engine import cursor_auth, opencode_auth


class CursorAuthTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.base = Path(self._dir.name)
        self.user = self.base / "user"
        (self.user / "Cursor").mkdir(parents=True)
        self.scratch = self.base / "scratch"
        self.scratch.mkdir()
        self.env = {"APPDATA": str(self.user)}

    def test_copies_only_auth_json_into_isolated_home(self):
        payload = json.dumps({"accessToken": "a", "refreshToken": "r"})
        (self.user / "Cursor" / "auth.json").write_text(payload, encoding="utf8")
        (self.user / "Cursor" / "other.db").write_text("private", encoding="utf8")
        cursor_auth.sync_credentials(self.scratch, user_environment=self.env)
        copied = sorted(p.relative_to(self.scratch).as_posix() for p in self.scratch.rglob("*") if p.is_file())
        self.assertEqual(copied, ["home/AppData/Roaming/Cursor/auth.json"])
        self.assertEqual((self.scratch / "home/AppData/Roaming/Cursor/auth.json").read_text(encoding="utf8"), payload)

    def test_missing_or_invalid_credentials_fail_closed_without_leaking_content(self):
        with self.assertRaises(cursor_auth.CursorAuthError):
            cursor_auth.sync_credentials(self.scratch, user_environment=self.env)
        for bad in ("not json SECRETVALUE", json.dumps([1]), json.dumps({"accessToken": ""}), "x" * (cursor_auth.MAX_AUTH_BYTES + 1)):
            (self.user / "Cursor" / "auth.json").write_text(bad, encoding="utf8")
            with self.assertRaises(cursor_auth.CursorAuthError) as caught:
                cursor_auth.sync_credentials(self.scratch, user_environment=self.env)
            self.assertNotIn("SECRETVALUE", str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)
            self.assertFalse((self.scratch / "home").exists())

    def test_clear_worker_home_removes_the_copied_session(self):
        (self.user / "Cursor" / "auth.json").write_text(json.dumps({"accessToken": "a"}), encoding="utf8")
        cursor_auth.sync_credentials(self.scratch, user_environment=self.env)
        opencode_auth.clear_worker_home(self.scratch)
        self.assertFalse((self.scratch / "home").exists())


if __name__ == "__main__":
    unittest.main()
