# Codex worker result contract

Approved on 2026-10-10 after the Windows Native investigation.

The generic runner launches its built-in Codex adapter with `exec --json` and
passes the complete worker brief as one argument. Custom commands invoking an
executable named `codex` (including `codex.exe` / `codex.cmd`) with `--json` use
the same result contract. Other custom workers keep their existing behavior.

Codex stdout must be JSONL containing only JSON objects, ending in
`turn.completed`, with no `turn.failed` or `error` event. The last completed
agent message must contain a JSON object with an explicit successful `status`
and no error. Commentary, a blocked response, malformed output or a missing
terminal event cannot advance to acceptance merely because the CLI exits zero.
Earlier tool failures may be recovered when the final turn and result succeed.
An explicit non-success status or error is `WORKER_FAILED` even with exit zero.
Quota/authentication errors keep their specific classifications; timeout wins.

The result remains a claim: scope, acceptance, patch compatibility, signed
evidence and project freshness must independently pass. Deadlines, process-tree
cleanup, explicit bounded retries and rejection of ignored out-of-scope files
remain unchanged. Nothing is automatically applied to the source project.

The coding demo resolves the worker CLI path once before creating its
temporary fixture and runs Python acceptance with `-B`. On Windows it first
retrieves authentication through the existing external helper, capturing and
discarding its stdout. Failed retrieval stops before fixture/AI execution.
Its brief also asks the
worker to avoid bytecode, stop on PowerShell errors, verify the worktree and use
the native patch tool when available. These instructions cannot repair Codex's
Windows sandbox runtime or guarantee how its tools execute commands.

On Windows, the shared CLI resolver prefers the complete project-local official
package at `.runtime/codex-0.162.0-alpha.20/bin/codex.exe` when present. This
release contains OpenAI's active-runtime ACL repair fix (#51822); stable 0.162.0
and 0.162.1 still contain the faulty access mask. The full package retains its
matching sandbox setup/runner helpers and manifest; helpers are never mixed
between versions. Installation evidence and the official archive hash are in
`docs/records/2026-10-10-codex-blocked-worker.md`.

Without this local package, normal PATH resolution remains available for other
installations/platforms. Custom commands with explicit executable paths and
historical signed requests are not rewritten. A new coding-demo request uses
the fixed package; replaying an old custom request still uses its saved path.

Windows subprocesses discard inherited `PSModulePath`, case-insensitively, so
each PowerShell version initializes its own module search path. Other variables
and the parent's environment remain unchanged. This prevents a PowerShell 7
module path from breaking Windows PowerShell's Security module in the provider
auth helper; it does not change execution policy, tokens or sandbox permissions.

The demo retains the existing MiMo named profile and CODEX_HOME. It checks
that the existing Windows sandbox marker is a non-empty JSON object before
authentication, fixture creation or AI execution. Missing, empty or malformed
setup stops explicitly; the demo never initializes or repairs a shared sandbox.
This is an early failure guard, not proof that a syntactically valid marker
will make every runtime operation succeed.

A private CODEX_HOME implementation was withdrawn. Windows sandbox account
names are machine-global; provisioning a new home can reset passwords and
firewall state used by the current desktop session. Private configuration does
not safely isolate those resources. No isolated-home request flag remains.

Free real-tool validation reached Codex exec_command using generated local SSE
responses, with zero paid inference. It proved the remaining runtime blocker:
helper_sandbox_lock_failed opening the shared .sandbox-bin directory. Engine
result is WORKER_FAILED despite CLI exit zero; acceptance and patch generation
are suppressed. Runtime provisioning itself has shared security side effects,
even without a model request. No further Codex execution is authorized here.

The first approved live test failed in external auth. A global config hash
change/new temporary-project trust entry was observed; the writer/full delta
was not established, and settings were not manually edited or restored. Later
free protocol validation left config.toml and mimo.config.toml byte-identical,
but sandbox provisioning logged account/firewall operations and left an empty
setup marker. Full evidence and remaining approval boundary are recorded in
`docs/records/2026-10-10-worker-auth-environment.md`.

Complete Native MiMo patch/acceptance remains unverified. Shared sandbox repair
requires separate approval under the user's prohibition on changing security
mechanisms. A second paid run also requires approval. Python 3.11+ is needed
for this Windows demo's standard-library TOML auth preflight; ordinary engine
imports retain the existing Python floor.
