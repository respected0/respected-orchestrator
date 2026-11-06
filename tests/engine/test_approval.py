import io
import json
import threading
import time
import unittest
from unittest import mock

from respected_orchestrator.engine import approval, local_api
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.local_api import LocalApi
from respected_orchestrator.engine.runner import create_task, execute_task
from tests.workflows.test_reviewer_reliability import CodingFixture

TOKEN = "t" * 32
NEW, OLD = "value = 1\n", "value = 0\n"


class ApprovalTests(CodingFixture):
    def executed(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        self.assertEqual(execute_task(self.ctx, run_id)["status"], "completed")
        return run_id

    def source(self):
        return (self.repo / "calculator.py").read_text(encoding="utf8")

    def opened(self, run_id=None):
        return approval.open_challenge(self.ctx, run_id or self.executed(), origin=Origin.RENDERER)

    def approved(self):
        c = self.opened()
        g = approval.decide(self.ctx, c["challenge_id"], "approve", c["binding"], origin=Origin.HUMAN)
        return c, g

    def test_the_one_legitimate_path_applies_exactly_once(self):
        c, g = self.approved()
        self.assertEqual(g["state"], "granted")
        self.assertEqual(self.source(), OLD)  # a decision alone changes nothing
        out = approval.apply_with_grant(self.ctx, g["token"], c["run_id"], origin=Origin.HUMAN)
        self.assertEqual(out["status"], "applied")
        self.assertEqual(self.source(), NEW)
        with self.assertRaisesRegex(ValueError, "already used"):
            approval.apply_with_grant(self.ctx, g["token"], c["run_id"], origin=Origin.HUMAN)

    def test_only_the_human_origin_can_decide_or_apply(self):
        c = self.opened()
        for origin in (Origin.RENDERER, Origin.MCP, Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError, msg=origin):
                approval.decide(self.ctx, c["challenge_id"], "approve", c["binding"], origin=origin)
            with self.assertRaises(PermissionError, msg=origin):
                approval.apply_with_grant(self.ctx, "a" * 64, c["run_id"], origin=origin)
        with self.assertRaises(PermissionError):
            approval.open_challenge(self.ctx, c["run_id"], origin=Origin.WORKER)
        self.assertEqual(list(self.ctx.data_root.glob("approvals/*.decided")), [])  # the challenge is still undecided
        self.assertEqual(self.source(), OLD)

    def test_ipc_renderer_and_mcp_may_ask_but_never_decide(self):
        run_id = self.executed()
        n = [0]

        def call(origin, cmd, **payload):
            n[0] += 1
            return LocalApi(self.ctx, TOKEN, origin=origin).handle(
                {"ipc": "1", "id": f"apr-{n[0]:05d}", "session": TOKEN, "cmd": cmd, "payload": payload})
        for origin in (Origin.RENDERER, Origin.MCP):
            asked = call(origin, "approval.open", run_id=run_id)
            self.assertTrue(asked["ok"], asked)
            c = asked["result"]
            for cmd, extra in (("approval.decide", {"challenge_id": c["challenge_id"], "decision": "approve", "binding": c["binding"]}),
                               ("approval.apply", {"token": "b" * 64, "run_id": run_id})):
                self.assertEqual(call(origin, cmd, **extra)["error"]["code"], "FORBIDDEN", (origin, cmd))
        self.assertEqual(self.source(), OLD)

    def test_human_connection_exposes_only_its_own_commands_and_children_are_never_human(self):
        c = self.opened()
        decide = {"ipc": "1", "id": "hum-00001", "session": TOKEN, "cmd": "approval.decide",
                  "payload": {"challenge_id": c["challenge_id"], "decision": "deny", "binding": c["binding"]}}
        other = {"ipc": "1", "id": "hum-00002", "session": TOKEN, "cmd": "plan.start", "payload": {}}
        out = io.StringIO()
        local_api.serve(self.ctx, io.StringIO(json.dumps(other) + "\n"), out, {"RESPECTED_IPC_TOKEN": TOKEN}, human=True)
        self.assertEqual(json.loads(out.getvalue())["error"]["code"], "FORBIDDEN")
        out = io.StringIO()
        local_api.serve(self.ctx, io.StringIO(json.dumps(decide) + "\n"), out, {"RESPECTED_IPC_TOKEN": TOKEN, "RESPECTED_ORCH_CHILD": "1"}, human=True)
        self.assertEqual(json.loads(out.getvalue())["error"]["code"], "FORBIDDEN")  # orchestrated process claiming to be the human
        out = io.StringIO()
        local_api.serve(self.ctx, io.StringIO(json.dumps(decide) + "\n"), out, {"RESPECTED_IPC_TOKEN": TOKEN}, human=True)
        self.assertEqual(json.loads(out.getvalue())["result"]["state"], "denied")

    def test_not_approvable_runs_never_get_a_challenge(self):
        run_id = self.executed()
        (self.ctx.run_dir(run_id) / "worker.patch").write_text("tampered\n", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "not approvable"):
            approval.open_challenge(self.ctx, run_id, origin=Origin.RENDERER)
        self.assertEqual(list(self.ctx.data_root.glob("approvals/*")), [])

    def test_denial_has_no_side_effect_and_cannot_be_turned_into_an_approval(self):
        c = self.opened()
        self.assertEqual(approval.decide(self.ctx, c["challenge_id"], "deny", c["binding"], origin=Origin.HUMAN)["state"], "denied")
        with self.assertRaisesRegex(ValueError, "already decided"):
            approval.decide(self.ctx, c["challenge_id"], "approve", c["binding"], origin=Origin.HUMAN)
        self.assertEqual(list(self.ctx.data_root.glob("approvals/grant-*")), [])
        self.assertEqual(self.source(), OLD)

    def test_a_decision_about_something_else_is_refused_and_burns_the_challenge(self):
        c, other = self.opened(), self.opened()
        with self.assertRaisesRegex(ValueError, "not about this run"):
            approval.decide(self.ctx, c["challenge_id"], "approve", other["binding"], origin=Origin.HUMAN)  # wrong window
        with self.assertRaisesRegex(ValueError, "already decided"):
            approval.decide(self.ctx, c["challenge_id"], "approve", c["binding"], origin=Origin.HUMAN)
        for bad in ("../x", "chal-zz", None, "chal-" + "0" * 16 + "x"):
            with self.assertRaises(ValueError):
                approval.decide(self.ctx, bad, "approve", "x", origin=Origin.HUMAN)
        with self.assertRaises(ValueError):
            approval.decide(self.ctx, other["challenge_id"], "maybe", other["binding"], origin=Origin.HUMAN)
        self.assertEqual(list(self.ctx.data_root.glob("approvals/grant-*")), [])

    def test_patch_or_project_changing_while_the_dialog_is_open_grants_nothing(self):
        c = self.opened()
        (self.repo / "calculator.py").write_text("value = 99\n", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "changed since it was shown"):
            approval.decide(self.ctx, c["challenge_id"], "approve", c["binding"], origin=Origin.HUMAN)
        self.assertEqual(list(self.ctx.data_root.glob("approvals/grant-*")), [])
        self.assertEqual(self.source(), "value = 99\n")

    def test_changes_between_decision_and_apply_apply_nothing(self):
        c, g = self.approved()
        (self.repo / "calculator.py").write_text("value = 5\n", encoding="utf8")
        with self.assertRaisesRegex(ValueError, "approve again"):
            approval.apply_with_grant(self.ctx, g["token"], c["run_id"], origin=Origin.HUMAN)
        self.assertEqual(self.source(), "value = 5\n")
        self.assertFalse((self.ctx.run_dir(c["run_id"]) / "applied.json").exists())

    def test_expired_challenge_and_expired_grant_are_dead(self):
        c = self.opened()
        with mock.patch.object(approval.time, "time", return_value=time.time() + approval.TTL_SECONDS + 5):
            with self.assertRaisesRegex(ValueError, "expired"):
                approval.decide(self.ctx, c["challenge_id"], "approve", c["binding"], origin=Origin.HUMAN)
        c, g = self.approved()
        with mock.patch.object(approval.time, "time", return_value=time.time() + approval.TTL_SECONDS + 5):
            with self.assertRaisesRegex(ValueError, "expired"):
                approval.apply_with_grant(self.ctx, g["token"], c["run_id"], origin=Origin.HUMAN)
        self.assertEqual(self.source(), OLD)

    def test_token_is_bound_to_its_run_and_forged_tokens_are_unknown(self):
        c, g = self.approved()
        other = self.executed()
        with self.assertRaisesRegex(ValueError, "another run"):
            approval.apply_with_grant(self.ctx, g["token"], other, origin=Origin.HUMAN)
        for forged in ("0" * 64, "f" * 64, "short", None, g["token"].upper()):
            with self.assertRaises(ValueError):
                approval.apply_with_grant(self.ctx, forged, c["run_id"], origin=Origin.HUMAN)
        self.assertEqual(self.source(), OLD)

    def test_concurrent_decisions_have_exactly_one_winner(self):
        c = self.opened()
        wins, losses = [], []

        def go():
            try:
                wins.append(approval.decide(self.ctx, c["challenge_id"], "approve", c["binding"], origin=Origin.HUMAN))
            except ValueError:
                losses.append(1)
        threads = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual((len(wins), len(losses)), (1, 7))
        self.assertEqual(len(list(self.ctx.data_root.glob("approvals/grant-*.json"))), 1)

    def test_concurrent_applies_with_one_token_apply_once(self):
        c, g = self.approved()
        outcomes = []

        def go():
            try:
                outcomes.append(approval.apply_with_grant(self.ctx, g["token"], c["run_id"], origin=Origin.HUMAN)["status"])
            except ValueError:
                outcomes.append("refused")
        threads = [threading.Thread(target=go) for _ in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(outcomes), ["applied"] + ["refused"] * 5)
        self.assertEqual(self.source(), NEW)

    def test_the_token_is_never_stored_and_a_crash_before_apply_never_applies(self):
        c, g = self.approved()
        stored = "".join(p.read_text(encoding="utf8") for p in (self.ctx.data_root / "approvals").iterdir() if p.is_file())
        self.assertNotIn(g["token"], stored)
        self.assertEqual(self.source(), OLD)  # nothing applies on its own: the grant just waits (and expires)


if __name__ == "__main__":
    unittest.main()
