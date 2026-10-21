# Respected Orchestrator — Kaynak Atlası

> Bu belge `tools/repository_map.py` tarafından `docs/repository_inventory.json` içindeki gözden geçirilmiş açıklamalardan üretilir. Doğrudan bu Markdown dosyasını düzenlemeyin.

**Kapsam:** 93 proje dosyası. Git çalıştırmadan dosya sistemi ve kök ignore kurallarıyla keşfedilen bağımsız ürün kaynağıdır. Bağımlılık/üretim önbellekleri ayrı kategoriler olarak açıklanır.

## Eksiksiz kaynak ağacı

```text
respected-orchestrator/
├── .gitattributes
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── AGENTS.md
├── README.md
├── docs/
│   ├── AUTONOMOUS_MASTER_REPORT.md
│   ├── REPOSITORY_MAP.md
│   ├── decisions/
│   │   ├── ACCEPTANCE_SANDBOX.md
│   │   ├── MCP_PERMISSIONS.md
│   │   ├── MEMORY_INTEGRATION.md
│   │   ├── PROJECT_SUPERVISOR_REVIEW.md
│   │   ├── ROLE_ASSIGNMENT.md
│   │   ├── RPP_V1.md
│   │   ├── RPP_V1_1.md
│   │   ├── campaign-master-lifecycle.md
│   │   └── codex-worker-results.md
│   ├── records/
│   │   ├── 2026-10-10-campaign-live-validation.md
│   │   ├── 2026-10-10-codex-blocked-worker.md
│   │   ├── 2026-10-10-windows-native-codex.md
│   │   ├── 2026-10-10-worker-auth-environment.md
│   │   ├── 2026-10-15-index-refresh-project.md
│   │   ├── 2026-10-15-mcp-access.md
│   │   ├── 2026-10-15-memory-integration-project.md
│   │   ├── 2026-10-15-role-assignment-validation.md
│   │   ├── 2026-10-15-secondbrain-memory-recall-project.md
│   │   └── 2026-10-master-program/
│   │       ├── A1_A2_RELIABILITY.md
│   │       ├── A3_A4_ENGINE.md
│   │       ├── CODEX_RECONNECT_REVIEW.md
│   │       ├── LANE_SUMMARY_REVIEW.md
│   │       ├── RPP_V11_STATUS.md
│   │       └── UNTRACKED_INPUTS_REVIEW.md
│   └── repository_inventory.json
├── packaging/
│   └── entrypoint.py
├── pyproject.toml
├── src/
│   └── respected_orchestrator/
│       ├── __init__.py
│       ├── __main__.py
│       ├── context.py
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── budget.py
│       │   ├── codex.py
│       │   ├── lanes.py
│       │   ├── processes.py
│       │   ├── runner.py
│       │   ├── sandbox.py
│       │   ├── sandbox_exec.py
│       │   ├── track_record.py
│       │   └── winproc.py
│       ├── interfaces/
│       │   ├── __init__.py
│       │   ├── integrations.py
│       │   ├── lifecycle.py
│       │   ├── mcp_server.py
│       │   ├── memory.py
│       │   └── rpp.py
│       ├── resources/
│       │   ├── policy.json
│       │   └── skills/
│       │       └── kod-orkestrasyon/
│       │           └── SKILL.md
│       └── workflows/
│           ├── __init__.py
│           ├── campaign.py
│           ├── maf_workflow.py
│           ├── planner.py
│           ├── project.py
│           └── roles.py
├── tests/
│   ├── __init__.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── test_codex_results.py
│   │   ├── test_completion_deadlines.py
│   │   ├── test_generated_artifacts.py
│   │   ├── test_lanes.py
│   │   ├── test_runner.py
│   │   ├── test_sandbox.py
│   │   ├── test_test_isolation.py
│   │   ├── test_token_budget.py
│   │   ├── test_windows_processes.py
│   │   └── test_worker_status_contract.py
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── test_integrations.py
│   │   ├── test_mcp_server.py
│   │   ├── test_memory.py
│   │   ├── test_memory_integration.py
│   │   ├── test_rpp.py
│   │   └── test_rpp_lifecycle.py
│   ├── packaging/
│   │   ├── __init__.py
│   │   └── test_frozen_build.py
│   └── workflows/
│       ├── __init__.py
│       ├── test_campaign.py
│       ├── test_maf_coding.py
│       ├── test_maf_workflow.py
│       ├── test_project.py
│       ├── test_project_adversarial.py
│       ├── test_project_recovery.py
│       ├── test_reviewer_reliability.py
│       └── test_roles.py
└── tools/
    ├── build_dist.py
    └── repository_map.py
```

## Dosya dosya sorumluluk ve ilişkiler

Her kayıt bir dosyayı açıklar; boş `.gitkeep` ve paket `__init__.py` dosyaları da dahildir. Aşağıdaki yollar depo köküne göredir. Tarihsel belgeler canlı davranışın yetkili kaynağı değildir.

### Depo kökü

#### [`.gitattributes`](../.gitattributes)

**Rol:** Satır sonu kuralı.

**Amaç / sorumluluk:** Depodaki metinleri LF olarak normalleştirir; .ps1/.bat/.cmd/.iss CRLF, görseller ve exe ikili kalır.

**İlişkiler ve sınır:** Git tarafından okunur; çalışma zamanı etkisi yoktur.

### .github/workflows

#### [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

**Rol:** Sürekli entegrasyon.

**Amaç / sorumluluk:** Windows'ta Python 3.13 ile paketi ve build araçlarını kurar, atlas kapısını çalıştırır, paketlenmiş motoru (tools/build_dist.py) derler, tam unittest keşfini (paketlenmiş exe'yi Python'suz PATH ile süren testler CI'da zorunludur) çalıştırır ve exe klasörünü artifact olarak yükler.

**İlişkiler ve sınır:** Yalnız Windows: kabul sandbox'ı, süreç ağacı denetimi ve worker shim'leri Windows kod yollarıdır.

### Depo kökü

#### [`.gitignore`](../.gitignore)

**Rol:** Kaynak kapsamı.

**Amaç / sorumluluk:** Bağımlılık, cache, build, yerel test artifacts ve proje içi sabitlenmiş .runtime paketini kaynak envanteri dışında tutar.

**İlişkiler ve sınır:** Yeni kaynak dosyaları atlas kapısından kaçırılmaz.

#### [`AGENTS.md`](../AGENTS.md)

**Rol:** Çalışma sözleşmesi.

**Amaç / sorumluluk:** Ürün sınırlarını, canlı veri korumasını, atlas bakımını ve anlamlı test kapılarını tanımlar.

**İlişkiler ve sınır:** Kullanıcı istemedikçe source Git/commit veya paralel ajan çalıştırılmaz.

#### [`README.md`](../README.md)

**Rol:** Ürün geliştirici rehberi.

**Amaç / sorumluluk:** Bağımsız ürün girişini, geliştirme komutlarını ve native/production kabul sınırlarını açıklar.

**İlişkiler ve sınır:** Runtime kaynaklarına ve tarihli extraction kaydına bağlanır.

### docs

#### [`docs/AUTONOMOUS_MASTER_REPORT.md`](../docs/AUTONOMOUS_MASTER_REPORT.md)

**Rol:** Autonomous master handoff report.

**Amaç / sorumluluk:** MAF pipeline integrationının gerçek uygulama, test, mock/canlı doğrulama, token ve kalan risk sonuçlarını founder için kaydeder.

**İlişkiler ve sınır:** runner/maf_workflow/__main__ değişiklikleri ve ilgili test komutlarıyla ilişkilendirir; canlı smoke sonucu ayrı tutulur.

#### [`docs/REPOSITORY_MAP.md`](../docs/REPOSITORY_MAP.md)

**Rol:** Üretilmiş atlas.

**Amaç / sorumluluk:** Ürünün bütün kaynak dosyalarının incelenmiş sorumluluk ve ilişkilerini gösterir.

**İlişkiler ve sınır:** tools/repository_map.py JSON kaynağından üretir; elle düzenlenmez.

### docs/decisions

#### [`docs/decisions/ACCEPTANCE_SANDBOX.md`](../docs/decisions/ACCEPTANCE_SANDBOX.md)

**Rol:** Kabul sandbox kararı.

**Amaç / sorumluluk:** Worker yazımı kodun motor anahtarını okuyup onay/kanıt sahteleyememesi için seçilen kısıtlı token + ACL sınırının gerekçesini, kanıtını ve açıkça belirtilen sınırlarını (profil dosyaları okunabilir, ağ açık, yalnızca Windows) kaydeder.

**İlişkiler ve sınır:** engine/sandbox.py, engine/sandbox_exec.py ve tests/engine/test_sandbox.py ile birlikte okunur.

#### [`docs/decisions/MCP_PERMISSIONS.md`](../docs/decisions/MCP_PERMISSIONS.md)

**Rol:** MCP yetki kararı.

**Amaç / sorumluluk:** MCP üzerinden bağlanan modelin yapabileceklerini sınırlayan kararı kaydeder: özel worker/command/apply_root/engine_source yalnızca --allow-privileged ile, kabul ve verify komutları yalnızca kullanıcının mcp_acceptance_allow önek listesindeyse, bypass bayrakları her yerde reddedilir; sınırları ve kanıtı belirtir.

**İlişkiler ve sınır:** interfaces/mcp_server.py, workflows/roles.py ve runner._command ile birlikte okunur; docs/decisions/ACCEPTANCE_SANDBOX.md onaylı komutların yine sandbox'ta çalıştığını açıklar.

#### [`docs/decisions/MEMORY_INTEGRATION.md`](../docs/decisions/MEMORY_INTEGRATION.md)

**Rol:** Karar: isteğe bağlı SecondBrain hafızası.

**Amaç / sorumluluk:** Görevlerin `memory.use` ile SecondBrain'den RPP `memory.recall` üzerinden hafıza isteme kararını anlatır. Hub'da etkinleştirme bir izindir, varsayılan değildir; en fazla yaklaşık 3000 karakter güvenilmez veri olarak brief'e eklenir, her hata 'hafıza yok' demektir. Token yalnızca 0600/ACL'li dosyada ve child stdin'inde tutulur, loglara ve kanıta sızmaz.

