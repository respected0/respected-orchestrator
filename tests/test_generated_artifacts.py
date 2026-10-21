"""A3: build/test output is not the worker's change, but real source never disappears into the "generated" bucket.

The file list in the first test is the real shape of the 2026-10-12 scope_violation records of Brain lane brain-rpp-v11
(build/lib/**, src/*.egg-info/**, __pycache__) plus the Tauri src-tauri/gen/schemas case of the 2026-10-11 hub lanes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator.engine import lanes
from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.runner import check_result, create_task, execute_task

PY = sys.executable


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True, text=True).stdout


def touch(repo, name, text="x\n"):
    path = Path(repo) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")
    return path


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "project"
        self.repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "Fixture"), ("config", "user.email", "fixture@example.invalid")]:
            git(self.repo, *args)
        touch(self.repo, "src/pkg/mod.py", "value = 0\n")
        touch(self.repo, "outside.txt", "private\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "baseline")
        self.baseline = git(self.repo, "rev-parse", "HEAD").strip()
        self.lane = lanes.Lane(repo_root=self.repo, worktree=self.repo, branch="x", run_root=self.root / "run", baseline_commit=self.baseline)

    def clutter(self):
        for name in ["build/lib/pkg/__init__.py", "build/lib/pkg/rpp.py", "src/pkg.egg-info/PKG-INFO", "src/pkg.egg-info/SOURCES.txt",
                     "src/pkg/__pycache__/mod.cpython-313.pyc", "src-tauri/gen/schemas/desktop.json", "target/debug/app.exe",
                     "node_modules/x/index.js"]:
            touch(self.repo, name)
        return 8


class ChangeSetTests(Fixture):
    def test_the_real_scope_violation_shape_is_split_into_source_and_generated(self):
        clutter = self.clutter()
        touch(self.repo, "src/pkg/mod.py", "value = 1\n")  # tracked, modified
        touch(self.repo, "src/pkg/rpp.py", "new source\n")  # untracked, a real new file
        changes = lanes.collect_worker_changes(self.lane, ["src/pkg"])
        self.assertEqual(changes.paths, ("src/pkg/mod.py", "src/pkg/rpp.py"))
        self.assertEqual(len(changes.generated), clutter)
        self.assertIn("build/lib/pkg/rpp.py", changes.generated)
        self.assertTrue(lanes.validate_change_scope(changes, ["src/pkg"], []).allowed)

    def test_legitimate_source_that_only_looks_generated_stays_a_real_change(self):
        for name in ["src/pkg/builder.py", "src/pkg/build.py", "src/pkg/targets.py", "src/pkg/dist_utils.py", "src/pkg/gen.py"]:
            touch(self.repo, name)
        changes = lanes.collect_worker_changes(self.lane, ["src/pkg"])
        self.assertEqual(changes.generated, ())
        self.assertEqual(len(changes.paths), 5)

    def test_a_tracked_directory_called_build_is_source_unless_the_repository_ignores_the_output(self):
        touch(self.repo, "build/keep.txt", "a tracked file inside a directory that is called build\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "track build/keep.txt")
        lane = lanes.Lane(self.repo, self.repo, "x", self.root / "run", git(self.repo, "rev-parse", "HEAD").strip())
        touch(self.repo, "build/keep.txt", "edited\n")  # tracked: always a real change
        touch(self.repo, "build/new.txt")  # untracked, not ignored, in a directory the repository tracks files in
        changes = lanes.collect_worker_changes(lane, ["src/pkg"])
        self.assertEqual((changes.paths, changes.generated), (("build/keep.txt", "build/new.txt"), ()))
        scope = lanes.validate_change_scope(changes, ["src/pkg"], [])
        self.assertFalse(scope.allowed)  # unowned real changes still fail closed
        self.assertEqual(scope.violations, ("build/keep.txt", "build/new.txt"))
        # the repository says build/lib is output: now that path is generated, the rest stays source
        touch(self.repo, ".gitignore", "build/lib/\n")
        touch(self.repo, "build/lib/pkg/a.py")
        again = lanes.collect_worker_changes(lane, ["src/pkg"])
        self.assertEqual(again.generated, ("build/lib/pkg/a.py",))
        self.assertIn("build/new.txt", again.paths)

    def test_an_ownership_entry_that_names_the_location_authorises_it(self):
        touch(self.repo, "dist/notes.md")
        touch(self.repo, "dist/other.bin")
        changes = lanes.collect_worker_changes(self.lane, ["dist/notes.md"])
        self.assertEqual(changes.paths, ("dist/notes.md",))
        self.assertEqual(changes.generated, ("dist/other.bin",))  # only what was named is source

    def test_bytecode_and_caches_are_generated_even_under_a_broad_ownership(self):
        touch(self.repo, "src/pkg/__pycache__/x.pyc")
        touch(self.repo, "src/pkg/stray.pyc")
        touch(self.repo, "src/.pytest_cache/v/cache/lastfailed")
        changes = lanes.collect_worker_changes(self.lane, ["src"])
        self.assertEqual(changes.paths, ())
        self.assertEqual(len(changes.generated), 3)

    def test_a_tracked_generated_looking_file_that_changes_is_still_a_real_change(self):
        touch(self.repo, "src/pkg/tracked.pyc")
        git(self.repo, "add", "-f", "src/pkg/tracked.pyc")
        git(self.repo, "commit", "-m", "track a pyc")
        lane = lanes.Lane(self.repo, self.repo, "x", self.root / "run", git(self.repo, "rev-parse", "HEAD").strip())
        touch(self.repo, "src/pkg/tracked.pyc", "changed\n")
        self.assertEqual(lanes.collect_worker_changes(lane, ["src"]).paths, ("src/pkg/tracked.pyc",))

    def test_a_link_leaving_the_worktree_is_never_hidden_as_generated(self):
        outside = self.root / "outside-dir"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret", encoding="utf8")
        link = self.repo / "build" / "lib" / "escape"
        link.parent.mkdir(parents=True)
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError):  # no symlink privilege: a directory junction is the same escape on Windows
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
            if made.returncode:
                self.skipTest("neither symlinks nor junctions can be created here")
        changes = lanes.collect_worker_changes(self.lane, ["src/pkg"])
        self.assertTrue(changes.unsafe_paths, changes)  # whatever git lists under the link resolves outside the worktree
        self.assertTrue(all(path.startswith("build/lib/escape") for path in changes.unsafe_paths))
        self.assertFalse(lanes.validate_change_scope(changes, ["src/pkg"], []).allowed)


class PatchTests(Fixture):
    def test_generated_output_never_enters_the_patch_and_the_patch_applies(self):
        self.clutter()
        touch(self.repo, "src/pkg/mod.py", "value = 1\n")
        touch(self.repo, "src/pkg/rpp.py", "new source\n")
        patch = lanes.export_worker_patch(self.lane, self.root / "worker.patch", ["src/pkg"])
        text = patch.path.read_text(encoding="utf8")
        self.assertIn("src/pkg/rpp.py", text)
        self.assertIn("src/pkg/mod.py", text)
        for forbidden in ("build/lib", "egg-info", ".pyc", "src-tauri/gen", "target/", "node_modules"):
            self.assertNotIn(forbidden, text)
        clean = self.root / "clean"
        subprocess.run(["git", "clone", "-q", str(self.repo), str(clean)], capture_output=True, check=True)
        git(clean, "checkout", "-q", self.baseline)
        self.assertIs(lanes.check_patch_against_master(clean, patch.path), lanes.RunStatus.COMPLETE)

    def test_an_ignored_path_the_ownership_names_is_exported_but_other_ignored_files_fail_closed(self):
        # found by the independent reviewer: git refuses "add -N" for ignored paths, so an authorised dist/ file was lost
        touch(self.repo, ".gitignore", "dist/" + chr(10) + ".env" + chr(10))
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-m", "ignore dist and .env")
        lane = lanes.Lane(self.repo, self.repo, "x", self.root / "run", git(self.repo, "rev-parse", "HEAD").strip())
        touch(self.repo, "dist/notes.md", "named by the ownership" + chr(10))
        patch = lanes.export_worker_patch(lane, self.root / "named.patch", ["dist/notes.md"])
        self.assertIn("dist/notes.md", patch.path.read_text(encoding="utf8"))
        git(self.repo, "reset", "-q")  # drop the intent-to-add from the first export
        touch(self.repo, "src/pkg/.env", "SECRET=1" + chr(10))  # ignored, inside a broadly owned directory, never named
        with self.assertRaises(lanes.LaneError):
            lanes.export_worker_patch(lane, self.root / "leak.patch", ["src/pkg"])
        self.assertFalse((self.root / "leak.patch").exists())  # nothing ignored is written into a patch

    def test_a_real_integration_conflict_still_fails_closed(self):
        touch(self.repo, "src/pkg/mod.py", "value = 1\n")
        patch = lanes.export_worker_patch(self.lane, self.root / "worker.patch", ["src/pkg"])
        master = self.root / "master"
        subprocess.run(["git", "clone", "-q", str(self.repo), str(master)], capture_output=True, check=True)
        git(master, "checkout", "-q", self.baseline)
        touch(master, "src/pkg/mod.py", "value = 99\n")  # master moved on under the patch
        self.assertIs(lanes.check_patch_against_master(master, patch.path), lanes.RunStatus.INTEGRATION_CONFLICT)


class EndToEndTests(Fixture):
    """Real runs: the engine decides, not a unit stub."""

    def setUp(self):
        super().setUp()
        self.ctx = EngineContext(self.root / "data")
        patcher = mock.patch("respected_orchestrator.engine.runner._stdin_is_tty", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def task(self, code, **extra):
        request = {"project_root": str(self.repo), "task": "t", "worker": "custom", "kind": "write", "ownership": ["src/pkg"],
                   "forbidden": ["outside.txt"], "command": [PY, "-c", code],
                   "acceptance": [[PY, "-c", "from pathlib import Path; assert Path('src/pkg/mod.py').read_text() == 'value = 1' + chr(10)"]],
                   "timeout_seconds": 30}
        request.update(extra)
        return create_task(self.ctx, request)["run_id"]

    EDIT = "from pathlib import Path; Path('src/pkg/mod.py').write_text('value = 1' + chr(10))"
    CLUTTER = ("import os; [(os.makedirs(os.path.dirname(p), exist_ok=True), open(p, 'w').write('x')) for p in "
               "['build/lib/pkg/a.py', 'src/pkg.egg-info/PKG-INFO', 'src/pkg/__pycache__/a.pyc', 'target/debug/t']]")

    def test_a_worker_that_also_leaves_build_output_is_completed_verified_and_applied_without_it(self):
        run_id = self.task(self.CLUTTER + "; " + self.EDIT)
        result = execute_task(self.ctx, run_id)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["changed_files"], ["src/pkg/mod.py"])
        self.assertEqual(result["generated_artifact_count"], 4)
        self.assertEqual(check_result(self.ctx, run_id)["changed_files"], ["src/pkg/mod.py"])

    def test_acceptance_that_writes_bytecode_does_not_fail_a_correct_lane(self):
        # the 2026-10-11 py_compile acceptance bug: acceptance itself leaves __pycache__
        acceptance = [[PY, "-c", "import py_compile; py_compile.compile('src/pkg/mod.py', cfile='src/pkg/__pycache__/mod.pyc')"],
                      [PY, "-c", "from pathlib import Path; assert Path('src/pkg/mod.py').read_text() == 'value = 1' + chr(10)"]]
        result = execute_task(self.ctx, self.task(self.EDIT, acceptance=acceptance))
        self.assertEqual((result["status"], result["changed_files"]), ("completed", ["src/pkg/mod.py"]))

    def test_real_scope_violations_are_still_reported_and_never_blamed_on_generated_files(self):
        run_id = self.task(self.CLUTTER + "; " + self.EDIT + "; open('outside.txt', 'w').write('oops')")
        result = execute_task(self.ctx, run_id)
        self.assertEqual((result["status"], result["reason"]), ("failed", "scope_violation"))
        self.assertEqual(result["changed_files"], ["outside.txt", "src/pkg/mod.py"])

    def test_a_read_task_that_only_leaves_build_output_changed_nothing(self):
        result = execute_task(self.ctx, self.task(self.CLUTTER, kind="read", acceptance=[]))
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["changed_files"], [])

    def test_an_unowned_new_source_file_is_a_violation_even_next_to_build_output(self):
        run_id = self.task(self.CLUTTER + "; " + self.EDIT + "; open('notes.md', 'w').write('x')")
        self.assertEqual(execute_task(self.ctx, run_id)["reason"], "scope_violation")


if __name__ == "__main__":
    unittest.main()
