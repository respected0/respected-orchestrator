"""Versioned, signed recovery checkpoints shared by runs, campaigns and projects.

The checkpoint is deliberately a small operational contract, never a dump of a worker request. It records only the
repository identity, role/round, the next approved action, hashes of completed checks and hard limits. A checkpoint is
written atomically through the owned evidence key, so a killed process leaves either the previous complete snapshot or
the new complete snapshot behind.
"""
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

from ..context import path_within_root, safe_path
from ..engine import winproc
from ..engine.evidence import load_signed, save_signed


SCHEMA_VERSION = 2
STATUSES = frozenset({"RESUMABLE", "NEEDS_REVIEW"})
KINDS = frozenset({"run", "campaign", "project"})
LIMIT_KEYS = frozenset({"max_rounds", "deadline_epoch", "max_weighted_tokens", "max_seconds"})

_AUTO = object()
_TOP_KEYS = frozenset({
    "schema_version", "kind", "operation_id", "status", "repo", "role", "round", "next_action", "checks",
    "limits", "updated_at",
})
_REPO_KEYS = frozenset({"commit", "root"})
_ACTION_KEYS = frozenset({"step", "target", "reason_code"})
_V1_KEYS = frozenset({
    "schema_version", "kind", "operation_id", "commit", "root", "role", "round", "next_step", "target",
    "check_hashes", "limits", "updated_at",
})
_FORBIDDEN_FIELDS = frozenset({
    "prompt", "prompts", "worker_prompt", "request", "request_body", "body", "messages", "message", "env",
    "environment", "api_key", "apikey", "authorization", "auth", "token", "tokens", "secret", "secrets",
    "password", "credentials", "credential", "stdout", "stderr", "transcript",
})
_SECRET_TEXT = re.compile(
    r"(?i)(?:api[_-]?key|authorization|bearer\s+|token\s*=|secret\s*=|password\s*=|-----BEGIN\s|sk-[a-z0-9_-]{16,})"
)
_OPERATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_ROLE = re.compile(r"[a-z][a-z0-9_.-]{0,31}")
_STEP = re.compile(r"[a-z][a-z0-9_.:-]{0,63}")
_CHECK = re.compile(r"[a-z][a-z0-9_.-]{0,63}")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_COMMIT = re.compile(r"[0-9a-fA-F]{40,64}")
_MAX_CHECKS = 64
_MAX_TARGET = 300


class CheckpointError(ValueError):
    """A checkpoint was incomplete, unsafe or from an incompatible schema."""

    def __init__(self, message, code="invalid_checkpoint"):
        super().__init__(message)
        self.code = code


def _exact_fields(value, fields, label):
    if not isinstance(value, dict):
        raise CheckpointError(f"{label} must be an object")
    unknown = sorted(set(value) - set(fields))
    missing = sorted(set(fields) - set(value))
    if unknown:
        raise CheckpointError(f"{label} has unknown fields: {', '.join(unknown)}", "unknown_field")
    if missing:
        raise CheckpointError(f"{label} is missing fields: {', '.join(missing)}", "incomplete_snapshot")


