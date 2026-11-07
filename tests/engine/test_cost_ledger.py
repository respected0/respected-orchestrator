import unittest

from respected_orchestrator.engine import cost_ledger as cl, usage_event as ue

AT = "2026-11-07T12:00:00+00:00"
CAT = [{"model": "m", "model_version": "1", "effective_from": "2026-10-01T00:00:00+00:00",
        "input_per_million": 1.0, "output_per_million": 2.0, "currency": "USD", "unit": "token"},
       {"model": "eur", "model_version": "1", "effective_from": "2026-10-01T00:00:00+00:00",
        "input_per_million": 1.0, "output_per_million": 2.0, "currency": "EUR", "unit": "token"},
       {"model": "old", "model_version": "1", "effective_from": "2025-01-01T00:00:00+00:00",
        "input_per_million": 1.0, "output_per_million": 2.0, "currency": "USD", "unit": "token"}]
SNAP = cl.snapshot(CAT, AT)


def ev(step="w", model="m", fresh=100_000, out=10_000, cache=0, billing="api_metered", run="r1", at=AT):
    raw = {"raw_input_tokens": fresh + cache, "cached_input_tokens": cache, "output_tokens": out}
    return ue.from_engine_usage(raw, tool="codex", run_id=run, step=step, at=at, model=model, billing=billing)


def run(rid="r1", accepted=True, events=None, **kw):
    base = dict(run_id=rid, task_class="bugfix", accepted=accepted, elapsed_seconds=10.0, fix_rounds=1, worker_violations=0,
                events=[ev(run=rid)] if events is None else events)
    return cl.run_record(**{**base, **kw})


