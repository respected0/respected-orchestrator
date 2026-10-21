"""The planner role (workflows/planner.py): request validation, drafting and failure verdicts (fake tool, no models)."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.processes import ProcessStopped
from respected_orchestrator.workflows import planner, roles

SETTINGS = {"default_roles": json.dumps({"planner": {"tool": "claude", "profile": ""}})}


class PlannerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name).resolve()
        self.ctx = EngineContext(base / "data")
        self.repo = base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        (self.repo / "a.txt").write_text("hello")
        subprocess.run(["git", "add", "a.txt"], cwd=self.repo, check=True)

    def plan(self, request=None, completed=None, result=("", None, None, None), stopped=None, **kw):
        request = {"goal": "do it", "project_root": str(self.repo), **(request or {})}
        patches = [mock.patch.object(planner, "tool_available", return_value=True),
                   mock.patch.object(planner, "tool_result", return_value=result),
                   mock.patch.object(planner, "execute", side_effect=stopped, return_value=completed or SimpleNamespace(stdout="", returncode=0))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return planner.plan(self.ctx, request, SETTINGS, **kw)

    def test_rejects_bad_requests(self):
        for request in ({"goal": " "}, {"goal": "x", "project_root": "relative"}, {"goal": "x", "project_root": str(self.repo.parent)}):
            with self.assertRaises(ValueError):
                planner.plan(self.ctx, request, SETTINGS)
        with self.assertRaises(ValueError):
            planner.plan(self.ctx, "not a dict", SETTINGS)

    def test_custom_tool_cannot_plan(self):
        with mock.patch.object(planner, "tool_available", return_value=True), \
                self.assertRaises(roles.RoleError) as caught:
            planner.plan(self.ctx, {"goal": "x", "project_root": str(self.repo), "roles": {"planner": {"tool": "custom"}}}, SETTINGS)
        self.assertEqual(caught.exception.code, "ROLE_UNAVAILABLE")

    def test_invalid_outcomes_are_drafted_with_the_problem(self):
        self.assertIn("JSON object", self.plan(result=("no json here", None, None, None))["problem"])
        self.assertIn("exited 3", self.plan(completed=SimpleNamespace(stdout="", returncode=3))["problem"])
        self.assertIn("stopped", self.plan(stopped=ProcessStopped("timeout"))["problem"])
        bad = self.plan(result=('prefix {"goal": "x", "phases": []} suffix', {"estimated_weighted_tokens": 1}, None, None))
        self.assertEqual(bad["status"], "invalid")
        self.assertIn("rejected by the engine", bad["problem"])
        draft = json.loads(Path(bad["draft"]).read_text(encoding="utf8"))
        self.assertFalse(draft["valid"])
        self.assertEqual(draft["spec"]["goal"], "x")

    def test_context_files_stay_inside_the_project(self):
        seen = {}
        original = planner._prompt
        with mock.patch.object(planner, "_prompt", side_effect=lambda *a: seen.update(context=a[3]) or original(*a)):
            self.plan({"context_files": ["a.txt", "../outside.txt", "missing.txt"]})
        self.assertEqual(seen["context"], {"a.txt": "hello"})

    def test_json_extraction(self):
        self.assertEqual(planner._json('x {"a": 1} y'), {"a": 1})
        self.assertIsNone(planner._json("[1]"))
        self.assertIsNone(planner._json("{broken"))


if __name__ == "__main__":
    unittest.main()
