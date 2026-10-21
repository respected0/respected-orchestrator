"""Durable autonomous projects: dependent phases of campaigns with preauthorized apply, verification and continuation.

Claude plans the project once (a JSON spec). A detached supervisor then runs each eligible phase as a campaign
(fresh engine snapshot + fresh source mirror every time), applies only fully approved lanes through the engine's own
verified `apply_task`, runs deterministic verify commands on the real source and moves on. State is signed JSON on disk,
so the supervisor can be killed or the machine restarted and `project-resume` continues without duplicating work.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import time
from uuid import uuid4

from ..engine import antigravity_orchestrator as agy, runner, sandbox
from ..engine.budget import MAX_BUDGET, UNKNOWN_STEP_TOKENS_DEFAULT
from . import campaign, roles
from ..context import EngineContext, safe_path
from ..engine.processes import ProcessStopped, execute
from ..engine.runner import _command, _load, _save, apply_task
from ..engine.runner import project_fingerprint as runner_fingerprint

_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_MAX_PHASES, _MAX_SECONDS, _MAX_ATTEMPTS = 12, 7 * 86400, 3
_TERMINAL = {"completed", "cancelled", "blocked"}


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def project_dir(ctx, project_id):
    if not re.fullmatch(r"proj-[a-z0-9-]{1,60}", str(project_id)):
        raise ValueError("Invalid project identity")
    return safe_path(ctx.data_root / "projects" / project_id)


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
    _save(ctx, directory / "project.json", dict(project_id=project_id, spec=spec, status="created", phases=phases,
                                                 weighted_tokens=0, unknown_usage_steps=0, created_at=_now(),
                                                 deadline_epoch=time.time() + spec["budget"]["max_seconds"]))
    return project_id, directory


def _spawn(ctx, project_id, directory, spec):
    engine = campaign._snapshot_engine(ctx, spec["engine_source"])
    command = [sys.executable, "-m", "respected_orchestrator", "--data-root", str(ctx.data_root), "project-run", project_id]
    pid = agy._spawn_detached(command, engine, directory / "supervisor.log", env=campaign._engine_env(engine))
    _save(ctx, directory / "supervisor.json", dict(project_id=project_id, pid=pid, engine=str(engine)))
    return pid


def start_project(ctx, request):
    project_id, directory = create_project(ctx, request)
    return dict(project_id=project_id, status="started", pid=_spawn(ctx, project_id, directory, _load(ctx, directory / "project.json")["spec"]))


def _supervisor_alive(ctx, directory):
    path = directory / "supervisor.json"
    return path.is_file() and agy._pid_is_alive(_load(ctx, path).get("pid", -1))


def resume_project(ctx, project_id):
    directory = project_dir(ctx, project_id)
    state = _load(ctx, directory / "project.json")
    if state["status"] in _TERMINAL:
        raise ValueError(f"Project is {state['status']}; nothing to resume")
    if _supervisor_alive(ctx, directory):
        raise ValueError("Project supervisor is already running")
    return dict(project_id=project_id, status="resumed", pid=_spawn(ctx, project_id, directory, state["spec"]))


def project_status(ctx, project_id):
    directory = project_dir(ctx, project_id)
    state = _load(ctx, directory / "project.json")
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
            if owner != os.getpid() and agy._pid_is_alive(owner):
                raise ValueError("Project is already being executed")
            lock.unlink(missing_ok=True)
            continue
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        return lock
    raise ValueError("Project is already being executed")


def _default_campaign_runner(ctx, campaign_id, timeout, cancel, engine_source):
    engine = campaign._snapshot_engine(ctx, engine_source)  # re-snapshot: earlier phases may have changed the engine
    command = [sys.executable, "-m", "respected_orchestrator", "--data-root", str(ctx.data_root), "campaign-run", campaign_id]
    execute(command, engine, timeout, cancel_path=cancel, mark_child=False, env=campaign._engine_env(engine), scrub_env=True)


def _verify(ctx, phase, cancel):
    for check in phase["verify"]:
        try:
            command = sandbox.wrap(ctx.data_root, runner._key_path(ctx), check["command"])  # applied worker code: no engine authority
        except sandbox.SandboxError as error:
            return f"verify refused, sandbox unavailable: {str(error)[:200]}"
        done = execute(command, Path(check["cwd"]), check["timeout_seconds"], cancel_path=cancel, scrub_env=True)
        if done.returncode:
            return f"verify {check['command'][:3]} exit {done.returncode}: {(done.stdout + done.stderr)[-1500:]}"
    return None


def _merge_lanes(attempt, lanes):
    merged = {lane["name"]: lane for lane in attempt.get("lanes") or []}
    for lane in lanes:
        merged[lane["name"]] = {k: lane.get(k) for k in ("name", "status", "reason", "changed_files")}
    attempt["lanes"] = list(merged.values())


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
            for lane in _load(ctx, result)["lanes"]:
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
            for lane in _load(ctx, result)["lanes"]:
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
                    _save(ctx, directory / "project.json", state)
                    return "blocked", f"lane {name} exhausted its token budget ({lane_spent.get(name, 0)} of {limit}); raise it explicitly"
            campaign_id, _ = campaign.create_campaign(ctx, {
                "goal": f"{spec['goal']} / {phase['name']}",
                "workstreams": [stage_lane(by_name[name]) for name in stage["lanes"]],
                "final": {"skip": True}, "lane_timeout_seconds": phase["lane_timeout_seconds"]})
            stage["campaign_id"] = campaign_id
            attempt.setdefault("campaign_id", campaign_id)
            attempt.setdefault("started_at", _now())
            if "engine_snapshot" not in attempt:  # one snapshot name per attempt, not one per stage
                attempt["engine_snapshot"] = campaign._snapshot_engine(ctx, spec["engine_source"]).name
            _save(ctx, directory / "project.json", state)
        cdir = campaign.campaign_dir(ctx, stage["campaign_id"])
        if not (cdir / "result.json").is_file():
            runner(ctx, stage["campaign_id"], phase["lane_timeout_seconds"] * len(stage["lanes"]) + 600, cancel)
        if not (cdir / "result.json").is_file():
            return "failed", "campaign produced no result (interrupted or timed out)"
        lanes = _load(ctx, cdir / "result.json")["lanes"]
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
                _save(ctx, directory / "project.json", state)
                return "blocked", f"token usage unknown for lane {unaccounted[0]}"
            _save(ctx, directory / "project.json", state)
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
                        apply_task(lane_ctx, lane["final_run_id"], accepted_fingerprints=trusted)
                        root = Path(by_name[lane["name"]]["request"]["project_root"])
                        if (root / ".git").exists():  # parallel lanes of one Git source: the next lane starts from this state
                            trusted.add(runner_fingerprint(root))
                    except Exception as error:  # conflict with a changed source: never forced
                        return "blocked", f"apply of {lane['name']} refused: {str(error)[:500]}"
                applied[lane["name"]] = dict(campaign_id=stage["campaign_id"], run_id=lane["final_run_id"],
                                             changed_files=lane.get("changed_files", []))
                stage["applied"].append(lane["name"])
                if lane["name"] not in applied_so_far:
                    applied_so_far.append(lane["name"])
                _save(ctx, directory / "project.json", state)
        if bad:
            attempt["failed_lanes"] = [lane["name"] for lane in bad]
            _save(ctx, directory / "project.json", state)
            return "failed", "lanes not approved: " + "; ".join(
                f"{lane['name']}: {lane['status']}/{lane.get('reason')}" for lane in bad)
        if not phase["auto_apply"]:
            return "blocked", "apply is not preauthorized for this phase (auto_apply=false); a human must authorize it"
        if _over_budget(state, spec):
            return "blocked", "token budget exceeded"
        index += 1
        attempt["stage_index"] = index
        _save(ctx, directory / "project.json", state)
    problem = _verify(ctx, phase, cancel)
    return ("failed", problem) if problem else ("done", "")


def run_project(ctx, project_id, campaign_runner=None, clock=time.time):
    directory = project_dir(ctx, project_id)
    lock = _acquire(directory)
    cancel = directory / "cancel"
    try:
        state = _load(ctx, directory / "project.json")
        spec = state["spec"]
        runner = campaign_runner or (lambda c, cid, timeout, cancel_path: _default_campaign_runner(c, cid, timeout, cancel_path, spec["engine_source"]))

        def finish(status, reason=None):
            state.update(status=status, reason=reason, finished_at=_now())
            _save(ctx, directory / "project.json", state)
            return state

        if state["status"] in _TERMINAL:
            if state["status"] == "completed":
                final_review(ctx, project_id)
            return state
        state["status"] = "running"
        while True:
            _save(ctx, directory / "project.json", state)
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
    state = _load(ctx, directory / "project.json")
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
