"""A Windows pseudo console (ConPTY, Windows 10 1809+) with one program running in it, through ctypes: no extra dependency.

The program sees a real terminal; we hold the two pipe ends: what it draws comes out of `read`, what a person types goes into `write`.
A pseudo console never opens a window, so this is the one spawn that does not go through winproc (ADR-035).
"""
from __future__ import annotations

import ctypes
import subprocess
from ctypes import wintypes as w

_PSEUDOCONSOLE = 0x00020016  # PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE
_EXTENDED_STARTUPINFO, _UNICODE_ENVIRONMENT, _STILL_ACTIVE = 0x00080000, 0x00000400, 259


class _Coord(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class _StartupInfo(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD),
                ("dwXSize", w.DWORD), ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
                ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [("StartupInfo", _StartupInfo), ("lpAttributeList", ctypes.c_void_p)]


class _ProcessInformation(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


def _kernel():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreatePipe.argtypes = [ctypes.POINTER(w.HANDLE), ctypes.POINTER(w.HANDLE), ctypes.c_void_p, w.DWORD]
    k.CreatePseudoConsole.argtypes = [_Coord, w.HANDLE, w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    k.CreatePseudoConsole.restype = ctypes.c_long
    k.ResizePseudoConsole.argtypes = [w.HANDLE, _Coord]
    k.ResizePseudoConsole.restype = ctypes.c_long
    k.ClosePseudoConsole.argtypes = [w.HANDLE]
    k.ClosePseudoConsole.restype = None
    k.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_size_t)]
    k.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
    k.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR,
                                 ctypes.POINTER(_StartupInfo), ctypes.POINTER(_ProcessInformation)]
    k.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
    k.WriteFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
    k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    k.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
    k.CloseHandle.argtypes = [w.HANDLE]
    return k


def _check(ok):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


class Pty:
    def __init__(self, argv, cwd, env, cols, rows):
        k = self._k = _kernel()
        in_read, self._in, self._out, out_write = w.HANDLE(), w.HANDLE(), w.HANDLE(), w.HANDLE()
        _check(k.CreatePipe(ctypes.byref(in_read), ctypes.byref(self._in), None, 0))
        _check(k.CreatePipe(ctypes.byref(self._out), ctypes.byref(out_write), None, 0))
        self._console = w.HANDLE()
        result = k.CreatePseudoConsole(_Coord(cols, rows), in_read, out_write, 0, ctypes.byref(self._console))
        k.CloseHandle(in_read)  # the pseudo console holds its own copies of these two ends
        k.CloseHandle(out_write)
        if result != 0:
            raise OSError(f"CreatePseudoConsole failed (0x{result & 0xFFFFFFFF:08x})")
        size = ctypes.c_size_t()
        k.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        self._attributes = ctypes.create_string_buffer(size.value)
        _check(k.InitializeProcThreadAttributeList(self._attributes, 1, 0, ctypes.byref(size)))
        _check(k.UpdateProcThreadAttribute(self._attributes, 0, _PSEUDOCONSOLE, self._console, ctypes.sizeof(w.HANDLE), None, None))
        startup = _StartupInfoEx()
        startup.StartupInfo.cb = ctypes.sizeof(_StartupInfoEx)
        startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES with empty handles: the program takes the pseudo console's, never our own redirected ones
        startup.lpAttributeList = ctypes.cast(self._attributes, ctypes.c_void_p)
        block = ctypes.create_unicode_buffer("".join(f"{name}={value}\0" for name, value in sorted(env.items())) + "\0")
        info = _ProcessInformation()
        try:
            _check(k.CreateProcessW(None, ctypes.create_unicode_buffer(subprocess.list2cmdline(argv)), None, None, False,
                                    _EXTENDED_STARTUPINFO | _UNICODE_ENVIRONMENT, block, str(cwd), ctypes.byref(startup.StartupInfo), ctypes.byref(info)))
        except OSError:
            self.close()
            raise
        k.CloseHandle(info.hThread)
        self._process, self.pid = info.hProcess, info.dwProcessId

    def read(self, size=1 << 16):
        """What the program drew since the last read; b"" once the pseudo console is closed. Blocks while there is nothing."""
        buffer, got = ctypes.create_string_buffer(size), w.DWORD()
        if not self._k.ReadFile(self._out, buffer, size, ctypes.byref(got), None):
            return b""
        return buffer.raw[:got.value]

    def write(self, data):
        done = w.DWORD()
        _check(self._k.WriteFile(self._in, data, len(data), ctypes.byref(done), None))

    def resize(self, cols, rows):
        if self._k.ResizePseudoConsole(self._console, _Coord(cols, rows)) != 0:
            raise OSError("ResizePseudoConsole failed")

    def exit_code(self, wait_ms=0):
        """The program's exit code, or None while it runs (waits up to `wait_ms` for it to end)."""
        self._k.WaitForSingleObject(self._process, wait_ms)
        code = w.DWORD()
        _check(self._k.GetExitCodeProcess(self._process, ctypes.byref(code)))
        return None if code.value == _STILL_ACTIVE else code.value

    def close(self):
        """Ends the pseudo console (and with it every program attached to it). Keep reading until `read` returns b"" so this cannot block."""
        if self._console:
            self._k.ClosePseudoConsole(self._console)
            self._console = None
            if getattr(self, "_process", None) and self.exit_code(2000) is None:
                self._k.TerminateProcess(self._process, 1)
            self._k.CloseHandle(self._in)
            self._k.DeleteProcThreadAttributeList(self._attributes)
