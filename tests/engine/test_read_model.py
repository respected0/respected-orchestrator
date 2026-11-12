import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import read_model, runner
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.local_api import LocalApi

TOKEN = "t" * 32


def run_id(n, h=None):
    return f"run-{20261106000000 + n:014d}-{(h or n):012x}"


class ReadModelTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ctx = EngineContext(Path(tmp.name).resolve() / "data")
        self.ctx.state_dir.mkdir(parents=True)

    def make(self, n, status="completed", task="do a thing", worker="codex", **extra):
        rid = run_id(n)
        directory = self.ctx.run_dir(rid)
        directory.mkdir()
        save_signed(self.ctx, directory / "request.json", dict(run_id=rid, task=task, worker=worker, kind="write",
                                                                 project_root="C:/p", created_at=f"t{n}", **extra))
        save_signed(self.ctx, directory / "status.json", {"run_id": rid, "status": status, **({"pid": 2**30} if status == "running" else {})})
        return rid

    def test_states_are_derived_from_engine_files_and_match_the_cli(self):
        ids = {s: self.make(i, s) for i, s in enumerate(["queued", "running", "completed", "failed", "timed_out", "cancelled", "interrupted"], 1)}
        page = {r["run_id"]: r for r in read_model.runs_page(self.ctx)["runs"]}
        want = {"queued": "queued", "running": "stale", "completed": "done", "failed": "failed", "timed_out": "failed",
                "cancelled": "cancelled", "interrupted": "stale"}
        for status, rid in ids.items():
            self.assertEqual(page[rid]["state"], want[status], status)
            # same decision as the CLI: the dead 'running' pid is interrupted there too, never in_progress here
            self.assertEqual(page[rid]["status"], runner.inspect_task(self.ctx, rid)["status"])
        cli = {r["run_id"]: r["status"] for r in runner.list_tasks(self.ctx)["runs"]}
        self.assertEqual({k: v["status"] for k, v in page.items()}, cli)

    def test_board_lanes_are_derived_from_the_run_files_on_every_read(self):
        ids = {s: self.make(i, s) for i, s in enumerate(["queued", "completed", "failed", "cancelled", "interrupted"], 1)}
        lanes = lambda: {r["run_id"]: (r["lane"], r["display"]) for r in read_model.runs_page(self.ctx)["runs"]}
        seen = lanes()
        self.assertEqual([seen[ids[s]] for s in ("queued", "completed", "failed", "cancelled", "interrupted")],
                         [("working", "queued"), ("archive", "done"), ("needs_you", "failed"), ("archive", "cancelled"), ("needs_you", "stale")])
        done = self.ctx.run_dir(ids["completed"])
        (done / "worker.patch").write_bytes(b"")  # an empty patch is nothing to approve
        self.assertEqual(lanes()[ids["completed"]], ("archive", "done"))
        (done / "worker.patch").write_bytes(b"diff --git a/x b/x\n")
        self.assertEqual(lanes()[ids["completed"]], ("ready", "awaiting_approval"))  # nothing was stored: the same record moved
        (done / "apply-failed.json").write_text("{}")
        self.assertEqual(lanes()[ids["completed"]], ("needs_you", "apply_failed"))
        (done / "applied.json").write_text("{}")
        self.assertEqual(lanes()[ids["completed"]], ("archive", "applied"))
        (self.ctx.state_dir / "run-broken").mkdir()
        self.assertEqual(lanes()["run-broken"], ("needs_you", "invalid"))
        self.assertTrue(all(r["lane"] in read_model.LANES for r in read_model.runs_page(self.ctx)["runs"]))

    def test_a_live_worker_is_in_progress(self):
        rid = self.make(1, "running")
        directory = self.ctx.run_dir(rid)
        save_signed(self.ctx, directory / "status.json", {"run_id": rid, "status": "running", "pid": os.getpid()})
        self.assertEqual(read_model.run_dto(self.ctx, rid)["state"], "in_progress")

    def test_pending_permission_moves_a_live_run_to_needs_you_and_damaged_files_never_break_the_list(self):
        rid = self.make(1, "running")
        directory = self.ctx.run_dir(rid)
        save_signed(self.ctx, directory / "status.json", {"run_id": rid, "status": "running", "pid": os.getpid()})
        (directory / "permission.request.json").write_text(json.dumps({
            "run_id": rid, "request_id": "700", "method": "session/request_permission",
            "title": "Run a shell command", "created_at": time.time(), "expires_at": time.time() + 60,
            "options": [{"id": "allow", "kind": "allow_once", "name": "Allow"},
                        {"id": "reject", "kind": "reject_once", "name": "Reject"}]}), encoding="utf8")
        dto = read_model.run_dto(self.ctx, rid)
        self.assertEqual((dto["lane"], dto["display"]), ("needs_you", "permission_request"))
        self.assertEqual(dto["pending_permission"]["request_id"], "700")
        self.assertEqual([o["id"] for o in dto["pending_permission"]["options"]], ["allow", "reject"])
        self.assertEqual(runner.inspect_task(self.ctx, rid)["pending_permission"]["title"], "Run a shell command")
        (directory / "permission.request.json").write_text("{not json", encoding="utf8")
        dto = read_model.run_dto(self.ctx, rid)
        self.assertIsNone(dto["pending_permission"])
        self.assertEqual([r["run_id"] for r in read_model.runs_page(self.ctx)["runs"]], [rid])
        (directory / "permission.request.json").write_text(json.dumps({
            "run_id": rid, "request_id": "700", "title": "old", "expires_at": time.time() - 1,
            "options": [{"id": "allow", "name": "Allow"}]}), encoding="utf8")
        self.assertIsNone(read_model.run_dto(self.ctx, rid)["pending_permission"])

    def test_corrupt_missing_duplicate_and_unknown_become_invalid_rows_not_crashes(self):
        good = self.make(1)
        bad = self.make(2)
        (self.ctx.run_dir(bad) / "status.json").write_text("{not json")
        mismatch = self.make(3)
        save_signed(self.ctx, self.ctx.run_dir(mismatch) / "status.json", {"run_id": run_id(99), "status": "completed"})
        unknown = self.make(4, "levitating")
        empty = run_id(5)
        self.ctx.run_dir(empty).mkdir()
        (self.ctx.state_dir / "run-oops").mkdir()
        by = {r["run_id"]: r for r in read_model.runs_page(self.ctx)["runs"]}
        self.assertEqual(by[good]["state"], "done")
        for rid in (bad, mismatch, unknown, empty, "run-oops"):
            self.assertEqual(by[rid]["state"], "invalid", rid)
            self.assertTrue(by[rid]["error"], rid)
        self.assertEqual(by[mismatch]["error"], "identity_mismatch")
        self.assertEqual(by[unknown]["error"], "unknown_status")
        self.assertEqual(by[unknown]["status"], "levitating")  # shown, never mapped to something healthy

    def test_filters_search_and_order(self):
        self.make(1, "completed", task="alpha refactor", worker="codex")
        self.make(2, "failed", task="beta fix", worker="claude")
        self.make(3, "failed", task="Gamma   FIX", worker="codex")
        names = lambda **kw: [r["task"] for r in read_model.runs_page(self.ctx, **kw)["runs"]]
        self.assertEqual(names(states=["failed"]), ["Gamma FIX", "beta fix"])
        self.assertEqual(names(query="fix", newest_first=False), ["beta fix", "Gamma FIX"])
        self.assertEqual(names(query="claude"), ["beta fix"])
        self.assertEqual(names(states=["failed"], query="alpha"), [])
        with self.assertRaises(ValueError):
            read_model.runs_page(self.ctx, states=["nope"])
        with self.assertRaises(ValueError):
            read_model.runs_page(self.ctx, cursor="../x")

    def test_dependencies_and_evidence_references(self):
        parent = self.make(1)
        child = self.make(2, retry_of=parent, correction_of=None)
        (self.ctx.run_dir(child) / "worker.patch").write_text("diff")
        (self.ctx.run_dir(child) / "worker.log").write_text("x" * 100)
        dto = read_model.run_dto(self.ctx, child)
        self.assertEqual(dto["dependencies"], {"retry_of": parent})
        self.assertEqual(dto["evidence"], {"patch": True, "logs": ["worker.log"]})
        self.assertNotIn("diff", str(dto))  # references only, never content

    def test_ten_thousand_runs_page_exactly_once_and_stay_fast(self):
        for n in range(10_000):
            rid = run_id(n)
            d = self.ctx.run_dir(rid)
            d.mkdir()
            (d / "request.json").write_text("{}")  # unsigned on purpose: they are invalid rows, which is the worst case
        seen, cursor, pages = [], None, 0
        started = time.monotonic()
        while True:
            page = read_model.runs_page(self.ctx, cursor=cursor, limit=200)
            seen += [r["run_id"] for r in page["runs"]]
            pages += 1
            cursor = page["next_cursor"]
            if cursor is None:
                break
        elapsed = time.monotonic() - started
        self.assertEqual(len(seen), 10_000)
        self.assertEqual(len(set(seen)), 10_000)
        self.assertEqual(seen, sorted(seen, reverse=True))
        self.assertEqual(pages, 50)
        self.assertLess(elapsed, 120, f"paging 10k runs took {elapsed:.1f}s")

    def test_projects_have_stages_and_dependencies(self):
        pid = "proj-20261106000000-abcd1234"
        directory = self.ctx.data_root / "projects" / pid
        directory.mkdir(parents=True)
        spec = {"goal": "ship it", "phases": [{"name": "a", "after": []}, {"name": "b", "after": ["a"]}]}
        save_signed(self.ctx, directory / "project.json", dict(project_id=pid, spec=spec, status="created", created_at="t",
                                                               phases={"a": {"status": "done", "attempts": [1]}, "b": {"status": "pending", "attempts": []}}))
        broken = self.ctx.data_root / "projects" / "proj-20261106000001-badbad00"
        broken.mkdir()
        (broken / "project.json").write_text("junk")
        rows = {p["project_id"]: p for p in read_model.projects_page(self.ctx)["projects"]}
        self.assertEqual(rows[pid]["goal"], "ship it")
        self.assertEqual([(s["name"], s["status"], s["after"]) for s in rows[pid]["stages"]], [("a", "done", []), ("b", "pending", ["a"])])
        self.assertFalse(rows[pid]["alive"])
        self.assertEqual(rows["proj-20261106000001-badbad00"]["state"], "invalid")


class BoardIpcTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ctx = EngineContext(Path(tmp.name).resolve() / "data")
        self.ctx.state_dir.mkdir(parents=True)
        self.api = LocalApi(self.ctx, TOKEN)
        self.n = 0

    def call(self, cmd, payload):
        self.n += 1
        return self.api.handle({"ipc": "1", "id": f"board-{self.n:05d}", "session": TOKEN, "cmd": cmd, "payload": payload})

    def test_commands_are_read_only_and_validate_their_input(self):
        ok = self.call("runs.list", {"states": ["failed"], "limit": 5})
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(ok["result"], {"runs": [], "next_cursor": None})
        self.assertTrue(self.call("projects.list", {})["ok"])
        for payload in ({"states": "failed"}, {"order": "sideways"}, {"limit": "5"}, {"cursor": 3}, {"states": ["nope"]}, {"cursor": "../.."}):
            r = self.call("runs.list", payload)
            self.assertFalse(r["ok"])
            self.assertEqual(r["error"]["code"], "BAD_REQUEST", payload)
        self.assertEqual(self.call("projects.list", {"cursor": "x"})["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
