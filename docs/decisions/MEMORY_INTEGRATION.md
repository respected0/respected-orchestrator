# Optional SecondBrain memory for tasks (decision)

Status: implemented 2026-10-15. Orchestrator never depends on SecondBrain: without the Hub's enable step nothing below runs.

## What happens
A task (or a campaign/project lane) can ask for memory with `memory: {use: true, query?: str}`. Enabling memory in the Hub is a *permission*, not a default:
a task without `memory.use: true` never reads memory (`memory_policy.source` = `off`; `use: false` is recorded as explicit). `use: true` while memory is not
enabled/configured is an error at creation (an explicit choice is never silently ignored). At execution the engine re-checks the configuration (so a Hub disable or a
SecondBrain revoke takes effect for queued tasks immediately), asks SecondBrain `memory.recall` over RPP (a subprocess; one request on stdin, one JSON line on
stdout; no import of SecondBrain code), and appends at most about 3,000 characters of snippets to the worker brief under a header that marks them as
untrusted data. The query is the explicit `memory.query` or the task's distinctive words (max 12). Any failure only means "no memory": the task runs normally.

## Where things live (hidden Hub settings; `hidden: true` in the RPP schema)
`memory_enabled`, `memory_command` (JSON `{argv, env}` telling the engine how to start SecondBrain's RPP; env keys limited to an allow-list),
`memory_grant_id`, and the write-only `memory_token`.

## Secret handling (each has a test)
- The grant token is stored only in `<data root>/memory-token` (0600 and, on Windows, inherited ACEs removed like `.engine-key`, so Codex sandbox users and
  other accounts cannot read it). It is never in `settings.json`, receipts, `request.json`, status, evidence, logs, error text or the brief; readback shows `***set***`.
- It travels only on the child's stdin, never in argv or environment; the child gets a minimal environment, not the Orchestrator's.
- Messages built from child output are scrubbed of the token. `memory-context.json` records only status, count, relative paths, scores, index state and counters:
  no snippets, titles, query text or token.
- Residual: the snippets themselves are in that run's `brief.md` (the worker model must see them) and the worker is a model with the user's file access,
  so only enable memory for projects where the user accepts that notes snippets reach the chosen worker model. A worker in a tool without a file sandbox
  could in principle read other files the user can read; the token file ACL covers the Codex sandbox users, not an unrestricted tool.

## Settings semantics fix made on the way
`settings.apply` is now a merge: omitted keys keep their stored values (before, a partial apply, which is what the Hub's generic form sends, silently reset
every other key to its default). Secret keys: `***set***` or absent keeps, `""` clears.

## Lanes
Campaign lane data roots hold neither settings nor token. `create_task(..., main_root=)` and `RESPECTED_ORCH_MAIN_ROOT` (set by the campaign for its MAF child)
point lanes at the main data root.

## Not covered
Recall is per task start, not per step; no caching; no automatic write-back. Reusable knowledge can be saved on explicit request through the MCP tool `orchestrator_memory_note` -> RPP `memory.write` (separate Hub permission `memory_write`, default off; new inbox file only, revertible; see SecondBrain `RPP_MEMORY_RECALL.md`). Task history is never written.
