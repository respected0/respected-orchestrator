"""Exercise demo commands in disposable fixtures without calling an AI model."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import run_maf_coding_demo as demo


class CodingDemoTests(unittest.TestCase):
    def test_demo_acceptance_creates_no_files_outside_ownership(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            requests = []
            def capture_request(ctx, request):
                requests.append(request)
                return {"run_id": "fixture"}
            with mock.patch.object(demo.tempfile, "mkdtemp", return_value=temporary), \
                    mock.patch.object(demo, "preflight_sandbox"), \
                    mock.patch.object(demo, "preflight_auth"), \
                    mock.patch.object(demo, "git"), \
                    mock.patch.object(demo, "get_cli_command", return_value=["fixture/codex"]), \
                    mock.patch.object(demo, "create_task", side_effect=capture_request), \
                    mock.patch.object(demo, "run_maf_coding_task", return_value={"status": "FAILED"}), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(demo.main(), 1)
            repo = root / "project"
            self.assertEqual(requests[0]["command"][requests[0]["command"].index("-p") + 1], "mimo")
            (repo / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf8")
            env = dict(os.environ)
            env.pop("PYTHONDONTWRITEBYTECODE", None)
            check = subprocess.run(requests[0]["acceptance"][0], cwd=repo, env=env,
                                   capture_output=True, text=True, timeout=10)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertFalse((repo / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
