"""Windows AppContainer worker launcher: no inherited user access, no silent fallback."""
import ctypes
import io
import msvcrt
import os
import subprocess
import sys
import time
import uuid
from ctypes import wintypes as w
from pathlib import Path

from . import winproc
from .worker_policy import SandboxStartError


_userenv = ctypes.WinDLL("userenv", use_last_error=True)
_advapi = ctypes.WinDLL("advapi32", use_last_error=True)
_kernel = ctypes.WinDLL("kernel32", use_last_error=True)
_msvcrt = ctypes.WinDLL("msvcrt")


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", w.DWORD)]


class _SecurityCapabilities(ctypes.Structure):
    _fields_ = [("AppContainerSid", ctypes.c_void_p), ("Capabilities", ctypes.POINTER(_SidAndAttributes)),
                ("CapabilityCount", w.DWORD), ("Reserved", w.DWORD)]


class _StartupInfo(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR),
                ("dwX", w.DWORD), ("dwY", w.DWORD), ("dwXSize", w.DWORD), ("dwYSize", w.DWORD),
                ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
                ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
                ("lpReserved2", ctypes.c_void_p), ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE),
                ("hStdError", w.HANDLE)]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [("StartupInfo", _StartupInfo), ("lpAttributeList", ctypes.c_void_p)]


class _ProcessInformation(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [("nLength", w.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p), ("bInheritHandle", w.BOOL)]


_userenv.CreateAppContainerProfile.argtypes = [w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, ctypes.c_void_p, w.DWORD,
                                               ctypes.POINTER(ctypes.c_void_p)]
_userenv.CreateAppContainerProfile.restype = ctypes.c_long
_userenv.DeleteAppContainerProfile.argtypes = [w.LPCWSTR]
_userenv.DeleteAppContainerProfile.restype = ctypes.c_long
_advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)]
_advapi.ConvertSidToStringSidW.restype = w.BOOL
_advapi.ConvertStringSidToSidW.argtypes = [w.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
_advapi.ConvertStringSidToSidW.restype = w.BOOL
_advapi.FreeSid.argtypes = [ctypes.c_void_p]
_kernel.LocalFree.argtypes = [w.HANDLE]
_advapi.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
_advapi.OpenProcessToken.restype = w.BOOL
_advapi.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD,
                                        ctypes.POINTER(w.DWORD)]
_advapi.GetTokenInformation.restype = w.BOOL
_kernel.GetCurrentProcess.restype = w.HANDLE
_kernel.CreatePipe.argtypes = [ctypes.POINTER(w.HANDLE), ctypes.POINTER(w.HANDLE),
                               ctypes.POINTER(_SecurityAttributes), w.DWORD]
_kernel.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL, w.DWORD,
                                   ctypes.c_void_p, w.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(_ProcessInformation)]
_kernel.CreateProcessW.restype = w.BOOL
_kernel.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, w.DWORD, w.DWORD,
                                                      ctypes.POINTER(ctypes.c_size_t)]
_kernel.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.c_size_t, ctypes.c_void_p,
                                              ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
_kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
_kernel.ResumeThread.argtypes = [w.HANDLE]
_kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
_kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
_kernel.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
_kernel.CloseHandle.argtypes = [w.HANDLE]
_kernel.SetHandleInformation.argtypes = [w.HANDLE, w.DWORD, w.DWORD]
_kernel.SetHandleInformation.restype = w.BOOL
_kernel.GetLastError = ctypes.get_last_error
_msvcrt._open_osfhandle.argtypes = [ctypes.c_void_p, ctypes.c_int]
_msvcrt._open_osfhandle.restype = ctypes.c_int


def _error(what, code=None):
    return SandboxStartError(f"{what}: {ctypes.WinError(ctypes.get_last_error() if code is None else code)}")


