import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator import context


class AtomicWriteTests(unittest.TestCase):
    def test_windows_replace_retries_transient_permission_error(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "status.json"
            real_replace = context.os.replace
            calls = []

            def flaky(source, destination):
                calls.append(1)
                if len(calls) < 3:
                    raise PermissionError(13, "Access is denied")
                return real_replace(source, destination)

            with mock.patch.object(context.os, "replace", side_effect=flaky):
                context.atomic_write_json(target, {"state": "ready"})

            self.assertEqual(3, len(calls))
            self.assertEqual({"state": "ready"}, json.loads(target.read_text(encoding="utf-8")))


class AtomicReadTests(unittest.TestCase):
    def test_windows_read_retries_transient_permission_error(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "status.json"
            target.write_text('{"state": "ready"}', encoding="utf8")
            real_read = Path.read_text
            calls = []

            def flaky(path, *args, **kwargs):
                calls.append(1)
                if len(calls) < 3:
                    raise PermissionError(13, "Access is denied")
                return real_read(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", flaky):
                self.assertEqual('{"state": "ready"}', context.read_text_retry(target))

            self.assertEqual(3, len(calls))


if __name__ == "__main__":
    unittest.main()
