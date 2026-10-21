"""Durable multi-repository campaigns: a detached supervisor runs parallel MAF lanes, then starts the final master."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
from uuid import uuid4

from ..engine import lanes
from ..engine import winproc
from ..context import FROZEN, EngineContext, engine_command, safe_path
from ..engine.processes import execute
from . import roles
from ..engine.runner import SUPPORTED_AGENTS, _track_record, _command, _load, _save, command_for, create_task, tool_available, tool_result

LANE_TIMEOUT_DEFAULT = 7200
FINAL_TIMEOUT_DEFAULT = 1800
_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
_MIRROR_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".runtime", ".local", "build", "dist",
                ".pytest_cache", "target", ".next", ".engine-key"}
_MIRROR_SECRET = re.compile(r"(?i)^(\.env.*|.*\.pem|.*\.key|credentials.*|secrets?\..*)$")
_MIRROR_MAX_BYTES = 5_000_000
_MIRROR_LOCK = threading.Lock()


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _final_command(final, settings):
    """Explicit command wins; else the `master` role (task `final.master` or Hub default_roles.master); else claude."""
    if "command" in final:
        if "master" in final:
            raise roles.RoleError("ROLE_CONFLICT", "final has both command and master", "State the final master once.")
        return _command(final["command"])
    settings = settings or {}
    if final.get("skip") is True:
        return _command(["claude", "-p", "{prompt}"])  # never started: nothing to resolve
    try:
        got = roles.resolve(settings, {"master": final["master"]} if "master" in final else {}, [], optional=["master"],
                            tools=list(SUPPORTED_AGENTS), available=tool_available, check_roles={"master"})
    except roles.RoleError as error:
        raise ValueError(f"{error.code}: {error.message}") from error
    if "master" not in got:
        return _command(["claude", "-p", "{prompt}"])
    return command_for(got["master"]["tool"], "{prompt}", profile=got["master"]["profile"])


def _spec(value, settings=None):
    if not isinstance(value, dict):
        raise ValueError("Campaign must be a JSON object")
    lanes = value.get("workstreams")
    if not isinstance(lanes, list) or not 1 <= len(lanes) <= 8:
        raise ValueError("Campaign needs 1..8 workstreams")
    names = set()
    for lane in lanes:
        if not isinstance(lane, dict) or not _NAME.fullmatch(str(lane.get("name", ""))) or lane["name"] in names:
            raise ValueError("Workstream names must be unique lowercase slugs")
        names.add(lane["name"])
        if not isinstance(lane.get("request"), dict) or not isinstance(lane.get("after", []), list):
            raise ValueError("Workstream needs a request object and an optional after list")
    resolved = set()
    pending = list(lanes)
    while pending:  # dependency order check: every lane must eventually have all its dependencies resolved
        ready = [lane for lane in pending if set(lane.get("after", [])) <= resolved]
        if not ready or not all(dep in names for lane in pending for dep in lane.get("after", [])):
            raise ValueError("Workstream dependencies are unknown or cyclic")
        resolved.update(lane["name"] for lane in ready)
        pending = [lane for lane in pending if lane not in ready]
    final = value.get("final", {})
    command = _final_command(final, settings)
    if final.get("skip") is not True and shutil.which(command[0]) is None and not Path(command[0]).is_file():
        raise ValueError(f"Final master executable '{command[0]}' unavailable")
    for key, default in (("lane_timeout_seconds", LANE_TIMEOUT_DEFAULT), ("timeout_seconds", FINAL_TIMEOUT_DEFAULT)):
        number = (final if key == "timeout_seconds" else value).get(key, default)
        if type(number) is not int or not 1 <= number <= 14400:
            raise ValueError(f"Invalid {key}")
    return {"goal": str(value.get("goal", ""))[:4000], "workstreams": lanes,
            "final": {"command": command, "timeout_seconds": final.get("timeout_seconds", FINAL_TIMEOUT_DEFAULT),
                      "allow_apply": final.get("allow_apply") is True, "skip": final.get("skip") is True},
            "lane_timeout_seconds": value.get("lane_timeout_seconds", LANE_TIMEOUT_DEFAULT)}


def campaign_dir(ctx, campaign_id):
    if not re.fullmatch(r"camp-[a-z0-9-]{1,60}", str(campaign_id)):
        raise ValueError("Invalid campaign identity")
    return safe_path(ctx.data_root / "campaigns" / campaign_id)


def _snapshot_engine(ctx, source=None):
    """Copy the engine so a campaign can develop the engine itself without touching the code that is running.

    `source` lets a long-lived supervisor snapshot the real (possibly just-updated) source instead of its own copy."""
    if FROZEN:  # the packaged executable is already an immutable copy of the engine
        return _engine_dir()
    source = Path(source).resolve() if source else Path(__file__).resolve().parents[1]  # the package
    files = sorted(p for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(source)).encode() + path.read_bytes())
    target = safe_path(ctx.data_root / "engine" / digest.hexdigest()[:12])
    if not (target / "respected_orchestrator").is_dir():
        shutil.copytree(source, target / "respected_orchestrator", ignore=shutil.ignore_patterns("__pycache__"))
    return target


def _engine_dir():
    """Folder that holds the running engine: src/ of a source checkout, or the packaged executable's folder."""
    return Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[2]


