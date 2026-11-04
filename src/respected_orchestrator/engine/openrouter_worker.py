"""OpenRouter worker: `_openrouter MODEL PROMPT` for the read roles, and `run_in_lane` for whole tasks.

A model behind an API has no tools, so it never touches files itself: for a task the engine shows it the owned files,
the model answers with whole-file replacements as JSON, and the engine writes them after checking every path against
the task scope. The key lives only in the DPAPI vault; the egress opt-in (ADR-007) stays the operator's environment
switch.
"""
import json
import sys
import time
import types
import uuid
from pathlib import Path

from ..context import default_data_root
from . import lanes
from .processes import ProcessStopped
from .provider import ProviderClient, ProviderError
from .provider_policy import ProviderDenied
from .secret_vault import SecretVault, VaultUnavailable

TIMEOUT = 120.0
RETRY_DELAYS = (3.0, 8.0)  # free models answer 429 often; retries are explicit and bounded, never another model
MAX_FILES = 25  # files the model is shown, and may return
MAX_FILE_BYTES = 120_000
MAX_CONTEXT_CHARS = 200_000
FAILURES = (ProviderDenied, ProviderError, VaultUnavailable)


def vault():
    return SecretVault(default_data_root() / "provider-key.dpapi")


def call(model, prompt, timeout=TIMEOUT, sleep=None):
    """One completion with the bounded 429/5xx retries. Raises ProviderDenied, ProviderError or VaultUnavailable."""
    client = ProviderClient(vault=vault())
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return client.complete(model=model, messages=[{"role": "user", "content": prompt}],
                                   idempotency_key=uuid.uuid4().hex, timeout=timeout)
        except ProviderError as error:
            if not error.retryable or attempt == len(RETRY_DELAYS):
                raise
            (sleep or time.sleep)(RETRY_DELAYS[attempt])


def failure_text(error):
    if isinstance(error, ProviderDenied):
        return f"provider_denied: {error}"
    if isinstance(error, ProviderError):
        return error.kind + (f" (HTTP {error.status})" if error.status else "")
    return f"vault_unavailable: {error}"


def envelope(result):
    return json.dumps({"type": "openrouter", "content": result["content"], "model": result["model"],
                       "usage": result["usage"]}, ensure_ascii=False)


def _normalize(items):
    return tuple(item.replace("\\", "/").rstrip("/") for item in items)


def _owned_files(worktree, ownership, forbidden):
    """(relative path, text) of the text files the task owns (a directory contributes what is inside it), within the caps."""
    denied = _normalize(forbidden)
    seen, used = [], 0
    for entry in _normalize(ownership):
        base = worktree / entry
        candidates = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file()) if base.is_dir() else []
        for path in candidates:
            relative = path.relative_to(worktree).as_posix()
            if relative in seen or relative.startswith(".git/") or lanes._path_is_owned(relative, denied):
                continue
            try:
                text = path.read_text("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if len(text.encode("utf-8")) > MAX_FILE_BYTES or used + len(text) > MAX_CONTEXT_CHARS or len(seen) >= MAX_FILES:
                continue
            seen.append(relative)
            used += len(text)
            yield relative, text


def build_prompt(worktree, request):
    write = request["kind"] == "write"

    def listing(items):
        return "\n".join(f"- {item}" for item in items) or "- (none)"
    parts = ["You are a coding worker without tools or a shell: you see only the files below and answer with ONE JSON object.",
             "## TASK\n" + request["task"],
             "## YOU MAY " + ("MODIFY" if write else "READ") + " ONLY\n" + listing(request["ownership"]),
             "## FORBIDDEN\n" + listing(request["forbidden"]),
             "## ACCEPTANCE (the engine runs these afterwards; you do not)\n" + listing(json.dumps(c) for c in request["acceptance"])]
    for relative, text in _owned_files(worktree, request["ownership"], request["forbidden"]):
        parts.append(f"## FILE {relative}\n```\n{text}\n```")
    if write:
        parts.append('## ANSWER FORMAT\nReply with ONLY a JSON object, no prose and no code fence: '
                     '{"status": "success", "summary": "...", "files": [{"path": "relative/path", "content": "the COMPLETE new content of that file"}]}. '
                     'List only files you change, each with its full content; a file may be new. '
                     'If you cannot do it: {"status": "failed", "reason": "..."}.')
    else:
        parts.append('## ANSWER FORMAT\nReply with ONLY a JSON object, no prose and no code fence: {"status": "success", "report": "..."}. '
                     'If you cannot do it: {"status": "failed", "reason": "..."}.')
    return "\n\n".join(parts)


def _plan_writes(worktree, payload, ownership, forbidden):
    """[(target, bytes)] for every returned file, or ValueError. Nothing is written unless every file passes."""
    files = payload.get("files")
    if not isinstance(files, list) or not files or len(files) > MAX_FILES:
        raise ValueError(f"files must be a list of 1..{MAX_FILES} entries")
    root = worktree.resolve()
    owned, denied = _normalize(ownership), _normalize(forbidden)
    planned = []
    for item in files:
        path, content = (item.get("path"), item.get("content")) if isinstance(item, dict) else (None, None)
        if not isinstance(path, str) or not isinstance(content, str) or not path.strip():
            raise ValueError("each file needs a path and its full content as strings")
        relative = path.replace("\\", "/").strip()
        parts = Path(relative).parts
        if Path(relative).is_absolute() or relative.startswith("/") or ".." in parts or (parts and parts[0] == ".git"):
            raise ValueError(f"path is not a bounded relative path: {path}")
        if not lanes._path_is_owned(relative, owned) or lanes._path_is_owned(relative, denied):
            raise ValueError(f"path is outside the task scope: {path}")
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"path leaves the worktree: {path}")
        data = content.encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"file is too large: {path}")
        planned.append((target, data))
    return planned


def run_in_lane(worktree, request, deadline, cancel_path):
    """The engine's own worker for OpenRouter tasks. No sandbox is needed: no model-controlled code runs here.

    The usual scope check, acceptance run and signed evidence follow exactly as for any other worker.
    Returns an object shaped like a finished process (stdout, stderr, returncode)."""
    def done(stdout="", stderr="", code=0):
        return types.SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)
    model = (request.get("worker_profile") or "").strip()
    if not model:
        return done(stderr="openrouter needs a model name as its profile", code=2)
    if cancel_path.exists():
        raise ProcessStopped("cancelled")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProcessStopped("timed_out")
    try:
        result = call(model, build_prompt(worktree, request), timeout=min(TIMEOUT, remaining))
    except FAILURES as error:
        return done(stderr=failure_text(error), code=1)
    payload = lanes._parse_json_object(result["content"] or "")
    if request["kind"] == "write":
        if payload is None:
            return done(stdout=envelope(result), stderr="invalid_worker_result: the reply is not a JSON object", code=1)
        if str(payload.get("status", "")).casefold() == "success":
            try:
                for target, data in _plan_writes(worktree, payload, request["ownership"], request["forbidden"]):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
            except ValueError as error:
                return done(stdout=envelope(result), stderr=f"invalid_worker_result: {error}", code=1)
    return done(stdout=envelope(result))


def main(argv):
    if len(argv) != 2 or not argv[0].strip():
        print("usage: respected-orchestrator _openrouter MODEL PROMPT", file=sys.stderr)
        return 2
    model, prompt = argv
    try:
        result = call(model, prompt)
    except FAILURES as error:
        print(failure_text(error), file=sys.stderr)
        return 1
    print(envelope(result))
    return 0
