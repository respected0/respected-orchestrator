"""Error hints that name the way out the person actually has: the Hub when it is installed, the product's own command otherwise."""
from __future__ import annotations

from .context import default_data_root


def hub_installed() -> bool:
    try:
        return (default_data_root().parent.parent / "RespectedHub/app/respected-hub.exe").is_file()
    except (OSError, ValueError):
        return False


def hint(hub: str, command: str) -> str:
    """`hub` says where to click, `command` is the Hubless equivalent (always correct, so it is always shown)."""
    return f"{hub}; ya da: {command}" if hub_installed() else f"Şu komutu çalıştırın: {command}"
