# Orchestrator mimarisi

Motorun nasıl paketlendiği, bir görevin nasıl doğrulandığı, hangi güvenlik sınırlarının uygulandığı ve hangi kuralların
bağlayıcı olduğu. Giriş ve komutlar: [README.md](../README.md). Üç ürünün ortak kuralları (kurucu, komutlar, ayarlar,
protokol) [PRODUCT_CONTRACT.md](PRODUCT_CONTRACT.md) dosyasındadır; burada tekrarlanmaz.

## 1. Paketlenmiş motor

- `packaging/build_dist.py` motoru PyInstaller ile (onedir, içerik `app/` altında) `dist/RespectedOrchestrator/` klasörüne
  dondurur: `respected-orchestrator.exe` ve her dosyanın SHA-256'sını taşıyan `distribution.json`. Agent Framework'ün tembel
  alt modülleri toplanır; bildirilen bağımlılıkların dışındaki kurulu paketler dışarıda bırakılır, böylece yerel derleme
  temiz bir CI derlemesiyle aynı içeriği taşır. `_selfcheck` her modülü içe aktarır ve eksik olanda başarısız olur.
- Kurucu (`packaging/windows/orchestrator_setup.iss`) programı `app\` altına yazar ve `setup` çalıştırır; `setup` dosyaları
  `distribution.json` ile doğrulayıp kurulumu `app\.respected\install.json` olarak kaydeder. `manifest`'in `install_state`
  değeri bu kayıttan ve dosyaların şimdiki hash'inden gelir; Hub ve ürün "kurulu" ile "onarım gerekli" konusunda aynı şeyi
  söyler.
- Motor kendini her zaman `context.engine_command` ile yeniden başlatır: donmuşsa exe, kaynaktan
  `python -m respected_orchestrator`. Ayrık görev, proje ve kampanya denetleyicileri ve kısıtlı belirteçli doğrulama
  başlatıcısı (`_sandbox-exec`) bu yoldan geçer. Her alt süreç `engine/winproc` üzerinden açılır.
- `--data-root` yalnızca motorun kendi alt süreçleri içindir (her kampanya hattının kendi kökü vardır); yardımda görünmez.
  Kişiler ve testler `RESPECTED_DATA_DIR` kullanır.

## 2. Görev ve sonuç denetimi

- Her görev projenin yalıtılmış bir Git çalışma ağacında çalışır. Sonuç bir iddiadır: kapsam (`ownership` / `forbidden`),
  doğrulama komutları, yamanın projeye hâlâ uyması, imzalı kanıt ve projenin güncelliği ayrı ayrı geçmelidir. Hiçbir şey
  kendiliğinden uygulanmaz; `apply` `check`'i yeniden çalıştırır, `git apply --check` yapar, commit atmaz ve çalışan
  süreçlerin içinden reddedilir. Yeniden denemeler açık ve sınırlıdır; süre sınırları ve süreç ağacı temizliği korunur.
- **Worker sınırı (SEC-03):** Bütün worker girişleri (`create`, `start`, MAF araç çağrıları ve kampanya alt şeritleri) tek
  `engine/worker_policy.py` politikasından ve `engine/appcontainer.py` başlatıcısından geçer. Politika kurulamaz, komut
  allowlist dışındaysa ya da AppContainer açılamazsa **hiçbir worker başlamaz**; görev `failed` / `sandbox_unavailable`
  olur. Sessiz, sandbox'sız geri dönüş yoktur.
- Varsayılan olarak yalnızca worker'ın kendi worktree'si yazılabilir; Python/araç dizini salt-okunur; ağ kapalıdır
  (`internetClient` yeteneği verilmez). `.cmd`/`.bat` şimleri reddedilir, sır adları ortamdan çıkarılır ve `TEMP`/`TMP`
  worker alanına yönlendirilir. Codex incelemesinde proje `cwd`'si salt-okunur, inceleme çalışma kökü yazılabilirdir.
  Motor, supervisor ve kampanya final master'ı güvenilen süreçler olarak sandbox dışında kalır.
- AppContainer profili her çalıştırmada oluşturulup kapatılır; izinler yalnızca worktree ve araç dizinine verilir ve kapanışta
  geri alınır. `sys.prefix` altındaki Python dosyaları için makine genelinde `ALL APPLICATION PACKAGES` salt-okunur
  paylaşımı kullanılır; bu grant kullanıcı profilini veya motor veri kökünü kapsamaz.
- Kanıt: `tests/engine/test_worker_policy.py` (18 test) politika doğrulamasını, worker ve MAF inceleme yollarının
  fail-closed başlatmasını, dış okuma/yazma reddini, `.engine-key` erişimsizliğini, varsayılan ağ reddini, alt süreç
  mirasını, timeout sonrası çocuk süreç temizliğini ve sentinel sır sızmamasını ölçer. `tests/workflows/test_campaign.py`
  kampanya şeridinin worktree dışına okuyup yazamadığını ve alt şeridin worker'ı doğrudan değil `engine maf` üzerinden
  çalıştırdığını ayrıca doğrular.
- **Worker güvenlik matrisi (SEC-04):** `tests/engine/security_cases.py` tek bir saldırı kaydıdır: 21 negatif vaka
  (19 worker içi + 2 dış: `symlink_patch`, `recursive_mcp`) ve 9 izinli vaka. Gerçek AppContainer yolu kaynakta
  `tests/engine/test_worker_security.py`, paketlenmiş exe'de `tests/packaging/test_frozen_security.py` ile aynı kaydı
  çalıştırır. `tests/engine/test_security_gate.py`; kayıt küçülmesini, zorunlu kategori kaybını ve CI adımının
  kaldırılmasını test düşürerek engeller.
- **Yama türü fail-closed (SEC-04):** Git indeksindeki `120000` (symlink) ve `160000` (gitlink/submodule) yolları
  `unsafe_paths` içine alınır; kapsam ihlali sayılır, `export_worker_patch` yama üretmeden reddeder ve
  `check_patch_against_master` bu modları taşıyan yamayı `INTEGRATION_CONFLICT` olarak reddeder. Windows symlink
  ayrıcalığı olmayan worker'ın `git update-index` ile `120000` hazırlayıp normal dosyayla maskelemesi de reddedilir.
- **CI güvenlik sınırları:** `.github/workflows/ci.yml` worker AppContainer matrisini, verify/acceptance sandbox
  matrisini, güvenlik kayıt kapısını ve frozen exe matrisini ayrı zorunlu adımlar olarak çalıştırır; tam keşif adımı
  korunur. `continue-on-error` yoktur; bu adımlardan biri düştüğünde iş düşer.
- **Kalan sınır:** AppContainer Windows'a özgüdür; Windows dışında worker başlatılmaz (REL-04 platform kararı). Yükseltilmiş
  veya doğrulanamayan oturumda motor fail-closed davranır ve worker başlatmaz (`unsupported_elevated`). İzin verilen araç dizinindeki çalıştırılabilirler ayrıca
  allowlist'e eklenmelidir; varsayılan politika yalnızca seçilen yorumlayıcıyı ve `sys.prefix`'i açar.
- **Hata sınıfları (ADR-005):** terminal görev kaydı ve MAF sonucu `failure_class`, `retryable` ve `retry_policy`
  alanlarını taşır. Sınıflar `test_failure`, `policy_denied`, `timeout`, `quota`, `auth`, `infrastructure`, `stale_patch`,
  `reviewer_reject` ile kapalıdır. `timeout` ve `infrastructure` sınırlı retry; `test_failure` ve `NEEDS_CHANGES` yalnızca
  `max_fix_rounds` (varsayılan 2, üst sınır 5) kadar kanıta dayalı düzeltme alır; `stale_patch` yeni yama; `auth`, `quota`,
  `policy_denied` ve nihai `REJECTED` insan müdahalesi gerektirir. `retry_task`, `retryable=false` kayıtları ve mevcut üç
  deneme sınırını aşan istekleri reddeder.
- **MAF sonlu durum makinesi (QUA-03):** implement → tester → bağımsız reviewer → sınırlı fix → yeniden doğrulama akışı
  `max_fix_rounds` ile sınırlıdır. `NEEDS_CHANGES` ara durumdur; terminal durumlar `MASTER_APPROVED`,
  `HUMAN_APPROVAL_REQUIRED`, `REJECTED`, `CANCELLED`, `STALE_PATCH`, `REPEATED_TEST_FAILURE` ve `FIX_ROUNDS_EXHAUSTED`
  olarak kapalıdır. Fix'e yalnızca imzalı kanıttan türetilen `run_id`, `checks`, `reason`, `failure_class` ve
  `evidence_paths` alanları verilir; ham stdout/stderr aktarılmaz. Aynı normalize test hatası ikinci kez görülürse reviewer
  çağrılmadan `REPEATED_TEST_FAILURE` ile durulur; hiçbir otomatik fix proje çalışma ağacına uygulanmaz.
- **Bağımsız review/apply değişmezleri (QUA-04):** bağımsızlık istendiğinde reviewer ile implementer aynı profil/araç
  olamaz. `check_result` sonucu HMAC imzası, kabul ve tester kanıtı, MAF kapısı, onayın çalıştırma ve `patch_sha256`
  bağlantısı, güncel proje parmak izi ve `git apply --check` ile doğrular. İnsan onayı istenen MAF sonucu onay dosyası
  olmadan; onay ise başka bir patch'e bağlanarak kullanılamaz. `apply_task` önceki doğrulamayı yeniden çalıştırır,
  yarışta değişen kaynağı uygulamaz, ikinci kez uygulamaz, commit veya otomatik merge yapmaz. Tester yalnızca görevin
  kabul komutları hakkında imzalı rapor üretir; tester tarafından verilen serbest komut `BAD_ASSIGNMENT` ile reddedilir.
  `tests/engine/test_review_apply_invariants.py` 12 saldırgan senaryonun 12/12 reddini, sıfır otomatik apply'ı ve meşru
  check→apply akışının 1/1 sürmesini kanıtlar.
- Bir veri kökünde aynı anda tek görev çalışır: sonradan başlatılan görev kendi süresi içinde sıraya girer (süre dolarsa
  `timed_out`, iptal edilirse `cancelled`); bozuk ya da yarım yazılmış kilit dosyası 5 saniyeden eskiyse bayat sayılıp alınır.
- Kanıt, veri kökündeki `.engine-key` ile HMAC imzalanır. Anahtar Windows'ta yalnızca kullanıcıya açık bir ACL ile korunur.
- **Codex sonucu:** yerleşik Codex uyarlayıcısı `exec --json` ile çalışır ve tam görev metnini tek argüman olarak verir
  (`--json` ile çağrılan `codex` adlı özel komutlar da aynı sözleşmeye tabidir). Çıktı yalnızca JSON nesnelerinden oluşan,
  `turn.completed` ile biten, `turn.failed` ya da `error` olayı içermeyen JSONL olmalıdır; son ajan mesajında açıkça başarılı
  bir `status` taşıyan bir JSON nesnesi bulunmalıdır. Yorum, engellenmiş yanıt, bozuk çıktı ya da eksik son olay, araç 0 ile
  çıksa bile doğrulamaya ilerlemez. Açık başarısızlık `WORKER_FAILED`; kota ve kimlik hataları kendi sınıflarını korur; zaman
  aşımı önceliklidir. Windows'ta projede `.runtime/codex-0.162.0-alpha.20/bin/codex.exe` varsa o tercih edilir, yoksa PATH.
  Motor ortak bir Codex kum havuzu kurmaz ya da onarmaz.
- Codex çalışanları `--sandbox workspace-write` ve `approval_policy="never"` ile başlar; kişinin `danger-full-access`
  ayarı devralınmaz. Çalışan, denetim ve gözden geçirme ortamlarından sır gibi görünen değişkenler çıkarılır
  (`RESPECTED_WORKER_ENV_ALLOW` ad başına açık istisnadır). İzin atlayan bayraklar (`--dangerously*`, `--yolo`,
  `bypassPermissions`, `danger-full-access`, `-y`, `--approval-mode yolo`, `sandbox_mode` geçersiz kılma) her yerde
  reddedilir.
- **OpenCode sonucu ve ACP:** OpenCode çalışanı gerçek `opencode acp` stdio oturumuyla çalışır; oturum kimliği, model
  seçimi ve dönüş sınırı Agent Client Protocol (ACP) üzerinden izlenir. Son ajan mesajı fail-closed ayrıştırılır:
  çıplak bir JSON nesnesi ya da fence dışında yalnızca açıklama metni bulunan **tek** bir ```json/``` bloğu kabul
  edilir. Fence dışındaki serbest metinden JSON çıkarılmaz; çoklu ya da yarım fence, JSON dizisi, bozuk JSON ve
  geçersiz `status` reddedilir (`WORKER_FAILED`). Açık kimlik hatası `AUTH_REQUIRED`, kota `LIMIT_EXHAUSTED`, zaman
  aşımı `TIMEOUT` olarak sınıflanır; zaman aşımı önceliklidir.
- OpenCode alt süreci proje yapılandırmasını okumaz (`OPENCODE_DISABLE_PROJECT_CONFIG=1`) ve izole bir HOME ile
  çalışır: `APPDATA`, `LOCALAPPDATA` ve kullanıcı yapılandırması görev scratch kökünde tutulur. Kimlik bilgisi ana
  kullanıcı deposundan `auth export --standalone` ile alınıp yalnızca çalışanın izole HOME'una
  `auth import --standalone` ile aktarılır; sır kanıt, log ve görev metnine yazılmaz. OpenCode ağ erişimi varsayılan
  kapalıdır; yalnızca `RESPECTED_OPENCODE_NETWORK=allow` ile açılır.
- **Sağlayıcı ağ kapısı (ADR-007):** Kendi API sağlayıcı adaptörleri (ADP-03) ağ varsayılan kapalıyken çalışmaz.
  `engine/provider_policy.py` soket açmadan önce `RESPECTED_PROVIDER_NETWORK=allow` ve
  `RESPECTED_PROVIDER_CODE_GATE=1` ister; yalnızca `https` ve açık allowlist'teki tam alan adına izin verir. Her
  redirect hedefi yeniden doğrulanır; proxy de allowlist'ten geçer. 401/429/5xx başka sağlayıcıya sessiz fallback
  yapmaz. Anahtar istek anında kasadan okunur, log/kanıt/ayar JSON'una yazılmaz ve `***set***` ile maskelenir.

## 3. Doğrulama kum havuzu

Doğrulama komutları (ve proje `verify` komutları) bir çalışanın yazdığı kod üzerinde çalışır. Bu kodun motorun yetkisini
taşımaması için komutlar `sandbox_exec` ile **kısıtlı bir belirteçle** (`CreateRestrictedToken` + `CreateProcessAsUser`)
çalışır:

- Belirteç kullanıcının bütün SID'lerini kısıtlayıcı SID olarak tutar (araçlar ve önbellekler aynı çalışır) ve bu veri
  köküne ait bir SID daha ekler (`sandbox.json`; hiçbir gerçek hesabın sahip olmadığı biçimli bir SID). Windows erişimi iki
  kez denetlediği için bu SID'e verilen **ret** kum havuzunu engeller, o SID'i taşımayan motoru etkilemez.
- `DISABLE_MAX_PRIVILEGE` yedekleme/geri yükleme/sahiplik alma ayrıcalıklarını kaldırır.
- Veri kökü bu SID'i bütün alt öğelerde (kalıtımlı), kökün kendisinde oluşturma/değiştirme/silme/ACL değiştirmede ve
  anahtar dosyasında reddeder. `workspaces/` (çalışanın alanı) kalıtımı keser ve kullanılabilir kalır.
- Bir **OWNER RIGHTS** girdisi sahibin örtük haklarını READ_CONTROL ile sınırlar; yoksa aynı kullanıcı WRITE_DAC'i korur ve
  kum havuzu erişimini geri verebilirdi (saldırı testiyle bulundu).
- Kurulamazsa çalışma `sandbox_unavailable` ile başarısız olur; sessiz geri dönüş yoktur. `RESPECTED_ORCH_SANDBOX=off`
  açık bir geliştirici anahtarıdır (Windows dışındaki tek yol).
- Kanıt (`tests/engine/test_sandbox.py`, negatif kontrolle): kum havuzundaki kod anahtarı okuyamaz (düz yol, `\\?\`,
  bağlantı noktası, sabit bağ), ayarları ve kanıtı okuyamaz, veri kökünde hiçbir şey oluşturamaz/değiştiremez/silemez,
  `maf-approval.json` sahteleyemez, ACL'yi ya da ret girdisini değiştiremez, sahiplik alamaz. Kum havuzu olmadan aynı
  denemelerin hepsi başarılı olur.
- Sınırlar: yalnızca motorun sırları ve kanıtı korunur; kod kişinin diğer dosyalarını okuyabilir ve ağa çıkabilir. Çalışan
  araçların (claude/codex/agy) kendisi bu belirteçle çalışmaz; kendi izin modları vardır. Yükseltilmiş yönetici olarak
  çalışan bir motor bu modelin dışındadır. Veri kökü başına ilk kullanımda bir PowerShell ACL kurulumu (yaklaşık bir
  saniye) yapılır.
- Tehdit modeli, varlık/yetki matrisi ve 25 saldırı senaryosu [THREAT_MODEL.md](THREAT_MODEL.md) dosyasındadır. Özet:
  bu kum havuzu yalnızca motorun çalıştırdığı doğrulama kodunu korur; worker için işletim sistemi düzeyinde dosya/ağ
  sınırı yoktur. Windows normal kullanıcı desteklenir; yükseltilmiş yönetici desteklenmez ve başlangıçta reddedilir.

## 4. Rol atama

Her uyumlu model, sağlayıcı ya da araç her role atanabilir; kod hiçbir zaman "X modeli yalnızca Y rolünü yapar"
demez. Kavramlar ayrıdır: **rol** (iş akışındaki görev, `^[a-z][a-z0-9_]{0,39}$`, açık küme: `implementer`, `reviewer`,
`deep_reviewer`, `planner`, `debugger`, `tester`, `coordinator`, `master`…), **profil** (motor için opak bir model
yapılandırması), **araç** (`codex`, `claude`, `gemini`, `agy`, `cursor`, `custom`) ve **atama** (`{tool, profile}` + kaynağı).

Her rol için öncelik:

1. **Açık atama** görev isteğinde: `roles: {rol: profil | {tool, profile, fallbacks}}` ya da `worker`, `worker_profile`,
   `workflow.reviewer_profile|reviewer_tool|deep_review_profile|deep_review_tool`. Aynı role iki farklı değer `ROLE_CONFLICT`.
2. **Ayarlardaki varsayılan:** `default_worker`, `default_worker_profile`, `default_reviewer_tool`,
   `default_reviewer_profile`, `default_roles`.
3. **Otomatik öneri**, yalnızca `auto_assign` açıksa, `auto_pool` adaylarından: yazma rolleri başsız düzenleyebilen bir
   araç ister; okuma rolleri `custom` kullanamaz; kullanılamayanlar gerekçesiyle `excluded`'da listelenir. Sıralama bu
   kurulumun kendi imzalı geçmişinden gelir (`track_record.py`): yumuşatılmış tamamlanma oranı, başka rolün kullanmadığı
   profil, daha düşük ortalama belirteç, havuz sırası. Her aday için 3'ten az kayıt varsa bu bir ölçüm değildir: ilk uygun
   aday alınır ve `basis: pool_order` olarak kaydedilir. Görev zorluğu ve fiyat modellenmez.

Belirtilmeyen `deep_reviewer` `reviewer`'dır. Çözülen atamalar ve kaynakları (`explicit` / `hub_default` / `auto`) imzalı
istekte `role_assignments` olarak saklanır.

- Açık seçim asla sessizce değiştirilmez: kullanılamayan atama `ROLE_UNAVAILABLE`'dır; yalnızca atamanın kendi
  `fallbacks` listesi devreye girer. Hiçbir kaynaktan atanmayan gerekli rol `ROLE_UNASSIGNED`; gözden geçirici, MAF
  akışının ücretli ilk adımından önce denetlenir.
- `require_independent_review` açıksa çalışanla aynı profili kullanan gözden geçirici `ROLE_INDEPENDENCE`'tır; kapalıysa
  izin verilir ve `role_notes`'a yazılır. `escalate_profile` sonraki düzeltmeleri başka profile verir, ilk çalışan gözden
  geçirici olur. `blocked_profiles` (varsayılan `mimo`) profilleri her rolde reddeder.
- Gözden geçirmeler atanan araçla yapılır: `codex` salt okunur kum havuzu yolunu kullanır; diğer araçlar boş bir kanıt
  klasöründe başsız çalışır. Bunların komut satırları belirteç kullanımı bildirmez; kullanım "bilinmiyor" kaydedilir
  (sıfır değil) ve hat bütçesinden varsayılan miktar düşülür.
- Tüketilen roller: `implementer`, `reviewer`, `deep_reviewer` (her görev), `debugger` (atandıysa düzeltme turları),
  `master` (kampanya/proje son incelemesi; açık `final.command` önceliklidir, ikisi birden `ROLE_CONFLICT`), `planner`
  (`plan` komutu: atanan araçla bir proje taslağı çıkarır, motorla doğrular, `drafts/`'a kaydeder, başlatmaz) ve `tester`.
  `plan` taslağı DAG doğrulamasından geçmeden kaydedilmez: her düğüm `id`, `depends_on`, `ownership`, `forbidden`,
  `acceptance` ve `budget` alanlarını taşır. Aşama `after` bağımlılıkları önceki aşamanın bütün hatlarına genişler; aynı
  aşamadaki hat bağımlılıkları doğrudan düğüm kenarıdır. Bilinmeyen kenar, döngü (`Cycle detected: p/one -> p/two ->
  p/one` gibi tam yol), geçersiz kapsam/komut/zaman aşımı ve ata-torun ilişkisi olmayan paralel `ownership` çakışmaları
  reddedilir; bütün çakışan çiftler tek tanıda raporlanır. Geçerli taslak `dag` alanıyla birlikte saklanır ve `plan`
  hiçbir worker, proje veya kampanya başlatmaz; başlatma yalnızca ayrı `project-start` çağrısıyla olur.
  `tester` motorun sahip olduğu doğrulama aşamasıdır: yalnızca görevin kabul komutlarını bir kez AppContainer içinde çalıştırır,
  serbest komut kabul etmez ve imzalı `tester-report.json` üretir. Rapor run/project fingerprint/patch SHA-256/assignment'a bağlıdır;
  MAF gözden geçirici çalışmadan önce kanıtı doğrular. `coordinator` (`coordinate` komutu) atanan araçla ya da verilen
  `spec` ile plan üretir; yalnızca doğrulanmış DAG ve rol ataması döndürür. Shell, worker başlatma, kampanya/proje
  başlatma ve apply yetkisi yoktur: `command`, `auto_apply`, `allow_apply` ve `shell` önerileri plan doğrulamasından önce
  reddedilir; yalnızca aşama `verify` kontrollerindeki motor sahipli `command` alanına izin verilir. Geçersiz planda
  `0` worker başlar ve karar taslağı `invalid` kaydedilir. Açık rol ataması kullanılamıyorsa `ROLE_UNAVAILABLE` döner;
  coordinator açık atamayı sessizce değiştirmez. Coordinator bir görev rolü değildir: `engine/runner.py` tek görevde
  `coordinator` atanırsa `ROLE_NOT_EXECUTABLE` döner ve `coordinate` komutuna yönlendirir.

Kod: `workflows/roles.py`, `workflows/coordinator.py`, `engine/runner.create_task`, `workflows/maf_workflow._review_assignment`, `interfaces/rpp.py`;
testler `tests/workflows/test_roles.py`.

## 5. Kampanyalar ve projeler

- `campaign-start` imzalı bir tanım saklar, motorun anlık görüntüsünü alır ve ayrık bir denetleyici (`campaign-run`)
  başlatır; çağıran çıkar, kimse sorgulamaz. `campaign-list` ve `campaign-status` durumu motordan okur.
- Her iş akışı hattı ayrı bir veri köküdür (kendi kilidi, anahtarı, durumu, çalışma ağaçları); hatlar gerçek paralel
  süreçlerdir, `after` bağımlılığı ifade eder. Scheduler deterministik hazır kuyruğu kullanır; `max_parallel` 1–8 arasıdır
  ve varsayılanı `min(4, hat sayısı)`dur. Bağımlı hat ancak bütün öncülleri `MASTER_APPROVED` olduğunda başlar; başarısız,
  zaman aşımına uğramış veya iptal edilmiş öncül bütün bağımlı zinciri `SKIPPED` yapar.
- Aynı normalize edilmiş `project_root` altında ownership kapsamı çakışan iki hat asla eşzamanlı çalışmaz; bağımsız hatlar
  boş kapasiteyi kullanmaya devam eder. Her hat için `QUEUED → RUNNING → terminal` geçişleri zaman damgası ve nedeniyle
  imzalı `result.json` içindeki `scheduler.states` / `scheduler.transitions` alanlarına yazılır. Hata, `TIMED_OUT`,
  `CANCELLED` ve bağımlılık kaynaklı `SKIPPED` terminal durumları ayrıdır.
- `campaign-cancel ID` bir iptal işareti bırakır; bekleyen hatlar `CANCELLED` olur, çalışan hatların sonucu dönüşte
  `CANCELLED` olarak kaydedilir. İptal edilen kampanyada son master hiç başlatılmaz.
- Bütün hatlar terminal duruma geldiğinde denetleyici imzalı `result.json` yazar ve iptal yoksa son incelemeyi bir kez
  başlatır (`final.claim`). `final.allow_apply` isteğe bağlıdır ve yalnızca motorun kendi komut satırına izin verir.
- Git olmayan kaynaklar kampanya klasöründeki geçici bir Git aynasında geliştirilir (sırlar ve ağır klasörler hariç).
- `plan` bir proje tanımını düğüm/kenar DAG'ına normalize eder ve `project-start` ile aynı motor doğrulamasına tabi tutar;
  taslak `drafts/` altında `spec`, `dag`, doğrulama sonucu ve `problem` ile saklanır. Bu aşama yalnızca taslak üretir.
- Kaynaktan çalışırken denetleyici motorun anlık görüntüsünden çalışır (motor kendini geliştirebilir); paketlenmiş exe
  zaten değişmez bir kopyadır.
- `maf-approve` etkileşimli bir terminal ister; insan onayı hiçbir zaman MCP'den sunulmaz.
- `integrate` iki ayrı doğrulanmış sonucu birleştirme kararına hazırlar. Girdi iki farklı `run_id` ve 1–16 birleşik
  doğrulama komutudur. Motor gerçek çalışma ağacının temiz ve run fingerprint'iyle aynı olduğunu doğrular; patch'leri
  `state/integrations/` altındaki geçici detached Git worktree'de sırayla `git apply --check` ve `git apply` ile dener.
  Aynı satır/dosya çakışması, HEAD drift, güvenlik ihlali veya birleşik doğrulama hatasında hiçbir kanıt yayımlamaz ve
  gerçek repoyu değiştirmez. Başarıda yalnızca imzalı `integration.json` ile `combined.patch` yayımlar; patch'i gerçek
  repoya uygulamak ayrı bir operatör kararıdır (`apply`). Geçici worktree ve staging her çıkışta temizlenir; temizlik
  sonrası gerçek repo HEAD'i ve fingerprint'i yeniden doğrulanır. Kod: `engine/integration.py`.
- **Checkpoint ve handoff (RES-01):** `workflows/checkpoint.py`, run/kampanya/proje için ortak ve sürümlü bir kurtarma
  anlık görüntüsü tanımlar. v2 şeması yalnızca `schema_version`, `kind`, `operation_id`, `status`, `repo` (commit/kök),
  `role`, `round`, `next_action` (step/hedef/neden), tamamlanan kontrollerin SHA-256 haritası, sabit limitler ve
  zaman damgasını taşır; şema kapalıdır ve bilinmeyen alanı reddeder. Prompt, worker isteği, ortam, API anahtarı,
  parola, belirteç, stdout/stderr ve transkript alanları yazımdan önce reddedilir; hedef metinlerinde sır deseni de
  yasaktır.
- Checkpoint, motorun sahip olduğu imza anahtarıyla imzalanır ve geçici dosya + atomik değiştirme ile yazılır. Yazma
  öncesinde doğrulama ve veri kökü sınırı uygulanır; reddedilen anlık görüntü yeni dosya oluşturmaz veya mevcut dosyayı
  değiştirmez. Süreç öldürülürse önceki ya da yeni tam anlık görüntü kalır, yarım geçici dosya okunmaz.
- İnceleme sonucu `RESUMABLE` veya `NEEDS_REVIEW` olur. Eksik/yarım, bozuk, imzası geçersiz, daha yeni şemalı,
  repo kökü erişilemez veya HEAD'i değişmiş checkpoint hiçbir zaman otomatik resume edilmez; `NEEDS_REVIEW` ve makine
  tarafından yorumlanabilir bir neden döner. Git olmayan kaynakta commit `None` olabildiğinden içerik drifti HEAD ile
  algılanamaz; bu durum insan incelemesi gerektirir.
- v1 checkpoint doğrulandıktan sonra bir kez v2'ye taşınır; eski imzalı payload `.v1.bak` olarak korunur ve ikinci
  inceleme byte düzeyinde değişiklik yapmaz. Bu görev yalnızca veri sözleşmesini kurar; gerçek kill/restart, kilit
  temizleme ve tekrar çalıştırılabilir adım whitelist'i RES-02 kapsamındadır.
- **Kontrollü resume (RES-02):** `project-resume`, proje checkpoint'inden yalnızca `resume`, `campaign`, `apply`,
  `verify`, `review` ve `complete` sınırlarından birini yeniden çalıştırır; her sınır diskte idempotenttir. Aynı
  `operation_id` korunur, yarım kampanya yeniden ücretlendirilmez ve imzalı `applied.json` ile açıklanabilen çökme
  sonrası apply tekrar edilmez. Canlı kilit sahibi varken resume reddedilir; yalnızca ölü PID veya bozuk kilit
  temizlenir. Bayat patch `stale patch` olarak sınıflandırılır ve zorla uygulanmaz.
- Kaynak içerik parmak izi veya Git HEAD değişmişse, checkpoint adımı bilinmiyorsa ya da checkpoint doğrulanamıyorsa
  otomatik resume yapılmaz. Operatör `project-approve ID` ile `data/projects/<project_id>/resume-approval.json`
  kaydını oluşturur; bu kayıt proje kimliği, operation kimliği, ham checkpoint SHA-256'sı, checkpoint durumu, neden,
  toplu kaynak parmak izi, repo commit'i, onaylayan ve UTC zaman damgasına bağlıdır. Herhangi biri değişirse onay
  geçersizdir. Onay yalnızca etkileşimli terminalden alınır; `RESPECTED_ORCH_CHILD=1` veya
  `RESPECTED_ORCH_DELEGATED=1` alt süreçlerinde reddedilir. MCP'de onay aracı yoktur ve onaysız `orchestrator_resume`
  fail-closed döner. Onay verilse bile `auto_apply=false` aşaması apply için ayrı insan yetkisi ister.

## 6. MCP sunucusu ve izinler

`respected-orchestrator mcp [--allow-auto-apply] [--allow-privileged]`, Hub'ın kullandığı motor işlevleri üzerinde
standart kütüphaneyle yazılmış bir stdio MCP sunucusudur; Hub gerekmez, başlattığı çalışmalar Hub'da görünür. Araçlar:
`orchestrator_status`, `_plan`, `_task_start`, `_project_start`, `_list`, `_progress`, `_evidence`, `_resume`, `_cancel`,
`_apply`, `_memory_note`. `integrations set İSTEMCİ=on` (ya da Hub'ın paneli) AI aracının ayarına kurulu programı
gösteren bir girdi ekler: `respected-orchestrator.exe mcp`. Başka girdiler korunur; kapatınca ve kaldırınca yalnızca kendi
girdisi kalkar (elle değiştirilmiş olsa da); kayıtta olmayan aynı adlı bir girdiye ve elle değiştirilmiş bir girdinin yeniden
yazılmasına izin verilmez.

OpenCode istemcisinde girdi `~/.config/opencode/opencode.json` içindeki `mcp.servers` altında
`{"type": "local", "command": [...]}` biçiminde tutulur; kaldırma ve geri alma önceki içeriği byte düzeyinde geri
yükler, diğer sunucular ve ayarlar korunur.

Sunucu, istem enjeksiyonuna uğramış olabilecek bir modelin isteğini alır. Bu yüzden MCP üzerinden
`orchestrator_task_start` ve `orchestrator_project_start` şunları reddeder:

- `worker: "custom"`, herhangi bir `command`, `apply_root`, `engine_source` — sunucu `--allow-privileged` ile
  kaydedilmedikçe. `--allow-auto-apply` yalnızca `auto_apply` reddini kaldırır. Hub ikisini de hiç vermez.
- Kişinin önceden onaylamadığı doğrulama ve `verify` komutları: `mcp_acceptance_allow` ayarındaki öneklerden biriyle
  kelimesi kelimesine başlamayan komut geçmez. Varsayılan liste boştur. Onaylı komutlar da doğrulama kum havuzunda çalışır.
- İzin atlayan bayraklar (bölüm 2).

Özyineleme yoktur: `RESPECTED_ORCH_CHILD` ya da `RESPECTED_ORCH_DELEGATED` tanımlıyken bütün araçlar gizlenir ve reddedilir;
sunucunun başlattığı her şey `RESPECTED_ORCH_DELEGATED=1` taşır. Çalışanlar yalıtılmış çalışma alanlarını düzenler; gerçek
ağaç yalnızca doğrulanmış `patch_sha256` ile `orchestrator_apply` üzerinden değişir.

Sınırlar: listelenen bir önek her argümana izin verir (`pytest -p eklenti` projeden kod çalıştırır); dar önekler yazın.
Aracı çağırıp çağırmamaya yine istemcinin kendi izin sorusu karar verir. `verify` girdisinin `cwd`'si kısıtlanmaz.

## 7. Brain hafızası

Orchestrator Brain'e hiçbir zaman bağımlı değildir; bağlantı yoksa aşağıdakilerin hiçbiri çalışmaz.

- **Bağlanma:** `memory connect [--write]` kurulu Brain'in `rpp` sunucusundan `memory.grant` ile izin alır ve
  `memory_enabled`, `memory_write`, `memory_grant_id`, `memory_command` (`{"argv": [<respected-brain.exe>, "rpp"], "env": {}}`)
  ve yalnızca yazılabilen `memory_token` ayarlarını `config set` ile aynı kodla yazar. Ayar yazılamazsa izin hemen iptal
  edilir; yarım bağlantı kalmaz. `memory disconnect` izni iptal eder ve alanları temizler.
- **Kullanım bir izindir, varsayılan değil:** `memory: {use: true, query?}` demeyen görev hafızayı okumaz. Bağlantı yokken
  `use: true` görev oluşturulurken hatadır. Çalışma anında yapılandırma yeniden denetlenir (kopan bağlantı kuyruktaki
  görevleri hemen etkiler), Brain'e `memory.recall` sorulur (alt süreç, stdin'de bir istek, stdout'ta bir yanıt) ve en
  fazla yaklaşık 3000 karakterlik parça, güvenilmeyen veri olduğunu belirten bir başlık altında görev metnine eklenir.
  Sorgu `memory.query` ya da görevin ayırt edici kelimeleri (en fazla 12). Her hata yalnızca "hafıza yok" demektir.
- **Anahtar:** yalnızca `<veri kökü>/memory-token` dosyasındadır (`.engine-key` gibi ACL'li; Codex kum havuzu kullanıcıları
  okuyamaz). `settings.json`'da, makbuzlarda, istekte, durumda, kanıtta, günlükte, hata metninde ve görev metninde yer
  almaz; okumada `***set***` görünür. Alt sürece yalnızca stdin'den, en az ortamla verilir. `memory-context.json` yalnızca
  durum, sayı, göreli yollar, puanlar ve dizin durumunu kaydeder.
- **Yazma:** `orchestrator_memory_note` MCP aracı, her iki izin varsa (bağlantı `--write` ile ve Brain tarafında yazma
  izni) yeniden kullanılabilir bilgiyi `memory.write` ile Brain'in gelen kutusuna yeni not olarak yazar. Görev
  geçmişi yazılmaz.
- **RES-03 resume ve karar belleği sözleşmesi:** operasyonel checkpoint ve handoff verisi motorda yerel kalır; Brain
  yokken campaign, apply ve verify sınırlarındaki 3/3 resume senaryosu Brain çağrısı `0` ile tamamlanır. Görev açıkça
  `memory.use` demezse opt-out akışında Brain çağrısı `0` olur; `memory_write` izni yokken not yazımı da `0` çağrıyla
  reddedilir. Grant matrisi 5/5 doğrulanır: Brain yokken `NOT_INSTALLED`, read grant ile bağlı/read-only, write grant
  ile tek not, revoke/disconnect ile token ve grant temizliği, denied/geçersiz grant ile mevcut ayarların korunması.
  Prompt-injection içeren not yalnızca güvenilmeyen veri bloğunda kalır; uyarı başlığı enjeksiyondan önce gelir ve
  token brief, kanıt veya `memory-context.json` içine sızmaz. Brain kod importu yasaktır (ADR-006); bağlantı yokken
  motor aynı işlevi görür.
- Kalan risk: parçalar o çalışmanın `brief.md` dosyasındadır (çalışan model görmek zorunda) ve çalışan, kişinin dosya
  erişimine sahip bir modeldir. Hafızayı yalnızca not parçalarının o modele gitmesini kabul ettiğiniz projelerde açın.

## 8. Ayarların saklanması

Ayarlar veri kökündeki `settings.json`'dadır (geçici dosya + atomik değiştirme). `settings.apply` birleştirir: verilmeyen
anahtarlar saklı değerini korur. Gizli anahtarda `***set***` ya da yokluk korur, `""` temizler. Geçerli her uygulama
`receipts/<operation_id>.json` makbuzu yazar (yalnızca işlem kimliği, zaman ve ayarların özeti, değerler değil); aynı
işlem kimliği aynı ayarlarla tekrarlanırsa saklı makbuz döner, farklı ayarlarla `OPERATION_ID_CONFLICT`. Bilinmeyen
anahtar hatadır.

Biçim sürümü `interfaces/migrate.py` içindeki `CURRENT` ile tutulur. Bir dosyanın biçimi değiştiğinde sürüm artırılır,
`STEPS`'e eski sürümden yenisine bir adım ve `tests/fixtures/releases/<sürüm>/` altına o sürümün yazdığı gerçek dosyalar
eklenir. `setup`/`repair` okumadan önce `migrate_data` çalışır: ilk çalıştırmada `<ad>.v<N>.bak` yedeği bırakılır,
ikinci çalıştırma byte düzeyinde hiçbir şey değiştirmez. Adım eksikse ya da dosya daha yeni bir biçimden geliyorsa
`MigrationError` ile durur; dosya ve yedek yazılmaz, veri kaybı olmaz. `CURRENT` yükseltilip `STEPS` veya fixture
eklenmezse `tests/interfaces/test_migrate.py` kırılır ve CI birleştirmez.

## 9. Testler

| Klasör | Kapsam |
|---|---|
| `tests/engine/` | çalıştırıcı, çalışma ağaçları, Codex sonuçları, süre sınırları, kum havuzu, Windows süreçleri, bütçe, geçmiş |
| `tests/workflows/` | MAF iş akışı, kampanyalar, rol atama |
| `tests/interfaces/` | RPP, kurulum ve hafıza bağlantısı, MCP sunucusu ve izinleri, Brain hafızası, AI aracı kayıtları |
| `tests/evals/` | değerlendirme fixture'ları, sabit SHA'lı koşucu, tekrar ve JSON rapor sözleşmesi |
| `tests/docs/` | DOC-01 kaynak/profil/ADR yapısal doğrulaması; `docs/ilerleme/poc/doc01_check.py` |
| `tests/packaging/` | derlenmiş exe, PATH'te Python yokken: RPP, MCP, ayrık denetleyiciyle gerçek bir yazma görevi, kum havuzlu doğrulama |
| `tests/test_main.py` | komut satırı, ortak komutlar, hata biçimi |

Testler geçici depolarda ve sahte çalışanlarla çalışır; HOME yalıtılır. Paketleme testleri önce `packaging/build_dist.py`
ister; Brain takımıyla aynı anda çalıştırmayın. CI derlenmiş exe'yi üretir ve iki takımı da zorunlu tutar.

### Değerlendirme koşucusu (`tests/evals/`)

- Her fixture geçici bir dizinde sıfırdan kurulur. Git kimliği, tarihi ve yapılandırması sabittir
  (`GIT_CONFIG_GLOBAL` boş, sistem yapılandırması kapalı, `core.autocrlf=false`); bu yüzden başlangıç SHA'sı tekrar edilebilir.
- Koşucu model çağrısı yapmaz ve ürün verisine dokunmaz. Rapor yolu `RESPECTED_DATA_DIR`, `RESPECTED_ORCH_DATA` veya
  `RESPECTED_DATA_ROOT` altına denk gelirse yazma reddedilir.
- Her görev için hatalı başlangıç (kabul testi başarısız olmalı) ve altın çözüm (geçmeli) ayrı ayrı çalıştırılır; iki koşul
  da doğrulanmadan görev `passed` sayılmaz. Ölçülmeyen maliyet `bilinmiyor` olarak kaydedilir.

## 10. Açık sınırlar

- Beta yalnızca Windows'u destekler; macOS/Linux kod yolları var ama doğrulanmadı. POSIX'te anahtar için işletim sistemi
  kum havuzu sınırı yoktur.
- Claude, Gemini ve Cursor çalışanları kendi onay modellerini korur. Sağlayıcının `turn.completed` olayı modeli
  bildirmediği için incelemelerde `model: null` görünür.
- Kapsam denetimi çalışmadan sonra, yamaya bakarak yapılır; çalışanın kendisi kişinin izinleriyle çalışır ve çalışma ağacının
  dışına yazması yakalanmaz (bölüm 2).
- Codex'in kum havuzu kullanıcı profilindeki programları (örneğin `AppData\Local\Programs` altındaki Python) çalıştıramayabilir:
  çalışan böyle bir doğrulama komutunu kendi kendini denerken çalıştıramayıp görevi başarısız bildirebilir. Motorun kendi
  doğrulaması ayrıca kısıtlı belirteçle yapılır.
- Kurucu Authenticode ile imzalı değildir.