class LedgerTests(unittest.TestCase):
    def group(self, runs, **kw):
        return cl.report(runs, SNAP, **kw)["groups"]["bugfix"]

    def test_golden_numbers_recompute(self):
        # 100k in * $1/M + 10k out * $2/M = 0.12 per run; 2 runs, 1 accepted -> all spend counts
        g = self.group([run("a"), run("b", accepted=False)])
        self.assertEqual((g["total_cost"], g["currency"], g["accepted"], g["cost_per_accepted"]), (0.24, "USD", 1, 0.24))
        self.assertEqual((g["acceptance_rate"], g["mean_elapsed_seconds"], g["worker_violations"], g["upper_bound"]), (0.5, 10.0, 0, False))

    def test_deterministic_and_snapshot_frozen(self):
        a, b = cl.report([run()], SNAP), cl.report([run()], cl.snapshot(reversed(CAT), AT))
        self.assertEqual(a, b)
        newer = cl.snapshot([{**CAT[0], "input_per_million": 5.0}, *CAT[1:]], AT)
        self.assertNotEqual(cl.report([run()], newer)["digest"], a["digest"])

    def test_unknown_never_zero(self):
        for events, reason in [([ue.from_engine_usage(None, tool="x", run_id="r1", step="w", at=AT, model="m", billing="api_metered")], "usage_incomplete"),
                               ([ev(billing="subscription")], "not_api_metered"), ([ev(billing="unknown")], "not_api_metered"),
                               ([ev(model="nope")], "model_unknown"), ([ev(model=None)], "model_unknown"), ([], "no_usage_events")]:
            g = self.group([run(events=events)])
            self.assertIsNone(g["total_cost"], reason)
            self.assertIsNone(g["cost_per_accepted"])
            self.assertEqual(g["uncomputable"], {reason: 1})

    def test_partial_cost_is_split_from_total(self):
        g = self.group([run("a"), run("b", events=[ev(model="nope", run="b")])])
        self.assertEqual((g["total_cost"], g["known_part"], g["cost_per_accepted_reason"]), (None, 0.12, "cost_not_computable"))

    def test_currency_mismatch_and_stale_price(self):
        g = self.group([run("a"), run("b", events=[ev(model="eur", run="b")])])
        self.assertEqual((g["total_cost"], g["known_part"]), (None, None))
        self.assertIn("currency_mismatch", g["uncomputable"])
        self.assertEqual(self.group([run(events=[ev(model="old")])])["uncomputable"], {"price_stale": 1})

    def test_negative_token_is_invalid_not_priced(self):
        bad = ue.from_engine_usage({"raw_input_tokens": 10, "cached_input_tokens": 0, "output_tokens": -5}, tool="x", run_id="r1",
                                   step="w", at=AT, model="m", billing="api_metered")
        self.assertEqual(self.group([run(events=[bad])])["uncomputable"], {"usage_incomplete": 1})

    def test_cache_makes_an_upper_bound(self):
        g = self.group([run(events=[ev(cache=50_000)])])
        self.assertEqual((g["total_cost"], g["upper_bound"]), (0.17, True))  # cached read priced at the full input rate

    def test_usage_correction_replaces_and_replay_does_not_double_count(self):
        first = ev(step="w")
        replay = dict(first)
        fix = {**ev(step="w-fix", out=20_000), "corrects": first["event_id"]}
        self.assertEqual(self.group([run(events=[first, replay])])["total_cost"], 0.12)
        self.assertEqual(self.group([run(events=[first, fix])])["total_cost"], 0.14)
        conflicting = ev(step="w", out=99)
        self.assertEqual(self.group([run(events=[first, conflicting])])["uncomputable"], {"conflicting_duplicate_events": 1})

    def test_missing_sample_and_unmeasured_quality(self):
        g = self.group([run(accepted=False, elapsed_seconds=None, fix_rounds=None, worker_violations=None)])
        self.assertEqual((g["cost_per_accepted"], g["cost_per_accepted_reason"], g["total_cost"]), (None, "no_accepted_runs", 0.12))
        self.assertEqual((g["mean_elapsed_seconds"], g["mean_fix_rounds"], g["worker_violations"]), (None, None, None))
        self.assertEqual(g["measured"], {"elapsed": 0, "fix_rounds": 0, "violations": 0})

    def test_task_class_filter_and_evidence_label(self):
        other = cl.run_record(run_id="z", task_class="docs", accepted=True, elapsed_seconds=1, fix_rounds=0, worker_violations=0,
                              events=[], eval_kind="real", eval_manifest="m1")
        rep = cl.report([run(), other], SNAP)
        self.assertEqual(sorted(rep["groups"]), ["bugfix", "docs"])
        self.assertEqual((rep["groups"]["bugfix"]["evidence"], rep["groups"]["docs"]["evidence"]), ("none", "real"))
        self.assertEqual(sorted(cl.report([run(), other], SNAP, task_class="docs")["groups"]), ["docs"])
        with self.assertRaises(ValueError):
            cl.run_record(run_id="q", task_class="c", accepted=True, elapsed_seconds=1, fix_rounds=0, worker_violations=0, events=[], eval_kind="fake")

    def test_diff(self):
        before = cl.report([run("a"), run("b", accepted=False)], SNAP)
        after = cl.report([run("a"), run("b")], SNAP)
        d = cl.diff(before, after)["bugfix"]
        self.assertEqual((d["acceptance_rate_delta"], d["cost_per_accepted_delta"], d["worker_violations_delta"]), (0.5, -0.12, 0))
        unknown = cl.report([run("a", events=[ev(model="nope")])], SNAP)
        self.assertEqual(cl.diff(before, unknown)["bugfix"]["cost_reason"], "cost_not_comparable")
        moved = cl.report([run("a")], cl.snapshot([{**CAT[0], "input_per_million": 2.0}, *CAT[1:]], AT))
        self.assertEqual(cl.diff(after, moved)["bugfix"]["cost_reason"], "price_snapshot_differs")
        self.assertEqual(cl.diff(before, cl.report([], SNAP))["bugfix"]["status"], "only_in_before")


if __name__ == "__main__":
    unittest.main()
