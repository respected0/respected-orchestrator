"""SCH-02: deterministic ready queue, bounded lane concurrency and scheduler state transitions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.processes import ProcessStopped
from respected_orchestrator.workflows import campaign
from respected_orchestrator.workflows.maf_workflow import run_maf_coding_task

WRITE = "from pathlib import Path; Path('f.txt').write_text('new\\n')"
CHECK = "from pathlib import Path; assert Path('f.txt').read_text() == 'new\\n'"


def approve(lane_ctx, run_id):
    return run_maf_coding_task(ctx=lane_ctx, run_id=run_id, reviewer=lambda results: {"decision": "APPROVED"})


class CampaignSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        patcher = mock.patch("respected_orchestrator.engine.runner._stdin_is_tty", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def source(self, name):
        path = self.root / name
        path.mkdir()
        (path / "f.txt").write_text("old\n")
        for args in (["init", "-b", "main"], ["add", "."],
                     ["-c", "user.name=t", "-c", "user.email=t@i.invalid", "commit", "-m", "base"]):
            subprocess.run(["git", *args], cwd=path, capture_output=True, check=True)
        return path

    def lane(self, name, source, command=None, after=(), ownership=None):
        return {"name": name, "after": list(after), "request": {
            "project_root": str(source), "task": f"{name} task", "worker": "custom", "kind": "write",
            "ownership": ownership or ["f.txt"], "command": command or [sys.executable, "-c", WRITE],
            "acceptance": [[sys.executable, "-c", CHECK]], "timeout_seconds": 30,
            "workflow": {"max_fix_rounds": 0}}}

    def spec(self, lanes, max_parallel=None):
        spec = {"goal": "scheduler", "workstreams": lanes, "lane_timeout_seconds": 30,
                "final": {"skip": True}}
        if max_parallel is not None:
            spec["max_parallel"] = max_parallel
        return spec

    def run_campaign(self, lanes, runner=approve, max_parallel=None):
        campaign_id, _ = campaign.create_campaign(self.ctx, self.spec(lanes, max_parallel))
        return campaign_id, campaign.run_campaign(self.ctx, campaign_id, lane_runner=runner)

    def transitions(self, result, name):
        return [(item["from"], item["to"]) for item in result["scheduler"]["transitions"][name]]

    def events(self, campaign_id):
        path = campaign.campaign_dir(self.ctx, campaign_id) / "events.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line]

    def test_scheduler_records_queued_to_running(self):
        source = self.source("one")
        _, result = self.run_campaign([self.lane("a", source)])
        self.assertIn(("QUEUED", "RUNNING"), self.transitions(result, "a"))

    def test_scheduler_records_running_to_approved(self):
        source = self.source("approved")
        _, result = self.run_campaign([self.lane("a", source)])
        self.assertEqual(result["status"], "LANES_APPROVED")
        self.assertIn(("RUNNING", "MASTER_APPROVED"), self.transitions(result, "a"))

    def test_scheduler_records_dependency_failure_to_skipped(self):
        first, second = self.source("first"), self.source("second")
        bad = [sys.executable, "-c", "raise SystemExit(3)"]
        _, result = self.run_campaign([self.lane("a", first, command=bad), self.lane("b", second, after=["a"])])
        self.assertEqual({lane["name"]: lane["status"] for lane in result["lanes"]},
                         {"a": "FAILED", "b": "SKIPPED"})
        self.assertIn(("QUEUED", "SKIPPED"), self.transitions(result, "b"))

    def test_scheduler_records_runner_error_to_failed(self):
        source = self.source("error")

        def broken(lane_ctx, run_id):
            raise RuntimeError("synthetic scheduler failure")

        _, result = self.run_campaign([self.lane("a", source)], runner=broken)
        self.assertEqual(result["lanes"][0]["status"], "FAILED")
        self.assertEqual(result["lanes"][0]["reason"], "lane_error")
        self.assertIn(("RUNNING", "FAILED"), self.transitions(result, "a"))

    def test_scheduler_records_timeout_to_timed_out(self):
        source = self.source("timeout")

        def timed_out(lane_ctx, run_id):
            raise ProcessStopped("timed_out")

        _, result = self.run_campaign([self.lane("a", source)], runner=timed_out)
        self.assertEqual(result["lanes"][0]["status"], "TIMED_OUT")
        self.assertEqual(result["lanes"][0]["reason"], "timed_out")
        self.assertIn(("RUNNING", "TIMED_OUT"), self.transitions(result, "a"))

    def test_scheduler_records_cancel_to_cancelled(self):
        first, second = self.source("cancel-a"), self.source("cancel-b")
        campaign_id, _ = campaign.create_campaign(self.ctx, self.spec(
            [self.lane("a", first), self.lane("b", second)], max_parallel=1))
        started = []

        def cancelling(lane_ctx, run_id):
            started.append(lane_ctx.data_root.name)
            campaign.cancel_campaign(self.ctx, campaign_id)
            return approve(lane_ctx, run_id)

        result = campaign.run_campaign(self.ctx, campaign_id, lane_runner=cancelling)
        self.assertEqual(started, ["a"])
        self.assertEqual(result["status"], "LANES_CANCELLED")
        self.assertEqual({lane["name"]: lane["status"] for lane in result["lanes"]},
                         {"a": "CANCELLED", "b": "CANCELLED"})
        self.assertIn(("RUNNING", "CANCELLED"), self.transitions(result, "a"))
        self.assertIn(("QUEUED", "CANCELLED"), self.transitions(result, "b"))

    def test_cancel_before_run_never_launches_the_final_master(self):
        source = self.source("cancel-before")
        final_marker = self.root / "final-ran.txt"
        spec = self.spec([self.lane("a", source)])
        spec["final"] = {"command": [sys.executable, "-c",
                                     "from pathlib import Path; Path(r'%s').write_text('ran')" % final_marker],
                         "timeout_seconds": 30}
        campaign_id, _ = campaign.create_campaign(self.ctx, spec)
        started = campaign.cancel_campaign(self.ctx, campaign_id)
        self.assertEqual(started["status"], "cancel_requested")

        result = campaign.run_campaign(self.ctx, campaign_id, lane_runner=approve)
        self.assertEqual(result["status"], "LANES_CANCELLED")
        self.assertEqual(result["lanes"][0]["status"], "CANCELLED")
        self.assertIn(("QUEUED", "CANCELLED"), self.transitions(result, "a"))
        self.assertFalse(final_marker.exists())

        again = campaign.cancel_campaign(self.ctx, campaign_id)
        self.assertEqual(again, {"campaign_id": campaign_id, "status": "LANES_CANCELLED", "already_finished": True})
        campaign.run_campaign(self.ctx, campaign_id, lane_runner=approve)
        self.assertFalse(final_marker.exists())

    def test_max_parallel_two_and_dependent_starts_after_approval(self):
        sources = [self.source(name) for name in ("parallel-a", "parallel-b", "parallel-c")]
        campaign_id, _ = campaign.create_campaign(self.ctx, self.spec(
            [self.lane("a", sources[0]), self.lane("b", sources[1]),
             self.lane("c", sources[2], after=["a"])], max_parallel=2))
        barrier = threading.Barrier(2, timeout=20)
        lock = threading.Lock()
        active = peak = 0

        def runner(lane_ctx, run_id):
            nonlocal active, peak
            name = lane_ctx.data_root.name
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                if name in {"a", "b"}:
                    barrier.wait()
                return approve(lane_ctx, run_id)
            finally:
                with lock:
                    active -= 1

        result = campaign.run_campaign(self.ctx, campaign_id, lane_runner=runner)
        self.assertEqual(peak, 2)
        self.assertEqual(result["status"], "LANES_APPROVED")
        states = [event for event in self.events(campaign_id) if event["event"] == "lane.state"]
        approved_a = next(index for index, event in enumerate(states)
                          if event.get("lane") == "a" and event.get("state") == "MASTER_APPROVED")
        started_c = next(index for index, event in enumerate(states)
                         if event.get("lane") == "c" and event.get("state") == "RUNNING")
        self.assertLess(approved_a, started_c)

    def test_overlapping_ownership_is_serialized_even_with_free_capacity(self):
        source = self.source("overlap")
        campaign_id, _ = campaign.create_campaign(self.ctx, self.spec(
            [self.lane("a", source), self.lane("b", source)], max_parallel=2))
        lock = threading.Lock()
        active = peak = 0

        def runner(lane_ctx, run_id):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                time.sleep(0.1)
                return approve(lane_ctx, run_id)
            finally:
                with lock:
                    active -= 1

        result = campaign.run_campaign(self.ctx, campaign_id, lane_runner=runner)
        self.assertEqual(peak, 1)
        self.assertEqual(result["status"], "LANES_APPROVED")

    def test_max_parallel_is_validated(self):
        source = self.source("validated")
        for value in (0, 9, True, "2"):
            with self.assertRaises(ValueError):
                campaign._spec(self.spec([self.lane("a", source)], max_parallel=value))


if __name__ == "__main__":
    unittest.main()
