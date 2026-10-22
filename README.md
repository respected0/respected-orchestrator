# Respected Orchestrator

Yerel AI görev motoru. Kodlama ajanlarını (Codex, Claude, Gemini, Antigravity, Cursor ya da kendi komutunuz) projenizin
yalıtılmış Git çalışma ağaçlarında çalıştırır, sonucu denetler (kapsam, doğrulama komutları, imzalı kanıt, yamanın
güncelliği) ve siz onaylamadan projenize hiçbir şey uygulamaz. Brain, not kasası, Hub ya da sürekli çalışan bir
servis gerektirmez; Brain hafızası isteğe bağlıdır.

## Kurulum

`RespectedOrchestrator-Windows-Setup.exe` kullanıcı başına kurulur, yönetici izni istemez, Python gerektirmez.
Bilgisayarda **Git** ve görevleri yapacak bir AI aracının komut satırı (oturumu açık) olmalıdır. Kurucu iki yol sunar:
**Respected Hub ile devam et** ya da **Yalnızca Orchestrator**. Kurucuyu yeniden çalıştırmak onarır/günceller, ayarları
değiştirir ya da kaldırır. Adım adım: [Kullanım rehberi](docs/USAGE.md).

| Ne | Nerede |
|---|---|
| Program | `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app\respected-orchestrator.exe` (kurucunun) |
| Ayarlar, görev çalışmaları, kanıtlar | `%LOCALAPPDATA%\Respected\RespectedOrchestrator\data` |

## Komutlar

Hepsi JSON yazar; hata `{"error": {"code", "message", "hint"}}`, çıkış kodu `0` başarı, `1` başarısız, `2` kullanım.
Tam liste ve istek biçimleri: [docs/COMMANDS.md](docs/COMMANDS.md).

- **Kurulum ve bakım:** `setup`, `repair`, `uninstall [--purge]`, `config [get|set]`, `health`, `status`.
- **Bağlantılar:** `memory connect [--write] | disconnect | status` (Brain hafızası),
  `integrations [set İSTEMCİ=on|off]` (AI araçlarına MCP kaydı), `mcp`, `rpp`.
- **Görevler:** `create` → `start` → `inspect` → `check` → `apply`; ayrıca `list`, `retry`, `cancel`, `maf`, `maf-approve`,
  `roles`, `plan`.
- **Projeler ve kampanyalar:** `project-start|status|resume|cancel`, `campaign-start|status|list`.

Hiçbir sonuç kendiliğinden uygulanmaz; bekleyen, başarısız, bayat ya da kurcalanmış sonuç `check`'ten geçmez. Güvenlik
sınırları ve bağlayıcı kurallar: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Beta yalnızca Windows'u destekler.

## Geliştirme

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -t .              # geçici depolar ve sahte çalışanlar; HOME yalıtılır
python packaging/build_dist.py                         # dist\RespectedOrchestrator\respected-orchestrator.exe
python -m unittest tests.packaging.test_frozen_build   # derlenmiş program, PATH'te Python yokken
python packaging/build_installer.py                    # dist\RespectedOrchestrator-Windows-Setup.exe
$env:RESPECTED_DATA_DIR = "$env:TEMP\orch-dev"; python -m respected_orchestrator status
```

Kaynak: `src/respected_orchestrator/engine/` (çalışma ağaçları, çalıştırıcı, Codex katmanı, doğrulama kum havuzu, süreç
denetimi, belirteç bütçesi), `workflows/` (MAF iş akışı, kampanyalar, projeler, planlayıcı, rol atama), `interfaces/`
(RPP, kurulum, MCP sunucusu, Brain hafızası, AI aracı kayıtları). Kurucu: `packaging/windows/orchestrator_setup.iss`.
Üç ürünün ortak sözleşmesi `docs/PRODUCT_CONTRACT.md` dosyasındadır.

## Lisans

[MIT lisansı](LICENSE).
