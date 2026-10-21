"""Private JSON entry point for Hub and developer verification; no public CLI script."""
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=default_data_root())
    parser.add_argument("command", choices=["status", "create", "start", "list", "inspect", "cancel", "check", "retry", "_execute", "maf", "maf-approve", "apply", "campaign-start", "campaign-run", "campaign-status", "project-start", "project-run", "project-resume", "project-status", "project-cancel", "antigravity", "rpp", "roles", "plan", "mcp"])
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    ctx = EngineContext(args.data_root)
    try:
        if args.command == "status":
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
        elif args.command == "project-start":
            from .workflows.project import start_project
            payload = start_project(ctx, _stdin_json())
        elif args.command == "rpp":
            from .interfaces import rpp
            return rpp.run(ctx)
        elif args.command == "list":
            payload = runner.list_tasks(ctx)
        elif args.command == "antigravity":
            from .engine.antigravity_orchestrator import main as legacy_main
            return legacy_main(args.args, ctx=ctx)
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
