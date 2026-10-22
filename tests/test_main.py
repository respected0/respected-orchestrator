"""The private JSON entry point (__main__.main): argument errors, dispatch and the error envelope."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator import __main__ as cli
from respected_orchestrator.workflows import planner, roles


def call(*argv, stdin=""):
    out = io.StringIO()
    with mock.patch.object(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin.encode()))), contextlib.redirect_stdout(out):
        code = cli.main(list(argv))
    return code, out.getvalue()


class MainTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = ["--data-root", str(Path(temp.name))]

    def test_status_list_and_roles_dry_run(self):
        code, text = call(*self.root, "status")
        self.assertEqual((code, json.loads(text)["product"]), (0, "respected-orchestrator"))
        self.assertEqual(call(*self.root, "list")[0], 0)
        code, text = call(*self.root, "roles", stdin='{"roles": {}, "needed": ["implementer"]}')
        self.assertIn("assignments", json.loads(text))

    def test_run_commands_need_exactly_one_identity(self):
        code, text = call(*self.root, "inspect")
        self.assertEqual(code, 1)
        self.assertIn("run identity", json.loads(text)["error"]["message"])

    def test_errors_become_a_json_envelope(self):
        code, text = call(*self.root, "create", stdin="not json")
        self.assertEqual(code, 1)
        self.assertIn("error", json.loads(text))
        error = roles.RoleError("ROLE_UNAVAILABLE", "nope", "fix it")
        with mock.patch.object(planner, "plan", side_effect=error):
            code, text = call(*self.root, "plan", stdin="{}")
        self.assertEqual((code, json.loads(text)), (1, {"error": {"code": "ROLE_UNAVAILABLE", "message": "nope", "hint": "fix it"}}))

    def test_dispatch_to_subsystems(self):
        with mock.patch("respected_orchestrator.interfaces.rpp.run", return_value=5) as rpp:
            self.assertEqual(call(*self.root, "rpp")[0], 5)
        rpp.assert_called_once()
        with mock.patch("respected_orchestrator.interfaces.mcp_server.serve", return_value=0) as serve:
            call(*self.root, "mcp", "--allow-auto-apply")
        self.assertEqual(serve.call_args.kwargs, {"allow_auto_apply": True, "allow_privileged": False})
        with mock.patch("respected_orchestrator.engine.sandbox_exec", create=True) as launcher:
            launcher.main.return_value = 3
            self.assertEqual(call("_sandbox-exec", "--sid", "S")[0], 3)
        with mock.patch("respected_orchestrator.workflows.campaign.list_campaigns", return_value={"campaigns": []}):
            self.assertEqual(json.loads(call(*self.root, "campaign-list")[1]), {"campaigns": []})

    def test_version_is_the_packaging_form_of_pyproject_version(self):
        import re
        from packaging.version import Version
        from respected_orchestrator import __version__
        text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertEqual(__version__, str(Version(re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1))))

    def test_version_and_shared_product_commands(self):
        from respected_orchestrator import __version__
        self.assertEqual(call("--version"), (0, f"respected-orchestrator {__version__}\n"))
        for name in ("setup", "repair", "uninstall", "config", "health", "memory"):
            self.assertEqual(call(*self.root, name, "--help")[0], 0)
        app = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(app, ignore_errors=True))
        (app / "respected-orchestrator.exe").write_bytes(b"exe")
        digest = __import__("hashlib").sha256(b"exe").hexdigest()
        (app / "distribution.json").write_text(json.dumps({"files": {"respected-orchestrator.exe": digest}}), encoding="utf-8")
        record = app / ".respected" / "install.json"
        with mock.patch.object(cli.EngineContext, "app_root", new_callable=mock.PropertyMock, return_value=app):
            for name, status in (("setup", "installed"), ("repair", "repaired")):
                code, text = call(*self.root, name)
                self.assertEqual((code, json.loads(text)["status"]), (0, status), text)
                self.assertTrue(record.is_file())
            for usage in (("setup", "--purge"), ("update",), ("config", "set", "nope=1"), ("config", "set", "default_timeout_seconds=x"), ("memory", "plug")):
                code, text = call(*self.root, *usage)
                self.assertEqual(code, 2, usage)
                if usage != ("update",):  # argparse refuses an unknown command itself
                    self.assertEqual(set(json.loads(text)["error"]), {"code", "message", "hint"})
            code, text = call(*self.root, "uninstall")
            self.assertEqual((code, json.loads(text)["status"]), (0, "removed"), text)
            self.assertFalse(record.exists())
            self.assertTrue((app / "respected-orchestrator.exe").is_file())  # the folder belongs to whoever installed it

    def test_integrations_register_this_program_in_an_ai_client_without_the_hub(self):
        home = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        (home / ".claude.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"USERPROFILE": str(home), "HOME": str(home), "APPDATA": str(home / "AppData")}):
            code, text = call(*self.root, "integrations")
            self.assertEqual(code, 0, text)
            self.assertIn("claude-code", {row["client"] for row in json.loads(text)["clients"]})
            code, text = call(*self.root, "integrations", "set", "claude-code=on")
            self.assertEqual((code, json.loads(text)["status"]), (0, "applied"), text)
            servers = json.loads((home / ".claude.json").read_text("utf-8"))["mcpServers"]
            self.assertEqual(servers["respected-orchestrator"]["args"][-1], "mcp")
            self.assertEqual(servers["other"], {"command": "x"})
            self.assertEqual(call(*self.root, "integrations", "set", "claude-code=maybe")[0], 2)
            self.assertEqual(call(*self.root, "integrations", "set", "claude-code=off")[0], 0)
        self.assertNotIn("respected-orchestrator", json.loads((home / ".claude.json").read_text("utf-8"))["mcpServers"])

    def test_config_reads_and_writes_through_the_settings_schema(self):
        code, text = call(*self.root, "config", "set", "default_worker=claude", "default_timeout_seconds=120")
        self.assertEqual((code, json.loads(text)), (0, {"default_worker": "claude", "default_timeout_seconds": 120}), text)
        self.assertEqual(json.loads(call(*self.root, "config", "get", "default_worker")[1]), {"default_worker": "claude"})
        self.assertEqual(json.loads(call(*self.root, "config")[1])["default_timeout_seconds"], 120)
        self.assertEqual(call(*self.root, "config", "set", "default_timeout_seconds=5")[0], 2)


if __name__ == "__main__":
    unittest.main()
