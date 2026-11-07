"""Prepare a GitHub release: version check, installer, SHA256SUMS.txt and the `gh` commands. Uploads only with --yes.

    python packaging/release.py [--skip-build] [--repo OWNER/NAME] [--yes]

Without --yes nothing leaves the machine: the script builds, hashes and prints the commands it would run.
Update model: users run the new installer from the GitHub release; there is no catalog, key or updater.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILT = DIST / "RespectedOrchestrator-Windows-Setup.exe"
NOTES = ROOT / "packaging" / "windows" / "UPDATE_NOTES.md"
DEFAULT_REPO = "respected0/respected-orchestrator"


def pep440(version: str) -> str:
    from packaging.version import Version
    return str(Version(version))


def versions() -> dict[str, str]:
    """Every place the version is written, in the form each one uses."""
    def grab(path: str, pattern: str) -> str:
        return re.search(pattern, (ROOT / path).read_text("utf-8"), re.M).group(1)
    return {
        "pyproject.toml": grab("pyproject.toml", r'^version\s*=\s*"([^"]+)"'),
        "__init__.py": grab("src/respected_orchestrator/__init__.py", r'^__version__\s*=\s*"([^"]+)"'),
        "orchestrator_setup.iss": grab("packaging/windows/orchestrator_setup.iss", r'#define AppVersion "([^"]+)"'),
        "desktop/package.json": json.loads((ROOT / "desktop/package.json").read_text("utf-8"))["version"],
        "desktop/Cargo.toml": grab("desktop/src-tauri/Cargo.toml", r'^version\s*=\s*"([^"]+)"'),
        "desktop/tauri.conf.json": json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text("utf-8"))["version"],
    }


def check_versions() -> str:
    found = versions()
    if len({pep440(v) for v in found.values()}) != 1:
        sys.exit("version mismatch: " + json.dumps(found, indent=1))
    return found["pyproject.toml"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true", help="reuse dist/RespectedOrchestrator-Windows-Setup.exe")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--yes", action="store_true", help="really create the GitHub release (otherwise only print)")
    args = parser.parse_args()
    version = check_versions()
    if not args.skip_build:
        subprocess.run([sys.executable, "-B", str(ROOT / "packaging" / "build_installer.py")], cwd=ROOT, check=True)
    if not BUILT.is_file():
        sys.exit(f"{BUILT} is missing; run without --skip-build")
    out = DIST / "release"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    installer = out / f"Respected-Orchestrator-{version}-Windows-x64-Setup.exe"
    shutil.copyfile(BUILT, installer)
    sums = out / "SHA256SUMS.txt"
    sums.write_bytes(f"{hashlib.sha256(installer.read_bytes()).hexdigest()} *{installer.name}\n".encode("ascii"))
    tag = f"v{version}"
    create = ["gh", "release", "create", tag, str(installer), str(sums), "--repo", args.repo,
              "--title", f"Respected Orchestrator {version}", "--notes-file", str(NOTES)]
    if "-" in version or re.search(r"(a|b|rc)\d", version):
        create.append("--prerelease")
    print(f"installer: {installer}\nchecksums: {sums}\n" + sums.read_text("ascii"))
    print("gh command:\n  " + subprocess.list2cmdline(create))
    if not args.yes:
        print("dry run: nothing uploaded (pass --yes to run the command above)")
        return
    subprocess.run(create, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
