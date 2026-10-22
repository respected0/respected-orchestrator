"""Vendor-neutral MCP (stdio) front for the Orchestrator engine; standard library only, no Hub needed.

Reuses the engine functions the Hub/CLI use. Safety: the engine's own approvals stay in force (MAF human approval needs a
terminal and is never exposed), apply needs the verified patch digest, and a process that is itself orchestrated (worker,
master or MCP-started supervisor) sees no tools, so delegation cannot recurse.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from .. import __version__
from ..workflows import campaign, project, roles
from ..engine import runner
from ..context import EngineContext
from ..engine.evidence import load_signed

DELEGATED = "RESPECTED_ORCH_DELEGATED"  # set on everything the engine spawns (see campaign._engine_env)
_RUN, _PROJECT, _CAMPAIGN = (re.compile(p) for p in (r"run-[A-Za-z0-9-]{1,80}", r"proj-[a-z0-9-]{1,60}", r"camp-[a-z0-9-]{1,60}"))
_LOG_TAIL = 3000


def _is_delegated(environ=os.environ):
    return environ.get(DELEGATED) == "1" or environ.get("RESPECTED_ORCH_CHILD") == "1"


def _schema(**properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


_ID = {"type": "string", "description": "run-*, proj-* or camp-* identity"}
_FREE = {"type": "object", "description": "Same JSON the Hub/CLI accepts for this operation", "additionalProperties": True}
_STRINGS = {"type": "array", "items": {"type": "string"}}
_TASK = {"type": "object", "additionalProperties": True, "required": ["project_root", "task", "ownership"], "properties": {
    "project_root": {"type": "string"}, "task": {"type": "string"}, "kind": {"enum": ["read", "write"]}, "worker": {"type": "string"},
    "ownership": _STRINGS, "forbidden": _STRINGS, "timeout_seconds": {"type": "integer"},
    "acceptance": {"type": "array", "items": _STRINGS, "description": "commands, each a string array"},
    "command": {**_STRINGS, "description": "worker=custom only"}, "roles": {"type": "object"}, "workflow": {"type": "object"}}}
# name -> (description, input schema, read-only)
TOOLS = {
    "orchestrator_status": ("Engine health: version, data root, available worker CLIs. Read-only.", _schema(), True),
    "orchestrator_plan": ("Draft (never start) a project spec from a goal with the planner role. Fields: goal, project_root (absolute Git root), "
                          "context_files?, roles?, timeout_seconds?. Slow: runs a model.", _FREE, False),
    "orchestrator_task_start": ("Create and start one isolated task (the worker edits a private workspace, never your tree). Fields: project_root, "
                                "task, ownership, acceptance, worker?, roles?, workflow?. Returns run_id.", _TASK, False),
    "orchestrator_project_start": ("Start a multi-phase project (phases/workstreams/budget). Returns project_id. phases[].auto_apply is refused "
                                   "unless the server was registered with --allow-auto-apply.", _FREE, False),
    "orchestrator_list": ("List recent task runs with status. Read-only.", _schema(), True),
    "orchestrator_progress": ("Status of a run, project or campaign by id (logs trimmed). Read-only.", _schema(id=_ID), True),
    "orchestrator_evidence": ("Verification evidence of a run: result, acceptance checks, review/MAF verdict, patch digest and preview. Read-only.",
                              _schema(run_id=_ID), True),
    "orchestrator_resume": ("Resume an interrupted project, or retry a failed/interrupted task (bounded retry budget).", _schema(id=_ID), False),
    "orchestrator_cancel": ("Request cancellation of a run or project.", _schema(id=_ID), False),
    "orchestrator_memory_note": ("Save one reusable note (decision, convention, finding; not task history) to the user's Brain inbox. Works only if the "
                                 "user enabled memory writes in the Hub; the note is a new file the user can revert. Same title+body is idempotent.",
                                 {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "tags": _STRINGS},
                                  "required": ["title", "body"], "additionalProperties": False}, False),
    "orchestrator_apply": ("Apply a verified patch to the real project tree (no commit). Needs patch_sha256 copied from orchestrator_evidence; "
                           "fails if verification, required human approval or freshness is missing.",
                           _schema(run_id=_ID, patch_sha256={"type": "string"}), False),
}


def _check_id(value, pattern):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError("Invalid identity")
    return value


def _trim(entry):
    entry = dict(entry)
    entry["logs"] = {name: text[-_LOG_TAIL:] for name, text in entry.get("logs", {}).items()}
    entry["patch_preview"] = entry.get("patch_preview", "")[:_LOG_TAIL]
    return entry


_PRIVILEGED_KEYS = {"apply_root", "engine_source", "command"}


def _commands_of(value, found):
    """Every acceptance / verify command (argv list) a task or project request carries."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "acceptance" and isinstance(item, list):
                found.extend(item)
            elif key == "verify" and isinstance(item, list):
                found.extend(entry.get("command") if isinstance(entry, dict) else entry for entry in item)
            else:
                _commands_of(item, found)
    elif isinstance(value, list):
        for item in value:
            _commands_of(item, found)


