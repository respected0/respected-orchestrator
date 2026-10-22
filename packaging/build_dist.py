"""Build the packaged Orchestrator: one self-contained folder that needs no Python on the machine.

    python packaging/build_dist.py [--output DIR]   ->   DIR/RespectedOrchestrator/{respected-orchestrator.exe, app/, distribution.json}

PyInstaller onedir build of the private JSON entry point (RPP, MCP, task/campaign/project commands); distribution.json
lists every file with its sha256 so the installer (the Hub) and the product's own install record can verify the copy.
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
    closure, queue = set(), ["respected-orchestrator"]
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


def build(output: Path) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = ROOT / "build"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
        "--contents-directory", "app", "--name", NAME,
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
    files = {path.relative_to(app).as_posix(): sha256(path) for path in sorted(app.rglob("*"))
             if path.is_file() and path.name != "distribution.json"}
    document = {"schema_version": 1, "product": "orchestrator", "version": source_version(),
                "platform": "windows" if os.name == "nt" else sys.platform, "launcher": LAUNCHER, "files": files}
    (app / "distribution.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    print(build(parser.parse_args().output))