def _is_elevated():
    """True when the current token is elevated (UAC). The worker boundary is not supported there."""
    if os.name != "nt":
        return False
    token = w.HANDLE()
    # TOKEN_QUERY; GetCurrentProcess() pseudo-handle is -1.
    if not _advapi.OpenProcessToken(_kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise _error("OpenProcessToken failed")
    try:
        elevated = w.DWORD()
        size = w.DWORD()
        if not _advapi.GetTokenInformation(token, 20, ctypes.byref(elevated), ctypes.sizeof(elevated),
                                           ctypes.byref(size)):  # TokenElevation
            raise _error("GetTokenInformation failed")
        return bool(elevated.value)
    finally:
        _kernel.CloseHandle(token)


class AppContainerProcess:
    def __init__(self, pid, handle, stdin, stdout, stderr, profile, sid, grants):
        self.pid, self._handle, self.stdout, self.stderr = pid, handle, stdout, stderr
        self.stdin = stdin
        self.returncode = None
        self._profile, self._sid, self._grants = profile, sid, grants

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        if _kernel.WaitForSingleObject(self._handle, 0) == 0:
            code = w.DWORD()
            _kernel.GetExitCodeProcess(self._handle, ctypes.byref(code))
            self.returncode = code.value
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            if _kernel.WaitForSingleObject(self._handle, w.INFINITE if timeout is None else max(0, int(timeout * 1000))) != 0:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            self.poll()
        return self.returncode

    def kill(self):
        if self.poll() is None:
            _kernel.TerminateProcess(self._handle, 1)

    def close(self):
        if getattr(self, "_closed", False):
            return
        self._closed = True
        if self._handle:
            _kernel.CloseHandle(self._handle)
            self._handle = None
        for stream in (self.stdin, self.stdout, self.stderr):
            if stream is None:
                continue
            try:
                stream.close()
            except OSError:
                pass
        for path in self._grants:
            winproc.run([winproc.system_tool("icacls"), str(path), "/remove", f"*{self._sid}"],
                        capture_output=True)
        if self._profile:
            _userenv.DeleteAppContainerProfile(self._profile)
        self._profile = None


def _sid_string(sid):
    text = w.LPWSTR()
    if not _advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        raise _error("ConvertSidToStringSidW failed")
    try:
        return text.value
    finally:
        _kernel.LocalFree(ctypes.cast(text, w.HANDLE))


def _grant(path, sid, rights):
    result = winproc.run([winproc.system_tool("icacls"), str(path), "/grant", f"*{sid}:{rights}"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise SandboxStartError(f"ACL grant failed for {path}: {(result.stderr or result.stdout).strip()[:300]}")


# Read-only toolchains are shared by every worker profile, so one grant (not one per
# worker) keeps spawn under a second. Any AppContainer can read these paths; they are
# executables and libraries only, never the engine data root.
_SHARED_TOOLCHAIN = "S-1-15-2-1"
_shared_granted = set()

# Network opt-in is enforced before spawn by runner.worker_network_mode: a task prompt cannot
# reach this path. OpenCode ACP is a single stdio process; it needs provider egress only.
_NETWORK_CAPABILITIES = ("S-1-15-3-1",)  # internetClient


def _grant_toolchain(path):
    key = str(Path(path).resolve()).casefold()
    if key in _shared_granted:
        return
    check = winproc.run([winproc.system_tool("icacls"), str(path), "/findsid", f"*{_SHARED_TOOLCHAIN}"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "SID Found:" in check.stdout:
        _shared_granted.add(key)
        return
    _grant(path, _SHARED_TOOLCHAIN, "(OI)(CI)RX")
    _shared_granted.add(key)


def _inside_toolchain(path):
    prefix = Path(sys.prefix).resolve()
    path = Path(path).resolve()
    return path == prefix or path.is_relative_to(prefix) or _shared_readable(path)


def _shared_readable(path):
    """True when ALL APPLICATION PACKAGES can already read the path (Program Files tools): no ACL change, and none possible without admin."""
    check = winproc.run([winproc.system_tool("icacls"), str(path), "/findsid", f"*{_SHARED_TOOLCHAIN}"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return "SID Found:" in check.stdout


def _pipe():
    attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), None, True)
    read, write = w.HANDLE(), w.HANDLE()
    if not _kernel.CreatePipe(ctypes.byref(read), ctypes.byref(write), ctypes.byref(attributes), 0):
        raise _error("CreatePipe failed")
    return read, write


def _parent_handle(handle):
    """Keep the engine side out of the child's inherited handle set.

    A child that inherits the write end of its own stdin pipe never observes EOF when the
    engine closes that end.  Interactive ACP workers wait for EOF after their final turn.
    """
    if not _kernel.SetHandleInformation(handle, 0x1, 0):  # HANDLE_FLAG_INHERIT
        raise _error("SetHandleInformation failed")
    return handle


def _text_stream(handle):
    value = handle.value if hasattr(handle, "value") else handle
    if isinstance(value, bytes):
        value = int.from_bytes(value, "little")
    fd = msvcrt.open_osfhandle(int(value), os.O_RDONLY)
    return io.TextIOWrapper(io.FileIO(fd, "r", closefd=True), encoding="utf-8", errors="replace", newline="")


def _binary_writer(handle):
    value = handle.value if hasattr(handle, "value") else handle
    if isinstance(value, bytes):
        value = int.from_bytes(value, "little")
    fd = msvcrt.open_osfhandle(int(value), os.O_WRONLY)
    return io.TextIOWrapper(io.FileIO(fd, "w", closefd=True), encoding="utf-8", errors="strict",
                            newline="\n", write_through=True)


def _environment_block(environment):
    entries = [f"{key}={value}" for key, value in environment.items() if "\x00" not in key + value]
    entries.sort(key=str.casefold)
    return ctypes.create_unicode_buffer("\x00".join(entries) + "\x00\x00")


def spawn(command, cwd, environment, *, allowed_roots, readonly_roots, network_mode, job, interactive=False):
    """Start one AppContainer process. Any setup failure raises before a process exists."""
    if os.name != "nt":
        raise SandboxStartError("AppContainer is only available on Windows")
    try:
        elevated = _is_elevated()
    except SandboxStartError as error:
        raise SandboxStartError(f"unsupported_elevated: session cannot be verified: {error}") from error
    if elevated:
        raise SandboxStartError("unsupported_elevated: the worker boundary is not enforced in an elevated session")
    profile = "RespectedOrchestratorWorker" + uuid.uuid4().hex[:12]
    sid_value = ctypes.c_void_p()
    result = _userenv.CreateAppContainerProfile(profile, profile, "Respected Orchestrator worker", None, 0,
                                                ctypes.byref(sid_value))
    if result != 0:
        raise SandboxStartError(f"CreateAppContainerProfile failed: {result & 0xffffffff:#x}")
    sid = _sid_string(sid_value)
    grants = []
    handles = []
    try:
        seen = set()
        writable = {Path(p).resolve() for p in allowed_roots}
        for path in [*allowed_roots, *readonly_roots]:
            path = Path(path).resolve()
            if path in seen:
                continue
            seen.add(path)
            if not path.exists():
                raise SandboxStartError(f"Worker root does not exist: {path}")
            if path in writable:
                _grant(path, sid, "(OI)(CI)M")
                grants.append(path)
            elif _inside_toolchain(path):
                _grant_toolchain(path)
            else:
                _grant(path, sid, "(OI)(CI)RX")
                grants.append(path)

        stdin_r, stdin_w = _pipe()
        stdout_r, stdout_w = _pipe()
        stderr_r, stderr_w = _pipe()
        _parent_handle(stdin_w)
        _parent_handle(stdout_r)
        _parent_handle(stderr_r)
        handles.extend([stdin_r, stdout_r, stderr_r])
        capability_sids = _NETWORK_CAPABILITIES if network_mode == "allow" else ()
        capabilities = (_SidAndAttributes * len(capability_sids))()
        capability_values = []
        for index, sid_text in enumerate(capability_sids):
            value = ctypes.c_void_p()
            if not _advapi.ConvertStringSidToSidW(sid_text, ctypes.byref(value)):
                raise _error(f"{sid_text} capability SID failed")
            capability_values.append(value)
            capabilities[index].Sid = value
            capabilities[index].Attributes = 0x4  # SE_GROUP_ENABLED
        security = _SecurityCapabilities(
            sid_value, capabilities if capability_values else None, len(capability_values), 0
        )

        size = ctypes.c_size_t()
        _kernel.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not _kernel.InitializeProcThreadAttributeList(buffer, 1, 0, ctypes.byref(size)):
            raise _error("InitializeProcThreadAttributeList failed")
        if not _kernel.UpdateProcThreadAttribute(buffer, 0, 0x00020009, ctypes.byref(security),
                                                 ctypes.sizeof(security), None, None):
            raise _error("UpdateProcThreadAttribute failed")
        startup = _StartupInfoEx()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput, startup.StartupInfo.hStdError = stdin_r, stdout_w, stderr_w
        startup.lpAttributeList = ctypes.addressof(buffer)
        info = _ProcessInformation()
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(part) for part in command]))
        block = _environment_block(environment)
        flags = 0x00080000 | 0x4 | 0x400 | 0x08000000  # EXTENDED_STARTUPINFO | SUSPENDED | UNICODE_ENV | NO_WINDOW
        if not _kernel.CreateProcessW(None, command_line, None, None, True, flags, block, str(cwd),
                                      ctypes.byref(startup), ctypes.byref(info)):
            raise _error("CreateProcessW failed")
        handles.extend([stdin_w, stdout_w, stderr_w])
        if job is not None and not _kernel.AssignProcessToJobObject(job.handle, info.hProcess):
            _kernel.TerminateProcess(info.hProcess, 1)
            raise _error("AssignProcessToJobObject failed")
        _kernel.ResumeThread(info.hThread)
        _kernel.CloseHandle(info.hThread)
        for handle in (stdin_r, stdout_w, stderr_w):
            _kernel.CloseHandle(handle)
            handles.remove(handle)
        if not interactive:
            _kernel.CloseHandle(stdin_w)
            handles.remove(stdin_w)
        handles.extend([info.hProcess])
        stdout = _text_stream(stdout_r)
        stderr = _text_stream(stderr_r)
        handles.remove(stdout_r)
        handles.remove(stderr_r)
        stdin = _binary_writer(stdin_w) if interactive else None
        process = AppContainerProcess(info.dwProcessId, info.hProcess, stdin, stdout, stderr, profile, sid, grants)
        handles.remove(info.hProcess)
        return process
    except Exception:
        for handle in handles:
            _kernel.CloseHandle(handle)
        for path in grants:
            winproc.run([winproc.system_tool("icacls"), str(path), "/remove", f"*{sid}"], capture_output=True)
        _userenv.DeleteAppContainerProfile(profile)
        raise
    finally:
        for capability in locals().get("capability_values", ()):
            if capability.value:
                _kernel.LocalFree(capability)
        _advapi.FreeSid(sid_value)
