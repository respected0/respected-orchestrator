"""Microsoft Agent Framework integration for the execution engine."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import time
from typing import Any

from agent_framework import CheckpointStorage, step, workflow

from ..context import EngineContext, safe_path
from ..engine.runner import (SUPPORTED_AGENTS, tool_result, command_for, tool_available, _load, _save, check_result, create_task, execute_task, get_cli_command,
                     inspect_task, project_fingerprint)
from ..engine import budget as tokens
from . import roles
from ..engine.processes import ProcessStopped, execute
from ..engine.codex import CodexCall, CodexOutcome, _redact, run_codex_call


WorkerResult = Mapping[str, Any]
Worker = Callable[[str], WorkerResult]
Reviewer = Callable[[Mapping[str, WorkerResult]], Mapping[str, Any]]


class ReviewerExecutionError(RuntimeError):
    """The review could not be obtained (not: the reviewer rejected the change). `reason` names the failure class."""
    reason = "reviewer_execution_failed"
    retryable = False

    def __init__(self, message="", *, cause="", usage=None):
        super().__init__(message)
        self.cause = cause
        self.usage = usage or {}
        self.review_attempts = []


class TokenBudgetExceededError(ReviewerExecutionError):
    """The lane's hard token budget is spent: no further paid step (review, retry, correction) is started."""
    reason = "token_budget_exceeded"
    retryable = False


class ReviewerTimeoutError(ReviewerExecutionError):
    reason = "reviewer_timeout"
    retryable = True


class ReviewerDisconnectedError(ReviewerExecutionError):
    reason = "reviewer_disconnected"
    retryable = True


class InvalidReviewResultError(ValueError):
    pass


def run_maf_slice(
    *,
    goal: str,
    workers: Mapping[str, Worker],
    reviewer: Reviewer,
    max_corrections: int = 2,
    checkpoint_storage: CheckpointStorage | None = None,
    resume_checkpoint_id: str | None = None,
) -> dict[str, Any]:
    if not workers:
        raise ValueError("At least one worker is required")
    if not isinstance(max_corrections, int) or not 0 <= max_corrections <= 2:
        raise ValueError("max_corrections must be between 0 and 2")

    @step(replay_key=lambda task_id, correction, round_number: f"{task_id}:{round_number}")
    async def execute_worker(
        task_id: str, correction: str, round_number: int
    ) -> dict[str, Any]:
        return dict(await asyncio.to_thread(workers[task_id], correction))

    @step(replay_key=lambda round_number, results: f"review:{round_number}")
    async def master_review(
        round_number: int, results: Mapping[str, WorkerResult]
    ) -> dict[str, Any]:
        return dict(await asyncio.to_thread(reviewer, results))

    @workflow(name="respected_maf_slice")
    async def slice_workflow(goal: str) -> dict[str, Any]:
        worker_results: dict[str, WorkerResult] = {}
        review_decisions: list[str] = []
        reviews: list[dict[str, Any]] = []
        corrections = {task_id: "" for task_id in workers}

        def reported_corrections() -> dict[str, str]:
            return {
                task_id: correction
                for task_id, correction in corrections.items()
                if correction
            }

        for round_number in range(max_corrections + 1):
            current_workers = (
                workers
                if round_number == 0
                else {
                    task_id: workers[task_id]
                    for task_id, correction in corrections.items()
                    if correction
                }
            )
            outcomes = await asyncio.gather(
                *(
                    execute_worker(task_id, corrections[task_id], round_number)
                    for task_id in current_workers
                )
            )
            for task_id, outcome in zip(current_workers, outcomes):
                if not isinstance(outcome, Mapping):
                    return _failure("invalid_worker_result", "Worker result is not an object",
                                    worker_results, review_decisions, reviews, reported_corrections())
                worker_results[task_id] = outcome

            if any(outcome.get("status") != "COMPLETE" for outcome in worker_results.values()):
                blocked = next(((outcome.get("engine_result") or {}).get("reason") for outcome in worker_results.values()
                                if (outcome.get("engine_result") or {}).get("reason") in {"reuse_verification_failed", "token_budget_exceeded"}), None)
                return _failure(blocked or "worker_failed", "Worker did not complete",
                                worker_results, review_decisions, reviews, reported_corrections())

            try:
                review = await master_review(round_number, worker_results)
            except ReviewerExecutionError as error:
                failure = _failure(error.reason, str(error), worker_results,
                                   review_decisions, reviews, reported_corrections())
                failure["review_failure"] = {"cause": error.cause, "retryable": error.retryable,
                                             "attempts": error.review_attempts}
                return failure
            except InvalidReviewResultError as error:
                return _failure("invalid_review_result", str(error), worker_results,
                                review_decisions, reviews, reported_corrections())
            except Exception as error:
                return _failure("reviewer_execution_failed", str(error), worker_results,
                                review_decisions, reviews, reported_corrections())
            if not isinstance(review, Mapping):
                return _failure("invalid_review_result", "Reviewer result is not an object",
                                worker_results, review_decisions, reviews, reported_corrections())
            decision = str(review.get("decision", "")).upper()
            if decision not in {"APPROVED", "NEEDS_CHANGES", "REJECTED", "HUMAN_APPROVAL_REQUIRED"}:
                return _failure("invalid_review_result", f"Unsupported reviewer decision: {decision}",
                                worker_results, review_decisions, reviews, reported_corrections())
            review_decisions.append(decision)
            reviews.append(dict(review))

            if decision == "APPROVED":
                return _result("MASTER_APPROVED", worker_results, review_decisions,
                               reviews, reported_corrections())
            if decision == "HUMAN_APPROVAL_REQUIRED":
                return _result("HUMAN_APPROVAL_REQUIRED", worker_results, review_decisions,
                               reviews, reported_corrections())
            if decision == "REJECTED":
                return _result("REJECTED", worker_results, review_decisions,
                               reviews, reported_corrections())
            if round_number == max_corrections:
                return _result("NEEDS_CHANGES", worker_results, review_decisions,
                               reviews, reported_corrections())

            raw_corrections = review.get("corrections")
            if not isinstance(raw_corrections, Mapping):
                return _failure("invalid_review_result", "NEEDS_CHANGES requires corrections",
                                worker_results, review_decisions, reviews, reported_corrections())
            corrections = {
                task_id: str(raw_corrections.get(task_id, ""))
                for task_id in workers
            }
            if not any(corrections.values()):
                return _failure("invalid_review_result", "NEEDS_CHANGES corrections are empty",
                                worker_results, review_decisions, reviews, reported_corrections())

        return _result("NEEDS_CHANGES", worker_results, review_decisions,
                       reviews, reported_corrections())

    async def run() -> dict[str, Any]:
        workflow_instance = slice_workflow.build(checkpoint_storage=checkpoint_storage)
        if resume_checkpoint_id is not None:
            run_result = await workflow_instance.run(checkpoint_id=resume_checkpoint_id)
        else:
            run_result = await workflow_instance.run(goal)
        output = run_result.get_outputs()[0]
        if checkpoint_storage is not None:
            checkpoint = await checkpoint_storage.get_latest(
                workflow_name="respected_maf_slice"
            )
            output["checkpoint_id"] = checkpoint.checkpoint_id if checkpoint else None
        return output

    return asyncio.run(run())


