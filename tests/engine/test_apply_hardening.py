import hashlib
import subprocess
import threading
import unittest
from unittest import mock

from respected_orchestrator.engine import lanes, runner
from respected_orchestrator.engine.evidence import load_signed, save_signed
from respected_orchestrator.engine.runner import apply_task, cancel_task, create_task, execute_task
from tests.workflows.test_reviewer_reliability import CodingFixture

OLD, NEW = "value = 0\n", "value = 1\n"


class ApplyHardeningTests(CodingFixture):
    def executed(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        self.assertEqual(execute_task(self.ctx, run_id)["status"], "completed")
        return run_id

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True).stdout

    def tree_hash(self):
        """Everything a person could notice: HEAD, index, working tree status and file bytes."""
        files = b"".join(p.read_bytes() for p in sorted(self.repo.iterdir()) if p.is_file())
        return hashlib.sha256((self.git("rev-parse", "HEAD") + self.git("status", "--porcelain") + self.git("diff", "--cached")).encode() + files).hexdigest()

    def artifact(self, run_id, name):
        path = self.ctx.run_dir(run_id) / name
        return load_signed(self.ctx, path) if path.is_file() else None

    def swap_patch(self, run_id, text):
        """Replace the worker patch and re-sign the result, as a fully forged-but-signed run would look."""
        directory = self.ctx.run_dir(run_id)
        (directory / "worker.patch").write_text(text, encoding="utf8", newline="\n")
        result = load_signed(self.ctx, directory / "result.json")
        result["patch_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        save_signed(self.ctx, directory / "result.json", result)

    def test_success_is_one_unstaged_uncommitted_change_with_proof_and_a_working_undo(self):
        run_id = self.executed()
        head = self.git("rev-parse", "HEAD")
        out = apply_task(self.ctx, run_id)
        self.assertEqual((out["committed"], out["staged"]), (False, False))
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("diff", "--cached"), "")
        self.assertEqual(self.git("status", "--porcelain").strip(), "M calculator.py")
        marker = self.artifact(run_id, "applied.json")
        self.assertNotEqual(marker["source_fingerprint_before"], marker["source_fingerprint"])
        self.assertIn("git apply --reverse", marker["undo"])
        self.assertIsNone(self.artifact(run_id, "apply-failed.json"))
        subprocess.run(["git", "apply", "--reverse", "--binary", str(self.ctx.run_dir(run_id) / "worker.patch")], cwd=self.repo, check=True)
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), OLD)  # the stated undo really undoes it

    def test_edit_between_check_and_apply_is_refused_even_when_the_patch_would_still_fit(self):
        run_id = self.executed()
        real_git, fired = lanes._git, []

        def raced(project, *args, **kwargs):
            out = real_git(project, *args, **kwargs)
            if args[:2] == ("apply", "--check") and not fired:
                fired.append(1)
                with open(self.repo / "calculator.py", "a", encoding="utf8", newline="") as handle:
                    handle.write("# the person's own edit\n")  # context still matches: git alone would apply on top of it
            return out
        with mock.patch.object(lanes, "_git", side_effect=raced):
            with self.assertRaisesRegex(ValueError, "changed while the patch was being checked"):
                apply_task(self.ctx, run_id)
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), OLD + "# the person's own edit\n")  # theirs, untouched
        self.assertFalse((self.ctx.run_dir(run_id) / "applied.json").exists())
        failed = self.artifact(run_id, "apply-failed.json")
        self.assertIn("changed while", failed["reason"])
        self.assertFalse((self.ctx.run_dir(run_id) / "applying").exists())  # nothing was written, so a retry is possible

    def test_second_click_and_a_crowd_of_clicks_apply_exactly_once(self):
        run_id = self.executed()
        outcomes = []

        def click():
            try:
                outcomes.append(apply_task(self.ctx, run_id)["status"])
            except ValueError as error:
                outcomes.append("refused")
        threads = [threading.Thread(target=click) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(outcomes), ["applied"] + ["refused"] * 7)
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), NEW)
        self.assertEqual(self.git("diff", "--stat").count("calculator.py"), 1)
        with self.assertRaisesRegex(ValueError, "already applied"):
            apply_task(self.ctx, run_id)

    def test_failed_apply_changes_nothing_and_leaves_a_signed_reason(self):
        run_id = self.executed()
        (self.repo / "calculator.py").write_text("value = 99\n", encoding="utf8")
        before = self.tree_hash()
        with self.assertRaisesRegex(ValueError, "stale"):
            apply_task(self.ctx, run_id)
        self.assertEqual(self.tree_hash(), before)
        failed = self.artifact(run_id, "apply-failed.json")
        self.assertIn("stale", failed["reason"])
        self.assertFalse(failed["project_changed"])
        self.assertFalse((self.ctx.run_dir(run_id) / "applied.json").exists())

    def test_forbidden_or_unsafe_patches_are_refused_even_with_a_valid_signature(self):
        cases = {
            "outside ownership": "diff --git a/evil.txt b/evil.txt\nnew file mode 100644\n--- /dev/null\n+++ b/evil.txt\n@@ -0,0 +1 @@\n+x\n",
            "symlink": "diff --git a/calculator.py b/calculator.py\nnew file mode 120000\n--- /dev/null\n+++ b/calculator.py\n@@ -0,0 +1 @@\n+/etc/passwd\n",
            "git dir": "diff --git a/.git/hooks/pre-commit b/.git/hooks/pre-commit\nnew file mode 100755\n--- /dev/null\n+++ b/.git/hooks/pre-commit\n@@ -0,0 +1 @@\n+x\n",
        }
        for name, text in cases.items():
            run_id = self.executed()
            self.swap_patch(run_id, text)
            before = self.tree_hash()
            with self.assertRaises(ValueError, msg=name):
                apply_task(self.ctx, run_id)
            self.assertEqual(self.tree_hash(), before, name)
            self.assertFalse((self.repo / "evil.txt").exists(), name)

    def test_cancelled_run_cannot_be_applied_and_a_late_cancel_does_not_unapply_a_completed_one(self):
        run_id = self.executed()
        self.assertEqual(cancel_task(self.ctx, run_id)["status"], "completed")  # too late: the run is done, cancel is a no-op
        status = load_signed(self.ctx, self.ctx.run_dir(run_id) / "status.json")
        save_signed(self.ctx, self.ctx.run_dir(run_id) / "status.json", {**status, "status": "cancelled"})
        before = self.tree_hash()
        with self.assertRaises(ValueError):
            apply_task(self.ctx, run_id)
        self.assertEqual(self.tree_hash(), before)

    def test_crash_after_the_write_never_allows_a_second_write(self):
        run_id = self.executed()
        real = runner.save_signed

        def crash(ctx, path, payload):
            if path.name == "applied.json":
                raise OSError("disk went away")
            return real(ctx, path, payload)
        with mock.patch.object(runner, "save_signed", side_effect=crash):
            with self.assertRaises(OSError):
                apply_task(self.ctx, run_id)
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), NEW)  # it was written once ...
        with self.assertRaisesRegex(ValueError, "did not finish"):
            apply_task(self.ctx, run_id)  # ... and the claim stops a second apply until a person looks
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), NEW)


if __name__ == "__main__":
    unittest.main()
