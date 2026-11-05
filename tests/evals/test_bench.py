import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.evals import bench, compare
from tests.evals.fixtures import all_fixtures

STUB = """import json, sys
from pathlib import Path
KNOWN = json.loads(Path(__file__).with_name("knowledge.json").read_text("utf-8"))
if KNOWN["quota"]:
    print("HTTP 429 rate limit exceeded")
    sys.exit(1)
current = Path("solution.py").read_text("utf-8")
for pair in KNOWN["pairs"]:
    if KNOWN["skill"] and current == pair["buggy"]:
        Path("solution.py").write_text(pair["fixed"], "utf-8")
"""


def stub_agent(directory, fixtures, *, skill=True, quota=False):
    """A fake model: its 'knowledge' sits in a file outside the work tree; the harness never hands it the golden source."""
    directory = Path(directory)
    (directory / "stub_agent.py").write_text(STUB, encoding="utf-8")
    pairs = [{"buggy": f.source, "fixed": f.fixed_source} for f in fixtures]
    (directory / "knowledge.json").write_text(json.dumps({"pairs": pairs, "skill": skill, "quota": quota}), encoding="utf-8")
    argv = lambda prompt: [sys.executable, str(directory / "stub_agent.py"), prompt]
    return bench.Agent("stub", "stub-1", "1.0", argv, worker="custom", orchestrated=argv)


class BenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixtures = list(all_fixtures())[:2]
        env = mock.patch.dict(os.environ, {"RESPECTED_WORKER_READONLY_ROOTS": str(Path(self.tmp.name).resolve())})
        env.start()
        self.addCleanup(env.stop)

    def run_stub(self, **options):
        agent = stub_agent(self.tmp.name, self.fixtures, **options)
        return bench.run_bench(agent, self.fixtures, 1, 120, release=False, commit="abc")

    def test_release_plan_needs_ten_tasks_three_repeats_two_arms(self):
        tasks = bench.select_tasks(10)
        plan = bench.make_plan(tasks, 3)
        self.assertEqual((len(tasks), plan["total_runs"]), (10, 60))
        with self.assertRaises(bench.BenchError):
            bench.make_plan(tasks[:9], 3)
        with self.assertRaises(bench.BenchError):
            bench.make_plan(tasks, 2)

    def test_both_arms_run_an_agent_process_and_only_hidden_acceptance_decides(self):
        report = self.run_stub()
        self.assertEqual(report["kind"], "harness-test")
        self.assertEqual([(r["arm"], r["status"]) for r in report["runs"]], [("direct", "passed"), ("orchestrated", "passed")] * 2, report["runs"])
        self.assertFalse(report["golden_used"])
        self.assertEqual(report["summary"]["direct"]["tokens"], "unknown")
        self.assertEqual(report["summary"]["direct"]["security_violations"], "unknown")
        self.assertEqual(report["summary"]["orchestrated"]["security_violations"], 0)
        self.assertEqual(bench.validate(report, release=False), [])

    def test_an_agent_that_cannot_solve_the_task_fails_in_both_arms(self):
        report = self.run_stub(skill=False)
        self.assertEqual({r["status"] for r in report["runs"]}, {"failed"})
        self.assertEqual(report["summary"]["direct"]["success_rate"], 0.0)

    def test_golden_in_argv_invalidates_the_run_without_executing_the_agent(self):
        golden = self.fixtures[0].fixed_source
        leaky = bench.Agent("leaky", "m", "1", lambda p: [sys.executable, "-c", "print(1)", golden],
                            orchestrated=lambda p: [sys.executable, "-c", golden])
        results = [run(leaky, self.fixtures[0], 1, 60) for run in (bench.run_direct, bench.run_orchestrated)]
        for result in results:
            self.assertEqual((result["status"], result["reason"]), ("invalid", "golden_leak"))
        report = bench.report(leaky, self.fixtures[:1], 1, 60, results, "complete", "abc")
        self.assertIn("golden fix reached an agent or a run is invalid", bench.validate(report, release=False))

    def test_a_quota_signal_stops_the_batch_after_the_first_run(self):
        report = self.run_stub(quota=True)
        self.assertEqual((report["status"], len(report["runs"])), ("stopped_quota", 1))
        self.assertTrue(bench.validate(report, release=False))

    def test_unmeasured_values_are_unknown_never_zero_and_conflicting_usage_is_unknown(self):
        self.assertEqual(bench.parse_claude_usage("not json"), {"tokens": "unknown", "cost": "unknown"})
        usage = {"m": {"inputTokens": 10, "outputTokens": 5}}
        zero = json.dumps({"modelUsage": usage, "usage": {"input_tokens": 0, "output_tokens": 0}})
        self.assertEqual(bench.parse_claude_usage(zero)["tokens"], 15)
        clash = json.dumps({"modelUsage": usage, "usage": {"input_tokens": 99, "output_tokens": 1}})
        self.assertEqual(bench.parse_claude_usage(clash)["tokens"], "unknown")
        report = self.run_stub()
        report["runs"][0]["cost"] = 0
        self.assertIn("unmeasured value written as 0", bench.validate(report, release=False))

    def test_different_model_version_or_timeout_is_incomparable(self):
        first = self.run_stub()
        self.assertEqual(bench.comparable(first, first), "comparable")
        self.assertEqual(bench.comparable(first, dict(first, agent=dict(first["agent"], model="other"))), "incomparable:agent")
        self.assertEqual(bench.comparable(first, dict(first, timeout=1)), "incomparable:timeout")

    def test_release_validation_rejects_a_harness_test_report(self):
        self.assertIn("not a real-agent report", bench.validate(self.run_stub()))

    def test_a_missing_cli_is_provider_missing_and_the_free_confirmation_is_required(self):
        with self.assertRaises(bench.BenchError) as raised:
            bench.real_agent("claude", "m")
        self.assertIn("not_confirmed_free", str(raised.exception))
        with mock.patch("respected_orchestrator.engine.clis.find", return_value={"claude": None}):
            with self.assertRaises(bench.ProviderMissing):
                bench.real_agent("claude", "m", confirm_free=True)

    def test_the_synthetic_harness_is_labelled_synthetic(self):
        self.assertEqual(compare.compare(self.fixtures[:1], repeat=1)["kind"], "synthetic")


if __name__ == "__main__":
    unittest.main()