def _reject_forbidden_fields(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CheckpointError("Checkpoint object keys must be strings")
            if key.casefold() in _FORBIDDEN_FIELDS:
                raise CheckpointError(f"Forbidden checkpoint field: {key}", "forbidden_field")
            _reject_forbidden_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_fields(child)


def _safe_text(value, label, pattern, *, allow_none=False):
    if value is None and allow_none:
        return
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise CheckpointError(f"Invalid {label}")
    if _SECRET_TEXT.search(value):
        raise CheckpointError(f"Secret material is not allowed in {label}", "forbidden_field")


def _validate_limits(value):
    _exact_fields(value, LIMIT_KEYS, "limits")
    for key, item in value.items():
        if item is not None and (type(item) is not int or item < 0 or item > 2**63 - 1):
            raise CheckpointError(f"Invalid limits.{key}")


def _validate_timestamp(value):
    if not isinstance(value, str) or not 10 <= len(value) <= 64 or any(char in value for char in "\r\n"):
        raise CheckpointError("Invalid updated_at")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CheckpointError("Invalid updated_at") from error
    if parsed.tzinfo is None:
        raise CheckpointError("updated_at must include a timezone")


def validate_checkpoint(value):
    """Validate and return a detached, closed-schema checkpoint (v2 only)."""
    if not isinstance(value, dict):
        raise CheckpointError("Checkpoint must be an object")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise CheckpointError("Unsupported checkpoint schema", "unsupported_schema")
    _reject_forbidden_fields(value)
    _exact_fields(value, _TOP_KEYS, "checkpoint")
    if value["kind"] not in KINDS:
        raise CheckpointError("Invalid checkpoint kind")
    _safe_text(value["operation_id"], "operation_id", _OPERATION)
    if value["status"] not in STATUSES:
        raise CheckpointError("Invalid checkpoint status")

    _exact_fields(value["repo"], _REPO_KEYS, "repo")
    commit = value["repo"]["commit"]
    if commit is not None and (not isinstance(commit, str) or not _COMMIT.fullmatch(commit)):
        raise CheckpointError("Invalid repo.commit")
    if not isinstance(value["repo"]["root"], str) or not Path(value["repo"]["root"]).is_absolute():
        raise CheckpointError("repo.root must be an absolute path")

    if value["role"] is not None:
        _safe_text(value["role"], "role", _ROLE)
    if type(value["round"]) is not int or not 0 <= value["round"] <= 1_000_000:
        raise CheckpointError("Invalid round")

    _exact_fields(value["next_action"], _ACTION_KEYS, "next_action")
    _safe_text(value["next_action"]["step"], "next_action.step", _STEP)
    _safe_text(value["next_action"]["reason_code"], "next_action.reason_code", _STEP)
    target = value["next_action"]["target"]
    if target is not None:
        if not isinstance(target, str) or not 0 < len(target) <= _MAX_TARGET:
            raise CheckpointError("Invalid next_action.target")
        if any(char in target for char in "\r\n\0") or _SECRET_TEXT.search(target):
            raise CheckpointError("Secret or multiline target is not allowed", "forbidden_field")

    checks = value["checks"]
    if not isinstance(checks, dict) or len(checks) > _MAX_CHECKS:
        raise CheckpointError("Invalid checks")
    for name, digest in checks.items():
        if not isinstance(name, str) or not _CHECK.fullmatch(name) or not isinstance(digest, str) \
                or not _SHA256.fullmatch(digest):
            raise CheckpointError("Checks must map safe names to SHA-256 hex digests")
    _validate_limits(value["limits"])
    _validate_timestamp(value["updated_at"])
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": value["kind"],
        "operation_id": value["operation_id"],
        "status": value["status"],
        "repo": {"commit": commit, "root": value["repo"]["root"]},
        "role": value["role"],
        "round": value["round"],
        "next_action": dict(value["next_action"]),
        "checks": dict(checks),
        "limits": dict(value["limits"]),
        "updated_at": value["updated_at"],
    }


def read_git_head(project_root):
    """Return the current commit for a Git worktree, or None when the source is not a readable Git worktree."""
    try:
        root = safe_path(Path(project_root))
        if not root.is_dir():
            return None
        completed = winproc.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
            encoding="utf8", errors="replace", timeout=10, check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    head = completed.stdout.strip().lower()
    return head if completed.returncode == 0 and _COMMIT.fullmatch(head) else None


