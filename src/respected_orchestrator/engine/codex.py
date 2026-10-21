"""Codex CLI call layer: one bounded `codex exec --json` turn with stream diagnosis and usage accounting."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Mapping, Sequence

from ..context import atomic_write_json
from .processes import ProcessStopped, execute


ACCOUNT_PROVIDERS = {1: "evren1", 2: "evren2"}


@dataclass(frozen=True)
class CodexCall:
    role: str
    profile: str
    account_slot: int | None
    prompt: str
    run_root: Path


@dataclass(frozen=True)
class CodexOutcome:
    status: str
    output: str
    usage: dict[str, int | None]
    events_path: Path
    stdout_path: Path
    stderr_path: Path
    cause: str = ""
    diagnostics: Mapping[str, object] | None = None


_DISCONNECT = re.compile(r"(?i)stream disconnected|connection (?:reset|refused|closed|lost)|reconnecting|"
                         r"error sending request|dns error|50[234]")
# Codex logs this on every run (model-list refresh); it says nothing about the turn that was running.
_BENIGN_STDERR = re.compile(r"codex_models_manager|failed to refresh available models")
ACTIVE_WINDOW_SECONDS = 30  # output newer than this at the deadline means work was still progressing


def _is_turn_completed(_stream: str, line: str) -> bool:
    return any(event.get("type") == "turn.completed" for event in _events(line))


def stream_verified_complete(stdout: str) -> bool:
    """A forcibly reaped Codex stream is a success only if it ended a turn and never reported turn.failed."""
    types = [event.get("type") for event in _events(stdout)]
    return "turn.completed" in types and "turn.failed" not in types


def _event_messages(events: Sequence[Mapping[str, object]]) -> list[str]:
    messages = []
    for event in events:
        if event.get("type") in {"error", "turn.failed"}:
            error = event.get("error")
            detail = event.get("message") or (error.get("message") if isinstance(error, dict) else None)
            messages.append(str(detail or event.get("type")))
    return messages


def diagnose(events, stderr: str, *, status: str, had_output: bool, last_output_age: float | None) -> dict:
    """Best-effort cause. Structured JSONL evidence outranks stderr text; anything else is reported as unknown."""
    stderr = chr(10).join(line for line in stderr.splitlines() if not _BENIGN_STDERR.search(line))
    messages = _event_messages(events)
    structured_disconnect = any(_DISCONNECT.search(m) for m in messages)
    if status == "COMPLETE":
        return {"cause": "completed", "confidence": "verified", "evidence": []}
    if any(event.get("type") == "turn.failed" for event in events):
        return {"cause": "provider_disconnected" if structured_disconnect else "provider_error",
                "confidence": "structured", "evidence": messages[-3:]}
    if status == "TIMEOUT":
        if structured_disconnect:
            return {"cause": "provider_disconnected", "confidence": "structured", "evidence": messages[-3:]}
        if _DISCONNECT.search(stderr):
            return {"cause": "provider_disconnected", "confidence": "heuristic_stderr", "evidence": []}
        if not had_output:
            return {"cause": "timeout_no_output", "confidence": "unknown",
                    "evidence": ["no output at all: slow reasoning, a hung provider and a silent disconnect look the same"]}
        active = last_output_age is not None and last_output_age < ACTIVE_WINDOW_SECONDS
        return {"cause": "timeout_active_at_deadline" if active else "timeout_stalled_after_output",
                "confidence": "observed_output_timing", "evidence": [f"last_output_age_seconds={last_output_age:.1f}"]}
    if structured_disconnect or _DISCONNECT.search(stderr):
        return {"cause": "provider_disconnected",
                "confidence": "structured" if structured_disconnect else "heuristic_stderr", "evidence": messages[-3:]}
    return {"cause": "failed", "confidence": "unknown", "evidence": messages[-3:]}


def _redact(value: str) -> str:
    return re.sub(
        r"(?i)((?:api[_-]?key|authorization|token)\s*[:=]\s*(?:bearer\s*)?)\S+",
        r"\1[REDACTED]",
        value,
    )


def _events(stdout: str) -> list[dict[str, object]]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _usage(events: Sequence[Mapping[str, object]]) -> dict[str, int | None]:
    event = next((item.get("usage") for item in reversed(events) if item.get("type") == "turn.completed"), None)
    values = event if isinstance(event, dict) else {}
    def integer(name: str) -> int | None:
        value = values.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    raw_input = integer("input_tokens")
    cached = integer("cached_input_tokens")
    output = integer("output_tokens")
    reasoning = integer("reasoning_output_tokens")
    weighted = None
    if raw_input is not None and cached is not None and output is not None:
        weighted = max(0, raw_input - cached) + round(cached * 0.03) + output
    return {
        "raw_input_tokens": raw_input,
        "cached_input_tokens": cached,
        "output_tokens": output,
        "reasoning_tokens": reasoning,
        "provider_quota_consumption": None,
        "estimated_weighted_tokens": weighted,
    }


def _agent_output(events: Sequence[Mapping[str, object]]) -> str:
    messages = []
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message" and isinstance(item.get("text"), str):
            messages.append(item["text"])
    return "\n".join(messages).strip()


def run_codex_call(
    call: CodexCall,
    *,
    cwd: Path,
    codex_path: str = "codex",
    timeout_seconds: float = 300,
) -> CodexOutcome:
    call.run_root.mkdir(parents=True, exist_ok=True)
    command = [codex_path, "exec", "--json", "--skip-git-repo-check", "--sandbox", "read-only"]
    if call.profile:
        command.extend(["-p", call.profile])
    provider = ACCOUNT_PROVIDERS.get(call.account_slot or 0)
    if provider:
        command.extend(["-c", f'model_provider="{provider}"'])
    command.append(call.prompt)
    metadata = {
        "state": "RUNNING",
        "role": call.role,
        "profile": call.profile,
        "account_slot": call.account_slot,
        "provider": provider,
        "started_at": time.time(),
    }
    process_path = call.run_root / "process.json"
    atomic_write_json(process_path, metadata)
    def record_pid(pid: int) -> None:
        metadata["pid"] = pid
        atomic_write_json(process_path, metadata)
    try:
        completed = execute(command, cwd, timeout_seconds, on_started=record_pid, complete_when=_is_turn_completed,
                           verify_complete=stream_verified_complete, scrub_env=True)
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
        had_output, last_output_age = True, None
    except ProcessStopped as error:
        returncode = 124
        stdout = error.stdout
        stderr = error.stderr
        timed_out = True
        had_output, last_output_age = error.had_output, error.last_output_age
    events = _events(stdout)
    output = _agent_output(events)
    usage = _usage(events)
    status = "TIMEOUT" if timed_out else "COMPLETE" if returncode == 0 and output else "FAILED"
    diagnostics = diagnose(events, stderr, status=status, had_output=had_output, last_output_age=last_output_age)
    cause = diagnostics["cause"]
    events_path = call.run_root / "events.jsonl"
    stdout_path = call.run_root / "stdout.log"
    stderr_path = call.run_root / "stderr.log"
    events_path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
    stdout_path.write_text(_redact(stdout), encoding="utf-8")
    stderr_path.write_text(_redact(stderr), encoding="utf-8")
    metadata.update({"state": status, "cause": cause, "diagnostics": diagnostics, "returncode": returncode, "ended_at": time.time()})
    atomic_write_json(process_path, metadata)
    return CodexOutcome(status, output, usage, events_path, stdout_path, stderr_path, cause, diagnostics)