# How a master (or the user) runs this engine's CLI; the packaged build has no Python in front of it.
ENGINE_CLI = subprocess.list2cmdline(engine_command()) if FROZEN else "python -m respected_orchestrator"


def _engine_env(root):
    return dict(os.environ, PYTHONPATH=str(root), RESPECTED_ORCH_DELEGATED="1")  # masters/workers must not re-enter the MCP front


def create_campaign(ctx, request):
    spec = _spec(request, roles.read_settings(ctx.data_root))
    campaign_id = f"camp-{dt.datetime.now(dt.timezone.utc):%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    directory = campaign_dir(ctx, campaign_id)
    directory.mkdir(parents=True, exist_ok=False)
    _save(ctx, directory / "campaign.json", dict(spec, campaign_id=campaign_id, created_at=_now()))
    return campaign_id, directory


def start_campaign(ctx, request):
    campaign_id, directory = create_campaign(ctx, request)
    engine = _snapshot_engine(ctx)
    command = engine_command("--data-root", str(ctx.data_root),
               "campaign-run", campaign_id)
    pid = lanes._spawn_detached(command, engine, directory / "supervisor.log", env=_engine_env(engine))
    _save(ctx, directory / "supervisor.json", dict(campaign_id=campaign_id, pid=pid, engine=str(engine)))
    return dict(campaign_id=campaign_id, status="started", pid=pid)


def campaign_status(ctx, campaign_id):
    directory = campaign_dir(ctx, campaign_id)
    result = _load(ctx, directory / "result.json") if (directory / "result.json").is_file() else None
    events = []
    if (directory / "events.jsonl").is_file():
        events = [json.loads(line) for line in (directory / "events.jsonl").read_text(encoding="utf8").splitlines() if line]
    supervisor = _load(ctx, directory / "supervisor.json") if (directory / "supervisor.json").is_file() else {}
    alive = lanes._pid_is_alive(supervisor.get("pid", -1)) if supervisor else False
    return dict(campaign_id=campaign_id, status=(result or {}).get("status", "running" if alive else "interrupted"),
                result=result, events=events, supervisor_alive=alive)


def _mirror_ignore(_directory, names):
    directory = Path(_directory)
    return [n for n in names if n in _MIRROR_SKIP or _MIRROR_SECRET.match(n)
            or ((directory / n).is_file() and (directory / n).stat().st_size > _MIRROR_MAX_BYTES)]


def _prepare_project(source, mirror):
    """Non-Git sources are developed in a throwaway Git mirror; the verified patch is applied back to the source."""
    if (source / ".git").exists():
        return source
    with _MIRROR_LOCK:  # concurrent lanes racing on git init/commit left half-built mirrors
        _build_mirror(source, mirror)
    return mirror


def _build_mirror(source, mirror):
    if not (mirror / ".git").exists():
        if mirror.exists():
            shutil.rmtree(mirror)  # partial mirror from an interrupted attempt
        shutil.copytree(source, mirror, ignore=_mirror_ignore)
        base = ["git", "-c", "core.autocrlf=false", "-c", "user.name=Respected Mirror",
                "-c", "user.email=mirror@invalid.local"]
        for args in (["init", "-b", "main"], ["add", "-A"], ["commit", "-m", "mirror baseline"]):
            done = winproc.run([*base, *args], cwd=mirror, capture_output=True, timeout=300)
            if done.returncode:
                raise RuntimeError(f"mirror git {args[0]} failed: {done.stderr.decode(errors='replace')[-300:]}")


def _maf_lane(lane_ctx, run_id, timeout, main_root=None):
    """Real lane: a separate process runs the whole MAF pipeline for one run in its own data root."""
    engine = _engine_dir()
    command = engine_command("--data-root", str(lane_ctx.data_root), "maf", run_id)
    env = _engine_env(engine)
    if main_root is not None:  # lanes hold no settings.json or memory token; the child resolves them from here
        env["RESPECTED_ORCH_MAIN_ROOT"] = str(main_root)
    completed = execute(command, engine, timeout, env=env, scrub_env=True)
    lines = [line for line in completed.stdout.splitlines() if line.strip().startswith("{")]
    if not lines:
        return {"status": "FAILED", "reason": "maf_no_output", "error": completed.stderr[-500:]}
    return json.loads(lines[-1])


