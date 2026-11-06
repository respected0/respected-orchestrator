"""B3-03.02 experiment (test-only, not shipped): an AppContainer process attached to a ConPTY pseudoconsole.

It mirrors engine.appcontainer.spawn (same profile, same ACL grants, same capability rules) and only adds the
PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE attribute. It never has an unsandboxed branch: any failure raises.
"""
import ctypes
import subprocess
import threading
import uuid
from ctypes import wintypes as w
from pathlib import Path

from respected_orchestrator.engine import appcontainer as ac
from respected_orchestrator.engine.worker_policy import SandboxStartError

K = ac._kernel


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


K.CreatePseudoConsole.argtypes = [COORD, w.HANDLE, w.HANDLE, w.DWORD, ctypes.POINTER(ctypes.c_void_p)]
K.CreatePseudoConsole.restype = ctypes.c_long
K.ResizePseudoConsole.argtypes = [ctypes.c_void_p, COORD]
K.ResizePseudoConsole.restype = ctypes.c_long
K.ClosePseudoConsole.argtypes = [ctypes.c_void_p]
K.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
K.WriteFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]


class PtyProcess:
    def __init__(self, base, hpc, in_w, out_r, cols, rows):
        self.base, self.hpc, self.in_w, self.out_r = base, hpc, in_w, out_r
        self.output = bytearray()
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self):
        buf = ctypes.create_string_buffer(65536)
        got = w.DWORD()
        while K.ReadFile(self.out_r, buf, 65536, ctypes.byref(got), None) and got.value:
            with self._lock:
                self.output += buf.raw[:got.value]

    def text(self):
        with self._lock:
            return bytes(self.output).decode("utf-8", "replace")

    def send(self, data: bytes):
        wrote = w.DWORD()
        if not K.WriteFile(self.in_w, data, len(data), ctypes.byref(wrote), None):
            raise OSError("pty write failed")

    def resize(self, cols, rows):
        if K.ResizePseudoConsole(self.hpc, COORD(cols, rows)) != 0:
            raise OSError("ResizePseudoConsole failed")

    def wait(self, timeout):
        return self.base.wait(timeout)

    def close(self):
        self.base.kill()
        if self.hpc:
            K.ClosePseudoConsole(self.hpc)
            self.hpc = None
        for h in (self.in_w, self.out_r):
            K.CloseHandle(h)
        self.base.close()


def spawn_pty(command, cwd, environment, *, allowed_roots, readonly_roots, network_mode, job=None, cols=100, rows=30):
    if ac._is_elevated():
        raise SandboxStartError("unsupported_elevated")
    profile = "RespectedPtyProbe" + uuid.uuid4().hex[:12]
    sid_value = ctypes.c_void_p()
    if ac._userenv.CreateAppContainerProfile(profile, profile, "pty probe", None, 0, ctypes.byref(sid_value)) != 0:
        raise SandboxStartError("CreateAppContainerProfile failed")
    sid = ac._sid_string(sid_value)
    grants, hpc, opened = [], ctypes.c_void_p(), []
    try:
        writable = {Path(p).resolve() for p in allowed_roots}
        for path in [*allowed_roots, *readonly_roots]:
            path = Path(path).resolve()
            if path in writable:
                ac._grant(path, sid, "(OI)(CI)M")
                grants.append(path)
            elif ac._inside_toolchain(path):
                ac._grant_toolchain(path)
            else:
                ac._grant(path, sid, "(OI)(CI)RX")
                grants.append(path)
        in_r, in_w = ac._pipe()
        out_r, out_w = ac._pipe()
        opened += [in_r, in_w, out_r, out_w]
        rc = K.CreatePseudoConsole(COORD(cols, rows), in_r, out_w, 0, ctypes.byref(hpc))
        if rc != 0:
            raise SandboxStartError(f"CreatePseudoConsole failed: {rc & 0xffffffff:#x}")
        caps_sids = ac._NETWORK_CAPABILITIES if network_mode == "allow" else ()
        caps = (ac._SidAndAttributes * len(caps_sids))()
        keep = []
        for i, text in enumerate(caps_sids):
            v = ctypes.c_void_p()
            ac._advapi.ConvertStringSidToSidW(text, ctypes.byref(v))
            keep.append(v)
            caps[i].Sid, caps[i].Attributes = v, 0x4
        security = ac._SecurityCapabilities(sid_value, caps if keep else None, len(keep), 0)
        size = ctypes.c_size_t()
        K.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
        attr = ctypes.create_string_buffer(size.value)
        if not K.InitializeProcThreadAttributeList(attr, 2, 0, ctypes.byref(size)):
            raise ac._error("InitializeProcThreadAttributeList failed")
        if not K.UpdateProcThreadAttribute(attr, 0, 0x00020009, ctypes.byref(security), ctypes.sizeof(security), None, None):
            raise ac._error("security attribute failed")
        if not K.UpdateProcThreadAttribute(attr, 0, 0x00020016, hpc, ctypes.sizeof(ctypes.c_void_p), None, None):
            raise ac._error("pseudoconsole attribute failed")
        startup = ac._StartupInfoEx()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        startup.lpAttributeList = ctypes.addressof(attr)
        # Finding (B3-03.02): without this the AppContainer child writes to the PARENT's stdout/stderr (leak outside the
        # PTY channel). Explicit USESTDHANDLES with null handles makes the pseudoconsole the only channel.
        startup.StartupInfo.dwFlags = 0x100
        info = ac._ProcessInformation()
        line = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(p) for p in command]))
        flags = 0x00080000 | 0x4 | 0x400  # EXTENDED_STARTUPINFO | SUSPENDED | UNICODE_ENVIRONMENT
        if not K.CreateProcessW(None, line, None, None, False, flags, ac._environment_block(environment), str(cwd),
                                ctypes.byref(startup), ctypes.byref(info)):
            raise ac._error("CreateProcessW (pty) failed")
        if job is not None and not K.AssignProcessToJobObject(job.handle, info.hProcess):
            K.TerminateProcess(info.hProcess, 1)
            raise ac._error("AssignProcessToJobObject failed")
        K.ResumeThread(info.hThread)
        K.CloseHandle(info.hThread)
        K.CloseHandle(in_r)
        K.CloseHandle(out_w)
        base = ac.AppContainerProcess(info.dwProcessId, info.hProcess, None, None, None, profile, sid, grants)
        return PtyProcess(base, hpc, in_w, out_r, cols, rows)
    except Exception:
        for h in opened:
            K.CloseHandle(h)
        if hpc.value:
            K.ClosePseudoConsole(hpc)
        for path in grants:
            ac.winproc.run([ac.winproc.system_tool("icacls"), str(path), "/remove", f"*{sid}"], capture_output=True)
        ac._userenv.DeleteAppContainerProfile(profile)
        raise
    finally:
        for v in locals().get("keep", ()):
            if v.value:
                K.LocalFree(v)
        ac._advapi.FreeSid(sid_value)
