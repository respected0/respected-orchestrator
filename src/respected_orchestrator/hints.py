"""Error hints: name the product's own command that gets the person out of the error."""
from __future__ import annotations


def hint(command: str) -> str:
    return f"Şu komutu çalıştırın: {command}"
