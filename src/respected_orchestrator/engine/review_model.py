"""Read-only review DTO for the approval center (B3-05.01).

One call answers "can this run be approved, and if not, why": the engine's own `check_result` is the verdict (tamper,
stale, conflict, MAF gate), on top of which the patch is parsed for things a human must see (symlinks, binary hunks,
paths outside the grant, secrets). Nothing here writes, applies or approves. Unknown is never green: a run is
`approvable` only when every blocker list is empty.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
import re

from ..context import safe_path
from ..interfaces import evidence_view
from . import runner
from .evidence import load_signed

MAX_REVIEW_BYTES = 2 * 1024 * 1024  # a patch a person cannot realistically review is not approvable
PREVIEW_BYTES = 200 * 1024
_FILE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def _scope_problem(path, ownership, forbidden):
    parts = path.replace("\\", "/").split("/")
    if path.startswith(("/", "\\")) or re.match(r"[A-Za-z]:", path) or ".." in parts or ".git" in parts:
        return "outside_project"
    under = lambda root: path == root.rstrip("/") or path.startswith(root.rstrip("/") + "/")
    if any(under(root) for root in forbidden):
        return "forbidden"
    if ownership and not any(under(root) for root in ownership):
        return "outside_ownership"
    return None


def parse_patch(text, ownership=(), forbidden=()):
    """Per-file facts from a git patch. Only what the patch itself says; a hunk it cannot place is simply not counted."""
    files, current = [], None
    for line in text.splitlines():
        match = _FILE.match(line)
        if match:
            current = {"path": match.group(2), "old_path": match.group(1), "symlink": False, "binary": False, "mode_change": False,
                       "added": 0, "removed": 0, "problem": None}
            current["problem"] = _scope_problem(current["path"], ownership, forbidden) or _scope_problem(current["old_path"], ownership, forbidden)
            files.append(current)
        elif current is None:
            continue
        elif line.startswith(("new file mode 120000", "old mode 120000", "new mode 120000", "deleted file mode 120000")):
            current["symlink"] = True
        elif line.startswith(("old mode", "new mode")):
            current["mode_change"] = True
        elif line.startswith(("GIT binary patch", "Binary files")):
            current["binary"] = True
        elif line.startswith("+") and not line.startswith("+++"):
            current["added"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            current["removed"] += 1
    return files


def _finding(kind, message, path=None):
    return {"kind": kind, "message": message, **({"path": path} if path else {})}


def review_dto(ctx, run_id):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    blockers, warnings = [], []
    dto = {"run_id": run_id, "approvable": False, "checked_at": now, "blockers": blockers, "warnings": warnings, "evidence": None,
           "patch": None, "fingerprints": None, "delivery": None, "diff": {"preview": "", "truncated": False, "bytes": 0}}
    try:
        directory = ctx.run_dir(run_id)
        request = load_signed(ctx, directory / "request.json")
        result = load_signed(ctx, directory / "result.json") if (directory / "result.json").is_file() else {}
        evidence = evidence_view.view(ctx, run_id)  # redacted presentation model: the one shared source
    except (ValueError, OSError, KeyError) as error:
        blockers.append(_finding("evidence_unreadable", str(error)[:300]))
        return dto
    dto["evidence"] = {k: evidence[k] for k in ("status", "reason", "checks", "reviewer", "tests", "risks", "cost")}
    dto["delivery"] = evidence["delivery"]
    if (directory / "applied.json").is_file():
        blockers.append(_finding("already_applied", "This patch was already applied."))
    try:
        runner.check_result(ctx, run_id)  # tamper, stale head/tree, conflicts, acceptance, tester and MAF binding
    except (ValueError, OSError, KeyError) as error:
        blockers.append(_finding("check_failed", str(error)[:300]))
    patch_path = safe_path(directory / "worker.patch")
    raw = patch_path.read_bytes() if patch_path.is_file() else b""
    sha = hashlib.sha256(raw).hexdigest()
    dto["patch"] = {"sha256": sha, "recorded_sha256": result.get("patch_sha256"), "bytes": len(raw), "files": []}
    dto["fingerprints"] = {"project_at_run": result.get("project_fingerprint"), "project_now": None}
    try:
        dto["fingerprints"]["project_now"] = runner.project_fingerprint(Path(request["project_root"]))
    except (ValueError, OSError, KeyError):
        blockers.append(_finding("project_unavailable", "The project cannot be fingerprinted now."))
    if result.get("patch_sha256") != sha:
        blockers.append(_finding("patch_hash_mismatch", "The patch on disk is not the one the evidence signed."))
    if not raw:
        blockers.append(_finding("empty_patch", "There is nothing to approve."))
    if len(raw) > MAX_REVIEW_BYTES:
        blockers.append(_finding("diff_too_large", f"Patch is {len(raw)} bytes; over {MAX_REVIEW_BYTES} it cannot be reviewed here."))
    text = raw[:MAX_REVIEW_BYTES].decode("utf8", errors="replace")
    files = parse_patch(text, request.get("ownership") or (), request.get("forbidden") or ())
    dto["patch"]["files"] = files
    recorded = sorted(result.get("changed_files") or [])
    if len(raw) <= MAX_REVIEW_BYTES and sorted(f["path"] for f in files) != recorded:
        blockers.append(_finding("changed_files_mismatch", "Files in the patch differ from the files the evidence lists."))
    for f in files:
        if f["problem"]:
            blockers.append(_finding(f["problem"], f"{f['path']} is not allowed for this run.", f["path"]))
        if f["symlink"]:
            blockers.append(_finding("symlink", f"{f['path']} is a symbolic link.", f["path"]))
        if f["binary"]:
            warnings.append(_finding("binary", f"{f['path']} is binary; its content cannot be shown.", f["path"]))
        if f["mode_change"]:
            warnings.append(_finding("mode_change", f"{f['path']} changes file mode.", f["path"]))
    if not evidence["checks"]:
        blockers.append(_finding("no_tests", "No acceptance results are recorded."))
    delivery = evidence["delivery"]
    if delivery is None:
        warnings.append(_finding("no_pr", "No pull request or CI result is recorded for this run (unknown, not passing)."))
    elif delivery.get("state") == "tampered":
        blockers.append(_finding("delivery_tampered", "The PR/CI receipt failed verification."))
    elif not delivery.get("ci"):
        warnings.append(_finding("ci_missing", "CI result is missing (unknown, not passing)."))
    elif delivery["ci"].get("conclusion") != "success":
        blockers.append(_finding("ci_not_green", f"CI concluded {delivery['ci'].get('conclusion')!r}."))
    clean = evidence_view._clean(text[:PREVIEW_BYTES], evidence_view._secret_values())
    if clean != text[:PREVIEW_BYTES]:
        warnings.append(_finding("secret_redacted", "Secret-looking values were hidden in the diff preview."))
    dto["diff"] = {"preview": clean, "truncated": len(raw) > PREVIEW_BYTES, "bytes": len(raw)}
    dto["approvable"] = not blockers
    return dto
