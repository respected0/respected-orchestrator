import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from respected_orchestrator.workflows import maf_workflow, roles
from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.runner import SUPPORTED_AGENTS, create_task, inspect_task

TOOLS = list(SUPPORTED_AGENTS)


def resolve(settings=None, requested=None, needed=("implementer",), up=("codex", "claude", "custom"), **kw):
    return roles.resolve(settings or {}, requested or {}, list(needed), tools=TOOLS, available=lambda t: t in up, **kw)


class ResolutionTests(unittest.TestCase):
    def test_explicit_beats_hub_default_beats_auto_and_every_model_fits_every_role(self):
        settings = {"default_reviewer_profile": "hubmodel",
                    "default_roles": json.dumps({"planner": {"tool": "claude", "profile": "p1"}}),
                    "auto_assign": True, "auto_pool": json.dumps([{"tool": "codex", "profile": "poolmodel"}])}
        got = resolve(settings, {"reviewer": {"tool": "claude", "profile": "mine"}},
                      ["implementer", "reviewer", "planner", "tester"])
        self.assertEqual((got["reviewer"]["profile"], got["reviewer"]["source"]), ("mine", "explicit"))
        self.assertEqual(got["planner"]["source"], "hub_default")
        self.assertEqual((got["tester"]["profile"], got["tester"]["source"]), ("poolmodel", "auto"))
        same = {role: {"tool": "claude", "profile": "one"} for role in ("implementer", "reviewer", "debugger", "coordinator")}
        got = resolve({}, same, list(same))
        self.assertEqual({v["profile"] for v in got.values()}, {"one"})
        self.assertEqual(roles.check_independence(got, False), ["reviewer_same_profile_as_implementer"])
        with self.assertRaises(roles.RoleError) as caught:
            roles.check_independence(got, True)
        self.assertEqual(caught.exception.code, "ROLE_INDEPENDENCE")

    def test_auto_assignment_ranks_by_measured_record_and_is_honest_without_one(self):
        pool = json.dumps([{"tool": "claude", "profile": "a"}, {"tool": "codex", "profile": "b"}, {"tool": "custom", "profile": "c"},
                           {"tool": "gemini", "profile": "g"}])
        settings = {"auto_assign": True, "auto_pool": pool}
        table = {("write", "claude", "a"): {"runs": 6, "ok": 2, "avg_tokens": 10, "avg_seconds": 1},
                 ("write", "codex", "b"): {"runs": 6, "ok": 6, "avg_tokens": 90, "avg_seconds": 1}}
        got = resolve(settings, {}, ["tester"], history=lambda: table)["tester"]
        self.assertEqual(got["basis"], "pool_order")  # no read-family history: says so, takes the first usable entry
        self.assertIn("not a measured recommendation", got["reason"])
        self.assertEqual((got["tool"], got["profile"]), ("claude", "a"))
        self.assertEqual([e["tool"] for e in got["excluded"]], ["custom", "gemini"])  # cannot do read work / not installed
        got = roles.recommend("debugger", [roles.normalize("x", e, tools=TOOLS) for e in json.loads(pool)], settings,
                              lambda t: t in ("claude", "codex", "custom"), "codex", [], lambda: table)
        self.assertEqual((got["basis"], got["tool"], got["profile"]), ("history", "codex", "b"))  # 6/6 beats 2/6
        self.assertEqual([r["profile"] for r in got["ranking"]], ["b", "a"])
        self.assertIn("6/6", got["reason"])
        self.assertIn("cannot do debugger work", [e["excluded"] for e in got["excluded"] if e["tool"] == "custom"][0])

    def test_a_configured_role_with_the_tools_own_model_is_an_assignment(self):
        hub = {"default_roles": json.dumps({"reviewer": {"tool": "claude", "profile": ""}})}
        got = resolve(hub, {}, ["implementer", "reviewer"])["reviewer"]
        self.assertEqual((got["tool"], got["profile"], got["source"]), ("claude", "", "hub_default"))
        with self.assertRaises(roles.RoleError):  # the legacy single-profile key still means "unset" when empty
            resolve({"default_reviewer_profile": ""}, {}, ["implementer", "reviewer"])

    def test_roles_nothing_can_execute_are_refused_in_a_task(self):
        from respected_orchestrator.engine import runner
        workflow = dict(reviewer_tool=None, reviewer_profile=None, deep_review_tool=None, deep_review_profile=None)
        with self.assertRaises(roles.RoleError) as caught:
            runner._explicit_roles({"roles": {"tester": {"profile": "x"}}}, workflow)
        self.assertEqual(caught.exception.code, "ROLE_NOT_EXECUTABLE")

    def test_nothing_is_assigned_silently(self):
        with self.assertRaises(roles.RoleError) as caught:
            resolve({}, {}, ["implementer", "reviewer"])
        self.assertEqual(caught.exception.code, "ROLE_UNASSIGNED")
        self.assertEqual(resolve({}, {}, ["implementer"], optional=["reviewer"]).keys(), {"implementer"})
        # auto is opt-in, and an explicit unavailable choice is an error, not a substitution
        with self.assertRaises(roles.RoleError) as caught:
            resolve({"auto_assign": True, "auto_pool": json.dumps([{"tool": "codex", "profile": "x"}])},
                    {"reviewer": {"tool": "gemini", "profile": "g"}}, ["implementer", "reviewer"])
        self.assertEqual(caught.exception.code, "ROLE_UNAVAILABLE")

    def test_fallbacks_are_only_the_listed_ones(self):
        ask = {"reviewer": {"tool": "gemini", "profile": "g", "fallbacks": [{"tool": "claude", "profile": "c"}]}}
        got = resolve({}, ask, ["implementer", "reviewer"])["reviewer"]
        self.assertEqual((got["tool"], got["profile"], got["source"]), ("claude", "c", "explicit"))
        self.assertIn("gemini", got["fallback_of"])

    def test_blocked_profiles_are_a_setting_not_code(self):
        with self.assertRaises(roles.RoleError):
            resolve({}, {"reviewer": "MiMo-9"}, ["implementer", "reviewer"])
        got = resolve({"blocked_profiles": ""}, {"reviewer": "MiMo-9"}, ["implementer", "reviewer"])
        self.assertEqual(got["reviewer"]["profile"], "MiMo-9")

    def test_settings_validation(self):
        self.assertEqual(roles.validate_settings({"default_roles": "{}", "auto_pool": "[]"}, TOOLS), [])
        for bad in ({"default_roles": "[1]"}, {"default_roles": '{"Bad Role": "x"}'}, {"auto_pool": '[{"tool": 1}]'},
                    {"default_roles": '{"planner": {"tool": "nope"}}'}, {"auto_pool": "{"}):
            self.assertTrue(roles.validate_settings(bad, TOOLS), bad)


