"""SEC-04 gate: the adversarial registry cannot silently shrink and CI must run each boundary separately."""

from pathlib import Path
import unittest

from tests.engine.security_cases import (
    ALLOWED_CASES,
    EXTERNAL_NEGATIVE_CASES,
    NEGATIVE_CASES,
    NEGATIVE_CATEGORIES,
    PROBE_NEGATIVE_CASES,
    REQUIRED_CATEGORIES,
)


ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"


class SecurityRegistryGateTest(unittest.TestCase):
    def test_registry_meets_the_security_minimum_and_is_unique(self):
        self.assertGreaterEqual(len(NEGATIVE_CASES), 15)
        self.assertGreaterEqual(len(ALLOWED_CASES), 5)
        for values in (NEGATIVE_CASES, ALLOWED_CASES):
            self.assertEqual(len(values), len(set(values)), values)

    def test_every_required_attack_category_is_registered(self):
        categories = set(NEGATIVE_CATEGORIES.values())
        self.assertTrue(REQUIRED_CATEGORIES <= categories, REQUIRED_CATEGORIES - categories)

    def test_probe_and_external_cases_form_the_complete_partition(self):
        self.assertEqual(
            set(PROBE_NEGATIVE_CASES) | set(EXTERNAL_NEGATIVE_CASES),
            set(NEGATIVE_CASES),
        )
        self.assertFalse(set(PROBE_NEGATIVE_CASES) & set(EXTERNAL_NEGATIVE_CASES))
        self.assertEqual(set(EXTERNAL_NEGATIVE_CASES), {"symlink_patch", "recursive_mcp"})

    def test_ci_runs_worker_and_verify_matrices_as_separate_required_steps(self):
        workflow = CI.read_text(encoding="utf-8")
        required = (
            "python -m unittest tests.engine.test_worker_security -v",
            "python -m unittest tests.engine.test_sandbox -v",
            "python -m unittest tests.engine.test_security_gate -v",
            "python -m unittest tests.packaging.test_frozen_security -v",
            "python tests/tools/run_ci.py",
        )
        for command in required:
            with self.subTest(command=command):
                self.assertIn(command, workflow)
        self.assertNotIn("continue-on-error", workflow)


if __name__ == "__main__":
    unittest.main()
