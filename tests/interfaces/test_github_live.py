"""FIX-03A/B live proof against a real throwaway test repository (opt-in; skipped, never green, otherwise).

Set RESPECTED_LIVE_GITHUB_REPO=owner/name and RESPECTED_LIVE_GITHUB_CLONE=<local clone of it, `origin` = that repo>.
Run with RESPECTED_TEST_SANDBOX=1 so the suite keeps the real HOME (gh needs its own login).
The signed run is a fixture (the real worker is not the subject here); `check_result` is patched, everything else
(git push, `gh pr create --draft`, read-back, check-run polling) is real. No merge is ever issued; the PR is closed after.
"""
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine.evidence import save_signed
from respected_orchestrator.interfaces import github_connector as gh

REPO = os.environ.get("RESPECTED_LIVE_GITHUB_REPO")
CLONE = os.environ.get("RESPECTED_LIVE_GITHUB_CLONE")


def git(*args):
    return subprocess.run(["git", *args], cwd=CLONE, capture_output=True, text=True, check=True).stdout.strip()


@unittest.skipUnless(REPO and CLONE, "live GitHub test: set RESPECTED_LIVE_GITHUB_REPO and RESPECTED_LIVE_GITHUB_CLONE")
class LiveGithubTests(unittest.TestCase):
    def test_draft_pr_and_check_run_round_trip(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        ctx = EngineContext(Path(temp.name).resolve() / "data")
        directory = ctx.run_dir("run-live")
        directory.mkdir(parents=True)
        (directory / "worker.patch").write_text("+live = 1\n", encoding="utf8")
        for name, body in (("request.json", {}), ("status.json", {"status": "completed"}),
                           ("result.json", {"status": "completed", "patch_sha256": "a" * 64})):
            save_signed(ctx, directory / name, {"run_id": "run-live", **body})
        branch = f"orch-live-{int(time.time())}"
        git("checkout", "-q", "-B", branch, "origin/main")
        (Path(CLONE) / "live.txt").write_text(branch, encoding="utf8")
        git("add", "live.txt")
        git("commit", "-q", "-m", "live test commit")
        head_sha = gh.local_head(CLONE, branch)
        operation = f"op-{branch[-10:]}"
        self.addCleanup(lambda: subprocess.run(["git", "push", "origin", "--delete", branch], cwd=CLONE, capture_output=True))
        with mock.patch.object(gh.runner, "check_result", return_value={"status": "verified"}):
            # negative: a revoked/invalid token and a missing branch fail structurally, with no push and no receipt
            bad = lambda args, **k: subprocess.run(args, env={**os.environ, "GH_TOKEN": "ghp_invalid"}, **k)
            with self.assertRaises(ValueError):
                gh.create_draft_pr(ctx, "run-live", repo=REPO, head=branch, base="main", title="t", body="b", operation_id=operation,
                                   push=lambda head: gh.push_branch(CLONE, head), head_sha=head_sha, run=bad)
            self.assertFalse((ctx.data_root / "receipts" / f"github-pr-{operation}.json").exists())
            with self.assertRaisesRegex(ValueError, "does not exist"):
                gh.local_head(CLONE, "no-such-branch-xyz")
            made = gh.create_draft_pr(ctx, "run-live", repo=REPO, head=branch, base="main", title="live draft", body="live test",
                                      operation_id=operation, push=lambda head: gh.push_branch(CLONE, head), head_sha=head_sha)
            self.addCleanup(lambda: subprocess.run(["gh", "pr", "close", str(made["pr_number"]), "--repo", REPO], capture_output=True))
            self.assertEqual((made["status"], made["head_sha"]), ("draft", head_sha))
            view = json.loads(subprocess.run(["gh", "pr", "view", str(made["pr_number"]), "--repo", REPO, "--json", "isDraft,state,mergedAt"],
                                             capture_output=True, text=True, check=True).stdout)
            self.assertEqual((view["isDraft"], view["state"], view["mergedAt"]), (True, "OPEN", None))
            self.assertEqual(gh.create_draft_pr(ctx, "run-live", repo=REPO, head=branch, base="main", title="x", body="x",
                                                operation_id=operation, push=lambda head: self.fail("pushed twice"), head_sha=head_sha), made)
        seen = []
        for _ in range(18):  # the hosted check-run appears a few seconds after the push
            polled = gh.poll_checks(ctx, operation)
            seen += polled["results"]
            if any(r["accepted"] for r in seen):
                break
            time.sleep(10)
        print(json.dumps({"head_sha": polled["head_sha"], "results": seen}, indent=1)[:1500])
        self.assertEqual(polled["head_sha"], head_sha)
        self.assertTrue(any(r["accepted"] for r in seen), "no check-run accepted for the PR head commit")
        self.assertEqual(gh.poll_checks(ctx, operation)["results"][0]["reason"], "duplicate")  # idempotent re-poll