class CommandTests(unittest.TestCase):
    def test_profile_is_the_model_and_only_writers_may_edit(self):
        from respected_orchestrator.engine import runner
        with mock.patch.object(runner, "get_cli_command", return_value=["tool"]):
            self.assertEqual(runner.command_for("claude", "p", profile="m", write=True),
                             ["tool", "--model", "m", "--permission-mode", "acceptEdits", "--output-format", "json", "-p", "p"])
            self.assertEqual(runner.command_for("claude", "p"), ["tool", "--output-format", "json", "-p", "p"])
            self.assertEqual(runner.command_for("gemini", "p", profile="g", write=True),
                             ["tool", "--model", "g", "--approval-mode", "auto_edit", "-o", "json", "-p", "p"])
            self.assertEqual(runner.command_for("agy", "p", profile="a", write=True),
                             ["tool", "--model", "a", "--mode", "accept-edits", "--output-format", "json", "-p", "p"])
        self.assertEqual(runner.command_for("custom", "p", ["x", "{prompt}", "{profile}"], "m"), ["x", "p", "m"])

    def test_usage_comes_from_each_tools_envelope_and_unknown_is_never_zero(self):
        from respected_orchestrator.engine.runner import tool_result
        claude = json.dumps({"type": "result", "result": "hi", "usage": {
            "input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000, "output_tokens": 10,
            "output_tokens_details": {"thinking_tokens": 4}}, "modelUsage": {"claude-x": {}}})
        text, usage, model, error = tool_result("claude", claude)
        self.assertEqual((text, model, error), ("hi", "claude-x", None))
        self.assertEqual((usage["raw_input_tokens"], usage["cached_input_tokens"], usage["estimated_weighted_tokens"]),
                         (1102, 1000, 102 + 30 + 10))
        text, usage, _, error = tool_result("agy", json.dumps({"status": "SUCCESS", "response": "ok", "usage": {
            "input_tokens": 50, "output_tokens": 5, "cache_read_tokens": 0}}))
        self.assertEqual((text, usage["estimated_weighted_tokens"], error), ("ok", 55, None))
        self.assertIsNotNone(tool_result("agy", json.dumps({"status": "FAILED", "response": ""}))[3])
        self.assertIsNotNone(tool_result("claude", json.dumps({"type": "result", "is_error": True, "result": "x"}))[3])
        self.assertEqual(tool_result("claude", "plain text"), ("plain text", None, None, None))
        self.assertIsNone(tool_result("claude", json.dumps({"type": "result", "result": "x"}))[1])