**İlişkiler ve sınır:** interfaces/memory.py ve runner.create_task bu kararı uygular; Hub gizli ayarları (memory_enabled, memory_command, memory_grant_id, memory_token) RPP settings.apply ile yazar. tests/interfaces/test_memory.py ve tests/interfaces/test_memory_integration.py kararın gizlilik ve politika kurallarını doğrular.

#### [`docs/decisions/PROJECT_SUPERVISOR_REVIEW.md`](../docs/decisions/PROJECT_SUPERVISOR_REVIEW.md)

**Rol:** Karar: proje supervisor adversarial incelemesi.

**Amaç / sorumluluk:** workflows/project.py otonom proje supervisor'ının ve workflows/campaign.py'nin ilgili parçalarının kaynak değiştirilmeden yapılan adversarial incelemesi. Şüpheli kusurları (ör. bozuk budget/verify/after için ValueError yerine AttributeError/TypeError) satır numaralarıyla belgeler.

**İlişkiler ve sınır:** src/respected_orchestrator/project.py ve workflows/campaign.py incelenen kodlardır. tests/workflows/test_project_adversarial.py bu incelemenin doğru kalan değişmezlerini ve sonradan kapatılan kusurlarını test eder.

#### [`docs/decisions/ROLE_ASSIGNMENT.md`](../docs/decisions/ROLE_ASSIGNMENT.md)

**Rol:** Karar: satıcıdan bağımsız rol ataması.

**Amaç / sorumluluk:** Her uyumlu model/sağlayıcı/araç her iş akışı rolünü üstlenebilir; kodda 'model X yalnızca rol Y' kuralı yoktur. Rol, profil, araç ve atama ayrı kavramlardır; öncelik sırası açık atama, Hub varsayılanı, isteğe bağlı otomatik atamadır; aynı rolün çelişen iki değeri ROLE_CONFLICT olur.

**İlişkiler ve sınır:** workflows/roles.py ve runner.create_task kararı uygular; maf_workflow reviewer/derin review için atanan aracı kullanır. tests/workflows/test_roles.py kararı doğrular; kayıt: docs/records/2026-10-15-role-assignment-validation.md.

#### [`docs/decisions/RPP_V1.md`](../docs/decisions/RPP_V1.md)

**Rol:** Karar: RPP v1.0 sunucu sözleşmesi.

**Amaç / sorumluluk:** Orchestrator'ın RPP v1.0'ı özel giriş noktasından (stdin'de tek JSON istek, stdout'ta tek JSON satır; ağ dinleyicisi ve genel CLI yok) sunmasını tanımlar. Op'lar manifest, health, settings.schema/validate/apply/readback; ayarlar atomik yazılır, apply kalıcı receipt üretir ve yanıtlar asla traceback veya secret içermez.

**İlişkiler ve sınır:** src/respected_orchestrator/rpp.py sözleşmeyi uygular; v1.1 uzantısı RPP_V1_1.md'dedir. tests/interfaces/test_rpp.py v1.0 davranışını doğrular.

#### [`docs/decisions/RPP_V1_1.md`](../docs/decisions/RPP_V1_1.md)

**Rol:** Karar: RPP v1.1 geriye uyumlu uzantı.

**Amaç / sorumluluk:** v1.0'ın katı üst kümesi olan v1.1'i tanımlar: 1.0..1.1 sürüm uzlaşması, lifecycle plan/apply/status/rollback ve operation.receipt op'ları, yedi yeni tipli hata ve zengin manifest. Taşıma ve mevcut op davranışı değişmez; yeni op'lar aynı allow-list kayıt desenine eklenir.

**İlişkiler ve sınır:** interfaces/rpp.py ve interfaces/lifecycle.py uygular; RPP_V1.md'ye eklenir. tests/interfaces/test_rpp.py (RppV11Tests) ve tests/interfaces/test_rpp_lifecycle.py doğrular.

#### [`docs/decisions/campaign-master-lifecycle.md`](../docs/decisions/campaign-master-lifecycle.md)

**Rol:** Karar: kampanya master yaşam döngüsü.

**Amaç / sorumluluk:** Detached kampanya supervisor'ı, ayrı data-root'lu paralel hatlar, completion event ile tek seferlik yeni master, Git mirror + apply, motor snapshot'ı ve worker sertleştirmesinin (sandbox, env scrub, key ACL, TTY onayı, reviewer≠implementer, MiMo yasağı) kararlarını ve sınırlarını kaydeder.

**İlişkiler ve sınır:** src/respected_orchestrator/campaign.py src/respected_orchestrator/runner.py src/respected_orchestrator/maf_workflow.py

#### [`docs/decisions/codex-worker-results.md`](../docs/decisions/codex-worker-results.md)

**Rol:** Codex sonuç ve ortam sözleşmesi kararı.

**Amaç / sorumluluk:** Tam brief/JSONL sonucu, explicit failure sınıflandırması, sabitlenmiş Windows runtime, child ortam ve salt okunur auth/sandbox preflight kararlarını açıklar.

**İlişkiler ve sınır:** runner/processes/demo ve regresyon testleri uygular; private-home yaklaşımı kaldırılmıştır; native runtime güvenlik onarımı ve yeni ücretli test ayrı onay sınırıdır.

### docs/records

#### [`docs/records/2026-10-10-campaign-live-validation.md`](../docs/records/2026-10-10-campaign-live-validation.md)

**Rol:** Kayıt: kampanya canlı doğrulaması.

**Amaç / sorumluluk:** İki küçük canlı kampanyanın (3 paralel Git hattı + non-Git mirror/apply) tarihli kanıtı: süreler, token kullanımı, otomatik master başlatma ve canlı denenmeyen yollar.

**İlişkiler ve sınır:** docs/decisions/campaign-master-lifecycle.md src/respected_orchestrator/campaign.py

#### [`docs/records/2026-10-10-codex-blocked-worker.md`](../docs/records/2026-10-10-codex-blocked-worker.md)

**Rol:** Windows Native blocked worker kanıt kaydı.

**Amaç / sorumluluk:** Belirli run JSONL/sandbox zaman korelasyonunu, salt okunur WinAPI access-mask kanıtını, resmi ACL düzeltmesini ve ücretsiz doğrulama sınırlarını kaydeder.

**İlişkiler ve sınır:** codex-worker-results kararı, runner CLI seçimi, ortak worker sınıflandırması ve test_codex_results regresyonları ile bağlıdır; canlı AI/sandbox doğrulaması kanıtlanmış davranıştan ayrı tutulur.

#### [`docs/records/2026-10-10-windows-native-codex.md`](../docs/records/2026-10-10-windows-native-codex.md)

**Rol:** Tarihli Windows Native kanıt kaydı.

**Amaç / sorumluluk:** Sandbox sharing violation, brief/cwd/patch sorunları, başarılı edit sonrası bytecode reddi ve ücretsiz doğrulama sonuçlarını kaydeder.

**İlişkiler ve sınır:** codex-worker-results kararına bağlanır; mevcut implementasyon ile çözülmemiş dış Windows runtime hedefini ayırır.

#### [`docs/records/2026-10-10-worker-auth-environment.md`](../docs/records/2026-10-10-worker-auth-environment.md)

**Rol:** Windows auth ve sandbox engeli kanıt kaydı.

**Amaç / sorumluluk:** Tek onaylı MiMo auth hatasını, PSModulePath karşılaştırmasını, ücretsiz gerçek exec_command provisioning hatasını ve ortak güvenlik yan etkisini kanıt/şüphe ayrımıyla kaydeder.

**İlişkiler ve sınır:** processes ve demo düzeltmeleri environment/marker regresyonlarıyla bağlıdır; geçici JSONL/status logları runtime engelini gösterir; shared sandbox onarımı ve yeni paid test uygulanmış sayılmaz.

#### [`docs/records/2026-10-15-index-refresh-project.md`](../docs/records/2026-10-15-index-refresh-project.md)

**Rol:** Tarihli kanıt kaydı: Hub hafıza paneli ve index refresh.

**Amaç / sorumluluk:** Hub hafıza panelinin yerel doğrulamasını, token dosyası ACL bulgusunu (dosya önce boş oluşturulup kısıtlanır, sonra yazılır) ve Orchestrator üzerinden memory.index.status/refresh proje çalıştırmasını token maliyetiyle kaydeder.

**İlişkiler ve sınır:** Karar: docs/decisions/MEMORY_INTEGRATION.md; düzeltme store_token ile test_the_file_is_restricted_while_still_empty testidir. SecondBrain tarafı RPP_MEMORY_RECALL.md sözleşmesine bağlıdır; çalışma zamanı bağımlılığı değildir.

#### [`docs/records/2026-10-15-mcp-access.md`](../docs/records/2026-10-15-mcp-access.md)

**Rol:** Tarihli kanıt kaydı: MCP erişimi.

**Amaç / sorumluluk:** `mcp` alt komutuyla stdio MCP sunucusunun (yalnız stdlib, Hub gerekmez) araçlarını, kayıt örneğini ve güvenlik kurallarını anlatır: ortam bayraklarıyla özyineleme koruması, değişiklik yalnız doğrulanmış patch_sha256 ile orchestrator_apply üzerinden, MAF insan onayı sunulmaz, auto_apply varsayılan reddedilir. 2026-10-17 denetimiyle Güvenlik bölümündeki bazı iddialar geçersiz kılındı (MCP_PERMISSIONS.md).

**İlişkiler ve sınır:** src/respected_orchestrator/mcp_server.py ve runner._key (.engine-key ACL düzeltmesi) ilgilidir. tests/test_mcp_server.py doğrular.

#### [`docs/records/2026-10-15-memory-integration-project.md`](../docs/records/2026-10-15-memory-integration-project.md)

**Rol:** Tarihli kanıt kaydı: hafıza entegrasyonu projeleri.

**Amaç / sorumluluk:** SecondBrain, Orchestrator ve Hub için Orchestrator üzerinden yürütülen hafıza entegrasyonu projelerini, token maliyetlerini ve bu sırada bulunup düzeltilen motor kusurlarını (Windows komut satırı sınırı nedeniyle 28000 karakter prompt tavanı, lane main_root, memory.use politikası) kaydeder.

**İlişkiler ve sınır:** Karar: docs/decisions/MEMORY_INTEGRATION.md. tests/test_roles.py ve tests/test_memory_integration.py bulunan kusurların regresyon testlerini içerir.

