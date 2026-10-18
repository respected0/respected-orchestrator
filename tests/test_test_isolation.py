from pathlib import Path
import sys
import tempfile
import unittest

from respected_orchestrator.processes import execute


class TestIsolationTests(unittest.TestCase):
    def test_test_process_marks_codex_api_calls_isolated(self) -> None:
        import tests

        self.assertEqual(tests.__dict__.get("RESPECTED_ORCH_TEST_ISOLATION"), None)
        self.assertEqual(__import__("os").environ["RESPECTED_ORCH_TEST_ISOLATION"], "1")

    def test_execute_blocks_codex_cli_in_isolated_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(RuntimeError, "blocked in isolated tests"):
                execute(["codex", "exec"], Path(temporary), 1)

    def test_execute_allows_local_acceptance_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = execute(
                [sys.executable, "-c", "print('fixture')"],
                Path(temporary),
                10,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "fixture")


if __name__ == "__main__":
    unittest.main()
