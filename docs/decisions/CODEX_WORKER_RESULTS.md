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

On Windows the CLI resolver prefers a complete project-local official Codex package at
`.runtime/codex-0.162.0-alpha.20/bin/codex.exe` when present (it carries OpenAI's sandbox ACL repair, #51822);
otherwise PATH resolution applies. Windows subprocesses drop an inherited `PSModulePath` so each PowerShell version
initialises its own module path. A shared Codex sandbox is never provisioned or repaired by the engine.
