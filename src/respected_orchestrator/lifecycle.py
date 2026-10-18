"""RPP v1.1 lifecycle state: versioned install manifest, plans, journal, rollback.

Local filesystem operations over explicit roots only; every path is confined with
safe_path.  No shell, no network.  Raises LifecycleError (code/message/hint) which
rpp.py converts into the protocol error triple.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from . import __version__
from .context import atomic_write_json, path_within_root, safe_path

PRODUCT_ID = "respected-orchestrator"
ACTIONS = ("install", "update", "repair", "uninstall")
MANIFEST_NAME = ".respected/install.json"

_ZERO_USAGE = {"raw_input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
               "reasoning_tokens": 0, "estimated_weighted_tokens": 0}


class LifecycleError(Exception):
    """Expected lifecycle failure carrying the protocol error triple."""

    def __init__(self, code, message, hint=""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def usage_zero():
    return dict(_ZERO_USAGE)


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe(path):
    try:
        return safe_path(Path(path))
    except (OSError, ValueError) as exc:
        raise LifecycleError("BAD_REQUEST", "A lifecycle path is not usable.",
                             "Use real directories with no links/reparse points.") from exc


def _read_text(path):
    try:
        return path.read_bytes().decode("utf-8")
    except OSError:
        return None


def _atomic_write_text(path, text):
    path = _safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".lifecycle-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _check_action(action):
    if action not in ACTIONS:
        raise LifecycleError("BAD_REQUEST", f"Unknown lifecycle action {action!r}.",
                             "Use one of: " + ", ".join(ACTIONS) + ".")


def _app_root(target):
    raw = target.get("app_root")
    if not isinstance(raw, str) or not raw or not os.path.isabs(raw):
        raise LifecycleError("BAD_REQUEST", "target.app_root must be an absolute path.",
                             "Pass an absolute app_root in the payload.")
    return _safe(Path(raw))


def _file_targets(app_root, files):
    """Validate payload files; return [(rel, safe path, content)] confined to app_root."""
    if not isinstance(files, dict):
        raise LifecycleError("BAD_REQUEST", "target.files must be an object of relative paths.",
                             'Send {"files": {"relative/path": "content"}}.')
    items = []
    for rel, content in files.items():
        if not isinstance(rel, str) or not isinstance(content, str):
            raise LifecycleError("BAD_REQUEST", "target.files keys and values must be strings.",
                                 "Send string relative paths mapped to string contents.")
        candidate = Path(rel)
        if candidate.is_absolute() or candidate.name in ("", ".", "..") or ".." in candidate.parts:
            raise LifecycleError("BAD_REQUEST", f"File path {rel!r} is not a safe relative path.",
                                 "Use relative paths inside the app root.")
        path = _safe(app_root / candidate)
        if not path_within_root(path, app_root):
            raise LifecycleError("BAD_REQUEST", f"File path {rel!r} escapes the app root.",
                                 "Use relative paths inside the app root.")
        items.append((rel, path, content))
    return items


def _load_manifest(app_root):
    path = _safe(app_root / MANIFEST_NAME)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return None
    return data


def verify(app_root):
    """Read-only install state for an app root (used by manifest and post-apply check)."""
    manifest = _load_manifest(app_root)
    if manifest is None:
        return {"installed": False, "install_state": "absent"}
    for rel, digest in manifest["files"].items():
        try:
            path = _safe(app_root / rel)
            matches = path.is_file() and _sha256_file(path) == digest
        except (OSError, ValueError):
            matches = False
        if not matches:
            return {"installed": True, "install_state": "repair-needed"}
    if manifest.get("product_version") != __version__:
        return {"installed": True, "install_state": "update-available"}
    return {"installed": True, "install_state": "installed"}


def _step(step_id, action, summary, reversible, reason):
    return {"id": step_id, "action": action, "summary": summary,
            "reversible": reversible, "irreversible_reason": reason}


def _plan_steps(action, app_root, files, purge):
    steps = []
    if action in ("install", "update", "repair"):
        items = _file_targets(app_root, files)
        if action == "repair" and _load_manifest(app_root) is None:
            raise LifecycleError("BAD_REQUEST", "repair needs an existing install record.",
                                 "Run an install plan for this app root first.")
        for rel, path, content in items:
            needed = action != "repair" or not path.is_file() or _sha256_file(path) != _sha256_text(content)
            if needed:
                verb = "restore" if action == "repair" else ("update" if action == "update" else "install")
                steps.append(_step("write:" + rel, "write", f"{verb} {rel}", True, None))
        steps.append(_step("manifest", "manifest", "write install record", True, None))
    else:
        manifest = _load_manifest(app_root)
        if manifest is None:
            raise LifecycleError("BAD_REQUEST", "uninstall needs an existing install record.",
                                 "Nothing is installed at this app root.")
        for rel in sorted(manifest["files"]):
            steps.append(_step("remove:" + rel, "remove", f"remove {rel}", True, None))
        steps.append(_step("manifest", "manifest", "remove install record", True, None))
        if purge:
            steps.append(_step("purge", "purge", "purge the product data root", False,
                               "removes the product data root and everything in it"))
    return steps


def plan(action, target):
    """Read-only dry-run plan; writes no state."""
    _check_action(action)
    app_root = _app_root(target)
    files = target.get("files") if isinstance(target.get("files"), dict) else {}
    steps = _plan_steps(action, app_root, files, bool(target.get("purge")))
    return {"action": action, "target": target, "dry_run": True, "plan": {"steps": steps}}

def _receipt_path(ctx, operation_id):
    return _safe(ctx.data_root / "receipts" / f"{operation_id}.json")


def _read_receipt(path):
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        raise LifecycleError("INTERNAL", "Stored receipt is unreadable.",
                             "Inspect the receipts directory for this operation_id.")
    if not isinstance(data, dict):
        raise LifecycleError("INTERNAL", "Stored receipt is malformed.",
                             "Inspect the receipts directory for this operation_id.")
    return data


def receipt(ctx, operation_id):
    """Return the stored receipt (lifecycle or settings.apply) for an operation_id."""
    data = _read_receipt(_receipt_path(ctx, operation_id))
    if data is None:
        raise LifecycleError("RECEIPT_NOT_FOUND", "No receipt for that operation_id.",
                             "Check the operation_id, or the DATA_ROOT/receipts directory.")
    return data


def _fingerprint(action, app_root, files, purge):
    safe_files = {key: _sha256_text(value) for key, value in files.items()
                  if isinstance(key, str) and isinstance(value, str)}
    payload = {"action": action, "app_root": str(app_root), "purge": purge, "files": safe_files}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _journal(receipt_path, receipt):
    atomic_write_json(receipt_path, receipt)


def _step_key(step):
    if step.get("action") == "manifest":
        return MANIFEST_NAME
    step_id = step.get("id", "")
    return step_id.split(":", 1)[1] if ":" in step_id else step_id


def _backup(receipt, key, path):
    backup = receipt.setdefault("backup", {})
    if key in backup:
        return
    existed = path.is_file()
    backup[key] = {"existed": existed, "content": _read_text(path) if existed else None}


def _purge_data_root(ctx):
    # shortcut: removes the whole data root; the journal then re-creates
    # DATA_ROOT/receipts so the audit receipt survives. Upgrade if purge must leave
    # nothing behind.
    try:
        if ctx.data_root.exists():
            shutil.rmtree(ctx.data_root)
    except OSError as exc:
        raise LifecycleError("PERMISSION_DENIED", "The data root could not be purged.",
                             "Grant the required permission and retry.") from exc


def _execute_step(ctx, action, app_root, step, items, purge, receipt):
    kind = step.get("action")
    key = _step_key(step)
    if kind == "write":
        path, content = items[key]
        _backup(receipt, key, path)
        _atomic_write_text(path, content)
    elif kind == "remove":
        path = _safe(app_root / key)
        _backup(receipt, key, path)
        if path.is_file():
            path.unlink()
    elif kind == "manifest":
        path = _safe(app_root / MANIFEST_NAME)
        _backup(receipt, MANIFEST_NAME, path)
        if action == "uninstall":
            if path.is_file():
                path.unlink()
        else:
            previous = _load_manifest(app_root) or {}
            manifest = {"product_id": PRODUCT_ID, "product_version": __version__,
                        "installed_at": previous.get("installed_at") or _now(),
                        "files": {rel: _sha256_text(content)
                                  for rel, (_path, content) in items.items()}}
            atomic_write_json(path, manifest)
    elif kind == "purge":
        _purge_data_root(ctx)
        receipt["irreversible_applied"] = True


def _verified(action, app_root):
    state = verify(app_root)["install_state"]
    return state == "absent" if action == "uninstall" else state == "installed"


def _run(ctx, receipt_path, receipt, action, app_root, items, purge):
    receipt["status"] = "in_progress"
    _journal(receipt_path, receipt)
    done = set(receipt.get("completed", []))
    try:
        for step in receipt["steps"]:
            if step.get("id") in done:
                continue
            _execute_step(ctx, action, app_root, step, items, purge, receipt)
            receipt.setdefault("completed", []).append(step["id"])
            _journal(receipt_path, receipt)
    except LifecycleError:
        receipt["status"] = "failed"
        _journal(receipt_path, receipt)
        if receipt.get("completed"):
            raise LifecycleError("LIFECYCLE_PARTIAL", "Applied some steps, then a later step failed.",
                                 "Inspect the receipt, then lifecycle.rollback or lifecycle.repair.")
        raise
    except OSError as exc:
        receipt["status"] = "failed"
        _journal(receipt_path, receipt)
        raise LifecycleError("PERMISSION_DENIED", "A lifecycle step could not write to disk.",
                             "Grant the required permission and retry the same operation_id.") from exc
    if not _verified(action, app_root):
        receipt["status"] = "failed"
        _journal(receipt_path, receipt)
        raise LifecycleError("VERIFY_FAILED", "Post-apply verification did not pass.",
                             "Inspect the receipt's failed check and re-run lifecycle.plan.")
    receipt["status"] = "applied"
    receipt["applied_at"] = _now()
    _journal(receipt_path, receipt)
    return receipt


def apply(ctx, operation_id, action, target):
    """Execute (or journal-replay) a lifecycle plan; idempotent per operation_id."""
    _check_action(action)
    app_root = _app_root(target)
    files = target.get("files") if isinstance(target.get("files"), dict) else {}
    purge = bool(target.get("purge"))
    items = {}
    if action in ("install", "update", "repair"):
        items = {rel: (path, content) for rel, path, content in _file_targets(app_root, files)}
    fingerprint = _fingerprint(action, app_root, files, purge)
    receipt_path = _receipt_path(ctx, operation_id)
    existing = _read_receipt(receipt_path)
    if existing is not None:
        if existing.get("action") != action or existing.get("target_sha256") != fingerprint:
            raise LifecycleError("LIFECYCLE_CONFLICT",
                                 "operation_id was already used with a different action or target.",
                                 "Use a new operation_id for a different lifecycle action.")
        if existing.get("status") in ("applied", "rolled_back"):
            return existing
        steps = existing.get("steps") or _plan_steps(action, app_root, files, purge)
        existing["steps"] = steps
    else:
        steps = _plan_steps(action, app_root, files, purge)
        existing = {"operation_id": operation_id, "op": "lifecycle.apply", "action": action,
                    "target_sha256": fingerprint, "app_root": str(app_root),
                    "status": "in_progress", "started_at": _now(), "steps": steps,
                    "completed": [], "backup": {}, "irreversible_applied": False,
                    "usage": usage_zero()}
    return _run(ctx, receipt_path, existing, action, app_root, items, purge)


def _restore_step(app_root, step, backup):
    if step.get("action") == "purge":
        return
    key = _step_key(step)
    entry = backup.get(key)
    if entry is None:
        return
    path = _safe(app_root / key)
    if entry.get("existed"):
        _atomic_write_text(path, entry.get("content") or "")
    elif path.is_file():
        path.unlink()


def rollback(ctx, operation_id):
    """Reverse the applied steps of a prior lifecycle.apply in reverse order."""
    receipt_path = _receipt_path(ctx, operation_id)
    receipt = _read_receipt(receipt_path)
    if receipt is None:
        raise LifecycleError("RECEIPT_NOT_FOUND", "No receipt for that operation_id.",
                             "Check the operation_id, or the DATA_ROOT/receipts directory.")
    if receipt.get("op") != "lifecycle.apply":
        raise LifecycleError("ROLLBACK_UNAVAILABLE", "Only a lifecycle apply can be rolled back.",
                             "Point rollback at a lifecycle.apply operation_id.")
    if receipt.get("status") == "rolled_back":
        return receipt
    if receipt.get("status") not in ("applied", "in_progress", "failed"):
        raise LifecycleError("ROLLBACK_UNAVAILABLE", "Nothing to roll back.",
                             "Apply the operation before rolling it back.")
    if receipt.get("irreversible_applied"):
        raise LifecycleError("ROLLBACK_UNAVAILABLE", "An irreversible step was applied.",
                             "The plan marked the step irreversible; recover manually.")
    app_root = _app_root({"app_root": receipt.get("app_root")})
    completed = set(receipt.get("completed", []))
    backup = receipt.get("backup", {})
    for step in reversed(receipt.get("steps", [])):
        if step.get("id") in completed:
            _restore_step(app_root, step, backup)
    receipt["status"] = "rolled_back"
    receipt["rolled_back_at"] = _now()
    _journal(receipt_path, receipt)
    return receipt
