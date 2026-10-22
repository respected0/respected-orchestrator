"""The install record: setup, repair and uninstall around a program folder the installer owns (temp dirs only)."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from respected_orchestrator import __version__
from respected_orchestrator.context import EngineContext
from respected_orchestrator.interfaces import installation
from respected_orchestrator.interfaces.installation import OperationError


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app = self.root / "app"
        self.binary = b"MZ\x90\x00\xff\xfe binary"
        (self.app / "app").mkdir(parents=True)
        (self.app / "respected-orchestrator.exe").write_bytes(self.binary)
        (self.app / "app" / "base_library.zip").write_bytes(b"PK\x03\x04")
        self.write_distribution()
        app_root = mock.patch.object(EngineContext, "app_root", new_callable=mock.PropertyMock, return_value=self.app)
        app_root.start()
        self.addCleanup(app_root.stop)
        self.ctx = EngineContext(self.root / "data")
        self.record = self.app / ".respected" / "install.json"

    def write_distribution(self, extra=None):
        files = {p.relative_to(self.app).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(self.app.rglob("*")) if p.is_file() and p.name != "distribution.json" and ".respected" not in p.parts}
        files.update(extra or {})
        (self.app / "distribution.json").write_text(json.dumps({"version": __version__, "files": files}), encoding="utf-8")

    def test_setup_records_the_intact_program_and_tampering_is_detected(self):
        result = installation.setup(self.ctx)
        self.assertEqual((result["status"], result["product_version"]), ("installed", __version__))
        self.assertTrue(self.ctx.data_root.is_dir())
        self.assertEqual(installation.verify(self.app)["install_state"], "installed")
        self.assertEqual((self.app / "respected-orchestrator.exe").read_bytes(), self.binary, "recording never rewrites program files")
        (self.app / "respected-orchestrator.exe").write_bytes(self.binary + b"!")
        self.assertEqual(installation.verify(self.app)["install_state"], "repair-needed")

    def test_a_program_that_does_not_match_its_build_gets_no_record(self):
        (self.app / "app" / "base_library.zip").write_bytes(b"changed after the build")
        with self.assertRaises(OperationError) as caught:
            installation.setup(self.ctx)
        self.assertEqual(caught.exception.code, "VERIFY_FAILED")
        self.assertFalse(self.record.exists())

    def test_distribution_paths_cannot_escape_the_program_folder_and_must_exist(self):
        (self.root / "outside.txt").write_text("x", encoding="utf-8")
        self.write_distribution({"../outside.txt": "0" * 64})
        with self.assertRaises(OperationError):
            installation.setup(self.ctx)
        (self.app / "distribution.json").unlink()
        with self.assertRaises(OperationError) as caught:
            installation.setup(self.ctx)
        self.assertEqual(caught.exception.code, "VERIFY_FAILED")
        self.assertEqual(installation.verify(self.app)["install_state"], "absent")

    def test_repair_needs_a_record_and_follows_the_program_the_installer_laid_down(self):
        with self.assertRaises(OperationError) as caught:
            installation.repair(self.ctx)
        self.assertEqual(caught.exception.code, "NOT_INSTALLED")
        installation.setup(self.ctx)
        installed_at = json.loads(self.record.read_text("utf-8"))["installed_at"]
        (self.app / "respected-orchestrator.exe").write_bytes(b"MZ next version")
        self.write_distribution()
        self.assertEqual(installation.repair(self.ctx)["status"], "repaired")
        self.assertEqual(installation.verify(self.app)["install_state"], "installed")
        self.assertEqual(json.loads(self.record.read_text("utf-8"))["installed_at"], installed_at)

    def test_uninstall_drops_the_record_keeps_the_program_and_keeps_data_unless_purged(self):
        installation.setup(self.ctx)
        (self.ctx.data_root / "settings.json").write_text("{}", encoding="utf-8")
        result = installation.uninstall(self.ctx)
        self.assertEqual((result["status"], result["purged"]), ("removed", False))
        self.assertFalse(self.record.exists())
        self.assertEqual((self.app / "respected-orchestrator.exe").read_bytes(), self.binary)
        self.assertTrue((self.ctx.data_root / "settings.json").is_file())
        installation.setup(self.ctx)
        self.assertTrue(installation.uninstall(self.ctx, purge=True)["purged"])
        self.assertFalse(self.ctx.data_root.exists())

    def test_uninstall_takes_back_its_own_mcp_registrations_and_leaves_the_rest(self):
        from respected_orchestrator.interfaces import integrations
        home = self.root / "home"
        home.mkdir()
        config = home / ".claude.json"
        config.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"USERPROFILE": str(home), "HOME": str(home), "APPDATA": str(home / "AppData")}):
            installation.setup(self.ctx)
            launcher = {"command": "cmd", "args": ["/c", "launch.cmd"]}
            planned = integrations.plan(self.ctx, {"desired": {"claude-code": True}, "launcher": launcher})
            integrations.apply(self.ctx, "op-enable-0001", {"desired": {"claude-code": True}, "launcher": launcher, "plan_digest": planned["plan_digest"]})
            self.assertIn("respected-orchestrator", json.loads(config.read_text("utf-8"))["mcpServers"])
            self.assertEqual(installation.uninstall(self.ctx)["conflicts"], [])
        self.assertEqual(json.loads(config.read_text("utf-8")), {"mcpServers": {"other": {"command": "x"}}})


class MemoryLinkTests(unittest.TestCase):
    """`memory connect` without the Hub: a fake Brain answers memory.grant/revoke over its rpp command."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(root / "data")
        self.exe = root / "respected-brain.exe"
        self.exe.write_bytes(b"fake")
        self.calls = []

    def fake(self, ok=True):
        def run(command, input=None, **kwargs):
            request = json.loads(input)
            self.calls.append(request)
            self.assertEqual((command, request["rpp"]), ([str(self.exe), "rpp"], "1"))
            result = {"grant_id": "grant-0001", "token": "rbm_" + "a" * 32} if request["op"] == "memory.grant" else {}
            reply = {"rpp": "1", "ok": ok, "result": result if ok else None,
                     "error": None if ok else {"code": "DENIED", "message": "no", "hint": ""}}
            return mock.Mock(stdout=json.dumps(reply).encode("utf-8"))
        from types import SimpleNamespace
        # only the Brain call is faked; the token file's own permission tools still run for real
        return mock.patch("respected_orchestrator.interfaces.memory_link.winproc", SimpleNamespace(run=run))

    def test_connect_stores_the_grant_and_disconnect_revokes_it(self):
        from respected_orchestrator.interfaces import memory, memory_link
        with self.fake():
            status = memory_link.connect(self.ctx, write=True, exe=self.exe)
        self.assertEqual((status["connected"], status["write"], status["grant_id"]), (True, True, "grant-0001"))
        self.assertEqual(self.calls[-1]["payload"], {"label": "Orchestrator", "write": True})
        self.assertTrue(memory.token_set(self.ctx.data_root))
        self.assertNotIn("rbm_", (self.ctx.data_root / "settings.json").read_text("utf-8"))
        with self.fake():
            self.assertTrue(memory_link.disconnect(self.ctx, exe=self.exe)["revoked"])
        self.assertEqual(self.calls[-1], {"rpp": "1", "op": "memory.revoke", "payload": {"grant_id": "grant-0001"}})
        self.assertFalse(memory.token_set(self.ctx.data_root))
        self.assertFalse(memory_link.status(self.ctx)["connected"])

    def test_a_refused_grant_or_a_missing_brain_changes_nothing(self):
        from respected_orchestrator.interfaces import memory_link
        with self.fake(ok=False), self.assertRaises(OperationError):
            memory_link.connect(self.ctx, exe=self.exe)
        with self.assertRaises(OperationError) as caught:
            memory_link.connect(self.ctx, exe=self.exe.with_name("missing.exe"))
        self.assertEqual(caught.exception.code, "NOT_INSTALLED")
        self.assertFalse((self.ctx.data_root / "settings.json").exists())


if __name__ == "__main__":
    unittest.main()
