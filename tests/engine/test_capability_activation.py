import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.capabilities import activation as ac, normalize as nz

which = lambda name: f"C:/bin/{Path(name).name}.exe" if Path(name).name.casefold().removesuffix(".exe") in {"gh"} else None
NOW = 1_000.0


def code_of(fn, *a, **k):
    try:
        fn(*a, **k)
    except ac.ActivationError as error:
        return error.code


def tree_hash(root):
    return hashlib.sha256(b"".join(p.relative_to(root).as_posix().encode() + p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file())).hexdigest()


class ActivationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.a = self.home / "app-a"
        self.b = self.home / "app-b"
        self.a.mkdir(parents=True)
        self.b.mkdir(parents=True)
        (self.home / ".claude.json").write_text(json.dumps({"mcpServers": {"user-gh": {"command": "gh", "args": ["mcp"]}, "ghost": {"command": "nope-xyz"}},
                                                          "projects": {str(self.a): {"mcpServers": {"only-a": {"command": "gh"}}}}}), encoding="utf-8")
        self.refresh()

    def refresh(self, project=None):
        self.inv = nz.build(self.home, project or self.a, which=which)
        self.ids = {r["name"]: r["id"] for r in self.inv["capabilities"]}

    def propose(self, project=None, name="user-gh", op="enable"):
        return ac.propose(project or self.a, [{"op": op, "capability_id": self.ids[name]}], self.inv, target_client="claude-code", now=NOW)

    def approved(self, plan, now=NOW + 1):
        return ac.approve(plan, "approve", plan["binding"], origin=Origin.HUMAN, now=now)

    def consume(self, plan, approval, used=None, project=None, now=NOW + 2):
        return ac.consume(plan, approval, self.inv, project_root=project or self.a, used_nonces=set() if used is None else used, now=now)

    def test_plan_describes_the_change_and_writes_nothing(self):
        before = tree_hash(self.home)
        plan = self.propose()
        self.assertEqual(plan["status"], "proposed")
        change = plan["changes"][0]
        self.assertEqual((change["write"]["action"], Path(change["write"]["path"]).name, change["compatibility"]), ("add_entry", ".mcp.json", "compatible"))
        self.assertEqual((change["rollback"]["op"], change["execution"]), ("disable", "MANIFEST_MISSING"))  # the manifest gate is separate and still closed
        self.assertEqual(tree_hash(self.home), before)

    def test_only_a_human_can_approve_and_approval_is_bound_to_the_plan(self):
        plan = self.propose()
        for origin in (Origin.RENDERER, Origin.MCP, Origin.WORKER, Origin.CHILD):
            with self.assertRaises(PermissionError, msg=origin):
                ac.approve(plan, "approve", plan["binding"], origin=origin, now=NOW)
        self.assertEqual(code_of(ac.approve, plan, "approve", "0" * 64, origin=Origin.HUMAN, now=NOW), "BINDING_MISMATCH")
        self.assertEqual(code_of(ac.approve, plan, "approve", plan["binding"], origin=Origin.HUMAN, now=NOW + 999), "EXPIRED")
        self.assertEqual(code_of(ac.approve, plan, "maybe", plan["binding"], origin=Origin.HUMAN, now=NOW), "BAD_DECISION")
        self.assertEqual(ac.approve(plan, "deny", plan["binding"], origin=Origin.HUMAN, now=NOW)["state"], "denied")

    def test_no_approval_no_go(self):
        plan = self.propose()
        for approval in (None, {}, {"state": "denied"}, ac.approve(plan, "deny", plan["binding"], origin=Origin.HUMAN, now=NOW)):
            self.assertEqual(code_of(self.consume, plan, approval), "NOT_APPROVED", approval)

    def test_happy_path_returns_writes_and_rollback_and_is_single_use(self):
        plan = self.propose()
        approval, used = self.approved(plan), set()
        out = self.consume(plan, approval, used)
        self.assertEqual((out["ok"], len(out["writes"]), out["rollback"][0]["op"]), (True, 1, "disable"))
        self.assertEqual(code_of(self.consume, plan, approval, used), "ALREADY_USED")  # repeated activation

    def test_tampered_plan_is_rejected(self):
        plan = self.propose()
        approval = self.approved(plan)
        bad = copy.deepcopy(plan)
        bad["changes"][0]["write"]["path"] = str(self.a.parent / "elsewhere" / ".mcp.json")
        self.assertEqual(code_of(self.consume, bad, approval), "TAMPERED")
        bad = copy.deepcopy(plan)
        bad["changes"][0]["record_digest"] = "0" * 64
        self.assertEqual(code_of(self.consume, bad, approval), "TAMPERED")

    def test_cross_project_bleed(self):
        plan = self.propose()
        approval = self.approved(plan)
        self.assertEqual(code_of(self.consume, plan, approval, project=self.b), "CROSS_PROJECT")  # approved for app-a, used for app-b
        other = self.propose()
        self.assertEqual(code_of(self.consume, plan, self.approved(other) | {"plan_id": "act-other"}), "BINDING_MISMATCH")
        self.refresh(self.b)  # app-a's own entry is still visible in the user file, but it cannot be planned for app-b
        self.assertEqual(code_of(ac.propose, self.b, [{"op": "enable", "capability_id": self.ids["only-a"]}], self.inv, target_client="claude-code", now=NOW), "CROSS_PROJECT")
        self.refresh(self.a)
        self.assertEqual(code_of(ac.propose, self.b, [{"op": "enable", "capability_id": self.ids["only-a"]}], self.inv, target_client="claude-code", now=NOW), "CROSS_PROJECT")

    def test_stale_inventory_and_changed_target_file(self):
        plan = self.propose()
        approval = self.approved(plan)
        (self.home / ".claude.json").write_text(json.dumps({"mcpServers": {"user-gh": {"command": "gh", "args": ["different"]}}}), encoding="utf-8")
        self.refresh()
        self.assertEqual(code_of(self.consume, plan, approval), "STALE")
        (self.home / ".claude.json").write_text(json.dumps({"mcpServers": {"user-gh": {"command": "gh", "args": ["mcp"]}}}), encoding="utf-8")
        self.refresh()
        self.assertTrue(self.consume(plan, approval)["ok"])
        (self.a / ".mcp.json").write_text("{}", encoding="utf-8")  # the project's own config moved since the plan was shown
        self.assertEqual(code_of(self.consume, plan, approval), "STALE")

    def test_expired_approval_and_incompatible_or_unknown_capabilities(self):
        plan = self.propose()
        self.assertEqual(code_of(self.consume, plan, self.approved(plan), now=NOW + 5000), "EXPIRED")
        self.assertEqual(code_of(ac.propose, self.a, [{"op": "enable", "capability_id": self.ids["ghost"]}], self.inv, target_client="claude-code", now=NOW), "INCOMPATIBLE")
        for bad in ({"op": "enable", "capability_id": "nope"}, {"op": "wipe", "capability_id": self.ids["user-gh"]}, {}):
            self.assertEqual(code_of(ac.propose, self.a, [bad], self.inv, target_client="claude-code", now=NOW), "BAD_CHANGE")
        self.assertEqual(code_of(ac.propose, self.a, [], self.inv, target_client="claude-code", now=NOW), "EMPTY_PLAN")
        self.assertEqual(code_of(ac.propose, self.a / "missing", [{"op": "enable", "capability_id": self.ids["user-gh"]}], self.inv, target_client="claude-code", now=NOW), "PROJECT_MISSING")
        self.assertEqual(code_of(ac.propose, self.a, [{"op": "enable", "capability_id": self.ids["user-gh"]}], self.inv, target_client="notepad", now=NOW), "INCOMPATIBLE")

    def test_disable_plan_and_zero_writes_across_the_whole_flow(self):
        before = tree_hash(self.home)
        plan = self.propose(name="only-a", op="disable")
        self.assertEqual((plan["changes"][0]["write"]["action"], plan["changes"][0]["rollback"]["op"]), ("remove_entry", "enable"))
        approval = self.approved(plan)
        self.consume(plan, approval, set())
        self.assertEqual(tree_hash(self.home), before)  # the module only decides; not one byte changed through propose/approve/consume


if __name__ == "__main__":
    unittest.main()
