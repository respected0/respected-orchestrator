"""B3-01.01: the desktop shell ships with a closed CSP, no remote origins and no ambient capabilities."""
import json
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "desktop" / "src-tauri"
CONF = json.loads((SRC / "tauri.conf.json").read_text(encoding="utf-8"))
CAP = json.loads((SRC / "capabilities" / "default.json").read_text(encoding="utf-8"))
CSP = {k: v for k, *v in (d.split() for d in CONF["app"]["security"]["csp"].split(";") if d.strip())}


class ShellPolicyTests(unittest.TestCase):
    def test_csp_is_closed(self):
        self.assertEqual(CSP["default-src"], ["'self'"])
        self.assertEqual(CSP["script-src"], ["'self'"])
        banned = {"'unsafe-inline'", "'unsafe-eval'", "*", "http:", "https:"}
        for directive, values in CSP.items():
            for value in values:
                self.assertNotIn(value, banned, f"{directive} {value}")
                self.assertFalse(re.match(r"https?://(?!ipc\.localhost)", value), f"remote origin in {directive}")
            if directive != "img-src":
                self.assertNotIn("data:", values, directive)
        self.assertEqual(CSP["object-src"], ["'none'"])
        self.assertEqual(CSP["frame-ancestors"], ["'none'"])

    def test_no_global_tauri_and_single_window(self):
        self.assertFalse(CONF["app"]["withGlobalTauri"])
        self.assertEqual([w["label"] for w in CONF["app"]["windows"]], ["main"])

    def test_no_capability_grants_shell_fs_http_or_opener(self):
        self.assertEqual(CAP["windows"], ["main"])
        for permission in CAP["permissions"]:
            self.assertNotRegex(permission, r"shell|fs:|http|opener|process|dialog|global-shortcut")
        capabilities = list((SRC / "capabilities").glob("*.json"))
        self.assertEqual(len(capabilities), 1)

    def test_exactly_one_read_only_command_and_no_plugins(self):
        lib = (SRC / "src" / "lib.rs").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"generate_handler!\[([^\]]*)\]", lib), ["engine_status"])
        self.assertEqual(lib.count("#[tauri::command]"), 1)
        toml = (SRC / "Cargo.toml").read_text(encoding="utf-8")
        self.assertNotRegex(toml, r"tauri-plugin-(shell|fs|http|opener|process)")

    def test_navigation_guard_is_registered(self):
        self.assertIn("on_navigation", (SRC / "src" / "lib.rs").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
