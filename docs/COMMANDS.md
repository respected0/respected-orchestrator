# Orchestrator komutları

Kurulu program: `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app\rorch.exe` (PATH'e eklenmez; tam yolu
kullanın). Kaynaktan: `python -m respected_orchestrator`. İç yapı ve kurallar: [ARCHITECTURE.md](ARCHITECTURE.md).

Ortak kurallar (üç ürün aynı, bkz. [PRODUCT_CONTRACT.md](PRODUCT_CONTRACT.md)):

- Çıktı UTF-8 JSON'dur. Hata: `{"error": {"code", "message", "hint"}}`.
- Çıkış kodu: `0` başarı, `1` işlem başarısız, `2` kullanım ya da geçersiz ayar.
- `--version` (`rorch <sürüm>`), `--help` ve `<komut> --help` hiçbir şey kurmaz ya da yazmaz.
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
| `health` | Veri klasörü yazılabilir mi, Git var mı, en az bir çalışan aracı bulunuyor mu, motor anahtarı okunabilir mi; sağlıklıysa 0. Yanıttaki `wizard` salt-okunur ilk-görev rehberidir. |
| `status` | Sürüm, veri klasörü, bulunan çalışan araçlarının yolları ve Git. |
| `daemon start` | Kalıcı motoru başlatır (çalışıyorsa onu gösterir). Çalışan motor başka sürümse reddeder. Çıktı: `running`, `pid`, `version`, `data_root`, `pipe`. Başlatamazsa `ENGINE_UNAVAILABLE` (çıkış 1). |
| `daemon status` | Çalışan motorun durumunu verir; çalışmıyorsa `{"running": false}` ve çıkış 1. |
| `daemon stop` | Motoru durdurur ve sürecin çıkmasını bekler; çalışmıyorsa hata değildir (`stopped: false`). |
| `daemon restart` | Durdurup yeniden başlatır (sürüm uyuşmazlığında çare). |
| `session list [PROJE]` | Kalıcı motorun canlı sohbet oturumlarını ve kayıtlı konuşmaları listeler. Motor yoksa başlatır. |
| `terminal list [PROJE]` | Ajan terminallerini listeler (ADR-035): kimlik, klasör, ajan, çalışıyor mu, çıkış kodu, boyut. Başlatma, yazma ve izleme bu uçta yoktur (yalnız tanınan masaüstü). |
| `session watch PROJE` | Canlı akış (`events.subscribe`, ADR-034): o projenin oturumlarıyla ilgili her bildirimi geldiği anda bir JSON satırı olarak yazar (`{"ipc", "event", "data"}`; `session.event` çalışan turun bir olayı, `session.state` oturumun yeni durumu). Ctrl+C ya da motorun durmasıyla biter. |
| `task start` (stdin'den JSON), `task status\|cancel\|retry RUN_ID` | Tek görev koşusu, **kalıcı motor üzerinden** (`task.*` komutları; masaüstündeki "Yeni görev" ile aynı yol). İstek gövdesi `create` ile aynıdır; `start` oluşturur ve başlatır, `status` günlükleri kırpılmış durumu verir. Bu yoldan `custom` işçi ve `command` seçilemez, kabul komutları yalnız `mcp_acceptance_allow` ayarındaki önekleri taşıyabilir; bunlar için süreç içi `create` / `start` kullanılır. |
| `session describe [AJAN]` | Ajanın tanımı (`agent.describe`, ADR-033): hazırlık, arayüzler, yetenekler, izin kipleri, model seçimi; her alan `native` / `unsupported` / `unverified` ve kaynağıyla. Sohbet arayüzü olan ajanlarda `chat_permissions` (`modes`, `always_denied`, `project_config`, `source`) izin politikasını makine okunur verir; sohbet arayüzü olmayanda boştur. Ajan verilmezse bilinen bütün ajanlar (`{"agents": [...]}`). Yalnız salt-okunur yoklama yapar, ajan başlatmaz. |
| `session models [AJAN]`, `session defaults` | Ajanın kendi model listesi; kayıtlı varsayılan ajan/model (değiştirme bu uçta yoktur). |
| `session start\|send\|events\|retry\|interrupt\|cancel\|resume\|transcript\|forget` | İstek gövdesi stdin'den JSON: `project_id` (zorunlu, oturumu adresler), `session_id`, `project_root` (var olan mutlak klasör), `agent`, `model`, `text`, `resume_session`, `continue_conversation`. Yanıt motorun kendi yanıtıdır; hata `{"error":{code,message,hint}}`, çıkış 1 (kullanım hatası 2). Oturum başlatma yalnız doğrulanmış sohbet adaptörü olan ajanlarda (şimdilik `opencode`) çalışır. Onay komutu yoktur. |

## Brain hafızası ve AI araçları

| Komut | Ne yapar |
|---|---|
| `memory connect` | Kurulu Brain'den okuma izni alır ve kaydeder. Brain kurulu değilse `NOT_INSTALLED`. |
| `memory connect --write` | Aynı, ayrıca Brain'in gelen kutusuna not yazma izni. |
| `memory disconnect` | İzni Brain tarafında iptal eder, ayarları temizler. |
| `memory status` | `{"connected", "write", ...}` |
| `integrations` | Hangi AI aracında MCP girdisi olduğunu ve olabileceğini gösterir. |
| `integrations set İSTEMCİ=on\|off [...]` | Kendini AI araçlarına MCP sunucusu olarak kaydeder ya da kaydı kaldırır. İstemciler: `claude-code`, `claude-desktop`, `codex`, `cursor`, `windsurf`, `opencode`. Girdi kurulu programı gösterir (`rorch.exe mcp`); başka girdiler korunur. OpenCode girdisi `~/.config/opencode/opencode.json` içindeki `mcp.servers` altına yazılır ve geri alma önceki dosyayı byte düzeyinde geri yükler. |
| `provider-key set\|status\|clear` | OpenRouter anahtarı: `set` anahtarı stdin'den okur ve Windows DPAPI ile şifreli saklar (ekrana ya da dosyaya düz metin yazılmaz), `status` yalnızca saklı olup olmadığını söyler, `clear` siler. |
| `provider-models [--free]` | OpenRouter'ın herkese açık model listesi (anahtar gerekmez, ağ kapısı yine açık olmalı); `--free` yalnızca bütün fiyatları 0 olan modelleri gösterir. |
| `mcp [--allow-auto-apply] [--allow-privileged]` | AI araçları için stdio MCP sunucusu. İki bayrak da MCP üzerinden normalde reddedilen işlemleri açar ([ARCHITECTURE.md](ARCHITECTURE.md#6-mcp-sunucusu-ve-izinler)); Masaüstü uygulaması ve `integrations` hiçbirini vermez. |
| `rpp` | stdin'den bir RPP isteği okur, stdout'a bir yanıt yazar. Masaüstü uygulaması ve Brain bunu kullanır. |

**RPP işlemleri** (protokol sürümü `"1"`): `manifest`, `health`, `settings.schema|validate|apply|readback`,
`integrations.plan|apply|rollback`, `memory.connect|disconnect|status`, `evidence.view`,
`github.issue_import|pr_plan|pr_create|ci_plan`.

**Masaüstü sohbet IPC komutları** (`rpp` değil, uygulamanın yerel motor bağlantısı): `sessions.list`, `session.start|send|events|retry|interrupt|cancel|resume`, `session.rename|pin|archive|export`, `session.models` (ajan CLI'ının model listesi; `{"agent"}` ister), `agent.describe` (ajan tanımı; `{"agent"}` isteğe bağlı). `runs.list` satırları `lane` (`needs_you` / `working` / `ready` / `archive`) ve `display` taşır; ikisi de okuma anında türetilir. **Görev komutları:** `task.start` (istek gövdesi `create` ile aynı; `{run_id, status, pid}` döner), `task.status|cancel|retry` (`{"run_id"}`). `task.permission.answer` (`{run_id, request_id, option_id}`) yalnız `TERMINAL` sınıfıdır: masaüstü görev grubundan gelir, CLI fiili ve MCP aracı yoktur (MCP cevaplayamaz). `runs.list` satırı bekleyen izni `pending_permission` (`{request_id, method, title, options, created_at, expires_at}`) olarak taşır; pano bunu 4 saniyelik yoklamayla Türkçe gösterir. Retler `PERMISSION_NOT_FOUND`, `PERMISSION_CLOSED`, `PERMISSION_ALREADY_ANSWERED`, `PERMISSION_EXPIRED`, `PERMISSION_OPTION_INVALID`, `PERMISSION_REQUEST_INVALID`, `FORBIDDEN`; ekran bunları Türkçe metne çevirir.

**Kabuğun yerel (Tauri) komutları — talimat dosyaları:** `discover_instruction_files {folder}` proje kökünü ve alt klasörleri (3 düzey, sınırlı) tarayıp `AGENTS.md`/`CLAUDE.md` satırlarını döner; `read_user_instruction {name}` yalnız `~/.claude/CLAUDE.md` ve `~/.codex/AGENTS.md` dosyalarını okur (yazma yoktur); `write_instruction_file {folder, name, text, expected?, force?}` en çok 256 KB düz metni tek yazmayla kaydeder, `expected` verilen metinle uyuşmazsa `FILE_CHANGED` döner ve `force` olmadan yazmaz. Dosya adı ve klasör sınırı native komutta doğrulanır.

**Ayarlar ekranı:** masaüstü `settings.schema`, `settings.readback` ve `settings.validate`'i okur; `settings.apply` ekrandan iletilmez, değişiklik kabuğun yerel onay penceresinden geçer (ARCHITECTURE "Masaüstü ayarlar ekranı").

**Komut kataloğu:** motor komutlarının tek tablosu `engine/catalog.py`'dir; `rorch session` fiilleri, `orchestrator_session_*` MCP araçları ve masaüstünün iletebildiği komut listeleri ondan üretilir. `catalog.list` (salt okunur) çağıranın çalıştırabildiği komutları verir: `{"commands": [{"name", "action", "cli", "mcp", "desktop"}]}`; yetkili komutlar ortak uçta görünmez. Yeni komut eklerken tabloya bir satır yazın, sonra `python -m respected_orchestrator.engine.catalog` ile masaüstü dosyalarını yeniden üretin.
Motor, masaüstünün göstereceği her şeyi tutar: `sessions.list {project_id, query?, include_archived?}` → `{sessions, conversations}` (`conversations`: bu çalışmanın oturumları ve kaydedilmiş
konuşmalar; satır `id,title,state,project_root,updated,saved,pinned,archived,match` taşır, sabitlenmiş önce, sonra en yeni; arşivliler `include_archived` verilmedikçe gizli, `query` Türkçe katlamalı süzer; `session.rename {id,title}` (en çok 120), `session.pin {id,pinned}`, `session.archive {id,archived}` ve `session.export {id,format: "markdown"|"json"}` → `{id,title,format,filename,text}` (motor dosya yazmaz; dosyayı kabuk kaydeder)); `session.defaults` (okuma) → `{agents, modes, agent, model}`; `session.start` isteğe bağlı `mode` alır ve `session.mode.set {session_id, mode}` oturumun izin kipini bir sonraki turdan başlayarak değiştirir (`default` / `accept-edits` / `bypass-permissions`; `default` dışı yalnız tanınan masaüstünden, yoksa `FORBIDDEN`; `MODE_INVALID`, `TURN_RUNNING`); `session.defaults.set {model, agent?}` (ayar sınıfı;
model ajanın listesinde değilse `MODEL_INVALID` ile reddedilir ve kaydedilmez); `session.transcript {session_id, before?, limit?}` → konuşmanın bir sayfası (en yeni; varsayılan 50, en çok 200 tur): `turns`, `first` (dönen ilk turun sırası; bir üst sayfa için `before` olarak yollanır, 0 ise daha eskisi yok), `total`, bütün konuşmanın `usage` toplamı ve tur çalışıyorsa `live` (`{turn, events}`: o ana kadarki olaylar); geçersiz `before`/`limit` → `PAGE_INVALID`;
`session.events` tur çalışırken `result: null` ve `live` (o ana kadarki olaylar) döner;
**ajan terminali (ADR-035):** `terminal.list` → `{terminals}`; `terminal.start {project_root, agent?, mode?, cols?, rows?}` → terminalin görünümü (`mode` ajanın CLI'ında doğrulanmış bir bayraksa geçerlidir; `default` bayrak eklemez ve kayıt `mode` alanını taşır); `terminal.start {session_id}` boştaki bir sohbet oturumunu aynı ajan oturumuyla terminale taşır; konuşmanın kipi CLI'da karşılığı varsa taşınır (oturum kayıtlı konuşma olarak kalır; `TURN_RUNNING`, `RESUME_INVALID`, `HANDOFF_UNSUPPORTED`); `terminal.input {terminal_id, data}` (`data`: yazılanın base64'ü, en çok 64 KiB); `terminal.resize {terminal_id, cols, rows}`; `terminal.kill {terminal_id}`; `terminal.attach {terminal_id}` → yanıttan sonra bağlantı o terminalin çıktısını taşır (`terminal.data` base64, `terminal.exit`, `terminal.ping`). `list` dışındakiler `TERMINAL` sınıfıdır; hata kodları `TERMINAL_UNKNOWN`, `ROOT_INVALID`, `SIZE_INVALID`, `INPUT_INVALID`, `AGENT_UNKNOWN`, `AGENT_NOT_INSTALLED`, `MODE_UNSUPPORTED`, `TOO_MANY_TERMINALS`, `TERMINAL_START_FAILED`, `TERMINAL_UNREACHABLE`;
`events.subscribe {project_id}` → `{subscribed, events}`; yanıttan sonra **o bağlantı tek yönlü akışa döner** (motor bildirim yazar, istemciden okumaz; bitirmek için bağlantı kapatılır; masaüstü iletim listelerinde yoktur, akışı kabuk açar);
`session.forget {session_id}` (kayıt silme; canlı oturum önce bitirilmelidir); `session.start` `{continue_conversation}` ile kaydedilmiş konuşmayı sürdürür,
`agent`/`model` verilmezse kayıtlı varsayılan kullanılır. Hata yanıtı `error.reason` içinde kararlı bir kod taşır (`MODEL_INVALID`, `ROOT_INVALID`,
`TEXT_EMPTY|TEXT_TOO_LONG|TEXT_UNSAFE`, `CHAT_DISABLED`, `AGENT_NOT_INSTALLED`, `SESSION_UNKNOWN`, `SESSION_LIVE`…); ekran metni bu koda göre yazar.

**MCP araçları:** `orchestrator_status`, `orchestrator_plan`, `orchestrator_task_start`, `orchestrator_project_start`,
`orchestrator_list`, `orchestrator_progress`, `orchestrator_evidence`, `orchestrator_resume`, `orchestrator_cancel`,
`orchestrator_apply`, `orchestrator_memory_note` (yalnızca hafıza yazma izni varsa).

**MCP oturum araçları** (kalıcı motorun canlı sohbet oturumları; `rorch session` ve masaüstüyle aynı oturumlar): `orchestrator_session_list`, `_start`, `_send`,
`_events`, `_transcript`, `_interrupt`, `_cancel`, `_resume`. Alanlar `rorch session` ile aynıdır; onay ve varsayılan değiştirme yoktur.
`orchestrator_agent_describe` (salt okunur) `rorch session describe` ile aynı cevabı verir.

## Görevler

| Komut | Girdi | Ne yapar |
|---|---|---|
| `create` | stdin: görev isteği | Görevi doğrular, rolleri çözer, imzalı isteği saklar; `run_id` döner. Başlatmaz. |
| `start RUN_ID` | | Ayrık bir denetleyici başlatır; Uygulama ya da terminal kapansa da sürer. Aynı veri kökünde aynı anda tek görev çalışır; sonradan başlatılan görev kendi süresi içinde sıraya girer. |
| `list` | | Görevler, en yenisi önce. |
| `inspect RUN_ID` | | Durum, aşamalar, değişiklikler, kullanım. |
| `artifact RUN_ID` | stdin: `{"name": "..."}` | Görevin kanıt paketindeki adı verilen çıktıyı (örneğin yama) okur; yalnızca okur. |
| `check RUN_ID` | | Sonucu yeniden doğrular: imzalı kanıt, kapsam, doğrulama, yamanın projeye uyması, projenin güncelliği. |
| `apply RUN_ID` | | `check`'ten geçen yamayı projeye uygular (`git apply`); commit atmaz. Çalışan süreçlerin içinden reddedilir. |
| `retry RUN_ID` | | Başarısız, zaman aşımına uğramış ya da iptal edilmiş görevi yeni bir çalışma olarak yeniden dener (toplam en fazla üç deneme). |
| `cancel RUN_ID` | | Görevi ve bütün süreç ağacını durdurur. |
| `maf RUN_ID` | | Görevi MAF iş akışıyla yürütür: uygulama, gözden geçirme, düzeltme turları. |
| `maf-approve RUN_ID` | | MAF sonucunu insan olarak onaylar; etkileşimli terminal ister, MCP'den yapılamaz. |
| `roles` | stdin: `{"roles": {...}, "needed": ["implementer", ...]}` | Rol atamasını kuru çalıştırır: hangi araç ve profilin, hangi kaynaktan seçileceğini gösterir. |
| `ledger` | stdin (isteğe bağlı): `{"catalog"?, "at"?, "billing"?, "task_class"?, "limit"?}` | Bu kurulumun imzalı koşu kanıtından görev sınıfı başına maliyet/kalite raporu (salt okunur, ağ yok). `catalog`: fiyat girdileri; `billing`: `{araç: "api_metered"\|"subscription"\|"unknown"}` (beyan yoksa `unknown`). Bilinmeyen ya da hesaplanamayan maliyet `null`'dır ve nedeni `uncomputable`'da yazar, hiçbir zaman 0 değildir. |
| `team` | stdin (isteğe bağlı): `{"team": {...}}` | Takım profillerini gösterir (`teams.json` yoksa rol ayarlarından türetilir, yazılmaz) ya da doğrulayıp kaydeder; içeriği değişen profilin `rev`'i artar. Bilinmeyen anahtar, kimlik bilgisi benzeri değer ve rolle uyumsuz yetenek reddedilir. |
| `handoff` | stdin: `{"run_id", "message": {to, scope:{paths}, reason, next_action, evidence?, note?, max_hops?, retry_budget?}}` | Bir koşu adına devir önerir. Gönderen ve kapsam koşunun imzalı kaydından gelir (mesajdaki `from` farklıysa reddedilir); `team_loop` karar verir: `deliver`, `duplicate`, `reject`, `escalate`. Yalnız `deliver` olay deposuna yazılır; hiçbir şey başlatmaz/uygulamaz. |
| `inbox PROFIL` | | Profile gelen, imzası doğrulanmış devirler. |
| `escalation RUN_ID` | | Durmuş bir koşunun açıklama kartı: sorun, önerilen adım, kalan bütçe, izinli eylemler ve olay zaman çizelgesi. |
| `operator RUN_ID retry\|resume\|dismiss BAĞLAMA [--ack=auth_checked]` | | Vaka kartındaki bir eylemi yürütür; etkileşimli terminal ister, bağlama kartla eşleşmelidir. `resume` otomatik durdurmaları kaldırır ama deneme, süre, belirteç sınırlarını ve güvenlik reddini asla. `apply` diye bir eylem yoktur. |
| `plan` | stdin: `{"goal", "project_root", "context_files"?, "roles"?}` | `planner` rolündeki araçla bir proje taslağı çıkarır, DAG/ownership doğrulamasıyla birlikte motorla doğrular, `drafts/` altına `spec` ve `dag` olarak kaydeder; hiçbir worker/proje/kampanya başlatmaz. |
| `coordinate` | stdin: `{"goal", "project_root", "spec"?, "context_files"?, "roles"?}` | `coordinator` rolündeki araçla ya da verilen `spec` ile plan ve rol ataması üretir. Aynı DAG/project validator'larından geçirir; `command`, `auto_apply`, `allow_apply` ve `shell` önerilerini reddeder. `drafts/` altına doğrulanmış taslak yazar; worker/proje/kampanya başlatmaz ve apply etmez. Açık atama kullanılamıyorsa `ROLE_UNAVAILABLE` döner. |
| `integrate` | stdin: `{"project_root", "run_ids": ["RUN-A", "RUN-B"], "verification": [{"command": [...], "timeout_seconds"?}]}` | İki doğrulanmış sonucu geçici detached worktree'de birleştirir ve birleşik doğrulamayı çalıştırır. Gerçek repoyu değiştirmez; başarıda karar için imzalı `integration.json` ve `combined.patch` üretir (`ready_for_decision`). Çakışma, HEAD drift veya doğrulama hatasında kanıt yayımlamaz. |

**Görev isteği** (`create`; Beta.4 ek alanları `profile`: takım profili kimliği, `handoff`: sürdürülen devrin kimliği; ikincisi `profile` ister):

| Alan | Ne |
|---|---|
| `project_root` | Git projesinin mutlak yolu (zorunlu) |
| `task` | Çalışana verilecek iş (zorunlu) |
| `kind` | `read` ya da `write` |
| `ownership` | Çalışanın değiştirebileceği göreli yollar; proje içinde kalmalı, `.git` ve proje kökünün kendisi olamaz |
| `forbidden` | Dokunulmayacak yollar ya da adlar |
| `acceptance` | Doğrulama komutları, her biri JSON argüman dizisi; `write` görevinde en az bir tane |
| `timeout_seconds` | Görevin en uzun süresi (1–3600 saniye); verilmezse `default_timeout_seconds` |
| `worker`, `worker_profile` | Çalışan araç ve profili; verilmezse ayarlardaki varsayılan |
| `roles` | Rol atamaları: `{rol: profil \| {tool, profile, fallbacks}}` |
| `workflow` | MAF ayarları: `reviewer_tool`, `reviewer_profile`, `deep_review_tool`, `deep_review_profile`, `max_fix_rounds` (0–5, varsayılan 2), `escalate_profile`, `require_independent_review` |
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
| `project-resume ID` | terminal | Doğrulanmış checkpoint sınırından sürdürür; onay gerekiyorsa reddeder. |
| `project-approve ID` | terminal | Kaynak/HEAD drift, bilinmeyen adım veya doğrulanamayan checkpoint için tek kullanımlık onay kaydı oluşturur. |
| `project-cancel ID` | | Projeyi ve hatlarını durdurur. |
| `campaign-start` | stdin: kampanya tanımı | Paralel hatları ayrık denetleyiciyle başlatır; bitince son incelemeyi bir kez çalıştırır. |
| `campaign-status ID` | | Hatların durumu ve son inceleme. |
| `campaign-cancel ID` | | Bekleyen/çalışan kampanya hatlarını iptal eder; son master başlatılmaz. |
| `campaign-list` | | Kampanyalar, en yenisi önce. |

**Proje tanımı:** `{"goal", "budget": {"max_seconds", "max_phase_attempts"}, "phases": [{"name", "after", "auto_apply",
"lane_timeout_seconds", "verify": [{"command", "cwd", "timeout_seconds"}], "workstreams": [{"name", "after", "request"}]}]}`.
Her hattın `request`'i bir görev isteğidir; aynı aşamada paralel çalışan hatlar ayrık dosyalara sahip olmalıdır. Aşama
`after` bağımlılıkları önceki aşamanın bütün hatlarına genişler; aynı aşamadaki `after` yalnızca o aşamanın hatlarını
bağlar. `plan` komutunun ürettiği taslak bu biçimdedir ve geçerli taslakta düğümlerin `id`, `depends_on`, `ownership`,
`forbidden`, `acceptance`, `budget` alanlarını, topolojik sırayı ve `valid` bayrağını taşıyan bir `dag` bulunur. Döngü,
bilinmeyen bağımlılık, paralel ownership çakışması veya geçersiz verify komutu taslağı `invalid` yapar.

**Kampanya tanımı:** `{"goal", "workstreams": [{"name", "after"?, "request"}] (1–8 hat), "lane_timeout_seconds"?, "max_parallel"?,
"final"?: {"command"?, "timeout_seconds"?, "allow_apply"?, "skip"?}}`. Hat adları küçük harfli kısa adlardır (`a-z0-9-`);
`after` bağımlılıkları döngü içeremez. `max_parallel` 1–8 arasındadır; verilmezse `min(4, hat sayısı)` kullanılır. Aynı
proje kökünde ownership kapsamı çakışan hatlar sırayla çalıştırılır. `campaign-cancel ID` bekleyen ve çalışan hatları
iptal eder; iptal edilen kampanyada son master başlatılmaz. `final` verilmezse son inceleme `master` rolündeki araçla
(yoksa `claude -p`) yapılır.

`project-run` ve `campaign-run` denetleyicilerin kendi giriş noktalarıdır; elle çalıştırılmaz.

`project-resume` yalnızca `resume`, `campaign`, `apply`, `verify`, `review`, `complete` adım whitelist'ini kabul eder.
Canlı bir kilit sahibi varsa hiçbir süreç başlatmaz; yalnızca ölü PID veya bozuk kilidi temizler. Kaynak parmak izi,
Git HEAD, checkpoint adımı veya checkpoint bütünlüğü değişmişse komut `human approval` hatası verir. Onay:

```powershell
& $exe project-approve PROJECT_ID
& $exe project-resume PROJECT_ID
```

Onay yalnızca etkileşimli terminalde alınır. `RESPECTED_ORCH_CHILD=1` ve `RESPECTED_ORCH_DELEGATED=1` alt süreçleri
reddedilir; MCP'de onay aracı yoktur. Onay verilse bile `auto_apply=false` aşamasında apply başlamaz. Bayat patch
zorlanmaz; `stale patch` nedeniyle bloke kalır.

## Kanıt görünümü

```powershell
rorch evidence run-2026-11-03-abc
```

İmzalı kanıtı salt-okunur, redakte edilmiş sunum modeli olarak döndürür. Patch/proje değişmişse `stale`,
imza geçersizse yapılandırılmış hata verir. Aynı çıktı RPP `evidence.view` operasyonundan da alınır.

```powershell
'{"rpp":"1","op":"evidence.view","payload":{"run_id":"run-2026-11-03-abc"}}' | rorch rpp
```

`health` yanıtındaki `wizard` alanı ilk görev ve sonraki adımı gösterir; onay yalnızca etkileşimli terminalde
`maf-approve` ile alınır, MCP/agent üzerinden onay verilemez.

## GitHub (GH-01/02/03)

`gh` CLI ile oturum açmış olmayı gerektirir. Issue ve CI geri bildirimi güvenilmeyen plan girdisidir; otomatik
worker başlatılmaz, merge komutu üretilmez.

| Komut | Girdi | Ne yapar |
|---|---|---|
| `github-import-issue` | stdin: `{"repo":"owner/name","number":1,"allowed_labels":["bug"]}` | Issue'yu salt-okunur içe aktarır; etiketleri izin listesine göre süzer. |
| `github-pr-plan` | stdin: `{"run_id":"run-...","repo":"owner/name","head":"branch","base":"main"}` | İmzalı `completed` ve secret'sız sonuçtan taslak PR planı üretir; yazmaz. |
| `github-pr-create` | stdin: `{"run_id":"run-...","confirm":true,"operation_id":"op-...","project_root":"C:\\proje","head":"branch"}` | Planı doğrular, yalnızca bu açık onayla branch'i push edip taslak PR açar. |
| `github-ci-plan` | stdin: `{"feedback":{...},"head_sha":"...","max_rounds":3,"used_rounds":0,"authorized":true,"approval":true}` | Round/SHA/reviewer/onay sınırlı düzeltme planı üretir; PR'a yorum/merge yazmaz. |
| `github-ci-ingest` | stdin: `{"operation_id":"op-...","body":"<ham webhook gövdesi>","headers":{"X-Hub-Signature-256":"sha256=...","X-GitHub-Event":"check_run","X-GitHub-Delivery":"..."}}`; sır `RESPECTED_GITHUB_WEBHOOK_SECRET` ortam değişkeninden | İmzalı `check_run` yükünü içe aktarır; yanlış imza/depo/commit/PR, tekrar ve eski sonuç reddedilir. Yorum/merge/düzeltme yapmaz. |
| `github-ci-poll` | stdin: `{"operation_id":"op-..."}` | `gh api` ile taslak PR'ın head commit'inin check-run'larını okur ve aynı kurallarla işler. |

Aynı sözleşme RPP `github.issue_import|pr_plan|pr_create|ci_plan|ci_ingest|ci_poll` operasyonlarından da kullanılır.

## İmzalı kurucu ve yayın kapısı

Paketleme sırasında Authenticode imzası `--sign-cert` (veya `RESPECTED_SIGN_CERT`) ile verilen PFX'ten alınır;
`--require-signed` imzasız artefaktı başarı saymaz. Doğrulama `release_signature.verify` ile fail-closed'dır:
tampered SHA, yanlış imzalayan, süresi dolmuş sertifika ve desteklenmeyen platform reddedilir. Depoda üretim
sertifikası yoktur; self-signed sertifika yalnızca hattı kanıtlar. Platform kapısı yalnızca Windows'u GA sayar.
