"""Acceptance tests for the EVAL-01 reproducible evaluation runner."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.evals import fixtures
from tests.evals.runner import (
    evaluate_fixture,
    run_all,
    validate_fixture,
    write_report,
)


class FixtureContractTest(unittest.TestCase):
    def test_twenty_fixtures_have_fixed_sha_and_acceptance_test(self):
        cases = fixtures.all_fixtures()
        self.assertEqual(len(cases), 20)
        self.assertEqual(len({case.id for case in cases}), 20)
        for case in cases:
            self.assertEqual(validate_fixture(case), [], case.id)
            self.assertRegex(case.start_sha, r"^[0-9a-f]{40}$")
            self.assertIn("unittest", case.test)
            self.assertNotEqual(case.source, case.fixed_source)

    def test_all_buggy_baselines_fail_and_golden_solutions_pass(self):
        report = run_all(repeat=1, timeout=20)
        self.assertEqual(report["summary"], {
            "total": 20, "passed": 20, "failed": 0, "rejected": 0,
        })
        for task in report["tasks"]:
            run = task["runs"][0]
            self.assertTrue(run["start_sha_matches"], task["task_id"])
            self.assertEqual(run["baseline_status"], "expected_failure", task["task_id"])
            self.assertEqual(run["golden_status"], "expected_pass", task["task_id"])
            self.assertEqual(run["cost"], "bilinmiyor")
            self.assertRegex(run["result_hash"], r"^[0-9a-f]{64}$")

    def test_three_repeats_keep_sha_and_record_metadata(self):
        result = evaluate_fixture(fixtures.by_id("RSP-001"), repeat=3, timeout=20)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["runs"]), 3)
        self.assertEqual({run["start_sha"] for run in result["runs"]}, {fixtures.by_id("RSP-001").start_sha})
        for index, run in enumerate(result["runs"], 1):
            self.assertEqual(run["run"], index)
            for key in ("start_sha", "baseline", "golden", "result_hash", "cost", "baseline_status", "golden_status"):
                self.assertIn(key, run)

    def test_invalid_fixtures_are_rejected_deterministically_twenty_times(self):
        base = fixtures.by_id("RSP-001")
        invalid = [
            replace(base, id=""),
            replace(base, id="RSP-1"),
            replace(base, id="rsp-001"),
            replace(base, title=""),
            replace(base, title="   "),
            replace(base, source=""),
            replace(base, source="   "),
            replace(base, fixed_source=""),
            replace(base, test=""),
            replace(base, test="print('not a test')"),
            replace(base, source=base.fixed_source),
            replace(base, source="x = 1\n"),
            replace(base, fixed_source="x = 1\n"),
            replace(base, start_sha=""),
            replace(base, start_sha="abc"),
            replace(base, start_sha="g" * 40),
            replace(base, start_sha="A" * 40),
            replace(base, id=None),
            replace(base, test=None),
            replace(base, title=None),
        ]
        self.assertEqual(len(invalid), 20)
        for case in invalid:
            first = validate_fixture(case)
            second = validate_fixture(case)
            self.assertTrue(first, case)
            self.assertEqual(first, second, case)
            result = evaluate_fixture(case, repeat=1, timeout=5)
            self.assertEqual(result["status"], "rejected")
            self.assertEqual(result["errors"], first)

    def test_timeout_is_recorded_without_a_false_pass(self):
        slow = replace(
            fixtures.by_id("RSP-001"),
            test="""import time
import unittest

class TestSlow(unittest.TestCase):
    def test_slow(self):
        time.sleep(2)
""",
        )
        result = evaluate_fixture(slow, repeat=1, timeout=0.2)
        self.assertEqual(result["status"], "failed")
        run = result["runs"][0]
        self.assertEqual(run["baseline_status"], "timeout")
        self.assertEqual(run["golden_status"], "timeout")
        self.assertTrue(run["baseline"]["timeout"])

    def test_report_schema_and_product_data_guard(self):
        result = run_all(repeat=1, timeout=20, fixtures=[fixtures.by_id("RSP-001")])
        self.assertEqual(result["schema"], "respected.eval.v1")
        self.assertEqual(result["summary"], {"total": 1, "passed": 1, "failed": 0, "rejected": 0})
        self.assertIn("timestamp_utc", result["metadata"])
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "report.json"
            write_report(result, destination)
            loaded = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "respected.eval.v1")
            data_root = Path(temporary) / "data"
            data_root.mkdir()
            with mock.patch.dict(os.environ, {"RESPECTED_DATA_DIR": str(data_root)}):
                with self.assertRaises(ValueError):
                    write_report(result, data_root / "evidence" / "report.json")


if __name__ == "__main__":
    unittest.main()