import unittest

from respected_orchestrator.workflows import routing_confidence as rc
from respected_orchestrator.workflows.routing_policy import suggest

AT = "2026-11-07T12:00:00+00:00"


def make(direct_pass=20, orch_pass=25, *, model="m", version="1", tasks=10, repeat=3, violations=0, tokens=100, **over):
    runs = []
    for arm, ok in (("direct", direct_pass), ("orchestrated", orch_pass)):
        for i in range(tasks * repeat):
            runs.append({"task_id": f"T{i // repeat}", "arm": arm, "repeat": i % repeat + 1, "status": "passed" if i < ok else "failed",
                         "tokens": tokens if tokens is not None else "unknown", "cost": "unknown",
                         "security_violation": (i < violations) if arm == "orchestrated" else None})
    base = {"schema": rc.SCHEMA, "kind": "real", "status": "complete", "commit": "abc123", "agent": {"name": "claude", "model": model, "version": version},
            "timeout": 300.0, "repeat": repeat, "task_ids": [f"T{i}" for i in range(tasks)], "golden_used": False, "runs": runs}
    return {**base, **over}


class ConfidenceTests(unittest.TestCase):
    def test_wilson(self):
        self.assertIsNone(rc.wilson(0, 0))
        low, high = rc.wilson(15, 30)
        self.assertTrue(0.3 < low < 0.5 < high < 0.7, (low, high))
        self.assertEqual(rc.wilson(0, 30)[0], 0.0)
        self.assertEqual(rc.wilson(30, 30)[1], 1.0)

    def test_valid_report_and_verdicts(self):
        e = rc.evaluate([make()])["entries"][0]
        self.assertEqual((e["usable"], e["problems"]), (True, []))
        self.assertEqual((e["direct"]["rate"], e["orchestrated"]["rate"], e["orchestrated"]["security_violations"]), (0.6667, 0.8333, 0))
        self.assertEqual(e["verdict"], "no_detectable_difference")  # 20/30 vs 25/30 overlap: not a win
        self.assertEqual(rc.evaluate([make(5, 29)])["entries"][0]["verdict"], "orchestrated_better")
        self.assertEqual(rc.evaluate([make(29, 5)])["entries"][0]["verdict"], "orchestrated_worse")

    def test_unusable_reports_say_why(self):
        cases = {"not a real-agent report": make(kind="harness-test"), "status is 'stopped_quota'": make(status="stopped_quota"),
                 "commit not recorded": make(commit="unknown"), "fewer than 10 tasks x 3 repeats x 2 arms": make(tasks=4),
                 "unmeasured value written as 0": make(tokens=0),
                 "agent name, model and version must all be recorded": make(version="unknown"),
                 "golden fix reached an agent or a run is invalid": make(golden_used=True)}
        for message, report in cases.items():
            self.assertIn(message, rc.problems(report), message)
        self.assertEqual(rc.problems({"schema": "respected.eval.compare.v1"}), ["wrong schema"])  # synthetic compare output
        self.assertEqual(rc.problems(None), ["wrong schema"])
        broken = make()
        broken["runs"][0]["status"] = "agent_error"
        self.assertIn("agent_error runs present", rc.problems(broken))

    def test_confound_and_version_drift_are_flagged_not_merged(self):
        ev = rc.evaluate([make(version="1"), make(version="2"), make(model="other"), make(version="1", timeout=60.0)])["entries"]
        self.assertEqual(ev[0]["flags"], ["confounded_runs", "same_model_version_drift"])
        self.assertEqual(ev[1]["flags"], ["same_model_version_drift"])
        self.assertEqual(ev[2]["flags"], [])

    def test_unknown_tokens_stay_unknown(self):
        e = rc.evaluate([make(tokens=None)])["entries"][0]
        self.assertEqual(e["orchestrated"]["tokens"], "unknown")

    def test_gate_fails_without_measurement(self):
        for reports in ([], [make(kind="harness-test")], [make(status="stopped_quota")]):
            g = rc.gate(reports)
            self.assertFalse(g["ok"])
            self.assertIn("no usable real-agent benchmark report", g["reasons"])

    def test_gate_security_and_regression(self):
        self.assertTrue(rc.gate([make()])["ok"])
        self.assertTrue(rc.gate([make(tokens=None)])["ok"])  # unknown cost does not fail the gate
        self.assertFalse(rc.gate([make(violations=1)])["ok"])
        worse = rc.gate([make(29, 5)])
        self.assertFalse(worse["ok"])
        self.assertIn("detectably lower", worse["reasons"][0])

    def test_history_feeds_routing_and_skips_flagged_reports(self):
        table = rc.routing_history([make(orch_pass=25)])
        self.assertEqual(table[("write", "claude", "m")], {"runs": 30, "ok": 25, "avg_tokens": None, "avg_seconds": None})
        self.assertEqual(rc.routing_history([make(version="1"), make(version="2")]), {})  # drift: neither is trusted
        self.assertEqual(rc.routing_history([make(kind="harness-test")]), {})
        pick = suggest("implementer", {"level": "high"}, [{"tool": "claude", "profile": "m", "available": True},
                                                          {"tool": "codex", "profile": "x", "available": True}],
                       history=lambda: table, at=AT)
        self.assertEqual((pick["selection"]["tool"], pick["basis"]), ("claude", "history"))
        self.assertEqual(pick["excluded"][0]["reasons"], ["insufficient_history_for_risk"])


if __name__ == "__main__":
    unittest.main()
