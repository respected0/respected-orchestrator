# Packaged engine: respected-orchestrator.exe

Status: implemented 2026-10-21 (user decision: the Orchestrator ships like SecondBrain, no Python on the machine).

* `tools/build_dist.py` freezes the private entry point with PyInstaller (onedir, contents in `app/`) into
  `RespectedOrchestrator/` with `respected-orchestrator.exe` and `distribution.json` (sha256 of every file, version read
  from the source). Agent Framework's lazy submodules are collected; installed packages outside the declared dependency
  closure are excluded, so a local build contains what a clean CI build contains.
* The engine restarts itself through `context.engine_command`: the exe when frozen, `python -m respected_orchestrator`
  from source. This covers the detached task, project and campaign supervisors; the restricted-token acceptance launcher
  becomes the private `_sandbox-exec` command. `_selfcheck` imports every module of a build and fails on a missing one.
* The Hub installs the folder as a signed catalog bundle and verifies it with the product's own RPP answers. The product
  records the install from its `distribution.json` (`lifecycle.apply` with `target.distribution`), re-hashing every file,
  so the Hub and the product agree on "installed" and "repair-needed". Uninstalling such a record leaves the folder to
  the Hub.
* The Hub's separate Python runtime component is gone; development builds of the Hub can still run this source on Python.

Proof: `tests/packaging/test_frozen_build.py` runs the built exe with no Python on PATH (RPP, MCP, a real write task through
the detached supervisor and sandboxed acceptance); `tests/interfaces/test_rpp_lifecycle.py` covers distribution records
including tampering and path escape. CI builds the exe and requires both.
