"""Windows child processes without console windows.

Why: engine supervisors run detached (no console of their own); on Windows every console program such a process
starts (git, python, icacls, cmd...) otherwise gets its OWN new, visible console window. Every spawn in this package
goes through here, so the flags exist in exactly one place. Hiding the window never hides output, errors or exit codes:
pipes, return codes and timeouts behave exactly as before."""
import os
import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def hidden_options(creationflags: int = 0) -> dict:
    """Popen/run keyword arguments that start a child without a visible window (empty on non-Windows)."""
    if os.name != "nt":
        return {}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": creationflags | NO_WINDOW, "startupinfo": info}


def run(*args, **kwargs):
    """subprocess.run with a hidden window; flags the caller already chose are kept."""
    options = hidden_options(kwargs.pop("creationflags", 0))
    for key, value in options.items():
        kwargs.setdefault(key, value)
    return subprocess.run(*args, **kwargs)
