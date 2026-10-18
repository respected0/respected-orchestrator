# Respected Orchestrator — Kaynak Atlası

> Bu belge `tools/repository_map.py` tarafından `docs/repository_inventory.json` içindeki gözden geçirilmiş açıklamalardan üretilir. Doğrudan bu Markdown dosyasını düzenlemeyin.

**Kapsam:** 86 proje dosyası. Git çalıştırmadan dosya sistemi ve kök ignore kurallarıyla keşfedilen bağımsız ürün kaynağıdır. Bağımlılık/üretim önbellekleri ayrı kategoriler olarak açıklanır.

## Eksiksiz kaynak ağacı

```text
respected-orchestrator/
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
├── pyproject.toml
├── src/
│   └── respected_orchestrator/
│       ├── __init__.py
│       ├── __main__.py
│       ├── antigravity_orchestrator.py
│       ├── budget.py
│       ├── campaign.py
│       ├── context.py
│       ├── integrations.py
│       ├── lifecycle.py
│       ├── maf_workflow.py
│       ├── mcp_server.py
│       ├── memory.py
│       ├── planner.py
│       ├── processes.py
│       ├── project.py
│       ├── resources/
│       │   ├── policy.json
│       │   └── skills/
│       │       └── kod-orkestrasyon/
│       │           └── SKILL.md
│       ├── roles.py
│       ├── rpp.py
│       ├── runner.py
│       ├── sandbox.py
│       ├── sandbox_exec.py
│       ├── track_record.py
│       ├── vertical_slice.py
│       └── winproc.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_antigravity.py
│   ├── test_campaign.py
│   ├── test_codex_results.py
│   ├── test_completion_deadlines.py
│   ├── test_engine.py
│   ├── test_generated_artifacts.py
│   ├── test_integrations.py
│   ├── test_maf_coding.py
│   ├── test_maf_coding_demo.py
│   ├── test_maf_workflow.py
│   ├── test_mcp_server.py
│   ├── test_memory.py
│   ├── test_memory_integration.py
│   ├── test_project.py
│   ├── test_project_adversarial.py
│   ├── test_project_recovery.py
│   ├── test_reviewer_reliability.py
│   ├── test_roles.py
│   ├── test_rpp.py
│   ├── test_rpp_lifecycle.py
│   ├── test_sandbox.py
│   ├── test_test_isolation.py
│   ├── test_token_budget.py
│   ├── test_vertical_slice.py
│   ├── test_windows_processes.py
│   ├── test_worker_environment.py
│   └── test_worker_status_contract.py
└── tools/
    ├── repository_map.py
    └── run_maf_coding_demo.py
```

## Dosya dosya sorumluluk ve ilişkiler

Her kayıt bir dosyayı açıklar; boş `.gitkeep` ve paket `__init__.py` dosyaları da dahildir. Aşağıdaki yollar depo köküne göredir. Tarihsel belgeler canlı davranışın yetkili kaynağı değildir.

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

**İlişkiler ve sınır:** sandbox.py, sandbox_exec.py ve tests/test_sandbox.py ile birlikte okunur.

#### [`docs/decisions/MCP_PERMISSIONS.md`](../docs/decisions/MCP_PERMISSIONS.md)

**Rol:** MCP yetki kararı.

**Amaç / sorumluluk:** MCP üzerinden bağlanan modelin yapabileceklerini sınırlayan kararı kaydeder: özel worker/command/apply_root/engine_source yalnızca --allow-privileged ile, kabul ve verify komutları yalnızca kullanıcının mcp_acceptance_allow önek listesindeyse, bypass bayrakları her yerde reddedilir; sınırları ve kanıtı belirtir.

**İlişkiler ve sınır:** mcp_server.py, roles.py ve runner._command ile birlikte okunur; docs/decisions/ACCEPTANCE_SANDBOX.md onaylı komutların yine sandbox'ta çalıştığını açıklar.

#### [`docs/decisions/MEMORY_INTEGRATION.md`](../docs/decisions/MEMORY_INTEGRATION.md)

**Rol:** Karar: isteğe bağlı SecondBrain hafızası.

**Amaç / sorumluluk:** Görevlerin `memory.use` ile SecondBrain'den RPP `memory.recall` üzerinden hafıza isteme kararını anlatır. Hub'da etkinleştirme bir izindir, varsayılan değildir; en fazla yaklaşık 3000 karakter güvenilmez veri olarak brief'e eklenir, her hata 'hafıza yok' demektir. Token yalnızca 0600/ACL'li dosyada ve child stdin'inde tutulur, loglara ve kanıta sızmaz.

**İlişkiler ve sınır:** memory.py ve runner.create_task bu kararı uygular; Hub gizli ayarları (memory_enabled, memory_command, memory_grant_id, memory_token) RPP settings.apply ile yazar. tests/test_memory.py ve tests/test_memory_integration.py kararın gizlilik ve politika kurallarını doğrular.

#### [`docs/decisions/PROJECT_SUPERVISOR_REVIEW.md`](../docs/decisions/PROJECT_SUPERVISOR_REVIEW.md)

**Rol:** Karar: proje supervisor adversarial incelemesi.

**Amaç / sorumluluk:** project.py otonom proje supervisor'ının ve campaign.py'nin ilgili parçalarının kaynak değiştirilmeden yapılan adversarial incelemesi. Şüpheli kusurları (ör. bozuk budget/verify/after için ValueError yerine AttributeError/TypeError) satır numaralarıyla belgeler.

**İlişkiler ve sınır:** src/respected_orchestrator/project.py ve campaign.py incelenen kodlardır. tests/test_project_adversarial.py bu incelemenin doğru kalan değişmezlerini ve sonradan kapatılan kusurlarını test eder.

#### [`docs/decisions/ROLE_ASSIGNMENT.md`](../docs/decisions/ROLE_ASSIGNMENT.md)

**Rol:** Karar: satıcıdan bağımsız rol ataması.

**Amaç / sorumluluk:** Her uyumlu model/sağlayıcı/araç her iş akışı rolünü üstlenebilir; kodda 'model X yalnızca rol Y' kuralı yoktur. Rol, profil, araç ve atama ayrı kavramlardır; öncelik sırası açık atama, Hub varsayılanı, isteğe bağlı otomatik atamadır; aynı rolün çelişen iki değeri ROLE_CONFLICT olur.

**İlişkiler ve sınır:** roles.py ve runner.create_task kararı uygular; maf_workflow reviewer/derin review için atanan aracı kullanır. tests/test_roles.py kararı doğrular; kayıt: docs/records/2026-10-15-role-assignment-validation.md.

#### [`docs/decisions/RPP_V1.md`](../docs/decisions/RPP_V1.md)

**Rol:** Karar: RPP v1.0 sunucu sözleşmesi.

**Amaç / sorumluluk:** Orchestrator'ın RPP v1.0'ı özel giriş noktasından (stdin'de tek JSON istek, stdout'ta tek JSON satır; ağ dinleyicisi ve genel CLI yok) sunmasını tanımlar. Op'lar manifest, health, settings.schema/validate/apply/readback; ayarlar atomik yazılır, apply kalıcı receipt üretir ve yanıtlar asla traceback veya secret içermez.

