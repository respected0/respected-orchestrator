"""Independent roots, link checks and atomic state (standard library only)."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile


def safe_path(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        try:
            metadata = part.lstat()
        except FileNotFoundError:
            continue
        if part.is_symlink() or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Link/reparse target refused: {part}")
    return path


def path_within_root(path: Path, root: Path) -> bool:
    try:
        return safe_path(path).is_relative_to(safe_path(root))
    except (OSError, ValueError):
        return False


def atomic_write_json(path: Path, payload) -> None:
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def default_data_root() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Respected/RespectedOrchestrator/data"   # one Respected folder for the whole ecosystem
    elif __import__("sys").platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "RespectedOrchestrator"


@dataclass(frozen=True)
class EngineContext:
    data_root: Path

    def __post_init__(self):
        if not self.data_root.is_absolute():
            raise ValueError("Data root must be absolute")
        object.__setattr__(self, "data_root", safe_path(self.data_root))

    @property
    def paths(self):
        return self

    @property
    def app_root(self):
        package_parent = Path(__file__).resolve().parents[1]
        return package_parent.parent if package_parent.name == 'src' else package_parent

    @property
    def state_dir(self):
        return self.data_root / "state"

    @property
    def workspace_root(self):
        return self.data_root / "workspaces"

    def run_dir(self, run_id: str) -> Path:
        import re
        if not isinstance(run_id, str) or not re.fullmatch(r"run-[a-z0-9-]{1,100}", run_id):
            raise ValueError("Invalid run identity")
        return safe_path(self.state_dir / run_id)


def validate_project(ctx: EngineContext, project_root: Path) -> Path:
    if not project_root.is_absolute():
        raise ValueError("Project must be an explicit absolute directory")
    project = safe_path(project_root)
    if not project.is_dir():
        raise ValueError("Project does not exist")
    for forbidden in (ctx.app_root, ctx.data_root):
        if project.is_relative_to(forbidden) or forbidden.is_relative_to(project):
            raise ValueError("Project must be separate from program and technical data")
    return project
