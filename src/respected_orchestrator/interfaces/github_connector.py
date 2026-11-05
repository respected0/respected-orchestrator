"""GitHub delivery boundary: read-only issue import, verified draft PRs, bounded CI feedback.

The connector never merges, never starts a worker from issue text, and every write takes an explicit operation id.
"""
import hashlib
import hmac
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
_SHA = re.compile(r"[0-9a-f]{40}\Z")
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


def local_head(project_root, head, run=None):
    """Commit the operator's branch points at; the draft PR must carry exactly this commit (FIX-03A)."""
    if not _BRANCH.fullmatch(head):
        raise ValueError("Invalid branch")
    completed = (run or winproc.run)(["git", "rev-parse", "--verify", f"refs/heads/{head}"], cwd=str(project_root),
                                     capture_output=True, check=False, timeout=30)
    sha = (completed.stdout or b"").decode("utf-8", "replace").strip()
    if completed.returncode != 0 or not _SHA.fullmatch(sha):
        raise ValueError(f"Branch {head} does not exist in the project")
    return sha


def create_draft_pr(ctx, run_id, *, repo, head, base, title, body, operation_id, push, head_sha, run=None):
    """Push an operator-supplied branch and open a draft PR only for a re-verified signed result.

    After creation the PR is read back: it must be an open draft whose head commit is `head_sha` (what was verified and pushed).
    """
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
    seen = json.loads(_run(["pr", "view", match.group(0), "--json", "headRefOid,isDraft,state,number"], run))
    if seen.get("isDraft") is not True or seen.get("state") != "OPEN" or seen.get("headRefOid") != head_sha:
        raise ValueError(f"Draft PR does not match the verified commit: {match.group(0)}")
    payload = {"status": "draft", "run_id": run_id, "patch_sha256": sha, "repo": repo, "head": head, "base": base,
               "url": match.group(0), "pr_number": seen["number"], "head_sha": head_sha, "verified": verified["status"]}
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


# --- CI feedback (ADR-020): polling is primary; the signature check and the file/stdin import never open a listener ---

MAX_WEBHOOK_BYTES = 1_000_000
_DONE = {"success", "failure", "cancelled", "timed_out", "neutral", "skipped", "action_required", "stale"}
_FIXABLE = {"success", "failure", "timed_out"}  # cancelled/neutral/skipped/stale/action_required never start a fix round


def verify_signature(secret, body, header):
    """X-Hub-Signature-256: `sha256=<hex>` over the exact body. Empty secret or any other shape is a refusal."""
    if not secret or not isinstance(body, bytes) or not isinstance(header, str) or not header.startswith("sha256="):
        return False
    return hmac.compare_digest("sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest(), header)


def _receipt(ctx, operation_id):
    if not isinstance(operation_id, str) or not _OPERATION.fullmatch(operation_id):
        raise ValueError("operation_id must be 8-64 characters of [A-Za-z0-9_-]")
    path = safe_path(ctx.data_root / "receipts" / f"github-pr-{operation_id}.json")
    if not path.is_file():
        raise ValueError("No draft PR receipt for this operation_id")
    receipt = load_signed(ctx, path)
    if not receipt.get("head_sha") or not receipt.get("pr_number"):
        raise ValueError("Draft PR receipt has no verified head commit")
    return receipt


def _refused(reason):
    return {"accepted": False, "reason": reason, "feedback": None}


def ingest_check_run(ctx, operation_id, event):
    """One check-run result -> {accepted, reason, feedback}. feedback feeds plan_ci_fix; nothing here fixes, comments or merges.

    Refused (fail closed): other repository/PR/commit, unknown status, already processed id, older than the latest result.
    """
    receipt = _receipt(ctx, operation_id)
    if not isinstance(event, dict):
        raise ValueError("CI event must be an object")
    if event.get("repo") != receipt["repo"]:
        return _refused("wrong_repository")
    if event.get("head_sha") != receipt["head_sha"]:
        return _refused("wrong_commit")
    if event.get("pull_numbers") and receipt["pr_number"] not in event["pull_numbers"]:
        return _refused("wrong_pr")
    if event.get("status") in ("queued", "in_progress"):
        return _refused("pending")
    conclusion, completed_at = event.get("conclusion"), event.get("completed_at")
    if event.get("status") != "completed" or conclusion not in _DONE or not isinstance(completed_at, str) or not completed_at:
        return _refused("unknown_status")
    ids = [str(i) for i in event.get("ids", []) if i]
    if not ids:
        return _refused("missing_id")
    state_path = safe_path(ctx.data_root / "receipts" / f"github-ci-{operation_id}.json")
    state = load_signed(ctx, state_path) if state_path.is_file() else {"seen": [], "latest": ""}
    if any(i in state["seen"] for i in ids):
        return _refused("duplicate")
    if completed_at < state["latest"]:  # ISO-8601 UTC sorts as text; an older result never rolls the state back
        return _refused("stale_event")
    save_signed(ctx, state_path, {"seen": [*state["seen"], *ids][-500:], "latest": completed_at, "conclusion": conclusion})
    feedback = {"sha": receipt["head_sha"], "conclusion": conclusion} if conclusion in _FIXABLE else None
    return {"accepted": True, "reason": conclusion, "feedback": feedback}


def ingest_webhook(ctx, operation_id, *, secret, body, headers):
    """Import a webhook payload that arrived by file/stdin: size cap, signature, event type, delivery id, then the shared checks."""
    body = body.encode("utf-8") if isinstance(body, str) else body
    if not isinstance(body, bytes) or len(body) > MAX_WEBHOOK_BYTES:
        raise ValueError("Webhook body missing or too large")
    headers = {str(k).casefold(): v for k, v in (headers or {}).items()}
    if not verify_signature(secret, body, headers.get("x-hub-signature-256")):
        raise ValueError("bad_signature")
    if headers.get("x-github-event") != "check_run":
        return _refused("ignored_event")
    try:
        payload = json.loads(body)
        run = payload["check_run"]
        delivery = headers.get("x-github-delivery")
        event = {"repo": payload["repository"]["full_name"], "head_sha": run["head_sha"], "status": run["status"],
                 "conclusion": run.get("conclusion"), "completed_at": run.get("completed_at"),
                 "pull_numbers": [p["number"] for p in run.get("pull_requests") or []],
                 "ids": [f"delivery:{delivery}" if delivery else None, f"check_run:{run['id']}:{run['status']}:{run.get('completed_at')}"]}
    except (ValueError, KeyError, TypeError):
        raise ValueError("bad_json") from None
    return ingest_check_run(ctx, operation_id, event)


def poll_checks(ctx, operation_id, run=None):
    """Ask GitHub (the operator's own `gh` session) for the check runs of the receipt's head commit and ingest each one."""
    receipt = _receipt(ctx, operation_id)
    data = json.loads(_run(["api", f"repos/{receipt['repo']}/commits/{receipt['head_sha']}/check-runs"], run))
    results = [ingest_check_run(ctx, operation_id, {
        "repo": receipt["repo"], "head_sha": item.get("head_sha"), "status": item.get("status"), "conclusion": item.get("conclusion"),
        "completed_at": item.get("completed_at"), "pull_numbers": [p.get("number") for p in item.get("pull_requests") or []],
        "ids": [f"check_run:{item.get('id')}:{item.get('status')}:{item.get('completed_at')}"]}) for item in data.get("check_runs") or []]
    return {"operation_id": operation_id, "head_sha": receipt["head_sha"], "results": results}
