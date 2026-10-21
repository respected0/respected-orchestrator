"""RPP v1.0 server contract: manifest, health, settings, protocol framing (temp dirs only)."""
import json
from pathlib import Path
import tempfile
import unittest

from respected_orchestrator import __version__

from respected_orchestrator.interfaces import rpp
from respected_orchestrator.context import EngineContext

OPID = "operation-0001"


class RppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")

    def call(self, op, payload=None, operation_id=None, version="1.0"):
        request = {"rpp": version, "op": op, "payload": payload if payload is not None else {}}
        if operation_id is not None:
            request["operation_id"] = operation_id
        return rpp.handle_request(request, self.ctx)

    # framing -------------------------------------------------------------
    def test_response_always_has_all_keys(self):
        for response in (self.call("manifest"), self.call("nope"),
                         rpp.handle_raw("{not json", self.ctx), rpp.handle_request(None, self.ctx)):
            self.assertEqual(set(response), {"rpp", "ok", "operation_id", "result", "error"})
            self.assertEqual(response["rpp"], "1.0")

    def test_unknown_op(self):
        response = self.call("does.not.exist")
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "UNKNOWN_OP")

    def test_protocol_unsupported(self):
        response = self.call("manifest", version="2.0")
        self.assertEqual(response["error"]["code"], "PROTOCOL_UNSUPPORTED")

    def test_missing_version_and_bad_json(self):
        self.assertEqual(rpp.handle_request({"op": "manifest"}, self.ctx)["error"]["code"], "BAD_REQUEST")
        self.assertEqual(rpp.handle_raw("{oops", self.ctx)["error"]["code"], "BAD_REQUEST")

    def test_operation_id_shape_and_echo(self):
        ok = self.call("manifest", operation_id=OPID)
        self.assertEqual(ok["operation_id"], OPID)
        self.assertIsNone(self.call("manifest")["operation_id"])
        self.assertEqual(self.call("manifest", operation_id="short")["error"]["code"], "BAD_REQUEST")

    def test_never_raises_on_garbage(self):
        for junk in (None, 3, [], "text", {"rpp": "1.0", "op": 5, "payload": "x"}):
            self.assertIsInstance(rpp.handle_request(junk, self.ctx), dict)

    # manifest/health -----------------------------------------------------
    def test_manifest(self):
        result = self.call("manifest")["result"]
        self.assertEqual(result["product_id"], "respected-orchestrator")
        self.assertEqual(result["product_version"], __version__)
        self.assertEqual(result["protocol"], {"min": "1.0", "max": "1.1"})
        self.assertTrue(result["settings_supported"])
        self.assertEqual(set(result["capabilities"]), {
            "task.create", "task.inspect", "task.cancel", "task.retry",
            "campaign.start", "campaign.status", "maf.workflow", "apply.verified-patch"})

    def test_health(self):
        result = self.call("health")["result"]
        self.assertIn(result["status"], {"healthy", "degraded", "unhealthy"})
        self.assertEqual(result["version"], __version__)
        names = [check["name"] for check in result["checks"]]
        self.assertEqual(set(names), {"data_root_writable", "git_available", "worker_cli", "engine_key"})
        for check in result["checks"]:
            self.assertIsInstance(check["ok"], bool)

    # settings schema/validate -------------------------------------------
    def test_schema(self):
        fields = {field["key"]: field for field in self.call("settings.schema")["result"]["fields"]}
        self.assertEqual(set(fields), {"default_worker", "default_worker_profile",
                                       "default_reviewer_profile", "default_timeout_seconds", "default_reviewer_tool",
                                       "default_roles", "auto_assign", "auto_pool", "require_independent_review",
                                       "blocked_profiles", "mcp_acceptance_allow", "memory_enabled", "memory_command",
                                       "memory_grant_id", "memory_token", "memory_write"})
        for key in ("memory_enabled", "memory_command", "memory_grant_id", "memory_token"):
            self.assertTrue(fields[key]["hidden"])
        self.assertTrue(fields["memory_token"]["secret"])
        self.assertEqual(fields["default_worker"]["type"], "enum")
        self.assertNotIn("custom", fields["default_worker"]["enum"])
        self.assertEqual(fields["default_timeout_seconds"]["min"], 60)
        self.assertEqual(fields["default_timeout_seconds"]["max"], 3600)
        for field in fields.values():
            self.assertIn("label", field)
            self.assertIn("default", field)
            self.assertIn("secret", field)

    def test_validate(self):
        good = self.call("settings.validate", {"settings": {"default_worker": "claude",
                                                            "default_timeout_seconds": 120}})
        self.assertTrue(good["result"]["valid"])
        self.assertEqual(good["result"]["errors"], [])

        bad = self.call("settings.validate", {"settings": {
            "default_worker": "custom", "unknown_key": 1, "default_timeout_seconds": "x"}})
        self.assertFalse(bad["result"]["valid"])
        keys = {error["key"] for error in bad["result"]["errors"]}
        self.assertEqual(keys, {"default_worker", "unknown_key", "default_timeout_seconds"})

        self.assertFalse(self.call("settings.validate", {"settings": {"default_timeout_seconds": 5}})
                         ["result"]["valid"])
        self.assertTrue(self.call("settings.validate", {"settings": {"default_worker_profile": "mimo-test"}})
                        ["result"]["errors"])

    # settings apply/readback --------------------------------------------
    def test_readback_defaults(self):
        result = self.call("settings.readback")["result"]
        self.assertEqual(result["source"], "defaults")
        self.assertEqual(result["settings"]["default_worker"], "codex")
        self.assertEqual(result["settings"]["default_reviewer_profile"], "")  # no model is hardcoded to a role
        self.assertEqual(result["settings"]["default_timeout_seconds"], 900)

    def test_apply_writes_readback(self):
        settings = {"default_worker": "claude", "default_timeout_seconds": 120}
        response = self.call("settings.apply", {"settings": settings}, operation_id=OPID)
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["status"], "applied")
        receipt = json.loads((self.ctx.data_root / "receipts" / f"{OPID}.json").read_text("utf-8"))
        self.assertEqual(set(receipt), {"operation_id", "op", "status", "applied_at", "settings_sha256"})
        self.assertEqual(receipt["settings_sha256"], response["result"]["settings_sha256"])
        self.assertNotIn("settings", receipt)
        readback = self.call("settings.readback")["result"]
        self.assertEqual(readback["source"], "file")
        self.assertEqual(readback["settings"]["default_worker"], "claude")
        self.assertEqual(readback["settings"]["default_worker_profile"], "")
        self.assertEqual(readback["settings"]["default_timeout_seconds"], 120)

    def test_apply_idempotent_replay(self):
        settings = {"default_worker": "claude"}
        first = self.call("settings.apply", {"settings": settings}, operation_id=OPID)
        stored = (self.ctx.data_root / "settings.json").read_text("utf-8")
        second = self.call("settings.apply", {"settings": settings}, operation_id=OPID)
        self.assertTrue(second["ok"])
        self.assertEqual(second["result"]["applied_at"], first["result"]["applied_at"])
        self.assertEqual((self.ctx.data_root / "settings.json").read_text("utf-8"), stored)

    def test_apply_conflict(self):
        self.call("settings.apply", {"settings": {"default_worker": "claude"}}, operation_id=OPID)
        stored = (self.ctx.data_root / "settings.json").read_text("utf-8")
        conflict = self.call("settings.apply", {"settings": {"default_worker": "gemini"}}, operation_id=OPID)
        self.assertFalse(conflict["ok"])
        self.assertEqual(conflict["error"]["code"], "OPERATION_ID_CONFLICT")
        self.assertEqual((self.ctx.data_root / "settings.json").read_text("utf-8"), stored)

    def test_apply_invalid_writes_nothing(self):
        response = self.call("settings.apply", {"settings": {"default_worker": "custom"}}, operation_id=OPID)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "INVALID_SETTINGS")
        self.assertFalse((self.ctx.data_root / "settings.json").exists())
        self.assertFalse((self.ctx.data_root / "receipts").exists())

    def test_apply_requires_operation_id(self):
        response = self.call("settings.apply", {"settings": {}})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "BAD_REQUEST")

    # secrets -------------------------------------------------------------
    def test_secret_redaction(self):
        fields = [{"key": "token", "secret": True}, {"key": "name", "secret": False}]
        redacted = rpp._redact({"token": "abc", "name": "n"}, fields)
        self.assertEqual(redacted["token"], "***set***")
        self.assertEqual(redacted["name"], "n")
        self.assertEqual(rpp._redact({"token": "", "name": "n"}, fields)["token"], "")


