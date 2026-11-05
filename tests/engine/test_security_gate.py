"""SEC-04 gate: the adversarial registry cannot silently shrink and CI must run each boundary separately."""

from pathlib import Path
import unittest

from tests.tools.run_security_ci import EXCLUDED, validate_manifest

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

    def test_ci_runs_the_security_set_as_a_standard_user_and_gates_on_the_manifest(self):
        workflow = CI.read_text(encoding="utf-8")
        security = workflow[workflow.index("Security matrix"):workflow.index("Unit, integration")]
        for command in ("tests/tools/run_security_as_user.ps1", "python tests/tools/run_security_ci.py verify security-manifest.json",
                        "python tests/tools/run_ci.py"):
            with self.subTest(command=command):
                self.assertIn(command, workflow)
        self.assertNotIn("ORCH_ALLOW_ELEVATED_SKIP", security)
        self.assertNotIn("continue-on-error", workflow)
        self.assertIn("security-manifest.json", workflow[workflow.index("upload-artifact"):])

    def test_no_security_test_can_skip_itself_in_an_elevated_session(self):
        for name in ("tests/engine/test_worker_security.py", "tests/packaging/test_frozen_security.py", "tests/engine/test_sandbox.py"):
            self.assertNotIn("ORCH_ALLOW_ELEVATED_SKIP", (ROOT / name).read_text(encoding="utf-8"), name)

    def test_gate_is_red_for_every_forged_or_degraded_manifest(self):
        good = {"commit_sha": "abc", "runner": "x", "elevated": False, "expected": 30, "tests": 30, "passed": 30, "failed": 0,
                "errors": 0, "skipped": 0, "excluded": EXCLUDED}
        self.assertEqual(validate_manifest(good, "abc"), [])
        bad = {"skipped": dict(good, skipped=1, passed=29), "failed": dict(good, failed=1, passed=29),
               "error": dict(good, errors=1, passed=29), "missing tests": dict(good, expected=40),
               "too few tests": dict(good, expected=3, tests=3, passed=3), "elevated": dict(good, elevated=True),
               "elevation unknown": {k: v for k, v in good.items() if k != "elevated"}, "other sha": dict(good, commit_sha="old"),
               "empty": {}, "not an object": [], "excluded changed": dict(good, excluded={})}
        for label, manifest in bad.items():
            with self.subTest(label):
                self.assertTrue(validate_manifest(manifest, "abc"), label)
        self.assertTrue(validate_manifest(good, ""), "no expected SHA must stay red")

    def test_an_elevated_run_is_red_even_when_no_test_ran(self):
        self.assertEqual(validate_manifest({"commit_sha": "a", "elevated": True, "expected": 30, "tests": 0, "passed": 0,
                                            "failed": 0, "errors": 0, "skipped": 0, "excluded": EXCLUDED}, "a")[0][:7], "the run")


if __name__ == "__main__":
    unittest.main()
