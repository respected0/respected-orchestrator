"""Read-only, redacted presentation model over signed engine evidence. Never writes evidence."""
import hashlib
import os
import re
from pathlib import Path

from ..context import safe_path
from ..engine import lanes, runner
from ..engine.evidence import load_signed


def _secret_values():
    return tuple(
        value for name, value in os.environ.items()
        if len(value) >= 8 and any(marker in name.upper() for marker in ("TOKEN", "SECRET", "API_KEY", "PASSWORD"))
    )


def _clean(value, secrets):
    if isinstance(value, str):
        value = re.sub(r"(?i)((?:password|secret)\s*[:=]\s*)\S+", r"\1[REDACTED]", lanes._redact(value))
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, list):
        return [_clean(item, secrets) for item in value]
    if isinstance(value, dict):
        return {str(key): _clean(item, secrets) for key, item in value.items()}
    return value


def view(ctx, run_id):
    """Return a presentation-only view; raises ValueError for missing or tampered evidence."""
    secrets = _secret_values()
    directory = ctx.run_dir(run_id)
    request = load_signed(ctx, directory / "request.json")
    status = load_signed(ctx, directory / "status.json")
    result = load_signed(ctx, directory / "result.json") if (directory / "result.json").is_file() else None
    current = status.get("status", "unknown")
    reason = status.get("reason") or ("completed" if current == "completed" else current)
    patch = {"sha256": result.get("patch_sha256"), "changed_files": result.get("changed_files", [])} if result else None
    if result and result.get("status") == "completed":
        patch_file = safe_path(directory / "worker.patch")
        expected = result.get("patch_sha256")
        if not patch_file.is_file() or hashlib.sha256(patch_file.read_bytes()).hexdigest() != expected:
            current, reason = "stale", "patch_changed"
        else:
            try:
                if runner.project_fingerprint(Path(request["project_root"])) != result.get("project_fingerprint"):
                    current, reason = "stale", "project_changed"
            except (OSError, ValueError, KeyError):
                current, reason = "stale", "project_unavailable"
    reviewer = (request.get("role_assignments") or {}).get("reviewer")
    tester = result.get("tester") if result else None
    usage = (result or {}).get("usage")
    return _clean({
        "schema_version": 1,
        "task_id": run_id,
        "status": current,
        "reason": reason,
        "patch_summary": patch,
        "checks": (result or {}).get("checks", []),
        "reviewer": reviewer,
        "tests": tester,
        "risks": (result or {}).get("remaining_risks") or status.get("remaining_risks") or [],
        "cost": {"known": isinstance(usage, dict), "tokens": usage, "estimated": "bilinmiyor"},
    }, secrets)