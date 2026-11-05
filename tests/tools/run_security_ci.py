"""FIX-01 / ADR-017: the mandatory security run and its evidence manifest. No test here may skip.

    python tests/tools/run_security_ci.py run MANIFEST.json   run the security set, write the manifest, exit 1 unless clean
    python tests/tools/run_security_ci.py verify MANIFEST.json   gate: re-check a manifest against this checkout and SHA

The set is the AppContainer worker matrix, the real sandbox cases, the verify-isolation cases and the frozen exe matrix.
An elevated session is a failure (the boundary refuses it), never a skip. The one excluded test needs a Cursor
CLI session and is listed by name in the manifest.
"""
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ("tests.engine.test_worker_security", "tests.engine.test_sandbox", "tests.engine.test_security_gate",
           "tests.packaging.test_frozen_security", "tests.engine.test_worker_policy.RealSandboxTests")
EXCLUDED = {"tests.engine.test_worker_policy.RealSandboxTests.test_node_worker_can_start_piped_children_and_resolve_paths":
            "needs a Cursor CLI session; runs only on a machine that has one (ADR-017)"}
MINIMUM_TESTS = 28  # the registry may grow, never shrink below what was measured; raise it when tests are added


def flatten(suite):
    for item in suite:
        yield from flatten(item) if isinstance(item, unittest.TestSuite) else [item]


def commit_sha():
    return os.environ.get("GITHUB_SHA") or subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def collect():
    loader = unittest.defaultTestLoader
    tests = [t for name in MODULES for t in flatten(loader.loadTestsFromName(name))]
    return [t for t in tests if t.id() not in EXCLUDED]


def run(manifest_path):
    from respected_orchestrator.engine import appcontainer
    elevated = appcontainer._is_elevated()
    tests = collect()
    result = {"commit_sha": commit_sha(), "runner": os.environ.get("ImageVersion", "local"), "elevated": elevated,
              "expected": len(tests), "tests": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
              "excluded": EXCLUDED, "skipped_ids": [], "started": time.time()}
    if not elevated:
        outcome = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests))
        result.update(tests=outcome.testsRun, failed=len(outcome.failures), errors=len(outcome.errors), skipped=len(outcome.skipped),
                      skipped_ids=[t.id() for t, _ in outcome.skipped])
        result["passed"] = result["tests"] - result["failed"] - result["errors"] - result["skipped"]
    result["finished"] = time.time()
    Path(manifest_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    problems = validate_manifest(result, result["commit_sha"])
    print("security run:", "OK" if not problems else "; ".join(problems))
    return 1 if problems else 0


def validate_manifest(manifest, expected_sha):
    """Every reason the gate must stay red. Pure, so the gate itself is unit-tested with forged manifests."""
    if not isinstance(manifest, dict) or not manifest:
        return ["manifest is empty or not an object"]
    problems = []
    if manifest.get("commit_sha") != expected_sha or not expected_sha:
        problems.append(f"manifest is for commit {manifest.get('commit_sha')!r}, not {expected_sha!r}")
    if manifest.get("elevated") is not False:
        problems.append("the run was elevated or did not record elevation")
    for field in ("failed", "errors", "skipped"):
        if manifest.get(field) != 0:
            problems.append(f"{field} = {manifest.get(field)!r}, must be 0")
    tests = manifest.get("tests")
    if not isinstance(tests, int) or tests < MINIMUM_TESTS or tests != manifest.get("expected") or tests != manifest.get("passed"):
        problems.append(f"tests={tests!r} expected={manifest.get('expected')!r} passed={manifest.get('passed')!r}; need all of at least {MINIMUM_TESTS}")
    if manifest.get("excluded") != EXCLUDED:
        problems.append("excluded set differs from the one recorded in ADR-017")
    return problems


def verify(manifest_path):
    try:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print("manifest unreadable:", error)
        return 1
    problems = validate_manifest(manifest, commit_sha())
    print("security gate:", "OK" if not problems else "; ".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    action, target = (sys.argv[1:3] + [None, None])[:2]
    sys.exit({"run": run, "verify": verify}.get(action, lambda _: print(__doc__) or 2)(target))
