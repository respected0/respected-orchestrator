# 2026-10-15 — memory integration (SecondBrain stale-index fix, Orchestrator client, Hub permission)

Decisions: `docs/decisions/MEMORY_INTEGRATION.md` (this repo), `respected-secondbrain/docs/decisions/RPP_MEMORY_RECALL.md`.

## Executed through Orchestrator (data root `C:\ov\dsb`, Hub-style defaults, one project per repository)
| repo | project | outcome | weighted tokens |
|---|---|---|---|
| SecondBrain (git mirror `C:\ov\sb`, patch `C:\ov\stale-fix.patch`) | `proj-20261015114454-f2146f66` | 1 lane approved first try; applied after a CRLF-normalised baseline-hash check | 121,356 |
| Orchestrator (non-git: engine-built mirror, apply_root = real tree) | `proj-20261015114537-ee48e02b` blocked, then `proj-20261015114840-6945ecb6` completed | 2 lanes (memory client, integration) approved first try | 69,757 (blocked run) + 299,756 |
| Hub (non-git mirror) | `proj-20261015115834-ebd5ec20` backend approved + applied, project blocked at its e2e verify; `proj-20261015120557-6a5fa386` ui blocked (acceptance could not import `@tauri-apps`); `proj-20261015120918-9382faa7` ui completed | backend 159,452 + ui 139,868 (blocked) + 92,160 | |
Usage KNOWN for every step. Final master reviews (Hub-default `master` role) ended VERDICT: APPROVED where run.

## Engine defects found and fixed while doing it (tests in `tests/test_roles.py`, `tests/test_memory_integration.py`)
1. A 60,000-byte diff preview in the review prompt exceeded the Windows command-line limit (32,767): the review failed without any record. Prompts are now capped
   at 28,000 characters (preview shortened) and a tool that cannot start is recorded as a failed review (`spawn_failed`).
2. `create_task` for a campaign lane looked for the memory token in the lane data root: `main_root` is now passed explicitly (found by the real lane run).
3. Memory policy: enabling in the Hub is a permission, tasks opt in with `memory.use` (decided after reviewing the UI promise "only tasks that use memory").
4. Role defaults set with an empty profile in `default_roles` (earlier round) and project phases now see earlier phases' output (earlier round).

## Manual edits after lane output (not produced by a lane; each verified by the tests named)
- Hub `rpp.rs`: `resolve_program` (bare `python` must be an absolute file for the Orchestrator's command validation) and the test using it;
  `memory_access.rs`: capability check also reads `capability_details` (a 1.0 manifest hides 1.1 capabilities) and validation errors are shown;
  `tests/memory_access_e2e.rs`: grants file name. Found by the project's own real-engine verify step; the project then had no failed lane to retry.
- Orchestrator: items 1-3 above.

## Evidence
- Leak confirmed before the fix and gone after: note edited after indexing, recall of the removed word returned the old snippet; now 0 results (`C:\ov\stale_probe.py`).
- End to end on disposable roots (`C:\ov\e2e_p12.py`, `e2e_lane.py`): SecondBrain grant, Orchestrator settings, a task and a campaign lane got the note
  snippet in their briefs, evidence has no snippet/title/token, a scan of every file under the Orchestrator, SecondBrain and project roots finds the token only in `memory-token`,
  revoke makes the next task run without memory (`PERMISSION_DENIED` recorded), disable removes the token file.
- Hub `memory_access_e2e` (real engines, temp roots) passes; `accept_hub.py` exit 0; `tsc` clean; 90 node tests.
- Suites: Orchestrator 307 OK; SecondBrain regression 1074 OK (17 skipped); RPP conformance run earlier in the day: 0 failures (not re-run after the final edits).

## Not verified
The Hub UI panel was not rendered in the native app (types and model tests only). Real Windows ACL denial of the token file for a Codex sandbox user was not exercised.
