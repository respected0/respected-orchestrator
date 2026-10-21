#!/usr/bin/env python3
"""Behavioral tests for guarded Antigravity worker orchestration."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_orchestrator():
    from respected_orchestrator.engine import antigravity_orchestrator
    return antigravity_orchestrator


def context_for(root: Path):
    from respected_orchestrator.context import EngineContext
    return EngineContext(root / "data")


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


def make_fake_agy(root: Path) -> tuple[Path, Path]:
    script = root / "fake_agy.py"
    record = root / "fake-agy-record.jsonl"
    script.write_text(
        """import json
import os
from pathlib import Path
import sys

record = Path(os.environ["FAKE_AGY_RECORD"])
with record.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}, ensure_ascii=False) + "\\n")
mode = os.environ.get("FAKE_AGY_MODE", "success")
if mode == "success":
    print(json.dumps({"status": "SUCCESS", "summary": "done"}))
elif mode == "change":
    Path("src/owned.txt").write_text("worker-change\\n", encoding="utf-8")
    print(json.dumps({"status": "SUCCESS", "summary": "changed"}))
elif mode == "forbidden":
    Path("other.txt").write_text("forbidden-worker-change\\n", encoding="utf-8")
    print(json.dumps({"status": "SUCCESS", "summary": "changed forbidden file"}))
elif mode == "limit":
    print("quota limit exhausted", file=sys.stderr)
    raise SystemExit(42)
elif mode == "auth":
    print("authentication required: login", file=sys.stderr)
    raise SystemExit(43)
elif mode == "malformed":
    print("not-json")
elif mode == "logical-failure":
    print(json.dumps({"status": "FAILED", "error": "worker rejected task"}))
else:
    print("worker crashed", file=sys.stderr)
    raise SystemExit(2)
