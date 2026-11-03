import unittest

from tests.evals import report as report_mod

BASE = {
    "schema": "respected.eval.compare.v1",
    "fixture_ids": ["RSP-001", "RSP-002"],
    "repeat": 3,
    "timeout": 20.0,
    "summary": {"orchestrated": {"success_rate": 0.8, "security_violations": 0, "cost": "bilinmiyor", "duration_seconds": 4.2}},
}


def make(success=0.8, violations=0, ids=("RSP-001", "RSP-002"), repeat=3):
    value = {**BASE, "fixture_ids": list(ids), "repeat": repeat, "summary": {"orchestrated": {
        "success_rate": success, "security_violations": violations, "cost": "bilinmiyor", "duration_seconds": 4.2}}}
    return value


class ReportTests(unittest.TestCase):
    def test_four_required_kpis(self):
        self.assertEqual(tuple(report_mod.kpis(BASE)), report_mod.REQUIRED_KPIS)

    def test_missing_data_raises_instead_of_zero(self):
        broken = make()
        broken["summary"]["orchestrated"].pop("cost")
        with self.assertRaises(ValueError):
            report_mod.kpis(broken)

    def test_regression_detected_in_two_runs(self):
        gate = report_mod.regression_gate(make(success=0.9, violations=0), make(success=0.8, violations=1))
        self.assertFalse(gate["ok"])
        self.assertIn("acceptance_success_rate", gate["regressions"])
        self.assertIn("worker_violations", gate["regressions"])

    def test_incomparable_reports_rejected(self):
        with self.assertRaises(ValueError):
            report_mod.regression_gate(make(), make(ids=("RSP-001",)))
        with self.assertRaises(ValueError):
            report_mod.regression_gate(make(), make(repeat=2))

    def test_markdown_contains_kpis(self):
        text = report_mod.render_markdown(BASE)
        for label in ("Kabul başarısı", "Worker ihlali", "Maliyet", "Süre"):
            self.assertIn(label, text)


if __name__ == "__main__":
    unittest.main()