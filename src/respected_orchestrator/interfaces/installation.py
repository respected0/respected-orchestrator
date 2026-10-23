"""The product's own install record: setup, repair and uninstall after (or before) the installer moved the program files.

The program folder belongs to the installer; this module records which verified build is there
(`<app>/.respected/install.json`, built from distribution.json), keeps the data root, and on uninstall takes back
the MCP registrations it made in AI clients. Confined paths only; no shell, no network.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
from stat import S_ISREG
import tempfile
import uuid

from .. import __version__
from ..context import atomic_write_json, path_within_root, safe_path
from .migrate import MigrationError, migrate_data

PRODUCT_ID = "respected-orchestrator"
RECORD_NAME = ".respected/install.json"


class OperationError(Exception):
    """Expected failure carrying the protocol error triple (code, message, hint)."""

    def __init__(self, code, message, hint=""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _safe(path):
    try:
        return safe_path(Path(path))
    except (OSError, ValueError) as exc:
        raise OperationError("BAD_REQUEST", "A path is not usable.", "Use real directories with no links/reparse points.") from exc


def _sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write_text(path, text):
    path = _safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _receipt_path(ctx, operation_id):
    return _safe(ctx.data_root / "receipts" / f"{operation_id}.json")


def _read_receipt(path):
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        raise OperationError("INTERNAL", "Stored receipt is unreadable.", "Inspect the receipts directory for this operation_id.")
    if not isinstance(data, dict):
        raise OperationError("INTERNAL", "Stored receipt is malformed.", "Inspect the receipts directory for this operation_id.")
    return data


def _distribution(app_root):
    """distribution.json's file hashes, each proven against the file on disk now."""
    try:
        files = json.loads(_safe(app_root / "distribution.json").read_text("utf-8"))["files"]
        if not isinstance(files, dict) or not files:
            raise ValueError("no files")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise OperationError("VERIFY_FAILED", "distribution.json is missing or unreadable.", "Run the installer again (Onar).") from exc
    for rel, digest in files.items():
        candidate = Path(rel)
        path = _safe(app_root / candidate)
        if candidate.is_absolute() or ".." in candidate.parts or not path_within_root(path, app_root):
            raise OperationError("VERIFY_FAILED", f"{rel} is not inside the program folder.", "Run the installer again (Onar).")
        if not isinstance(digest, str) or not path.is_file() or _sha256_file(path) != digest:
            raise OperationError("VERIFY_FAILED", f"{rel} does not match distribution.json.", "Run the installer again (Onar).")
    return dict(files)


def _record(app_root):
    path = _safe(app_root / RECORD_NAME)
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("files"), dict) else None


def verify(app_root, cache=None):
    """Read-only install state of a program folder: absent, installed or repair-needed.

    `cache` (a file in the data root) remembers size and mtime of files whose hash matched, so the next call does not hash them again.
    """
    record = _record(app_root)
    if record is None:
        return {"installed": False, "install_state": "absent"}
    try:
        seen = json.loads(cache.read_text("utf-8")) if cache else {}
    except (OSError, ValueError):
        seen = {}
    if not isinstance(seen, dict):
        seen = {}
    fresh = {}
    checked = set()  # a folder is checked for links once, not once per file (that walk was most of the cost)
    for rel, digest in record["files"].items():
        try:
            path = app_root / rel
            if path.parent not in checked:
                _safe(path.parent)
                checked.add(path.parent)
            stat = path.lstat()
            if not S_ISREG(stat.st_mode) or getattr(stat, "st_file_attributes", 0) & 0x400:
                stat = None  # missing, a link or a reparse point
            key = [stat.st_size, stat.st_mtime_ns, digest] if stat else None
            matches = key is not None and (seen.get(rel) == key or _sha256_file(path) == digest)
            if matches:
                fresh[rel] = key
        except (OSError, ValueError, OperationError):
            matches = False
        if not matches or record.get("product_version") != __version__:
            return {"installed": True, "install_state": "repair-needed"}
    if cache and fresh != seen:
        try:
            atomic_write_json(cache, fresh)
        except OSError:
            pass
    return {"installed": True, "install_state": "installed"}


def setup(ctx):
    """Record the verified program and prepare the data root; repeated it behaves as repair."""
    files = _distribution(ctx.app_root)
    previous = _record(ctx.app_root) or {}
    ctx.data_root.mkdir(parents=True, exist_ok=True)
    try:
        migrate_data(ctx.data_root)  # an update moves old-format data first
    except MigrationError as error:
        raise OperationError("DATA_FORMAT", str(error), "Ayrıntı için mesaja bakın; veri dosyasına dokunulmadı.") from error
    atomic_write_json(_safe(ctx.app_root / RECORD_NAME), {"product_id": PRODUCT_ID, "product_version": __version__,
                                                         "installed_at": previous.get("installed_at") or _now(),
                                                         "files": files, "distribution": True})
    return {"status": "installed", "product_version": __version__, "app_root": str(ctx.app_root), "data_root": str(ctx.data_root)}


def repair(ctx):
    """Re-verify the program the installer laid down (new or the same version) and rewrite the record."""
    if _record(ctx.app_root) is None:
        raise OperationError("NOT_INSTALLED", "There is no install record to repair.", "Run the installer.")
    return {**setup(ctx), "status": "repaired"}


def uninstall(ctx, *, purge=False):
    """Take back owned MCP registrations, drop the install record and, with purge, the data root. Never the program files."""
    from . import integrations
    conflicts = []
    owned = integrations._owned(ctx)
    if owned:
        desired = {client: False for client in owned}
        try:
            planned = integrations.plan(ctx, {"desired": desired})
            integrations.apply(ctx, "uninstall-" + uuid.uuid4().hex[:16], {"desired": desired, "plan_digest": planned["plan_digest"]})
        except OperationError as error:  # an entry the user edited stays; the rest of the removal goes on
            conflicts.append(error.message)
    record = _safe(ctx.app_root / RECORD_NAME)
    if record.is_file():
        record.unlink()
    if purge and ctx.data_root.exists():
        try:
            shutil.rmtree(ctx.data_root)
        except OSError as exc:
            raise OperationError("PERMISSION_DENIED", "The data root could not be deleted.", "Close running tasks and retry.") from exc
    return {"status": "removed" if not conflicts else "removed_with_conflicts", "purged": purge, "conflicts": conflicts}
