"""Durable autonomous projects: dependent phases of campaigns with preauthorized apply, verification and continuation.

Claude plans the project once (a JSON spec). A detached supervisor then runs each eligible phase as a campaign
(fresh engine snapshot + fresh source mirror every time), applies only fully approved lanes through the engine's own
verified `apply_task`, runs deterministic verify commands on the real source and moves on. State is signed JSON on disk,
so the supervisor can be killed or the machine restarted and `project-resume` continues without duplicating work.
"""
import datetime as dt
import getpass
import hashlib
import os
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

from .. import __version__
from ..engine import lanes, sandbox
from ..engine.budget import MAX_BUDGET, UNKNOWN_STEP_TOKENS_DEFAULT
from . import campaign, checkpoint, roles
from ..context import EngineContext, engine_command, path_within_root, safe_path
from ..engine.processes import ProcessStopped, execute
from ..engine.runner import _command, apply_task, source_fingerprint
from ..engine.evidence import load_signed, save_signed
from ..engine.runner import project_fingerprint as runner_fingerprint
from ..engine.evidence import key_path

_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_MAX_PHASES, _MAX_SECONDS, _MAX_ATTEMPTS = 12, 7 * 86400, 3
_TERMINAL = {"completed", "cancelled", "blocked"}
_RESUME_STEPS = frozenset({"resume", "campaign", "apply", "verify", "review", "complete"})
_RESUME_APPROVAL = "resume-approval.json"
_APPROVAL_KEYS = frozenset({
    "project_id", "operation_id", "checkpoint_sha256", "checkpoint_status", "reason", "source_fingerprint",
    "repo_commit", "approved_by", "approved_at",
})


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def project_dir(ctx, project_id):
    if not re.fullmatch(r"proj-[a-z0-9-]{1,60}", str(project_id)):
        raise ValueError("Invalid project identity")
    return safe_path(ctx.data_root / "projects" / project_id)


def _project_roots(state):
    """Every unique source root in a stable order (checkpoint digests and approvals bind all of them)."""
    roots = set()
    for phase in state["spec"]["phases"]:
        for lane in phase["workstreams"]:
            raw = (lane.get("request") or {}).get("project_root")
            if not isinstance(raw, str) or not raw:
                raise ValueError("Project lane has no project_root")
            roots.add(str(safe_path(Path(raw))))
    if not roots:
        raise ValueError("Project has no source roots")
    return sorted(roots)


def _source_snapshot(state):
    """Aggregate + per-root source identities used by the project checkpoint and resume approval."""
    per_root = {root: source_fingerprint(Path(root)) for root in _project_roots(state)}
    digest = hashlib.sha256(b"RESPECTED-PROJECT-SOURCES-V1\0")
    for root, fingerprint in per_root.items():
        name = root.encode("utf8")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(bytes.fromhex(fingerprint))
    return digest.hexdigest(), per_root


def _checkpoint_checks(per_root):
    if 1 + len(per_root) > 64:
        raise ValueError("Too many project source roots for a safe checkpoint")
    checks = {"source-fingerprint": _source_snapshot_digest(per_root)}
    for index, (root, fingerprint) in enumerate(per_root.items()):
        checks[f"source-{index:03d}"] = fingerprint
    return checks


def _source_snapshot_digest(per_root):
    digest = hashlib.sha256(b"RESPECTED-PROJECT-SOURCES-V1\0")
    for root, fingerprint in per_root.items():
        name = root.encode("utf8")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(bytes.fromhex(fingerprint))
    return digest.hexdigest()


def _checkpoint_limits(state):
    budget = state["spec"]["budget"]
    return dict(max_rounds=budget["max_phase_attempts"], deadline_epoch=int(state["deadline_epoch"]),
                max_weighted_tokens=budget["max_weighted_tokens"], max_seconds=budget["max_seconds"])


def _round_number(state):
    total = 0
    for record in state["phases"].values():
        total += len(record.get("attempts") or [])
        total += sum(len(attempt.get("stages") or []) for attempt in record.get("attempts") or [])
    return min(total, 1_000_000)


def _resume_action(ctx, state):
    """The next re-executable boundary. This is advisory state; every boundary is idempotent on disk."""
    if state.get("status") == "completed":
        return "complete", None
    for phase in state["spec"]["phases"]:
        record = state["phases"][phase["name"]]
        if record["status"] == "done":
            continue
        attempts = record.get("attempts") or []
        target = phase["name"]
        if not attempts or attempts[-1].get("outcome"):
            return "campaign", target
        attempt = attempts[-1]
        stages = attempt.get("stages") or []
        if not stages:
            return "campaign", target
        stage = stages[-1]
        if not stage.get("campaign_id"):
            return "campaign", target
        result = campaign.campaign_dir(ctx, stage["campaign_id"]) / "result.json"
        if result is None or not result.is_file():
            return "campaign", target
        if "weighted_tokens" not in stage:
            return "apply", target
        applied = record.get("applied_lanes") or {}
        if any(name not in applied for name in stage.get("lanes") or []):
            return "apply", target
        if len(stages) > int(attempt.get("stage_index") or 0):
            return "campaign", target
        remaining = [lane["name"] for lane in phase["workstreams"] if lane["name"] not in applied]
        if remaining:
            return "campaign", target
        return "verify", target
    return "review" if state["spec"].get("final_review") else "complete", None


