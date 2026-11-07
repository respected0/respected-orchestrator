"""Screenshot-to-task attachments, engine side (B4-07): capture is the person's act, sharing with a model is a second, separate decision.

Three layers, each refusing by default:
  CaptureSession  `screenshot_enabled` (off by default) + OS permission + a person pressing capture arms it; an image can be submitted
                  only while armed; cancel, a wrong token or a failed check discards it. There is no call that captures on its own,
                  so background capture does not exist.
  attach          the image is inspected (PNG or JPEG only, size and pixel limits, malformed structure refused), its metadata is stripped
                  (PNG ancillary chunks, JPEG EXIF/XMP/comment), the person must have previewed THESE exact bytes (digest bound) and be human,
                  and it is stored only under the run it is attached to, as a file plus a signed envelope. It is `task_only` and
                  `shared_with_model: false`.
  share           showing an attachment to a model needs its own consent record (provider, expiry, bound to the attachment digest and the run).
                  `bytes_for_model` re-checks the consent on every read, so a revoke, an expiry, another provider or another run stops it at once.
Redaction (drawing over secrets) happens in the interface before the preview; the engine binds the previewed bytes by digest and records
how many regions the person masked, but cannot see pixels it does not decode. Nothing here sends anything anywhere."""
import hashlib
import secrets
import shutil
import struct
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..context import EngineContext, safe_path
from .authority import Action, Origin, authorize
from .evidence import load_signed, save_signed

MAX_BYTES, MAX_SIDE, MAX_PIXELS = 8 * 1024 * 1024, 8192, 36_000_000
TTL_SECONDS = 24 * 3600
CONSENT_SECONDS = 600
PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_KEEP = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS"}
GRANTED = "granted"


