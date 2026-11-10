import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import catalog, daemon, runner
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.local_api import LocalApi

TOKEN = "t" * 32
RUN = "run-20261110120000-aaaaaaaaaaaa"
READ_TASK = {"project_root": "C:/p", "task": "oku", "kind": "read", "ownership": ["."]}


class TaskApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ctx = EngineContext(Path(tmp.name).resolve() / "data")
        self.n = 0

    def call(self, cmd, payload, origin=Origin.RENDERER):
        self.n += 1
        api = LocalApi(self.ctx, TOKEN, origin=origin, only=daemon.SERVED_DESKTOP if origin is Origin.RENDERER else daemon.SERVED)
        return api.handle({"ipc": "1", "id": f"task-{self.n:06d}", "session": TOKEN, "cmd": cmd, "payload": payload})

    def started(self):
        return (mock.patch.object(runner, "create_task", return_value={"run_id": RUN, "status": "queued"}),
                mock.patch.object(runner, "start_task", return_value={"run_id": RUN, "status": "queued", "pid": 7}))

    def test_start_creates_and_starts_one_run_through_the_runner(self):
        create, start = self.started()
        with create as made, start as begun:
            reply = self.call("task.start", READ_TASK)
        self.assertEqual(reply["result"], {"run_id": RUN, "status": "queued", "pid": 7})
        made.assert_called_once_with(self.ctx, READ_TASK)
        begun.assert_called_once_with(self.ctx, RUN)

    def test_only_the_operator_may_pick_a_custom_worker_or_an_unlisted_check(self):
        refused = ({**READ_TASK, "worker": "custom", "command": ["x"]}, {**READ_TASK, "apply_root": "C:/x"},
                   {**READ_TASK, "kind": "write", "acceptance": [["python", "-c", "x"]]})
        for origin in (Origin.RENDERER, Origin.MCP):
            for payload in refused:
                create, start = self.started()
                with create as made, start:
                    reply = self.call("task.start", payload, origin)
                self.assertEqual(reply["error"]["code"], "ENGINE_ERROR", (origin, payload))
                made.assert_not_called()
        create, start = self.started()
        with create as made, start:
            self.assertTrue(self.call("task.start", refused[0], Origin.HUMAN)["ok"])
        made.assert_called_once()

    def test_a_worker_or_its_descendant_starts_nothing(self):
        for origin in (Origin.WORKER, Origin.CHILD):
            create, start = self.started()
            with create as made, start:
                for cmd, payload in (("task.start", READ_TASK), ("task.status", {"run_id": RUN}), ("task.cancel", {"run_id": RUN})):
                    self.assertEqual(self.call(cmd, payload, origin)["error"]["code"], "FORBIDDEN", (origin, cmd))
            made.assert_not_called()

    def test_status_cancel_and_retry_take_a_run_identity_and_status_is_trimmed(self):
        for cmd in ("task.status", "task.cancel", "task.retry"):
            for bad in ({}, {"run_id": "../../etc"}, {"run_id": 7}, {"run_id": "proj-abc"}):
                self.assertEqual(self.call(cmd, bad)["error"]["code"], "BAD_REQUEST", (cmd, bad))
        with mock.patch.object(runner, "inspect_task", return_value={"status": "done", "logs": {"worker": "x" * 9000}, "patch_preview": "p" * 9000}):
            seen = self.call("task.status", {"run_id": RUN})["result"]
        self.assertEqual((seen["status"], len(seen["logs"]["worker"]), len(seen["patch_preview"])), ("done", 3000, 3000))
        with mock.patch.object(runner, "cancel_task", return_value={"run_id": RUN, "status": "cancelled"}) as cancel:
            self.assertEqual(self.call("task.cancel", {"run_id": RUN})["result"]["status"], "cancelled")
        cancel.assert_called_once_with(self.ctx, RUN)
        create, start = self.started()
        with mock.patch.object(runner, "retry_task", return_value={"run_id": RUN}), start as begun:
            self.assertEqual(self.call("task.retry", {"run_id": RUN})["result"]["pid"], 7)
        begun.assert_called_once_with(self.ctx, RUN)
        self.assertEqual(self.call("task.status", {"run_id": RUN})["error"]["message"], "Unknown run.")  # no path of the data folder
        with mock.patch.object(runner, "retry_task", side_effect=ValueError("Only failed runs can be retried")):
            self.assertEqual(self.call("task.retry", {"run_id": RUN})["error"]["code"], "ENGINE_ERROR")

    def test_the_cli_and_the_desktop_reach_the_same_four_commands(self):
        names = ["task.start", "task.status", "task.cancel", "task.retry"]
        self.assertEqual(catalog.desktop("task"), names)
        self.assertEqual([catalog.CLI[("task", verb)].name for verb in ("start", "status", "cancel", "retry")], names)
        self.assertEqual(catalog.CLI[("session", "start")].name, "session.start")  # the same verb under another command is another entry


if __name__ == "__main__":
    unittest.main()
