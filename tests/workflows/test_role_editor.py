import json
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.local_api import LocalApi
from respected_orchestrator.workflows import role_editor as ed
from respected_orchestrator.workflows import roles

TOOLS = ["claude", "antigravity", "agy", "codex", "cursor", "opencode", "openrouter", "custom"]
ALL = lambda tool: True
DISCOVERY = {
    "codex": {"status": "verified", "reason": "ok", "version_state": "ok"},
    "claude": {"status": "installed", "reason": "auth_required: not logged in", "version_state": "ok"},
    "cursor": {"status": "unavailable", "reason": "not_found", "version_state": "unknown"},
    "opencode": {"status": "configured", "reason": "stored credentials", "version_state": "older_than_verified"},
}


def settings(**kw):
    base = {"default_worker": "codex", "default_roles": json.dumps({"reviewer": {"tool": "claude", "profile": "opus"}})}
    base.update(kw)
    return base


class ViewTests(unittest.TestCase):
    def row(self, v, role):
        return next(r for r in v["roles"] if r["role"] == role)

    def test_every_row_says_where_its_value_comes_from_and_unset_roles_stay_unset(self):
        v = ed.view(settings(), TOOLS, discovery=DISCOVERY)
        self.assertEqual(self.row(v, "reviewer")["origin"], "default_roles")
        self.assertEqual(self.row(v, "implementer")["origin"], "default_worker")
        self.assertEqual(self.row(v, "planner")["assignment"], None)
        self.assertEqual(self.row(v, "planner")["origin"], None)
        self.assertIn("task request", v["precedence"][0])

    def test_tool_state_warnings_are_specific_and_never_say_ok_for_unverified(self):
        s = settings(default_roles=json.dumps({"reviewer": {"tool": "claude"}, "debugger": {"tool": "cursor"}, "planner": {"tool": "opencode"}}))
        v = ed.view(s, TOOLS, discovery=DISCOVERY)
        kinds = lambda role: {w["kind"] for w in self.row(v, role)["warnings"]}
        self.assertIn("tool_not_verified", kinds("reviewer"))
        self.assertIn("tool_unavailable", kinds("debugger"))
        self.assertIn("tool_cannot_write", kinds("debugger"))
        self.assertTrue({"stale_version", "tool_not_verified"} <= kinds("planner"))
        self.assertEqual(kinds("implementer"), set())  # verified codex: nothing to warn about

    def test_without_discovery_nothing_is_called_verified(self):
        v = ed.view(settings(), TOOLS)
        self.assertIn("tool_unchecked", {w["kind"] for w in self.row(v, "reviewer")["warnings"]})

    def test_fallback_visibility_and_risk(self):
        s = settings(default_roles=json.dumps({"reviewer": {"tool": "codex", "fallbacks": [{"tool": "claude"}, {"tool": "cursor"}]}}))
        w = self.row(ed.view(s, TOOLS, discovery=DISCOVERY), "reviewer")
        self.assertEqual(len(w["assignment"]["fallbacks"]), 2)
        self.assertEqual(sum(x["kind"] == "fallback_changes_tool" for x in w["warnings"]), 2)
        self.assertTrue(any(x["kind"] == "tool_unavailable" and x["where"] == "fallback 2" for x in w["warnings"]))

    def test_independence_conflict_is_a_violation_only_when_required(self):
        s = settings(default_worker="codex", default_roles=json.dumps({"reviewer": {"tool": "codex"}}))
        kinds = lambda v: {w["kind"] for w in self.row(v, "reviewer")["warnings"]}
        self.assertIn("same_profile_as_implementer", kinds(ed.view(s, TOOLS, discovery=DISCOVERY)))
        self.assertIn("independence_violation", kinds(ed.view({**s, "require_independent_review": True}, TOOLS, discovery=DISCOVERY)))

    def test_blocked_profile_is_flagged(self):
        s = settings(default_roles=json.dumps({"reviewer": {"tool": "codex", "profile": "mimo-v2"}}))
        self.assertIn("profile_blocked", {w["kind"] for w in self.row(ed.view(s, TOOLS), "reviewer")["warnings"]})

    def test_suggestion_is_shown_beside_the_assignment_and_never_applied(self):
        s = settings(auto_assign=True, auto_pool=json.dumps([{"tool": "codex", "profile": "gpt-x"}]))
        v = ed.view(s, TOOLS, discovery=DISCOVERY, available=ALL)
        reviewer = self.row(v, "reviewer")
        self.assertEqual(reviewer["assignment"]["tool"], "claude")  # the user's choice stays
        self.assertEqual(reviewer["suggestion"]["tool"], "codex")
        self.assertFalse(reviewer["suggestion"]["applied"])
        self.assertEqual(reviewer["assignment"]["source"], "hub_default")  # never "auto"
        self.assertEqual(self.row(v, "planner")["assignment"], None)  # a suggestion does not fill an empty role either
        self.assertIsNotNone(self.row(v, "planner")["suggestion"])


