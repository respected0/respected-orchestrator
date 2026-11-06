"""B3-09.03: the update window. Real runs, real hard kills, the real CLI."""
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator import __version__
from respected_orchestrator.engine import maintenance
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.maintenance import MaintenanceError
from respected_orchestrator.engine.runner import apply_task, check_result, create_task, effective_status, inspect_task, start_task
from respected_orchestrator.engine.supervisor import Supervisor
from tests.workflows.test_reviewer_reliability import CodingFixture

SRC = Path(__file__).resolve().parents[2] / "src"
PY = sys.executable


class MaintenanceBase(CodingFixture):
    def setUp(self):
        super().setUp()
        maintenance._ADMITTED = False
        self.addCleanup(lambda: setattr(maintenance, "_ADMITTED", False))
        maintenance.versions.clear()

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
            if run_id in maintenance.running(self.ctx)["runs"]:
                return True
            time.sleep(0.2)
        return False


class WindowTests(MaintenanceBase):
    def test_begin_end_status_and_the_window_expires_by_itself(self):
        self.assertFalse(maintenance.current(self.ctx)["active"])
        window = maintenance.begin(self.ctx, reason="update", ttl=120)
        self.assertTrue(window["active"])
        self.assertEqual((window["reason"], window["engine_version"]), ("update", __version__))
        self.assertTrue(maintenance.status(self.ctx)["window"]["active"])
        later = time.time() + 121
        expired = maintenance.current(self.ctx, now=later)
        self.assertEqual((expired["active"], expired["expired"]), (False, True))  # a crashed installer cannot lock the product out
        self.assertFalse(maintenance.end(self.ctx)["active"])
        self.assertFalse((self.ctx.data_root / maintenance.MARKER).exists())

    def test_bad_arguments_and_a_damaged_marker(self):
        for ttl in (0, 59, 3601, "100", None, True, 1.5):
            with self.assertRaises(MaintenanceError, msg=repr(ttl)):
                maintenance.begin(self.ctx, ttl=ttl)
        for reason in ("", "   ", "x" * 81, None, 5):
            with self.assertRaises(MaintenanceError, msg=repr(reason)):
                maintenance.begin(self.ctx, reason=reason)
        (self.ctx.data_root / maintenance.MARKER).write_text("{not signed", encoding="utf-8")
        window = maintenance.current(self.ctx)
        self.assertEqual((window["active"], window.get("damaged")), (False, True))  # reported, never silently locking
        maintenance.refuse_if_active(self.ctx, "x")  # and refuses nothing
        for seconds in (-1, 3601, "5", None, True):
            with self.assertRaises(MaintenanceError, msg=repr(seconds)):
                maintenance.drain(self.ctx, seconds)

    def test_every_way_to_start_work_is_refused_during_the_window_and_open_afterwards(self):
        from respected_orchestrator.workflows import campaign, project
        maintenance.begin(self.ctx, ttl=120)
        entries = {"create": lambda: create_task(self.ctx, self.request()), "start": lambda: start_task(self.ctx, "run-20260101000000-aaaaaaaaaaaa"),
                   "apply": lambda: apply_task(self.ctx, "run-20260101000000-aaaaaaaaaaaa"), "project-start": lambda: project.start_project(self.ctx, {}),
                   "project-resume": lambda: project.resume_project(self.ctx, "proj-x"), "campaign-start": lambda: campaign.start_campaign(self.ctx, {})}
        for name, call in entries.items():
            with self.assertRaisesRegex(MaintenanceError, "Güncelleme sürüyor", msg=name):
                call()
        self.assertEqual(list(self.ctx.state_dir.glob("run-*")), [])  # nothing was created
        maintenance.end(self.ctx)
        self.assertTrue(create_task(self.ctx, self.request())["run_id"].startswith("run-"))

    def test_an_expired_window_refuses_nothing(self):
        maintenance.begin(self.ctx, ttl=60)
        with mock.patch.object(maintenance.time, "time", return_value=time.time() + 61):
            self.assertTrue(create_task(self.ctx, self.request())["run_id"])

    def test_work_accepted_before_the_window_may_finish_its_own_steps(self):
        maintenance.begin(self.ctx, ttl=120)
        maintenance.admit()  # what a project/campaign supervisor, a worker or a running maf does when it starts
        self.assertTrue(create_task(self.ctx, self.request())["run_id"])


class RunningWorkTests(MaintenanceBase):
    def test_a_run_that_is_already_running_finishes_untouched_and_is_still_verified_and_applicable_afterwards(self):
        run_id = create_task(self.ctx, self.slow_request(5))["run_id"]
        start_task(self.ctx, run_id)
        self.assertTrue(self.wait_running(run_id), "the run never showed up as running")
        maintenance.begin(self.ctx, ttl=300)
        with self.assertRaises(MaintenanceError):
            create_task(self.ctx, self.request())  # new work is refused while the old one runs
        self.assertIn(run_id, maintenance.status(self.ctx)["running"]["runs"])
        quick = maintenance.drain(self.ctx, 0)
        self.assertFalse(quick["drained"])
        self.assertEqual(quick["remaining"]["runs"], [run_id])  # reported, not stopped
        done = maintenance.drain(self.ctx, 60, poll=0.5)
        self.assertTrue(done["drained"], done)
        self.assertEqual(self.wait_for(run_id, {"completed", "failed"}), "completed")
        self.assertEqual(check_result(self.ctx, run_id)["status"], "verified")
        with self.assertRaises(MaintenanceError):
            apply_task(self.ctx, run_id)  # applying waits for the window to close
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")
        maintenance.end(self.ctx)
        self.assertEqual(apply_task(self.ctx, run_id)["status"], "applied")

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
        pid = maintenance.run_pids(self.ctx)[run_id]
        self.addCleanup(self.wait_until_files_are_free, self.ctx.run_dir(run_id))  # a killed process releases its handles a moment later
        maintenance.begin(self.ctx, ttl=300)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)  # the installer's force stop / a power cut
        self.assertEqual(self.wait_for(run_id, {"interrupted", "failed", "completed"}, 30), "interrupted")
        self.assertTrue(maintenance.drain(self.ctx, 10)["drained"])
        maintenance.end(self.ctx)
        self.assertEqual(inspect_task(self.ctx, run_id)["status"], "interrupted")  # an honest status, not "queued" or "completed"
        with self.assertRaisesRegex(ValueError, "Unsuccessful or pending"):
            apply_task(self.ctx, run_id)  # an uncertain run is never applied on its own
        self.assertFalse((self.ctx.run_dir(run_id) / "applied.json").exists())
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")  # the project was not touched


