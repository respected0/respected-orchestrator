import json
import random
import re
import string
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import local_api
from respected_orchestrator.engine.authority import Origin
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

    def test_short_token_refused(self):
        with self.assertRaises(ValueError):
            LocalApi(self.api.ctx, "short")

    def test_typescript_contract_matches_python(self):
        ts_cmds = re.findall(r"'([a-z.]+)'", TS[TS.index("COMMANDS"):TS.index("export type Command")])
        ts_errs = re.findall(r"'([A-Z_]+)'", TS[TS.index("ERROR_CODES"):TS.index("export type ErrorCode")])
        self.assertEqual(sorted(ts_cmds), sorted(local_api.COMMANDS))
        self.assertEqual(sorted(ts_errs), sorted(ERRORS))
        self.assertIn(f"MAX_REQUEST_BYTES = {MAX_REQUEST_BYTES}", TS)


if __name__ == "__main__":
    unittest.main()