""",
        encoding="utf-8",
    )
    if os.name == "nt":
        wrapper = root / "agy.cmd"
        wrapper.write_text(
            f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8"
        )
    else:
        wrapper = root / "agy"
        wrapper.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8"
        )
        wrapper.chmod(0o755)
    return wrapper, record


class PolicyFilesTest(unittest.TestCase):
    def test_policy_defines_guarded_single_writer_defaults(self) -> None:
        policy_file = ROOT / "src/respected_orchestrator/resources/policy.json"
        policy = json.loads(
            policy_file.read_text(encoding="utf-8")
        )

        self.assertEqual(policy["schema_version"], 1)
        self.assertEqual(policy["max_active_write_workers"], 1)
        self.assertFalse(policy["dangerously_skip_permissions"])
        self.assertGreater(policy["read_timeout_seconds"], 0)
        self.assertGreater(policy["write_timeout_seconds"], 0)
        self.assertTrue(policy["worker_executable_candidates"])
        self.assertEqual(policy["workspace_root"], "")

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


class ConfigurationTest(unittest.TestCase):
    def test_load_policy_and_resolve_expanded_executable_candidate(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            executable = root / "agy" / "bin" / "agy.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"fake")
            policy_path = root / "policy.json"
            policy_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "worker_executable_candidates": [
                            "%LOCALAPPDATA%/agy/bin/agy.exe"
                        ],
                        "workspace_root": "../repo-worktrees",
                        "max_active_write_workers": 1,
                        "read_timeout_seconds": 10,
                        "write_timeout_seconds": 20,
                        "dangerously_skip_permissions": False,
                    }
                ),
                encoding="utf-8",
            )

            policy = orchestrator.load_policy(policy_path)
            resolved = orchestrator.resolve_agy(
                policy, {"LOCALAPPDATA": str(root), "PATH": ""}
            )

            self.assertEqual(resolved, executable.resolve())
            self.assertEqual(policy.max_active_write_workers, 1)

    def test_missing_worker_executable_is_a_typed_error(self) -> None:
        orchestrator = load_orchestrator()
        policy = orchestrator.Policy(
            schema_version=1,
            worker_executable_candidates=("definitely-missing-agy",),
            workspace_root="../workers",
            max_active_write_workers=1,
            read_timeout_seconds=10,
            write_timeout_seconds=20,
            dangerously_skip_permissions=True,
        )

        with self.assertRaises(orchestrator.WorkerUnavailableError):
            orchestrator.resolve_agy(policy, {"PATH": ""})

    def test_inaccessible_worker_candidate_is_a_typed_error(self) -> None:
        orchestrator = load_orchestrator()
        policy = orchestrator.Policy(
            schema_version=1,
            worker_executable_candidates=("C:/protected/agy.exe",),
            workspace_root="../workers",
            max_active_write_workers=1,
            read_timeout_seconds=10,
            write_timeout_seconds=20,
            dangerously_skip_permissions=True,
        )

        with mock.patch.object(Path, "is_file", side_effect=PermissionError("denied")):
            with self.assertRaises(orchestrator.WorkerUnavailableError):
                orchestrator.resolve_agy(policy, {"PATH": ""})


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


class WorkerInvocationTest(unittest.TestCase):
    def make_worker(self, orchestrator, root: Path, kind=None):
        worktree = (root / "lane").resolve()
        (worktree / "src").mkdir(parents=True)
        (worktree / "src" / "owned.txt").write_text("base\n", encoding="utf-8")
        run_root = (root / "state" / "run-001").resolve()
        lane = orchestrator.Lane(
            repo_root=ROOT.resolve(),
            worktree=worktree,
            branch="agy/test-worker",
            run_root=run_root,
            baseline_commit="a" * 40,
        )
        request = orchestrator.RunRequest(
            run_id="run-001",
            slug="test-worker",
            kind=kind or orchestrator.TaskKind.READ,
            objective="Report the repository root basename.",
            known_context="Do not include any master conversation.",
            ownership=("src",),
            forbidden=(".git",),
            acceptance=((sys.executable, "--version"),),
            include_untracked=(),
        )
        return request, lane

    def test_runs_once_inside_lane_with_required_flags(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fake_agy, record = make_fake_agy(root)
            request, lane = self.make_worker(orchestrator, root)
            with mock.patch.dict(
                os.environ,
                {"FAKE_AGY_RECORD": str(record), "FAKE_AGY_MODE": "success"},
            ):
                result = orchestrator.run_worker(request, lane, fake_agy)

            invocation = json.loads(record.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(Path(invocation["cwd"]).resolve(), lane.worktree.resolve())
            self.assertNotIn("--dangerously-skip-permissions", invocation["argv"])
            self.assertIn("--output-format", invocation["argv"])
            self.assertIn("json", invocation["argv"])
            self.assertIn("--print-timeout", invocation["argv"])
            self.assertIn("READ-ONLY TASK", (lane.run_root / "brief.md").read_text(encoding="utf-8"))
            self.assertEqual(result.status, orchestrator.RunStatus.COMPLETE)
            self.assertEqual(len(record.read_text(encoding="utf-8").splitlines()), 1)
            process = json.loads(
                (lane.run_root / "process.json").read_text(encoding="utf-8")
            )
            self.assertGreater(process["pid"], 0)
            self.assertEqual(process["state"], "FINISHED")
            self.assertEqual(process["timeout_seconds"], 900)

    def test_malformed_success_is_rejected(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fake_agy, record = make_fake_agy(root)
            request, lane = self.make_worker(orchestrator, root)
            with mock.patch.dict(
                os.environ,
                {"FAKE_AGY_RECORD": str(record), "FAKE_AGY_MODE": "malformed"},
            ):
                result = orchestrator.run_worker(request, lane, fake_agy)

            self.assertEqual(result.status, orchestrator.RunStatus.WORKER_FAILED)
            self.assertEqual(len(record.read_text(encoding="utf-8").splitlines()), 1)

    def test_zero_exit_failure_payload_is_rejected(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fake_agy, record = make_fake_agy(root)
            request, lane = self.make_worker(orchestrator, root)
            with mock.patch.dict(
                os.environ,
                {"FAKE_AGY_RECORD": str(record), "FAKE_AGY_MODE": "logical-failure"},
            ):
                result = orchestrator.run_worker(request, lane, fake_agy)

            self.assertEqual(result.status, orchestrator.RunStatus.WORKER_FAILED)


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

    def test_limit_result_is_persisted_after_one_process(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            fake_agy, record = make_fake_agy(root)
            request, lane = WorkerInvocationTest().make_worker(orchestrator, root)
            with mock.patch.dict(
                os.environ,
                {"FAKE_AGY_RECORD": str(record), "FAKE_AGY_MODE": "limit"},
            ):
                result = orchestrator.run_worker(request, lane, fake_agy)

            persisted = json.loads(
                (lane.run_root / "worker-result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result.status, orchestrator.RunStatus.LIMIT_EXHAUSTED)
            self.assertEqual(persisted["status"], "LIMIT_EXHAUSTED")
            self.assertEqual(len(record.read_text(encoding="utf-8").splitlines()), 1)


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


class AcceptanceTest(unittest.TestCase):
    def test_records_redacted_output_and_stops_after_first_failure(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            lane = orchestrator.Lane(
                repo_root=root,
                worktree=root,
                branch="agy/checks",
                run_root=root / "state",
                baseline_commit="a" * 40,
            )
            marker = root / "must-not-run.txt"
            commands = (
                (sys.executable, "-c", "print('token=super-secret')"),
                (sys.executable, "-c", "raise SystemExit(7)"),
                (sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('bad')"),
            )

            checks = orchestrator.run_acceptance(lane, commands)

            self.assertEqual([check.returncode for check in checks], [0, 7])
            self.assertFalse(marker.exists())
            first_log = checks[0].stdout_path.read_text(encoding="utf-8")
            self.assertIn("token=[REDACTED]", first_log)
            self.assertNotIn("super-secret", first_log)

    def test_acceptance_timeout_is_terminal_and_stops_later_commands(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            lane = orchestrator.Lane(
                repo_root=root,
                worktree=root,
                branch="agy/timeout",
                run_root=root / "state",
                baseline_commit="a" * 40,
            )
            marker = root / "must-not-run.txt"
            commands = (
                (sys.executable, "-c", "import time; time.sleep(2)"),
                (sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('bad')"),
            )

            checks = orchestrator.run_acceptance(lane, commands, timeout_seconds=0.05)

            self.assertEqual(len(checks), 1)
            self.assertTrue(checks[0].timed_out)
            self.assertEqual(checks[0].returncode, 124)
            self.assertFalse(marker.exists())


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


class CLIWorkflowTest(unittest.TestCase):
    def write_policy(self, repo: Path, workspace: Path, fake_agy: Path) -> Path:
        policy_path = repo / "policy.json"
        policy_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "worker_executable_candidates": [str(fake_agy)],
                    "workspace_root": str(workspace),
                    "max_active_write_workers": 1,
                    "read_timeout_seconds": 10,
                    "write_timeout_seconds": 20,
                    "dangerously_skip_permissions": False,
                }
            ),
            encoding="utf-8",
        )
        return policy_path

    def test_write_workflow_preserves_master_until_explicit_apply(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = init_repo(root)
            fake_agy, record = make_fake_agy(root)
            workspace = root / "worker lanes 🚀"
            policy = self.write_policy(repo, workspace, fake_agy)
            original = (repo / "src" / "owned.txt").read_bytes()
            arguments = [
                "run-write",
                "--repo-root",
                str(repo),
                "--policy",
                str(policy),
                "--run-id",
                "run-e2e",
                "--slug",
                "e2e-change",
                "--objective",
                "Change the owned fixture.",
                "--owner",
                "src",
                "--forbid",
                "other.txt",
                "--accept",
                json.dumps([sys.executable, "-c", "from pathlib import Path; assert Path('src/owned.txt').read_text() == 'worker-change\\n'"]),
            ]
            with mock.patch.dict(
                os.environ,
                {"FAKE_AGY_RECORD": str(record), "FAKE_AGY_MODE": "change"},
            ):
                code = orchestrator.main(arguments, ctx=context_for(root), project_root=repo)

            run_root = context_for(root).paths.state_dir / "orchestration" / "run-e2e"
            verification = json.loads(
                (run_root / "verification.json").read_text(encoding="utf-8")
            )
            process = json.loads((run_root / "process.json").read_text(encoding="utf-8"))
            patch = run_root / "worker.patch"
            self.assertEqual(code, 0)
            self.assertEqual(verification["status"], "COMPLETE")
            self.assertEqual(process["timeout_seconds"], 20)
            self.assertTrue(patch.is_file())
            self.assertEqual((repo / "src" / "owned.txt").read_bytes(), original)

            with self.assertRaisesRegex(ValueError, "Raw patch"):
                orchestrator.main(
                    ["apply-patch", "--repo-root", str(repo), "--patch", str(patch)], ctx=context_for(root), project_root=repo
                )
            self.assertEqual((repo / "src" / "owned.txt").read_bytes(), original)

    def test_scope_violation_preserves_lane_and_never_applies(self) -> None:
        orchestrator = load_orchestrator()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repo = init_repo(root)
            fake_agy, record = make_fake_agy(root)
            workspace = root / "workers"
            policy = self.write_policy(repo, workspace, fake_agy)
            original = (repo / "other.txt").read_bytes()
            with mock.patch.dict(
                os.environ,
                {"FAKE_AGY_RECORD": str(record), "FAKE_AGY_MODE": "forbidden"},
            ):
                code = orchestrator.main(
                    [
                        "run-write",
                        "--repo-root",
                        str(repo),
                        "--policy",
                        str(policy),
                        "--run-id",
                        "run-scope",
                        "--slug",
                        "scope-violation",
                        "--objective",
                        "Attempt a bounded change.",
                        "--owner",
                        "src",
                        "--forbid",
                        "other.txt",
                    ], ctx=context_for(root), project_root=repo
                )

            run_root = context_for(root).paths.state_dir / "orchestration" / "run-scope"
            verification = json.loads(
                (run_root / "verification.json").read_text(encoding="utf-8")
            )
            self.assertNotEqual(code, 0)
            self.assertEqual(verification["status"], "SCOPE_VIOLATION")
            self.assertEqual((repo / "other.txt").read_bytes(), original)
            self.assertTrue((workspace / "scope-violation").is_dir())

    def test_write_requires_explicit_ownership_and_json_argument_arrays(self) -> None:
        orchestrator = load_orchestrator()
        with self.assertRaises(SystemExit):
            orchestrator.main(
                [
                    "run-write",
                    "--slug",
                    "missing-owner",
                    "--objective",
                    "No ownership supplied.",
                ]
            )
        with self.assertRaises(SystemExit):
            orchestrator.main(
                [
                    "run-write",
                    "--slug",
                    "bad-accept",
                    "--objective",
                    "Malformed acceptance.",
                    "--owner",
                    "src",
                    "--accept",
                    "not-json",
                ]
            )


if __name__ == "__main__":
    unittest.main()
