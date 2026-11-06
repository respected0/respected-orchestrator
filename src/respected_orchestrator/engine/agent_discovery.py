"""Which agent CLIs are really usable here, and why (B3-07.01).

Builds on the read-only probes of `agent_adapters` and adds one honest status per agent:

  unavailable  cannot be used at all (not found, moved, renamed, hangs, prints nothing sensible, blocked by policy)
  installed    runs and reports a version, but is not logged in (or login state cannot be read)
  configured   logged in, but no chat mode could be confirmed (or the login is only a stored credential)
  verified     logged in and its chat flag is present in its own help text. This is NOT a real model session.

Every status carries a `reason`. Probes run with secret-looking environment variables removed, so no key is read or
passed on; a CLI that only works through such a variable therefore shows as `installed / auth_required`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import agent_adapters, winproc
from .processes import scrub_environment

STATUSES = ("unavailable", "installed", "configured", "verified")
STORED_CREDENTIAL_ONLY = {"opencode"}  # `auth list` shows stored credentials, which prove nothing about validity
_POLICY = re.compile(r"(?i)(managed|disabled|blocked|restricted|not permitted|not allowed)\b.{0,60}\b(policy|administrator|organi[sz]ation|enterprise)")
_CACHE_SECONDS = 30
_cache = {}


class Probe:
    """A `run` for agent_adapters.verify: scrubbed environment, no stdin, hard timeout, remembers what it saw."""

    def __init__(self, environ=None, timeout=20):
        self.env = scrub_environment(dict(os.environ if environ is None else environ))
        self.timeout = timeout
        self.outputs = []
        self.timed_out = False
        self.failed = None

    def __call__(self, argv, timeout=None):
        try:
            done = winproc.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout or self.timeout,
                               stdin=subprocess.DEVNULL, shell=False, env=self.env)
        except subprocess.TimeoutExpired:
            self.timed_out = True
            return None, "timeout"
        except OSError as exc:
            self.failed = str(exc)[:160]
            return None, self.failed
        text = done.stdout + done.stderr
        self.outputs.append(text[:4000])
        return done.returncode, text


def _result(agent, status, reason, row=None, path=None):
    return {"agent": agent, "status": status, "reason": reason, "path": path, "version": (row or {}).get("version"),
            "auth": (row or {}).get("auth", "unknown"), "version_state": (row or {}).get("version_state", "unknown"), "proof": "help flags and status commands only; no model session was run",
            "chat": ((row or {}).get("caps") or {}).get("chat", {}).get("status", "unsupported")}


def classify(agent, row, probe, path):
    spec = agent_adapters.ADAPTERS[agent]
    if agent == "custom":
        return _result(agent, "configured", "user-defined command: nothing is probed or assumed", row)
    if not row["found"]:
        return _result(agent, "unavailable", "not_found: none of " + ", ".join(spec["binaries"]) + " is on PATH", row)
    if not Path(path).is_file():
        return _result(agent, "unavailable", "binary_missing_on_disk: PATH points at a file that is gone (moved or uninstalled)", row, path)
    if Path(path).stem.casefold() not in {b.casefold() for b in spec["binaries"]}:
        return _result(agent, "unavailable", f"renamed_executable: {Path(path).name} is not a known name for this agent", row, path)
    if probe.timed_out and not row["version"]:
        return _result(agent, "unavailable", "timeout: the version probe did not answer in time", row, path)
    if any(_POLICY.search(o) for o in probe.outputs):
        return _result(agent, "unavailable", "enterprise_policy: the CLI reports it is restricted by an administrator or policy", row, path)
    if not row["version"]:
        return _result(agent, "unavailable", "version_probe_failed: the CLI did not report a version", row, path)
    if agent_adapters._parse(row["version"]) is None:
        return _result(agent, "unavailable", "unexpected_output: the version output contains no version number", row, path)
    if row["auth"] == "needs_login":
        return _result(agent, "installed", "auth_required: not logged in (probes run without secret environment variables)", row, path)
    if row["auth"] != "ok":
        return _result(agent, "installed", "auth_unknown: login state could not be read", row, path)
    if agent in STORED_CREDENTIAL_ONLY:
        return _result(agent, "configured", "stored credentials found; their validity cannot be checked without a model call", row, path)
    chat = row["caps"].get("chat", {}).get("status")
    if chat != "verified":
        why = "older than the verified version" if row["version_state"] == "older_than_verified" else f"chat mode is {chat}"
        return _result(agent, "configured", f"logged in, but {why}", row, path)
    return _result(agent, "verified", "logged in and the chat flag is present in the CLI's own help", row, path)


def discover(agent, *, probe=None, which=None, use_cache=True):
    if agent not in agent_adapters.ADAPTERS:
        raise ValueError("Unknown agent")
    real = probe is None and which is None  # only the real machine view is cached; injected fakes never are
    if real and use_cache and agent in _cache and time.monotonic() - _cache[agent][0] < _CACHE_SECONDS:
        return _cache[agent][1]
    probe, which = probe or Probe(), which or shutil.which
    seen = {}

    def tracked_which(name):
        found = which(name)
        if found and "path" not in seen:
            seen["path"] = found
        return found
    row = agent_adapters.verify(agent, probe, tracked_which)
    result = classify(agent, row, probe, seen.get("path"))
    if real:
        _cache[agent] = (time.monotonic(), result)
    return result


def discover_all(**kwargs):
    return {agent: discover(agent, **kwargs) for agent in agent_adapters.ADAPTERS}


def ledger(results):
    """Plain-text compatibility ledger of one discovery run, for release evidence."""
    lines = ["agent        status       reason"]
    lines += [f"{r['agent']:<12} {r['status']:<12} {r['reason']}" + (f"  [{r['version']}]" if r["version"] else "") for r in results.values()]
    return "\n".join(lines)
