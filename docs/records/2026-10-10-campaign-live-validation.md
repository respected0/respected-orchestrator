# Campaign live validation, 2026-10-10

Two small, harmless live campaigns on disposable temp projects (no ecosystem
repository was touched). Data root: `%TEMP%\respected-live-data-222814`.

1. `camp-20261010192826-5aad66f5`: three Git lanes (hub, secondbrain, orchestrator)
   started in the same second, ran concurrently, DeepSeek implemented under the
   Codex `workspace-write` sandbox (logon via CodexSandbox users), GLM reviewed
   (`APPROVED`), `LANES_APPROVED`, then the supervisor started `claude -p`
   automatically (`master.finished COMPLETE`). Lanes took 4.3, 6.5 and 7.4 minutes.
   Usage (weighted tokens): 118653, 50881, 113715. Claude could not apply because
   `claude -p` has no permission for it by default; `allow_apply` was added.
2. `camp-20261010193746-75d4f7fa`: a non-Git source via mirror, `allow_apply=true`:
   lane approved in 4.2 minutes, the new master process applied the patch to the
   source (no `.git` created, no commit) and reported no further cycle needed.

Not exercised live: GLM-takeover/DeepSeek-review correction (covered offline by
`test_escalation_hands_code_to_glm_and_deepseek_reviews_it`), supervisor crash
recovery (re-running `campaign-run` resumes recorded lanes and the one-shot final
claim), `HUMAN_APPROVAL_REQUIRED` (offline only). One transient
`CreateProcessWithLogonW failed: 1056` appeared in a worker tool call and the
worker recovered. Offline suite: see the final report of this session.
