"""DPAPI-protected provider key store (ADP-03).

The key never enters a settings JSON, log or evidence file. Windows DPAPI binds the encrypted blob to the current
user; a missing vault or non-Windows host fails closed instead of falling back to plaintext.
"""

import os
from pathlib import Path


class VaultUnavailable(RuntimeError):
    """No OS-protected key store is available on this host."""


def _protect(data):
    try:
        import win32crypt
    except ImportError as error:
        raise VaultUnavailable("DPAPI is available only on Windows with pywin32") from error
    return win32crypt.CryptProtectData(data, "respected-provider-key", None, None, None, 0)


def _unprotect(blob):
    try:
        import win32crypt
    except ImportError as error:
        raise VaultUnavailable("DPAPI is available only on Windows with pywin32") from error
    return win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1]


class SecretVault:
    def __init__(self, path):
        self.path = Path(path)

    def store(self, secret):
        value = (secret or "").strip()
        if not value:
            raise ValueError("secret must not be empty")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_bytes(_protect(value.encode("utf-8")))
        os.replace(temporary, self.path)

    def load(self):
        if not self.path.exists():
            return None
        return _unprotect(self.path.read_bytes()).decode("utf-8")
