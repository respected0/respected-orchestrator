"""REL-03: first-run health wizard shared by the CLI health output and the Hub (both read the same schema)."""
import sys
from pathlib import Path

_ACTIONS = {
    "data_root_writable": ("data_root_permissions", "Data klasörüne yazma izni verin.",
                           "RESPECTED_DATA_DIR'i yazılabilir bir klasöre yönlendirin"),
    "git_available": ("install_git", "Git'i kurun ve PATH'e ekleyin.", "git --version"),
    "worker_cli": ("install_or_sign_in_worker", "En az bir worker CLI kurun ve oturum açın.",
                   "codex --version"),
    "engine_key": ("repair_engine_key", "Bozuk .engine-key dosyasını kaldırıp repair çalıştırın.",
                   "respected-orchestrator repair"),
}


def sample_task():
    """A read-only first task: it never writes, never runs a worker, and needs no Hub."""
    return {"mode": "read", "writes": False, "prompt": "Repo kökündeki dosyaları listele ve hiçbir şeyi değiştirme."}


def guide(checks, data_root=None, hub_installed=False):
    steps = []
    for check in checks:
        if check.get("ok"):
            continue
        action, help_text, command = _ACTIONS.get(check.get("name"), ("inspect", "Kontrolü inceleyin.", "respected-orchestrator health"))
        steps.append({"check": check.get("name"), "action": action, "help": help_text, "command": command})
    locations = {"data": str(data_root)} if data_root else {}
    return {"hub_required": False, "hub_installed": bool(hub_installed), "steps": steps,
            "sample_task": sample_task(), "data_locations": locations,
            "uninstall": {"keeps_data": True, "purge_flag": "--purge"}}


def platform_hint():
    if sys.platform == "win32":
        return "Windows: kurulum yönetici izni istemez."
    return "Bu platform için yayın kararı ADR-008'e bağlıdır; desteklenmeyen güvenlik vaadi verilmez."