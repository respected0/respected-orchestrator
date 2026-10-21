"""Campaign supervisor: parallel lanes, dependencies, completion event and one-shot final master (fake workers only)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from respected_orchestrator.workflows import campaign
from respected_orchestrator.context import EngineContext
from respected_orchestrator.workflows.maf_workflow import run_maf_coding_task
from respected_orchestrator.engine.runner import apply_task, check_result

WRITE = "from pathlib import Path; Path('f.txt').write_text('new\\n')"
CHECK = "from pathlib import Path; assert Path('f.txt').read_text() == 'new\\n'"


def approve(lane_ctx, run_id):
    return run_maf_coding_task(ctx=lane_ctx, run_id=run_id, reviewer=lambda results: {"decision": "APPROVED"})


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        self.out = self.root / "master.txt"
        patcher = mock.patch("respected_orchestrator.engine.runner._stdin_is_tty", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def source(self, name, git=True):
        path = self.root / name
        path.mkdir()
        (path / "f.txt").write_text("old\n")
        if git:
            for args in (["init", "-b", "main"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@i.invalid",
                                                                 "commit", "-m", "base"]):
                subprocess.run(["git", *args], cwd=path, capture_output=True, check=True)
        return path

    def lane(self, name, source, command=None, after=()):
        return {"name": name, "after": list(after), "request": {
            "project_root": str(source), "task": f"{name} task", "worker": "custom", "kind": "write",
            "ownership": ["f.txt"], "command": command or [sys.executable, "-c", WRITE],
            "acceptance": [[sys.executable, "-c", CHECK]], "timeout_seconds": 30,
            "workflow": {"max_corrections": 0}}}

    def spec(self, lanes):
        record = ("import sys; open(r'%s','a').write(sys.argv[1] + chr(10) + '=====' + chr(10))" % self.out)
        return {"goal": "demo", "workstreams": lanes,
                "final": {"command": [sys.executable, "-c", record, "{prompt}"], "timeout_seconds": 30}}

    def start(self, spec):
        with mock.patch.object(campaign.agy, "_spawn_detached", return_value=4242) as spawn:
            started = campaign.start_campaign(self.ctx, spec)
        return started["campaign_id"], spawn

    def test_three_lanes_run_concurrently_then_one_master_is_started(self):
        sources = [self.source(n) for n in ("hub", "second", "orch")]
        lanes = [self.lane(n, s) for n, s in zip(("hub", "second", "orch"), sources)]
        campaign_id, spawn = self.start(self.spec(lanes))
        command = spawn.call_args.args[0]
        self.assertEqual(command[-2:], ["campaign-run", campaign_id])
        self.assertIn("engine", str(spawn.call_args.args[1]))  # supervisor runs from an engine snapshot
        barrier = threading.Barrier(3, timeout=20)  # sequential execution could never pass this barrier

        def runner(lane_ctx, run_id):
            barrier.wait()
            return approve(lane_ctx, run_id)

        result = campaign.run_campaign(self.ctx, campaign_id, lane_runner=runner)
        self.assertEqual(result["status"], "LANES_APPROVED", result)
        self.assertEqual(len({lane["lane_data_root"] for lane in result["lanes"]}), 3)
        text = self.out.read_text()
        self.assertEqual(text.count("====="), 1)
        for name in ("hub", "second", "orch"):
            self.assertIn(name, text)
        events = [e["event"] for e in campaign.campaign_status(self.ctx, campaign_id)["events"]]
        self.assertEqual(events.count("lane.completed"), 3)
        self.assertEqual(events[-2:], ["campaign.completed", "master.finished"])
        campaign.run_campaign(self.ctx, campaign_id, lane_runner=runner)  # resume: master is not started twice
        self.assertEqual(self.out.read_text().count("====="), 1)
        for lane in result["lanes"]:
            self.assertEqual(Path(lane["lane_data_root"]).parent.name, "lanes")
        self.assertEqual(sources[0].joinpath("f.txt").read_text(), "old\n")

    def test_dependency_waits_and_failed_dependency_skips_dependents(self):
        first, second = self.source("a"), self.source("b")
        bad = [sys.executable, "-c", "raise SystemExit(3)"]
        lanes = [self.lane("a", first, command=bad), self.lane("b", second, after=["a"])]
        campaign_id, _ = self.start(self.spec(lanes))
        result = campaign.run_campaign(self.ctx, campaign_id, lane_runner=approve)
        self.assertEqual({lane["name"]: lane["status"] for lane in result["lanes"]},
                         {"a": "FAILED", "b": "SKIPPED"})
        self.assertEqual(result["status"], "LANES_NEED_REVIEW")
        self.assertIn("SKIPPED", self.out.read_text())

    def test_non_git_source_uses_mirror_and_verified_patch_is_applied_back(self):
        source = self.source("hub", git=False)
        (source / ".env").write_text("SECRET=1\n")
        campaign_id, _ = self.start(self.spec([self.lane("hub", source)]))
        result = campaign.run_campaign(self.ctx, campaign_id, lane_runner=approve)
        lane = result["lanes"][0]
        self.assertEqual(lane["status"], "MASTER_APPROVED")
        mirror = self.ctx.data_root / "campaigns" / campaign_id / "mirrors" / "hub"
        self.assertFalse((mirror / ".env").exists())
        self.assertFalse((source / ".git").exists())
        lane_ctx = EngineContext(Path(lane["lane_data_root"]))
        self.assertEqual((source / "f.txt").read_text(), "old\n")
        self.assertEqual(check_result(lane_ctx, lane["final_run_id"])["status"], "verified")
        self.assertEqual(apply_task(lane_ctx, lane["final_run_id"])["status"], "applied")
        self.assertEqual((source / "f.txt").read_text(), "new\n")
        self.assertFalse((source / ".git").exists())

    def test_invalid_campaigns_are_rejected(self):
        source = self.source("x")
        for bad in ({}, {"workstreams": []},
                    {"workstreams": [self.lane("a", source, after=["a"])]},
                    {"workstreams": [self.lane("a", source), self.lane("a", source)]},
                    {"workstreams": [self.lane("a", source)], "final": {"command": ["claude", "--yolo", "{prompt}"]}}):
            with self.assertRaises(ValueError, msg=str(bad)):
                campaign._spec(bad)

    def test_apply_permission_for_the_final_master_is_opt_in_and_narrow(self):
        source = self.source("a")
        for allow in (False, True):
            spec = self.spec([self.lane(f"a{int(allow)}", source)])
            spec["final"] = {"command": ["claude", "-p", "{prompt}"], "allow_apply": allow}
            with mock.patch.object(campaign.shutil, "which", return_value="claude"):
                campaign_id, _ = self.start(spec)
            fake = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "ok", ""))
            with mock.patch.object(campaign, "execute", fake):
                campaign.run_campaign(self.ctx, campaign_id, lane_runner=approve)
            fake.assert_called_once()
            command, kwargs = fake.call_args.args[0], fake.call_args.kwargs
            self.assertEqual(command[command.index("--permission-mode") + 1], "dontAsk")
            self.assertNotIn("--dangerously-skip-permissions", command)
            self.assertEqual("Bash(python -m respected_orchestrator:*)" in command, allow)
            self.assertFalse(kwargs["mark_child"])
            self.assertIn("PYTHONPATH", kwargs["env"])
            self.assertEqual(command[0], "claude")
            self.assertIn("approved lanes" if allow else "not permitted", command[-1] if not allow else " ".join(command))

    def test_engine_snapshot_is_a_separate_copy(self):
        snapshot = campaign._snapshot_engine(self.ctx)
        self.assertTrue((snapshot / "respected_orchestrator" / "campaign.py").is_file())
        self.assertNotIn("__pycache__", {p.name for p in snapshot.rglob("*")})
        self.assertTrue(snapshot.is_relative_to(self.ctx.data_root))


    def test_final_prompt_states_per_lane_apply_state_and_makes_goal_authoritative(self):
        spec = {"goal": "ship the feature", "final": {"allow_apply": False}}
        lanes = [{"name": "a", "status": "MASTER_APPROVED", "applied": True},
                 {"name": "b", "status": "MASTER_APPROVED", "applied": False},
                 {"name": "c", "status": "FAILED", "applied": False}]
        prompt = campaign._final_prompt(spec, None, lanes, None, project_review=True)
        self.assertIn("ship the feature", prompt)
        self.assertIn("the authority for what counts as done", prompt)
        self.assertIn("a: already applied and verified; do not run apply", prompt)
        self.assertIn("b: approved but not applied", prompt)
        self.assertIn("c: FAILED; do not apply", prompt)
        self.assertIn("VERDICT: APPROVED|CHANGES REQUIRED|BLOCKED", prompt)
        self.assertIn("not permitted", prompt)

    def test_campaign_final_prompt_does_not_ask_for_a_project_verdict_line(self):
        spec = {"goal": "demo", "final": {"allow_apply": False}}
        prompt = campaign._final_prompt(spec, None, [{"name": "a", "status": "MASTER_APPROVED"}], None)
        self.assertNotIn("VERDICT:", prompt)
        self.assertIn("approved but not applied", prompt)


if __name__ == "__main__":
    unittest.main()
