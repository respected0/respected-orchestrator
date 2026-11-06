"""B3-08.03 offline / no-process proof for `capabilities.inventory`. Not a unittest: it prints a report that goes into the evidence log.

Source mode: the engine runs with a `sitecustomize` that makes every attempt to open a network connection or start a process
raise AND be recorded. Executable mode (RESPECTED_PROOF_EXE): the packaged engine is polled every ~10 ms for child processes and for
sockets owned by it while it answers repeated inventory calls. Both run against a synthetic home with a hostile config and, optionally,
the real home (RESPECTED_PROOF_REAL_HOME=1).
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXE = os.environ.get("RESPECTED_PROOF_EXE")
SITECUSTOMIZE = '''
import os, socket, subprocess, sys
LOG = os.environ["PROOF_LOG"]
def deny(kind):
    def f(*a, **k):
        with open(LOG, "a") as h: h.write(kind + "\\n")
        raise PermissionError("blocked by the proof harness: " + kind)
    return f
socket.socket.connect = deny("socket.connect"); socket.socket.connect_ex = deny("socket.connect_ex")
socket.create_connection = deny("socket.create_connection"); socket.getaddrinfo = deny("socket.getaddrinfo")
subprocess.Popen.__init__ = deny("subprocess.Popen")
os.system = deny("os.system")
for name in ("spawnl", "spawnv", "spawnle", "spawnve", "spawnlp", "spawnvp", "startfile", "popen"):
    if hasattr(os, name): setattr(os, name, deny("os." + name))
'''


def make_home(tmp):
    home = tmp / "kullanıcı"
    (home / ".codex").mkdir(parents=True)
    marker = tmp / "MARKER-must-not-exist"
    (home / ".claude.json").write_text(json.dumps({"mcpServers": {"evil": {"command": "python", "args": ["-c", f"open(r'{marker}','w')"],
                                                                         "env": {"API_KEY": "sk-SHOULDNEVERAPPEAR123456"}},
                                                              "remote": {"type": "http", "url": "https://unreachable.invalid/mcp?token=SHOULDNEVERAPPEAR"}}}), encoding="utf-8")
    (home / ".codex/config.toml").write_text('[mcp_servers.x]\ncommand = "cmd"\nargs = ["/c", "echo hi"]\n', encoding="utf-8")
    (home / ".claude/skills/s").mkdir(parents=True)
    (home / ".claude/skills/s/SKILL.md").write_text("---\nname: s\n---\n", encoding="utf-8")
    return home, marker


def ask(proc, n, token):
    proc.stdin.write(json.dumps({"ipc": "1", "id": f"proof-{n:05d}", "session": token, "cmd": "capabilities.inventory", "payload": {}}) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def engine(cmd, env):
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env)


def run_source(home, marker, tmp, calls=5):
    guard = tmp / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    log = tmp / "attempts.log"
    token = "p" * 32
    env = {**os.environ, "USERPROFILE": str(home), "HOME": str(home), "RESPECTED_DATA_DIR": str(tmp / "data"), "RESPECTED_IPC_TOKEN": token,
           "PYTHONPATH": os.pathsep.join([str(guard), str(ROOT / "src")]), "PROOF_LOG": str(log), "PYTHONIOENCODING": "utf-8"}
    proc = engine([sys.executable, "-m", "respected_orchestrator", "_ipc"], env)
    replies = [ask(proc, i, token) for i in range(calls)]
    proc.stdin.close()
    proc.wait(timeout=30)
    attempts = log.read_text().split() if log.exists() else []
    return replies, attempts, proc.stderr.read()


def run_exe(home, tmp, calls=10):
    token = "q" * 32
    env = {**os.environ, "USERPROFILE": str(home), "HOME": str(home), "RESPECTED_DATA_DIR": str(tmp / "data"), "RESPECTED_IPC_TOKEN": token}
    proc = engine([EXE, "_ipc"], env)
    seen_children, seen_sockets, stop = set(), set(), threading.Event()

    def watch():
        while not stop.is_set():
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  f"(Get-CimInstance Win32_Process -Filter 'ParentProcessId={proc.pid}' | ForEach-Object {{ $_.Name + ':' + $_.ProcessId }}) -join ','; "
                                  f"(Get-NetTCPConnection -OwningProcess {proc.pid} -ErrorAction SilentlyContinue | ForEach-Object {{ $_.LocalAddress + ':' + $_.LocalPort + '>' + $_.RemoteAddress }}) -join ','; "
                                  f"(Get-NetUDPEndpoint -OwningProcess {proc.pid} -ErrorAction SilentlyContinue | ForEach-Object {{ $_.LocalAddress + ':' + $_.LocalPort }}) -join ','"],
                                 capture_output=True, text=True).stdout.strip().splitlines()
            out += [""] * (3 - len(out))
            seen_children.update(x for x in out[0].split(",") if x)
            seen_sockets.update(x for x in (out[1] + "," + out[2]).split(",") if x)
    thread = threading.Thread(target=watch)
    thread.start()
    started = time.monotonic()
    replies = [ask(proc, i, token) for i in range(calls)]
    elapsed = time.monotonic() - started
    stop.set()
    thread.join()
    proc.stdin.close()
    proc.wait(timeout=30)
    return replies, sorted(seen_children), sorted(seen_sockets), elapsed


def control(tmp):
    """The guard must catch what it claims to catch, or "no attempts" would mean nothing."""
    guard = tmp / "ctl"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    log = tmp / "control.log"
    code = "\n".join([
        "import socket, subprocess, os",
        "for f in (lambda: subprocess.Popen(['cmd', '/c', 'echo x']), lambda: socket.create_connection(('127.0.0.1', 9)), lambda: os.system('echo x'),",
        "          lambda: socket.getaddrinfo('example.com', 80)):",
        "    try: f()",
        "    except PermissionError: pass",
    ])
    subprocess.run([sys.executable, "-c", code], env={**os.environ, "PYTHONPATH": str(guard), "PROOF_LOG": str(log)}, capture_output=True)
    return sorted(set(log.read_text().split())) if log.exists() else []


def main():
    report = []
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        home, marker = make_home(tmp)
        caught = control(tmp)
        report.append(f"control (guard must catch these): {caught}")
        replies, attempts, err = run_source(home, marker, tmp)
        caps = replies[0]["result"]["capabilities"] if replies[0].get("ok") else []
        blob = json.dumps(replies)
        report += [f"source: {len(replies)} calls ok={all(r.get('ok') for r in replies)} capabilities={len(caps)} blocked-attempts={attempts or 'none'} "
                   f"marker-created={marker.exists()} secret-in-output={'SHOULDNEVERAPPEAR' in blob} stderr-empty={err.strip() == ''}"]
        ok = len(caught) == 4 and all(r.get("ok") for r in replies) and not attempts and not marker.exists() and "SHOULDNEVERAPPEAR" not in blob and len(caps) >= 3
        if EXE:
            r2, children, sockets, elapsed = run_exe(home, tmp)
            ok2 = all(r.get("ok") for r in r2) and not children and not sockets and not marker.exists()
            report.append(f"exe:    {len(r2)} calls ok={all(r.get('ok') for r in r2)} elapsed={elapsed:.2f}s child-processes-seen={children or 'none'} "
                          f"sockets-seen={sockets or 'none'} marker-created={marker.exists()}")
            ok = ok and ok2
        if os.environ.get("RESPECTED_PROOF_REAL_HOME") == "1":
            real_tmp = tmp / "real"
            real_tmp.mkdir()
            rr, ra, _ = run_source(Path.home(), real_tmp / "m", real_tmp)
            report.append(f"source on the real home: ok={all(r.get('ok') for r in rr)} capabilities={len(rr[0]['result']['capabilities'])} blocked-attempts={ra or 'none'}")
            ok = ok and all(r.get("ok") for r in rr) and not ra
    print("\n".join(report))
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
