import unittest

from tests.evals import compare
from tests.evals.fixtures import all_fixtures


class CompareTests(unittest.TestCase):
    def test_direct_and_orchestrated_are_independent(self):
        report = compare.compare(list(all_fixtures())[:2], repeat=1)
        self.assertEqual(report["summary"]["direct"]["success_rate"], 0.0)
        self.assertEqual(report["summary"]["orchestrated"]["success_rate"], 1.0)
        self.assertEqual(report["summary"]["direct"]["security_violations"], 0)
        self.assertEqual(report["summary"]["orchestrated"]["security_violations"], 0)

    def test_metadata_is_complete(self):
        report = compare.compare(list(all_fixtures())[:1], repeat=1)
        for key in ("python", "platform", "git", "timestamp_utc", "model"):
            self.assertTrue(report["metadata"].get(key))

    def test_unknown_cost_stays_unknown(self):
        report = compare.compare(list(all_fixtures())[:1], repeat=1)
        self.assertEqual(report["summary"]["direct"]["cost"], "bilinmiyor")
        self.assertNotEqual(report["summary"]["direct"]["cost"], 0)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            compare.evaluate_task(all_fixtures()[0], "self-approved")


if __name__ == "__main__":
    unittest.main()