def create_checkpoint(kind, operation_id, project_root, *, commit=_AUTO, role=None, round_number=0,
                      next_action=None, checks=None, limits=None, status="RESUMABLE", updated_at=None):
    """Build a validated checkpoint; commit defaults to the current HEAD of project_root."""
    root = Path(project_root)
    if not root.is_absolute() or not root.is_dir():
        raise CheckpointError("project_root must be an existing absolute directory")
    if commit is _AUTO:
        commit = read_git_head(root)
    action = {"step": "resume", "target": None, "reason_code": "checkpoint_ready"}
    action.update(next_action or {})
    limit_values = {key: None for key in LIMIT_KEYS}
    limit_values.update(limits or {})
    value = {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "operation_id": operation_id,
        "status": status,
        "repo": {"commit": commit, "root": str(safe_path(root))},
        "role": role,
        "round": round_number,
        "next_action": action,
        "checks": dict(checks or {}),
        "limits": limit_values,
        "updated_at": updated_at or dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    return validate_checkpoint(value)


def checkpoint_path(ctx, kind, operation_id):
    """Canonical private path for a checkpoint beneath this engine's data root."""
    if kind not in KINDS:
        raise CheckpointError("Invalid checkpoint kind")
    _safe_text(operation_id, "operation_id", _OPERATION)
    path = safe_path(ctx.data_root / "checkpoints" / kind / f"{operation_id}.json")
    if not path_within_root(path, ctx.data_root):
        raise CheckpointError("Checkpoint path escapes the data root", "path_refused")
    return path


def save_checkpoint(ctx, path, value):
    """Validate before writing: a rejected snapshot never creates or replaces a file."""
    target = safe_path(Path(path))
    if not path_within_root(target, ctx.data_root):
        raise CheckpointError("Checkpoint path escapes the data root", "path_refused")
    document = validate_checkpoint(value)
    save_signed(ctx, target, document)
    return document


def _migrate_v1(ctx, path, value):
    _exact_fields(value, _V1_KEYS, "v1 checkpoint")
    _validate_limits(value["limits"])
    _validate_timestamp(value["updated_at"])
    migrated = {
        "schema_version": SCHEMA_VERSION,
        "kind": value["kind"],
        "operation_id": value["operation_id"],
        "status": "RESUMABLE",
        "repo": {"commit": value["commit"], "root": value["root"]},
        "role": value["role"],
        "round": value["round"],
        "next_action": {"step": value["next_step"], "target": value["target"], "reason_code": "legacy_resume"},
        "checks": dict(value["check_hashes"]),
        "limits": dict(value["limits"]),
        "updated_at": value["updated_at"],
    }
    document = validate_checkpoint(migrated)
    backup = path.with_name(path.name + ".v1.bak")
    if not backup.exists():
        save_signed(ctx, backup, value)
    save_signed(ctx, path, document)
    return document


def inspect_checkpoint(ctx, path, *, project_root=None):
    """Read a checkpoint without leaking untrusted content.

    Returns an envelope ``{status, reason, migrated, checkpoint}``. Any unreadable, tampered, incomplete or
    incompatible snapshot becomes NEEDS_REVIEW; callers must require human approval before resuming it.
    """
    target = safe_path(Path(path))
    if not path_within_root(target, ctx.data_root):
        return {"status": "NEEDS_REVIEW", "reason": "path_refused", "migrated": False, "checkpoint": None}
    try:
        value = load_signed(ctx, target)
    except FileNotFoundError:
        return {"status": "NEEDS_REVIEW", "reason": "checkpoint_missing", "migrated": False, "checkpoint": None}
    except json.JSONDecodeError:
        return {"status": "NEEDS_REVIEW", "reason": "checkpoint_unreadable", "migrated": False, "checkpoint": None}
    except (OSError, UnicodeError):
        return {"status": "NEEDS_REVIEW", "reason": "checkpoint_unreadable", "migrated": False, "checkpoint": None}
    except (ValueError, TypeError):
        return {"status": "NEEDS_REVIEW", "reason": "signature_invalid", "migrated": False, "checkpoint": None}

    migrated = False
    version = value.get("schema_version")
    looks_v1 = version == 1 or (version is None and ("next_step" in value or "check_hashes" in value))
    if looks_v1:
        try:
            value = _migrate_v1(ctx, target, value)
            migrated = True
        except (CheckpointError, OSError) as error:
            reason = getattr(error, "code", "migration_failed")
            return {"status": "NEEDS_REVIEW", "reason": reason, "migrated": False, "checkpoint": None}
    else:
        try:
            value = validate_checkpoint(value)
        except CheckpointError as error:
            return {"status": "NEEDS_REVIEW", "reason": error.code, "migrated": False, "checkpoint": None}

    root = Path(project_root) if project_root is not None else Path(value["repo"]["root"])
    try:
        if not safe_path(root).is_dir():
            return {"status": "NEEDS_REVIEW", "reason": "repo_unavailable", "migrated": migrated,
                    "checkpoint": value}
    except (OSError, ValueError):
        return {"status": "NEEDS_REVIEW", "reason": "repo_unavailable", "migrated": migrated,
                "checkpoint": value}
    head = read_git_head(root)
    if head != value["repo"]["commit"]:
        reason = "repo_head_changed" if head is not None else "repo_unavailable"
        return {"status": "NEEDS_REVIEW", "reason": reason, "migrated": migrated, "checkpoint": value}

    return {"status": value["status"], "reason": None, "migrated": migrated, "checkpoint": value}
