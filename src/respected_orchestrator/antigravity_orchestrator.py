#!/usr/bin/env python3
"""Guarded launcher for isolated Antigravity repository workers."""

from __future__ import annotations

from . import winproc
from .context import EngineContext, validate_project, path_within_root
from .processes import execute, ProcessStopped
from uuid import uuid4

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Mapping, Sequence


class RunStatus(str, Enum):
    COMPLETE = "COMPLETE"
    LIMIT_EXHAUSTED = "LIMIT_EXHAUSTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TIMEOUT = "TIMEOUT"
    WORKER_FAILED = "WORKER_FAILED"
    SCOPE_VIOLATION = "SCOPE_VIOLATION"
    TEST_FAILED = "TEST_FAILED"
    INTEGRATION_CONFLICT = "INTEGRATION_CONFLICT"


class TaskKind(str, Enum):
    READ = "read"
    WRITE = "write"


class WorkerUnavailableError(RuntimeError):
    """Raised when no configured Antigravity executable can be resolved."""


class WriterLockError(RuntimeError):
    """Raised when an existing writer lock requires operator attention."""


class LaneError(RuntimeError):
    """Raised when a worktree lane cannot be created or safely prepared."""


@dataclass(frozen=True)
class Policy:
    schema_version: int
    worker_executable_candidates: tuple[str, ...]
    workspace_root: str
    max_active_write_workers: int
    read_timeout_seconds: int
    write_timeout_seconds: int
    dangerously_skip_permissions: bool


@dataclass(frozen=True)
class RunRequest:
    run_id: str
    slug: str
    kind: TaskKind
    objective: str
    known_context: str
    ownership: tuple[str, ...]
    forbidden: tuple[str, ...]
    acceptance: tuple[tuple[str, ...], ...]
    include_untracked: tuple[str, ...]
    context_paths: tuple[str, ...] = ()  # read-only inputs outside ownership (earlier lanes' applied output)


@dataclass(frozen=True)
class RunPaths:
    repo_root: Path
    workspace_root: Path
    state_root: Path
    run_root: Path


@dataclass
class Lane:
    repo_root: Path
    worktree: Path
    branch: str
    run_root: Path
    baseline_commit: str | None = None


@dataclass(frozen=True)
class BaselineManifest:
    paths: tuple[str, ...]
    hashes: Mapping[str, str | None]


@dataclass(frozen=True)
class GitStatus:
    porcelain: str


@dataclass(frozen=True)
class WorkerResult:
    status: RunStatus
    returncode: int | None
    timed_out: bool
    payload: Mapping[str, object] | None
    stdout_path: Path
    stderr_path: Path


@dataclass(frozen=True)
class ChangeSet:
    paths: tuple[str, ...]
    statuses: Mapping[str, str]
    unsafe_paths: tuple[str, ...]
    generated: tuple[str, ...] = ()  # build/test output that is neither the worker's change nor part of any patch


@dataclass(frozen=True)
class ScopeResult:
    allowed: bool
    violations: tuple[str, ...]


@dataclass(frozen=True)
class CheckResult:
    command: tuple[str, ...]
    returncode: int
    timed_out: bool
    duration_seconds: float
    stdout_path: Path
    stderr_path: Path


@dataclass(frozen=True)
class PatchResult:
    path: Path
    sha256: str


