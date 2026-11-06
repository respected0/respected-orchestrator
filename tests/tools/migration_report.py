"""B3-09.02 migration report: before/after SHA-256 of every file for the committed release fixtures, plus the upgrade-proof results.

    python tests/tools/migration_report.py [--proof proof-beta1.json --proof proof-beta2.json] > report.md
"""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from respected_orchestrator.interfaces.migrate import CURRENT, migrate_data  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "releases"


def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def scenario(name, settings_bytes):
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data"
        (data / "state").mkdir(parents=True)
        (data / "settings.json").write_bytes(settings_bytes)
        (data / "state" / "evidence.json").write_bytes(b'{"signed": "evidence kept as is"}')
        before = tree(data)
        moved = migrate_data(data)
        after = tree(data)
        again = migrate_data(data)
        rows = []
        for rel in sorted(set(before) | set(after)):
            status = "unchanged" if before.get(rel) == after.get(rel) else ("new" if rel not in before else "REWRITTEN" if rel in after else "REMOVED")
            rows.append((rel, before.get(rel, "-"), after.get(rel, "-"), status))
        backup_ok = after.get("settings.json.v1.bak") == before["settings.json"] if "settings.json.v1.bak" in after else None
        return {"name": name, "moved": moved, "second_run_moved": again, "rows": rows, "backup_equals_original": backup_ok,
                "version_after": json.loads((data / "settings.json").read_text(encoding="utf-8"))["schema_version"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", action="append", default=[])
    args = parser.parse_args()
    out = ["# B3-09.02 — Migrasyon raporu", "", f"Geçerli biçim: `{CURRENT}`. Her senaryo geçici bir veri kökünde koşar; ikinci koşu hiçbir şey taşımamalıdır.", ""]
    beta1 = json.loads((FIXTURES / "0.1.0-beta.1" / "settings.json").read_text(encoding="utf-8"))
    gemini = {**{k: v for k, v in beta1.items() if k != "schema_version"}, "default_worker": "gemini", "default_reviewer_tool": "gemini", "default_worker_profile": "gemini-2.5-pro"}
    cases = [("beta.1 gerçek fixture (Gemini yok)", (FIXTURES / "0.1.0-beta.1" / "settings.json").read_bytes()),
             ("beta.1 + Gemini varsayılanları", json.dumps(gemini, indent=2).encode()),
             ("beta.2 gerçek fixture", (FIXTURES / "0.1.0-beta.2" / "settings.json").read_bytes())]
    for name, raw in cases:
        r = scenario(name, raw)
        out += [f"## {r['name']}", "", f"taşınan: {r['moved'] or 'yok (zaten güncel)'} · biçim sonrası: {r['version_after']} · ikinci koşuda taşınan: {r['second_run_moved'] or 'yok'} · yedek özgünle aynı: {r['backup_equals_original']}", "",
                "| dosya | önce (sha256) | sonra (sha256) | durum |", "|---|---|---|---|"]
        out += [f"| `{rel}` | `{b[:16]}…` | `{a[:16]}…` | {s} |" if b != "-" and a != "-" else f"| `{rel}` | `{b[:16]}` | `{a[:16]}…` | {s} |" for rel, b, a, s in r["rows"]]
        out.append("")
    for path in args.proof:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        na = data.get("not_applicable", [])
        out += [f"## Gerçek yükseltme kanıtı: {data['from']} (motor {data.get('from_version')}) → bu çalışma kopyası", "",
                f"sonuç: **{'OK' if data['ok'] else 'BAŞARISIZ'}** · adım: {len(data['steps'])} · uygulanamaz: {len(na)} · başarısız: {sum(1 for s in data['steps'] if not s['ok'])}", ""]
        out += [f"- {'N/A' if s.get('not_applicable') else 'OK ' if s['ok'] else 'FAIL'} {s['step']}" for s in data["steps"]]
        out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
