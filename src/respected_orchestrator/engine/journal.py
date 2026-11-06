"""Append-only event journal (B3-02.02). Informational only: reading it never grants any authority.

One line per event: `<crc32 hex8> <json>`. seq is strictly increasing. A torn or corrupt tail is cut at the last
good record; corruption in the middle stops replay there and is reported, never skipped silently. The same
(operation_id, event_type) is stored once, so a retried producer is idempotent. Secrets are masked before writing.
"""
import hashlib
import json
import os
import re
import time
import zlib

VERSION = 1
MAX_PAYLOAD_BYTES = 16 * 1024
_SECRET_KEY = re.compile(r"key|token|secret|password|passwd|authorization|credential", re.I)
_SECRET_VALUE = re.compile(r"\b(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._~+/=-]{12,})")


def mask(value):
    if isinstance(value, dict):
        return {k: ("[redacted]" if _SECRET_KEY.search(str(k)) else mask(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub("[redacted]", value)
    return value


def _encode(record):
    body = json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return f"{zlib.crc32(body.encode()):08x} {body}\n".encode()


def _decode(line):
    crc, _, body = line.rstrip(b"\n").partition(b" ")
    if len(crc) != 8 or zlib.crc32(body) != int(crc, 16):
        raise ValueError("crc mismatch")
    record = json.loads(body)
    if record.get("v") != VERSION or not isinstance(record.get("seq"), int):
        raise ValueError("unsupported record")
    return record


class Journal:
    def __init__(self, path):
        self.path = path
        self.corrupt = False  # a record before the tail failed its checksum
        self._seen = set()
        self._seq = 0
        self._load()

    def _load(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        good = 0
        data = self.path.read_bytes() if self.path.exists() else b""
        for line in data.splitlines(keepends=True):
            try:
                if not line.endswith(b"\n"):
                    raise ValueError("torn tail")
                record = _decode(line)
                if self._seq and record["seq"] != self._seq + 1:  # the first record of a rotated file may start anywhere
                    raise ValueError("seq gap")
            except (ValueError, TypeError):
                break
            self._seq = record["seq"]
            self._seen.add((record["op"], record["type"]))
            good += len(line)
        if good < len(data):
            rest = data[good:]
            # Only an unterminated final fragment is a torn write; anything else is real corruption.
            self.corrupt = rest.count(b"\n") > 0
            if not self.corrupt:  # a corrupt journal is left untouched as evidence; only a torn last write is cut
                with open(self.path, "r+b") as f:
                    f.truncate(good)

    @property
    def last_seq(self):
        return self._seq

    def append(self, operation_id, event_type, run_id=None, payload=None):
        """Returns the stored record, or None when this (operation_id, event_type) was already stored."""
        if self.corrupt:
            raise RuntimeError("Journal is corrupt; refusing to extend it")
        if (operation_id, event_type) in self._seen:
            return None
        payload = mask(payload or {})
        if len(json.dumps(payload)) > MAX_PAYLOAD_BYTES:
            payload = {"truncated": True}
        record = dict(v=VERSION, seq=self._seq + 1, ts=time.time(), op=operation_id, run=run_id, type=event_type, p=payload)
        line = _encode(record)
        with open(self.path, "ab") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        self._seq += 1
        self._seen.add((operation_id, event_type))
        return record

    def replay(self, after=0, limit=None):
        out = []
        with open(self.path, "rb") as f:
            for line in f:
                try:
                    record = _decode(line)
                except (ValueError, TypeError):
                    break  # corrupt from here on: return the trusted prefix only
                if record["seq"] > after:
                    out.append(record)
                    if limit and len(out) >= limit:
                        break
        return out

    def archive(self, to_path):
        """Retention by rotation: move the file away and continue seq in a fresh one, so reconnect cursors stay monotonic."""
        os.replace(self.path, to_path)
        self._seen.clear()
        self.corrupt = False
        self.append(f"rotated-{self._seq}", "journal.rotated", payload={"archive": os.path.basename(str(to_path))})

    def snapshot(self):
        """Cheap state for a reconnecting UI: last event type per run + a hash of it, valid at last_seq."""
        state = {}
        for r in self.replay():
            if r["run"]:
                state[r["run"]] = {"seq": r["seq"], "type": r["type"]}
        digest = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        return {"last_seq": self._seq, "state": state, "state_hash": digest}