class AttachError(PermissionError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


# ---------------------------------------------------------------------------------------------------------------- image checks
def _png(data: bytes) -> tuple[int, int, bytes]:
    pos, size, width, height, out, seen_idat, ended = len(PNG_SIG), len(data), 0, 0, bytearray(PNG_SIG), False, False
    first = True
    while pos + 12 <= size:
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body_end = data[pos + 4:pos + 8], pos + 8 + length
        if body_end + 4 > size or length > size:
            raise AttachError("MALFORMED", "PNG chunk runs past the end of the file")
        if first:
            if kind != b"IHDR" or length != 13:
                raise AttachError("MALFORMED", "PNG must start with a 13-byte IHDR")
            width, height = struct.unpack(">II", data[pos + 8:pos + 16])
            first = False
        seen_idat |= kind == b"IDAT"
        if kind in _PNG_KEEP:
            out += data[pos:body_end + 4]  # critical chunks only: text, EXIF, time, colour profile and every private chunk are dropped
        pos = body_end + 4
        if kind == b"IEND":
            ended = True
            break
    if first or not seen_idat or not ended:
        raise AttachError("MALFORMED", "PNG has no image data or no end marker")
    return width, height, bytes(out)


def _jpeg(data: bytes) -> tuple[int, int, bytes]:
    out, pos, size, width, height = bytearray(b"\xff\xd8"), 2, len(data), 0, 0
    while pos + 4 <= size:
        if data[pos] != 0xFF:
            raise AttachError("MALFORMED", "JPEG segment marker expected")
        marker = data[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker == 0xD9:
            out += b"\xff\xd9"
            if not width:
                raise AttachError("MALFORMED", "JPEG has no frame header")
            return width, height, bytes(out)
        (length,) = struct.unpack(">H", data[pos + 2:pos + 4])
        end = pos + 2 + length
        if length < 2 or end > size:
            raise AttachError("MALFORMED", "JPEG segment runs past the end of the file")
        if marker in (0xC0, 0xC1, 0xC2) and length >= 8:
            height, width = struct.unpack(">HH", data[pos + 5:pos + 9])
        if marker == 0xDA:  # start of scan: entropy-coded data follows to the end marker, copied verbatim
            out += data[pos:]
            if not width or not data.rstrip(b"\x00").endswith(b"\xff\xd9"):
                raise AttachError("MALFORMED", "JPEG has no frame header or no end marker")
            return width, height, bytes(out)
        if not (0xE1 <= marker <= 0xEF or marker == 0xFE):  # drop APP1..APP15 (EXIF, XMP, ICC, ...) and comments; keep the rest incl. JFIF APP0
            out += data[pos:end]
        pos = end
    raise AttachError("MALFORMED", "JPEG ended before an image was found")


def inspect(data: Any) -> dict[str, Any]:
    """{mime, width, height, clean (metadata-stripped bytes), sha256}. Raises AttachError for anything that is not a sane PNG/JPEG."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise AttachError("EMPTY", "no image data")
    data = bytes(data)
    if len(data) > MAX_BYTES:
        raise AttachError("TOO_LARGE", f"images are limited to {MAX_BYTES // (1024 * 1024)} MB")
    if data.startswith(PNG_SIG):
        mime, (width, height, clean) = "image/png", _png(data)
    elif data.startswith(b"\xff\xd8\xff"):
        mime, (width, height, clean) = "image/jpeg", _jpeg(data)
    else:
        raise AttachError("BAD_FORMAT", "only PNG and JPEG images are accepted (SVG, GIF, WebP, BMP, PDF and anything else are refused)")
    if not (0 < width <= MAX_SIDE and 0 < height <= MAX_SIDE and width * height <= MAX_PIXELS):
        raise AttachError("TOO_BIG", f"image is {width}x{height}; the limit is {MAX_SIDE}px a side and {MAX_PIXELS // 1_000_000} megapixels")
    return {"mime": mime, "width": width, "height": height, "clean": clean, "sha256": hashlib.sha256(clean).hexdigest(), "metadata_removed": len(data) - len(clean)}


# ------------------------------------------------------------------------------------------------------------------ capturing
class CaptureSession:
    """Armed by a person's click, valid for one image. States: idle -> armed -> idle."""

    def __init__(self, settings: Mapping[str, Any], permission: Callable[[], str], *, clock: Callable[[], float] = time.monotonic, window: float = 120.0):
        self._settings, self._permission, self._clock, self._window = settings, permission, clock, window
        self.state, self._token, self._armed_at = "idle", None, 0.0
        self.images_held = 0  # a capture is inspected and returned, never kept by the session
        self.closed_reason: str | None = None

    def arm(self) -> str:
        if not self._settings.get("screenshot_enabled"):
            raise AttachError("CAPTURE_OFF", "screenshot capture is switched off in the settings")
        if self.state != "idle":
            raise AttachError("BUSY", "a capture is already in progress")
        permission = self._permission()
        if permission != GRANTED:
            raise AttachError("NO_PERMISSION", f"screen capture permission is {permission}; nothing was captured")
        self.state, self._token, self._armed_at, self.closed_reason = "armed", secrets.token_hex(8), self._clock(), None
        return self._token

    def cancel(self, reason: str = "cancelled") -> None:
        self.state, self._token, self.closed_reason = "idle", None, reason

    def submit(self, token: str, image: bytes, meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """The OS/interface hands over what the person selected. Returns the inspected image or discards it and raises."""
        if self.state != "armed" or token != self._token:
            raise AttachError("NOT_ARMED", "an image arrived without the person starting a capture; it was dropped")
        try:
            if self._clock() - self._armed_at > self._window:
                raise AttachError("EXPIRED", "the capture window closed; capture again")
            if not self._settings.get("screenshot_enabled") or self._permission() != GRANTED:
                raise AttachError("PERMISSION_REVOKED", "capture was switched off or permission was revoked; the image was discarded")
            meta = dict(meta or {})
            if meta.get("monitor") is not None and (type(meta["monitor"]) is not int or not 0 <= meta["monitor"] < 16):
                raise AttachError("BAD_META", "monitor must be a small integer index")
            if meta.get("dpi_scale") is not None and (not isinstance(meta["dpi_scale"], (int, float)) or isinstance(meta["dpi_scale"], bool) or not 0.5 <= meta["dpi_scale"] <= 6):
                raise AttachError("BAD_META", "dpi_scale must be between 0.5 and 6")
            info = inspect(image)
            return {**info, "monitor": meta.get("monitor"), "dpi_scale": meta.get("dpi_scale")}
        except AttachError as error:
            self.cancel(error.code.lower())
            raise
        finally:
            if self.state == "armed":
                self.cancel("submitted")  # one image per press, whatever happened


# ------------------------------------------------------------------------------------------------------------------ attaching
def _dir(ctx: EngineContext, run_id: str) -> Path:
    return safe_path(ctx.run_dir(run_id) / "attachments")


def _env(ctx: EngineContext, run_id: str, att_id: str) -> dict[str, Any]:
    if not isinstance(att_id, str) or not att_id.startswith("att-") or not att_id[4:].isalnum() or len(att_id) != 20:
        raise AttachError("BAD_ID", "invalid attachment id")
    try:
        return load_signed(ctx, _dir(ctx, run_id) / f"{att_id}.json")
    except (OSError, ValueError) as error:
        raise AttachError("NOT_FOUND", "no such attachment on this run (or its record does not verify)") from error


def attach(ctx: EngineContext, run_id: str, image: bytes, previewed_sha256: str, *, origin: Origin, redacted_regions: int = 0, now: float | None = None) -> dict[str, Any]:
    """Store an image on one queued run. `previewed_sha256` must be the digest of the cleaned bytes the person actually looked at."""
    authorize(origin, Action.PRIVILEGED)
    info = inspect(image)
    if previewed_sha256 != info["sha256"]:
        raise AttachError("PREVIEW_REQUIRED", "the attached image is not the one that was previewed; preview it first")
    if type(redacted_regions) is not int or not 0 <= redacted_regions <= 200:
        raise AttachError("BAD_META", "redacted_regions must be a small count")
    try:
        directory = ctx.run_dir(run_id)
        status = load_signed(ctx, directory / "status.json")
    except (OSError, ValueError) as error:
        raise AttachError("WRONG_RUN", "that run does not exist or cannot be read") from error
    if status.get("status") != "queued":
        raise AttachError("WRONG_RUN", "an image can only be attached to a run that has not started")
    att_id = "att-" + secrets.token_hex(8)
    target = _dir(ctx, run_id)
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{att_id}.bin").write_bytes(info["clean"])
    stamp = time.time() if now is None else now
    record = {"id": att_id, "run_id": run_id, "mime": info["mime"], "bytes": len(info["clean"]), "sha256": info["sha256"], "width": info["width"],
              "height": info["height"], "metadata_removed_bytes": info["metadata_removed"], "redacted_regions": redacted_regions, "created_at": stamp,
              "expires_at": stamp + TTL_SECONDS, "visibility": "task_only", "shared_with_model": False}
    save_signed(ctx, target / f"{att_id}.json", record)
    return {k: v for k, v in record.items()}


def read_for_person(ctx: EngineContext, run_id: str, att_id: str, *, origin: Origin, now: float | None = None) -> tuple[dict[str, Any], bytes]:
    """The preview path: a human (or the interface acting for one) reads the stored image. Never an evidence, log or model path."""
    authorize(origin, Action.READ)
    if origin in (Origin.WORKER, Origin.CHILD):
        raise AttachError("NOT_ALLOWED", "attachments are not visible to workers")
    record = _env(ctx, run_id, att_id)
    if (time.time() if now is None else now) > record["expires_at"]:
        raise AttachError("EXPIRED", "the attachment expired and is purged on the next sweep")
    data = (_dir(ctx, run_id) / f"{att_id}.bin").read_bytes()
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise AttachError("TAMPERED", "the stored image no longer matches its record")
    return record, data


def purge(ctx: EngineContext, run_id: str) -> int:
    """Delete every attachment and consent of a run. Returns how many files were removed."""
    directory = _dir(ctx, run_id)
    if not directory.exists():
        return 0
    count = sum(1 for _ in directory.iterdir())
    shutil.rmtree(directory)
    return count


def sweep(ctx: EngineContext, *, now: float | None = None) -> int:
    """Remove expired attachments from every run (TTL retention)."""
    removed, stamp = 0, time.time() if now is None else now
    for directory in (ctx.data_root / "state").glob("run-*/attachments"):
        for envelope in directory.glob("att-*.json"):
            try:
                record = load_signed(ctx, envelope)
            except (OSError, ValueError):
                record = {"expires_at": 0}  # an unreadable or tampered record is treated as expired
            if stamp > record.get("expires_at", 0):
                for path in (envelope, envelope.with_suffix(".bin"), directory / f"{envelope.stem}.consent.json"):
                    if path.exists():
                        path.unlink()
                        removed += 1
    return removed


# --------------------------------------------------------------------------------------------------------------- model transfer
def share(ctx: EngineContext, run_id: str, att_id: str, provider: str, *, origin: Origin, now: float | None = None) -> dict[str, Any]:
    """A person agrees that THIS image, of THIS run, may be shown to ONE named provider for a short time."""
    authorize(origin, Action.PRIVILEGED)
    record = _env(ctx, run_id, att_id)
    if not isinstance(provider, str) or not provider.strip() or len(provider) > 80:
        raise AttachError("BAD_PROVIDER", "name the provider that will receive the image")
    stamp = time.time() if now is None else now
    consent = {"attachment": att_id, "run_id": run_id, "sha256": record["sha256"], "provider": provider.strip(), "granted_at": stamp,
               "expires_at": min(stamp + CONSENT_SECONDS, record["expires_at"]), "revoked": False,
               "disclosure": f"This image will be sent to {provider.strip()}, outside this computer, and may be kept by them."}
    save_signed(ctx, _dir(ctx, run_id) / f"{att_id}.consent.json", consent)
    return consent


def revoke(ctx: EngineContext, run_id: str, att_id: str, *, origin: Origin) -> None:
    authorize(origin, Action.PRIVILEGED)
    path = _dir(ctx, run_id) / f"{att_id}.consent.json"
    if path.exists():
        save_signed(ctx, path, {**load_signed(ctx, path), "revoked": True})


def bytes_for_model(ctx: EngineContext, run_id: str, att_id: str, provider: str, *, now: float | None = None) -> bytes:
    """What a worker adapter must call before it puts an image into a request. Re-checked on every call."""
    record = _env(ctx, run_id, att_id)
    try:
        consent = load_signed(ctx, _dir(ctx, run_id) / f"{att_id}.consent.json")
    except (OSError, ValueError) as error:
        raise AttachError("NO_CONSENT", "the person has not agreed to share this image with a model") from error
    stamp = time.time() if now is None else now
    if consent.get("revoked"):
        raise AttachError("REVOKED", "sharing was revoked")
    if stamp > consent["expires_at"] or stamp > record["expires_at"]:
        raise AttachError("EXPIRED", "the sharing consent expired")
    if consent["provider"] != provider or consent["run_id"] != run_id or consent["sha256"] != record["sha256"]:
        raise AttachError("CONSENT_MISMATCH", "the consent is for another provider, run or image")
    data = (_dir(ctx, run_id) / f"{att_id}.bin").read_bytes()
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise AttachError("TAMPERED", "the stored image no longer matches its record")
    return data
