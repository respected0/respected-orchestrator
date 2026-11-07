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

    def test_exactly_six_shell_commands_each_granted_to_the_main_window_only(self):
        lib = (SRC / "src" / "lib.rs").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"generate_handler!\[([^\]]*)\]", lib), ["engine_status, confirm_close, request_apply, capability_inventory, session_call, preview_open"])
        self.assertEqual(lib.count("#[tauri::command]"), 6)
        # B3-05.02: the renderer may only name a run to ask about. No token, decision or binding can be passed in.
        signature = re.search(r"async fn request_apply\(([^)]*)\)", lib).group(1)
        self.assertTrue(signature.startswith("run_id: String,"))
        self.assertNotRegex(signature, r"token|decision|binding|challenge")
        # session relay: only a command name (checked against a fixed list in Rust) and a payload the engine validates; no approve verbs
        relay = re.search(r"fn session_call\(([^)]*)\)", lib).group(1)
        self.assertTrue(relay.startswith("cmd: String, payload: serde_json::Value,"))
        self.assertNotRegex(relay, r"token|decision|binding|challenge")
        # B3-08.03: the inventory command is read-only data: at most a project folder in, no approvals, no write verbs.
        inventory = re.search(r"fn capability_inventory\(([^)]*)\)", lib).group(1)
        self.assertTrue(inventory.startswith("project_root: Option<String>,"))
        self.assertNotRegex(inventory, r"approval|token|decision|trust")
        # B3-06.03: the preview command takes an address and nothing else from the renderer; every command is listed in build.rs and
        # granted by name to the window "main" (not to "*"), so a window without a capability has no commands even for a local origin.
        preview = re.search(r"async fn preview_open<R: tauri::Runtime>\(([^)]*)\)", lib).group(1)
        self.assertTrue(preview.startswith("url: String,"))
        self.assertNotRegex(preview, r"port|enable|setting")
        names = ["engine_status", "confirm_close", "request_apply", "capability_inventory", "session_call", "preview_open"]
        build = (SRC / "build.rs").read_text(encoding="utf-8")
        for name in names:
            self.assertIn(f'"{name}"', build)
        capability = json.loads(next((SRC / "capabilities").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(capability["windows"], ["main"])
        self.assertEqual({p for p in capability["permissions"] if p.startswith("allow-")}, {"allow-" + n.replace("_", "-") for n in names})
        toml = (SRC / "Cargo.toml").read_text(encoding="utf-8")
        self.assertNotRegex(toml, r"tauri-plugin-(shell|fs|http|opener|process)")

    def test_navigation_guard_is_registered(self):
        self.assertIn("on_navigation", (SRC / "src" / "lib.rs").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
