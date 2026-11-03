"""ADP-01 real OpenCode end-to-end evidence harness.

Temporary development harness. It uses a project and data root outside this repository,
drives the public CLI (create/start/inspect/check/apply), and writes redacted evidence only.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
POC = REPO / "docs" / "ilerleme" / "poc"
OPENCODE = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@opencode" / "cli" / "bin" / "opencode.exe"
MODEL = "amd/DeepSeek-V4.1-Flash"
BASE_ENV = dict(os.environ, PYTHONPATH=str(SRC), RESPECTED_OPENCODE_NETWORK="allow")
TERMINAL = {"completed", "failed", "timed_out", "cancelled", "interrupted"}


def clean(value):
    if isinstance(value, str):
        return value.replace("\r\n", "\n")
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    return value


def run_process(command, *, payload=None, env=None, cwd=None, timeout=180):
    return subprocess.run(
        [str(part) for part in command],
        input=None if payload is None else json.dumps(payload, ensure_ascii=False),
        text=True, encoding="utf-8", errors="replace", capture_output=True,
        cwd=str(cwd or REPO), env=env or BASE_ENV, timeout=timeout,
    )


def parse_output(result):
    text = result.stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}


def cli(data_root, args, *, payload=None, env=None, timeout=180):
    command = [sys.executable, "-m", "respected_orchestrator", "--data-root", str(data_root), *args]
    result = run_process(command, payload=payload, env=env, timeout=timeout)
    return result.returncode, parse_output(result), result


def must_cli(data_root, args, *, payload=None, env=None, timeout=180):
    code, value, result = cli(data_root, args, payload=payload, env=env, timeout=timeout)
    if code != 0:
        raise RuntimeError(f"CLI {args} failed ({code}): {value}\n{result.stderr}")
    return value


def git(project, *args):
    return subprocess.run(["git", *args], cwd=project, text=True, encoding="utf-8",
                          capture_output=True, check=True).stdout


def setup_project(root):
    project = root / "project"
    project.mkdir()
    git(project, "init", "-b", "main")
    git(project, "config", "user.name", "ADP01 E2E")
    git(project, "config", "user.email", "adp01@example.invalid")
    (project / "owned.txt").write_text("base\n", encoding="utf8")
    (project / "outside.txt").write_text("private\n", encoding="utf8")
    git(project, "add", ".")
    git(project, "commit", "-m", "baseline")
    return project


def request_for(project, *, kind, task, acceptance=None, profile=MODEL, timeout=300):
    return {
        "project_root": str(project),
        "task": task,
        "worker": "opencode",
        "kind": kind,
        "ownership": ["owned.txt"],
        "forbidden": ["outside.txt"],
        "acceptance": acceptance or [],
        "timeout_seconds": timeout,
        "worker_profile": profile,
    }


def create(data_root, request):
    return must_cli(data_root, ["create"], payload=request)


def wait_terminal(data_root, run_id, *, limit=480, env=None):
    deadline = time.monotonic() + limit
    snapshots = []
    while time.monotonic() < deadline:
        code, value, result = cli(data_root, ["inspect", run_id], env=env)
        if code != 0:
            raise RuntimeError(f"inspect failed: {value}\n{result.stderr}")
        snapshots.append(value)
        if value.get("status") in TERMINAL:
            return value, snapshots
        time.sleep(2)
    raise TimeoutError(f"run did not become terminal: {run_id}")


def run_task(data_root, project, *, name, kind, task, acceptance=None, profile=MODEL,
             timeout=300, start_env=None, wait_limit=480):
    before = (project / "owned.txt").read_text(encoding="utf8")
    status_before = git(project, "status", "--porcelain")
    created = create(data_root, request_for(project, kind=kind, task=task, acceptance=acceptance,
                                            profile=profile, timeout=timeout))
    run_id = created["run_id"]
    started = must_cli(data_root, ["start", run_id], env=start_env)
    inspected, snapshots = wait_terminal(data_root, run_id, limit=wait_limit, env=start_env)
    check = None
    if inspected.get("status") == "completed":
        code, check, raw = cli(data_root, ["check", run_id], env=start_env)
        if code != 0:
            raise RuntimeError(f"check failed for {name}: {check}\n{raw.stderr}")
    home = data_root / "state" / run_id / "worker-tmp" / "home"
    if home.exists():
        raise AssertionError(f"worker credential HOME survived cleanup for {name}: {home}")
    if name in {"read", "invalid_model", "timeout", "acceptance_failure", "auth_missing"}:
        after = (project / "owned.txt").read_text(encoding="utf8")
        if after != before or git(project, "status", "--porcelain") != status_before:
            raise AssertionError(f"{name} changed the real project worktree")
    return {
        "name": name, "run_id": run_id, "created": created, "started": started,
        "status": inspected, "check": check, "snapshots": snapshots,
    }


def credential_secrets():
    result = run_process([OPENCODE, "auth", "export", "--standalone"], env=BASE_ENV)
    if result.returncode != 0:
        raise RuntimeError("real auth export failed; cannot establish secret-scan baseline")
    payload = json.loads(result.stdout)
    found = set()

    def visit(value, key=""):
        if isinstance(value, dict):
            for child_key, child in value.items():
                visit(child, str(child_key))
        elif isinstance(value, list):
            for child in value:
                visit(child, key)
        elif isinstance(value, str) and len(value) >= 8 and any(
                marker in key.casefold() for marker in ("key", "token", "secret", "refresh", "access")):
            found.add(value)

    visit(payload)
    if not found:
        raise RuntimeError("auth export contained no scannable credential values")
    return found


def scan_for_secrets(roots, records, secrets):
    encoded = json.dumps(records, ensure_ascii=False).encode("utf8")
    for secret in secrets:
        needle = secret.encode("utf8")
        if needle in encoded:
            raise AssertionError("credential value leaked into CLI evidence")
        for root in roots:
            for path in Path(root).rglob("*"):
                if path.is_file() and needle in path.read_bytes():
                    raise AssertionError(f"credential value leaked into {path}")


def redact(value, secrets):
    text = json.dumps(value, ensure_ascii=False, indent=2)
    for secret in secrets:
        text = text.replace(secret, "***REDACTED***")
    return text


def write_evidence(name, value, secrets):
    POC.mkdir(parents=True, exist_ok=True)
    path = POC / f"adp01_real_{name}.log"
    path.write_text(redact(value, secrets) + "\n", encoding="utf8")
    return path


def mcp_roundtrip(root, secrets):
    home = root / "mcp-home"
    config = home / ".config" / "opencode" / "opencode.json"
    config.parent.mkdir(parents=True)
    original = {
        "theme": "dark",
        "mcp": {"servers": {"probe": {"type": "local", "command": ["C:\\Windows\\System32\\where.exe", "cmd.exe"]}}},
        "keybinds": {"leader": "ctrl+x"},
    }
    original_text = json.dumps(original, ensure_ascii=False, indent=2) + "\n"
    config.write_text(original_text, encoding="utf8")
    data_root = root / "mcp-data"
    env = dict(BASE_ENV)
    env.update({
        "HOME": str(home), "USERPROFILE": str(home), "APPDATA": str(home / "AppData"),
        "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_CACHE_HOME": str(home / ".cache"), "XDG_STATE_HOME": str(home / ".local/state"),
        "RESPECTED_DATA_DIR": str(data_root),
    })
    real_config = Path(os.environ["USERPROFILE"]) / ".config" / "opencode" / "opencode.json"
    real_before = real_config.read_bytes() if real_config.is_file() else None
    receipt = must_cli(data_root, ["integrations", "set", "opencode=on"], env=env, timeout=60)
    installed = json.loads(config.read_text(encoding="utf8"))
    expected_entry = installed["mcp"]["servers"]["respected-orchestrator"]
    if installed["mcp"]["servers"]["probe"] != original["mcp"]["servers"]["probe"]:
        raise AssertionError("foreign OpenCode MCP entry changed")
    if installed.get("theme") != original["theme"] or installed.get("keybinds") != original["keybinds"]:
        raise AssertionError("foreign OpenCode top-level settings changed")
    debug = run_process([OPENCODE, "debug", "config", "--standalone"], env=env, cwd=home, timeout=60)
    if debug.returncode != 0:
        raise RuntimeError(f"opencode debug config failed: {debug.stderr}")
    debug_payload = json.loads(debug.stdout)
    debug_document = next((item.get("info", {}) for item in debug_payload
                           if Path(item.get("path", "")).resolve() == config.resolve()), None)
    if debug_document is None or debug_document.get("mcp", {}).get("servers", {}).get(
            "respected-orchestrator") != expected_entry:
        raise AssertionError("OpenCode did not read back the installed MCP entry")
    rpp_request = {"rpp": "1", "op": "integrations.rollback",
                   "operation_id": receipt["operation_id"],
                   "payload": {"operation_id": receipt["operation_id"]}}
    rpp = run_process([sys.executable, "-m", "respected_orchestrator", "rpp"], payload=rpp_request, env=env, timeout=60)
    if rpp.returncode != 0:
        raise RuntimeError(f"integrations.rollback failed: {rpp.stdout}\n{rpp.stderr}")
    if config.read_text(encoding="utf8") != original_text:
        raise AssertionError("rollback did not restore the original OpenCode config bytes")
    if real_before is not None and real_config.read_bytes() != real_before:
        raise AssertionError("the real user OpenCode config changed")
    return {
        "receipt": receipt,
        "installed_entry": expected_entry,
        "probe_preserved": True,
        "foreign_settings_preserved": True,
        "debug_config": {"returncode": debug.returncode, "document": debug_document},
        "rollback": parse_output(rpp),
        "rollback_bytes_restored": True,
        "real_user_config_unchanged": True,
    }


def main():
    if not OPENCODE.is_file():
        raise RuntimeError(f"OpenCode not found: {OPENCODE}")
    root = Path(tempfile.mkdtemp(prefix="respected-adp01-e2e-")).resolve()
    project = setup_project(root)
    data_root = root / "data"
    version = run_process([OPENCODE, "--version"], timeout=30).stdout.strip()
    secrets = credential_secrets()
    records = {"version": version, "root": str(root), "model": MODEL, "scenarios": {}}
    try:
        records["scenarios"]["read"] = run_task(
            data_root, project, name="read", kind="read",
            task='Read owned.txt with your read tool. Do not modify any file. Reply with exactly this JSON object and no prose: {"status":"success","summary":"ADP01_READ_OK"}',
        )
        write_acceptance = [[sys.executable, "-c",
                             "from pathlib import Path; assert Path('owned.txt').read_text(encoding='utf8') == 'changed\\n'"]]
        write_record = run_task(
            data_root, project, name="write", kind="write",
            task='Use your file edit tool to replace the entire content of owned.txt with exactly the text changed followed by one newline. Do not modify any other file. Reply with exactly this JSON object and no prose: {"status":"success","summary":"ADP01_WRITE_OK"}',
            acceptance=write_acceptance,
        )
        write_record["project_before_apply"] = (project / "owned.txt").read_text(encoding="utf8")
        write_record["apply"] = must_cli(data_root, ["apply", write_record["run_id"]])
        write_record["project_after_apply"] = (project / "owned.txt").read_text(encoding="utf8")
        records["scenarios"]["write"] = write_record
        records["scenarios"]["invalid_model"] = run_task(
            data_root, project, name="invalid_model", kind="read", profile="invalid/model",
            task='Reply with exactly {"status":"success","summary":"SHOULD_NOT_RUN"} and nothing else.',
        )
        records["scenarios"]["timeout"] = run_task(
            # 8s: auth export/import completes first, while the real model answer consistently
            # takes longer; 3/5/8s probes all reached timed_out before any provider response.
            data_root, project, name="timeout", kind="read", timeout=8, wait_limit=120,
            task='Read owned.txt and reply with exactly {"status":"success","summary":"ADP01_TIMEOUT"} and nothing else.',
        )
        records["scenarios"]["acceptance_failure"] = run_task(
            data_root, project, name="acceptance_failure", kind="read",
            task='Read owned.txt and reply with exactly {"status":"success","summary":"ADP01_ACCEPTANCE"} and nothing else.',
            acceptance=[[sys.executable, "-c", "raise SystemExit(9)"]],
        )
        auth_home = root / "auth-empty-home"
        auth_home.mkdir()
        auth_env = dict(BASE_ENV)
        auth_env.update({
            "HOME": str(auth_home), "USERPROFILE": str(auth_home), "APPDATA": str(auth_home / "AppData"),
            "XDG_CONFIG_HOME": str(auth_home / ".config"), "XDG_DATA_HOME": str(auth_home / ".local/share"),
            "XDG_CACHE_HOME": str(auth_home / ".cache"), "XDG_STATE_HOME": str(auth_home / ".local/state"),
        })
        records["scenarios"]["auth_missing"] = run_task(
            data_root, project, name="auth_missing", kind="read", start_env=auth_env, wait_limit=120,
            task='Read owned.txt and reply with exactly {"status":"success","summary":"ADP01_AUTH"} and nothing else.',
        )
        records["mcp"] = mcp_roundtrip(root, secrets)
        statuses = {name: value["status"].get("status") for name, value in records["scenarios"].items()}
        if statuses != {"read": "completed", "write": "completed", "invalid_model": "failed",
                        "timeout": "timed_out", "acceptance_failure": "failed", "auth_missing": "failed"}:
            raise AssertionError(f"unexpected scenario statuses: {statuses}")
        if records["scenarios"]["write"]["project_after_apply"] != "changed\n":
            raise AssertionError("real write E2E did not apply the verified patch")
        scan_for_secrets([root, POC], records, secrets)
        records["secret_scan"] = "passed: no exported credential value in CLI evidence or run data"
        records["ok"] = True
    finally:
        for record in records.get("scenarios", {}).values():
            status = record.get("status", {}).get("status")
            if status not in TERMINAL:
                try:
                    cli(data_root, ["cancel", record["run_id"]], env=BASE_ENV, timeout=30)
                except Exception:
                    pass
    for name, value in records["scenarios"].items():
        write_evidence(name, value, secrets)
    write_evidence("mcp", records["mcp"], secrets)
    write_evidence("summary", records, secrets)
    print(json.dumps({"ok": True, "root": str(root), "version": version,
                      "statuses": {name: record["status"].get("status")
                                   for name, record in records["scenarios"].items()},
                      "mcp": {"entry": records["mcp"]["installed_entry"],
                              "rollback_bytes_restored": records["mcp"]["rollback_bytes_restored"]}},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
