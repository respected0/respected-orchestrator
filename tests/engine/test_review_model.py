import json
import subprocess
import unittest

from respected_orchestrator.engine import review_model
from respected_orchestrator.engine.authority import Origin
from respected_orchestrator.engine.evidence import save_signed, load_signed
from respected_orchestrator.engine.local_api import LocalApi
from respected_orchestrator.engine.runner import create_task, execute_task
from tests.workflows.test_reviewer_reliability import CodingFixture

SYMLINK = "diff --git a/calculator.py b/calculator.py\nnew file mode 120000\n--- /dev/null\n+++ b/calculator.py\n@@ -0,0 +1 @@\n+/etc/passwd\n"


class ReviewModelTests(CodingFixture):
    def executed(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        self.assertEqual(execute_task(self.ctx, run_id)["status"], "completed")
        return run_id

    def kinds(self, dto, key="blockers"):
        return [f["kind"] for f in dto[key]]

    def test_verified_run_is_approvable_and_shows_the_facts_a_person_needs(self):
        dto = review_model.review_dto(self.ctx, self.executed())
        self.assertTrue(dto["approvable"], dto["blockers"])
        self.assertEqual(dto["blockers"], [])
        self.assertEqual(dto["patch"]["sha256"], dto["patch"]["recorded_sha256"])
        self.assertEqual([f["path"] for f in dto["patch"]["files"]], ["calculator.py"])
        self.assertEqual(dto["patch"]["files"][0]["added"], 1)
        self.assertEqual(dto["fingerprints"]["project_at_run"], dto["fingerprints"]["project_now"])
        self.assertIn("+value = 1", dto["diff"]["preview"])
        self.assertTrue(dto["checked_at"])  # visible verification timestamp
        self.assertIn("no_pr", self.kinds(dto, "warnings"))  # unknown PR/CI is a warning, never shown as passing
        self.assertTrue(dto["evidence"]["checks"] and dto["evidence"]["reviewer"] is not False)

    def test_review_is_read_only(self):
        run_id = self.executed()
        before = sorted(str(p) for p in self.ctx.run_dir(run_id).iterdir())
        review_model.review_dto(self.ctx, run_id)
        self.assertEqual(before, sorted(str(p) for p in self.ctx.run_dir(run_id).iterdir()))
        self.assertEqual((self.repo / "calculator.py").read_text(encoding="utf8"), "value = 0\n")

    def test_tampered_signature_is_not_approvable(self):
        run_id = self.executed()
        path = self.ctx.run_dir(run_id) / "result.json"
        envelope = json.loads(path.read_text(encoding="utf8"))
        envelope["payload"]["changed_files"] = ["other.txt"]
        path.write_text(json.dumps(envelope), encoding="utf8")
        dto = review_model.review_dto(self.ctx, run_id)
        self.assertFalse(dto["approvable"])
        self.assertIn("evidence_unreadable", self.kinds(dto))

    def test_patch_swapped_after_signing_is_not_approvable(self):
        run_id = self.executed()
        (self.ctx.run_dir(run_id) / "worker.patch").write_text(SYMLINK, encoding="utf8")
        dto = review_model.review_dto(self.ctx, run_id)
        self.assertFalse(dto["approvable"])
        self.assertIn("patch_hash_mismatch", self.kinds(dto))
        self.assertIn("symlink", self.kinds(dto))

    def test_stale_project_head_is_not_approvable(self):
        run_id = self.executed()
        (self.repo / "unrelated.txt").write_text("moved\n", encoding="utf8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "moved"], cwd=self.repo, check=True, capture_output=True)
        dto = review_model.review_dto(self.ctx, run_id)
        self.assertFalse(dto["approvable"])
        self.assertIn("check_failed", self.kinds(dto))
        self.assertNotEqual(dto["fingerprints"]["project_at_run"], dto["fingerprints"]["project_now"])

    def test_applied_run_cannot_be_approved_again(self):
        run_id = self.executed()
        save_signed(self.ctx, self.ctx.run_dir(run_id) / "applied.json", {"run_id": run_id})
        self.assertIn("already_applied", self.kinds(review_model.review_dto(self.ctx, run_id)))

    def test_huge_patch_is_flagged_and_preview_is_bounded(self):
        run_id = self.executed()
        (self.ctx.run_dir(run_id) / "worker.patch").write_bytes(b"+" + b"x" * (review_model.MAX_REVIEW_BYTES + 10))
        dto = review_model.review_dto(self.ctx, run_id)
        self.assertIn("diff_too_large", self.kinds(dto))
        self.assertTrue(dto["diff"]["truncated"])
        self.assertLessEqual(len(dto["diff"]["preview"]), review_model.PREVIEW_BYTES)

    def test_secret_in_diff_is_hidden_and_warned(self):
        run_id = self.executed()
        (self.ctx.run_dir(run_id) / "worker.patch").write_text("diff --git a/calculator.py b/calculator.py\n+api_key = sk-live-1234567890abcdef\n", encoding="utf8")
        dto = review_model.review_dto(self.ctx, run_id)
        self.assertNotIn("sk-live-1234567890abcdef", json.dumps(dto))
        self.assertIn("secret_redacted", self.kinds(dto, "warnings"))

    def test_tampered_ci_receipt_blocks_and_failed_ci_blocks(self):
        run_id = self.executed()
        receipts = self.ctx.data_root / "receipts"
        receipts.mkdir(parents=True)
        (receipts / "github-pr-1.json").write_text("{not signed", encoding="utf8")
        dto = review_model.review_dto(self.ctx, run_id)
        self.assertIn("delivery_tampered", self.kinds(dto))
        (receipts / "github-pr-1.json").unlink()
        save_signed(self.ctx, receipts / "github-pr-1.json", {"run_id": run_id, "url": "u", "pr_number": 1, "head_sha": "a"})
        self.assertIn("ci_missing", self.kinds(review_model.review_dto(self.ctx, run_id), "warnings"))
        save_signed(self.ctx, receipts / "github-ci-1.json", {"conclusion": "failure", "latest": "t"})
        dto = review_model.review_dto(self.ctx, run_id)
        self.assertIn("ci_not_green", self.kinds(dto))
        self.assertFalse(dto["approvable"])

    def test_missing_or_unknown_run_is_a_blocker_not_a_crash(self):
        dto = review_model.review_dto(self.ctx, "run-20260101000000-aaaaaaaaaaaa")
        self.assertFalse(dto["approvable"])
        self.assertEqual(self.kinds(dto), ["evidence_unreadable"])


class ParsePatchTests(unittest.TestCase):
    def test_scope_symlink_binary_and_escape_are_named(self):
        text = ("diff --git a/ok.py b/ok.py\n+a\n-b\n"
                "diff --git a/../evil b/../evil\n+x\n"
                "diff --git a/.git/hooks/pre-commit b/.git/hooks/pre-commit\n+x\n"
                "diff --git a/C:/win b/C:/win\n+x\n"
                "diff --git a/vendor/x b/vendor/x\n+x\n"
                "diff --git a/other.py b/other.py\n+x\n"
                "diff --git a/img.png b/img.png\nGIT binary patch\nliteral 3\n"
                "diff --git a/ok.py b/ok.py\nold mode 100644\nnew mode 100755\n")
        files = review_model.parse_patch(text, ownership=["ok.py", "img.png", "../evil", ".git", "C:/win", "vendor"], forbidden=["vendor"])
        got = [(f["path"], f["problem"]) for f in files]
        self.assertEqual(got[0], ("ok.py", None))
        self.assertEqual(got[1], ("../evil", "outside_project"))
        self.assertEqual(got[2][1], "outside_project")
        self.assertEqual(got[3][1], "outside_project")
        self.assertEqual(got[4], ("vendor/x", "forbidden"))
        self.assertEqual(got[5], ("other.py", "outside_ownership"))
        self.assertTrue(files[6]["binary"])
        self.assertTrue(files[7]["mode_change"])
        self.assertEqual((files[0]["added"], files[0]["removed"]), (1, 1))

    def test_garbage_does_not_crash(self):
        for text in ("", "\x00\x01", "+++ only\n--- only\n", "diff --git broken\n"):
            self.assertEqual(review_model.parse_patch(text), [])


class ReviewIpcTests(CodingFixture):
    def call(self, origin, run_id, n=1):
        api = LocalApi(self.ctx, "t" * 32, origin=origin)
        return api.handle({"ipc": "1", "id": f"rev-{n:05d}", "session": "t" * 32, "cmd": "review.view", "payload": {"run_id": run_id}})

    def test_every_origin_may_read_and_bad_ids_are_refused(self):
        run_id = create_task(self.ctx, self.request())["run_id"]
        execute_task(self.ctx, run_id)
        for origin in (Origin.RENDERER, Origin.MCP, Origin.HUMAN):
            r = self.call(origin, run_id)
            self.assertTrue(r["ok"] and r["result"]["approvable"], r)
        for bad in ("../x", "", 5, None):
            self.assertEqual(self.call(Origin.RENDERER, bad, 2)["error"]["code"], "BAD_REQUEST")


if __name__ == "__main__":
    unittest.main()
