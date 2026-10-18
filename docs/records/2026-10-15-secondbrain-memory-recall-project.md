# 2026-10-15 — first SecondBrain project run through Orchestrator: `memory.recall`

Contract and safety rules: `respected-secondbrain/docs/decisions/RPP_MEMORY_RECALL.md`.

## Setup
- Isolation: a plain git mirror of SecondBrain `src/`, `tests/`, `pyproject.toml` at `C:\ov\sb` (baseline commit), data root `C:\ov\dsb`.
  The real repository (about 15 uncommitted paths) was not touched during the run. Afterwards the mirror's owned files were copied
  into the real repo only after checking that the two pre-existing files (`search/engine.py`, `rpp.py`) were byte-identical to the
  mirror baseline and that the six new files did not exist. Full patch: `C:\ov\memory-recall.patch`.
- Roles: Hub-style defaults written with RPP `settings.apply` (`default_worker claude/sonnet`, `default_roles` reviewer = agy with the
  tool's own model, master = claude/sonnet). No lane named a role; all assignments are recorded as `hub_default`.
- Spec generator: `C:\ov\make_spec.py` (4 lanes, 2 phases, `auto_apply`, verify commands, lane token budget 2.5 M, project budget 12 M).

## Execution evidence
| project | result | weighted tokens |
|---|---|---|
| `proj-20261015102550-cfd6ea8e` | phase `foundations` done (readonly-engine 124k, grants 56k, both approved first try); phase `operation` blocked: agy reviewer denied a shell command twice (see defects) | 275,151 |
| `proj-20261015103402-cc56899f` (phase `operation` only, after the engine fixes) | completed: recall-op approved first try (111k); register failed acceptance once (96k), approved on the correction attempt (95k); final master (claude/sonnet role) VERDICT: APPROVED | 303,196 |
Usage was KNOWN for every step (0 unknown). Total about 578k weighted tokens.

## Orchestrator defects found by this run (fixed, with tests in `tests/test_roles.py`)
1. agy as reviewer tried a shell command (the diff preview was cut at 6000 bytes), was denied and returned nothing: tool reviewers now get a 60,000-byte
   preview and are told they have no shell or repository.
2. A new phase's lanes did not see earlier phases' applied output (cut from HEAD): context paths now include every earlier phase's applied files.
   (No dedicated unit test; proven by the real run, where `recall-op` received 4 context files.)
3. A role configured in `default_roles` with the tool's own model (empty profile) counted as unassigned: now it is an assignment.

## Not done / remaining
- Manual follow-up edit after the run: title/category caps in `rpp_memory.py` plus one test (the reviewers did not flag unbounded titles).
- SecondBrain `docs/repository_inventory.json` not updated (it was already stale for all earlier RPP files).
- Hub has no grant UI or IPC route; Orchestrator does not call `memory.recall` yet.
- The phase-1 project stayed `blocked` (history kept; not resumed).
