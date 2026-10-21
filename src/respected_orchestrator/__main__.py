"""Private JSON entry point for Hub and developer verification; the only user-facing commands are --version and the product-contract lifecycle commands (setup, update, repair, uninstall)."""
import argparse
import json
from pathlib import Path
import sys
import uuid

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


LIFECYCLE_ACTIONS = {"setup": "install", "update": "update", "repair": "repair", "uninstall": "uninstall"}
LIFECYCLE_USAGE = "usage: respected-orchestrator {setup|update|repair|uninstall} [--purge (uninstall only)]\nRecords, re-verifies or removes the install record of this program folder; --purge also deletes the data root."


def _lifecycle_command(ctx, command, extra):
    """Product-contract lifecycle commands over lifecycle.apply; the program folder itself belongs to whoever installed it."""
    if extra not in ([], ["--purge"]) or (extra and command != "uninstall"):
        raise ValueError(LIFECYCLE_USAGE)
    from .interfaces import lifecycle
    target = {"app_root": str(ctx.app_root), "distribution": True, "purge": bool(extra)}
    return lifecycle.apply(ctx, "operation-" + uuid.uuid4().hex[:16], LIFECYCLE_ACTIONS[command], target)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["_sandbox-exec"]:  # restricted-token launcher of the packaged build: touches no data root
        from .engine import sandbox_exec
        return sandbox_exec.main(argv[1:])
    if argv[:1] == ["--version"]:
        print(f"respected-orchestrator {__version__}")
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=default_data_root())
    parser.add_argument("command", choices=["status", "create", "start", "list", "inspect", "cancel", "check", "retry", "_execute", "maf", "maf-approve", "apply", "campaign-start", "campaign-run", "campaign-status", "campaign-list", "project-start", "project-run", "project-resume", "project-status", "project-cancel", "rpp", "roles", "plan", "mcp", "setup", "update", "repair", "uninstall", "_selfcheck"])
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    ctx = EngineContext(args.data_root)
    try:
        if args.command == "_selfcheck":
            payload = _selfcheck()
        elif args.command in LIFECYCLE_ACTIONS:
            if args.args[:1] in (["--help"], ["-h"]):
                print(LIFECYCLE_USAGE)
                return 0
            payload = _lifecycle_command(ctx, args.command, args.args)
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
    except roles.RoleError as error:
        print(json.dumps(dict(error=error.message, code=error.code, hint=error.hint), ensure_ascii=True))
        return 1
    except Exception as error:
        print(json.dumps(dict(error=str(error)), ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
