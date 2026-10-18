"""Generate a Turkish repository atlas from explicitly reviewed file metadata.

Discovery is automatic; semantic explanations require a human or agent review.
Only the standard library and Git are required. No installed application/vault I/O.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

INVENTORY = "docs/repository_inventory.json"
MAP = "docs/REPOSITORY_MAP.md"
GENERATED = {INVENTORY, MAP}
EXCLUDED_PARTS = {".git", ".venv", "venv", "env", "ENV", "node_modules", "build", "dist", "release-assets", "release-stage", ".local", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox"}


def project_files(root: Path, *, filesystem_only: bool = False) -> list[str]:
    """Read the index, not HEAD, so staged additions/deletions behave correctly."""
    if filesystem_only:
        # Source-only extraction can forbid Git or start before a repository exists.
        known = set()
        inventory = root / INVENTORY
        if inventory.is_file():
            known = {entry['path'] for entry in json.loads(inventory.read_text(encoding='utf8'))['files']}
        patterns = []
        if (root / '.gitignore').is_file():
            patterns = [line.strip() for line in (root / '.gitignore').read_text(encoding='utf8').splitlines()
                        if line.strip() and not line.startswith('#')]
        def ignored(relative):
            result = False
            candidates = [relative, *[p.as_posix() for p in PurePosixPath(relative).parents if p != PurePosixPath('.')]]
            for raw in patterns:
                negate = raw.startswith('!')
                pattern = raw.lstrip('!').strip('/')
                matched = any(fnmatch.fnmatchcase(value, pattern) if '/' in pattern or raw.startswith('/')
                              else any(fnmatch.fnmatchcase(part, pattern) for part in PurePosixPath(value).parts)
                              for value in candidates)
                if matched:
                    result = not negate
            return result
        found = set(known)
        for directory, names, files in os.walk(root, followlinks=False):
            names[:] = [name for name in names if name not in EXCLUDED_PARTS and not (Path(directory) / name).is_symlink()
                        and not getattr((Path(directory) / name).lstat(), 'st_file_attributes', 0) & 0x400]
            for name in files:
                path = (Path(directory) / name).relative_to(root).as_posix()
                if not ignored(path):
                    found.add(path)
        return sorted(path for path in found if not EXCLUDED_PARTS.intersection(PurePosixPath(path).parts))
    result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], check=True, capture_output=True)
    return sorted({path for path in result.stdout.decode("utf-8").split("\0") if path and not EXCLUDED_PARTS.intersection(PurePosixPath(path).parts)})


def content_digest(path: Path) -> str:
    """Normalize only checkout line endings; content edits still invalidate review."""
    content = path.read_bytes()
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        if b"\0" not in content:
            content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def needs_review(entry: dict) -> bool:
    return any(str(value).startswith("NEEDS_REVIEW") for value in [entry.get("role", ""), entry.get("purpose", ""), *entry.get("relationships", [])])


def validate_inventory(root: Path, inventory: dict, *, filesystem_only: bool = False) -> list[str]:
    errors = []
    if inventory.get("schema") != 1 or not isinstance(inventory.get("files"), list):
        return ["INVALID_SCHEMA: expected schema=1 and files array"]
    entries = inventory["files"]
    if any(not isinstance(entry, dict) or not isinstance(entry.get("path"), str) for entry in entries):
        return ["INVALID_ENTRY: every entry needs a path string"]
    counts = Counter(entry["path"] for entry in entries)
    actual = set(project_files(root, filesystem_only=filesystem_only))
    errors.extend(f"DUPLICATE: {path}" for path, count in sorted(counts.items()) if count > 1)
    errors.extend(f"MISSING: {path}" for path in sorted(actual - counts.keys()))
    errors.extend(f"GHOST: {path}" for path in sorted(counts.keys() - actual))
    for entry in sorted(entries, key=lambda item: item["path"]):
        path = entry["path"]
        if path not in actual:
            continue
        if not (root / path).is_file():
            errors.append(f"MISSING_ON_DISK: {path}")
            continue
        role, purpose, relations = entry.get("role"), entry.get("purpose"), entry.get("relationships")
        if not isinstance(role, str) or not role.strip() or not isinstance(purpose, str) or len(purpose.strip()) < 15 or not isinstance(relations, list) or not relations or any(not isinstance(r, str) or not r.strip() for r in relations) or needs_review(entry):
            errors.append(f"NEEDS_REVIEW: {path}")
        elif path not in GENERATED and entry.get("review_sha256") != content_digest(root / path):
            errors.append(f"STALE_DESCRIPTION: {path}")
        elif path in GENERATED and entry.get("review_sha256") != "generated":
            errors.append(f"INVALID_GENERATED_REVIEW: {path}")
    return errors


def update_inventory(root: Path, inventory: dict, *, filesystem_only: bool = False) -> dict:
    """Discover additions and remove index deletions, never invent responsibilities."""
    by_path = {entry["path"]: entry for entry in inventory["files"]}
    files = []
    for path in project_files(root, filesystem_only=filesystem_only):
        files.append(by_path.get(path, {"path": path, "role": "NEEDS_REVIEW", "purpose": "NEEDS_REVIEW: İçeriği okuyup gerçek sorumluluğu açıklayın.", "relationships": ["NEEDS_REVIEW: Çağıranları, girdileri ve çıktıları doğrulayın."], "review_sha256": "generated" if path in GENERATED else "NEEDS_REVIEW"}))
    return {**inventory, "schema": 1, "files": files}


def render_tree(paths: list[str], root_name: str = "secondbrain") -> str:
    tree = {}
    for path in paths:
        node = tree
        for part in PurePosixPath(path).parts:
            node = node.setdefault(part, {})
    lines = [root_name + "/"]
    def walk(node, prefix):
        children = sorted(node)
        for index, name in enumerate(children):
            last = index == len(children) - 1
            lines.append(prefix + ("└── " if last else "├── ") + name + ("/" if node[name] else ""))
            walk(node[name], prefix + ("    " if last else "│   "))
    walk(tree, "")
    return "\n".join(lines)


def render_map(inventory: dict) -> str:
    entries = sorted(inventory["files"], key=lambda entry: entry["path"])
    sections = inventory.get("sections", [])
    lines = ["# " + inventory.get("title", "Respected Brain — Ayrıntılı Depo ve Mimari Atlası"), "", "> Bu belge `tools/repository_map.py` tarafından `docs/repository_inventory.json` içindeki gözden geçirilmiş açıklamalardan üretilir. Doğrudan bu Markdown dosyasını düzenlemeyin.", "", f"**Kapsam:** {len(entries)} proje dosyası. " + inventory.get("discovery", "Git indeksindeki dosyalar ve henüz eklenmemiş, ignore edilmeyen proje dosyaları dahildir.") + " Bağımlılık/üretim önbellekleri ayrı kategoriler olarak açıklanır.", ""]
    for section in sections:
        lines.extend(["## " + section["title"], "", section["body"].strip(), ""])
    lines.extend(["## Eksiksiz kaynak ağacı", "", "```text", render_tree([entry["path"] for entry in entries], inventory.get("project", "secondbrain")), "```", "", "## Dosya dosya sorumluluk ve ilişkiler", "", "Her kayıt bir dosyayı açıklar; boş `.gitkeep` ve paket `__init__.py` dosyaları da dahildir. Aşağıdaki yollar depo köküne göredir. Tarihsel belgeler canlı davranışın yetkili kaynağı değildir.", ""])
    previous = None
    for entry in entries:
        group = str(PurePosixPath(entry["path"]).parent)
        if group != previous:
            lines.extend(["### " + ("Depo kökü" if group == "." else group), ""])
            previous = group
        href = "../" + entry["path"].replace(" ", "%20")
        lines.extend([f"#### [`{entry['path']}`]({href})", "", f"**Rol:** {entry['role']}.", "", f"**Amaç / sorumluluk:** {entry['purpose']}", "", "**İlişkiler ve sınır:** " + " ".join(entry["relationships"]), ""])
    lines.extend(["## Haritayı güncel tutma sözleşmesi", "", "Yeni dosya keşfi otomatiktir; yeni kodun doğru anlamsal açıklaması otomatik olarak bilinemeyeceği için insan/ajan incelemesi gerekir. `--update` yeni kayıtları `NEEDS_REVIEW` olarak ekler ve indeksten silinenleri çıkarır. Dosya değişikliği açıklamanın artık doğru olduğuna dair yeniden inceleme gerektirir; LF/CRLF dönüşümü değişiklik sayılmaz.", "", "```sh", "python tools/repository_map.py --update", "# JSON içindeki NEEDS_REVIEW alanlarını gerçek rol/amaç/ilişkilerle doldur.", "python tools/repository_map.py --accept-reviewed path/to/changed.py", "python tools/repository_map.py --write", "python tools/repository_map.py --check", "python -m unittest tests.repository_map_test -v", "```", "", "`--accept-reviewed` yalnız açıklaması incelenmiş açık bir yolun içerik hash'ini günceller; içerik açıklaması üretmez. Aynı komutta birden fazla seçenek verilebilir. `--write` keşfedilmiş eksikleri görünür biçimde üretebilir ama `--check` her `NEEDS_REVIEW` kaydını reddeder. CI kapısı eksik/fazla/çift kayıtları, kayıp dosyaları, eski açıklama hash'lerini ve Markdown üretim farkını hata kodu 1 ile durdurur. Staged deletion Git indeksinden kalktığı için envanterden çıkar; yalnız diskten silinmiş izlenen dosya hata olarak kalır.", "", "JSON envanteri ve üretilmiş Markdown kendi kendini hash'leme döngüsünü önlemek için `generated` damgası taşır. JSON açıklamalarındaki değişiklik yine Markdown üretim karşılaştırmasıyla yakalanır. Diğer dosyalar SHA256 inceleme damgasıyla bağlıdır. Hash, açıklamanın doğru olduğunu matematiksel olarak kanıtlamaz; açıklamayı yazan kişi kodu ve ilişkileri okumakla sorumludur.", "", "Her dosya ekleme/silme/yeniden adlandırma ve davranış değişikliğinde bu güncelleme aynı iş içinde yapılır. CI çalışması dosyaya yazmaz. `--root` yalnız farklı bir kaynak checkout'u denetlemek içindir; kurulu AppRoot, DataRoot veya kişisel vault üzerinde bu aracı çalıştırmayın.", ""])
    lines.extend(["", "`--filesystem-only` Git çalıştırmaz; kök ignore kurallarını ve gözden geçirilmiş kaynak yollarını kullanır. Eksik bilinen dosya check hatası olarak korunur. Staged durum ve iç içe ignore sözleşmelerinin Git ile eşdeğerliği bu modun kapsamı değildir; CI normal Git modunu kullanır.", ""])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--accept-reviewed", action="append", default=[], metavar="PATH")
    parser.add_argument("--filesystem-only", action="store_true", help="No Git subprocesses; root ignore rules and reviewed paths, not staged status.")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        document = json.loads((root / INVENTORY).read_text(encoding="utf-8"))
        if args.update:
            counts = Counter(entry["path"] for entry in document["files"])
            duplicates = [path for path, count in counts.items() if count > 1]
            if duplicates:
                raise ValueError("DUPLICATE: " + ", ".join(duplicates))
            document = update_inventory(root, document, filesystem_only=args.filesystem_only)
        for path in args.accept_reviewed:
            entry = next((entry for entry in document["files"] if entry["path"] == path), None)
            if entry is None or path not in project_files(root, filesystem_only=args.filesystem_only) or needs_review(entry):
                raise ValueError("Cannot accept an absent or unexplained entry: " + path)
            entry["review_sha256"] = "generated" if path in GENERATED else content_digest(root / path)
        if args.update or args.accept_reviewed:
            (root / INVENTORY).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        rendered = render_map(document)
        if args.write:
            (root / MAP).write_text(rendered, encoding="utf-8", newline="\n")
        if args.check:
            errors = validate_inventory(root, document, filesystem_only=args.filesystem_only)
            if not (root / MAP).is_file() or (root / MAP).read_text(encoding="utf-8") != rendered:
                errors.append("MAP_DRIFT: " + MAP)
            for error in errors:
                print(error, file=sys.stderr)
            if errors:
                return 1
        print(f"Repository atlas: {len(document['files'])} files; " + ("check passed" if args.check else "generated" if args.write else "inventory updated"))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"Repository atlas error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
