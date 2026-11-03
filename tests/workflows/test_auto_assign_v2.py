"""COST-03: deterministic auto-assign v2 decisions from measured evidence."""
import json
import unittest

from respected_orchestrator.engine.runner import SUPPORTED_AGENTS
from respected_orchestrator.workflows import roles

TOOLS = list(SUPPORTED_AGENTS)


def run(pool, history, needed="tester", available=("codex", "claude", "custom"), **settings):
    return roles.resolve({"auto_assign": True, "auto_pool": json.dumps(pool), **settings}, {},
                         [needed], tools=TOOLS, available=lambda tool: tool in available,
                         history=lambda: history)[needed]


def row(runs, ok, tokens):
    return {"runs": runs, "ok": ok, "avg_tokens": tokens, "avg_seconds": 1}


class AutoAssignV2Tests(unittest.TestCase):
    def test_insufficient_history_says_pool_order(self):
        got = run([{"tool": "codex", "profile": "a"}], {("read", "codex", "a"): row(2, 2, 10)})
        self.assertEqual((got["basis"], got["profile"]), ("pool_order", "a"))
        self.assertIn("not a measured recommendation", got["reason"])

    def test_equal_scores_are_deterministic_by_pool_order(self):
        history = {("read", "codex", "a"): row(4, 3, 10), ("read", "codex", "b"): row(4, 3, 10)}
        got = run([{"tool": "codex", "profile": "a"}, {"tool": "codex", "profile": "b"}], history)
        self.assertEqual(got["profile"], "a")
        self.assertEqual([r["profile"] for r in got["ranking"]], ["a", "b"])

    def test_blocked_profile_is_excluded_not_silently_used(self):
        history = {("read", "codex", "mimo-x"): row(10, 10, 1), ("read", "codex", "safe"): row(3, 2, 20)}
        got = run([{"tool": "codex", "profile": "mimo-x"}, {"tool": "codex", "profile": "safe"}], history,
                  blocked_profiles="mimo")
        self.assertEqual(got["profile"], "safe")
        self.assertIn("blocked", got["excluded"][0]["excluded"])

    def test_write_role_never_gets_a_read_only_tool(self):
        history = {("write", "custom", "c"): row(10, 10, 1), ("write", "codex", "ok"): row(3, 2, 30)}
        got = run([{"tool": "custom", "profile": "c"}, {"tool": "codex", "profile": "ok"}], history,
                  needed="debugger", available=("custom", "codex"))
        self.assertEqual((got["tool"], got["profile"]), ("codex", "ok"))
        self.assertIn("cannot do debugger work", got["excluded"][0]["excluded"])

    def test_lost_model_uses_only_the_explicit_fallback(self):
        requested = {"implementer": {"tool": "codex", "profile": "dead",
                                     "fallbacks": [{"tool": "codex", "profile": "backup"}]}}
        got = roles.resolve({"blocked_profiles": "dead"}, requested, ["implementer"], tools=TOOLS,
                            available=lambda tool: tool == "codex")["implementer"]
        self.assertEqual(got["profile"], "backup")
        self.assertIn("blocked", got["fallback_of"])

    def test_expensive_candidate_loses_an_equal_record(self):
        history = {("read", "codex", "cheap"): row(4, 3, 10), ("read", "codex", "pricey"): row(4, 3, 900)}
        got = run([{"tool": "codex", "profile": "pricey"}, {"tool": "codex", "profile": "cheap"}], history)
        self.assertEqual(got["profile"], "cheap")

    def test_explicit_override_is_never_replaced(self):
        got = roles.resolve({"auto_assign": True, "auto_pool": json.dumps([{"tool": "codex", "profile": "auto"}])},
                            {"tester": {"tool": "claude", "profile": "mine"}}, ["tester"], tools=TOOLS,
                            available=lambda tool: True)["tester"]
        self.assertEqual((got["profile"], got["source"]), ("mine", "explicit"))


if __name__ == "__main__":
    unittest.main()