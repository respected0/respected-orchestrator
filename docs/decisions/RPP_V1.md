# RPP v1.0 server-side contract (Respected Orchestrator)

Additive extension: [RPP v1.1](./RPP_V1_1.md) adds lifecycle operations, version
negotiation across 1.0..1.1, typed errors and a richer manifest, without changing any
v1.0 request, response or op behaviour.

## Decision

The Respected Orchestrator exposes the Respected Product Protocol (RPP) v1.0 from a
private entry point in `src/respected_orchestrator/interfaces/rpp.py`, reached through
`respected-orchestrator.exe --data-root DATA rpp` (from source: `python -m respected_orchestrator ...`) with one JSON request on stdin
and one JSON response line on stdout. RPP is a request/response contract, not MCP and
not a daemon: there is no network listener and no public CLI script.

## Contract

- Request: `{"rpp":"1.0","op":<op>,"operation_id":<string 8..64 [A-Za-z0-9_-]>,"payload":{...}}`.
  `operation_id` is required for `settings.apply` and optional (echoed, or `null`) otherwise.
- Every response carries `rpp`, `ok`, `operation_id`, `result` and `error`, and never a
  traceback or secret. Errors use `UNKNOWN_OP`, `PROTOCOL_UNSUPPORTED`, `BAD_REQUEST`,
  `INVALID_SETTINGS`, `OPERATION_ID_CONFLICT` or `INTERNAL`.
- Ops: `manifest`, `health`, `settings.schema`, `settings.validate`, `settings.apply`,
  `settings.readback`. `manifest.capabilities` lists only features that exist.
- Settings live in `DATA_ROOT/settings.json` (atomic temp-file replace). Applying valid
  settings also writes a durable receipt `DATA_ROOT/receipts/<operation_id>.json`
  (`operation_id`, `op`, `status`, `applied_at`, `settings_sha256`). Replay of the same
  `operation_id` with identical settings returns the stored receipt without rewriting;
  different settings under the same `operation_id` fail with `OPERATION_ID_CONFLICT`.
- Settings schema: `default_worker` (enum of supported agents excluding `custom`,
  default `codex`), `default_worker_profile` (default `""`), `default_reviewer_profile`
  (default `glm`), `default_timeout_seconds` (integer 60..3600, default 900). MiMo
  profiles are rejected through `runner._refuse_mimo`. Unknown keys are errors.
- Health reports real checks: data root writable, git present (`runner.shutil.which`),
  at least one worker CLI resolved (`runner.get_cli_command`), and engine key
  present/readable as a boolean only (its contents are never read or returned).

## Consequences

Secrets are accepted but never returned: `settings.readback` and receipts redact any
field marked `secret:true` to `***set***`. The protocol keeps the diff small and reuses
existing helpers (`atomic_write_json`, `safe_path`, `runner`). Tests use temporary
directories only and never touch live user data or Git.
