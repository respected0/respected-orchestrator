"""Human approval protocol for the privileged apply (B3-05.02).

Three steps, each its own call:
  open_challenge  (TASK: the renderer or MCP may *ask* for an approval; only an approvable run gets a challenge)
  decide          (PRIVILEGED = HUMAN only: the native presence service reports what the person chose in its own dialog)
  consume/apply   (PRIVILEGED: the single-use decision token is burned, the run is re-verified, then applied)

Every state change is claimed with an exclusive file create first, so a replay or a race can never take a second path.
Anything that goes wrong after a claim burns it: the person has to approve again. A denial, an expiry or a refusal
writes no change to the project.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time

from ..context import safe_path
from .authority import Action, authorize
from .evidence import load_signed, save_signed
from . import review_model, runner

TTL_SECONDS = 120
_CHALLENGE_PREFIX = "chal-"


def _dir(ctx):
    directory = safe_path(ctx.data_root / "approvals")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _challenge_path(ctx, challenge_id):
    if not (isinstance(challenge_id, str) and len(challenge_id) == 21 and challenge_id.startswith(_CHALLENGE_PREFIX)
            and all(c in "0123456789abcdef" for c in challenge_id[5:])):
        raise ValueError("Invalid challenge identity")
    return _dir(ctx) / f"{challenge_id}.json"


def binding_of(run_id, patch_sha256, project_fingerprint, challenge_id):
    """What the person is shown, as one digest. The dialog echoes it back; a decision about anything else cannot match."""
    return hashlib.sha256("\n".join((run_id, patch_sha256, project_fingerprint, challenge_id)).encode()).hexdigest()


def _claim(path):
    """Exclusive create: exactly one caller ever succeeds for a given path."""
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


def _summary(challenge):
    keys = ("challenge_id", "run_id", "patch_sha256", "project_fingerprint", "files", "binding", "checked_at", "expires_at")
    return {k: challenge[k] for k in keys}


def open_challenge(ctx, run_id, *, origin):
    authorize(origin, Action.TASK)
    review = review_model.review_dto(ctx, run_id)
    if not review["approvable"]:
        raise ValueError("Run is not approvable: " + ", ".join(f["kind"] for f in review["blockers"]))
    challenge_id = _CHALLENGE_PREFIX + secrets.token_hex(8)
    patch, fingerprint = review["patch"]["sha256"], review["fingerprints"]["project_now"]
    challenge = {"challenge_id": challenge_id, "run_id": run_id, "patch_sha256": patch, "project_fingerprint": fingerprint,
                 "files": [f["path"] for f in review["patch"]["files"]], "checked_at": review["checked_at"],
                 "expires_at": time.time() + TTL_SECONDS, "binding": binding_of(run_id, patch, fingerprint, challenge_id)}
    save_signed(ctx, _challenge_path(ctx, challenge_id), challenge)
    return _summary(challenge)


def _record(ctx, challenge_id, state, **extra):
    save_signed(ctx, _dir(ctx) / f"{challenge_id}.decision.json", {"challenge_id": challenge_id, "state": state, "at": time.time(), **extra})


def decide(ctx, challenge_id, decision, binding, *, origin):
    """Only the native presence service (HUMAN) gets here. `decision` is what the person chose in the native dialog."""
    authorize(origin, Action.PRIVILEGED)
    path = _challenge_path(ctx, challenge_id)
    challenge = load_signed(ctx, path)
    if decision not in ("approve", "deny"):
        raise ValueError("decision must be 'approve' or 'deny'")
    if not _claim(path.with_suffix(".decided")):
        raise ValueError("This challenge was already decided")  # replay or race: the second caller changes nothing
    if time.time() > challenge["expires_at"]:
        _record(ctx, challenge_id, "expired")
        raise ValueError("Challenge expired; ask again")
    if binding != challenge["binding"]:
        _record(ctx, challenge_id, "refused", reason="binding_mismatch")
        raise ValueError("The decision is not about this run and patch")
    if decision == "deny":
        _record(ctx, challenge_id, "denied")
        return {"challenge_id": challenge_id, "state": "denied"}
    now = review_model.review_dto(ctx, challenge["run_id"])  # the patch or project may have moved while the dialog was open
    if (not now["approvable"] or now["patch"]["sha256"] != challenge["patch_sha256"]
            or now["fingerprints"]["project_now"] != challenge["project_fingerprint"]):
        _record(ctx, challenge_id, "refused", reason="stale")
        raise ValueError("The run changed since it was shown; nothing was approved")
    token = secrets.token_hex(32)
    expires = time.time() + TTL_SECONDS
    save_signed(ctx, _grant_path(ctx, token), {"challenge_id": challenge_id, "run_id": challenge["run_id"],
                                              "patch_sha256": challenge["patch_sha256"],
                                              "project_fingerprint": challenge["project_fingerprint"], "expires_at": expires})
    _record(ctx, challenge_id, "granted")
    return {"challenge_id": challenge_id, "state": "granted", "token": token, "expires_at": expires}


def _grant_path(ctx, token):
    if not (isinstance(token, str) and len(token) == 64 and all(c in "0123456789abcdef" for c in token)):
        raise ValueError("Invalid decision token")
    return _dir(ctx) / f"grant-{hashlib.sha256(token.encode()).hexdigest()[:32]}.json"  # the token itself is never stored


def consume(ctx, token, run_id, *, origin):
    """Burn the token (single use) and prove it still describes this exact run, patch and project state."""
    authorize(origin, Action.PRIVILEGED)
    path = _grant_path(ctx, token)
    if not path.is_file():
        raise ValueError("Unknown decision token")
    if not _claim(path.with_suffix(".used")):
        raise ValueError("Decision token already used")
    grant = load_signed(ctx, path)
    if grant["run_id"] != run_id:
        raise ValueError("Decision token belongs to another run")
    if time.time() > grant["expires_at"]:
        raise ValueError("Decision token expired")
    now = review_model.review_dto(ctx, run_id)
    if (not now["approvable"] or now["patch"]["sha256"] != grant["patch_sha256"]
            or now["fingerprints"]["project_now"] != grant["project_fingerprint"]):
        raise ValueError("The run changed since it was approved; approve again")
    return grant


def apply_with_grant(ctx, token, run_id, *, origin):
    """The only privileged apply path for the desktop: a burned, bound, unexpired human decision, then the engine's own apply."""
    grant = consume(ctx, token, run_id, origin=origin)
    result = runner.apply_task(ctx, run_id)
    return {**result, "challenge_id": grant["challenge_id"]}
