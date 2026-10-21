# Product source rules

This is the independent Respected Orchestrator source. Do not import SecondBrain internals, require a vault, install
global dependencies, edit AI configs or modify live user data. The private JSON entry point is for the Hub and tests,
not a separate user-facing CLI; the only public commands are `--version` and the product-contract lifecycle commands
(`setup`, `update`, `repair`, `uninstall`: install record only, see `docs/PRODUCT_CONTRACT.md` in the ecosystem root). Worker fixtures and Git operations belong in temporary projects.

No Git commits, pushes or parallel agents unless the user explicitly asks. Preserve scope checks, deadlines,
process-tree cleanup, failed/stale/tampered-result rejection and explicit bounded retries.

Every spawn of the engine goes through `context.engine_command` (it must keep working in the packaged exe); every
child process goes through `engine/winproc`. Run `python -m unittest discover -s tests -t .` and, for packaging changes,
`python packaging/build_dist.py` plus `tests.packaging.test_frozen_build`.

Binding decisions live in `docs/decisions/`; keep them true to the code in the same change. No folders named after
process tools.
