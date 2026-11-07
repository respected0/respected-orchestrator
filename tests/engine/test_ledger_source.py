import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import ledger_source
from respected_orchestrator.engine.evidence import save_signed

AT = "2026-11-07T12:00:00+00:00"
CAT = [{"model": "m", "model_version": "1", "effective_from": "2026-10-01T00:00:00+00:00",
        "input_per_million": 1.0, "output_per_million": 2.0, "currency": "USD", "unit": "token"}]
USAGE = {"raw_input_tokens": 100_000, "cached_input_tokens": 0, "output_tokens": 10_000, "estimated_weighted_tokens": 110_000}


def run(ctx, name, request=None, status="completed", result=None, attempts=None, **extra):
    directory = ctx.data_root / "state" / name
    directory.mkdir(parents=True)
    save_signed(ctx, directory / "request.json", request or {"kind": "write", "worker": "codex"})
    save_signed(ctx, directory / "status.json", {"status": status, "updated_at": AT, **extra})
    if result is not None:
        save_signed(ctx, directory / "result.json", result)
    if attempts is not None:
        save_signed(ctx, directory / "review-attempts.json", {"attempts": attempts})
    return directory


class LedgerSourceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ctx = EngineContext(Path(temp.name).resolve())

    def group(self, **kw):
        return ledger_source.report(self.ctx.data_root, CAT, AT, **kw)["groups"]["write"]

    def test_real_evidence_is_priced_only_when_billing_is_stated(self):
        run(self.ctx, "run-1", result={"duration_seconds": 4.0}, usage=USAGE, model="m")
        run(self.ctx, "run-2", status="failed", reason="scope_violation", usage=USAGE, model="m")
        unstated = self.group()
        self.assertEqual((unstated["runs"], unstated["accepted"], unstated["total_cost"]), (2, 1, None))
        self.assertEqual(unstated["uncomputable"], {"not_api_metered": 2})  # billing is never assumed
        g = self.group(billing={"codex": "api_metered"})
        self.assertEqual((g["total_cost"], g["cost_per_accepted"], g["worker_violations"], g["mean_elapsed_seconds"]), (0.24, 0.24, 1, 4.0))
        self.assertEqual(g["measured"]["fix_rounds"], 0)  # not recorded: reported as unmeasured, not zero

    def test_review_attempts_add_events_and_missing_usage_stays_unknown(self):
        run(self.ctx, "run-1", result={"duration_seconds": 1}, usage=USAGE, model="m",
            attempts=[{"tool": "claude", "profile": "m", "usage": USAGE}, {"tool": "claude", "profile": "m"}])
        g = self.group(billing={"codex": "api_metered", "claude": "api_metered"})
        self.assertIsNone(g["total_cost"])
        self.assertEqual(g["uncomputable"], {"usage_incomplete": 1})
        self.assertEqual(g["known_part"], None)  # the whole run is uncomputable; no partial run cost is invented

    def test_no_catalog_means_uncomputable_not_free(self):
        run(self.ctx, "run-1", result={"duration_seconds": 1}, usage=USAGE, model="m")
        g = ledger_source.report(self.ctx.data_root, [], AT, billing={"codex": "api_metered"})["groups"]["write"]
        self.assertEqual((g["total_cost"], g["uncomputable"]), (None, {"model_unknown": 1}))

    def test_skips_running_custom_unsigned_and_uses_lane_roots(self):
        run(self.ctx, "run-1", status="running")
        run(self.ctx, "run-2", request={"kind": "write", "worker": "custom"})
        bad = run(self.ctx, "run-3")
        (bad / "status.json").write_text('{"status": "completed"}')
        self.assertEqual(ledger_source.runs(self.ctx.data_root), [])
        lane = EngineContext(self.ctx.data_root / "campaigns" / "c1" / "lanes" / "l1")
        run(lane, "run-9", result={"duration_seconds": 2}, usage=USAGE, model="m")
        self.assertEqual([r["run_id"] for r in ledger_source.runs(self.ctx.data_root)], ["run-9"])

    def test_limit(self):
        for i in range(3):
            run(self.ctx, f"run-{i}", usage=USAGE, model="m")
        self.assertEqual(len(ledger_source.runs(self.ctx.data_root, limit=2)), 2)


if __name__ == "__main__":
    unittest.main()


class BenchLinkTests(unittest.TestCase):
    def report(self, **over):
        from tests.workflows.test_routing_confidence import make
        return make(direct_pass=20, orch_pass=27, tokens=None, **over)

    def test_arms_become_task_classes_with_the_reports_provenance(self):
        rows = ledger_source.from_bench(self.report())
        self.assertEqual(len(rows), 60)
        self.assertEqual({r["task_class"] for r in rows}, {"bench:direct", "bench:orchestrated"})
        self.assertEqual({r["eval"]["kind"] for r in rows}, {"real"})
        self.assertEqual(rows[0]["eval"]["manifest"], "claude@1:abc123")
        snap = ledger_source.cost_ledger.snapshot([], "2026-11-08T00:00:00+00:00")
        rep = ledger_source.cost_ledger.report(rows, snap)
        direct, orch = rep["groups"]["bench:direct"], rep["groups"]["bench:orchestrated"]
        self.assertEqual((direct["acceptance_rate"], orch["acceptance_rate"], direct["evidence"], orch["evidence"]), (0.6667, 0.9, "real", "real"))
        self.assertEqual((direct["total_cost"], orch["total_cost"]), (None, None))  # a benchmark has no input/output split: cost is unknown, never zero
        self.assertEqual(orch["uncomputable"], {"not_api_metered": 30})
        self.assertEqual((orch["worker_violations"], direct["worker_violations"]), (0, None))  # direct arm violations are not measured

    def test_synthetic_and_invalid_reports(self):
        rows = ledger_source.from_bench(self.report(kind="harness-test"))
        self.assertEqual({r["eval"]["kind"] for r in rows}, {"synthetic"})
        for bad in (None, {}, {"schema": "respected.eval.compare.v1", "runs": []}, {"schema": "respected.eval.bench.v1", "runs": "x"}):
            with self.assertRaises(ValueError):
                ledger_source.from_bench(bad)
        self.assertEqual(ledger_source.from_bench({"schema": "respected.eval.bench.v1", "runs": [{"arm": "weird"}, "x"]}), [])

    def test_violations_count_only_for_the_orchestrated_arm(self):
        rows = ledger_source.from_bench(self.report(violations=2))
        orch = [r for r in rows if r["task_class"] == "bench:orchestrated"]
        self.assertEqual(sum(r["worker_violations"] for r in orch), 2)