def _failure(reason, error, worker_results, review_decisions, reviews, corrections):
    return {
        "status": "FAILED",
        "reason": reason,
        "error": error,
        "worker_results": worker_results,
        "review_decisions": review_decisions,
        "reviews": reviews,
        "corrections": corrections,
    }


def _result(status, worker_results, review_decisions, reviews, corrections):
    return {
        "status": status,
        "worker_results": worker_results,
        "review_decisions": review_decisions,
        "reviews": reviews,
        "corrections": corrections,
    }


def preview_bytes(tool: str) -> int:
    """Codex reviews inside the project and can read more; every other tool sees only the diff, so it gets a large one."""
    return 6000 if tool == "codex" else 60000


MAX_PROMPT_CHARS = 28000  # the prompt is a command-line argument; Windows refuses command lines over 32,767 characters


def _review_prompt(stage: str, task: str, result: Mapping[str, Any], patch_preview: str = "", tool: str = "codex") -> str:
    """The review prompt, with the diff preview shortened until the whole prompt fits one command line."""
    prompt = _review_prompt_text(stage, task, result, patch_preview, tool)
    while len(prompt) > MAX_PROMPT_CHARS and patch_preview:
        patch_preview = patch_preview[: int(len(patch_preview) * 0.8)]
        prompt = _review_prompt_text(stage, task, result, patch_preview, tool)
    return prompt


def _review_prompt_text(stage: str, task: str, result: Mapping[str, Any], patch_preview: str = "", tool: str = "codex") -> str:
    engine_result = result.get("engine_result", {})
    evidence = {
        "task": task,
        "changed_files": engine_result.get("changed_files", []),
        "checks": engine_result.get("checks", []),
        "patch_sha256": engine_result.get("patch_sha256"),
        "duration_seconds": engine_result.get("duration_seconds"),
        "patch_preview": patch_preview,
    }
    return (
        f"You are the independent {stage} reviewer. Judge only the evidence below. "
        "The orchestrator already verified deterministically: the worker finished, only owned files "
        "changed, and every acceptance command in `checks` exited with returncode 0. "
        f"`patch_preview` is the real unified diff (possibly truncated at {preview_bytes(tool)} bytes). "
        "APPROVED if the diff does what the task asks, stays within the task, and the passing checks "
        "adequately cover it. Do not demand evidence about how the worker worked (tools, shell, "
        "transcripts); that is not available. Use NEEDS_CHANGES for a concrete defect or missing "
        "requirement visible in the diff or checks, and REJECTED for unsafe or off-task changes. "
        + ("" if tool == "codex" else
           "You have no shell and no repository access: do not run commands or open files (a denied command ends your "
           "turn without an answer). If the diff is truncated, judge what is shown and say what you could not see. ") +
        'Return only JSON: {"decision":"APPROVED|NEEDS_CHANGES|REJECTED",'
        '"corrections":{"coding":"concise correction or empty"},"reason":"..."}. '
        f"Evidence: {json.dumps(evidence, ensure_ascii=True)}"
    )


