# Windows Native Codex investigation and approved corrections

Date: 2026-10-10 (Europe/Istanbul).

## Evidence

- `~/.codex/.sandbox/sandbox.2026-10-09.log:820` records runtime read/execute
  validation failing while opening the ACL target for the active
  `cua_node/3dd31cfff853001c/bin/node_repl.exe`, with Windows error 32.
  Lines 821-823 turn that failure into `setup refresh had errors`.
- A read-only Restart Manager resource query found four running users of that
  executable. Their parents lead to the desktop Codex app. This identifies
  current file users, not the exact historical incompatible handle.
- Current runtime ACL already allows `CodexSandboxUsers` read/execute.
  Broadening permissions is not justified by the sharing-violation evidence.
- The old 22:56 demo's stdout line 6 shows access denied while reading the brief
  from `data/state`, outside its worktree. Later rollout user messages contain
  the full inline brief. The existing inline-brief change is retained.
- Rollout metadata records the correct parent worktree, while the 23:13 demo's
  stdout line 10 shows a denied `Set-Location` followed by `C:\` and continued
  commands. The precise child-executor cwd mechanism remains unresolved.
- The 23:13 demo's stdout lines 18 and 21 show incorrect shell invocation of
  the patch wrapper: stdin instead of a patch argument, then broken quoting.
- The 2026-10-10 00:06 demo (`run-20261009210638-b825c4c60349`) changed
  `calculator.py` to `return a + b`; its `check-1.log:6` says `OK`.
  `status.json:6` rejects it for scope violation involving two `.pyc` files.
  Their creation timestamps match the runner acceptance step, after worker exit.
- Model-list decoding failed even in that successful-edit demo. It is a
  separate observed error, not sufficient to explain all failed work.
- Rollouts include both `0.162.0` and `0.162.0-alpha.20`. Ubuntu WSL2 success
  with `0.160.1` is user-reported evidence, not a controlled local comparison.

## Implemented scope

See [the result decision](../decisions/codex-worker-results.md).

The runner now reads Codex JSONL completion and final agent status before
acceptance. The demo resolves the CLI once, retains workspace-write sandboxing
and uses Python `-B` so acceptance does not produce out-of-scope bytecode.
The brief includes Windows command and native patch guidance. No dependencies
or configuration files were changed.

## Verification

Four regression tests were run before the changes: the failed-stream cases
advanced to acceptance, the built-in adapter lacked JSON output, and the demo
acceptance produced `__pycache__`. Those expected regressions then passed after
the changes. Fixtures and all fixture Git operations use temporary projects.
The AI CLI boundary is mocked; real runner gates and Python acceptance execute.

Full suite: `.venv/Scripts/python.exe -B -m unittest discover -s tests
-p 'test_*.py' -v` with this product's `src` on `PYTHONPATH` passed all 61 tests
on Windows. This includes scope rejection of ignored files, signed-result
tampering, stale projects, bounded retries and Windows descendant cleanup.
Repository-atlas verification uses the required filesystem-only review gate;
it is separate from the Git-backed CI gate, which was not run.
`--update`, semantic review, explicit `--accept-reviewed` for every changed file,
generated `--write` and `--check` passed with 26 inventoried source files.

## Remaining limits

No live AI worker, model endpoint or sandbox refresh was started. No Codex
session or kernel was closed. Runtime files, live data, model profiles,
credentials, Context Mode and Ponytail settings were not modified. No source
repository Git command was run.

The external sandbox sharing violation remains unresolved. Existing API/tool
controls do not establish a way to release every relevant runtime user without
affecting active sessions. CLI path resolution improves reproducibility but
does not freeze an executable's contents or prove a particular version fixes
the runtime. A larger timeout is not a demonstrated solution.
