import json
import shutil
import tempfile
import unittest
from pathlib import Path

from respected_orchestrator.interfaces.migrate import CURRENT, SHIPPED, STEPS, MigrationError, migrate_data

# one folder per published release: the data files that release wrote, copied from a real install and never edited
RELEASES = Path(__file__).resolve().parents[1] / "fixtures" / "releases"


class MigrateTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)

    def test_unversioned_beta_files_count_as_version_one_and_stay_untouched(self):
        (self.data / "settings.json").write_text('{"default_worker": "codex"}', encoding="utf-8")
        self.assertEqual(migrate_data(self.data), [])
        self.assertEqual(json.loads((self.data / "settings.json").read_text()), {"default_worker": "codex"})

    def test_old_format_moves_and_the_original_is_kept(self):
        (self.data / "settings.json").write_text('{"default_worker": "codex"}', encoding="utf-8")
        steps = {("settings.json", 1): lambda d: {"worker": d["default_worker"]}}
        self.assertEqual(migrate_data(self.data, current={"settings.json": 2}, steps=steps), ["settings.json"])
        self.assertEqual(json.loads((self.data / "settings.json").read_text()), {"worker": "codex", "schema_version": 2})
        self.assertEqual(json.loads((self.data / "settings.json.v1.bak").read_text()), {"default_worker": "codex"})

    def test_newer_or_unmigratable_data_is_refused_untouched(self):
        for text, current in (('{"schema_version": 9}', 1), ('{}', 2), ('[]', 1), ('{bad', 1)):
            with self.subTest(text=text):
                (self.data / "settings.json").write_text(text, encoding="utf-8")
                with self.assertRaises(MigrationError):
                    migrate_data(self.data, current={"settings.json": current}, steps={})
                self.assertEqual((self.data / "settings.json").read_text(), text)
                self.assertFalse(list(self.data.glob("*.bak")))

    def test_registry_has_a_step_for_every_shipped_older_version(self):
        for name, target in CURRENT.items():
            for version in range(SHIPPED[name], target):
                self.assertIn((name, version), STEPS)

    def test_every_published_release_moves_to_the_current_format_and_then_stays_put(self):
        releases = sorted(path for path in RELEASES.iterdir() if path.is_dir())
        self.assertTrue(releases, "tests/fixtures/releases is empty")
        for release in releases:
            with self.subTest(release=release.name):
                data = self.data / release.name
                shutil.copytree(release, data)
                names = [path.name for path in data.glob("*.json")]
                migrate_data(data)
                for name in names:  # files written before versions existed count as version 1
                    self.assertEqual(json.loads((data / name).read_text("utf-8")).get("schema_version", 1), CURRENT[name], name)
                settled = {path.name: path.read_bytes() for path in data.glob("*.json")}
                self.assertEqual(migrate_data(data), [], "a second run must change nothing")
                self.assertEqual({path.name: path.read_bytes() for path in data.glob("*.json")}, settled)

    def test_the_first_release_data_is_kept_as_a_fixture(self):
        for name in SHIPPED:
            self.assertTrue(list(RELEASES.glob(f"*/{name}")), f"{name}: add the file of the first release to tests/fixtures/releases")


if __name__ == "__main__":
    unittest.main()
