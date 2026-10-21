"""The `planner` role made executable: any assigned tool/model drafts a project spec; the engine validates it.

A draft is never started and never edited by the engine. It is saved under <data root>/drafts with the planner's
assignment, usage and the validation verdict, so a person (or the Master) reviews it, then starts it with `project-start`."""
import datetime as dt
import json
from pathlib import Path
import tempfile

from . import roles
from ..context import EngineContext, atomic_write_json
from ..engine.processes import ProcessStopped, execute
from ..engine.runner import SUPPORTED_AGENTS, _track_record, command_for, tool_available, tool_result
from ..engine.antigravity_orchestrator import _git_path_list

CONTEXT_FILE_BYTES = 20_000
FILE_LIST_LIMIT = 300

_FORMAT = (
    'Return ONLY one JSON object: {"goal": str, "budget": {"max_seconds": int, "max_phase_attempts": 2}, "phases": [{"name": '
    'lowercase-slug, "after": [phase names], "auto_apply": true, "lane_timeout_seconds": 1500, "verify": [{"command": [argv...], '
    '"cwd": <project_root>, "timeout_seconds": 300}], "workstreams": [{"name": lowercase-slug, "after": [lane names in the same '
    'phase], "request": {"project_root": <project_root>, "task": str, "kind": "write", "ownership": [relative file paths the lane '
    'may change], "acceptance": [[argv...]], "timeout_seconds": 600, "workflow": {"max_corrections": 1}}}]}]}. '
    'Rules: lanes of one phase that run in parallel must own disjoint files; a lane that needs another lane\'s files lists it in '
    '"after"; every lane needs at least one deterministic acceptance command (argv array, use "python" as the interpreter) that '
    'fails before the work and passes after; tasks must be small, concrete and self-contained; do not invent files you were not '
    'shown unless the task creates them; at most 8 lanes per phase, 12 phases.'
)


def _prompt(goal, root, files, context):
    shown = "\n".join(f"--- {name} ---\n{text}" for name, text in context.items())
    return (f"You are the planner of a software project. Plan the work for this goal as a project spec.\nGOAL: {goal}\n"
            f"project_root: {root}\nTracked files (first {FILE_LIST_LIMIT}): {', '.join(files) or '(none)'}\n"
            f"{shown}\n{_FORMAT}")


def _json(text):
    start, end = text.find("{"), text.rfind("}")
    try:
        value = json.loads(text[start:end + 1]) if 0 <= start < end else None
    except ValueError:
        value = None
    return value if isinstance(value, dict) else None


def plan(ctx: EngineContext, request: dict, settings: dict | None = None) -> dict:
    if not isinstance(request, dict) or not isinstance(request.get("goal"), str) or not request["goal"].strip():
        raise ValueError("plan needs a goal")
    root = Path(request.get("project_root", ""))
    if not root.is_absolute() or not (root / ".git").exists():
        raise ValueError("plan needs an absolute project_root that is a Git project")
    settings = roles.read_settings(ctx.data_root) if settings is None else settings
    asked = {"planner": request["roles"]["planner"]} if isinstance(request.get("roles"), dict) and "planner" in request["roles"] else {}
    planner = roles.resolve(settings, asked, ["planner"], tools=list(SUPPORTED_AGENTS), available=tool_available,
                            history=lambda: _track_record(ctx))["planner"]
    if planner["tool"] == "custom":
        raise roles.RoleError("ROLE_UNAVAILABLE", "The planner needs a model tool; custom commands cannot plan",
                              "Assign claude, codex, gemini or agy to the planner role.")
    files = _git_path_list(root, "ls-files", "-z")[:FILE_LIST_LIMIT]
    context = {}
    for name in request.get("context_files", [])[:10]:
        path = (root / name).resolve()
        if root.resolve() in path.parents and path.is_file():
            context[name] = path.read_text(encoding="utf8", errors="replace")[:CONTEXT_FILE_BYTES]
    prompt = _prompt(request["goal"].strip()[:4000], str(root).replace("\\", "/"), files, context)
    started = dt.datetime.now(dt.timezone.utc)
    with tempfile.TemporaryDirectory(prefix="plan-") as neutral:  # the prompt carries everything; no repository access
        try:
            completed = execute(command_for(planner["tool"], prompt, profile=planner["profile"]), Path(neutral),
                                request.get("timeout_seconds", 600), scrub_env=True)
            text, usage, _model, error = tool_result(planner["tool"], completed.stdout)
            error = error or (None if completed.returncode == 0 else f"planner exited {completed.returncode}")
        except ProcessStopped as stopped:
            text, usage, error = "", None, f"planner stopped: {stopped.reason}"
    spec, problem = _json(text), error
    if problem is None and spec is None:
        problem = "planner did not return a JSON object"
    if problem is None:
        from . import project
        try:
            project._spec(spec, settings)
        except (ValueError, roles.RoleError) as invalid:
            problem = f"spec rejected by the engine: {invalid}"
    drafts = ctx.data_root / "drafts"
    name = f"plan-{started:%Y%m%d%H%M%S}.json"
    atomic_write_json(drafts / name, {"goal": request["goal"], "planner": planner, "usage": usage, "valid": problem is None,
                                      "problem": problem, "spec": spec, "raw": None if spec else text[:4000]})
    return {"status": "drafted" if problem is None else "invalid", "draft": str(drafts / name), "problem": problem,
            "planner": planner, "usage": usage,
            "next": "review the draft, then pipe its `spec` into project-start" if problem is None else "fix or re-plan; nothing was started"}
