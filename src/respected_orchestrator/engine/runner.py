"""Any-to-any tasks, extracted adapters and guarded worktree execution."""
import datetime as dt
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from uuid import uuid4

from . import lanes, sandbox
from . import budget, winproc
from ..interfaces import memory
from ..workflows import roles
from ..context import EngineContext, atomic_write_json, safe_path, validate_project
from .processes import ProcessStopped, execute
from .codex import _is_turn_completed, stream_verified_complete

SUPPORTED_AGENTS = ("claude", "gemini", "antigravity", "agy", "codex", "cursor", "custom")
SELF_CHECK = (
    "\n\n## Self-check (required)\nBefore you finish, run the acceptance commands yourself, review your own "
    "diff for defects and scope creep, and fix what you find. If running a command is denied, do not retry or work "
    "around it: read the code instead, make sure the files are written, and finish. Then report the final JSON result.\n"
    "\n## Token discipline\nEvery tool call re-reads the whole conversation, so long tool output is paid again on each "
    "later step. Read only the files and line ranges you need, never re-read a file you already have, keep command "
    "output short (filter or limit it), and do not explore beyond the task's scope.\n"
)
# For tools without shell approval: a denied command ends their turn with nothing written, so never ask for one.
NO_SHELL_SELF_CHECK = (
    "\n\n## Self-check (required)\nDo not run any command: the engine runs the acceptance commands itself after you "
    "finish. Write the files with your file-editing tools, re-read what you wrote for defects and scope creep, fix them, "
    "then report the final JSON result.\n"
    + SELF_CHECK[SELF_CHECK.index("\n## Token discipline"):]
)
TERMINAL = {"completed", "failed", "cancelled", "timed_out", "interrupted"}
# Stable 0.162.0/0.162.1 lack OpenAI's active-runtime ACL fix (#51822).
# the brief travels as one command-line argument; Windows caps a command line at 32 767 characters (audit P1 #18)
MAX_TASK_CHARS = 20000 if sys.platform == "win32" else 60000
LOCAL_CODEX = Path(__file__).resolve().parents[3] / ".runtime" / "codex-0.162.0-alpha.20" / "bin" / "codex.exe"


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", cleaned).strip("-")[:40] or "task"


def get_cli_command(agent: str) -> list[str] | None:
    if agent == "codex" and sys.platform == "win32" and LOCAL_CODEX.is_file():
        return [str(safe_path(LOCAL_CODEX))]
    executable = {"antigravity": "agy", "agy": "agy", "cursor": "cursor-agent"}.get(agent, agent)
    found = shutil.which(executable)
    # cmd.exe would re-parse the prompt of a .cmd/.bat shim (truncation, command injection): such workers are unavailable (audit P0 #2)
    if found and Path(found).suffix.lower() in {".cmd", ".bat"}:
        return None
    return [found] if found else None


def tool_available(tool):
    return tool == "custom" or get_cli_command(tool) is not None


# Model-selection flags of CLIs that take the profile as a model name (codex profiles are handled below).
_MODEL_FLAG = {"claude": "--model", "gemini": "--model", "cursor": "--model", "agy": "--model", "antigravity": "--model"}
# Headless CLIs refuse edits unless told to accept them; this allows file edits only (shell stays unapproved) and the
# engine still validates scope, runs acceptance outside the worker and rejects out-of-scope changes.
_EDIT_FLAGS = {"claude": ["--permission-mode", "acceptEdits"], "gemini": ["--approval-mode", "auto_edit"],
               "agy": ["--mode", "accept-edits"], "antigravity": ["--mode", "accept-edits"]}


def command_for(worker, prompt, custom=(), profile=None, write=False):
    if worker == "custom":
        return [part.replace("{prompt}", prompt).replace("{profile}", profile or "") for part in custom]
    command = get_cli_command(worker)
    if command is None:
        raise lanes.WorkerUnavailableError(f"Worker CLI '{worker}' unavailable")
    if worker in _MODEL_FLAG:
        envelope = {"claude": ["--output-format", "json"], "gemini": ["-o", "json"],
                    "agy": ["--output-format", "json"], "antigravity": ["--output-format", "json"]}.get(worker, [])
        return [*command, *([_MODEL_FLAG[worker], profile] if profile else []),
                *(_EDIT_FLAGS.get(worker, []) if write else []), *envelope, "-p", prompt]
    if worker == "codex":
        profile = (profile or os.environ.get("RESPECTED_CODEX_PROFILE", "")).strip()
        # Explicit OS sandbox and no approval prompts: fail closed rather than inherit a
        # danger-full-access user config or wait for a human that is not there.
        return [*command, "exec", "--sandbox", "workspace-write", "-c", 'approval_policy="never"',
                *(["-p", profile] if profile else []), "--json", prompt]
    return [*command, "exec", "--json", prompt]


def _usage(raw_input, cached, output, reasoning):
    """Engine usage dict (same weighting as Codex); None when the tool did not report the numbers."""
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (raw_input, cached, output)):
        return None
    return {"raw_input_tokens": raw_input, "cached_input_tokens": cached, "output_tokens": output,
            "reasoning_tokens": reasoning if isinstance(reasoning, int) else None,
            "estimated_weighted_tokens": max(0, raw_input - cached) + round(cached * 0.03) + output}