@dataclass
class WriterLock:
    path: Path
    run_id: str

    @classmethod
    def acquire(
        cls,
        state_root: Path,
        run_id: str,
        task_kind: str,
        workspace: Path,
    ) -> "WriterLock":
        state_root.mkdir(parents=True, exist_ok=True)
        path = state_root / ".write-worker.lock.json"
        if path.exists():
            metadata = json.loads(path.read_text(encoding="utf-8"))
            pid = int(metadata.get("pid", -1))
            if _pid_is_alive(pid):
                raise WriterLockError(f"active writer lock for run {metadata.get('run_id', 'unknown')}: {path}")
            path.unlink(missing_ok=True)  # owner died without releasing (kill/reboot): reclaim (audit P1 #10); shortcut: pid reuse can keep a dead lock alive

        metadata = {
            "run_id": run_id,
            "pid": os.getpid(),
            "task_kind": task_kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workspace": str(workspace),
        }
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(metadata, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except FileExistsError as error:
            raise WriterLockError(f"active writer lock: {path}") from error
        return cls(path=path, run_id=run_id)

    def release(self) -> None:
        if not self.path.exists():
            return
        metadata = json.loads(self.path.read_text(encoding="utf-8"))
        if metadata.get("run_id") != self.run_id:
            raise WriterLockError(f"writer lock ownership changed: {self.path}")
        self.path.unlink()


def load_policy(path: Path) -> Policy:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported orchestration policy schema")
    if type(data.get('dangerously_skip_permissions')) is not bool:
        raise ValueError('Permission bypass policy must be a boolean')
    if data['dangerously_skip_permissions']:
        raise ValueError('Permission bypass is disabled in the independent engine')
    return Policy(
        schema_version=1,
        worker_executable_candidates=tuple(data["worker_executable_candidates"]),
        workspace_root=str(data["workspace_root"]),
        max_active_write_workers=int(data["max_active_write_workers"]),
        read_timeout_seconds=int(data["read_timeout_seconds"]),
        write_timeout_seconds=int(data["write_timeout_seconds"]),
        dangerously_skip_permissions=bool(data["dangerously_skip_permissions"]),
    )


def resolve_agy(policy: Policy, environ: Mapping[str, str]) -> Path:
    search_path = environ.get("PATH", "")
    for candidate in policy.worker_executable_candidates:
        expanded = _expand_environment(candidate, environ)
        has_separator = "/" in expanded or "\\" in expanded
        if has_separator:
            path = Path(expanded)
            try:
                if path.is_file():
                    return path.resolve()
            except OSError:
                continue
        else:
            found = shutil.which(expanded, path=search_path)
            if found:
                return Path(found).resolve()
    raise WorkerUnavailableError("Antigravity executable not found")


def normalize_repo_path(repo_root: Path, value: str) -> str:
    root = repo_root.resolve()
    raw = Path(value)
    target = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        relative = target.relative_to(root)
    except ValueError as error:
        raise ValueError(f"path escapes repository: {value}") from error
    if relative == Path("."):
        raise ValueError("repository root is not a bounded ownership path")
    return relative.as_posix()


def git_status(repo_root: Path) -> GitStatus:
    return GitStatus(_git(repo_root, "status", "--porcelain=v1").stdout)


def create_lane(request: RunRequest, paths: RunPaths) -> Lane:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", request.slug):
        raise LaneError(f"invalid task slug: {request.slug}")
    paths.workspace_root.mkdir(parents=True, exist_ok=True)
    paths.run_root.mkdir(parents=True, exist_ok=True)
    worktree = (paths.workspace_root / request.slug).resolve()
    branch = f"orchestrator/{request.slug}"
    if worktree.exists():
        raise LaneError(f"lane already exists: {worktree}")
    branch_exists = winproc.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=paths.repo_root,
        check=False,
    ).returncode == 0
    if branch_exists:
        raise LaneError(f"lane branch already exists: {branch}")
    result = winproc.run(
        ["git", "worktree", "add", "-b", branch, str(worktree), "HEAD"],
        cwd=paths.repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise LaneError(result.stderr.strip() or result.stdout.strip())
    return Lane(
        repo_root=paths.repo_root.resolve(),
        worktree=worktree,
        branch=branch,
        run_root=paths.run_root.resolve(),
    )


def overlay_dirty_inputs(
    lane: Lane,
    ownership: Sequence[str],
    include_untracked: Sequence[str],
    context_paths: Sequence[str] = (),
) -> BaselineManifest:
    owned = tuple(normalize_repo_path(lane.repo_root, item) for item in ownership)
    selected: list[str] = []

    tracked_output = _git(
        lane.repo_root, "diff", "--name-only", "-z", "HEAD", "--"
    ).stdout
    for raw in filter(None, tracked_output.split("\0")):
        normalized = normalize_repo_path(lane.repo_root, raw)
        if _path_is_owned(normalized, owned):
            selected.append(normalized)

    for raw in include_untracked:
        normalized = normalize_repo_path(lane.repo_root, raw)
        ignored = winproc.run(
            ["git", "check-ignore", "--quiet", "--", normalized],
            cwd=lane.repo_root,
            check=False,
        ).returncode == 0
        if ignored:
            raise LaneError(f"ignored input cannot enter a lane: {normalized}")
        if not _path_is_owned(normalized, owned):
            raise LaneError(f"untracked input is outside ownership: {normalized}")
        source = lane.repo_root / normalized
        tracked = winproc.run(
            ["git", "ls-files", "--error-unmatch", "--", normalized],
            cwd=lane.repo_root,
            capture_output=True,
            check=False,
        ).returncode == 0
        if tracked or not source.is_file():
            raise LaneError(f"selected input is not an untracked file: {normalized}")
        selected.append(normalized)

    for raw in context_paths:  # same copy as above, but not part of the lane's ownership: changing one is a scope violation
        normalized = normalize_repo_path(lane.repo_root, raw)
        if (lane.repo_root / normalized).is_file() and winproc.run(
                ["git", "check-ignore", "--quiet", "--", normalized], cwd=lane.repo_root, check=False).returncode != 0:
            selected.append(normalized)

    hashes: dict[str, str | None] = {}
    for relative in sorted(set(selected)):
        source = lane.repo_root / relative
        destination = lane.worktree / relative
        if source.is_symlink():
            raise LaneError(f"symlink input is not supported: {relative}")
        if source.exists():
            if not source.is_file():
                raise LaneError(f"lane input must be a file: {relative}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
        else:
            if destination.exists():
                destination.unlink()
            hashes[relative] = None
    return BaselineManifest(paths=tuple(sorted(hashes)), hashes=hashes)


def commit_lane_baseline(lane: Lane, manifest: BaselineManifest) -> str:
    _git(lane.worktree, "add", "-A")
    if _git(lane.worktree, "status", "--porcelain=v1").stdout.strip():
        _git(lane.worktree, "-c", "user.name=Respected Orchestrator", "-c", "user.email=orchestrator@example.invalid", "commit", "-m", "chore: snapshot orchestration baseline")
    commit = _git(lane.worktree, "rev-parse", "HEAD").stdout.strip()
    lane.baseline_commit = commit
    lane.run_root.mkdir(parents=True, exist_ok=True)
    payload = {"paths": list(manifest.paths), "hashes": dict(manifest.hashes), "commit": commit}
    (lane.run_root / "baseline.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return commit


DEFAULT_READ_TEMPLATE = """# Antigravity Read Worker Brief

## ROLE
You are an isolated repository investigation worker.

## OBJECTIVE
{{OBJECTIVE}}

## KNOWN CONTEXT
{{KNOWN_CONTEXT}}

## WORKSPACE
READ-ONLY TASK.
You are already inside the assigned worktree: `{{WORKSPACE}}`.
Operate only inside the assigned worktree.
Do not modify repository files.

## OWNERSHIP
Read only the minimum repository scope needed for the objective:
{{OWNERSHIP}}

## FORBIDDEN
{{FORBIDDEN}}

## RULES
- Do not run destructive commands.
- Do not run git reset, git clean, git restore, or git stash.
- Do not rewrite Git history.
- Do not access sibling worktrees or parent project directories.
- Keep raw logs on disk and return a concise conclusion.

## ACCEPTANCE
{{ACCEPTANCE}}

## RETURN
Return JSON with: `status`, `root_cause`, `files_examined`, `checks`, and `remaining_risks`.
"""

DEFAULT_WRITE_TEMPLATE = """# Antigravity Write Worker Brief

## ROLE
You are an isolated implementation worker.

## OBJECTIVE
{{OBJECTIVE}}

## KNOWN CONTEXT
{{KNOWN_CONTEXT}}

## WORKSPACE
You are already inside the assigned worktree: `{{WORKSPACE}}`.
Operate only inside the assigned worktree.

## OWNERSHIP
You may modify only:
{{OWNERSHIP}}

## FORBIDDEN
{{FORBIDDEN}}

## RULES
- Investigate the root cause before changing code.
- Make the smallest robust change.
- Do not perform unrelated cleanup or refactoring.
- Do not run git reset, git clean, git restore, or git stash.
- Do not rewrite Git history.
- Do not access sibling worktrees or parent project directories.

## ACCEPTANCE
{{ACCEPTANCE}}

## RETURN
Return JSON with: `status`, `root_cause`, `files_changed`, `implementation`, `checks`, and
`remaining_risks`.
"""


def render_brief(request: RunRequest, lane: Lane) -> str:
    repo_root = lane.repo_root
    template_name = "read-worker.md" if request.kind is TaskKind.READ else "write-worker.md"
    template_file = repo_root / ".orchestration" / "templates" / template_name
    if template_file.is_file():
        template = template_file.read_text(encoding="utf-8")
    else:
        template = DEFAULT_READ_TEMPLATE if request.kind is TaskKind.READ else DEFAULT_WRITE_TEMPLATE

    replacements = {
        "OBJECTIVE": request.objective,
        "KNOWN_CONTEXT": request.known_context,
        "WORKSPACE": str(lane.worktree),
        "OWNERSHIP": _markdown_list(request.ownership),
        "FORBIDDEN": _markdown_list(request.forbidden),
        "ACCEPTANCE": _markdown_list(
            tuple(json.dumps(list(command), ensure_ascii=False) for command in request.acceptance)
        ),
    }
    for name, value in replacements.items():
        template = template.replace("{{" + name + "}}", value)
    return template + (
        "\n\n## MACHINE-READABLE STATUS CONTRACT\n"
        'Return a JSON object with "status": "success" only when the task '
        'completed successfully; otherwise use "status": "failed". '
        "Never use task-specific markers such as WORKER_OK as the status value. "
        "Include the other requested result fields. "
        "Edit files with plain shell commands or direct file writes, never the apply_patch tool "
        "(it fails on Windows); if an edit fails twice, report \"status\": \"failed\". "
        "After the edit and acceptance checks pass, immediately emit the final JSON and stop; "
        "do not start background processes."
    )


def run_worker(
    request: RunRequest,
    lane: Lane,
    agy_path: Path,
    timeout_seconds: float | None = None,
    *, dangerously_skip_permissions: bool = False,
) -> WorkerResult:
    if dangerously_skip_permissions:
        raise ValueError('Permission bypass is disabled in the independent engine')
    lane.run_root.mkdir(parents=True, exist_ok=True)
    brief = render_brief(request, lane)
    brief_path = lane.run_root / "brief.md"
    brief_path.write_text(brief, encoding="utf-8")
    if timeout_seconds is None:
        timeout_seconds = 900 if request.kind is TaskKind.READ else 1800
    print_timeout = f"{max(1, (int(timeout_seconds) + 59) // 60)}m"
    command = [
        str(agy_path),
        "-p",
        f"Read and follow the complete worker brief at: {brief_path}",
        "--output-format",
        "json",
        "--print-timeout",
        print_timeout,
    ]
    if dangerously_skip_permissions:
        command.append('--dangerously-skip-permissions')
    timed_out = False
    returncode: int | None
    stdout = ""
    stderr = ""
    process_path = lane.run_root / "process.json"
    started_at = datetime.now(timezone.utc).isoformat()
    process_metadata: dict[str, object] = {
        "run_id": request.run_id,
        "task_kind": request.kind.value,
        "pid": None,
        "state": "RUNNING",
        "started_at": started_at,
        "executable": str(agy_path),
        "cwd": str(lane.worktree),
        "timeout_seconds": timeout_seconds,
    }
    process_path.write_text(
        json.dumps(process_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    def record_process(pid):
        process_metadata['pid'] = pid
        process_path.write_text(json.dumps(process_metadata, indent=2), encoding='utf8')
    try:
        process = execute(command, lane.worktree, timeout_seconds, on_started=record_process)
        stdout, stderr = process.stdout, process.stderr
        returncode = process.returncode
    except ProcessStopped as error:
        timed_out = True
        returncode = 124
        stdout, stderr = error.stdout, error.stderr

    process_metadata.update(
        {
            "state": "TIMEOUT" if timed_out else "FINISHED",
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "returncode": returncode,
        }
    )
    process_path.write_text(
        json.dumps(process_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    status = classify_worker_exit(returncode or 0, stdout, stderr, timed_out)
    payload = _parse_json_object(stdout)
    if status is RunStatus.COMPLETE and payload is None:
        status = RunStatus.WORKER_FAILED
    if status is RunStatus.COMPLETE and payload is not None and "status" in payload:
        payload_status = str(payload["status"]).casefold()
        if payload_status not in {"success", "complete", "completed", "ok"}:
            status = RunStatus.WORKER_FAILED

    stdout_path = lane.run_root / "stdout.log"
    stderr_path = lane.run_root / "stderr.log"
    stdout_path.write_text(_redact(stdout), encoding="utf-8")
    stderr_path.write_text(_redact(stderr), encoding="utf-8")
    result = WorkerResult(
        status=status,
        returncode=returncode,
        timed_out=timed_out,
        payload=payload,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    (lane.run_root / "worker-result.json").write_text(
        json.dumps(
            {
                "status": result.status.value,
                "returncode": result.returncode,
                "timed_out": result.timed_out,
                "payload": result.payload,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def classify_worker_exit(
    returncode: int,
    stdout: str,
    stderr: str,
    timed_out: bool,
) -> RunStatus:
    if timed_out:
        return RunStatus.TIMEOUT
    payload = _parse_json_object(stdout)
    if payload is not None:
        status = str(payload.get("status", "")).casefold()
        if returncode == 0 and status in {"success", "complete", "completed", "ok"} and not payload.get("error"):
            return RunStatus.COMPLETE
        # Classify provider errors, never arbitrary response/risk prose.
        combined = (str(payload.get("error", "")) + "\n" + stderr).casefold()
    else:
        combined = f"{stdout}\n{stderr}".casefold()
    if any(marker in combined for marker in ("quota", "limit exhausted", "rate limit")):
        return RunStatus.LIMIT_EXHAUSTED
    if any(
        marker in combined
        for marker in ("authentication required", "unauthenticated", "login required")
    ):
        return RunStatus.AUTH_REQUIRED
    if returncode != 0 or (payload is not None and (
        payload.get("error") or ("status" in payload and status not in {"success", "complete", "completed", "ok"})
    )):
        return RunStatus.WORKER_FAILED
    return RunStatus.COMPLETE


# Output that tests and builds leave behind. Only UNTRACKED or ignored paths are ever candidates: a tracked file
# (even one called build/x.py) is real source and keeps being a real change.
_ALWAYS_GENERATED_PARTS = frozenset({"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis", ".tox", ".nox",
                                     ".ipynb_checkpoints"})
_GENERATED_SUFFIXES = (".pyc", ".pyo")
# Directories that are build output when the repository ignores the path or tracks nothing inside them (a tracked, unignored
# build/ stays source: fail closed).
_BUILD_PARTS = frozenset({"build", "dist", "target", "node_modules", ".venv", "venv", ".eggs", "htmlcov", ".next", ".turbo"})


def _generated_prefix(path: str) -> tuple[str, bool] | None:
    """(directory prefix, always) when `path` lies in generated-looking output, else None."""
    parts = path.split("/")
    if path.endswith(_GENERATED_SUFFIXES):
        return path, True
    for index, part in enumerate(parts[:-1] if len(parts) > 1 else []):
        if part in _ALWAYS_GENERATED_PARTS or part.endswith(".egg-info"):
            return "/".join(parts[: index + 1]), True
        if part in _BUILD_PARTS or (part == "src-tauri" and parts[index + 1 : index + 2] == ["gen"]):
            return "/".join(parts[: index + 2]) if part == "src-tauri" else "/".join(parts[: index + 1]), False
    return None


def _names_generated_location(owned: str) -> bool:
    """An ownership entry that itself points into build-looking output (e.g. `dist/notes.md`) authorises that location."""
    return _generated_prefix(owned.rstrip("/") + "/x") is not None


def collect_worker_changes(lane: Lane, ownership: Sequence[str] = ()) -> ChangeSet:
    if not lane.baseline_commit:
        raise LaneError("lane baseline commit is missing")
    tracked = _git_path_list(
        lane.worktree,
        "diff",
        "--name-only",
        "-z",
        lane.baseline_commit,
        "--",
    )
    untracked = _git_path_list(
        lane.worktree,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
    )
    ignored = _git_path_list(lane.worktree, "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--")
    statuses: dict[str, str] = {}
    unsafe: list[str] = []
    for path in tracked:
        target = lane.worktree / path
        statuses[path] = "D" if not target.exists() else "M"
    authorised = tuple(item.replace("\\", "/").rstrip("/") for item in ownership if _names_generated_location(item.replace("\\", "/")))
    tracked_prefix: dict[str, bool] = {}
    ignored_paths = set(ignored)
    generated: list[str] = []
    for path in sorted({*untracked, *ignored}):
        target = lane.worktree / path
        if not path_within_root(target, lane.worktree):
            unsafe.append(path)  # a symlink out of the worktree is never "generated": fail closed
            continue
        found = _generated_prefix(path)
        if found is not None and not _path_is_owned(path, authorised):
            prefix, always = found
            if not always and prefix not in tracked_prefix:
                tracked_prefix[prefix] = bool(_git_path_list(lane.worktree, "ls-files", "-z", "--", prefix))
            # Build-looking directory: output when the repository itself ignores the path, or tracks nothing inside it.
            if always or path in ignored_paths or not tracked_prefix[prefix]:
                generated.append(path)
                continue
        statuses[path] = "?"
    for path in statuses:
        if not path_within_root(lane.worktree / path, lane.worktree):
            unsafe.append(path)
    return ChangeSet(
        paths=tuple(sorted(statuses)),
        statuses=statuses,
        unsafe_paths=tuple(sorted(set(unsafe))),
        generated=tuple(generated),
    )


def validate_change_scope(
    changes: ChangeSet,
    ownership: Sequence[str],
    forbidden: Sequence[str],
) -> ScopeResult:
    owned = tuple(item.replace("\\", "/").rstrip("/") for item in ownership)
    denied = tuple(item.replace("\\", "/").rstrip("/") for item in forbidden)
    violations = {
        path
        for path in changes.paths
        if not _path_is_owned(path, owned) or _path_is_owned(path, denied)
    }
    violations.update(changes.unsafe_paths)
    ordered = tuple(sorted(violations))
    return ScopeResult(allowed=not ordered, violations=ordered)


def run_acceptance(
    lane: Lane,
    commands: Sequence[Sequence[str]],
    timeout_seconds: float | None = None,
) -> tuple[CheckResult, ...]:
    checks_root = lane.run_root / "checks"
    checks_root.mkdir(parents=True, exist_ok=True)
    results: list[CheckResult] = []
    for index, raw_command in enumerate(commands, start=1):
        command = tuple(str(part) for part in raw_command)
        if not command:
            raise ValueError("acceptance command cannot be empty")
        started = time.monotonic()
        timed_out = False
        try:
            completed = execute(command, lane.worktree, timeout_seconds if timeout_seconds is not None else 1800)
            returncode = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except ProcessStopped as error:
            timed_out = True
            returncode = 124
            stdout = _coerce_output(error.stdout)
            stderr = _coerce_output(error.stderr)
            stderr += f"\nAcceptance command timed out after {timeout_seconds} seconds.\n"
        duration = time.monotonic() - started
        stdout_path = checks_root / f"{index:02d}-stdout.log"
        stderr_path = checks_root / f"{index:02d}-stderr.log"
        stdout_path.write_text(_redact(stdout), encoding="utf-8")
        stderr_path.write_text(_redact(stderr), encoding="utf-8")
        result = CheckResult(
            command=command,
            returncode=returncode,
            timed_out=timed_out,
            duration_seconds=duration,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )
        results.append(result)
        if returncode != 0:
            break
    (lane.run_root / "checks.json").write_text(
        json.dumps(
            [
                {
                    "command": list(item.command),
                    "returncode": item.returncode,
                    "timed_out": item.timed_out,
                    "duration_seconds": item.duration_seconds,
                    "stdout_path": str(item.stdout_path),
                    "stderr_path": str(item.stderr_path),
                }
                for item in results
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return tuple(results)


def export_worker_patch(lane: Lane, output: Path, ownership: Sequence[str] = ()) -> PatchResult:
    if not lane.baseline_commit:
        raise LaneError("lane baseline commit is missing")
    changes = collect_worker_changes(lane, ownership)
    untracked = [path for path, status_code in changes.statuses.items() if status_code == "?"]
    # A path the ownership itself names inside build-looking output (e.g. dist/notes.md) may be git-ignored: the lane was
    # explicitly authorised for it, so it is added with -f. Any other ignored file (a stray .env...) still makes the
    # export fail: nothing ignored enters a patch unless it was named.
    named = tuple(item.replace("\\", "/").rstrip("/") for item in ownership if _names_generated_location(item.replace("\\", "/")))
    forced = [path for path in untracked if _path_is_owned(path, named)]
    plain = [path for path in untracked if path not in forced]
    if plain:
        _git(lane.worktree, "add", "-N", "--", *plain)
    if forced:
        _git(lane.worktree, "add", "-N", "-f", "--", *forced)
    completed = winproc.run(
        ["git", "diff", "--binary", "--full-index", lane.baseline_commit, "--"],
        cwd=lane.worktree,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LaneError(completed.stderr.decode("utf-8", errors="replace").strip())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(completed.stdout)
    return PatchResult(path=output, sha256=hashlib.sha256(completed.stdout).hexdigest())


def check_patch_against_master(repo_root: Path, patch: Path) -> RunStatus:
    completed = winproc.run(
        ["git", "apply", "--check", "--binary", "--whitespace=nowarn", str(patch)],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    return RunStatus.COMPLETE if completed.returncode == 0 else RunStatus.INTEGRATION_CONFLICT


def main(argv: Sequence[str] | None = None, *, ctx: EngineContext | None = None, project_root: Path | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if ctx is None:
        from .context import default_data_root
        ctx = EngineContext(default_data_root())
    args.ctx = ctx
    args.state_root = ctx.paths.state_dir / "orchestration"
    if hasattr(args, "repo_root"):
        if project_root is not None and args.repo_root is not None and args.repo_root.resolve() != project_root.resolve():
            raise ValueError("--repo-root must match the explicit code project")
        selected = project_root or args.repo_root
        if selected is None:
            raise ValueError("An explicit code project is required")
        args.repo_root = validate_project(ctx, selected)
        if project_root is not None and selected.resolve() != project_root.resolve():
            raise ValueError("--repo-root must match the explicit code project")
    if getattr(args, "run_id", None) and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.run_id):
        raise ValueError("Invalid orchestration run identity")
    if args.command == "doctor":
        return _doctor(args)
    if args.command in {"run-read", "run-write"}:
        if args.background:
            return _start_background(args, list(argv) if argv is not None else sys.argv[1:])
        try:
            return _run_cli(args)
        except Exception as error:
            if args.run_id:
                policy = load_policy(args.policy or Path(__file__).parent / "resources/policy.json")
                root = args.state_root / args.run_id
                _write_verification(root, RunStatus.WORKER_FAILED, error=str(error))
            raise
    if args.command == "inspect":
        terminal = args.run_root / "verification.json"
        if terminal.exists():
            payload = json.loads(terminal.read_text(encoding="utf-8"))
        else:
            supervisor = args.run_root / "supervisor.json"
            metadata = json.loads(supervisor.read_text(encoding="utf-8")) if supervisor.exists() else {}
            alive = _pid_is_alive(int(metadata.get("pid", -1)))
            payload = {"status": "RUNNING" if alive else "WORKER_FAILED", "supervisor": metadata}
        _print_json(payload)
        return 0
    if args.command == "check-patch":
        status = check_patch_against_master(args.repo_root.resolve(), args.patch.resolve())
        print(status.value)
        return 0 if status is RunStatus.COMPLETE else 21
    if args.command == "apply-patch":
        raise ValueError("Raw patch application is disabled; inspect and verify the owned task result in Hub")
    parser.error("unsupported command")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor")
    _add_repo_policy_arguments(doctor)

    for command_name, kind in (("run-read", TaskKind.READ), ("run-write", TaskKind.WRITE)):
        command = subparsers.add_parser(command_name)
        _add_repo_policy_arguments(command)
        command.set_defaults(task_kind=kind)
        command.add_argument("--run-id")
        command.add_argument("--background", action="store_true", help="Detach from the calling tool session; inspect the returned run_root.")
        command.add_argument("--timeout-seconds", type=int, help="Bound worker and acceptance duration.")
        command.add_argument("--slug", required=True)
        command.add_argument("--objective", required=True)
        command.add_argument("--known-context", default="No additional context.")
        command.add_argument("--owner", action="append", required=True)
        command.add_argument("--forbid", action="append", default=[])
        command.add_argument("--accept", action="append", type=_parse_command, default=[])
        command.add_argument("--include-untracked", action="append", default=[])

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--run-root", type=Path, required=True)
    for command_name in ("check-patch", "apply-patch"):
        command = subparsers.add_parser(command_name)
        command.add_argument("--repo-root", type=Path, default=None)
        command.add_argument("--patch", type=Path, required=True)
    return parser


def _add_repo_policy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--policy", type=Path)


def _parse_command(value: str) -> tuple[str, ...]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError("acceptance command must be a JSON array") from error
    if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) for item in parsed):
        raise argparse.ArgumentTypeError("acceptance command must be a non-empty JSON string array")
    return tuple(parsed)


def _doctor(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    policy_path = (args.policy or Path(__file__).parent / "resources/policy.json").resolve()
    policy = load_policy(policy_path)
    workspace_root = _workspace_root(repo_root, policy) if policy.workspace_root else args.ctx.workspace_root
    for forbidden in (args.ctx.paths.app_root, repo_root):
        if workspace_root.is_relative_to(forbidden) or forbidden.is_relative_to(workspace_root):
            raise ValueError("Worker workspace must be separate from program, data and vault")
    payload: dict[str, object] = {
        "status": RunStatus.COMPLETE.value,
        "repo_root": str(repo_root),
        "policy": str(policy_path),
        "workspace_root": str(workspace_root),
        "git": shutil.which("git"),
    }
    try:
        payload["agy"] = str(resolve_agy(policy, os.environ))
    except WorkerUnavailableError as error:
        payload["status"] = RunStatus.WORKER_FAILED.value
        payload["agy_error"] = str(error)
    _print_json(payload)
    return 0 if payload["status"] == RunStatus.COMPLETE.value else 20


def _run_cli(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    policy_path = (args.policy or Path(__file__).parent / "resources/policy.json").resolve()
    policy = load_policy(policy_path)
    workspace_root = _workspace_root(repo_root, policy) if policy.workspace_root else args.ctx.workspace_root
    for forbidden in (args.ctx.paths.app_root, repo_root):
        if workspace_root.is_relative_to(forbidden) or forbidden.is_relative_to(workspace_root):
            raise ValueError("Worker workspace must be separate from program, data and vault")
    run_id = args.run_id or _new_run_id(args.slug)
    paths = RunPaths(
        repo_root=repo_root,
        workspace_root=workspace_root,
        state_root=args.state_root,
        run_root=args.state_root / run_id,
    )
    request = RunRequest(
        run_id=run_id,
        slug=args.slug,
        kind=args.task_kind,
        objective=args.objective,
        known_context=args.known_context,
        ownership=tuple(normalize_repo_path(repo_root, item) for item in args.owner),
        forbidden=tuple(normalize_repo_path(repo_root, item) for item in args.forbid),
        acceptance=tuple(args.accept),
        include_untracked=tuple(args.include_untracked),
    )
    lock: WriterLock | None = None
    if request.kind is TaskKind.WRITE:
        lock = WriterLock.acquire(paths.state_root, run_id, request.kind.value, workspace_root / request.slug)
    try:
        lane = create_lane(request, paths)
        manifest = overlay_dirty_inputs(lane, request.ownership, request.include_untracked)
        commit_lane_baseline(lane, manifest)
        try:
            agy_path = resolve_agy(policy, os.environ)
        except WorkerUnavailableError as error:
            _write_verification(lane.run_root, RunStatus.WORKER_FAILED, error=str(error))
            return 20
        worker_timeout = (
            policy.read_timeout_seconds
            if request.kind is TaskKind.READ
            else policy.write_timeout_seconds
        )
        if args.timeout_seconds is not None:
            if args.timeout_seconds <= 0:
                raise ValueError("timeout must be positive")
            worker_timeout = min(worker_timeout, args.timeout_seconds)
        worker = run_worker(request, lane, agy_path, timeout_seconds=worker_timeout,
                            dangerously_skip_permissions=policy.dangerously_skip_permissions)
        if worker.status is not RunStatus.COMPLETE:
            _write_verification(lane.run_root, worker.status)
            return 20

        changes = collect_worker_changes(lane, request.ownership)
        scope = validate_change_scope(changes, request.ownership, request.forbidden)
        if request.kind is TaskKind.READ and changes.paths:
            scope = ScopeResult(False, changes.paths)
        if not scope.allowed:
            _write_verification(
                lane.run_root,
                RunStatus.SCOPE_VIOLATION,
                changed_files=list(changes.paths),
                violations=list(scope.violations),
            )
            return 21

        checks = run_acceptance(
            lane,
            request.acceptance,
            timeout_seconds=worker_timeout,
        )
        if any(check.returncode != 0 for check in checks):
            _write_verification(
                lane.run_root,
                RunStatus.TEST_FAILED,
                changed_files=list(changes.paths),
            )
            return 21

        # Acceptance commands may mutate files after the initial scope check.
        changes = collect_worker_changes(lane, request.ownership)
        scope = validate_change_scope(changes, request.ownership, request.forbidden)
        if request.kind is TaskKind.READ and changes.paths:
            scope = ScopeResult(False, changes.paths)
        if not scope.allowed:
            _write_verification(lane.run_root, RunStatus.SCOPE_VIOLATION,
                                changed_files=list(changes.paths), violations=list(scope.violations))
            return 21

        if request.kind is TaskKind.WRITE:
            patch = export_worker_patch(lane, lane.run_root / "worker.patch", request.ownership)
            patch_status = check_patch_against_master(repo_root, patch.path)
            if patch_status is not RunStatus.COMPLETE:
                _write_verification(
                    lane.run_root,
                    patch_status,
                    changed_files=list(changes.paths),
                    patch=str(patch.path),
                )
                return 21
            _write_verification(
                lane.run_root,
                RunStatus.COMPLETE,
                changed_files=list(changes.paths),
                patch=str(patch.path),
                patch_sha256=patch.sha256,
            )
        else:
            _write_verification(lane.run_root, RunStatus.COMPLETE, changed_files=[])
        _print_json({"status": RunStatus.COMPLETE.value, "run_root": str(lane.run_root)})
        return 0
    finally:
        if lock is not None:
            lock.release()


def _workspace_root(repo_root: Path, policy: Policy) -> Path:
    configured = Path(_expand_environment(policy.workspace_root, os.environ))
    return configured.resolve() if configured.is_absolute() else (repo_root / configured).resolve()


def _new_run_id(slug: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{slug}-{uuid4().hex[:12]}"


def _write_verification(run_root: Path, status: RunStatus, **details: object) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    payload = {"status": status.value, **details}
    (run_root / "verification.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _print_json(payload: Mapping[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def _expand_environment(value: str, environ: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        return environ.get(name, match.group(0))

    return re.sub(r"%([^%]+)%|\$\{([^}]+)\}", replace, value)


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) calls TerminateProcess on Windows!
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied: conservatively alive.
        try:
            return kernel.WaitForSingleObject(handle, 0) != 0  # WAIT_OBJECT_0 = exited
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _spawn_detached(command: Sequence[str], cwd: Path, log_path: Path, *, env: Mapping[str, str] | None = None) -> int:
    options: dict[str, object] = {}
    if os.name == "nt":
        # A hidden console of its own (not DETACHED_PROCESS): the supervisor survives its parent exactly as before, and
        # every child it starts inherits that console instead of opening a new visible window.
        options.update(winproc.hidden_options(subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_BREAKAWAY_FROM_JOB))
    else:
        options["start_new_session"] = True
    with log_path.open("ab") as log:
        try:
            process = subprocess.Popen(
                list(command), cwd=cwd, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, close_fds=True, env=env, **options,
            )
        except PermissionError:
            if os.name == "nt" and "creationflags" in options:
                # When running inside a Windows Job Object that prohibits breakaway,
                # retry without CREATE_BREAKAWAY_FROM_JOB.
                options.update(winproc.hidden_options(subprocess.CREATE_NEW_PROCESS_GROUP))
                process = subprocess.Popen(
                    list(command), cwd=cwd, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=log, close_fds=True, env=env, **options,
                )
            else:
                raise
    import threading
    threading.Thread(target=process.wait, daemon=True).start()
    return process.pid


def _start_background(args: argparse.Namespace, argv: list[str]) -> int:
    repo = args.repo_root.resolve()
    policy = load_policy(args.policy or Path(__file__).parent / "resources/policy.json")
    resolve_agy(policy, os.environ)  # Fail before reserving a run or creating a lane.
    run_id = args.run_id or _new_run_id(args.slug)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_id):
        raise ValueError("invalid run id")
    root = args.state_root / run_id
    root.mkdir(parents=True, exist_ok=False)
    child_args = [item for item in argv if item != "--background"]
    if not args.run_id:
        child_args.extend(["--run-id", run_id])
    try:
        command = [sys.executable, "-m", "respected_orchestrator", "--data-root", str(args.ctx.data_root),
                   "antigravity", *child_args]
        env = dict(os.environ)
        pid = _spawn_detached(command, repo, root / "launcher.log", env=env)
    except Exception as error:
        _write_verification(root, RunStatus.WORKER_FAILED, error=str(error))
        raise
    (root / "supervisor.json").write_text(json.dumps({"pid": pid, "run_id": run_id}), encoding="utf-8")
    _print_json({"status": "STARTED", "pid": pid, "run_root": str(root)})
    return 0


def _path_is_owned(path: str, ownership: Sequence[str]) -> bool:
    return any(path == item or path.startswith(item.rstrip("/") + "/") for item in ownership)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    result = winproc.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise LaneError(result.stderr.strip() or result.stdout.strip())
    return result


def _markdown_list(values: Sequence[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- None."


def _parse_json_object(value: str) -> Mapping[str, object] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def _redact(value: str) -> str:
    patterns = (
        r"(?i)(api[_-]?key\s*[:=]\s*)\S+",
        r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+",
        r"(?i)(token\s*[:=]\s*)\S+",
    )
    redacted = value
    for pattern in patterns:
        redacted = re.sub(pattern, r"\1[REDACTED]", redacted)
    return redacted


def _git_path_list(cwd: Path, *args: str) -> tuple[str, ...]:
    completed = winproc.run(
        ["git", *args], cwd=cwd, capture_output=True, check=False
    )
    if completed.returncode != 0:
        raise LaneError(completed.stderr.decode("utf-8", errors="replace").strip())
    return tuple(
        item.decode("utf-8", errors="strict").replace("\\", "/")
        for item in completed.stdout.split(b"\0")
        if item
    )
