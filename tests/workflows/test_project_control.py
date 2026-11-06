import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.evidence import load_signed, save_signed
from respected_orchestrator.engine.journal import Journal
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.local_api import LocalApi
from respected_orchestrator.workflows import project, project_control

PY = sys.executable
TOKEN = "t" * 32


class ProjectControlTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        self.source = self.root / "src"
        self.source.mkdir()
        (self.source / "f.txt").write_text("old\n")
        lane = {"name": "one", "after": [], "request": {
            "project_root": str(self.source), "task": "t", "worker": "custom", "kind": "write", "ownership": ["f.txt"],
            "command": [PY, "-c", "pass"], "acceptance": [[PY, "-c", "pass"]], "timeout_seconds": 30, "workflow": {"max_fix_rounds": 0}}}
        phase = {"name": "one", "after": [], "workstreams": [lane], "auto_apply": True,
                 "verify": [{"command": [PY, "-c", "pass"], "cwd": str(self.source)}]}
        self.pid, _ = project.create_project(self.ctx, dict(goal="demo", phases=[phase]))
        self.spawned = []

        def fake_spawn(ctx, project_id, directory, spec):
            self.spawned.append(project_id)
            save_signed(ctx, directory / "supervisor.json", dict(project_id=project_id, pid=os.getpid(), engine="x"))
            return os.getpid()
        patcher = mock.patch.object(project, "_spawn", fake_spawn)
        patcher.start()
        self.addCleanup(patcher.stop)

    def events(self):
        path = self.ctx.state_dir / "events.log"
        return [r for r in Journal(path).replay()] if path.exists() else []

    def test_status_explains_each_state_in_plain_words(self):
        created = project_control.status(self.ctx, self.pid)["explanation"]
        self.assertEqual((created["state"], created["retryable"], created["next_action"]), ("created", True, "resume"))
        self.assertIn("süpervizör yaşamıyor", created["summary"])
        for terminal in ("completed", "cancelled", "blocked"):
            state = load_signed(self.ctx, project.project_dir(self.ctx, self.pid) / "project.json")
            save_signed(self.ctx, project.project_dir(self.ctx, self.pid) / "project.json", {**state, "status": terminal})
            e = project_control.status(self.ctx, self.pid)["explanation"]
            self.assertEqual((e["state"], e["retryable"], e["next_action"]), (terminal, False, "none"))
        self.assertIn("Bilinmeyen", project_control.explain({"status": "levitating"})["summary"])
        self.assertEqual(project_control.explain({"status": "running", "alive": True})["next_action"], "wait")

    def test_cancel_is_idempotent_audited_once_and_refused_when_finished(self):
        first = project_control.cancel(self.ctx, self.pid, "op-cancel-0001")
        again = project_control.cancel(self.ctx, self.pid, "op-cancel-0002")
        self.assertEqual((first["repeat"], again["repeat"]), (False, True))
        self.assertEqual([e["type"] for e in self.events()], ["project.cancel_requested"])
        self.assertIn("İptal istendi", project_control.status(self.ctx, self.pid)["explanation"]["summary"])
        path = project.project_dir(self.ctx, self.pid) / "project.json"
        save_signed(self.ctx, path, {**load_signed(self.ctx, path), "status": "completed"})
        with self.assertRaisesRegex(ValueError, "nothing to cancel"):
            project_control.cancel(self.ctx, self.pid, "op-cancel-0003")

    def test_resume_moves_state_exactly_once(self):
        out = project_control.resume(self.ctx, self.pid, "op-resume-0001")
        self.assertEqual(out["status"], "resumed")
        with self.assertRaisesRegex(ValueError, "already running"):
            project_control.resume(self.ctx, self.pid, "op-resume-0002")
        self.assertEqual(self.spawned, [self.pid])  # one supervisor, not two
        self.assertEqual(len(self.events()), 1)
        self.assertTrue(project_control.status(self.ctx, self.pid)["explanation"]["alive"])

    def test_missing_role_starts_zero_workers(self):
        path = project.project_dir(self.ctx, self.pid) / "project.json"
        state = load_signed(self.ctx, path)
        state["spec"]["phases"][0]["workstreams"][0]["request"]["worker"] = "ghostcli"
        save_signed(self.ctx, path, state)
        with self.assertRaisesRegex(ValueError, "Role unavailable"):
            project_control.resume(self.ctx, self.pid, "op-resume-0003")
        self.assertEqual(self.spawned, [])
        self.assertEqual(self.events(), [])

    def test_stale_checkpoint_resume_is_refused_without_human_approval(self):
        (self.source / "f.txt").write_text("changed behind the project's back\n")
        with self.assertRaises(ValueError) as caught:
            project_control.resume(self.ctx, self.pid, "op-resume-0004")
        self.assertTrue(str(caught.exception))
        self.assertEqual(self.spawned, [])

    def test_bad_ids_and_unknown_projects_are_errors_not_crashes(self):
        for bad in ("../x", None, "proj-zzz-nope", 5):
            with self.assertRaises((ValueError, TypeError, OSError)):
                project_control.status(self.ctx, bad)


class ProjectIpcTests(unittest.TestCase):
    def setUp(self):
        ProjectControlTests.setUp(self)
        self.n = 0

    def call(self, origin, cmd, **payload):
        self.n += 1
        api = LocalApi(self.ctx, TOKEN, origin=origin)
        return api.handle({"ipc": "1", "id": f"proj-{self.n:05d}", "session": TOKEN, "cmd": cmd, "payload": payload})

    def test_create_start_cancel_resume_flow_over_typed_ipc(self):
        status = self.call(Origin.RENDERER, "project.status", project_id=self.pid)
        self.assertTrue(status["ok"], status)
        self.assertEqual(status["result"]["explanation"]["next_action"], "resume")
        resumed = self.call(Origin.RENDERER, "project.resume", project_id=self.pid)
        self.assertTrue(resumed["ok"], resumed)
        self.assertFalse(self.call(Origin.RENDERER, "project.resume", project_id=self.pid)["ok"])  # second click: no second supervisor
        cancelled = self.call(Origin.RENDERER, "project.cancel", project_id=self.pid)
        self.assertTrue(cancelled["ok"] and cancelled["result"]["repeat"] is False)
        self.assertEqual(self.spawned, [self.pid])

    def test_unauthorized_origins_change_nothing(self):
        for origin in (Origin.WORKER, Origin.CHILD):
            for cmd in ("project.cancel", "project.resume"):
                r = self.call(origin, cmd, project_id=self.pid)
                self.assertEqual(r["error"]["code"], "FORBIDDEN", (origin, cmd))
        self.assertFalse((project.project_dir(self.ctx, self.pid) / "cancel").exists())
        self.assertEqual(self.spawned, [])

    def test_errors_surface_as_engine_errors(self):
        r = self.call(Origin.RENDERER, "project.cancel", project_id="../../etc")
        self.assertEqual(r["error"]["code"], "ENGINE_ERROR")
        r = self.call(Origin.RENDERER, "project.status")
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