def _model(events_path: Path) -> str | None:
    try:
        lines = events_path.read_text(encoding="utf8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed":
            model = event.get("model") or event.get("model_id")
            return model if isinstance(model, str) else None
    return None


def _json_object(value: str) -> dict[str, object] | None:
    candidates = [value.strip()]
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        candidates.append(value[start:end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


REVIEW_BASE_SECONDS = {"glm": 900, "deepseek": 600}  # observed: GLM review 266 s; DeepSeek reviews of larger diffs hit 300 s
REVIEW_FALLBACK_SECONDS = 450
REVIEW_SECONDS_PER_PATCH_KB = 5  # the reviewer reads the diff and explores the repo: more patch, more time
REVIEW_SCALE_CAP_SECONDS = 600
REVIEW_RETRY_GROWTH = 1.5
REVIEW_TIMEOUT_CAP_SECONDS = 3600


def review_timeout_default(profile: str, patch_bytes: int = 0) -> int:
    """Provider-aware first-attempt review ceiling (a ceiling only: reviews end on their completion event)."""
    name = profile.casefold()
    base = next((seconds for key, seconds in REVIEW_BASE_SECONDS.items() if key in name), REVIEW_FALLBACK_SECONDS)
    return min(REVIEW_TIMEOUT_CAP_SECONDS, base + min(REVIEW_SCALE_CAP_SECONDS, patch_bytes // 1000 * REVIEW_SECONDS_PER_PATCH_KB))


def review_attempt_timeouts(first: float, retries: int) -> list[int]:
    """Ceilings of the bounded review attempts: each retry after a timeout/disconnect gets more room, capped."""
    ceilings = [int(first)]
    for _ in range(retries):
        ceilings.append(min(REVIEW_TIMEOUT_CAP_SECONDS, int(ceilings[-1] * REVIEW_RETRY_GROWTH)))
    return ceilings


def _fresh_root(base: Path) -> Path:
    """Evidence of an earlier (failed) review is never overwritten: a new attempt gets its own directory."""
    candidate, index = base, 1
    while candidate.exists():
        index += 1
        candidate = base.with_name(f"{base.name}-r{index}")
    return candidate


def _record_review_attempt(ctx: EngineContext, run_id: str, entry: dict[str, Any]) -> None:
    path = ctx.run_dir(run_id) / "review-attempts.json"
    attempts = _load(ctx, path)["attempts"] if path.is_file() else []
    _save(ctx, path, {"attempts": [*attempts, entry]})


def _run_tool_call(tool: str, profile: str, prompt: str, run_root: Path, timeout_seconds: float) -> CodexOutcome:
    """One review through any non-Codex tool CLI. The prompt carries all evidence, so the reviewer gets an empty
    directory instead of the project. Usage comes from the tool's JSON envelope; if absent it stays UNKNOWN, never zero."""
    run_root.mkdir(parents=True, exist_ok=True)
    text, usage = "", None
    stdout_path, stderr_path = run_root / "stdout.log", run_root / "stderr.log"
    try:
        completed = execute(command_for(tool, prompt, profile=profile), run_root, timeout_seconds, scrub_env=True)
        text, usage, _model, error = tool_result(tool, completed.stdout)
        status = "COMPLETE" if completed.returncode == 0 and text.strip() and not error else "FAILED"
        stdout, stderr, cause = completed.stdout, completed.stderr, "" if status == "COMPLETE" else "tool_failed"
    except ProcessStopped as error:
        status, stdout, stderr, cause = "TIMEOUT", error.stdout, error.stderr, error.reason
    except (OSError, ValueError) as error:  # could not start the tool: recorded as a failed review, never a silent gap
        status, stdout, stderr, cause = "FAILED", "", f"{type(error).__name__}: {str(error)[:300]}", "spawn_failed"
    stdout_path.write_text(_redact(stdout), encoding="utf8")
    stderr_path.write_text(_redact(stderr), encoding="utf8")
    return CodexOutcome(status, text, usage or {}, run_root / "events.jsonl", stdout_path, stderr_path, cause)


def _run_codex_review(
    *,
    stage: str,
    task: str,
    result: Mapping[str, Any],
    profile: str,
    cwd: Path,
    run_root: Path,
    codex_path: str | None,
    timeout_seconds: float,
    patch_preview: str = "",
    tool: str = "codex",
) -> dict[str, Any]:
    started = time.monotonic()
    prompt = _review_prompt(stage, task, result, patch_preview, tool)
    if tool == "codex":
        command = get_cli_command("codex")
        executable = codex_path or (command[0] if command else "codex")
        outcome = run_codex_call(CodexCall(stage, profile, None, prompt, run_root), cwd=cwd, codex_path=executable,
                                 timeout_seconds=max(0.1, timeout_seconds))
    else:
        outcome = _run_tool_call(tool, profile, prompt, run_root, max(0.1, timeout_seconds))
    if outcome.status != "COMPLETE":
        message = f"{stage} reviewer status: {outcome.status} ({outcome.cause or 'unknown'})"
        if outcome.cause == "provider_disconnected":  # structured evidence of a lost connection, whether or not it timed out
            error_class = ReviewerDisconnectedError
        elif outcome.status == "TIMEOUT":
            error_class = ReviewerTimeoutError
        else:
            error_class = ReviewerExecutionError
        raise error_class(message, cause=outcome.cause or "unknown", usage=outcome.usage)
    payload = _json_object(outcome.output)
    if not isinstance(payload, dict):
        raise InvalidReviewResultError(f"{stage} reviewer returned invalid JSON")
    decision = str(payload.get("decision", "")).upper()
    if decision not in {"APPROVED", "NEEDS_CHANGES", "REJECTED"}:
        raise InvalidReviewResultError(f"{stage} reviewer decision is invalid: {decision}")
    if decision == "NEEDS_CHANGES" and not isinstance(payload.get("corrections"), Mapping):
        raise InvalidReviewResultError(f"{stage} reviewer correction payload is invalid")
    return {
        **payload,
        "stage": stage,
        "profile": profile,
        "tool": tool,
        "model": _model(outcome.events_path),
        "usage": outcome.usage,
        "duration_seconds": round(time.monotonic() - started, 3),
    }


def _review_with_retry(
    *,
    stage: str,
    profile: str,
    tool: str = "codex",
    base_root: Path,
    first_timeout: float,
    retries: int,
    remaining: Callable[[], float],
    record: Callable[[dict[str, Any]], None],
    before_attempt: Callable[[], None] | None = None,
    **review_args: Any,
) -> dict[str, Any]:
    """One review with a bounded number of retries after a timeout or disconnect (never after a rejection).

    Every attempt keeps its own evidence directory and a record (status, cause, ceiling, duration, usage), so a failed
    review is never overwritten and its tokens are never lost. Total time stays inside the pipeline deadline."""
    last: ReviewerExecutionError | None = None
    attempts: list[dict[str, Any]] = []
    for number, ceiling in enumerate(review_attempt_timeouts(first_timeout, retries), start=1):
        if before_attempt is not None:
            try:
                before_attempt()
            except ReviewerExecutionError as error:  # a spent budget stops the retry loop; earlier attempts stay recorded
                error.review_attempts = attempts
                raise
        room = remaining()
        if room <= 0:
            error = last or ReviewerExecutionError(f"pipeline timeout before {stage} review")
            error.review_attempts = attempts
            raise error
        root = _fresh_root(base_root if number == 1 else base_root.with_name(f"{base_root.name}-retry{number - 1}"))
        timeout = min(room, ceiling)
        started = time.monotonic()
        entry = {"stage": stage, "profile": profile, "tool": tool, "attempt": number, "timeout_seconds": round(timeout, 1), "evidence": root.name}
        try:
            review = _run_codex_review(stage=stage, profile=profile, tool=tool, run_root=root, timeout_seconds=timeout,
                                       **review_args)
        except ReviewerExecutionError as error:
            entry.update(status=error.reason, cause=error.cause, usage=error.usage, duration_seconds=round(time.monotonic() - started, 1))
            attempts.append(entry)
            record(entry)
            last = error
            if not error.retryable:
                break
            continue
        entry.update(status="COMPLETE", cause="completed", decision=review.get("decision"), usage=review.get("usage"),
                     duration_seconds=round(time.monotonic() - started, 1))
        record(entry)
        return review
    last.review_attempts = attempts
    raise last


USAGE_FIELDS = ("raw_input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "estimated_weighted_tokens")


def _sum_usage(usages) -> dict[str, int]:
    totals = {field: 0 for field in USAGE_FIELDS}
    for usage in usages:
        if isinstance(usage, Mapping):
            for field in USAGE_FIELDS:
                value = usage.get(field)
                if isinstance(value, int) and not isinstance(value, bool):
                    totals[field] += value
    return totals


def _usage_total(reviews: list[Mapping[str, Any]], worker_results: Mapping[str, WorkerResult]) -> dict[str, int]:
    return _sum_usage([
        *(review.get("usage") for review in reviews),
        *(result.get("engine_result", {}).get("usage") for result in worker_results.values() if not result.get("reused")),
    ])


def _review_assignment(source_request, workflow, injected, codex_path):
    """(reviewer tool, profile, deep tool, deep profile), checked before any paid step. An injected reviewer callable
    (tests, custom review) needs no assignment. Runs recorded before role assignment existed carry their reviewer in
    `workflow` only."""
    stored = dict(source_request.get("role_assignments") or {})
    for role, tool_key, profile_key in (("reviewer", "reviewer_tool", "reviewer_profile"),
                                        ("deep_reviewer", "deep_review_tool", "deep_review_profile")):
        if role not in stored and workflow.get(profile_key):
            stored[role] = {"tool": workflow.get(tool_key) or "codex", "profile": workflow[profile_key]}
    def available(tool):
        return bool(codex_path) if tool == "codex" and codex_path else tool_available(tool)
    try:
        chosen = roles.resolve({"blocked_profiles": ""}, stored, [] if injected else ["reviewer"], optional=["reviewer", "deep_reviewer"],
                               tools=list(SUPPORTED_AGENTS), available=available, check_roles={"reviewer", "deep_reviewer"})
    except roles.RoleError as error:
        raise ReviewerExecutionError(f"{error.code}: {error.message} {error.hint}", cause=error.code) from error
    first = chosen.get("reviewer") or {"tool": "codex", "profile": ""}
    deep = chosen.get("deep_reviewer", first)
    return first["tool"], first["profile"], deep["tool"], deep["profile"]


def run_maf_coding_task(
    *,
    ctx: EngineContext,
    run_id: str,
    checkpoint_storage: CheckpointStorage | None = None,
    resume_checkpoint_id: str | None = None,
    reviewer: Reviewer | None = None,
    request: Mapping[str, Any] | None = None,
    codex_path: str | None = None,
) -> dict[str, Any]:
    source_request = dict(request) if request is not None else inspect_task(ctx, run_id)["request"]
    workflow = dict(source_request.get("workflow", {}))
    max_corrections = workflow.get("max_corrections", 2)
    deep_review = workflow.get("deep_review", "never")
    risk_changed_files = workflow.get("risk_changed_files", 5)
    human_approval = workflow.get("human_approval", False)
    primary_profile = source_request.get("worker_profile", "")
    primary_tool = source_request.get("worker", "codex")
    debugger = (source_request.get("role_assignments") or {}).get("debugger")
    reviewer_tool, reviewer_profile, deep_review_tool, deep_review_profile = _review_assignment(
        source_request, workflow, reviewer is not None, codex_path)
    escalate_profile = workflow.get("escalate_profile")
    escalate_from_round = workflow.get("escalate_from_round", 2)
    # Ceiling only: reviews end on their completion event, never by waiting this out.
    explicit_review_timeout = workflow.get("review_timeout_seconds")
    review_retries = workflow.get("review_retries", 1)

    def review_timeout_for(profile: str, patch_bytes: int = 0) -> float:
        return explicit_review_timeout or review_timeout_default(profile, patch_bytes)

    project = Path(source_request["project_root"])
    # Coherent budget: every attempt needs worker time plus its review(s) including the bounded review retries.
    # An explicit workflow timeout_seconds is a hard cap and wins; reviews are always reserved room.
    fast_ceiling = review_timeout_for(reviewer_profile)
    review_budget = sum(review_attempt_timeouts(fast_ceiling, review_retries)) + (
        sum(review_attempt_timeouts(review_timeout_for(deep_review_profile), review_retries)) if deep_review != "never" else 0)
    derived_total = (source_request["timeout_seconds"] + review_budget) * (1 + max_corrections)
    total_budget = workflow.get("timeout_seconds") or derived_total
    state = SimpleNamespace(attempts=[], deadline=time.monotonic() + total_budget)
    attempts_path = ctx.run_dir(run_id) / "maf-attempts.json"
    if attempts_path.is_file():
        state.attempts = _load(ctx, attempts_path)["attempts"]
    if not isinstance(state.attempts, list):
        raise ValueError("Invalid MAF attempt history")
    # Plain ints captured by the step closures would change the workflow signature between invocations and break
    # checkpoint resume, so per-invocation facts live on the state object.
    state.preexisting = len(state.attempts)  # a re-invocation continues this history instead of repeating it
    state.used_corrections = sum(1 for attempt in state.attempts if attempt.get("correction"))
    invocation_reviews: list[dict[str, Any]] = []  # every review call of THIS invocation, failed ones included
    initial_maf_result = ctx.run_dir(run_id) / "maf-result.json"
    if not initial_maf_result.is_file():
        _save(ctx, initial_maf_result, {
            "root_run_id": run_id,
            "status": "PENDING",
            "human_approval_required": False,
        })

    def record_attempt(entry: dict[str, Any]) -> None:
        state.attempts.append(entry)
        _save(ctx, attempts_path, {"attempts": state.attempts})

    lane_budget = workflow.get("max_weighted_tokens")  # run-level and lifetime: a retry or re-invocation never resets it
    unknown_charge = workflow.get("unknown_step_tokens", tokens.UNKNOWN_STEP_TOKENS_DEFAULT)

    def lifetime_spend() -> dict[str, Any]:
        steps = [tokens.worker_step(attempt.get("engine_result") or {}) for attempt in state.attempts]
        reviews_path = ctx.run_dir(run_id) / "review-attempts.json"
        if reviews_path.is_file():
            steps.extend(tokens.review_step(entry) for entry in _load(ctx, reviews_path)["attempts"])
        return tokens.summarize(steps)

    def budget_exceeded() -> dict[str, Any] | None:
        if lane_budget is None:
            return None
        spend = lifetime_spend()
        basis = tokens.committed(spend, unknown_charge)
        if basis < lane_budget:
            return None
        return {"limit": lane_budget, "basis": basis, "known_weighted_tokens": spend["usage"]["estimated_weighted_tokens"],
                "unknown_steps": spend["unknown_steps"], "unknown_step_tokens": unknown_charge}

    def require_budget(step: str) -> None:
        exceeded = budget_exceeded()
        if exceeded:
            raise TokenBudgetExceededError(
                f"lane token budget {exceeded['limit']} reached before the {step} "
                f"(known {exceeded['known_weighted_tokens']} + {exceeded['unknown_steps']} unknown step(s) x {unknown_charge})",
                cause="token_budget_exceeded")

    def worker(correction: str = "") -> dict[str, Any]:
        remaining = state.deadline - time.monotonic()
        # Keep the fast review's room: a correction that eats it could never be approved.
        worker_room = remaining - (min(fast_ceiling, total_budget // 2) if correction else 0)
        if worker_room <= 0:
            return {"status": "FAILED", "engine_result": {"status": "failed", "reason": "pipeline_timeout"}}
        if correction and budget_exceeded():  # no new paid worker once the lane budget is spent; nothing is approved
            return {"status": "FAILED", "engine_result": {"status": "failed", "reason": "token_budget_exceeded"}}
        if correction:
            cancel_path = ctx.run_dir(run_id) / "cancel.request"
            if cancel_path.exists():
                return {"status": "FAILED", "engine_result": {"status": "cancelled", "reason": "cancellation_requested"}}
            if project_fingerprint(project) != source_request["project_fingerprint"]:
                return {"status": "FAILED", "engine_result": {"status": "failed", "reason": "stale_project"}}
            previous = next((
                attempt for attempt in reversed(state.attempts)
                if attempt.get("status") == "completed"
                and isinstance(attempt.get("engine_result"), Mapping)
                and attempt["engine_result"].get("status") == "completed"
                and isinstance(attempt.get("run_id"), str)
            ), None)
            if previous is None:
                return {"status": "FAILED", "engine_result": {"status": "failed",
                        "reason": "correction_inheritance_missing"}}
            previous_result = previous["engine_result"]
            previous_patch_sha256 = previous_result.get("patch_sha256")
            if not isinstance(previous_patch_sha256, str):
                return {"status": "FAILED", "engine_result": {"status": "failed",
                        "reason": "correction_inheritance_missing"}}
            child_request = {
                key: value for key, value in source_request.items()
                if key not in {"run_id", "created_at", "project_fingerprint",
                               "correction_of", "correction_round", "retry_of", "retry_depth",
                               "inherited_patch_run_id", "inherited_patch_sha256"}
            }
            implementer = primary_profile
            if escalate_profile and len(state.attempts) >= escalate_from_round:
                # The reviewer takes over the code; the original implementer becomes the independent reviewer.
                implementer = escalate_profile
                child_request["worker_profile"] = escalate_profile
                child_request["workflow"] = {**source_request["workflow"], "reviewer_profile": primary_profile,
                                             "deep_review_profile": primary_profile,
                                             "reviewer_tool": primary_tool, "deep_review_tool": primary_tool}
            elif debugger:  # the debugger role, when assigned, takes the review-driven correction rounds
                implementer = debugger["profile"]
                child_request.update(worker=debugger["tool"], worker_profile=debugger["profile"])
            child_request.update(
                task=f"{source_request['task']}\n\nIndependent reviewer correction: {correction}",
                correction_of=run_id,
                correction_round=len(state.attempts),
                timeout_seconds=min(source_request["timeout_seconds"], max(1, int(worker_room) + 1)),
                inherited_patch_run_id=previous["run_id"],
                inherited_patch_sha256=previous_patch_sha256,
            )
            try:
                current_run_id = create_task(ctx, child_request)["run_id"]
                _save(ctx, ctx.run_dir(current_run_id) / "maf-result.json", {
                    "root_run_id": run_id,
                    "status": "PENDING",
                    "human_approval_required": False,
                })
            except Exception as error:
                record_attempt({"run_id": None, "correction_round": len(state.attempts),
                                "correction": correction, "status": "failed",
                                "reason": "correction_submission_failed", "error": str(error)})
                return {"status": "FAILED", "engine_result": {"status": "failed",
                        "reason": "correction_submission_failed", "error": str(error)}}
        else:
            reusable = state.attempts[-1] if state.preexisting and state.attempts else None
            if reusable and reusable.get("status") == "completed" and isinstance(reusable.get("run_id"), str):
                # Review-only retry: an earlier invocation coded this work and it passed acceptance, but its review
                # did not finish. Re-verify the signed result and patch (never trust the old record), then review it
                # again; the worker is not run a second time and no duplicate attempt is recorded.
                try:
                    check_result(ctx, reusable["run_id"], maf_gate=False)
                except Exception as error:  # tampered, stale or conflicting: fail closed, never approve
                    return {"status": "FAILED", "engine_result": {"status": "failed", "reason": "reuse_verification_failed",
                                                                  "error": str(error)[:300]}}
                return {"status": "COMPLETE", "run_id": reusable["run_id"], "engine_result": reusable["engine_result"],
                        "correction": reusable.get("correction", ""), "reused": True}
            if budget_exceeded():
                return {"status": "FAILED", "engine_result": {"status": "failed", "reason": "token_budget_exceeded"}}
            current_run_id = run_id
            implementer = primary_profile
        try:
            engine_result = execute_task(ctx, current_run_id)
        except Exception as error:
            engine_result = {"status": "failed", "reason": "engine_error", "error": str(error)}
        record_attempt({
            "run_id": current_run_id,
            "correction_round": 0 if not correction else len(state.attempts),
            "correction": correction,
            "implementer": implementer,
            "status": engine_result.get("status"),
            "reason": engine_result.get("reason"),
            "engine_result": engine_result,
        })
        return {
            "status": "COMPLETE" if engine_result.get("status") == "completed" else "FAILED",
            "run_id": current_run_id,
            "engine_result": engine_result,
            "correction": correction,
        }

    def record_review(entry: dict[str, Any]) -> None:
        invocation_reviews.append(entry)
        _record_review_attempt(ctx, run_id, entry)

    def patch_size(coding: Mapping[str, Any]) -> int:
        try:
            return safe_path(ctx.run_dir(coding["run_id"]) / "worker.patch").stat().st_size
        except (OSError, KeyError, ValueError):
            return 0

    def preview(coding: Mapping[str, Any], tool: str = "codex") -> str:
        # Bounded diff so the reviewer sees actual content, not just a hash.
        try:
            patch = safe_path(ctx.run_dir(coding["run_id"]) / "worker.patch")
            return patch.read_bytes()[:preview_bytes(tool)].decode("utf8", errors="replace")
        except (OSError, KeyError, ValueError):
            return ""

    def default_reviewer(results: Mapping[str, WorkerResult]) -> dict[str, Any]:
        coding = results["coding"]
        engine = coding.get("engine_result", {})
        checks = engine.get("checks")
        # The reviewer prompt asserts these facts, so never spend a review without them.
        if (engine.get("status") != "completed" or not checks
                or any(c.get("returncode") != 0 for c in checks)
                or (engine.get("changed_files") and not preview(coding))):
            raise ReviewerExecutionError("missing deterministic evidence for review")
        remaining = state.deadline - time.monotonic()
        if remaining <= 0:
            raise ReviewerExecutionError("pipeline timeout before review")
        implementer = (state.attempts[-1].get("implementer") or "") if state.attempts else ""
        # Escalation (the user's own escalate_profile) hands the code over: the former implementer reviews the new one.
        def reviewer_for(tool, profile):
            if escalate_profile and implementer and profile.casefold() == implementer.casefold():
                return primary_tool, primary_profile
            return tool, profile
        fast_tool, fast_profile = reviewer_for(reviewer_tool, reviewer_profile)
        deep_tool, deep_profile = reviewer_for(deep_review_tool, deep_review_profile)
        if (workflow.get("require_independent_review") and implementer
                and fast_profile.casefold() == implementer.casefold()):
            raise ReviewerExecutionError("reviewer would be the implementer")
        patch_bytes = patch_size(coding)
        fast = _review_with_retry(
            stage="fast", task=source_request["task"], result=coding, profile=fast_profile, tool=fast_tool,
            cwd=project, base_root=ctx.run_dir(run_id) / f"review-fast-{len(state.attempts)}",
            codex_path=codex_path, first_timeout=review_timeout_for(fast_profile, patch_bytes), retries=review_retries,
            remaining=lambda: state.deadline - time.monotonic(), record=record_review, patch_preview=preview(coding, fast_tool),
            before_attempt=lambda: require_budget("review attempt"),
        )
        fast["implementer"] = implementer
        if fast["decision"] != "APPROVED":
            return fast
        changed_files = coding.get("engine_result", {}).get("changed_files", [])
        should_deep_review = deep_review == "always" or (
            deep_review == "risk_based" and len(changed_files) >= risk_changed_files
        )
        if should_deep_review:
            remaining = state.deadline - time.monotonic()
            if remaining <= 0:
                raise ReviewerExecutionError("pipeline timeout before deep review")
            deep = _review_with_retry(
                stage="deep", task=source_request["task"], result=coding, profile=deep_profile, tool=deep_tool,
                cwd=project, base_root=ctx.run_dir(run_id) / f"review-deep-{len(state.attempts)}",
                codex_path=codex_path, first_timeout=review_timeout_for(deep_profile, patch_bytes), retries=review_retries,
                remaining=lambda: state.deadline - time.monotonic(), record=record_review, patch_preview=preview(coding, deep_tool),
                before_attempt=lambda: require_budget("deep review"),
            )
            if deep["decision"] != "APPROVED":
                return deep
            fast["deep_review"] = deep
        if human_approval:
            fast["decision"] = "HUMAN_APPROVAL_REQUIRED"
        return fast

    selected_reviewer = reviewer or default_reviewer

    def routing_reviewer(results: Mapping[str, WorkerResult]) -> dict[str, Any]:
        require_budget("review")
        review = dict(selected_reviewer(results))
        if human_approval and str(review.get("decision", "")).upper() == "APPROVED":
            review["decision"] = "HUMAN_APPROVAL_REQUIRED"
        return review

    result = run_maf_slice(
        goal=f"Execute coding task {run_id}",
        workers={"coding": worker},
        reviewer=routing_reviewer,
        max_corrections=max(0, max_corrections - state.used_corrections),
        checkpoint_storage=checkpoint_storage,
        resume_checkpoint_id=resume_checkpoint_id,
    )
    result["budget"] = {"total_seconds": total_budget, "fast_review_ceiling_seconds": fast_ceiling,
                        "review_budget_seconds": review_budget, "review_retries": review_retries,
                        "total_source": "explicit" if workflow.get("timeout_seconds") else "derived"}
    result["attempts"] = state.attempts
    result["final_run_id"] = state.attempts[-1]["run_id"] if state.attempts else None
    lifetime = lifetime_spend()
    basis = tokens.committed(lifetime, unknown_charge)
    result["usage_status"] = lifetime["usage_status"]  # KNOWN / PARTIAL / UNKNOWN: missing provider data is never "0"
    result["token_budget"] = {"limit": lane_budget, "known_weighted_tokens": lifetime["usage"]["estimated_weighted_tokens"],
                              "unknown_steps": lifetime["unknown_steps"], "unknown_step_tokens": unknown_charge, "basis": basis,
                              "exceeded": lane_budget is not None and basis >= lane_budget}
    final_path = ctx.run_dir(result["final_run_id"] or run_id) / "maf-result.json"
    if final_path.is_file():  # a re-invocation never erases the earlier outcome: it moves to maf-history/
        prior = _load(ctx, final_path)
        if prior.get("status") != "PENDING":
            history = final_path.parent / "maf-history"
            _save(ctx, history / f"maf-result-{len(list(history.glob('*.json'))) + 1}.json", prior)
    _save(ctx, final_path, {
        "root_run_id": run_id,
        "status": result["status"],
        "human_approval_required": result["status"] == "HUMAN_APPROVAL_REQUIRED",
        "reviews": [{k: r.get(k) for k in ("decision", "stage", "profile", "model", "implementer", "reason")}
                    for r in result.get("reviews", [])],
        "implementers": [a.get("implementer") for a in state.attempts],
        "reason": result.get("reason"),
        "review_failure": result.get("review_failure"),
        "usage_status": result["usage_status"],
        "token_budget": result["token_budget"],
    })
    # token_usage = what THIS invocation spent (new worker runs, successful and failed reviews); the lifetime total
    # of the run comes from the cumulative ledger, so a review-only retry never counts the coded work twice.
    # Every review call of this invocation is in invocation_reviews (fast, deep, failed, retried); an injected reviewer
    # records none and reports usage in its own result instead.
    review_usages = ([entry.get("usage") for entry in invocation_reviews] if invocation_reviews
                     else [review.get("usage") for review in result.get("reviews", [])])
    spent = _sum_usage([
        *review_usages,
        *(attempt.get("engine_result", {}).get("usage") for attempt in state.attempts[state.preexisting:]),
    ])
    new_steps = [tokens.worker_step(attempt.get("engine_result") or {}) for attempt in state.attempts[state.preexisting:]]
    new_steps += [tokens.review_step(entry) for entry in invocation_reviews]
    new_steps += [tokens.review_step(review) for review in result.get("reviews", []) if "usage" in review and not invocation_reviews]
    this_invocation = tokens.summarize(new_steps)
    ledger_path = ctx.run_dir(run_id) / "maf-usage.json"
    invocations = _load(ctx, ledger_path)["invocations"] if ledger_path.is_file() else []
    invocations.append({"at": datetime.now(timezone.utc).isoformat(), "usage": spent,
                        "reused_attempts": state.preexisting, "review_calls": len(invocation_reviews),
                        "usage_status": this_invocation["usage_status"], "unknown_steps": this_invocation["unknown_steps"],
                        "cached_cost_share": tokens.cached_cost_share(spent)})
    _save(ctx, ledger_path, {"invocations": invocations})
    result["token_usage"] = spent
    result["unknown_usage_steps"] = this_invocation["unknown_steps"]  # steps of THIS invocation that ran but reported nothing
    result["cached_cost_share"] = tokens.cached_cost_share(spent)
    result["token_usage_lifetime"] = _sum_usage(item["usage"] for item in invocations)
    return result
