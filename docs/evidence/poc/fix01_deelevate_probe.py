"""FIX-01 spike: can an elevated Windows process start a de-elevated child that the AppContainer boundary accepts?

    python docs/evidence/poc/fix01_deelevate_probe.py info
        prints the current token: elevation, elevation type, integrity level, Administrators group state
    python docs/evidence/poc/fix01_deelevate_probe.py run -- <command...>
        runs <command> with a RESTRICTED copy of the current token: Administrators becomes deny-only, all privileges
        except SeChangeNotify are removed and the integrity level is lowered to Medium. The child's exit code is returned.

Nothing here widens access: the child token is strictly weaker than the parent's. It does not touch any engine policy
(`appcontainer._is_elevated` is read, not changed).
"""
import ctypes
import json
import subprocess
import sys
from ctypes import wintypes

adv = ctypes.WinDLL("advapi32", use_last_error=True)
ker = ctypes.WinDLL("kernel32", use_last_error=True)
ker.GetCurrentProcess.restype = wintypes.HANDLE
ker.CloseHandle.argtypes = [wintypes.HANDLE]
adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
adv.SetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
adv.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
adv.CreateRestrictedToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HANDLE)]

TOKEN_ASSIGN_PRIMARY, TOKEN_DUPLICATE, TOKEN_QUERY, TOKEN_ADJUST_DEFAULT = 0x1, 0x2, 0x8, 0x80
DISABLE_MAX_PRIVILEGE = 0x1
TOKEN_ELEVATION_TYPE, TOKEN_ELEVATION, TOKEN_INTEGRITY, TOKEN_GROUPS = 18, 20, 25, 2
SID_ADMINS, SID_MEDIUM = "S-1-5-32-544", "S-1-16-8192"
SE_GROUP_USE_FOR_DENY_ONLY = 0x10
SE_GROUP_INTEGRITY = 0x20


class SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD)] + [(n, ctypes.c_void_p) for n in ("r", "d", "t")] + [
        (n, wintypes.DWORD) for n in ("x", "y", "xs", "ys", "xc", "yc", "fill", "flags")] + [
        ("show", wintypes.WORD), ("cb2", wintypes.WORD), ("r2", ctypes.c_void_p),
        ("hin", wintypes.HANDLE), ("hout", wintypes.HANDLE), ("herr", wintypes.HANDLE)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("pid", wintypes.DWORD), ("tid", wintypes.DWORD)]


def fail(name):
    raise OSError(f"{name}: {ctypes.WinError(ctypes.get_last_error())}")


def open_token(access):
    token = wintypes.HANDLE()
    if not adv.OpenProcessToken(ker.GetCurrentProcess(), access, ctypes.byref(token)):
        fail("OpenProcessToken")
    return token


def sid(text):
    value = ctypes.c_void_p()
    if not adv.ConvertStringSidToSidW(text, ctypes.byref(value)):
        fail("ConvertStringSidToSidW")
    return value


def query(token, kind):
    size = wintypes.DWORD()
    adv.GetTokenInformation(token, kind, None, 0, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    if not adv.GetTokenInformation(token, kind, buffer, size, ctypes.byref(size)):
        fail("GetTokenInformation")
    return buffer


def sid_text(pointer):
    out = wintypes.LPWSTR()
    adv.ConvertSidToStringSidW(pointer, ctypes.byref(out))
    return out.value


def describe(token):
    elevated = wintypes.DWORD.from_buffer(query(token, TOKEN_ELEVATION)).value
    kind = wintypes.DWORD.from_buffer(query(token, TOKEN_ELEVATION_TYPE)).value  # 1 default, 2 full, 3 limited
    label = query(token, TOKEN_INTEGRITY)
    integrity = sid_text(ctypes.c_void_p.from_buffer(label, 0).value)
    groups = query(token, TOKEN_GROUPS)
    count = wintypes.DWORD.from_buffer(groups, 0).value
    entries = (SidAndAttributes * count).from_buffer(groups, ctypes.sizeof(ctypes.c_void_p))
    admin = next((e.Attributes for e in entries if sid_text(e.Sid) == SID_ADMINS), None)
    return {
        "token_elevation": elevated,
        "token_elevation_type": {1: "default", 2: "full", 3: "limited"}.get(kind, kind),
        "integrity": integrity,
        "administrators_attributes": None if admin is None else hex(admin),
        "administrators_enabled": bool(admin is not None and not admin & SE_GROUP_USE_FOR_DENY_ONLY),
    }


def restricted_token():
    base = open_token(TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT)
    disable = (SidAndAttributes * 1)()
    disable[0].Sid = sid(SID_ADMINS)
    out = wintypes.HANDLE()
    if not adv.CreateRestrictedToken(base, DISABLE_MAX_PRIVILEGE, 1, disable, 0, None, 0, None, ctypes.byref(out)):
        fail("CreateRestrictedToken")
    label = SidAndAttributes()
    label.Sid, label.Attributes = sid(SID_MEDIUM), SE_GROUP_INTEGRITY
    if not adv.SetTokenInformation(out, TOKEN_INTEGRITY, ctypes.byref(label), ctypes.sizeof(label) + 16):
        fail("SetTokenInformation(integrity)")
    return out


def run(command):
    token = restricted_token()
    info, start = ProcessInfo(), StartupInfo()
    start.cb = ctypes.sizeof(start)
    line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
    if not adv.CreateProcessAsUserW(token, None, line, None, None, True, 0x400, None, None, ctypes.byref(start), ctypes.byref(info)):
        fail("CreateProcessAsUserW")
    ker.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
    code = wintypes.DWORD()
    ker.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    return code.value


if __name__ == "__main__":
    if sys.argv[1] == "info":
        print(json.dumps(describe(open_token(TOKEN_QUERY)), indent=2))
    else:
        sys.exit(run(sys.argv[sys.argv.index("--") + 1:]))
