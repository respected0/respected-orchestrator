"""Isolated worker lanes: git worktree per run, guarded worker launch, change scope, acceptance and patch export."""

from __future__ import annotations

from . import winproc
from ..context import path_within_root

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
    """Raised when the requested worker CLI is not installed."""


class WriterLockError(RuntimeError):
    """Raised when an existing writer lock requires operator attention."""


class LaneError(RuntimeError):
    """Raised when a worktree lane cannot be created or safely prepared."""


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


def remove_lane(lane: Lane) -> None:
    """Drop a finished lane from the project's repository: its worktree, its Git record and its branch.

    The result lives in the run folder (worker.patch and the signed result), so nothing in the lane is needed once the run
    ended. Best effort and silent: a leftover is only clutter, it must never change how the run ended."""
    git = lambda *args: winproc.run(["git", *args], cwd=lane.repo_root, capture_output=True, text=True, encoding="utf-8", check=False)
    git("worktree", "remove", "--force", str(lane.worktree))
    shutil.rmtree(lane.worktree, ignore_errors=True)  # a file the worker still held open can keep the folder after Git gave up
    git("worktree", "prune")
    git("branch", "-D", lane.branch)


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


DEFAULT_READ_TEMPLATE = """# Read Worker Brief

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

DEFAULT_WRITE_TEMPLATE = """# Write Worker Brief

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
