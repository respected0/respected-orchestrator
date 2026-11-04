"""CUR-01: boru shim'i yüklüyken (Cursor'un node.exe'si, AppContainer) yasak erişimler hâlâ engelleniyor mu?

Kullanım: python cursor01_deny_probe.py  -> JSON; her yasak işlem DENIED, izinli işlemler OK olmalı.
Ağ kapalı politikayla (RESPECTED_CURSOR_NETWORK yok) koşar; sahte bir dosya/token dışında hiçbir sır kullanılmaz.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from respected_orchestrator.context import EngineContext  # noqa: E402
from respected_orchestrator.engine import runner  # noqa: E402
from respected_orchestrator.engine.processes import execute  # noqa: E402
from respected_orchestrator.engine.worker_policy import default_policy  # noqa: E402

CODE = r"""
const fs = require('fs'), net = require('net'), cp = require('child_process');
const out = {};
const tryit = (name, fn) => { try { fn(); out[name] = 'ALLOWED'; } catch (e) { out[name] = 'DENIED ' + (e.code || e.message); } };
tryit('read_outside_file', () => fs.readFileSync(process.env.PROBE_OUTSIDE, 'utf8'));
tryit('write_outside_file', () => fs.writeFileSync(process.env.PROBE_OUTSIDE + '.new', 'x'));
tryit('overwrite_outside_file', () => fs.writeFileSync(process.env.PROBE_OUTSIDE, 'x'));
tryit('read_engine_key', () => fs.readFileSync(process.env.PROBE_FILE_ONE));
tryit('list_engine_data_root', () => fs.readdirSync(process.env.PROBE_DATA));
tryit('read_user_cursor_auth', () => fs.readFileSync(process.env.PROBE_FILE_TWO));
{
  const r = cp.spawnSync('C:/Windows/System32/cmd.exe', ['/c', 'type', process.env.PROBE_OUTSIDE]);
  out.child_reads_outside_file = r.status === 0 ? 'LEAKED' : 'DENIED status=' + r.status;
}
tryit('own_workspace_write', () => { fs.writeFileSync('ok.txt', 'ok'); });
out.own_workspace_write = out.own_workspace_write === 'ALLOWED' ? 'OK' : 'BROKEN';
const s = net.connect({ host: '1.1.1.1', port: 443 });
const t = setTimeout(() => { out.network = 'DENIED timeout'; s.destroy(); done(); }, 6000);
s.on('connect', () => { out.network = 'ALLOWED'; clearTimeout(t); s.destroy(); done(); });
s.on('error', (e) => { out.network = 'DENIED ' + e.code; clearTimeout(t); done(); });
function done() { console.log(JSON.stringify(out)); process.exit(0); }
"""


def main():
    root = Path(tempfile.mkdtemp(prefix="respected-cur01-probe-")).resolve()
    work, tmp, outside, data = root / "work", root / "work" / "tmp", root / "outside", root / "data"
    for folder in (work, tmp, outside, data):
        folder.mkdir(parents=True, exist_ok=True)
    (outside / "private.txt").write_text("private", encoding="utf8")
    (data / ".engine-key").write_text("not-a-real-key", encoding="utf8")
    auth = Path(os.environ["APPDATA"]) / "Cursor" / "auth.json"
    node = runner.get_cli_command("cursor")
    command = [*node[:-1], "-e", CODE]
    policy = default_policy(EngineContext(data), work, command, temp_root=tmp, ttl=60,
                            readonly_roots=[runner.NODE_PIPE_SHIM.parent])
    env = dict(os.environ, PROBE_OUTSIDE=str(outside / "private.txt"), PROBE_FILE_ONE=str(data / ".engine-key"),
               PROBE_DATA=str(data), PROBE_FILE_TWO=str(auth))
    result = execute(command, work, 50, policy=policy, env=env)
    print(json.dumps({"returncode": result.returncode, "result": json.loads(result.stdout.strip().splitlines()[-1]) if result.stdout.strip() else None,
                      "stderr": result.stderr[-300:]}, indent=1))


if __name__ == "__main__":
    main()
