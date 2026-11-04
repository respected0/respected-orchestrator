"""CI entry point: unittest discovery, with an explicit skip list for hosted runners.

Hosted Windows runners are elevated and the worker boundary refuses elevated sessions by design, so tests that need
the real sandbox cannot run there. With ORCH_ALLOW_ELEVATED_SKIP=1 *and* an elevated token, exactly the test ids in
tests/elevated_ci_skips.txt are reported as skipped (never silently passed). Anywhere else everything runs.
Run the full suite on a non-elevated machine before releasing.
"""
import os
import sys
import unittest
from pathlib import Path

from respected_orchestrator.engine import appcontainer

SKIPS = Path(__file__).resolve().parents[1] / "elevated_ci_skips.txt"


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    skipping = os.environ.get("ORCH_ALLOW_ELEVATED_SKIP") == "1" and appcontainer._is_elevated()
    ids = set(SKIPS.read_text(encoding="utf-8").split()) if skipping else set()
    suite = unittest.TestSuite()
    for test in flatten(unittest.defaultTestLoader.discover("tests", top_level_dir=".")):
        if test.id() in ids:
            method = getattr(test, test._testMethodName)
            test = _skipped(test, method)
        suite.addTest(test)
    print(f"run_ci: elevated skip list active for {len(ids)} test ids" if skipping else "run_ci: no skips")
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


def _skipped(test, method):
    reason = "needs the worker sandbox; refused in an elevated session (hosted CI runner)"
    setattr(test, test._testMethodName, unittest.skip(reason)(method))
    return test


if __name__ == "__main__":
    sys.exit(main())
