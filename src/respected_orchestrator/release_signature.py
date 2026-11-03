"""REL-01: fail-closed Authenticode verification and optional signing for Windows release artifacts.

Nothing is reported as signed unless PowerShell's Get-AuthenticodeSignature returns Valid, the signer subject matches
the expected identity, the certificate has not expired, and (when supplied) the expected SHA-256 still matches.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _query(path, run):
    script = ("$s = Get-AuthenticodeSignature -LiteralPath '" + str(path).replace("'", "''") + "'; "
              "$c = $s.SignerCertificate; "
              "$o = [ordered]@{Status=[string]$s.Status; Message=[string]$s.StatusMessage; "
              "Subject=if ($c) {[string]$c.Subject} else {''}; "
              "NotAfter=if ($c) {[string]$c.NotAfter.ToString('o')} else {''}}; "
              "$o | ConvertTo-Json -Compress")
    try:
        completed = (run or subprocess.run)(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                                            capture_output=True, check=False)
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    try:
        data = json.loads(completed.stdout.decode("utf-8-sig", "replace"))
    except (UnicodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def verify(path, *, expected_sha256=None, expected_signer=None, now=None, run=None):
    """Return a decision object; signed is True only for one unambiguous, current, expected signature."""
    target = Path(path)
    if not target.is_file():
        return {"signed": False, "status": "missing", "sha256": None}
    digest = sha256(target)
    if expected_sha256 and digest != str(expected_sha256).upper():
        return {"signed": False, "status": "tampered", "sha256": digest}
    if os.name != "nt":
        return {"signed": False, "status": "unsupported_platform", "sha256": digest}
    data = _query(target, run)
    if data is None:
        return {"signed": False, "status": "offline_or_unknown", "sha256": digest}
    if data.get("Status") != "Valid":
        return {"signed": False, "status": "unsigned", "sha256": digest, "detail": data.get("Message", "")}
    subject = str(data.get("Subject") or "")
    if not subject:
        return {"signed": False, "status": "unsigned", "sha256": digest}
    if expected_signer and expected_signer not in subject:
        return {"signed": False, "status": "wrong_signer", "sha256": digest, "subject": subject}
    expiry = str(data.get("NotAfter") or "")
    try:
        not_after = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    except ValueError:
        return {"signed": False, "status": "unknown_expiry", "sha256": digest, "subject": subject}
    if (now or datetime.now(timezone.utc)) >= not_after:
        return {"signed": False, "status": "cert_expired", "sha256": digest, "subject": subject}
    return {"signed": True, "status": "signed", "sha256": digest, "subject": subject, "not_after": expiry}


def sign(path, *, certificate=None, timestamp_url=None, run=None):
    """Sign with signtool from an operator-supplied cert; the key never comes from this repository."""
    certificate = certificate or os.environ.get("RESPECTED_SIGN_CERT")
    if not certificate:
        raise ValueError("RESPECTED_SIGN_CERT is not set; refusing to mark anything as signed")
    command = ["signtool", "sign", "/sha256", "/fd", "SHA256", "/f", certificate]
    password = os.environ.get("RESPECTED_SIGN_PASSWORD")
    if password:
        command += ["/p", password]
    if timestamp_url or os.environ.get("RESPECTED_SIGN_TIMESTAMP"):
        command += ["/tr", timestamp_url or os.environ["RESPECTED_SIGN_TIMESTAMP"], "/td", "SHA256"]
    completed = (run or subprocess.run)(command + [str(path)], capture_output=True, check=False)
    if completed.returncode != 0:
        raise ValueError((completed.stderr or b"").decode("utf-8", "replace").strip()[:300] or "signtool failed")
    return str(path)