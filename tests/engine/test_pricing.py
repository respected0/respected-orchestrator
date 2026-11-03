import unittest

from respected_orchestrator.engine import pricing

CATALOG = [
    {"model": "m1", "model_version": "v1", "effective_from": "2026-01-01", "currency": "USD",
     "unit": "per_million_tokens", "input_per_million": 2.0, "output_per_million": 8.0},
    {"model": "m1", "model_version": "v2", "effective_from": "2026-06-01", "currency": "USD",
     "unit": "per_million_tokens", "input_per_million": 3.0, "output_per_million": 12.0},
]


class PricingTests(unittest.TestCase):
    def test_unknown_model_is_never_zero(self):
        quoted = pricing.quote(CATALOG, "missing", 10, 10, at="2026-07-01")
        self.assertEqual(quoted["status"], "unknown")
        self.assertIsNone(quoted["amount"])
        self.assertEqual(quoted["reason"], "model_unknown")
        self.assertEqual(pricing.display(quoted), "unknown")

    def test_price_change_selects_version_by_timestamp(self):
        before = pricing.quote(CATALOG, "m1", 1_000_000, 0, at="2026-05-31")
        after = pricing.quote(CATALOG, "m1", 1_000_000, 0, at="2026-06-01")
        self.assertEqual((before["amount"], before["model_version"]), (2.0, "v1"))
        self.assertEqual((after["amount"], after["model_version"]), (3.0, "v2"))

    def test_input_and_output_prices_are_separate(self):
        quoted = pricing.quote(CATALOG, "m1", 1_000_000, 500_000, at="2026-07-01")
        self.assertEqual(quoted["amount"], 9.0)
        self.assertEqual(quoted["currency"], "USD")
        self.assertEqual(quoted["at"], "2026-07-01")
        self.assertEqual(quoted["model_version"], "v2")

    def test_missing_usage_is_unknown_not_zero(self):
        quoted = pricing.quote(CATALOG, "m1", None, 5, at="2026-07-01")
        self.assertEqual(quoted["status"], "unknown")
        self.assertIsNone(quoted["amount"])
        self.assertEqual(quoted["reason"], "usage_unknown")

    def test_provider_downtime_has_no_fallback(self):
        quoted = pricing.quote(CATALOG, "m1", 10, 10, at="2026-07-01", provider_available=False)
        self.assertEqual(quoted["status"], "unknown")
        self.assertEqual(quoted["reason"], "provider_unavailable")

    def test_quotes_are_deterministic_and_carry_versions(self):
        first = pricing.quote(CATALOG, "m1", 10, 10, at="2026-07-01", observed_tokens=20)
        self.assertEqual(first, pricing.quote(CATALOG, "m1", 10, 10, at="2026-07-01", observed_tokens=20))
        self.assertEqual((first["model_version"], first["effective_from"], first["at"]),
                         ("v2", "2026-06-01", "2026-07-01"))
        self.assertEqual(first["confidence"], "observed")


if __name__ == "__main__":
    unittest.main()