#### [`docs/records/2026-10-15-role-assignment-validation.md`](../docs/records/2026-10-15-role-assignment-validation.md)

**Rol:** Tarihli kanıt kaydı: rol ataması doğrulaması.

**Amaç / sorumluluk:** Rol ataması uygulamasının neyi değiştirdiğini (workflows/roles.py, sabit reviewer/MiMo kurallarının kaldırılması, yeni RPP ayarları) ve tam test paketi ile gerçek tek kullanımlık repo üzerindeki doğrulama kanıtını kaydeder.

**İlişkiler ve sınır:** Karar: docs/decisions/ROLE_ASSIGNMENT.md. tests/test_roles.py, test_campaign ve test_project kanıtta anılan testlerdir.

#### [`docs/records/2026-10-15-secondbrain-memory-recall-project.md`](../docs/records/2026-10-15-secondbrain-memory-recall-project.md)

**Rol:** Tarihli kanıt kaydı: SecondBrain memory.recall projesi.

**Amaç / sorumluluk:** SecondBrain'in ilk projesinin Orchestrator üzerinden çalıştırılmasını kaydeder: git mirror izolasyonu, Hub tarzı rol varsayılanları, iki fazlı proje sonuçları, reviewer engeli ve toplam yaklaşık 578k ağırlıklı token. Gerçek repo yalnızca baseline hash denetiminden sonra güncellenmiştir.

**İlişkiler ve sınır:** Sözleşme respected-secondbrain RPP_MEMORY_RECALL.md'de; ilgili karar docs/decisions/MEMORY_INTEGRATION.md. Proje supervisor'ı workflows/project.py ve kayıtla birlikte test_project_recovery.py ilgilidir.

### docs/records/2026-10-master-program

#### [`docs/records/2026-10-master-program/A1_A2_RELIABILITY.md`](../docs/records/2026-10-master-program/A1_A2_RELIABILITY.md)

**Rol:** Tarihli kanıt kaydı: reviewer güvenilirliği (A1/A2).

**Amaç / sorumluluk:** Sağlayıcıya duyarlı review zaman aşımı, ayrı hata sınıfları, sınırlı review yeniden denemesi (varsayılan 1) ve yalnız review yeniden çalıştırma yolunu belgeler. Worker işi yalnızca imzalı sonuç yeniden doğrulanırsa yeniden kullanılır; red kesindir, geçersiz çıktı yeniden denenmez.

**İlişkiler ve sınır:** workflows/maf_workflow.py, engine/vertical_slice.py, engine/runner.py ve workflows/project.py ile uygulanır. tests/test_reviewer_reliability.py doğrular.

#### [`docs/records/2026-10-master-program/A3_A4_ENGINE.md`](../docs/records/2026-10-master-program/A3_A4_ENGINE.md)

**Rol:** Tarihli kanıt kaydı: üretilmiş artefakt ve token bütçesi (A3/A4).

**Amaç / sorumluluk:** A3: untracked/ignored üretilmiş dosyaları (build, egg-info, __pycache__) gerçek değişiklikten ayırıp patch'e sokmama, gerçek scope ihlallerini koruma. A4: lane başına kalıcı token bütçesi, UNKNOWN kullanımın açık raporlanması ve proje bütçesinde varsayılan ücretlendirme.

**İlişkiler ve sınır:** engine/antigravity_orchestrator.py, engine/runner.py, engine/budget.py, workflows/maf_workflow.py, workflows/project.py ve workflows/campaign.py ilgilidir; A1_A2_RELIABILITY.md üzerine kurulur. tests/test_generated_artifacts.py ve tests/test_token_budget.py doğrular.

#### [`docs/records/2026-10-master-program/CODEX_RECONNECT_REVIEW.md`](../docs/records/2026-10-master-program/CODEX_RECONNECT_REVIEW.md)

**Rol:** İnceleme kaydı: Codex reconnect bildirimi.

**Amaç / sorumluluk:** Codex JSONL akışındaki fatal olmayan 'Reconnecting...' üst düzey error olayının worker_failed sayılması hatasının düzeltmesini onaylar. Tolerans yalnızca tam önek, turn.failed yokluğu, başka error yokluğu ve tam olarak bir turn.completed ile bitiş koşullarında geçerlidir.

**İlişkiler ve sınır:** engine/vertical_slice.py'deki Codex akış ayrıştırıcısını inceler. tests/test_reviewer_reliability.py diagnose ve reconnect testleriyle ilişkilidir.

#### [`docs/records/2026-10-master-program/LANE_SUMMARY_REVIEW.md`](../docs/records/2026-10-master-program/LANE_SUMMARY_REVIEW.md)

**Rol:** İnceleme kaydı: lane özeti hata nedeni.

**Amaç / sorumluluk:** Kampanya lane özetinin genel worker_failed yerine imzalı çalıştırma durumundaki gerçek nedeni (scope_violation, timed_out) taşımasını onaylar. Geçersiz/eksik imzalı status genel MAF nedenine döner; başka run dizinine kopyalanmış status final_run_id eşleşmezse reddedilir.

**İlişkiler ve sınır:** campaign._lane_summary ve workflows/project.py hata mesajı incelenen koddur. tests/test_project_recovery.py ilgili özet testlerini içerir.

#### [`docs/records/2026-10-master-program/RPP_V11_STATUS.md`](../docs/records/2026-10-master-program/RPP_V11_STATUS.md)

**Rol:** Tarihli kanıt kaydı: RPP v1.1 uygulama durumu.

**Amaç / sorumluluk:** Orchestrator'ın RPP v1.1 yüzeyinin (sürüm uzlaşması, lifecycle ve receipt op'ları, yedi yeni hata) tamamlandığını kod satırı ve test referanslarıyla kaydeder; kardeş repolar yalnız okunmuştur, kod değişmemiştir.

**İlişkiler ve sınır:** Sözleşme docs/decisions/RPP_V1_1.md ve RPP_V1.md; kod interfaces/rpp.py ve interfaces/lifecycle.py. tests/test_rpp.py ve tests/test_rpp_lifecycle.py anılan testlerdir.

#### [`docs/records/2026-10-master-program/UNTRACKED_INPUTS_REVIEW.md`](../docs/records/2026-10-master-program/UNTRACKED_INPUTS_REVIEW.md)

**Rol:** İnceleme kaydı: untracked sahipli girdiler.

**Amaç / sorumluluk:** Lane'lerin HEAD'den oluşturulması nedeniyle untracked sahipli dosyaların worker'a taşınması için opt-in tasarımı onaylar: ignored, tracked, dosya olmayan ve symlink girdiler reddedilir, ownership ve forbidden süzgeci uygulanır. Git'in NUL ayrımlı çıktısının yerel kod sayfasıyla çözülmesi düzeltilmiştir.

**İlişkiler ve sınır:** runner'daki include_untracked_owned yolu ve overlay_dirty_inputs incelenen koddur. tests/test_generated_artifacts.py ilgili untracked sahipli girdi testleriyle ilişkilidir.

### docs

#### [`docs/repository_inventory.json`](../docs/repository_inventory.json)

**Rol:** Anlamsal atlas kaynağı.

**Amaç / sorumluluk:** Dosya rol, amaç, ilişki ve içerik inceleme hash kayıtlarını tutar.

**İlişkiler ve sınır:** repository_map update/accept-reviewed/write/check kapılarının tek anlamsal kaynağıdır.

### packaging

#### [`packaging/entrypoint.py`](../packaging/entrypoint.py)

**Rol:** Paketleme giriş noktası.

**Amaç / sorumluluk:** PyInstaller'ın dondurduğu programın girişidir: respected_orchestrator.__main__.main'i çalıştırır ve çıkış kodunu döndürür.

**İlişkiler ve sınır:** tools/build_dist.py tarafından kullanılır; ürün mantığı içermez.

### Depo kökü

#### [`pyproject.toml`](../pyproject.toml)

**Rol:** Python paket tarifi.

**Amaç / sorumluluk:** respected-orchestrator kimliği, Python tabanı ve policy/skill wheel kaynaklarını tanımlar. dev ekstrası PyInstaller'ı getirir (tools/build_dist.py).

**İlişkiler ve sınır:** Setuptools bağımsız wheel üretir; public console script ve Brain bağımlılığı yoktur.

### src/respected_orchestrator

#### [`src/respected_orchestrator/__init__.py`](../src/respected_orchestrator/__init__.py)

**Rol:** Paket kimliği.

**Amaç / sorumluluk:** Bağımsız Python paketini ve sürümünü tanımlar.

**İlişkiler ve sınır:** Private status girişinin sürüm kaynağıdır; import yan etkisi yoktur.

#### [`src/respected_orchestrator/__main__.py`](../src/respected_orchestrator/__main__.py)

**Rol:** Private JSON giriş.

**Amaç / sorumluluk:** Hub ve testler için özel JSON girişidir (herkese açık CLI değil). status/create/start/list/inspect/cancel/check/retry/apply, maf/maf-approve, campaign-*, project-*, roles, plan, rpp ve mcp komutlarını ilgili modüle yönlendirir. stdin JSON'u UTF-8 BOM'lu da kabul eder; hatalar JSON error olarak döner, başarısız _execute sonucu exit 1 verir. mcp alt komutu --allow-auto-apply ve ayrı --allow-privileged anahtarlarını sunucuya iletir. _selfcheck tüm motor modüllerini ve Agent Framework'ü yükleyerek paketlenmiş exe'nin eksiksiz olduğunu kanıtlar; _sandbox-exec veri kökü oluşturmadan kısıtlı token başlatıcısına geçer.

**İlişkiler ve sınır:** runner, roles, campaign, project, maf_workflow, planner, mcp_server, rpp ve lanes'ı çağırır; Brain launcher/vault gerektirmez. tests/engine/test_runner.py ve tests/workflows/test_maf_coding.py private JSON sözleşmesini doğrular.

#### [`src/respected_orchestrator/context.py`](../src/respected_orchestrator/context.py)

**Rol:** Bağımsız roots/state.

**Amaç / sorumluluk:** EngineContext DataRoot/state/workspace ve AppRoot ayrımı, no-link path ve atomik JSON yazısını sağlar. Windows varsayılan DataRoot'u tek Respected klasöründedir: `%LOCALAPPDATA%/Respected/RespectedOrchestrator/data`. FROZEN ve engine_command: paketlenmiş exe içinde motor kendini exe ile, kaynakta `python -m respected_orchestrator` ile yeniden başlatır; frozen modda app_root exe'nin klasörüdür (distribution.json ve kurulum kaydı orada).

