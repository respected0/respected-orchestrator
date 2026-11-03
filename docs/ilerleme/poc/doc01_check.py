"""DOC-01 yapısal doğrulama: kaynak, profil, ADR ve benchmark bağları."""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = ROOT / "docs" / "COMPETITOR_RESEARCH.md"
ADR_DIR = ROOT / "docs" / "adr"
ACCESS = "2026-10-30"
ACCESS_RE = re.compile(r"\(erişim: \d{4}-\d{2}-\d{2}\)")


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def profiled_blocks(text: str, heading: str) -> list[tuple[str, str]]:
    start = text.index(heading)
    rest = text[start + len(heading):]
    end = rest.find("\n## ")
    rest = rest if end < 0 else rest[:end]
    parts = re.split(r"^### (?:Çerçeve|Rakip): (.+)$", rest, flags=re.M)
    return list(zip(parts[1::2], parts[2::2]))


def main() -> int:
    errors: list[str] = []
    text = RESEARCH.read_text(encoding="utf-8")

    sources = dict(re.findall(r"^\| (S\d+) \| [^|]+ \| (https?://\S+) \|", text, flags=re.M))
    if len(sources) < 21:
        fail(errors, f"kaynak tablosu: 21 beklenirken {len(sources)} bulundu")
    for sid, url in sources.items():
        row = re.search(rf"^\| {sid} \|.*$", text, flags=re.M).group(0)
        if ACCESS not in row or not url.startswith("https://"):
            fail(errors, f"{sid}: erişim tarihi veya mutlak URL eksik")
    print(f"PASS kaynak tablosu: {len(sources)} kaynak, tümü https + {ACCESS}")

    frameworks = profiled_blocks(text, "## Çerçeve profilleri")
    competitors = profiled_blocks(text, "## Doğrudan rakip profilleri")
    if len(frameworks) < 4:
        fail(errors, f"çerçeve profili: 4 beklenirken {len(frameworks)}")
    if len(competitors) < 10:
        fail(errors, f"rakip profili: 10 beklenirken {len(competitors)}")
    for kind, blocks in (("çerçeve", frameworks), ("rakip", competitors)):
        for name, body in blocks:
            for field in ("**Doğrulama:**", "**Kaynak:**", "**Gözlem:**", "**Respected için çıkarım:**"):
                if field not in body:
                    fail(errors, f"{kind} {name}: {field} eksik")
            refs = re.findall(r"S\d+", body)
            if not refs:
                fail(errors, f"{kind} {name}: kaynak kimliği yok")
            elif any(ref not in sources for ref in refs):
                fail(errors, f"{kind} {name}: tanımsız kaynak")
    print(f"PASS profiller: {len(frameworks)} çerçeve + {len(competitors)} rakip, alanlar ve kaynaklar tam")

    unverified = re.findall(r"^- \*\*U-(\d+):\*\*", text, flags=re.M)
    if len(unverified) < 5:
        fail(errors, f"doğrulanmamış iddia: 5 beklenirken {len(unverified)}")
    print(f"PASS doğrulanmamış iddialar: {len(unverified)} işaretli")

    benchmark = text[text.index("## Benchmark'a bağlı kararlar"):]
    if "EVAL-01" not in benchmark or "eval01_results.json" not in benchmark:
        fail(errors, "benchmark kararı EVAL-01 kanıtına bağlı değil")
    if "EVAL-02" not in benchmark or "doğrulanmadı" not in benchmark:
        fail(errors, "ajan başarısı iddiası sınırlandırılmamış")
    print("PASS benchmark kararları EVAL-01 kanıtına bağlı, ajan başarısı doğrulanmadı olarak işaretli")

    adrs = sorted(ADR_DIR.glob("ADR-*.md"))
    if len(adrs) < 5:
        fail(errors, f"ADR: 5 beklenirken {len(adrs)}")
    for adr in adrs:
        body = adr.read_text(encoding="utf-8")
        for field in ("## Durum", "## Bağlam", "## Karar", "## Sonuçlar", "## Kaynaklar"):
            if field not in body:
                fail(errors, f"{adr.name}: {field} eksik")
        if not ACCESS_RE.search(body):
            fail(errors, f"{adr.name}: erişim tarihi yok")
    print(f"PASS ADR: {len(adrs)} karar kaydı, Durum/Bağlam/Karar/Sonuçlar/Kaynaklar alanları tam")

    if errors:
        for err in errors:
            print("FAIL", err)
        return 1
    print(f"RESULT PASS {date.today().isoformat()}")
    return 0


if __name__ == "__main__":
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main()
    text = buf.getvalue()
    print(text, end="")
    if "--out" in sys.argv:
        Path(sys.argv[sys.argv.index("--out") + 1]).write_text(text, encoding="utf-8")
    raise SystemExit(code)
