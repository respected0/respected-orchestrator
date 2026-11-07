"""Deterministic task risk classification (B4-01.01).

The level comes only from structure the engine can check: the files a lane owns, its acceptance commands, its kind and the
repository inventory. Task text is never read for permissions or to lower a level; the only thing it can do is raise the
level when it looks like it carries a secret. A result is advice for routing: it grants nothing (`grants_authority` is
always False) and unknown metadata yields "unknown", never a guess."""
import re
from collections.abc import Collection, Mapping
from pathlib import PurePosixPath
from typing import Any

SCHEMA = 1
LEVELS = ("low", "medium", "high", "unknown")
MEDIUM_FILES, HIGH_FILES = 3, 9

_SENSITIVE = re.compile(
    r"(^|/)(\.github|\.git|secrets?|auth|security|sandbox|packaging|installer|migrations?)(/|$)|\.(iss|ps1|bat|cmd|pem|key)$"
    r"|(^|/)(\.env[^/]*|id_rsa|credentials[^/]*)$", re.I)
_DEPENDENCIES = re.compile(r"(^|/)(pyproject\.toml|requirements[^/]*\.txt|package(-lock)?\.json|Cargo\.(toml|lock)|poetry\.lock|uv\.lock)$", re.I)
_DOCS = (".md", ".txt", ".rst")
_SECRET_TEXT = re.compile(
    r"AKIA[0-9A-Z]{16}|\bsk-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*\S{6,}", re.I)


def _is_test(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return "tests" in path.lower().split("/") or name.startswith("test_") or name.endswith(("_test.py", ".test.js", ".spec.ts"))


def _paths(value: Any) -> list[str] | None:
    """Normalised relative POSIX paths, or None when the field is absent or malformed."""
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        return None
    return [re.sub(r"^(\./)+", "", item.strip().replace("\\", "/")) or "." for item in value]


def classify(request: Mapping[str, Any], *, inventory: Collection[str] | None = None) -> dict[str, Any]:
    """{schema, level, reasons:[{code, detail}], features, grants_authority} for one lane request.

    `inventory` is the set of tracked repository paths, or None when it is unknown or stale; without it a lane cannot be "low"."""
    reasons: list[dict[str, str]] = []
    rank = 0  # 0 low, 1 medium, 2 high

    def add(code: str, detail: str, to: int) -> None:
        nonlocal rank
        reasons.append({"code": code, "detail": detail})
        rank = max(rank, to)

    owned = _paths(request.get("ownership")) if isinstance(request, Mapping) else None
    kind = request.get("kind") if isinstance(request, Mapping) else None
    if owned is None or kind not in ("write", "read") or (kind == "write" and not owned):
        # A write lane without a usable scope cannot be judged; say so instead of picking a level.
        return {"schema": SCHEMA, "level": "unknown", "grants_authority": False, "features": {"files": None},
                "reasons": [{"code": "missing_metadata", "detail": "ownership or kind is missing or malformed"}]}

    acceptance = request.get("acceptance")
    has_acceptance = isinstance(acceptance, list) and any(isinstance(c, list) and c for c in acceptance)
    sensitive = sorted(p for p in owned if _SENSITIVE.search(p))
    dependencies = sorted(p for p in owned if _DEPENDENCIES.search(p))
    tests = [p for p in owned if _is_test(p)]
    code = [p for p in owned if not p.lower().endswith(_DOCS) and not _is_test(p)]
    new = sorted(p for p in owned if inventory is not None and p not in inventory
                 and not any(known.startswith(p.rstrip("/") + "/") for known in inventory))
    text = request.get("task")
    secret_like = isinstance(text, str) and bool(_SECRET_TEXT.search(text))

    if sensitive:
        add("sensitive_path", f"{len(sensitive)} owned path(s) are security or release surfaces: {', '.join(sensitive[:3])}", 2)
    if dependencies:
        add("dependency_manifest", f"owns dependency manifest(s): {', '.join(dependencies[:3])}", 2)
    if secret_like:
        add("secret_like_text", "task text looks like it contains a credential (value not recorded)", 2)
    if len(owned) >= HIGH_FILES:
        add("wide_scope", f"owns {len(owned)} paths", 2)
    elif len(owned) >= MEDIUM_FILES:
        add("moderate_scope", f"owns {len(owned)} paths", 1)
    if kind == "write" and not has_acceptance:
        add("no_verification", "no deterministic acceptance command", 1)
    if code and not tests and kind == "write":
        add("code_without_tests", "changes code and owns no test file", 1)
    if inventory is None:
        add("inventory_unknown", "repository inventory missing or stale; paths cannot be checked", 1)
    elif new:
        add("new_paths", f"{len(new)} owned path(s) are not in the inventory", 1)

    return {"schema": SCHEMA, "level": LEVELS[rank], "reasons": reasons, "grants_authority": False,
            "features": {"files": len(owned), "code_files": len(code), "test_files": len(tests), "sensitive": len(sensitive),
                         "dependency_manifests": len(dependencies), "new_paths": len(new), "has_acceptance": has_acceptance,
                         "kind": kind, "secret_like_text": secret_like}}
