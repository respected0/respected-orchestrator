import json
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.workflows import roles, team_profiles as tp

TOOLS = ["codex", "claude", "agy", "opencode", "custom", "openrouter", "cursor"]


def member(role="implementer", **over):
    return {"id": role, "role": role, "assignment": {"tool": "codex", "profile": "gpt"}, **over}


def code_of(fn, *a, **k):
    with_ = None
    try:
        fn(*a, **k)
    except tp.ProfileError as error:
        with_ = error.code
    return with_


class ProfileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def team(self, *members):
        return {"schema": 1, "id": "core", "name": "Core", "members": list(members)}

    def test_all_five_standard_profiles_validate(self):
        team = tp.validate_team(self.team(*[member(r, assignment={"tool": "claude", "profile": "m"}) for r in tp.TEAM_ROLES]), TOOLS)
        self.assertEqual([m["role"] for m in team["members"]], list(tp.TEAM_ROLES))
        self.assertEqual(team["members"][2]["capabilities"], ["read", "review"])
        self.assertEqual(tp.requested(team)["tester"], {"tool": "claude", "profile": "m", "fallbacks": []})  # qa -> engine "tester"

    def test_invalid_ids_and_shapes(self):
        for bad in ("A", "1x", "x", "has space", "../x", "ss-abc123", "a" * 41, "", None):
            self.assertEqual(code_of(tp.validate_member, member(id=bad), TOOLS), "BAD_ID", bad)
        self.assertEqual(code_of(tp.validate_member, member(role="boss"), TOOLS), "BAD_ROLE")
        self.assertEqual(code_of(tp.validate_member, "x", TOOLS), "BAD_PROFILE")
        self.assertEqual(code_of(tp.validate_member, member(name="\x00"), TOOLS), "BAD_NAME")
        self.assertEqual(code_of(tp.validate_member, member(budget={"max_weighted_tokens": 0}), TOOLS), "BAD_BUDGET")
        self.assertEqual(code_of(tp.validate_member, member(budget={"max_weighted_tokens": True}), TOOLS), "BAD_BUDGET")
        self.assertEqual(code_of(tp.validate_member, member(assignment={"tool": "nope"}), TOOLS), "BAD_ASSIGNMENT")
        self.assertEqual(code_of(tp.validate_member, member(rev=0), TOOLS), "BAD_REV")

    def test_privilege_escalation_is_refused(self):
        self.assertEqual(code_of(tp.validate_member, member("reviewer", capabilities=["read", "write"]), TOOLS), "PRIVILEGE_ESCALATION")
        self.assertEqual(code_of(tp.validate_member, member("qa", capabilities=["write"]), TOOLS), "PRIVILEGE_ESCALATION")
        self.assertEqual(code_of(tp.validate_member, member(assignment={"tool": "opencode"}, capabilities=["write"]), TOOLS), "PRIVILEGE_ESCALATION")
        self.assertEqual(code_of(tp.validate_member, member(capabilities=["root"]), TOOLS), "BAD_CAPABILITY")
        for extra in ("permissions", "allow_apply", "shell", "env", "api_key"):
            self.assertEqual(code_of(tp.validate_member, member(**{extra: True}), TOOLS), "BAD_PROFILE", extra)

    def test_no_secrets(self):
        token = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2"
        self.assertEqual(code_of(tp.validate_member, member(name=token), TOOLS), "SECRET_IN_PROFILE")
        self.assertEqual(code_of(tp.validate_member, member(assignment={"tool": "codex", "profile": "x"}, name="password=hunter22xx"), TOOLS), "SECRET_IN_PROFILE")

    def test_duplicate_ids_and_foreign_schema(self):
        self.assertEqual(code_of(tp.validate_team, self.team(member(), member()), TOOLS), "DUPLICATE_ID")
        self.assertEqual(code_of(tp.migrate, {"schema": 2, "id": "x"}, TOOLS), "UNSUPPORTED_SCHEMA")
        self.assertEqual(code_of(tp.migrate, [1], TOOLS), "UNSUPPORTED_SCHEMA")

    def test_migration_from_existing_settings(self):
        settings = {"default_worker": "codex", "default_worker_profile": "gpt", "default_reviewer_profile": "r1",
                    "default_reviewer_tool": "claude", "default_roles": json.dumps({"tester": {"tool": "claude", "profile": "q"}})}
        team = tp.load(self.root, TOOLS, settings)  # no teams.json yet
        self.assertEqual(team["id"], "default")
        self.assertEqual({m["id"]: m["assignment"]["tool"] for m in team["members"]}, {"implementer": "codex", "reviewer": "claude", "qa": "claude"})
        self.assertFalse((self.root / tp.FILE).exists())  # deriving never writes

    def test_profile_and_session_are_different_and_old_snapshot_is_frozen(self):
        team = tp.save(self.root, self.team(member(rev=1)), TOOLS)
        first = team["members"][0]
        session = tp.new_session(first)
        self.assertNotEqual(session["session_id"], first["id"])
        self.assertTrue(session["session_id"].startswith("ss-"))
        self.assertNotEqual(tp.new_session(first)["session_id"], session["session_id"])
        old = json.dumps(session["profile"], sort_keys=True)
        edited = json.loads(json.dumps(team))
        edited["members"][0]["assignment"]["profile"] = "other-model"
        saved = tp.save(self.root, edited, TOOLS, previous=team)
        self.assertEqual(saved["members"][0]["rev"], 2)
        self.assertNotEqual(tp.snapshot(saved["members"][0])["digest"], session["profile"]["digest"])
        self.assertEqual(json.dumps(session["profile"], sort_keys=True), old)  # the run's reference did not move
        again = tp.save(self.root, saved, TOOLS, previous=saved)
        self.assertEqual(again["members"][0]["rev"], 2)  # unchanged content keeps its rev
        self.assertEqual(tp.load(self.root, TOOLS)["members"][0]["assignment"]["profile"], "other-model")

    def test_deleted_cli_is_reported_not_replaced(self):
        team = tp.validate_team(self.team(member(), member("reviewer", assignment={"tool": "claude"})), TOOLS)
        status = tp.check(team, lambda tool: tool != "codex")
        self.assertEqual([(s["id"], s["status"]) for s in status], [("implementer", "tool_missing"), ("reviewer", "ok")])
        with self.assertRaises(roles.RoleError) as caught:  # and the resolver itself still refuses to substitute
            roles.resolve({}, tp.requested(team), ["implementer"], tools=TOOLS, available=lambda t: t != "codex")
        self.assertEqual(caught.exception.code, "ROLE_UNAVAILABLE")

    def test_requested_goes_through_the_normal_resolver(self):
        team = tp.validate_team(self.team(member(), member("reviewer", assignment={"tool": "claude", "profile": "r"})), TOOLS)
        got = roles.resolve({}, tp.requested(team), ["implementer", "reviewer"], tools=TOOLS, available=lambda t: True)
        self.assertEqual((got["implementer"]["source"], got["reviewer"]["profile"]), ("explicit", "r"))

    def test_unreadable_file_is_an_error_not_a_default(self):
        (self.root / tp.FILE).write_text("{not json", "utf-8")
        self.assertEqual(code_of(tp.load, self.root, TOOLS), "UNREADABLE")


if __name__ == "__main__":
    unittest.main()
