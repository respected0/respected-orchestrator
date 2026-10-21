"""Behavioral tests for isolated worker lanes (engine/lanes.py)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]


def load_orchestrator():
    from respected_orchestrator.engine import lanes
    return lanes


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )


def init_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.name", "Orchestration Test")
    run_git(repo, "config", "user.email", "orchestration@example.invalid")
    (repo / "src").mkdir()
    (repo / "src" / "owned.txt").write_text("base-owned\n", encoding="utf-8")
    (repo / "other.txt").write_text("base-other\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    run_git(repo, "add", ".")
    run_git(repo, "commit", "-m", "baseline")
    return repo


class WorkerTemplateTest(unittest.TestCase):
    def test_worker_templates_define_bounded_handoff_sections(self) -> None:
        orchestrator = load_orchestrator()
        required = {
            "ROLE",
            "OBJECTIVE",
            "KNOWN CONTEXT",
            "WORKSPACE",
            "OWNERSHIP",
            "FORBIDDEN",
            "RULES",
            "ACCEPTANCE",
            "RETURN",
        }

        for name, text in (("read-worker.md", orchestrator.DEFAULT_READ_TEMPLATE), ("write-worker.md", orchestrator.DEFAULT_WRITE_TEMPLATE)):
            headings = {
                line.removeprefix("## ").strip()
                for line in text.splitlines()
                if line.startswith("## ")
            }
            self.assertTrue(required.issubset(headings), name)
            self.assertIn("Do not run git reset, git clean, git restore, or git stash.", text)
            self.assertIn("Operate only inside the assigned worktree.", text)

        read_text = orchestrator.DEFAULT_READ_TEMPLATE
        self.assertIn("READ-ONLY TASK", read_text)
        self.assertIn("Do not modify repository files.", read_text)


class PathSafetyTest(unittest.TestCase):
    def test_normalizes_unicode_repository_path(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "src" / "Türkçe 🚀.py"
            target.parent.mkdir()
            target.write_text("pass\n", encoding="utf-8")

            self.assertEqual(
                orchestrator.normalize_repo_path(root, "src/Türkçe 🚀.py"),
                "src/Türkçe 🚀.py",
            )

    def test_rejects_parent_traversal_and_absolute_outside_path(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            outside = root.parent / "outside.txt"

            with self.assertRaises(ValueError):
                orchestrator.normalize_repo_path(root, "../outside.txt")
            with self.assertRaises(ValueError):
                orchestrator.normalize_repo_path(root, str(outside))


class WriterLockTest(unittest.TestCase):
    def test_active_writer_lock_blocks_a_second_writer(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary).resolve()
            lock = orchestrator.WriterLock.acquire(
                state_root, "run-one", "write", Path("C:/worker-one")
            )
            self.addCleanup(lock.release)

            with self.assertRaisesRegex(orchestrator.WriterLockError, "active"):
                orchestrator.WriterLock.acquire(
                    state_root, "run-two", "write", Path("C:/worker-two")
                )

    def test_stale_writer_lock_of_a_dead_process_is_reclaimed(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary).resolve()
            state_root.mkdir(exist_ok=True)
            lock_path = state_root / ".write-worker.lock.json"
            lock_path.write_text(
                json.dumps(
                    {
                        "run_id": "old-run",
                        "pid": 2147483647,
                        "task_kind": "write",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "workspace": "C:/old-worker",
                    }
                ),
                encoding="utf-8",
            )

            lock = orchestrator.WriterLock.acquire(state_root, "new-run", "write", Path("C:/new-worker"))
            self.addCleanup(lock.release)
            self.assertEqual(json.loads(lock_path.read_text(encoding="utf-8"))["run_id"], "new-run")


class GitLaneTest(unittest.TestCase):
    def make_request(self, orchestrator, **overrides):
        values = {
            "run_id": "run-001",
            "slug": "fix-owned",
            "kind": orchestrator.TaskKind.WRITE,
            "objective": "Update the owned fixture.",
            "known_context": "Temporary test repository.",
            "ownership": ("src",),
            "forbidden": (".git",),
            "acceptance": (),
            "include_untracked": (),
        }
        values.update(overrides)
        return orchestrator.RunRequest(**values)

    def make_paths(self, orchestrator, root: Path, repo: Path):
        workspace = root / "repo-worktrees"
        return orchestrator.RunPaths(
            repo_root=repo,
            workspace_root=workspace,
            state_root=workspace / ".orchestration-state",
            run_root=workspace / ".orchestration-state" / "run-001",
        )

    def test_creates_sibling_lane_without_changing_master(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = init_repo(root)
            before = run_git(repo, "status", "--porcelain=v1", "--branch").stdout

            lane = orchestrator.create_lane(
                self.make_request(orchestrator),
                self.make_paths(orchestrator, root, repo),
            )

            self.assertEqual(lane.worktree.parent.resolve(), (root / "repo-worktrees").resolve())
            self.assertEqual(lane.branch, "orchestrator/fix-owned")
            self.assertEqual(run_git(lane.worktree, "branch", "--show-current").stdout.strip(), lane.branch)
            self.assertEqual(run_git(repo, "status", "--porcelain=v1", "--branch").stdout, before)

    def test_overlays_only_owned_dirty_inputs_and_commits_lane_baseline(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = init_repo(root)
            owned = repo / "src" / "owned.txt"
            other = repo / "other.txt"
            new_file = repo / "src" / "Türkçe 🚀.txt"
            owned.write_text("dirty-owned\n", encoding="utf-8")
            other.write_text("dirty-other\n", encoding="utf-8")
            new_file.write_text("selected-untracked\n", encoding="utf-8")
            before_status = run_git(repo, "status", "--porcelain=v1").stdout
            request = self.make_request(
                orchestrator, include_untracked=("src/Türkçe 🚀.txt",)
            )
            lane = orchestrator.create_lane(
                request, self.make_paths(orchestrator, root, repo)
            )

            manifest = orchestrator.overlay_dirty_inputs(
                lane, request.ownership, request.include_untracked
            )
            commit = orchestrator.commit_lane_baseline(lane, manifest)

            self.assertEqual(
                (lane.worktree / "src" / "owned.txt").read_text(encoding="utf-8"),
                "dirty-owned\n",
            )
            self.assertEqual(
                (lane.worktree / "src" / "Türkçe 🚀.txt").read_text(encoding="utf-8"),
                "selected-untracked\n",
            )
            self.assertEqual(
                (lane.worktree / "other.txt").read_text(encoding="utf-8"),
                "base-other\n",
            )
            self.assertEqual(len(commit), 40)
            self.assertEqual(run_git(repo, "status", "--porcelain=v1").stdout, before_status)
            self.assertEqual(other.read_text(encoding="utf-8"), "dirty-other\n")
            self.assertEqual(manifest.paths, ("src/Türkçe 🚀.txt", "src/owned.txt"))

    def test_rejects_ignored_input_and_lane_collision(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = init_repo(root)
            (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")
            request = self.make_request(orchestrator, include_untracked=(".env",))
            paths = self.make_paths(orchestrator, root, repo)
            lane = orchestrator.create_lane(request, paths)

            with self.assertRaisesRegex(orchestrator.LaneError, "ignored"):
                orchestrator.overlay_dirty_inputs(
                    lane, request.ownership, request.include_untracked
                )
            with self.assertRaises(orchestrator.LaneError):
                orchestrator.create_lane(request, paths)

    def test_rejects_ownership_outside_repository(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = init_repo(root)
            request = self.make_request(orchestrator, ownership=("../outside",))
            lane = orchestrator.create_lane(
                request, self.make_paths(orchestrator, root, repo)
            )

            with self.assertRaises(ValueError):
                orchestrator.overlay_dirty_inputs(
                    lane, request.ownership, request.include_untracked
                )


class CircuitBreakerTest(unittest.TestCase):
    def test_classifies_terminal_worker_failures_without_retry(self) -> None:
        orchestrator = load_orchestrator()
        cases = (
            ((42, "", "quota limit exhausted", False), orchestrator.RunStatus.LIMIT_EXHAUSTED),
            ((43, "", "authentication required: login", False), orchestrator.RunStatus.AUTH_REQUIRED),
            ((2, "", "worker crashed", False), orchestrator.RunStatus.WORKER_FAILED),
            ((0, "", "", True), orchestrator.RunStatus.TIMEOUT),
        )
        for arguments, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(orchestrator.classify_worker_exit(*arguments), expected)

class ScopeEnforcementTest(unittest.TestCase):
    def test_read_lane_requires_zero_diff_and_write_lane_rejects_forbidden_path(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = init_repo(root)
            request = GitLaneTest().make_request(orchestrator)
            paths = GitLaneTest().make_paths(orchestrator, root, repo)
            lane = orchestrator.create_lane(request, paths)
            lane.baseline_commit = run_git(lane.worktree, "rev-parse", "HEAD").stdout.strip()

            self.assertEqual(orchestrator.collect_worker_changes(lane).paths, ())
            (lane.worktree / "src" / "owned.txt").write_text("allowed\n", encoding="utf-8")
            (lane.worktree / "other.txt").write_text("forbidden\n", encoding="utf-8")
            changes = orchestrator.collect_worker_changes(lane)
            scope = orchestrator.validate_change_scope(
                changes, ("src",), ("other.txt", ".git")
            )

            self.assertFalse(scope.allowed)
            self.assertEqual(scope.violations, ("other.txt",))

    def test_unsafe_link_path_is_a_scope_violation(self) -> None:
        orchestrator = load_orchestrator()
        changes = orchestrator.ChangeSet(
            paths=("src/link",),
            statuses={"src/link": "M"},
            unsafe_paths=("src/link",),
        )

        scope = orchestrator.validate_change_scope(changes, ("src",), ())

        self.assertFalse(scope.allowed)
        self.assertEqual(scope.violations, ("src/link",))


class PatchTest(unittest.TestCase):
    def test_exports_only_worker_delta_and_checks_dirty_master_without_mutation(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = init_repo(root)
            owned = repo / "src" / "owned.txt"
            owned.write_text("dirty-owned\n", encoding="utf-8")
            request = GitLaneTest().make_request(orchestrator)
            paths = GitLaneTest().make_paths(orchestrator, root, repo)
            lane = orchestrator.create_lane(request, paths)
            manifest = orchestrator.overlay_dirty_inputs(lane, request.ownership, ())
            orchestrator.commit_lane_baseline(lane, manifest)
            (lane.worktree / "src" / "owned.txt").write_text(
                "worker-change\n", encoding="utf-8"
            )
            patch_path = lane.run_root / "worker.patch"

            patch = orchestrator.export_worker_patch(lane, patch_path)
            before = owned.read_bytes()
            compatible = orchestrator.check_patch_against_master(repo, patch.path)

            self.assertEqual(compatible, orchestrator.RunStatus.COMPLETE)
            self.assertEqual(owned.read_bytes(), before)
            patch_text = patch.path.read_text(encoding="utf-8")
            self.assertIn("worker-change", patch_text)
            self.assertNotIn("base-owned", patch_text)

            owned.write_text("conflicting-master\n", encoding="utf-8")
            conflict_before = owned.read_bytes()
            conflict = orchestrator.check_patch_against_master(repo, patch.path)
            self.assertEqual(conflict, orchestrator.RunStatus.INTEGRATION_CONFLICT)
            self.assertEqual(owned.read_bytes(), conflict_before)


if __name__ == "__main__":
    unittest.main()
