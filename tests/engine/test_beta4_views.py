"""The three read-only Beta.4 views (team, capability recommendations, budget/success), straight and through the IPC server."""
import json
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import analytics, local_api
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.workflows import handoff, team_profiles as tp, team_view

TOOLS = ["codex", "claude", "opencode", "custom", "agy", "openrouter", "cursor"]
USAGE = {"raw_input_tokens": 1000, "cached_input_tokens": 0, "output_tokens": 100, "estimated_weighted_tokens": 1100}


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ctx = EngineContext(Path(temp.name).resolve() / "data")

    def run_(self, n, status="completed", worker="codex", project="C:/proj/a", reason=None, usage=USAGE, **extra):
        name = f"run-2026110800000{n}-aaaaaaaaaaa{n}"
        d = self.ctx.data_root / "state" / name
        d.mkdir(parents=True)
        save_signed(self.ctx, d / "request.json", {"kind": "write", "worker": worker, "project_root": project})
        save_signed(self.ctx, d / "status.json", {"status": status, "updated_at": "2026-11-08T00:00:00+00:00", **({"reason": reason} if reason else {}),
                                                  **({"usage": usage} if usage else {}), **extra})
        return name


class AnalyticsTests(Base):
    def test_disabled_collection_computes_nothing(self):
        self.run_(1)
        self.assertEqual(analytics.summary(self.ctx, {"usage_collection": False}), {"enabled": False, "reason": "usage_collection is off: nothing was read or computed"})

    def test_zero_runs(self):
        out = analytics.summary(self.ctx, {})
        self.assertEqual((out["enabled"], out["totals"]["runs"], out["totals"]["acceptance_rate"], out["budget"]["status"]), (True, 0, None, "no_budget"))

    def test_percentage_needs_a_meaningful_denominator(self):
        for n in range(1, 4):
            self.run_(n)
        totals = analytics.summary(self.ctx, {})["totals"]
        self.assertEqual((totals["runs"], totals["acceptance_rate"]), (3, None))
        self.assertIn("fewer than 5 runs", totals["rate_note"])
        for n in range(4, 8):
            self.run_(n, status="failed", reason="test_failed")
        totals = analytics.summary(self.ctx, {})["totals"]
        self.assertEqual((totals["runs"], totals["acceptance_rate"]), (7, round(3 / 7, 4)))

    def test_actual_unknown_and_estimate_stay_apart_and_unknown_is_never_zero(self):
        self.run_(1)
        self.run_(2, usage=None)  # reported nothing
        out = analytics.summary(self.ctx, {})
        t = out["totals"]
        self.assertEqual((t["tokens_actual"], t["runs_with_usage"], t["runs_without_usage"]), (1100, 1, 1))
        self.assertEqual(out["estimate"]["status"], "not_computed")
        self.assertTrue(any(w["kind"] == "unknown_usage" for w in out["warnings"]))
        blank = EngineContext(self.ctx.data_root.parent / "blank")
        n = f"run-20261108000009-aaaaaaaaaaa9"
        d = blank.data_root / "state" / n
        d.mkdir(parents=True)
        save_signed(blank, d / "request.json", {"kind": "write", "worker": "codex", "project_root": "C:/p"})
        save_signed(blank, d / "status.json", {"status": "completed"})
        self.assertIsNone(analytics.summary(blank, {})["totals"]["tokens_actual"])

    def test_budget_is_green_only_when_every_run_reported(self):
        self.run_(1)
        self.assertEqual(analytics.summary(self.ctx, {"budget_weighted_tokens": 100000})["budget"]["status"], "ok")
        self.run_(2, usage=None)
        self.assertEqual(analytics.summary(self.ctx, {"budget_weighted_tokens": 100000})["budget"]["status"], "unknown_possible_overrun")
        self.assertEqual(analytics.summary(self.ctx, {"budget_weighted_tokens": 1000})["budget"]["status"], "over")
        near = EngineContext(self.ctx.data_root.parent / "near")
        d = near.data_root / "state" / "run-20261108000001-aaaaaaaaaaa1"
        d.mkdir(parents=True)
        save_signed(near, d / "request.json", {"kind": "write", "worker": "codex", "project_root": "C:/p"})
        save_signed(near, d / "status.json", {"status": "completed", "usage": USAGE})
        self.assertEqual(analytics.summary(near, {"budget_weighted_tokens": 1300})["budget"]["status"], "near")
        for bad in (0, -5, True, "100", 1.5):
            self.assertEqual(analytics.summary(near, {"budget_weighted_tokens": bad})["budget"]["status"], "no_budget")

    def test_429_burst_is_counted_and_warned(self):
        for n in range(1, 6):
            self.run_(n, status="failed", reason="limit_exhausted", usage=None)
        out = analytics.summary(self.ctx, {})
        self.assertEqual(out["totals"]["quota_stops"], 5)
        self.assertTrue(any(w["kind"] == "quota_stops" for w in out["warnings"]))
        self.assertEqual(out["counts_by_failure"], {"quota": 5})

    def test_breakdowns_by_agent_and_project_and_a_large_window_is_bounded(self):
        self.run_(1, worker="codex", project="C:/a")
        self.run_(2, worker="claude", project="C:/b")
        out = analytics.summary(self.ctx, {})
        self.assertEqual({b["name"]: b["runs"] for b in out["by_agent"]}, {"claude": 1, "codex": 1})
        self.assertEqual({b["name"]: b["runs"] for b in out["by_project"]}, {"C:/a": 1, "C:/b": 1})
        big = EngineContext(self.ctx.data_root.parent / "big")
        for i in range(120):
            d = big.data_root / "state" / f"run-20261108{i:06d}-{i:012x}"
            d.mkdir(parents=True)
            save_signed(big, d / "request.json", {"kind": "write", "worker": "codex", "project_root": "C:/p"})
            save_signed(big, d / "status.json", {"status": "completed", "usage": USAGE})
        out = analytics.summary(big, {}, limit=100)
        self.assertEqual((out["window_runs"], len(out["runs"])), (100, analytics.MAX_ROWS))


