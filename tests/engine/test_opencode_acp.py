"""ACP client tests use a real stdio child so reader ordering and EOF are exercised."""
import json
from pathlib import Path
import queue
import sys
import tempfile
import textwrap
import time
import unittest

from respected_orchestrator.engine.opencode_acp import AcpError, LineQueue, run_session
from respected_orchestrator.engine.processes import execute


FAKE_SERVER = textwrap.dedent(r'''
    import json, os, sys, time

    MODE = sys.argv[1] if len(sys.argv) > 1 else "success"
    RECORD = sys.argv[2] if len(sys.argv) > 2 else ""
    CWD = os.getcwd()
    SESSION = "ses_fixture"

    def send(value):
        print(json.dumps(value, separators=(",", ":")), flush=True)

    def read():
        line = sys.stdin.readline()
        return json.loads(line) if line else None

    def reply(ident, result):
        send({"jsonrpc": "2.0", "id": ident, "result": result})

    def error(ident, code, message):
        send({"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}})

    def options(value="opencode/fixture"):
        return [
            {"id": "model", "type": "select", "currentValue": "opencode/fixture", "options": [
                {"value": "opencode/fixture"}, {"value": "fixture/model"}, {"value": "bad/model"}]},
            {"id": "mode", "type": "select", "currentValue": "build", "options": [
                {"value": "build"}, {"value": "plan"}]},
        ]

    def record(value):
        if RECORD:
            with open(RECORD, "a", encoding="utf8") as handle:
                handle.write(json.dumps(value, sort_keys=True) + "\n")

    def response(want):
        while True:
            value = read()
            if value is None:
                return None
            if value.get("id") == want:
                return value

    def chunk(prompt_id, text):
        send({"jsonrpc": "2.0", "method": "session/update", "params": {
            "sessionId": SESSION, "update": {"sessionUpdate": "agent_message_chunk",
            "messageId": "msg_fixture", "content": {"type": "text", "text": text}}}})

    def finish(prompt_id, text):
        if MODE == "split":
            chunk(prompt_id, text[:12])
            chunk(prompt_id, text[12:])
        else:
            chunk(prompt_id, text)
        reply(prompt_id, {"stopReason": "end_turn", "usage": {
            "inputTokens": 100, "outputTokens": 7, "totalTokens": 107,
            "thoughtTokens": 2, "cachedReadTokens": 10}})

    for raw in sys.stdin:
        request = json.loads(raw)
        method, ident = request.get("method"), request.get("id")
        params = request.get("params") or {}
        if method == "initialize":
            reply(ident, {"protocolVersion": 1, "agentInfo": {"name": "OpenCode", "version": "fixture"}})
        elif method == "session/new":
            CWD = params["cwd"]
            reply(ident, {"sessionId": SESSION, "configOptions": options()})
        elif method == "session/set_config_option":
            record({"config": params["configId"], "value": params["value"]})
            if MODE == "invalid_model" and params.get("value") == "bad/model":
                error(ident, -32602, "Invalid params: model not found: bad/model")
            else:
                chosen = options()
                for option in chosen:
                    if option["id"] == params["configId"]:
                        option["currentValue"] = params["value"]
                reply(ident, {"configOptions": chosen})
        elif method == "session/prompt":
            if MODE == "auth":
                error(ident, -32000, "authentication required")
            elif MODE == "limit":
                error(ident, -32000, "free usage limit reached")
            elif MODE == "early_eof":
                sys.exit(0)
            elif MODE == "hang":
                time.sleep(10)
            elif MODE == "stop_reason":
                reply(ident, {"stopReason": "max_tokens", "usage": {}})
            elif MODE == "permission":
                send({"jsonrpc": "2.0", "id": 700, "method": "session/request_permission", "params": {
                    "sessionId": SESSION, "options": [{"optionId": "allow", "name": "Allow"}]}})
                record(response(700))
                finish(ident, '{"status":"success","summary":"permission rejected"}')
            elif MODE in {"fs_git", "fs_outside"}:
                path = os.path.join(CWD, ".git", "config") if MODE == "fs_git" else os.path.join(os.path.dirname(CWD), "outside.txt")
                send({"jsonrpc": "2.0", "id": 701, "method": "fs/write_text_file", "params": {
                    "sessionId": SESSION, "path": path, "content": "x"}})
                answer = response(701)
                record(answer)
                finish(ident, '{"status":"success","summary":"fs denied"}')
            elif MODE == "fake_failed":
                finish(ident, '{"status":"failed"}')
            elif MODE == "malformed":
                finish(ident, "not-json")
            elif MODE == "missing_status":
                finish(ident, '{"summary":"no status"}')
            elif MODE == "fenced":
                finish(ident, 'Done.\n```json\n{"status":"success","summary":"fenced"}\n```\nThanks.')
            elif MODE == "fenced_plain":
                finish(ident, '```\n{"status":"success","summary":"plain"}\n```')
            elif MODE == "fenced_multiple":
                finish(ident, '```json\n{"status":"success"}\n```\n```json\n{"status":"success"}\n```')
            elif MODE == "fenced_prose_json":
                finish(ident, 'The result is {"status":"success"} done.')
            elif MODE == "fenced_broken":
                finish(ident, '```json\n{bad json}\n```')
            elif MODE == "fenced_array":
                finish(ident, '```json\n[{"status":"success"}]\n```')
            elif MODE == "fenced_unterminated":
                finish(ident, '```json\n{"status":"success"}')
            elif MODE == "fenced_invalid_status":
                finish(ident, '```json\n{"status":"maybe"}\n```')
            elif MODE == "write_file_success":
                with open(os.path.join(CWD, "owned.txt"), "w", encoding="utf8") as handle:
                    handle.write("changed\n")
                finish(ident, '{"status":"success","summary":"wrote"}')
            else:
                finish(ident, '{"status":"success","summary":"ok"}')
''')


class OpenCodeAcpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.work.mkdir()
        self.record = self.root / "record.jsonl"

    def run_mode(self, mode, *, model=None, write=True, timeout=5):
        lines = LineQueue()
        result = {}
        command = [sys.executable, "-c", FAKE_SERVER, mode, str(self.record)]

        def ready(stdin):
            try:
                result["value"] = run_session(
                    stdin, lines, cwd=self.work, prompt="fixture prompt", model=model,
                    write=write, deadline=time.monotonic() + timeout,
                )
            finally:
                stdin.close()

        completed = execute(
            command, self.work, timeout, interactive=True, on_ready=ready,
            on_output=lambda name, line: lines.push(name, line) if name == "stdout" else None,
            on_output_closed=lambda name: lines.close(name) if name == "stdout" else None,
        )
        self.assertEqual(completed.returncode, 0)
        return result["value"]

    def records(self):
        return [json.loads(line) for line in self.record.read_text(encoding="utf8").splitlines() if line]

    def test_prompt_model_and_mode_use_acp_not_argv_and_split_chunks_are_joined(self):
        result = self.run_mode("split", model="fixture/model")
        self.assertEqual(result["payload"]["status"], "success")
        self.assertEqual(result["usage"]["inputTokens"], 100)
        self.assertEqual(result["model"], "fixture/model")
        records = self.records()
        self.assertIn({"config": "model", "value": "fixture/model"}, records)
        self.assertIn({"config": "mode", "value": "build"}, records)
        self.assertNotIn("fixture prompt", " ".join(sys.argv))

    def test_read_session_selects_plan_mode(self):
        self.run_mode("success", write=False)
        self.assertIn({"config": "mode", "value": "plan"}, self.records())

    def test_permission_request_is_cancelled_and_fs_requests_are_denied(self):
        for mode in ("permission", "fs_git", "fs_outside"):
            with self.subTest(mode=mode):
                if self.record.exists():
                    self.record.unlink()
                result = self.run_mode(mode)
                self.assertEqual(result["payload"]["status"], "success")
                answer = self.records()[-1]
                if mode == "permission":
                    self.assertEqual(answer.get("result"), {"outcome": {"outcome": "cancelled"}})
                else:
                    self.assertEqual(answer.get("error", {}).get("code"), -32601)

    def test_protocol_and_provider_failures_fail_closed(self):
        cases = (("invalid_model", "worker_failed"), ("auth", "auth"), ("limit", "limit"),
                 ("early_eof", "worker_failed"), ("stop_reason", "worker_failed"))
        for mode, kind in cases:
            with self.subTest(mode=mode):
                with self.assertRaises(AcpError) as caught:
                    self.run_mode(mode, model="bad/model" if mode == "invalid_model" else None)
                self.assertEqual(caught.exception.kind, kind)

    def test_timeout_cannot_deadlock_the_interactive_reader(self):
        started = time.monotonic()
        with self.assertRaises(AcpError) as caught:
            self.run_mode("hang", timeout=0.5)
        self.assertEqual(caught.exception.kind, "timed_out")
        self.assertLess(time.monotonic() - started, 5)

    def test_failed_or_malformed_final_payload_is_never_success(self):
        for mode in ("fake_failed", "malformed", "missing_status"):
            with self.subTest(mode=mode):
                result = self.run_mode(mode)
                self.assertEqual(result["payload"]["status"], "failed")

    def test_single_fenced_final_message_is_accepted_only_when_unambiguous(self):
        for mode in ("fenced", "fenced_plain"):
            with self.subTest(mode=mode):
                self.assertEqual(self.run_mode(mode)["payload"]["status"], "success")
        for mode in ("fenced_multiple", "fenced_prose_json", "fenced_broken",
                     "fenced_array", "fenced_unterminated", "fenced_invalid_status"):
            with self.subTest(mode=mode):
                self.assertEqual(self.run_mode(mode)["payload"]["status"], "failed")

    def test_reader_threads_start_before_ready_callback(self):
        lines = queue.Queue()
        script = "import sys; value=sys.stdin.readline(); sys.stdout.write(value); sys.stdout.flush()"

        def output(name, line):
            if name == "stdout":
                lines.put(line)

        def ready(stdin):
            stdin.write("ping\n")
            stdin.flush()
            self.assertEqual(lines.get(timeout=2), "ping\n")

        completed = execute([sys.executable, "-c", script], self.work, 5, interactive=True,
                            on_ready=ready, on_output=output)
        self.assertEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