**İlişkiler ve sınır:** runner ve çıkarılmış motor kullanır; Brain context/vault/lease bağı yoktur.

### src/respected_orchestrator/engine

#### [`src/respected_orchestrator/engine/__init__.py`](../src/respected_orchestrator/engine/__init__.py)

**Rol:** Worker yürütme paketi.

**Amaç / sorumluluk:** AI worker CLI'larını güvenle çalıştıran katman: süreç ve Windows süreç denetimi, kabul sandbox'ı, izole worktree lane motoru (lanes), Codex çağrı katmanı (codex), görev koşucusu (runner), token bütçesi ve başarı kaydı. 2026-10-21'de düz paket bu alt paketlere ayrıldı.

**İlişkiler ve sınır:** Kök paketteki __main__.py ve context.py ile diğer alt paketler tarafından içe aktarılır; Hub yalnızca `python -m respected_orchestrator` çağırır, bu yüzden dışarıdan görünen davranış değişmez.

#### [`src/respected_orchestrator/engine/budget.py`](../src/respected_orchestrator/engine/budget.py)

**Rol:** Token bütçesi ve kullanım muhasebesi.

**Amaç / sorumluluk:** Şerit başına token bütçesini ve dürüst kullanım muhasebesini yönetir. Kullanım bildirmeyen ama başlamış adım SIFIR değil BİLİNMEYEN sayılır ve yalnızca bütçe kontrolünde varsayılan bir ücretle yazılır; hiç başlamayan adım sayılmaz. (2026-10-21: `src/respected_orchestrator/budget.py` yolundan taşındı.)

**İlişkiler ve sınır:** Proje/kampanya bütçe kontrolleri ve runner tarafından çağrılır; engine sonuçlarındaki usage alanlarını okur. tests/engine/test_token_budget.py ile test edilir.

#### [`src/respected_orchestrator/engine/codex.py`](../src/respected_orchestrator/engine/codex.py)

**Rol:** Codex CLI çağrı katmanı.

**Amaç / sorumluluk:** Tek sınırlı `codex exec --json` turunu çalıştırır (run_codex_call, CodexCall, CodexOutcome); JSONL akışını ayrıştırır, turn.completed doğrulaması (stream_verified_complete), bağlantı kopması/zaman aşımı/başarısızlık tanısı (diagnose), kullanım/token hesabı ve gizli bilgi maskelemesi yapar. Etkin çıktı penceresi dolmadan zaman aşımını ilerleme kabul etmez.

**İlişkiler ve sınır:** processes.execute ve context.atomic_write_json kullanır. runner (turn tamamlanma kontrolü) ve maf_workflow (Codex çağrıları) buradan içe aktarır. tests/workflows/test_reviewer_reliability.py, tests/engine/test_completion_deadlines.py ve tests/workflows/test_maf_coding.py kapsar.

#### [`src/respected_orchestrator/engine/lanes.py`](../src/respected_orchestrator/engine/lanes.py)

**Rol:** Yalıtılmış worker lane motoru.

**Amaç / sorumluluk:** Policy yükleme, git worktree lane oluşturma, sahipli kirli girdilerin bindirilmesi ve baseline commit, brief, tek yazar kilidi (ölü sahipli kilidi geri alır), worker çalıştırma ve çıkış sınıflandırması (sıfır exit'li açık hata reddi), değişiklik toplama (üretilmiş çıktı ayrımı), kapsam doğrulama, acceptance ve binary patch dışa aktarımı/ana dala karşı kontrol. İzin atlatan komutlar reddedilir; ham patch uygulama yoktur.

**İlişkiler ve sınır:** runner, workflows/project, workflows/campaign ve planner tarafından kullanılır; winproc, processes ve context'e dayanır. tests/engine/test_lanes.py, tests/engine/test_runner.py, tests/engine/test_codex_results.py, tests/engine/test_generated_artifacts.py ve tests/engine/test_worker_status_contract.py kapsar.

#### [`src/respected_orchestrator/engine/processes.py`](../src/respected_orchestrator/engine/processes.py)

**Rol:** Worker süreç yönetimi.

**Amaç / sorumluluk:** Windows suspended child/job ve POSIX process group ile deadline, cancel, process-tree temizliği ve çıktı akışı sağlar. complete_when/verify_complete ile doğrulanmış completion event'inde ağacı temizleyip ilerler; iptal geç completion'dan üstündür. scrub_environment anahtar/token/secret benzeri değişkenleri çocuğa geçirmez (RESPECTED_WORKER_ENV_ALLOW hariç), çocuğa RESPECTED_ORCH_CHILD=1 koyar ve izole test modunda Codex API çağrılarını reddeder. (2026-10-21: `src/respected_orchestrator/processes.py` yolundan taşındı.)

**İlişkiler ve sınır:** runner, lanes, campaign, project ve codex worker/acceptance/master süreçlerini buradan çalıştırır. tests/engine/test_runner.py (tree cleanup, ortam sızıntısı) ve tests/engine/test_codex_results.py dolaylı kapsar.

#### [`src/respected_orchestrator/engine/runner.py`](../src/respected_orchestrator/engine/runner.py)

**Rol:** Tek görev worker yürütücüsü.

**Amaç / sorumluluk:** Create/start/list/inspect/cancel/check/retry ile imzalı yaşam döngüsünü; Codex brief/strict JSONL, scope, acceptance, freshness ve correction patch hash/scope doğrulamasını yürütür. Codex açık --sandbox workspace-write ve approval_policy=never ile çalışır, MiMo profilleri reddedilir, reviewer implementer'dan farklı olmalıdır, .engine-key Windows'ta mevcut kullanıcıya ACL'lenir. apply_task doğrulanmış (gerekirse insan onaylı) patch'i commit etmeden uygular; maf-approve yalnız etkileşimli operatör terminalinde, patch_sha256'ya bağlı ve değiştirilemez onay verir. Kabul komutları sandbox.wrap ile kısıtlı token'da çalışır (kurulamazsa sandbox_unavailable ile fail-closed), kabul öncesi worker'ın bıraktığı __pycache__/.pyc silinir (üretilen dosya sayısı yine raporlanır); Windows'ta .cmd/.bat worker kabukları kullanılamaz, görev metni Windows'ta 20000 karakterle sınırlıdır, bypass bayrağı kontrolü genişletildi, retry açık memory kararını korur, tester/coordinator rolleri ROLE_NOT_EXECUTABLE ile reddedilir. (2026-10-21: `src/respected_orchestrator/runner.py` yolundan taşındı.) Ayrık süpervizör context.engine_command ile başlar (exe veya kaynak); icacls mutlak yoldan çağrılır.

**İlişkiler ve sınır:** context, processes ve lanes katmanlarını kullanır; __main__, maf_workflow, campaign ve project tarafından çağrılır. tests/engine/test_runner.py, tests/engine/test_codex_results.py ve tests/workflows/test_maf_coding.py kapsar.

#### [`src/respected_orchestrator/engine/sandbox.py`](../src/respected_orchestrator/engine/sandbox.py)

**Rol:** Güvenilmeyen kod sınır katmanı.

**Amaç / sorumluluk:** Motorun kendi çalıştırdığı worker yazımı kodun (kabul ve verify komutları) yetkisini sınırlar: Windows'ta veri kökü başına rastgele bir SID üretir, veri kökünün (workspaces hariç) tüm çocuklarına ve .engine-key dosyasına bu SID için inheritable DENY ACE ekler, OWNER RIGHTS ACE ile sahibin örtük WRITE_DAC hakkını kaldırır ve komutu sandbox_exec üzerinden kısıtlı token ile çalıştıracak biçimde sarar (wrap). Sınır kurulamazsa SandboxError verir (fail-closed); RESPECTED_ORCH_SANDBOX=off yalnızca açık geliştirici anahtarıdır. Karar: docs/decisions/ACCEPTANCE_SANDBOX.md. (2026-10-21: `src/respected_orchestrator/sandbox.py` yolundan taşındı.) Paketlenmiş exe'de kısıtlı token başlatıcısı `_sandbox-exec` özel alt komutuyla çalışır; PowerShell ACL kurulumu mutlak sistem yoluyla çağrılır.

**İlişkiler ve sınır:** runner (kabul komutları) ve project (_verify) tarafından çağrılır; anahtar yolunu runner._key_path verir. sandbox_exec ile birlikte çalışır; PowerShell ACL kurulumunu winproc.run ile gizli pencerede yürütür. tests/engine/test_sandbox.py gerçek saldırı denemeleri ve negatif kontrolle sınırı kanıtlar.

#### [`src/respected_orchestrator/engine/sandbox_exec.py`](../src/respected_orchestrator/engine/sandbox_exec.py)

**Rol:** Kısıtlı token ile komut çalıştırıcı.

**Amaç / sorumluluk:** python -m ... sandbox_exec --sid SID -- komut: çağıranın token'ından CreateRestrictedToken ile (kullanıcının tüm SID'leri + veri köküne ait ek SID kısıtlayıcı SID olarak, DISABLE_MAX_PRIVILEGE) yeni bir token üretir ve komutu CreateProcessAsUser ile çağıranın standart tutamaçlarıyla başlatır; çıkış kodunu döndürür. Çağıranın job nesnesi (süreç ağacı sonlandırma, zaman aşımı) çocuk için de geçerlidir. Yalnızca Windows. (2026-10-21: `src/respected_orchestrator/sandbox_exec.py` yolundan taşındı.)

**İlişkiler ve sınır:** sandbox.wrap tarafından komut öneki olarak eklenir; processes.execute bunu sıradan bir süreç gibi yönetir. tests/engine/test_sandbox.py ile doğrulanır.

#### [`src/respected_orchestrator/engine/track_record.py`](../src/respected_orchestrator/engine/track_record.py)

**Rol:** Ölçülü araç/profil sicili.

**Amaç / sorumluluk:** (araç, profil) başına başarı, token ve süre sicilini bu kurulumun imzalı run kanıtından okur. Yalnızca imzası doğrulanan kanıt sayılır; imzasız, kurcalanmış veya kısmi kayıt atlanır. Adayları yalnızca sıralar, asla elemez; geçmiş MIN_RUNS altındaysa kullanılabilir geçmiş yoktur. (2026-10-21: `src/respected_orchestrator/track_record.py` yolundan taşındı.)

