"""IPC face of screenshot attachments (B4-07).

Flow, each step a separate act of the person:
  arm (a click, `screenshot_enabled` on, OS/browser permission) -> part* (the chosen image, in chunks) -> stage (inspect + strip metadata, kept in a
  short-lived staging file) -> preview (the engine's cleaned bytes, which are what gets attached) -> commit (HUMAN connection only, after the native
  dialog; binds the digest the person previewed) -> later, share with a model (a second HUMAN decision) or delete.
The renderer can do arm/part/stage/preview/cancel/delete; commit, share and revoke need the native presence connection (authority.PRIVILEGED).
The staging file is deleted on commit, cancel, expiry and the next sweep; images never reach evidence, journals or events."""
import base64
import binascii
import hashlib
import re
import secrets
import time
from collections.abc import Callable
from typing import Any

from ..context import EngineContext, safe_path
from . import attachment
from .authority import Origin
from .evidence import load_signed, save_signed

MAX_CHUNK_BYTES = 48 * 1024
STAGE_SECONDS = 600
_STAGE = re.compile(r"stg-[0-9a-f]{16}")
_RUN = re.compile(r"run-\d{14}-[0-9a-f]{12}")


def _stage_dir(ctx: EngineContext):
    return safe_path(ctx.data_root / "staging")


def sweep_staging(ctx: EngineContext, now: float | None = None) -> int:
    stamp, removed = time.time() if now is None else now, 0
    for meta in _stage_dir(ctx).glob("stg-*.json"):
        try:
            expired = stamp > load_signed(ctx, meta)["expires_at"]
        except (OSError, ValueError, KeyError):
            expired = True
        if expired:
            for path in (meta, meta.with_suffix(".bin")):
                if path.exists():
                    path.unlink()
                    removed += 1
    return removed


def _load_stage(ctx: EngineContext, stage_id: Any, now: float | None = None) -> tuple[dict[str, Any], bytes]:
    if not isinstance(stage_id, str) or not _STAGE.fullmatch(stage_id):
        raise attachment.AttachError("BAD_ID", "invalid staged image id")
    try:
        meta = load_signed(ctx, _stage_dir(ctx) / f"{stage_id}.json")
        data = (_stage_dir(ctx) / f"{stage_id}.bin").read_bytes()
    except (OSError, ValueError) as error:
        raise attachment.AttachError("NOT_FOUND", "that staged image does not exist (any more)") from error
    if (time.time() if now is None else now) > meta["expires_at"]:
        raise attachment.AttachError("EXPIRED", "the staged image expired; choose it again")
    if hashlib.sha256(data).hexdigest() != meta["sha256"]:
        raise attachment.AttachError("TAMPERED", "the staged image no longer matches its record")
    return meta, data


def _drop_stage(ctx: EngineContext, stage_id: str) -> None:
    for suffix in (".json", ".bin"):
        path = _stage_dir(ctx) / f"{stage_id}{suffix}"
        if path.exists():
            path.unlink()


