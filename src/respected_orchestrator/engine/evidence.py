"""Signed owned evidence: the per-data-root engine key (private ACL) and HMAC-signed JSON envelopes."""
import hashlib
import hmac
import json
import os

from . import winproc
from ..context import atomic_write_json, safe_path


RESTRICTED_KEYS = set()


def restrict_key(path):
    # Windows: drop inherited ACEs so only this user (not the Codex sandbox users) can read the key.
    if os.name != "nt" or path in RESTRICTED_KEYS:
        return
    user = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ['USERNAME']}".lstrip("\\")
    winproc.run([winproc.system_tool("icacls"), str(path), "/inheritance:r", "/grant:r", f"{user}:(F)"],
                   capture_output=True, check=True, timeout=30)
    RESTRICTED_KEYS.add(path)


def key_path(ctx):
    signing_key(ctx)  # makes sure it exists with its private ACL before the sandbox denies itself access
    return safe_path(ctx.data_root / ".engine-key")


def signing_key(ctx):
    path = safe_path(ctx.data_root / ".engine-key")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # Create privately, close the ACL while the file is still empty, write the secret, then publish atomically:
        # the key path never exists with secret bytes under an inherited ACL, nor half-written.
        tmp = path.with_name(f".engine-key.{os.getpid()}.{os.urandom(4).hex()}.tmp")
        descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                restrict_key(tmp)
                handle.write(os.urandom(32))
                handle.flush()
                os.fsync(handle.fileno())
            os.link(tmp, path)  # fails if another process published first: then its key wins
        except FileExistsError:
            pass
        finally:
            RESTRICTED_KEYS.discard(tmp)
            tmp.unlink(missing_ok=True)
    restrict_key(path)
    key = path.read_bytes()
    if os.name != "nt" and path.stat().st_mode & 0o077:
        path.chmod(0o600)  # POSIX only; Windows relies on the user-profile ACL of the data root
    if len(key) != 32:
        raise ValueError("Invalid engine key; preserve existing evidence")
    return key


def signature(ctx, payload):
    return hmac.new(signing_key(ctx), json.dumps(payload, sort_keys=True, ensure_ascii=True).encode(), hashlib.sha256).hexdigest()


def save_signed(ctx, path, payload):
    atomic_write_json(path, {"payload": payload, "signature": signature(ctx, payload)})


def load_signed(ctx, path):
    envelope = json.loads(safe_path(path).read_text(encoding="utf8"))
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict):
        raise ValueError("Invalid owned evidence")
    payload = envelope["payload"]
    if not hmac.compare_digest(str(envelope.get("signature", "")), signature(ctx, payload)):
        raise ValueError("Evidence tampered")
    return payload