**İlişkiler ve sınır:** runner._track_record ve roles otomatik atama tarafından çağrılır; runner._load ve EngineContext kullanır. tests/workflows/test_roles.py ve tests/workflows/test_reviewer_reliability.py ile kapsanır.

#### [`src/respected_orchestrator/engine/winproc.py`](../src/respected_orchestrator/engine/winproc.py)

**Rol:** Windows süreç başlatma yardımcısı.

**Amaç / sorumluluk:** Windows'ta çocuk süreçleri konsol penceresi açmadan başlatır; ayrık supervisor'ların git/python/icacls çağrıları görünür pencere açmasın diye bayraklar tek yerde tutulur. Çıktı, hata, çıkış kodu ve zaman aşımı davranışı değişmez; Windows dışında boş seçenek döner. (2026-10-21: `src/respected_orchestrator/winproc.py` yolundan taşındı.) system_tool: PowerShell ve icacls'ı SystemRoot altındaki mutlak yoldan verir; kırpılmış veya ele geçirilmiş PATH onları gizleyemez ya da değiştiremez.

**İlişkiler ve sınır:** Paketteki süreç başlatan modüller (memory, runner, processes vb.) tarafından kullanılır. tests/engine/test_windows_processes.py ile test edilir.

### src/respected_orchestrator/interfaces

#### [`src/respected_orchestrator/interfaces/__init__.py`](../src/respected_orchestrator/interfaces/__init__.py)

**Rol:** Arayüz paketi.

**Amaç / sorumluluk:** Dışarının motorla konuştuğu yollar: AI istemcileri için MCP sunucusu, Respected Hub için RPP, yaşam döngüsü/entegrasyon kayıtları ve SecondBrain hafıza bağlantısı. 2026-10-21'de düz paket bu alt paketlere ayrıldı.

**İlişkiler ve sınır:** Kök paketteki __main__.py ve context.py ile diğer alt paketler tarafından içe aktarılır; Hub yalnızca `python -m respected_orchestrator` çağırır, bu yüzden dışarıdan görünen davranış değişmez.

#### [`src/respected_orchestrator/interfaces/integrations.py`](../src/respected_orchestrator/interfaces/integrations.py)

**Rol:** AI istemcisi MCP entegrasyonu.

**Amaç / sorumluluk:** RPP integrations.* işlemlerini uygular: Orchestrator MCP sunucusunu AI istemci yapılandırmalarına (claude-code, codex, cursor, gemini, windsurf, claude-desktop) Discover/Inspect/Plan/Apply/Verify/Rollback akışıyla kaydeder. Yalnızca 'respected-orchestrator' girdisine dokunur; sahip olunmayan veya kullanıcının sonradan düzenlediği girdi ezilmez, apply onaylanan planın özetini ister. Okunamayan bir istemci yapılandırması, istenmeyen diğer istemcilerin planını engellemez (state=unreadable); istenen istemci için hata yine verilir. (2026-10-21: `src/respected_orchestrator/integrations.py` yolundan taşındı.)

**İlişkiler ve sınır:** interfaces/rpp.py tarafından çağrılır; lifecycle (LifecycleError, atomik yazma, makbuz) ve context.safe_path kullanır. tests/interfaces/test_integrations.py ile test edilir.

#### [`src/respected_orchestrator/interfaces/lifecycle.py`](../src/respected_orchestrator/interfaces/lifecycle.py)

**Rol:** RPP yaşam döngüsü durumu.

**Amaç / sorumluluk:** Sürümlü kurulum manifestosu, planlar, günlük ve rollback için RPP v1.1 yaşam döngüsü durumunu yönetir (install/update/repair/uninstall). Yalnızca açık kökler üzerinde safe_path ile sınırlı yerel dosya işlemi yapar; kabuk ve ağ yoktur, hatalar LifecycleError üçlüsüyle döner. (2026-10-21: `src/respected_orchestrator/lifecycle.py` yolundan taşındı.) target.distribution=true: paketlenmiş (frozen) kurulum metin olarak gönderilmez; ürün distribution.json'daki her dosyanın hash'ini diskte doğrular ve kaydı bundan yazar (program dosyalarına dokunmaz). Böyle bir kaydın uninstall'u yalnız kaydı kaldırır; klasörün sahibi kuran taraftır (Hub).

**İlişkiler ve sınır:** interfaces/rpp.py ve interfaces/integrations.py tarafından kullanılır; context'teki safe_path ve atomic_write_json'a dayanır. tests/interfaces/test_rpp_lifecycle.py ile test edilir.

#### [`src/respected_orchestrator/interfaces/mcp_server.py`](../src/respected_orchestrator/interfaces/mcp_server.py)

**Rol:** Vendor-bağımsız MCP stdio ön yüzü.

**Amaç / sorumluluk:** Orchestrator motorunu yalnızca standart kütüphaneyle MCP (stdio) araçları olarak sunar (plan, task_start, project_start, progress, evidence, resume, cancel, memory_note, apply). Motorun onayları geçerli kalır, apply doğrulanmış patch özetini ister ve orkestre edilen süreçler (RESPECTED_ORCH_DELEGATED) araç görmez, böylece özyinelemeli delegasyon olmaz. MCP üzerinden custom worker, command, apply_root ve engine_source reddedilir (--allow-auto-apply ile açılır). Özel seçenekler için ayrı --allow-privileged anahtarı vardır; acceptance/verify komutları roles.acceptance_allowed ile kullanıcının mcp_acceptance_allow önek listesine karşı denetlenir (varsayılan boş). `initialize` yanıtı kod-orkestrasyon skill'inin kurallar kısmını (front matter ve CLI kampanya bölümü hariç) MCP `instructions` olarak verir; böylece bağlanan her AI istemcisi skill'i ayrı dosya kurulmadan alır. (2026-10-21: `src/respected_orchestrator/mcp_server.py` yolundan taşındı.)

**İlişkiler ve sınır:** AI istemcileri interfaces/integrations.py ile kaydedilen komutla başlatır; campaign, project, roles, runner ve context motor işlevlerini çağırır. tests/interfaces/test_mcp_server.py ile test edilir.

#### [`src/respected_orchestrator/interfaces/memory.py`](../src/respected_orchestrator/interfaces/memory.py)

**Rol:** İsteğe bağlı SecondBrain bellek istemcisi.

**Amaç / sorumluluk:** SecondBrain'in salt-okunur RPP 'memory.recall' işlemi için isteğe bağlı, hata-yumuşak istemcidir. Grant token gizlidir: yalnızca data_root/memory-token içinde durur, çocuğun stdin'inden geçer ve çıktıdan üretilen mesajlardan temizlenir; dönen notlar güvenilmez veri olarak işaretlenir. (2026-10-21: `src/respected_orchestrator/memory.py` yolundan taşındı.)

**İlişkiler ve sınır:** interfaces/rpp.py ayarlarını ve runner/project bellek bağlamını besler; winproc ile süreç başlatır, token dosyasını runner._restrict_key ile kısıtlar. tests/interfaces/test_memory.py ve tests/interfaces/test_memory_integration.py ile test edilir.

#### [`src/respected_orchestrator/interfaces/rpp.py`](../src/respected_orchestrator/interfaces/rpp.py)

**Rol:** RPP v1.0/1.1 protokol girişi.

**Amaç / sorumluluk:** Respected Product Protocol: bir JSON istek alır, tek satır JSON yanıt döner. Hub ve testler için özel modüldür; daemon değildir ve ağ dinlemez. Her hata yapılandırılmış hata üçlüsü olarak döner, fırlatılmaz; yetenekleri, ayar şemasını ve lifecycle/memory/roles/runner işlemlerini yönlendirir. (2026-10-21: `src/respected_orchestrator/rpp.py` yolundan taşındı.)

**İlişkiler ve sınır:** Hub ve testler çağırır; lifecycle, memory, roles, runner, integrations ve context'i kullanır. tests/interfaces/test_rpp.py ve tests/interfaces/test_rpp_lifecycle.py ile test edilir.

### src/respected_orchestrator/resources

#### [`src/respected_orchestrator/resources/policy.json`](../src/respected_orchestrator/resources/policy.json)

**Rol:** Ürün varsayılanı.

**Amaç / sorumluluk:** Antigravity keşfi, single writer, read/write süreleri ve bypass=false varsayılanlarını sağlar.

**İlişkiler ve sınır:** Compatibility doctor/run okur; workspace bağımsız DataRoot'tadır.

### src/respected_orchestrator/resources/skills/kod-orkestrasyon

#### [`src/respected_orchestrator/resources/skills/kod-orkestrasyon/SKILL.md`](../src/respected_orchestrator/resources/skills/kod-orkestrasyon/SKILL.md)

**Rol:** Çıkarılmış skill.

**Amaç / sorumluluk:** Orchestrator'a ait kod-orkestrasyon skill'i (2026-10-21'de SecondBrain'den taşındı). Kurallar bölümü MCP araçlarının kullanımını (task_start, progress, evidence, onaylı apply, memory_note) anlatır ve mcp_server tarafından `instructions` olarak verilir; ayrı Claude Master kampanya bölümü CLI döngüsünü (campaign-start/status, apply, allow_apply, MiMo yasağı) anlatır. Kampanya komutu paketlenmiş exe ile (kaynakta python -m ile) verilir.

**İlişkiler ve sınır:** mcp_server._instructions okur; pyproject package-data ile paketlenir. Global provider skill ayarı değiştirilmez.

### src/respected_orchestrator/workflows

#### [`src/respected_orchestrator/workflows/__init__.py`](../src/respected_orchestrator/workflows/__init__.py)

**Rol:** İş akışı paketi.

**Amaç / sorumluluk:** Motorun üzerindeki görev akışları: MAF kodlama hattı, planlayıcı, rol/model ataması, kampanyalar ve projeler. 2026-10-21'de düz paket bu alt paketlere ayrıldı.

**İlişkiler ve sınır:** Kök paketteki __main__.py ve context.py ile diğer alt paketler tarafından içe aktarılır; Hub yalnızca `python -m respected_orchestrator` çağırır, bu yüzden dışarıdan görünen davranış değişmez.

