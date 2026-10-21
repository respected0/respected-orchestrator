# Campaign master lifecycle and worker hardening

Approved by the user's 2026-10-10 instruction to make the Claude → Orchestrator →
parallel DeepSeek/GLM lanes → completion event → new Claude cycle operational.

- `campaign-start` persists a signed spec, snapshots the engine and detaches a
  supervisor (`campaign-run`). The caller (the Claude master) exits; nothing polls.
- Each workstream is a separate DataRoot (own WriterLock, key, state, worktrees),
  so lanes run as real parallel processes; `after` expresses dependencies. A lane
  whose dependency is not `MASTER_APPROVED` is `SKIPPED`.
- The completion event is the supervisor joining all lane threads. It writes the
  signed `result.json` and starts the final master exactly once (`final.claim`).
  Default final master is `claude -p {prompt}`; `final.allow_apply` is opt-in and
  only whitelists the engine's own CLI (`respected-orchestrator.exe`, or `python -m respected_orchestrator` from source).
- Non-Git sources (Hub, Orchestrator today) are developed in a throwaway Git mirror
  under the campaign directory (secrets and heavy directories excluded). `apply`
  re-runs `check_result`, `git apply --check`, then applies to `apply_root`; it never
  commits and is refused inside worker processes.
- From a source checkout the supervisor runs from an engine snapshot so the engine can develop itself; the packaged
  executable is already an immutable copy and is used as is.
- Codex workers are launched with explicit `--sandbox workspace-write` and
  `approval_policy="never"`; the user's `danger-full-access` config is not inherited.
  Worker/check/reviewer environments drop secret-looking variables
  (`RESPECTED_WORKER_ENV_ALLOW` is the explicit opt-out per name).
- `.engine-key` is ACL-restricted to the current user (Windows), unreadable by the
  Codex sandbox users. `maf-approve` requires an interactive terminal.
- Reviewer profile must differ from the implementer. `workflow.escalate_profile`
  hands later corrections to GLM and makes the original implementer the reviewer.
  MiMo profiles are refused everywhere.

Limits: on POSIX there is no OS sandbox boundary for the key; non-Codex CLIs
(claude/gemini/cursor workers) keep their own approval model; `model` is not
reported by the provider's `turn.completed` events so reviews show `model: null`.
