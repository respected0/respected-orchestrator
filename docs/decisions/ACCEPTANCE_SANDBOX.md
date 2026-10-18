# Acceptance sandbox: worker-written code must not hold the engine's authority

Status: implemented 2026-10-17 (Windows). Audit finding P0 #4.

## Problem
The engine runs acceptance commands (and project `verify` commands) on code a worker wrote. They ran as the same
Windows user as the engine, so that code could read `data_root/.engine-key` (the HMAC key that signs run evidence and
`maf-approval.json`), read the memory grant token in the settings, rewrite signed evidence or re-ACL any of it. The human
approval gate (TTY + `RESPECTED_ORCH_CHILD`) was therefore only as strong as the file permissions of a same-user process.

## Decision
Those commands run through `sandbox_exec` with a **restricted token** (`CreateRestrictedToken` + `CreateProcessAsUser`):

* The token keeps every SID the user has as a *restricting* SID, so tools, caches and the worktree behave as before, and
  adds one more restricting SID that belongs to this data root (`data_root/sandbox.json`, a well-formed SID that no real
  account owns). Windows checks access twice (normal SIDs, restricting SIDs); a **deny ACE for that SID** therefore blocks
  the sandbox while the engine, whose token lacks the SID, is unaffected.
* `DISABLE_MAX_PRIVILEGE` removes backup/restore/take-ownership style privileges (only traversal stays).
* The data root denies the SID on every current and future child (inheritable, inherit-only), on the directory itself
  for creating/replacing/deleting/re-ACLing, and on the key file (its ACL is protected, so it carries its own deny).
  `workspaces/` (the worker's area) breaks inheritance first and stays fully usable.
* An **OWNER RIGHTS** ACE limits the owner's implicit rights to READ_CONTROL. Without it the owner (the same user) would
  keep WRITE_DAC, which no deny ACE can remove, and the sandbox could grant itself back access. This was found by the
  adversarial test, not assumed.
* Fail closed: if the boundary cannot be set up the run ends `failed` with reason `sandbox_unavailable`; there is no
  silent fallback. `RESPECTED_ORCH_SANDBOX=off` is an explicit developer switch (also the only way non-Windows runs).
* Final approval stays in the trusted control plane: it needs the key (unreadable to the sandbox) and the interactive gate.

## Proven (tests/test_sandbox.py, with a negative control)
Sandboxed code cannot: read the key (plain path, `\\?\` path, junction, hardlink), read settings/evidence, create or
overwrite or delete anything under the data root, forge `maf-approval.json`, rewrite the key's ACL, remove the deny ACE,
take ownership, or obtain the signing key through the engine's own `_signature`. It can: write/read its worktree and
start child processes. The same probe without the sandbox succeeds in every attack, so "denied" means the boundary.

## Limits (not hidden)
* Only the engine's secrets and evidence are protected. The sandboxed code still reads the user's other files
  (for example AI client credentials in the profile) and has network access.
* Worker CLIs themselves (claude/codex/agy) are not run in this token; they have their own permission modes.
* Windows only. A user who is a local administrator running an elevated engine is outside this model.
* First use per data root runs one PowerShell ACL setup (about a second); the result is cached by key file identity.
