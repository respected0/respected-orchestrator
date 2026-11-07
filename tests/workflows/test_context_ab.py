import subprocess
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.workflows import context_ab as ab
from tests.workflows.test_routing_confidence import make


def report(orch_pass=27, tokens=1000, **over):
    return make(direct_pass=20, orch_pass=orch_pass, tokens=tokens, context_prep=False, **over)


def prep(orch_pass=27, tokens=600, **over):
    return make(direct_pass=20, orch_pass=orch_pass, tokens=tokens, context_prep=True, **over)


class ShadowTests(unittest.TestCase):
    def test_prompt_size_only_and_claims_nothing(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name).resolve()
        for args in [("init", "-b", "main"), ("config", "user.name", "F"), ("config", "user.email", "f@example.invalid")]:
            subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)
        (repo / "src").mkdir()
        (repo / "src" / "target.py").write_text("def parse_config():\n    return 1\n" + "# filler\n" * 400, encoding="utf-8")
        for i in range(10):
            (repo / "src" / f"other_{i}.py").write_text(f"def helper_{i}():\n    return {i}\n" + "# filler\n" * 400, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "c"], cwd=repo, capture_output=True, check=True)
        out = ab.shadow_sizes(repo, [{"id": "T1", "task": "fix parse config", "allowed": ["src"]}, {"id": "T2", "task": "zzz nothing", "allowed": ["src"]}])
        self.assertEqual(out["kind"], "prompt_size_only")
        self.assertIn("no agent was called", out["claims"])
        first, second = out["tasks"]
        self.assertGreater(first["saved_fraction"], 0.8)
        self.assertEqual(second["prepared_tokens"], 0)
        empty = ab.shadow_sizes(repo, [{"id": "T3", "task": "x", "allowed": ["nothing-here"]}])
        self.assertIsNone(empty["tasks"][0]["saved_fraction"])  # no baseline to compare with: no number
        self.assertIsNone(empty["mean_saved_fraction"])


class CompareTests(unittest.TestCase):
    def test_a_real_saving_is_claimed_only_when_everything_holds(self):
        out = ab.compare(report(tokens=1000), prep(tokens=600))
        self.assertEqual((out["claim"], out["mode"], out["tokens"]["saved_fraction"]), ("token_saving", "eligible_for_opt_in", 0.4))

    def test_no_claim_cases(self):
        cases = {
            "unknown tokens": (report(tokens=None), prep(tokens=600), "token counts are not known"),
            "zero is not a measurement": (report(tokens=0), prep(tokens=600), "unmeasured value written as 0"),
            "no saving": (report(tokens=1000), prep(tokens=1000), "did not use fewer tokens"),
            "more tokens": (report(tokens=1000), prep(tokens=1400), "did not use fewer tokens"),
            "security regression": (report(tokens=1000), prep(tokens=600, violations=1), "security violations"),
            "success dropped": (report(orch_pass=29, tokens=1000), prep(orch_pass=10, tokens=600), "succeeds detectably less"),
            "different agent version": (report(), prep(version="2"), "agent differs"),
            "different tasks": (report(), prep(tasks=11), "task_ids differs"),
            "different timeout": (report(), prep(timeout=60.0), "timeout differs"),
        }
        for name, (base, other, text) in cases.items():
            out = ab.compare(base, other)
            self.assertEqual(out["claim"], "no_claim", name)
            self.assertEqual(out["mode"], "shadow", name)
            self.assertTrue(any(text in r for r in out["reasons"]), (name, out["reasons"]))

    def test_unusable_reports_and_small_samples(self):
        self.assertTrue(any("baseline: not a real-agent report" in r for r in ab.compare(report(kind="harness-test"), prep())["reasons"]))
        self.assertTrue(any("prepared: status is" in r for r in ab.compare(report(), prep(status="stopped_quota"))["reasons"]))
        self.assertEqual(ab.compare(None, None)["claim"], "no_claim")

    def test_the_arms_must_be_labelled_correctly(self):
        for base, prepared in ((prep(tokens=1000), prep(tokens=600)), (report(tokens=1000), report(tokens=600))):
            out = ab.compare(base, prepared)
            self.assertEqual(out["claim"], "no_claim")
            self.assertTrue(any("context_prep: true" in r for r in out["reasons"]))

    def test_manifest_records_the_conclusion(self):
        base, prepared = report(tokens=1000), prep(tokens=600)
        m = ab.manifest(base, prepared, ab.compare(base, prepared))
        self.assertEqual((m["schema"], m["verdict"], m["tokens"]["saved_fraction"]), ("respected.eval.contextab.v1", "token_saving", 0.4))
        no = ab.manifest(base, prep(tokens=None), ab.compare(base, prep(tokens=None)))
        self.assertEqual((no["verdict"], no["mode"]), ("no_claim", "shadow"))


if __name__ == "__main__":
    unittest.main()
