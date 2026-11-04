"""CUR-01 real Cursor worker run inside the engine's AppContainer sandbox.

Two scenarios against the public CLI, in a temp project and temp data root: `deny` (no operator opt-in: must fail
closed, no provider call) and `write` (RESPECTED_CURSOR_NETWORK=allow, model `auto`, one tiny edit). Afterwards it
checks the credential HOME is gone and that no auth.json token value appears in any evidence file.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent))
import adp01_real_e2e as h  # noqa: E402

POC = h.POC
AUTH = Path(os.environ["APPDATA"]) / "Cursor" / "auth.json"


def secrets():
    data = json.loads(AUTH.read_text(encoding="utf8"))
    return {v for v in data.values() if isinstance(v, str) and len(v) >= 8}


def request(project, task, acceptance):
    return {"project_root": str(project), "task": task, "worker": "cursor", "kind": "write",
            "ownership": ["owned.txt"], "forbidden": ["outside.txt"], "acceptance": acceptance,
            "timeout_seconds": 300, "worker_profile": "auto"}


def scenario(root, project, name, env):
    data_root = root / f"data-{name}"
    task = ('Use your file edit tool to replace the entire content of owned.txt with exactly the text changed followed '
            'by one newline. Do not modify any other file. Reply with exactly this JSON object and no prose: '
            '{"status":"success","summary":"CUR01_WRITE_OK"}')
    accept = [[sys.executable, "-c", "from pathlib import Path; assert Path('owned.txt').read_text(encoding='utf8') == 'changed\\n'"]]
    created = h.must_cli(data_root, ["create"], payload=request(project, task, accept), env=env)
    run_id = created["run_id"]
    started = h.must_cli(data_root, ["start", run_id], env=env)
    status, snapshots = h.wait_terminal(data_root, run_id, limit=420, env=env)
    home = data_root / "state" / run_id / "worker-tmp" / "home"
    check = h.cli(data_root, ["check", run_id], env=env)[1] if status.get("status") == "completed" else None
    return {"name": name, "run_id": run_id, "started": started, "status": status, "check": check,
            "credential_home_removed": not home.exists()}


def main():
    root = Path(tempfile.mkdtemp(prefix="respected-cur01-")).resolve()
    project = h.setup_project(root)
    secret_values = secrets()
    base = dict(os.environ, PYTHONPATH=str(h.SRC))
    base.pop("RESPECTED_CURSOR_NETWORK", None)
    records = {"root": str(root), "scenarios": {}}
    records["scenarios"]["deny"] = scenario(root, project, "deny", base)
    records["scenarios"]["write"] = scenario(root, project, "write", dict(base, RESPECTED_CURSOR_NETWORK="allow"))
    h.scan_for_secrets([root], records, secret_values)
    records["secret_scan"] = "passed: no Cursor auth.json token value in CLI output or run data"
    POC.mkdir(parents=True, exist_ok=True)
    for name, value in records["scenarios"].items():
        (POC / f"cursor01_{name}.log").write_text(h.redact(value, secret_values) + "\n", encoding="utf8")
    (POC / "cursor01_summary.log").write_text(h.redact(records, secret_values) + "\n", encoding="utf8")
    print(json.dumps({"statuses": {n: v["status"].get("status") for n, v in records["scenarios"].items()},
                      "reasons": {n: v["status"].get("reason") for n, v in records["scenarios"].items()},
                      "home_removed": {n: v["credential_home_removed"] for n, v in records["scenarios"].items()}}, indent=2))


if __name__ == "__main__":
    main()
