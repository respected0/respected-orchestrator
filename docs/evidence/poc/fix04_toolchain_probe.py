"""FIX-04 follow-up: tool-chain shapes that verify commands really use, run through the production AppContainer path
(network denied). Run from the repo root in a NON-elevated Windows session:

    python docs/evidence/poc/fix04_toolchain_probe.py docs/evidence/poc/fix04_toolchain_results.json

Cases: a venv created OUTSIDE sys.prefix (with and without an extra read-only root for its base interpreter),
`node npm-cli.js test` instead of the refused `npm.cmd` shim, and `git` with its stderr recorded.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from respected_orchestrator.engine import appcontainer  # noqa: E402
from respected_orchestrator.engine.processes import execute  # noqa: E402
from respected_orchestrator.engine.worker_policy import default_policy  # noqa: E402


def run(command, ws, readonly=(), env=None, policy_command=None):
    policy = default_policy(None, ws, policy_command or command, temp_root=ws / "tmp", network_mode="deny", ttl=120, readonly_roots=readonly)
    try:
        done = execute(command, ws, 120, policy=policy, env=env)
        return {"returncode": done.returncode, "tail": (done.stdout + done.stderr).strip()[-300:]}
    except Exception as error:  # noqa: BLE001 - every failure shape is a result
        return {"returncode": None, "tail": f"{type(error).__name__}: {error}"[-300:]}


def main(out):
    assert not appcontainer._is_elevated(), "run in a non-elevated session"
    base = Path(tempfile.mkdtemp(prefix="fix04t-")).resolve()
    ws = base / "ws"
    (ws / "tmp").mkdir(parents=True)
    venv = base / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    vpy = str(venv / "Scripts" / "python.exe")
    (ws / "package.json").write_text('{"name":"p","version":"1.0.0","scripts":{"test":"node -e \\"process.exit(0)\\""}}', encoding="utf-8")
    npm_cli = Path(shutil.which("node")).parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    cache = str(ws / "tmp" / "npm-cache")
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i"], cwd=ws, check=True)
    node_env = {**__import__("os").environ, "npm_config_cache": cache, "npm_config_update_notifier": "false"}
    py = [sys.executable]  # policy built from the interpreter, as the verify path would
    results = {
        "venv_outside_prefix": run([vpy, "-c", "import sys;print('venv', sys.prefix)"], ws),
        "venv_with_venv_readonly": run([vpy, "-c", "import sys;print('venv', sys.prefix)"], ws, readonly=(venv,)),
        "node_npm_cli_test": run(["node", str(npm_cli), "test"], ws, env=node_env, policy_command=py),
        "git_status": run(["git", "status", "--short"], ws, policy_command=py),
        "git_config_origin": run(["git", "config", "--show-origin", "--list"], ws, policy_command=py),
        # the executable's own directory is also handed to the policy (what default_policy does for command[0])
        "policy_built_from_git_exe": run(["git", "status", "--short"], ws),
        "policy_built_from_node_exe": run(["node", "--version"], ws),
    }
    shutil.rmtree(base, ignore_errors=True)
    Path(out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8", newline="\n")
    for name, row in results.items():
        print(f"{name:28} rc={row['returncode']} {ascii(row['tail'][-110:])}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fix04_toolchain_results.json")
