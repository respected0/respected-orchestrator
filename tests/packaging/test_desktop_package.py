import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("build_dist_under_test", ROOT / "packaging" / "build_dist.py")
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)


class DesktopPackageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.app = self.root / "RespectedOrchestrator"
        (self.app / "app" / "lib").mkdir(parents=True)
        (self.app / bd.LAUNCHER).write_bytes(b"MZ engine launcher")
        (self.app / "app" / "python313.dll").write_bytes(b"runtime")
        (self.app / "app" / "lib" / "mod.pyd").write_bytes(b"module")
        self.shell = self.root / "built-desktop.exe"
        self.shell.write_bytes(b"MZ desktop shell")
        bd.write_distribution(self.app, desktop=False)

    def manifest(self):
        return json.loads((self.app / "distribution.json").read_text(encoding="utf-8"))

    def test_engine_only_package_is_consistent_and_names_no_shell(self):
        self.assertEqual(bd.audit(self.app), [])
        self.assertNotIn("desktop", self.manifest())

    def test_attaching_the_shell_puts_it_next_to_the_launcher_in_one_hash_chain(self):
        document = bd.attach_desktop(self.app, self.shell)
        self.assertEqual(document["desktop"], bd.DESKTOP)
        self.assertEqual((self.app / bd.DESKTOP).read_bytes(), b"MZ desktop shell")
        files = self.manifest()["files"]
        self.assertEqual(files[bd.DESKTOP], bd.sha256(self.app / bd.DESKTOP))
        self.assertEqual(files[bd.LAUNCHER], bd.sha256(self.app / bd.LAUNCHER))
        self.assertEqual({k for k in files if "/" not in k}, {bd.LAUNCHER, bd.DESKTOP})  # both at the root, runtime stays under app/
        self.assertEqual((document["schema_version"], document["product"], document["launcher"]), (1, "orchestrator", bd.LAUNCHER))
        self.assertEqual(bd.audit(self.app), [])

    def test_reattaching_a_new_shell_updates_the_chain(self):
        bd.attach_desktop(self.app, self.shell)
        before = self.manifest()["files"][bd.DESKTOP]
        self.shell.write_bytes(b"MZ desktop shell v2")
        bd.attach_desktop(self.app, self.shell)
        self.assertNotEqual(self.manifest()["files"][bd.DESKTOP], before)
        self.assertEqual(bd.audit(self.app), [])

    def test_attach_refuses_a_missing_shell_or_a_folder_that_is_not_an_engine(self):
        with self.assertRaises(FileNotFoundError):
            bd.attach_desktop(self.app, self.root / "nope.exe")
        with self.assertRaises(FileNotFoundError):
            bd.attach_desktop(self.root, self.shell)
        self.assertEqual(bd.audit(self.app), [])  # the refused attempts changed nothing
        self.assertFalse((self.app / bd.DESKTOP).exists())

    def test_every_kind_of_tampering_is_named_by_the_audit(self):
        bd.attach_desktop(self.app, self.shell)
        cases = {
            "launcher swapped": (lambda: (self.app / bd.LAUNCHER).write_bytes(b"MZ implant"), "hash mismatch: " + bd.LAUNCHER),
            "shell swapped": (lambda: (self.app / bd.DESKTOP).write_bytes(b"MZ implant"), "hash mismatch: " + bd.DESKTOP),
            "runtime file changed": (lambda: (self.app / "app" / "python313.dll").write_bytes(b"other"), "hash mismatch: app/python313.dll"),
            "runtime file removed": (lambda: (self.app / "app" / "lib" / "mod.pyd").unlink(), "missing: app/lib/mod.pyd"),
            "file added": (lambda: (self.app / "app" / "extra.dll").write_bytes(b"x"), "not in the manifest: app/extra.dll"),
            "shell removed": (lambda: (self.app / bd.DESKTOP).unlink(), "missing: " + bd.DESKTOP),
        }
        for name, (tamper, expected) in cases.items():
            with self.subTest(name):
                bd.attach_desktop(self.app, self.shell)  # fresh, consistent state
                tamper()
                self.assertIn(expected, bd.audit(self.app))
        bd.attach_desktop(self.app, self.shell)
        self.assertEqual(bd.audit(self.app), [])

    def test_manifest_problems_are_reported_not_crashed_on(self):
        bd.attach_desktop(self.app, self.shell)
        manifest = self.manifest()
        path = self.app / "distribution.json"
        for name, edit, expected in (
            ("shell named but not hashed", lambda m: m["files"].pop(bd.DESKTOP), "named but not hashed"),
            ("shell hashed but not named", lambda m: m.pop("desktop"), "hashed but not named"),
            ("launcher not listed", lambda m: m["files"].pop(bd.LAUNCHER), "launcher is not in the manifest"),
            ("wrong schema", lambda m: m.update(schema_version=2), "schema 1"),
            ("wrong product", lambda m: m.update(product="brain"), "schema 1"),
        ):
            doc = json.loads(json.dumps(manifest))
            edit(doc)
            path.write_text(json.dumps(doc), encoding="utf-8")
            self.assertTrue(any(expected in p for p in bd.audit(self.app)), name)
        for bad in ("{not json", "[]", "{}", ""):
            path.write_text(bad, encoding="utf-8")
            self.assertEqual(bd.audit(self.app), ["distribution.json is missing or unreadable"], repr(bad))
        path.unlink()
        self.assertEqual(bd.audit(self.app), ["distribution.json is missing or unreadable"])

    def test_the_products_own_install_verification_accepts_the_attached_shell_and_rejects_tampering(self):
        from respected_orchestrator.interfaces import installation
        bd.attach_desktop(self.app, self.shell)
        files = installation._distribution(self.app)
        self.assertIn(bd.DESKTOP, files)  # the existing verifier already covers every listed file
        (self.app / bd.DESKTOP).write_bytes(b"MZ implant")
        with self.assertRaises(installation.OperationError) as caught:
            installation._distribution(self.app)
        self.assertEqual(caught.exception.code, "VERIFY_FAILED")

    def test_installer_script_adds_the_shell_shortcut_only_when_the_build_ships_it(self):
        text = (ROOT / "packaging" / "windows" / "orchestrator_setup.iss").read_text(encoding="utf-8-sig")
        self.assertIn('#ifexist StageDir + "\\respected-orchestrator-desktop.exe"', text)
        icons = text[text.index("#ifexist StageDir"):text.index("#endif", text.index("#ifexist StageDir"))]
        self.assertIn('Filename: "{app}\\respected-orchestrator-desktop.exe"', icons)
        self.assertNotIn("respected-orchestrator.exe", icons.replace("respected-orchestrator-desktop.exe", ""))  # no shortcut to the engine launcher
        for forbidden in ("[Run]", "[Registry]", "startup", "RunOnce", "[Tasks]"):
            self.assertNotIn(forbidden, icons)  # no autostart, no service, no registry run key

    def test_the_manifest_is_deterministic_for_the_same_folder(self):
        bd.attach_desktop(self.app, self.shell)
        first = (self.app / "distribution.json").read_text(encoding="utf-8")
        bd.write_distribution(self.app, desktop=True)
        self.assertEqual((self.app / "distribution.json").read_text(encoding="utf-8"), first)


if __name__ == "__main__":
    unittest.main()
