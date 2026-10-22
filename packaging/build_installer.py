r"""Build dist/RespectedOrchestrator-Windows-Setup.exe (not Authenticode-signed) from the packaged distribution.

    python packaging/build_installer.py [--skip-dist]

Runs packaging/build_dist.py (PyInstaller onedir) unless --skip-dist, then compiles packaging/windows/orchestrator_setup.iss
with Inno Setup (set INNO_COMPILER when ISCC.exe is not on PATH or in %LOCALAPPDATA%\Programs\Inno Setup 6).
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def inno() -> str:
    for candidate in (os.environ.get("INNO_COMPILER"), shutil.which("ISCC.exe"),
                      str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe")):
        if candidate and Path(candidate).is_file():
            return candidate
    sys.exit("Inno Setup compiler (ISCC.exe) not found; set INNO_COMPILER")


def run(command):
    if subprocess.run(command, cwd=ROOT).returncode:
        sys.exit(f"failed: {' '.join(map(str, command))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-dist", action="store_true", help="reuse the existing dist/RespectedOrchestrator folder")
    args = parser.parse_args()
    if not args.skip_dist:
        run([sys.executable, "-B", str(ROOT / "packaging" / "build_dist.py"), "--output", str(DIST)])
    if not (DIST / "RespectedOrchestrator" / "respected-orchestrator.exe").is_file():
        sys.exit("dist/RespectedOrchestrator is missing; run without --skip-dist")
    version = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text("utf-8"), re.M).group(1)
    run([inno(), f"/DAppVersion={version}", f"/DStageDir={DIST / 'RespectedOrchestrator'}", f"/DOutputDir={DIST}",
         str(ROOT / "packaging" / "windows" / "orchestrator_setup.iss")])
    print(DIST / "RespectedOrchestrator-Windows-Setup.exe")
