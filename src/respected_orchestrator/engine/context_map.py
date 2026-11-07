"""Read-only repository context map with a cache that follows Git (B4-05.01).

Lists the files a task may see (tracked files inside the allowed scope, outside the forbidden one) with a short symbol outline of
each, so later steps can pick what to show a model without reading the whole project. It reads files; it never writes into the
project, runs project code or follows a link. What never enters the map: symlinks and submodules, anything outside the scope, build
and cache directories, files that look like secrets (by name), files that are not UTF-8 text, and files over the size limit. Those
are listed as `skipped` with a reason, so absence is explained. Only names, sizes, hashes and symbol names are kept, never file
contents. The cache key is HEAD + the digest of uncommitted changes + the scope, so any Git drift or scope change rebuilds it."""
import ast
import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..context import EngineContext, atomic_write_json, safe_path
from . import lanes

SCHEMA = 1
MAX_FILES, MAX_FILE_BYTES, MAX_SYMBOLS = 5000, 400_000, 60
_GENERATED = re.compile(r"(^|/)(node_modules|dist|build|target|__pycache__|\.venv|venv|\.tox|\.mypy_cache|\.pytest_cache|\.next|coverage)(/|$)")
_SECRETISH = re.compile(r"(^|/)(\.env[^/]*|id_rsa[^/]*|id_ed25519[^/]*|credentials[^/]*|[^/]*\.(pem|key|pfx|p12|kdb|keystore)|\.npmrc|\.pypirc|secrets?\.[^/]+)$", re.I)
_LANG = {".py": "python", ".js": "javascript", ".ts": "javascript", ".tsx": "javascript", ".jsx": "javascript", ".rs": "rust", ".go": "go",
         ".md": "markdown", ".json": "json", ".toml": "toml", ".yml": "yaml", ".yaml": "yaml", ".css": "css", ".html": "html"}
_PATTERNS = {
    "javascript": re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(function|class)\s+([A-Za-z_$][\w$]*)", re.M),
    "rust": re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(fn|struct|enum|trait|impl)\s+([A-Za-z_][\w]*)", re.M),
    "go": re.compile(r"^(func|type)\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w]*)", re.M),
    "markdown": re.compile(r"^(#{1,3})\s+(.{1,80})$", re.M),
}


def _symbols(language: str | None, text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if language == "python":
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError):
            return [{"kind": "unparsed", "name": "syntax error", "line": 1}]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append({"kind": "class" if isinstance(node, ast.ClassDef) else "function", "name": node.name, "line": node.lineno})
        out.sort(key=lambda s: s["line"])
    elif language in _PATTERNS:
        for match in _PATTERNS[language].finditer(text):
            out.append({"kind": match.group(1) if language != "markdown" else "heading", "name": match.group(2).strip(), "line": text.count("\n", 0, match.start()) + 1})
    return out[:MAX_SYMBOLS]


def _head(project: Path) -> str:
    try:
        return lanes._git(project, "rev-parse", "HEAD").stdout.strip()
    except lanes.LaneError:
        return "no-commit"


def cache_key(project: Path, allowed: Sequence[str], forbidden: Sequence[str]) -> dict[str, str]:
    """HEAD, uncommitted-change digest and scope digest. Any difference means the map may be stale."""
    status = lanes._git(project, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    changed = sorted(part[3:] for part in status.split("\0") if len(part) > 3)
    digest = hashlib.sha256()
    for name in changed:
        path = project / name
        digest.update(name.encode() + b"\0")
        try:
            digest.update(hashlib.sha256(path.read_bytes()).digest() if path.is_file() and not path.is_symlink() else b"-")
        except OSError:
            digest.update(b"?")
    scope = hashlib.sha256(json.dumps([sorted(allowed), sorted(forbidden)]).encode()).hexdigest()
    return {"head": _head(project), "dirty": digest.hexdigest(), "scope": scope}


def build(project: Path, *, allowed: Sequence[str], forbidden: Sequence[str] = (), max_files: int = MAX_FILES) -> dict[str, Any]:
    project = project.resolve()
    allowed, forbidden = [a.strip("/") for a in allowed], [f.strip("/") for f in forbidden]
    listed = lanes._git_path_list(project, "ls-files", "-z")
    files, skipped, truncated = [], [], False
    for name in sorted(listed):
        if allowed and not lanes._path_is_owned(name, allowed):
            continue  # outside the scope: not even named
        if lanes._path_is_owned(name, forbidden):
            skipped.append({"path": name, "reason": "forbidden"})
            continue
        if _SECRETISH.search(name):
            skipped.append({"path": name, "reason": "secret_like_name"})
            continue
        if _GENERATED.search(name):
            skipped.append({"path": name, "reason": "generated_or_cache"})
            continue
        path = project / name
        try:
            if path.is_symlink() or not path.is_file():
                skipped.append({"path": name, "reason": "link_or_not_a_file"})
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                skipped.append({"path": name, "reason": "too_large"})
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append({"path": name, "reason": "not_utf8_text"})
            continue
        except OSError:
            skipped.append({"path": name, "reason": "unreadable"})
            continue
        if len(files) >= max_files:
            truncated = True
            break
        language = _LANG.get(Path(name).suffix.lower())
        files.append({"path": name, "size": size, "sha256": hashlib.sha256(raw).hexdigest(), "language": language,
                      "symbols": _symbols(language, text), "in_task_scope": bool(allowed) and lanes._path_is_owned(name, allowed)})
    return {"schema": SCHEMA, "key": cache_key(project, allowed, forbidden), "files": files, "skipped": skipped, "truncated": truncated,
            "counts": {"files": len(files), "skipped": len(skipped), "symbols": sum(len(f["symbols"]) for f in files)}}


def load_or_build(ctx: EngineContext, project: Path, *, allowed: Sequence[str], forbidden: Sequence[str] = ()) -> tuple[dict[str, Any], str]:
    """(map, "hit" or "rebuilt:<why>"). The cache file lives under the data root, one per project path; a damaged one is rebuilt."""
    project = project.resolve()
    allowed_clean = [a.strip("/") for a in allowed]
    forbidden_clean = [f.strip("/") for f in forbidden]
    target = safe_path(ctx.data_root / "context-cache" / (hashlib.sha256(str(project).encode()).hexdigest()[:16] + ".json"))
    key = cache_key(project, allowed_clean, forbidden_clean)
    try:
        cached = json.loads(target.read_text("utf-8"))
        if cached.get("schema") == SCHEMA and cached.get("key") == key:
            return cached, "hit"
        why = next((name for name in ("head", "dirty", "scope") if (cached.get("key") or {}).get(name) != key[name]), "schema")
    except (OSError, ValueError, AttributeError):
        why = "no_valid_cache"
    fresh = build(project, allowed=allowed_clean, forbidden=forbidden_clean)
    atomic_write_json(target, fresh)
    return fresh, f"rebuilt:{why}"
