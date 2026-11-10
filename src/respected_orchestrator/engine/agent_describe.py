"""`agent.describe` (ADR-033): what one agent CLI is and can do, in one shape for every agent.

Built from the read-only probes that already exist (`--version`, `--help`, login status); no agent is started and no token is spent.
A field is `native` only when the installed CLI's own help showed it on this machine (`source: probe`); a documented claim that was
not seen is `unverified`, and what is not offered is `unsupported`. The screen draws what is here and nothing else.
"""
from __future__ import annotations

import datetime as dt
import shutil
import time

from . import agent_adapters, agent_discovery, chat_session, terminals

STATUSES = ("native", "unsupported", "unverified")
SOURCES = ("probe", "doc", "none")
INTERFACES = ("chat", "terminal", "handoff")
# our adapter capability -> the flag name Orchestrator.inc uses for the same thing
FLAGS = {"send_input": "steer", "interrupt": "interrupt", "resume": "resume", "usage": "usage", "approval": "approvals"}
# what only a live session can tell (KALAN_ISLER 3.3): documented, never seen here
LIVE = {"claude": {"commands": "init message field slash_commands", "context": "Agent SDK get_context_usage / statusLine context_window"}}
_NO_CONTRACT = "no adapter contract for this yet"
_CACHE_SECONDS = 30
_cache = {}  # agent -> (monotonic, description); the real machine view only


def _field(status, source, note, **more):
    return {"status": status, "source": source, "note": note, **more}


def _claim(cell):
    """An agent_adapters cell as a field."""
    if cell["status"] == "verified":
        return _field("native", "probe", cell["evidence"])
    if cell["status"] == agent_adapters.GATED:
        return _field("unsupported", "none", cell["evidence"])
    why = "documented, not probed: " if cell["status"] == "source" else "claimed but not found in the CLI: "
    return _field("unverified", "doc", why + cell["evidence"])


def _readiness(agent, found):
    code = found["reason"].split(":")[0]
    if agent == "custom":
        installation, authentication, effective = "unknown", "not_applicable", "unknown"
    else:
        installation = ("not_installed" if code in ("not_found", "binary_missing_on_disk")
                        else "unknown" if found["status"] == "unavailable" else "installed")
        authentication = ({"ok": "configured" if agent in agent_discovery.STORED_CREDENTIAL_ONLY else "authorized",
                           "needs_login": "unauthorized"}.get(found["auth"], "unknown") if installation == "installed" else "unknown")
        effective = ("ready" if found["status"] in ("configured", "verified")
                     else "unknown" if code in ("auth_unknown", "timeout") else "not_ready")
    return {"installation": {"state": installation}, "authentication": {"state": authentication}, "effective": effective, "reason": found["reason"]}


def _help(spec, path, row, probe):
    """(help text or None, why not) for a table entry that is proven by the CLI's own help."""
    if path is None:
        return None, "binary not found"
    if row["version_state"] == "older_than_verified":
        return None, "older than the verified version"
    code, text = probe([path, *spec[0]])
    return (text, "") if code == 0 else (None, f"help probe failed: {' '.join(spec[0])}")


def _modes(spec, path, row, probe):
    if spec is None:
        return _field("unsupported", "none", _NO_CONTRACT, items=[])
    text, why = _help(spec, path, row, probe)
    seen = [{"id": mode, "native": native} for mode, native, token in spec[1] if text is not None and token in text]
    if not seen:
        return _field("unverified", "doc", why or f"no known mode in `{' '.join(spec[0])}`", items=[])
    # `default` passes no flag: the agent's own baseline
    return _field("native", "probe", f"`{' '.join(spec[0])}`", items=[{"id": "default", "native": ""}, *seen])


def _models(agent, spec, path, row, probe):
    """Whether a model can be chosen; the list itself stays in `session.models`, which runs the CLI."""
    selection = "catalog" if agent in chat_session.SUPPORTED else "text"
    if spec is None:
        return _field("unsupported", "none", _NO_CONTRACT, selection=selection, items=[])
    text, why = _help(spec, path, row, probe)
    if text is None or spec[1] not in text:
        return _field("unverified", "doc", why or f"{spec[1]} not in `{' '.join(spec[0])}`", selection=selection, items=[])
    return _field("native", "probe", f"{spec[1]} in `{' '.join(spec[0])}`", selection=selection, items=[])


def describe(agent, *, probe=None, which=None, now=None, use_cache=True):
    if not isinstance(agent, str) or agent not in agent_adapters.ADAPTERS:
        raise ValueError("Unknown agent")
    real = probe is None and which is None and now is None
    if real and use_cache and agent in _cache and time.monotonic() - _cache[agent][0] < _CACHE_SECONDS:
        return _cache[agent][1]
    probe, which = probe or agent_discovery.Probe(), which or shutil.which
    spec = agent_adapters.ADAPTERS[agent]
    row, found = agent_discovery.inspect(agent, probe, which)
    path = found["path"] if found["status"] != "unavailable" else None
    chat = _claim(row["caps"]["chat"])
    if chat["status"] == "native" and agent not in chat_session.SUPPORTED:
        chat = _field("unverified", "doc", "flag present, but the chat stream was never verified with this agent: " + chat["note"])
    live = LIVE.get(agent, {})
    # ADR-035: the agent's own interface runs in a terminal host as soon as its program is on this machine; chat -> terminal keeps the
    # same agent session only where the CLI has a documented way to continue one (terminals.RESUME_ARGS).
    terminal = _field("native", "probe", "the program is installed; it runs in its own terminal host") if path else _field("unsupported", "none", "the agent CLI is not installed")
    both = chat["status"] == "native" and terminal["status"] == "native" and agent in terminals.RESUME_ARGS
    handoff = _field("native", "probe", "an idle chat session continues in the terminal with the same agent session") if both else _field("unsupported", "none", "needs both interfaces and a documented way to continue a session")
    result = {
        "agent": agent,
        "checked_at": (now or dt.datetime.now(dt.timezone.utc)).isoformat(),
        "version": found["version"],
        "readiness": _readiness(agent, found),
        "interfaces": {"chat": chat, "terminal": terminal, "handoff": handoff},
        "capabilities": {flag: _claim(row["caps"][cap]) for cap, flag in FLAGS.items() if row["caps"][cap]["status"] != agent_adapters.GATED},
        "modes": _modes(spec.get("modes"), path, row, probe),
        "models": _models(agent, spec.get("model"), path, row, probe),
        "commands": _field("unverified", "doc", live["commands"], items=[]) if "commands" in live else _field("unsupported", "none", _NO_CONTRACT, items=[]),
        "context": _field("unverified", "doc", live["context"]) if "context" in live else _field("unsupported", "none", _NO_CONTRACT),
        "extra": [],
    }
    if real:
        _cache[agent] = (time.monotonic(), result)
    return result


def describe_all(**kwargs):
    return [describe(agent, **kwargs) for agent in agent_adapters.ADAPTERS]
