"""REL-04: run one real security test per fixture family and gate the release decision."""
import argparse
import os
import json
import platform
from pathlib import Path
import sys
import time
import unittest

from respected_orchestrator import release_platform

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

FIXTURES = {
    "symlink": "tests.engine.test_apply_hardening.ApplyHardeningTests.test_forbidden_or_unsafe_patches_are_refused_even_with_a_valid_signature",
    "child_tree": "tests.engine.test_windows_processes.ProcessLifecycleTests.test_timeout_kills_the_whole_tree",
    "migration": "tests.interfaces.test_migrate.MigrateTest.test_a_failing_step_leaves_the_original_bytes_and_no_backup",
    "installer_rollback": "tests.interfaces.test_integrations.IntegrationsTest.test_opencode_rollback_restores_exact_foreign_content",
    "janitor": "tests.engine.test_windows_processes.ProcessLifecycleTests.test_an_orphan_left_by_a_finished_command_is_reaped",
    "secret_env": "tests.engine.test_runner.EngineTests.test_worker_environment_drops_secrets_unless_allowed",
    "mcp_recursion": "tests.interfaces.test_mcp_server.McpServerTest.test_stdio_roundtrip_and_recursion_guard",
}


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skipped_names = []

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.skipped_names.append(test.id())


def run_one(node):
    suite = unittest.defaultTestLoader.loadTestsFromName(node)
    stream = open(os.devnull, "w", encoding="utf-8")
    result = unittest.TextTestRunner(stream=stream, verbosity=0, resultclass=Result).run(suite)
    stream.close()
    if result.skipped_names:
        return "blocked"
    if not result.wasSuccessful():
        problems = result.failures + result.errors
        detail = problems[0][1][-600:] if problems else "unknown"
        if "No module named 'msvcrt'" in detail or "No module named 'winreg'" in detail:
            return "blocked"
        print("FIXTURE_FAIL", node, detail, file=sys.stderr)
        return "fail"
    return "pass"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", default=sys.platform)
    parser.add_argument("--output")
    args = parser.parse_args()
    fixtures = {}
    started = time.time()
    for name, node in FIXTURES.items():
        fixtures[name] = run_one(node)
    decision = release_platform.decide(args.platform, fixtures)
    payload = {
        "platform": args.platform,
        "machine": platform.platform(),
        "python": sys.version.split()[0],
        "seconds": round(time.time() - started, 2),
        "fixtures": fixtures,
        "tests": FIXTURES,
        "decision": decision,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + chr(10))


if __name__ == "__main__":
    main()