def _lane_summary(name, lane_ctx, output):
    attempts = output.get("attempts", [])
    last = (attempts[-1].get("engine_result") or {}) if attempts else {}
    reason = output.get("reason")
    generic = reason
    if reason in (None, "worker_failed") and output.get("status") != "MASTER_APPROVED" and output.get("final_run_id"):
        try:  # MAF labels every incomplete worker 'worker_failed'; the signed run status knows the cause (scope_violation, test_failed ...)
            signed = _load(lane_ctx, lane_ctx.run_dir(output["final_run_id"]) / "status.json")
        except (OSError, ValueError):
            signed = {}
        if signed.get("run_id") != output["final_run_id"]:
            signed = {}
        reason = "/".join(str(part) for part in (signed.get("reason") or signed.get("status"),
                                                 signed.get("worker_incomplete")) if part)
    reason = reason or generic
    if reason is None and output.get("status") != "MASTER_APPROVED":  # every non-approved lane must name a reason
        reason = last.get("reason") or output.get("status") or "unknown"
    return dict(name=name, status=output.get("status"), reason=reason,
                final_run_id=output.get("final_run_id"), lane_data_root=str(lane_ctx.data_root),
                changed_files=last.get("changed_files", []), attempts=len(attempts),
                implementers=[a.get("implementer") for a in attempts],
                reviews=[{k: r.get(k) for k in ("decision", "stage", "profile", "model", "reason")}
                         for r in output.get("reviews", [])],
                token_usage=output.get("token_usage"), token_usage_status=output.get("usage_status"),
                unknown_usage_steps=output.get("unknown_usage_steps"), token_budget=output.get("token_budget"))


def _final_prompt(spec, directory, lanes, engine, project_review=False):
    apply_hint = f"{ENGINE_CLI} --data-root <lane_data_root> apply <final_run_id>"
    permission = ("You may run exactly that command for approved lanes." if spec["final"]["allow_apply"]
                  else "You are not permitted to run it; tell the user which commands to run.")
    states = []
    for lane in lanes:
        label = lane.get("name") or lane.get("phase")
        if lane.get("applied"):
            states.append(f"{label}: already applied and verified; do not run apply for it")
        elif lane.get("status") == "MASTER_APPROVED":
            states.append(f"{label}: approved but not applied; to apply it run {apply_hint}")
        else:
            states.append(f"{label}: {lane.get('status')}; do not apply")
    verdict = ("End with exactly one line 'VERDICT: APPROVED|CHANGES REQUIRED|BLOCKED' followed by evidence-based findings."
               if project_review else "End with a short verdict per lane and whether a new cycle is needed.")
    roots = (f"Source roots you may read (applied lane output is there): {', '.join(spec['roots'])}. " if spec.get("roots") else "")
    return (
        "You are the Claude Master. The campaign you planned has finished; all evidence below is verified by the "
        "orchestrator (signed results, deterministic acceptance, independent model review). Do not poll or wait.\n"
        f"Goal (the authority for what counts as done; judge every lane against it): {spec['goal']}\n"
        f"{roots}Lanes: {json.dumps(lanes, ensure_ascii=True)}\nLane state: " + "; ".join(states) + "\n"
        "Decide per lane: accept, or request another bounded development cycle with exact reasons. A lane may only "
        "be applied when status is MASTER_APPROVED (HUMAN_APPROVAL_REQUIRED needs the user). "
        f"Applying an approved but not yet applied lane: run {apply_hint}. {permission} "
        "Applying leaves a working-tree change only; never commit. " + verdict
    )[:24000]


