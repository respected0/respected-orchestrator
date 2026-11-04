"""Isolated, repeatable evaluation runner for the twenty baseline fixtures."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Iterable

from tests.evals.fixtures import Fixture, all_fixtures


COMMAND = [sys.executable, "-m", "unittest", "-q", "test_solution"]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DATA_ROOT_ENV = ("RESPECTED_DATA_DIR", "RESPECTED_ORCH_DATA", "RESPECTED_DATA_ROOT")


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "Respected Eval",
        "GIT_AUTHOR_EMAIL": "eval@example.invalid",
        "GIT_COMMITTER_NAME": "Respected Eval",
        "GIT_COMMITTER_EMAIL": "eval@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    })
    return env


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
        cwd=root, env=_git_env(), capture_output=True, text=True, timeout=30,
    )


def build_repository(fixture: Fixture, root: Path) -> str:
    for name, content in fixture.files().items():
        (root / name).write_text(content, encoding="utf-8", newline="\n")
    commands = [
        ["init", "-q", "-b", "main"],
        ["config", "user.name", "Respected Eval"],
        ["config", "user.email", "eval@example.invalid"],
        ["add", "-A"],
        ["commit", "-q", "-m", f"fixture:{fixture.id}"],
    ]
    for command in commands:
        done = _run_git(root, command)
        if done.returncode:
            raise RuntimeError(f"git {' '.join(command)} failed: {done.stderr.strip()}")
    done = _run_git(root, ["rev-parse", "HEAD"])
    if done.returncode:
        raise RuntimeError(f"git rev-parse failed: {done.stderr.strip()}")
    return done.stdout.strip()


def validate_fixture(fixture: Fixture) -> list[str]:
    errors = []
    if not isinstance(fixture.id, str) or not re.fullmatch(r"RSP-[0-9]{3}", fixture.id):
        errors.append("invalid_id")
    if not isinstance(fixture.title, str) or not fixture.title.strip():
        errors.append("missing_title")
    if not isinstance(fixture.source, str) or not fixture.source.strip():
        errors.append("missing_source")
    if not isinstance(fixture.fixed_source, str) or not fixture.fixed_source.strip():
        errors.append("missing_fixed_source")
    if not isinstance(fixture.test, str) or "unittest" not in fixture.test:
        errors.append("missing_acceptance_test")
    if fixture.source == fixture.fixed_source:
        errors.append("golden_equals_baseline")
    if "def " not in fixture.source or "def " not in fixture.fixed_source:
        errors.append("missing_function")
    if not isinstance(fixture.start_sha, str) or not SHA_RE.fullmatch(fixture.start_sha):
        errors.append("invalid_start_sha")
    return sorted(errors)


def _execute(command: list[str], cwd: Path, timeout: float) -> dict:
    started = time.perf_counter()
    try:
        done = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return {
            "returncode": done.returncode,
            "stdout": done.stdout.replace("\r\n", "\n"),
            "stderr": done.stderr.replace("\r\n", "\n"),
            "duration_seconds": round(time.perf_counter() - started, 4),
            "timeout": False,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "returncode": None,
            "stdout": (error.stdout or "").replace("\r\n", "\n") if isinstance(error.stdout, str) else "",
            "stderr": (error.stderr or "").replace("\r\n", "\n") if isinstance(error.stderr, str) else "",
            "duration_seconds": round(time.perf_counter() - started, 4),
            "timeout": True,
        }


def _hash(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _metadata() -> dict:
    git = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10)
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "git": git.stdout.strip() if git.returncode == 0 else "bilinmiyor",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _is_product_data(path: Path) -> bool:
    resolved = path.resolve()
    roots = [Path(value) for value in (os.environ.get(name) for name in DATA_ROOT_ENV) if value]
    for root in roots:
        try:
            if resolved.is_relative_to(root.resolve()):
                return True
        except OSError:
            continue
    return False


def evaluate_fixture(fixture: Fixture, repeat: int = 1, timeout: float = 20.0) -> dict:
    errors = validate_fixture(fixture)
    if errors:
        return {"task_id": fixture.id, "status": "rejected", "errors": errors}
    runs = []
    for index in range(repeat):
        root = Path(tempfile.mkdtemp(prefix=f"orch-eval-{fixture.id.lower()}-"))
        try:
            actual_sha = build_repository(fixture, root)
            baseline = _execute(COMMAND, root, timeout)
            (root / "solution.py").write_text(fixture.fixed_source, encoding="utf-8", newline="\n")
            golden = _execute(COMMAND, root, timeout)
            result = {
                "run": index + 1,
                "start_sha": actual_sha,
                "expected_start_sha": fixture.start_sha,
                "start_sha_matches": actual_sha == fixture.start_sha,
                "baseline": baseline,
                "golden": golden,
                "baseline_status": (
                    "timeout" if baseline["timeout"] else
                    "expected_failure" if baseline["returncode"] != 0 else "unexpected_pass"
                ),
                "golden_status": (
                    "timeout" if golden["timeout"] else
                    "expected_pass" if golden["returncode"] == 0 else "unexpected_failure"
                ),
                "cost": "bilinmiyor",
            }
            result["result_hash"] = _hash({
                "start_sha": actual_sha,
                "baseline": baseline["stdout"] + baseline["stderr"],
                "golden": golden["stdout"] + golden["stderr"],
            })
            runs.append(result)
        finally:
            shutil.rmtree(root, ignore_errors=True)
    passed = all(
        run["start_sha_matches"] and run["baseline_status"] == "expected_failure"
        and run["golden_status"] == "expected_pass" for run in runs
    )
    return {"task_id": fixture.id, "status": "passed" if passed else "failed", "runs": runs}


def run_all(repeat: int = 3, timeout: float = 20.0, fixtures: Iterable[Fixture] | None = None) -> dict:
    selected = list(fixtures) if fixtures is not None else list(all_fixtures())
    results = [evaluate_fixture(fixture, repeat, timeout) for fixture in selected]
    return {
        "schema": "respected.eval.v1",
        "metadata": _metadata(),
        "repeat": repeat,
        "tasks": results,
        "summary": {
            "total": len(results),
            "passed": sum(result["status"] == "passed" for result in results),
            "failed": sum(result["status"] == "failed" for result in results),
            "rejected": sum(result["status"] == "rejected" for result in results),
        },
    }


def write_report(report: dict, destination: Path) -> None:
    if _is_product_data(destination):
        raise ValueError("Evaluation report must not be written under product data root")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--out", type=Path, default=Path("docs/evidence/poc/eval01_results.json"))
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    report = run_all(args.repeat, args.timeout)
    write_report(report, args.out)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["failed"] == 0 and report["summary"]["rejected"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())