"""RES-01: signed checkpoint/handoff contract, atomicity and migration (no worker calls)."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from respected_orchestrator import context
from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.evidence import load_signed, save_signed
from respected_orchestrator.workflows import checkpoint


REPO_ROOT = Path(__file__).resolve().parents[2]


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ctx = EngineContext(self.root / "data")
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.path = checkpoint.checkpoint_path(self.ctx, "run", "op-test")

    def value(self, kind="run", **changes):
        value = checkpoint.create_checkpoint(
            kind, f"op-{kind}", self.repo, commit=None, role="worker", round_number=0,
            next_action={"step": "review", "target": "patch.diff", "reason_code": "review_ready"},
            checks={"review": "a" * 64},
            limits={"max_rounds": 3, "deadline_epoch": None, "max_weighted_tokens": 1000,
                    "max_seconds": 600},
            updated_at="2026-11-02T10:00:00+00:00",
        )
        value.update(changes)
        return value

    def test_sigterm_mid_operation_leaves_the_last_atomic_snapshot_resumable(self):
        script = r"""
from pathlib import Path
import os
import signal
import sys
from respected_orchestrator.context import EngineContext
from respected_orchestrator.workflows import checkpoint
ctx = EngineContext(Path(sys.argv[1]))
root = Path(sys.argv[2])
path = Path(sys.argv[3])
value = checkpoint.create_checkpoint("run", "op-sigterm", root, commit=None, role="worker")
checkpoint.save_checkpoint(ctx, path, value)
os.kill(os.getpid(), signal.SIGTERM)
raise SystemExit(97)
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        completed = subprocess.run(
            [sys.executable, "-c", script, str(self.ctx.data_root), str(self.repo), str(self.path)],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertNotEqual(0, completed.returncode, completed.stdout + completed.stderr)
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual("RESUMABLE", state["status"], state)
        self.assertEqual("op-sigterm", state["checkpoint"]["operation_id"])

    def test_a_corrupt_temporary_file_is_never_read_and_cannot_damage_the_snapshot(self):
        checkpoint.save_checkpoint(self.ctx, self.path, self.value())
        (self.path.parent / ".state-deadbeef.tmp").write_text("{broken", encoding="utf8")
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual("RESUMABLE", state["status"], state)
        self.assertEqual(0, state["checkpoint"]["round"])

    def test_half_of_a_validly_signed_state_is_needs_review(self):
        payload = self.value()
        payload.pop("updated_at")
        save_signed(self.ctx, self.path, payload)
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual(("NEEDS_REVIEW", "incomplete_snapshot"), (state["status"], state["reason"]), state)

    def test_v1_migrates_once_and_the_second_inspection_is_byte_stable(self):
        old = {
            "schema_version": 1, "kind": "campaign", "operation_id": "op-v1", "commit": None,
            "root": str(self.repo), "role": "worker", "round": 0, "next_step": "review",
            "target": "patch.diff", "check_hashes": {"review": "b" * 64},
            "limits": {"max_rounds": 2, "deadline_epoch": None, "max_weighted_tokens": 50,
                       "max_seconds": 300},
            "updated_at": "2026-11-02T10:00:00+00:00",
        }
        save_signed(self.ctx, self.path, old)
        first = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual("RESUMABLE", first["status"], first)
        self.assertTrue(first["migrated"])
        self.assertEqual(2, first["checkpoint"]["schema_version"])
        self.assertEqual("legacy_resume", first["checkpoint"]["next_action"]["reason_code"])
        settled = self.path.read_bytes()
        second = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertFalse(second["migrated"])
        self.assertEqual(settled, self.path.read_bytes())
        self.assertEqual(2, load_signed(self.ctx, self.path)["schema_version"])
        backup = self.path.with_name(self.path.name + ".v1.bak")
        self.assertEqual(1, load_signed(self.ctx, backup)["schema_version"])

    def test_a_different_git_head_is_needs_review(self):
        def git(*args):
            completed = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True,
                                       text=True, timeout=30, check=False)
            self.assertEqual(0, completed.returncode, completed.stderr)

        git("init")
        git("config", "user.email", "tests@example.invalid")
        git("config", "user.name", "Tests")
        (self.repo / "a.txt").write_text("a\n", encoding="utf8")
        git("add", "a.txt")
        git("commit", "-m", "first")
        value = checkpoint.create_checkpoint("project", "op-head", self.repo, role="master")
        checkpoint.save_checkpoint(self.ctx, self.path, value)
        (self.repo / "b.txt").write_text("b\n", encoding="utf8")
        git("add", "b.txt")
        git("commit", "-m", "second")
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual(("NEEDS_REVIEW", "repo_head_changed"), (state["status"], state["reason"]), state)

    def test_interrupted_replace_keeps_the_previous_complete_snapshot(self):
        original = self.value()
        checkpoint.save_checkpoint(self.ctx, self.path, original)
        replacement = checkpoint.create_checkpoint(
            "run", "op-test", self.repo, commit=None, role="worker", round_number=1,
            checks={"review": "c" * 64}, updated_at="2026-11-02T10:01:00+00:00",
        )
        with mock.patch.object(context, "_replace", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                checkpoint.save_checkpoint(self.ctx, self.path, replacement)
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual("RESUMABLE", state["status"], state)
        self.assertEqual(0, state["checkpoint"]["round"])
        self.assertEqual([], list(self.path.parent.glob(".state-*")))

    def test_prompt_secret_api_key_and_environment_dumps_are_rejected_before_writing(self):
        bad_values = []
        top_prompt = self.value()
        top_prompt["prompt"] = "worker instructions"
        bad_values.append(top_prompt)
        nested_key = self.value()
        nested_key["next_action"]["api_key"] = "not-a-real-key"
        bad_values.append(nested_key)
        environment = self.value()
        environment["env"] = {"TOKEN": "not-a-real-token"}
        bad_values.append(environment)
        request_body = self.value()
        request_body["request_body"] = {"messages": []}
        bad_values.append(request_body)
        secret_value = self.value(next_action={"step": "review", "target": "sk-" + "A" * 24,
                                               "reason_code": "review_ready"})
        bad_values.append(secret_value)
        for bad in bad_values:
            with self.subTest(keys=sorted(bad)):
                with self.assertRaises(checkpoint.CheckpointError):
                    checkpoint.save_checkpoint(self.ctx, self.path, bad)
                self.assertFalse(self.path.exists())

    def test_the_closed_schema_contains_no_prompt_or_secret_payload(self):
        checkpoint.save_checkpoint(self.ctx, self.path, self.value())
        payload = json.loads(self.path.read_text(encoding="utf8"))["payload"]
        self.assertEqual(set(checkpoint._TOP_KEYS), set(payload))
        self.assertNotIn("prompt", json.dumps(payload).casefold())

    def test_run_campaign_and_project_use_the_same_contract(self):
        for kind in sorted(checkpoint.KINDS):
            with self.subTest(kind=kind):
                path = checkpoint.checkpoint_path(self.ctx, kind, f"op-kind-{kind}")
                checkpoint.save_checkpoint(self.ctx, path, self.value(kind=kind))
                state = checkpoint.inspect_checkpoint(self.ctx, path)
                self.assertEqual("RESUMABLE", state["status"], state)
                self.assertEqual(kind, state["checkpoint"]["kind"])

    def test_newer_schema_tamper_broken_json_and_missing_files_are_never_resumed(self):
        newer = self.value()
        newer["schema_version"] = 3
        save_signed(self.ctx, self.path, newer)
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual(("NEEDS_REVIEW", "unsupported_schema"), (state["status"], state["reason"]), state)

        checkpoint.save_checkpoint(self.ctx, self.path, self.value())
        envelope = json.loads(self.path.read_text(encoding="utf8"))
        envelope["payload"]["round"] = 9
        self.path.write_text(json.dumps(envelope), encoding="utf8")
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual(("NEEDS_REVIEW", "signature_invalid"), (state["status"], state["reason"]), state)

        self.path.write_text("{broken", encoding="utf8")
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual(("NEEDS_REVIEW", "checkpoint_unreadable"), (state["status"], state["reason"]), state)

        self.path.unlink()
        state = checkpoint.inspect_checkpoint(self.ctx, self.path)
        self.assertEqual(("NEEDS_REVIEW", "checkpoint_missing"), (state["status"], state["reason"]), state)

    def test_a_path_outside_the_private_data_root_is_refused(self):
        outside = self.root / "outside.json"
        with self.assertRaisesRegex(checkpoint.CheckpointError, "escapes"):
            checkpoint.save_checkpoint(self.ctx, outside, self.value())
        self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
