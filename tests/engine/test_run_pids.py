"""Which runs are really being worked on right now (`supervisor.run_pids`), and what a run that is killed the hard way looks like afterwards."""
import subprocess
import sys
import time
from pathlib import Path

from respected_orchestrator.engine import supervisor
from respected_orchestrator.engine.runner import apply_task, create_task, effective_status, inspect_task, start_task
from tests.workflows.test_reviewer_reliability import CodingFixture

PY = sys.executable


class RunningWorkTests(CodingFixture):
    def slow_request(self, seconds=6):
        request = self.request()
        code = (f"import time; from pathlib import Path; time.sleep({seconds}); Path('calculator.py').write_text('value = 1' + chr(10))")
        request["command"] = [PY, "-c", code]
        request["timeout_seconds"] = 60
        return request

    def wait_for(self, run_id, states, seconds=60):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            status = effective_status(self.ctx, self.ctx.run_dir(run_id))["status"]
            if status in states:
                return status
            time.sleep(0.3)
        return status

    def wait_until_files_are_free(self, directory, seconds=15):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                for path in Path(directory).glob("*.log"):
                    path.rename(path.with_suffix(path.suffix + ".probe")); path.with_suffix(path.suffix + ".probe").rename(path)
                return
            except OSError:
                time.sleep(0.3)

    def wait_running(self, run_id):
        end = time.monotonic() + 30
        while time.monotonic() < end:
            if run_id in supervisor.run_pids(self.ctx):
                return True
            time.sleep(0.2)
        return False

    def test_the_desktop_sees_a_really_running_run_as_active(self):
        """Regression: `runs.active` only read supervisor claims that nothing wrote, so the "work is running" notice never appeared for real runs."""
        from respected_orchestrator.engine.local_api import LocalApi
        run_id = create_task(self.ctx, self.slow_request(6))["run_id"]
        start_task(self.ctx, run_id)
        self.assertTrue(self.wait_running(run_id))
        api = LocalApi(self.ctx, "t" * 32)
        reply = api.handle({"ipc": "1", "id": "act-00001", "session": "t" * 32, "cmd": "runs.active", "payload": {}})
        self.assertEqual(list(reply["result"]["runs"]), [run_id])
        self.assertEqual(self.wait_for(run_id, {"completed", "failed"}), "completed")
        reply = api.handle({"ipc": "1", "id": "act-00002", "session": "t" * 32, "cmd": "runs.active", "payload": {}})
        self.assertEqual(reply["result"]["runs"], {})  # and it is gone once finished

    def test_killing_a_running_run_the_hard_way_leaves_it_interrupted_and_never_applied(self):
        run_id = create_task(self.ctx, self.slow_request(20))["run_id"]
        start_task(self.ctx, run_id)
        self.assertTrue(self.wait_running(run_id))
        pid = supervisor.run_pids(self.ctx)[run_id]
        self.addCleanup(self.wait_until_files_are_free, self.ctx.run_dir(run_id))  # a killed process releases its handles a moment later
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)  # an update's force stop / a power cut
        self.assertEqual(self.wait_for(run_id, {"interrupted", "failed", "completed"}, 30), "interrupted")
        self.assertNotIn(run_id, supervisor.run_pids(self.ctx))
        self.assertEqual(inspect_task(self.ctx, run_id)["status"], "interrupted")  # an honest status, not "queued" or "completed"
        with self.assertRaisesRegex(ValueError, "Unsuccessful or pending"):
            apply_task(self.ctx, run_id)  # an uncertain run is never applied on its own
        self.assertFalse((self.ctx.run_dir(run_id) / "applied.json").exists())
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")  # the project was not touched
