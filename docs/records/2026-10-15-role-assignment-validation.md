# 2026-10-15 — role assignment implementation and real validation

Decision: [ROLE_ASSIGNMENT.md](../decisions/ROLE_ASSIGNMENT.md).

## Changed
- New `roles.py`; `runner.create_task` resolves roles (explicit > Hub default > opt-in auto) and stores `role_assignments`.
- Removed hardcoded reviewer default (`deepseek`), RPP reviewer default (`glm`), the unconditional "reviewer must differ
  from implementer" refusal and the hardcoded MiMo refusal (now the `blocked_profiles` setting, default `mimo`).
  `vertical_slice.run_codex_call` still carries its old MiMo guard (legacy demo path, no settings access).
- Reviews run through the assigned tool (`maf_workflow._run_tool_call`); `command_for` passes the profile as `--model`
  for claude/gemini/cursor and the file-edit flag for write tasks on claude/gemini.
- RPP settings gained `default_reviewer_tool`, `default_roles`, `auto_assign`, `auto_pool`, `require_independent_review`,
  `blocked_profiles` (Hub-compatible types only); validator handles `boolean`.
- Campaign lanes receive the Hub settings of the main data root (lane data roots have none of their own).

## Evidence
- Full suite, serial: 266 tests OK (257 before + 9 new in `tests/test_roles.py`); one more case added afterwards, that
  module re-run: 10/10, plus `test_campaign`, `test_project`, `test_maf_coding_demo` re-run OK. One earlier `test_engine`
  run showed a Windows temp-dir cleanup lock on `supervisor.log` (not reproduced on re-run).
- Real workflow on a disposable repo and data root (not the user's data): Hub defaults written through RPP
  `settings.apply` (claude / haiku for implementer and reviewer), task stated no roles. `create` recorded both roles as
  `hub_default`; `maf` ran the real `claude` worker, acceptance, and a real `claude` review of the same model:
  `MASTER_APPROVED`; `check` + `apply` wrote `textkit.py` (verified by import). Usage reported UNKNOWN.
- `roles` dry runs: explicit reviewer on `gemini` overrides the Hub default; `cursor` (not installed) gives
  `ROLE_UNAVAILABLE` with no substitution; a role without any source gives `ROLE_UNASSIGNED`.

## Not verified / open
- Real review through `gemini` is unverified (no API key here); agy and claude reviews are proven (see follow-up).
- Token usage: see follow-up (claude/agy known; gemini unverified).
- `docs/repository_inventory.json` has NEEDS_REVIEW markers for ~25 files (older ones were already stale); not reviewed.

## Follow-up 2026-10-15: multi-lane campaign validation and fixes
Real project on a disposable git repo (data root `C:\ov\d`): lanes `slug` (claude/haiku worker, agy reviewer) and `words`
(agy worker, claude/haiku reviewer) in parallel, then `cli` (Hub defaults, claude/haiku on every role) depending on both;
`auto_apply`, a verify command, final review by the `master` role. Completed in one attempt, usage KNOWN, `cli.main` correct,
final master verdict APPROVED (172,756 weighted tokens).
Defects found by real runs and fixed (each with a regression test in `tests/test_roles.py` unless noted):
1. A dependent lane's worktree lacked its dependencies' applied files (cut from HEAD): `context_paths` (read-only inputs).
2. Parallel lanes of one git source: the second lane's result was refused as stale after the first was applied:
   the supervisor now trusts only the project states its own applies produced (`accepted_fingerprints`).
3. agy workers were told to edit through the shell, which is denied, ending the turn with nothing written: tool-specific
   edit instruction and a no-command self-check for claude/gemini/agy workers.
4. Usage was UNKNOWN for non-codex tools: claude and agy JSON envelopes are parsed (gemini parser written from its
   documented shape, NOT verified: this machine's gemini has no API key).
5. Final review saw only the last attempt's lanes and could not read the source: lanes merge across attempts, source
   roots are passed (`--add-dir`).
6. Worktree paths over ~200 characters fail inside git (`'$GIT_DIR' too big`): clear early error.
7. `vertical_slice.run_codex_call` hardcoded the MiMo refusal below the settings layer: removed.
Recovery check (no AI, custom workers): supervisor killed mid-stage, `project-resume` finished; the applied lane was not
repeated (attempt 1 `failed: two ... running`, attempt 2 only `two`).
Hub configuration: Hub's own `formFromSchema`/`parseFieldValue`/`verifyReadback` drove `settings.validate/apply/readback`
against the real engine; the applied values then resolved as `hub_default` roles (`roles` dry run). Hub UI itself not run.
Suite: 273 tests; the last full run had 2 failures, both test doubles lacking the new `accepted_fingerprints` keyword;
fixed and those modules re-run OK (full suite not re-run afterwards).

## Follow-up 2026-10-15 (second pass): evidence-based auto assignment, planner role, conformance check
- `tools/rpp_conformance.py` data roots: it creates `tempfile.mkdtemp("rpp-conf-")` and puts `orch`, `brain` and `app` under it
  (checked in the script, the leftover `/tmp/rpp-conf-*` directories, and mtimes of `%LOCALAPPDATA%\RespectedBrain`,
  `RespectedOrchestrator`, `.claude`, `.codex`, `.gemini`, `.cursor`). Nothing outside the temp root changed because of it.
  `.codex\config.toml` was modified hours later by the Codex app itself, unrelated. Leftover temp directories are harmless.
- Auto assignment is now `roles.recommend` + `track_record.py`: capability filter, ranking by this installation's signed run
  evidence, and an explicit "no evidence, first listed entry" label when fewer than 3 runs exist. Measured on the validation
  data root: write `claude/haiku` 7/8 completed, `agy` 5/11 (mostly the shell-edit defect fixed that day, so old failures
  weigh it down until new runs accumulate); read `claude/haiku` 7/7, `agy` 5/5.
- `planner` role is executable: `plan` command (real run with claude/haiku, 53,149 weighted tokens, produced a valid
  two-phase draft with a dependency; never started).
- Superseded statements above: "Representable but not consumed: planner" and "auto picks the first usable entry".
- Full regression after all of the above (serial, one run, machine under other load): 275 tests OK (775 s).
