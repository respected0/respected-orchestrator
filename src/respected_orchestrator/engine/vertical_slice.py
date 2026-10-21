"""Minimal autonomous Codex vertical slice."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
import re
import time
from typing import Mapping, Sequence

from ..context import atomic_write_json
from .processes import ProcessStopped, execute


MASTER_PROFILE = "glm"
WORKER_PROFILES = {"fast": "glm", "complex": "deepseek"}
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


def _json_object(value: str) -> dict[str, object] | None:
    candidates = [value.strip()]
    match = re.search(r"\{.*\}", value, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


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


def _master_plan_prompt(goal: str) -> str:
    return (
        "You are the MASTER. Split this goal into exactly two tiny independent tasks. Each task "
        "must name and require exactly one repository file. "
        'Return only JSON: {"tasks":[{"id":"fast","objective":"..."},{"id":"complex","objective":"..."}]}. '
        f"Goal: {goal}"
    )


def _worker_prompt(task_id: str, objective: str, correction: str = "") -> str:
    return (
        "You are a worker. Complete only this task. You may run read-only commands to inspect the "
        "one repository file named in your objective. Do not modify files, invoke skills or MCP tools, "
        "spawn subagents, inspect job logs, or inspect any other file. Return only JSON with status, "
        "summary, evidence and risks. "
        f"Task ID: {task_id}\nObjective: {objective}\nCorrection: {correction or 'None'}"
    )


def _master_review_prompt(goal: str, results: Mapping[str, str]) -> str:
    evidence = "\n".join(f"{key}: {value[:2000]}" for key, value in results.items())
    return (
        "You are the MASTER reviewer. Return only JSON: "
        '{"decision":"APPROVED|NEEDS_CHANGES","corrections":{"fast":"...","complex":"..."},"reason":"..."}. '
        f"Goal: {goal}\nWorker evidence:\n{evidence}"
    )


def _final_prompt(goal: str, results: Mapping[str, str], test_result: Mapping[str, object]) -> str:
    evidence = "\n".join(f"{key}: {value[:2000]}" for key, value in results.items())
    return (
        "You are the final reviewer. Return APPROVED, NEEDS_CHANGES or REJECTED as the first line, "
        "then one concise reason. "
        f"Goal: {goal}\nWorker evidence:\n{evidence}\nDeterministic test: {json.dumps(test_result)}"
    )


def run_vertical_slice(
    *,
    goal: str,
    job_root: Path,
    repo_root: Path,
    test_command: Sequence[str],
    codex_path: str = "codex",
    timeout_seconds: float = 300,
    max_workers: int = 2,
) -> dict[str, object]:
    job_root.mkdir(parents=True, exist_ok=True)
    state_path = job_root / "state.json"
    state: dict[str, object] = {"status": "RUNNING", "goal": goal, "master_polls_during_workers": 0}
    started_at = time.monotonic()
    atomic_write_json(state_path, state)

    plan_call = CodexCall("master", MASTER_PROFILE, 1, _master_plan_prompt(goal), job_root / "master-plan")
    plan = run_codex_call(plan_call, cwd=repo_root, codex_path=codex_path, timeout_seconds=timeout_seconds)
    plan_payload = _json_object(plan.output) or {}
    raw_tasks = plan_payload.get("tasks")
    tasks = {
        str(item.get("id")): str(item.get("objective", ""))
        for item in raw_tasks
        if isinstance(item, dict) and item.get("id") in WORKER_PROFILES
    } if isinstance(raw_tasks, list) else {}
    if set(tasks) != set(WORKER_PROFILES):
        state.update({"status": "FAILED", "error": "Master did not return exactly fast and complex tasks"})
        atomic_write_json(state_path, state)
        return state

    def worker(task_id: str, objective: str, correction: str = "") -> tuple[str, CodexOutcome]:
        slot = 2 if task_id == "fast" else 1
        call = CodexCall(
            task_id,
            WORKER_PROFILES[task_id],
            slot,
            _worker_prompt(task_id, objective, correction),
            job_root / task_id / ("correction" if correction else "initial"),
        )
        return task_id, run_codex_call(call, cwd=repo_root, codex_path=codex_path, timeout_seconds=timeout_seconds)

    outcomes: dict[str, CodexOutcome] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(2, max_workers))) as executor:
        futures = [executor.submit(worker, task_id, objective) for task_id, objective in tasks.items()]
        for future in as_completed(futures):
            task_id, outcome = future.result()
            outcomes[task_id] = outcome
    state["master_polls_during_workers"] = 0
    state["worker_status"] = {key: value.status for key, value in outcomes.items()}
    state["usage"] = {key: value.usage for key, value in outcomes.items()}
    atomic_write_json(state_path, state)
    if any(outcome.status != "COMPLETE" for outcome in outcomes.values()):
        state["status"] = "FAILED"
        state["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
        atomic_write_json(state_path, state)
        return state

    results = {key: outcome.output for key, outcome in outcomes.items()}
    review_call = CodexCall("master-review", MASTER_PROFILE, 1, _master_review_prompt(goal, results), job_root / "master-review")
    review = run_codex_call(review_call, cwd=repo_root, codex_path=codex_path, timeout_seconds=timeout_seconds)
    review_payload = _json_object(review.output) or {}
    corrections = review_payload.get("corrections") if isinstance(review_payload.get("corrections"), dict) else {}
    if str(review_payload.get("decision", "")).upper() == "NEEDS_CHANGES" and isinstance(corrections, dict):
        correction_tasks = {key: str(value) for key, value in corrections.items() if key in outcomes and str(value).strip()}
        if correction_tasks:
            with ThreadPoolExecutor(max_workers=max(1, min(2, max_workers))) as executor:
                futures = [
                    executor.submit(worker, task_id, tasks[task_id], correction)
                    for task_id, correction in correction_tasks.items()
                ]
                for future in as_completed(futures):
                    task_id, outcome = future.result()
                    outcomes[task_id] = outcome
            results = {key: outcome.output for key, value in outcomes.items()}
            state["usage"] = {key: value.usage for key, value in outcomes.items()}
            state["corrections"] = correction_tasks
            atomic_write_json(state_path, state)
            second_review = run_codex_call(
                CodexCall("master-review", MASTER_PROFILE, 1, _master_review_prompt(goal, results), job_root / "master-review-2"),
                cwd=repo_root,
                codex_path=codex_path,
                timeout_seconds=timeout_seconds,
            )
            second_payload = _json_object(second_review.output) or {}
            if str(second_payload.get("decision", "")).upper() != "APPROVED":
                state["status"] = "NEEDS_CHANGES"
                state["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
                atomic_write_json(state_path, state)
                return state

    checks_root = job_root / "checks"
    checks_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        completed = execute(list(test_command), repo_root, 300)
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except ProcessStopped as error:
        returncode = 124
        stdout = error.stdout
        stderr = error.stderr
        timed_out = True
    (checks_root / "stdout.log").write_text(_redact(stdout), encoding="utf-8")
    (checks_root / "stderr.log").write_text(_redact(stderr), encoding="utf-8")
    test_result = {
        "command": list(test_command),
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    state["test"] = test_result
    if returncode != 0:
        state["status"] = "TEST_FAILED"
        state["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
        atomic_write_json(state_path, state)
        return state

    final_call = CodexCall("final-review", "", None, _final_prompt(goal, results, test_result), job_root / "final-review")
    final = run_codex_call(final_call, cwd=repo_root, codex_path=codex_path, timeout_seconds=timeout_seconds)
    decision = final.output.splitlines()[0].strip().upper() if final.output else ""
    state["final_review"] = {
        "status": decision if decision in {"APPROVED", "NEEDS_CHANGES", "REJECTED"} else "AWAITING_FINAL_REVIEW",
        "usage": final.usage,
    }
    state["status"] = "COMPLETE" if final.status == "COMPLETE" and decision == "APPROVED" else "AWAITING_FINAL_REVIEW"
    state["routing"] = {
        "master": {"profile": MASTER_PROFILE, "model": "glm-5.3", "account_slot": 1},
        "fast": {"profile": WORKER_PROFILES["fast"], "model": "glm-5.3", "account_slot": 2},
        "complex": {"profile": WORKER_PROFILES["complex"], "model": "deepseek-v4.1-flash", "account_slot": 1},
    }
    state["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
    atomic_write_json(state_path, state)
    return state
