"""Windows child processes without console windows.

Why: engine supervisors run detached (no console of their own); on Windows every console program such a process
starts (git, python, icacls, cmd...) otherwise gets its OWN new, visible console window. Every spawn in this package
goes through here, so the flags exist in exactly one place. Hiding the window never hides output, errors or exit codes:
pipes, return codes and timeouts behave exactly as before."""
import os
import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


_SYSTEM_TOOLS = {"powershell": r"System32\WindowsPowerShell\v1.0\powershell.exe",
                 "icacls": r"System32\icacls.exe"}


def system_tool(name: str) -> str:
    """Absolute path of a Windows system tool, so a trimmed or hijacked PATH can neither hide nor replace it."""
    root = os.environ.get("SystemRoot")
    if os.name == "nt" and root and name in _SYSTEM_TOOLS and os.path.isfile(os.path.join(root, _SYSTEM_TOOLS[name])):
        return os.path.join(root, _SYSTEM_TOOLS[name])
    return name


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


def popen(*args, **kwargs):
    """subprocess.Popen with a hidden window; flags the caller already chose are kept."""
    options = hidden_options(kwargs.pop("creationflags", 0))
    for key, value in options.items():
        kwargs.setdefault(key, value)
    return subprocess.Popen(*args, **kwargs)


def is_elevated() -> bool:
    """True when the current Windows token is elevated (UAC)."""
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes as w
    advapi, kernel = ctypes.WinDLL("advapi32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    advapi.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    advapi.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    token = w.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        elevated, size = w.DWORD(), w.DWORD()
        if not advapi.GetTokenInformation(token, 20, ctypes.byref(elevated), ctypes.sizeof(elevated), ctypes.byref(size)):  # TokenElevation
            raise ctypes.WinError(ctypes.get_last_error())
        return bool(elevated.value)
    finally:
        kernel.CloseHandle(token)
