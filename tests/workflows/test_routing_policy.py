import unittest

from respected_orchestrator.workflows.routing_policy import suggest

AT = "2026-11-07T12:00:00+00:00"
CATALOG = [{"model": "m-cheap", "model_version": "1", "effective_from": "2026-01-01T00:00:00+00:00",
            "input_per_million": 1.0, "output_per_million": 2.0, "currency": "USD", "unit": "token"},
           {"model": "m-dear", "model_version": "1", "effective_from": "2026-01-01T00:00:00+00:00",
            "input_per_million": 10.0, "output_per_million": 20.0, "currency": "USD", "unit": "token"}]
USAGE = {"input": 100_000, "output": 10_000}
LOW, HIGH = {"level": "low"}, {"level": "high"}


def cand(tool="codex", profile="a", **over):
    return {"tool": tool, "profile": profile, "available": True, "quota": "ok", **over}


def hist(rows):
    return lambda: {("write", t, p): {"runs": r, "ok": o, "avg_tokens": None, "avg_seconds": None} for (t, p), (r, o) in rows.items()}


class RoutingTests(unittest.TestCase):
    def run_(self, cands, risk=LOW, **kw):
        return suggest("implementer", risk, cands, catalog=CATALOG, at=AT, **kw)

    def test_no_candidates(self):
        r = self.run_([])
        self.assertIsNone(r["selection"])
        self.assertIn("empty", r["reason"])

    def test_explicit_is_never_overridden(self):
        r = self.run_([cand("claude", "b")], risk=HIGH, explicit={"tool": "codex", "profile": "x"}, history=hist({("claude", "b"): (50, 50)}))
        self.assertEqual(r["selection"], {"tool": "codex", "profile": "x"})
        self.assertEqual((r["basis"], r["applied"], r["ranking"]), ("explicit", False, []))

    def test_zero_of_three_samples_is_not_a_recommendation(self):
        r = self.run_([cand(profile="a"), cand(profile="b")], history=hist({("codex", "a"): (2, 2)}))
        self.assertEqual(r["basis"], "list_order")
        self.assertIn("not a measured recommendation", r["reason"])

    def test_history_wins_when_informed(self):
        r = self.run_([cand(profile="a"), cand(profile="b")], history=hist({("codex", "a"): (4, 1), ("codex", "b"): (4, 4)}))
        self.assertEqual((r["selection"]["profile"], r["basis"]), ("b", "history"))

    def test_high_risk_needs_history(self):
        r = self.run_([cand(profile="a"), cand(profile="b")], risk=HIGH, history=hist({("codex", "b"): (3, 3)}))
        self.assertEqual(r["selection"]["profile"], "b")
        self.assertEqual(r["excluded"][0]["reasons"], ["insufficient_history_for_risk"])
        self.assertEqual(self.run_([cand()], risk={"level": "bogus"})["risk_level"], "unknown")

    def test_exclusions_carry_reasons(self):
        r = self.run_([cand(available=False), cand("custom", "c"), cand(quota="exhausted", profile="q"), cand("gemini", "g")])
        self.assertIsNone(r["selection"])
        self.assertEqual([e["reasons"] for e in r["excluded"]],
                         [["tool_unavailable"], ["tool_cannot_do_role"], ["quota_exhausted"], ["tool_cannot_do_role"]])

    def test_unknown_cost_is_unknown_not_zero(self):
        r = self.run_([cand(price_model="no-such-model")], expected_usage=USAGE)
        cost = r["ranking"][0]["cost"]
        self.assertEqual((cost["status"], cost["amount"]), ("unknown", None))
        self.assertIn("cost unknown", r["reason"])
        self.assertIsNone(self.run_([cand(price_model="m-cheap")])["ranking"][0]["cost"]["amount"])  # no usage given

    def test_budget(self):
        budget = {"max_amount": 1.0, "currency": "USD"}
        r = self.run_([cand(profile="dear", price_model="m-dear"), cand(profile="mystery"), cand(profile="cheap", price_model="m-cheap")],
                      expected_usage=USAGE, budget=budget)
        self.assertEqual(r["selection"]["profile"], "cheap")
        self.assertEqual({e["profile"]: e["reasons"] for e in r["excluded"]},
                         {"dear": ["over_budget"], "mystery": ["cost_unknown_under_budget"]})

    def test_invalid_price_catalog_is_unknown(self):
        bad = [{"model": "m", "effective_from": "not a date"}]
        r = suggest("implementer", LOW, [cand(price_model="m")], catalog=bad, expected_usage=USAGE, at=AT)
        self.assertEqual(r["ranking"][0]["cost"]["reason"], "price_invalid")

    def test_model_version_drift_drops_old_history(self):
        h = hist({("codex", "a"): (9, 9)})
        same = self.run_([cand(model_version="2", history_version="2")], risk=HIGH, history=h)
        drift = self.run_([cand(model_version="3", history_version="2")], risk=HIGH, history=h)
        self.assertEqual(same["selection"]["profile"], "a")
        self.assertIsNone(drift["selection"])
        self.assertEqual(drift["excluded"][0]["reasons"], ["version_changed_no_history"])

    def test_read_role_uses_read_history(self):
        h = lambda: {("read", "claude", "r"): {"runs": 3, "ok": 3, "avg_tokens": None, "avg_seconds": None}}
        r = suggest("reviewer", HIGH, [cand("claude", "r")], history=h, at=AT)
        self.assertEqual(r["selection"]["tool"], "claude")


