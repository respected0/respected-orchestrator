"""Measured track record per (tool, profile), read from this installation's own signed run evidence.

Automatic assignment ranks candidates with these numbers and says so; with too little history it says that instead.
Only evidence whose signature verifies is counted. Families: "write" (implementer/debugger attempts, from run status
and result) and "read" (review attempts). Nothing here ever excludes a candidate: it only orders them."""
from pathlib import Path
from typing import Any

from ..context import EngineContext
from .runner import _load

MIN_RUNS = 3  # below this a candidate has no usable history


def _roots(data_root: Path) -> list[Path]:
    return [data_root, *sorted((data_root / "campaigns").glob("*/lanes/*"))]


def _bump(table: dict, key: tuple, ok: bool, tokens: Any, seconds: Any) -> None:
    row = table.setdefault(key, {"runs": 0, "ok": 0, "tokens": [], "seconds": []})
    row["runs"] += 1
    row["ok"] += bool(ok)
    if isinstance(tokens, int) and not isinstance(tokens, bool):
        row["tokens"].append(tokens)
    if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
        row["seconds"].append(seconds)


def stats(data_root: Path, limit: int = 400) -> dict[tuple[str, str, str], dict[str, Any]]:
    """{(family, tool, profile): {runs, ok, avg_tokens|None, avg_seconds|None}} over the newest `limit` runs."""
    table: dict[tuple, dict] = {}
    seen = 0
    for root in _roots(data_root):
        ctx = EngineContext(root)
        for directory in sorted((root / "state").glob("run-*"), reverse=True):
            if seen >= limit:
                break
            seen += 1
            try:
                request, status = _load(ctx, directory / "request.json"), _load(ctx, directory / "status.json")
                result = _load(ctx, directory / "result.json") if (directory / "result.json").is_file() else {}
                if status.get("status") in ("queued", "running"):
                    continue
                if request.get("kind") == "write" and request.get("worker") != "custom":
                    usage = result.get("usage") or {}
                    _bump(table, ("write", request["worker"], request.get("worker_profile") or ""),
                          status.get("status") == "completed", usage.get("estimated_weighted_tokens"),
                          result.get("duration_seconds"))
                reviews = directory / "review-attempts.json"
                if reviews.is_file():
                    for entry in _load(ctx, reviews).get("attempts", []):
                        _bump(table, ("read", entry.get("tool") or "codex", entry.get("profile") or ""),
                              entry.get("status") == "COMPLETE", (entry.get("usage") or {}).get("estimated_weighted_tokens"),
                              entry.get("duration_seconds"))
            except (OSError, ValueError, KeyError):
                continue  # unsigned, tampered or partial evidence is not counted
    for row in table.values():
        for name in ("tokens", "seconds"):
            values = row.pop(name)
            row["avg_" + name] = round(sum(values) / len(values)) if values else None
    return table