def _write_checkpoint(ctx, state, step=None, target=None, snapshot=None):
    """Atomically persist the current FSM boundary and source identity (never a worker prompt)."""
    if step is None:
        step, target = _resume_action(ctx, state)
    if step not in _RESUME_STEPS:
        raise ValueError("Unknown project resume step")
    aggregate, per_root = snapshot or _source_snapshot(state)
    roots = _project_roots(state)
    document = checkpoint.create_checkpoint(
        "project", state["project_id"], roots[0], role="master", round_number=_round_number(state),
        next_action={"step": step, "target": target, "reason_code": "fsm_boundary"},
        checks=_checkpoint_checks(per_root), limits=_checkpoint_limits(state))
    if document["checks"]["source-fingerprint"] != aggregate:
        raise ValueError("Project source snapshot is inconsistent")
    checkpoint.save_checkpoint(ctx, checkpoint.checkpoint_path(ctx, "project", state["project_id"]), document)
    return document


def _raw_sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _own_apply_matches(ctx, state, root, current):
    """True when this supervisor's signed applied marker explains the current root state.

    This is the crash window after `apply_task` wrote `applied.json` but before the project checkpoint/state recorded it.
    Anything else is external drift and needs a human.
    """
    root_by_lane = {}
    for phase in state["spec"]["phases"]:
        for lane in phase["workstreams"]:
            root_by_lane[lane["name"]] = str(safe_path(Path(lane["request"]["project_root"])))
    seen = set()
    for record in state["phases"].values():
        for attempt in record.get("attempts") or []:
            for stage in attempt.get("stages") or []:
                campaign_id = stage.get("campaign_id")
                if not campaign_id:
                    continue
                result_path = campaign.campaign_dir(ctx, campaign_id) / "result.json"
                if not result_path.is_file():
                    continue
                try:
                    campaign_lanes = load_signed(ctx, result_path).get("lanes") or []
                except (OSError, ValueError, TypeError):
                    continue
                for lane in campaign_lanes:
                    run_id = lane.get("final_run_id")
                    data_root = lane.get("lane_data_root")
                    if (lane.get("status") != "MASTER_APPROVED" or not run_id or not data_root
                            or root_by_lane.get(lane.get("name")) != root):
                        continue
                    key = (str(data_root), run_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        lane_ctx = EngineContext(Path(data_root))
                        marker = lane_ctx.run_dir(run_id) / "applied.json"
                        applied = load_signed(lane_ctx, marker) if marker.is_file() else {}
                    except (OSError, ValueError, TypeError):
                        continue
                    if applied.get("source_fingerprint") == current:
                        return True
    return False


def _resume_assessment(ctx, state):
    """Inspect a checkpoint without mutating it; return the exact identity an approval must bind."""
    directory = project_dir(ctx, state["project_id"])
    path = checkpoint.checkpoint_path(ctx, "project", state["project_id"])
    roots = _project_roots(state)
    aggregate, per_root = _source_snapshot(state)
    commit = checkpoint.read_git_head(roots[0])
    inspected = checkpoint.inspect_checkpoint(ctx, path, project_root=roots[0])
    document = inspected.get("checkpoint")
    reason = inspected.get("reason") if inspected["status"] != "RESUMABLE" else None
    own_apply = False
    if document is not None and reason is None:
        if document["next_action"]["step"] not in _RESUME_STEPS:
            reason = "unknown_step"
        elif document["checks"].get("source-fingerprint") != aggregate:
            changed = [(index, root, fingerprint) for index, (root, fingerprint)
                       in enumerate(per_root.items()) if document["checks"].get(f"source-{index:03d}") != fingerprint]
            if document["repo"]["commit"] == commit and changed and all(
                    _own_apply_matches(ctx, state, root, fingerprint) for _, root, fingerprint in changed):
                own_apply = True
            else:
                reason = "source_changed"
        elif document["repo"]["commit"] != commit:
            reason = "repo_head_changed"
    return {
        "directory": directory, "path": path, "status": inspected["status"], "reason": reason,
        "checkpoint": document, "checkpoint_sha256": _raw_sha256(path), "source_fingerprint": aggregate,
        "per_root": per_root, "repo_commit": commit, "own_apply": own_apply,
    }


def _approval_matches(ctx, assessment, state):
    path = assessment["directory"] / _RESUME_APPROVAL
    if not path.is_file() or assessment["checkpoint"] is None or not assessment["reason"]:
        return False
    try:
        approval = load_signed(ctx, path)
        approved_at = dt.datetime.fromisoformat(str(approval["approved_at"]).replace("Z", "+00:00"))
    except (OSError, ValueError, TypeError, KeyError):
        return False
    if set(approval) != _APPROVAL_KEYS or approved_at.tzinfo is None:
        return False
    approver = approval.get("approved_by")
    if not isinstance(approver, str) or not 1 <= len(approver) <= 200 or any(c in approver for c in "\r\n\0"):
        return False
    return (
        approval.get("project_id") == state["project_id"]
        and approval.get("operation_id") == assessment["checkpoint"]["operation_id"]
        and approval.get("checkpoint_sha256") == assessment["checkpoint_sha256"]
        and approval.get("checkpoint_status") == assessment["status"]
        and approval.get("reason") == assessment["reason"]
        and approval.get("source_fingerprint") == assessment["source_fingerprint"]
        and approval.get("repo_commit") == assessment["repo_commit"]
    )


def _require_resume_clearance(ctx, state):
    assessment = _resume_assessment(ctx, state)
    if assessment["own_apply"]:
        _write_checkpoint(ctx, state, snapshot=(assessment["source_fingerprint"], assessment["per_root"]))
        return
    if not assessment["reason"]:
        return
    if _approval_matches(ctx, assessment, state):
        return
    raise ValueError(
        f"Project resume requires human approval ({assessment['reason']}); run project-approve in an interactive terminal")


def _stdin_is_tty():
    return sys.stdin is not None and sys.stdin.isatty()


def approve_project_resume(ctx, project_id):
    """Record a terminal-only human acknowledgement for an otherwise refused project resume."""
    if os.environ.get("RESPECTED_ORCH_CHILD") == "1" or os.environ.get("RESPECTED_ORCH_DELEGATED") == "1":
        raise ValueError("Project resume approval must come from the operator, not from an orchestrated process")
    if not _stdin_is_tty():
        raise ValueError("Human project resume approval requires an interactive terminal")
    directory = project_dir(ctx, project_id)
    state = load_signed(ctx, directory / "project.json")
    if state["status"] in _TERMINAL:
        raise ValueError(f"Project is {state['status']}; nothing to approve")
    assessment = _resume_assessment(ctx, state)
    if not assessment["reason"]:
        raise ValueError("Project checkpoint is valid; no human approval is required")
    document = assessment["checkpoint"]
    if document is None or not assessment["checkpoint_sha256"]:
        raise ValueError("A checkpoint that cannot be validated cannot be approved")
    approval = dict(
        project_id=project_id, operation_id=document["operation_id"],
        checkpoint_sha256=assessment["checkpoint_sha256"], checkpoint_status=assessment["status"],
        reason=assessment["reason"], source_fingerprint=assessment["source_fingerprint"],
        repo_commit=assessment["repo_commit"], approved_by=getpass.getuser(), approved_at=_now())
    save_signed(ctx, directory / _RESUME_APPROVAL, approval)
    return dict(project_id=project_id, status="approval_recorded", reason=assessment["reason"],
                checkpoint_sha256=approval["checkpoint_sha256"], approved_at=approval["approved_at"])


def _spec(value, settings=None):
    if not isinstance(value, dict) or not isinstance(value.get("phases"), list) or not 1 <= len(value["phases"]) <= _MAX_PHASES:
        raise ValueError(f"Project needs 1..{_MAX_PHASES} phases")
    budget = value.get("budget", {})
    if not isinstance(budget, dict):
        raise ValueError("Invalid project budget")
    seconds, attempts = budget.get("max_seconds", 86400), budget.get("max_phase_attempts", 2)
    tokens = budget.get("max_weighted_tokens")
    unknown_step = budget.get("unknown_step_tokens", UNKNOWN_STEP_TOKENS_DEFAULT)  # assumed charge per step with no usage data
    if type(seconds) is not int or not 60 <= seconds <= _MAX_SECONDS or type(attempts) is not int or not 1 <= attempts <= _MAX_ATTEMPTS \
            or (tokens is not None and (type(tokens) is not int or tokens < 1)) \
            or type(unknown_step) is not int or not 0 <= unknown_step <= 10_000_000:
        raise ValueError("Invalid project budget")
    names, phases = set(), []
    for phase in value["phases"]:
        if not isinstance(phase, dict) or not _NAME.fullmatch(str(phase.get("name", ""))) or phase["name"] in names:
            raise ValueError("Phase names must be unique lowercase slugs")
        names.add(phase["name"])
        after = phase.get("after", [])
        if not isinstance(after, list) or not all(isinstance(dep, str) and _NAME.fullmatch(dep) for dep in after):
            raise ValueError("Phase dependencies must be lowercase slugs")
        campaign._spec({"workstreams": phase.get("workstreams"), "final": {"skip": True},
                        "lane_timeout_seconds": phase.get("lane_timeout_seconds", campaign.LANE_TIMEOUT_DEFAULT)})
        verify = []
        for check in phase.get("verify", []):
            if not isinstance(check, dict):
                raise ValueError("Verify checks need an existing cwd and a sane timeout")
            timeout = check.get("timeout_seconds", 1800)
            if type(timeout) is not int or not 1 <= timeout <= 14400 or not Path(check.get("cwd", "")).is_dir():
                raise ValueError("Verify checks need an existing cwd and a sane timeout")
            verify.append(dict(command=_command(check.get("command")), cwd=str(check["cwd"]), timeout_seconds=timeout))
        lane_budget = phase.get("lane_token_budget")  # hard per-lane cap across all attempts of the phase (None = none)
        if lane_budget is not None and (type(lane_budget) is not int or not 1000 <= lane_budget <= MAX_BUDGET):
            raise ValueError("Invalid lane token budget")
        phases.append(dict(name=phase["name"], after=list(after), workstreams=phase["workstreams"], lane_token_budget=lane_budget,
                           verify=verify, auto_apply=phase.get("auto_apply") is True,
                           lane_timeout_seconds=phase.get("lane_timeout_seconds", campaign.LANE_TIMEOUT_DEFAULT)))
    done = set()
    while len(done) < len(phases):  # every phase must eventually have all dependencies resolved (no cycles/unknowns)
        ready = {p["name"] for p in phases if p["name"] not in done and set(p["after"]) <= done}
        if not ready or any(dep not in names for p in phases for dep in p["after"]):
            raise ValueError("Phase dependencies are unknown or cyclic")
        done |= ready
    final = value.get("final_review")
    if final is not None:  # fresh Claude Master over the verified outcome; never allowed to apply
        placeholder = [{"name": "review", "after": [], "request": {}}]  # dont borrow a real phase to validate shape
        final = campaign._spec({"workstreams": placeholder, "final": dict(final, allow_apply=False)}, settings)["final"]
    source = value.get("engine_source")
    if source is not None and not (Path(source) / "campaign.py").is_file():
        raise ValueError("engine_source must be the respected_orchestrator package directory")
    return dict(goal=str(value.get("goal", ""))[:4000], phases=phases, final_review=final, engine_source=source,
                budget=dict(max_seconds=seconds, max_phase_attempts=attempts, max_weighted_tokens=tokens,
                            unknown_step_tokens=unknown_step))


def create_project(ctx, request):
    spec = _spec(request, roles.read_settings(ctx.data_root))
    project_id = f"proj-{dt.datetime.now(dt.timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    directory = project_dir(ctx, project_id)
    directory.mkdir(parents=True, exist_ok=False)
    phases = {p["name"]: dict(status="pending", attempts=[], applied=[], applied_lanes={}) for p in spec["phases"]}
    state = dict(project_id=project_id, spec=spec, status="created", phases=phases,
                 weighted_tokens=0, unknown_usage_steps=0, created_at=_now(),
                 deadline_epoch=time.time() + spec["budget"]["max_seconds"])
    save_signed(ctx, directory / "project.json", state)
    _write_checkpoint(ctx, state, "campaign")
    return project_id, directory


def _spawn(ctx, project_id, directory, spec):
    engine = campaign._snapshot_engine(ctx, spec["engine_source"])
    command = engine_command("--data-root", str(ctx.data_root), "project-run", project_id)
    pid = lanes._spawn_detached(command, engine, directory / "supervisor.log", env=campaign._engine_env(engine))
    save_signed(ctx, directory / "supervisor.json", dict(project_id=project_id, pid=pid, engine=str(engine), engine_version=__version__))
    return pid


def start_project(ctx, request):
    from ..engine import maintenance
    maintenance.refuse_if_active(ctx, "proje başlatma")
    project_id, directory = create_project(ctx, request)
    return dict(project_id=project_id, status="started", pid=_spawn(ctx, project_id, directory, load_signed(ctx, directory / "project.json")["spec"]))


def _supervisor_alive(ctx, directory):
    path = directory / "supervisor.json"
    return path.is_file() and lanes._pid_is_alive(load_signed(ctx, path).get("pid", -1))


def resume_project(ctx, project_id):
    from ..engine import maintenance
    maintenance.refuse_if_active(ctx, "proje devam ettirme")
    directory = project_dir(ctx, project_id)
    state = load_signed(ctx, directory / "project.json")
    if state["status"] in _TERMINAL:
        raise ValueError(f"Project is {state['status']}; nothing to resume")
    if _supervisor_alive(ctx, directory):
        raise ValueError("Project supervisor is already running")
    _clear_stale_lock(directory)
    _require_resume_clearance(ctx, state)
    return dict(project_id=project_id, status="resumed", pid=_spawn(ctx, project_id, directory, state["spec"]))


def project_status(ctx, project_id):
    directory = project_dir(ctx, project_id)
    state = load_signed(ctx, directory / "project.json")
    state.pop("spec")
    return dict(state, alive=_supervisor_alive(ctx, directory))


def cancel_project(ctx, project_id):
    (project_dir(ctx, project_id) / "cancel").write_text(_now(), encoding="utf8")
    return dict(project_id=project_id, status="cancel_requested")


def _acquire(directory):
    """One supervisor per project: the lock holds a pid; a dead pid's lock is stale and replaced.

    A stale lock is unlinked and retried a few times: a second racer may recreate the lock in the
    unlink->create window, so each retry re-reads the owner and only gives up once it is not alive."""
    lock = directory / "run.lock"
    for _ in range(5):
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                owner = int(lock.read_text(encoding="utf8") or -1)
            except (OSError, ValueError):
                owner = -1
            if owner != os.getpid() and lanes._pid_is_alive(owner):
                raise ValueError("Project is already being executed")
            lock.unlink(missing_ok=True)
            continue
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        return lock
    raise ValueError("Project is already being executed")


def _clear_stale_lock(directory):
    """Preflight for resume: never take a live owner's lock; remove only a dead or corrupt owner."""
    lock = directory / "run.lock"
    if not lock.exists():
        return
    try:
        owner = int(lock.read_text(encoding="utf8") or -1)
    except (OSError, ValueError):
        owner = -1
    if owner != os.getpid() and lanes._pid_is_alive(owner):
        raise ValueError("Project is already being executed")
    lock.unlink(missing_ok=True)


def _default_campaign_runner(ctx, campaign_id, timeout, cancel, engine_source):
    engine = campaign._snapshot_engine(ctx, engine_source)  # re-snapshot: earlier phases may have changed the engine
    command = engine_command("--data-root", str(ctx.data_root), "campaign-run", campaign_id)
    execute(command, engine, timeout, cancel_path=cancel, mark_child=False, env=campaign._engine_env(engine), scrub_env=True)


def _verify(ctx, phase, cancel):
    for check in phase["verify"]:
        try:  # applied worker code: AppContainer, network denied unless the operator listed this phase (ADR-018)
            done, network = sandbox.run_check(ctx, check["command"], Path(check["cwd"]), check["timeout_seconds"], task_id=phase["name"],
                                              scratch=ctx.data_root / "verify-tmp", cancel_path=cancel)
        except sandbox.SandboxError as error:
            return f"verify refused, sandbox unavailable: {str(error)[:200]}"
        if done.returncode:
            return f"verify {check['command'][:3]} exit {done.returncode} (network: {network}): {(done.stdout + done.stderr)[-1500:]}"
    return None


def _merge_lanes(attempt, lanes):
    merged = {lane["name"]: lane for lane in attempt.get("lanes") or []}
    for lane in lanes:
        merged[lane["name"]] = {k: lane.get(k) for k in ("name", "status", "reason", "changed_files")}
    attempt["lanes"] = list(merged.values())


def _after_campaign_result(ctx, state, phase, stage):
    """Idempotent boundary after a signed campaign result and before token accounting/apply."""
    _write_checkpoint(ctx, state, "apply", f"{phase['name']}:{attempt_target(stage)}")


def attempt_target(stage):
    return str(stage.get("campaign_id") or "pending")


def _budget_used(state, spec):
    """Known weighted tokens plus an explicit assumed charge per step that ran but reported no usage (never zero)."""
    assumed = spec["budget"].get("unknown_step_tokens", UNKNOWN_STEP_TOKENS_DEFAULT)
    return state["weighted_tokens"] + state.get("unknown_usage_steps", 0) * assumed


def _over_budget(state, spec):
    limit = spec["budget"]["max_weighted_tokens"]
    return bool(limit) and _budget_used(state, spec) > limit


def _lane_spent(ctx, record, assumed):
    """lane name -> weighted tokens spent by all earlier runs of that lane in this phase (known + assumed unknown steps)."""
    spent = {}
    for attempt in record["attempts"]:
        for stage in attempt.get("stages", []):
            result = campaign.campaign_dir(ctx, stage["campaign_id"]) / "result.json" if stage.get("campaign_id") else None
            if result is None or not result.is_file():
                continue
            for lane in load_signed(ctx, result)["lanes"]:
                usage = lane.get("token_usage") if isinstance(lane.get("token_usage"), dict) else {}
                spent[lane["name"]] = (spent.get(lane["name"], 0) + (usage.get("estimated_weighted_tokens") or 0)
                                       + int(lane.get("unknown_usage_steps") or 0) * assumed)
    return spent


_REVIEW_RETRYABLE = {"reviewer_timeout", "reviewer_disconnected", "reviewer_execution_failed"}


def _review_retry_roots(ctx, record):
    """lane name -> lane data root of its latest run that was coded and verified but whose REVIEW failed.

    A retry continues that very lane (review-only): the worker is not run again and the old evidence stays in place."""
    found = {}
    for attempt in record["attempts"]:
        for stage in attempt.get("stages", []):
            result = campaign.campaign_dir(ctx, stage["campaign_id"]) / "result.json" if stage.get("campaign_id") else None
            if result is None or not result.is_file():
                continue
            for lane in load_signed(ctx, result)["lanes"]:
                if lane.get("reason") in _REVIEW_RETRYABLE and lane.get("final_run_id") and lane.get("lane_data_root"):
                    found[lane["name"]] = lane["lane_data_root"]
                else:
                    found.pop(lane["name"], None)
    return found


def _attempt(ctx, directory, state, phase, attempt, note, runner, cancel):
    """One bounded attempt in stages: campaign -> apply approved lanes -> next stage -> verify.

    A stage is the not-yet-applied lanes whose `after` dependencies are all applied; each stage is one fresh campaign
    (its own mirror), so a dependent lane sees its dependency's applied output. The applied mapping and the stage
    records live on the phase/attempt record, so a kill resumes the interrupted stage without a duplicate campaign."""
    spec = state["spec"]
    record = state["phases"][phase["name"]]
    applied = record.setdefault("applied_lanes", {})
    stages = attempt.setdefault("stages", [])
    attempts = record["attempts"]
    previous_failed = set(attempts[-2].get("failed_lanes", [])) if len(attempts) > 1 else set()
    index = attempt.get("stage_index", 0)

    review_roots = _review_retry_roots(ctx, record)
    lane_spent = _lane_spent(ctx, record, spec["budget"].get("unknown_step_tokens", UNKNOWN_STEP_TOKENS_DEFAULT))

    def stage_lane(lane):
        task = lane["request"]["task"]
        if note and lane["name"] in previous_failed:  # correct only the lanes that failed, not the applied ones
            task += f"\n\nCORRECTION: the previous attempt failed. Earlier changes may already be applied; fix this: {note}"
        resumed = {"resume_lane_data_root": review_roots[lane["name"]]} if lane["name"] in review_roots else {}
        request = dict(lane["request"], task=task)
        # Earlier lanes' applied output (new and changed files) is a read-only input: the worktree is cut from HEAD,
        # where uncommitted applied work does not exist.
        # (also earlier phases: a new phase's campaign is again cut from HEAD, where their applied output does not exist)
        others = (rec.get("applied_lanes", {}) for key, rec in state["phases"].items() if key != phase["name"])
        done = sorted({name for entry in (*applied.values(), *(e for table in others for e in table.values()))
                       for name in entry.get("changed_files", [])})
        if done:
            request["context_paths"] = sorted({*request.get("context_paths", []), *done})[:200]
        limit = (request.get("workflow") or {}).get("max_weighted_tokens") or phase.get("lane_token_budget")
        if limit:
            # A fresh worker run gets only what its earlier runs left; a resumed lane keeps its own lifetime ledger.
            left = limit if lane["name"] in review_roots else limit - lane_spent.get(lane["name"], 0)
            request["workflow"] = dict(request.get("workflow") or {}, max_weighted_tokens=max(1000, left))
        return dict(lane, after=[dep for dep in lane.get("after", []) if dep not in applied], request=request, **resumed)

    while True:
        if index < len(stages):
            stage = stages[index]
        else:
            remaining = [lane for lane in phase["workstreams"] if lane["name"] not in applied]
            ready = [lane for lane in remaining if all(dep in applied for dep in lane.get("after", []))]
            if not ready:
                break
            stage = dict(campaign_id=None, lanes=[lane["name"] for lane in ready], applied=[])
            stages.append(stage)
        by_name = {lane["name"]: lane for lane in phase["workstreams"]}
        if not stage["campaign_id"]:
            by_lane = {lane["name"]: lane for lane in phase["workstreams"]}
            for name in stage["lanes"]:
                limit = (by_lane[name]["request"].get("workflow") or {}).get("max_weighted_tokens") or phase.get("lane_token_budget")
                if limit and name not in review_roots and limit - lane_spent.get(name, 0) < 1000:
                    stages.pop()  # nothing was launched for this stage
                    save_signed(ctx, directory / "project.json", state)
                    return "blocked", f"lane {name} exhausted its token budget ({lane_spent.get(name, 0)} of {limit}); raise it explicitly"
            _write_checkpoint(ctx, state, "campaign", f"{phase['name']}:{len(stages)}")
            campaign_id, _ = campaign.create_campaign(ctx, {
                "goal": f"{spec['goal']} / {phase['name']}",
                "workstreams": [stage_lane(by_name[name]) for name in stage["lanes"]],
                "final": {"skip": True}, "lane_timeout_seconds": phase["lane_timeout_seconds"]})
            stage["campaign_id"] = campaign_id
            attempt.setdefault("campaign_id", campaign_id)
            attempt.setdefault("started_at", _now())
            if "engine_snapshot" not in attempt:  # one snapshot name per attempt, not one per stage
                attempt["engine_snapshot"] = campaign._snapshot_engine(ctx, spec["engine_source"]).name
            save_signed(ctx, directory / "project.json", state)
        cdir = campaign.campaign_dir(ctx, stage["campaign_id"])
        if not (cdir / "result.json").is_file():
            runner(ctx, stage["campaign_id"], phase["lane_timeout_seconds"] * len(stage["lanes"]) + 600, cancel)
        if not (cdir / "result.json").is_file():
            return "failed", "campaign produced no result (interrupted or timed out)"
        _after_campaign_result(ctx, state, phase, stage)
        lanes = load_signed(ctx, cdir / "result.json")["lanes"]
        if "weighted_tokens" not in stage:  # account every started lane once, and persist before any early return
            unaccounted = [lane["name"] for lane in lanes
                           if lane.get("final_run_id") and not isinstance(lane.get("token_usage"), dict)]
            spend = sum((lane["token_usage"] or {}).get("estimated_weighted_tokens", 0)
                        for lane in lanes if isinstance(lane.get("token_usage"), dict))
            unknown_steps = sum(int(lane.get("unknown_usage_steps") or 0) for lane in lanes)
            stage["weighted_tokens"], stage["unknown_usage_steps"] = spend, unknown_steps
            attempt["weighted_tokens"] = attempt.get("weighted_tokens", 0) + spend
            attempt["unknown_usage_steps"] = attempt.get("unknown_usage_steps", 0) + unknown_steps
            state["weighted_tokens"] += spend
            state["unknown_usage_steps"] = state.get("unknown_usage_steps", 0) + unknown_steps
            if unaccounted:
                attempt["unaccounted"] = unaccounted
                save_signed(ctx, directory / "project.json", state)
                _write_checkpoint(ctx, state, "apply", f"{phase['name']}:{attempt_target(stage)}")
                return "blocked", f"token usage unknown for lane {unaccounted[0]}"
            save_signed(ctx, directory / "project.json", state)
        _write_checkpoint(ctx, state, "apply", f"{phase['name']}:{attempt_target(stage)}")
        _merge_lanes(attempt, lanes)
        bad = [lane for lane in lanes if lane["status"] != "MASTER_APPROVED"]
        applied_so_far = attempt.setdefault("applied", [])
        if phase["auto_apply"]:
            # Project states this supervisor created by applying verified lanes of this stage (after a restart, the
            # current state of a root whose lane is already applied counts: git apply --check still guards each patch).
            roots = {Path(by_name[lane["name"]]["request"]["project_root"]) for lane in lanes}
            trusted = ({runner_fingerprint(root) for root in roots if (root / ".git").exists()}
                       if any(lane["name"] in applied for lane in lanes) else set())
            for lane in lanes:
                if lane["status"] != "MASTER_APPROVED" or lane["name"] in applied:
                    continue
                lane_ctx = EngineContext(Path(lane["lane_data_root"]))
                if not (lane_ctx.run_dir(lane["final_run_id"]) / "applied.json").is_file():
                    try:
                        applied_result = apply_task(lane_ctx, lane["final_run_id"], accepted_fingerprints=trusted)
                        root = Path(by_name[lane["name"]]["request"]["project_root"])
                        if (root / ".git").exists():  # parallel lanes of one Git source: the next lane starts from this state
                            trusted.add(runner_fingerprint(root))
                        applied[lane["name"]] = dict(campaign_id=stage["campaign_id"], run_id=lane["final_run_id"],
                                                     changed_files=lane.get("changed_files", []),
                                                     source_fingerprint=applied_result.get("source_fingerprint"))
                    except Exception as error:  # conflict with a changed source: never forced
                        problem = str(error)[:500]
                        stale = any(marker in problem.casefold() for marker in (
                            "stale", "conflict", "patch failed", "does not apply"))
                        kind = "stale patch" if stale else "verification failure"
                        return "blocked", f"apply of {lane['name']} refused ({kind}): {problem}"
                applied.setdefault(lane["name"], dict(campaign_id=stage["campaign_id"], run_id=lane["final_run_id"],
                                                       changed_files=lane.get("changed_files", [])))
                stage["applied"].append(lane["name"])
                if lane["name"] not in applied_so_far:
                    applied_so_far.append(lane["name"])
                save_signed(ctx, directory / "project.json", state)
                _write_checkpoint(ctx, state, "verify", f"{phase['name']}:{attempt_target(stage)}")
        if bad:
            attempt["failed_lanes"] = [lane["name"] for lane in bad]
            save_signed(ctx, directory / "project.json", state)
            return "failed", "lanes not approved: " + "; ".join(
                f"{lane['name']}: {lane['status']}/{lane.get('reason')}" for lane in bad)
        if not phase["auto_apply"]:
            return "blocked", "apply is not preauthorized for this phase (auto_apply=false); a human must authorize it"
        if _over_budget(state, spec):
            return "blocked", "token budget exceeded"
        index += 1
        attempt["stage_index"] = index
        save_signed(ctx, directory / "project.json", state)
    _write_checkpoint(ctx, state, "verify", phase["name"])
    problem = _verify(ctx, phase, cancel)
    return ("failed", problem) if problem else ("done", "")


def run_project(ctx, project_id, campaign_runner=None, clock=time.time):
    directory = project_dir(ctx, project_id)
    lock = _acquire(directory)
    cancel = directory / "cancel"
    try:
        state = load_signed(ctx, directory / "project.json")
        if state["status"] not in _TERMINAL:
            _require_resume_clearance(ctx, state)
        spec = state["spec"]
        runner = campaign_runner or (lambda c, cid, timeout, cancel_path: _default_campaign_runner(c, cid, timeout, cancel_path, spec["engine_source"]))

        def finish(status, reason=None):
            state.update(status=status, reason=reason, finished_at=_now())
            save_signed(ctx, directory / "project.json", state)
            if status == "completed":
                _write_checkpoint(ctx, state, "review" if spec.get("final_review") else "complete")
            return state

        if state["status"] in _TERMINAL:
            if state["status"] == "completed":
                final_review(ctx, project_id)
            return state
        state["status"] = "running"
        while True:
            save_signed(ctx, directory / "project.json", state)
            if cancel.exists():
                return finish("cancelled")
            if clock() > state["deadline_epoch"]:
                return finish("blocked", "time budget exceeded")
            if _over_budget(state, spec):
                return finish("blocked", "token budget exceeded")
            phases = state["phases"]
            ready = [p for p in spec["phases"] if phases[p["name"]]["status"] == "pending"
                     and all(phases[d]["status"] == "done" for d in p["after"])]
            if not ready:
                pending = [n for n, p in phases.items() if p["status"] != "done"]
                if pending:
                    return finish("blocked", f"phases not runnable: {pending}")
                finish("completed")
                final_review(ctx, project_id)
                return state
            phase, record = ready[0], phases[ready[0]["name"]]
            attempts = record["attempts"]
            if not attempts or attempts[-1].get("outcome"):
                if len(attempts) >= spec["budget"]["max_phase_attempts"]:
                    record["status"] = "failed"
                    return finish("blocked", f"phase {phase['name']} exhausted {len(attempts)} attempts: {attempts[-1]['note'][:500]}")
                attempts.append({})
            attempt = attempts[-1]
            previous = attempts[-2]["note"] if len(attempts) > 1 else ""
            try:
                outcome, note = _attempt(ctx, directory, state, phase, attempt, previous, runner, cancel)
            except ProcessStopped as stopped:
                outcome, note = "failed", f"stopped: {stopped}"
            except Exception as error:
                outcome, note = "failed", str(error)[:500]
            if cancel.exists():
                return finish("cancelled")
            attempt.update(outcome=outcome, note=note, finished_at=_now())
            if clock() > state["deadline_epoch"]:
                return finish("blocked", "time budget exceeded")
            if _over_budget(state, spec):
                return finish("blocked", "token budget exceeded")
            if outcome == "done":
                record["status"] = "done"
            elif outcome == "blocked":
                record["status"] = "blocked"
                return finish("blocked", f"phase {phase['name']}: {note}")
    finally:
        lock.unlink(missing_ok=True)


def final_review(ctx, project_id):
    """Fresh Claude Master over the verified outcome (read-only, no apply). Exactly once."""
    directory = project_dir(ctx, project_id)
    state = load_signed(ctx, directory / "project.json")
    if state["spec"]["final_review"] and state["status"] == "completed":
        lanes = []
        roots = {lane["request"]["project_root"] for phase in state["spec"]["phases"] for lane in phase["workstreams"]}
        for phase, record in state["phases"].items():
            # A lane applied in an earlier attempt must still be shown: latest known state per lane across attempts.
            merged = {}
            for attempt in record["attempts"]:
                merged.update({lane["name"]: lane for lane in attempt.get("lanes") or []})
            applied = set(record.get("applied_lanes", {}))
            for lane in merged.values():  # the supervisor already applied+verified these; say so
                lanes.append(dict(lane, phase=phase, applied=lane["name"] in applied, verified=lane["name"] in applied))
        campaign._start_final_master(ctx, directory, dict(goal=state["spec"]["goal"], final=state["spec"]["final_review"],
                                                          roots=sorted(roots)), lanes, project_review=True)
        _write_checkpoint(ctx, state, "complete")