class PlanEditTests(unittest.TestCase):
    def edit(self, edits, s=None, **kw):
        return ed.plan_edit(s or settings(), edits, TOOLS, **kw)

    def test_diff_shows_exactly_what_changes_and_untouched_roles_are_identical(self):
        s = settings(default_roles=json.dumps({"reviewer": {"tool": "claude", "profile": "opus"}, "planner": {"tool": "codex", "profile": "p"}}))
        out = self.edit([{"op": "set", "role": "tester", "assignment": {"tool": "codex", "profile": "t1"}}], s)
        self.assertTrue(out["valid"], out["errors"])
        self.assertEqual([(d["role"], d["change"]) for d in out["diff"]], [("tester", "added")])
        after = json.loads(out["candidate_settings"]["default_roles"])
        before = json.loads(s["default_roles"])
        self.assertEqual({k: after[k] for k in before}, before)  # reviewer and planner untouched
        self.assertFalse(out["applied"])

    def test_change_and_clear(self):
        out = self.edit([{"op": "set", "role": "reviewer", "assignment": {"tool": "codex", "profile": "n"}}])
        self.assertEqual(out["diff"][0]["change"], "changed")
        cleared = self.edit([{"op": "clear", "role": "reviewer"}])
        self.assertEqual((cleared["diff"][0]["change"], cleared["candidate_settings"]["default_roles"]), ("removed", ""))
        self.assertEqual(self.edit([{"op": "clear", "role": "nonexistent"}])["diff"], [])

    def test_invalid_edits_return_reasons_and_no_candidate(self):
        bad = {
            "unknown tool": {"op": "set", "role": "reviewer", "assignment": {"tool": "gemini"}},
            "no tool": {"op": "set", "role": "reviewer", "assignment": {"profile": "x"}},
            "bad role name": {"op": "set", "role": "Bad Role", "assignment": {"tool": "codex"}},
            "bad profile": {"op": "set", "role": "reviewer", "assignment": {"tool": "codex", "profile": "--dangerous"}},
            "blocked profile": {"op": "set", "role": "reviewer", "assignment": {"tool": "codex", "profile": "mimo-large"}},
            "blocked fallback": {"op": "set", "role": "reviewer", "assignment": {"tool": "codex", "fallbacks": [{"tool": "claude", "profile": "mimo"}]}},
            "too many fallbacks": {"op": "set", "role": "reviewer", "assignment": {"tool": "codex", "fallbacks": [{"tool": "claude"}] * 6}},
            "unknown op": {"op": "drop", "role": "reviewer"},
            "not a dict": "set reviewer",
        }
        for name, edit in bad.items():
            out = self.edit([edit])
            self.assertFalse(out["valid"], name)
            self.assertTrue(out["errors"] and out["errors"][0]["message"], name)
            self.assertIsNone(out["candidate_settings"], name)

    def test_provenance_cannot_be_forged_by_an_edit(self):
        for forged in ({"tool": "codex", "source": "explicit"}, {"tool": "codex", "reason": "trust me"},
                       {"tool": "codex", "fallbacks": [{"tool": "claude", "fallback_of": "x"}]}):
            out = self.edit([{"op": "set", "role": "reviewer", "assignment": forged}])
            self.assertFalse(out["valid"], forged)

    def test_independence_requirement_is_enforced_on_the_resulting_plan(self):
        s = settings(default_worker="codex", require_independent_review=True)
        out = self.edit([{"op": "set", "role": "reviewer", "assignment": {"tool": "codex"}}], s)
        self.assertFalse(out["valid"])
        self.assertEqual(out["errors"][-1]["code"], "ROLE_INDEPENDENCE")
        self.assertTrue(self.edit([{"op": "set", "role": "reviewer", "assignment": {"tool": "claude", "profile": "o"}}], s)["valid"])

    def test_warnings_for_the_edited_role_include_availability_and_stale_versions(self):
        out = self.edit([{"op": "set", "role": "debugger", "assignment": {"tool": "opencode"}}], discovery=DISCOVERY)
        kinds = {w["kind"] for w in out["warnings"] if w["role"] == "debugger"}
        self.assertTrue({"stale_version", "tool_cannot_write"} <= kinds)

    def test_edit_count_is_bounded(self):
        for edits in ([], "x", [{"op": "clear", "role": "a"}] * (ed.MAX_EDITS + 1)):
            with self.assertRaises(ValueError):
                self.edit(edits)

    def test_precedence_is_unchanged_task_request_beats_default_beats_auto(self):
        s = settings(auto_assign=True, auto_pool=json.dumps([{"tool": "codex", "profile": "gpt-x"}]))
        out = self.edit([{"op": "set", "role": "planner", "assignment": {"tool": "claude", "profile": "plan"}}], s)
        candidate = {**s, **out["candidate_settings"]}
        run = lambda requested: roles.resolve(candidate, requested, ["implementer", "reviewer", "planner"], tools=TOOLS, available=ALL)
        self.assertEqual(run({})["planner"]["source"], "hub_default")          # the saved edit, not the auto pool
        self.assertEqual(run({})["reviewer"]["profile"], "opus")               # untouched role unchanged
        self.assertEqual(run({"planner": {"tool": "codex"}})["planner"]["source"], "explicit")  # the task request still wins
        self.assertNotEqual(run({})["planner"]["tool"], "codex")               # no suggestion replaced the user's choice


