"""SEC-02: measure Windows AppContainer as a worker sandbox.

Runs real child and grandchild processes in an AppContainer with no capabilities.
Writes ``sec02_results.json`` next to the given output path and exits non-zero if
any acceptance measurement fails.
"""
import ctypes
import json
import socket
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes as w
from pathlib import Path

userenv = ctypes.WinDLL("userenv", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", w.DWORD)]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("AppContainerSid", ctypes.c_void_p),
        ("Capabilities", ctypes.POINTER(SID_AND_ATTRIBUTES)),
        ("CapabilityCount", w.DWORD),
        ("Reserved", w.DWORD),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR),
        ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD),
        ("dwXSize", w.DWORD), ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD),
        ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
        ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
        ("lpReserved2", ctypes.c_void_p), ("hStdInput", w.HANDLE),
        ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", w.HANDLE), ("hThread", w.HANDLE),
        ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD),
    ]


userenv.CreateAppContainerProfile.argtypes = [
    w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, ctypes.c_void_p, w.DWORD,
    ctypes.POINTER(ctypes.c_void_p),
]
userenv.CreateAppContainerProfile.restype = ctypes.c_long
userenv.DeleteAppContainerProfile.argtypes = [w.LPCWSTR]
userenv.DeleteAppContainerProfile.restype = ctypes.c_long
advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)]
advapi32.ConvertSidToStringSidW.restype = w.BOOL
advapi32.FreeSid.argtypes = [ctypes.c_void_p]
kernel32.CreateProcessW.argtypes = [
    w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL, w.DWORD,
    ctypes.c_void_p, w.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = w.BOOL
kernel32.InitializeProcThreadAttributeList.argtypes = [
    ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_size_t),
]
kernel32.UpdateProcThreadAttribute.argtypes = [
    ctypes.c_void_p, w.DWORD, ctypes.c_size_t, ctypes.c_void_p,
    ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
]
kernel32.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
kernel32.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
kernel32.TerminateProcess.argtypes = [w.HANDLE, w.UINT]


CHILD = r"""
import json, socket, subprocess, sys
from pathlib import Path
ws, outside, secret, engine_key, result = map(Path, sys.argv[1:6])
out = {"forbidden": {}, "allowed": {}, "children": []}

def attempt(fn):
    try:
        return {"ok": True, "value": fn()}
    except Exception as error:
        return {"ok": False, "error": type(error).__name__ + ": " + str(error)[:120]}

def read_secret():
    return secret.read_text(encoding="utf-8")

def write_outside():
    (outside / "pwn.txt").write_text("pwned", encoding="utf-8")
    return True

def read_engine_key():
    return engine_key.read_text(encoding="utf-8")

def tcp_egress():
    sock = socket.create_connection(("1.1.1.1", 443), timeout=3)
    sock.close()
    return "connected"

def delete_outside():
    (outside / "delete-me.txt").unlink()
    return True

for name, fn in [
    ("read_outside", read_secret),
    ("write_outside", write_outside),
    ("read_engine_key", read_engine_key),
    ("tcp_egress", tcp_egress),
    ("delete_outside", delete_outside),
]:
    out["forbidden"][name] = attempt(fn)

for index in range(1, 4):
    target = ws / ("allowed-%d.txt" % index)
    out["allowed"][index] = attempt(lambda target=target: (
        target.write_text("ok", encoding="utf-8"),
        target.read_text(encoding="utf-8"),
    )[1] == "ok")

for index in range(1, 4):
    grand = ws / ("grand-%d.py" % index)
    grand_result = ws / ("grand-%d.json" % index)
    grand.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        "ws, outside, result = map(Path, sys.argv[1:4])\n"
        "try:\n"
        "    (outside / 'grand-pwn.txt').write_text('x', encoding='utf-8')\n"
        "    blocked = False\n"
        "except Exception as error:\n"
        "    blocked = True\n"
        "allowed = (lambda p: (p.write_text('ok', encoding='utf-8'), p.exists())[1])(ws / 'grand-ok.txt')\n"
        "result.write_text(json.dumps({'blocked': blocked, 'allowed': allowed}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [sys.executable, str(grand), str(ws), str(outside), str(grand_result)],
            capture_output=True, text=True, timeout=30,
        )
        out["children"].append({
            "launched": True,
            "exit_code": proc.returncode,
            "result": json.loads(grand_result.read_text(encoding="utf-8")) if grand_result.exists() else None,
            "stderr": proc.stderr[-200:],
        })
    except Exception as error:
        out["children"].append({"launched": False, "error": type(error).__name__ + ": " + str(error)[:120]})

result.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
"""