def run_campaign(ctx, campaign_id, lane_runner=None):
    directory = campaign_dir(ctx, campaign_id)
    spec = _load(ctx, directory / "campaign.json")
    if (directory / "result.json").is_file():
        result = _load(ctx, directory / "result.json")
        _start_final_master(ctx, directory, spec, result["lanes"])  # no-op once claimed
        return result
    timeout = spec["lane_timeout_seconds"]
    lane_runner = lane_runner or (lambda lane_ctx, run_id: _maf_lane(lane_ctx, run_id, timeout, ctx.data_root))
    lock, finished, summaries = threading.Lock(), {}, {}
    for lane in spec["workstreams"]:
        finished[lane["name"]] = threading.Event()

    def event(kind, **fields):
        with lock, (directory / "events.jsonl").open("a", encoding="utf8") as handle:
            handle.write(json.dumps(dict(event=kind, at=_now(), **fields), ensure_ascii=True) + "\n")

    def run_lane(lane):
        name = lane["name"]
        lane_ctx = EngineContext(directory / "lanes" / name)
        try:
            resume = lane.get("resume_lane_data_root")
            if resume:  # review-only retry: continue the SAME lane (run, patch, evidence and history are kept in place)
                root = safe_path(Path(resume))
                if not root.is_relative_to(safe_path(ctx.data_root / "campaigns")) or not (root / "lane.json").is_file():
                    raise ValueError("resume_lane_data_root must be an existing lane of this data root")
                lane_ctx = EngineContext(root)
            for dependency in lane.get("after", []):
                finished[dependency].wait()
                if summaries[dependency]["status"] != "MASTER_APPROVED":
                    summaries[name] = dict(name=name, status="SKIPPED", reason=f"dependency {dependency} not approved")
                    return
            record = lane_ctx.data_root / "lane.json"
            if record.is_file():
                done = _load(lane_ctx, record)
            else:
                request = dict(lane["request"])
                source = Path(request["project_root"])
                request["project_root"] = str(_prepare_project(source, directory / "mirrors" / name))
                if request["project_root"] != str(source):
                    request["apply_root"] = str(source)
                request.setdefault("master", "claude")
                done = {"run_id": create_task(lane_ctx, request, settings=roles.read_settings(ctx.data_root), main_root=ctx.data_root,
                                                   history=lambda: _track_record(ctx))["run_id"]}
                _save(lane_ctx, record, done)
            event("lane.started", lane=name, run_id=done["run_id"], resumed=bool(resume))
            output = lane_runner(lane_ctx, done["run_id"])
            summaries[name] = _lane_summary(name, lane_ctx, output)
        except Exception as error:  # a broken lane must never stop the others or the final review
            summaries[name] = dict(name=name, status="FAILED", reason="lane_error", error=str(error)[:500])
        finally:
            event("lane.completed", lane=name, status=summaries[name]["status"])
            finished[name].set()

    threads = [threading.Thread(target=run_lane, args=(lane,)) for lane in spec["workstreams"]]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()  # blocks until completion; nothing polls
    lanes = [summaries[lane["name"]] for lane in spec["workstreams"]]
    approved = all(lane["status"] == "MASTER_APPROVED" for lane in lanes)
    result = dict(campaign_id=campaign_id, status="LANES_APPROVED" if approved else "LANES_NEED_REVIEW",
                  lanes=lanes, completed_at=_now())
    _save(ctx, directory / "result.json", result)
    event("campaign.completed", status=result["status"])
    _start_final_master(ctx, directory, spec, lanes)
    return result


def _start_final_master(ctx, directory, spec, lanes, project_review=False):
    """Completion event: exactly one new master process is started with the verified results."""
    if spec["final"].get("skip"):
        return
    try:
        descriptor = os.open(directory / "final.claim", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    except FileExistsError:
        return
    engine = _engine_dir()
    prompt = _final_prompt(spec, directory, lanes, engine, project_review)
    command = [part.replace("{prompt}", prompt) for part in spec["final"]["command"]]
    if Path(command[0]).stem.casefold() == "claude" and "--permission-mode" not in command:
        # Unattended but bounded: dontAsk denies anything not allow-listed instead of prompting or bypassing.
        tools = ["Read", "Glob", "Grep"]
        if spec["final"]["allow_apply"]:  # opt-in: only the engine's own CLI (which re-verifies evidence) may run
            tools += [f"Bash({ENGINE_CLI}:*)", f"PowerShell({ENGINE_CLI}:*)"]
        command[1:1] = ["--permission-mode", "dontAsk", "--allowedTools", *tools,
                         *[arg for root in spec.get("roots", []) for arg in ("--add-dir", root)]]
    try:
        # Trusted master: keeps its own login environment and is not marked as an orchestrated worker.
        completed = execute(command, directory, spec["final"]["timeout_seconds"], mark_child=False,
                            env=_engine_env(engine))
        outcome = dict(status="COMPLETE" if completed.returncode == 0 else "FAILED", returncode=completed.returncode)
        (directory / "final-review.md").write_text(tool_result(Path(command[0]).stem.casefold(), completed.stdout)[0], encoding="utf8")
        (directory / "final-review.err.log").write_text(completed.stderr[-4000:], encoding="utf8")
    except Exception as error:
        outcome = dict(status="BLOCKED", error=str(error)[:500])
    _save(ctx, directory / "final.json", dict(outcome, finished_at=_now()))
    with (directory / "events.jsonl").open("a", encoding="utf8") as handle:
        handle.write(json.dumps(dict(event="master.finished", at=_now(), **outcome)) + "\n")
