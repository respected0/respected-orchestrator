"""Fail-closed integration of two verified worker results in a temporary Git worktree.

The real project is never written: patches are checked and applied in a detached
worktree, one combined verification runs there, and only signed decision evidence
is published. Applying the combined patch remains a separate operator decision.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from ..context import EngineContext, safe_path, validate_project
from . import evidence, lanes, processes, runner, winproc, worker_policy


MAX_RUNS = 2
MAX_VERIFICATION_COMMANDS = 16
MAX_TIMEOUT_SECONDS = 3600


class _Stop(RuntimeError):
    def __init__(self, status: str, reason: str, details: dict | None = None):
        super().__init__(reason)
        self.status = status
        self.reason = reason
        self.details = details or {}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot(project: Path) -> tuple[str, str]:
    return (lanes._git(project, "rev-parse", "HEAD").stdout.strip(),
            runner.project_fingerprint(project))


def _failure(status: str, reason: str, project: Path | None, base_head: str | None,
             base_fingerprint: str | None, details: dict | None = None) -> dict:
    payload = {"status": status, "reason": reason}
    if details:
        payload.update(details)
    if project is None:
        return payload
    try:
        current_head, current_fingerprint = _snapshot(project)
        unchanged = ((base_head is None or current_head == base_head)
                     and (base_fingerprint is None or current_fingerprint == base_fingerprint))
        payload.update(real_repo_head=current_head, real_repo_fingerprint=current_fingerprint,
                       real_repo_unchanged=unchanged)
        if not unchanged:
            payload.update(status="real_repo_mutation", original_status=status, reason=reason)
    except (OSError, ValueError, lanes.LaneError) as error:
        payload["snapshot_error"] = str(error)
    return payload


def _parse_request(ctx: EngineContext, request) -> tuple[Path, list[str], list[dict]]:
    if not isinstance(request, dict):
        raise _Stop("invalid_input", "Integration request must be a JSON object")
    try:
        project = validate_project(ctx, Path(request.get("project_root", "")))
    except (OSError, TypeError, ValueError) as error:
        raise _Stop("invalid_input", f"Invalid project root: {error}") from error

    run_ids = request.get("run_ids")
    if (not isinstance(run_ids, list) or len(run_ids) != MAX_RUNS
            or any(not isinstance(item, str) for item in run_ids)
            or len(set(run_ids)) != MAX_RUNS):
        raise _Stop("invalid_input", "Exactly two distinct run identities are required")
    for run_id in run_ids:
        try:
            ctx.run_dir(run_id)
        except (TypeError, ValueError) as error:
            raise _Stop("invalid_input", f"Invalid run identity: {run_id}") from error

    raw_commands = request.get("verification")
    if (not isinstance(raw_commands, list)
            or not 1 <= len(raw_commands) <= MAX_VERIFICATION_COMMANDS):
        raise _Stop("invalid_input", "One to sixteen combined verification commands are required")
    verification = []
    for item in raw_commands:
        if not isinstance(item, dict):
            raise _Stop("invalid_input", "Each verification command must be an object")
        try:
            command = list(runner._command(item.get("command")))
        except (TypeError, ValueError) as error:
            raise _Stop("invalid_input", f"Invalid verification command: {error}") from error
        timeout = item.get("timeout_seconds", 300)
        if type(timeout) is not int or not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
            raise _Stop("invalid_input",
                        f"Verification timeout must be 1..{MAX_TIMEOUT_SECONDS} seconds")
        verification.append({"command": command, "timeout_seconds": timeout})
    return project, list(run_ids), verification


def _load_run(ctx: EngineContext, run_id: str, project: Path) -> dict:
    directory = ctx.run_dir(run_id)
    try:
        request = evidence.load_signed(ctx, directory / "request.json")
        status = evidence.load_signed(ctx, directory / "status.json")
        result = evidence.load_signed(ctx, directory / "result.json")
    except (OSError, ValueError) as error:
        raise _Stop("base_mismatch",
                    f"Signed run evidence is unavailable for {run_id}: {error}") from error
    if status.get("status") != "completed" or result.get("status") != "completed":
        raise _Stop("base_mismatch", f"Run is not completed: {run_id}")
    if (result.get("run_id") != run_id
            or request.get("project_fingerprint") != result.get("project_fingerprint")):
        raise _Stop("base_mismatch", f"Run ownership mismatch: {run_id}")
    target = Path(request.get("apply_root") or request.get("project_root", ""))
    try:
        target = safe_path(target)
    except (OSError, TypeError, ValueError) as error:
        raise _Stop("base_mismatch", f"Run target is invalid: {run_id}") from error
    if target != project:
        raise _Stop("base_mismatch", f"Run targets another project: {run_id}")
    patch = safe_path(directory / "worker.patch")
    if not patch.is_file():
        raise _Stop("base_mismatch", f"Patch is missing: {run_id}")
    patch_bytes = patch.read_bytes()
    if _digest(patch_bytes) != result.get("patch_sha256"):
        raise _Stop("base_mismatch", f"Patch integrity check failed: {run_id}")
    return {"run_id": run_id, "request": request, "result": result, "patch": patch,
            "patch_bytes": patch_bytes, "patch_sha256": result["patch_sha256"]}


def _integration_id(base_head: str, base_fingerprint: str, runs: list[dict],
                    verification: list[dict]) -> str:
    material = {
        "base_head": base_head,
        "base_fingerprint": base_fingerprint,
        "patches": sorted((run["run_id"], run["patch_sha256"]) for run in runs),
        "verification": verification,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "integration-" + _digest(encoded)[:24]


def _combined_patch(worktree: Path, base_head: str) -> bytes:
    lanes._git(worktree, "add", "-N", "--all")
    result = winproc.run(["git", "diff", "--binary", "--full-index", base_head, "--"],
                         cwd=worktree, capture_output=True, check=False)
    if result.returncode != 0:
        raise lanes.LaneError(result.stderr.decode("utf-8", errors="replace").strip())
    if lanes._patch_has_unsafe_mode(result.stdout):
        raise _Stop("integration_conflict", "Combined patch contains an unsafe file mode")
    return result.stdout


def _apply_patch(worktree: Path, run: dict) -> None:
    if lanes._patch_has_unsafe_mode(run["patch_bytes"]):
        raise _Stop("integration_conflict",
                    f"Patch contains an unsafe file mode: {run['run_id']}")
    if not run["patch_bytes"]:
        return
    try:
        lanes._git(worktree, "apply", "--check", "--binary", "--whitespace=nowarn",
                   str(run["patch"]))
        lanes._git(worktree, "apply", "--binary", "--whitespace=nowarn", str(run["patch"]))
    except lanes.LaneError as error:
        raise _Stop("integration_conflict",
                    f"Patch conflicts after earlier patches: {run['run_id']}: {error}") from error


def _verify(ctx: EngineContext, worktree: Path, scratch: Path,
            verification: list[dict]) -> tuple[list[dict], bool]:
    results = []
    for index, item in enumerate(verification, start=1):
        command = item["command"]
        timeout = item["timeout_seconds"]
        started = datetime.now(timezone.utc)
        try:
            policy = worker_policy.default_policy(
                ctx, worktree, command, network_mode="deny", temp_root=scratch,
                ttl=float(timeout),
            )
            completed = processes.execute(command, worktree, timeout, scrub_env=True,
                                          policy=policy)
            entry = {
                "command": command,
                "returncode": int(completed.returncode),
                "timed_out": False,
                "duration_seconds": round(
                    (datetime.now(timezone.utc) - started).total_seconds(), 3),
                "stdout_sha256": _digest(completed.stdout.encode("utf-8", errors="replace")),
                "stderr_sha256": _digest(completed.stderr.encode("utf-8", errors="replace")),
            }
            results.append(entry)
            if completed.returncode != 0:
                return results, False
        except processes.ProcessStopped as error:
            results.append({
                "command": command,
                "returncode": None,
                "timed_out": error.reason == "timed_out",
                "stopped": error.reason,
                "duration_seconds": round(
                    (datetime.now(timezone.utc) - started).total_seconds(), 3),
            })
            return results, False
        except Exception as error:  # sandbox startup and every other failure is verification failure
            results.append({
                "command": command,
                "returncode": None,
                "timed_out": False,
                "error": str(error),
                "duration_seconds": round(
                    (datetime.now(timezone.utc) - started).total_seconds(), 3),
            })
            return results, False
    return results, True


def _cleanup(project: Path | None, worktree: Path | None, stage: Path | None) -> None:
    if project is not None and worktree is not None:
        winproc.run(["git", "worktree", "remove", "--force", str(worktree)],
                    cwd=project, capture_output=True, check=False)
        shutil.rmtree(worktree, ignore_errors=True)
        winproc.run(["git", "worktree", "prune"],
                    cwd=project, capture_output=True, check=False)
    if stage is not None:
        shutil.rmtree(stage, ignore_errors=True)


def _existing(ctx: EngineContext, integration_id: str, runs: list[dict],
              base_head: str, base_fingerprint: str) -> dict | None:
    directory = ctx.state_dir / "integrations" / integration_id
    evidence_path = directory / "integration.json"
    if not evidence_path.is_file():
        return None
    try:
        payload = evidence.load_signed(ctx, evidence_path)
        combined_path = Path(payload["combined_patch"])
        expected = [{"run_id": run["run_id"], "patch_sha256": run["patch_sha256"]}
                    for run in runs]
        actual = [{"run_id": item.get("run_id"), "patch_sha256": item.get("patch_sha256")}
                  for item in payload.get("patches", [])]
        if (payload.get("status") != "ready_for_decision"
                or payload.get("base_head") != base_head
                or payload.get("base_fingerprint") != base_fingerprint
                or actual != expected
                or not combined_path.is_file()
                or _digest(combined_path.read_bytes()) != payload.get("combined_patch_sha256")):
            raise ValueError("signed integration evidence does not match this request")
        return dict(payload, evidence=str(evidence_path))
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise _Stop("base_mismatch", f"Published integration evidence is invalid: {error}") from error


def _publish(ctx: EngineContext, integration_id: str, base_head: str, base_fingerprint: str,
             runs: list[dict], combined_patch: bytes,
             verification: list[dict]) -> dict:
    directory = ctx.state_dir / "integrations" / integration_id
    directory.mkdir(parents=True, exist_ok=True)
    combined_path = safe_path(directory / "combined.patch")
    temporary = directory / f".combined-{uuid.uuid4().hex}.tmp"
    temporary.write_bytes(combined_patch)
    os.replace(temporary, combined_path)
    patches = [{"run_id": run["run_id"], "patch_sha256": run["patch_sha256"],
                "changed_files": list(run["result"]["changed_files"])}
               for run in runs]
    changed_files = sorted({name for item in patches for name in item["changed_files"]})
    payload = {
        "status": "ready_for_decision",
        "integration_id": integration_id,
        "run_ids": [run["run_id"] for run in runs],
        "base_head": base_head,
        "base_fingerprint": base_fingerprint,
        "patches": patches,
        "changed_files": changed_files,
        "combined_patch": str(combined_path),
        "combined_patch_sha256": _digest(combined_patch),
        "verification": verification,
        "verification_count": len(verification),
        "real_repo_unchanged": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    evidence_path = directory / "integration.json"
    evidence.save_signed(ctx, evidence_path, payload)
    return dict(payload, evidence=str(evidence_path))


def integrate(ctx: EngineContext, request) -> dict:
    """Check two verified results together and publish decision evidence without touching the project."""
    project = None
    base_head = None
    base_fingerprint = None
    worktree = None
    stage = None
    try:
        project, run_ids, verification = _parse_request(ctx, request)
        base_head, base_fingerprint = _snapshot(project)
        if lanes._git(project, "status", "--porcelain=v1").stdout.strip():
            raise _Stop("base_mismatch",
                        "Integration requires a clean project working tree")

        runs = [_load_run(ctx, run_id, project) for run_id in run_ids]
        fingerprints = [run["result"]["project_fingerprint"] for run in runs]
        if len(set(fingerprints)) != 1:
            raise _Stop("base_mismatch", "The two runs were produced from different project states")
        if fingerprints[0] != base_fingerprint:
            raise _Stop("head_drift", "Project HEAD or working tree changed after the runs")

        for run in runs:
            try:
                runner.check_result(ctx, run["run_id"])
            except ValueError as error:
                if "stale" in str(error):
                    raise _Stop("head_drift", str(error)) from error
                raise _Stop("base_mismatch", str(error)) from error

        after_head, after_fingerprint = _snapshot(project)
        if after_head != base_head or after_fingerprint != base_fingerprint:
            raise _Stop("real_repo_mutation", "Project changed while runs were being checked")

        integration_id = _integration_id(base_head, base_fingerprint, runs, verification)
        existing = _existing(ctx, integration_id, runs, base_head, base_fingerprint)
        if existing is not None:
            return existing

        integration_root = ctx.state_dir / "integrations"
        integration_root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{integration_id}-", dir=integration_root))
        worktree = stage / "worktree"
        scratch = stage / "tmp"
        scratch.mkdir()
        lanes._git(project, "worktree", "add", "--detach", str(worktree), base_head)

        for run in runs:
            _apply_patch(worktree, run)
        combined_patch = _combined_patch(worktree, base_head)
        verification_results, verified = _verify(ctx, worktree, scratch, verification)
        if not verified:
            raise _Stop("verification_failed", "Combined verification failed",
                        {"verification": verification_results})

        _cleanup(project, worktree, stage)
        worktree = None
        stage = None
        final_head, final_fingerprint = _snapshot(project)
        if final_head != base_head or final_fingerprint != base_fingerprint:
            raise _Stop("real_repo_mutation", "Project changed during integration")
        return _publish(ctx, integration_id, base_head, base_fingerprint, runs,
                        combined_patch, verification_results)
    except _Stop as error:
        return _failure(error.status, error.reason, project, base_head, base_fingerprint,
                        error.details)
    except Exception as error:
        return _failure("engine_error", str(error), project, base_head, base_fingerprint)
    finally:
        _cleanup(project, worktree, stage)
