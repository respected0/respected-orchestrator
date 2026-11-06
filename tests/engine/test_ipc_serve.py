import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "k" * 32


class IpcServeTests(unittest.TestCase):
    def run_engine(self, lines, token=TOKEN):
        with tempfile.TemporaryDirectory() as data:
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), RESPECTED_DATA_DIR=data, PYTHONUTF8="1", RESPECTED_IPC_TOKEN=token)
            return subprocess.run([sys.executable, "-m", "respected_orchestrator", "_ipc"], input="\n".join(lines) + "\n",
                                  capture_output=True, text=True, env=env, timeout=60)

    def test_one_response_line_per_request_and_token_is_required(self):
        good = json.dumps(dict(ipc="1", id="serve-0001", session=TOKEN, cmd="hello"))
        bad = json.dumps(dict(ipc="1", id="serve-0002", session="nope", cmd="hello"))
        proc = self.run_engine([good, bad])
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([r["id"] for r in replies], ["serve-0001", "serve-0002"])
        self.assertEqual([r["ok"] for r in replies], [True, False])
        self.assertEqual(replies[1]["error"]["code"], "UNAUTHENTICATED")

    def test_missing_token_refuses_to_start(self):
        proc = self.run_engine([], token="")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout)["error"]["code"], "IPC_TOKEN")


if __name__ == "__main__":
    unittest.main()