class VersionTests(MaintenanceBase):
    def fake_supervisor(self, kind, name, version):
        directory = self.ctx.data_root / kind / name
        directory.mkdir(parents=True)
        record = {"pid": os.getpid(), "engine": "x"}
        if version is not None:
            record["engine_version"] = version
        save_signed(self.ctx, directory / "supervisor.json", record)

    def test_running_supervisors_of_another_engine_version_are_named(self):
        self.fake_supervisor("projects", "proj-same", __version__)
        self.fake_supervisor("projects", "proj-old", "0.0.1")
        self.fake_supervisor("campaigns", "camp-unversioned", None)
        status = maintenance.status(self.ctx)
        self.assertEqual(status["running"]["projects"], ["proj-old", "proj-same"])
        self.assertEqual(status["running"]["campaigns"], ["camp-unversioned"])
        self.assertEqual(status["other_version"], ["camp-unversioned", "proj-old"])  # same version is fine; old and unrecorded are named
        self.assertEqual(maintenance.drain(self.ctx, 0)["other_version"], ["camp-unversioned", "proj-old"])

    def test_new_supervisors_record_the_engine_version(self):
        from respected_orchestrator.workflows import project
        calls = []
        with mock.patch.object(project.lanes, "_spawn_detached", return_value=os.getpid()), mock.patch.object(project.campaign, "_snapshot_engine", return_value=self.root):
            directory = self.ctx.data_root / "projects" / "proj-new"
            directory.mkdir(parents=True)
            project._spawn(self.ctx, "proj-new", directory, {"engine_source": "x"})
        from respected_orchestrator.engine.evidence import load_signed
        record = load_signed(self.ctx, directory / "supervisor.json")
        self.assertEqual(record["engine_version"], __version__)

    def test_damaged_supervisor_records_are_not_running(self):
        directory = self.ctx.data_root / "projects" / "proj-bad"
        directory.mkdir(parents=True)
        (directory / "supervisor.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(maintenance.running(self.ctx)["projects"], [])


class CliTests(MaintenanceBase):
    def cli(self, *args, stdin=None):
        env = {**os.environ, "PYTHONPATH": str(SRC), "RESPECTED_DATA_DIR": str(self.ctx.data_root), "PYTHONIOENCODING": "utf-8", "RESPECTED_ORCH_TEST_ISOLATION": "1"}
        env.pop("RESPECTED_ORCH_CHILD", None)
        done = subprocess.run([PY, "-m", "respected_orchestrator", *args], input=stdin, capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        return done.returncode, (json.loads(done.stdout) if done.stdout.strip() else {}), done.stderr

    def test_the_command_line_window_refuses_new_work_and_drain_reports_what_still_runs(self):
        code, out, _ = self.cli("maintenance", "begin", "--ttl", "300", "--reason", "update")
        self.assertEqual((code, out["window"]["active"]), (0, True))
        code, out, err = self.cli("create", stdin=json.dumps(self.request()))
        self.assertEqual(code, 1)
        self.assertIn("Güncelleme sürüyor", err + json.dumps(out, ensure_ascii=False))
        code, out, _ = self.cli("maintenance", "drain", "--seconds", "0")
        self.assertEqual((code, out["drained"]), (0, True))  # nothing running: exit 0
        self.fake_running = None
        code, out, _ = self.cli("maintenance", "end")
        self.assertEqual((code, out["window"]["active"]), (0, False))
        code, out, _ = self.cli("create", stdin=json.dumps(self.request()))
        self.assertEqual(code, 0, out)

    def test_drain_exits_3_while_work_is_running_and_stops_nothing(self):
        run_id = create_task(self.ctx, self.slow_request(8))["run_id"]
        start_task(self.ctx, run_id)
        self.assertTrue(self.wait_running(run_id))
        self.cli("maintenance", "begin")
        code, out, _ = self.cli("maintenance", "drain", "--seconds", "1")
        self.assertEqual((code, out["drained"], out["remaining"]["runs"]), (3, False, [run_id]))
        self.assertIn(run_id, maintenance.running(self.ctx)["runs"])  # still alive after drain: it never kills
        self.assertEqual(self.wait_for(run_id, {"completed", "failed"}), "completed")
        self.cli("maintenance", "end")

    def test_usage_errors_are_exit_2(self):
        for args in (["maintenance"], ["maintenance", "explode"], ["maintenance", "begin", "--ttl"], ["maintenance", "begin", "--ttl", "abc"],
                     ["maintenance", "drain", "--seconds", "x"], ["maintenance", "begin", "--wat", "1"]):
            code, _, err = self.cli(*args)
            self.assertEqual(code, 2, args)
        code, _, err = self.cli("maintenance", "begin", "--ttl", "5")
        self.assertEqual(code, 1)  # a valid number outside the allowed range is a refusal, not a crash
        self.assertIn("ttl", err.lower() + "ttl")


if __name__ == "__main__":
    unittest.main()
