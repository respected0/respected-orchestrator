"""Credential bridge tests: secrets travel only over memory/stdin, never argv or logs."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

from respected_orchestrator.engine import opencode_auth


FAKE_CLI = textwrap.dedent(r'''
    import hashlib, json, os, pathlib, sys

    args = sys.argv[1:]
    action = args[1] if args[:1] == ["auth"] else args[0]
    if action == "export":
        payload = [{"provider": "fixture", "secret": "s3cr3t-value"}]
        if os.environ.get("OPENCODE_FIXTURE_EXPORT_MODE") == "empty":
            payload = []
        elif os.environ.get("OPENCODE_FIXTURE_EXPORT_MODE") == "failed":
            raise SystemExit(3)
        print(json.dumps(payload), flush=True)
    elif action == "import":
        record = pathlib.Path(os.environ["OPENCODE_FIXTURE_RECORD"])
        raw = sys.stdin.read()
        record.write_text(json.dumps({
            "sha256": hashlib.sha256(raw.encode("utf8")).hexdigest(),
            "home": os.environ.get("HOME"),
            "standalone": "--standalone" in sys.argv,
        }), encoding="utf8")
        print("Imported 1 credentials", flush=True)
    else:
        raise SystemExit(4)
''')


class OpenCodeAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = self.root / "record.json"
        self.home = self.root / "worker-tmp" / "home"
        self.home.mkdir(parents=True)

    def environment(self, **extra):
        env = {**os.environ, "HOME": str(self.home), "USERPROFILE": str(self.home),
               "XDG_DATA_HOME": str(self.home / ".local" / "share"),
               "OPENCODE_FIXTURE_RECORD": str(self.record)}
        env.update(extra)
        return env

    def command(self):
        return [sys.executable, "-c", FAKE_CLI]

    def test_credentials_are_imported_through_stdin_into_the_isolated_home(self):
        environment = self.environment()
        opencode_auth.sync_credentials(self.command(), environment, deadline=time.monotonic() + 5,
                                       user_environment=environment)
        record = json.loads(self.record.read_text(encoding="utf8"))
        expected = json.dumps([{"provider": "fixture", "secret": "s3cr3t-value"}],
                              ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(record["sha256"], hashlib.sha256(expected.encode("utf8")).hexdigest())
        self.assertEqual(Path(record["home"]).resolve(), self.home.resolve())
        self.assertTrue(record["standalone"])

    def test_export_failures_are_bounded_and_never_include_secret_output(self):
        for mode in ("empty", "failed"):
            with self.subTest(mode=mode):
                with self.assertRaises(opencode_auth.OpenCodeAuthError) as caught:
                    opencode_auth.sync_credentials(
                        self.command(), self.environment(OPENCODE_FIXTURE_EXPORT_MODE=mode),
                        deadline=time.monotonic() + 5,
                        user_environment=self.environment(OPENCODE_FIXTURE_EXPORT_MODE=mode))
                self.assertNotIn("s3cr3t", str(caught.exception))

    def test_import_failure_is_reported_without_echoing_input(self):
        def fake_run(command, **kwargs):
            if "export" in command:
                return mock.Mock(returncode=0, stdout='[{"secret":"s3cr3t-value"}]', stderr="")
            return mock.Mock(returncode=9, stdout="", stderr="s3cr3t-value")
        with mock.patch.object(opencode_auth, "_run", side_effect=fake_run):
            with self.assertRaises(opencode_auth.OpenCodeAuthError) as caught:
                opencode_auth.sync_credentials(self.command(), self.environment(), deadline=time.monotonic() + 5)
        self.assertNotIn("s3cr3t", str(caught.exception))

    def test_cleanup_removes_only_the_worker_home(self):
        (self.home / "auth.json").write_text("s3cr3t-value", encoding="utf8")
        keep = self.root / "worker-tmp" / "keep.txt"
        keep.write_text("keep", encoding="utf8")
        opencode_auth.clear_worker_home(self.root / "worker-tmp")
        self.assertFalse(self.home.exists())
        self.assertTrue(keep.exists())


if __name__ == "__main__":
    unittest.main()
