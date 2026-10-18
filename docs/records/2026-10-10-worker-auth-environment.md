# Windows worker authentication and environment correction

Date: 2026-10-10. Follow-up to the single approved live test
`run-20261009220955-e86602647c77`.

## Observed failure

The project-local 0.162.0-alpha.20 worker failed in 40.152 seconds with exit 1,
`WORKER_FAILED`, and no corrections/retry run. The provider auth command exited
2; model refresh returned HTTP 401. JSONL contains `turn.failed` and no worker
tool calls. No acceptance, patch or verified result was produced.

Evidence directory:
`C:\Users\Furkan\AppData\Local\Temp\respected-maf-live-20261010-010955-3c2wdoms\data\state\run-20261009220955-e86602647c77`.
`stderr.log` line 2 is the auth command error, line 5 the 401;
`stdout.log` line 10 is the terminal failure. Source and worktree fixture files
remain byte-identical. The sandbox log last modification remains 21:42:51Z,
before this test, so this run did not test the ACL fix.

## Free reproduction proves the auth cause

Existing helper: `C:\Users\Furkan\AppData\Local\CodexSwitcher\Evren-Token.ps1`.
Its configured arguments select `-Mode token -Slot 1`, without `-Auto`, so the
offline probe reads existing credentials without the helper's network test.
No helper or credential file was edited, and no token was printed or persisted.

The helper succeeds in the application-tool environment, but exits 2 in the
native PowerShell-launched Python environment. Both report the same Windows
user and restricted/elevation metadata. User profile and LOCALAPPDATA match.
The critical difference is inherited `PSModulePath`.

The failing environment includes PowerShell 7/native bundled module paths
alongside Windows PowerShell paths. In a child Windows PowerShell process,
`Import-Module Microsoft.PowerShell.Security` reports duplicate extended type
members (`AuditToString`, `AccessToString`, `Sddl`, etc.). The helper calls
`ConvertTo-SecureString` at line 24; its catch at lines 89–90 suppresses the
actual module exception, eventually emitting the misleading missing-key
message at lines 112–113.

| Controlled offline probe | Result |
| --- | --- |
| Existing helper, inherited parent environment | exit 2, empty stdout |
| Same helper, cwd, arguments and user; only child `PSModulePath` removed | exit 0, non-empty captured stdout |

Windows `os.environ` normalizes names to uppercase. Filtering the copied
environment must therefore be case-insensitive; removing a mixed-case key from
a normal Python dict does not remove `PSMODULEPATH`. No credential reset or
Windows security bypass is required.

## Implemented correction

- Shared execute copies the child environment and removes PSModulePath on
  Windows, case-insensitively. Parent environment, other variables, Windows
  jobs, deadlines, cancellation and descendant cleanup remain intact.
- The demo uses the existing profile/provider/helper. Authentication retrieval
  is bounded, captured and discarded; failures stop before Git or inference.
- Missing/empty/malformed existing sandbox marker now stops the demo before
  auth, fixture creation or AI. This exposes broken setup; it does not hide it
  or claim a valid marker guarantees runtime success.
- Private-home isolation was removed after inspecting provisioning behavior.
  No isolated_codex request flag or private config preparation remains.

## Free verification and remaining runtime blocker

A single GET of the existing provider's /models endpoint returned HTTP 200,
15 models, including mimo-v2.6-pro. It proves authentication/model presence,
not Codex metadata schema compatibility. Token data was never printed/stored.
No paid inference occurred in the follow-up.

Direct native sandbox validation failed with helper_sandbox_lock_failed.
Evidence: C:\Users\Furkan\AppData\Local\Temp\respected-free-native-proof-hwoa2lea.

A deterministic localhost Responses fixture then exercised the real project
runtime's exec --json and exec_command tool through MAF. Two generated SSE
responses requested a PowerShell worktree check/file edit, then reported
blocked after the actual tool failed. This makes the failure independent of
MiMo generation or EVREN compatibility; no external inference was requested.

