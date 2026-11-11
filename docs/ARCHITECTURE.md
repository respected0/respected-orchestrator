# Orchestrator mimarisi

Motorun nasıl paketlendiği, bir görevin nasıl doğrulandığı, hangi güvenlik sınırlarının uygulandığı ve hangi kuralların
bağlayıcı olduğu. Giriş ve komutlar: [README.md](../README.md). Üç ürünün ortak kuralları (kurucu, komutlar, ayarlar,
protokol) [PRODUCT_CONTRACT.md](PRODUCT_CONTRACT.md) dosyasındadır; burada tekrarlanmaz.

## 1. Paketlenmiş motor

- `packaging/build_dist.py` motoru PyInstaller ile (onedir, içerik `app/` altında) `dist/RespectedOrchestrator/` klasörüne
  dondurur: `rorch.exe` ve her dosyanın SHA-256'sını taşıyan `distribution.json`. Agent Framework'ün tembel
  alt modülleri toplanır; bildirilen bağımlılıkların dışındaki kurulu paketler dışarıda bırakılır, böylece yerel derleme
  temiz bir CI derlemesiyle aynı içeriği taşır. `_selfcheck` her modülü içe aktarır ve eksik olanda başarısız olur.
- Kurucu (`packaging/windows/orchestrator_setup.iss`, ADR-031) **yalnızca dosya kopyalar**: programı `app\` altına yazar, güncellemede
  eski dosyaları siler, dosyaları kullanan süreçleri Windows'a kapattırır; sayfa, ayar, yedek, geri alma ve `setup` çağrısı içermez.
  Kurulumu motor tamamlar: ilk açılışta (`daemon`) dosyaları `distribution.json` ile doğrular ve kurulumu `app\.respected\install.json`
  olarak kaydeder (`rorch setup` aynı işi elle yapar). `manifest`'in `install_state` değeri bu kayıttan ve dosyaların şimdiki
  hash'inden gelir; masaüstü uygulaması ve CLI "kurulu" ile "onarım gerekli" konusunda aynı şeyi söyler. `distribution.json` ile uyuşmayan
  bir klasör kaydedilmez (motor çalışır, `health` ve `repair` söyler).
- Masaüstü kabuğu (`respected-orchestrator-desktop.exe`) motorla **tek pakettir** (ADR-025): `build_dist.py --desktop <exe>` onu motor
  başlatıcısının yanına, klasör köküne koyar ve `distribution.json`'a hem `files` içinde (sha256) hem de isteğe bağlı üst düzey
  `desktop` anahtarıyla yazar; `schema_version` 1 kalır. `build_dist.py --audit` bildirimi klasörle karşılaştırır (eksik, fazla,
  karma uyuşmazlığı, adlandırılmış ama karmasız kabuk). Kabuk motoru önce `RESPECTED_APP_DIR` (verilmişse yalnız orası), sonra kendi
  klasöründe, sonra `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app` altında arar ve başlatıcının karmasını `distribution.json`
  ile eşleştirmeden çalıştırmaz (kurulu klasörlerde bildirim zorunlu). Onarım kurucuyu yeniden çalıştırmaktır; kabuk dosya yazmaz.
- Motor kendini her zaman `context.engine_command` ile yeniden başlatır: donmuşsa exe, kaynaktan
  `python -m respected_orchestrator`. Ayrık görev, proje ve kampanya denetleyicileri
  bu yoldan geçer. Her alt süreç `engine/winproc` üzerinden açılır.
- `--data-root` yalnızca motorun kendi alt süreçleri içindir (her kampanya hattının kendi kökü vardır); yardımda görünmez.
  Kişiler ve testler `RESPECTED_DATA_DIR` kullanır.

### Kalıcı motor (ADR-030, 1. dilim)

- `rorch daemon start|stop|restart|status` veri kökü başına **tek** kalıcı süreç yönetir (`engine/daemon.py`, istemci: `engine/daemon_client.py`).
  Tekillik `state/daemon.lock` dosya kilididir (çökme kilidi bırakır; yükseltilmiş oturumda çalışmaz). İlk istemci motoru yoksa başlatır
  (gizli konsol, `lanes._spawn_detached`); çalışan motor başka sürümse kullanılmaz, `daemon restart` istenir. Hiçbir istemci motor
  yokken yerel bir kopyayla cevap vermez (`ENGINE_UNAVAILABLE`).
- Tek giriş: adlandırılmış boru `\\.\pipe\rorch-<kullanıcı>-<veri kökü özeti>`; erişim listesi yalnız mevcut kullanıcıdır, uzak istemci
  reddedilir, ilk örnek bayrağı adın önceden alınmasını önler. Port yoktur. Protokol `local_api` ile aynıdır; ek olarak `daemon.status`
  ve `daemon.stop`. Yalnız Windows; Unix soketi sonraki iş.
- Arayan kimliğini motor çözer: bağlanan süreç, o an bir koşu üzerinde çalışan sürecin kendisi ya da soyundansa (`winproc.ancestors`,
  yeniden kullanılmış PID zinciri keser) `CHILD` olur ve hiçbir komut çalıştıramaz; diğer herkes `MCP` düzeyindedir (okuma ve görev).
  Sunulan katalog yalnız `READ` ve `TASK` komutlarıdır: onay, uygulama, ayar ve ekran görüntüsü onayı bu uçta **yoktur**.
- Boşta (bağlantı yok, çalışan koşu yok) 30 dakika sonra motor kendiliğinden çıkar; testler için `RESPECTED_DAEMON_IDLE_SECONDS`.
- Canlı sohbet oturumları (`SessionController`) artık **motorun tek örneğindedir**: her bağlantı aynı denetleyiciyi görür, `rorch session ...` ona
  bağlanır (motor yoksa başlatır). Bir tur çalışırken motor boşta çıkmaz; boşta oturumlar kaydedilir ve `resume` ile sürdürülür.
  Ortak uçta `session.defaults.set` (ayar) yoktur.
- Motor, kendini Windows iş nesnesine (`winproc.contain_children`, kapanınca öldür) koyar: motor nasıl biterse bitsin ajan çocukları kalmaz.
  Koşular `CREATE_BREAKAWAY_FROM_JOB` ile ayrık başladığından iş nesnesinin dışındadır ve motor kapanınca da devam eder.
- Masaüstü kabuğu (3. dilim) motoru başlatıcıya `daemon start` dedirterek ayakta tutar ve çıktıdaki boruya bağlanır (`Connection::connect`);
  kabuk motoru artık kendi çocuğu olarak çalıştırmaz ve kapanınca motoru durdurmaz. Boru adını motor verir (kabuk adı hesaplamaz) ve
  yalnız `rorch-` ailesinden bir ad açılır. Kabuğu motor tanır: bağlanan sürecin dosyası, başlatıcının yanındaki
  `respected-orchestrator-desktop.exe` ve baytları `distribution.json`'daki karma ile aynıysa `RENDERER` düzeyi verilir (okuma, görev ve
  ayar komutları; onay/uygulama yine yoktur). Tek ayar komutu `session.defaults.set`'tir. Paketsiz (kaynaktan) çalışan motorda kimse tanınmaz.
  Aynı kullanıcının kabuk sürecine kod enjekte etmesi bu kontrolün kapsamı dışındadır.
- Yerli onay bağlantısı (`approval.decide/apply`, ekran görüntüsü onayı) kabuğun **özel** çocuk motorudur (`connect_private`, `_ipc --human`): yalnız
  kabuğun kendi borularından erişilir. Onay durumu imzalı dosyalardadır, bu yüzden ortak motorla tutarlıdır.
- `rorch mcp` kendi sürecidir; `orchestrator_session_*` araçlarını motora iletir (4. dilim). Görev, proje, kampanya, apply ve not araçları süreç içinde çalışır (`KALAN_ISLER.md` 1.1). Sesli giriş ve ekran görüntüsü hazırlığı bağlantı başınadır; kabuk tek bağlantı tutar.

## 2. Görev ve sonuç denetimi

- Her görev projenin ayrı bir Git çalışma ağacında çalışır (ayrı klasör ve dal; işletim sistemi düzeyinde yalıtım değildir). Sonuç bir iddiadır: kapsam (`ownership` / `forbidden`),
  doğrulama komutları, yamanın projeye hâlâ uyması, imzalı kanıt ve projenin güncelliği ayrı ayrı geçmelidir. Hiçbir şey
  kendiliğinden uygulanmaz; `apply` `check`'i yeniden çalıştırır, `git apply --check` yapar, commit atmaz ve çalışan
  süreçlerin içinden reddedilir. Yeniden denemeler açık ve sınırlıdır; süre sınırları ve süreç ağacı temizliği korunur.
- **Worker başlatma:** Bütün worker girişleri (`create`, `start`, MAF araç çağrıları ve kampanya alt şeritleri) tek
  `engine/processes.execute` yolundan geçer. İşçi **kullanıcı olarak, ajanın kendi izin kipiyle** çalışır; motor
  işletim sistemi düzeyinde dosya ya da ağ sınırı koymaz. Motorun işi kapsamı, süreyi ve sonucu denetlemektir: `.cmd`/`.bat`
  şimleri reddedilir (Cursor için şimin yanındaki `versions\<sürüm>\node.exe` + `index.js` doğrudan girişi kullanılır;
  `--trust --output-format json` ile çağrılır, `usage` `inputTokens/outputTokens/cacheReadTokens` alanlarından okunur,
  `cacheReadTokens` yoksa kullanım `unknown` kalır; `inputTokens` önbellek okumasını içermez, ham girdi ikisinin toplamıdır),
  sır gibi görünen ortam değişkenleri çalışandan çıkarılır (`processes.scrub_environment`, `RESPECTED_WORKER_ENV_ALLOW` ad
  başına açık istisnadır), her alt süreç `RESPECTED_ORCH_CHILD=1` ile işaretlenir, süre sınırı dolunca ya da iptalde bütün süreç
  ağacı Windows iş nesnesiyle kapatılır. Motor, supervisor ve kampanya final master'ı ayrı güvenilen süreçlerdir.
- **Güven modeli:** İşçi ve doğrulama komutları kullanıcının yetkisiyle çalıştığı için `.engine-key` dosyasını okuyabilir.
  Kanıt ve onay bütünlüğü imza (HMAC) ve motorun yeniden doğrulamasıyla sağlanır; anahtarın gizliliği için ek bir garanti
  **verilmez**. Bir işçinin yazdığı koddan korunmak, ajanın kendi izin kipine ve kullanıcının seçtiği kipe bağlıdır.
- **Yama türü fail-closed (SEC-04):** Git indeksindeki `120000` (symlink) ve `160000` (gitlink/submodule) yolları
  `unsafe_paths` içine alınır; kapsam ihlali sayılır, `export_worker_patch` yama üretmeden reddeder ve
  `check_patch_against_master` bu modları taşıyan yamayı `INTEGRATION_CONFLICT` olarak reddeder. Windows symlink
  ayrıcalığı olmayan worker'ın `git update-index` ile `120000` hazırlayıp normal dosyayla maskelemesi de reddedilir.
- **Kalan sınır:** Yol Windows'ta doğrulandı. macOS ve Linux'ta çalışır durumda olması hedeflenir ama henüz doğrulanmadı
  (REL-04 platform kararı: GA yalnız Windows). Yükseltilmiş yönetici oturumunda supervisor başlamaz (`is_elevated`).
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
- OpenCode alt süreci kullanıcının kendi profiliyle (HOME, oturum) çalışır; motor kimlik bilgisi kopyalamaz ya da yönlendirmez.
  Ağ ve model erişimi ajanın kendi ayarıdır.
- **Cursor çalışanı (CUR-01):** Cursor oturumu kullanıcının kendi profilindedir (`%APPDATA%\Cursor\auth.json`); motor ona dokunmaz.
  Çalışan, `.cmd` şimi yerine kendi `node.exe` + `index.js` girişiyle başlatılır.
- **Sağlayıcı ağ kapısı (ADR-007):** Kendi API sağlayıcı adaptörleri (ADP-03) ağ varsayılan kapalıyken çalışmaz.
  `engine/provider_policy.py` soket açmadan önce `RESPECTED_PROVIDER_NETWORK=allow` ve
  `RESPECTED_PROVIDER_CODE_GATE=1` ister; yalnızca `https` ve açık allowlist'teki tam alan adına izin verir. Her
  redirect hedefi yeniden doğrulanır; proxy de allowlist'ten geçer. 401/429/5xx başka sağlayıcıya sessiz fallback
  yapmaz. Anahtar istek anında kasadan okunur, log/kanıt/ayar JSON'una yazılmaz ve `***set***` ile maskelenir.
- **Fiyat kataloğu (COST-02):** `engine/pricing.py` sürüm kontrollü katalogdan deterministik teklif üretir. Her
  rakamsal teklif `at`, `model_version`, `effective_from` ve `currency` taşır; model, kullanım veya sağlayıcı
  bilinmiyorsa tutar `None` ve durum `unknown` olur, sıfıra çevrilmez. Fiyatlar liste fiyatıdır
  (`estimate_only`); canlı fiyat çağrısı zorunlu değildir.
- **OpenRouter çalışanı:** `openrouter` aracının CLI'si yoktur; profil model adıdır (örneğin `vendor/model:free`, zorunlu). Okuma rolleri (reviewer, tester, planner, coordinator) `engine/openrouter_worker.py` üzerinden `_openrouter MODEL PROMPT` ile tek sohbet çağrısı yapar. Tam görevlerde (`kind=read` ya da `write`) motor sağlayıcıyı kendi sürecinde çağırır (model denetimli kod çalıştırmaz): sahip olunan dosyaların içeriği isteme konur (yasak dosyalar konmaz) ve model tam dosya içerikleriyle bir JSON döndürür. Motor yazmadan önce her yolu denetler: göreli, `..` ve `.git` yok, sahip olunan kapsamda, yasak kapsamda değil, çalışma ağacının içinde, dosya başına en çok 120 KB ve en çok 25 dosya; biri bile geçmezse hiçbir şey yazılmaz ve görev `worker_failed` olur. `kind=read` görevi hiçbir şey yazmaz. Ardından her çalışan gibi kapsam denetimi, kabul komutları ve imzalı kanıt gelir. Ağ `RESPECTED_PROVIDER_NETWORK=allow` ve `RESPECTED_PROVIDER_CODE_GATE=1` anahtarlarına bağlıdır, anahtar `provider-key set` ile DPAPI kasasına girer; 429 ve 5xx en çok iki kez yeniden denenir, başka modele geçilmez. Anahtar yoksa araç kullanılamaz sayılır.
- **Sağlayıcı adaptörü (ADP-03):** `engine/provider.py` OpenRouter çağrılarını `require_access` kapısından
  geçirir; `secret_vault.py` anahtarı Windows DPAPI ile şifreli tutar, düz metin dosya yoktur. Aynı
  `idempotency_key` ikinci kez ağ çağrısı yapmaz. 401 `unauthorized`, 429 `rate_limited`, 5xx
  `provider_error`, süre aşımı `timeout` ve `[DONE]` görmeden biten akış `stream_incomplete` olarak
  ayrılır; hiçbiri başka sağlayıcıya veya modele sessiz fallback yapmaz. Kullanım bilinmiyorsa `None`
  ve `usage_status=UNKNOWN` kalır. `models()` yalnızca genel model kataloğunu okur ve anahtar istemez.
- **Yetenek manifestosu (EXT-01):** `engine/capability_manifest.py` skill ve MCP araçlarını fail-closed
  denetler. Manifest yoksa, alanı eksikse ya da SHA-256 tutmuyorsa çalışmaz; `trust` yalnızca `trusted`, provenance
  kurulum kaydıyla eşleşmek zorundadır. Araç yalnızca manifestte bildirilen ve görev planında açıkça onaylanan
  işlemi yapabilir; bildirilmeyen araç/izin otomatik yetkilendirilmez. `exec` kapalıdır, veri kapsamı repo dışına
  çıkamaz. Açıklama metni yetki sayılmaz; metin içindeki talimatlar yeni izin vermez.
<!-- EVAL-03_ARCH -->- **KPI ve regresyon kapısı (EVAL-03):** `tests/evals/report.py` her raporda kabul başarısı, worker
  ihlali, maliyet ve süre KPI'larını üretir. Eksik veri sıfıra çevrilmez; `missing_kpi` hatası verir. İki koşu
  arasında başarı düşerse veya worker ihlali artarsa regresyon kapısı kapanır; farklı fixture/repeat/timeout
  raporları karşılaştırılamaz sayılır. Bu sentetik harness model başarısını ölçmez; gerçek ajanlı karşılaştırma
  henüz yoktur ve ayrı bir şema/rapor olarak planlanmıştır (ADR-019, FIX-02).
<!-- EVAL-02_ARCH -->- **Karşılaştırma koşucusu (EVAL-02):** `tests/evals/compare.py` aynı fixture, commit, makine ve zaman
  aşımıyla doğrudan ve orkestre kolları çalıştırır. Doğrudan kol değişiklik uygulamaz; orkestre kol doğrulanmış
  altın fixture yamasını uygular. Başarı oranı ile güvenlik ihlali ayrı metriklerdir; maliyet ölçülmediyse
  `bilinmiyor` kalır, sıfır yazılmaz. Her koşu sürüm/tarih/runtime metadata taşır.

## 3. Doğrulama komutları

Kabul ve proje `verify` komutları, motorun işçiden sonra ayrı bir süreç olarak çalıştırdığı komutlardır
(`processes.run_check`): çalışma ağacında, sır adlı ortam değişkenleri çıkarılmış olarak, görevin süre sınırıyla. Motor bu
komutları bir kutuda çalıştırmaz; sonucu (çıkış kodu, çıktı özeti) imzalı kanıta yazar ve kapsam denetimini komuttan sonra
yeniden yapar. İşçinin yazdığı kodun motorun sırlarını okuyabileceği varsayılır (bölüm 2, *Güven modeli*). Tehdit modeli
[THREAT_MODEL.md](THREAT_MODEL.md) dosyasındadır.

## 4. Rol atama

Her uyumlu model, sağlayıcı ya da araç her role atanabilir; kod hiçbir zaman "X modeli yalnızca Y rolünü yapar"
demez. Kavramlar ayrıdır: **rol** (iş akışındaki görev, `^[a-z][a-z0-9_]{0,39}$`, açık küme: `implementer`, `reviewer`,
`deep_reviewer`, `planner`, `debugger`, `tester`, `coordinator`, `master`…), **profil** (motor için opak bir model
yapılandırması), **araç** (`codex`, `claude`, `agy`, `cursor`, `opencode`, `custom`) ve **atama** (`{tool, profile}` + kaynağı).

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

**Akıllı yönlendirme (B4-01; görev oluşturulurken `workflows/run_hooks.route` çağırır):** `engine/task_classifier.py` görevi yapıdan `low|medium|high|unknown`
diye sınıflar (görev metni izin vermez, düzeyi düşüremez; risk yetki genişletmez). `workflows/routing_policy.py` aday başına
neden kaydederek **öneri** üretir; bilinmeyen maliyet `unknown`'dır, 0 değildir; yüksek/bilinmeyen risk ölçülü geçmiş ister;
açık atama olduğu gibi kalır. `routing_mode`: `shadow` (varsayılan; yalnız `routing-log.jsonl`'a öneri/gerçek farkını yazar),
`active` (öneri `effective` olur), `off` (kapalı; geri alma tek ayar).
`workflows/routing_confidence.py` gerçek ajan kıyaslama raporlarını (`tests/evals/bench.py run`, şema `respected.eval.bench.v1`) okur:
sentetik/eksik/yarım/sıfır-yazılmış/10×3×2'den küçük raporu reddeder, Wilson aralığıyla orkestrasyon–doğrudan karşılaştırır
("fark saptanamadı" bir sonuçtur, üstünlük değil), sürüm kayması ve karıştırılmış koşuları birleştirmeden işaretler. Geçerli gerçek
rapor yoksa kapı **başarısız** olur; ölçülmemiş benchmark geçmiş sayılmaz. Raporun orkestre kolundan `routing_policy.suggest` için
geçmiş tablosu üretilebilir.

**Takım ve ajan profilleri (B4-02.01; görev oluşturulurken `run_hooks.apply_profile`, CLI'da `rorch team`):** `workflows/team_profiles.py`, `<veri>/teams.json`
(şema 1). Profil = kalıcı kimlik (`id`, ad, takım rolü `lead|implementer|reviewer|qa|designer`, araç/model ataması, bütçe,
yetenekler, `rev`); **oturum** ayrı kimliktir (`ss-…`) ve profil kimliğinden türetilmez. Profil düzenlenince `rev` artar; bir koşu
başladığı profilin `snapshot()`'ını (kimlik, rev, özet) saklar, sonraki düzenleme eski kaydı değiştirmez. Bilinmeyen anahtar, kimlik
bilgisi benzeri değer ve rol/araçla uyumsuz yetenek (ör. reviewer/qa için `write`) reddedilir; profil hiçbir izni genişletmez.
`requested()` takımı `roles.resolve`'a açık atama olarak verir, yani öncelik, engelli profil ve `ROLE_UNAVAILABLE` davranışı aynıdır;
kaldırılan araç `check()` ile `tool_missing` raporlanır ve yerine başkası konmaz. `teams.json` yoksa takım mevcut rol ayarlarından
türetilir (yazılmaz); bilinmeyen şema `UNSUPPORTED_SCHEMA`.

**Devir mesajı ve posta kutusu (B4-02.02; CLI'da `rorch handoff` ve `rorch inbox`, `workflows/team_commands` üzerinden):** `workflows/handoff.py`. Bir ajanın devir önerisi
güvenilmez girdidir: kapalı alan kümesi, küçük boyut (ham 8 KB, zarf 4 KB), gönderen motorun bildiği oturumdan alınır (mesajdaki
`from` farklıysa `SPOOFED_SENDER`), alıcı takımda olmalı ve `next_action` alıcının rolüne uymalıdır, yol kapsamı yalnız göndericinin
sahip olduklarının alt kümesi olabilir (`SCOPE_WIDENING`), kanıt referansları bu kurulumun imzalı `result.json` yama özetiyle
doğrulanır (`FORGED_EVIDENCE`). Serbest `note` yalnız maskelenerek saklanan metindir, yorumlanmaz. Zarf `authority: none` taşır,
yani yetki değil veridir; alıcının yetkisi kendi profilinden ve normal çözümleyiciden gelir. `post` zarfı imzalayıp olay deposuna
(`events.log`, tür `handoff.posted`) ekler (aynı `operation_id` bir kez); `inbox` yalnız imzası doğrulananları döndürür, bozukları sayar.
Hop/yeniden deneme sınırlarının uygulanması koordinatörün işidir (B4-02.03).

**Çalışma yoluna bağlantılar (8 Kasım 2026, `workflows/run_hooks.py`, `workflows/team_commands.py`):** `create_task` isteği `profile` (takım profili kimliği)
alabilir: profil, istek o rolü kendisi söylemedikçe **açık atama** olur (açık > profil), bütçesi şerit bütçesini yalnız düşürür, koşu kaydına dondurulmuş
`profile_ref` (profil özeti + koşunun kendi oturum kimliği) yazılır; `handoff` bir doğrulanmış devri sürdürür (`handoff_ref`). Otomatik seçilen roller
`routing_policy.decide`'dan geçer (`routing_mode`: shadow yalnız `routing-log.jsonl` yazar). `retry_task` her seferinde `recovery.decide`'ı çağırır
(sınıf başına tavan zincirdeki önceki denemelerden sayılır; sınıflanamayan hata eski davranışı korur). Yeni komutlar: `team` (göster/kaydet), `handoff`
(`{run_id, message}`: gönderen ve kapsam koşunun kendi imzalı kaydından gelir), `inbox PROFIL`, `escalation RUN` (vaka kartı + zaman çizelgesi),
`operator RUN retry|resume|dismiss BAĞLAMA` (yalnız insan terminali; `resume` yalnız durdurmaları kaldırır, deneme/süre/belirteç sınırlarını ve `policy_denied`'ı
asla), `ledger`. Masaüstü üç salt okunur görünüm gösterir (Takım, Yetenek önerileri, Bütçe ve başarı) ve yalnız sabit listedeki üç IPC komutunu
(`team.view`, `capabilities.recommend`, `analytics.summary`) `read_call` ile iletir.

**Bağlam, ses, ekran görüntüsü, uzak gözlemci (B4-05…09):** `engine/context_map.py` (Git'e bağlı önbellekli, salt okunur depo haritası), `engine/context_prep.py` (sınırlı,
kaynak özetli, ayıklayıcı kritik kanıtı asla kırpmayan bağlam), `workflows/context_ab.py` (kazanım iddiası yalnız ölçülmüş verilerle); `engine/voice.py`
(ses yalnız taslak metin; ADR-027); `engine/attachment.py` (yakalama/ekleme/model paylaşımı üç ayrı karar; ADR-028); `interfaces/observer.py` (salt okunur, döngü
adresi, hiçbir yerden başlatılmaz; ADR-029).

**Kurtarma kararı (B4-08.01; yeniden denemeden önce `run_hooks.retry_guard` çağırır):** `workflows/recovery.py` `decide(reason, provider_status, state, limits)`
saf bir karar verir (`retry|pause|operator|stop`), kendisi hiçbir şey yapmaz. Sıra: önce kaynak sınırları (deneme ≤ 3 varsayılan/5
tavan, devir, süre, belirteç; ölçülemeyen belirteç bütçesi `pause`), sonra `policy_denied` → `stop`, `auth` → `operator`,
`quota` → `pause` (otomatik devam yok), yalnız test hatası/zaman aşımı/altyapı/bayat yama/düzeltme isteği sınıf başına tavanla
`retry` olabilir, aynı sınıf tekrar ederse devre kesici `pause`; sınıflanamayan hata `operator`. Geçersiz sınır istisna fırlatır,
sessizce varsayılana düşmez. `retry` her zaman sayılan bir denemedir, bu yüzden her döngü biter.
**Takım döngüsü (B4-02.03; `workflows/team_commands` üzerinden):** `workflows/team_loop.py` `evaluate` doğrulanmış devri `deliver|duplicate|
reject|escalate` diye sınıflar: aynı `operation_id` yinelenmez; hop bütçesi (zarf `max_hops` ile `max_handoffs`'ın küçüğü) ve yeniden
çalışma bütçesi aşılınca `escalate` (insana) ve durdurulacak oturumlar döner; alıcı aracı yoksa, çalışan oturumla yol çakışırsa,
bağımsız gözden geçirme isteniyorken gözden geçiren yazarla aynı araç/profildeyse, ya da aynı kenar yeni kanıt olmadan tekrarlanırsa
`reject`. `apply` diye bir eylem yoktur.

**Yetenek uyumluluğu, önerisi, izin kartı ve etkinleştirme planı (B4-03; yerel API'de `capabilities.recommend`):** hepsi
`engine/capabilities/` altında, çevrimdışı ve salt okunur; keşif kaydı (`normalize.build`) girdi olur. (1) `compatibility.resolve`
her kayıt için `compatible|incompatible|unknown` ve nedenleri verir (istemci/tür desteği keşif matrisinden; yalnız `stdio` aktarımı
onaylı; paket çalıştırıcıları ve diğer aktarımlar `unknown`; eksik program, yanlış proje `incompatible`); güveni okumaz. (2)
`recommendation.recommend` görev metninden küçük bir sözlükle kategori çıkarır, yetenekleri yalnız AD ve yapısal gerçeklerle
eşler; serbest metin açıklamaları asla eşleştirilmez ve talimat benzeri olanlar gösterilmez; her öneri `needs_approval: true`,
yüksek/bilinmeyen riskte onaysızlar `blocked_by_risk`. (3) `permissions.inspect` risk kartı üretir (komut, ağ, sır, dosya, kök,
genişlik) ve dört şeyi ayrı tutar: yürütme kapısı (`capability_manifest`, manifest + eşleşen onay kaydı), güven (yalnız onay kaydı;
manifestin kendi `trust` iddiası sayılmaz), erişilebilirlik ve risk. (4) `activation.propose/approve/consume` değişikliği
açıklar (proje bazlı, hedef yapılandırma dosyası proje içinde), yalnız HUMAN onaylar (`authority`), onay plana özetle bağlı, tek
kullanımlık ve süreli; `consume` taze envanterle yeniden denetler (bayat/oynanmış/başka proje/başka plan) ve yalnız "yazılabilir"
der. Hiçbiri dosya yazmaz; yürütme kapısı bağımsız ve son sözdür.

**Kullanım olayı (B4-04.01; `engine/ledger_source` üzerinden):** `engine/usage_event.py` her model çağrısı için tipli `UsageEvent`
üretir (taze girdi, önbellek okuma/yazma, çıktı, akıl yürütme; her alan için `reported|derived|absent|invalid` kaynağı). Raporlanmayan
değer `None`'dır, 0 değil; önbelleğin girdiye dahil olup olmadığı olayda `cache_semantics` olarak yazılır ve yalnız dahil olduğu bilinen
motor sözlüğünden taze girdi türetilir. Abonelik/bilinmeyen faturalama `cost_eligible: false` taşır, API maliyeti sayılmaz. Aynı
`event_id` iki kez sayılmaz; farklı rakamlı tekrar `conflicts`'te raporlanır. Olay yalnız sayı ve kimlik içerir.

**Maliyet/kalite defteri (B4-04.02; CLI'da `rorch ledger`, yerel API'de `analytics.summary`):** `engine/cost_ledger.py` fiyat kataloğunu özetli bir
anlık görüntüye (`snapshot`) dondurur ve koşu kayıtlarından görev sınıfı başına rapor üretir (çevrimdışı, aynı girdi aynı `digest`).
Bir koşunun maliyeti yalnız API-faturalı, tüm sayıları bilinen, fiyatı katalogda bulunan/yürürlükte/bayat olmayan ve tek para
birimli olaylardan hesaplanır; aksi halde o koşu `uncomputable` (nedenli) olur ve grup toplamı `None`'dır (fiyatlanabilen kısım
`known_part`'ta ayrı). Kabul edilen görev başına maliyet, başarısız koşuların harcamasını da içerir. Önbellek okuması tam girdi
fiyatıyla sayılır (`upper_bound`). `diff` yalnız iki tarafta da sayı, aynı para birimi ve aynı fiyat görüntüsü varsa fark verir.
`engine/ledger_source.py` defteri bu kurulumun kendi imzalı koşu kanıtından (`status.json`, `review-attempts.json`) her çağrıda
türetir; yeni dosya yazmaz, imzasız/kurcalanmış/çalışan/`custom` koşuları atlar. Faturalama (`api_metered|subscription`) araç başına
çağıranın beyanıdır; beyan yoksa `unknown` olduğundan hiçbir koşu varsayımla API maliyetine dönüşmez. Fiyat kataloğu da çağıranındır;
katalog yoksa koşular hesaplanamaz sayılır. Rapor `ledger` komutuyla alınır (salt okunur; ağ ve yazma yok).

Belirtilmeyen `deep_reviewer` `reviewer`'dır. Çözülen atamalar ve kaynakları (`explicit` / `configured_default` / `auto`) imzalı
istekte `role_assignments` olarak saklanır.

- Açık seçim asla sessizce değiştirilmez: kullanılamayan atama `ROLE_UNAVAILABLE`'dır; yalnızca atamanın kendi
  `fallbacks` listesi devreye girer. Hiçbir kaynaktan atanmayan gerekli rol `ROLE_UNASSIGNED`; gözden geçirici, MAF
  akışının ücretli ilk adımından önce denetlenir.
- `require_independent_review` açıksa çalışanla aynı profili kullanan gözden geçirici `ROLE_INDEPENDENCE`'tır; kapalıysa
  izin verilir ve `role_notes`'a yazılır. `escalate_profile` sonraki düzeltmeleri başka profile verir, ilk çalışan gözden
  geçirici olur. `blocked_profiles` (varsayılan `mimo`) profilleri her rolde reddeder.
- Gözden geçirmeler atanan araçla yapılır: `codex` kendi salt okunur kipinde (`--sandbox read-only`) çalışır; diğer araçlar boş bir kanıt
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
  `tester` motorun sahip olduğu doğrulama aşamasıdır: yalnızca görevin kabul komutlarını bir kez çalıştırır,
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

`rorch mcp [--allow-auto-apply] [--allow-privileged]`, masaüstü uygulamasının kullandığı motor işlevleri üzerinde
standart kütüphaneyle yazılmış bir stdio MCP sunucusudur; başka bir ürün gerekmez, başlattığı çalışmalar masaüstü uygulamasında görünür. Araçlar:
`orchestrator_status`, `_plan`, `_task_start`, `_project_start`, `_list`, `_progress`, `_evidence`, `_resume`, `_cancel`,
`_apply`, `_memory_note` ve kalıcı motorun sohbet oturumları için `orchestrator_session_list`, `_start`, `_send`, `_events`,
`_transcript`, `_interrupt`, `_cancel`, `_resume` (ADR-030: çağrı motora iletilir, motor yoksa başlatılır, ulaşılamazsa `ENGINE_UNAVAILABLE`; onay, uygulama ve
varsayılan değiştirme araçları yoktur). Görev, proje ve kampanya araçları canlı durum tutmadığı için eskisi gibi süreç içinde çalışır;
`orchestrator_apply` yetkili bir komuttur ve motorun ortak ucunda sunulmaz. `integrations set İSTEMCİ=on` (ya da masaüstü uygulamasının paneli) AI aracının ayarına kurulu programı
gösteren bir girdi ekler: `rorch.exe mcp`. Başka girdiler korunur; kapatınca ve kaldırınca yalnızca kendi
girdisi kalkar (elle değiştirilmiş olsa da); kayıtta olmayan aynı adlı bir girdiye ve elle değiştirilmiş bir girdinin yeniden
yazılmasına izin verilmez.

OpenCode istemcisinde girdi `~/.config/opencode/opencode.json` içindeki `mcp.servers` altında
`{"type": "local", "command": [...]}` biçiminde tutulur; kaldırma ve geri alma önceki içeriği byte düzeyinde geri
yükler, diğer sunucular ve ayarlar korunur.

Sunucu, istem enjeksiyonuna uğramış olabilecek bir modelin isteğini alır. Bu yüzden MCP üzerinden
`orchestrator_task_start` ve `orchestrator_project_start` şunları reddeder:

- `worker: "custom"`, herhangi bir `command`, `apply_root`, `engine_source` — sunucu `--allow-privileged` ile
  kaydedilmedikçe. `--allow-auto-apply` yalnızca `auto_apply` reddini kaldırır. Masaüstü uygulaması ikisini de hiç vermez.
- Kişinin önceden onaylamadığı doğrulama ve `verify` komutları: `mcp_acceptance_allow` ayarındaki öneklerden biriyle
  kelimesi kelimesine başlamayan komut geçmez. Varsayılan liste boştur. Onaylı komutlar da doğrulama komutu olarak çalışır (bölüm 3).
- İzin atlayan bayraklar (bölüm 2).

Özyineleme yoktur: `RESPECTED_ORCH_CHILD` ya da `RESPECTED_ORCH_DELEGATED` tanımlıyken bütün araçlar gizlenir ve reddedilir;
sunucunun başlattığı her şey `RESPECTED_ORCH_DELEGATED=1` taşır. Çalışanlar kendi ayrı çalışma ağaçlarını düzenler; gerçek
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
- **Anahtar:** yalnızca `<veri kökü>/memory-token` dosyasındadır (`.engine-key` gibi ACL'li). `settings.json`'da, makbuzlarda, istekte, durumda, kanıtta, günlükte, hata metninde ve görev metninde yer
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
**Masaüstü ayarlar ekranı** (Ayarlar → Genel → Motor ayarları) formu motorun kendi şemasından çizer (`settings.schema`, `settings.readback`; ikisi de `read_call` listesindedir) ve yalnız değişen anahtarları yollar. `settings.apply` ekrandan **iletilmez**: ekran `settings_request` ile yalnız ister; kabuk değişikliği motora doğrulatır (`settings.validate`), sonra motorun etiketleri ve kayıtlı değerleriyle kurduğu yerel bir onay penceresi gösterir ve ancak Evet yanıtında kendi bağlantısından uygular (`settings_change.rs`). Gerekçe: bazı ayarlar WebView'ın kendi başına açamaması gereken izin anahtarlarıdır (yerel önizleme, mikrofon, ekran yakalama, konuşma tanıma programı, kabul komutu listesi). Gizli değer pencerede ve formda gösterilmez.

**Proje talimat dosyaları** (`AGENTS.md`, `CLAUDE.md`; oturum çubuğunda "Proje talimatları"): kabuğun proje klasörüne yazdığı **tek** şeydir (`files.rs` `request_write`, `write_instruction_file`). Yalnız bu iki ad, yalnız kişinin yerel seçiciyle seçtiği bir klasörün (ya da alt klasörünün) doğrudan içine, en çok 256 KB düz metin olarak yazılır; başka yere açılan bağlantı ve aynı adlı klasör reddedilir. Her kayıt, gerçek yolu gösteren yerel onay penceresinden geçer ve dosya tek adımda değiştirilir. Dosya görünümünün geri kalanı salt okunurdur.

Biçim sürümü `interfaces/migrate.py` içindeki `CURRENT` ile tutulur. Bir dosyanın biçimi değiştiğinde sürüm artırılır,
`STEPS`'e eski sürümden yenisine bir adım ve `tests/fixtures/releases/<sürüm>/` altına o sürümün yazdığı gerçek dosyalar
eklenir. `setup`/`repair` okumadan önce `migrate_data` çalışır: ilk çalıştırmada `<ad>.v<N>.bak` yedeği bırakılır,
ikinci çalıştırma byte düzeyinde hiçbir şey değiştirmez. Adım eksikse ya da dosya daha yeni bir biçimden geliyorsa
`MigrationError` ile durur; dosya ve yedek yazılmaz, veri kaybı olmaz. `CURRENT` yükseltilip `STEPS` veya fixture
eklenmezse `tests/interfaces/test_migrate.py` kırılır ve CI birleştirmez.

`settings.json` biçim 2 (beta.2): Gemini CLI kaldırıldığı için `default_worker`/`default_reviewer_tool` değeri `gemini` olan
ayarlar `agy` (Antigravity) olur ve eşlik eden model adı (`*_profile`) boşaltılır; `default_roles` ve `auto_pool` içindeki
`tool: "gemini"` atamaları (`fallbacks` dahil) aynı şekilde `agy` olur. `agy`, `antigravity` ve başka hiçbir araç, profil ya da
okunamayan metin değiştirilmez. Kaydedilen her ayar dosyası güncel sürüm numarasını taşır. beta.1'in `~/.gemini/settings.json`
içine yazdığı MCP girdisi için sahiplik kaydı varsa `gemini` istemcisi yalnızca geri alınabilir: `integrations set gemini=off` ve
`uninstall` girdiyi kaldırır, açma reddedilir; kayıt yoksa `gemini` bilinmeyen istemcidir.

## 9. Testler

| Klasör | Kapsam |
|---|---|
| `tests/engine/` | çalıştırıcı, çalışma ağaçları, Codex sonuçları, süre sınırları, Windows süreçleri, bütçe, geçmiş |
| `tests/workflows/` | MAF iş akışı, kampanyalar, rol atama |
| `tests/interfaces/` | RPP, kurulum ve hafıza bağlantısı, MCP sunucusu ve izinleri, Brain hafızası, AI aracı kayıtları |
| `tests/evals/` | değerlendirme fixture'ları, sabit SHA'lı koşucu, tekrar ve JSON rapor sözleşmesi |
| `tests/docs/` | DOC-01 kaynak/profil/ADR yapısal doğrulaması; `docs/evidence/poc/doc01_check.py` |
| `tests/packaging/` | derlenmiş exe, PATH'te Python yokken: RPP, MCP, ayrık denetleyiciyle gerçek bir yazma görevi, kabul doğrulaması |
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

- Beta yalnızca Windows'u destekler; macOS/Linux kod yolları var ama henüz doğrulanmadı.
- Claude ve Cursor çalışanları kendi onay modellerini korur. Sağlayıcının `turn.completed` olayı modeli
  bildirmediği için incelemelerde `model: null` görünür.
- Kapsam denetimi çalışmadan sonra, yamaya bakarak yapılır. İşçi işletim sistemi sınırı olmadan çalıştığı için çalışma ağacının dışına yazabilir;
  bunu motor engellemez, ajanın kendi izin kipi sınırlar. Kapsam dışı değişiklik yamaya girmez ve sonucu reddettirir.
- Sohbet oturumları (`session.*` IPC komutları, `engine/chat_session.py`, `engine/session_control.py`) yalnız `opencode run --standalone
  --format json` akışını eşler; diğer CLI'lar açıkça reddedilir. Süreç motorun kullanıcısı olarak çalışır. Her tur için dosya değiştiren/komut çalıştıran/ağ araçları, oturumun **izin kipi** açmadıkça reddedilir (aşağıda), proje yapılandırması yok sayılır, çalışma dizini
  `PWD` ile verilir, süreç `RESPECTED_ORCH_CHILD=1` ile işaretlenir (insan onayı veremez), `.cmd` shim'i çalıştırılmaz. Akıştaki her
  olay güvenilmeyen veridir; oturumda `approve` komutu yoktur (onaylar yalnız onay merkezinde). Canlı oturumlar süreç içidir; konuşma kayıtları
  (`chat/sessions.json`) yeniden başlatmada kalır ve `continue_conversation` ile sürdürülür. `interrupt` süreç ağacını öldürür; tur sonucu `session.events` ile okunur.
  **İzin kipleri (KALAN_ISLER 4.6; 10–11 Kasım 2026'da ücretsiz modelle gerçek koşularla ölçüldü):** \chat_session.MODES\ üç kip tanır: \default\ (salt okunur),
  \ccept-edits\ (\edit\; edit/write/patch'i kapsar), \ypass-permissions\ (kabuk, ağ ve alt görev de açılır). Kip, tur ortamında CLI v2'nin **sıralı \permissions\**
  kurallarına çevrilir (son eşleşen kural kazanır): önce her şeyi reddeden ya da açan \*\ kuralı, sonra kipin eylemleri (ead\, \glob\, \grep\; \ccept-edits'te \edit\),
  en sonda \ALWAYS_DENIED\. \sk\ etkileşimsiz turda reddedildiği için soran bir kip ve \uto\ yoktur. Model yazımlı JavaScript çalıştıran \execute\ ile
  CLI'ın kendi araçları (\opencode_worktree_*\, \opencode_session_*\, \opencode_models\, MCP okuma) **her kipte kapalıdır**; joker eylem onları gizlemediği için adları
  açıkça reddedilir ve \execute\ yasağı Code Mode'u tümüyle kaldırır. 11 Kasım 2026 ölçümü: bu adlar araç kataloğunda görünse de çağrı \TOOL_UNAVAILABLE\ döndü.
  Kipi yalnız kişi seçer: \default\ dışı kiple başlatma ve \session.mode.set\ \TERMINAL\ sınıfındadır (tanınan masaüstü ve insan kökeni), MCP kökeni ve işçi soyu seçemez;
  akıştaki hiçbir şey kipi değiştiremez. Kip turlar arasında değişir ve konuşmayla birlikte kaydedilir: sürdürülen konuşma kendi kipini geri yükler, açıkça verilen kip bunu ezer. Açık kipte ajan gerçek proje
  klasörüne yazar; motor yalıtım eklemez.
  **Canlı akış (ADR-034):** ajanın çıktısı satır satır okunur; her olay turun `live` listesine girer ve abonelere bildirilir. Abonelik ayrı bir
  boru bağlantısıdır: `events.subscribe {project_id}` yanıtından sonra o bağlantıdan yalnız motor yazar (`session.event`, `session.state`; `id` taşımaz),
  istemciden bir şey okunmaz. Abone yalnız kendi `project_id`'sinin oturumlarını duyar; komut `READ` sınıfıdır, `CHILD` kökeni abone olamaz. Geride kalan
  abone (2000 bekleyen bildirim) kesilir ve durumu yeniden okur. Bildirimdeki her olay da güvenilmeyen veridir ve hiçbir yetki taşımaz. Masaüstünde akışı
  kabuk açar (`engine_subscribe`) ve bildirimleri yalnız `main` penceresine iletir; sohbet ekranı motoru yoklamaz. Konuşma geçmişi sayfalıdır
  (`session.transcript` `before`/`limit`; varsayılan 50 tur).
  **Ajanın kendi terminali (ADR-035, motor tarafı):** her terminal ayrı, kopuk bir süreçte yaşar (`rorch _pty-host`, `engine/pty_host.py`); sözde konsolu
  (ConPTY, `engine/conpty.py`) o tutar, bu yüzden motor ya da masaüstü kapansa da terminal çalışır. Bu, `winproc`'tan geçmeyen tek süreç başlatmadır
  (sözde konsol pencere açmaz). Sunucunun kendi borusu yalnız geçerli kullanıcıya açıktır ve yalnız o veri kökünün kalıcı motorunu kabul eder; port yoktur.
  Canlı terminaller `state/terminals.json`'da tutulur. `terminal.start|input|resize|kill|attach` `TERMINAL` yetki sınıfındadır (yalnız tanınan masaüstü ve
  insan kökeni; terminale yazmak kullanıcı adına komut çalıştırmaktır), `terminal.list` `READ`. `terminal.attach` bağlantıyı o terminalin çıktı akışına çevirir;
  baytlar programın kendisinindir, motor yorumlamaz. Terminaldeki ajan proje klasöründe, kendi izin kipiyle ve `RESPECTED_ORCH_CHILD=1` ile çalışır;
  motor yalıtım eklemez. `terminal.start` isteğe bağlı `mode` alır; yalnız ajanın kendi CLI'ında doğrulanmış bayrağı olan kipler geçerlidir (`mode=None` / `default`
  bayrak eklemez, bilinmeyen kip `MODE_UNSUPPORTED` döner) ve kayda yazılır. Sohbetten geçişte konuşmanın kipi CLI'da karşılığı varsa terminale taşınır; yoksa terminal
  ajanın kendi salt okunur başlangıcıyla açılır. Masaüstünde bölme xterm.js'tir ve **WebGL çizicisiyle** çalışır: uygulamanın CSP'si (`style-src 'self'`) değişmedi, varsayılan çizicinin
  eklediği stil öğeleri engellenir. Akışı kabuk açar (`terminal_attach` / `terminal_detach`) ve yalnız `main` penceresine iletir; yazılanlar `session_call`
  üzerinden `terminal.input` olarak gider. Terminalin çizdiği her şey programın kendi baytlarıdır ve yalnız terminal öykünücüsüne verilir.
  **Sohbetten terminale geçiş** `terminal.start {session_id}` iledir: yalnız boştaki ve ajanın kimlik verdiği oturum geçer, terminal aynı ajan oturumuyla açılır
  (`terminals.RESUME_ARGS`; bugün yalnız `opencode`), sohbet tarafı terminal ayağa kalktıktan sonra bırakılır ve kayıtlı konuşma olarak kalır.
  **Masaüstü yalnız görsel katmandır.** Varsayılan ajan/model, geçerli model denetimi (başlatma ve `session.defaults.set` modeli ajanın kendi listesine
  karşı doğrular), konuşma geçmişi, başlık, oturum-klasör eşlemesi, sıralama ve token/maliyet toplamları motorda hesaplanır ve saklanır
  (`engine/session_store.py`, veri kökünde `chat/sessions.json`); masaüstü bunları çizer ve kullanıcının seçimini iletir. Tarayıcı depolaması
  yalnız görünüm tercihlerini (tema, kenar çubuğu, grup sırası, sıralama ölçütü) tutar; `desktop/tests/engine_owns.test.ts` bunu denetler.
  **Motor komutlarının tek tablosu `engine/catalog.py`'dir (ADR-032):** yerel API'nin komut listesi, `rorch session`, `orchestrator_session_*`
  ve kabuğun iletebildiği komut listeleri (`desktop/src/contracts/catalog.ts`, `desktop/src-tauri/src/catalog.rs`; üretilir, elle düzenlenmez,
  `tests/engine/test_local_api.py` ayrışmayı yakalar) ondan kurulur. Kabuğun izin listesi derleme zamanında sabittir, çalışırken motordan alınmaz.
  **Ekranların kaynağı (sahte veri yoktur; veri yoksa boş durum, motora ulaşılamazsa hata çizilir):** Sohbet ve sağ paneller `session.*`,
  `session.models`, `capabilities.inventory` ve yalnız seçilen klasörde `list_dir`/`read_text_file`; Görevler ve Gelen kutusu `runs.list`
  (Gelen kutusu: başarısız, yarıda kalan, bozuk kayıtlar); Projeler `projects.list`; Etkinlik `activity.list` (en yeni 100 olay); Ajanlar ve
  ekipler `team.view`; Bütçe ve başarı `analytics.summary`; MCP ve beceriler `capabilities.inventory`. İnceleme ekranı yoktur: `review.view`
  yalnız yerel onay penceresi içindir (bu, `KALAN_ISLER.md` 1.7 ile değişecek).
  Dosya ağacı ve seçili klasör izni kabukta kalır: izin kullanıcının yerel klasör penceresindeki seçimidir ve motora vekâlet edilemez.
  **`.worktreeinclude` (`lanes.copy_worktree_includes`):** proje kökünde bu dosya varsa, hem gitignore'da olan hem de dosyadaki bir desene
  (`.gitignore` sözdizimi) uyan dosyalar yeni çalışma ağacına kopyalanır; Claude Code ve Codex'in ortak kuralıdır. Dosya yoksa hiçbir şey
  kopyalanmaz ve gitignore'daki dosyalar çalışma ağacına girmez. Kopyalar çalışma ağacında da gitignore'da kaldığı için temel commit'e ve
  dışa aktarılan yamaya girmez. Sembolik bağlar atlanır; 500 dosya ya da 50 MB aşılırsa çalışma ağacı açılmaz. Bu, kullanıcının kendi
  deposuna yazdığı açık bir izindir: adı geçen sırlar (ör. `.env`) işçinin okuyabildiği klasöre girer.
  **Pano şeridi saklanmaz, türetilir (`read_model.lane_of`):** `runs.list` her satırda `lane` (`needs_you`, `working`, `ready`, `archive`) ve
  `display` verir; ikisi de her okumada koşunun kendi dosyalarından hesaplanır (durum, boş olmayan `worker.patch`, `applied.json`,
  `apply-failed.json`). Doğrulanmış ama uygulanmamış değişiklik `ready` / `awaiting_approval`'dır; başarısız, yarıda kalan, bozuk kayıt ve
  başarısız uygulama `needs_you`'dur. Ekran kartı sürükleyip durum değiştiremez; karttan yalnız `task.cancel` ve `task.retry` istenir.
  **Görev komutları (`task.start`, `task.status`, `task.cancel`, `task.retry`):** tek görev koşusunu motor üzerinden başlatır ve izler; kayıtlar
  `rorch create/start` ve süreç içi MCP araçlarının yazdığı kayıtlarla aynıdır (`runner.create_task`, `start_task`), yani üç yüz aynı koşuları
  görür. Masaüstündeki "Yeni görev" formu ve `rorch task` bu komutları kullanır. Terminaldeki operatör (`HUMAN`) dışındaki her çağıran için MCP
  kuralları motorda uygulanır: `custom` işçi, `command`, `apply_root`, `engine_source` reddedilir; kabul komutları yalnız kullanıcının
  `mcp_acceptance_allow` listesindeki öneklerle başlayabilir. İşçi soyundan gelen bağlantı (`CHILD`) hiçbirini çağıramaz. Onay ve uygulama
  bu komutlarda yoktur.
  **Ajan tanımı (`agent.describe`, ADR-033, `engine/agent_describe.py`):** bir ajan CLI'ının ne olduğunu ve neyi desteklediğini her ajan için
  aynı biçimde verir: hazırlık (kurulum, giriş, `ready` / `not_ready` / `unknown`), arayüzler (`chat`, `terminal`, `handoff`), yetenek
  bayrakları (Orchestrator.inc'in adlarıyla), izin kipleri (dört ortak ad + ajanın kendi adı), model seçimi, komutlar, bağlam. Her alan
  `native` / `unsupported` / `unverified` durumu ve kaynağı (`probe` / `doc` / `none`) taşır; `native` yalnız yüklü CLI'ın kendi yardım
  metninde bu makinede görülünce verilir, sürüm doğrulanan tabandan eskiyse verilmez. Yalnız salt-okunur yoklamalar çalışır (`--version`,
  `--help`, giriş durumu); ajan başlatılmaz. Sohbet arayüzü yalnız akışı gerçekten doğrulanmış ajanda (`chat_session.SUPPORTED`) `native`'dir.
  `modes` CLI'ın kendi kip bayraklarıdır; sohbetin izin kipleri ayrı `chat_modes` alanındadır ve `session.defaults.modes` ile aynıdır. Komut listesi ve bağlam canlı oturum ister; o zamana kadar boş ve `unverified` kalır. Ekran yalnız bu cevabı çizer: yeni sohbet
  sayfası varsayılan ajanın durum satırını buradan gösterir. Eski `capabilities.matrix` komutu ve `capability_matrix.py` bununla kalktı.
  `session.models` (salt okunur) ajan CLI'ının kendi `models` çıktısını döndürür; yalnız `sağlayıcı/ad` biçimindeki satırlar kalır ve
  ajan CLI'ını çalıştırır. Sohbet ekranı model listesini, token kullanımını (`usage`
  olayları), planı (`todowrite` araç çağrısı), okunan/değişen dosyaları (araç girdileri) ve sağ paneli yalnız bu yanıtlardan ve
  `session.transcript` sayfalarından ve akış bildirimlerinden üretir; motorun vermediği hiçbir değer (bağlam yüzdesi gibi) çizilmez. Eklenen dosya yolları mesaj
  metninin içinde (`@yol`) gider; oturum komutları yalnız metin alır. Proje/dosya seçimi Tauri'nin yerel iletişim kutusuyla
  (`pick_folder`, `pick_files`; yalnız bu iki uygulama komutu `main` penceresine izinlidir, `dialog`/`fs` eklenti komutlarının
  hiçbiri hiçbir pencereye verilmez) yapılır.
- Kurucu üretimde güvenilir bir Authenticode sertifikasıyla imzalı değildir. İmza/doğrulama hattı gerçek bir
  self-signed test sertifikasıyla kanıtlanmıştır; üretim sertifikası ve zaman damgası operasyonel bağımlılıktır
  (`KANIT_LOG.md` §REL-01).

## 11. Kanıt görünümü, GitHub sınırı ve yayın kapıları

- **Kanıt görünümü (UX-01/UX-02):** `interfaces/evidence_view.view` imzalı `request/status/result` kayıtlarını
  yalnızca okur; patch SHA'sı ve proje parmak izi değişmişse `stale`, imza geçersizse hata üretir. Görünüm
  redakte edilir, ortam secret'ları çağrı anında maskelenir ve maliyet bilinmiyorsa `unknown` kalır. RPP
  `evidence.view` ile CLI `evidence <run_id>` aynı JSON'u döndürür; hiçbir yazma yapılmaz. Masaüstü uygulaması çalışma kanıtını bu API'den (`evidence`, salt-okunur izin listesi) okur; şema 2 `delivery` (taslak PR + son CI) ekler, v1 alanları aynıdır (FIX-03C).
- **İnsan onayı (UX-03):** Decision Center yeni onay yetkisi açmaz. `maf-approve` yalnızca etkileşimli TTY'de,
  patch SHA'sına, proje parmak izine ve onay anındaki git HEAD'ine bağlı olarak çalışır; MCP/agent onayı, replay,
  ekran drift'i, eski sonuç ve review sonrası değişen HEAD reddedilir.
- **GitHub sınırı (GH-01/02/03):** `interfaces/github_connector` issue'yu salt-okunur ve güvenilmeyen plan
  girdisi olarak alır; taslak PR yalnızca imzalı `completed` kanıt ve açık `operation_id` ile açılır; CI
  düzeltmesi round/SHA/reviewer/onay sınırlarına tabidir. Merge komutu üretilmez. Adaptör RPP
  `github.issue_import|pr_plan|pr_create|ci_plan|ci_ingest|ci_poll` ve CLI `github-import-issue|pr-plan|pr-create|ci-plan|ci-ingest|ci-poll`
  yüzeyine bağlıdır; `pr_create` açık `operation_id`, `confirm: true` ve operatör `project_root` ister.
  `pr_create` PR'ı geri okur: açık taslak ve başı doğrulanmış commit olmalı, yoksa hata verir ve makbuz yazılmaz; makbuz `pr_number` ve
  `head_sha` taşır. CI geri bildirimi yoklama (`ci_poll`, `gh api`) ya da stdin'den webhook içe aktarma (`ci_ingest`, HMAC
  `X-Hub-Signature-256`, sır `RESPECTED_GITHUB_WEBHOOK_SECRET`) ile gelir; dinleyici açılmaz (ADR-020). Eski/yanlış commit, tekrar,
  sırasız, bilinmeyen durum reddedilir. **Sınır:** gerçek uzak PR ve canlı check-run bu depoda henüz denenmedi; bu bir test
  deposu ve belirteç ister (ROADMAP FIX-03A/B).
- **Salt-okunur MCP denemesi (EXT-02):** `interfaces/mcp_client.StdioMcpClient` gerçek alt süreçle JSON-RPC
  `initialize`, `tools/list` ve `tools/call` yapar; süreç gizli pencerede başlar, zaman aşımı/bayt sınırı ve
  protokol hataları fail-closed'dır. `readonly_probe` yalnızca manifestte `read` izinli `mcp.context`
  aracını çalıştırır (`build_args` ile sunucunun kendi parametre adı verilir); yol kaçışı, sağlayıcı yokluğu ve secret
  sızıntısı fail-closed'dır. Tool çıktısı güvenilmeyen veridir. Belirli bir MCP sunucusuna bağımlılık yoktur; canlı
  doğrulama context-mode `ctx_search` ile yapıldı (`CONTEXT_MODE_SERVER=<start.mjs>` ile açılan test).
- **Yayın kapıları (REL-01/REL-03/REL-04):** Authenticode doğrulaması fail-closed'dır; sertifika yoksa artefakt
  imzasız kalır ve `--require-signed` başarısız olur. `signtool sign /fd SHA256` hattı self-signed test
  sertifikasıyla gerçek kurucu üzerinde doğrulandı; tampered ve yanlış imzalayan reddedildi. Üretim sertifikası
  yoktur. `health` yanıtındaki `wizard` salt-okunur ilk-görev rehberi verir. Platform kapısı yalnızca Windows'u GA
  sayar; gerçek fixture matrisi Windows 10/10 pass, Linux 7 blocked (no-go), macOS koşulmadı (no-go) sonucunu
  verir (`docs/adr/ADR-008-platform-parity.md`).
