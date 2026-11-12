import json
import os
import random
import re
import string
import tempfile
import time
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import catalog, daemon, local_api, runner
from respected_orchestrator.engine.authority import Action, Origin
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.local_api import ERRORS, LocalApi, MAX_REQUEST_BYTES

TOKEN = "t" * 32
TS = (Path(__file__).resolve().parents[2] / "desktop" / "src" / "contracts" / "ipc.ts").read_text(encoding="utf-8")


class LocalApiTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.api = LocalApi(EngineContext(Path(tmp.name).resolve() / "data"), TOKEN)
        self.n = 0

    def call(self, cmd="engine.manifest", payload=None, **over):
        self.n += 1
        request = {"ipc": "1", "id": over.pop("id", f"call-{self.n:06d}"), "session": TOKEN, "cmd": cmd, "payload": payload or {}}
        request.update(over)
        return self.api.handle(request)

    def code(self, response):
        self.assertFalse(response["ok"], response)
        self.assertIn(response["error"]["code"], ERRORS)
        return response["error"]["code"]

    def test_valid_calls_are_traceable_and_wrap_rpp(self):
        hello = self.call("hello", id="trace-0001")
        self.assertTrue(hello["ok"])
        self.assertEqual(hello["id"], "trace-0001")
        self.assertIn("engine.health", hello["result"]["commands"])
        manifest = self.call("engine.manifest")
        self.assertTrue(manifest["ok"])
        self.assertEqual(manifest["result"]["product_id"], "respected-orchestrator")

    def test_unknown_and_non_allowlisted_commands_are_rejected(self):
        for cmd in ("nope", "github.pr_create", "integrations.apply", "memory.connect", "maf-approve", "apply", "", None, 5):
            self.assertEqual(self.code(self.call(cmd)), "UNKNOWN_COMMAND", cmd)

    def test_session_token_and_version(self):
        self.assertEqual(self.code(self.call(session="x" * 32)), "UNAUTHENTICATED")
        self.assertEqual(self.code(self.call(session=None)), "UNAUTHENTICATED")
        self.assertEqual(self.code(self.call(ipc="2")), "UNSUPPORTED_VERSION")

    def test_malformed_and_oversized_input(self):
        self.assertEqual(self.code(self.api.handle_raw("{not json")), "BAD_REQUEST")
        self.assertEqual(self.code(self.api.handle_raw("[1]")), "BAD_REQUEST")
        self.assertEqual(self.code(self.api.handle_raw("x" * (MAX_REQUEST_BYTES + 1))), "PAYLOAD_TOO_LARGE")
        self.assertEqual(self.code(self.call(payload=[1])), "BAD_REQUEST")
        self.assertEqual(self.code(self.call(id="short")), "BAD_REQUEST")
        self.assertEqual(self.code(self.api.handle_raw("[" * 60000)), "BAD_REQUEST")

    def test_replay_same_request_is_idempotent_and_different_one_conflicts(self):
        first = self.call("engine.health", id="same-id-0001")
        self.assertEqual(self.call("engine.health", id="same-id-0001"), first)
        self.assertEqual(self.code(self.call("engine.manifest", id="same-id-0001")), "REPLAY_CONFLICT")

    def make_permission_run(self, *, expires_in=60, status="running", option_ids=("allow", "reject")):
        rid = "run-20261112000000-000000000001"
        directory = self.api.ctx.run_dir(rid)
        directory.mkdir(parents=True, exist_ok=True)
        for stale in ("permission.response.json", "permission.answered.json"):
            (directory / stale).unlink(missing_ok=True)
        save_signed(self.api.ctx, directory / "request.json", {"run_id": rid, "task": "permission fixture", "worker": "opencode",
                                                               "kind": "write", "project_root": "C:/p", "created_at": "t"})
        save_signed(self.api.ctx, directory / "status.json", {"run_id": rid, "status": status,
                                                              **({"pid": os.getpid()} if status == "running" else {})})
        (directory / "permission.request.json").write_text(json.dumps({
            "run_id": rid, "request_id": "700", "title": "Run a shell command", "created_at": time.time(),
            "expires_at": time.time() + expires_in,
            "options": [{"id": i, "name": i.title(), "kind": "allow_once" if i == "allow" else "reject_once"} for i in option_ids]}),
            encoding="utf8")
        return rid, directory

    def test_pending_permission_is_answered_once_by_the_desktop_and_refusals_are_coded(self):
        rid, directory = self.make_permission_run()
        listed = self.call("runs.list")["result"]["runs"][0]
        self.assertEqual(listed["pending_permission"]["request_id"], "700")
        answered = self.call("task.permission.answer", {"run_id": rid, "request_id": "700", "option_id": "allow"})
        self.assertTrue(answered["ok"], answered)
        response = json.loads((directory / "permission.response.json").read_text(encoding="utf8"))
        self.assertEqual((response["request_id"], response["option_id"], response["origin"]), ("700", "allow", "renderer"))
        self.assertEqual(self.code(self.call("task.permission.answer", {"run_id": rid, "request_id": "700", "option_id": "allow"})),
                         "PERMISSION_ALREADY_ANSWERED")
        self.assertEqual(self.code(self.call("task.permission.answer", {"run_id": "run-20261112000000-000000000002",
                                                                        "request_id": "700", "option_id": "allow"})), "PERMISSION_NOT_FOUND")
        self.assertEqual(self.code(self.call("task.permission.answer", {"run_id": rid, "request_id": "701", "option_id": "allow"})),
                         "PERMISSION_NOT_FOUND")
        self.assertEqual(self.code(self.call("task.permission.answer", {"run_id": rid, "request_id": "700", "option_id": "bogus"})),
                         "PERMISSION_OPTION_INVALID")
        mcp = LocalApi(self.api.ctx, TOKEN, origin=Origin.MCP)
        self.assertEqual(self.code(mcp.handle(dict(ipc="1", id="mcp-perm-01", session=TOKEN, cmd="task.permission.answer",
                                                    payload={"run_id": rid, "request_id": "700", "option_id": "allow"}))), "FORBIDDEN")

    def test_expired_closed_and_damaged_permission_requests_are_refused(self):
        rid, directory = self.make_permission_run(expires_in=-1)
        self.assertEqual(self.code(self.call("task.permission.answer", {"run_id": rid, "request_id": "700", "option_id": "allow"})),
                         "PERMISSION_EXPIRED")
        rid, directory = self.make_permission_run(status="completed")
        self.assertEqual(self.code(self.call("task.permission.answer", {"run_id": rid, "request_id": "700", "option_id": "allow"})),
                         "PERMISSION_CLOSED")
        rid, directory = self.make_permission_run()
        (directory / "permission.request.json").write_text("{broken", encoding="utf8")
        self.assertEqual(self.code(self.call("task.permission.answer", {"run_id": rid, "request_id": "700", "option_id": "allow"})),
                         "PERMISSION_REQUEST_INVALID")
        self.assertTrue(self.call("runs.list")["ok"])
        self.assertIsNone(self.call("runs.list")["result"]["runs"][0]["pending_permission"])

    def test_authority_matrix_is_enforced(self):
        worker = LocalApi(self.api.ctx, TOKEN, origin=Origin.WORKER)
        self.assertEqual(self.code(worker.handle(dict(ipc="1", id="worker-0001", session=TOKEN, cmd="engine.health", payload={}))), "FORBIDDEN")
        mcp = LocalApi(self.api.ctx, TOKEN, origin=Origin.MCP)
        self.assertEqual(self.code(mcp.handle(dict(ipc="1", id="mcp-00001", session=TOKEN, cmd="settings.apply", payload={}))), "FORBIDDEN")

    def test_fuzz_never_raises_and_never_succeeds_unauthenticated(self):
        rnd = random.Random(7)
        junk = [None, 0, True, [], {}, "x", "ipc", 1.5, {"a": [1]}]
        for _ in range(500):
            request = {k: rnd.choice(junk + [rnd.choice(string.ascii_letters)]) for k in rnd.sample(["ipc", "id", "session", "cmd", "payload", "x"], rnd.randint(0, 6))}
            response = self.api.handle(request)
            self.assertFalse(response["ok"])
            self.assertEqual(set(response), {"ipc", "id", "ok", "result", "error"})

    def test_runs_active_lists_only_live_workers(self):
        import subprocess, sys
        from respected_orchestrator.engine.supervisor import Supervisor
        worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(lambda: (worker.kill(), worker.wait()))
        with Supervisor(self.api.ctx) as s:
            s.claim_run("run-live", worker.pid)
            s.claim_run("run-dead", 99999999)
        self.assertEqual(self.call("runs.active")["result"]["runs"], {"run-live": worker.pid})

    def test_short_token_refused(self):
        with self.assertRaises(ValueError):
            LocalApi(self.api.ctx, "short")

    def test_the_catalog_lists_only_what_the_caller_may_run(self):
        def names(**options):
            api = LocalApi(self.api.ctx, TOKEN, **options)
            reply = api.handle({"ipc": "1", "id": "catalog-0001", "session": TOKEN, "cmd": "catalog.list", "payload": {}})
            return reply, {row["name"] for row in (reply["result"] or {}).get("commands", [])}
        reply, renderer = names()
        self.assertIn({"name": "session.start", "action": "task", "cli": "session start", "mcp": "orchestrator_session_start", "desktop": "session"}, reply["result"]["commands"])
        self.assertIn("session.defaults.set", renderer)
        self.assertNotIn("approval.apply", renderer)  # privileged: not the renderer's
        _reply, mcp = names(origin=Origin.MCP, only=daemon.SERVED)
        self.assertTrue({"session.start", "catalog.list"} <= mcp)
        self.assertTrue({"approval.decide", "approval.apply", "settings.apply", "session.defaults.set", "attachment.commit"}.isdisjoint(mcp))
        self.assertEqual(mcp, {n for n in daemon.SERVED if n in mcp})
        self.assertEqual(self.code(names(origin=Origin.CHILD)[0]), "FORBIDDEN")  # a worker's descendant learns nothing

    def test_every_face_is_built_from_the_one_table(self):
        from respected_orchestrator.interfaces import mcp_server
        self.assertEqual(list(local_api.COMMANDS), [entry.name for entry in catalog.ENTRIES])
        for tool, entry in catalog.MCP.items():
            self.assertEqual(mcp_server.TOOLS[tool], entry.mcp[1:])
            self.assertEqual(entry.mcp[3], entry.action is Action.READ, tool)  # "read-only" is the engine's class, not a second opinion
        for entry in catalog.ENTRIES:
            self.assertIn(entry.desktop, (None, *catalog.DESKTOP_GROUPS), entry.name)
            if entry.desktop == "read":
                self.assertIs(entry.action, Action.READ, entry.name)
            self.assertFalse(entry.action is Action.PRIVILEGED and (entry.cli or entry.mcp or entry.desktop), entry.name)

    def test_typescript_contract_matches_python(self):
        for path, text in catalog.generated(Path(__file__).resolve().parents[2]).items():  # run `python -m respected_orchestrator.engine.catalog`
            self.assertEqual(path.read_text(encoding="utf-8"), text, f"{path.name} is not what the catalog generates")
        ts_cmds = re.findall(r"'([a-z._]+)'", catalog.render_ts().splitlines()[1])
        ts_errs = re.findall(r"'([A-Z_]+)'", TS[TS.index("ERROR_CODES"):TS.index("export type ErrorCode")])
        self.assertEqual(sorted(ts_cmds), sorted(local_api.COMMANDS))
        self.assertEqual(sorted(ts_errs), sorted(ERRORS))
        self.assertIn(f"MAX_REQUEST_BYTES = {MAX_REQUEST_BYTES}", TS)


