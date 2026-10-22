"""respected-orchestrator command line: the shared product commands (docs/PRODUCT_CONTRACT.md) and the engine's own.

Shared: --version, setup, repair, uninstall [--purge], config [get KEY | set KEY=VALUE...], health, memory connect|disconnect|status,
rpp, mcp. Own: integrations [set CLIENT=on|off...] registers this program as an MCP server in AI clients (what the Hub's screen does). Output is JSON; errors are {"error": {code, message, hint}}; exit codes 0 ok, 1 failed, 2 usage.
`--data-root` is the engine's own handle for the child processes it starts (each campaign lane has its own root); people use
RESPECTED_DATA_DIR.
"""
import argparse
import json
from pathlib import Path
import sys

from .context import EngineContext, default_data_root
from .workflows import roles
from .engine import runner
from . import __version__


def _stdin_json():
    # Windows PowerShell pipes prepend a BOM; accept it.
    return json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))


def _selfcheck():
    """Import every engine module: proves a packaged executable carries its whole closure (CI runs it on the build)."""
    import importlib, pkgutil
    from . import __path__ as package_path
    names = sorted(module.name for module in pkgutil.walk_packages(package_path, __package__ + ".") if not module.name.endswith("__main__"))
    for name in names:
        importlib.import_module(name)
    import agent_framework  # the MAF runtime the workflows need at run time
    return dict(status="ok", version=__version__, modules=len(names))


SHARED = ("setup", "repair", "uninstall", "config", "health", "memory", "integrations")
USAGE = {
    "setup": "setup",
    "repair": "repair",
    "uninstall": "uninstall [--purge]",
    "config": "config | config get <anahtar> | config set <anahtar>=<değer>...",
    "health": "health",
    "memory": "memory connect [--write] | memory disconnect | memory status",
    "integrations": "integrations | integrations set <istemci>=on|off...",
}


class UsageError(ValueError):
    pass


def _value(field, text):
    if field["type"] == "boolean":
        if text.strip().lower() not in ("true", "false"):
            raise UsageError(f"{field['key']} true ya da false olmalı")
        return text.strip().lower() == "true"
    if field["type"] == "integer":
        try:
            return int(text)
        except ValueError:
            raise UsageError(f"{field['key']} tam sayı olmalı") from None
    return text


def _config(ctx, rest):
    from .interfaces import rpp
    fields = {field["key"]: field for field in rpp.schema_fields()}
    if not rest:
        return rpp.read_settings(ctx)
    if rest[0] == "get" and len(rest) == 2 and rest[1] in fields:
        return {rest[1]: rpp.read_settings(ctx)[rest[1]]}
    if rest[0] == "set" and len(rest) > 1:
        values = {}
        for item in rest[1:]:
            key, separator, text = item.partition("=")
            if not separator or key not in fields:
                raise UsageError(f"Bilinmeyen ayar ya da eksik '=': {item}")
            values[key] = _value(fields[key], text)
        rpp.apply_settings(ctx, values)
        current = rpp.read_settings(ctx)
        return {key: current[key] for key in values}
    raise UsageError("Kullanım: " + USAGE["config"])


def _integrations(ctx, rest):
    """AI clients that start this program as their MCP server: status, or `set claude-code=on codex=off`."""
    from .context import engine_command
    from .interfaces import integrations
    command = engine_command("mcp")
    launcher = {"command": command[0], "args": command[1:]}
    if not rest:
        return integrations.plan(ctx, {"desired": {}, "launcher": launcher})
    if rest[0] != "set" or len(rest) < 2:
        raise UsageError("Kullanım: " + USAGE["integrations"])
    desired = {}
    for item in rest[1:]:
        client, separator, state = item.partition("=")
        if not separator or state not in ("on", "off"):
            raise UsageError(f"Beklenen <istemci>=on|off: {item}")
        desired[client] = state == "on"
    planned = integrations.plan(ctx, {"desired": desired, "launcher": launcher})
    import uuid
    return integrations.apply(ctx, "cli-" + uuid.uuid4().hex[:16], {"desired": desired, "launcher": launcher, "plan_digest": planned["plan_digest"]})


def _shared(ctx, command, rest):
    """The commands every Respected product has, with the same names, flags and output."""
    from .interfaces import installation, memory_link, rpp
    if command == "config":
        return _config(ctx, rest)
    if command == "integrations":
        return _integrations(ctx, rest)
    if command == "memory":
        if rest == ["connect"] or rest == ["connect", "--write"]:
            return memory_link.connect(ctx, write=rest[1:] == ["--write"])
        if rest in (["disconnect"], ["status"]):
            return memory_link.disconnect(ctx) if rest[0] == "disconnect" else memory_link.status(ctx)
        raise UsageError("Kullanım: " + USAGE["memory"])
    if rest not in ([], ["--purge"]) or (rest and command != "uninstall"):
        raise UsageError("Kullanım: " + USAGE[command])
    if command == "health":
        return rpp.health(ctx)
    if command == "uninstall":
        return installation.uninstall(ctx, purge=bool(rest))
    return installation.setup(ctx) if command == "setup" else installation.repair(ctx)


def _error(code, message, hint):
    print(json.dumps({"error": {"code": code, "message": message, "hint": hint}}, ensure_ascii=False))


