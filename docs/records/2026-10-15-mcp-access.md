# Orchestrator MCP access (2026-10-15)

`python -m respected_orchestrator [--data-root R] mcp [--allow-auto-apply]` is a stdio MCP server
(`mcp_server.py`, stdlib only, no Hub needed) over the same engine functions Hub/CLI use. Shared data root, so Hub shows MCP-started runs.

Tools: `orchestrator_status`, `_plan`, `_task_start`, `_project_start`, `_list`, `_progress` (run/project/campaign), `_evidence`, `_resume`, `_cancel`, `_apply`.

Register (any client; example Claude Code, user scope; PYTHONPATH = the installed `src` dir):
`claude mcp add respected-orchestrator -e PYTHONPATH=<src> -- <python> -m respected_orchestrator mcp`

Safety
- No recursion: the server hides all tools (and refuses calls) when `RESPECTED_ORCH_CHILD` or `RESPECTED_ORCH_DELEGATED` is set;
  it sets `RESPECTED_ORCH_DELEGATED=1` for everything it spawns, and `campaign._engine_env` does the same for masters/supervisors.
- Workers edit isolated workspaces; the real tree changes only through `orchestrator_apply`, which needs the verified `patch_sha256`
  (from `orchestrator_evidence`) plus the engine's own checks (acceptance evidence, freshness, required MAF approval).
- MAF human approval needs a terminal and is NOT exposed: such runs report "approval required" and must be approved in a terminal/Hub.
- `phases[].auto_apply` is refused unless the server is registered with `--allow-auto-apply`.
- Model-role flexibility, budgets, recovery (resume/retry) unchanged: all engine behaviour.

`.engine-key`: `runner._key` now creates a private temp file, restricts its ACL while empty, writes the secret, then publishes with
`os.link` (concurrent creators: first wins). Regression: `test_engine_key_is_restricted_before_secret_is_written`.

Evidence: `tests/test_mcp_server.py` (5), full orchestrator suite 314 OK; real `claude -p` session with Hub not running
(`--mcp-config`, temp data root, disposable repo) started a custom-worker task, polled it to `completed`, read evidence/patch digest; nothing applied.

Limits: `orchestrator_plan` blocks (model run, up to its timeout) and requests are served one at a time; no installer/Hub wiring yet
(registration is manual); no `tester`/`coordinator` roles; the MCP client's own permission prompt is the only approval for non-apply tools;
only Claude Code was exercised (Codex not tried); `mcp` SDK not used, protocol subset = initialize/ping/tools.

## Hub-managed registration (same day, second step)

- Engine (`integrations.py`, RPP 1.1 ops `integrations.plan|apply|rollback`): clients claude-code (`~/.claude.json`), codex (`~/.codex/config.toml`),
  cursor, gemini, windsurf, claude-desktop (Windows). Only the entry `respected-orchestrator` is touched (JSON `mcpServers` / TOML
  `[mcp_servers.respected-orchestrator]`); everything else is preserved. Ownership digest in `<data>/integrations.json`; foreign or
  user-edited entries and unparseable configs are refused (all-or-nothing); apply requires the approved `plan_digest`; whole-file backups
  in `<data>/integration-backups/<op>/`; rollback is entry-surgical and refuses if the entry changed since.
- Hub (`src-tauri/src/mcp_access.rs`, commands `orchestrator_mcp_plan|apply`, journaled as orchestrator/`integrations`, rollback via `lifecycle_rollback`):
  stable launcher `managed/orchestrator/mcp/respected-orchestrator-mcp.cmd` (managed Python + active Orchestrator + data root; rewritten after
  Orchestrator install/update/repair; registrations removed before Orchestrator uninstall); the launcher is started as a client would
  (initialize + tools/list) before any client config is written. `integrations.apply/rollback` are not reachable through the webview bridge.
- UI: `views/OrchestratorMcp.tsx` on the Orchestrator workspace (per-client switch, exact plan, "Onayla ve uygula").

Evidence (disposable HOME / temp roots; real configs untouched)
- `cargo test --test mcp_access_e2e`: plan writes nothing; stale digest refused; foreign JSON/TOML content preserved; registered command answers
  `tools/call` with no Hub; disable restores the original; same-name foreign entry refused; entry-changed rollback refused.
- Real Claude Code on the Hub-written disposable config: `claude mcp list` -> respected-orchestrator "Connected"; after Hub disable the entry is gone, the
  foreign entry and Claude's own keys remain. Real `claude -p` session with that entry: task started/polled/evidence; `orchestrator_apply` with a wrong digest
  refused, with the verified digest applied to a disposable repo (`owned.txt` = changed, uncommitted).
- Codex 0.160.1 (`codex mcp list`, disposable CODEX_HOME) lists the Hub-written entry and, after disable, only the foreign one.
- Tests: Python test_integrations (6) + test_mcp_server (5) + rpp suites 50 OK; Hub cargo lib 31, rpp_e2e/lifecycle_e2e OK; tsc OK; node tests 96 OK.

Limits: Codex was not driven through a model session (needs the user's login; I did not copy credentials); Claude Code/other clients may rewrite
their config at the same moment (restart the client after changes); the native Hub window for the new panel was not screenshot-tested;
Windows launcher only (`.sh` variant written but untested); no macOS/Linux; the shipped catalog bundle was not rebuilt/installed-exe E2E re-run;
repository inventories not updated. The MCP subsystem is considered complete; further work belongs elsewhere.

## Superseded on 2026-10-17 (audit)
The "Safety" claims above were too strong: a calling model could pass `worker: custom`, `command`, `apply_root`, `engine_source`, arbitrary
acceptance/`verify` commands and flags the old denylist missed, and so run code or apply a patch elsewhere. Current rules: `decisions/MCP_PERMISSIONS.md`
(privileged options need `--allow-privileged`; acceptance/verify commands need a prefix the user listed in `mcp_acceptance_allow`; acceptance runs in the
sandbox of `decisions/ACCEPTANCE_SANDBOX.md`). `--allow-auto-apply` only lifts the `auto_apply` refusal.
