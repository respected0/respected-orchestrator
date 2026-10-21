# Respected Orchestrator

Independent local AI task engine: it runs coding agents (Codex, Claude, Gemini, Antigravity, Cursor or a custom command)
in isolated Git worktrees, checks their result (scope, acceptance commands, signed evidence, patch freshness) and never
changes your project unless you apply a verified result. It needs no SecondBrain, vault, Hub process or global service.

People use it through **Respected Hub** (workspace, task list, evidence, MCP access for AI clients). The engine ships as
`respected-orchestrator.exe`, a packaged folder that needs no Python on the machine; Git must be installed for worktrees.

## Layout

| Path | What it is |
| --- | --- |
| `src/respected_orchestrator/engine/` | worktree lanes, task runner, Codex call layer, acceptance sandbox, process control, token budget |
| `src/respected_orchestrator/workflows/` | MAF coding workflow, campaigns, autonomous projects, planner, role assignment |
| `src/respected_orchestrator/interfaces/` | RPP server (Hub protocol), lifecycle records, MCP server, SecondBrain memory client, AI-client integrations |
| `src/respected_orchestrator/__main__.py` | private JSON entry point for the Hub and tests (not a public CLI) |
| `packaging/` (incl. `build_dist.py`) | packaged build (PyInstaller onedir + `distribution.json`) |
| `tests/` | `engine/`, `workflows/`, `interfaces/` mirror the package; `packaging/` drives the built exe |
| `docs/decisions/` | binding design decisions (RPP, sandbox, MCP permissions, roles, memory, campaigns, Codex results) |

## Develop

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -t .          # temp repos and fake workers only; HOME is sandboxed
python packaging/build_dist.py                          # -> dist/RespectedOrchestrator/respected-orchestrator.exe
python -m unittest tests.packaging.test_frozen_build # the built exe with no Python on PATH
```

The private entry point takes one JSON request on stdin per command and prints one JSON line; use an explicit,
disposable data root during development:

```powershell
$data = "$env:TEMP\orch-dev"
python -m respected_orchestrator --data-root $data status
Get-Content -Raw request.json | python -m respected_orchestrator --data-root $data create   # -> run_id
python -m respected_orchestrator --data-root $data start RUN_ID     # detached supervisor
python -m respected_orchestrator --data-root $data inspect RUN_ID
python -m respected_orchestrator --data-root $data check RUN_ID     # re-verifies signed evidence and freshness
```

The packaged build answers the same commands: `respected-orchestrator.exe --data-root DATA status`. Other commands:
`rpp` (Hub protocol), `mcp` (stdio MCP server), `plan`, `roles`, `maf`, `apply`, `retry`, `cancel`,
`campaign-*`, `project-*`.

A read task request:

```json
{
  "project_root": "C:/path/to/a/git/project",
  "task": "Inspect src and explain its public entry points. Do not change files.",
  "worker": "codex",
  "kind": "read",
  "ownership": ["src"],
  "forbidden": [".env", "credentials"],
  "acceptance": [],
  "timeout_seconds": 120
}
```

Write tasks need at least one `acceptance` command as a JSON argv array and ownership that covers the files they may
change. Nothing is applied automatically; pending, failed, stale or tampered results never pass `check`; retries are
explicit and bounded.

## Safety limits

* Windows workers run in a kill-on-close Job Object; timeout, cancel or supervisor death removes the whole process tree.
* Acceptance commands run under a Windows restricted token that cannot read the engine key or rewrite run evidence
  (`docs/decisions/ACCEPTANCE_SANDBOX.md`). Scope validation is a post-execution file check, not an OS sandbox for the
  worker itself, which runs with the user's permissions.
* Logs are redacted for recognised key/token patterns, not for every possible secret format.
* Windows is the supported platform for the beta; macOS/Linux code paths exist but are not verified.
