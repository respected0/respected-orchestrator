"""FIX-04 toolchain compatibility probe through the production path (engine.sandbox.run_check), network denied.

Run from the repository root: python docs/evidence/poc/fix04_toolchain2_probe.py > docs/evidence/poc/fix04_toolchain2_results.json
Each command also runs unwrapped (control) so "works" and "does not work" are comparable. Not a test: it measures what is installed.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from respected_orchestrator.context import EngineContext
from respected_orchestrator.engine import sandbox

CASES = {
    "pytest": [sys.executable, "-m", "pytest", "--version"],
    "pip": [sys.executable, "-m", "pip", "--version"],
    "pip_list": [sys.executable, "-m", "pip", "list", "--disable-pip-version-check"],
    "venv_create": [sys.executable, "-m", "venv", "v"],
    "compileall": [sys.executable, "-m", "compileall", "-q", "."],
    "ruff": [sys.executable, "-m", "ruff", "--version"],
    "mypy": [sys.executable, "-m", "mypy", "--version"],
    "gcc": [shutil.which("gcc") or "gcc", "--version"],
    "go": [shutil.which("go") or "go", "version"],
    "cargo": [shutil.which("cargo") or "cargo", "--version"],
    "dotnet": [shutil.which("dotnet") or "dotnet", "--version"],
    "tsc": [shutil.which("tsc") or "tsc", "--version"],
    "git": [shutil.which("git") or "git", "--version"],
}

root = Path(tempfile.mkdtemp(prefix="orch-fix04-tc-")).resolve()
ctx = EngineContext(root / "data")
work = ctx.data_root / "workspaces" / "lane"
work.mkdir(parents=True)
(work / "a.py").write_text("x = 1\n", encoding="utf-8")
results = {}
for name, command in CASES.items():
    control = subprocess.run(command, cwd=work, capture_output=True, text=True, errors="replace") if shutil.which(command[0]) or Path(command[0]).exists() else None
    if control is None:
        results[name] = {"control": "not installed"}
        continue
    entry = {"control": control.returncode}
    try:
        done, network = sandbox.run_check(ctx, command, work, 120, task_id="probe", scratch=root / "scratch")
        entry["appcontainer"] = done.returncode
        entry["tail"] = (done.stdout + done.stderr).strip()[-160:]
    except sandbox.SandboxError as error:
        entry["appcontainer"] = "refused"
        entry["tail"] = str(error)[:160]
    results[name] = entry
print(json.dumps({"python": sys.version.split()[0], "results": results}, indent=2, ensure_ascii=False))
