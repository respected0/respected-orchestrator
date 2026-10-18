# A1 reviewer reliability, A2 review-only retry, and the console-window leak (2026-10-12)

Direct engineering by the Master (user-authorised for Track A). Engine + tests only; no Hub files, no git, no startup task.

## Evidence that motivated it (signed run records)
- Three reviews ended `reviewer_execution_failed` after exactly 300.0 s (`review-fast-1/process.json`: state TIMEOUT, returncode 124). 300 s was the fixed ceiling for non-GLM reviewers; DeepSeek reviews of larger diffs need more. The records said `provider_disconnected` only because `diagnose` matched codex's routine stderr line `codex_models_manager ... failed to refresh available models: stream disconnected ...`, which every codex process prints every ~4.5 min.
- In four lanes the worker had finished and its patch was verified (a read-only `check_result` of the real old runs confirms it today) yet the whole lane was redone: avoidable worker work 136,073 + 306,282 + 148,925 = **591,280 weighted tokens and ~4,930 s** (plus the 300 s reviewer wait each time).

## A1 — implemented (`maf_workflow.py`, `vertical_slice.py`, `runner.py`)
- Provider-aware ceiling `review_timeout_default(profile, patch_bytes)`: GLM 900 s, DeepSeek 600 s, other 450 s, +5 s per patch KB (capped +600 s), never above 3600 s; an explicit `workflow.review_timeout_seconds` still wins.
- Failure classes are separate and carried to the caller: `reviewer_timeout`, `reviewer_disconnected`, `reviewer_execution_failed` (non-retryable), `invalid_review_result`, `worker_failed`, plus `review_failure{cause, retryable, attempts}`.
- `diagnose` ignores the benign models-refresh stderr line; real disconnects (structured `Reconnecting...` events, genuine stderr) still classify as `provider_disconnected`.
- Bounded retry: `workflow.review_retries` (default 1, 0..2); a retry after timeout/disconnect gets 1.5x room (cap 3600 s), stays inside the pipeline deadline, keeps its own evidence directory (`review-fast-N`, `-retryK`, `-rN`; nothing is overwritten) and every attempt (failed ones with their tokens) is recorded in signed `review-attempts.json`.
- Unchanged fail-closed rules: a rejection is final, invalid reviewer output is not retried, the reviewer may not be the implementer, deterministic evidence is still required before any review.

## A2 — implemented
- Re-invoking `maf RUN_ID` after a failed review reuses the last completed attempt **only after** `check_result(..., maf_gate=False)` re-verifies signed status/result, acceptance evidence, patch hash, unchanged project and patch-vs-master; otherwise `reuse_verification_failed` (worker not re-run, nothing approved). No duplicate attempt record; correction budget already used is carried over.
- History kept: the previous `maf-result.json` moves to `maf-history/`; token ledger `maf-usage.json`: `token_usage` = this invocation only, `token_usage_lifetime` = all invocations (review-only retry never counts the coded work twice).
- Supervisor: `resume_lane_data_root` (validated to live under this data root's `campaigns/` and to contain `lane.json`); `project._review_retry_roots` continues the same lane on the next attempt when its reason is a review failure. Applied-twice is still blocked (`apply_task` -> "already applied").

## Console windows (user report) — real cause and fix
- Cause: supervisors (`project-run`, `campaign-run`, `_execute`) are started with `DETACHED_PROCESS` (no console). On Windows every console program such a process starts without `CREATE_NO_WINDOW` (git, icacls, python: 11 call sites) opens its own visible console. Tests that start real detached tasks (`test_engine`, `test_campaign`) multiplied it. In addition I had started three full suites in parallel plus Brain and Hub suites.
- Fix: new `winproc.py` (`CREATE_NO_WINDOW` + `STARTUPINFO` SW_HIDE) used by all 11 `subprocess.run` sites and `processes.execute`; `_spawn_detached` now gives the supervisor a hidden console of its own (not `DETACHED_PROCESS`) so its children share it. Output, errors, exit codes, timeouts and the job-object tree kill are unchanged (nothing is hidden except the window).
- Verification: (1) `tests/test_windows_processes.py` (static guard: no raw spawn left; detached child + its child have no visible console; tree killed on timeout and cancel; orphan reaped; hidden run keeps stdout/stderr/exit code); (2) 35 child launches from a detached process: `conhost.exe` peak +2, back to baseline; (3) serial heavy modules: python peak 5, git 2, cmd 2, all back to baseline; (4) bounded 2-way and 3-way parallel full suites with a watchdog (abort at python>16/24 or new visible console windows): 0 visible console windows at every 0.5 s sample, python peak 8/10, no leftovers. Other applications' conhost/codex/unity processes were not touched.

## Tests
`tests/test_reviewer_reliability.py` (18) and `tests/test_windows_processes.py` (8) new; `test_maf_coding.py` expectations updated (budget includes retry room; one test split into per-run cases because a re-invoked run now resumes). Mutation checks: disabling reuse, the stderr filter and the project resume each fail the intended tests.
Full suite: 226 tests OK serially (255 s alone); 226 OK in each of two and of three concurrent full runs (338 s / 356 s). The earlier 5 load failures (3 failures + 2 errors, names not captured: the run was killed) were NOT reproduced by these bounded experiments; they happened with three suites plus the Brain suite plus cargo running together (474 s). Treated as unexplained load sensitivity, not hidden.
