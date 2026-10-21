# Autonomous Master Report

## Overall outcome

**PARTIAL** — the MAF-to-Orchestrator production integration is implemented and 44 focused tests pass, but no intentional live end-to-end EVREN smoke test was run. One unintended live reviewer call occurred during early test development before the reviewer was mocked; it returned `REJECTED` and its temporary usage evidence was discarded with the test fixture. A later interrupted session left the full unit-test suite red; that failure is now root-caused and fixed, and **88/88 tests pass** (see the Recovery phase section below).

## Executive summary

The normal Orchestrator task path now supports a configurable MAF pipeline:

`Task → isolated implementation worker → deterministic scope/acceptance checks → independent reviewer → bounded correction → optional deep review → human approval if required → final result`

Corrections no longer restart the same completed run identity. Each correction creates a fresh signed run and isolated worktree while preserving the original attempt, patch, fingerprint, reviewer, and approval evidence. Reviewer execution failures, malformed reviewer output, rejection, worker failure, timeout, cancellation, scope violation, and acceptance failure remain distinct fail-closed states.

## Initial architectural findings

- `runner.execute_task()` already owned the correct safety boundary: isolated lane, ownership/forbidden scope, acceptance, fingerprint, patch, cancellation, timeout, and signed result envelopes.
- `maf_workflow.run_maf_slice()` already provided bounded correction and checkpoint replay, but `run_maf_coding_task()` reused the same run identity, making correction unsafe.
- `vertical_slice.run_codex_call()` already provided bounded Codex execution and token usage parsing, including cached-input separation.
- The private JSON entrypoint was the correct integration surface for Hub/tests; no new public CLI or orchestration engine was needed.

## Implemented functionality

- Added per-task Codex worker profiles and signed workflow policy metadata.
- Added Codex token/model metadata to runner results.
- Added MAF pipeline execution through the private `maf` command.
- Added independent Codex reviewer calls with strict JSON decision validation.
- Added optional fast/deep review routing and risk-based deep review.
- Added fresh-run correction children with signed `maf-attempts.json` history.
- Added a two-correction default limit (`0..2`).
- Added human approval gating and `maf-approve`.
- Added pending/final MAF gates so crashes, failed review, or invalid review cannot be bypassed through `check_result`.
- Added token accounting for worker and reviewer usage without double-counting cached input.

## Changed files

- `src/respected_orchestrator/engine/runner.py`
- `src/respected_orchestrator/workflows/maf_workflow.py`
- `src/respected_orchestrator/__main__.py`
- `tests/test_maf_coding.py`
- `tests/test_maf_workflow.py`
- `docs/repository_inventory.json`
- `docs/REPOSITORY_MAP.md`
- `docs/AUTONOMOUS_MASTER_REPORT.md`

## Test commands and results

1. Baseline before changes:
   - `PYTHONPATH=src python -m unittest tests.test_engine tests.test_maf_workflow tests.test_maf_coding -v`
   - **31 tests, OK**
2. Final focused compatibility and MAF suite:
   - `PYTHONPATH=src python -m unittest tests.test_engine tests.test_maf_workflow tests.test_maf_coding tests.test_vertical_slice -v`
   - **44 tests, OK**
3. Full Python suite and syntax check:
   - `PYTHONPATH=src python -m compileall -q src tests`
   - `PYTHONPATH=src python -m unittest discover -s tests -v`
   - **83 tests, OK**
4. Repository map:
   - `python tools/repository_map.py --filesystem-only --update`
   - `python tools/repository_map.py --accept-reviewed <each reviewed path>`
   - `python tools/repository_map.py --filesystem-only --write`
   - `python tools/repository_map.py --filesystem-only --check`

## Mock versus live verification

- **Mocked:** approval, worker failure, reviewer request changes, correction and re-review, rejection, invalid reviewer output, reviewer execution failure, correction retry limit, deep-review routing, human approval, checkpoint replay, token accounting, scope violation, acceptance failure, timeout, cancellation, and patch isolation.
- **Live:** no intentional live EVREN smoke test was run. One accidental reviewer call occurred during test development before the reviewer mock was added; it was bounded by the fixture timeout, returned `REJECTED`, and made no repository change.

## Reviewer findings

No independent DeepSeek review of the final diff was performed because it would have required another paid call. The accidental early live reviewer call reviewed a disposable test fixture, not the final change, so it is not valid review evidence.

## Token usage and optimization opportunities

- Codex worker results now record raw input, cached input, output, reasoning, estimated weighted tokens, model, and duration.
- Reviewer calls record the same usage fields plus profile and stage.
- Cached input is not added to raw input; weighted usage uses `max(0, raw - cached) + round(cached * 0.03) + output`.
- Remaining optimization opportunities:
  - Measure real reviewer prompt size and token usage in one bounded smoke test.
  - Compare fast versus deep review cost on the same bounded evidence.
  - Add cumulative usage persistence across correction rounds.

## Known defects or risks

