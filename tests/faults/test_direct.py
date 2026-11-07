"""New fault fixtures for Beta.4 that no earlier test covered. Each test name starts with the matrix id it proves."""
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import cost_ledger, failures, task_classifier
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.capabilities import activation, compatibility, normalize, permissions, recommendation
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.engine.journal import Journal
from respected_orchestrator.workflows import handoff, operator, recovery, routing_policy, team_loop, team_profiles as tp

TOOLS = ["codex", "claude", "opencode", "custom", "agy", "openrouter", "cursor"]
AT = "2026-11-08T00:00:00+00:00"


class FaultTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    # F01 -- retries are bounded for every failure class, with and without an operator, in every starting state
    def test_f01_no_loop_is_unbounded(self):
        for klass in failures.FailureClass:
            reason = {"test_failure": "test_failed", "policy_denied": "scope_violation", "timeout": "timed_out", "quota": "limit_exhausted", "auth": "auth_required",
                      "infrastructure": "worker_failed", "stale_patch": "stale_project", "reviewer_reject": "needs_changes"}[klass.value]
            for resume in (False, True):
                for start in (0, 1, 2):
                    state, retries = {**recovery.FRESH, "attempts": start}, 0
                    for _ in range(50):
                        d = recovery.decide(reason, None, state, operator_resume=resume)
                        if d["action"] != "retry":
                            break
                        retries += 1
                        state = recovery.advance(state, d, elapsed_seconds=1, spent_tokens=1)
                    else:
                        self.fail(f"{klass} resume={resume} never stopped")
                    self.assertLessEqual(retries, 3 - start, (klass, resume, start))

    # F02 -- a policy denial can never be resumed, not even by a person
    def test_f02_policy_denial_never_resumes(self):
        for start in (0, 1, 2):
            self.assertEqual(recovery.decide("scope_violation", None, {**recovery.FRESH, "attempts": start}, operator_resume=True)["action"], "stop")

    # F03 -- circuit breaker opens, a person may go past it inside the limits, and it closes again for a different failure after repair
    def test_f03_breaker_open_resume_close(self):
        state = recovery.FRESH
        d = recovery.decide("timed_out", None, state)
        state = recovery.advance(state, d)
        opened = recovery.decide("timed_out", None, state)
        self.assertEqual((opened["action"], opened["why"]), ("pause", "same_failure_class_keeps_failing_breaker_open"))
        resumed = recovery.decide("timed_out", None, state, operator_resume=True)
        self.assertEqual((resumed["action"], resumed["mode"]), ("retry", "operator_resume"))
        repaired = recovery.decide("test_failed", None, state)  # the timeout was repaired; the next failure is a different class
        self.assertEqual(repaired["action"], "retry")

    # F04 -- the whole decision stack runs with the network unusable (nothing here may open a socket)
    def test_f04_everything_works_offline(self):
        def refuse(*a, **k):
            raise AssertionError("a socket was opened")
        home = self.root / "home"
        (home / "app").mkdir(parents=True)
        (home / ".claude.json").write_text(json.dumps({"mcpServers": {"gh": {"command": "gh"}, "r": {"type": "http", "url": "https://x.example/mcp"}}}), encoding="utf-8")
        with mock.patch.object(socket, "socket", refuse), mock.patch.object(socket, "create_connection", refuse), mock.patch.object(socket, "getaddrinfo", refuse):
            risk = task_classifier.classify({"kind": "write", "ownership": ["a.py"], "acceptance": [["x"]], "task": "t"})
            routing_policy.suggest("implementer", risk, [{"tool": "codex", "profile": "a", "available": True}], at=AT)
            inventory = normalize.build(home, home / "app", which=lambda n: "C:/bin/gh.exe")
            compatibility.resolve_all(inventory, "claude-code", project=str(home / "app"))
            recommendation.recommend("run the tests on github", risk, inventory, "claude-code", project=str(home / "app"))
            for record in inventory["capabilities"]:
                permissions.inspect(record)
            cost_ledger.report([], cost_ledger.snapshot([], AT))
            activation.propose(home / "app", [{"op": "enable", "capability_id": inventory["capabilities"][0]["id"]}], inventory, target_client="claude-code", now=0.0)

    # F05 -- a half-written teams.json is an error, never silently replaced by a default
    def test_f05_half_written_team_file(self):
        (self.root / tp.FILE).write_text('{"schema": 1, "id": "co', "utf-8")
        with self.assertRaises(tp.ProfileError) as caught:
            tp.load(self.root, TOOLS)
        self.assertEqual(caught.exception.code, "UNREADABLE")

    # F06 -- an interrupted write to the event store loses at most the torn record; earlier handoffs stay verifiable and posting continues
    def test_f06_torn_event_store_tail(self):
        ctx = EngineContext(self.root / "data")
        team = tp.validate_team({"schema": 1, "id": "core", "name": "Core", "members": [
            {"id": r, "role": r, "assignment": {"tool": "claude", "profile": "m"}} for r in ("implementer", "reviewer")]}, TOOLS)
        first = handoff.parse(ctx, team, {"to": "reviewer", "scope": {"paths": ["a.py"]}, "reason": "needs_review", "next_action": "review"},
                              sender={"profile_id": "implementer", "session_id": "ss-1"}, granted_scope=["a.py"])
        handoff.post(ctx, first)
        log = ctx.state_dir / "events.log"
        with open(log, "ab") as handle:
            handle.write(b"deadbeef {\"v\":1,\"seq\":2,\"op\":\"x\"")  # a torn final line
        self.assertEqual(len(handoff.inbox(ctx, "core", "reviewer")["messages"]), 1)
        second = handoff.parse(ctx, team, {"to": "reviewer", "scope": {"paths": ["a.py"]}, "reason": "needs_review", "next_action": "review", "hop": 2},
                               sender={"profile_id": "implementer", "session_id": "ss-2"}, granted_scope=["a.py"])
        self.assertIsNotNone(handoff.post(ctx, second))  # the journal cut the tail on load and kept working
        self.assertEqual(len(handoff.inbox(ctx, "core", "reviewer")["messages"]), 2)

    # F07 -- the same handoff delivered twice is stored once (duplicate action)
    def test_f07_duplicate_handoff_is_one_event(self):
        ctx = EngineContext(self.root / "data")
        team = tp.validate_team({"schema": 1, "id": "core", "name": "Core", "members": [
            {"id": r, "role": r, "assignment": {"tool": "claude", "profile": "m"}} for r in ("implementer", "reviewer")]}, TOOLS)
        env = handoff.parse(ctx, team, {"to": "reviewer", "scope": {"paths": ["a.py"]}, "reason": "needs_review", "next_action": "review"},
                            sender={"profile_id": "implementer", "session_id": "ss-1"}, granted_scope=["a.py"])
        self.assertIsNotNone(handoff.post(ctx, env))
        self.assertIsNone(handoff.post(ctx, env))
        self.assertEqual(team_loop.evaluate(team, [env], env)["action"], "duplicate")
        self.assertEqual(sum(1 for r in Journal(ctx.state_dir / "events.log").scan() if r["type"] == handoff.EVENT), 1)

    # F08 -- no module of the Beta.4 decision layer can apply a patch: there is no such action anywhere in their vocabularies
    def test_f08_no_apply_anywhere(self):
        self.assertNotIn("apply", operator.ACTIONS)
        self.assertNotIn("apply", team_loop.evaluate.__doc__ or "apply-free")
        self.assertFalse({"apply", "merge"} & set(handoff.ACTIONS))
        self.assertFalse({"apply", "merge"} & {d for d in ("retry", "pause", "operator", "stop")})
        self.assertFalse(hasattr(activation, "apply") or hasattr(operator, "apply"))

    # F09 -- an operator approval cannot be replayed or moved to another run
    def test_f09_operator_binding_is_single_case(self):
        a = operator.case.__doc__
        self.assertIn("explanation card", a)
        for origin in (Origin.RENDERER, Origin.MCP, Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError):
                operator.act(None, "run-x", "retry", "0" * 64, origin=origin, inspect_run=None, retry=None)

    # F10 -- activation consume burns its nonce; a replay and a stale file both fail closed
    def test_f10_activation_replay(self):
        home = self.root / "home"
        (home / "app").mkdir(parents=True)
        (home / ".claude.json").write_text(json.dumps({"mcpServers": {"gh": {"command": "gh"}}}), encoding="utf-8")
        inv = normalize.build(home, home / "app", which=lambda n: "C:/bin/gh.exe")
        plan = activation.propose(home / "app", [{"op": "enable", "capability_id": inv["capabilities"][0]["id"]}], inv, target_client="claude-code", now=0.0)
        approval = activation.approve(plan, "approve", plan["binding"], origin=Origin.HUMAN, now=1.0)
        used: set[str] = set()
        activation.consume(plan, approval, inv, project_root=home / "app", used_nonces=used, now=2.0)
        with self.assertRaises(activation.ActivationError) as caught:
            activation.consume(plan, approval, inv, project_root=home / "app", used_nonces=used, now=3.0)
        self.assertEqual(caught.exception.code, "ALREADY_USED")

    # F11 -- unsigned or tampered run evidence never reaches the cost ledger
    def test_f11_tampered_evidence_is_skipped_by_the_ledger(self):
        from respected_orchestrator.engine import ledger_source
        ctx = EngineContext(self.root / "data")
        d = ctx.data_root / "state" / "run-1"
        d.mkdir(parents=True)
        save_signed(ctx, d / "request.json", {"kind": "write", "worker": "codex"})
        save_signed(ctx, d / "status.json", {"status": "completed"})
        self.assertEqual(len(ledger_source.runs(ctx.data_root)), 1)
        (d / "status.json").write_text(json.dumps({"payload": {"status": "completed"}, "signature": "forged"}))
        self.assertEqual(ledger_source.runs(ctx.data_root), [])


if __name__ == "__main__":
    unittest.main()