if __name__ == "__main__":
    unittest.main()


class DecideTests(unittest.TestCase):
    def go(self, mode, explicit=None, actual=None, cands=None, **settings):
        from respected_orchestrator.workflows.routing_policy import decide
        s = {"routing_mode": mode, **settings} if mode is not None else settings
        return decide(s, "implementer", LOW, cands or [cand(profile="b")], explicit=explicit, actual=actual, at=AT)

    def test_shadow_is_default_and_never_effective(self):
        for mode in (None, "garbage", "shadow"):
            d = self.go(mode, actual={"tool": "codex", "profile": "a"})
            self.assertEqual((d["mode"], d["effective"], d["differs"]), ("shadow", None, True))

    def test_active_uses_suggestion_and_off_is_the_kill_switch(self):
        actual = {"tool": "codex", "profile": "a"}
        self.assertEqual(self.go("active", actual=actual)["effective"], {"tool": "codex", "profile": "b"})
        off = self.go("off", actual=actual)
        self.assertEqual((off["suggestion"], off["effective"]), (None, None))  # same inputs, one setting flipped = rollback

    def test_active_never_replaces_explicit_and_needs_a_candidate(self):
        d = self.go("active", explicit={"tool": "claude", "profile": "x"}, actual={"tool": "claude", "profile": "x"})
        self.assertEqual((d["effective"], d["differs"]), (None, False))
        self.assertIsNone(self.go("active", cands=[cand(available=False)])["effective"])  # no silent fallback to something else

    def test_record_appends_and_survives_a_bad_path(self):
        import json, tempfile
        from pathlib import Path
        from respected_orchestrator.workflows.routing_policy import record, LOG_NAME
        actual = {"tool": "codex", "profile": "a"}
        d = self.go("shadow", actual=actual)
        with tempfile.TemporaryDirectory() as tmp:
            record(tmp, d, "implementer", actual, AT)
            record(tmp, d, "implementer", actual, AT)
            lines = [json.loads(x) for x in (Path(tmp) / LOG_NAME).read_text("utf-8").splitlines()]
        self.assertEqual(len(lines), 2)
        self.assertEqual((lines[0]["suggested"]["profile"], lines[0]["differs"]), ("b", True))
        record(Path(tmp) / "missing", d, "implementer", actual, AT)  # must not raise
