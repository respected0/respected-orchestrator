"""DOC-01 yapısal doğrulama: ADR karar kayıtlarının zorunlu alanları ve erişim tarihleri."""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ADR_DIR = ROOT / "docs" / "adr"
ACCESS_RE = re.compile(r"\(erişim: \d{4}-\d{2}-\d{2}\)")


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def main() -> int:
    errors: list[str] = []

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
