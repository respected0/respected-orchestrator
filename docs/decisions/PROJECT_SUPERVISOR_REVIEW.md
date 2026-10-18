# Project Supervisor Review (adversarial)

Scope: `src/respected_orchestrator/project.py` (autonomous project supervisor), cross-checked against
`tests/test_project.py` and the `create_campaign` / `_snapshot_engine` / `_lane_summary` parts of
`src/respected_orchestrator/campaign.py`. No source was modified. Line numbers are for the current tree.

Companion tests: `tests/test_project_adversarial.py` (8 tests, all pass against the current code). Each
asserts an invariant that is currently *correct*; the defects below are documented, not asserted, because a
failing test was out of scope.

## Suspected defects

### D1 - `_spec` raises `AttributeError` (not `ValueError`) for non-dict budget/verify (medium)
`project.py:40`, `project.py:55-56`. `budget = value.get("budget", {})` then `budget.get(...)`, and
`for check in phase.get("verify", [])` then `check.get(...)`, assume both are dicts. A spec with
`"budget": "x"` or `"verify": ["x"]` (a string element) throws `AttributeError`, escaping the intended
`ValueError` contract that `create_project`/`start_project` rely on for clean rejection.
Fix: `if not isinstance(budget, dict): raise ValueError("Invalid project budget")` and reject any
non-dict `check` up front.

### D2 - phase `after` entries are never validated as slug strings (medium)
`project.py:60`, `project.py:65`. `after=list(phase.get("after", []))` accepts anything iterable and
`set(p["after"])` is used directly. `after=[["one"]]` raises `TypeError: unhashable type: 'list'`
instead of `ValueError`; `after="one"` is silently exploded into `['o','n','e']` and only fails later as
"unknown dependency". The campaign layer (`campaign.py:44`) validates lane `after` type; the project
layer does not.
Fix: `after = phase.get("after", []); if not isinstance(after, list) or not all(isinstance(d, str) and _NAME.fullmatch(d) for d in after): raise ValueError(...)`.

### D3 - lock acquisition TOCTOU on a stale lock (low)
`project.py:131-149`. When the existing `run.lock` is stale, each racer `unlink`s then re-creates. Two
concurrent supervisors can both judge the lock stale; the loser exhausts its 2 loop iterations and raises
`ValueError("Could not take the project lock")` rather than the friendlier "already being executed".
A third process can also interleave in the unlink->re-create window. Impact is bounded (single host, and a
stale lock only exists when the previous owner is dead), so severity is low.
Fix: on the post-unlink O_EXCL failure, re-read the owner; if it is now alive report "already being
executed", otherwise retry a few bounded times before giving up.

### D4 - token budget is only enforced between attempts (medium)
`project.py:232` checks `state["weighted_tokens"]` at the top of the loop, and usage is only added after a
completed campaign (`project.py:184-188`). A single attempt can therefore exceed `max_weighted_tokens` by an
arbitrary amount (bounded only by the campaign's own lane timeout), and a campaign that never writes
`result.json` (killed/timed out) records `0` weighted tokens even though it spent real budget. The
`max_seconds` deadline (checked in the same place, plus `cancel_path` wired into the runner/verify) is the
only hard stop within an attempt.
Fix: re-check the budget after each attempt and treat a missing `token_usage` on an interrupted campaign as
"unknown" rather than `0` (e.g. block rather than continue once a campaign is unaccounted for).

### D5 - only `ProcessStopped` is caught around `_attempt` (low-medium)
`project.py:253-256`. Any other exception from `_attempt` (state write `OSError`, a runner bug, a tamper
`ValueError` from `_load`) propagates out of `run_project`, leaving `state["status"] == "running"` on disk
(the value last saved at `project.py:227`) with the lock released. `resume_project` can recover, but
`project_status` reports a stale "running" and the crash reason is lost.
Fix: catch `Exception`, mark the attempt failed with `str(error)[:500]`, save, and let normal retry/block
accounting take over.

### D6 - `final_review` can be skipped permanently (medium)
`project.py:223-224` return immediately for a terminal project, and `final_review` is called only from the
live path right after `finish("completed")` (`project.py:241-243`). If the supervisor dies after
`finish("completed")` but before/during `final_review`, every future `run_project` hits the terminal guard
and the promised fresh review never runs. `_start_final_master` is idempotent ("no-op once claimed"), so
re-running it is safe.
Fix: on a `completed` state with a configured `final_review`, call `final_review` before returning from the
terminal branch (or persist a `final_reviewed` flag).

### D7 - `final_review` is validated against an arbitrary phase (low)
`project.py:71` borrows `phases[0]["workstreams"]` (the first *declared* phase, possibly a dependent one)
only to satisfy `campaign._spec`. No lanes actually run from it, so this is a validation quirk, not a
functional bug; it can reject an otherwise valid `final_review` if that phase happens to be shaped oddly.
Fix: validate with a single placeholder workstream instead of a real phase.

## Invariants verified as correct (covered by the new tests)
- Crash immediately after `apply_task` returns: resume skips the already-applied lane via the on-disk
  `applied.json` guard (`project.py:198`) and reuses the recorded campaign (`project.py:169,178`) - no double
  apply, no duplicate campaign.
- A refused apply is terminal for the phase (returned `"blocked"`, `project.py:192-202`) and is not retried.
- `ProcessStopped` is a failed attempt and is retried only up to `max_phase_attempts`
  (`project.py:246-256`); a rejected lane likewise burns the budget then blocks without applying.
- `cancel` is honoured at the loop top and after each attempt (`project.py:228,257`), leaving completed
  applies in place, and a cancelled project is terminal on re-run.
- Time and token budgets stop the loop before launching another campaign; a corrupt (non-numeric) lock is
  treated as stale rather than fatal.

## Notes
- `run_project`'s terminal guard makes re-running a `blocked`/`cancelled`/`completed` project a no-op, which
  is what tests D3/D6 partly rely on.
- The `max_phase_attempts` check at `project.py:247` reads `attempts[-1]['note']`; an attempt that reached
  here always has `note` because the guarded branch only re-enters when `attempts[-1].get("outcome")` is set.