class TeamViewTests(Base):
    def make_team(self):
        members = [{"id": r, "name": r.capitalize(), "role": r, "assignment": {"tool": "claude", "profile": "m"}} for r in ("implementer", "reviewer")]
        return tp.save(self.ctx.data_root, {"schema": 1, "id": "core", "name": "Core", "members": members}, TOOLS)

    def test_members_status_and_missing_tool(self):
        self.make_team()
        out = team_view.view(self.ctx, {}, TOOLS, lambda tool: tool != "claude")
        self.assertEqual((out["ok"], out["team"]["id"], [(m["id"], m["status"]) for m in out["members"]]), (True, "core", [("implementer", "tool_missing"), ("reviewer", "tool_missing")]))
        self.assertIn("nothing was substituted", out["members"][0]["reason"])

    def test_history_shows_handoffs_with_names_and_hides_forged_records(self):
        team = self.make_team()
        env = handoff.parse(self.ctx, team, {"to": "reviewer", "scope": {"paths": ["a.py"]}, "reason": "needs_review", "next_action": "review", "note": "please look"},
                            sender={"profile_id": "implementer", "session_id": "ss-1"}, granted_scope=["a.py"])
        handoff.post(self.ctx, env)
        from respected_orchestrator.engine.journal import Journal
        Journal(self.ctx.state_dir / "events.log").append("forged", handoff.EVENT, None, {"envelope": {**env, "operation_id": "forged"}, "sig": "0" * 64})
        Journal(self.ctx.state_dir / "events.log").append("esc-1", "handoff.escalated", "run-x", {"reasons": ["hop budget spent"], "api_token": "SECRET"})
        out = team_view.view(self.ctx, {}, TOOLS, lambda t: True)
        kinds = [h["kind"] for h in out["history"]]
        self.assertEqual((kinds, out["rejected_records"]), (["handoff", "escalated"], 1))
        first = out["history"][0]
        self.assertEqual((first["from"], first["to"], first["action"], first["hop"], first["note"]), ("Implementer", "Reviewer", "review", 1, "please look"))
        self.assertEqual(out["history"][1]["detail"]["api_token"], "[redacted]")

    def test_unreadable_team_file_is_a_problem_not_a_default(self):
        self.ctx.data_root.mkdir(parents=True, exist_ok=True)
        (self.ctx.data_root / tp.FILE).write_text("{broken", "utf-8")
        out = team_view.view(self.ctx, {}, TOOLS, lambda t: True)
        self.assertEqual((out["ok"], out["problem"]["code"], out["members"] if "members" in out else None), (False, "UNREADABLE", None))

    def test_no_stored_team_shows_the_derived_default_and_renamed_actors_use_the_current_name(self):
        out = team_view.view(self.ctx, {"default_worker": "codex"}, TOOLS, lambda t: True)
        self.assertEqual((out["ok"], out["team"]["id"], [m["id"] for m in out["members"]]), (True, "default", ["implementer"]))


class IpcTests(Base):
    def api(self, origin=Origin.HUMAN):
        return local_api.LocalApi(self.ctx, "tok-0123456789abcdef", origin=origin)

    def call(self, cmd, payload=None, origin=Origin.HUMAN, n=[0]):
        n[0] += 1
        return self.api(origin).handle({"ipc": local_api.IPC, "id": f"req-{n[0]:08}", "session": "tok-0123456789abcdef", "cmd": cmd, "payload": payload or {}})

    def test_commands_are_registered_read_only(self):
        for cmd in ("team.view", "analytics.summary", "capabilities.recommend"):
            self.assertIn(cmd, local_api.COMMANDS)
            self.assertEqual(local_api.COMMANDS[cmd][1].value, "read", cmd)

    def test_team_and_analytics_over_ipc_and_workers_are_refused(self):
        self.run_(1)
        out = self.call("analytics.summary")
        self.assertEqual((out["ok"], out["result"]["totals"]["runs"]), (True, 1))
        self.assertTrue(self.call("team.view")["ok"])
        for cmd in ("team.view", "analytics.summary"):
            self.assertEqual(self.call(cmd, origin=Origin.WORKER)["error"]["code"], "FORBIDDEN")
        self.assertEqual(self.call("analytics.summary", {"limit": 0})["error"]["code"], "BAD_REQUEST")

    def test_recommend_needs_a_task_and_returns_an_explained_read_only_answer(self):
        for bad in ({}, {"task": ""}, {"task": "x" * 2001}, {"task": 5}, {"task": "run tests", "project_root": "relative/path"}):
            self.assertEqual(self.call("capabilities.recommend", bad)["error"]["code"], "BAD_REQUEST", bad)
        out = self.call("capabilities.recommend", {"task": "update the docs"})
        self.assertTrue(out["ok"])
        self.assertEqual((out["result"]["side_effects"], out["result"]["risk_level"]), ("none", "unknown"))
        self.assertEqual(json.loads(json.dumps(out["result"]))["task_categories"], ["docs"])
        self.assertEqual(self.call("capabilities.recommend", {"task": "make it better"})["result"]["recommendations"], [])


if __name__ == "__main__":
    unittest.main()