def tool_result(tool, stdout):
    """(text, usage, model, error) from a headless CLI's JSON envelope. Anything that is not the tool's own envelope
    (custom commands, plain text, an unknown shape) passes through unchanged with usage None = UNKNOWN, never zero."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return stdout, None, None, None
    if not isinstance(data, dict):
        return stdout, None, None, None
    if tool == "claude" and data.get("type") == "result":
        raw = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        fresh, cached = (raw.get("input_tokens"), raw.get("cache_creation_input_tokens", 0)), raw.get("cache_read_input_tokens", 0)
        known = all(isinstance(v, int) for v in (*fresh, cached))
        details = raw.get("output_tokens_details") if isinstance(raw.get("output_tokens_details"), dict) else {}
        usage = _usage(sum(fresh) + cached, cached, raw.get("output_tokens"), details.get("thinking_tokens")) if known else None
        models = data.get("modelUsage") if isinstance(data.get("modelUsage"), dict) else {}
        error = "claude reported an error result" if data.get("is_error") else None
        return str(data.get("result", "")), usage, next(iter(models), None), error
    if tool in ("agy", "antigravity") and "response" in data:
        raw = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        usage = _usage(raw.get("input_tokens"), raw.get("cache_read_tokens", 0), raw.get("output_tokens"), raw.get("thinking_tokens"))
        error = None if str(data.get("status", "")).casefold() == "success" else f"agy status {data.get('status')}"
        return str(data.get("response", "")), usage, None, error
    if tool == "gemini" and ("response" in data or "error" in data):  # shape taken from the CLI docs; not verified live
        models = ((data.get("stats") or {}).get("models") or {}) if isinstance(data.get("stats"), dict) else {}
        tokens = [m.get("tokens") for m in models.values() if isinstance(m, dict) and isinstance(m.get("tokens"), dict)]
        usage = _usage(sum(t.get("prompt", 0) for t in tokens), sum(t.get("cached", 0) for t in tokens),
                       sum(t.get("candidates", 0) for t in tokens), sum(t.get("thoughts", 0) for t in tokens)) if tokens else None
        return str(data.get("response", "")), usage, next(iter(models), None), (str(data["error"])[:200] if data.get("error") else None)
    return stdout, None, None, None


def _final_json(text):
    payload = lanes._parse_json_object(text)
    if payload is not None:
        return payload
    # Accept prose around exactly one fenced block; any other fence is ambiguous.
    if text.count("```") != 2:
        return None
    match = re.search(r"```json[ \t]*\r?\n(.*?)\r?\n?```", text, re.DOTALL | re.IGNORECASE)
    return lanes._parse_json_object(match.group(1)) if match else None


def _codex_payload(stdout):
    failure = {"status": "failed", "error": "Invalid or failed Codex JSONL result"}
    try:
        events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    except json.JSONDecodeError:
        return failure
    if not events or any(not isinstance(event, dict) for event in events):
        return failure
    # Codex emits non-fatal "Reconnecting... n/m" notices as error events and then completes one turn.
    def reconnect(event):
        message = event.get("message")
        return isinstance(message, str) and message.startswith("Reconnecting...")
    completed_turns = sum(event.get("type") == "turn.completed" for event in events)
    if completed_turns != 1 or events[-1].get("type") != "turn.completed" or any(
        event.get("type") == "turn.failed" or (event.get("type") == "error" and not reconnect(event)) for event in events
    ):
        return failure
    items = [event.get("item") for event in events if event.get("type") == "item.completed"]
    message = next((item for item in reversed(items)
                    if isinstance(item, dict) and item.get("type") == "agent_message"), {})
    text = message.get("text")
    payload = _final_json(text) if isinstance(text, str) else None
    return payload if payload is not None and "status" in payload else failure


def _codex_metadata(stdout):
    try:
        events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    except json.JSONDecodeError:
        events = []
    event = next((item for item in reversed(events)
                  if isinstance(item, dict) and item.get("type") == "turn.completed"), {})
    usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
    def integer(name):
        value = usage.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    raw_input = integer("input_tokens")
    cached = integer("cached_input_tokens")
    output = integer("output_tokens")
    reasoning = integer("reasoning_output_tokens")
    weighted = None
    if raw_input is not None and cached is not None and output is not None:
        weighted = max(0, raw_input - cached) + round(cached * 0.03) + output
    model = event.get("model") or event.get("model_id")
    return {
        "usage": {
            "raw_input_tokens": raw_input,
            "cached_input_tokens": cached,
            "output_tokens": output,
            "reasoning_tokens": reasoning,
            "estimated_weighted_tokens": weighted,
        },
        "model": model if isinstance(model, str) else None,
    }


_RESTRICTED_KEYS = set()


def _restrict_key(path):
    # Windows: drop inherited ACEs so only this user (not the Codex sandbox users) can read the key.
    if os.name != "nt" or path in _RESTRICTED_KEYS:
        return
    user = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ['USERNAME']}".lstrip("\\")
    winproc.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(F)"],
                   capture_output=True, check=True, timeout=30)
    _RESTRICTED_KEYS.add(path)


def _key_path(ctx):
    _key(ctx)  # makes sure it exists with its private ACL before the sandbox denies itself access
    return safe_path(ctx.data_root / ".engine-key")


def _key(ctx):
    path = safe_path(ctx.data_root / ".engine-key")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # Create privately, close the ACL while the file is still empty, write the secret, then publish atomically:
        # the key path never exists with secret bytes under an inherited ACL, nor half-written.
        tmp = path.with_name(f".engine-key.{os.getpid()}.{os.urandom(4).hex()}.tmp")
        descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                _restrict_key(tmp)
                handle.write(os.urandom(32))
                handle.flush()
                os.fsync(handle.fileno())
            os.link(tmp, path)  # fails if another process published first: then its key wins
        except FileExistsError:
            pass
        finally:
            _RESTRICTED_KEYS.discard(tmp)
            tmp.unlink(missing_ok=True)
    _restrict_key(path)
    key = path.read_bytes()
    if os.name != "nt" and path.stat().st_mode & 0o077:
        path.chmod(0o600)  # POSIX only; Windows relies on the user-profile ACL of the data root
    if len(key) != 32:
        raise ValueError("Invalid engine key; preserve existing evidence")
    return key


def _signature(ctx, payload):
    return hmac.new(_key(ctx), json.dumps(payload, sort_keys=True, ensure_ascii=True).encode(), hashlib.sha256).hexdigest()


def _save(ctx, path, payload):
    atomic_write_json(path, {"payload": payload, "signature": _signature(ctx, payload)})


def _load(ctx, path):
    envelope = json.loads(safe_path(path).read_text(encoding="utf8"))
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict):
        raise ValueError("Invalid owned evidence")
    payload = envelope["payload"]
    if not hmac.compare_digest(str(envelope.get("signature", "")), _signature(ctx, payload)):
        raise ValueError("Evidence tampered")
    return payload


def _drop_bytecode(root):
    for path in Path(root).rglob("__pycache__"):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
    for path in Path(root).rglob("*.pyc"):
        path.unlink(missing_ok=True)


def _command(value):
    if not isinstance(value, list) or not value or not all(isinstance(s, str) and s and "\0" not in s for s in value):
        raise ValueError("Command must be a non-empty JSON string array")
    bad = ("--dangerously", "--yolo", "bypasspermissions", "danger-full-access", "approval-mode=yolo", "--approval-mode yolo", "sandbox_mode")
    if any(s.casefold().startswith(bad) or any(b in s.casefold() for b in bad[2:]) or s in {"-y", "--sandbox=none"} for s in value)             or any(a.casefold() == "--approval-mode" and b.casefold() == "yolo" for a, b in zip(value, value[1:])):
        raise ValueError("Permission bypass flags are refused")
    return value


def _scope(project, values):
    if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
        raise ValueError("Scope must be a JSON string array")
    output = []
    for value in values:
        if Path(value).is_absolute() or ".." in Path(value).parts or Path(value) == Path("."):
            raise ValueError("Scope must be bounded relative paths")
        safe_path(project / value)
        normalized = lanes.normalize_repo_path(project, value)
        if normalized == ".git" or normalized.startswith(".git/"):
            raise ValueError("Git administration is outside task scope")
        output.append(normalized)
    return output


def _profile_field(value):
    if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 100):
        raise ValueError("Invalid profile name")
    return value.strip() if value else None


def _tool_field(value):
    if value is not None and value not in SUPPORTED_AGENTS:
        raise ValueError("Unsupported reviewer tool")
    return value


def _workflow(value):
    if not isinstance(value, dict):
        raise ValueError("Workflow must be a JSON object")
    max_corrections = value.get("max_corrections", 2)
    deep_review = value.get("deep_review", "never")
    reviewer_profile = _profile_field(value.get("reviewer_profile"))  # None = unassigned here: Hub default / auto / error later
    deep_review_profile = _profile_field(value.get("deep_review_profile"))
    reviewer_tool = _tool_field(value.get("reviewer_tool"))
    deep_review_tool = _tool_field(value.get("deep_review_tool"))
    independent = value.get("require_independent_review")
    risk_changed_files = value.get("risk_changed_files", 5)
    timeout_seconds = value.get("timeout_seconds")  # None = derived from worker + review budgets
    review_timeout_seconds = value.get("review_timeout_seconds")  # None = provider-aware default
    review_retries = value.get("review_retries", 1)  # bounded extra review attempts after a timeout/disconnect
    max_weighted_tokens = value.get("max_weighted_tokens")  # None = no hard lane budget
    unknown_step_tokens = value.get("unknown_step_tokens", budget.UNKNOWN_STEP_TOKENS_DEFAULT)
    escalate_profile = value.get("escalate_profile")  # None = never hand the code to another model
    escalate_from_round = value.get("escalate_from_round", 2)
    if escalate_profile is not None and (not isinstance(escalate_profile, str) or not escalate_profile.strip()
                                         or len(escalate_profile) > 100):
        raise ValueError("Invalid escalation profile")
    if type(escalate_from_round) is not int or not 1 <= escalate_from_round <= 2:
        raise ValueError("Invalid escalation round")
    if (type(max_corrections) is not int or not 0 <= max_corrections <= 2
            or deep_review not in {"never", "always", "risk_based"}
            or (independent is not None and not isinstance(independent, bool))
            or type(risk_changed_files) is not int or risk_changed_files < 1
            or (timeout_seconds is not None and (type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 14400))
            or (review_timeout_seconds is not None
                and (type(review_timeout_seconds) is not int or not 1 <= review_timeout_seconds <= 3600))
            or type(review_retries) is not int or not 0 <= review_retries <= 2
            or (max_weighted_tokens is not None and (type(max_weighted_tokens) is not int or not 1000 <= max_weighted_tokens <= budget.MAX_BUDGET))
            or type(unknown_step_tokens) is not int or not 0 <= unknown_step_tokens <= 10_000_000
            or not isinstance(value.get("human_approval", False), bool)):
        raise ValueError("Invalid workflow policy")
    return {
        "max_corrections": max_corrections,
        "deep_review": deep_review,
        "reviewer_profile": reviewer_profile,
        "deep_review_profile": deep_review_profile,
        "reviewer_tool": reviewer_tool,
        "deep_review_tool": deep_review_tool,
        "require_independent_review": independent,
        "risk_changed_files": risk_changed_files,
        "timeout_seconds": timeout_seconds,
        "review_timeout_seconds": review_timeout_seconds,
        "review_retries": review_retries,
        "max_weighted_tokens": max_weighted_tokens,
        "unknown_step_tokens": unknown_step_tokens,
        "human_approval": value.get("human_approval", False),
        "escalate_profile": escalate_profile.strip() if escalate_profile else None,
        "escalate_from_round": escalate_from_round,
    }


def project_fingerprint(project):
    digest = hashlib.sha256()
    for args in [("rev-parse", "HEAD"), ("diff", "--binary", "--full-index", "HEAD", "--")]:
        result = winproc.run(["git", *args], cwd=project, capture_output=True, check=True, timeout=30)
        digest.update(result.stdout)
    for name in lanes._git_path_list(project, "ls-files", "--others", "--exclude-standard", "-z"):
        path = safe_path(project / name)
        digest.update(name.encode("utf8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _explicit_roles(request, workflow):
    """Assignments the task prompt states itself: `roles` plus the per-field spellings (worker, worker_profile,
    workflow.reviewer_*). Stating one role two ways with different values is an error, never a silent pick."""
    asked = request.get("roles", {})
    if not isinstance(asked, dict):
        raise roles.RoleError("BAD_ASSIGNMENT", "roles must be an object of role -> assignment")
    for role in asked:
        if role in ("tester", "coordinator"):  # accepted by the settings model but nothing runs them yet: never pretend (audit P2)
            raise roles.RoleError("ROLE_NOT_EXECUTABLE", f"Role {role} cannot be executed yet", "Use planner, implementer, reviewer, deep_reviewer, debugger or master.")
    asked = {role: dict(value) if isinstance(value, dict) else {"profile": value} for role, value in asked.items()}
    spelled = {"implementer": (request.get("worker"), request.get("worker_profile")),
               "reviewer": (workflow["reviewer_tool"], workflow["reviewer_profile"]),
               "deep_reviewer": (workflow["deep_review_tool"], workflow["deep_review_profile"])}
    for role, (tool, profile) in spelled.items():
        for key, value in (("tool", tool), ("profile", profile)):
            if value is None:
                continue
            entry = asked.setdefault(role, {})
            if entry.get(key) not in (None, value):
                raise roles.RoleError("ROLE_CONFLICT", f"Role {role} has two different {key} values in the task",
                                      "State each assignment once.")
            entry[key] = value
    return asked


def _track_record(ctx):
    from . import track_record  # imports runner, so it is loaded only when automatic assignment needs it
    return track_record.stats(ctx.data_root)


def _keep_sources(assignments, previous):
    """A retried or corrected task re-submits concrete values; keep where they originally came from."""
    for role, entry in assignments.items():
        before = (previous or {}).get(role)
        if before and (before.get("tool"), before.get("profile")) == (entry["tool"], entry["profile"]):
            entry["source"] = before.get("source", entry["source"])
    return assignments


def settings_root(ctx, main_root=None):
    """Campaign lanes hold no settings.json or memory token; the main data root is handed down by environment."""
    raw = str(main_root) if main_root is not None else os.environ.get("RESPECTED_ORCH_MAIN_ROOT")
    if raw and os.path.isabs(raw) and os.path.isfile(os.path.join(raw, "settings.json")):
        return Path(raw)
    return ctx.data_root


def _memory_policy(request, settings, root):
    value = request.get("memory")
    if value is None:
        value = {}
    if not isinstance(value, dict) or not set(value) <= {"use", "query"}:
        raise ValueError("memory must be an object with optional use and query")
    use, query = value.get("use"), value.get("query")
    if use is not None and not isinstance(use, bool):
        raise ValueError("memory.use must be a boolean")
    if query is not None and (not isinstance(query, str) or not 1 <= len(query) <= 200):
        raise ValueError("memory.query must be 1..200 characters")
    ready = memory.configured(settings, root)
    if use is True and not ready:
        raise ValueError("memory requested but SecondBrain access is not enabled in the Hub")
    if use is not None:
        policy = {"use": use, "source": "explicit"}
    else:  # enabling memory in the Hub is a permission, not a default: every task opts in with memory.use
        policy = {"use": False, "source": "off"}
    if query is not None:
        policy["query"] = query
    return policy


def create_task(ctx: EngineContext, request: dict, *, settings: dict | None = None, history=None, main_root=None) -> dict:
    if not isinstance(request, dict):
        raise ValueError("Task request must be a JSON object")
    project = validate_project(ctx, Path(request.get("project_root", "")))
    if Path(lanes._git(project, "rev-parse", "--show-toplevel").stdout.strip()).resolve() != project:
        raise ValueError("Select the Git project root")
    task = request.get("task")
    worker, kind = request.get("worker", "codex"), request.get("kind", "write")
    master = request.get('master', 'user')
    if master not in (*SUPPORTED_AGENTS, 'user'):
        raise ValueError('Unsupported master label')
    if not isinstance(task, str) or not task.strip() or len(task) > MAX_TASK_CHARS or worker not in SUPPORTED_AGENTS or kind not in {"read", "write"}:
        raise ValueError("Invalid task, worker or execution kind")
    ownership = _scope(project, request.get("ownership", []))
    if not ownership:
        raise ValueError("An explicit execution scope is required")
    forbidden = _scope(project, request.get("forbidden", []))
    acceptance = request.get("acceptance", [])
    if not isinstance(acceptance, list) or (kind == "write" and not acceptance):
        raise ValueError("Write tasks require explicit acceptance commands")
    acceptance = [_command(item) for item in acceptance]
    custom = _command(request.get("command")) if worker == "custom" else []
    if not isinstance(request.get("worker_profile", ""), str) or len(request.get("worker_profile", "")) > 100:
        raise ValueError("Worker profile must be a bounded string")
    workflow = _workflow(request.get("workflow", {}))
    # Role assignment: explicit task prompt > Hub defaults (settings.json) > automatic recommendation (opt-in).
    memory_settings = roles.read_settings(settings_root(ctx, main_root)) if settings is None else settings
    settings = roles.read_settings(ctx.data_root) if settings is None else settings
    memory_policy = _memory_policy(request, memory_settings, settings_root(ctx, main_root))
    # A reviewer is only required when the MAF workflow runs (it re-checks and fails before any paid work).
    assigned = roles.resolve(settings, _explicit_roles(request, workflow), ["implementer"], optional=["reviewer", "debugger"],
                             tools=list(SUPPORTED_AGENTS), available=tool_available, check_roles={"implementer"},
                             history=history or (lambda: _track_record(ctx)))
    assigned = _keep_sources(assigned, request.get("role_assignments"))
    reviewer = assigned.get("reviewer")
    # Unspecified deep reviewer = the reviewer (a documented inheritance, not a model rule).
    deep = assigned.get("deep_reviewer", reviewer)
    required = workflow["require_independent_review"]
    if required is None:
        required = bool(settings.get("require_independent_review", False))
    notes = roles.check_independence({k: v for k, v in {"implementer": assigned["implementer"], "reviewer": reviewer,
                                                       "deep_reviewer": deep}.items() if v}, required)
    roles.refuse_blocked(settings, workflow["escalate_profile"])
    worker, worker_profile = assigned["implementer"]["tool"], assigned["implementer"]["profile"]
    workflow.update(reviewer_profile=reviewer["profile"] if reviewer else None,
                    reviewer_tool=reviewer["tool"] if reviewer else None,
                    deep_review_profile=deep["profile"] if deep else None,
                    deep_review_tool=deep["tool"] if deep else None,
                    require_independent_review=required)
    correction_of = request.get("correction_of")
    correction_round = request.get("correction_round", 0)
    if correction_of is not None and (not isinstance(correction_of, str) or not correction_of):
        raise ValueError("Correction parent must be a run identity")
    if type(correction_round) is not int or not 0 <= correction_round <= 2:
        raise ValueError("Correction round must be 0..2")
    inherited_patch_run_id = request.get("inherited_patch_run_id")
    inherited_patch_sha256 = request.get("inherited_patch_sha256")
    if inherited_patch_run_id is not None:
        try:
            ctx.run_dir(inherited_patch_run_id)
        except ValueError as error:
            raise ValueError("Invalid inherited patch run identity") from error
    if (inherited_patch_run_id is None) != (inherited_patch_sha256 is None):
        raise ValueError("Inherited patch run and hash must be supplied together")
    if inherited_patch_sha256 is not None and not (
            isinstance(inherited_patch_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", inherited_patch_sha256)):
        raise ValueError("Invalid inherited patch hash")
    timeout = request.get("timeout_seconds", 900)
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("Deadline must be 1..3600 seconds")
    apply_root = request.get("apply_root")  # real source when the task runs in a Git mirror of a non-Git project
    if apply_root is not None:
        apply_root = str(validate_project(ctx, Path(apply_root)))
    include_untracked_owned = request.get("include_untracked_owned", False)
    if not isinstance(include_untracked_owned, bool):
        raise ValueError("Untracked ownership inclusion must be a boolean")
    include = _scope(project, request.get("include_untracked", []))
    context_paths = _scope(project, request.get("context_paths", []))
    if len(context_paths) > 200 or any(lanes._path_is_owned(name, forbidden) for name in context_paths):
        raise ValueError("Context paths must be at most 200 files and outside the forbidden scope")
    if include_untracked_owned and (project / ".git").exists():
        # untracked files inside the allowed scope are real inputs (like dirty tracked ones); a lane built from HEAD alone
        # would recreate them from scratch and produce a patch that cannot integrate ("new file ... already exists").
        listed = lanes._git_path_list(project, "ls-files", "--others", "--exclude-standard", "-z")
        found = [name for name in listed
                 if lanes._path_is_owned(name, ownership) and not lanes._path_is_owned(name, forbidden)]
        if len(found) > 200:
            raise ValueError("Too many untracked inputs in scope; list them explicitly in include_untracked")
        include = sorted({*include, *_scope(project, found)})
    for name in include:
        if not lanes._path_is_owned(name, ownership) or lanes._path_is_owned(name, forbidden):
            raise ValueError("Selected untracked input must be within allowed scope")
    if worker != "custom" and get_cli_command(worker) is None:
        raise ValueError(f"Worker CLI '{worker}' unavailable")
    run_id = f"run-{dt.datetime.now(dt.timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:12]}"
    directory = ctx.run_dir(run_id)
    directory.mkdir(parents=True, exist_ok=False)
    payload = dict(run_id=run_id, task=task.strip(), project_root=str(project), master=master, worker=worker, kind=kind,
                   ownership=ownership, forbidden=forbidden, acceptance=acceptance, command=custom,
                   include_untracked=include, context_paths=context_paths, timeout_seconds=timeout, created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                   project_fingerprint=project_fingerprint(project), retry_of=None, retry_depth=0,
                   worker_profile=worker_profile, workflow=workflow, role_assignments=assigned, role_notes=notes,
                   correction_of=correction_of,
                   correction_round=correction_round,
                   inherited_patch_run_id=inherited_patch_run_id,
                   inherited_patch_sha256=inherited_patch_sha256, apply_root=apply_root, memory_policy=memory_policy)
    _save(ctx, directory / "request.json", payload)
    _save(ctx, directory / "status.json", {"run_id": run_id, "status": "queued"})
    return {"run_id": run_id, "status": "queued"}


def _write_status(ctx, directory, status, **details):
    payload = dict(run_id=directory.name, status=status, updated_at=dt.datetime.now(dt.timezone.utc).isoformat(), **details)
    _save(ctx, directory / "status.json", payload)
    return payload


def _validated_inherited_patch(ctx: EngineContext, request: dict, project: Path) -> Path:
    prior_run_id = request.get("inherited_patch_run_id")
    expected_sha256 = request.get("inherited_patch_sha256")
    if request.get("correction_of") is None or prior_run_id is None or expected_sha256 is None:
        raise ValueError("Correction inheritance metadata is invalid")
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Inherited patch hash is invalid")
    prior_directory = ctx.run_dir(prior_run_id)
    prior_request = _load(ctx, prior_directory / "request.json")
    prior_status = _load(ctx, prior_directory / "status.json")
    prior_result = _load(ctx, prior_directory / "result.json")
    prior_parent = prior_request.get("correction_of")
    valid_parent = (
        prior_parent == request["correction_of"]
        or (prior_parent is None and prior_run_id == request["correction_of"])
    )
    for key in ("project_root", "project_fingerprint", "ownership", "forbidden", "include_untracked"):
        if prior_request.get(key) != request.get(key):
            raise ValueError("Inherited patch belongs to a different task scope")
    if not valid_parent or prior_request.get("correction_round", 0) >= request.get("correction_round", 0):
        raise ValueError("Inherited patch is not from a prior correction attempt")
    if prior_status.get("status") != "completed" or prior_result.get("status") != "completed":
        raise ValueError("Inherited patch has no successful completion evidence")
    if prior_result.get("run_id") != prior_run_id or prior_result.get("patch_sha256") != expected_sha256:
        raise ValueError("Inherited patch ownership mismatch")
    patch = safe_path(prior_directory / "worker.patch")
    if not patch.is_file() or hashlib.sha256(patch.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Inherited patch is missing or tampered")
    if patch.stat().st_size and lanes.check_patch_against_master(project, patch) is not lanes.RunStatus.COMPLETE:
        raise ValueError("Inherited patch conflicts with the current project")
    return patch


def _memory_context(ctx, directory, request):
    """Optional SecondBrain recall; never raises. Evidence holds no snippets, titles, token or command."""
    if (request.get("memory_policy") or {}).get("use") is not True:
        return "", None
    try:
        root = settings_root(ctx)
        query = request["memory_policy"].get("query") or memory.query_from_task(request["task"])
        # re-checks configuration now, so a Hub disable or revoke also stops tasks queued earlier
        result = memory.recall_for_task(roles.read_settings(root), root, query)
        items = result.get("results") or []
        evidence = {"status": result.get("status"), "count": result.get("count", 0),
                    "paths": [item.get("path") for item in items], "scores": [item.get("score") for item in items],
                    "index_state": result.get("index_state"), "dropped": result.get("dropped", 0),
                    "dropped_stale": result.get("dropped_stale", 0), "query_terms": len(query.split()),
                    "grant_id": result.get("grant_id")}
        if result.get("code"):
            evidence["code"] = result["code"]
        _save(ctx, directory / "memory-context.json", evidence)
        return memory.context_block(result), {"status": evidence["status"], "count": evidence["count"]}
    except Exception:
        return "", {"status": "error", "count": 0}


def execute_task(ctx: EngineContext, run_id: str) -> dict:
    directory = ctx.run_dir(run_id)
    request = _load(ctx, directory / "request.json")
    status = _load(ctx, directory / "status.json")
    if status["status"] in TERMINAL:
        return status
    claim = safe_path(directory / ".execute-claim")
    try:
        descriptor = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    except FileExistsError:
        raise ValueError("Task already claimed; inspect interrupted work before retrying")
    cancel = safe_path(directory / "cancel.request")
    lock = None
    started = time.monotonic()
    deadline = started + request["timeout_seconds"]
    details = {}
    try:
        if cancel.exists():
            raise ProcessStopped("cancelled")
        project = validate_project(ctx, Path(request["project_root"]))
        if request["project_fingerprint"] != project_fingerprint(project):
            raise ValueError("Project changed since submission; task is stale")
        # One active task per data root. Stale locks are preserved for inspection.
        lock = lanes.WriterLock.acquire(safe_path(ctx.state_dir), run_id, request["kind"], ctx.workspace_root / run_id)
        _write_status(ctx, directory, "running", pid=os.getpid(), phase="preparing")
        paths = lanes.RunPaths(project, safe_path(ctx.workspace_root), ctx.state_dir, directory)
        known_context = "Explicit local task; no required memory integration."
        block, summary = _memory_context(ctx, directory, request)
        if summary:
            details["memory"] = summary
        if block:
            known_context += "\n\n" + block
        run_request = lanes.RunRequest(run_id, run_id, lanes.TaskKind(request["kind"]), request["task"],
                                    known_context, tuple(request["ownership"]),
                                    tuple(request["forbidden"]), tuple(tuple(c) for c in request["acceptance"]),
                                    tuple(request["include_untracked"]), tuple(request.get("context_paths", [])))
        if sys.platform == "win32" and len(str(ctx.workspace_root / run_id)) > 200:
            # Git for Windows rejects worktree paths over ~260 characters ("'$GIT_DIR' too big") once nested files are added.
            raise ValueError(f"Data root path is too long for Git worktrees ({len(str(ctx.workspace_root / run_id))} chars "
                             "for the workspace root, limit 200); use a shorter --data-root")
        lane = lanes.create_lane(run_request, paths)
        details["workspace"] = str(lane.worktree)
        manifest = lanes.overlay_dirty_inputs(lane, run_request.ownership, run_request.include_untracked,
                                              run_request.context_paths)
        lanes.commit_lane_baseline(lane, manifest)
        def scope_ok():
            changes = lanes.collect_worker_changes(lane, run_request.ownership)
            scope = lanes.validate_change_scope(changes, run_request.ownership, run_request.forbidden)
            return changes, scope.allowed and (request["kind"] != "read" or not changes.paths)

        inherited_patch = (_validated_inherited_patch(ctx, request, project)
                           if request.get("inherited_patch_run_id") is not None else None)
        if inherited_patch is not None and inherited_patch.stat().st_size:
            try:
                lanes._git(lane.worktree, "apply", "--check", "--binary", "--whitespace=nowarn", str(inherited_patch))
                lanes._git(lane.worktree, "apply", "--binary", "--whitespace=nowarn", str(inherited_patch))
            except subprocess.CalledProcessError as error:
                return _write_status(ctx, directory, "failed", reason="inherited_patch_conflict",
                                     error=error.stderr, **details)
            changes, allowed = scope_ok()
            if not allowed:
                return _write_status(ctx, directory, "failed", reason="scope_violation",
                                     changed_files=list(changes.paths), **details)
        brief = directory / "brief.md"
        text = lanes.render_brief(run_request, lane)
        if request["worker"] in _EDIT_FLAGS:
            # These CLIs edit through their own file tools and get no shell approval; the shared contract tells the
            # Codex worker to edit with shell commands, which would be denied here and end the turn with nothing written.
            text = text.replace("Edit files with plain shell commands or direct file writes, never the apply_patch tool "
                                "(it fails on Windows); ",
                                "Edit files with your own file-editing tools (shell commands are not approved here); ")
            checklist = NO_SHELL_SELF_CHECK
        else:
            checklist = SELF_CHECK
        brief.write_text(text + checklist, encoding="utf8")
        _write_status(ctx, directory, "running", pid=os.getpid(), phase="worker", **details)
        command = command_for(request["worker"], brief.read_text(encoding="utf8"), request["command"],
                              request.get("worker_profile"), write=request["kind"] == "write")
        def live_output(name, line):
            with safe_path(directory / f'{name}.log').open('a', encoding='utf8') as handle:
                handle.write(lanes._redact(line))
        codex_json = "--json" in command and (request["worker"] == "codex" or Path(command[0]).stem.casefold() == "codex")
        completed = execute(command, lane.worktree, deadline - time.monotonic(), cancel_path=cancel, on_output=live_output,
                            complete_when=_is_turn_completed if codex_json else None,
                            verify_complete=stream_verified_complete if codex_json else None,
                            scrub_env=True)
        (directory / "stdout.log").write_text(lanes._redact(completed.stdout), encoding="utf8")
        (directory / "stderr.log").write_text(lanes._redact(completed.stderr), encoding="utf8")
        text, tool_usage, tool_model, tool_error = tool_result(request["worker"], completed.stdout)
        if tool_usage is not None or tool_model:
            details.update(usage=tool_usage, model=tool_model)
        payload = _codex_payload(completed.stdout) if codex_json else lanes._parse_json_object(
            completed.stdout if request["worker"] in ("agy", "antigravity") else text)
        if codex_json:
            details.update(_codex_metadata(completed.stdout))
        if tool_error:
            return _write_status(ctx, directory, "failed", reason="worker_failed", exit_code=completed.returncode,
                                 provider_status=tool_error, **details)
        classification = lanes.classify_worker_exit(completed.returncode, json.dumps(payload) if codex_json else text, completed.stderr, False)
        logical_failure = payload is not None and (payload.get("error") or ("status" in payload and str(payload["status"]).casefold() not in {"success", "complete", "completed", "ok"}))
        if completed.returncode != 0 or classification is not lanes.RunStatus.COMPLETE or logical_failure:
            return _write_status(ctx, directory, "failed", reason="worker_failed", exit_code=completed.returncode, provider_status=classification.value, **details)
        if request["worker"] in ("agy", "antigravity") and (payload is None or "status" not in payload):
            return _write_status(ctx, directory, "failed", reason="invalid_worker_result", **details)

        changes, allowed = scope_ok()
        if not allowed:
            return _write_status(ctx, directory, "failed", reason="scope_violation", changed_files=list(changes.paths), **details)
        checks = []
        _write_status(ctx, directory, "running", pid=os.getpid(), phase="verifying", **details)
        generated_seen = list(changes.generated)  # what the worker left, reported even though bytecode is dropped below
        _drop_bytecode(lane.worktree)  # worker-planted bytecode is excluded from the patch, so it must not decide acceptance (audit P1 #19)
        try:
            sandboxed = [sandbox.wrap(ctx.data_root, _key_path(ctx), command) for command in request["acceptance"]]
        except sandbox.SandboxError as error:  # fail closed: worker-written code never runs with the engine's authority
            return _write_status(ctx, directory, "failed", reason="sandbox_unavailable", detail=str(error)[:300], **details)
        for index, (command, wrapped) in enumerate(zip(request["acceptance"], sandboxed), 1):
            check = execute(wrapped, lane.worktree, deadline - time.monotonic(), cancel_path=cancel, scrub_env=True)
            (directory / f"check-{index}.log").write_text(lanes._redact(check.stdout + "\n" + check.stderr), encoding="utf8")
            checks.append(dict(command=command, returncode=check.returncode))
            if check.returncode:
                return _write_status(ctx, directory, "failed", reason="test_failed", checks=checks, **details)
        changes, allowed = scope_ok()
        if not allowed:
            return _write_status(ctx, directory, "failed", reason="scope_violation", changed_files=list(changes.paths), **details)
        if cancel.exists():
            raise ProcessStopped("cancelled")
        patch = lanes.export_worker_patch(lane, safe_path(directory / "worker.patch"), run_request.ownership)
        if project_fingerprint(project) != request["project_fingerprint"]:
            return _write_status(ctx, directory, "failed", reason="stale_project", **details)
        if patch.path.stat().st_size and lanes.check_patch_against_master(project, patch.path) is not lanes.RunStatus.COMPLETE:
            return _write_status(ctx, directory, "failed", reason="integration_conflict", **details)
        result = dict(run_id=run_id, status="completed", checks=checks, changed_files=list(changes.paths),
                      generated_artifacts=generated_seen[:100], generated_artifact_count=len(generated_seen),
                      patch_sha256=patch.sha256, project_fingerprint=request["project_fingerprint"],
                      duration_seconds=round(time.monotonic() - started, 3), **details)
        _save(ctx, directory / "result.json", result)
        return _write_status(ctx, directory, "completed", **{k: v for k, v in result.items() if k not in {"run_id", "status"}})
    except ProcessStopped as error:
        (directory / "stopped.log").write_text(lanes._redact(error.stdout + "\n" + error.stderr), encoding="utf8")
        if details.get("workspace") and '"turn.completed"' not in error.stdout:
            # A worker stopped before turn.completed is never success, even if files changed.
            details["worker_incomplete"] = "no_turn_completed"
        return _write_status(ctx, directory, error.reason, **details)
    except Exception as error:
        return _write_status(ctx, directory, "failed", reason="engine_error", error=str(error), **details)
    finally:
        if lock:
            lock.release()


def start_task(ctx, run_id):
    directory = ctx.run_dir(run_id)
    _load(ctx, directory / "request.json")
    if _load(ctx, directory / "status.json")["status"] != "queued":
        raise ValueError("Only queued tasks can start")
    source = str(Path(__file__).resolve().parents[2])  # src/
    env = dict(os.environ, PYTHONPATH=source)
    command = [sys.executable, "-m", "respected_orchestrator", "--data-root", str(ctx.data_root), "_execute", run_id]
    pid = lanes._spawn_detached(command, ctx.app_root, directory / "supervisor.log", env=env)
    _save(ctx, directory / "supervisor.json", dict(run_id=run_id, pid=pid))
    return dict(run_id=run_id, status="queued", pid=pid)


def cancel_task(ctx, run_id):
    directory = ctx.run_dir(run_id)
    status = _load(ctx, directory / "status.json")
    if status["status"] in TERMINAL:
        return status
    safe_path(directory / "cancel.request").touch(exist_ok=True)
    return dict(run_id=run_id, status="cancellation_requested")


def inspect_task(ctx, run_id):
    directory = ctx.run_dir(run_id)
    request = _load(ctx, directory / "request.json")
    status = _load(ctx, directory / "status.json")
    if status["status"] == "running" and not lanes._pid_is_alive(status.get("pid", -1)):
        status = {**status, "status": "interrupted", "reason": "supervisor_exited"}
    elif status["status"] == "queued" and (directory / "supervisor.json").is_file():
        supervisor = _load(ctx, directory / "supervisor.json")
        if not lanes._pid_is_alive(supervisor.get("pid", -1)):
            status = {**status, "status": "interrupted", "reason": "supervisor_exited"}
    logs = {}
    for path in sorted(directory.glob("*.log")):
        path = safe_path(path)
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - 60000))
            logs[path.name] = handle.read(60000).decode("utf8", errors="replace")
    patch = safe_path(directory / "worker.patch")
    preview = ""
    if patch.is_file():
        with patch.open("rb") as handle:
            preview = handle.read(60000).decode("utf8", errors="replace")
    return dict(request=request, **status, logs=logs, patch_preview=preview)


def list_tasks(ctx):
    root = safe_path(ctx.state_dir)
    runs = []
    if root.is_dir():
        for path in sorted(root.glob("run-*"), reverse=True)[:100]:
            try:
                entry = inspect_task(ctx, path.name)
                runs.append({k: v for k, v in entry.items() if k not in {"logs", "patch_preview"}})
            except (ValueError, OSError) as error:
                runs.append(dict(run_id=path.name, status="invalid", error=str(error)))
    return {"runs": runs}


def check_result(ctx, run_id, *, maf_gate=True, accepted_fingerprints=()):
    directory = ctx.run_dir(run_id)
    request = _load(ctx, directory / "request.json")
    status = _load(ctx, directory / "status.json")
    result = _load(ctx, directory / "result.json") if (directory / "result.json").is_file() else {}
    if status["status"] != "completed" or result.get("status") != "completed":
        raise ValueError("Unsuccessful or pending result cannot be accepted")
    if result.get("run_id") != run_id or result.get("project_fingerprint") != request["project_fingerprint"]:
        raise ValueError("Result ownership mismatch")
    if request["kind"] == "write" and (len(result.get("checks", [])) != len(request["acceptance"]) or any(c.get("returncode") != 0 for c in result["checks"])):
        raise ValueError("Result has no successful acceptance evidence")
    maf_result_path = directory / "maf-result.json"
    if maf_gate and maf_result_path.is_file():  # maf_gate=False: re-verify a completed worker before it is (re)reviewed
        maf_result = _load(ctx, maf_result_path)
        if maf_result["status"] != "MASTER_APPROVED":
            approval_path = directory / "maf-approval.json"
            if maf_result["status"] != "HUMAN_APPROVAL_REQUIRED" or not approval_path.is_file():
                raise ValueError("MAF approval is required before acceptance")
            approval = _load(ctx, approval_path)
            if (approval.get("run_id") != run_id
                    or approval.get("root_run_id") != maf_result.get("root_run_id")):
                raise ValueError("MAF approval does not belong to this run")
            if approval.get("patch_sha256") != result.get("patch_sha256"):
                raise ValueError("MAF approval is not bound to this patch; re-approve the current result")
    patch = safe_path(directory / "worker.patch")
    if hashlib.sha256(patch.read_bytes()).hexdigest() != result["patch_sha256"]:
        raise ValueError("Patch tampered")
    project = validate_project(ctx, Path(request["project_root"]))
    current = project_fingerprint(project)
    # accepted_fingerprints: states the supervisor itself created by applying verified sibling lanes of the same stage.
    if current != result["project_fingerprint"] and current not in accepted_fingerprints:
        raise ValueError("Result is stale: project changed")
    if patch.stat().st_size and lanes.check_patch_against_master(project, patch) is not lanes.RunStatus.COMPLETE:
        raise ValueError("Patch conflicts with current project")
    return dict(run_id=run_id, status="verified", patch=str(patch), changed_files=result["changed_files"])


def _stdin_is_tty():
    return sys.stdin is not None and sys.stdin.isatty()


def apply_task(ctx, run_id, accepted_fingerprints=()):
    """Apply a fully verified (and, if required, human-approved) patch to the project working tree. No commit."""
    if os.environ.get("RESPECTED_ORCH_CHILD") == "1":
        raise ValueError("Applying a patch must come from the master or operator, not from a worker")
    directory = ctx.run_dir(run_id)
    marker = directory / "applied.json"
    if marker.is_file():
        raise ValueError("Patch already applied")
    verified = check_result(ctx, run_id, accepted_fingerprints=accepted_fingerprints)
    request = _load(ctx, directory / "request.json")
    project = validate_project(ctx, Path(request.get("apply_root") or request["project_root"]))
    patch = Path(verified["patch"])
    if patch.stat().st_size:
        # --check first: a changed source (stale context) must fail before anything is written.
        lanes._git(project, "apply", "--check", "--binary", "--whitespace=nowarn", str(patch))
        lanes._git(project, "apply", "--binary", "--whitespace=nowarn", str(patch))
    applied = dict(run_id=run_id, patch_sha256=_load(ctx, directory / "result.json")["patch_sha256"],
                   changed_files=verified["changed_files"], applied_at=dt.datetime.now(dt.timezone.utc).isoformat())
    _save(ctx, marker, applied)
    return dict(applied, status="applied")


def approve_maf_task(ctx, run_id):
    # Not authentication: there is no identity model yet. This only stops orchestrator-spawned
    # workers/checks (which inherit RESPECTED_ORCH_CHILD) from approving themselves.
    if os.environ.get("RESPECTED_ORCH_CHILD") == "1":
        raise ValueError("Approval must come from the operator, not from an orchestrated process")
    # Workers, checks and the Claude master run with stdin detached; only a person at a terminal approves.
    if not _stdin_is_tty():
        raise ValueError("Human approval requires an interactive terminal")
    directory = ctx.run_dir(run_id)
    maf_result = _load(ctx, directory / "maf-result.json")
    if maf_result["status"] != "HUMAN_APPROVAL_REQUIRED":
        raise ValueError("Only human-approval-required MAF results can be approved")
    if (directory / "maf-approval.json").is_file():
        raise ValueError("MAF approval already recorded; it is immutable")
    # Bind the approval to the exact reviewed result so it cannot be replayed onto a changed patch.
    status = _load(ctx, directory / "status.json")
    result = _load(ctx, directory / "result.json") if (directory / "result.json").is_file() else {}
    patch = safe_path(directory / "worker.patch")
    if (status.get("status") != "completed" or result.get("status") != "completed"
            or result.get("run_id") != run_id or not patch.is_file()
            or hashlib.sha256(patch.read_bytes()).hexdigest() != result.get("patch_sha256")):
        raise ValueError("Only an intact completed result can be approved")
    approval = dict(run_id=run_id, root_run_id=maf_result["root_run_id"], patch_sha256=result["patch_sha256"],
                    approved_by=getpass.getuser(), approved_at=dt.datetime.now(dt.timezone.utc).isoformat())
    _save(ctx, directory / "maf-approval.json", approval)
    return approval


def retry_task(ctx, run_id):
    inspected = inspect_task(ctx, run_id)
    request = inspected["request"]
    if inspected["status"] not in {"failed", "timed_out", "cancelled", "interrupted"}:
        raise ValueError("Only unsuccessful terminal tasks can be retried")
    if request["retry_depth"] >= 2:
        raise ValueError("Retry budget exhausted (three total attempts)")
    claim = safe_path(ctx.run_dir(run_id) / '.retry-claim')
    try:
        descriptor = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    except FileExistsError:
        raise ValueError('Task already retried; continue from its retry child') from None
    try:
        again = dict(request)
        policy = request.get("memory_policy") or {}
        if "memory" not in again and policy.get("source") == "explicit":  # the stored request keeps the decision as memory_policy (audit P2)
            again["memory"] = {k: policy[k] for k in ("use", "query") if k in policy}
        created = create_task(ctx, again)
        directory = ctx.run_dir(created["run_id"])
        next_request = _load(ctx, directory / "request.json")
        next_request.update(retry_of=run_id, retry_depth=request["retry_depth"] + 1)
        _save(ctx, directory / "request.json", next_request)
        _save(ctx, ctx.run_dir(run_id) / 'retry.json', dict(run_id=run_id, retry_run_id=created['run_id']))
        return created
    except Exception:
        claim.unlink()
        raise
