"""Move the person's data files to this build's format in place, before anything reads them.

A new build that changes a file's format bumps its number in CURRENT and adds one step per old version to STEPS; `setup`
(and so `repair`) runs this first, so an update never asks the person for anything. Files written before versions existed
(0.1.0-beta.1) have no `schema_version` and count as version 1. The original is kept as `<name>.v<N>.bak`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ..context import atomic_write_json

CURRENT = {"settings.json": 2}  # file name in the data root -> current version
SHIPPED = {"settings.json": 1}  # the oldest version a release shipped; every version from there to CURRENT needs a step
STEPS: dict[tuple[str, int], Callable[[dict], dict]] = {}  # (file name, from_version) -> document of the next version

REMOVED_TOOL, REPLACEMENT_TOOL = "gemini", "agy"  # Google moved from the Gemini CLI to Antigravity (agy)


def _move_assignment(value):
    """A role assignment ({tool, profile, fallbacks}) that named the removed tool names the replacement instead. The
    profile was a model of the removed tool, so it is cleared (empty = the tool's own model). Anything else, including
    agy and antigravity entries, is returned untouched."""
    if isinstance(value, list):
        return [_move_assignment(item) for item in value]
    if not isinstance(value, dict):
        return value
    moved = dict(value)
    if moved.get("tool") == REMOVED_TOOL:
        moved["tool"], moved["profile"] = REPLACEMENT_TOOL, ""
    if "fallbacks" in moved:
        moved["fallbacks"] = _move_assignment(moved["fallbacks"])
    return moved


def _settings_without_gemini(document: dict) -> dict:
    """settings.json 1 -> 2: only settings that named the Gemini CLI change; they use agy (Antigravity) instead."""
    document = dict(document)
    for tool_key, profile_key in (("default_worker", "default_worker_profile"),
                                  ("default_reviewer_tool", "default_reviewer_profile")):
        if document.get(tool_key) == REMOVED_TOOL:
            document[tool_key], document[profile_key] = REPLACEMENT_TOOL, ""
    for key in ("default_roles", "auto_pool"):  # JSON text (as older versions stored it) or an already parsed value
        raw = document.get(key)
        try:
            parsed = json.loads(raw) if isinstance(raw, str) and raw.strip() else raw
        except ValueError:
            continue  # unreadable text is left for the person to fix, never rewritten
        if isinstance(parsed, dict):
            moved = {role: _move_assignment(item) for role, item in parsed.items()}
        elif isinstance(parsed, list):
            moved = _move_assignment(parsed)
        else:
            continue
        if moved != parsed:
            document[key] = json.dumps(moved, ensure_ascii=False) if isinstance(raw, str) else moved
    return document


STEPS[("settings.json", 1)] = _settings_without_gemini


class MigrationError(Exception):
    pass


def migrate_data(data_root: Path, *, current=CURRENT, steps=STEPS) -> list[str]:
    """Returns the names of the files that were moved; newer or damaged data is reported, never overwritten."""
    moved = []
    for name, target in current.items():
        path = Path(data_root) / name
        if not path.is_file():
            continue
        try:
            original = path.read_bytes()
        except OSError as error:
            raise MigrationError(f"{name} okunamadı ({error.strerror or error}); veri dosyasına dokunulmadı") from error
        try:
            document = json.loads(original)
        except ValueError as error:
            raise MigrationError(f"{name} okunamadı; dosyayı düzeltin ya da yedeğe alıp silin") from error
        if not isinstance(document, dict):
            raise MigrationError(f"{name} biçimi tanınmıyor")
        version = document.get("schema_version", 1)
        if not isinstance(version, int) or isinstance(version, bool):
            raise MigrationError(f"{name}: schema_version sayı olmalı")
        if version > target:
            raise MigrationError(f"{name} daha yeni bir sürümden (biçim {version}); programı güncelleyin")
        if version == target:
            continue
        for step in range(version, target):
            if (name, step) not in steps:
                raise MigrationError(f"{name} için biçim {step} → {step + 1} taşıması yok")
            document = steps[(name, step)](document)
            document["schema_version"] = step + 1
        backup = path.with_name(f"{name}.v{version}.bak")
        try:
            if not backup.exists():
                backup.write_bytes(original)
            atomic_write_json(path, document)  # temp file + replace: the original stays whole until the new one is complete
        except OSError as error:  # read-only folder or file, full disk, a locked file...
            raise MigrationError(f"{name} yazılamadı ({error.strerror or error}); özgün dosya olduğu gibi duruyor") from error
        moved.append(name)
    return moved