- The accidental live reviewer call left no retained token evidence because the disposable test root was cleaned up.
- Deep review risk routing currently uses changed-file count; it does not yet inspect semantic risk or security-sensitive paths.
- Correction children rebuild from the current project fingerprint; the pipeline blocks correction if the project changed, but does not automatically replay the previous patch.
- MAF is still marked experimental by Microsoft Agent Framework.

## Remaining tasks

- Run one intentional, small live EVREN end-to-end smoke test with usage reporting.
- Add semantic risk indicators for deep-review routing.
- Benchmark GLM/DeepSeek/MiMo on representative bounded tasks.
- Add Hub UI integration for `maf`, `maf-approve`, and final run inspection.

## How to run or inspect the pipeline

```powershell
$env:PYTHONPATH = "src"
$request = @{
  project_root = "C:\path\to\project"
  task = "Implement the bounded change"
  worker = "codex"
  worker_profile = "glm"
  kind = "write"
  ownership = @("src/example.py")
  forbidden = @("secrets.json")
  acceptance = @(@("python", "-m", "pytest"))
  timeout_seconds = 900
  workflow = @{
    max_corrections = 2
    reviewer_profile = "deepseek"
    deep_review = "risk_based"
    deep_review_profile = "deepseek"
    risk_changed_files = 5
    timeout_seconds = 900
    human_approval = $false
  }
} | ConvertTo-Json -Depth 5

$request | python -m respected_orchestrator --data-root C:\path\to\data create
python -m respected_orchestrator --data-root C:\path\to\data maf RUN_ID
python -m respected_orchestrator --data-root C:\path\to\data check FINAL_RUN_ID
```

If the MAF result is `HUMAN_APPROVAL_REQUIRED`, inspect the final run and then run:

```powershell
python -m respected_orchestrator --data-root C:\path\to\data maf-approve FINAL_RUN_ID
```

## Recommended next step

Run one bounded live EVREN smoke test with a tiny temporary Git project, then use its recorded usage to tune reviewer prompts and deep-review routing before enabling the pipeline for production tasks.


## Recovery phase — interrupted-session stabilization

Added by the recovery engineer (DeepSeek V4.1 Flash) after the GLM session was cut off by `stream disconnected before completion`.

**Status: COMPLETE** for the recovery scope. The project-wide outcome stays PARTIAL only because the intentional live EVREN smoke test is still outstanding.

### Root cause of the failing full-test run

- `python -m unittest discover -s tests` imports each test module as a top-level module (`test_test_isolation`), so the `tests` package `__init__.py` is never executed. That also explains the "15 focused tests passed" result: focused runs like `python -m unittest tests.test_test_isolation` do import the package and run its `__init__`.
- The isolated-test guard in `src/respected_orchestrator/engine/processes.py::execute` was armed only by the `RESPECTED_ORCH_TEST_ISOLATION` env var, which was set solely in `tests/__init__.py` and `tests/conftest.py`.
- Under discovery the env var was therefore unset for nearly the whole run, the guard was disarmed, and `execute(["codex", "exec"], ...)` actually launched the real Codex CLI. The only reported failure was `test_execute_blocks_codex_cli_in_isolated_tests` (`RuntimeError not raised`).

### Changes made

- `src/respected_orchestrator/engine/processes.py`: added `import sys` and `_tests_loaded()`, which returns True when a test module (`tests`, `tests.*`, `test_*`) is already in `sys.modules`. The Codex-blocking guard now fires when the env var is set **or** a test session is detected, so the block no longer depends on the import path. Production imports are unaffected (`_tests_loaded()` is False in a plain process).
- `docs/repository_inventory.json`: updated the `processes.py` role/purpose/relationships.
- `docs/AUTONOMOUS_MASTER_REPORT.md`: this section.

No production behavior, sandbox, ownership, acceptance, approval, fingerprint, or worktree logic was changed.

### Verification (commands and results)

- Production import sanity: `_tests_loaded()` is `False` and the env var is unset in a plain `python -c "import respected_orchestrator.processes"` process, so the guard stays inert outside tests.
- `python -m unittest tests.test_test_isolation -v` -> 3 tests, OK.
- `python -m unittest discover -s tests` -> **88 tests, OK** (previously 88 run, 1 failure).
- Correction-patch inheritance, tamper rejection, worktree/run isolation, and the bounded two-correction limit are exercised by the passing tests `test_correction_inherits_verified_patch_in_new_worktrees`, `test_correction_rejects_tampered_previous_patch`, `test_correction_uses_a_new_isolated_run_and_re_review_approves`, and `test_correction_retry_limit_is_bounded_at_two`.

### Remaining risks and items requiring independent GLM review

- `_tests_loaded()` is a name-based heuristic. It could in principle misfire if a production process imported a module literally named `test_*`; nothing does today, and the env-var path remains the explicit control. A single explicit test-session marker could replace the heuristic.
- The guard only blocks commands whose executable name starts with `codex`. Whether it should also block other external AI CLIs (for example Antigravity/`agy` when not faked) is a design decision for review.
- No intentional live EVREN smoke test has been run, so token/cost tuning evidence is still missing.
