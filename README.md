# Respected Orchestrator

Independent local AI task engine. Python >=3.10 and Git are required for worktree
execution. No Brain install, vault, Hub process, global service or provider config
write is required. Source `src/respected_orchestrator/` is independently packaged
by `pyproject.toml`; it has no `respectedbrain` imports or package dependencies.

The user-facing entry is **Respected Hub**. There is no public console script or
setup wizard. Until native Hub acceptance, the private JSON entry below is the
developer/test path. This is a development engine, not a signed distribution.

## Developer path

From this directory, set `PYTHONPATH` to its absolute `src` path. Use an explicit
isolated data root for development; do not point it at a user's vault or live app.

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m respected_orchestrator --data-root ABSOLUTE_TEMP_DATA_ROOT status
# Submit the JSON request on stdin (example below), then use its returned run_id.
Get-Content -Raw ABSOLUTE_REQUEST_JSON | python -m respected_orchestrator --data-root ABSOLUTE_TEMP_DATA_ROOT create
python -m respected_orchestrator --data-root ABSOLUTE_TEMP_DATA_ROOT start RUN_ID
python -m respected_orchestrator --data-root ABSOLUTE_TEMP_DATA_ROOT inspect RUN_ID
python -m respected_orchestrator --data-root ABSOLUTE_TEMP_DATA_ROOT check RUN_ID
python -m respected_orchestrator --data-root ABSOLUTE_TEMP_DATA_ROOT cancel RUN_ID
```

Request for a read investigation (replace the project path with a disposable Git
project; choose an installed CLI):

```json
{
  "project_root": "ABSOLUTE_GIT_PROJECT_ROOT",
  "task": "Inspect src and explain its public entry points. Do not change files.",
  "worker": "codex",
  "kind": "read",
  "ownership": ["src"],
  "forbidden": [".env", "credentials"],
  "acceptance": [],
  "timeout_seconds": 120
}
```

Write tasks require at least one `acceptance` command as a JSON argv array, for
example `[["python", "-m", "unittest", "discover", "-s", "tests"]]`. Include
test/code paths in ownership. `custom` workers use `command: ["tool", "{prompt}"]`;
no shell parsing is added. Auth and OS approval remain the CLI's responsibility.
Optional `include_untracked` selects nonignored, owned inputs explicitly.

`start` detaches the supervisor from Hub/the caller. State and workspaces belong
to DataRoot, not the project. Status is queued/running until worker, tests, scope
and patch compatibility succeed. Inspection includes live redacted worker logs,
check logs and patch preview. `check` revalidates signed evidence, patch hash and
project freshness. Nothing is automatically applied. Pending/failed/tampered
results cannot pass `check`; retry is explicit and bounded to two retries.

Stale writer locks are preserved after a supervisor crash. Inspect the interrupted
run and preserve evidence; recovery/cleanup of those lanes is a remaining lifecycle
task. A retry may report the stale lock instead of starting. Do not delete user
workspaces to hide this state.

## Safety and extraction limits

Windows workers start suspended, join a kill-on-close Job Object, then resume;
timeout/cancel/supervisor death removes the owned process tree. POSIX normal
timeout/cancel uses a new process group. macOS/Linux native acceptance and abrupt
supervisor-death containment remain unverified.

Scope validation is a post-execution file check, not a full OS read/write sandbox.
The worker runs with the user's permissions. HMAC detects evidence edits without
the independent local key; it is not a security boundary against another process
with full access to the same account. Logs are redacted for recognized key/token
patterns, not guaranteed to contain every possible secret format.

Antigravity lane/brief/overlay/check/patch helpers and their adapted tests were
extracted from Brain. A private `antigravity` compatibility route remains for
developer tooling; raw apply is disabled and its older evidence is separate from
the signed Hub task lifecycle. Generic adapter construction was retained for
Codex, Claude, Gemini, Antigravity and Cursor; live provider acceptance is pending.
Brain integration is optional and is not invoked automatically. Cleanup, manual
patch integration, multi-worker scheduling and product lifecycle are tracked in
the [extraction record](../secondbrain/docs/records/2026-10-product-extraction/IMPLEMENTATION.md).

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python tools/repository_map.py --filesystem-only --check
```

The standalone [source atlas](docs/REPOSITORY_MAP.md) describes every product file.
Tests use temporary repositories and fake worker executables, not live AI configs.
