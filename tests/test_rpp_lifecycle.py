"""RPP v1.1 lifecycle surface: plans, journal replay, rollback (temp dirs only)."""
import json
from pathlib import Path
import tempfile
import unittest

from respected_orchestrator import __version__

from respected_orchestrator.interfaces import rpp
from respected_orchestrator.context import EngineContext, atomic_write_json

OPID = "lifecycle-0001"
OPID2 = "lifecycle-0002"


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        self.app = self.root / "app"
        self.files = {"bin/tool.txt": "hello", "share/data.txt": "v1"}

    def call(self, op, payload=None, operation_id=None, version="1.1"):
        request = {"rpp": version, "op": op, "payload": payload if payload is not None else {}}
        if operation_id is not None:
            request["operation_id"] = operation_id
        return rpp.handle_request(request, self.ctx)

    def target(self, **extra):
        target = {"app_root": str(self.app), "files": dict(self.files)}
        target.update(extra)
        return target

    def receipt_file(self, operation_id):
        return self.ctx.data_root / "receipts" / f"{operation_id}.json"

    def test_plan_is_read_only(self):
        before = sorted(str(path) for path in self.root.rglob("*"))
        response = self.call("lifecycle.plan", {"action": "install", "target": self.target()})
        self.assertTrue(response["ok"])
        result = response["result"]
        self.assertTrue(result["dry_run"])
        ids = [step["id"] for step in result["plan"]["steps"]]
        self.assertEqual(ids, ["write:bin/tool.txt", "write:share/data.txt", "manifest"])
        self.assertFalse(self.app.exists())
        self.assertEqual(before, sorted(str(path) for path in self.root.rglob("*")))

    def test_apply_install_writes_files_and_receipt(self):
        response = self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["status"], "applied")
        self.assertEqual((self.app / "bin/tool.txt").read_text("utf-8"), "hello")
        manifest = json.loads((self.app / ".respected/install.json").read_text("utf-8"))
        self.assertEqual(set(manifest["files"]), set(self.files))
        self.assertEqual(manifest["product_version"], __version__)
        self.assertTrue(self.receipt_file(OPID).is_file())

    def test_apply_is_idempotent_per_operation_id(self):
        first = self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        second = self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        self.assertEqual(first["result"]["applied_at"], second["result"]["applied_at"])
        self.assertEqual(first["result"]["usage"], second["result"]["usage"])

    def test_apply_conflict(self):
        self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        changed = {"app_root": str(self.app), "files": {"bin/tool.txt": "changed"}}
        conflict = self.call("lifecycle.apply", {"action": "install", "target": changed}, operation_id=OPID)
        self.assertEqual(conflict["error"]["code"], "LIFECYCLE_CONFLICT")
        self.assertEqual((self.app / "bin/tool.txt").read_text("utf-8"), "hello")

    def test_crash_journal_replay_resumes(self):
        target = self.target()
        steps = rpp.lifecycle.plan("install", target)["plan"]["steps"]
        (self.app / "bin").mkdir(parents=True, exist_ok=True)
        (self.app / "bin/tool.txt").write_text("hello", encoding="utf-8")
        receipt = {"operation_id": OPID, "op": "lifecycle.apply", "action": "install",
                   "target_sha256": rpp.lifecycle._fingerprint("install", self.app, self.files, False),
                   "app_root": str(self.app), "status": "in_progress", "started_at": "t0",
                   "steps": steps, "completed": ["write:bin/tool.txt"],
                   "backup": {"bin/tool.txt": {"existed": False, "content": None}},
                   "irreversible_applied": False, "usage": rpp.lifecycle.usage_zero()}
        atomic_write_json(self.receipt_file(OPID), receipt)
        replay = self.call("lifecycle.apply", {"action": "install", "target": target}, operation_id=OPID)
        self.assertTrue(replay["ok"])
        self.assertEqual(replay["result"]["status"], "applied")
        self.assertEqual(set(replay["result"]["completed"]),
                         {"write:bin/tool.txt", "write:share/data.txt", "manifest"})
        self.assertTrue((self.app / "share/data.txt").is_file())
        self.assertTrue((self.app / ".respected/install.json").is_file())

    def test_uninstall_removes_only_owned_files(self):
        self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        (self.app / "user-notes.txt").write_text("keep me", encoding="utf-8")
        response = self.call("lifecycle.apply",
                             {"action": "uninstall", "target": {"app_root": str(self.app)}},
                             operation_id=OPID2)
        self.assertTrue(response["ok"])
        self.assertFalse((self.app / "bin/tool.txt").exists())
        self.assertTrue((self.app / "user-notes.txt").is_file())
        self.assertFalse((self.app / ".respected/install.json").exists())
        self.assertTrue(self.ctx.data_root.is_dir())

    def test_rollback_restores_previous_contents(self):
        self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        updated = {"app_root": str(self.app), "files": {"bin/tool.txt": "hello", "share/data.txt": "v2"}}
        self.call("lifecycle.apply", {"action": "update", "target": updated}, operation_id=OPID2)
        self.assertEqual((self.app / "share/data.txt").read_text("utf-8"), "v2")
        rolled = self.call("lifecycle.rollback", {"operation_id": OPID2})
        self.assertTrue(rolled["ok"])
        self.assertEqual(rolled["result"]["status"], "rolled_back")
        self.assertEqual((self.app / "share/data.txt").read_text("utf-8"), "v1")
        again = self.call("lifecycle.rollback", {"operation_id": OPID2})
        self.assertEqual(again["result"]["status"], "rolled_back")

    def test_rollback_unavailable_for_purge(self):
        self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        self.call("lifecycle.apply",
                  {"action": "uninstall", "target": {"app_root": str(self.app), "purge": True}},
                  operation_id=OPID2)
        response = self.call("lifecycle.rollback", {"operation_id": OPID2})
        self.assertEqual(response["error"]["code"], "ROLLBACK_UNAVAILABLE")

    def test_repair_restores_missing_file(self):
        self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        (self.app / "share/data.txt").unlink()
        plan = self.call("lifecycle.plan", {"action": "repair", "target": self.target()})
        ids = [step["id"] for step in plan["result"]["plan"]["steps"]]
        self.assertEqual(ids, ["write:share/data.txt", "manifest"])
        self.call("lifecycle.apply", {"action": "repair", "target": self.target()}, operation_id=OPID2)
        self.assertEqual((self.app / "share/data.txt").read_text("utf-8"), "v1")

    def test_status_matches_receipt(self):
        self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        status = self.call("lifecycle.status", {"operation_id": OPID})
        direct = self.call("operation.receipt", {"operation_id": OPID})
        self.assertEqual(status["result"], direct["result"])

    def test_plan_exposes_irreversible_step(self):
        self.call("lifecycle.apply", {"action": "install", "target": self.target()}, operation_id=OPID)
        plan = self.call("lifecycle.plan",
                         {"action": "uninstall", "target": {"app_root": str(self.app), "purge": True}})
        last = plan["result"]["plan"]["steps"][-1]
        self.assertFalse(last["reversible"])
        self.assertIsNotNone(last["irreversible_reason"])

    def test_apply_requires_operation_id_and_valid_action(self):
        bad = self.call("lifecycle.apply", {"action": "install", "target": self.target()})
        self.assertEqual(bad["error"]["code"], "BAD_REQUEST")
        bad_action = self.call("lifecycle.plan", {"action": "detonate", "target": self.target()})
        self.assertEqual(bad_action["error"]["code"], "BAD_REQUEST")

    def test_unsafe_path_rejected(self):
        target = {"app_root": str(self.app), "files": {"../escape.txt": "x"}}
        response = self.call("lifecycle.plan", {"action": "install", "target": target})
        self.assertEqual(response["error"]["code"], "BAD_REQUEST")

    def test_uninstall_without_install_fails(self):
        response = self.call("lifecycle.apply",
                             {"action": "uninstall", "target": {"app_root": str(self.app)}},
                             operation_id=OPID)
        self.assertEqual(response["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()