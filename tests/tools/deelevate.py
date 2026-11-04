"""CI helper: run a command with a UAC-filtered (non-elevated) copy of this token. Windows only.

    python tests/tools/deelevate.py -- python -m unittest tests.engine.test_worker_security -v

GitHub's Windows runners are elevated and the worker boundary refuses elevated sessions, so the AppContainer
matrix has to run from the filtered token. The tests fail (not skip) when the child is still elevated.
"""
import ctypes
import msvcrt
import os
import subprocess
import tempfile
import sys
from ctypes import wintypes

from respected_orchestrator.engine import appcontainer, sandbox_exec as sx

LUA_TOKEN = 0x4


def main(command):
    sx.kernel.GetCurrentProcess.restype = wintypes.HANDLE
    sx.advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    base = wintypes.HANDLE()
    if not sx.advapi.OpenProcessToken(sx.kernel.GetCurrentProcess(),
                                      sx.TOKEN_ASSIGN_PRIMARY | sx.TOKEN_DUPLICATE | sx.TOKEN_QUERY, ctypes.byref(base)):
        sx._fail("OpenProcessToken")
    sx.advapi.CreateRestrictedToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                                ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HANDLE)]
    token = wintypes.HANDLE()
    if not sx.advapi.CreateRestrictedToken(base, LUA_TOKEN, 0, None, 0, None, 0, None, ctypes.byref(token)):
        sx._fail("CreateRestrictedToken")
    # The filtered token is medium integrity: cmd.exe/user32 cannot initialise under it on the runner (0xC0000142),
    # so start the command directly and give it a file as stdout, replayed afterwards (pipes are not reliably inherited).
    out = tempfile.NamedTemporaryFile(prefix="deelevate-", suffix=".log", delete=False)
    handle = msvcrt.get_osfhandle(out.fileno())
    os.set_handle_inheritable(handle, True)
    startup = sx.STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    startup.dwFlags = sx.STARTF_USESTDHANDLES
    startup.hStdInput, startup.hStdOutput, startup.hStdError = None, handle, handle
    info = sx.PROCESS_INFORMATION()
    sx.advapi.CreateProcessAsUserW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                               wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
                                               ctypes.POINTER(sx.STARTUPINFOW), ctypes.POINTER(sx.PROCESS_INFORMATION)]
    line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
    sys.stdout.flush()
    if not sx.advapi.CreateProcessAsUserW(token, None, line, None, None, True, sx.CREATE_NO_WINDOW | sx.CREATE_UNICODE_ENVIRONMENT,
                                          None, None, ctypes.byref(startup), ctypes.byref(info)):
        sx._fail("CreateProcessAsUserW")
    sx.kernel.CloseHandle(info.hThread)
    sx.kernel.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
    code = wintypes.DWORD()
    sx.kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    out.close()
    print(open(out.name, encoding="utf-8", errors="replace").read(), end="")
    print(f"deelevate: child exit code {code.value:#x}")
    return code.value


if __name__ == "__main__":
    argv = sys.argv[1:]
    argv = argv[1:] if argv[:1] == ["--"] else argv
    if argv[:2] == ["--check"]:  # child mode: report whether this token is elevated
        print("elevated" if appcontainer._is_elevated() else "limited")
        sys.exit(0)
    sys.exit(main(argv))
