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

CURRENT = {"settings.json": 1}  # file name in the data root -> current version
SHIPPED = {"settings.json": 1}  # the oldest version a release shipped; every version from there to CURRENT needs a step
STEPS: dict[tuple[str, int], Callable[[dict], dict]] = {}  # (file name, from_version) -> document of the next version


class MigrationError(Exception):
    pass


def migrate_data(data_root: Path, *, current=CURRENT, steps=STEPS) -> list[str]:
    """Returns the names of the files that were moved; newer or damaged data is reported, never overwritten."""
    moved = []
    for name, target in current.items():
        path = Path(data_root) / name
        if not path.is_file():
            continue
        original = path.read_bytes()
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
        if not backup.exists():
            backup.write_bytes(original)
        atomic_write_json(path, document)
        moved.append(name)
    return moved