class ReviewPromptTests(unittest.TestCase):
    def test_tool_reviewers_get_a_larger_diff_and_are_told_they_have_no_shell(self):
        codex = maf_workflow._review_prompt("fast", "t", {}, "diff")
        other = maf_workflow._review_prompt("fast", "t", {}, "diff", "agy")
        self.assertIn("truncated at 6000 bytes", codex)
        self.assertNotIn("no shell", codex)
        self.assertIn("truncated at 60000 bytes", other)
        self.assertIn("do not run commands", other)
        big = maf_workflow._review_prompt("fast", "t", {}, "x" * 100000, "agy")
        self.assertLessEqual(len(big), maf_workflow.MAX_PROMPT_CHARS)  # fits one Windows command line
        self.assertIn("xxxx", big)

    def test_a_tool_that_cannot_be_started_is_a_recorded_failed_review(self):
        with mock.patch.object(maf_workflow, "execute", side_effect=OSError("command line too long")):
            outcome = maf_workflow._run_tool_call("agy", "", "p", Path(tempfile.mkdtemp()), 5)
        self.assertEqual((outcome.status, outcome.cause), ("FAILED", "spawn_failed"))
        self.assertIn("too long", outcome.stderr_path.read_text(encoding="utf8"))


class MasterRoleTests(unittest.TestCase):
    def test_final_master_comes_from_the_master_role_unless_a_command_is_given(self):
        from respected_orchestrator.workflows import campaign
        from respected_orchestrator.engine import runner
        hub = {"default_roles": json.dumps({"master": {"tool": "claude", "profile": "m1"}})}
        with mock.patch.object(runner, "get_cli_command", return_value=["tool"]), \
                mock.patch.object(campaign, "tool_available", lambda t: True):
            self.assertEqual(campaign._final_command({}, hub)[:3], ["tool", "--model", "m1"])
            self.assertEqual(campaign._final_command({"master": {"tool": "claude", "profile": "m2"}}, hub)[2], "m2")
            self.assertEqual(campaign._final_command({"command": ["x", "{prompt}"]}, hub), ["x", "{prompt}"])
            with self.assertRaises(roles.RoleError):
                campaign._final_command({"command": ["x"], "master": "m"}, hub)
        self.assertEqual(campaign._final_command({}, {}), ["claude", "-p", "{prompt}"])


class TaskIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "F"), ("config", "user.email", "f@example.invalid"),
                     ("commit", "--allow-empty", "-m", "base")]:
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        self.ctx = EngineContext(self.root / "data")
        self.ctx.data_root.mkdir()

    def request(self, **extra):
        request = dict(project_root=str(self.repo), task="t", worker="custom", command=[sys.executable, "-c", "1"],
                       kind="write", ownership=["a.txt"], acceptance=[[sys.executable, "-c", "1"]], timeout_seconds=10)
        request.update(extra)
        return request

    def task(self, **extra):
        return inspect_task(self.ctx, create_task(self.ctx, self.request(**extra))["run_id"])["request"]

    def test_hub_defaults_apply_and_the_prompt_overrides_them(self):
        (self.ctx.data_root / "settings.json").write_text(json.dumps(
            {"default_reviewer_profile": "hubrev", "default_reviewer_tool": "claude"}), encoding="utf8")
        got = self.task()
        self.assertEqual(got["role_assignments"]["reviewer"]["source"], "hub_default")
        self.assertEqual((got["workflow"]["reviewer_tool"], got["workflow"]["reviewer_profile"]), ("claude", "hubrev"))
        got = self.task(workflow={"reviewer_profile": "mine"})
        self.assertEqual(got["role_assignments"]["reviewer"]["source"], "explicit")
        self.assertEqual(got["workflow"]["reviewer_profile"], "mine")

    def test_applied_dependency_output_is_a_read_only_input_of_the_next_lane(self):
        from respected_orchestrator.engine.runner import execute_task
        (self.repo / "dep.py").write_text("x = 1", encoding="utf8")  # applied by an earlier lane, still uncommitted
        code = "from pathlib import Path; assert Path('dep.py').read_text() == 'x = 1'; Path('a.txt').write_text('ok')"
        results = {}
        for label, extra in (("with", {"context_paths": ["dep.py"]}), ("without", {})):
            run_id = create_task(self.ctx, self.request(command=[sys.executable, "-c", code], **extra))["run_id"]
            results[label] = execute_task(self.ctx, run_id)
        self.assertEqual(results["with"]["status"], "completed", results["with"])
        self.assertEqual(results["with"]["changed_files"], ["a.txt"])  # the context file is not part of the change
        self.assertEqual(results["without"]["status"], "failed")

    def test_parallel_lanes_of_one_git_source_apply_in_turn(self):
        from respected_orchestrator.engine.runner import apply_task, check_result, execute_task, project_fingerprint
        runs = []
        for name in ("a.txt", "b.txt"):
            code = f"open('{name}','w').write('x')"
            runs.append(create_task(self.ctx, self.request(command=[sys.executable, "-c", code], ownership=[name]))["run_id"])
        for run_id in runs:
            self.assertEqual(execute_task(self.ctx, run_id)["status"], "completed")
        apply_task(self.ctx, runs[0])
        with self.assertRaisesRegex(ValueError, "stale"):  # the project moved on: refused by default
            check_result(self.ctx, runs[1])
        trusted = {project_fingerprint(self.repo)}  # the state the supervisor itself produced
        apply_task(self.ctx, runs[1], accepted_fingerprints=trusted)
        self.assertTrue((self.repo / "b.txt").is_file())

    def test_planner_role_drafts_a_validated_spec_and_never_starts_it(self):
        from respected_orchestrator.workflows import planner
        root = self.root
        repo = root / "plan-repo"
        repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "F"), ("config", "user.email", "f@example.invalid")]:
            subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)
        (repo / "a.py").write_text("x = 1", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "b"], cwd=repo, capture_output=True, check=True)
        lane = {"name": "one", "request": {"project_root": str(repo), "task": "t", "kind": "write", "ownership": ["a.py"],
                                           "acceptance": [["python", "-c", "1"]]}}
        good = json.dumps({"goal": "g", "phases": [{"name": "p", "auto_apply": True, "workstreams": [lane]}]})
        seen = {}

        def fake(command, cwd, timeout, **kw):
            seen["cwd"] = cwd
            return SimpleNamespace(returncode=0, stdout=json.dumps({"type": "result", "result": "here: " + good, "usage": {
                "input_tokens": 1, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 1}}), stderr="")
        with mock.patch.object(planner, "execute", fake), mock.patch.object(planner, "tool_available", lambda t: True):
            done = planner.plan(self.ctx, {"goal": "do it", "project_root": str(repo), "roles": {"planner": {"tool": "claude", "profile": "m"}}})
        self.assertEqual((done["status"], done["planner"]["source"], done["usage"]["estimated_weighted_tokens"]), ("drafted", "explicit", 2))
        self.assertNotEqual(Path(seen["cwd"]), repo)  # the planner never gets the repository
        self.assertTrue(json.loads(Path(done["draft"]).read_text(encoding="utf8"))["valid"])
        self.assertFalse((self.ctx.data_root / "projects").exists())
        bad = json.dumps({"goal": "g", "phases": []})
        with mock.patch.object(planner, "execute", lambda *a, **k: SimpleNamespace(returncode=0, stdout=bad, stderr="")),                 mock.patch.object(planner, "tool_available", lambda t: True):
            done = planner.plan(self.ctx, {"goal": "do it", "project_root": str(repo), "roles": {"planner": "m"}})
        self.assertEqual(done["status"], "invalid")
        self.assertIn("rejected by the engine", done["problem"])
        with self.assertRaises(roles.RoleError):  # no planner anywhere: clear error, nothing run
            planner.plan(self.ctx, {"goal": "do it", "project_root": str(repo)})

    def test_edit_tool_workers_are_not_told_to_edit_through_the_shell(self):
        from respected_orchestrator.engine import runner
        with mock.patch.object(runner, "get_cli_command", return_value=["agy"]),                 mock.patch.object(runner, "execute", return_value=SimpleNamespace(returncode=1, stdout="", stderr="")):
            run_id = create_task(self.ctx, self.request(worker="agy"))["run_id"]
            runner.execute_task(self.ctx, run_id)
        brief = (self.ctx.run_dir(run_id) / "brief.md").read_text(encoding="utf8")
        self.assertIn("file-editing tools", brief)
        self.assertNotIn("plain shell commands", brief)

    def test_conflicting_statements_of_one_role_are_an_error(self):
        with self.assertRaises(roles.RoleError) as caught:
            self.task(worker_profile="a", roles={"implementer": {"profile": "b"}})
        self.assertEqual(caught.exception.code, "ROLE_CONFLICT")

    def test_review_stops_before_paid_work_when_no_reviewer_exists(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        with self.assertRaisesRegex(maf_workflow.ReviewerExecutionError, "ROLE_UNASSIGNED"):
            maf_workflow.run_maf_coding_task(ctx=self.ctx, run_id=run_id)

    def test_a_review_can_run_through_any_tool_cli(self):
        completed = SimpleNamespace(returncode=0, stdout='noise {"decision": "APPROVED", "reason": "ok"}', stderr="")
        seen = {}

        def fake_command(tool, prompt, profile=None):
            seen.update(tool=tool, profile=profile)
            return [sys.executable, "-c", "1"]
        with mock.patch.object(maf_workflow, "command_for", fake_command), \
                mock.patch.object(maf_workflow, "execute", return_value=completed):
            review = maf_workflow._run_codex_review(stage="fast", task="t", result={}, profile="gem", tool="gemini",
                                                    cwd=self.repo, run_root=self.root / "rev", codex_path=None,
                                                    timeout_seconds=5)
        self.assertEqual((review["decision"], review["tool"], review["usage"]), ("APPROVED", "gemini", {}))
        self.assertEqual(seen, {"tool": "gemini", "profile": "gem"})


if __name__ == "__main__":
    unittest.main()