class AttachApi:
    def __init__(self, ctx: EngineContext, read_settings: Callable[[], dict[str, Any]]):
        self.ctx, self._read = ctx, read_settings
        self._settings: dict[str, Any] = {}
        self._permission = "unknown"
        self.session = attachment.CaptureSession(self._settings, lambda: self._permission)
        self._token: str | None = None
        self._buffer = bytearray()
        self._seq = 0

    def _refresh(self, permission: Any = None) -> None:
        self._settings.clear()
        self._settings["screenshot_enabled"] = self._read().get("screenshot_enabled") is True
        if permission is not None:
            self._permission = permission if permission in (attachment.GRANTED, "denied") else "unknown"

    def _reset(self) -> None:
        self._buffer[:] = bytes(len(self._buffer))
        self._buffer.clear()
        self._token, self._seq = None, 0

    def status(self) -> dict[str, Any]:
        self._refresh()
        return {"enabled": bool(self._settings["screenshot_enabled"]), "state": self.session.state, "held": len(self._buffer), "max_bytes": attachment.MAX_BYTES,
                "max_side": attachment.MAX_SIDE, "chunk_bytes": MAX_CHUNK_BYTES, "stage_seconds": STAGE_SECONDS}

    def arm(self, permission: Any) -> dict[str, Any]:
        self._refresh(permission)
        self._reset()
        self._token = self.session.arm()
        return {"token": self._token, "chunk_bytes": MAX_CHUNK_BYTES}

    def part(self, token: Any, seq: Any, chunk: Any) -> dict[str, Any]:
        if self.session.state != "armed" or token != self._token:
            self._reset()
            raise attachment.AttachError("NOT_ARMED", "an image arrived without the person starting a capture; it was dropped")
        try:
            data = base64.b64decode(chunk, validate=True) if isinstance(chunk, str) else None
        except (binascii.Error, ValueError):
            data = None
        if data is None or type(seq) is not int or seq != self._seq or len(data) > MAX_CHUNK_BYTES or len(self._buffer) + len(data) > attachment.MAX_BYTES:
            self.session.cancel("bad_part")
            self._reset()
            raise attachment.AttachError("BAD_PART", "the image upload was malformed or too large; it was discarded")
        self._buffer.extend(data)
        self._seq += 1
        return {"held": len(self._buffer)}

    def stage(self, token: Any, monitor: Any = None, dpi_scale: Any = None) -> dict[str, Any]:
        self._refresh()
        image = bytes(self._buffer)
        token = token if token == self._token else ""
        self._reset()
        info = self.session.submit(token, image, {"monitor": monitor, "dpi_scale": dpi_scale})
        sweep_staging(self.ctx)
        stage_id, now = "stg-" + secrets.token_hex(8), time.time()
        directory = _stage_dir(self.ctx)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{stage_id}.bin").write_bytes(info["clean"])
        save_signed(self.ctx, directory / f"{stage_id}.json", {"id": stage_id, "sha256": info["sha256"], "mime": info["mime"], "width": info["width"], "height": info["height"],
                                                               "bytes": len(info["clean"]), "created_at": now, "expires_at": now + STAGE_SECONDS})
        return {"stage_id": stage_id, "sha256": info["sha256"], "mime": info["mime"], "width": info["width"], "height": info["height"], "bytes": len(info["clean"]),
                "metadata_removed_bytes": info["metadata_removed"], "expires_in": STAGE_SECONDS}

    def preview(self, stage_id: Any) -> dict[str, Any]:
        meta, data = _load_stage(self.ctx, stage_id)
        return {"stage_id": meta["id"], "sha256": meta["sha256"], "mime": meta["mime"], "width": meta["width"], "height": meta["height"], "data": base64.b64encode(data).decode()}

    def describe(self, stage_id: Any) -> dict[str, Any]:
        meta, _ = _load_stage(self.ctx, stage_id)
        return {k: meta[k] for k in ("id", "sha256", "mime", "width", "height", "bytes")}

    def cancel(self, stage_id: Any = None) -> dict[str, Any]:
        self.session.cancel("cancelled")
        self._reset()
        if isinstance(stage_id, str) and _STAGE.fullmatch(stage_id):
            _drop_stage(self.ctx, stage_id)
        return {"state": self.session.state, "held": 0}

    def records(self, run_id: Any) -> dict[str, Any]:
        if not isinstance(run_id, str) or not _RUN.fullmatch(run_id):
            raise attachment.AttachError("WRONG_RUN", "a valid run id is required")
        out = []
        folder = attachment._dir(self.ctx, run_id)
        for envelope in sorted(p for p in folder.glob("att-*.json") if not p.name.endswith(".consent.json")) if folder.exists() else []:
            try:
                record = load_signed(self.ctx, envelope)
            except (OSError, ValueError):
                continue
            consent = {"state": "none"}
            path = envelope.with_name(f"{envelope.stem}.consent.json")
            if path.exists():
                try:
                    c = load_signed(self.ctx, path)
                    state = "revoked" if c.get("revoked") else "expired" if time.time() > c["expires_at"] else "active"
                    consent = {"state": state, "provider": c["provider"], "expires_at": c["expires_at"]}
                except (OSError, ValueError, KeyError):
                    consent = {"state": "unreadable"}
            out.append({k: record[k] for k in ("id", "run_id", "mime", "bytes", "sha256", "width", "height", "redacted_regions", "expires_at", "visibility", "shared_with_model")} | {"consent": consent})
        return {"run_id": run_id, "attachments": out}

    def delete_run(self, run_id: Any) -> dict[str, Any]:
        if not isinstance(run_id, str) or not _RUN.fullmatch(run_id):
            raise attachment.AttachError("WRONG_RUN", "a valid run id is required")
        return {"removed": attachment.purge(self.ctx, run_id)}


# ---------------------------------------------------------------------------------------------------- human-only (native presence connection)
def commit(ctx: EngineContext, stage_id: Any, run_id: Any, sha256: Any, redacted_regions: Any, origin: Origin) -> dict[str, Any]:
    meta, data = _load_stage(ctx, stage_id)
    if sha256 != meta["sha256"]:
        raise attachment.AttachError("PREVIEW_REQUIRED", "the image changed since it was previewed; preview it again")
    record = attachment.attach(ctx, run_id, data, sha256, origin=origin, redacted_regions=redacted_regions)
    _drop_stage(ctx, meta["id"])
    return record


def share(ctx: EngineContext, run_id: Any, att_id: Any, provider: Any, origin: Origin) -> dict[str, Any]:
    return attachment.share(ctx, run_id, att_id, provider, origin=origin)


def revoke(ctx: EngineContext, run_id: Any, att_id: Any, origin: Origin) -> dict[str, Any]:
    attachment.revoke(ctx, run_id, att_id, origin=origin)
    return {"revoked": True}
