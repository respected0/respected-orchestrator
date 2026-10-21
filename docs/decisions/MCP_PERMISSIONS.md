# Orchestrator MCP: what a calling model may and may not do

Status: implemented 2026-10-17 (audit P0 #3, category A3).

## The server
`respected-orchestrator.exe [--data-root R] mcp [--allow-auto-apply] [--allow-privileged]` is a stdio MCP server
(`interfaces/mcp_server.py`, standard library only, no Hub process needed) over the same engine functions Hub uses; runs it
starts show up in the Hub. Tools: `orchestrator_status`, `_plan`, `_task_start`, `_project_start`, `_list`, `_progress`,
`_evidence`, `_resume`, `_cancel`, `_apply`, `_memory_note`. The Hub registers it per AI client through a stable launcher
(plan, approval-bound apply, journaled; foreign entries kept). No recursion: every tool is hidden and refused when
`RESPECTED_ORCH_CHILD` or `RESPECTED_ORCH_DELEGATED` is set, and everything the server spawns carries `RESPECTED_ORCH_DELEGATED=1`.
Workers edit isolated workspaces; the real tree changes only through `orchestrator_apply` with the verified `patch_sha256` and the
engine's own checks. MAF human approval is never exposed over MCP.

## Problem
The MCP server hands tool calls to whatever model the client runs, including a prompt-injected one. It accepted a custom worker command,
`apply_root` (any directory), `engine_source` (any directory with a `campaign.py`, started as the supervisor), `final_review.command`,
acceptance commands (arbitrary programs) and bypass flags the denylist missed.

## Decision
Over MCP, `orchestrator_task_start` and `orchestrator_project_start` refuse:
* `worker: "custom"`, any `command`, `apply_root`, `engine_source` - unless the server was registered with **`--allow-privileged`**.
  This is a separate switch from `--allow-auto-apply` (which only lifts the `auto_apply` refusal); neither is ever passed by the Hub.
* **acceptance and `verify` commands** that the user has not pre-approved. The user lists command prefixes in the Orchestrator setting
  **`mcp_acceptance_allow`** (Hub settings form; JSON, e.g. `[["python","-m","pytest"]]`). A command passes only when it starts with a listed
  prefix word for word. The default list is empty, so a model cannot make the engine run a program of its choosing until the user says which.
* bypass flags: the check is no longer three exact strings; `--dangerously*`, `--yolo`, `bypassPermissions`, `danger-full-access`,
  `-y`, `--approval-mode yolo` and `sandbox_mode` overrides are refused everywhere (`runner._command`).

Even approved checks run under the acceptance sandbox (`ACCEPTANCE_SANDBOX.md`): they cannot read the engine key or forge evidence.

## Proven
`tests/interfaces/test_mcp_server.py`: privileged options refused (also with `--allow-auto-apply` set), unlisted and extended/substring commands refused for
tasks and project `verify`, listed prefixes pass the gate, `--allow-privileged` lifts it, malformed lists rejected by settings validation.

## Limits
* A listed prefix allows any arguments (`pytest -p some_plugin` runs plugin code from the project). List narrow prefixes.
* The caller's own MCP permission prompt (client side) still decides whether a tool call happens at all.
* `cwd` of a `verify` entry is not restricted.
