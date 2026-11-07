import json
import unittest

from respected_orchestrator.engine import runner, usage_event as ue

META = {"tool": "claude", "run_id": "run-1", "step": "worker", "at": "2026-11-07T12:00:00+00:00"}


class UsageEventTests(unittest.TestCase):
    def test_missing_usage_is_unknown_null_never_zero(self):
        for usage in (None, {}, "junk"):
            e = ue.from_engine_usage(usage, **META)
            self.assertEqual(e["status"], "unknown")
            self.assertTrue(all(e[f] is None for f in ue.COUNTS), e)
            self.assertEqual({e["provenance"][f] for f in ue.COUNTS}, {"absent"})

    def test_engine_dict_normalises_cached_out_of_input(self):
        e = ue.from_engine_usage({"raw_input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 50, "reasoning_tokens": None}, **META)
        self.assertEqual((e["fresh_input_tokens"], e["cache_read_tokens"], e["output_tokens"], e["reasoning_tokens"]), (600, 400, 50, None))
        self.assertEqual((e["status"], e["provenance"]["fresh_input_tokens"], e["provenance"]["reasoning_tokens"]), ("known", "derived", "absent"))

    def test_real_runner_envelope_round_trip(self):
        out = json.dumps({"type": "result", "result": "ok", "usage": {"input_tokens": 10, "cache_creation_input_tokens": 5,
                                                                      "cache_read_input_tokens": 100, "output_tokens": 7}})
        _, usage, _, _ = runner.tool_result("claude", out)
        e = ue.from_engine_usage(usage, **META)
        self.assertEqual((e["fresh_input_tokens"], e["cache_read_tokens"], e["output_tokens"]), (15, 100, 7))

    def test_partial_and_invalid_values(self):
        e = ue.make(counts={"fresh_input_tokens": 5, "output_tokens": -3, "cache_read_tokens": True, "reasoning_tokens": 2.5}, **META)
        self.assertEqual(e["status"], "partial")
        self.assertEqual([e["provenance"][f] for f in ("output_tokens", "cache_read_tokens", "reasoning_tokens")], ["invalid"] * 3)
        self.assertTrue(e["output_tokens"] is None and e["cache_read_tokens"] is None)
        contradictory = ue.from_engine_usage({"raw_input_tokens": 10, "cached_input_tokens": 50, "output_tokens": 1}, **META)
        self.assertIsNone(contradictory["fresh_input_tokens"])
        self.assertEqual(contradictory["provenance"]["fresh_input_tokens"], "invalid")

    def test_chat_adapter_keeps_semantics_unknown_and_ignores_stream_cost(self):
        e = ue.from_chat_event({"kind": "usage", "input": 9, "output": 3, "reasoning": 1, "cache_read": 40, "cache_write": 2, "cost": 0.0, "quota": "unknown"}, **META)
        self.assertEqual((e["cache_semantics"], e["source"], e["fresh_input_tokens"], e["cache_write_tokens"]), ("unknown", "session", 9, 2))
        self.assertNotIn("cost", e)
        self.assertNotIn("quota", e)

    def test_subscription_is_not_cost_eligible(self):
        self.assertTrue(ue.from_engine_usage({}, billing="api_metered", **META)["cost_eligible"])
        self.assertFalse(ue.from_engine_usage({}, billing="subscription", **META)["cost_eligible"])
        self.assertFalse(ue.from_engine_usage({}, **META)["cost_eligible"])  # billing never guessed
        with self.assertRaises(ValueError):
            ue.make(counts={}, billing="free", **META)

    def test_duplicates_do_not_double_count_and_conflicts_are_reported(self):
        a = ue.from_engine_usage({"raw_input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 5}, **META)
        replay = dict(a)
        other = ue.from_engine_usage({"raw_input_tokens": 20, "cached_input_tokens": 0, "output_tokens": 5}, **{**META, "step": "review"})
        t = ue.totals([a, replay, other])
        self.assertEqual((t["events"], t["fields"]["fresh_input_tokens"]["total"], t["fields"]["output_tokens"]["total"]), (2, 30, 10))
        changed = ue.from_engine_usage({"raw_input_tokens": 99, "cached_input_tokens": 0, "output_tokens": 5}, **META)
        t = ue.totals([a, changed])
        self.assertEqual((t["events"], t["conflicts"], t["fields"]["fresh_input_tokens"]["total"]), (1, [a["event_id"]], 10))

    def test_totals_keep_unknown_unknown(self):
        known = ue.from_engine_usage({"raw_input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 5}, **META)
        blank = ue.from_engine_usage(None, **{**META, "step": "review"})
        t = ue.totals([known, blank])
        self.assertEqual(t["status"], "partial")
        self.assertEqual(t["fields"]["output_tokens"], {"total": 5, "events_missing": 1})
        self.assertIsNone(t["fields"]["cache_write_tokens"]["total"])  # nobody reported it: None, not 0
        self.assertEqual(ue.totals([blank])["status"], "unknown")
        self.assertEqual(ue.totals([])["status"], "none")

    def test_model_upgrade_is_visible_per_event(self):
        a = ue.from_engine_usage({}, model="m", model_version="1", **META)
        b = ue.from_engine_usage({}, model="m", model_version="2", **{**META, "step": "r2"})
        self.assertNotEqual((a["model_version"], a["event_id"]), (b["model_version"], b["event_id"]))

    def test_no_free_text_fields(self):
        e = ue.from_engine_usage({"raw_input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1, "prompt": "SECRET"}, **META)
        self.assertNotIn("SECRET", json.dumps(e))


if __name__ == "__main__":
    unittest.main()
