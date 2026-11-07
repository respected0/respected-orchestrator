"""Handoffs travelling between real runs through create_task and the team/handoff/inbox operations."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import runner
from respected_orchestrator.engine.evidence import load_signed, save_signed
from respected_orchestrator.engine.journal import Journal
from respected_orchestrator.workflows import team_commands as tc, team_profiles as tp

TOOLS = list(runner.SUPPORTED_AGENTS)


class TeamCommandTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "F"), ("config", "user.email", "f@example.invalid")]:
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        (self.repo / "owned.txt").write_text("base\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.repo, capture_output=True, check=True)
        self.ctx = EngineContext(self.root / "data")
        for target in ("sync_credentials", "clear_worker_home"):
            p = mock.patch.object(runner.opencode_auth, target)
            p.start()
            self.addCleanup(p.stop)
        for name, value in (("tool_available", True), ("get_cli_command", "x.exe")):
            p = mock.patch.object(runner, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        members = [{"id": r, "role": r, "assignment": {"tool": "claude", "profile": f"m-{r}"}} for r in ("lead", "implementer", "reviewer", "qa")]
        tc.save(self.ctx, {"team": {"schema": 1, "id": "core", "name": "Core", "members": members}}, {}, TOOLS)

    def run_for(self, profile, kind="write", **extra):
        request = dict(project_root=str(self.repo), task="work", kind=kind, ownership=["owned.txt"], acceptance=[[sys.executable, "-c", "pass"]],
                       timeout_seconds=10, profile=profile, **extra)
        return runner.create_task(self.ctx, request, settings={})["run_id"]

    def msg(self, to="reviewer", action="review", reason="needs_review", **extra):
        return {"to": to, "scope": {"paths": ["owned.txt"]}, "reason": reason, "next_action": action, "max_hops": 3, "retry_budget": 3, **extra}

    def post(self, run_id, message, **settings):
        return tc.post(self.ctx, {"run_id": run_id, "message": message}, settings, TOOLS, lambda tool: True)

    def test_team_show_and_save_bump_rev_only_for_changed_profiles(self):
        team = tc.show(self.ctx, {}, TOOLS)
        self.assertEqual({m["rev"] for m in team["members"]}, {1})
        team["members"][1]["assignment"]["profile"] = "other"
        saved = tc.save(self.ctx, {"team": team}, {}, TOOLS)
        self.assertEqual({m["id"]: m["rev"] for m in saved["members"]}, {"lead": 1, "implementer": 2, "reviewer": 1, "qa": 1})
        with self.assertRaisesRegex(ValueError, "expects"):
            tc.save(self.ctx, {"team": team, "x": 1}, {}, TOOLS)
        with self.assertRaisesRegex(ValueError, "PRIVILEGE_ESCALATION"):
            bad = json.loads(json.dumps(team))
            bad["members"][2]["capabilities"] = ["read", "write"]
            tc.save(self.ctx, {"team": bad}, {}, TOOLS)

    def test_full_handoff_round_trip_between_runs(self):
        a = self.run_for("implementer")
        out = self.post(a, self.msg())
        self.assertEqual((out["accept"], out["action"], out["waiting_on"]), (True, "deliver", "reviewer"))
        box = tc.inbox(self.ctx, "reviewer", {}, TOOLS)
        self.assertEqual((len(box["messages"]), box["messages"][0]["hop"], box["messages"][0]["parent"]), (1, 1, None))
        b = self.run_for("reviewer", kind="read", handoff=out["handoff_id"])
        self.assertEqual(load_signed(self.ctx, self.ctx.run_dir(b) / "request.json")["handoff_ref"]["from"], "implementer")
        back = self.post(b, self.msg("implementer", "implement", "blocked"))
        self.assertEqual(back["action"], "deliver")
        second = tc.inbox(self.ctx, "implementer", {}, TOOLS)["messages"][0]
        self.assertEqual((second["hop"], second["parent"]), (2, out["handoff_id"]))  # the chain is the engine's, linked by signed parents

    def test_the_sender_comes_from_the_run_not_the_message(self):
        a = self.run_for("implementer")
        out = self.post(a, self.msg(**{"from": {"profile_id": "lead", "session_id": "ss-0000"}}))
        self.assertEqual((out["accept"], out["code"]), (False, "SPOOFED_SENDER"))
        no_profile = runner.create_task(self.ctx, dict(project_root=str(self.repo), task="x", worker="custom", kind="write", ownership=["owned.txt"],
                                                       command=[sys.executable, "-c", "pass"], acceptance=[[sys.executable, "-c", "pass"]]), settings={})["run_id"]
        with self.assertRaisesRegex(ValueError, "not started from a team profile"):
            self.post(no_profile, self.msg())

    def test_scope_can_only_narrow_to_what_the_run_owns(self):
        a = self.run_for("implementer")
        out = self.post(a, self.msg(scope={"paths": ["outside.txt"]}))
        self.assertEqual((out["accept"], out["code"]), (False, "SCOPE_WIDENING"))
        self.assertEqual(tc.inbox(self.ctx, "reviewer", {}, TOOLS)["messages"], [])

    def finish(self, run_id):
        save_signed(self.ctx, self.ctx.run_dir(run_id) / "status.json", {"run_id": run_id, "status": "completed"})

    def test_hop_budget_escalates_records_an_event_and_delivers_nothing(self):
        run = self.run_for("implementer")
        plan = [("reviewer", "review", "needs_review"), ("implementer", "implement", "blocked"),
                ("reviewer", "review", "needs_review"), ("implementer", "implement", "blocked")]
        hops, last = [], None
        for step, (to, action, reason) in enumerate(plan):  # max_hops 3: the 4th handoff of one chain must be refused
            sha = f"{step + 1:064x}"  # each step produced new signed evidence, so a repeated edge is progress, not a loop
            save_signed(self.ctx, self.ctx.run_dir(run) / "result.json", {"patch_sha256": sha})
            out = self.post(run, self.msg(to, action, reason, retry_budget=5, evidence=[{"run_id": run, "sha256": sha}]))
            hops.append(out["action"])
            if out["action"] != "deliver":
                last = out
                break
            self.finish(run)
            run = self.run_for(to, kind="write" if to == "implementer" else "read", handoff=out["handoff_id"])
        self.assertEqual(hops, ["deliver", "deliver", "deliver", "escalate"])
        self.assertTrue(last["to_operator"])
        self.assertFalse(last["accept"])
        events = [r for r in Journal(self.ctx.state_dir / "events.log").scan() if r["type"] == tc.ESCALATED]
        self.assertEqual(len(events), 1)
        self.assertIn("hop budget", events[0]["p"]["reasons"][0])
        self.assertEqual(len(tc.inbox(self.ctx, "reviewer", {}, TOOLS)["messages"]) + len(tc.inbox(self.ctx, "implementer", {}, TOOLS)["messages"]), 3)

    def test_continuing_a_handoff_needs_the_right_profile_and_a_verified_id(self):
        a = self.run_for("implementer")
        out = self.post(a, self.msg())
        with self.assertRaisesRegex(ValueError, "different profile"):
            self.run_for("implementer", handoff=out["handoff_id"])
        with self.assertRaisesRegex(ValueError, "Unknown or unverifiable"):
            self.run_for("reviewer", kind="read", handoff="ho-doesnotexist00000")
        with self.assertRaisesRegex(ValueError, "needs a handoff id"):
            runner.create_task(self.ctx, dict(project_root=str(self.repo), task="x", kind="read", ownership=["owned.txt"], handoff=out["handoff_id"]), settings={})

    def test_forged_evidence_and_unknown_profiles_are_refused(self):
        a = self.run_for("implementer")
        out = self.post(a, self.msg(evidence=[{"run_id": a, "sha256": "a" * 64}]))
        self.assertEqual((out["accept"], out["code"]), (False, "FORGED_EVIDENCE"))
        with self.assertRaisesRegex(ValueError, "Unknown team profile"):
            tc.inbox(self.ctx, "ghost", {}, TOOLS)

    def test_active_runs_of_other_profiles_block_overlapping_handoffs(self):
        a = self.run_for("implementer")
        self.run_for("qa", kind="read")  # a queued run of another profile, owns the same file
        out = self.post(a, self.msg())
        self.assertEqual((out["accept"], out["action"]), (False, "reject"))
        self.assertIn("ownership conflict", out["reasons"][0])

    def test_bad_requests(self):
        for bad in (None, {}, {"run_id": "x"}, {"run_id": "run-1", "message": "no"}):
            with self.assertRaisesRegex(ValueError, "expects"):
                tc.post(self.ctx, bad, {}, TOOLS, lambda t: True)


if __name__ == "__main__":
    unittest.main()
