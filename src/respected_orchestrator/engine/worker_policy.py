"""Worker execution policy: one validated boundary for every coding-agent launch.

A policy is built before a worker process exists. Any validation failure (missing
roots, a data-root grant, an unlisted executable) raises and the caller must not
start a worker. There is deliberately no unsandboxed fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys

from ..context import EngineContext, safe_path
from .processes import scrub_environment


class WorkerPolicyError(RuntimeError):
    """The requested worker boundary is invalid or cannot be enforced."""


class SandboxStartError(RuntimeError):
    """The sandbox launcher failed; no worker process may exist."""


NETWORK_MODES = {"deny", "allow"}


def _root(path: Path) -> Path:
    try:
        return safe_path(path)
    except (OSError, ValueError) as error:
        raise WorkerPolicyError(f"Worker root refused: {path}: {error}") from error


@dataclass(frozen=True)
class WorkerPolicy:
    allowed_roots: tuple[Path, ...]
    readonly_roots: tuple[Path, ...] = ()
    network_mode: str = "deny"
    executable_allowlist: tuple[Path, ...] = ()
    secrets: tuple[str, ...] = ()
    temp_root: Path | None = None
    ttl: float = 600.0

    def __post_init__(self):
        if self.network_mode not in NETWORK_MODES:
            raise WorkerPolicyError(f"Unknown network mode: {self.network_mode!r}")
        if not isinstance(self.ttl, (int, float)) or isinstance(self.ttl, bool) or self.ttl <= 0:
            raise WorkerPolicyError("Worker policy ttl must be positive")
        allowed = tuple(_root(path) for path in self.allowed_roots)
        readonly = tuple(_root(path) for path in self.readonly_roots)
        temp = _root(self.temp_root) if self.temp_root is not None else None
        if not allowed:
            raise WorkerPolicyError("Worker policy needs at least one writable root")
        if temp is not None and temp not in allowed:
            allowed = (*allowed, temp)
        for path in allowed:
            if not path.exists() or not path.is_dir():
                raise WorkerPolicyError(f"Worker writable root does not exist: {path}")
        for path in readonly:
            if not path.exists() or not path.is_dir():
                raise WorkerPolicyError(f"Worker read-only root does not exist: {path}")
            if any(path == writable or path.is_relative_to(writable) for writable in allowed):
                raise WorkerPolicyError(f"Read-only root overlaps a writable root: {path}")
        for writable in allowed:
            if any(writable == read or writable.is_relative_to(read) for read in readonly):
                raise WorkerPolicyError(f"Writable root overlaps a read-only root: {writable}")
        object.__setattr__(self, "allowed_roots", allowed)
        object.__setattr__(self, "readonly_roots", readonly)
        object.__setattr__(self, "temp_root", temp)

    def protect(self, data_root: Path) -> "WorkerPolicy":
        """Refuse a boundary that can reach the engine data root or its signing key."""
        protected = _root(data_root)
        key = protected / ".engine-key"
        for path in (*self.allowed_roots, *self.readonly_roots):
            if path == protected:
                raise WorkerPolicyError(f"Worker root must not be the engine data root: {path}")
            if protected.is_relative_to(path):
                raise WorkerPolicyError(f"Worker root contains the engine data root: {path}")
            if key.is_relative_to(path):
                raise WorkerPolicyError(f"Worker root exposes the evidence signing key: {path}")
        return self

    def resolve(self, command) -> list[str]:
        if not command:
            raise WorkerPolicyError("Worker command is empty")
        executable = str(command[0])
        found = executable if Path(executable).is_absolute() else shutil.which(executable)
        if not found:
            raise WorkerPolicyError(f"Worker executable not found: {executable}")
        resolved = _root(Path(found))
        if not resolved.is_file():
            raise WorkerPolicyError(f"Worker executable is not a file: {resolved}")
        allowlist = {_root(path) for path in self.executable_allowlist}
        if allowlist and resolved not in allowlist:
            raise WorkerPolicyError(f"Worker executable is not allowlisted: {resolved}")
        if resolved.suffix.lower() in {".cmd", ".bat"}:
            raise WorkerPolicyError("Shell shims are not executable workers")
        return [str(resolved), *map(str, command[1:])]

    def environment(self, environment) -> dict[str, str]:
        worker_env = scrub_environment(environment)
        for name in self.secrets:
            worker_env.pop(name, None)
        temp = str(self.temp_root or self.allowed_roots[0])
        worker_env["TEMP"] = worker_env["TMP"] = temp
        # AppContainer remaps TEMP to its own per-profile directory, so the granted scratch root is
        # published explicitly; otherwise the policy's temp grant is unreachable by the worker.
        worker_env["RESPECTED_WORKER_TMP"] = temp
        return worker_env

    def check_timeout(self, seconds: float) -> None:
        if seconds <= 0:
            raise WorkerPolicyError("Worker timeout must be positive")
        if seconds > self.ttl:
            raise WorkerPolicyError(f"Worker timeout {seconds:.1f}s exceeds policy ttl {self.ttl:.1f}s")


def default_policy(ctx: EngineContext | None, workdir: Path, command, *, network_mode: str = "deny",
                   temp_root: Path | None = None, readonly_roots=(), ttl: float = 600.0) -> WorkerPolicy:
    """Grant only the worker's own workspace, its interpreter/tool directory and the system prefix."""
    executable = Path(command[0]) if command else None
    if executable is not None and not executable.is_absolute():
        found = shutil.which(str(executable))
        executable = Path(found) if found else None
    support = []
    if executable is not None:
        support.append(executable.resolve().parent)
    support.append(Path(sys.prefix))
    support.extend(Path(p) for p in readonly_roots)
    policy = WorkerPolicy(
        allowed_roots=(Path(workdir),),
        readonly_roots=tuple(dict.fromkeys(support)),
        network_mode=network_mode,
        temp_root=Path(temp_root) if temp_root is not None else None,
        ttl=ttl,
    )
    return policy.protect(ctx.data_root) if ctx is not None else policy


def extra_readonly_roots() -> tuple[Path, ...]:
    """User-approved tool support directories (dependencies, interpreter data), never the user profile."""
    raw = os.environ.get("RESPECTED_WORKER_READONLY_ROOTS", "")
    return tuple(Path(part.strip()) for part in raw.split(os.pathsep) if part.strip())
