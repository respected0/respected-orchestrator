# Orchestrator komutları

Kurulu program: `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app\respected-orchestrator.exe` (PATH'e eklenmez; tam yolu
kullanın). Kaynaktan: `python -m respected_orchestrator`. İç yapı ve kurallar: [ARCHITECTURE.md](ARCHITECTURE.md).

Ortak kurallar (üç ürün aynı, bkz. ekosistem kökündeki `docs/PRODUCT_CONTRACT.md`):

- Çıktı UTF-8 JSON'dur. Hata: `{"error": {"code", "message", "hint"}}`.
- Çıkış kodu: `0` başarı, `1` işlem başarısız, `2` kullanım ya da geçersiz ayar.
- `--version` (`respected-orchestrator <sürüm>`), `--help` ve `<komut> --help` hiçbir şey kurmaz ya da yazmaz.
- Veri klasörü: `%LOCALAPPDATA%\Respected\RespectedOrchestrator\data`; geliştirmede ve testte `RESPECTED_DATA_DIR` ile
  değişir. (`--data-root` motorun kendi alt süreçleri içindir, kişiler kullanmaz.)
- JSON isteği alan komutlar onu **stdin**'den okur: `Get-Content -Raw istek.json | & $exe create`.

## Kurulum ve bakım

| Komut | Ne yapar |
|---|---|
| `setup` | Kurucunun yazdığı programı `distribution.json` ile doğrular ve kaydeder, veri klasörünü hazırlar. Kurucu çalıştırır; elle de çalışır. |
| `repair` | Programı doğrular (bozuksa kurucuyu yeniden çalıştırmayı söyler), kurulum kaydını yeniler. |
| `uninstall [--purge]` | AI araçlarındaki kendi MCP girdilerini ve kurulum kaydını kaldırır. `--purge` ayarları ve çalışma verisini de siler. Program dosyaları kaldırıcınındır. |
| `config` | Bütün ayarları gösterir (gizli değerler `***set***`). |
| `config get ANAHTAR` | Bir ayarı gösterir. |
| `config set A=D [A=D...]` | Doğrular ve uygular; geçersizse hiçbir şey yazmaz (çıkış 2). Mantıksal değerler `true`/`false`. Anahtarlar: [USAGE.md](USAGE.md#8-ayarlar). |
| `health` | Veri klasörü yazılabilir mi, Git var mı, en az bir çalışan aracı bulunuyor mu, motor anahtarı okunabilir mi; sağlıklıysa 0. |
| `status` | Sürüm, veri klasörü, bulunan çalışan araçlarının yolları ve Git. |

## Brain hafızası ve AI araçları

| Komut | Ne yapar |
|---|---|
| `memory connect` | Kurulu Brain'den okuma izni alır ve kaydeder. Brain kurulu değilse `NOT_INSTALLED`. |
| `memory connect --write` | Aynı, ayrıca Brain'in gelen kutusuna not yazma izni. |
| `memory disconnect` | İzni Brain tarafında iptal eder, ayarları temizler. |
| `memory status` | `{"connected", "write", ...}` |
| `integrations` | Hangi AI aracında MCP girdisi olduğunu ve olabileceğini gösterir. |
| `integrations set İSTEMCİ=on\|off [...]` | Kendini AI araçlarına MCP sunucusu olarak kaydeder ya da kaydı kaldırır. İstemciler: `claude-code`, `claude-desktop`, `codex`, `cursor`, `gemini`, `windsurf`. Girdi kurulu programı gösterir (`respected-orchestrator.exe mcp`); başka girdiler korunur. |
| `mcp [--allow-auto-apply] [--allow-privileged]` | AI araçları için stdio MCP sunucusu. İki bayrak da MCP üzerinden normalde reddedilen işlemleri açar ([ARCHITECTURE.md](ARCHITECTURE.md#6-mcp-sunucusu-ve-izinler)); Hub ve `integrations` hiçbirini vermez. |
| `rpp` | stdin'den bir RPP isteği okur, stdout'a bir yanıt yazar. Hub bunu kullanır. |

**RPP işlemleri** (protokol sürümü `"1"`): `manifest`, `health`, `settings.schema|validate|apply|readback`,
`integrations.plan|apply|rollback`, `memory.connect|disconnect|status`.

**MCP araçları:** `orchestrator_status`, `orchestrator_plan`, `orchestrator_task_start`, `orchestrator_project_start`,
`orchestrator_list`, `orchestrator_progress`, `orchestrator_evidence`, `orchestrator_resume`, `orchestrator_cancel`,
`orchestrator_apply`, `orchestrator_memory_note` (yalnızca hafıza yazma izni varsa).

## Görevler

| Komut | Girdi | Ne yapar |
|---|---|---|
| `create` | stdin: görev isteği | Görevi doğrular, rolleri çözer, imzalı isteği saklar; `run_id` döner. Başlatmaz. |
| `start RUN_ID` | | Ayrık bir denetleyici başlatır; Hub ya da terminal kapansa da sürer. |
| `list` | | Görevler, en yenisi önce. |
| `inspect RUN_ID` | | Durum, aşamalar, değişiklikler, kullanım. |
| `check RUN_ID` | | Sonucu yeniden doğrular: imzalı kanıt, kapsam, doğrulama, yamanın projeye uyması, projenin güncelliği. |
| `apply RUN_ID` | | `check`'ten geçen yamayı projeye uygular (`git apply`); commit atmaz. Çalışan süreçlerin içinden reddedilir. |
| `retry RUN_ID` | | Başarısız, zaman aşımına uğramış ya da iptal edilmiş görevi yeni bir çalışma olarak yeniden dener (toplam en fazla üç deneme). |
| `cancel RUN_ID` | | Görevi ve bütün süreç ağacını durdurur. |
| `maf RUN_ID` | | Görevi MAF iş akışıyla yürütür: uygulama, gözden geçirme, düzeltme turları. |
| `maf-approve RUN_ID` | | MAF sonucunu insan olarak onaylar; etkileşimli terminal ister, MCP'den yapılamaz. |
| `roles` | stdin: `{"roles": {...}, "needed": ["implementer", ...]}` | Rol atamasını kuru çalıştırır: hangi araç ve profilin, hangi kaynaktan seçileceğini gösterir. |
| `plan` | stdin: `{"goal", "project_root", "context_files"?, "roles"?}` | `planner` rolündeki araçla bir proje taslağı çıkarır, motorla doğrular, `drafts/` altına kaydeder; başlatmaz. |

**Görev isteği** (`create`):

| Alan | Ne |
|---|---|
| `project_root` | Git projesinin mutlak yolu (zorunlu) |
| `task` | Çalışana verilecek iş (zorunlu) |
| `kind` | `read` ya da `write` |
| `ownership` | Çalışanın değiştirebileceği göreli yollar |
| `forbidden` | Dokunulmayacak yollar ya da adlar |
| `acceptance` | Doğrulama komutları, her biri JSON argüman dizisi; `write` görevinde en az bir tane |
| `timeout_seconds` | Görevin en uzun süresi; verilmezse `default_timeout_seconds` |
| `worker`, `worker_profile` | Çalışan araç ve profili; verilmezse ayarlardaki varsayılan |
| `roles` | Rol atamaları: `{rol: profil \| {tool, profile, fallbacks}}` |
| `workflow` | MAF ayarları: `reviewer_tool`, `reviewer_profile`, `deep_review_tool`, `deep_review_profile`, `max_corrections` (0–2), `escalate_profile`, `require_independent_review` |
| `memory` | `{"use": true, "query"?: "..."}`: Brain hafızasından parça ekle (bağlantı gerekir) |
| `context_paths` | Çalışana bağlam olarak verilecek dosyalar |
| `command` | Yalnızca `worker: "custom"` için çalışan komutu (MCP'den reddedilir) |

Örnek bir okuma görevi:

```json
{
  "project_root": "C:/yol/git/projesi",
  "task": "src klasörünü incele ve genel giriş noktalarını açıkla. Dosya değiştirme.",
  "worker": "codex",
  "kind": "read",
  "ownership": ["src"],
  "forbidden": [".env", "credentials"],
  "acceptance": [],
  "timeout_seconds": 120
}
```

## Projeler ve kampanyalar

| Komut | Girdi | Ne yapar |
|---|---|---|
| `project-start` | stdin: proje tanımı | Aşamalı bir projeyi ayrık denetleyiciyle başlatır; kimliğini döner. |
| `project-status ID` | | Aşamalar, hatlar, doğrulamalar. |
| `project-resume ID` | | Durmuş bir projeyi kaldığı yerden sürdürür. |
| `project-cancel ID` | | Projeyi ve hatlarını durdurur. |
| `campaign-start` | stdin: kampanya tanımı | Paralel hatları ayrık denetleyiciyle başlatır; bitince son incelemeyi bir kez çalıştırır. |
| `campaign-status ID` | | Hatların durumu ve son inceleme. |
| `campaign-list` | | Kampanyalar, en yenisi önce. |

**Proje tanımı:** `{"goal", "budget": {"max_seconds", "max_phase_attempts"}, "phases": [{"name", "after", "auto_apply",
"lane_timeout_seconds", "verify": [{"command", "cwd", "timeout_seconds"}], "workstreams": [{"name", "after", "request"}]}]}`.
Her hattın `request`'i bir görev isteğidir; aynı aşamada paralel çalışan hatlar ayrık dosyalara sahip olmalıdır. `plan`
komutunun ürettiği taslak bu biçimdedir.

**Kampanya tanımı:** `{"goal", "workstreams": [{"name", "after"?, "request"}] (1–8 hat), "lane_timeout_seconds"?,
"final"?: {"command"?, "timeout_seconds"?, "allow_apply"?, "skip"?}}`. Hat adları küçük harfli kısa adlardır (`a-z0-9-`);
`after` bağımlılıkları döngü içeremez. `final` verilmezse son inceleme `master` rolündeki araçla (yoksa `claude -p`) yapılır.

`project-run` ve `campaign-run` denetleyicilerin kendi giriş noktalarıdır; elle çalıştırılmaz.
