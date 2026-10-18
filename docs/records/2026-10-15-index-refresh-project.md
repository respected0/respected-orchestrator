# 2026-10-15 — native verification, token ACL, and the index refresh project

## 1. Native verification of the Hub memory panel (built release exe, disposable roots, fake home, WebView2 DevTools; driver `C:\ov\native_memory.mjs`)
Panel mounts on Orchestrator -> Ayarlar, shows "Kapalı", the confirmation lists what is shared, enable writes the token file and a SecondBrain grant, disable removes the file and revokes
the grant; the token is not in the page DOM, not in `settings.json`, not in the grants file. 
Confirmed defects fixed (both found by this run):
1. The panel reloaded its status after an action and that reload cleared the action's error, so a failed enable showed nothing (the user only saw "Kapalı"). Error/result is now set after the reload (same fix applied to the new index card).
2. `memory_command` in a development Hub (source mode) lacked the Hub's `RESPECTED_APP_DIR`/`RESPECTED_DATA_DIR`, so recall could target another SecondBrain data root than the grant (fixed in `brain_rpp_command`; production/frozen mode was already correct).
Side finding: with `RESPECTED_DATA_DIR` unset the development Hub talks to SecondBrain's DEFAULT data root; a first run hit the real folder with `memory.grant` and was refused with NO_VAULT (nothing was written: `%LOCALAPPDATA%\RespectedBrain` is empty).

## 2. Token file ACL (Windows)
`icacls` on `memory-token`: only the owner (`RESPECTED\Furkan:(F)`), inheritance removed, identical to `.engine-key`; the local accounts `CodexSandboxOffline` / `CodexSandboxOnline` are not in the ACL.
A real access attempt as those accounts was not made (no credentials). Confirmed defect fixed: the file was written with the secret BEFORE the ACL was tightened (about 100 ms with inherited `Users:RX`); `store_token` now creates the empty file, restricts it, then writes (test `test_the_file_is_restricted_while_still_empty`).
The same ordering weakness exists in the pre-existing `.engine-key` creation (`runner._key`); left as is (outside this change; key is created once per data root).

## 3. Index refresh (`memory.index.status` / `memory.index.refresh`) through Orchestrator
Contract: `respected-secondbrain/docs/decisions/RPP_MEMORY_RECALL.md` ("Index refresh").
| repo | project | outcome | weighted tokens |
|---|---|---|---|
| SecondBrain (mirror `C:\ov\sb`, patch `C:\ov\index-refresh.patch`) | `proj-20261015123815-2a492a17` | index-op approved first try; register failed acceptance once, approved on correction | 251,090 |
| Hub backend | `proj-20261015125522-f408f4f9` | lane approved + applied; project blocked at its own real-engine verify (the test assumed a vault with only 3 notes, the install creates template notes); fixed by hand, passes | 134,091 |
| Hub UI | `proj-20261015125949-fb1ea907` | approved first try | 76,518 |
Lesson recorded: a failing phase `verify` after an applied lane cannot be retried by the project (no failed lane); put real-engine tests in the lane acceptance when the engines they need are already applied.

## Evidence
- `C:\ov\e2e_refresh.py` (real RPP subprocesses): status missing -> recall INDEX_MISSING -> refresh without confirm BAD_REQUEST -> refresh (2 indexed) -> replay `replayed:true` -> recall hit -> note edited: recall returns 0 results (`dropped_stale` 1), status stale -> refresh (1 indexed, 1 skipped) -> old word 0 hits, new word hit; token only as hash; 1.0 request UNSUPPORTED_OP.
- Native: `C:\ov\native_index.mjs` on the SecondBrain settings page: missing state, confirmation, refresh result sentence, `memory-index-refresh.json` written, index created only under SecondBrain's data root, vault note byte-identical.
- Suites: see final report (SecondBrain full regression, Hub `accept_hub.py`, Orchestrator targeted tests, RPP conformance).