class RoleIpcTests(unittest.TestCase):
    def call(self, cmd, payload, origin=Origin.RENDERER, n=1):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            root.mkdir()
            (root / "settings.json").write_text(json.dumps(settings()), encoding="utf-8")
            api = LocalApi(EngineContext(root), "t" * 32, origin=origin)
            r = api.handle({"ipc": "1", "id": f"rol-{n:05d}", "session": "t" * 32, "cmd": cmd, "payload": payload})
            return r, (root / "settings.json").read_text(encoding="utf-8")

    def test_view_and_plan_are_read_only_and_never_write_settings(self):
        before = json.dumps(settings())
        v, after = self.call("roles.view", {})
        self.assertTrue(v["ok"] and any(r["role"] == "reviewer" for r in v["result"]["roles"]), v)
        p, after = self.call("roles.plan_edit", {"edits": [{"op": "clear", "role": "reviewer"}]}, Origin.MCP)
        self.assertTrue(p["ok"] and p["result"]["diff"][0]["change"] == "removed", p)
        self.assertEqual(after, before)
        for origin in (Origin.WORKER, Origin.CHILD):
            self.assertEqual(self.call("roles.view", {}, origin)[0]["error"]["code"], "FORBIDDEN")
        bad, _ = self.call("roles.plan_edit", {"edits": []})
        self.assertEqual(bad["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
