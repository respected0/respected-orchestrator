"""docs/PRODUCT_CONTRACT.md measured against the Orchestrator itself (no other repo takes part).

Default target is this source checkout. To test a built program set RESPECTED_CONFORMANCE_ORCHESTRATOR_EXE.
Every check points the product at temporary folders (RESPECTED_APP_DIR / RESPECTED_DATA_DIR); nothing touches a real install.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ("setup", "repair", "uninstall", "config", "health", "rpp", "mcp")
REQUIRED_OPS = ("manifest", "health", "settings.schema", "settings.validate", "settings.apply", "settings.readback")
RETIRED_OPS = ("lifecycle.plan", "lifecycle.apply", "lifecycle.status", "lifecycle.rollback", "operation.receipt")
RESPONSE_KEYS = {"rpp", "ok", "operation_id", "result", "error"}
SETTING = ("default_timeout_seconds", "1200", "5")  # a setting, a valid value, an invalid one


def launcher():
    exe = os.environ.get("RESPECTED_CONFORMANCE_ORCHESTRATOR_EXE")
    if exe:
        return [exe], dict(os.environ)
    return [sys.executable, "-m", "respected_orchestrator"], dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONDONTWRITEBYTECODE="1")


class ProductContract(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_product(self, args, stdin=None):
        command, env = launcher()
        env.update(RESPECTED_APP_DIR=str(self.root / "app"), RESPECTED_DATA_DIR=str(self.root / "data"),
                   USERPROFILE=str(self.root / "home"), HOME=str(self.root / "home"))
        return subprocess.run(command + args, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env, timeout=120, cwd=self.root)

    def rpp(self, op, payload=None, version="1"):
        request = json.dumps({"rpp": version, "op": op, "payload": payload or {}, "operation_id": "operation-0001"})
        done = self.run_product(["rpp"], request)
        self.assertTrue(done.stdout.strip(), f"{op}: empty stdout, stderr={done.stderr[:300]}")
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_version_names_the_product_and_installs_nothing(self):
        done = self.run_product(["--version"])
        self.assertEqual(done.returncode, 0, done.stderr[:300])
        self.assertRegex(done.stdout.strip(), r"^respected-orchestrator \S+$")
        self.assertFalse((self.root / "data").exists())

    def test_commands_exist_and_retired_ones_do_not(self):
        for name in COMMANDS:
            with self.subTest(command=name):
                self.assertEqual(self.run_product([name, "--help"]).returncode, 0)
        for retired in (["update"], ["uninstall", "--keep-data"], ["uninstall", "--purge-data"]):
            with self.subTest(retired=retired):
                self.assertEqual(self.run_product(retired).returncode, 2)

    def test_config_and_rpp_settings_are_the_same_settings(self):
        key, good, bad = SETTING
        done = self.run_product(["config", "set", f"{key}={good}"])
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        written = json.loads(done.stdout)[key]
        self.assertEqual(json.loads(self.run_product(["config", "get", key]).stdout), {key: written})
        self.assertEqual(json.loads(self.run_product(["config"]).stdout)[key], written)
        self.assertEqual(self.rpp("settings.readback")["result"]["settings"][key], written)
        refused = self.run_product(["config", "set", f"{key}={bad}"])
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(set(json.loads(refused.stdout)["error"]), {"code", "message", "hint"})
        self.assertEqual(json.loads(self.run_product(["config", "get", key]).stdout), {key: written}, "a refused change writes nothing")

    def test_usage_errors_share_one_shape_and_exit_code(self):
        done = self.run_product(["config", "set", "definitely_not_a_setting=1"])
        self.assertEqual(done.returncode, 2)
        self.assertEqual(set(json.loads(done.stdout)), {"error"})
        self.assertEqual(set(json.loads(done.stdout)["error"]), {"code", "message", "hint"})

    def test_schema_fields_carry_turkish_label_and_help(self):
        fields = self.rpp("settings.schema")["result"]["fields"]
        self.assertTrue(fields)
        for field in fields:
            self.assertTrue({"key", "type", "label", "help", "default", "secret"} <= set(field), field)
            self.assertIn(field["type"], ("string", "integer", "boolean", "enum"))

    def test_rpp_speaks_one_version_with_one_envelope(self):
        for version in ("1.0", "1.1", "2"):
            response = self.rpp("manifest", version=version)
            self.assertEqual((set(response), response["error"]["code"]), (RESPONSE_KEYS, "UNSUPPORTED_VERSION"))
        unknown = self.rpp("does.not.exist")
        self.assertEqual((set(unknown), unknown["rpp"], unknown["error"]["code"]), (RESPONSE_KEYS, "1", "UNKNOWN_OP"))
        for op in REQUIRED_OPS:
            self.assertNotEqual((self.rpp(op).get("error") or {}).get("code"), "UNKNOWN_OP", f"lacks {op}")
        for op in RETIRED_OPS:
            self.assertEqual(self.rpp(op)["error"]["code"], "UNKNOWN_OP", f"still has {op}: installing is the installer's")

    def test_manifest_reports_product_install_state_and_roots(self):
        result = self.rpp("manifest")["result"]
        self.assertEqual((result["product_id"], result["rpp"]), ("respected-orchestrator", "1"))
        self.assertTrue(result["product_version"])
        self.assertEqual((result["installed"], result["install_state"]), (False, "absent"))
        self.assertEqual(set(result["roots"]), {"app", "data", "vault"})
        self.assertEqual(result["capabilities"], sorted(result["capabilities"]))
        self.assertTrue(set(REQUIRED_OPS) <= set(result["capabilities"]))

    def test_installer_has_the_contract_switches_and_pages_and_no_other_product_path(self):
        text = (ROOT / "packaging/windows/orchestrator_setup.iss").read_text(encoding="utf-8")
        for token in ("/SET=", "'PURGE'", "Onar / Güncelle", "Ayarları değiştir", "Kaldır", "{code:UninstallArgs}", "'uninstall --purge'",
                      "WizardStyle=modern", "PrivilegesRequired=lowest", "DisableDirPage=yes"):
            self.assertIn(token, text, f"installer lacks {token}")
        self.assertNotRegex(text, r"--package|--allow-unattested|--keep-data|update --", "installer still uses a retired command")
        self.assertNotRegex(text, r"(?i)hub", "the installer must not know any other product's manager")
        self.assertIn("Brain hafızası", text)  # the optional memory link stays

    def test_contract_is_this_products_own_and_names_no_manager(self):
        text = (ROOT / "docs/PRODUCT_CONTRACT.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"^# Respected Orchestrator ürün sözleşmesi")
        self.assertNotRegex(text, r"(?i)\bhub\b")
        self.assertNotRegex(text, r"common/conformance|/HUB=|/VAULT=")


if __name__ == "__main__":
    unittest.main()
