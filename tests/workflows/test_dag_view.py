import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.local_api import LocalApi
from respected_orchestrator.workflows import dag_view, planner

ROOT = str(Path(tempfile.gettempdir()).resolve())


def lane(name, own, after=None):
    return {"name": name, "after": after or [], "request": {"project_root": ROOT, "task": "t", "kind": "write", "ownership": own,
                                                            "acceptance": [["python", "-c", "pass"]]}}


def phase(name, lanes, after=None):
    return {"name": name, "after": after or [], "workstreams": lanes}


def view(*phases):
    return dag_view.dag_view({"goal": "g", "phases": list(phases)}, ROOT)


def engine_accepts(spec):
    try:
        return planner._dag(spec, ROOT)["valid"]
    except (ValueError, TypeError):
        return False


class DagViewTests(unittest.TestCase):
    def test_valid_plan_is_laid_out_by_dependency_depth(self):
        v = view(phase("a", [lane("x", ["src/a.py"]), lane("y", ["src/b.py"])]),
                 phase("b", [lane("z", ["src/c.py"])], after=["a"]))
        self.assertTrue(v["valid"])
        self.assertEqual(v["findings"], [])
        layers = {n["id"]: n["layer"] for n in v["nodes"]}
        self.assertEqual(layers, {"a/x": 0, "a/y": 0, "b/z": 1})
        self.assertEqual(sorted((e["from"], e["to"]) for e in v["edges"]), [("a/x", "b/z"), ("a/y", "b/z")])
        self.assertEqual([n["row"] for n in v["nodes"] if n["layer"] == 0], [0, 1])
        self.assertEqual(v["authority"]["workers"], False)

    def test_cycle_highlights_the_nodes_and_edges_and_is_invalid(self):
        v = view(phase("a", [lane("x", ["a.py"])], after=["b"]), phase("b", [lane("y", ["b.py"])], after=["a"]))
        self.assertFalse(v["valid"])
        cycle = [f for f in v["findings"] if f["kind"] == "cycle"]
        self.assertTrue(cycle)
        self.assertEqual(cycle[0]["nodes"], ["a/x", "b/y"])
        self.assertTrue(cycle[0]["edges"])
        self.assertTrue(any(e["issue"] for e in v["edges"]))
        self.assertTrue(all("cycle" in n["issues"] for n in v["nodes"]))
        self.assertIn("Cycle", v["engine_message"])

    def test_unknown_edges_are_named(self):
        v = view(phase("a", [lane("x", ["a.py"], after=["ghost"])]), phase("b", [lane("y", ["b.py"])], after=["nowhere"]))
        self.assertFalse(v["valid"])
        kinds = [(f["kind"], f["nodes"]) for f in v["findings"]]
        self.assertIn(("unknown_dependency", ["a/x"]), kinds)
        self.assertIn(("unknown_dependency", ["b/y"]), kinds)

    def test_parallel_ownership_collision_is_flagged_but_ordered_work_is_fine(self):
        collide = view(phase("a", [lane("x", ["src"]), lane("y", ["src/mod.py"])]))
        self.assertFalse(collide["valid"])
        found = [f for f in collide["findings"] if f["kind"] == "ownership_collision"]
        self.assertEqual(found[0]["nodes"], ["a/x", "a/y"])
        self.assertIn("src", found[0]["message"])
        ordered = view(phase("a", [lane("x", ["src"]), lane("y", ["src/mod.py"], after=["x"])]))
        self.assertTrue(ordered["valid"], ordered["engine_message"])
        self.assertEqual(ordered["findings"], [])

    def test_duplicate_names_and_unexplained_engine_rejections_are_never_silent(self):
        dup = view(phase("a", [lane("x", ["a.py"]), lane("x", ["b.py"])]))
        self.assertFalse(dup["valid"])
        self.assertIn("duplicate_name", [f["kind"] for f in dup["findings"]])
        bad = lane("x", ["a.py"])
        bad["request"]["acceptance"] = []
        lonely = view(phase("a", [bad]))
        self.assertFalse(lonely["valid"])
        self.assertEqual([f["kind"] for f in lonely["findings"]], ["engine"])
        self.assertIn("acceptance", lonely["findings"][0]["message"])

    def test_garbage_specs_do_not_crash_and_are_invalid(self):
        for spec in ({}, {"phases": "x"}, {"phases": [1, None]}, {"phases": [{"name": 5}]}, {"phases": [{"name": "a", "workstreams": "x"}]},
                     {"phases": [{"name": "a", "after": "b", "workstreams": [{"name": "x", "request": 4, "after": 9}]}]}):
            v = dag_view.dag_view(spec, ROOT)
            self.assertFalse(v["valid"], spec)
            self.assertTrue(v["engine_message"], spec)

    def test_view_verdict_always_equals_the_engine_verdict(self):
        specs = [
            [phase("a", [lane("x", ["a.py"])])],
            [phase("a", [lane("x", ["src"]), lane("y", ["src/m.py"])])],
            [phase("a", [lane("x", ["a.py"])], after=["a"])],
            [phase("a", [lane("x", ["a.py"], after=["x"])])],
            [phase("a", [lane("x", ["a.py"])]), phase("a", [lane("y", ["b.py"])])],
        ]
        for phases in specs:
            spec = {"goal": "g", "phases": phases}
            self.assertEqual(dag_view.dag_view(spec, ROOT)["valid"], engine_accepts(spec), phases)

    def test_largest_legal_plan_96_nodes_and_over_200_edges(self):
        phases = []
        for p in range(12):
            lanes = [lane(f"l{i}", [f"p{p}/f{i}.py"]) for i in range(8)]
            phases.append(phase(f"p{p}", lanes, after=[f"p{p - 1}"] if p else []))
        v = view(*phases)
        self.assertTrue(v["valid"], v["engine_message"])
        self.assertEqual(v["counts"]["nodes"], 96)
        self.assertGreaterEqual(v["counts"]["edges"], 200)
        self.assertEqual(max(n["layer"] for n in v["nodes"]), 11)
        self.assertEqual(len({(n["layer"], n["row"]) for n in v["nodes"]}), 96)  # no two nodes share a cell

    def test_view_is_deterministic(self):
        phases = [phase("a", [lane("y", ["b.py"]), lane("x", ["a.py"])]), phase("b", [lane("z", ["c.py"])], after=["a"])]
        self.assertEqual(view(*phases), view(*list(phases)))


class PlanViewIpcTests(unittest.TestCase):
    def test_plan_view_is_read_only_and_validates_input(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        api = LocalApi(EngineContext(Path(tmp.name).resolve() / "data"), "t" * 32)
        call = lambda payload, n: api.handle({"ipc": "1", "id": f"plan-{n:05d}", "session": "t" * 32, "cmd": "plan.view", "payload": payload})
        ok = call({"spec": {"goal": "g", "phases": [phase("a", [lane("x", ["a.py"])])]}, "project_root": ROOT}, 1)
        self.assertTrue(ok["ok"], ok)
        self.assertTrue(ok["result"]["valid"])
        for n, payload in enumerate(({}, {"spec": [], "project_root": ROOT}, {"spec": {}, "project_root": ""}, {"spec": {}}), 2):
            self.assertEqual(call(payload, n)["error"]["code"], "BAD_REQUEST")
        no_workers = list(Path(tmp.name).rglob("run-*"))
        self.assertEqual(no_workers, [])  # nothing was created: no run, no worker


if __name__ == "__main__":
    unittest.main()