**İlişkiler ve sınır:** src/respected_orchestrator/rpp.py sözleşmeyi uygular; v1.1 uzantısı RPP_V1_1.md'dedir. tests/test_rpp.py v1.0 davranışını doğrular.

#### [`docs/decisions/RPP_V1_1.md`](../docs/decisions/RPP_V1_1.md)

**Rol:** Karar: RPP v1.1 geriye uyumlu uzantı.

**Amaç / sorumluluk:** v1.0'ın katı üst kümesi olan v1.1'i tanımlar: 1.0..1.1 sürüm uzlaşması, lifecycle plan/apply/status/rollback ve operation.receipt op'ları, yedi yeni tipli hata ve zengin manifest. Taşıma ve mevcut op davranışı değişmez; yeni op'lar aynı allow-list kayıt desenine eklenir.

**İlişkiler ve sınır:** rpp.py ve lifecycle.py uygular; RPP_V1.md'ye eklenir. tests/test_rpp.py (RppV11Tests) ve tests/test_rpp_lifecycle.py doğrular.

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

**Amaç / sorumluluk:** Rol ataması uygulamasının neyi değiştirdiğini (roles.py, sabit reviewer/MiMo kurallarının kaldırılması, yeni RPP ayarları) ve tam test paketi ile gerçek tek kullanımlık repo üzerindeki doğrulama kanıtını kaydeder.

**İlişkiler ve sınır:** Karar: docs/decisions/ROLE_ASSIGNMENT.md. tests/test_roles.py, test_campaign ve test_project kanıtta anılan testlerdir.

#### [`docs/records/2026-10-15-secondbrain-memory-recall-project.md`](../docs/records/2026-10-15-secondbrain-memory-recall-project.md)

**Rol:** Tarihli kanıt kaydı: SecondBrain memory.recall projesi.

**Amaç / sorumluluk:** SecondBrain'in ilk projesinin Orchestrator üzerinden çalıştırılmasını kaydeder: git mirror izolasyonu, Hub tarzı rol varsayılanları, iki fazlı proje sonuçları, reviewer engeli ve toplam yaklaşık 578k ağırlıklı token. Gerçek repo yalnızca baseline hash denetiminden sonra güncellenmiştir.

**İlişkiler ve sınır:** Sözleşme respected-secondbrain RPP_MEMORY_RECALL.md'de; ilgili karar docs/decisions/MEMORY_INTEGRATION.md. Proje supervisor'ı project.py ve kayıtla birlikte test_project_recovery.py ilgilidir.

### docs/records/2026-10-master-program

#### [`docs/records/2026-10-master-program/A1_A2_RELIABILITY.md`](../docs/records/2026-10-master-program/A1_A2_RELIABILITY.md)

**Rol:** Tarihli kanıt kaydı: reviewer güvenilirliği (A1/A2).

**Amaç / sorumluluk:** Sağlayıcıya duyarlı review zaman aşımı, ayrı hata sınıfları, sınırlı review yeniden denemesi (varsayılan 1) ve yalnız review yeniden çalıştırma yolunu belgeler. Worker işi yalnızca imzalı sonuç yeniden doğrulanırsa yeniden kullanılır; red kesindir, geçersiz çıktı yeniden denenmez.

**İlişkiler ve sınır:** maf_workflow.py, vertical_slice.py, runner.py ve project.py ile uygulanır. tests/test_reviewer_reliability.py doğrular.

#### [`docs/records/2026-10-master-program/A3_A4_ENGINE.md`](../docs/records/2026-10-master-program/A3_A4_ENGINE.md)

**Rol:** Tarihli kanıt kaydı: üretilmiş artefakt ve token bütçesi (A3/A4).

**Amaç / sorumluluk:** A3: untracked/ignored üretilmiş dosyaları (build, egg-info, __pycache__) gerçek değişiklikten ayırıp patch'e sokmama, gerçek scope ihlallerini koruma. A4: lane başına kalıcı token bütçesi, UNKNOWN kullanımın açık raporlanması ve proje bütçesinde varsayılan ücretlendirme.

**İlişkiler ve sınır:** antigravity_orchestrator.py, runner.py, budget.py, maf_workflow.py, project.py ve campaign.py ilgilidir; A1_A2_RELIABILITY.md üzerine kurulur. tests/test_generated_artifacts.py ve tests/test_token_budget.py doğrular.

#### [`docs/records/2026-10-master-program/CODEX_RECONNECT_REVIEW.md`](../docs/records/2026-10-master-program/CODEX_RECONNECT_REVIEW.md)

**Rol:** İnceleme kaydı: Codex reconnect bildirimi.

**Amaç / sorumluluk:** Codex JSONL akışındaki fatal olmayan 'Reconnecting...' üst düzey error olayının worker_failed sayılması hatasının düzeltmesini onaylar. Tolerans yalnızca tam önek, turn.failed yokluğu, başka error yokluğu ve tam olarak bir turn.completed ile bitiş koşullarında geçerlidir.

**İlişkiler ve sınır:** vertical_slice.py'deki Codex akış ayrıştırıcısını inceler. tests/test_reviewer_reliability.py diagnose ve reconnect testleriyle ilişkilidir.

#### [`docs/records/2026-10-master-program/LANE_SUMMARY_REVIEW.md`](../docs/records/2026-10-master-program/LANE_SUMMARY_REVIEW.md)

**Rol:** İnceleme kaydı: lane özeti hata nedeni.

**Amaç / sorumluluk:** Kampanya lane özetinin genel worker_failed yerine imzalı çalıştırma durumundaki gerçek nedeni (scope_violation, timed_out) taşımasını onaylar. Geçersiz/eksik imzalı status genel MAF nedenine döner; başka run dizinine kopyalanmış status final_run_id eşleşmezse reddedilir.

**İlişkiler ve sınır:** campaign._lane_summary ve project.py hata mesajı incelenen koddur. tests/test_project_recovery.py ilgili özet testlerini içerir.

#### [`docs/records/2026-10-master-program/RPP_V11_STATUS.md`](../docs/records/2026-10-master-program/RPP_V11_STATUS.md)

**Rol:** Tarihli kanıt kaydı: RPP v1.1 uygulama durumu.

**Amaç / sorumluluk:** Orchestrator'ın RPP v1.1 yüzeyinin (sürüm uzlaşması, lifecycle ve receipt op'ları, yedi yeni hata) tamamlandığını kod satırı ve test referanslarıyla kaydeder; kardeş repolar yalnız okunmuştur, kod değişmemiştir.

**İlişkiler ve sınır:** Sözleşme docs/decisions/RPP_V1_1.md ve RPP_V1.md; kod rpp.py ve lifecycle.py. tests/test_rpp.py ve tests/test_rpp_lifecycle.py anılan testlerdir.

#### [`docs/records/2026-10-master-program/UNTRACKED_INPUTS_REVIEW.md`](../docs/records/2026-10-master-program/UNTRACKED_INPUTS_REVIEW.md)

**Rol:** İnceleme kaydı: untracked sahipli girdiler.

