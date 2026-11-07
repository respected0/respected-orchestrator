"""The Beta.4 decision modules, exercised through the real create_task / retry_task path (workflows/run_hooks.py)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import runner
from respected_orchestrator.engine.evidence import load_signed, save_signed
from respected_orchestrator.workflows import routing_policy, run_hooks, team_profiles as tp

TOOLS = list(runner.SUPPORTED_AGENTS)


class WiringTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "F"), ("config", "user.email", "f@example.invalid")]:
            subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        (self.repo / "owned.txt").write_text("base\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=self.repo, capture_output=True, check=True)
        self.ctx = EngineContext(self.root / "data")
        for target in ("sync_credentials", "clear_worker_home"):
            patcher = mock.patch.object(runner.opencode_auth, target)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, value in (("tool_available", True), ("get_cli_command", "x.exe")):
            patcher = mock.patch.object(runner, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def request(self, **extra):
        base = dict(project_root=str(self.repo), task="fixture task", kind="write", ownership=["owned.txt"],
                    acceptance=[[sys.executable, "-c", "pass"]], timeout_seconds=10)
        return {**base, **extra}

    def stored(self, run_id):
        return load_signed(self.ctx, self.ctx.run_dir(run_id) / "request.json")

    def team(self, *members):
        return tp.save(self.ctx.data_root, {"schema": 1, "id": "core", "name": "Core", "members": list(members)}, TOOLS)

    @staticmethod
    def member(role="implementer", pid=None, tool="claude", **extra):
        return {"id": pid or role, "role": role, "assignment": {"tool": tool, "profile": "model-a"}, **extra}

    # ---- profiles -------------------------------------------------------------------------------------------------------
    def test_profile_becomes_the_explicit_implementer_and_is_frozen_in_the_run(self):
        team = self.team(self.member())
        run = runner.create_task(self.ctx, self.request(profile="implementer"), settings={})
        request = self.stored(run["run_id"])
        self.assertEqual((request["role_assignments"]["implementer"]["tool"], request["role_assignments"]["implementer"]["source"], request["worker"]),
                         ("claude", "explicit", "claude"))
        ref = request["profile_ref"]
        self.assertTrue(ref["session_id"].startswith("ss-"))
        self.assertNotEqual(ref["session_id"], "implementer")
        self.assertEqual((ref["profile"]["profile_id"], ref["profile"]["rev"]), ("implementer", 1))
        edited = json.loads(json.dumps(team))
        edited["members"][0]["assignment"]["profile"] = "model-b"
        tp.save(self.ctx.data_root, edited, TOOLS, previous=team)
        self.assertEqual(self.stored(run["run_id"])["profile_ref"], ref)  # the old run's evidence did not move
        newer = runner.create_task(self.ctx, self.request(profile="implementer"), settings={})
        self.assertEqual(self.stored(newer["run_id"])["profile_ref"]["profile"]["rev"], 2)
        self.assertNotEqual(self.stored(newer["run_id"])["profile_ref"]["session_id"], ref["session_id"])

    def test_explicit_request_beats_the_profile_and_bad_profiles_are_refused(self):
        self.team(self.member(), self.member("reviewer", tool="claude"))
        run = runner.create_task(self.ctx, self.request(profile="implementer", roles={"implementer": {"tool": "codex", "profile": "mine"}}), settings={})
        self.assertEqual(self.stored(run["run_id"])["role_assignments"]["implementer"]["profile"], "mine")
        for bad, text in (("ghost", "Unknown team profile"), ("reviewer", "only implementer or designer profiles can run a write task"), (5, "must be a team profile id")):
            with self.assertRaisesRegex(ValueError, text):
                runner.create_task(self.ctx, self.request(profile=bad), settings={})

    def test_profile_without_write_cannot_run_a_write_task(self):
        self.team(self.member(capabilities=["read"]))
        with self.assertRaisesRegex(ValueError, "not allowed to write"):
            runner.create_task(self.ctx, self.request(profile="implementer"), settings={})
        self.assertEqual(runner.create_task(self.ctx, self.request(profile="implementer", kind="read"), settings={})["status"], "queued")

    def test_profile_budget_only_lowers_the_lane_budget(self):
        self.team(self.member(budget={"max_weighted_tokens": 5000}))
        low = runner.create_task(self.ctx, self.request(profile="implementer"), settings={})
        self.assertEqual(self.stored(low["run_id"])["workflow"]["max_weighted_tokens"], 5000)
        smaller = runner.create_task(self.ctx, self.request(profile="implementer", workflow={"max_weighted_tokens": 3000}), settings={})
        self.assertEqual(self.stored(smaller["run_id"])["workflow"]["max_weighted_tokens"], 3000)
        bigger = runner.create_task(self.ctx, self.request(profile="implementer", workflow={"max_weighted_tokens": 90000}), settings={})
        self.assertEqual(self.stored(bigger["run_id"])["workflow"]["max_weighted_tokens"], 5000)

    def test_no_profile_changes_nothing(self):
        run = runner.create_task(self.ctx, self.request(), settings={})
        request = self.stored(run["run_id"])
        self.assertNotIn("profile_ref", request)
        self.assertNotIn("routing", request)

    def test_unreadable_team_file_is_an_error_not_a_default(self):
        self.ctx.data_root.mkdir(parents=True, exist_ok=True)
        (self.ctx.data_root / tp.FILE).write_text("{broken", "utf-8")
        with self.assertRaisesRegex(ValueError, "Team profiles unreadable"):
            runner.create_task(self.ctx, self.request(profile="implementer"), settings={})

    # ---- routing --------------------------------------------------------------------------------------------------------
    POOL = json.dumps([{"tool": "claude", "profile": "a"}, {"tool": "codex", "profile": "b"}])

    def routed(self, mode, history=None, **settings):
        base = {"auto_assign": True, "auto_pool": self.POOL, **({"routing_mode": mode} if mode else {}), **settings}
        return runner.create_task(self.ctx, self.request(), settings=base, history=history)

    def log(self):
        path = self.ctx.data_root / routing_policy.LOG_NAME
        return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []

    def test_shadow_is_default_logs_and_never_changes_the_assignment(self):
        run = self.routed(None)
        request = self.stored(run["run_id"])
        reviewers = [r for r in request["routing"] if r["role"] == "reviewer"]
        self.assertEqual((reviewers[0]["mode"], "applied" in reviewers[0]), ("shadow", False))
        self.assertEqual(request["role_assignments"]["reviewer"]["source"], "auto")
        self.assertTrue(any(line["role"] == "reviewer" and line["mode"] == "shadow" for line in self.log()))

    def test_off_is_the_kill_switch(self):
        run = self.routed("off")
        self.assertNotIn("routing", self.stored(run["run_id"]))
        self.assertEqual(self.log(), [])

    def test_explicit_and_configured_roles_are_never_routed(self):
        run = runner.create_task(self.ctx, self.request(roles={"reviewer": {"tool": "claude", "profile": "mine"}}),
                                 settings={"auto_assign": True, "auto_pool": self.POOL, "routing_mode": "active"})
        request = self.stored(run["run_id"])
        self.assertEqual(request["role_assignments"]["reviewer"]["profile"], "mine")
        self.assertEqual([r["role"] for r in request.get("routing", [])], [r for r in ("tester", "debugger") if r in [x["role"] for x in request.get("routing", [])]])
        self.assertTrue(all(r["role"] != "reviewer" for r in request.get("routing", [])))

    def test_active_replaces_an_automatic_pick_with_the_policy_suggestion(self):
        assigned = {"reviewer": {"tool": "claude", "profile": "a", "source": "auto", "fallbacks": []},
                    "implementer": {"tool": "codex", "profile": "", "source": "configured_default"}}
        history = lambda: {("read", "codex", "b"): {"runs": 5, "ok": 5, "avg_tokens": None, "avg_seconds": None},
                           ("read", "claude", "a"): {"runs": 5, "ok": 0, "avg_tokens": None, "avg_seconds": None}}
        settings = {"auto_pool": self.POOL, "routing_mode": "active"}
        out = run_hooks.route(self.ctx, settings, self.request(), assigned, TOOLS, lambda t: True, history, ["owned.txt"], [[sys.executable]])
        self.assertEqual(assigned["reviewer"]["profile"], "b")
        self.assertEqual((out[0]["applied"], out[0]["differs"], assigned["reviewer"]["basis"]), (True, True, "routing_policy"))
        self.assertEqual(assigned["implementer"], {"tool": "codex", "profile": "", "source": "configured_default"})  # untouched
        shadow = {"reviewer": {"tool": "claude", "profile": "a", "source": "auto", "fallbacks": []}}
        run_hooks.route(self.ctx, {**settings, "routing_mode": "shadow"}, self.request(), shadow, TOOLS, lambda t: True, history, ["owned.txt"], [[sys.executable]])
        self.assertEqual(shadow["reviewer"]["profile"], "a")  # same inputs, shadow: logged only

    # ---- recovery -------------------------------------------------------------------------------------------------------
    def fail(self, run_id, reason):
        save_signed(self.ctx, self.ctx.run_dir(run_id) / "status.json", {"run_id": run_id, "status": "failed", "reason": reason,
                                                                          **runner.failures.describe(reason)})

    def test_second_timeout_in_a_chain_is_stopped_by_the_recovery_table(self):
        first = runner.create_task(self.ctx, self.request(), settings={})["run_id"]
        self.fail(first, "timed_out")
        second = runner.retry_task(self.ctx, first)["run_id"]
        self.fail(second, "timed_out")
        with self.assertRaisesRegex(ValueError, "Recovery policy: pause .*breaker"):
            runner.retry_task(self.ctx, second)
        self.assertFalse((self.ctx.run_dir(second) / ".retry-claim").exists())  # refused before anything was claimed

    def test_a_different_class_still_retries_and_old_limits_hold(self):
        first = runner.create_task(self.ctx, self.request(), settings={})["run_id"]
        self.fail(first, "timed_out")
        second = runner.retry_task(self.ctx, first)["run_id"]
        self.fail(second, "test_failed")
        third = runner.retry_task(self.ctx, second)["run_id"]
        self.fail(third, "test_failed")
        with self.assertRaisesRegex(ValueError, "Retry budget exhausted"):
            runner.retry_task(self.ctx, third)

    def test_unclassified_failure_keeps_the_older_behaviour(self):
        first = runner.create_task(self.ctx, self.request(), settings={})["run_id"]
        save_signed(self.ctx, self.ctx.run_dir(first) / "status.json", {"run_id": first, "status": "failed", "reason": "something_new"})
        self.assertEqual(runner.retry_task(self.ctx, first)["status"], "queued")


if __name__ == "__main__":
    unittest.main()
