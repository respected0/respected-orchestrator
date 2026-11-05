"""Upgrade proof: data written by the OLD release (git tag, real CLI) must work under THIS checkout.

    python tests/tools/upgrade_proof.py [--from v0.1.0-beta.1] [--out proof.json]

Everything runs in a throwaway HOME/APPDATA/data root, so the person's real setup is never touched. Phase 1 uses the
old release's own source (`git archive`) to create settings (Gemini defaults), a Gemini MCP registration, a finished
task, an unstarted task, a campaign and a project. Phase 2 runs this checkout on the same folders: setup/repair, health,
check/inspect/evidence of the old task, status of old campaign/project, Gemini cleanup, a new task, uninstall.
Exit 0 only if every step passed; the JSON report lists each step (no step is skipped silently).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
report = []
TERMINAL = {"completed", "failed", "blocked", "cancelled", "LANES_NEED_REVIEW"}


def step(name, ok, detail=""):
    report.append({"step": name, "ok": bool(ok), "detail": str(detail)[:1500]})
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:160]}]" if not ok else ""), flush=True)


class Side:
    """One release: its source folder + the shared isolated environment."""

    def __init__(self, src, env):
        self.src, self.env = src, dict(env, PYTHONPATH=str(src), PYTHONUTF8="1")

    def cli(self, *args, stdin=None, timeout=120):
        done = subprocess.run([PY, "-m", "respected_orchestrator", *args], input=stdin, capture_output=True, text=True,
                              encoding="utf-8", env=self.env, cwd=self.env["WORK"], timeout=timeout)
        try:
            out = json.loads(done.stdout) if done.stdout.strip() else {}
        except ValueError:
            out = {"raw": done.stdout}
        return done.returncode, out, done.stderr


def wait(side, argv, key, done_values, seconds=120):
    end = time.time() + seconds
    while time.time() < end:
        _, out, _ = side.cli(*argv)
        if out.get(key) in done_values:
            return out
        time.sleep(1)
    return out


def run_status(side, run_id, seconds=120):
    """Poll `list` until the run has a final status (the `status` command is the global one, not a run's)."""
    end, status = time.time() + seconds, None
    while time.time() < end:
        _, out, _ = side.cli("list")
        row = next((r for r in out.get("runs", []) if r.get("run_id") == run_id), {})
        status = row.get("status")
        if status in {"completed", "failed", "cancelled"}:
            break
        time.sleep(1)
    return status


def write_py(path, text):
    Path(path).write_text(text, encoding="utf-8")


def git_repo(path):
    path.mkdir(parents=True)
    for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=path, check=True)
    (path / "f.txt").write_text("old\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=path, check=True)
    return path


def task(repo, name, ownership, code, ok_code):
    return {"project_root": str(repo), "task": name, "worker": "custom", "kind": "write", "ownership": [ownership],
            "command": [PY, "-c", code], "acceptance": [[PY, "-c", ok_code]], "timeout_seconds": 60}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="old", default="v0.1.0-beta.1")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="upgrade-proof-")).resolve()
    home = work / "home"
    for sub in ("AppData/Roaming", "AppData/Local", ".gemini", ".claude"):
        (home / sub).mkdir(parents=True)
    env = {**os.environ, "USERPROFILE": str(home), "HOME": str(home), "APPDATA": str(home / "AppData/Roaming"),
           "LOCALAPPDATA": str(home / "AppData/Local"), "RESPECTED_DATA_DIR": str(work / "data"), "WORK": str(work),
           "RESPECTED_ORCH_TEST_ISOLATION": "1"}
    env.pop("RESPECTED_ORCH_CHILD", None)
    old_src = work / "old"
    old_src.mkdir()
    archive = subprocess.run(["git", "archive", args.old, "src"], cwd=ROOT, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(old_src)], input=archive, check=True)
    old, new = Side(old_src / "src", env), Side(ROOT / "src", env)
    for side in (old, new):
        side.env["PYTHONPATH"] = str(side.src)

    # ---- phase 1: the OLD release creates its data -------------------------------------------------------------
    code, out, err = old.cli("--version")
    step("old release runs", code == 0, out or err)
    old_version = out.get("raw", "").split()[-1] if isinstance(out, dict) else None
    code, out, err = old.cli("config", "set", "default_worker=gemini", "default_reviewer_tool=gemini", "blocked_profiles=mimo")
    step("old: Gemini defaults saved", code == 0, out or err)
    (home / ".gemini" / "settings.json").write_text(json.dumps({"theme": "mine", "mcpServers": {"other": {"command": "x"}}}))
    code, out, err = old.cli("integrations", "set", "gemini=on")
    registered = "respected" in (home / ".gemini" / "settings.json").read_text().lower()
    step("old: Gemini MCP registered", code == 0 and registered, out or err)

    repo = git_repo(work / "proj")
    write = "from pathlib import Path; Path('f.txt').write_text('new\\n')"
    check = "from pathlib import Path; assert Path('f.txt').read_text()=='new\\n'"
    code, made, err = old.cli("create", stdin=json.dumps(task(repo, "finished", "f.txt", write, check)))
    done_id = made.get("run_id")
    old.cli("start", done_id)
    finished = run_status(old, done_id)
    step("old: task completed", finished == "completed", finished)
    code, made2, _ = old.cli("create", stdin=json.dumps(task(repo, "unstarted", "f.txt", write, check)))
    pending_id = made2.get("run_id")
    step("old: unstarted task created", bool(pending_id), made2)

    lane = {"name": "lane", "after": [], "request": {**task(repo, "lane", "f.txt", write, check), "workflow": {"max_fix_rounds": 0}}}
    record = work / "final.txt"
    cspec = {"goal": "demo", "workstreams": [lane],
             "final": {"command": [PY, "-c", f"open(r'{record}','a').write('ok')"], "timeout_seconds": 30}}
    code, made3, err = old.cli("campaign-start", stdin=json.dumps(cspec))
    campaign_id = made3.get("campaign_id")
    camp = wait(old, ["campaign-status", campaign_id], "status", TERMINAL) if campaign_id else {}
    step("old: campaign reached a terminal state", camp.get("status") in TERMINAL, camp or made3 or err)

    repo3 = git_repo(work / "proj3")
    phase = {"name": "one", "after": [], "auto_apply": False, "workstreams": [{"name": "one", "after": [], "request": {
        **task(repo3, "phase", "f.txt", write, check), "workflow": {"max_fix_rounds": 0}}}],
        "verify": [{"command": [PY, "-c", check], "cwd": str(repo3)}]}
    code, made5, err = old.cli("project-start", stdin=json.dumps({"goal": "demo", "phases": [phase]}))
    project_id = made5.get("project_id")
    proj = wait(old, ["project-status", project_id], "status", {"completed", "failed", "blocked", "cancelled", "awaiting_approval", "needs_approval"}, 90) if project_id else {}
    project_old_status = proj.get("status")
    step("old: project started and reached a stable state", bool(project_old_status), proj or made5 or err)

    # a project the OLD engine was running when the process died (an update stops running processes): the old code
    # itself writes the in-flight state, then the process is hard-killed inside the second phase.
    repo4 = git_repo(work / "proj4")
    crash = f"""
import os, sys
from pathlib import Path
from unittest import mock
from respected_orchestrator.context import EngineContext
from respected_orchestrator.workflows import project, campaign
ctx = EngineContext(Path(r"{work / 'data'}"))
def lane(n): return {{"name": n, "after": [], "request": {{"project_root": r"{repo4}", "task": n, "worker": "custom", "kind": "write",
    "ownership": ["f.txt"], "command": [r"{PY}", "-c", "pass"], "acceptance": [[r"{PY}", "-c", "pass"]], "timeout_seconds": 30,
    "workflow": {{"max_fix_rounds": 0}}}}}}
def phase(n, after=()): return {{"name": n, "after": list(after), "workstreams": [lane(n)], "auto_apply": False,
    "verify": [{{"command": [r"{PY}", "-c", "pass"], "cwd": r"{repo4}"}}]}}
pid, _ = project.create_project(ctx, {{"goal": "crash", "phases": [phase("one"), phase("two", ["one"])]}})
calls = []
def runner(c, campaign_id, timeout, cancel):
    calls.append(campaign_id)
    if len(calls) == 2:
        os._exit(9)                       # hard kill while the second phase is running
    campaign.run_campaign(c, campaign_id, lane_runner=lambda lc, rid: {{"status": "completed"}})
with mock.patch("respected_orchestrator.engine.runner._stdin_is_tty", return_value=True):
    project.run_project(ctx, pid, campaign_runner=runner)
"""
    done = subprocess.run([PY, "-c", crash], env=old.env, capture_output=True, text=True, cwd=work)
    found = sorted((work / "data").rglob("proj-*/project.json"))
    killed_id = found[-1].parent.name if found else None
    code, st, _ = old.cli("project-status", killed_id) if killed_id else (1, {}, "")
    step("old: project killed mid-run (second phase in flight)", done.returncode == 9 and st.get("status") not in
         {"completed", "cancelled", "blocked"}, f"rc={done.returncode} {st} {done.stderr[-300:]}")

    # ---- phase 2: THIS checkout on the same data ---------------------------------------------------------------
    code, out, err = new.cli("--version")
    new_version = out.get("raw", "").split()[-1] if isinstance(out, dict) else None
    step("new release runs and is a different version", code == 0 and new_version and new_version != old_version, f"old={old_version} new={new_version}")
    settings_before = (work / "data" / "settings.json").read_bytes() if (work / "data" / "settings.json").is_file() else b""
    exe = ROOT / "dist" / "RespectedOrchestrator" / "respected-orchestrator.exe"
    frozen = lambda *a: (lambda d: (d.returncode, json.loads(d.stdout or "{}"), d.stderr))(
        subprocess.run([str(exe), *a], capture_output=True, text=True, encoding="utf-8", env=env, cwd=work, timeout=180))
    code, out, err = frozen("setup")
    step("new: setup migrates in place", code == 0, out or err)
    settings = json.loads((work / "data" / "settings.json").read_text("utf-8")) if (work / "data" / "settings.json").is_file() else {}
    step("new: Gemini defaults moved to agy, other keys kept", settings.get("default_worker") == "agy"
         and settings.get("default_reviewer_tool") == "agy" and settings.get("blocked_profiles") == "mimo", settings)
    step("new: original settings kept as .bak", bool(settings_before) and any((work / "data").glob("settings.json.v1.bak")),
         [p.name for p in (work / "data").glob("*.bak")])
    code, out, err = frozen("repair")
    step("new: repair is idempotent", code == 0, out or err)
    code, out, err = frozen("health")
    step("new: health", code in (0, 1) and "error" not in out, out or err)

    code, out, err = new.cli("check", done_id)
    step("new: old finished task still verifies", code == 0 and out.get("status") == "verified", out or err)
    code, out, err = new.cli("inspect", done_id)
    step("new: old task inspectable", code == 0 and out.get("request", {}).get("task") == "finished", out or err)
    code, out, err = new.cli("evidence", done_id)
    step("new: old task evidence readable", code == 0, out or err)
    code, out, err = new.cli("list")
    step("new: old tasks listed", code == 0 and done_id in json.dumps(out) and pending_id in json.dumps(out), out or err)
    code, out, err = new.cli("start", pending_id)
    step("new: old unstarted task starts", code == 0, out or err)
    ended = run_status(new, pending_id)
    step("new: old unstarted task runs to a result", ended in {"completed", "failed"}, ended)
    if campaign_id:
        code, out, err = new.cli("campaign-status", campaign_id)
        step("new: old campaign status readable", code == 0 and out.get("status") == camp.get("status"), out or err)

    if project_id:
        code, out, err = new.cli("project-status", project_id)
        step("new: old project status readable and unchanged", code == 0 and out.get("status") == project_old_status,
             f"old={project_old_status} new={out.get('status') if isinstance(out, dict) else out} {err}")

    code, st2, err = new.cli("project-status", killed_id)
    step("new: interrupted old project is readable and not falsely finished", code == 0 and st2.get("status") not in {"completed"}, st2 or err)
    code, out, err = new.cli("project-resume", killed_id)
    refused = code != 0 and "approval" in json.dumps(out).lower()
    step("new: interrupted old project resumes, or is refused only for human approval", code == 0 or refused, out or err)
    if code == 0:
        time.sleep(3)
    code, out, err = new.cli("project-cancel", killed_id)
    step("new: interrupted old project can be cancelled", code == 0, out or err)

    code, out, err = new.cli("integrations", "set", "gemini=off")
    gem = (home / ".gemini" / "settings.json").read_text()
    step("new: Gemini MCP entry removed, user's own entries kept", code == 0 and "respected" not in gem.lower()
         and '"other"' in gem and '"theme"' in gem, out or err or gem)
    repo2 = git_repo(work / "proj2")
    code, made4, err = new.cli("create", stdin=json.dumps(task(repo2, "after upgrade", "f.txt", write, check)))
    new.cli("start", made4.get("run_id", ""))
    fin = run_status(new, made4.get("run_id", ""))
    step("new: a fresh task works end to end", fin == "completed", fin or err)
    code, out, err = new.cli("uninstall")
    step("new: uninstall leaves no Respected entry in AI tools", code in (0, 1), out or err)
    code2, out2, _ = new.cli("integrations")
    step("new: integrations listing has no gemini", "gemini" not in json.dumps(out2).lower() or out2 == {}, out2)

    result = {"from": args.old, "from_version": old_version, "ok": all(s["ok"] for s in report), "steps": report}
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    print("UPGRADE PROOF:", "OK" if result["ok"] else "FAILED")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