**Amaç / sorumluluk:** Lane'lerin HEAD'den oluşturulması nedeniyle untracked sahipli dosyaların worker'a taşınması için opt-in tasarımı onaylar: ignored, tracked, dosya olmayan ve symlink girdiler reddedilir, ownership ve forbidden süzgeci uygulanır. Git'in NUL ayrımlı çıktısının yerel kod sayfasıyla çözülmesi düzeltilmiştir.

**İlişkiler ve sınır:** runner'daki include_untracked_owned yolu ve overlay_dirty_inputs incelenen koddur. tests/test_generated_artifacts.py ilgili untracked sahipli girdi testleriyle ilişkilidir.

### docs

#### [`docs/repository_inventory.json`](../docs/repository_inventory.json)

**Rol:** Anlamsal atlas kaynağı.

**Amaç / sorumluluk:** Dosya rol, amaç, ilişki ve içerik inceleme hash kayıtlarını tutar.

**İlişkiler ve sınır:** repository_map update/accept-reviewed/write/check kapılarının tek anlamsal kaynağıdır.

### Depo kökü

#### [`pyproject.toml`](../pyproject.toml)

**Rol:** Python paket tarifi.

**Amaç / sorumluluk:** respected-orchestrator kimliği, Python tabanı ve policy/skill wheel kaynaklarını tanımlar.

**İlişkiler ve sınır:** Setuptools bağımsız wheel üretir; public console script ve Brain bağımlılığı yoktur.

### src/respected_orchestrator

#### [`src/respected_orchestrator/__init__.py`](../src/respected_orchestrator/__init__.py)

**Rol:** Paket kimliği.

**Amaç / sorumluluk:** Bağımsız Python paketini ve sürümünü tanımlar.

**İlişkiler ve sınır:** Private status girişinin sürüm kaynağıdır; import yan etkisi yoktur.

#### [`src/respected_orchestrator/__main__.py`](../src/respected_orchestrator/__main__.py)

**Rol:** Private JSON giriş.

**Amaç / sorumluluk:** Hub ve testler için özel JSON girişidir (herkese açık CLI değil). status/create/start/list/inspect/cancel/check/retry/apply, maf/maf-approve, campaign-*, project-*, roles, plan, rpp, mcp ve antigravity komutlarını ilgili modüle yönlendirir. stdin JSON'u UTF-8 BOM'lu da kabul eder; hatalar JSON error olarak döner, başarısız _execute sonucu exit 1 verir. mcp alt komutu --allow-auto-apply ve ayrı --allow-privileged anahtarlarını sunucuya iletir.

**İlişkiler ve sınır:** runner, roles, campaign, project, maf_workflow, planner, mcp_server, rpp ve antigravity_orchestrator'ı çağırır; Brain launcher/vault gerektirmez. tests/test_engine.py ve tests/test_maf_coding.py private JSON sözleşmesini doğrular.

#### [`src/respected_orchestrator/antigravity_orchestrator.py`](../src/respected_orchestrator/antigravity_orchestrator.py)

**Rol:** Çıkarılmış worktree motoru.

