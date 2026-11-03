"""Bridge the signed-in OpenCode credentials into an isolated worker HOME.

OpenCode resolves its credential store from HOME/XDG.  Worker isolation therefore also
removes the credentials the provider needs.  This module copies the user's exported
credentials over a stdin pipe into the worker's own scratch HOME.  Export output and
import input stay in memory: neither is written to an engine log or passed in argv.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from . import winproc
from .processes import scrub_environment


MAX_EXPORT_BYTES = 2 * 1024 * 1024
COMMAND_TIMEOUT = 30.0


class OpenCodeAuthError(RuntimeError):
    """Credential export/import failed; the caller must not start an unauthenticated worker."""


def _remaining(deadline: float) -> float:
    remaining = min(COMMAND_TIMEOUT, deadline - time.monotonic())
    if remaining <= 0:
        raise OpenCodeAuthError("OpenCode authentication timed out")
    return remaining


def _run(command, *, environment, deadline: float, stdin: str | None = None):
    try:
        return winproc.run(
            list(command), input=stdin, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=environment, timeout=_remaining(deadline),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise OpenCodeAuthError("OpenCode authentication command failed") from error


def _export(command, *, environment, deadline: float) -> str:
    # The export reads the signed-in user's local store, so it uses the engine environment.
    result = _run([*command, "auth", "export", "--standalone"],
                  environment=environment, deadline=deadline)
    if result.returncode != 0:
        raise OpenCodeAuthError("OpenCode credentials are unavailable")
    payload = result.stdout
    if not isinstance(payload, str) or len(payload.encode("utf-8", "replace")) > MAX_EXPORT_BYTES:
        raise OpenCodeAuthError("OpenCode credential export is invalid")
    try:
        credentials = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise OpenCodeAuthError("OpenCode credential export is invalid") from error
    if not isinstance(credentials, list) or not credentials:
        raise OpenCodeAuthError("OpenCode credentials are unavailable")
    if not all(isinstance(item, dict) for item in credentials):
        raise OpenCodeAuthError("OpenCode credential export is invalid")
    return json.dumps(credentials, ensure_ascii=False, separators=(",", ":"))


def sync_credentials(command, environment, *, deadline: float, user_environment=None) -> None:
    """Copy user credentials into the isolated HOME; no secret leaves this function."""
    if not command:
        raise OpenCodeAuthError("OpenCode executable is unavailable")
    credentials = _export(command, environment=dict(os.environ if user_environment is None else user_environment),
                          deadline=deadline)
    isolated = scrub_environment(environment)
    result = _run([*command, "auth", "import", "--standalone"],
                  environment=isolated, deadline=deadline, stdin=credentials)
    if result.returncode != 0:
        raise OpenCodeAuthError("OpenCode credentials could not be imported")


def clear_worker_home(temp_root) -> None:
    """Remove the copied credential store when the worker's scratch root is no longer needed."""
    root = Path(temp_root).resolve()
    home = (root / "home").resolve()
    if home.parent != root:
        raise OpenCodeAuthError("OpenCode worker HOME is outside its scratch root")
    shutil.rmtree(home, ignore_errors=True)
