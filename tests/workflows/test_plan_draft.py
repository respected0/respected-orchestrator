import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.workflows import plan_draft as pd

ROOT = str(Path(tempfile.gettempdir()).resolve())


def lane(name, own, after=None):
    return {"name": name, "after": after or [], "request": {"project_root": ROOT, "task": "t", "kind": "write", "ownership": own,
                                                            "acceptance": [["python", "-c", "pass"]]}}


def spec():
    return {"goal": "g", "phases": [{"name": "a", "after": [], "workstreams": [lane("x", ["a.py"]), lane("y", ["b.py"])]},
                                    {"name": "b", "after": ["a"], "workstreams": [lane("z", ["c.py"])]}]}


class PlanDraftTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ctx = EngineContext(Path(tmp.name).resolve() / "data")
        self.settings = {}

    def create(self, s=None):
        return pd.create_draft(self.ctx, s or spec(), ROOT, self.settings)

    def edit(self, draft, edits, revision=None):
        return pd.edit_draft(self.ctx, draft["draft_id"], draft["revision"] if revision is None else revision, edits, self.settings)

    def test_valid_edit_makes_a_new_revision_with_a_new_hash(self):
        d = self.create()
        self.assertTrue(d["valid"], d["problem"])
        self.assertEqual(d["revision"], 1)
        e = self.edit(d, [{"op": "set_lane", "phase": "a", "lane": "x", "field": "task", "value": "better task"}])
        self.assertEqual((e["revision"], e["valid"]), (2, True))
        self.assertNotEqual(e["spec_hash"], d["spec_hash"])
        self.assertEqual(pd.get_draft(self.ctx, d["draft_id"])["spec"]["phases"][0]["workstreams"][0]["request"]["task"], "better task")

    def test_invalid_edits_are_kept_for_fixing_but_marked_invalid_with_the_engine_reason(self):
        cases = {
            "cycle": [{"op": "set_phase_after", "phase": "a", "value": ["b"]}],
            "collision": [{"op": "set_lane", "phase": "a", "lane": "y", "field": "ownership", "value": ["a.py"]}],
            "unknown dep": [{"op": "set_lane", "phase": "a", "lane": "y", "field": "after", "value": ["ghost"]}],
            "id collision": [{"op": "rename_lane", "phase": "a", "lane": "y", "to": "x"}],
            "bad slug": [{"op": "rename_lane", "phase": "a", "lane": "y", "to": "NOT A SLUG"}],
            "role unavailable": [{"op": "set_lane", "phase": "a", "lane": "x", "field": "worker", "value": "nonexistent-agent"}],
            "no ownership": [{"op": "set_lane", "phase": "a", "lane": "y", "field": "ownership", "value": []}],
        }
        for name, edits in cases.items():
            d = self.create()
            e = self.edit(d, edits)
            self.assertFalse(e["valid"], name)
            self.assertTrue(e["problem"], name)
            self.assertEqual(e["revision"], 2, name)
        self.assertIn("Role unavailable", self.edit(self.create(), cases["role unavailable"])["problem"])

    def test_malformed_edits_are_caller_errors_and_save_nothing(self):
        d = self.create()
        bad = [[], "x", [{"op": "drop_table"}], [{"op": "set_lane", "phase": "nope", "lane": "x", "field": "task", "value": "v"}],
               [{"op": "set_lane", "phase": "a", "lane": "zzz", "field": "task", "value": "v"}],
               [{"op": "set_lane", "phase": "a", "lane": "x", "field": "shell", "value": "rm -rf"}],
               [{"op": "set_lane", "phase": "a", "lane": "x", "field": "task"}],
               [{"op": "set_phase_after", "phase": "a", "value": "b"}], [{"op": "rename_lane", "phase": "a", "lane": "x", "to": 5}],
               [{"op": "set_phase_after", "phase": "a", "value": []}] * (pd.MAX_EDITS + 1)]
        for edits in bad:
            with self.assertRaises(ValueError, msg=str(edits)[:60]):
                self.edit(d, edits)
        self.assertEqual(pd.get_draft(self.ctx, d["draft_id"])["revision"], 1)

    def test_authority_keys_in_a_speculative_plan_make_it_invalid(self):
        s = spec()
        s["phases"][0]["auto_apply"] = True
        self.assertFalse(self.create(s)["valid"])
        s = spec()
        s["phases"][0]["workstreams"][0]["request"]["command"] = ["rm", "-rf", "/"]
        self.assertFalse(self.create(s)["valid"])

    def test_stale_revision_is_refused_and_concurrent_edits_have_exactly_one_winner(self):
        d = self.create()
        self.edit(d, [{"op": "set_lane", "phase": "a", "lane": "x", "field": "task", "value": "one"}])
        with self.assertRaises(pd.StaleRevision):
            self.edit(d, [{"op": "set_lane", "phase": "a", "lane": "x", "field": "task", "value": "two"}], revision=1)
        d = self.create()
        results, errors = [], []

        def go(n):
            try:
                results.append(self.edit(d, [{"op": "set_lane", "phase": "a", "lane": "x", "field": "task", "value": f"v{n}"}]))
            except pd.StaleRevision:
                errors.append(n)
        threads = [threading.Thread(target=go, args=(n,)) for n in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual((len(results), len(errors)), (1, 5))
        self.assertEqual(pd.get_draft(self.ctx, d["draft_id"])["revision"], 2)

    def test_invalid_or_stale_or_unconfirmed_plans_start_zero_workers(self):
        launch = mock.Mock()
        d = self.create()
        bad = self.edit(d, [{"op": "set_phase_after", "phase": "a", "value": ["b"]}])
        with self.assertRaises(pd.NotStartable):
            pd.start_draft(self.ctx, d["draft_id"], bad["revision"], bad["spec_hash"], origin=Origin.HUMAN, start=launch)
        with self.assertRaises(pd.StaleRevision):
            pd.start_draft(self.ctx, d["draft_id"], 1, d["spec_hash"], origin=Origin.HUMAN, start=launch)
        good = self.create()
        with self.assertRaises(pd.NotStartable):  # hash not typed back / wrong plan
            pd.start_draft(self.ctx, good["draft_id"], good["revision"], bad["spec_hash"], origin=Origin.HUMAN, start=launch)
        for origin in (Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                pd.start_draft(self.ctx, good["draft_id"], good["revision"], good["spec_hash"], origin=origin, start=launch)
        launch.assert_not_called()
        self.assertFalse(list(self.ctx.data_root.rglob("run-*")) or list((self.ctx.data_root / "projects").glob("*")))

    def test_start_is_exactly_once_and_freezes_the_draft(self):
        launch = mock.Mock(return_value={"project_id": "proj-x", "status": "started"})
        d = self.create()
        out = pd.start_draft(self.ctx, d["draft_id"], d["revision"], d["spec_hash"], origin=Origin.RENDERER, start=launch)
        self.assertTrue(out["started"])
        launch.assert_called_once_with(self.ctx, pd.get_draft(self.ctx, d["draft_id"])["spec"])
        with self.assertRaises(pd.NotStartable):
            pd.start_draft(self.ctx, d["draft_id"], d["revision"], d["spec_hash"], origin=Origin.HUMAN, start=launch)
        with self.assertRaises(pd.NotStartable):
            self.edit(d, [{"op": "set_lane", "phase": "a", "lane": "x", "field": "task", "value": "late"}], revision=1)
        launch.assert_called_once()

    def test_a_hand_edited_draft_file_is_not_trusted(self):
        d = self.create()
        path = pd._path(self.ctx, d["draft_id"])
        path.write_text(path.read_text(encoding="utf-8").replace('"better"', '"x"').replace('"g"', '"tampered goal"'), encoding="utf-8")
        launch = mock.Mock()
        with self.assertRaises(ValueError):
            pd.start_draft(self.ctx, d["draft_id"], d["revision"], d["spec_hash"], origin=Origin.HUMAN, start=launch)
        launch.assert_not_called()

    def test_ids_are_validated(self):
        for bad in ("../x", "plan-", "plan-ZZZ", "", None):
            with self.assertRaises(ValueError):
                pd.get_draft(self.ctx, bad)


if __name__ == "__main__":
    unittest.main()


class PlanIpcTests(unittest.TestCase):
    def setUp(self):
        from respected_orchestrator.engine.local_api import LocalApi
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ctx = EngineContext(Path(self.tmp.name).resolve() / "data")
        self.LocalApi = LocalApi
        self.n = 0

    def call(self, api, cmd, payload):
        self.n += 1
        return api.handle({"ipc": "1", "id": f"plan-{self.n:05d}", "session": "t" * 32, "cmd": cmd, "payload": payload})

    def test_gui_flow_create_edit_invalid_then_explicit_start_only_when_valid(self):
        api = self.LocalApi(self.ctx, "t" * 32)
        made = self.call(api, "plan.create", {"spec": spec(), "project_root": ROOT})
        self.assertTrue(made["ok"], made)
        d = made["result"]
        broke = self.call(api, "plan.edit", {"draft_id": d["draft_id"], "revision": 1,
                                             "edits": [{"op": "set_phase_after", "phase": "a", "value": ["b"]}]})
        self.assertTrue(broke["ok"] and not broke["result"]["valid"])
        stale = self.call(api, "plan.edit", {"draft_id": d["draft_id"], "revision": 1, "edits": [{"op": "set_phase_after", "phase": "a", "value": []}]})
        self.assertEqual(stale["error"]["code"], "ENGINE_ERROR")
        refused = self.call(api, "plan.start", {"draft_id": d["draft_id"], "revision": 2, "confirm_hash": broke["result"]["spec_hash"]})
        self.assertFalse(refused["ok"])
        self.assertIn("not valid", refused["error"]["message"])
        self.assertFalse((self.ctx.data_root / "projects").exists())  # nothing was started
        mcp = self.LocalApi(self.ctx, "t" * 32, origin=Origin.MCP)
        self.assertEqual(self.call(mcp, "plan.start", {"draft_id": d["draft_id"], "revision": 1, "confirm_hash": d["spec_hash"]})["error"]["code"], "FORBIDDEN")
        worker = self.LocalApi(self.ctx, "t" * 32, origin=Origin.WORKER)
        self.assertEqual(self.call(worker, "plan.create", {"spec": spec(), "project_root": ROOT})["error"]["code"], "FORBIDDEN")
