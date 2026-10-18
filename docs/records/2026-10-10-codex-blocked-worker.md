# Windows Native MAF: blocked worker root cause

Date: 2026-10-10. Run: `run-20261009214208-56fa8b626e7e`.
Investigation, project-scoped corrections and free regressions only. No AI call,
Git command, current-session restart, credential/configuration edit, ACL write
or sandbox security bypass was performed during this investigation.

## Proven chain

Evidence directory:
`C:\Users\Furkan\AppData\Local\Temp\respected-maf-live-20261010-004208-_n5moyfq\data\state\run-20261009214208-56fa8b626e7e`.

| Evidence | Finding |
| --- | --- |
| `stdout.log`, lines 6 and 9 | Both shell calls exit -1 before process creation: `helper_unknown_error: setup refresh had errors`. |
| `stdout.log`, line 10 | Final agent JSON is `status: blocked`; no files changed, checks not run. |
| `stdout.log`, line 11 | `turn.completed` describes completion of the model turn, not completion of the assigned coding task. |
| `stderr.log`, lines 4–5 | CreateProcess rejection at 21:42:38Z and 21:42:51Z matches those tool failures. |
| `status.json` | Engine correctly rejects the blocked result, but labels the provider `COMPLETE` because the CLI exited zero. |
| Worktree and artifacts | `calculator.py` remains unchanged; no acceptance log, patch or verified result exists. |

Sandbox evidence: `C:\Users\Furkan\.codex\.sandbox\sandbox.2026-10-09.log`.
Lines 848–855 show the 0.162.0 sandbox setup helper using the correct assigned
worktree, then failing runtime read/execute validation while opening
`C:\Users\Furkan\AppData\Local\OpenAI\Codex\runtimes\cua_node\3dd31cfff853001c\bin\node_repl.exe`
for a root-only ACL update (`os error 32`). The helper exits 1, which propagates
as the generic refresh error. The user-profile ACL warning in line 849 is
explicitly continued; the runtime validation failure is the fatal condition.

Session `01a1229d-d4dd-7ec3-aacb-613603edba85` records CLI 0.162.0 and the correct
cwd in session metadata and turn context. The subprocess/worktree argument is
not the cause of this run. The engine passes the complete brief directly as one
argv value; changing that back would not fix a process-creation failure.

## Root cause proved without changing permissions

Read-only Windows `CreateFileW` probes against the active runtime executable
used identical sharing flags (`READ | WRITE | DELETE`), `OPEN_EXISTING`, and
`FILE_FLAG_BACKUP_SEMANTICS`. Handles were immediately closed:

| Desired access | Result |
| --- | --- |
| `MAXIMUM_ALLOWED` | Fails with Win32 error 32. |
| `READ_CONTROL` | Succeeds. |
| `READ_CONTROL | WRITE_DAC` | Succeeds. |

No ACL setter was called. Restart Manager's read-only resource list identified
four active `node_repl.exe` processes belonging to the current desktop app;
none was stopped. Existing runtime ReadAndExecute and worktree Modify grants
do not resolve the incompatible access request. Broadening permissions or
disabling the sandbox is unnecessary.

OpenAI independently describes this exact defect and access-mask correction in
[PR #51822](https://github.com/openai/codex/pull/51822), merged 2026-10-07.
Its Windows regression holds the executable open throughout ACL repair and
checks preserved deny permissions. Source comparison confirms the faulty file
open in [stable 0.162.0](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/windows-sandbox-rs/src/acl.rs#L549)
and [stable 0.162.1](https://github.com/openai/codex/blob/rust-v0.162.1/codex-rs/windows-sandbox-rs/src/acl.rs#L549).
[0.162.0-alpha.20](https://github.com/openai/codex/blob/rust-v0.162.0-alpha.20/codex-rs/windows-sandbox-rs/src/acl.rs#L549)
restricts that open to directories and requests narrower access for files.

Conclusion: the execution blocker is a Codex Windows runtime defect exposed by
concurrent use of the desktop runtime. Orchestrator has a separate classification
defect; MAF and the JSONL parser correctly rejected the task. The model reported
the blocker correctly. WSL success is consistent with this Windows-only defect,
but was not independently rerun here.

## Other observations and limits

Model refresh decode errors (`stderr.log`, lines 2–3) and missing-model-metadata
item (`stdout.log`, line 2) are real, but nonfatal in this run: the model produces
two tool calls and a valid final result. The EVREN response compatibility issue
remains separate and was not modified. No evidence in this run proves C:\ root
execution, worktree Access denied, shell quoting, patch encoding or a 180-second
timeout as its cause; shell creation fails before those stages.

## Applied correction

1. Shared `classify_worker_exit` now maps explicit blocked/failed/other
   non-success statuses and error payloads to `WORKER_FAILED` despite exit zero.
   Timeout, quota and authentication classifications remain specific.
2. Shared Windows Codex resolution now prefers the project-local fixed runtime.
   The demo already resolves through this helper. Normal PATH fallback and
   explicit custom-command paths are preserved; old signed requests remain
   historical evidence, not silently rewritten commands.
3. Installed the complete official Windows package in
   `.runtime/codex-0.162.0-alpha.20/`, isolated from the app/global installation.
   CLI reports `codex-cli 0.162.0-alpha.20`. Manifest, setup helper, command runner
   and code-mode host are present. Official
   [package discovery](https://github.com/openai/codex/blob/rust-v0.162.0-alpha.20/codex-rs/install-context/src/lib.rs#L286)
   resolves matching resources beside this manifest.

Archive: [official Windows full package](https://github.com/openai/codex/releases/download/rust-v0.162.0-alpha.20/codex-package-x86_64-pc-windows-msvc.tar.gz).
Size: 160449849 bytes. SHA-256 verified against official release metadata:
`54c20799c80d402be8a298c2e03b096773c7a9fc4ee98b52f7a92813581af0c4`.
Archive paths/types were checked before extraction; no links or escaping paths
were accepted. `.runtime/` is excluded from source inventory.

## Free verification

The new regression failed before implementation: the exact blocked shape and
four explicit failure payloads returned `COMPLETE`. After correction, replaying
the original saved stdout yields `blocked / WORKER_FAILED` without launching a
worker or rewriting the historical status.

34 Git-free tests pass: six Codex result/runtime-selection regressions, demo
acceptance, seven MAF tests, three vertical-slice tests, and existing policy,
path, lock, invocation, circuit-breaker, acceptance/timeout and unsafe-scope
tests. The demo test now mocks Git while retaining the real temporary Python
acceptance check. Signed failure state, exact cwd/full brief, no acceptance or
patch on blocked results, terminal stream validation and lock release are tested.

Git-backed lane/patch/engine fixtures were deliberately excluded because Git
is forbidden in this session. No live sandbox refresh or paid worker test was
run. The fixed CLI is a prerelease; complete Native MAF execution and any further
runtime/provider incompatibility still require an explicitly approved real run.