class RppV11Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")

    def call(self, op, payload=None, operation_id=None, version="1.1"):
        request = {"rpp": version, "op": op, "payload": payload if payload is not None else {}}
        if operation_id is not None:
            request["operation_id"] = operation_id
        return rpp.handle_request(request, self.ctx)

    def test_v11_request_echoes_negotiated_version(self):
        response = self.call("manifest")
        self.assertTrue(response["ok"])
        self.assertEqual(response["rpp"], "1.1")

    def test_v10_request_still_supported(self):
        response = self.call("manifest", version="1.0")
        self.assertTrue(response["ok"])
        self.assertEqual(response["rpp"], "1.0")

    def test_protocol_unsupported_boundaries(self):
        for version in ("2.0", "0.9", "1", "one"):
            response = self.call("manifest", version=version)
            self.assertEqual(response["error"]["code"], "PROTOCOL_UNSUPPORTED", version)

    def test_v11_ops_require_v11(self):
        for op in ("lifecycle.plan", "lifecycle.apply", "lifecycle.status",
                   "lifecycle.rollback", "operation.receipt"):
            response = self.call(op, version="1.0")
            self.assertEqual(response["error"]["code"], "UNSUPPORTED_OP", op)
            self.assertIn("1.1", response["error"]["hint"])

    def test_manifest_adds_v11_keys(self):
        result = self.call("manifest")["result"]
        self.assertIn(result["install_state"],
                      {"absent", "installed", "update-available", "repair-needed"})
        self.assertIsInstance(result["installed"], bool)
        self.assertEqual(set(result["roots"]), {"data", "app", "vault"})
        self.assertEqual(result["roots"]["data"], str(self.ctx.data_root))
        self.assertIsNone(result["roots"]["vault"])
        details = {item["id"]: item for item in result["capability_details"]}
        self.assertEqual(details["lifecycle"]["since"], "1.1")
        self.assertIn("lifecycle.apply", details["lifecycle"]["ops"])
        self.assertEqual(details["operation.receipt"]["since"], "1.1")
        for capability in result["capabilities"]:
            self.assertEqual(details[capability]["since"], "1.0")

    def test_receipt_not_found(self):
        response = self.call("operation.receipt", {"operation_id": OPID})
        self.assertEqual(response["error"]["code"], "RECEIPT_NOT_FOUND")

    def test_operation_receipt_reads_settings_receipt(self):
        self.call("settings.apply", {"settings": {"default_worker": "claude"}},
                  operation_id=OPID, version="1.0")
        response = self.call("operation.receipt", {"operation_id": OPID})
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["op"], "settings.apply")

    def test_operation_receipt_accepts_request_operation_id(self):
        self.call("settings.apply", {"settings": {}}, operation_id=OPID, version="1.0")
        response = self.call("operation.receipt", operation_id=OPID)
        self.assertTrue(response["ok"])


if __name__ == "__main__":
    unittest.main()
