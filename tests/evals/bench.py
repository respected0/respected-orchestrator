"""Real-agent benchmark: the same coding agent, model, task and start commit with and without the Orchestrator (FIX-02, ADR-019).

Separate from the synthetic harness in compare.py (which writes the golden fix and measures only the harness). Here the golden
fix never reaches the agent: it is not in the prompt, argv, environment or work tree (checked on every run), and only the hidden
acceptance command decides success. Anything not measured is the string "unknown", never 0.

    python -m tests.evals.bench plan  OUT.json [--tasks 10] [--repeat 3]
    python -m tests.evals.bench run   OUT.json --agent claude --model MODEL --confirm-free [--tasks 10] [--repeat 3]

`run` starts real agent calls. ADR-019: only a zero marginal cost agent/model, and the operator asks the user before each batch.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tests.evals import runner
from tests.evals.fixtures import Fixture, all_fixtures

SCHEMA = "respected.eval.bench.v1"
UNKNOWN = "unknown"
ARMS = ("direct", "orchestrated")
MIN_TASKS, MIN_REPEAT = 10, 3
QUOTA = re.compile(r"(?i)\b429\b|rate.?limit|quota|billing|insufficient.{0,20}(credit|fund)|payment required")


class BenchError(RuntimeError):
    pass


class ProviderMissing(BenchError):
    """Agent CLI not installed. Recorded as PROVIDER_MISSING; no result is invented."""


def unknown_usage(output):
    return {"tokens": UNKNOWN, "cost": UNKNOWN}


@dataclass(frozen=True)
class Agent:
    name: str
    model: str
    version: str
    direct: Callable[[str], list]                       # prompt -> argv, run in the plain work tree
    worker: str = "custom"                              # engine worker for the orchestrated arm
    orchestrated: Callable[[str], list] | None = None   # prompt -> argv, only for worker "custom"
    usage: Callable[[str], dict] = unknown_usage
    real: bool = False


def parse_claude_usage(stdout):
    """Only `modelUsage` is trusted (ADR-019); a missing or contradicting top-level usage means unknown."""
    try:
        data = json.loads(stdout)
        models = data["modelUsage"].values()
        tokens = sum(int(m["inputTokens"]) + int(m["outputTokens"]) for m in models)
        top = data.get("usage") or {}
        if top and (int(top.get("input_tokens", 0)) + int(top.get("output_tokens", 0))) not in (0, tokens):
            return {"tokens": UNKNOWN, "cost": UNKNOWN}
        return {"tokens": tokens, "cost": UNKNOWN}  # total_cost_usd is a list-price estimate, not money spent
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"tokens": UNKNOWN, "cost": UNKNOWN}


def real_agent(name, model, *, confirm_free=False):
    """Adapter for an installed CLI. Refuses without the free-path confirmation (ADR-019 §3) and when the CLI is absent."""
    if not confirm_free:
        raise BenchError("not_confirmed_free: pass --confirm-free only for a zero marginal cost agent/model")
    from respected_orchestrator.engine import clis
    found = clis.find([clis.EXECUTABLE.get(name, name)])[clis.EXECUTABLE.get(name, name)]
    exe = clis.worker_executable(name, found)
    if not exe:
        raise ProviderMissing(f"PROVIDER_MISSING: {name}")
    version = runner.subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30).stdout.strip() or UNKNOWN
    argv = {"claude": lambda p: [exe, "-p", p, "--model", model, "--output-format", "json", "--permission-mode", "acceptEdits"],
            "codex": lambda p: [exe, "exec", "--model", model, "--sandbox", "workspace-write", p],
            "opencode": lambda p: [exe, "run", "--model", model, p]}.get(name)
    if argv is None:
        raise BenchError(f"no direct adapter for {name}")
    return Agent(name, model, version, argv, worker=name, usage=parse_claude_usage if name == "claude" else unknown_usage, real=True)


def prompt_for(fixture: Fixture):
    return f"Fix the bug in solution.py so that test_solution.py passes. Task: {fixture.title}. Change only solution.py."


def select_tasks(count=MIN_TASKS):
    """Fixtures that meet the ADR-019 §6 criteria, measured: valid, stdlib only, baseline fails, golden passes, pinned start SHA."""
    chosen = []
    for fixture in all_fixtures():
        if runner.validate_fixture(fixture):
            continue
        imports = set(re.findall(r"(?m)^(?:from|import)\s+(\w+)", fixture.source + fixture.test)) - {"solution", "test_solution"}
        if not imports <= set(sys.stdlib_module_names):
            continue
        root = Path(tempfile.mkdtemp(prefix="orch-sel-"))
        try:
            sha = runner.build_repository(fixture, root)
            baseline = runner._execute(runner.COMMAND, root, 20)["returncode"]
            (root / "solution.py").write_text(fixture.fixed_source, encoding="utf-8", newline="\n")
            golden = runner._execute(runner.COMMAND, root, 20)["returncode"]
        finally:
            shutil.rmtree(root, ignore_errors=True)
        if sha == fixture.start_sha and baseline not in (0, None) and golden == 0:
            chosen.append(fixture)
    if len(chosen) < count:
        raise BenchError(f"only {len(chosen)} fixtures meet the criteria, {count} needed")
    return chosen[:count]


def make_plan(tasks, repeat=MIN_REPEAT, *, release=True):
    if release and (len(tasks) < MIN_TASKS or repeat < MIN_REPEAT):
        raise BenchError(f"a release plan needs >= {MIN_TASKS} tasks x >= {MIN_REPEAT} repeats")
    runs = [{"task_id": f.id, "arm": arm, "repeat": n} for f in tasks for n in range(1, repeat + 1) for arm in ARMS]
    return {"schema": SCHEMA + ".plan", "tasks": [f.id for f in tasks], "repeat": repeat, "runs": runs, "total_runs": len(runs)}


def assert_no_leak(fixture, argv, env, root):
    """The golden fix must not reach the agent through argv, environment or any file of the work tree."""
    golden = fixture.fixed_source.strip()
    haystacks = [" ".join(map(str, argv))] + [str(v) for v in env.values()]
    haystacks += [p.read_text("utf-8", "replace") for p in Path(root).rglob("*") if p.is_file() and ".git" not in p.parts and p.stat().st_size < 1_000_000]
    if any(golden in h for h in haystacks):
        raise BenchError("golden_leak")


def _acceptance(root, timeout):
    done = runner._execute(runner.COMMAND, root, timeout)
    return "timeout" if done["timeout"] else "passed" if done["returncode"] == 0 else "failed"


def _record(fixture, arm, repeat, start, status, started, usage, **extra):
    return {"task_id": fixture.id, "arm": arm, "repeat": repeat, "start_sha": start, "start_sha_matches": start == fixture.start_sha,
            "status": status, "duration_seconds": round(time.monotonic() - started, 3), "tokens": usage["tokens"], "cost": usage["cost"],
            "interventions": 0, "retries": 0, "security_violation": None, **extra}


def run_direct(agent, fixture, repeat, timeout):
    root = Path(tempfile.mkdtemp(prefix="orch-bench-d-"))
    started = time.monotonic()
    try:
        start = runner.build_repository(fixture, root)
        argv = agent.direct(prompt_for(fixture))
        try:
            assert_no_leak(fixture, argv, {}, root)
        except BenchError as error:
            return _record(fixture, "direct", repeat, start, "invalid", started, agent.usage(""), reason=str(error))
        done = runner._execute(argv, root, timeout)
        output = done["stdout"] + done["stderr"]
        usage = agent.usage(done["stdout"])
        if done["timeout"]:
            return _record(fixture, "direct", repeat, start, "timeout", started, usage)
        if QUOTA.search(output):
            return _record(fixture, "direct", repeat, start, "quota_stop", started, usage)
        if done["returncode"] != 0:  # a crashed agent (port clash, auth) is not evidence about the model
            return _record(fixture, "direct", repeat, start, "agent_error", started, usage, reason=output[-200:])
        return _record(fixture, "direct", repeat, start, _acceptance(root, timeout), started, usage)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_orchestrated(agent, fixture, repeat, timeout):
    from respected_orchestrator.context import EngineContext
    from respected_orchestrator.engine.runner import check_result, create_task, execute_task
    base = Path(tempfile.mkdtemp(prefix="orch-bench-o-"))
    started = time.monotonic()
    try:
        repo = base / "project"
        repo.mkdir()
        start = runner.build_repository(fixture, repo)
        request = dict(project_root=str(repo), task=prompt_for(fixture), worker=agent.worker, kind="write", ownership=["solution.py"],
                       acceptance=[runner.COMMAND], timeout_seconds=timeout)
        if agent.worker == "custom":
            request["command"] = agent.orchestrated(prompt_for(fixture))
        elif agent.worker in ("openrouter", "opencode"):
            request["worker_profile"] = agent.model
        try:
            assert_no_leak(fixture, request.get("command", []), {}, repo)
        except BenchError as error:
            return _record(fixture, "orchestrated", repeat, start, "invalid", started, agent.usage(""), reason=str(error))
        ctx = EngineContext(base / "data")
        run_id = create_task(ctx, request)["run_id"]
        result = execute_task(ctx, run_id)
        reason = result.get("reason")
        verified = result.get("status") == "completed" and check_result(ctx, run_id).get("status") == "verified"
        if QUOTA.search(json.dumps(result)):
            status = "quota_stop"
        else:
            status = "passed" if verified else "timeout" if reason == "timed_out" else "failed"
        return _record(fixture, "orchestrated", repeat, start, status, started, agent.usage(""), reason=reason or UNKNOWN,
                       security_violation=reason in ("scope_violation", "sandbox_unavailable"), run_id=run_id)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _sum(runs, key):
    values = [r[key] for r in runs]
    return UNKNOWN if not values or any(v == UNKNOWN for v in values) else sum(values)


def summarize(runs):
    out = {}
    for arm in ARMS:
        rows = [r for r in runs if r["arm"] == arm]
        out[arm] = {"runs": len(rows), "success_rate": round(sum(r["status"] == "passed" for r in rows) / len(rows), 4) if rows else UNKNOWN,
                    "timeouts": sum(r["status"] == "timeout" for r in rows), "invalid": sum(r["status"] == "invalid" for r in rows),
                    "interventions": sum(r["interventions"] for r in rows), "retries": sum(r["retries"] for r in rows),
                    "duration_seconds": round(sum(r["duration_seconds"] for r in rows), 3), "tokens": _sum(rows, "tokens"), "cost": _sum(rows, "cost"),
                    # Direct runs without a sandbox, so the counter is not measured there (ADR-019 §7).
                    "security_violations": sum(r["security_violation"] is True for r in rows) if arm == "orchestrated" else UNKNOWN}
    return out


def run_bench(agent, tasks, repeat, timeout=300.0, *, release=True, commit=UNKNOWN):
    make_plan(tasks, repeat, release=release)
    runs, status = [], "complete"
    for fixture in tasks:
        for n in range(1, repeat + 1):
            for arm, call in (("direct", run_direct), ("orchestrated", run_orchestrated)):
                result = call(agent, fixture, n, timeout)
                runs.append(result)
                if result["status"] == "quota_stop":  # ADR-019 §4: never push on after a quota or billing sign
                    status = "stopped_quota"
                    return report(agent, tasks, repeat, timeout, runs, status, commit)
    return report(agent, tasks, repeat, timeout, runs, status, commit)


def report(agent, tasks, repeat, timeout, runs, status, commit=UNKNOWN):
    return {"schema": SCHEMA, "kind": "real" if agent.real else "harness-test", "status": status, "commit": commit,
            "agent": {"name": agent.name, "model": agent.model, "version": agent.version},
            "environment": {k: v for k, v in runner._metadata().items()}, "timeout": timeout, "repeat": repeat,
            "task_ids": [f.id for f in tasks], "selection": "ADR-019 section 6: stdlib only, baseline fails, golden passes, pinned start sha",
            "golden_used": False, "runs": runs, "summary": summarize(runs)}


def validate(report_, *, release=True):
    """Problems that make a report unusable as release evidence. Empty list = acceptable."""
    problems = []
    if report_.get("schema") != SCHEMA:
        return ["wrong schema"]
    runs = report_.get("runs", [])
    if report_.get("status") != "complete":
        problems.append(f"status is {report_.get('status')!r}")
    if any(r.get("status") == "agent_error" for r in runs):
        problems.append("agent_error runs present: the agent did not run, rerun them")
    if report_.get("golden_used") is not False or any(r.get("status") == "invalid" for r in runs):
        problems.append("golden fix reached an agent or a run is invalid")
    if release and report_.get("kind") != "real":
        problems.append("not a real-agent report")
    tasks, repeat = report_.get("task_ids", []), report_.get("repeat", 0)
    if release and (len(tasks) < MIN_TASKS or repeat < MIN_REPEAT or len(runs) != len(tasks) * repeat * 2):
        problems.append("fewer than 10 tasks x 3 repeats x 2 arms")
    for field in ("commit", "environment", "agent"):
        if not report_.get(field) or (field == "commit" and report_[field] == UNKNOWN):
            problems.append(f"{field} not recorded")
    if any(r.get("tokens") == 0 or r.get("cost") == 0 for r in runs):
        problems.append("unmeasured value written as 0")
    return problems


def comparable(first, second):
    """Reports compare only when agent, model, version, timeout, repeat and tasks match."""
    for field in ("agent", "timeout", "repeat", "task_ids"):
        if first.get(field) != second.get(field):
            return f"incomparable:{field}"
    return "comparable"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "run"])
    parser.add_argument("out")
    parser.add_argument("--tasks", type=int, default=MIN_TASKS)
    parser.add_argument("--repeat", type=int, default=MIN_REPEAT)
    parser.add_argument("--agent")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--confirm-free", action="store_true")
    args = parser.parse_args(argv)
    tasks = select_tasks(args.tasks)
    if args.action == "plan":
        payload = make_plan(tasks, args.repeat)
    else:
        sha = runner.subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or UNKNOWN
        payload = run_bench(real_agent(args.agent, args.model, confirm_free=args.confirm_free), tasks, args.repeat, args.timeout, commit=sha)
    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{args.action}: wrote {args.out}", "; ".join(validate(payload)) if args.action == "run" else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