if __name__ == "__main__":
    unittest.main()


class EventStreamTests(unittest.TestCase):
    def setUp(self):
        from respected_orchestrator.engine.journal import Journal
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.journal = Journal(self.root / "events.log")
        self.api = LocalApi(EngineContext(self.root / "data"), TOKEN, journal=self.journal)
        self.n = 0

    def call(self, cmd, payload=None):
        self.n += 1
        return self.api.handle(dict(ipc="1", id=f"evt-{self.n:06d}", session=TOKEN, cmd=cmd, payload=payload or {}))

    def test_pages_are_bounded_and_cover_a_burst_exactly_once(self):
        for i in range(1200):
            self.journal.append(f"o{i}", "step", run_id=f"r{i % 4}")
        seen, after = [], 0
        while True:
            r = self.call("events.since", {"after": after, "limit": 100000})["result"]
            self.assertLessEqual(len(r["events"]), local_api.MAX_EVENTS_PER_CALL)
            self.assertFalse(r["gap"])
            seen += [e["seq"] for e in r["events"]]
            after = r["events"][-1]["seq"]
            if not r["has_more"]:
                break
        self.assertEqual(seen, list(range(1, 1201)))

    def test_reopening_three_times_reaches_the_same_state_hash(self):
        for i in range(30):
            self.journal.append(f"o{i}", "step" if i % 2 else "done", run_id=f"r{i % 3}")
        hashes = {self.call("events.snapshot")["result"]["state_hash"] for _ in range(3)}
        self.assertEqual(len(hashes), 1)
        from respected_orchestrator.engine.journal import Journal
        self.assertEqual(Journal(self.root / "events.log").snapshot()["state_hash"], hashes.pop())

    def test_cursor_ahead_of_or_behind_a_rotated_journal_is_a_gap(self):
        for i in range(5):
            self.journal.append(f"o{i}", "step", run_id="r")
        self.assertTrue(self.call("events.since", {"after": 99})["result"]["gap"])
        self.journal.archive(self.root / "events.1")
        self.journal.append("n1", "step", run_id="r")
        self.assertTrue(self.call("events.since", {"after": 2})["result"]["gap"])  # events 3..5 live in the archive now
        self.assertFalse(self.call("events.since", {"after": 5})["result"]["gap"])  # 6 is the rotation marker: next in line

    def test_bad_cursor_and_missing_journal(self):
        self.assertFalse(self.call("events.since", {"after": -1})["ok"])
        self.assertFalse(self.call("events.since", {"after": "x"})["ok"])
        self.assertFalse(self.call("events.since", {"after": True})["ok"])
        bare = LocalApi(EngineContext(self.root / "d2"), TOKEN)
        self.assertEqual(bare.handle(dict(ipc="1", id="evt-nojrnl", session=TOKEN, cmd="events.snapshot"))["error"]["code"], "ENGINE_ERROR")

