"""Optional SecondBrain memory wired into settings, task policy, execution and campaign lanes (fake RPP child only)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from respected_orchestrator.workflows import campaign

from respected_orchestrator.interfaces import memory, rpp

from respected_orchestrator.engine import runner
from respected_orchestrator.engine.evidence import load_signed
from respected_orchestrator.context import EngineContext

TOKEN = "rbm_" + "A1b2C3d4" * 4
OTHER_TOKEN = "rbm_" + "Z9y8X7w6" * 4
HEADER = "Reference notes from the user's SecondBrain memory"

FAKE = r'''
import json, sys
mode, side = sys.argv[1], sys.argv[2]
raw = sys.stdin.read()
open(side, "w", encoding="utf-8").write(raw)
if mode == "crash":
    sys.exit(3)
if mode == "denied":
    print(json.dumps({"ok": False, "result": None, "error": {"code": "PERMISSION_DENIED", "message": "no", "hint": ""}}))
    sys.exit(1)
print(json.dumps({"ok": True, "error": None, "result": {
    "results": [{"path": "notes/a.md", "title": "SECRETTITLE", "category": "c", "tags": [], "snippet": "SECRETSNIPPET", "score": 1.5}] * 3,
    "count": 3, "dropped": 2, "dropped_stale": 1, "limit": 5, "read_only": True,
    "index": {"state": "fresh"}, "vault_id": "v", "grant_id": "grant_0001"}}))
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        self.script = self.root / "fake_rpp.py"
        self.script.write_text(FAKE, encoding="utf-8")
        self.side = self.root / "side.json"

    def command(self, mode="ok"):
        return json.dumps({"argv": [sys.executable, str(self.script), mode, str(self.side)], "env": {}})

    def apply(self, settings, opid="operation-0001"):
        return rpp.handle_request({"rpp": "1", "op": "settings.apply", "operation_id": opid,
                                   "payload": {"settings": settings}}, self.ctx)

    def readback(self):
        return rpp.handle_request({"rpp": "1", "op": "settings.readback", "payload": {}}, self.ctx)["result"]["settings"]


class WriteTests(Base):
    def setUp(self):
        super().setUp()
        self.base = {"memory_enabled": True, "memory_command": self.command(), "memory_token": TOKEN}

    def note(self, **extra):
        return memory.write_note(self.settings(), self.ctx.data_root, "Decision", "Use SQLite.", ["db"], operation_id="note-0000001", **extra)

    def settings(self):
        return json.loads((self.ctx.data_root / "settings.json").read_text("utf-8"))

    def test_write_needs_its_own_permission_and_never_leaks_the_token(self):
        self.assertTrue(self.apply(self.base)["ok"])
        self.assertEqual(self.note()["status"], "disabled")  # memory on, write permission off
        self.assertFalse(self.side.exists())
        self.assertTrue(self.apply({"memory_write": True}, "operation-0002")["ok"])
        result = self.note()
        self.assertEqual(result["status"], "ok")
        sent = json.loads(self.side.read_text("utf-8"))
        self.assertEqual((sent["op"], sent["operation_id"], sent["payload"]["token"]), ("memory.write", "note-0000001", TOKEN))
        self.assertNotIn(TOKEN, json.dumps(result))

    def test_denied_is_reported_not_raised(self):
        self.apply({**self.base, "memory_write": True, "memory_command": self.command("denied")})
        self.assertEqual(self.note()["status"], "denied")


class SettingsTests(Base):
    def test_partial_apply_keeps_unrelated_keys(self):
        self.assertTrue(self.apply({"default_worker": "claude", "default_timeout_seconds": 120})["ok"])
        self.assertTrue(self.apply({"default_worker_profile": "prof"}, "operation-0002")["ok"])
        settings = self.readback()
        self.assertEqual((settings["default_worker"], settings["default_timeout_seconds"],
                          settings["default_worker_profile"]), ("claude", 120, "prof"))

    def test_token_is_write_only(self):
        response = self.apply({"memory_enabled": True, "memory_command": self.command(), "memory_token": TOKEN})
        self.assertTrue(response["ok"], response)
        self.assertNotIn("memory_token", json.loads((self.ctx.data_root / "settings.json").read_text("utf-8")))
        self.assertEqual(self.readback()["memory_token"], memory.REDACTED)
        for path in self.ctx.data_root.rglob("*"):
            if path.is_file() and path.name != memory.TOKEN_FILE and path.name != ".engine-key":
                self.assertNotIn(TOKEN, path.read_text("utf-8", errors="replace"), path.name)
        self.assertNotIn(TOKEN, json.dumps(response))
        self.assertEqual(memory.load_token(self.ctx.data_root), TOKEN)

    def test_redacted_keeps_and_empty_clears(self):
        self.apply({"memory_enabled": True, "memory_command": self.command(), "memory_token": TOKEN})
        self.assertTrue(self.apply({"memory_token": memory.REDACTED}, "operation-0002")["ok"])
        self.assertTrue(self.apply({"default_worker": "claude"}, "operation-0003")["ok"])
        self.assertEqual(memory.load_token(self.ctx.data_root), TOKEN)
        self.assertTrue(self.apply({"memory_enabled": False, "memory_token": ""}, "operation-0004")["ok"])
        self.assertIsNone(memory.load_token(self.ctx.data_root))
        self.assertEqual(self.readback()["memory_token"], "")

    def test_digest_changes_with_token_without_containing_it(self):
        base = {"memory_command": self.command()}
        first = self.apply({**base, "memory_token": TOKEN}, "operation-0001")["result"]["settings_sha256"]
        second = self.apply({**base, "memory_token": OTHER_TOKEN}, "operation-0002")["result"]["settings_sha256"]
        self.assertNotEqual(first, second)
        receipt = (self.ctx.data_root / "receipts" / "operation-0002.json").read_text("utf-8")
        self.assertNotIn(OTHER_TOKEN, receipt)

    def test_enabled_requires_command_and_token(self):
        def errors(settings):
            result = rpp.handle_request({"rpp": "1", "op": "settings.validate", "payload": {"settings": settings}},
                                        self.ctx)["result"]
            return {error["key"] for error in result["errors"]}

        self.assertEqual(errors({"memory_enabled": True}), {"memory_enabled"})
        self.assertEqual(errors({"memory_enabled": True, "memory_command": self.command()}), {"memory_enabled"})
        self.assertEqual(errors({"memory_enabled": True, "memory_command": self.command(), "memory_token": TOKEN}), set())
        self.assertEqual(errors({"memory_enabled": False}), set())
        self.assertEqual(errors({"memory_token": "bad"}), {"memory_token"})
        self.assertFalse(self.apply({"memory_enabled": True}, "operation-0009")["ok"])


class TaskTests(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "Fixture"),
                     ("config", "user.email", "fixture@example.invalid")]:
            self.git(*args)
        (self.repo / "owned.txt").write_text("base\n", encoding="utf8")
        self.git("add", ".")
        self.git("commit", "-m", "fixture baseline")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)

    def hub(self, mode="ok", enabled=True):
        self.ctx.data_root.mkdir(parents=True, exist_ok=True)
        settings = {"memory_enabled": enabled, "memory_command": self.command(mode)}
        (self.ctx.data_root / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        memory.store_token(self.ctx.data_root, TOKEN)
        return settings

    def create(self, settings=None, **extra):
        request = dict(project_root=str(self.repo), task="fixture task", worker="custom", kind="write",
                       ownership=["owned.txt"], forbidden=[],
                       command=[sys.executable, "-c", "from pathlib import Path; Path('owned.txt').write_text('changed\\n')"],
                       acceptance=[[sys.executable, "-c", "from pathlib import Path; assert Path('owned.txt').read_text() == 'changed\\n'"]],
                       timeout_seconds=30)
        request.update(extra)
        return runner.create_task(self.ctx, request, settings=settings)

    def policy(self, created):
        return load_signed(self.ctx, self.ctx.run_dir(created["run_id"]) / "request.json")["memory_policy"]

    def test_policy_matrix(self):
        with self.assertRaisesRegex(ValueError, "memory requested but SecondBrain access is not enabled"):
            self.create(settings={}, memory={"use": True})
        self.assertEqual(self.policy(self.create(settings={}, memory={"use": False})),
                         {"use": False, "source": "explicit"})
        self.assertEqual(self.policy(self.create(settings={})), {"use": False, "source": "off"})
        settings = self.hub()
        self.assertEqual(self.policy(self.create(settings=settings)), {"use": False, "source": "off"})  # permission, not default
        self.assertEqual(self.policy(self.create(settings=settings, memory={"use": False})),
                         {"use": False, "source": "explicit"})
        self.assertEqual(self.policy(self.create(settings=settings, memory={"use": True, "query": "alpha beta"})),
                         {"use": True, "source": "explicit", "query": "alpha beta"})

    def test_a_lane_context_uses_the_main_root_for_the_token_at_creation(self):
        settings = self.hub()
        lane_ctx = EngineContext(self.root / "data" / "campaigns" / "camp-x" / "lanes" / "lane")  # holds neither settings nor token
        request = dict(project_root=str(self.repo), task="fixture task", worker="custom", kind="write", ownership=["owned.txt"], forbidden=[],
                       command=[sys.executable, "-c", "pass"], acceptance=[[sys.executable, "-c", "pass"]], timeout_seconds=30,
                       memory={"use": True})
        with self.assertRaisesRegex(ValueError, "not enabled"):
            runner.create_task(lane_ctx, request, settings=settings)
        created = runner.create_task(lane_ctx, request, settings=settings, main_root=self.ctx.data_root)
        policy = load_signed(lane_ctx, lane_ctx.run_dir(created["run_id"]) / "request.json")["memory_policy"]
        self.assertEqual(policy, {"use": True, "source": "explicit"})

    def test_policy_rejects_bad_requests(self):
        settings = self.hub()
        for bad in ({"bogus": 1}, {"use": "yes"}, {"query": ""}, {"query": "x" * 201}, "text"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.create(settings=settings, memory=bad)

    def run_task(self, **extra):
        created = self.create(**extra)
        result = runner.execute_task(self.ctx, created["run_id"])
        return result, self.ctx.run_dir(created["run_id"])

    def test_context_reaches_brief_and_evidence_is_clean(self):
        self.hub()
        result, directory = self.run_task(memory={"use": True})
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["memory"], {"status": "ok", "count": 3})
        brief = (directory / "brief.md").read_text("utf-8")
        self.assertIn("Explicit local task; no required memory integration.", brief)
        self.assertIn(HEADER, brief)
        self.assertIn("notes/a.md", brief)
        self.assertNotIn(TOKEN, brief)
        evidence = load_signed(self.ctx, directory / "memory-context.json")
        self.assertEqual(set(evidence), {"status", "count", "paths", "scores", "index_state", "dropped",
                                         "dropped_stale", "query_terms", "grant_id"})
        self.assertEqual((evidence["count"], evidence["dropped"], evidence["dropped_stale"]), (3, 2, 1))
        self.assertEqual((evidence["index_state"], evidence["grant_id"]), ("fresh", "grant_0001"))
        raw = (directory / "memory-context.json").read_text("utf-8")
        for secret in ("SECRETSNIPPET", "SECRETTITLE", TOKEN, "fake_rpp"):
            self.assertNotIn(secret, raw)
        for path in directory.rglob("*.json"):
            self.assertNotIn(TOKEN, path.read_text("utf-8"), path.name)
        self.assertEqual(json.loads(self.side.read_text("utf-8"))["payload"]["token"], TOKEN)

    def test_failing_child_never_fails_the_task(self):
        for mode, status in (("denied", "denied"), ("crash", "error")):
            with self.subTest(mode=mode):
                self.hub(mode)
                result, directory = self.run_task(memory={"use": True})
                self.assertEqual(result["status"], "completed", result)
                self.assertEqual(result["memory"]["status"], status)
                self.assertNotIn(HEADER, (directory / "brief.md").read_text("utf-8"))
                self.assertEqual(load_signed(self.ctx, directory / "memory-context.json")["status"], status)

    def test_disabled_after_creation_runs_without_memory(self):
        settings = self.hub()
        created = self.create(settings=settings, memory={"use": True})
        self.hub(enabled=False)
        result = runner.execute_task(self.ctx, created["run_id"])
        directory = self.ctx.run_dir(created["run_id"])
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["memory"]["status"], "disabled")
        self.assertNotIn(HEADER, (directory / "brief.md").read_text("utf-8"))
        self.assertFalse(self.side.exists())

    def test_enabling_memory_is_a_permission_not_a_default(self):
        self.hub()
        result, directory = self.run_task()  # the Hub enabled memory, the task did not opt in
        self.assertEqual(result["status"], "completed", result)
        self.assertNotIn("memory", result)
        self.assertFalse(self.side.exists())

    def test_no_memory_when_policy_off(self):
        result, directory = self.run_task(settings={})
        self.assertEqual(result["status"], "completed", result)
        self.assertNotIn("memory", result)
        self.assertFalse((directory / "memory-context.json").exists())


class LaneRootTests(Base):
    def test_settings_root_prefers_valid_main_root(self):
        main = self.root / "main"
        main.mkdir()
        with mock.patch.dict(os.environ, {"RESPECTED_ORCH_MAIN_ROOT": str(main)}):
            self.assertEqual(runner.settings_root(self.ctx), self.ctx.data_root)  # no settings.json yet
            (main / "settings.json").write_text("{}", encoding="utf-8")
            self.assertEqual(runner.settings_root(self.ctx), main)
        with mock.patch.dict(os.environ, {"RESPECTED_ORCH_MAIN_ROOT": "relative"}):
            self.assertEqual(runner.settings_root(self.ctx), self.ctx.data_root)

    def test_main_root_survives_environment_scrub(self):
        from respected_orchestrator.engine.processes import scrub_environment
        self.assertIn("RESPECTED_ORCH_MAIN_ROOT", scrub_environment({"RESPECTED_ORCH_MAIN_ROOT": "x", "API_TOKEN": "y"}))

    def test_maf_lane_passes_main_root(self):
        seen = []

        def fake_execute(command, cwd, timeout, **kwargs):
            seen.append(kwargs)
            return SimpleNamespace(stdout='{"status": "MASTER_APPROVED"}', stderr="")

        lane = EngineContext(self.root / "lane")
        with mock.patch.dict(os.environ), mock.patch.object(campaign, "execute", fake_execute):
            os.environ.pop("RESPECTED_ORCH_MAIN_ROOT", None)
            campaign._maf_lane(lane, "run-1", 5, self.ctx.data_root)
            campaign._maf_lane(lane, "run-1", 5)
        self.assertEqual(seen[0]["env"]["RESPECTED_ORCH_MAIN_ROOT"], str(self.ctx.data_root))
        self.assertTrue(seen[0]["scrub_env"])
        self.assertNotIn("RESPECTED_ORCH_MAIN_ROOT", seen[1]["env"])


if __name__ == "__main__":
    unittest.main()
