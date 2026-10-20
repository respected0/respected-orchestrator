import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from respected_orchestrator import mcp_server, runner
from respected_orchestrator.context import EngineContext

SRC = str(Path(__file__).resolve().parents[1] / "src")


def call(ctx, name, args, **kw):
    reply = mcp_server.handle(ctx, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}, **kw)
    return reply


class McpServerTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.ctx = EngineContext(Path(self.root))

    def test_lists_tools_but_an_orchestrated_process_sees_none(self):
        listing = lambda **kw: mcp_server.handle(self.ctx, {"id": 1, "method": "tools/list"}, **kw)["result"]["tools"]
        self.assertIn("orchestrator_task_start", [t["name"] for t in listing()])
        self.assertEqual(listing(delegated=True), [])
        self.assertIn("error", call(self.ctx, "orchestrator_status", {}, delegated=True))

    def test_delegation_flag_detection(self):
        self.assertTrue(mcp_server._is_delegated({mcp_server.DELEGATED: "1"}))
        self.assertTrue(mcp_server._is_delegated({"RESPECTED_ORCH_CHILD": "1"}))
        self.assertFalse(mcp_server._is_delegated({}))

    def test_apply_needs_the_verified_digest_and_ids_are_validated(self):
        run = self.ctx.run_dir("run-x1")
        run.mkdir(parents=True)
        runner._save(self.ctx, run / "result.json", {"patch_sha256": "abc"})
        bad = call(self.ctx, "orchestrator_apply", {"run_id": "run-x1", "patch_sha256": "zzz"})["result"]
        self.assertTrue(bad["isError"])
        self.assertIn("does not match", bad["content"][0]["text"])
        self.assertTrue(call(self.ctx, "orchestrator_cancel", {"id": "../../etc"})["result"]["isError"])

    def test_memory_note_is_disabled_unless_the_user_enabled_writes(self):
        reply = call(self.ctx, "orchestrator_memory_note", {"title": "t", "body": "b"})
        self.assertIn('disabled', reply['result']['content'][0]['text'])

    def test_privileged_task_options_are_refused_over_mcp_and_bypass_flags_are_not_commands(self):
        for args in ({"worker": "custom", "command": ["x"]}, {"apply_root": "C:/x"}, {"final_review": {"command": ["x"]}}, {"engine_source": "C:/e"}):
            out = call(self.ctx, "orchestrator_task_start", args)["result"]
            self.assertTrue(out["isError"], args)
            self.assertIn("disabled over MCP", out["content"][0]["text"])
        for bad in (["claude", "--permission-mode", "bypassPermissions"], ["codex", "exec", "-s", "danger-full-access"],
                    ["gemini", "-y"], ["gemini", "--approval-mode", "yolo"], ["x", "--dangerously-skip-permissions=true"]):
            with self.assertRaises(ValueError):
                runner._command(bad)

    def test_acceptance_commands_over_mcp_need_the_users_prefix_list(self):
        import json as _json
        base = {"project_root": self.root, "task": "t", "ownership": ["a.txt"]}
        def refused(args, **kw):
            out = call(self.ctx, "orchestrator_task_start", args, **kw)["result"]
            return out["isError"] and "mcp_acceptance_allow" in out["content"][0]["text"]
        # default: nothing is listed, so no acceptance command a model supplies is run
        self.assertTrue(refused({**base, "acceptance": [["python", "-c", "import os; os.system('calc')"]]}))
        self.assertTrue(refused({**base, "acceptance": [["python", "-m", "pytest"]]}))
        phases = {"phases": [{"name": "p", "verify": [{"command": ["python", "-c", "print(1)"], "cwd": self.root, "timeout_seconds": 5}]}]}
        out = call(self.ctx, "orchestrator_project_start", phases)["result"]
        self.assertTrue(out["isError"] and "mcp_acceptance_allow" in out["content"][0]["text"])
        # the user lists a prefix: only commands that start with it pass the gate (they then meet the normal validation)
        from respected_orchestrator import roles
        settings = {"mcp_acceptance_allow": _json.dumps([["python", "-m", "pytest"]])}
        self.assertTrue(roles.acceptance_allowed(settings, ["python", "-m", "pytest", "-q"]))
        for command in (["python", "-c", "x"], ["python", "-m", "pip", "install", "x"], ["python", "-m"], ["pytest"], [], "python -m pytest", None, [1]):
            self.assertFalse(roles.acceptance_allowed(settings, command), command)
        self.assertEqual(roles.validate_settings({"mcp_acceptance_allow": "[[]]"}, ["codex"])[0]["key"], "mcp_acceptance_allow")
        self.assertEqual(roles.validate_settings({"mcp_acceptance_allow": "not json"}, ["codex"])[0]["key"], "mcp_acceptance_allow")
        (Path(self.root) / "settings.json").write_text(_json.dumps(settings), encoding="utf-8")
        # listed prefix: the gate no longer refuses (the request then fails later for its own reasons: project_root is not a Git repo)
        out = call(self.ctx, "orchestrator_task_start", {**base, "acceptance": [["python", "-m", "pytest", "-q"]]})["result"]
        self.assertNotIn("mcp_acceptance_allow", out["content"][0]["text"])
        # an unlisted command in the same request still stops it, and a prefix match is not a substring match
        self.assertTrue(refused({**base, "acceptance": [["python", "-m", "pytest"], ["python", "-c", "x"]]}))
        self.assertTrue(refused({**base, "acceptance": [["env", "python", "-m", "pytest"]]}))
        # the explicit server-level switch is separate from auto_apply
        out = call(self.ctx, "orchestrator_task_start", {**base, "acceptance": [["python", "-c", "x"]]}, allow_privileged=True)["result"]
        self.assertNotIn("mcp_acceptance_allow", out["content"][0]["text"])
        out = call(self.ctx, "orchestrator_task_start", {"worker": "custom", "command": ["x"]}, allow_auto_apply=True)["result"]
        self.assertIn("--allow-privileged", out["content"][0]["text"])        # auto_apply consent does not unlock privileged options

    def test_auto_apply_is_refused_by_default(self):
        out = call(self.ctx, "orchestrator_project_start", {"phases": [{"auto_apply": True}]})["result"]
        self.assertTrue(out["isError"])
        self.assertIn("auto_apply", out["content"][0]["text"])

    def test_stdio_roundtrip_and_recursion_guard(self):
        def run(extra_env):
            env = dict(os.environ, PYTHONPATH=SRC, **extra_env)
            if not extra_env:
                env.pop(mcp_server.DELEGATED, None)
            lines = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                     {"jsonrpc": "2.0", "method": "notifications/initialized"},
                     {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
            done = subprocess.run([sys.executable, "-m", "respected_orchestrator", "--data-root", self.root, "mcp"], env=env,
                                  input="\n".join(map(json.dumps, lines)) + "\n", capture_output=True, text=True, timeout=60)
            return [json.loads(line) for line in done.stdout.splitlines()]
        free = run({})
        self.assertEqual(free[0]["result"]["protocolVersion"], "2025-06-18")
        instructions = free[0]["result"]["instructions"]  # the kod-orkestrasyon skill, without front matter or the CLI section
        self.assertIn("orchestrator_task_start", instructions)
        self.assertNotIn("name: kod-orkestrasyon", instructions)
        self.assertNotIn("campaign-start", instructions)
        self.assertEqual(len(free), 2)  # the notification gets no reply
        self.assertGreater(len(free[1]["result"]["tools"]), 5)
        self.assertEqual(run({mcp_server.DELEGATED: "1"})[1]["result"]["tools"], [])


if __name__ == "__main__":
    unittest.main()
