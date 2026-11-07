import unittest

from respected_orchestrator.workflows import team_loop as tl, team_profiles as tp

TOOLS = ["codex", "claude", "opencode", "custom", "agy", "openrouter", "cursor"]


def team(**tools):
    members = [{"id": r, "role": r, "assignment": {"tool": tools.get(r, "claude"), "profile": tools.get(r + "_p", r)}} for r in tp.TEAM_ROLES]
    return tp.validate_team({"schema": 1, "id": "core", "name": "Core", "members": members}, TOOLS)


def env(op, frm="implementer", to="reviewer", action="review", session=None, paths=("src/a.py",), evidence=(), hop=1, max_hops=5, retry=2):
    return {"operation_id": op, "from": {"profile_id": frm, "rev": 1, "session_id": session or f"ss-{frm}"}, "to": {"profile_id": to, "role": to},
            "scope": {"paths": list(paths)}, "evidence": [{"run_id": r, "sha256": s} for r, s in evidence], "next_action": action,
            "hop": hop, "max_hops": max_hops, "retry_budget": retry}


class TeamLoopTests(unittest.TestCase):
    def test_plain_delivery(self):
        d = tl.evaluate(team(), [], env("a"))
        self.assertEqual((d["accept"], d["action"], d["waiting_on"], d["stop_sessions"]), (True, "deliver", "reviewer", []))

    def test_duplicate_handoff_is_idempotent(self):
        first = env("a")
        d = tl.evaluate(team(), [first], env("a"))
        self.assertEqual((d["accept"], d["action"], d["waiting_on"]), (False, "duplicate", None))

    def test_a_b_cycle_without_progress_is_rejected_and_with_progress_allowed(self):
        t = team()
        chain = [env("1", "implementer", "reviewer", "review", evidence=[("run-1", "a" * 64)]),
                 env("2", "reviewer", "implementer", "implement", evidence=[("run-1", "a" * 64)])]
        again = env("3", "implementer", "reviewer", "review", evidence=[("run-1", "a" * 64)])
        d = tl.evaluate(t, chain, again)
        self.assertEqual((d["action"], d["reasons"]), ("reject", ["same handoff repeated without new evidence (cycle)"]))
        better = env("3", "implementer", "reviewer", "review", evidence=[("run-1", "a" * 64), ("run-2", "b" * 64)])
        self.assertEqual(tl.evaluate(t, chain, better)["action"], "deliver")

    def test_max_hop_exceeded_escalates_and_names_running_sessions_to_stop(self):
        chain = [env(str(i), session=f"ss-{i}", max_hops=3) for i in range(3)]
        active = {"ss-0": {"profile_id": "implementer", "paths": []}, "ss-9": {"profile_id": "other-task", "paths": []}}
        d = tl.evaluate(team(), chain, env("new", session="ss-x", max_hops=3), active=active)
        self.assertEqual((d["action"], d["to_operator"], d["accept"], d["stop_sessions"]), ("escalate", True, False, ["ss-0"]))
        self.assertNotIn("apply", d["action"])
        self.assertEqual(tl.evaluate(team(), chain, env("new", max_hops=9), lim={"max_handoffs": 3})["action"], "escalate")  # the lower limit wins

    def test_retry_ceiling_counts_rework_handoffs(self):
        chain = [env("1", "reviewer", "implementer", "implement", evidence=[("r", "a" * 64)]),
                 env("2", "reviewer", "implementer", "implement", evidence=[("r", "b" * 64)])]
        d = tl.evaluate(team(), chain, env("3", "reviewer", "implementer", "implement", evidence=[("r", "c" * 64)], retry=2))
        self.assertEqual((d["action"], d["reasons"][0][:12]), ("escalate", "retry budget"))
        self.assertEqual(tl.evaluate(team(), chain, env("3", "reviewer", "implementer", "implement", evidence=[("r", "c" * 64)], retry=3))["action"], "deliver")

    def test_conflicting_files_with_a_running_session(self):
        active = {"ss-qa": {"profile_id": "qa", "paths": ["src"]}}
        d = tl.evaluate(team(), [], env("a", paths=["src/a.py"]), active=active)
        self.assertEqual(d["action"], "reject")
        self.assertIn("ownership conflict with running session ss-qa", d["reasons"][0])
        self.assertEqual(tl.evaluate(team(), [], env("a", paths=["docs/x.md"]), active=active)["action"], "deliver")
        own = {"ss-implementer": {"profile_id": "implementer", "paths": ["src"]}}  # the sender's own session is not a conflict
        self.assertEqual(tl.evaluate(team(), [], env("a"), active=own)["action"], "deliver")

    def test_reviewer_must_differ_from_author_when_required(self):
        same = team(implementer="claude", implementer_p="m", reviewer="claude", reviewer_p="m")
        self.assertEqual(tl.evaluate(same, [], env("a"))["action"], "deliver")  # allowed unless the setting demands independence
        d = tl.evaluate(same, [], env("a"), require_independent_review=True)
        self.assertEqual(d["action"], "reject")
        self.assertIn("independent review", d["reasons"][0])
        other = team(implementer="claude", implementer_p="m", reviewer="codex", reviewer_p="g")
        self.assertEqual(tl.evaluate(other, [], env("a"), require_independent_review=True)["action"], "deliver")

    def test_missing_resource_rejects_without_substituting(self):
        d = tl.evaluate(team(reviewer="codex"), [], env("a"), available=lambda tool: tool != "codex")
        self.assertEqual(d["action"], "reject")
        self.assertIn("nothing was substituted", d["reasons"][0])

    def test_invalid_limits_raise(self):
        with self.assertRaises(ValueError):
            tl.evaluate(team(), [], env("a"), lim={"max_handoffs": 0})

    def test_simulated_job_always_ends(self):
        """Two roles bounce work back and forth forever: the chain must stop being delivered within the hop budget."""
        t, chain, delivered = team(), [], 0
        for i in range(40):
            a, b, action = ("implementer", "reviewer", "review") if i % 2 == 0 else ("reviewer", "implementer", "implement")
            e = env(f"op{i}", a, b, action, evidence=[(f"run-{i}", f"{i:064x}")], max_hops=8, retry=5)
            d = tl.evaluate(t, chain, e)
            if d["action"] != "deliver":
                self.assertEqual(d["action"], "escalate")
                break
            chain.append(e)
            delivered += 1
        self.assertLessEqual(delivered, 3)  # default max_handoffs
        self.assertLess(i, 39)


if __name__ == "__main__":
    unittest.main()