#### [`src/respected_orchestrator/workflows/campaign.py`](../src/respected_orchestrator/workflows/campaign.py)

**Rol:** Kalıcı çok-repo kampanya supervisor'ı.

**Amaç / sorumluluk:** Claude master'ın devrettiği 1..8 workstream'i detached supervisor ile paralel MAF hatlarına çevirir (ayrı data-root, WriterLock, anahtar ve çalışma alanı; after ile bağımlılık). Non-Git kaynak için gizli dosyalar hariç geçici Git mirror kurar, doğrulanmış patch'i apply_root'a uygulatır ve motoru snapshot'layıp supervisor'ı oradan çalıştırır. Tüm hatlar bitince imzalı result.json yazar, final.claim ile tam bir kez final master başlatır; allow_apply açıksa yalnız 'python -m respected_orchestrator' komutlarına izin verir. (2026-10-21: `src/respected_orchestrator/campaign.py` yolundan taşındı.) Paketlenmiş exe'de motor anlık görüntüsü kopyalanmaz (exe zaten değişmez kopya); master'a önerilen uygulama komutu ve izinli araç deseni çalışan motorun gerçek CLI'ıdır (ENGINE_CLI).

**İlişkiler ve sınır:** runner.create_task/apply_task, maf_workflow.run_maf_coding_task ve processes.execute'u kullanır; workflows/project.py bunu faz başına çağırır; __main__ campaign-* komutlarıyla bağlanır. tests/workflows/test_campaign.py kapsar.

#### [`src/respected_orchestrator/workflows/maf_workflow.py`](../src/respected_orchestrator/workflows/maf_workflow.py)

**Rol:** MAF workflow adapter.

**Amaç / sorumluluk:** Microsoft Agent Framework functional workflow ile eş zamanlı worker fan-out, replayable step cache, checkpoint resume, bağımsız review, önceki başarılı patch'i devralan sınırlı correction ve isteğe bağlı deep review sağlar. Review deadline'ı provider-aware tavan ve pipeline deadline ile sınırlıdır, toplam bütçe worker+review tavanlarından türetilir veya açık timeout_seconds sert sınırdır. Reviewer hatası/geçersiz çıktısı fail-closed kalır; escalate_from_round'dan itibaren düzeltmeyi escalate_profile devralır, önceki implementer bağımsız reviewer olur; imzalı maf-result.json yazılır. (2026-10-21: `src/respected_orchestrator/maf_workflow.py` yolundan taşındı.)

**İlişkiler ve sınır:** runner execute_task/create_task/check_result ve codex run_codex_call adaptörlerini kullanır; __main__ 'maf' komutu ve campaign tarafından çağrılır. tests/workflows/test_maf_coding.py kapsar.

#### [`src/respected_orchestrator/workflows/planner.py`](../src/respected_orchestrator/workflows/planner.py)

**Rol:** Planner rolü yürütücüsü.

**Amaç / sorumluluk:** 'planner' rolünü çalıştırılabilir yapar: atanan araç/model bir proje spesifikasyonu taslağı üretir, motor doğrular. Taslak asla başlatılmaz veya motorca düzenlenmez; planlayıcı ataması, kullanım ve doğrulama sonucuyla <data root>/drafts altına kaydedilir ve project-start ile insan/Master onayından sonra başlar. (2026-10-21: `src/respected_orchestrator/planner.py` yolundan taşındı.)

**İlişkiler ve sınır:** interfaces/mcp_server.py (orchestrator_plan) ve Hub tarafından çağrılır; roles, runner, processes ve lanes'ı kullanır. tests/workflows/test_roles.py ve tests/workflows/test_project.py ile dolaylı kapsanır.

#### [`src/respected_orchestrator/workflows/project.py`](../src/respected_orchestrator/workflows/project.py)

**Rol:** Kalıcı otonom proje/faz supervisor'ı.

