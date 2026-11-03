"""GitHub delivery boundary: read-only issue import, verified draft PRs, bounded CI feedback.

The connector never merges, never starts a worker from issue text, and every write takes an explicit operation id.
"""
import json
import re
from pathlib import Path

from ..context import atomic_write_json, safe_path
from ..engine import winproc
from ..engine.evidence import load_signed, save_signed
from ..engine import runner

_ISSUE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_BRANCH = re.compile(r"[A-Za-z0-9._/-]{1,200}\Z")
_OPERATION = re.compile(r"[A-Za-z0-9_-]{8,64}\Z")
MAX_BODY = 100_000
_SECRET_DIFF = re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----")


def _run(args, run=None):
    completed = (run or winproc.run)(["gh", *args], capture_output=True, check=False, timeout=60)
    if completed.returncode != 0:
        raise ValueError((completed.stderr or b"").decode("utf-8", "replace").strip()[:300] or "gh failed")
    return completed.stdout.decode("utf-8", "replace")


def import_issue(repo, number, allowed_labels=(), run=None):
    """Read one issue as untrusted planning input; labels outside the allow-list are dropped."""
    if not isinstance(repo, str) or not _ISSUE.fullmatch(repo):
        raise ValueError("GitHub repository must be owner/name")
    if type(number) is not int or number < 1:
        raise ValueError("Issue number must be a positive integer")
    data = json.loads(_run(["issue", "view", str(number), "--repo", repo,
                            "--json", "number,title,body,labels,url,updatedAt"], run))
    if not isinstance(data, dict) or data.get("number") != number:
        raise ValueError("Unexpected GitHub issue response")
    allowed = {str(label).casefold() for label in allowed_labels}
    labels = [str(item.get("name", "")) for item in data.get("labels") or []
              if isinstance(item, dict) and str(item.get("name", "")).casefold() in allowed]
    return {"source": {"provider": "github", "repo": repo, "issue": number,
                       "revision": data.get("updatedAt"), "url": data.get("url")},
            "task": {"title": str(data.get("title", ""))[:300],
                     "body": str(data.get("body") or "")[:MAX_BODY], "labels": labels},
            "untrusted": True}


def plan_draft_pr(ctx, run_id, *, repo, head, base):
    """Read-only plan: verify the result and return exactly what a later, separately approved PR would publish."""
    if not _ISSUE.fullmatch(repo) or not _BRANCH.fullmatch(head) or not _BRANCH.fullmatch(base):
        raise ValueError("Invalid repository or branch")
    verified = runner.check_result(ctx, run_id)
    patch = safe_path(ctx.run_dir(run_id) / "worker.patch")
    if _SECRET_DIFF.search(patch.read_text("utf-8", "replace")):
        raise ValueError("Patch appears to contain a secret; refusing to publish")
    sha = load_signed(ctx, ctx.run_dir(run_id) / "result.json")["patch_sha256"]
    return {"status": "planned", "run_id": run_id, "patch_sha256": sha, "repo": repo,
            "head": head, "base": base, "verified": verified["status"], "writes": 0}


def push_branch(project_root, head, run=None):
    """Push one explicit branch from the operator's project; never force and never touch another branch."""
    if not _BRANCH.fullmatch(head):
        raise ValueError("Invalid branch")
    completed = (run or winproc.run)(["git", "push", "origin", head], cwd=str(project_root),
                                     capture_output=True, check=False, timeout=120)
    if completed.returncode != 0:
        raise ValueError((completed.stderr or b"").decode("utf-8", "replace").strip()[:300] or "git push failed")


def create_draft_pr(ctx, run_id, *, repo, head, base, title, body, operation_id, push, run=None):
    """Push an operator-supplied branch and open a draft PR only for a re-verified signed result."""
    if not isinstance(operation_id, str) or not _OPERATION.fullmatch(operation_id):
        raise ValueError("operation_id must be 8-64 characters of [A-Za-z0-9_-]")
    if not _ISSUE.fullmatch(repo) or not _BRANCH.fullmatch(head) or not _BRANCH.fullmatch(base):
        raise ValueError("Invalid repository or branch")
    plan = plan_draft_pr(ctx, run_id, repo=repo, head=head, base=base)
    verified, sha = {"status": plan["verified"]}, plan["patch_sha256"]
    receipt = safe_path(ctx.data_root / "receipts" / f"github-pr-{operation_id}.json")
    if receipt.is_file():
        prior = load_signed(ctx, receipt)
        if prior.get("patch_sha256") != sha or prior.get("run_id") != run_id:
            raise ValueError("operation_id was already used for different evidence")
        return prior
    push(head)
    output = _run(["pr", "create", "--draft", "--repo", repo, "--head", head, "--base", base,
                   "--title", title[:300], "--body", body[:MAX_BODY]], run)
    match = re.search(r"https://github\.com/\S+/pull/\d+", output)
    if not match:
        raise ValueError("Could not read the draft PR URL")
    payload = {"status": "draft", "run_id": run_id, "patch_sha256": sha, "repo": repo,
               "head": head, "base": base, "url": match.group(0), "verified": verified["status"]}
    save_signed(ctx, receipt, payload)
    return payload


def plan_ci_fix(feedback, *, head_sha, max_rounds, used_rounds, authorized=True, approval=True):
    """Read-only CI/review feedback -> at most one bounded fix round, never a merge."""
    if not isinstance(feedback, dict):
        raise ValueError("CI feedback must be an object")
    if feedback.get("sha") != head_sha:
        return {"action": "none", "reason": "old_revision"}
    if feedback.get("conclusion") in ("success", "SUCCESS"):
        return {"action": "none", "reason": "ci_green_no_merge"}
    if not authorized:
        return {"action": "none", "reason": "unauthorized_reviewer"}
    if not approval:
        return {"action": "none", "reason": "approval_revoked"}
    if feedback.get("flaky"):
        return {"action": "none", "reason": "flaky_test"}
    if used_rounds >= max_rounds:
        return {"action": "none", "reason": "round_budget_exhausted"}
    return {"action": "fix", "reason": "bounded_ci_fix", "round": used_rounds + 1}