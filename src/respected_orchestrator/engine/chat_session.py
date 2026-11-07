"""Structured Chat session adapter (B3-03.03): one agent CLI's JSONL stream -> typed, sanitised events.

Supported: `opencode run --standalone --format json` only (the one CLI whose stream was captured live; fixtures in
tests/fixtures/chat). codex/claude/cursor are NOT mapped: their streams were never captured here, so they are
refused explicitly instead of guessed. Everything inside a stream is untrusted data: control/escape sequences are
stripped, secrets masked, sizes capped, and no event can carry authority (see session_control, B3-03.04).
An `ask_user` event exists only when the stream itself contains a question tool call; it is never synthesised.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

from . import agent_adapters, clis, winproc
from .journal import mask

SUPPORTED = ("opencode",)
MAX_LINE = 1 << 20
MAX_TEXT = 8000
MAX_TOOL_OUTPUT = 4000
_ASK_TOOLS = {"question", "ask_user", "askuser"}
# Tools a chat turn may not use (checked live 2026-11-07: with these denied the model's shell request never ran; without them it did).
# Reading project files stays allowed: that is what a chat about a project is. Names cover this CLI version's `shell` and older `bash`.
DENIED_TOOLS = ("bash", "shell", "edit", "write", "patch", "webfetch", "websearch", "task")
_RATE = re.compile(r"\b429\b|rate.?limit|usage limit reached|quota", re.I)
_ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_SESSION = re.compile(r"^ses_[A-Za-z0-9]{8,64}$")
_MODEL = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./:#-]+$")


class Unsupported(RuntimeError):
    pass


def clean(text, limit=MAX_TEXT):
    """Visible text only: escape sequences and control characters removed, length capped, secrets masked."""
    text = _CTRL.sub("", _ANSI.sub("", str(text)).replace("\r\n", "\n").replace("\r", "\n"))
    text = mask(text)
    return text if len(text) <= limit else text[:limit] + "…[truncated]"


def _ev(kind, **fields):
    return {"kind": kind, "untrusted": True, **fields}


def _usage(part):
    tokens = part.get("tokens") or {}
    cache = tokens.get("cache") or {}
    return _ev("usage", input=tokens.get("input"), output=tokens.get("output"), reasoning=tokens.get("reasoning"),
               cache_read=cache.get("read"), cache_write=cache.get("write"), cost=part.get("cost"),
               quota="unknown")  # the stream carries no quota, so none is claimed


def normalize(line):
    """One JSONL line -> list of events. Never raises: damage becomes an `error` event."""
    if len(line) > MAX_LINE:
        return [_ev("error", code="oversized_line", message="line dropped")]
    line = line.strip()
    if not line:
        return []
    try:
        obj = json.loads(line)
    except ValueError:
        code = "rate_limited" if _RATE.search(line) else "bad_json"
        return [_ev("error", code=code, message=clean(line, 300))]
    if not isinstance(obj, dict):
        return [_ev("error", code="bad_json", message="not an object")]
    kind, part = obj.get("type"), obj.get("part") if isinstance(obj.get("part"), dict) else {}
    sid = obj.get("sessionID") if isinstance(obj.get("sessionID"), str) else None
    base = {"session_id": sid}
    if kind == "step_start":
        return [_ev("status", state="step_started", **base)]
    if kind == "text":
        return [_ev("message", role="assistant", text=clean(part.get("text", "")), **base)]
    if kind == "tool_use":
        state = part.get("state") if isinstance(part.get("state"), dict) else {}
        name = clean(part.get("tool", ""), 80)
        event = _ev("ask_user" if name.lower() in _ASK_TOOLS else "tool_call", tool=name,
                    status=clean(state.get("status", "unknown"), 40), input=mask(state.get("input", {})),
                    output=clean(state.get("output", ""), MAX_TOOL_OUTPUT), **base)
        return [event]
    if kind == "step_finish":
        return [_usage(part), _ev("status", state="step_finished", reason=clean(part.get("reason", ""), 40), **base)]
    if kind == "error":
        data = obj.get("error") if isinstance(obj.get("error"), dict) else {}
        message = json.dumps(data, ensure_ascii=False) if data else str(obj.get("message", ""))
        return [_ev("error", code="rate_limited" if _RATE.search(message) else "agent_error", message=clean(message, 500), **base)]
    return [_ev("unknown", original_type=clean(kind if isinstance(kind, str) else "", 40), **base)]  # kept visible, trusted never


def parse_stream(lines):
    """All events plus a verdict. `complete` only when the last step finished with reason `stop` and nothing errored."""
    events, seq = [], 0
    for line in lines:
        for event in normalize(line):
            event["seq"] = seq
            seq += 1
            events.append(event)
    finishes = [e for e in events if e["kind"] == "status" and e["state"] == "step_finished"]
    starts = [e for e in events if e["kind"] == "status" and e["state"] == "step_started"]
    errors = [e for e in events if e["kind"] == "error"]
    if any(e["code"] == "rate_limited" for e in errors):
        state = "rate_limited"
    elif errors:
        state = "error"
    elif finishes and len(finishes) == len(starts) and finishes[-1]["reason"] == "stop":
        state = "complete"
    else:
        state = "incomplete"
    sessions = {e["session_id"] for e in events if e.get("session_id")}
    return {"events": events, "state": state, "complete": state == "complete",
            "session_id": next(iter(sessions)) if len(sessions) == 1 else None, "session_ids": len(sessions)}


def command(agent, *, model, prompt, binary, session_id=None):
    """argv for one structured turn. Pure; nothing runs. Never adds an auto-approve flag: approvals stay with the human authority."""
    if agent not in SUPPORTED:
        raise Unsupported(f"{agent}: no verified structured-stream adapter (only {', '.join(SUPPORTED)})")
    if not _MODEL.match(model or ""):
        raise ValueError("Invalid model id")
    if session_id is not None and not _SESSION.match(session_id):
        raise ValueError("Invalid session id")
    if not isinstance(prompt, str) or not prompt.strip() or prompt.lstrip().startswith("-") or "\x00" in prompt:
        raise ValueError("Invalid prompt")
    # --standalone: a private server per turn. The shared background service ignores the caller's environment and working
    # directory (checked live 2026-11-07: its shell tool ran in the directory the service was first started in).
    argv = [binary, "run", "--standalone", "--model", model, "--format", "json"]
    if session_id:
        argv += ["--session", session_id]
    return argv + [prompt]


def turn_environment(cwd, environ=None):
    """Environment for one turn. The CLI takes its project directory from PWD (not from the process working directory), project
    config is ignored so a repository cannot re-enable tools, mutating/network tools are denied, and the child is marked so it can
    never act as the human approver (processes.execute does the same for workers)."""
    env = dict(os.environ if environ is None else environ)
    env.update({"PWD": str(cwd), "OPENCODE_DISABLE_PROJECT_CONFIG": "1", "RESPECTED_ORCH_CHILD": "1",
                "OPENCODE_CONFIG_CONTENT": json.dumps({"permission": {tool: "deny" for tool in DENIED_TOOLS}})})
    return env


def native_binary(agent):
    """The program the engine may spawn: never a `.cmd` shim (cmd.exe would re-parse the prompt, audit P0 #2). None if absent."""
    names = agent_adapters.ADAPTERS[agent]["binaries"]
    found = clis.find(list(names))
    return next((path for path in (clis.worker_executable(agent, found[name]) for name in names) if path), None)


def run_turn(agent, *, model, prompt, cwd, session_id=None, row=None, runner=None, timeout=180):
    """Run one turn only when the matrix says chat is verified and logged in; returns parse_stream's verdict."""
    row = row or agent_adapters.verify(agent)
    if not agent_adapters.usable(row, "chat"):
        raise Unsupported(f"{agent}: chat is not verified/logged in on this machine")
    path = native_binary(agent)
    if path is None:
        raise Unsupported(f"{agent}: no directly spawnable program (a .cmd shim is never run)")
    argv = command(agent, model=model, prompt=prompt, binary=path, session_id=session_id)
    done = (runner or winproc.run)(argv, cwd=str(cwd), env=turn_environment(cwd), capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=timeout, stdin=subprocess.DEVNULL, shell=False)
    result = parse_stream(done.stdout.splitlines())
    if done.returncode != 0 and result["state"] == "complete":
        result["state"], result["complete"] = "error", False
    return result