def _refuse_unlisted_commands(ctx, args, allow_privileged):
    """Over MCP the model may only add checks the user pre-approved (setting mcp_acceptance_allow, empty by default)."""
    if allow_privileged:
        return
    found = []
    _commands_of(args, found)
    if not found:
        return
    from ..workflows import roles
    settings = roles.read_settings(ctx.data_root)
    for command in found:
        if not roles.acceptance_allowed(settings, command):
            raise ValueError("acceptance/verify commands are disabled over MCP unless the user lists them: add a command prefix to the "
                             "Orchestrator setting mcp_acceptance_allow (or register the server with --allow-privileged)")


def _refuse_privileged(value, allow):
    """Over MCP a model may not pick custom workers, commands, another apply target or another engine (audit P0 #3)."""
    if allow:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("acceptance", "verify"):
                continue  # their commands go through the user's prefix list (_refuse_unlisted_commands)
            if key in _PRIVILEGED_KEYS or (key == "worker" and item == "custom"):
                raise ValueError(f"'{key}' is disabled over MCP; register the server with --allow-privileged to allow it")
            _refuse_privileged(item, allow)
    elif isinstance(value, list):
        for item in value:
            _refuse_privileged(item, allow)


def _dispatch(ctx, name, args, allow_auto_apply, allow_privileged=False):
    if name in ("orchestrator_task_start", "orchestrator_project_start"):
        _refuse_privileged(args, allow_privileged)
        _refuse_unlisted_commands(ctx, args, allow_privileged)
    if name == "orchestrator_status":
        return dict(product="respected-orchestrator", version=__version__, data_root=str(ctx.data_root),
                    workers={w: runner.get_cli_command(w) for w in runner.SUPPORTED_AGENTS if w != "custom"})
    if name == "orchestrator_plan":
        from ..workflows.planner import plan
        return plan(ctx, args)
    if name == "orchestrator_task_start":
        created = runner.create_task(ctx, args)
        return dict(created, **runner.start_task(ctx, created["run_id"]))
    if name == "orchestrator_project_start":
        phases = args.get("phases") if isinstance(args.get("phases"), list) else []
        if not allow_auto_apply and any(isinstance(p, dict) and p.get("auto_apply") for p in phases):
            raise ValueError("auto_apply writes to the real tree and is disabled over MCP; register the server with --allow-auto-apply")
        return project.start_project(ctx, args)
    if name == "orchestrator_list":
        return runner.list_tasks(ctx)
    ident = args.get("id", args.get("run_id"))
    if name == "orchestrator_progress":
        if isinstance(ident, str) and ident.startswith("proj-"):
            return project.project_status(ctx, _check_id(ident, _PROJECT))
        if isinstance(ident, str) and ident.startswith("camp-"):
            return campaign.campaign_status(ctx, _check_id(ident, _CAMPAIGN))
        return _trim(runner.inspect_task(ctx, _check_id(ident, _RUN)))
    if name == "orchestrator_evidence":
        directory = ctx.run_dir(_check_id(ident, _RUN))
        out = {"status": load_signed(ctx, directory / "status.json")}
        for key in ("result", "maf-result", "maf-approval", "review-attempts"):
            if (directory / f"{key}.json").is_file():
                out[key] = load_signed(ctx, directory / f"{key}.json")
        out["patch_preview"] = runner.inspect_task(ctx, ident)["patch_preview"][:_LOG_TAIL]
        return out
    if name == "orchestrator_resume":
        if isinstance(ident, str) and ident.startswith("proj-"):
            return project.resume_project(ctx, _check_id(ident, _PROJECT))
        retried = runner.retry_task(ctx, _check_id(ident, _RUN))
        return dict(retried, **runner.start_task(ctx, retried["run_id"])) if "run_id" in retried else retried
    if name == "orchestrator_cancel":
        if isinstance(ident, str) and ident.startswith("proj-"):
            return project.cancel_project(ctx, _check_id(ident, _PROJECT))
        return runner.cancel_task(ctx, _check_id(ident, _RUN))
    if name == "orchestrator_memory_note":
        from . import memory
        from ..workflows import roles
        tags = args.get("tags") or []
        key = json.dumps([args.get("title"), args.get("body"), tags], ensure_ascii=False, sort_keys=True)
        return memory.write_note(roles.read_settings(ctx.data_root), ctx.data_root, args.get("title"), args.get("body"), tags,
                                 operation_id="note-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24])
    if name == "orchestrator_apply":
        run_id = _check_id(ident, _RUN)
        recorded = load_signed(ctx, ctx.run_dir(run_id) / "result.json").get("patch_sha256")
        if not recorded or args.get("patch_sha256") != recorded:
            raise ValueError("patch_sha256 does not match the verified patch; read orchestrator_evidence first")
        return runner.apply_task(ctx, run_id)
    raise ValueError(f"Unknown tool {name}")


def _instructions():
    """The kod-orkestrasyon skill (rules part) is the server's MCP instructions, so every connected client gets it."""
    text = (Path(__file__).resolve().parents[1] / "resources/skills/kod-orkestrasyon/SKILL.md").read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[-1].split("\n## Claude Master")[0].strip()


def handle(ctx, message, *, delegated=False, allow_auto_apply=False, allow_privileged=False):
    """One JSON-RPC message -> response dict, or None for notifications."""
    method, ident = message.get("method"), message.get("id")
    if ident is None:
        return None

    def reply(**kw):
        return {"jsonrpc": "2.0", "id": ident, **kw}
    if method == "initialize":
        version = (message.get("params") or {}).get("protocolVersion", "2025-03-26")
        return reply(result={"protocolVersion": version, "capabilities": {"tools": {}},
                             "serverInfo": {"name": "respected-orchestrator", "version": __version__},
                             "instructions": _instructions()})
    if method == "ping":
        return reply(result={})
    if method == "tools/list":  # an orchestrated process sees nothing to call: no recursive delegation
        tools = [] if delegated else [{"name": n, "description": d, "inputSchema": s, "annotations": {"readOnlyHint": ro}}
                                      for n, (d, s, ro) in TOOLS.items()]
        return reply(result={"tools": tools})
    if method == "tools/call":
        params = message.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        if delegated or name not in TOOLS or not isinstance(args, dict):
            text = "Unavailable: orchestrated processes cannot delegate" if delegated else "Unknown tool or bad arguments"
            return reply(error={"code": -32602, "message": text})
        saved = sys.stdout
        sys.stdout = sys.stderr  # engine code must never write into the protocol stream
        try:
            text, error = json.dumps(_dispatch(ctx, name, args, allow_auto_apply, allow_privileged), ensure_ascii=True, default=str), False
        except roles.RoleError as failure:
            text, error = json.dumps(dict(error=failure.message, code=failure.code, hint=failure.hint)), True
        except Exception as failure:
            text, error = json.dumps(dict(error=str(failure))), True
        finally:
            sys.stdout = saved
        return reply(result={"content": [{"type": "text", "text": text}], "isError": error})
    return reply(error={"code": -32601, "message": f"Method not found: {method}"})


def serve(data_root, allow_auto_apply=False, allow_privileged=False):
    delegated = _is_delegated()
    os.environ[DELEGATED] = "1"  # everything this server spawns (supervisors, workers, masters) inherits it
    ctx, out = EngineContext(Path(data_root)), sys.stdout
    for line in sys.stdin.buffer:
        try:
            response = handle(ctx, json.loads(line.decode("utf-8-sig")), delegated=delegated, allow_auto_apply=allow_auto_apply, allow_privileged=allow_privileged)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            out.write(json.dumps(response, ensure_ascii=True) + "\n")
            out.flush()
    return 0