def main(argv=None):
    if sys.platform == "win32":  # JSON goes out (and RPP comes in) as UTF-8 whatever the console code page is
        for stream in (sys.stdin, sys.stdout, sys.stderr):
            if callable(getattr(stream, "reconfigure", None)):
                stream.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["_sandbox-exec"]:  # restricted-token launcher of the packaged build: touches no data root
        from .engine import sandbox_exec
        return sandbox_exec.main(argv[1:])
    if argv[:1] == ["--version"]:
        print(f"respected-orchestrator {__version__}")
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=default_data_root(), help=argparse.SUPPRESS)
    parser.add_argument("command", choices=["status", "create", "start", "list", "inspect", "cancel", "check", "retry", "_execute", "maf", "maf-approve", "apply", "campaign-start", "campaign-run", "campaign-status", "campaign-list", "project-start", "project-run", "project-resume", "project-status", "project-cancel", "rpp", "roles", "plan", "mcp", *SHARED, "_selfcheck"])
    parser.add_argument("args", nargs=argparse.REMAINDER)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit:  # --help (0) or a usage error (2, already explained on stderr)
        return int(exit.code or 0)
    ctx = EngineContext(args.data_root)
    try:
        if args.command == "_selfcheck":
            payload = _selfcheck()
        elif args.command in ("rpp", "mcp") and args.args[:1] in (["--help"], ["-h"]):
            print({"rpp": "usage: respected-orchestrator rpp  (one RPP 1 request on stdin, one response on stdout)",
                   "mcp": "usage: respected-orchestrator mcp [--allow-auto-apply] [--allow-privileged]  (stdio MCP server)"}[args.command])
            return 0
        elif args.command in SHARED:
            if args.args[:1] in (["--help"], ["-h"]):
                print("usage: respected-orchestrator " + USAGE[args.command])
                return 0
            payload = _shared(ctx, args.command, args.args)
            print(json.dumps(payload, ensure_ascii=False))
            healthy = args.command != "health" or payload["status"] == "healthy"
            return 0 if healthy and not payload.get("conflicts") else 1
        elif args.command == "status":
            payload = dict(product="respected-orchestrator", version=__version__, data_root=str(ctx.data_root),
                           workers={worker: runner.get_cli_command(worker) for worker in runner.SUPPORTED_AGENTS if worker != "custom"},
                           git=runner.shutil.which("git"))
        elif args.command == "create":
            payload = runner.create_task(ctx, _stdin_json())
        elif args.command == "roles":  # dry run: stdin {"roles": {...}, "needed": [...]} -> the assignments that would apply
            request = _stdin_json()
            payload = dict(assignments=roles.resolve(
                roles.read_settings(ctx.data_root), request.get("roles", {}), request.get("needed", ["implementer"]),
                tools=list(runner.SUPPORTED_AGENTS), available=runner.tool_available,
                history=lambda: runner._track_record(ctx)))
        elif args.command == "plan":  # planner role: draft a project spec (never started); stdin {goal, project_root, ...}
            from .workflows.planner import plan
            payload = plan(ctx, _stdin_json())
        elif args.command == "mcp":  # stdio MCP server for Claude Code/Codex/any client; optional args --allow-auto-apply, --allow-privileged
            from .interfaces.mcp_server import serve
            return serve(ctx.data_root, allow_auto_apply="--allow-auto-apply" in args.args, allow_privileged="--allow-privileged" in args.args)
        elif args.command == "campaign-start":
            from .workflows.campaign import start_campaign
            payload = start_campaign(ctx, _stdin_json())
        elif args.command == "campaign-list":
            from .workflows.campaign import list_campaigns
            payload = list_campaigns(ctx)
        elif args.command == "project-start":
            from .workflows.project import start_project
            payload = start_project(ctx, _stdin_json())
        elif args.command == "rpp":
            from .interfaces import rpp
            return rpp.run(ctx)
        elif args.command == "list":
            payload = runner.list_tasks(ctx)
        else:
            if len(args.args) != 1:
                raise ValueError("Exactly one run identity is required")
            if args.command == "maf":
                from .workflows.maf_workflow import run_maf_coding_task
                payload = run_maf_coding_task(ctx=ctx, run_id=args.args[0])
            elif args.command == "maf-approve":
                payload = runner.approve_maf_task(ctx, args.args[0])
            elif args.command == "apply":
                payload = runner.apply_task(ctx, args.args[0])
            elif args.command.startswith("project-"):
                from .workflows import project
                payload = {"project-run": project.run_project, "project-resume": project.resume_project,
                           "project-status": project.project_status, "project-cancel": project.cancel_project}[args.command](ctx, args.args[0])
            elif args.command in {"campaign-run", "campaign-status"}:
                from .workflows import campaign
                payload = (campaign.run_campaign if args.command == "campaign-run" else campaign.campaign_status)(ctx, args.args[0])
            else:
                method = {"start": runner.start_task, "inspect": runner.inspect_task, "cancel": runner.cancel_task,
                          "check": runner.check_result, "retry": runner.retry_task, "_execute": runner.execute_task}[args.command]
                payload = method(ctx, args.args[0])
        print(json.dumps(payload, ensure_ascii=True))
        return 1 if payload.get("status") in {"failed", "timed_out", "cancelled", "interrupted"} and args.command == "_execute" else 0
    except UsageError as error:
        _error("USAGE", str(error), "respected-orchestrator --help")
        return 2
    except roles.RoleError as error:
        _error(error.code, error.message, error.hint)
        return 1
    except Exception as error:
        from .interfaces.installation import OperationError
        from .interfaces.rpp import RppError
        if isinstance(error, (OperationError, RppError)):
            _error(error.code, error.message, error.hint)
            return 2 if error.code == "INVALID_SETTINGS" else 1
        _error("FAILED", str(error), "Ayrıntı için mesaja bakın.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
