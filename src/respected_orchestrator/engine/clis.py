"""Which worker CLIs sit on PATH. A health call needs every answer at once, and importing the whole runner for it costs more than the lookup."""
import os
from pathlib import Path
import shutil
import sys

SUPPORTED_AGENTS = ("claude", "gemini", "antigravity", "agy", "codex", "cursor", "custom")
EXECUTABLE = {"antigravity": "agy", "agy": "agy", "cursor": "cursor-agent"}
LOCAL_CODEX = Path(__file__).resolve().parents[3] / ".runtime" / "codex-0.162.0-alpha.20" / "bin" / "codex.exe"


def find(names):
    """name -> first matching file on PATH or None, in shutil.which order but with one folder listing per PATH entry (not one probe per name x extension)."""
    if sys.platform != "win32":
        return {name: shutil.which(name) for name in names}
    extensions = [ext.lower() for ext in os.environ.get("PATHEXT", ".EXE;.CMD;.BAT;.COM").split(";") if ext]
    found = dict.fromkeys(names)
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        folder = folder.strip('"')
        if not folder or all(found.values()):
            continue
        try:
            listing = {entry.name.lower(): entry.name for entry in os.scandir(folder)}
        except OSError:
            continue
        for name in names:
            for extension in extensions:
                hit = listing.get(name.lower() + extension)
                if not found[name] and hit:
                    found[name] = os.path.join(folder, hit)
    return found


def resolve(agents):
    """(agents whose CLI resolves, path of git or None): the same answers as runner.get_cli_command, in one pass."""
    names = {agent: EXECUTABLE.get(agent, agent) for agent in agents}
    found = find([*names.values(), "git"])
    usable = []
    for agent, name in names.items():
        if agent == "codex" and sys.platform == "win32" and LOCAL_CODEX.is_file():
            usable.append(agent)
        elif found[name] and Path(found[name]).suffix.lower() not in {".cmd", ".bat"}:  # a .cmd shim would re-parse the prompt (see runner.get_cli_command)
            usable.append(agent)
    return usable, found["git"]
