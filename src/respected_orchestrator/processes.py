"""Bounded worker processes. Windows jobs kill descendants on supervisor exit."""
import ctypes
import os
from pathlib import Path
from . import winproc
import re
import signal
import subprocess
import sys
import threading
import time
from ctypes import wintypes


class ProcessStopped(RuntimeError):
    def __init__(self, reason, stdout="", stderr="", had_output=False, last_output_age=None):
        self.reason, self.stdout, self.stderr, self.had_output = reason, stdout, stderr, had_output
        self.last_output_age = last_output_age  # seconds since the last byte of output, None if never
        super().__init__(reason)


def _is_codex_command(command) -> bool:
    return bool(command) and Path(command[0]).name.lower().startswith("codex")


def _tests_loaded() -> bool:
    # unittest discover -s tests imports test modules top-level, so tests/__init__ may not run.
    # shortcut: name-based test detection; upgrade to an explicit test-session marker if a false positive appears.
    return any(name == "tests" or name.startswith(("tests.", "test_")) for name in sys.modules)


class WindowsJob:
    def __init__(self):
        class Limits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Limits), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle or not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def attach_and_resume(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())
        # The child is suspended until it belongs to the kill-on-close job.
        class ThreadEntry(ctypes.Structure):
            _fields_ = [(name, wintypes.DWORD if name not in ("tpBasePri", "tpDeltaPri") else wintypes.LONG)
                        for name in ("dwSize", "cntUsage", "th32ThreadID", "th32OwnerProcessID", "tpBasePri", "tpDeltaPri", "dwFlags")]
        self.api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self.api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        self.api.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
        self.api.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
        self.api.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenThread.restype = wintypes.HANDLE
        self.api.ResumeThread.argtypes = [wintypes.HANDLE]
        self.api.ResumeThread.restype = wintypes.DWORD
        snapshot = self.api.CreateToolhelp32Snapshot(4, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        resumed = False
        try:
            entry = ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            more = self.api.Thread32First(snapshot, ctypes.byref(entry))
            while more:
                if entry.th32OwnerProcessID == process.pid:
                    thread = self.api.OpenThread(2, False, entry.th32ThreadID)
                    if thread:
                        try:
                            resumed = self.api.ResumeThread(thread) != 0xFFFFFFFF
                        finally:
                            self.api.CloseHandle(thread)
                    break
                more = self.api.Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            self.api.CloseHandle(snapshot)
        if not resumed:
            raise RuntimeError("Could not resume the owned worker thread")

    def close(self):
        if getattr(self, "handle", None):
            self.api.CloseHandle(self.handle)
            self.handle = None


_SECRET_NAME = re.compile(r"(?i)key|token|secret|passw|credential|auth|cookie|session")


def scrub_environment(environ):
    """Drop secret-looking variables from untrusted worker/check environments.

    shortcut: name-based; names listed in RESPECTED_WORKER_ENV_ALLOW (comma separated) are kept.
    """
    allowed = {n.strip().casefold() for n in environ.get("RESPECTED_WORKER_ENV_ALLOW", "").split(",") if n.strip()}
    return {k: v for k, v in environ.items()
            if k.casefold() in allowed or not _SECRET_NAME.search(k)}


def execute(command, cwd: Path, timeout_seconds: float, *, cancel_path: Path | None = None, on_started=None, on_output=None, env=None, complete_when=None, verify_complete=None, exit_grace=2.0, scrub_env=False, mark_child=True):
    # complete_when(stream, line) -> True marks a candidate completion event. The process then gets
    # exit_grace seconds to exit on its own and its real exit code is kept. If it has to be reaped,
    # the code is 0 only when verify_complete(stdout) confirms the whole stream; otherwise the
    # reaped (non-zero) code stands. Silence never ends a run; only the deadline or cancel does.
    if timeout_seconds <= 0:
        raise ProcessStopped("timed_out")
    if cancel_path is not None and cancel_path.exists():
        raise ProcessStopped("cancelled")
    environment = dict(os.environ if env is None else env)
    if scrub_env:
        environment = scrub_environment(environment)
    if _is_codex_command(command) and (environment.get("RESPECTED_ORCH_TEST_ISOLATION") == "1" or _tests_loaded()):
        raise RuntimeError("Codex API calls are blocked in isolated tests")
    # Marks every child so a worker cannot act as the human approver (see runner.approve_maf_task).
    if mark_child:
        environment["RESPECTED_ORCH_CHILD"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"  # ignored .pyc files count as out-of-scope changes
    else:
        environment.pop("RESPECTED_ORCH_CHILD", None)
    job = WindowsJob() if os.name == "nt" else None
    process = None
    readers = []
    output = {"stdout": [], "stderr": []}
    if os.name == "nt":
        # PowerShell 7 module paths can break Windows PowerShell's Security module.
        environment = {k: v for k, v in environment.items() if k.casefold() != "psmodulepath"}
    options = winproc.hidden_options(0x4) if job else {"start_new_session": True}  # 0x4 = CREATE_SUSPENDED until the job owns it
    deadline = time.monotonic() + timeout_seconds
    completed_event = threading.Event()
    last_output = [None]
    try:
        process = subprocess.Popen(list(command), cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding="utf8", errors="replace", env=environment, **options)
        if job:
            job.attach_and_resume(process)
        if on_started:
            on_started(process.pid)
        def read_stream(name, stream):
            try:
                for line in iter(stream.readline, ''):
                    output[name].append(line)
                    last_output[0] = time.monotonic()
                    if on_output:
                        on_output(name, line)
                    if complete_when and complete_when(name, line):
                        completed_event.set()
            finally:
                stream.close()
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            reader = threading.Thread(target=read_stream, args=(name, stream), daemon=True)
            reader.start()
            readers.append(reader)
        def finish_tree():
            if job:
                job.close()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=5)
            for reader in readers:
                reader.join(timeout=5)
            if any(reader.is_alive() for reader in readers):
                raise RuntimeError("Owned worker output pipes did not close")
        while True:
            reason = "cancelled" if cancel_path is not None and cancel_path.exists() else "timed_out" if time.monotonic() >= deadline else None
            if reason:
                finish_tree()
                age = None if last_output[0] is None else time.monotonic() - last_output[0]
                raise ProcessStopped(reason, ''.join(output['stdout']), ''.join(output['stderr']),
                                     bool(output['stdout'] or output['stderr']), age)
            if process.poll() is not None:
                finish_tree()
                return subprocess.CompletedProcess(list(command), process.returncode, ''.join(output['stdout']), ''.join(output['stderr']))
            if completed_event.is_set():
                # Candidate completion: let a clean exit (and output draining) finish first.
                try:
                    process.wait(timeout=max(0, min(exit_grace, deadline - time.monotonic())))
                except subprocess.TimeoutExpired:
                    pass
                if cancel_path is not None and cancel_path.exists():
                    continue  # cancellation outranks a late completion; handled at loop top
                exited = process.poll() is not None
                finish_tree()
                stdout = ''.join(output['stdout'])
                code = process.returncode
                if not exited and (verify_complete is None or not verify_complete(stdout)):
                    code = code if code else 1  # reaped and unverified: never success
                elif not exited:
                    code = 0
                return subprocess.CompletedProcess(list(command), code, stdout, ''.join(output['stderr']))
            time.sleep(min(0.05, max(0.001, deadline - time.monotonic())))
    finally:
        if job:
            job.close()
        elif process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        for reader in readers:
            reader.join(timeout=5)
