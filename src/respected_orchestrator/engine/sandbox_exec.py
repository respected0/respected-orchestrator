"""Run one command under a restricted token (see sandbox.py). Windows only.

    respected-orchestrator.exe _sandbox-exec --sid S-1-5-21-... -- <command...>   (sandbox.py boots it from source otherwise)

Runs as the trusted user, builds the token, starts the command with this process's standard handles and returns its
exit code. The caller's job object (process-tree kill, timeouts) covers the child because job membership is inherited.
"""
import argparse
import ctypes
import subprocess
import sys
from ctypes import wintypes

advapi, kernel = ctypes.WinDLL("advapi32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)

TOKEN_ASSIGN_PRIMARY, TOKEN_DUPLICATE, TOKEN_QUERY = 0x1, 0x2, 0x8
DISABLE_MAX_PRIVILEGE = 0x1            # keeps only SeChangeNotifyPrivilege (traversal), so no backup/restore bypass of ACLs
SE_GROUP_ENABLED, SE_GROUP_LOGON_ID = 0x4, 0xC0000000
STARTF_USESTDHANDLES, STD_IN, STD_OUT, STD_ERR = 0x100, -10, -11, -12
CREATE_NO_WINDOW, CREATE_UNICODE_ENVIRONMENT = 0x08000000, 0x400


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD), ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
                ("hStdError", wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


def _fail(name):
    raise OSError(f"{name} failed: {ctypes.WinError(ctypes.get_last_error())}")


def _token_sids(token):
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    """Every SID the normal token has (user + enabled groups): restricting with all of them keeps access unchanged.
    Returns (sids, buffers); the buffers own the SID memory and must outlive the use of the SIDs."""
    def query(kind):
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, kind, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, kind, buffer, size, ctypes.byref(size)):
            _fail("GetTokenInformation")
        return buffer
    user, groups = query(1), query(2)                                             # TokenUser, TokenGroups
    count = wintypes.DWORD.from_buffer(groups, 0).value
    entries = (SID_AND_ATTRIBUTES * count).from_buffer(groups, ctypes.sizeof(ctypes.c_void_p))
    sids = [ctypes.c_void_p.from_buffer(user, 0).value]                           # TOKEN_USER starts with the SID pointer
    sids += [entry.Sid for entry in entries if entry.Attributes & (SE_GROUP_ENABLED | SE_GROUP_LOGON_ID)]
    return sids, (user, groups)


def restricted_token(sandbox_sid):
    advapi.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    base = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), TOKEN_ASSIGN_PRIMARY | TOKEN_DUPLICATE | TOKEN_QUERY, ctypes.byref(base)):
        _fail("OpenProcessToken")
    user_token_sids, keepalive = _token_sids(base)
    extra = ctypes.c_void_p()
    if not advapi.ConvertStringSidToSidW(sandbox_sid, ctypes.byref(extra)):
        _fail("ConvertStringSidToSidW")
    restrict = (SID_AND_ATTRIBUTES * (len(user_token_sids) + 1))()
    for index, sid in enumerate([*user_token_sids, extra.value]):
        restrict[index].Sid, restrict[index].Attributes = sid, 0
    new = wintypes.HANDLE()
    advapi.CreateRestrictedToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                             wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HANDLE)]
    if not advapi.CreateRestrictedToken(base, DISABLE_MAX_PRIVILEGE, 0, None, 0, None, len(restrict), restrict, ctypes.byref(new)):
        _fail("CreateRestrictedToken")
    return new, keepalive


def run(sandbox_sid, command):
    token, _keepalive = restricted_token(sandbox_sid)
    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    startup.dwFlags = STARTF_USESTDHANDLES
    kernel.GetStdHandle.restype = wintypes.HANDLE
    startup.hStdInput, startup.hStdOutput, startup.hStdError = (kernel.GetStdHandle(n) for n in (STD_IN, STD_OUT, STD_ERR))
    info = PROCESS_INFORMATION()
    advapi.CreateProcessAsUserW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, wintypes.BOOL,
                                            wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(STARTUPINFOW),
                                            ctypes.POINTER(PROCESS_INFORMATION)]
    line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
    if not advapi.CreateProcessAsUserW(token, None, line, None, None, True, CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT, None, None,
                                       ctypes.byref(startup), ctypes.byref(info)):
        _fail("CreateProcessAsUserW")
    kernel.CloseHandle(info.hThread)
    kernel.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
    code = wintypes.DWORD()
    kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    kernel.CloseHandle(info.hProcess)
    return code.value


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--sid", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("no command")
    sys.stdout.flush()
    return run(args.sid, command)