**Amaç / sorumluluk:** Tek seferlik yazılmış proje planını (bağımlı fazlar, workstream'ler, deterministik verify komutları, bütçe) imzalı project.json olarak saklar. Detached supervisor her fazı yeni motor snapshot'ı ve mirror ile campaign olarak çalıştırır; yalnız MASTER_APPROVED ve auto_apply ile önceden yetkilendirilmişse hep-ya-hiç apply eder, gerçek kaynakta verify çalıştırır. Sınırlı düzeltme denemesi, zaman/token bütçesi, iptal dosyası, pid'li tek-supervisor kilidi, resume ve isteğe bağlı final review sağlar. Faz verify komutları sandbox'tan ve temizlenmiş ortamdan (scrub_env, çocuk işareti) geçer. (2026-10-21: `src/respected_orchestrator/project.py` yolundan taşındı.) Proje ve kampanya süpervizörleri context.engine_command ile başlar (exe veya kaynak).

**İlişkiler ve sınır:** campaign.create_campaign/run_campaign/_snapshot_engine, runner.apply_task ve processes.execute'u kullanır; __main__ project-* komutlarıyla bağlanır. tests/workflows/test_project.py kapsar.

#### [`src/respected_orchestrator/workflows/roles.py`](../src/respected_orchestrator/workflows/roles.py)

**Rol:** Vendor-bağımsız rol ataması.

**Amaç / sorumluluk:** Rolleri (implementer, reviewer, planner vb.) profil ve araçlarla eşler; hiçbir model bir role bağlanmaz. Öncelik: açık görev ataması > Hub varsayılanı > otomatik öneri (isteğe bağlı); açık atama sessizce değiştirilmez, kullanılamazsa kendi yedeği yoksa hata verir. Engelli profil listesi ve Hub ayar alanlarını da yönetir. Profil adı düz model adı karakter kümesiyle sınırlıdır (kabuk/argüman enjeksiyonunu önler). mcp_acceptance_allow ayarı (JSON komut önekleri listesi), doğrulaması ve acceptance_allowed denetimi eklendi. (2026-10-21: `src/respected_orchestrator/roles.py` yolundan taşındı.)

**İlişkiler ve sınır:** planner, mcp_server, runner, project ve rpp tarafından kullanılır; track_record sıralama verisini kullanır. tests/workflows/test_roles.py ile test edilir.

### tests

#### [`tests/__init__.py`](../tests/__init__.py)

**Rol:** Test yalıtım kapısı.

**Amaç / sorumluluk:** Test paketi yüklenince motorun gerçek codex/AI çağrılarını reddetmesini (RESPECTED_ORCH_TEST_ISOLATION) sağlar, worker kimliğini (RESPECTED_ORCH_CHILD) temizler ve HOME, USERPROFILE, APPDATA, LOCALAPPDATA'yı taze boş bir klasöre yönlendirir; hiçbir test gerçek AI istemci ayarına veya veri köküne ulaşamaz. Çocuk süreçler devralır; klasör çıkışta silinir.

**İlişkiler ve sınır:** Eski pytest conftest.py'nin yerini alır; engine/processes ve tests/engine/test_test_isolation.py yalıtımı doğrular.

### tests/engine

#### [`tests/engine/__init__.py`](../tests/engine/__init__.py)

**Rol:** Test paketi işaretçisi.

**Amaç / sorumluluk:** motor (lane, runner, codex, sandbox, süreç, bütçe) testlerini unittest keşfi için paket yapar; içerik taşımaz.

**İlişkiler ve sınır:** python -m unittest discover -s tests -t . ve CI tarafından keşfedilir.

#### [`tests/engine/test_codex_results.py`](../tests/engine/test_codex_results.py)

**Rol:** Model çağırmayan Codex failure regresyonu.

**Amaç / sorumluluk:** Sıfır exit'te açık failure, provider hata sınıflandırması, metadata uyarısı, eksik/başarısız stream reddi, reconnect bildirimi, blocked worker'ın imzalı failure state'i ve Windows proje-local Codex CLI tercihini doğrular.

**İlişkiler ve sınır:** runner ve lanes kodunu geçici teknik veriyle çalıştırır; Git ve worker alt süreci taklit edilir, canlı model çağrılmaz.

#### [`tests/engine/test_completion_deadlines.py`](../tests/engine/test_completion_deadlines.py)

**Rol:** Completion/deadline testleri.

**Amaç / sorumluluk:** Gerçek yerel alt süreçlerle temsili Codex JSONL akışlarını (completion+hang, crash, turn.failed, reconnect, sessiz, aktif, stall, stderr disconnect) tekrarlar; verified completion'ın beklemeden ilerlemesini, başarısız/belirsiz sürecin asla başarı olmamasını, iptalin üstünlüğünü, tanı belirsizliğini ve deadline politikası doğrulamasını sınar.

**İlişkiler ve sınır:** processes.execute, codex completion/cause yardımcıları, maf_workflow review_timeout_default ve runner._workflow ile model çağrısı olmadan çalışır.

#### [`tests/engine/test_generated_artifacts.py`](../tests/engine/test_generated_artifacts.py)

**Rol:** Üretilmiş artefakt testleri.

**Amaç / sorumluluk:** Gerçek git depolarında collect_worker_changes ve export_worker_patch'in üretilmiş çıktıyı (build, egg-info, bytecode) kaynak değişiklikten ayırdığını, takip edilen veya sahiplikle adı geçen yolları gerçek sayıp symlink kaçışı, entegrasyon çakışması ve scope ihlalini kapalı-başarısız bıraktığını doğrular.

**İlişkiler ve sınır:** lanes ve runner (create_task, execute_task, check_result) uçtan uca kullanılır. Kayıt: A3_A4_ENGINE.md.

#### [`tests/engine/test_lanes.py`](../tests/engine/test_lanes.py)

**Rol:** Lane motoru davranış testleri.

**Amaç / sorumluluk:** Policy dosyaları, yürütülebilir çözümleme, yol güvenliği, yazar kilidi, git lane oluşturma ve kirli girdi bindirme, worker çağrısı ve devre kesici, kapsam ihlali, acceptance zaman aşımı ve yalnız worker farkını içeren patch dışa aktarımını sahte worker ve geçici Git depolarıyla sınar.

**İlişkiler ve sınır:** engine/lanes.py'yi doğrudan test eder; canlı provider veya Brain gerekmez.

#### [`tests/engine/test_runner.py`](../tests/engine/test_runner.py)

**Rol:** Engine acceptance testleri.

**Amaç / sorumluluk:** Geçici projelerde izolasyon, scope/stale/tamper/retry sınırı, Codex JSONL failure ve final-result, Unicode brief, Windows cancel/crash/process-tree temizliği, ortam sızıntısı temizliği, engine-key ACL, sandbox/MiMo/reviewer kuralları, apply_task ve private JSON giriş davranışlarını doğrular.

**İlişkiler ve sınır:** runner, processes ve __main__ gerçek disposable Git projelerinde çalışır; Codex CLI sınırı model çağrısı olmadan taklit edilir.

#### [`tests/engine/test_sandbox.py`](../tests/engine/test_sandbox.py)

**Rol:** Çalışan kod sınırı saldırı testleri.

**Amaç / sorumluluk:** Kısıtlı token sınırını düşmanca denemelerle kanıtlar: anahtarı (düz yol, uzun yol öneki, junction, hardlink) okuma, ayar/kanıt okuma, onay sahteciliği, kanıt üzerine yazma/silme, veri kökünde dosya yaratma, anahtar ACL'sini yeniden yazma, deny ACE'i kaldırma, sahiplik alma reddedilir; worktree ve alt süreç çalışır. Aynı sonda sandbox olmadan çalıştırılınca saldırıların başarılı olduğunu gösteren negatif kontrol ve idempotent kurulum testi içerir.

**İlişkiler ve sınır:** sandbox, sandbox_exec ve runner._signature ile gerçek Windows ACL'leri üzerinde çalışır (yalnızca Windows).

#### [`tests/engine/test_test_isolation.py`](../tests/engine/test_test_isolation.py)

**Rol:** Test izolasyon regresyonları.

**Amaç / sorumluluk:** Test işaretinin aktif olduğunu, izole testlerde Codex CLI çağrısının engellendiğini ve yerel Python acceptance komutlarının çalışmaya devam ettiğini doğrular.

**İlişkiler ve sınır:** tests paket işareti ve processes execute guard sözleşmesini sınar; canlı provider çağrısı yapmaz.

#### [`tests/engine/test_token_budget.py`](../tests/engine/test_token_budget.py)

**Rol:** Token bütçesi testleri.

**Amaç / sorumluluk:** budget modülünü ve lane/proje bütçelerini doğrular: ücretli adım öncesi denetim, UNKNOWN kullanımın açık raporu ve ücretlendirmesi, yeniden denemenin bütçeyi sıfırlamaması, bütçe aşımında hiçbir şeyin onaylanmaması ve imzalı geçmişin yeniden yazılmaması, geçersiz bütçe ayarlarının reddi.

**İlişkiler ve sınır:** budget, campaign, project, runner ve maf_workflow kullanır. Kayıt: A3_A4_ENGINE.md.

#### [`tests/engine/test_windows_processes.py`](../tests/engine/test_windows_processes.py)

**Rol:** Windows süreç yönetimi testleri.

**Amaç / sorumluluk:** Hiçbir modülün gizli pencere yardımcısı olmadan süreç başlatmadığını, ayrık süpervizör ve çocuklarının görünür konsol açmadığını, zaman aşımı ve iptalde tüm süreç ağacının öldürüldüğünü, yetim süreçlerin temizlendiğini, eksik yürütülebilirin sızıntısız raporlandığını ve çocuk süreçlerin PSModulePath devralmadığını doğrular. Sistem araçlarının PATH'ten bağımsız mutlak yol çözümünü ve frozen modda motorun kendini exe ile (supervisor ve sandbox başlatıcısı) yeniden başlattığını da sınar.

**İlişkiler ve sınır:** winproc, processes ve lanes'i kullanır. Kayıt: A1_A2_RELIABILITY.md konsol penceresi sızıntısı düzeltmesi.

#### [`tests/engine/test_worker_status_contract.py`](../tests/engine/test_worker_status_contract.py)

**Rol:** test.

**Amaç / sorumluluk:** render_brief çıktısının makine-okunur status sözleşmesini, apply_patch yasağını ve final JSON talimatını doğrular.

**İlişkiler ve sınır:** lanes.render_brief ile temporary template dizinlerini kullanır; worker çalıştırmaz.

### tests/interfaces

#### [`tests/interfaces/__init__.py`](../tests/interfaces/__init__.py)

**Rol:** Test paketi işaretçisi.

**Amaç / sorumluluk:** arayüzler (RPP, MCP, hafıza, entegrasyon) testlerini unittest keşfi için paket yapar; içerik taşımaz.

**İlişkiler ve sınır:** python -m unittest discover -s tests -t . ve CI tarafından keşfedilir.

#### [`tests/interfaces/test_integrations.py`](../tests/interfaces/test_integrations.py)

**Rol:** Entegrasyon (client config) testleri.

**Amaç / sorumluluk:** integrations modülünün istemci yapılandırmasına eklediği girdiyi doğrular: yabancı içerik korunur, apply idempotent ve onaylı digest ister, düzenlenmiş/yabancı girdi ve geçersiz config yazılmadan reddedilir, rollback yalnız bizim girdimizi geri alır. Okunamayan bir istemci yapılandırmasının diğerlerini engellemediği test edilir.

**İlişkiler ve sınır:** integrations ve rpp modüllerini çağırır; RPP op'ları yalnız v1.1'de listelenir. RPP_V1_1.md lifecycle sözleşmesiyle uyumludur.

#### [`tests/interfaces/test_mcp_server.py`](../tests/interfaces/test_mcp_server.py)

**Rol:** MCP sunucu testleri.

**Amaç / sorumluluk:** mcp_server araç listesini, orkestre edilen süreçte araçların gizlenmesini (özyineleme koruması), apply için doğrulanmış digest ve kimlik doğrulamasını, varsayılan auto_apply reddini, hafıza notunun yazma izni olmadan kapalı olmasını ve stdio gidiş-dönüşünü doğrular. MCP'de ayrıcalıklı görev seçenekleri ve bypass bayrağı varyantlarının reddi test edilir. MCP'de acceptance/verify komutlarının kullanıcı listesi olmadan reddi, önek eşleşmesi, ayrı --allow-privileged anahtarı ve auto_apply onayının özel seçenekleri açmadığı test edilir. initialize yanıtındaki `instructions` alanının skill kurallarını içerdiği, front matter ve CLI bölümünü içermediği test edilir.

**İlişkiler ve sınır:** mcp_server ve runner'ı çağırır. Kayıt: docs/records/2026-10-15-mcp-access.md.

#### [`tests/interfaces/test_memory.py`](../tests/interfaces/test_memory.py)

**Rol:** Hafıza istemcisi testleri.

**Amaç / sorumluluk:** memory modülünün RPP çağrısını doğrular: sonuç ve hata eşlemeleri, zaman aşımı, başlatma hatası, child çıktısında token temizliği, token dosyası gidiş-dönüşü ve boşken kısıtlama, geçersiz token reddi, komut/ayar doğrulaması, sorgu üretimi ve bağlam bloğu.

**İlişkiler ve sınır:** memory modülünü çağırır; token yalnızca stdin ve 0600/ACL dosyasında kalır. Karar: docs/decisions/MEMORY_INTEGRATION.md.

#### [`tests/interfaces/test_memory_integration.py`](../tests/interfaces/test_memory_integration.py)

**Rol:** Hafıza entegrasyon testleri.

**Amaç / sorumluluk:** Hafızanın runner, kampanya ve RPP ayarlarıyla bütünleşmesini doğrular: yazma izni ayrıdır ve token sızmaz, token yazma-yalnızdır, memory.use politika matrisi, brief ve kanıt temizliği, hata veya devre dışı durumunda görevin normal çalışması, lane'de main_root kullanımı.

**İlişkiler ve sınır:** memory, campaign, rpp ve runner kullanır. Karar: docs/decisions/MEMORY_INTEGRATION.md.

#### [`tests/interfaces/test_rpp.py`](../tests/interfaces/test_rpp.py)

**Rol:** RPP testleri.

**Amaç / sorumluluk:** interfaces/rpp.py'nin v1.0 ve v1.1 davranışını doğrular: her yanıtta tüm anahtarlar, bilinmeyen op, sürüm uzlaşması ve sınırları, operation_id şekli, çöp girdide istisna olmaması, manifest, health, ayar şeması, apply idempotansı ve çakışması, secret maskeleme ve receipt okuma. Ayar şemasının mcp_acceptance_allow alanını da içerdiği doğrulanır.

**İlişkiler ve sınır:** rpp ve EngineContext çağrılır. Karar: docs/decisions/RPP_V1.md ve RPP_V1_1.md.

#### [`tests/interfaces/test_rpp_lifecycle.py`](../tests/interfaces/test_rpp_lifecycle.py)

**Rol:** RPP lifecycle testleri.

**Amaç / sorumluluk:** lifecycle op'larını doğrular: plan salt okunurdur, apply dosya ve receipt yazar, operation_id başına idempotenttir, çakışma, çökme journal'ından devam, uninstall yalnız sahip olunan dosyaları siler, rollback önceki içeriği geri verir, güvensiz yol reddedilir. DistributionRecordTests: bütün paketin kaydı ve sonradan kurcalanan ikili dosyanın repair-needed görünmesi, build'den sapmış kopyanın kayıtsız reddi, distribution.json ile kökten kaçışın reddi, eksik distribution.json için tipli hata ve kaydı kaldırıp program dosyalarını koruyan uninstall.

**İlişkiler ve sınır:** rpp ve lifecycle modüllerini çağırır. Karar: docs/decisions/RPP_V1_1.md; durum: RPP_V11_STATUS.md.

### tests/packaging

#### [`tests/packaging/__init__.py`](../tests/packaging/__init__.py)

**Rol:** Test paketi işaretçisi.

**Amaç / sorumluluk:** Paketlenmiş build testlerini unittest keşfi için paket yapar; içerik taşımaz.

**İlişkiler ve sınır:** python -m unittest discover -s tests -t . ve CI tarafından keşfedilir.

#### [`tests/packaging/test_frozen_build.py`](../tests/packaging/test_frozen_build.py)

**Rol:** Paketlenmiş exe uçtan uca testi.

**Amaç / sorumluluk:** dist/ (veya RESPECTED_ORCH_DIST) içindeki paketlenmiş motoru PATH'te Python yokken sürer: _selfcheck ve status, RPP manifest/health, MCP tools/list ve geçici git deposunda gerçek bir yazma görevini ayrık süpervizör (_execute) ve kısıtlı token'lı kabul (_sandbox-exec) üzerinden sonuna kadar çalıştırıp doğrular. Build yoksa yerelde atlanır, CI'da zorunludur.

**İlişkiler ve sınır:** tools/build_dist.py çıktısını kullanır; motorun kendini yeniden başlattığı iki yolu (supervisor, sandbox) frozen modda kanıtlar.

### tests/workflows

#### [`tests/workflows/__init__.py`](../tests/workflows/__init__.py)

**Rol:** Test paketi işaretçisi.

**Amaç / sorumluluk:** iş akışları (MAF, kampanya, proje, roller) testlerini unittest keşfi için paket yapar; içerik taşımaz.

**İlişkiler ve sınır:** python -m unittest discover -s tests -t . ve CI tarafından keşfedilir.

#### [`tests/workflows/test_campaign.py`](../tests/workflows/test_campaign.py)

**Rol:** Kampanya testleri.

**Amaç / sorumluluk:** Sahte worker'larla gerçek eşzamanlılık, bağımlılık/atlama, tek seferlik final master, non-Git mirror + apply, geçersiz spec, allow_apply daraltması, engine snapshot ve final prompt içeriğini doğrular.

**İlişkiler ve sınır:** src/respected_orchestrator/campaign.py ve runner.apply_task'ı sınar; tests/workflows/test_project.py aynı fixture yaklaşımını paylaşır.

#### [`tests/workflows/test_maf_coding.py`](../tests/workflows/test_maf_coding.py)

**Rol:** MAF coding testleri.

**Amaç / sorumluluk:** Fake worker/reviewer ile MAF adapterinin completed/failed, checkpoint replay, fresh-run correction ve patch devralma, escalation, sınırlı retry, deep review, reviewer timeout/geçersiz çıktı, token ve bütçe muhasebesi, insan onayı (tahrif, çapraz-run, operatör-yalnız reddi) ve private JSON yönlendirmesini doğrular.

**İlişkiler ve sınır:** maf_workflow, runner create/execute/check/approve ve __main__ maf/maf-approve sözleşmelerini geçici Git fixture'larıyla canlı model çağrısı olmadan sınar.

#### [`tests/workflows/test_maf_workflow.py`](../tests/workflows/test_maf_workflow.py)

**Rol:** MAF workflow tests.

**Amaç / sorumluluk:** Iki fake worker es zamirligi, bounded correction, rejection, invalid/failed reviewer output ve checkpoint resume davranislarini dogrular.

**İlişkiler ve sınır:** maf_workflow adaptörünün karar durumlarını canlı model çağrısı olmadan sınar.

#### [`tests/workflows/test_project.py`](../tests/workflows/test_project.py)

**Rol:** Otonom proje testleri.

**Amaç / sorumluluk:** Sahte worker'larla bağımlı fazların yeni prompt olmadan bitmesini, sınırlı yeniden deneme sonrası blocked'ı, auto_apply yetkisizken kaynağa dokunulmamasını, kilit/iptal/zaman bütçesini, çöken supervisor'ın çift campaign olmadan resume'unu, geçersiz spec reddini ve final review girdisini doğrular.

**İlişkiler ve sınır:** src/respected_orchestrator/project.py'yi sınar; tests/workflows/test_campaign.py ile fixture yaklaşımını paylaşır.

#### [`tests/workflows/test_project_adversarial.py`](../tests/workflows/test_project_adversarial.py)

**Rol:** Proje adversarial testleri.

**Amaç / sorumluluk:** workflows/project.py için kötü niyetli ve çökme senaryolarını doğrular: apply sonrası çökmede ikinci apply olmaması, çakışmada engelleme, ProcessStopped sınırlı deneme, iptal, bütçe, kalıcı deadline ve bozuk kilit, bozuk spec için ValueError, reddedilen lane'in sınırlı yeniden denenmesi.

**İlişkiler ve sınır:** project, campaign, maf_workflow ve runner'ı kullanır. Karar: docs/decisions/PROJECT_SUPERVISOR_REVIEW.md.

#### [`tests/workflows/test_project_recovery.py`](../tests/workflows/test_project_recovery.py)

**Rol:** Proje kurtarma testleri.

**Amaç / sorumluluk:** Proje supervisor'ının kurtarma davranışını doğrular: başarısız denemede token kaydı, kullanımı raporlanmayan lane'de kapalı-başarısız engelleme, bağımlı lane'in uygulanmış çıktıyı görmesi, yalnız başarısız lane'lerin düzeltmesi, kill sonrası çift kampanya/apply olmaması ve imzalı durumdan hata nedeni.

**İlişkiler ve sınır:** project, campaign, maf_workflow ve runner'ı kullanır. Kayıt: LANE_SUMMARY_REVIEW.md ve A3_A4_ENGINE.md.

#### [`tests/workflows/test_reviewer_reliability.py`](../tests/workflows/test_reviewer_reliability.py)

**Rol:** Reviewer güvenilirliği testleri.

**Amaç / sorumluluk:** Review hata teşhisini (zararsız modeller-yenileme satırı), sağlayıcıya duyarlı zaman aşımlarını, sınırlı yeniden denemeyi, yalnız review yeniden çalıştırmada worker'ın tekrar çalışmaması ve token geçmişinin korunmasını, tahrif edilmiş veya değişmiş proje patch'inin yeniden kullanılmamasını doğrular.

**İlişkiler ve sınır:** maf_workflow, codex, project, campaign ve runner'ı kullanır; modeller sahte çağrılarla taklit edilir. Kayıt: A1_A2_RELIABILITY.md.

#### [`tests/workflows/test_roles.py`](../tests/workflows/test_roles.py)

**Rol:** Rol ataması testleri.

**Amaç / sorumluluk:** roles çözümlemesini (açık atama > Hub varsayılanı > otomatik, sessiz atama yok), engelli profillerin ayar olmasını, komut üretimini ve kullanımın hiç sıfır sayılmamasını, review prompt sınırını, master rolünü ve planner'ın doğrulanmış spec üretip başlatmamasını doğrular. Görevde çalıştırılamayan rollerin (tester/coordinator) reddi test edilir.

**İlişkiler ve sınır:** roles, maf_workflow ve runner (create_task, inspect_task) kullanılır. Karar: docs/decisions/ROLE_ASSIGNMENT.md.

### tools

#### [`tools/build_dist.py`](../tools/build_dist.py)

**Rol:** Paketlenmiş motor build aracı.

**Amaç / sorumluluk:** PyInstaller onedir ile Python gerektirmeyen tek klasör üretir: respected-orchestrator.exe, app/ ve her dosyanın sha256'sını listeleyen distribution.json. Agent Framework'ün tembel alt modüllerini toplar; bildirilen bağımlılık kapanışı dışındaki kurulu paketleri dışlar ki yerel build temiz CI build'iyle aynı olsun (yaklaşık 29 MB). Sürüm kaynaktaki __version__'dan okunur.

**İlişkiler ve sınır:** packaging/entrypoint.py'yi dondurur; Hub release/tools/build_bundle.py bunu çağırıp imzalı katalog paketi yapar; tests/packaging/test_frozen_build.py çıktıyı sınar.

#### [`tools/repository_map.py`](../tools/repository_map.py)

**Rol:** Atlas geliştirici aracı.

**Amaç / sorumluluk:** Bağımsız ürün adıyla metadata/hash denetimi ve no-Git filesystem keşfi sağlar.

**İlişkiler ve sınır:** Brain aracının bağımsız kopyasıdır; dış repo importu yoktur, normal Git CI modu korunur.

## Haritayı güncel tutma sözleşmesi

Yeni dosya keşfi otomatiktir; yeni kodun doğru anlamsal açıklaması otomatik olarak bilinemeyeceği için insan/ajan incelemesi gerekir. `--update` yeni kayıtları `NEEDS_REVIEW` olarak ekler ve indeksten silinenleri çıkarır. Dosya değişikliği açıklamanın artık doğru olduğuna dair yeniden inceleme gerektirir; LF/CRLF dönüşümü değişiklik sayılmaz.

```sh
python tools/repository_map.py --update
# JSON içindeki NEEDS_REVIEW alanlarını gerçek rol/amaç/ilişkilerle doldur.
python tools/repository_map.py --accept-reviewed path/to/changed.py
python tools/repository_map.py --write
python tools/repository_map.py --check
python -m unittest tests.repository_map_test -v
```

`--accept-reviewed` yalnız açıklaması incelenmiş açık bir yolun içerik hash'ini günceller; içerik açıklaması üretmez. Aynı komutta birden fazla seçenek verilebilir. `--write` keşfedilmiş eksikleri görünür biçimde üretebilir ama `--check` her `NEEDS_REVIEW` kaydını reddeder. CI kapısı eksik/fazla/çift kayıtları, kayıp dosyaları, eski açıklama hash'lerini ve Markdown üretim farkını hata kodu 1 ile durdurur. Staged deletion Git indeksinden kalktığı için envanterden çıkar; yalnız diskten silinmiş izlenen dosya hata olarak kalır.

JSON envanteri ve üretilmiş Markdown kendi kendini hash'leme döngüsünü önlemek için `generated` damgası taşır. JSON açıklamalarındaki değişiklik yine Markdown üretim karşılaştırmasıyla yakalanır. Diğer dosyalar SHA256 inceleme damgasıyla bağlıdır. Hash, açıklamanın doğru olduğunu matematiksel olarak kanıtlamaz; açıklamayı yazan kişi kodu ve ilişkileri okumakla sorumludur.

Her dosya ekleme/silme/yeniden adlandırma ve davranış değişikliğinde bu güncelleme aynı iş içinde yapılır. CI çalışması dosyaya yazmaz. `--root` yalnız farklı bir kaynak checkout'u denetlemek içindir; kurulu AppRoot, DataRoot veya kişisel vault üzerinde bu aracı çalıştırmayın.


`--filesystem-only` Git çalıştırmaz; kök ignore kurallarını ve gözden geçirilmiş kaynak yollarını kullanır. Eksik bilinen dosya check hatası olarak korunur. Staged durum ve iç içe ignore sözleşmelerinin Git ile eşdeğerliği bu modun kapsamı değildir; CI normal Git modunu kullanır.
