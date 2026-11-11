"""What the engine remembers about chat sessions: the saved conversations (so they survive a restart) and the person's default agent/model.

The desktop shows this and sends the person's choices; it keeps no copy. The file lives under the engine's data root. An unreadable file is
simply an empty store; a failed write is reported to the caller as OSError and never loses what is already on disk (atomic write).
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from ..context import atomic_write_json

DEFAULT_AGENT = "opencode"
DEFAULT_MODEL = "opencode/deepseek-v4.1-flash-free"
MAX_CONVERSATIONS = 100
MAX_TURNS = 200
MAX_BYTES = 3_000_000
TITLE_MAX = 52
RENAME_MAX = 120


def title_of(turns, fallback):
    """A short name like a chat app gives: the first sentence of the first message, cut at a word, capital first letter."""
    first = next((t["user"] for t in turns if isinstance(t.get("user"), str) and t["user"].strip()), "")
    line = next((x.strip() for x in first.splitlines() if x.strip()), "")
    if not line:
        return fallback
    sentence = re.sub(r"[.!?:;,\s]+$", "", re.split(r"[.!?:;]\s", line)[0]) or line
    head = sentence[:TITLE_MAX + 1]
    space = head.rfind(" ")
    cut = sentence if len(sentence) <= TITLE_MAX else head[:space] if space > 12 else sentence[:TITLE_MAX]
    return {"i": "İ", "ı": "I"}.get(cut[0], cut[0].upper()) + cut[1:]


def display_title(record):
    """The name the person sees: their own rename wins, otherwise the saved first-sentence title."""
    custom = record.get("title_custom")
    return custom if isinstance(custom, str) and custom.strip() else record.get("title") or title_of(record.get("turns") or [], "Sohbet")


def folded(text):
    """Case-insensitive comparison that also makes Turkish İ and I meet: search is a person typing, not an id match."""
    return str(text).casefold().replace("\u0307", "")


def usage_of(turns):
    """Token and cost totals exactly as the stream reported them; None when no step reported any."""
    total = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cost": None, "last_input": None, "steps": 0}

    def num(v):
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 and v == v and v != float("inf") else None

    for turn in turns:
        for event in ((turn.get("result") or {}).get("events") or []):
            if event.get("kind") != "usage":
                continue
            i, o = num(event.get("input")), num(event.get("output"))
            if i is None and o is None:
                continue
            total["steps"] += 1
            total["input"] += i or 0
            total["output"] += o or 0
            total["reasoning"] += num(event.get("reasoning")) or 0
            total["cache_read"] += num(event.get("cache_read")) or 0
            if i is not None:
                total["last_input"] = i
            c = num(event.get("cost"))
            if c is not None:
                total["cost"] = (total["cost"] or 0) + c
    return total if total["steps"] else None


class SessionStore:
    def __init__(self, path=None):
        self._path, self._lock = Path(path) if path else None, threading.RLock()
        self._defaults, self._conversations = {}, {}
        if self._path and self._path.is_file():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data.get("defaults"), dict):
                    self._defaults = {k: v for k, v in data["defaults"].items() if k in ("agent", "model") and isinstance(v, str)}
                if isinstance(data.get("conversations"), dict):
                    self._conversations = {k: v for k, v in data["conversations"].items() if isinstance(v, dict) and isinstance(v.get("turns"), list)}
            except (OSError, ValueError, AttributeError):
                self._defaults, self._conversations = {}, {}

    def defaults(self):
        with self._lock:
            return {"agent": self._defaults.get("agent", DEFAULT_AGENT), "model": self._defaults.get("model", DEFAULT_MODEL)}

    def set_defaults(self, agent, model):
        with self._lock:
            previous = dict(self._defaults)
            self._defaults = {"agent": agent, "model": model}
            self._flush(previous)

    def get(self, conversation_id):
        with self._lock:
            return self._conversations.get(conversation_id)

    def all(self):
        with self._lock:
            return sorted(self._conversations.values(), key=lambda c: c.get("updated", 0), reverse=True)

    def put(self, record, touch=True):
        with self._lock:
            record = {**record, "updated": time.time() if touch else record.get("updated", time.time()), "turns": record["turns"][-MAX_TURNS:]}
            self._conversations[record["id"]] = record
            ordered = sorted(self._conversations.values(), key=lambda c: c["updated"], reverse=True)[:MAX_CONVERSATIONS]
            while len(ordered) > 1 and len(json.dumps(ordered)) > MAX_BYTES:
                ordered.pop()
            self._conversations = {c["id"]: c for c in ordered}
            self._flush()

    def delete(self, conversation_id):
        with self._lock:
            if self._conversations.pop(conversation_id, None) is not None:
                self._flush()

    def _flush(self, previous_defaults=None):
        if self._path is None:
            return
        try:
            atomic_write_json(self._path, {"defaults": self._defaults, "conversations": self._conversations})
        except OSError:
            if previous_defaults is not None:
                self._defaults = previous_defaults
            raise
