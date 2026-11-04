"""FIX-04 spike: can verify-type commands run inside the worker AppContainer with the network denied?

Run from the repo root on a NON-elevated Windows session:
    python docs/evidence/poc/fix04_verify_appcontainer_probe.py docs/evidence/poc/fix04_results.json

Every case runs twice: unsandboxed (control, proves the attack/tool is real) and through the production
AppContainer path (`default_policy` + `processes.execute`, network_mode="deny"). Nothing here weakens a policy.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from respected_orchestrator.engine import appcontainer  # noqa: E402
from respected_orchestrator.engine.processes import execute  # noqa: E402
from respected_orchestrator.engine.worker_policy import default_policy  # noqa: E402

PY = sys.executable


def listener():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    threading.Thread(target=lambda: [server.accept() for _ in range(8)], daemon=True).start()
    return server, server.getsockname()[1]


def main(out):
    assert not appcontainer._is_elevated(), "run in a non-elevated session"
    work = Path(tempfile.mkdtemp(prefix="fix04-")).resolve()
    ws = work / "ws"
    (ws / "tmp").mkdir(parents=True)
    (ws / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test(self):\n        self.assertEqual(1, 1)\n"
        "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8")
    (ws / "package.json").write_text('{"name":"p","version":"1.0.0","scripts":{"test":"node -e \\"process.exit(0)\\""}}',
                                     encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A"], cwd=ws, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i"], cwd=ws, check=True)
    server, port = listener()
    child_net = ("import subprocess,sys;"
                 f"r=subprocess.run([sys.executable,'-c','import socket;socket.create_connection((\\'1.1.1.1\\',443),3)'],capture_output=True);"
                 "print('CONNECTED' if r.returncode==0 else 'BLOCKED')")
    cases = {
        # legitimate verify tooling (must keep working)
        "python_print": ([PY, "-c", "print('ok')"], "ok"),
        "python_unittest": ([PY, "-m", "unittest", "-q"], "OK"),
        "git_status": (["git", "status", "--short"], None),
        "git_rev_parse": (["git", "rev-parse", "HEAD"], None),
        "node_version": (["node", "--version"], None),
        "npm_test": (["npm.cmd", "test"], None),
        "cmd_echo": (["cmd.exe", "/c", "echo ok"], "ok"),
        # network egress (must be blocked when sandboxed)
        "net_ip": ([PY, "-c", "import socket;socket.create_connection(('1.1.1.1',443),3);print('CONNECTED')"], "CONNECTED"),
        "net_dns": ([PY, "-c", "import socket;print('RESOLVED',socket.gethostbyname('example.com'))"], "RESOLVED"),
        "net_loopback": ([PY, "-c", f"import socket;socket.create_connection(('127.0.0.1',{port}),3);print('CONNECTED')"], "CONNECTED"),
        "net_child_process": ([PY, "-c", child_net], "CONNECTED"),
    }
    results = {"python": PY, "cases": {}}
    policy = default_policy(None, ws, [PY], temp_root=ws / "tmp", network_mode="deny", ttl=60)
    for name, (command, marker) in cases.items():
        row = {}
        for mode in ("control", "appcontainer"):
            try:
                if mode == "control":
                    done = subprocess.run(command, cwd=ws, capture_output=True, text=True, timeout=60, shell=False)
                    code, text = done.returncode, (done.stdout + done.stderr)
                else:
                    done = execute(command, ws, 60, policy=policy)
                    code, text = done.returncode, (done.stdout + done.stderr)
            except Exception as error:  # noqa: BLE001 - the probe records every failure shape
                code, text = None, f"{type(error).__name__}: {error}"
            row[mode] = {"returncode": code, "marker_seen": bool(marker and marker in text), "tail": text.strip()[-160:]}
        results["cases"][name] = row
    server.close()
    shutil.rmtree(work, ignore_errors=True)
    Path(out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    for name, row in results["cases"].items():
        c, a = row["control"], row["appcontainer"]
        print(f"{name:18} control rc={c['returncode']} marker={c['marker_seen']} | appcontainer rc={a['returncode']} marker={a['marker_seen']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fix04_results.json")