def run(*args, check=False):
    return subprocess.run(args, capture_output=True, text=True, check=check)


def grant(path, sid, rights):
    return run("icacls", str(path), "/grant", f"*{sid}:{rights}")


def revoke(path, sid):
    return run("icacls", str(path), "/remove", f"*{sid}")


def launch(command, cwd, sid, timeout_seconds=60):
    capabilities = SECURITY_CAPABILITIES(sid, None, 0, 0)
    size = ctypes.c_size_t()
    kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    if not kernel32.InitializeProcThreadAttributeList(buffer, 1, 0, ctypes.byref(size)):
        return False, None, ctypes.get_last_error()
    if not kernel32.UpdateProcThreadAttribute(
        buffer, 0, 0x00020009, ctypes.byref(capabilities), ctypes.sizeof(capabilities), None, None
    ):
        return False, None, ctypes.get_last_error()
    startup = STARTUPINFOEXW()
    startup.StartupInfo.cb = ctypes.sizeof(startup)
    startup.lpAttributeList = ctypes.addressof(buffer)
    process = PROCESS_INFORMATION()
    command_line = ctypes.create_unicode_buffer(command)
    ok = kernel32.CreateProcessW(
        None, command_line, None, None, False, 0x00080000, None, str(cwd),
        ctypes.byref(startup), ctypes.byref(process),
    )
    if not ok:
        return False, None, ctypes.get_last_error()
    kernel32.WaitForSingleObject(process.hProcess, timeout_seconds * 1000)
    code = w.DWORD()
    kernel32.GetExitCodeProcess(process.hProcess, ctypes.byref(code))
    kernel32.CloseHandle(process.hThread)
    kernel32.CloseHandle(process.hProcess)
    return True, code.value, 0


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "sec02_results.json").resolve()
    baseline_tcp = False
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=3).close()
        baseline_tcp = True
    except OSError as error:
        baseline_error = type(error).__name__ + ": " + str(error)[:120]

    root = Path(tempfile.mkdtemp(prefix="sec02_")).resolve()
    workspace = root / "ws"
    outside = root / "outside"
    data_root = root / "data"
    workspace.mkdir()
    outside.mkdir()
    data_root.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("TOPSECRET", encoding="utf-8")
    (outside / "delete-me.txt").write_text("keep", encoding="utf-8")
    engine_key = data_root / ".engine-key"
    engine_key.write_text("ENGINE-KEY-SENTINEL", encoding="utf-8")
    (workspace / "child.py").write_text(CHILD, encoding="utf-8")

    profile_name = "RespectedOrchestratorSec02" + str(int(time.time()))
    sid_value = ctypes.c_void_p()
    hr = userenv.CreateAppContainerProfile(
        profile_name, profile_name, "SEC-02 probe", None, 0, ctypes.byref(sid_value)
    )
    if hr == -2147024713:
        profile_name += "b"
        hr = userenv.CreateAppContainerProfile(
            profile_name, profile_name, "SEC-02 probe", None, 0, ctypes.byref(sid_value)
        )
    if hr != 0:
        raise SystemExit(f"CreateAppContainerProfile failed: {hr & 0xffffffff:#x}")
    sid_text = w.LPWSTR()
    if not advapi32.ConvertSidToStringSidW(sid_value, ctypes.byref(sid_text)):
        raise SystemExit("ConvertSidToStringSidW failed")
    sid = sid_text.value

    python_dir = Path(sys.executable).resolve().parent
    codex_dir = Path.home() / "AppData/Local/Programs/OpenAI/Codex"
    granted = []
    try:
        for path, rights in [
            (workspace, "(OI)(CI)M"),
            (root, "RX"),
            (python_dir, "(OI)(CI)RX"),
        ]:
            result = grant(path, sid, rights)
            if result.returncode != 0:
                raise SystemExit(f"icacls grant failed for {path}: {result.stderr or result.stdout}")
            granted.append(path)

        trials = []
        for run_index in range(1, 4):
            (outside / "delete-me.txt").write_text("keep", encoding="utf-8")
            result_path = workspace / f"result-{run_index}.json"
            command = f'"{sys.executable}" "{workspace / "child.py"}" "{workspace}" "{outside}" "{secret}" "{engine_key}" "{result_path}"'
            created, exit_code, error = launch(command, workspace, sid_value)
            report = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
            trials.append({
                "run": run_index,
                "created": created,
                "create_error": error,
                "exit_code": exit_code,
                "result": report,
            })

        codex_compatible = None
        codex_exit = None
        if codex_dir.exists():
            grant(codex_dir, sid, "(OI)(CI)RX")
            granted.append(codex_dir)
            created, codex_exit, error = launch(f'"{codex_dir / "bin/codex.exe"}" --version', workspace, sid_value, 30)
            codex_compatible = bool(created and codex_exit == 0)
        else:
            error = "codex executable directory not found"

        unsupported_created, unsupported_exit, unsupported_error = launch(
            f'"{workspace / "not-installed-cli.exe"}" --version', workspace, sid_value, 10
        )

        forbidden_total = forbidden_blocked = 0
        allowed_total = allowed_ok = 0
        child_total = child_blocked = 0
        for trial in trials:
            report = trial["result"] or {}
            for outcome in report.get("forbidden", {}).values():
                forbidden_total += 1
                forbidden_blocked += int(not outcome.get("ok", True))
            for outcome in report.get("allowed", {}).values():
                allowed_total += 1
                allowed_ok += int(bool(outcome.get("ok")))
            for child in report.get("children", []):
                child_total += 1
                nested = child.get("result") or {}
                child_blocked += int(bool(child.get("launched") and nested.get("blocked") and nested.get("allowed")))

        summary = {
            "forbidden_blocked": f"{forbidden_blocked}/{forbidden_total}",
            "allowed_workspace_writes": f"{allowed_ok}/{allowed_total}",
            "child_policy_inherited": f"{child_blocked}/{child_total}",
            "network_baseline_connected": baseline_tcp,
            "codex_launched": bool(codex_compatible),
            "codex_exit_code": codex_exit,
            "windows_sandbox_binary": Path("C:/Windows/System32/WindowsSandbox.exe").exists(),
            "pass": (
                forbidden_total == 15 and forbidden_blocked == 15
                and allowed_total == 9 and allowed_ok == 9
                and child_total == 9 and child_blocked == 9
                and baseline_tcp
            ),
        }
        document = {
            "technology": "Windows AppContainer; no capability SIDs; workspace ACL granted to container SID",
            "profile": profile_name,
            "sid": sid,
            "baseline_tcp_error": None if baseline_tcp else baseline_error,
            "trials": trials,
            "codex": {
                "path": str(codex_dir / "bin/codex.exe"),
                "launched": bool(codex_compatible),
                "exit_code": codex_exit,
                "note": "Non-zero exit means the CLI needs files outside the allowed roots; it is reported unsupported, not silently run unsandboxed.",
            },
            "unsupported_cli_probe": {
                "created": unsupported_created,
                "exit_code": unsupported_exit,
                "create_error": unsupported_error,
                "note": "A missing CLI is reported unsupported; there is no widened fallback.",
            },
            "summary": summary,
        }
        output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["pass"] else 1
    finally:
        for path in granted:
            revoke(path, sid)
        userenv.DeleteAppContainerProfile(profile_name)
        advapi32.FreeSid(sid_value)


if __name__ == "__main__":
    sys.exit(main())
