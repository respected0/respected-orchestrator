"""Build the packaged Orchestrator: one self-contained folder that needs no Python on the machine.

    python packaging/build_dist.py [--output DIR] [--desktop EXE]   ->   DIR/RespectedOrchestrator/{respected-orchestrator.exe, [respected-orchestrator-desktop.exe], app/, distribution.json}

PyInstaller onedir build of the private JSON entry point (RPP, MCP, task/campaign/project commands); distribution.json
lists every file with its sha256 so the installer and the product's own install record can verify the copy.
Windows only for now; build on the platform you ship.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = "RespectedOrchestrator"
LAUNCHER = "respected-orchestrator.exe" if os.name == "nt" else "respected-orchestrator"


def source_version() -> str:
    """The version of the source being frozen (not of whatever copy happens to be pip-installed)."""
    from packaging.version import Version
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return str(Version(re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)))  # the PEP 440 form the package metadata reports


def foreign_modules() -> list[str]:
    """Top-level modules of installed distributions outside the engine's declared dependency closure.

    The Agent Framework imports optional integrations behind try/except; PyInstaller follows them into whatever the build
    machine happens to have installed (boto, numpy, grpc...). Excluding everything outside the closure makes a local build
    contain the same as a clean CI build."""
    from importlib import metadata
    name = lambda raw: re.split(r"[ ;\[<>=!~(]", raw.strip(), maxsplit=1)[0].lower().replace("_", "-")
    closure, queue = set(), ["respected-orchestrator", "pywin32"]  # pywin32: DPAPI key vault, imported lazily
    while queue:
        current = queue.pop()
        if current in closure:
            continue
        closure.add(current)
        try:
            requires = metadata.requires(current) or []
        except metadata.PackageNotFoundError:
            continue
        queue.extend(name(r) for r in requires if "extra ==" not in r and "extra==" not in r)
    def tops(dist):
        listed = (dist.read_text("top_level.txt") or "").split()
        return set(listed) or {Path(f).parts[0].removesuffix(".py") for f in dist.files or [] if not str(f).startswith("..")
                               and not Path(f).parts[0].endswith((".dist-info", ".egg-info", ".pth", ".data")) and Path(f).parts[0] != "__pycache__"}
    needed, excluded = {"respected_orchestrator"}, set()
    for dist in metadata.distributions():
        (needed if name(dist.metadata["Name"] or "") in closure else excluded).update(t for t in tops(dist) if t.isidentifier())
    return sorted(excluded - needed)  # a namespace shared with a needed package (opentelemetry) stays in


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


DESKTOP = "respected-orchestrator-desktop.exe"


def write_distribution(app: Path, *, desktop: bool) -> dict:
    """distribution.json for the folder as it is now: every file's sha256, plus the shell's name when it is shipped (ADR-025)."""
    files = {path.relative_to(app).as_posix(): sha256(path) for path in sorted(app.rglob("*"))
             if path.is_file() and path.name != "distribution.json"}
    document = {"schema_version": 1, "product": "orchestrator", "version": source_version(),
                "platform": "windows" if os.name == "nt" else sys.platform, "launcher": LAUNCHER, "files": files}
    if desktop:
        document["desktop"] = DESKTOP
    (app / "distribution.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document


def attach_desktop(app: Path, exe: Path) -> dict:
    """Put the desktop shell next to the engine launcher and rewrite distribution.json so one hash chain covers both."""
    exe = Path(exe)
    if not exe.is_file():
        raise FileNotFoundError(f"desktop executable not found: {exe}")
    if not (app / LAUNCHER).is_file():
        raise FileNotFoundError(f"{app} is not a built engine folder (no {LAUNCHER})")
    shutil.copy2(exe, app / DESKTOP)
    return write_distribution(app, desktop=True)


def audit(app: Path) -> list[str]:
    """Manifest audit: what is wrong between distribution.json and the folder. An empty list means the chain is consistent."""
    problems = []
    try:
        document = json.loads((app / "distribution.json").read_text(encoding="utf-8"))
        files = document["files"]
        if not isinstance(files, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
            raise ValueError("files must map names to hashes")
    except (OSError, ValueError, KeyError, TypeError):
        return ["distribution.json is missing or unreadable"]
    if document.get("schema_version") != 1 or document.get("product") != "orchestrator":
        problems.append("distribution.json is not a schema 1 orchestrator manifest")
    on_disk = {path.relative_to(app).as_posix() for path in app.rglob("*") if path.is_file() and path.name != "distribution.json"}
    for name in sorted(on_disk - set(files)):
        problems.append(f"not in the manifest: {name}")
    for name, expected in sorted(files.items()):
        path = app / name
        if not path.is_file():
            problems.append(f"missing: {name}")
        elif sha256(path) != expected:
            problems.append(f"hash mismatch: {name}")
    if document.get("launcher") not in files:
        problems.append("the launcher is not in the manifest")
    shell = document.get("desktop")
    if shell is not None and shell not in files:
        problems.append("the desktop shell is named but not hashed")
    if shell is None and DESKTOP in files:
        problems.append("the desktop shell is hashed but not named")
    return problems


def build(output: Path, desktop: Path | None = None, freeze: bool = True) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not freeze:
        app = output / NAME
        if desktop:
            attach_desktop(app, desktop)
        else:
            write_distribution(app, desktop=False)
        return app
    work = ROOT / "build"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
        "--contents-directory", "app", "--name", NAME,
        *(["--icon", str(ROOT / "packaging/windows/icon.ico")] if os.name == "nt" else []),
        "--distpath", str(output), "--workpath", str(work / "frozen"), "--specpath", str(work),
        "--paths", str(ROOT / "src"),
        "--collect-submodules", "respected_orchestrator", "--copy-metadata", "respected-orchestrator",
        "--collect-submodules", "agent_framework", "--copy-metadata", "agent-framework-core",  # lazy imports: static analysis misses them
        "--add-data", str(ROOT / "src/respected_orchestrator/resources") + os.pathsep + "respected_orchestrator/resources",
        *[arg for module in foreign_modules() for arg in ("--exclude-module", module)],
        str(ROOT / "packaging/entrypoint.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    app = output / NAME
    built = app / (NAME + (".exe" if os.name == "nt" else ""))
    built.replace(app / LAUNCHER)
    write_distribution(app, desktop=False)
    if desktop:
        attach_desktop(app, desktop)
    shutil.rmtree(work, ignore_errors=True)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--desktop", type=Path, help="the built desktop shell to ship next to the engine launcher (ADR-025)")
    parser.add_argument("--no-freeze", action="store_true", help="skip PyInstaller: reuse the existing folder and only (re)write the manifest / attach the shell")
    parser.add_argument("--audit", action="store_true", help="only check distribution.json against the folder and exit non-zero on any problem")
    arguments = parser.parse_args()
    if arguments.audit:
        found = audit(arguments.output.resolve() / NAME)
        print(json.dumps({"problems": found}, ensure_ascii=False))
        sys.exit(1 if found else 0)
    print(build(arguments.output, arguments.desktop, freeze=not arguments.no_freeze))
