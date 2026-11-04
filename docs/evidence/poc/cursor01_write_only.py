"""CUR-01: tek senaryo (write: RESPECTED_CURSOR_NETWORK=allow; deny: anahtarsız). Kullanım: python cursor01_write_only.py <çıktı.log> [write|deny]"""
import json, os, sys, tempfile
from pathlib import Path
POC = Path(__file__).parent
sys.path.insert(0, str(POC))
import cursor01_sandbox_e2e as c  # noqa: E402
h = c.h
root = Path(tempfile.mkdtemp(prefix="respected-cur01-")).resolve()
project = h.setup_project(root)
secret_values = c.secrets()
base = dict(os.environ, PYTHONPATH=str(h.SRC), RESPECTED_CURSOR_NETWORK="allow")
name = sys.argv[2] if len(sys.argv) > 2 else "write"
if name == "deny":
    base.pop("RESPECTED_CURSOR_NETWORK")
rec = {"root": str(root), "scenarios": {name: c.scenario(root, project, name, base)}}
h.scan_for_secrets([root], rec, secret_values)
out = Path(sys.argv[1])
out.write_text(h.redact(rec, secret_values) + "\n", encoding="utf8")
s = rec["scenarios"][name]
print(json.dumps({"status": s["status"].get("status"), "reason": s["status"].get("reason"),
                  "incomplete": s["status"].get("worker_incomplete"), "check": bool(s["check"]),
                  "home_removed": s["credential_home_removed"]}, indent=1))
