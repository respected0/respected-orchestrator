"""B3-09.02: the data migration under faults. Real process death, real read-only files and folders, damaged inputs, concurrent runs.

After every failure the previous good file must be in place byte for byte, and nothing else in the data root may change."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.engine.journal import Journal
from respected_orchestrator.interfaces import migrate
from respected_orchestrator.interfaces.migrate import MigrationError, migrate_data

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
FIXTURES = ROOT / "tests" / "fixtures" / "releases"


def digest_tree(root):
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def v1_settings(gemini=True):
    """A real beta.1 settings file (the committed fixture), with the Gemini defaults beta.1 could have saved."""
    document = json.loads((FIXTURES / "0.1.0-beta.1" / "settings.json").read_text(encoding="utf-8"))
    document.pop("schema_version", None)
    if gemini:
        document.update(default_worker="gemini", default_reviewer_tool="gemini", default_worker_profile="gemini-2.5-pro")
    return json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")


class MigrationFaultTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data = Path(tmp.name) / "data"
        self.data.mkdir()
        self.settings = self.data / "settings.json"
        self.original = v1_settings()
        self.settings.write_bytes(self.original)

    def populate(self):
        """The rest of a real data root: signed evidence, approvals, checkpoints, receipts and an append-only event journal."""
        for rel, content in (("state/run-20261101000000-aaaaaaaaaaaa/result.json", b'{"signed": "evidence"}'),
                             ("state/run-20261101000000-aaaaaaaaaaaa/worker.patch", b"+value = 1\n"),
                             ("approvals/chal-0123456789abcdef.json", b'{"approval": 1}'),
                             ("projects/proj-x/checkpoint.json", b'{"checkpoint": 1}'),
                             ("receipts/github-pr-1.json", b"{}"), (".engine-key", b"k" * 32)):
            path = self.data / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        journal = Journal(self.data / "state" / "events.log")
        for i in range(25):
            journal.append(f"op-{i}", "run.started", f"run-{i}", {"i": i})

    def assert_untouched_original(self):
        self.assertEqual(self.settings.read_bytes(), self.original)

    def test_a_real_beta1_file_moves_and_every_other_byte_in_the_data_root_stays(self):
        self.populate()
        before = digest_tree(self.data)
        self.assertEqual(migrate_data(self.data), ["settings.json"])
        after = digest_tree(self.data)
        changed = {k for k in after if after.get(k) != before.get(k)}
        self.assertEqual(changed, {"settings.json", "settings.json.v1.bak"})  # nothing else moved, appeared or vanished
        self.assertEqual(set(before) - set(after), set())
        self.assertEqual(after["settings.json.v1.bak"], hashlib.sha256(self.original).hexdigest())  # the backup IS the old file
        moved = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual((moved["schema_version"], moved["default_worker"], moved["default_worker_profile"]), (2, "agy", ""))
        journal = Journal(self.data / "state" / "events.log")
        self.assertEqual((journal.last_seq, journal.corrupt, len(journal.replay())), (25, False, 25))  # the event store reads on, untouched

    def test_the_second_run_changes_nothing(self):
        migrate_data(self.data)
        settled = digest_tree(self.data)
        self.assertEqual(migrate_data(self.data), [])
        self.assertEqual(digest_tree(self.data), settled)

    def test_killing_the_process_at_the_worst_moment_leaves_the_old_file_and_the_next_run_finishes_the_job(self):
        script = (f"import os, sys\nsys.path.insert(0, r'{SRC}')\n"
                  "from respected_orchestrator import context\n"
                  "context._replace = lambda *a, **k: os._exit(9)  # power loss right before the new file replaces the old one\n"
                  f"from respected_orchestrator.interfaces.migrate import migrate_data\nmigrate_data(r'{self.data}')\n")
        died = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(died.returncode, 9)
        self.assert_untouched_original()  # the previous good file is exactly as it was
        self.assertEqual((self.data / "settings.json.v1.bak").read_bytes(), self.original)
        self.assertEqual(migrate_data(self.data), ["settings.json"])  # nothing special is needed to recover
        self.assertEqual(json.loads(self.settings.read_text(encoding="utf-8"))["schema_version"], 2)
        self.assertEqual((self.data / "settings.json.v1.bak").read_bytes(), self.original)  # and the backup was not overwritten

    def test_a_failing_write_raises_a_clear_error_and_changes_nothing_but_the_backup(self):
        with mock.patch("respected_orchestrator.context._replace", side_effect=PermissionError(13, "Erişim engellendi")):
            with self.assertRaises(MigrationError) as caught:
                migrate_data(self.data)
        self.assertIn("settings.json yazılamadı", str(caught.exception))
        self.assert_untouched_original()
        self.assertEqual([p.name for p in self.data.glob(".state-*")], [])  # no temp litter after a clean failure
        self.assertEqual(migrate_data(self.data), ["settings.json"])  # fault gone: it just works

    @unittest.skipUnless(os.name == "nt", "uses the Windows read-only attribute")
    def test_a_read_only_settings_file_is_reported_and_left_alone(self):
        subprocess.run(["attrib", "+R", str(self.settings)], check=True, capture_output=True)
        try:
            with self.assertRaises(MigrationError) as caught:
                migrate_data(self.data)
            self.assertIn("yazılamadı", str(caught.exception))
            self.assert_untouched_original()
        finally:
            subprocess.run(["attrib", "-R", str(self.settings)], capture_output=True)
        self.assertEqual(migrate_data(self.data), ["settings.json"])

    @unittest.skipUnless(os.name == "nt", "uses a Windows ACL")
    def test_a_folder_that_denies_new_files_is_reported_and_the_original_stays(self):
        user = os.environ.get("USERNAME", "")
        denied = subprocess.run(["icacls", str(self.data), "/deny", f"{user}:(WD,AD)"], capture_output=True, text=True)
        self.assertEqual(denied.returncode, 0, denied.stdout + denied.stderr)  # without the ACL the protection would be untested
        try:
            with self.assertRaises(MigrationError):
                migrate_data(self.data)
            self.assert_untouched_original()
        finally:
            subprocess.run(["icacls", str(self.data), "/remove:d", user], capture_output=True)
        self.assertEqual(migrate_data(self.data), ["settings.json"])

    def test_damaged_or_unexpected_files_are_refused_and_never_rewritten(self):
        cases = {
            "invalid json": b"{ not json", "empty file": b"", "truncated": self.original[: len(self.original) // 2],
            "array": b"[1, 2, 3]", "scalar": b"42", "null": b"null", "NUL bytes": b"\x00\x00\x00",
            "version as text": b'{"schema_version": "2"}', "version as bool": b'{"schema_version": true}',
            "version as float": b'{"schema_version": 1.5}', "newer version": b'{"schema_version": 99}',
            "version zero": b'{"schema_version": 0}', "negative version": b'{"schema_version": -1}',
        }
        for name, content in cases.items():
            with self.subTest(name):
                self.settings.write_bytes(content)
                before = digest_tree(self.data)
                with self.assertRaises(MigrationError, msg=f"{name} was accepted"):
                    migrate_data(self.data)
                self.assertEqual(digest_tree(self.data), before, name)  # no byte changed, no backup appeared

    def test_an_existing_backup_is_never_overwritten(self):
        backup = self.data / "settings.json.v1.bak"
        backup.write_bytes(b"the oldest copy the person has")
        migrate_data(self.data)
        self.assertEqual(backup.read_bytes(), b"the oldest copy the person has")
        self.assertEqual(json.loads(self.settings.read_text(encoding="utf-8"))["schema_version"], 2)

    def test_a_file_with_a_byte_order_mark_still_migrates(self):
        self.settings.write_bytes(b"\xef\xbb\xbf" + self.original)
        self.assertEqual(migrate_data(self.data), ["settings.json"])
        self.assertEqual(json.loads(self.settings.read_text(encoding="utf-8"))["schema_version"], 2)

    def test_unreadable_input_is_a_migration_error_not_a_crash(self):
        with mock.patch.object(Path, "read_bytes", side_effect=PermissionError(13, "Erişim engellendi")):
            with self.assertRaises(MigrationError) as caught:
                migrate_data(self.data)
        self.assertIn("okunamadı", str(caught.exception))

    def test_a_missing_data_root_or_file_is_not_an_error(self):
        self.assertEqual(migrate_data(self.data / "nowhere"), [])
        self.settings.unlink()
        self.assertEqual(migrate_data(self.data), [])

    def test_four_processes_migrating_at_once_end_with_one_valid_current_file(self):
        script = f"import sys\nsys.path.insert(0, r'{SRC}')\nfrom respected_orchestrator.interfaces.migrate import migrate_data\nprint(migrate_data(r'{self.data}'))\n"
        procs = [subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
        results = [p.communicate(timeout=60) + (p.returncode,) for p in procs]
        self.assertTrue(all(code == 0 for _, _, code in results), results)
        document = json.loads(self.settings.read_text(encoding="utf-8"))  # parses: never a half-written file
        self.assertEqual((document["schema_version"], document["default_worker"]), (2, "agy"))
        self.assertEqual((self.data / "settings.json.v1.bak").read_bytes(), self.original)
        self.assertEqual([p.name for p in self.data.glob(".state-*")], [])

    def test_the_committed_release_fixtures_both_reach_the_current_format_losslessly(self):
        for release in ("0.1.0-beta.1", "0.1.0-beta.2"):
            with self.subTest(release):
                data = self.data.parent / release
                data.mkdir()
                raw = (FIXTURES / release / "settings.json").read_bytes()
                (data / "settings.json").write_bytes(raw)
                old = json.loads(raw)
                migrate_data(data)
                new = json.loads((data / "settings.json").read_text(encoding="utf-8"))
                self.assertEqual(new["schema_version"], migrate.CURRENT["settings.json"])
                for key, value in old.items():
                    if key != "schema_version":
                        self.assertEqual(new.get(key), value, f"{release}: {key} changed")  # no setting lost or altered (no Gemini in these)
                self.assertEqual(set(new) - set(old), {"schema_version"} if "schema_version" not in old else set())


if __name__ == "__main__":
    unittest.main()
