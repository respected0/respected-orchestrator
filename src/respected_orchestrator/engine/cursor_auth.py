"""Bridge the signed-in Cursor session into an isolated worker HOME.

Cursor keeps its login in ``%APPDATA%\\Cursor\\auth.json`` (accessToken/refreshToken); everything else it needs it
recreates under ``HOME/.cursor``. The worker's HOME/APPDATA are redirected into its scratch root, so this module copies
that single file there (measured live: nothing else is required). The content is validated in memory and never logged,
put into argv, status or evidence; ``opencode_auth.clear_worker_home`` removes the copy afterwards.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

MAX_AUTH_BYTES = 64 * 1024


class CursorAuthError(RuntimeError):
    """The Cursor session could not be copied; the caller must not start an unauthenticated worker."""


def source_path(user_environment=None) -> Path:
    environment = os.environ if user_environment is None else user_environment
    base = environment.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "Cursor" / "auth.json"


def sync_credentials(temp_root, *, user_environment=None) -> None:
    """Copy only auth.json into ``<temp_root>/home/AppData/Roaming/Cursor``; no secret leaves this function."""
    try:
        raw = source_path(user_environment).read_bytes()
        if len(raw) > MAX_AUTH_BYTES:
            raise ValueError
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get("accessToken"), str) or not data["accessToken"]:
            raise ValueError
        target = Path(temp_root) / "home" / "AppData" / "Roaming" / "Cursor"
        target.mkdir(parents=True, exist_ok=True)
        (target / "auth.json").write_bytes(raw)
    except (OSError, ValueError) as error:
        raise CursorAuthError("Cursor credentials are unavailable") from None
