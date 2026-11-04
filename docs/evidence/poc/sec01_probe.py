"""SEC-01 zararsiz PoC'ler: motorun baslattigi cocuk surecin dosya/ag sinirini olcer.

Calistirma (depo kokunde):
    python docs/evidence/poc/sec01_probe.py docs/evidence/poc/sec01_results.json

Sonuc sozlesmesi: ALLOWED = islem gerceklesti, DENIED = islem engellendi.
Bu betik hicbir sey silmez; yalnizca gecici klasorde calisir.
"""
import json
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from respected_orchestrator.engine import winproc  # noqa: E402


def run(code, cwd):
    p = winproc.run([sys.executable, "-c", code], cwd=str(cwd), capture_output=True, text=True, timeout=45)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip().splitlines()[-1:] and p.stderr.strip().splitlines()[-1] or ""


def main(out_file=None):
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ws, outside = base / "workspace", base / "outside"
        ws.mkdir()
        outside.mkdir()
        (outside / "secret.txt").write_text("TOPSECRET", encoding="utf-8")
        (ws / ".env").write_text("API_KEY=sk-fake-not-real\n", encoding="utf-8")

        rc, o, err = run(f"print(open({str(outside / 'secret.txt')!r}, encoding='utf-8').read())", ws)
        results.append(dict(id="P-01", probe="workspace disindaki dosyayi okuma",
                            result="ALLOWED" if rc == 0 and "TOPSECRET" in o else "DENIED", evidence=o or err))

        rc, o, err = run(f"open({str(outside / 'written.txt')!r}, 'w', encoding='utf-8').write('x'); print('write-ok')", ws)
        results.append(dict(id="P-02", probe="workspace disina dosya yazma",
                            result="ALLOWED" if (outside / "written.txt").is_file() else "DENIED", evidence=o or err))

        net_code = (
            "import socket\n"
            "try:\n"
            "    s = socket.create_connection(('example.com', 443), 8)\n"
            "    s.close(); print('connected')\n"
            "except Exception as exc:\n"
            "    print('blocked: %s' % type(exc).__name__)\n"
        )
        rc, o, err = run(net_code, ws)
        results.append(dict(id="P-03", probe="internete TCP cikisi (example.com:443)",
                            result="ALLOWED" if o == "connected" else "DENIED", evidence=o or err))

        rc, o, err = run("print(open('.env', encoding='utf-8').read().strip())", ws)
        results.append(dict(id="P-04", probe="worktree icindeki .env dosyasini okuma",
                            result="ALLOWED" if "sk-fake-not-real" in o else "DENIED", evidence=o or err))

        link = ws / "link"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, text=True)
        if link.exists():
            rc, o, err = run(f"print(open({str(link / 'secret.txt')!r}, encoding='utf-8').read())", ws)
            results.append(dict(id="P-05", probe="workspace icindeki junction uzerinden disari okuma",
                                result="ALLOWED" if "TOPSECRET" in o else "DENIED", evidence=o or err))
        else:
            results.append(dict(id="P-05", probe="workspace icindeki junction uzerinden disari okuma",
                                result="SKIPPED", evidence="mklink /J basarisiz"))

    text = json.dumps(results, ensure_ascii=False, indent=1)
    print(text)
    if out_file:
        Path(out_file).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)