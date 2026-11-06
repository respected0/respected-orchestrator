import re
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "THREAT_MODEL.md"


class DesktopThreatModelTest(unittest.TestCase):
    def rows(self):
        text = DOC.read_text(encoding="utf-8")
        return [line for line in text.splitlines() if re.match(r"\| D-\d{2} \|", line)]

    def test_at_least_twelve_scenarios_each_with_owner_layer_and_test_plan(self):
        rows = self.rows()
        self.assertGreaterEqual(len(rows), 12)
        for row in rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            self.assertEqual(len(cells), 7, row)
            self.assertTrue(all(cells), row)
            self.assertTrue(re.search(r"B3-\d{2}\.\d{2}", cells[6]), row)

    def test_no_desktop_row_claims_protection_before_a_test_exists(self):
        for row in self.rows():
            self.assertIn("Planlı", row)
            self.assertNotIn("Engellenir", row)

    def test_renderer_approval_forgery_is_covered(self):
        self.assertTrue(any("Renderer'dan `approve`" in r for r in self.rows()))


if __name__ == "__main__":
    unittest.main()
