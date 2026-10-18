# Product source rules

This is the independent Respected Orchestrator source. Do not import Brain
internals, require a vault, install global dependencies, edit AI configs or modify
live user data. Private JSON entrypoints are for Hub and tests, not a separate
user-facing CLI. Worker fixtures and Git operations belong in temporary projects.

No source repository Git actions/commits or parallel agents unless the user
explicitly requests them. Preserve scope checks, deadlines, process-tree cleanup,
failed/stale/tampered-result rejection and explicit bounded retries.

For any changed/added/moved file, read its contents/callers, update its semantic
role/purpose/relationships in `docs/repository_inventory.json`, run
`python tools/repository_map.py --filesystem-only --update`, fill NEEDS_REVIEW,
then `--accept-reviewed PATH` for each reviewed file. Generate `--write` and pass
`--check` with relevant tests. Do not manually edit generated REPOSITORY_MAP.
When Git is available/authorized the normal Git-backed mode remains the CI gate.

Decisions belong in docs/decisions and dated evidence in docs/records. No folders
named after process tools. Cross-product extraction status is currently in
`../secondbrain/docs/PROJECT_STATUS.md`; that documentation link is not a runtime
dependency. Long-term protocol/lifecycle targets must be distinguished from code.
