"""Read-only, bounded access to one run's own evidence files (B3-06.02).

The UI never names a path: it names a file the engine itself listed for that run (a plain file name, or `artifacts/<name>`),
and gets back at most MAX_CHUNK bytes at a time, redacted and stripped of terminal control codes. Links, reparse points,
anything outside the run directory and anything not in the listing are refused. Each chunk read is recorded in the event
journal together with the file's digest, so an audit can say exactly what was shown.
"""
from __future__ import annotations

import hashlib
import re
from uuid import uuid4

from ..context import safe_path
from ..interfaces import evidence_view
from . import activity
from .journal import Journal

MAX_CHUNK = 64 * 1024
DIGEST_LIMIT = 32 * 1024 * 1024  # bigger files are shown without a digest ("unknown"), never with a guessed one
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
_KINDS = {".json": "evidence", ".log": "log", ".patch": "patch", ".txt": "text", ".md": "text", ".png": "image", ".jpg": "image", ".jpeg": "image",
          ".webp": "image", ".gif": "image"}
_LOOK = 512  # bytes inspected on each side of a chunk so a secret cut by the boundary is still recognised
_PATTERNS = tuple(re.compile(p) for p in (
    rb"(?i)(?:api[_-]?key|authorization\s*[:=]\s*bearer|token|password|secret)\s*[:=]\s*(\S+)",
    rb"(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._~+/=-]{12,})",
))
_HIDDEN = {"applying"}  # claims and locks are control files, not evidence


def _kind(name):
    dot = name.rfind(".")
    return _KINDS.get(name[dot:].lower()) if dot > 0 else None


def _run_dir(ctx, run_id):
    directory = safe_path(ctx.run_dir(run_id))
    if not directory.is_dir():
        raise ValueError("Unknown run")
    return directory


def _listing(directory):
    """name -> path for the files this view may open. A name that is not here does not exist for the caller."""
    found = {}
    for path in sorted(directory.iterdir()):
        if path.is_file() and not path.is_symlink() and _NAME.fullmatch(path.name) and path.name not in _HIDDEN and _kind(path.name):
            found[path.name] = path
    sub = directory / "artifacts"
    if sub.is_dir() and not sub.is_symlink():
        for path in sorted(sub.iterdir()):
            if path.is_file() and not path.is_symlink() and _NAME.fullmatch(path.name) and _kind(path.name):
                found[f"artifacts/{path.name}"] = path
    return found


def _mask(window, env_secrets):
    """Same-length masking of secret values in raw bytes, so byte offsets inside the window stay valid."""
    out = bytearray(window)
    for pattern in _PATTERNS:
        for m in pattern.finditer(window):
            a, b = m.span(m.lastindex or 0)
            out[a:b] = b"*" * (b - a)
    for secret in env_secrets:
        raw = secret.encode()
        start = window.find(raw)
        while start != -1:
            out[start:start + len(raw)] = b"*" * len(raw)
            start = window.find(raw, start + 1)
    return bytes(out)


def _digest(path, size):
    if size > DIGEST_LIMIT:
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def list_artifacts(ctx, run_id):
    directory = _run_dir(ctx, run_id)
    out = []
    for name, path in _listing(directory).items():
        try:
            safe_path(path)
            size = path.stat().st_size
        except (OSError, ValueError):
            continue  # a file that turned into a link or vanished is simply not offered
        out.append({"name": name, "kind": _kind(name), "size": size})
    return {"run_id": run_id, "artifacts": out}


def read_chunk(ctx, run_id, name, offset=0, length=MAX_CHUNK, *, journal=None):
    if type(offset) is not int or type(length) is not int or offset < 0 or length < 1:
        raise ValueError("offset and length must be positive integers")
    length = min(length, MAX_CHUNK)
    directory = _run_dir(ctx, run_id)
    path = _listing(directory).get(name) if isinstance(name, str) else None
    if path is None:
        raise ValueError("Not an artifact of this run")
    path = safe_path(path)  # refuses links/reparse points, also if the file changed since it was listed
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Not an artifact of this run")
    size = path.stat().st_size
    lead = min(offset, _LOOK)
    with path.open("rb") as handle:
        handle.seek(offset - lead)
        window = handle.read(lead + length + _LOOK)
    window = _mask(window, evidence_view._secret_values())
    raw = window[lead:lead + length]
    if offset + len(raw) < size and len(raw) == length:  # cut at a line end when there is one
        cut = raw.rfind(b"\n")
        if cut > 0:
            raw = raw[:cut + 1]
    next_offset = offset + len(raw)
    eof = next_offset >= size
    kind = _kind(name)
    binary = kind == "image" or b"\x00" in raw
    content = None if binary else activity.clean(evidence_view._clean(raw.decode("utf8", errors="replace"), evidence_view._secret_values()), limit=MAX_CHUNK * 2)
    digest = _digest(path, size)  # of the real file, not of what was shown
    (journal or Journal(ctx.state_dir / "events.log")).append(
        f"artifact-{uuid4().hex}", "artifact.read", run_id,
        {"name": name, "offset": offset, "bytes": len(raw), "size": size, "sha256": digest})
    return {"run_id": run_id, "name": name, "kind": kind, "size": size, "offset": offset, "next_offset": next_offset, "eof": eof,
            "binary": binary, "content": content, "sha256": digest}