Run: run-20261009225540-53a1ec1f0ed7. Elapsed: 30.709 seconds.
Evidence: C:\Users\Furkan\AppData\Local\Temp\respected-local-protocol-proof-vkfh6wa9\data\state\run-20261009225540-53a1ec1f0ed7.
The sibling root result.json contains the local fixture summary/tool output.
stdout.log line 5: command_execution exit -1 with sandbox provisioning failure
opening C:\Users\Furkan\.codex\.sandbox-bin.
Line 6: explicit blocked final result; line 7: turn.completed.
Engine: failed / worker_failed / WORKER_FAILED, CLI exit 0. No acceptance log,
worker.patch or verified result.json exists. Source fixture remains unchanged.
config.toml and mimo.config.toml hashes remained unchanged during this fixture.

### Proven facts versus unresolved explanation

Provisioning failure opening .sandbox-bin is proven on the real tool path.
The owner's read-only CreateFile probes against that directory succeed with
MAXIMUM_ALLOWED, READ_CONTROL and read attributes; the directory is owned by
RESPECTED/Furkan. Its ACL grants owner Modify + ChangePermissions, SYSTEM and
Administrators Modify, and CodexSandboxUsers ReadAndExecute. No ACL was changed
by an explicit repair command.

Codex alpha.20 setup_provisioning.rs lines 362-368 opens the directory in
ProvisionOnly mode with READ_CONTROL | WRITE_DAC. Its generated DACL at lines
378-389 grants SYSTEM/Admins Modify without WRITE_DAC, while the owner has it.
This permission asymmetry is a strong candidate for service-side failure,
not a fully proven access-check result: service token and underlying Win32
error were not accessible. Do not declare an owner ACL repair sufficient.

Sources:
https://github.com/openai/codex/blob/rust-v0.162.0-alpha.20/codex-rs/windows-sandbox-rs/src/setup_provisioning.rs#L343
https://github.com/openai/codex/blob/rust-v0.162.0-alpha.20/codex-rs/windows-sandbox-rs/src/setup.rs#L1197

### Unexpected shared security side effects

The direct sandbox probe and local protocol fixture triggered provisioning.
Logs C:\Users\Furkan\.codex\.sandbox\sandbox-924bab1667e6fe58.log and
sandbox-bf3a9de09380da43.log record ensuring the global sandbox users, firewall
rule configuration and WFP filters before the directory lock failure.
setup_marker.json is now zero bytes; setup_error.json reports the lock failure.
Existing-session effects are unknown. The probe should not have been assumed
free of security-state side effects merely because no model was contacted.
Further Codex executions were stopped; no service was stopped, and no global
settings, account passwords, firewall rules or ACLs were manually repaired,
rolled back, copied or restored.

Earlier private-home source inspection also found provision_sandbox_users
creates new passwords for the same global CodexSandboxOffline/Online names.
That approach was withdrawn to avoid additional session interference.

## Validation and prioritized next steps

Final verification: `.venv/Scripts/python.exe -B -m unittest discover -s tests`
with child-only `PYTHONPATH=src`: 72 tests, 55.709 seconds, exit 0, OK.
`repository_map.py --filesystem-only --write --check`: 30 files, check passed.
The free suite includes environment casing/parent preservation, preflight
no-write behavior, invalid-marker stop before auth/Git/worker, blocked JSONL,
MAF, scope, stale/tampered result rejection, deadlines and tree cleanup.
Git operations are confined to disposable fixture projects; source Git was
never used. Python 3.11+ is needed for the demo's TOML preflight.

1. Preserve evidence and stop runtime retries while shared setup is invalid.
2. With separate approval, inspect/repair the shared sandbox provisioning state
   and the service's directory access; retain protected DACL, sandbox-user read
   restrictions and firewall isolation. Do not blindly reset accounts or
   broaden permissions. Session impact must be agreed before provisioning.
3. Validate actual command/patch/acceptance with an offline local fixture after
   repair. Only then request approval for one additional paid MiMo test.

The project-local alpha.20 contains the independently proven original active
runtime ACL fix, but is a prerelease. Native MiMo end-to-end success and Codex's
model metadata decode issue are not declared fixed. Full brief transfer is
correct and remains intact.