**Amaç / sorumluluk:** Policy, lane/worktree, dirty-input overlay, baseline commit, brief, WriterLock, kapsam kontrolü, acceptance ve binary patch dışa aktarımı yardımcılarını ve ortak worker çıkış sınıflandırmasını (sıfır exit'li açık failure reddi dahil) korur. İzin atlatan (permission bypass) komutlar reddedilir; ham apply kapalıdır. WriterLock sahibi ölmüş kilidi geri alır; yaşayan sahip varsa reddeder.

**İlişkiler ve sınır:** runner ve processes/context tarafından ortak katman olarak kullanılır; 'antigravity' alt komutu uyumluluk girişi olarak __main__'den çağrılır. tests/test_engine.py ve tests/test_codex_results.py kapsar.

#### [`src/respected_orchestrator/budget.py`](../src/respected_orchestrator/budget.py)

**Rol:** Token bütçesi ve kullanım muhasebesi.

**Amaç / sorumluluk:** Şerit başına token bütçesini ve dürüst kullanım muhasebesini yönetir. Kullanım bildirmeyen ama başlamış adım SIFIR değil BİLİNMEYEN sayılır ve yalnızca bütçe kontrolünde varsayılan bir ücretle yazılır; hiç başlamayan adım sayılmaz.

**İlişkiler ve sınır:** Proje/kampanya bütçe kontrolleri ve runner tarafından çağrılır; engine sonuçlarındaki usage alanlarını okur. tests/test_token_budget.py ile test edilir.

#### [`src/respected_orchestrator/campaign.py`](../src/respected_orchestrator/campaign.py)

**Rol:** Kalıcı çok-repo kampanya supervisor'ı.

**Amaç / sorumluluk:** Claude master'ın devrettiği 1..8 workstream'i detached supervisor ile paralel MAF hatlarına çevirir (ayrı data-root, WriterLock, anahtar ve çalışma alanı; after ile bağımlılık). Non-Git kaynak için gizli dosyalar hariç geçici Git mirror kurar, doğrulanmış patch'i apply_root'a uygulatır ve motoru snapshot'layıp supervisor'ı oradan çalıştırır. Tüm hatlar bitince imzalı result.json yazar, final.claim ile tam bir kez final master başlatır; allow_apply açıksa yalnız 'python -m respected_orchestrator' komutlarına izin verir.

**İlişkiler ve sınır:** runner.create_task/apply_task, maf_workflow.run_maf_coding_task ve processes.execute'u kullanır; project.py bunu faz başına çağırır; __main__ campaign-* komutlarıyla bağlanır. tests/test_campaign.py kapsar.

#### [`src/respected_orchestrator/context.py`](../src/respected_orchestrator/context.py)

**Rol:** Bağımsız roots/state.

**Amaç / sorumluluk:** EngineContext DataRoot/state/workspace ve AppRoot ayrımı, no-link path ve atomik JSON yazısını sağlar.

**İlişkiler ve sınır:** runner ve çıkarılmış motor kullanır; Brain context/vault/lease bağı yoktur.

#### [`src/respected_orchestrator/integrations.py`](../src/respected_orchestrator/integrations.py)

**Rol:** AI istemcisi MCP entegrasyonu.

**Amaç / sorumluluk:** RPP integrations.* işlemlerini uygular: Orchestrator MCP sunucusunu AI istemci yapılandırmalarına (claude-code, codex, cursor, gemini, windsurf, claude-desktop) Discover/Inspect/Plan/Apply/Verify/Rollback akışıyla kaydeder. Yalnızca 'respected-orchestrator' girdisine dokunur; sahip olunmayan veya kullanıcının sonradan düzenlediği girdi ezilmez, apply onaylanan planın özetini ister. Okunamayan bir istemci yapılandırması, istenmeyen diğer istemcilerin planını engellemez (state=unreadable); istenen istemci için hata yine verilir.

**İlişkiler ve sınır:** rpp.py tarafından çağrılır; lifecycle (LifecycleError, atomik yazma, makbuz) ve context.safe_path kullanır. tests/test_integrations.py ile test edilir.

#### [`src/respected_orchestrator/lifecycle.py`](../src/respected_orchestrator/lifecycle.py)

**Rol:** RPP yaşam döngüsü durumu.

**Amaç / sorumluluk:** Sürümlü kurulum manifestosu, planlar, günlük ve rollback için RPP v1.1 yaşam döngüsü durumunu yönetir (install/update/repair/uninstall). Yalnızca açık kökler üzerinde safe_path ile sınırlı yerel dosya işlemi yapar; kabuk ve ağ yoktur, hatalar LifecycleError üçlüsüyle döner.

**İlişkiler ve sınır:** rpp.py ve integrations.py tarafından kullanılır; context'teki safe_path ve atomic_write_json'a dayanır. tests/test_rpp_lifecycle.py ile test edilir.

#### [`src/respected_orchestrator/maf_workflow.py`](../src/respected_orchestrator/maf_workflow.py)

**Rol:** MAF workflow adapter.

**Amaç / sorumluluk:** Microsoft Agent Framework functional workflow ile eş zamanlı worker fan-out, replayable step cache, checkpoint resume, bağımsız review, önceki başarılı patch'i devralan sınırlı correction ve isteğe bağlı deep review sağlar. Review deadline'ı provider-aware tavan ve pipeline deadline ile sınırlıdır, toplam bütçe worker+review tavanlarından türetilir veya açık timeout_seconds sert sınırdır. Reviewer hatası/geçersiz çıktısı fail-closed kalır; escalate_from_round'dan itibaren düzeltmeyi escalate_profile devralır, önceki implementer bağımsız reviewer olur; imzalı maf-result.json yazılır.

**İlişkiler ve sınır:** runner execute_task/create_task/check_result ve vertical_slice run_codex_call adaptörlerini kullanır; __main__ 'maf' komutu ve campaign tarafından çağrılır. tests/test_maf_coding.py kapsar.

#### [`src/respected_orchestrator/mcp_server.py`](../src/respected_orchestrator/mcp_server.py)

**Rol:** Vendor-bağımsız MCP stdio ön yüzü.

**Amaç / sorumluluk:** Orchestrator motorunu yalnızca standart kütüphaneyle MCP (stdio) araçları olarak sunar (plan, task_start, project_start, progress, evidence, resume, cancel, memory_note, apply). Motorun onayları geçerli kalır, apply doğrulanmış patch özetini ister ve orkestre edilen süreçler (RESPECTED_ORCH_DELEGATED) araç görmez, böylece özyinelemeli delegasyon olmaz. MCP üzerinden custom worker, command, apply_root ve engine_source reddedilir (--allow-auto-apply ile açılır). Özel seçenekler için ayrı --allow-privileged anahtarı vardır; acceptance/verify komutları roles.acceptance_allowed ile kullanıcının mcp_acceptance_allow önek listesine karşı denetlenir (varsayılan boş).

**İlişkiler ve sınır:** AI istemcileri integrations.py ile kaydedilen komutla başlatır; campaign, project, roles, runner ve context motor işlevlerini çağırır. tests/test_mcp_server.py ile test edilir.

#### [`src/respected_orchestrator/memory.py`](../src/respected_orchestrator/memory.py)

**Rol:** İsteğe bağlı SecondBrain bellek istemcisi.

**Amaç / sorumluluk:** SecondBrain'in salt-okunur RPP 'memory.recall' işlemi için isteğe bağlı, hata-yumuşak istemcidir. Grant token gizlidir: yalnızca data_root/memory-token içinde durur, çocuğun stdin'inden geçer ve çıktıdan üretilen mesajlardan temizlenir; dönen notlar güvenilmez veri olarak işaretlenir.

**İlişkiler ve sınır:** rpp.py ayarlarını ve runner/project bellek bağlamını besler; winproc ile süreç başlatır, token dosyasını runner._restrict_key ile kısıtlar. tests/test_memory.py ve tests/test_memory_integration.py ile test edilir.

#### [`src/respected_orchestrator/planner.py`](../src/respected_orchestrator/planner.py)

**Rol:** Planner rolü yürütücüsü.

**Amaç / sorumluluk:** 'planner' rolünü çalıştırılabilir yapar: atanan araç/model bir proje spesifikasyonu taslağı üretir, motor doğrular. Taslak asla başlatılmaz veya motorca düzenlenmez; planlayıcı ataması, kullanım ve doğrulama sonucuyla <data root>/drafts altına kaydedilir ve project-start ile insan/Master onayından sonra başlar.

**İlişkiler ve sınır:** mcp_server.py (orchestrator_plan) ve Hub tarafından çağrılır; roles, runner, processes ve antigravity_orchestrator'ı kullanır. tests/test_roles.py ve tests/test_project.py ile dolaylı kapsanır.

#### [`src/respected_orchestrator/processes.py`](../src/respected_orchestrator/processes.py)

**Rol:** Worker süreç yönetimi.

**Amaç / sorumluluk:** Windows suspended child/job ve POSIX process group ile deadline, cancel, process-tree temizliği ve çıktı akışı sağlar. complete_when/verify_complete ile doğrulanmış completion event'inde ağacı temizleyip ilerler; iptal geç completion'dan üstündür. scrub_environment anahtar/token/secret benzeri değişkenleri çocuğa geçirmez (RESPECTED_WORKER_ENV_ALLOW hariç), çocuğa RESPECTED_ORCH_CHILD=1 koyar ve izole test modunda Codex API çağrılarını reddeder.

**İlişkiler ve sınır:** runner, antigravity_orchestrator, campaign, project ve vertical_slice worker/acceptance/master süreçlerini buradan çalıştırır. tests/test_engine.py (tree cleanup, ortam sızıntısı) ve tests/test_codex_results.py dolaylı kapsar.

#### [`src/respected_orchestrator/project.py`](../src/respected_orchestrator/project.py)

**Rol:** Kalıcı otonom proje/faz supervisor'ı.

**Amaç / sorumluluk:** Tek seferlik yazılmış proje planını (bağımlı fazlar, workstream'ler, deterministik verify komutları, bütçe) imzalı project.json olarak saklar. Detached supervisor her fazı yeni motor snapshot'ı ve mirror ile campaign olarak çalıştırır; yalnız MASTER_APPROVED ve auto_apply ile önceden yetkilendirilmişse hep-ya-hiç apply eder, gerçek kaynakta verify çalıştırır. Sınırlı düzeltme denemesi, zaman/token bütçesi, iptal dosyası, pid'li tek-supervisor kilidi, resume ve isteğe bağlı final review sağlar. Faz verify komutları sandbox'tan ve temizlenmiş ortamdan (scrub_env, çocuk işareti) geçer.

**İlişkiler ve sınır:** campaign.create_campaign/run_campaign/_snapshot_engine, runner.apply_task ve processes.execute'u kullanır; __main__ project-* komutlarıyla bağlanır. tests/test_project.py kapsar.

### src/respected_orchestrator/resources

#### [`src/respected_orchestrator/resources/policy.json`](../src/respected_orchestrator/resources/policy.json)

**Rol:** Ürün varsayılanı.

**Amaç / sorumluluk:** Antigravity keşfi, single writer, read/write süreleri ve bypass=false varsayılanlarını sağlar.

**İlişkiler ve sınır:** Compatibility doctor/run okur; workspace bağımsız DataRoot'tadır.

### src/respected_orchestrator/resources/skills/kod-orkestrasyon

#### [`src/respected_orchestrator/resources/skills/kod-orkestrasyon/SKILL.md`](../src/respected_orchestrator/resources/skills/kod-orkestrasyon/SKILL.md)

**Rol:** Çıkarılmış skill.

**Amaç / sorumluluk:** Master/worker, explicit scope, bağımsız task/log/cancel/verify ve patch inceleme sözleşmesini Hub'a uyarlar. Claude Master kampanya döngüsünü (campaign-start/status, apply, allow_apply, MiMo yasağı) anlatır.

**İlişkiler ve sınır:** Eski vault/dashboard komutları kaldırıldı; global provider skill ayarı değiştirilmez.

### src/respected_orchestrator

#### [`src/respected_orchestrator/roles.py`](../src/respected_orchestrator/roles.py)

**Rol:** Vendor-bağımsız rol ataması.

**Amaç / sorumluluk:** Rolleri (implementer, reviewer, planner vb.) profil ve araçlarla eşler; hiçbir model bir role bağlanmaz. Öncelik: açık görev ataması > Hub varsayılanı > otomatik öneri (isteğe bağlı); açık atama sessizce değiştirilmez, kullanılamazsa kendi yedeği yoksa hata verir. Engelli profil listesi ve Hub ayar alanlarını da yönetir. Profil adı düz model adı karakter kümesiyle sınırlıdır (kabuk/argüman enjeksiyonunu önler). mcp_acceptance_allow ayarı (JSON komut önekleri listesi), doğrulaması ve acceptance_allowed denetimi eklendi.

**İlişkiler ve sınır:** planner, mcp_server, runner, project ve rpp tarafından kullanılır; track_record sıralama verisini kullanır. tests/test_roles.py ile test edilir.

#### [`src/respected_orchestrator/rpp.py`](../src/respected_orchestrator/rpp.py)

**Rol:** RPP v1.0/1.1 protokol girişi.

**Amaç / sorumluluk:** Respected Product Protocol: bir JSON istek alır, tek satır JSON yanıt döner. Hub ve testler için özel modüldür; daemon değildir ve ağ dinlemez. Her hata yapılandırılmış hata üçlüsü olarak döner, fırlatılmaz; yetenekleri, ayar şemasını ve lifecycle/memory/roles/runner işlemlerini yönlendirir.

**İlişkiler ve sınır:** Hub ve testler çağırır; lifecycle, memory, roles, runner, integrations ve context'i kullanır. tests/test_rpp.py ve tests/test_rpp_lifecycle.py ile test edilir.

#### [`src/respected_orchestrator/runner.py`](../src/respected_orchestrator/runner.py)

**Rol:** Tek görev worker yürütücüsü.

**Amaç / sorumluluk:** Create/start/list/inspect/cancel/check/retry ile imzalı yaşam döngüsünü; Codex brief/strict JSONL, scope, acceptance, freshness ve correction patch hash/scope doğrulamasını yürütür. Codex açık --sandbox workspace-write ve approval_policy=never ile çalışır, MiMo profilleri reddedilir, reviewer implementer'dan farklı olmalıdır, .engine-key Windows'ta mevcut kullanıcıya ACL'lenir. apply_task doğrulanmış (gerekirse insan onaylı) patch'i commit etmeden uygular; maf-approve yalnız etkileşimli operatör terminalinde, patch_sha256'ya bağlı ve değiştirilemez onay verir. Kabul komutları sandbox.wrap ile kısıtlı token'da çalışır (kurulamazsa sandbox_unavailable ile fail-closed), kabul öncesi worker'ın bıraktığı __pycache__/.pyc silinir (üretilen dosya sayısı yine raporlanır); Windows'ta .cmd/.bat worker kabukları kullanılamaz, görev metni Windows'ta 20000 karakterle sınırlıdır, bypass bayrağı kontrolü genişletildi, retry açık memory kararını korur, tester/coordinator rolleri ROLE_NOT_EXECUTABLE ile reddedilir.

**İlişkiler ve sınır:** context, processes ve antigravity_orchestrator katmanlarını kullanır; __main__, maf_workflow, campaign ve project tarafından çağrılır. tests/test_engine.py, tests/test_codex_results.py ve tests/test_maf_coding.py kapsar.

#### [`src/respected_orchestrator/sandbox.py`](../src/respected_orchestrator/sandbox.py)

**Rol:** Güvenilmeyen kod sınır katmanı.

**Amaç / sorumluluk:** Motorun kendi çalıştırdığı worker yazımı kodun (kabul ve verify komutları) yetkisini sınırlar: Windows'ta veri kökü başına rastgele bir SID üretir, veri kökünün (workspaces hariç) tüm çocuklarına ve .engine-key dosyasına bu SID için inheritable DENY ACE ekler, OWNER RIGHTS ACE ile sahibin örtük WRITE_DAC hakkını kaldırır ve komutu sandbox_exec üzerinden kısıtlı token ile çalıştıracak biçimde sarar (wrap). Sınır kurulamazsa SandboxError verir (fail-closed); RESPECTED_ORCH_SANDBOX=off yalnızca açık geliştirici anahtarıdır. Karar: docs/decisions/ACCEPTANCE_SANDBOX.md.

**İlişkiler ve sınır:** runner (kabul komutları) ve project (_verify) tarafından çağrılır; anahtar yolunu runner._key_path verir. sandbox_exec ile birlikte çalışır; PowerShell ACL kurulumunu winproc.run ile gizli pencerede yürütür. tests/test_sandbox.py gerçek saldırı denemeleri ve negatif kontrolle sınırı kanıtlar.

#### [`src/respected_orchestrator/sandbox_exec.py`](../src/respected_orchestrator/sandbox_exec.py)

**Rol:** Kısıtlı token ile komut çalıştırıcı.

**Amaç / sorumluluk:** python -m ... sandbox_exec --sid SID -- komut: çağıranın token'ından CreateRestrictedToken ile (kullanıcının tüm SID'leri + veri köküne ait ek SID kısıtlayıcı SID olarak, DISABLE_MAX_PRIVILEGE) yeni bir token üretir ve komutu CreateProcessAsUser ile çağıranın standart tutamaçlarıyla başlatır; çıkış kodunu döndürür. Çağıranın job nesnesi (süreç ağacı sonlandırma, zaman aşımı) çocuk için de geçerlidir. Yalnızca Windows.

**İlişkiler ve sınır:** sandbox.wrap tarafından komut öneki olarak eklenir; processes.execute bunu sıradan bir süreç gibi yönetir. tests/test_sandbox.py ile doğrulanır.

#### [`src/respected_orchestrator/track_record.py`](../src/respected_orchestrator/track_record.py)

**Rol:** Ölçülü araç/profil sicili.

**Amaç / sorumluluk:** (araç, profil) başına başarı, token ve süre sicilini bu kurulumun imzalı run kanıtından okur. Yalnızca imzası doğrulanan kanıt sayılır; imzasız, kurcalanmış veya kısmi kayıt atlanır. Adayları yalnızca sıralar, asla elemez; geçmiş MIN_RUNS altındaysa kullanılabilir geçmiş yoktur.

**İlişkiler ve sınır:** runner._track_record ve roles otomatik atama tarafından çağrılır; runner._load ve EngineContext kullanır. tests/test_roles.py ve tests/test_reviewer_reliability.py ile kapsanır.

#### [`src/respected_orchestrator/vertical_slice.py`](../src/respected_orchestrator/vertical_slice.py)

**Rol:** Autonomous vertical slice.

**Amaç / sorumluluk:** Codex çağrı adaptörünü (run_codex_call, CodexOutcome, diagnose) ve GLM master planı + paralel Codex worker + bounded correction + deterministik test + final gate dikey dilimini sağlar. turn.completed'da beklemeden ilerler; stream_verified_complete turn.failed görülen akışı başarıya çevirmez; diagnose yapılandırılmış JSONL kanıtını stderr regex'inden üstün tutar ve confidence raporlar. MiMo profilleri reddedilir, reviewer süreçleri scrub_env ile çalışır.

**İlişkiler ve sınır:** processes.execute ve context'i kullanır; maf_workflow ve runner Codex çağrıları için buradan yararlanır. tests/test_codex_results.py ve tests/test_maf_coding.py dolaylı kapsar.

#### [`src/respected_orchestrator/winproc.py`](../src/respected_orchestrator/winproc.py)

**Rol:** Windows süreç başlatma yardımcısı.

**Amaç / sorumluluk:** Windows'ta çocuk süreçleri konsol penceresi açmadan başlatır; ayrık supervisor'ların git/python/icacls çağrıları görünür pencere açmasın diye bayraklar tek yerde tutulur. Çıktı, hata, çıkış kodu ve zaman aşımı davranışı değişmez; Windows dışında boş seçenek döner.

**İlişkiler ve sınır:** Paketteki süreç başlatan modüller (memory, runner, processes vb.) tarafından kullanılır. tests/test_windows_processes.py ile test edilir.

### tests

#### [`tests/__init__.py`](../tests/__init__.py)

**Rol:** Test paketi izolasyon işareti.

**Amaç / sorumluluk:** RESPECTED_ORCH_TEST_ISOLATION=1 koyarak testlerde gerçek Codex API çağrılarını izole eder ve test sürecinin devraldığı RESPECTED_ORCH_CHILD işaretini temizler.

**İlişkiler ve sınır:** tests paketini içe aktaran unittest süreçlerini etkiler; processes.execute guard'ı bu işareti okur.

#### [`tests/conftest.py`](../tests/conftest.py)

**Rol:** pytest izolasyon işareti.

**Amaç / sorumluluk:** pytest keşfi sırasında Codex API çağrılarının açıkça izole olduğunu işaretler.

**İlişkiler ve sınır:** pytest test süreçlerini etkiler; processes execute guard'ı bu işareti okur.

#### [`tests/test_antigravity.py`](../tests/test_antigravity.py)

**Rol:** Korunmuş regresyonlar.

**Amaç / sorumluluk:** 26 Antigravity testini independent context, bypass=false ve raw-apply reddiyle uyarlayıp lane/scope/patch sözleşmesini sınar. Ölü sahipli yazar kilidinin geri alındığı durum test edilir.

**İlişkiler ve sınır:** Temporary Git/fake worker kullanır; Brain veya canlı provider ayarı gerekmez.

#### [`tests/test_campaign.py`](../tests/test_campaign.py)

**Rol:** Kampanya testleri.

**Amaç / sorumluluk:** Sahte worker'larla gerçek eşzamanlılık, bağımlılık/atlama, tek seferlik final master, non-Git mirror + apply, geçersiz spec, allow_apply daraltması, engine snapshot ve final prompt içeriğini doğrular.

**İlişkiler ve sınır:** src/respected_orchestrator/campaign.py ve runner.apply_task'ı sınar; tests/test_project.py aynı fixture yaklaşımını paylaşır.

#### [`tests/test_codex_results.py`](../tests/test_codex_results.py)

**Rol:** Model çağırmayan Codex failure regresyonu.

**Amaç / sorumluluk:** Sıfır exit'te açık failure, provider hata sınıflandırması, metadata uyarısı, eksik/başarısız stream reddi, reconnect bildirimi, blocked worker'ın imzalı failure state'i ve Windows proje-local Codex CLI tercihini doğrular.

**İlişkiler ve sınır:** runner ve antigravity_orchestrator kodunu geçici teknik veriyle çalıştırır; Git ve worker alt süreci taklit edilir, canlı model çağrılmaz.

#### [`tests/test_completion_deadlines.py`](../tests/test_completion_deadlines.py)

**Rol:** Completion/deadline testleri.

**Amaç / sorumluluk:** Gerçek yerel alt süreçlerle temsili Codex JSONL akışlarını (completion+hang, crash, turn.failed, reconnect, sessiz, aktif, stall, stderr disconnect) tekrarlar; verified completion'ın beklemeden ilerlemesini, başarısız/belirsiz sürecin asla başarı olmamasını, iptalin üstünlüğünü, tanı belirsizliğini ve deadline politikası doğrulamasını sınar.

**İlişkiler ve sınır:** processes.execute, vertical_slice completion/cause yardımcıları, maf_workflow review_timeout_default ve runner._workflow ile model çağrısı olmadan çalışır.

#### [`tests/test_engine.py`](../tests/test_engine.py)

**Rol:** Engine acceptance testleri.

**Amaç / sorumluluk:** Geçici projelerde izolasyon, scope/stale/tamper/retry sınırı, Codex JSONL failure ve final-result, Unicode brief, Windows cancel/crash/process-tree temizliği, ortam sızıntısı temizliği, engine-key ACL, sandbox/MiMo/reviewer kuralları, apply_task ve private JSON giriş davranışlarını doğrular.

**İlişkiler ve sınır:** runner, processes ve __main__ gerçek disposable Git projelerinde çalışır; Codex CLI sınırı model çağrısı olmadan taklit edilir.

#### [`tests/test_generated_artifacts.py`](../tests/test_generated_artifacts.py)

**Rol:** Üretilmiş artefakt testleri.

**Amaç / sorumluluk:** Gerçek git depolarında collect_worker_changes ve export_worker_patch'in üretilmiş çıktıyı (build, egg-info, bytecode) kaynak değişiklikten ayırdığını, takip edilen veya sahiplikle adı geçen yolları gerçek sayıp symlink kaçışı, entegrasyon çakışması ve scope ihlalini kapalı-başarısız bıraktığını doğrular.

**İlişkiler ve sınır:** antigravity_orchestrator ve runner (create_task, execute_task, check_result) uçtan uca kullanılır. Kayıt: A3_A4_ENGINE.md.

#### [`tests/test_integrations.py`](../tests/test_integrations.py)

**Rol:** Entegrasyon (client config) testleri.

**Amaç / sorumluluk:** integrations modülünün istemci yapılandırmasına eklediği girdiyi doğrular: yabancı içerik korunur, apply idempotent ve onaylı digest ister, düzenlenmiş/yabancı girdi ve geçersiz config yazılmadan reddedilir, rollback yalnız bizim girdimizi geri alır. Okunamayan bir istemci yapılandırmasının diğerlerini engellemediği test edilir.

**İlişkiler ve sınır:** integrations ve rpp modüllerini çağırır; RPP op'ları yalnız v1.1'de listelenir. RPP_V1_1.md lifecycle sözleşmesiyle uyumludur.

#### [`tests/test_maf_coding.py`](../tests/test_maf_coding.py)

**Rol:** MAF coding testleri.

**Amaç / sorumluluk:** Fake worker/reviewer ile MAF adapterinin completed/failed, checkpoint replay, fresh-run correction ve patch devralma, escalation, sınırlı retry, deep review, reviewer timeout/geçersiz çıktı, token ve bütçe muhasebesi, insan onayı (tahrif, çapraz-run, operatör-yalnız reddi) ve private JSON yönlendirmesini doğrular.

**İlişkiler ve sınır:** maf_workflow, runner create/execute/check/approve ve __main__ maf/maf-approve sözleşmelerini geçici Git fixture'larıyla canlı model çağrısı olmadan sınar.

#### [`tests/test_maf_coding_demo.py`](../tests/test_maf_coding_demo.py)

**Rol:** Model ve Git çağırmayan demo kabul regresyonu.

**Amaç / sorumluluk:** Demo named MiMo profile argv ve gerçek temporary Python acceptance sonucunun ownership dışında bytecode üretmediğini doğrular.

**İlişkiler ve sınır:** demo preflight/Git/AI sınırları taklit edilir; acceptance gerçek child Python ile -B kullanır.

#### [`tests/test_maf_workflow.py`](../tests/test_maf_workflow.py)

**Rol:** MAF workflow tests.

**Amaç / sorumluluk:** Iki fake worker es zamirligi, bounded correction, rejection, invalid/failed reviewer output ve checkpoint resume davranislarini dogrular.

**İlişkiler ve sınır:** maf_workflow adaptörünün karar durumlarını canlı model çağrısı olmadan sınar.

#### [`tests/test_mcp_server.py`](../tests/test_mcp_server.py)

**Rol:** MCP sunucu testleri.

**Amaç / sorumluluk:** mcp_server araç listesini, orkestre edilen süreçte araçların gizlenmesini (özyineleme koruması), apply için doğrulanmış digest ve kimlik doğrulamasını, varsayılan auto_apply reddini, hafıza notunun yazma izni olmadan kapalı olmasını ve stdio gidiş-dönüşünü doğrular. MCP'de ayrıcalıklı görev seçenekleri ve bypass bayrağı varyantlarının reddi test edilir. MCP'de acceptance/verify komutlarının kullanıcı listesi olmadan reddi, önek eşleşmesi, ayrı --allow-privileged anahtarı ve auto_apply onayının özel seçenekleri açmadığı test edilir.

**İlişkiler ve sınır:** mcp_server ve runner'ı çağırır. Kayıt: docs/records/2026-10-15-mcp-access.md.

#### [`tests/test_memory.py`](../tests/test_memory.py)

**Rol:** Hafıza istemcisi testleri.

**Amaç / sorumluluk:** memory modülünün RPP çağrısını doğrular: sonuç ve hata eşlemeleri, zaman aşımı, başlatma hatası, child çıktısında token temizliği, token dosyası gidiş-dönüşü ve boşken kısıtlama, geçersiz token reddi, komut/ayar doğrulaması, sorgu üretimi ve bağlam bloğu.

**İlişkiler ve sınır:** memory modülünü çağırır; token yalnızca stdin ve 0600/ACL dosyasında kalır. Karar: docs/decisions/MEMORY_INTEGRATION.md.

#### [`tests/test_memory_integration.py`](../tests/test_memory_integration.py)

**Rol:** Hafıza entegrasyon testleri.

**Amaç / sorumluluk:** Hafızanın runner, kampanya ve RPP ayarlarıyla bütünleşmesini doğrular: yazma izni ayrıdır ve token sızmaz, token yazma-yalnızdır, memory.use politika matrisi, brief ve kanıt temizliği, hata veya devre dışı durumunda görevin normal çalışması, lane'de main_root kullanımı.

**İlişkiler ve sınır:** memory, campaign, rpp ve runner kullanır. Karar: docs/decisions/MEMORY_INTEGRATION.md.

#### [`tests/test_project.py`](../tests/test_project.py)

**Rol:** Otonom proje testleri.

**Amaç / sorumluluk:** Sahte worker'larla bağımlı fazların yeni prompt olmadan bitmesini, sınırlı yeniden deneme sonrası blocked'ı, auto_apply yetkisizken kaynağa dokunulmamasını, kilit/iptal/zaman bütçesini, çöken supervisor'ın çift campaign olmadan resume'unu, geçersiz spec reddini ve final review girdisini doğrular.

**İlişkiler ve sınır:** src/respected_orchestrator/project.py'yi sınar; tests/test_campaign.py ile fixture yaklaşımını paylaşır.

#### [`tests/test_project_adversarial.py`](../tests/test_project_adversarial.py)

**Rol:** Proje adversarial testleri.

**Amaç / sorumluluk:** project.py için kötü niyetli ve çökme senaryolarını doğrular: apply sonrası çökmede ikinci apply olmaması, çakışmada engelleme, ProcessStopped sınırlı deneme, iptal, bütçe, kalıcı deadline ve bozuk kilit, bozuk spec için ValueError, reddedilen lane'in sınırlı yeniden denenmesi.

**İlişkiler ve sınır:** project, campaign, maf_workflow ve runner'ı kullanır. Karar: docs/decisions/PROJECT_SUPERVISOR_REVIEW.md.

#### [`tests/test_project_recovery.py`](../tests/test_project_recovery.py)

**Rol:** Proje kurtarma testleri.

**Amaç / sorumluluk:** Proje supervisor'ının kurtarma davranışını doğrular: başarısız denemede token kaydı, kullanımı raporlanmayan lane'de kapalı-başarısız engelleme, bağımlı lane'in uygulanmış çıktıyı görmesi, yalnız başarısız lane'lerin düzeltmesi, kill sonrası çift kampanya/apply olmaması ve imzalı durumdan hata nedeni.

**İlişkiler ve sınır:** project, campaign, maf_workflow ve runner'ı kullanır. Kayıt: LANE_SUMMARY_REVIEW.md ve A3_A4_ENGINE.md.

#### [`tests/test_reviewer_reliability.py`](../tests/test_reviewer_reliability.py)

**Rol:** Reviewer güvenilirliği testleri.

**Amaç / sorumluluk:** Review hata teşhisini (zararsız modeller-yenileme satırı), sağlayıcıya duyarlı zaman aşımlarını, sınırlı yeniden denemeyi, yalnız review yeniden çalıştırmada worker'ın tekrar çalışmaması ve token geçmişinin korunmasını, tahrif edilmiş veya değişmiş proje patch'inin yeniden kullanılmamasını doğrular.

**İlişkiler ve sınır:** maf_workflow, vertical_slice, project, campaign ve runner'ı kullanır; modeller sahte çağrılarla taklit edilir. Kayıt: A1_A2_RELIABILITY.md.

#### [`tests/test_roles.py`](../tests/test_roles.py)

**Rol:** Rol ataması testleri.

**Amaç / sorumluluk:** roles çözümlemesini (açık atama > Hub varsayılanı > otomatik, sessiz atama yok), engelli profillerin ayar olmasını, komut üretimini ve kullanımın hiç sıfır sayılmamasını, review prompt sınırını, master rolünü ve planner'ın doğrulanmış spec üretip başlatmamasını doğrular. Görevde çalıştırılamayan rollerin (tester/coordinator) reddi test edilir.

**İlişkiler ve sınır:** roles, maf_workflow ve runner (create_task, inspect_task) kullanılır. Karar: docs/decisions/ROLE_ASSIGNMENT.md.

#### [`tests/test_rpp.py`](../tests/test_rpp.py)

**Rol:** RPP testleri.

**Amaç / sorumluluk:** rpp.py'nin v1.0 ve v1.1 davranışını doğrular: her yanıtta tüm anahtarlar, bilinmeyen op, sürüm uzlaşması ve sınırları, operation_id şekli, çöp girdide istisna olmaması, manifest, health, ayar şeması, apply idempotansı ve çakışması, secret maskeleme ve receipt okuma. Ayar şemasının mcp_acceptance_allow alanını da içerdiği doğrulanır.

**İlişkiler ve sınır:** rpp ve EngineContext çağrılır. Karar: docs/decisions/RPP_V1.md ve RPP_V1_1.md.

#### [`tests/test_rpp_lifecycle.py`](../tests/test_rpp_lifecycle.py)

**Rol:** RPP lifecycle testleri.

**Amaç / sorumluluk:** lifecycle op'larını doğrular: plan salt okunurdur, apply dosya ve receipt yazar, operation_id başına idempotenttir, çakışma, çökme journal'ından devam, uninstall yalnız sahip olunan dosyaları siler, rollback önceki içeriği geri verir, güvensiz yol reddedilir.

**İlişkiler ve sınır:** rpp ve lifecycle modüllerini çağırır. Karar: docs/decisions/RPP_V1_1.md; durum: RPP_V11_STATUS.md.

#### [`tests/test_sandbox.py`](../tests/test_sandbox.py)

**Rol:** Çalışan kod sınırı saldırı testleri.

**Amaç / sorumluluk:** Kısıtlı token sınırını düşmanca denemelerle kanıtlar: anahtarı (düz yol, uzun yol öneki, junction, hardlink) okuma, ayar/kanıt okuma, onay sahteciliği, kanıt üzerine yazma/silme, veri kökünde dosya yaratma, anahtar ACL'sini yeniden yazma, deny ACE'i kaldırma, sahiplik alma reddedilir; worktree ve alt süreç çalışır. Aynı sonda sandbox olmadan çalıştırılınca saldırıların başarılı olduğunu gösteren negatif kontrol ve idempotent kurulum testi içerir.

**İlişkiler ve sınır:** sandbox, sandbox_exec ve runner._signature ile gerçek Windows ACL'leri üzerinde çalışır (yalnızca Windows).

#### [`tests/test_test_isolation.py`](../tests/test_test_isolation.py)

**Rol:** Test izolasyon regresyonları.

**Amaç / sorumluluk:** Test işaretinin aktif olduğunu, izole testlerde Codex CLI çağrısının engellendiğini ve yerel Python acceptance komutlarının çalışmaya devam ettiğini doğrular.

**İlişkiler ve sınır:** tests paket işareti ve processes execute guard sözleşmesini sınar; canlı provider çağrısı yapmaz.

#### [`tests/test_token_budget.py`](../tests/test_token_budget.py)

**Rol:** Token bütçesi testleri.

**Amaç / sorumluluk:** budget modülünü ve lane/proje bütçelerini doğrular: ücretli adım öncesi denetim, UNKNOWN kullanımın açık raporu ve ücretlendirmesi, yeniden denemenin bütçeyi sıfırlamaması, bütçe aşımında hiçbir şeyin onaylanmaması ve imzalı geçmişin yeniden yazılmaması, geçersiz bütçe ayarlarının reddi.

**İlişkiler ve sınır:** budget, campaign, project, runner ve maf_workflow kullanır. Kayıt: A3_A4_ENGINE.md.

#### [`tests/test_vertical_slice.py`](../tests/test_vertical_slice.py)

**Rol:** Vertical slice testleri.

**Amaç / sorumluluk:** Usage ayrımı, paralel worker ve zero-poll ile tek turlu correction/second Master approval geçişlerini sahte Codex çağrılarıyla sınar.

**İlişkiler ve sınır:** vertical_slice davranışını canlı model olmadan doğrular; canlı EVREN/GPT demo state ayrı tutulur.

#### [`tests/test_windows_processes.py`](../tests/test_windows_processes.py)

**Rol:** Windows süreç yönetimi testleri.

**Amaç / sorumluluk:** Hiçbir modülün gizli pencere yardımcısı olmadan süreç başlatmadığını, ayrık süpervizör ve çocuklarının görünür konsol açmadığını, zaman aşımı ve iptalde tüm süreç ağacının öldürüldüğünü, yetim süreçlerin temizlendiğini ve eksik yürütülebilirin sızıntısız raporlandığını doğrular.

**İlişkiler ve sınır:** winproc, processes ve antigravity_orchestrator'ı kullanır. Kayıt: A1_A2_RELIABILITY.md konsol penceresi sızıntısı düzeltmesi.

#### [`tests/test_worker_environment.py`](../tests/test_worker_environment.py)

**Rol:** Ücretsiz Windows ortam ve preflight regresyonları.

**Amaç / sorumluluk:** Child PSModulePath casing/parent korumasını, mevcut auth helper/config no-write davranışını ve bozuk marker durumunda auth/Git/AI öncesi durmayı doğrular.

**İlişkiler ve sınır:** processes.execute gerçek temporary Python child çalıştırır; demo auth sınırı taklit edilir; sandbox marker yalnız temporary fixture içinde yazılır, gerçek Codex/runtime çalıştırılmaz.

#### [`tests/test_worker_status_contract.py`](../tests/test_worker_status_contract.py)

**Rol:** test.

**Amaç / sorumluluk:** render_brief çıktısının makine-okunur status sözleşmesini, apply_patch yasağını ve final JSON talimatını doğrular.

**İlişkiler ve sınır:** antigravity_orchestrator.render_brief ile temporary template dizinlerini kullanır; worker çalıştırmaz.

### tools

#### [`tools/repository_map.py`](../tools/repository_map.py)

**Rol:** Atlas geliştirici aracı.

**Amaç / sorumluluk:** Bağımsız ürün adıyla metadata/hash denetimi ve no-Git filesystem keşfi sağlar.

**İlişkiler ve sınır:** Brain aracının bağımsız kopyasıdır; dış repo importu yoktur, normal Git CI modu korunur.

#### [`tools/run_maf_coding_demo.py`](../tools/run_maf_coding_demo.py)

**Rol:** Sınırlı canlı MAF coding demo.

**Amaç / sorumluluk:** Tek MiMo/evren1 worker için CLI çözer; Windows mevcut marker/auth preflight ile erken durur; disposable Git fixture ve bytecode üretmeyen acceptance çalıştırır.

**İlişkiler ve sınır:** maf_workflow/runner/processes fail-closed kapılarını kullanır; mevcut named profile/home korunur ve explicit config yazılmaz; Codex provisioning yan etkileri evidence kaydında ayrı risk olarak belirtilir. test_maf_coding_demo argv/acceptance; test_worker_environment auth/marker/child ortamını model çağırmadan doğrular.

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
