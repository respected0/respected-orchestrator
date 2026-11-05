"""FIX-03B / ADR-020: signed, idempotent, commit-bound CI feedback by import or polling (no listener)."""
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.interfaces import github_connector as gh

HEAD = "b" * 40
OP = "op-ci123456"


def ok(text):
    return SimpleNamespace(returncode=0, stdout=text.encode(), stderr=b"")


class CiIngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = EngineContext(Path(self.temp.name).resolve() / "data")
        (self.ctx.data_root / "receipts").mkdir(parents=True)
        save_signed(self.ctx, self.ctx.data_root / "receipts" / f"github-pr-{OP}.json",
                    {"status": "draft", "repo": "o/r", "head_sha": HEAD, "pr_number": 7, "run_id": "run-pr", "patch_sha256": "a" * 64})

    def event(self, **change):
        base = {"repo": "o/r", "head_sha": HEAD, "status": "completed", "conclusion": "failure", "completed_at": "2026-11-05T10:00:00Z",
                "pull_numbers": [7], "ids": ["check_run:1:completed:2026-11-05T10:00:00Z"]}
        return {**base, **change}

    def test_signature_is_exact_and_secret_bound(self):
        body = b'{"a":1}'
        good = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
        self.assertTrue(gh.verify_signature("s3cret", body, good))
        for secret, data, header in (("", body, good), ("other", body, good), ("s3cret", body + b" ", good), ("s3cret", body, good[7:]),
                                     ("s3cret", body, None), ("s3cret", body, "sha1=" + good[7:]), ("s3cret", "text", good)):
            with self.subTest(secret=secret, header=header):
                self.assertFalse(gh.verify_signature(secret, data, header))

    def test_each_conclusion_maps_to_the_right_feedback_and_never_to_a_merge(self):
        got = {}
        for index, conclusion in enumerate(("failure", "timed_out", "success", "cancelled", "neutral")):
            got[conclusion] = gh.ingest_check_run(self.ctx, OP, self.event(
                conclusion=conclusion, completed_at=f"2026-11-05T10:0{index}:00Z", ids=[f"check_run:{index}"]))
        self.assertTrue(all(v["accepted"] for v in got.values()))
        self.assertEqual({k: v["feedback"] and v["feedback"]["conclusion"] for k, v in got.items()},
                         {"failure": "failure", "timed_out": "timed_out", "success": "success", "cancelled": None, "neutral": None})
        self.assertEqual(gh.plan_ci_fix(got["failure"]["feedback"], head_sha=HEAD, max_rounds=2, used_rounds=0)["action"], "fix")
        self.assertEqual(gh.plan_ci_fix(got["success"]["feedback"], head_sha=HEAD, max_rounds=2, used_rounds=0)["reason"], "ci_green_no_merge")

    def test_other_repo_pr_commit_unknown_status_and_missing_id_are_refused(self):
        for change, reason in (({"repo": "x/y"}, "wrong_repository"), ({"head_sha": "c" * 40}, "wrong_commit"), ({"pull_numbers": [9]}, "wrong_pr"),
                               ({"status": "in_progress", "conclusion": None}, "pending"), ({"status": "weird"}, "unknown_status"),
                               ({"conclusion": "exploded"}, "unknown_status"), ({"completed_at": None}, "unknown_status"), ({"ids": []}, "missing_id")):
            with self.subTest(reason=reason):
                got = gh.ingest_check_run(self.ctx, OP, self.event(**change))
                self.assertEqual((got["accepted"], got["reason"], got["feedback"]), (False, reason, None))

    def test_a_repeated_delivery_counts_once_and_an_older_result_never_rolls_back(self):
        self.assertTrue(gh.ingest_check_run(self.ctx, OP, self.event())["accepted"])
        self.assertEqual(gh.ingest_check_run(self.ctx, OP, self.event())["reason"], "duplicate")
        newer = self.event(conclusion="success", completed_at="2026-11-05T11:00:00Z", ids=["check_run:2"])
        self.assertTrue(gh.ingest_check_run(self.ctx, OP, newer)["accepted"])
        late_old = self.event(conclusion="failure", ids=["check_run:3"])  # finished earlier, arrived later
        self.assertEqual(gh.ingest_check_run(self.ctx, OP, late_old)["reason"], "stale_event")

    def test_receipt_must_exist_and_carry_a_verified_commit(self):
        with self.assertRaisesRegex(ValueError, "No draft PR receipt"):
            gh.ingest_check_run(self.ctx, "op-missing123", self.event())
        save_signed(self.ctx, self.ctx.data_root / "receipts" / "github-pr-op-oldreceipt.json", {"status": "draft", "repo": "o/r"})
        with self.assertRaisesRegex(ValueError, "no verified head"):
            gh.ingest_check_run(self.ctx, "op-oldreceipt", self.event())

    def webhook(self, secret="s3cret", headers=None, body=None):
        body = body if body is not None else json.dumps({
            "repository": {"full_name": "o/r"},
            "check_run": {"id": 5, "head_sha": HEAD, "status": "completed", "conclusion": "failure",
                          "completed_at": "2026-11-05T10:00:00Z", "pull_requests": [{"number": 7}]}}).encode()
        head = {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
                "X-GitHub-Event": "check_run", "X-GitHub-Delivery": "d-1"}
        head.update(headers or {})
        return gh.ingest_webhook(self.ctx, OP, secret="s3cret", body=body, headers=head)

    def test_webhook_import_accepts_a_signed_event_once_and_rejects_forgery_and_garbage(self):
        self.assertEqual(self.webhook()["feedback"]["conclusion"], "failure")
        self.assertEqual(self.webhook()["reason"], "duplicate")
        with self.assertRaisesRegex(ValueError, "bad_signature"):
            self.webhook(secret="wrong")
        with self.assertRaisesRegex(ValueError, "bad_signature"):
            self.webhook(headers={"X-Hub-Signature-256": "sha256=" + "0" * 64})
        with self.assertRaisesRegex(ValueError, "bad_json"):
            self.webhook(body=b"not json")
        with self.assertRaisesRegex(ValueError, "too large"):
            self.webhook(body=b"x" * (gh.MAX_WEBHOOK_BYTES + 1))
        self.assertEqual(self.webhook(headers={"X-GitHub-Event": "push"})["reason"], "ignored_event")

    def test_rpp_ingest_takes_the_secret_from_the_environment_never_the_payload(self):
        from unittest import mock
        from respected_orchestrator.interfaces import rpp
        body = json.dumps({"repository": {"full_name": "o/r"}, "check_run": {
            "id": 9, "head_sha": HEAD, "status": "completed", "conclusion": "success", "completed_at": "2026-11-05T10:00:00Z"}})
        signature = "sha256=" + hmac.new(b"env-secret", body.encode(), hashlib.sha256).hexdigest()
        payload = {"operation_id": OP, "body": body, "secret": "payload-secret",
                   "headers": {"X-Hub-Signature-256": signature, "X-GitHub-Event": "check_run"}}
        ask = lambda: rpp.handle_request({"rpp": rpp.RPP, "op": "github.ci_ingest", "payload": payload}, self.ctx)
        with mock.patch.dict("os.environ", {"RESPECTED_GITHUB_WEBHOOK_SECRET": "env-secret"}):
            self.assertEqual(ask()["result"]["reason"], "success")
        with mock.patch.dict("os.environ", {"RESPECTED_GITHUB_WEBHOOK_SECRET": ""}):
            refused = ask()
        self.assertEqual((refused["ok"], refused["error"]["code"]), (False, "GITHUB_ERROR"))

    def test_poll_reads_check_runs_for_the_verified_commit_and_stays_read_only(self):
        seen = []
        runs = {"check_runs": [{"id": 11, "head_sha": HEAD, "status": "completed", "conclusion": "success",
                                "completed_at": "2026-11-05T10:00:00Z", "pull_requests": [{"number": 7}]},
                               {"id": 12, "head_sha": HEAD, "status": "in_progress", "conclusion": None, "completed_at": None}]}
        got = gh.poll_checks(self.ctx, OP, run=lambda args, **k: (seen.append(args), ok(json.dumps(runs)))[1])
        self.assertEqual([r["reason"] for r in got["results"]], ["success", "pending"])
        self.assertEqual(seen, [["gh", "api", f"repos/o/r/commits/{HEAD}/check-runs"]])
        with self.assertRaisesRegex(ValueError, "HTTP 403"):
            gh.poll_checks(self.ctx, OP, run=lambda *a, **k: SimpleNamespace(returncode=1, stdout=b"", stderr=b"HTTP 403 rate limit"))


if __name__ == "__main__":
    unittest.main()
