"""Run one bounded live MAF-to-Codex coding demonstration."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from respected_orchestrator.context import EngineContext, safe_path
from respected_orchestrator.maf_workflow import run_maf_coding_task
from respected_orchestrator.processes import execute
from respected_orchestrator.runner import check_result, create_task, get_cli_command, inspect_task
from respected_orchestrator.vertical_slice import _events, _usage


ROOT = Path(__file__).resolve().parents[1]


def preflight_sandbox(home: Path | None = None) -> None:
    home = home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    marker = safe_path(home / ".sandbox" / "setup_marker.json")
    try:
        setup = json.loads(marker.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise RuntimeError("Existing Windows sandbox setup unavailable; no AI worker launched") from error
    if not isinstance(setup, dict) or not setup:
        raise RuntimeError("Existing Windows sandbox setup unavailable; no AI worker launched")


def preflight_auth(source: Path | None = None) -> None:
    import tomllib

    source = source or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    config = tomllib.loads(safe_path(source).read_text(encoding="utf-8-sig"))
    provider = config.get("model_providers", {}).get("evren1", {})
    auth = provider.get("auth", {})
    if not auth.get("command") or not isinstance(auth.get("args"), list) or not auth.get("cwd"):
        raise RuntimeError("External provider authentication configuration required")
    # Capture and discard the token; fail before any AI request if retrieval fails.
    preflight = execute([auth["command"], *auth["args"]], Path(auth["cwd"]), auth.get("timeout_ms", 8000) / 1000)
    if preflight.returncode or not preflight.stdout.strip():
        raise RuntimeError("External provider authentication failed; no AI worker launched")


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def create_fixture(root: Path) -> Path:
    repo = root / "project"
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Respected Fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "calculator.py").write_text(
        "def add(a, b):\n    ...\n",
        encoding="utf-8",
    )
    (repo / "test_calculator.py").write_text(
        "import unittest\n\nfrom calculator import add\n\n\nclass CalculatorTest(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n",
        encoding="utf-8",
    )
    (repo / "secret.txt").write_text("private\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture baseline")
    return repo


def main() -> int:
    codex = get_cli_command("codex")
    if codex is None:
        raise RuntimeError("Codex CLI unavailable")
    started = time.monotonic()
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    if sys.platform == "win32":
        preflight_sandbox()
        preflight_auth()
    root = Path(tempfile.mkdtemp(prefix=f"respected-maf-live-{stamp}-"))
    ctx = EngineContext(root / "data")
    repo = create_fixture(root)

    command = [
        *codex,
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "-p",
        "mimo",
        "-m",
        "mimo-v2.6-pro",
        "-c",
        'model_provider="evren1"',
        "{prompt}",
    ]
    request = {
        "project_root": str(repo),
        "task": (
            "Implement add(a, b) in calculator.py so it returns the sum. Keep the change minimal. "
            "Run Python checks with -B to avoid creating bytecode outside ownership. "
            "On Windows, use PowerShell with $ErrorActionPreference = 'Stop' and verify the assigned "
            "worktree before file operations; stop if entering it fails. "
            "Use the native apply_patch tool when available instead of a shell wrapper."
        ),
        "worker": "custom",
        "kind": "write",
        "ownership": ["calculator.py", "test_calculator.py"],
        "forbidden": ["secret.txt"],
        "command": command,
        "acceptance": [[sys.executable, "-B", "-m", "unittest", "test_calculator.py"]],
        "timeout_seconds": 180,
    }
    created = create_task(ctx, request)
    run_id = created["run_id"]

    maf_result = run_maf_coding_task(ctx=ctx, run_id=run_id)
    if maf_result.get("status") != "MASTER_APPROVED":
        print(json.dumps(maf_result, indent=2, default=str))
        return 1

    verified = check_result(ctx, run_id)
    inspected = inspect_task(ctx, run_id)
    stdout_path = ctx.run_dir(run_id) / "stdout.log"
    usage = _usage(_events(stdout_path.read_text(encoding="utf-8")))
    elapsed = round(time.monotonic() - started, 3)

    print(json.dumps({
        "status": "MASTER_APPROVED_AND_VERIFIED",
        "run_id": run_id,
        "changed_files": verified["changed_files"],
        "patch": verified["patch"],
        "workspace": inspected["request"]["project_root"],
        "model": "mimo-v2.6-pro",
        "provider": "evren1",
        "usage": usage,
        "elapsed_seconds": elapsed,
        "evidence_root": str(ctx.run_dir(run_id)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
