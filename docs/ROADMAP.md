# Orchestrator: gelecekte yapılacaklar

> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Beta.2 Öncesi Kalan Kritik Düzeltmeler

Bu bölümdeki dört düzeltme (FIX-01..FIX-04; FIX-03 üç alt görev) **beta.2 yayın kapısına dahildir**; biri bile açıksa beta.2
yayınlanmaz. Hiçbiri henüz uygulanmadı; kutular yalnızca "Tamamlanma kanıtı" üretildiğinde işaretlenir. Mevcut GH-01/02/03,
UX-01/02/03, EVAL-02/03 ve SEC-01..04 işleri tamamlandı sayılır ve yeniden açılmaz; aşağıdaki görevler onların **bıraktığı
açıkları** kapatır (kaynak: ilgili `KANIT_LOG.md` "Kalan risk" satırları). Mevcut görev kimlikleri yeniden numaralanmaz.
Dosya yolları depo kökünden verilir; `(Hub)` = `respected-hub` deposu.

**Ölçümler yapıldı, düzeltmeler yapılmadı (5 Kasım 2026).** Kararlar ADR-017..020'dedir; ham kanıt
`docs/evidence/poc/` altındadır (`fix01_hosted_probe.log`, `fix01_hosted_followup.log`, `fix01_deelevate_probe.py`,
`fix04_verify_appcontainer_probe.py`, `fix04_results.json`, `fix04_toolchain_probe.py`, `fix04_toolchain_results.json`).
Bu ölçümler bir seçeneğin çalıştığını ya da çalışmadığını gösterir; hiçbiri bir güvenlik açığını kapatmış ya da bir
görevi tamamlamış sayılmaz. Bugünkü kod ve CI aynen eskisi gibidir: hosted CI AppContainer vakalarını atlar,
verify hâlâ ağa çıkabilir (S-24 "Yok"), Hub `evidence.view` kullanmaz, gerçek PR/canlı CI denenmemiştir.

### Uygulama sırası ve bağımlılık

| Sıra | Görev | Öncelik | Zorunlu bağımlılık | Paralel yürüyebilir |
| --- | --- | --- | --- | --- |
| 1 | FIX-01 CI güvenlik koşusu | P0 | yok | FIX-02, FIX-03, FIX-04 ile |
| 2 | FIX-04 verify ağ izolasyonu | P1 | yok (tasarım/kod). Nihai CI kanıtı FIX-01 manifest hattını kullanır | FIX-02, FIX-03 ile |
| 3 | FIX-02 gerçek ajan benchmark | P1 | yürütücü/adaptör yok. *Nihai sonuç koşusu* FIX-01 ve FIX-04 sonrası | FIX-03 ile |
| 4 | FIX-03A → FIX-03B → FIX-03C | P1 | 03B, 03A'nın PR/commit eşlemesine bağlı; 03C'nin `evidence.view` bağlantısı bağımsız, PR/CI gösterimi 03B'ye bağlı | FIX-01/02/04 ile |

Bağımlılıklar yalnızca *nihai kanıt koşusu* içindir; geliştirme işlerinin hepsi aynı anda başlayabilir.

### Beta.2 Release Gate

Aşağıdakilerin **tamamı aynı yayın commit SHA'sı** için kanıtlanmadan beta.2 etiketi atılmaz (kanıt başka commit'e aitse geçersizdir):

- [ ] FIX-01: Windows güvenlik matrisi yükseltilmemiş ortamda gerçekten koştu; `skipped = 0` ve `failed = 0` (tek istisna: ADR-017'de adıyla çıkarılan Cursor testi, manifestte `excluded` altında listeli); kanıt manifesti commit SHA'sını taşıyor.
- [ ] FIX-04: ağ-kapalı verify negatif matrisi %100 geçti; izin politikası kurulamazsa verify koşmadı; S-24 satırı güncellendi.
- [ ] FIX-02: ≥10 görev x ≥3 tekrar x 2 kol gerçek ajan koşusu tamam; rapor makine okunur, commit/model/ortam kayıtlı; altın çözüm hiçbir gerçek koşuda kullanılmadı; güvenlik ihlali ayrı metrik.
- [ ] FIX-03A: test reposunda gerçek taslak PR açıldı; otomatik merge yok.
- [ ] FIX-03B: imza, idempotensi, yanlış-commit reddi ve sırasız olay testleri geçti.
- [ ] FIX-03C: Hub güncel kanıtı gösteriyor, eski/geçersiz kanıtı reddediyor; insan onayı sözleşmesi (UX-03, ADR-004) bozulmadı.
- [ ] Regresyon: `python tests/tools/run_ci.py` ve `tests.interfaces.test_human_approval_contract` geçti.
- [ ] `KANIT_LOG.md` her FIX için girdi içeriyor (kapsam, komut, gerçek çıktı, SHA-256, kalan risk).
- [ ] Hiçbir güvenlik politikası gevşetilmedi; güvenlik adımlarında `ORCH_ALLOW_ELEVATED_SKIP` kullanılmıyor.

---

### FIX-01 — GitHub CI AppContainer güvenlik testlerinin atlanmasını engelle

- [ ] **Öncelik:** P0 — Kritik. **Beta.2'yi bloke eder: Evet.**
- **Mevcut sorun / kanıt kaynağı (kodda doğrulandı):**
  - `.github/workflows/ci.yml` (üç adım): `ORCH_ALLOW_ELEVATED_SKIP: "1"` ile worker matrisi, frozen exe matrisi ve tam keşif çalışıyor.
  - `tests/engine/test_worker_security.py:101` ve `tests/packaging/test_frozen_security.py:127`: yükseltilmiş oturumda `skipTest`. İlkindeki yorum "de-elevated CI step"ten söz ediyor; **`ci.yml`'de böyle bir adım yok.**
  - `tests/tools/run_ci.py` + `tests/elevated_ci_skips.txt` (109 test kimliği; `test_worker_policy.RealSandboxTests`, `test_runner`, kampanya/proje testleri dahil) yükseltilmişken atlanıp CI yeşil kalıyor.
  - `tests/engine/test_security_gate.py::test_ci_runs_worker_and_verify_matrices_as_separate_required_steps` yalnızca `ci.yml` metninde komut dizilerinin geçtiğini ve `continue-on-error` olmadığını denetliyor; testlerin koştuğunu/atlanmadığını denetlemiyor.
  - Sonuç: AppContainer sınırı (SEC-03/SEC-04) hosted CI'da ölçülmeden CI yeşil görünebilir. SEC-04 kanıtı yerel, yükseltilmemiş koşuya dayanır.
- **Hedeflenen davranış:** Zorunlu güvenlik matrisi gerçekten çalışmadan yayın kapısı geçemez; skip, timeout, runner hatası veya sandbox başlatılamaması **kırmızıdır**.
- **Mimari değişiklikler:**
  - **Karar verildi: `docs/adr/ADR-017-ci-security-run.md`.** Hosted runner'da ölçüldü (`docs/evidence/poc/fix01_hosted_probe.log`): runner belirteci yükseltilmiş; belirteci kısıtlayarak de-elevate etmek `TokenElevation`'ı temizlemiyor (**çalışmaz**); ama iş içinde oluşturulan geçici **standart yerel kullanıcı** altında `_is_elevated()` False ve AppContainer matrisi 13 testin 12'sini geçti, 0 hata (1 skip: Cursor CLI yok). Self-hosted runner gerekmez; maliyet 0 (public depo). Uygulama: güvenlik adımı bu kullanıcı altında koşar.
  - Güvenlik adımlarından `ORCH_ALLOW_ELEVATED_SKIP` kaldırılır; yükseltilmiş oturum adımı **fail** eder.
  - Test koşusu makine okunur sonuç üretir (`tests`, `passed`, `failed`, `skipped`, `errors`, `commit_sha`, `runner`, `elevated`) ve artefakt olarak yüklenir.
  - `test_security_gate.py` YAML denetimine ek olarak bu manifesti doğrular.
- **Etkilenecek modüller/dosyalar:** `.github/workflows/ci.yml`, `tests/tools/run_ci.py`, `tests/elevated_ci_skips.txt` (güvenlik kimlikleri için kullanılmaz), `tests/engine/test_security_gate.py`, `tests/engine/test_worker_security.py`, `tests/packaging/test_frozen_security.py`, `tests/engine/security_cases.py`, `docs/THREAT_MODEL.md`. `src/respected_orchestrator/engine/appcontainer.py` politikası gevşetilmez.
- **Teknik alt görevler:**
  - [x] Yükseltilmemiş ortam seçeneklerini ölç ve karar ver (ADR-017, ölçüm kaydı `fix01_hosted_probe.log`). *Bu kutu yalnızca ölçüm/karar içindir; FIX-01'in kendisi tamamlanmadı.*
  - [ ] Geçici standart kullanıcıyı workflow'da kur. Ölçüldü (`fix01_hosted_followup.log`): yetki yalnızca çalışma alanı + Python kurulum dizinine verilince 16 sn, matris 50 sn, 13 testten 12 geçti, 0 hata, 1 skip.
  - [ ] Cursor'a bağlı `test_node_worker_can_start_piped_children_and_resolve_paths` **karar verildi**: zorunlu güvenlik kümesinden adıyla çıkarılır, manifestte `excluded` altında gerekçesiyle listelenir, yalnızca Cursor CLI'ı olan yerel makinede koşar (ADR-017). Başka skip yoktur ve olamaz.
  - [x] Hosted `git` `rc=128` sebebi ölçüldü: `fatal: could not open '/dev/null' ... Permission denied` (runner git 2.56.0; yerelde git 2.55.0 çalışıyor; sürüm mü görüntü mü **ayrıştırılmadı**). Sonuç: verify komutları `git`'e güvenemez; motorun kendi git çağrıları sandbox dışındadır (ADR-018 §4). *Kutu yalnızca ölçüm içindir.*
  - [ ] **Açık (ölçülmedi):** hosted `git` farkının asıl sebebi (git sürümü 2.56.0 vs 2.55.0 mi, runner görüntüsü mü). Yerelde aynı sürüm çiftiyle ayrıştır; çözülmezse "verify içinde git desteklenmez" kalıcı uyumluluk listesine yazılır.
  - [ ] **Açık (ölçülmedi):** ölçüm tek runner görüntüsünde (`windows-2025-vs2026`, 20261030.294.1) yapıldı. Manifest görüntü sürümünü kaydeder; görüntü değişince güvenlik koşusu yeniden doğrulanır ve fark kırmızı yakalanır.
  - [ ] Zorunlu güvenlik test kümesini `security_cases.py`'den türet (21 negatif, 9 izinli vaka) + `RealSandboxTests` + frozen matris.
  - [ ] Güvenlik adımlarından skip yolunu kaldır; yükseltilmiş/başlatılamayan/timeout durumunu fail ettir.
  - [ ] Manifest üret; `skipped != 0` veya beklenenden az test → kapı kırmızı.
  - [ ] `test_security_gate.py`'yi manifest doğrulayacak şekilde genişlet (mevcut YAML denetimi korunur).
  - [ ] Güvenlik işini merge koruması ve beta.2 etiket kapısına zorunlu kontrol olarak bağla.
- **Bağımlılıklar:** Yok (ilk sıra). Self-hosted seçilirse runner kurulumu bağımlılıktır.
- **Testler:**
  - Pozitif: 9 izinli vaka ve meşru kapsam içi okuma/yazma geçer.
  - Negatif: 21 negatif vaka reddedilir; sarmalamasız kontrol koşusu saldırıların gerçek olduğunu gösterir.
  - Entegrasyon: CI'da gerçek koşu → manifest → kapı; manifest SHA'sı `GITHUB_SHA` ile eşleşir.
  - Regresyon/kapı: `skipped=1`, eksik test, SHA uyuşmazlığı, boş manifest, yükseltilmiş oturum, sandbox başlatma hatası ve timeout senaryolarının her biri (sahte manifestlerle birim testi) kapıyı kırmızı yapar.
- **Ölçülebilir kabul kriterleri:**
  - Zorunlu AppContainer matrisinde `skipped = 0`; pozitif ve negatif testlerin %100'ü geçer.
  - Gerçek güvenlik testi koşmadığında yayın kapısı başarısız.
  - Bilerek bozulmuş izolasyon politikası yeşil CI üretmez (kırmızı koşu kanıtı).
  - Her koşu commit SHA + test özeti + artefakt taşır.
  - Yükseltme veya sandbox hatası sessiz skip'e yol açmaz.
- **Tamamlanma kanıtı:** `KANIT_LOG.md` FIX-01 girdisi; bir yeşil ve bilerek kırmızı yapılmış bir CI koşusunun günlüğü; manifest dosyası; ilgili ADR.
- **Mevcut çözüm (tekrarlanmaz):** Ayrı güvenlik adımları, `continue-on-error` yasağı ve frozen matris SEC-04'te var; yalnızca skip yolu ve kanıt doğrulaması eklenir.

### FIX-04 — Verify sandbox ağ erişiminin sınırlandırılması

- [ ] **Öncelik:** P1 — Güvenlik. **Beta.2'yi bloke eder: Evet.**
- **Mevcut sorun / kanıt kaynağı (kodda doğrulandı):** `docs/THREAT_MODEL.md` S-24: "**Yok**; kısıtlı belirteç ağı kapatmaz"; §11 S-24'ün "hâlâ Yok" kalması gerektiğini söyler. `src/respected_orchestrator/engine/sandbox.py` başlık notu: verify/kabul kodu kısıtlı belirteçle çalışır, kullanıcı dosyalarını okuyabilir ve ağı kullanabilir. Worker tarafında ağ reddi AppContainer ile kanıtlı (`tests/engine/test_worker_policy.py::RealSandboxTests::test_network_is_denied_by_default`, `security_cases.py`); verify yolunda eşdeğeri yok. İki sınır aynı kabul edilmez.
- **Hedeflenen davranış:** Varsayılan olarak ağ kapalı verify; yalnızca açıkça yetkilendirilmiş, sınırlı istisna.
- **Mimari değişiklikler:**
  - Verify için ayrı ağ tehdit modeli (veri sızdırma, DNS tüneli, loopback servisleri, alt süreç).
  - **Karar verildi: `docs/adr/ADR-018-verify-network-isolation.md`.** Verify, worker ile aynı AppContainer yolundan ağ kapalı çalışır. Ölçüm (`docs/evidence/poc/fix04_results.json`): IP, DNS, loopback ve alt süreç çıkışı engellendi; Python/unittest/git/node/cmd çalıştı. Güvenlik Duvarı/WFP yönetici gerektirdiği için reddedildi.
  - Ağ istisnası **ya hep ya hiç**: AppContainer'ın `internetClient` yeteneği host bazında süzemez; yönetici olmadan host/port izin listesi OS düzeyinde uygulanamaz. İstisna görev başına, insan onaylı ve kanıt paketine yazılır (ADR-007 ile uyumlu). "Yalnızca şu host'a" vaadi verilmez.
  - Politika kurulamazsa güvenilmeyen verify **çalışmaz** (fail-closed). `RESPECTED_ORCH_SANDBOX=off` yolu ağ garantisi vermez; bu bağlamda reddedilmeli ya da açıkça "ağ korumasız" işaretlenmelidir.
- **Etkilenecek modüller/dosyalar:** `src/respected_orchestrator/engine/sandbox.py`, `sandbox_exec.py`, `appcontainer.py`, `worker_policy.py`, `winproc.py`, `engine/runner.py` (acceptance/verify çağrıları), `workflows/project.py` (proje verify), `tests/engine/test_sandbox.py`, `tests/engine/security_cases.py`, `docs/THREAT_MODEL.md` (S-24, §11), `docs/ARCHITECTURE.md`, `docs/evidence/KANIT_LOG.md`.
- **Teknik alt görevler:**
  - [x] Verify ağ tehdit modeli ve teknoloji karşılaştırması (ADR-018, `fix04_verify_appcontainer_probe.py`). *Yalnızca ölçüm/karar; FIX-04'ün kendisi tamamlanmadı.*
  - [ ] Verify/acceptance çağrılarını (`engine/runner.py`, `workflows/project.py`, `sandbox.py`) AppContainer yoluna taşı; OS düzeyinde varsayılan-kapalı ağ.
  - [ ] Çıkış denemeleri: DNS adı, doğrudan IP, localhost/loopback, alt süreç ve özyinelemeli alt süreç.
  - [ ] Politika kurulamazsa fail-closed (yapılandırılmış hata; verify koşmaz).
  - [ ] Yetkilendirilmiş ağ istisnası (görev başına, insan onaylı, hep-ya-hiç) ve testleri: onaysız istek reddedilir, onay yalnızca o görevde geçerli, kanıtta `network: allowed` görünür.
  - [ ] Araç uyumluluk testi (ölçülen sonuçlar ADR-018'de): `.cmd` shim reddi; `npm test` desteklenmez (npm sürücü kökünü `lstat` eder); `sys.prefix` dışı venv yalnızca onaylı `extra_readonly_roots` ile; `default_policy` `Program Files` altındaki `command[0]` dizini için ACL denemesi yapmamalı (bugün `SandboxStartError` verir); hosted'da `git` çalışmaz.
  - [ ] **Açık (ölçülmedi):** Python/node/cmd dışındaki araç zincirleri (ör. pytest ve eklentileri, derleyiciler, pip kurulu araçlar) AppContainer'da denenir; sonuç "desteklenir / desteklenmez" uyumluluk listesine yazılır. Listede olmayan araç için "çalışır" denmez.
  - [ ] S-24 yeniden sınıflandırma ve §11 "Yok kalmalıdır" cümlesinin güncellenmesi (yalnızca testler geçtikten sonra).
- **Bağımlılıklar:** Tasarım/kod bağımsız. Nihai CI kanıtı FIX-01 manifest hattına bağlanır (ağ negatifleri güvenlik matrisine girer). FIX-02'nin Orchestrated kol nihai koşusu bunu bekler.
- **Testler:**
  - Pozitif: ağ gerektirmeyen mevcut kabul/verify akışları değişmeden geçer; onaylı istisna yalnızca o görevin verify'ında ağı açar.
  - Negatif: dış IP, dış DNS, loopback servisi, alt süreç/özyinelemeli alt süreç reddedilir; sarmalamasız kontrol saldırının gerçek olduğunu gösterir.
  - Entegrasyon: `runner` acceptance ve `workflows/project` verify aynı politika ile koşar; politika kurulamazsa ikisi de çalışmaz.
  - Regresyon: `tests.engine.test_sandbox`, `test_runner`, `test_project*`; engine key koruması (S-01..S-04) bozulmaz.
- **Ölçülebilir kabul kriterleri:** İzinsiz dış ağ bağlantısı kurulamaz; yasak DNS/IP engellenir; alt süreç aşamaz; politika kurulamazsa güvenilmeyen kod çalışmaz; onaylı ağ istisnası yalnızca onaylanan görevde ve kanıtta görünür biçimde çalışır; tüm negatif ağ testleri geçer; diğer kabul/verify iş akışlarında regresyon yok.
- **Tamamlanma kanıtı:** `KANIT_LOG.md` FIX-04 girdisi (S-24 yeniden test sonucu, gerçek çıktı, SHA-256), güncellenmiş THREAT_MODEL satırı, spike karşılaştırma notu, CI manifestinde ağ vakaları.
- **Ölçüldü (yerel + hosted, ADR-018):** Python, unittest, node, cmd AppContainer içinde çalışır; ağ kapalıdır. `npm.cmd` shim politikasıyla, `node npm-cli.js test` ise sürücü kökü `lstat` EPERM'iyle çalışmaz. Venv yalnızca kökü salt-okunur verilince çalışır. `git` yerelde çalışır, hosted'da çalışmaz. **Henüz ölçülmeyen:** Python dışı/venv dışı başka araç zincirleri (ör. pytest eklentileri, derleyiciler); bunlar için "çalışır" denmez.

### FIX-02 — Gerçek AI ajanlarıyla karşılaştırmalı benchmark

- [ ] **Öncelik:** P1 — Yüksek. **Beta.2'yi bloke eder: Evet.**
- **Mevcut sorun / kanıt kaynağı (kodda doğrulandı):** `tests/evals/compare.py`: Orchestrated kolda `fixture.fixed_source` doğrudan `solution.py`'ye yazılır; Direct kolda hiçbir şey yapılmaz; `model="golden-fixture"`, `security_violation` sabit `False`, `interventions` sabit 0. `KANIT_LOG.md` EVAL-02/EVAL-03 "Kalan risk": sonuç model başarısı değildir. 20 fixture (`tests/evals/fixtures.py`, sabit SHA'lar `start_shas.json`) ve rapor/regresyon kapısı (`tests/evals/report.py`) var; ADR-002 yeniden üretilebilirliği tanımlar.
- **Hedeflenen davranış:** Aynı coding agent, aynı model/sürüm/görev/başlangıç commit'i ile Direct ve Orchestrated kolda **gerçekten** çalışır; sonuç tarafsız ve tekrar üretilebilir.
- **Mimari değişiklikler:**
  - Mevcut sentetik harness **olduğu gibi kalır** ve çıktısı "synthetic" olarak etiketlenir; gerçek benchmark ayrı şema (öneri: `respected.eval.bench.v1`) ve ayrı rapor dosyası üretir. Sentetik rapor gerçek sonuç olarak sunulamaz.
  - Direct kolda ajan CLI'ı doğrudan çalışma dizininde, Orchestrated kolda aynı ajan Orchestrator görevi olarak (worker + verify + review) çalışır. Altın çözüm gerçek koşuda ajana veya sonuca hiçbir yolla verilmez; yalnızca gizli kabul komutu kullanılır.
  - Adaptörler mevcut `engine/clis.py` (`SUPPORTED_AGENTS`: claude, antigravity/agy, codex, cursor, opencode, openrouter), `engine/codex.py`, `opencode_acp.py`, `openrouter_worker.py` üzerinden; yeni adaptör sistemi icat edilmez.
  - Ölçümler: başarı, güvenlik ihlali (ayrı), timeout, manuel müdahale, retry, süre. Token/maliyet yalnızca ajan gerçekten raporlarsa (`engine/pricing.py`, `budget.py`); aksi halde bilinmiyor. Not: `compare.py` `"bilinmiyor"`, `evidence_view` `unknown` yazıyor; şemada tek yazım sabitlenir.
  - Güvenilirlik: görev başına ≥3 tekrar; kesin eşik yerine dağılım bilgisi raporlanır (EVAL-03'teki `shortcut` kısıtı).
  - **Karar verildi: `docs/adr/ADR-019-real-agent-benchmark.md`.** Ücretsiz yol kuralı: yalnızca marjinal maliyeti 0 olan ajan/model (ücretsiz katman modelleri, kullanıcının zaten ödediği abonelik kotası); kullanım başına faturalı API anahtarı kullanılmaz; kota/fatura belirtisinde parti durur. Temsilî görev ölçütü ADR'de tanımlı.
- **Etkilenecek modüller/dosyalar:** `tests/evals/compare.py` (dokunulmaz ya da yalnızca etiket), yeni `tests/evals/` yürütücü/rapor modülleri, `tests/evals/fixtures.py`, `start_shas.json`, `tests/evals/report.py`, `engine/clis.py` ve worker modülleri (yalnızca çağrı), `docs/evidence/poc/` sonuçları, `docs/adr/ADR-002-reproducible-evaluation.md` (güncelleme önerilir).
- **Teknik alt görevler:**
  - [ ] Gerçek benchmark yürütücüsü ve iki kol (Direct / Orchestrated).
  - [ ] Ajan adaptör katmanı (Claude Code, Codex, kurulu diğerleri); kurulu olmayan ajan `PROVIDER_MISSING` kaydedilir, uydurulmaz.
  - [ ] Eşdeğerlik: aynı model/sürüm/başlangıç commit'i/timeout/ortam; ajan sürümü ve model kimliği rapora yazılır.
  - [ ] ≥10 temsilî görev seçimi (ADR-019 §6 ölçütleriyle 20 fixture'dan; seçim ve gerekçesi rapora yazılır) ve her biri için ≥3 tekrar planı; toplam ≥ 10 x 3 x 2 = 60 koşu.
  - [ ] Güvenlik ihlali, timeout, müdahale ve retry kaydı; başarı ile güvenlik ihlali ayrı alanlar.
  - [ ] Makine okunur rapor (commit, model, ortam, ham koşular); sentetik/gerçek ayrımı; `report.py` kapısının gerçek rapora uyarlanması.
- **Bağımlılıklar:** Yürütücü/adaptör bağımsız. Nihai sonuç koşusu FIX-01 (güvenlik ihlali sayacının dayandığı izolasyon kanıtı) ve FIX-04 sonrası. **Gerçek koşular yalnızca 0 maliyetli ajan/modelle yapılır (ADR-019) ve her koşu partisinden önce kullanıcıdan onay alınır.**
- **Testler:**
  - Pozitif: sahte (stub) ajan CLI'ı ile iki kol uçtan uca koşar, rapor şemaya uyar.
  - Negatif: altın çözüm ajan girdisine/çıktısına sızarsa koşu geçersiz; eksik token/maliyet `0` yazılmaz; farklı model/commit/timeout karşılaştırması `incomparable`; kurulu olmayan ajan uydurma sonuç üretmez.
  - Entegrasyon: bir gerçek ajanla küçük keşif koşusu (kullanıcı onaylı) ve rapor doğrulaması.
  - Regresyon: `tests.evals.test_compare`, `test_report`, `test_eval_runner` değişmeden geçer.
- **Ölçülebilir kabul kriterleri:** İki kolda da gerçek ajan; altın çözüm kullanılmaz; eşdeğer başlangıç koşulları; başarı ve güvenlik ihlali ayrı; ≥10 görev x ≥3 tekrar planı hazır; ölçülemeyen değerler bilinmiyor olarak işaretli; sonuçlar commit/model/ortam ile tekrar üretilebilir; mevcut sentetik altyapı çalışır.
- **Tamamlanma kanıtı:** `KANIT_LOG.md` FIX-02 girdisi; plan dosyası; ham ve özet JSON rapor; adaptör testleri çıktısı; gerçek koşu yapıldıysa maliyet/token kaydı (ya da bilinmiyor).
- **Ölçüldü (ADR-019):** Claude Code CLI `--output-format json` makine okunur; güvenilir sayılar `modelUsage` altında, üst düzey `usage` sıfır olabilir; `total_cost_usd` liste fiyatı tahminidir. Çağrının abonelik kotasından mı ücretli krediden mi düştüğü çıktıdan anlaşılamadı, bu yüzden Claude Code kullanıcı bunu doğrulamadan varsayılan benchmark ajanı olmaz. **Belirsiz:** ücretsiz modellerin kalitesi düşük olabilir, sonuç "bu model ile ölçüm"dür; Direct kol ajanın kendi (kum havuzsuz) çalışması olduğundan güvenlik ihlali sayacı iki kolda aynı anlama gelmez, bu açıkça yazılmalı.

### FIX-03 — GitHub PR/CI ve Hub Evidence API uçtan uca entegrasyonu

Üst görev; üç alt görevin tamamı bitince işaretlenir. **Beta.2'yi bloke eder: Evet.** Öncelik P1.

- [ ] FIX-03 (03A + 03B + 03C)
- **Mevcut durum (kodda doğrulandı):**
  - GH-01/02/03 *adaptör + RPP/CLI* olarak tamamlandı: `src/respected_orchestrator/interfaces/github_connector.py` (`import_issue`, `plan_draft_pr`, `push_branch`, `create_draft_pr`, `plan_ci_fix`), ADR-014. `KANIT_LOG.md` GH-02: gerçek uzak PR **denenmedi**; GH-03: canlı CI webhook'una **bağlanmadı**, geri bildirimi çağıran taraf verir. Kaynakta webhook alıcısı veya imza doğrulaması **yok** (arandı, bulunmadı).
  - UX-01/02 tamamlandı: `interfaces/evidence_view.py`, RPP `evidence.view`, CLI `evidence <run_id>`. UX-02 "Kalan risk": Hub bu API'yi çağırmıyor. Doğrulandı: Hub `inspect` çağırıp `evidenceModel.ts` ile yorumluyor (`respected-hub/src/products/orchestrator/views/EvidencePanel.tsx:81`); `respected-hub/src-tauri/src/products/orchestrator/mod.rs:20` eylem izin listesinde `evidence` yok.
  - Bunlar duplicate değildir; kapsamları yalnızca bu açıklardır.
- **Ortak kısıtlar:** Otomatik merge yok (ADR-014 §4); onay yalnızca etkileşimli TTY (UX-03, ADR-004); Hub onay vermez/yama uygulamaz; CLI/MCP/RPP/Hub davranışı `docs/PRODUCT_CONTRACT.md` ile uyumlu kalır.
- **Toplu kabul:** gerçek PR açılır; PR/CI ↔ görev/commit eşleşir; sahte imzalı/tekrar webhook güvenli yönetilir; Hub güncel kanıtı gösterir; eski/geçersiz kanıt kabul edilmez; AI ajanı insan onayı üretemez; CLI/MCP/Hub sözleşmesi bozulmaz.

#### FIX-03A — GitHub PR gerçek entegrasyon testi

- [ ] **Öncelik:** P1. **Beta.2'yi bloke eder: Evet.** Kapsam: GH-02'nin canlı uçta kanıtlanmamış kısmı.
- **Mevcut sorun / kanıt:** `KANIT_LOG.md` GH-02 "Kalan risk".
- **Hedeflenen davranış:** İzole test reposunda doğrulanmış patch'ten gerçek taslak PR açılır; hata senaryoları güvenli sonuçlanır.
- **Mimari değişiklik:** Yeni özellik yok. Opt-in canlı test (varsayılan keşifte atlanır ve skip olarak raporlanır, yeşil sayılmaz; release kapısında zorunlu). Kimlik bilgisi kod/repo içinde tutulmaz (ADR-007).
- **Etkilenecek:** `interfaces/github_connector.py`, `interfaces/rpp.py`, `__main__.py`, yeni canlı test modülü `tests/interfaces/` altında (ad önerisi), `docs/evidence/poc/` günlükleri.
- **Alt görevler:**
  - [ ] İzole test reposu ve en düşük yetkili token ile gerçek taslak PR.
  - [ ] Branch/commit eşleştirme: PR head SHA'sı = kanıttaki doğrulanmış patch commit'i.
  - [ ] Yetkisiz token, silinmiş dal, kapalı repo, rate-limit ve API hata yanıtları (yapılandırılmış hata, kısmi push yok).
  - [ ] PR'ın doğru `run_id`/`operation_id` ile ilişkilendirilmesi; aynı `operation_id` yeniden çağrısı imzalı makbuzu döndürür.
  - [ ] Merge'in hiçbir yolla çağrılmadığının testi.
- **Bağımlılık:** Yok. Önkoşul: test reposu ve token (kullanıcı sağlar; yoksa görev "engelli" kaydedilir, sahte sonuç yazılmaz).
- **Testler:** Pozitif: gerçek taslak PR (`--draft`). Negatif: yetkisiz token, eksik `confirm`, yanlış run, secret'lı patch (mevcut testler korunur) + canlı yetkisiz çağrı. Entegrasyon: canlı uçtan uca. Regresyon: `test_github_connector`, `test_github_rpp`.
- **Kabul:** Gerçek PR başarıyla açıldı; PR ↔ görev/commit eşleşti; otomatik merge yok; yetkisiz işlem güvenli hata verdi.
- **Kanıt:** `KANIT_LOG.md` FIX-03A girdisi, PR bağlantısı, günlük, SHA-256.

#### FIX-03B — Gerçek CI webhook bağlantısı

- [ ] **Öncelik:** P1. **Beta.2'yi bloke eder: Evet.** Kapsam: GH-03'ün canlı olmayan kısmı.
- **Mevcut sorun / kanıt:** `KANIT_LOG.md` GH-03 "Kalan risk"; kaynakta webhook kodu yok.
- **Hedeflenen davranış:** CI sonuçları imzası doğrulanmış, idempotent ve doğru commit/PR/görev ile eşleşmiş olarak `plan_ci_fix` sınırlarını besler.
- **Mimari değişiklik — karar verildi: `docs/adr/ADR-020-ci-feedback-ingestion.md`.** Birincil yol `gh api` ile yoklama (gelen bağlantı/port/tünel yok, maliyet 0); webhook **dinleyicisi eklenmez**. `X-Hub-Signature-256` HMAC doğrulayıcısı ve `X-GitHub-Delivery` idempotensisi saf işlev olarak yazılır ve webhook yükünü dosya/stdin'den içe aktaran komutta (ad önerisi `github-ci-ingest`) kullanılır. Olay → PR/commit/görev eşlemesi yoklama ve içe aktarmada aynıdır. Çıktı otomatik düzeltme/yorum/merge üretmez.
- **Etkilenecek:** `interfaces/github_connector.py`, `interfaces/rpp.py`, olay deposu (mevcut imzalı kanıt düzenine uygun), testler `tests/interfaces/`.
- **Alt görevler:**
  - [ ] `gh api` ile check-run yoklaması (head SHA'ya bağlı) ve `github-ci-ingest` içe aktarma yolu.
  - [ ] İmza doğrulama; imzasız/yanlış imzalı olay reddi.
  - [ ] `success`, `failure`, `cancelled` (ve `timed_out`/`neutral`) işleme.
  - [ ] Tekrarlanan teslimatın idempotent işlenmesi (aynı delivery id → tek etki).
  - [ ] Başka commit/PR/depoya ait sonucun reddi (head SHA = görevin doğrulanmış SHA'sı).
  - [ ] Eksik, gecikmiş ve sırasız olay: eski SHA'lı olay durumu geri almaz; bilinmeyende fail-closed.
- **Bağımlılık:** FIX-03A. Gerçek doğrulama için ücretsiz public test deposu (Actions ücretsiz); gelen bağlantı gerekmez.
- **Testler:** Pozitif: geçerli imzalı başarı/başarısızlık/iptal. Negatif: sahte imza, tekrar, yanlış SHA, sırasız olay, bozuk JSON, aşırı büyük gövde. Entegrasyon: gerçek test deposundaki check-run'ın yoklanması. Regresyon: `plan_ci_fix` sınırları, `test_github_*`.
- **Kabul:** Sahte imzalı olay reddedilir; tekrar tek kez işlenir; doğru görev/commit ile eşleşir; sırasız olay güvenli yönetilir.
- **Kanıt:** `KANIT_LOG.md` FIX-03B girdisi; gerçek olay günlüğü (secret'sız); testler.

#### FIX-03C — Hub Evidence API entegrasyonu

- [ ] **Öncelik:** P1. **Beta.2'yi bloke eder: Evet.** Kapsam: UX-02'nin Hub tarafı (`respected-hub` deposu).
- **Mevcut sorun / kanıt:** Yukarıda doğrulanan `inspect` kullanımı; `KANIT_LOG.md` UX-02 "Kalan risk".
- **Hedeflenen davranış:** Hub, imzalı kanıtı doğrulayan salt-okunur `evidence.view` çıktısını gösterir; eski/geçersiz kanıt onaya hazır görünmez; Hub yeni yetki almaz.
- **Mimari değişiklik:** Hub'ın eylem izin listesine salt-okunur `evidence` eklenir; `EvidencePanel` bu çıktıyı kullanır. Gerekirse `evidence_view` şemasına diff/test özeti alanları eklenir (şema sürümü artar, eski alanlar silinmez). Onay/uygulama komutu kullanıcının terminalinde kalır (`workspaceModel.ts` açıklaması korunur).
- **Etkilenecek:** (Hub) `src-tauri/src/products/orchestrator/mod.rs`, `src/products/orchestrator/evidenceModel.ts`, `views/EvidencePanel.tsx`, `campaigns.ts` ve testleri; (Orchestrator) `interfaces/evidence_view.py`, `interfaces/rpp.py`.
- **Alt görevler:**
  - [ ] `evidence.view` çıktısını göstermek: durum, sebep, patch özeti/dosya diff'i, kontrol sonuçları, reviewer kararları, tester.
  - [ ] Kanıt durumları (geçerli, `stale`, başarısız, kurcalanmış) açık gösterilir; kanıt güncelliği/geçerliliği her gösterimde yeniden okunur.
  - [ ] Hata durumları (kilitli, bulunamadı, şema uyuşmazlığı) anlaşılır mesajla.
  - [ ] Secret/yol sızıntısı: redakte edilmemiş alan arayüze geçmez; yeni alanlar için sızıntı testi.
  - [ ] PR/CI durumunu (FIX-03A/B) görünüme bağlamak.
  - [ ] Hub'da onay düğmesi/uygulama yetkisi eklenmediğinin testi.
- **Bağımlılık:** `evidence.view` bağlantısı bağımsız; PR/CI gösterimi FIX-03B'ye bağlı.
- **Testler:** Pozitif: güncel kanıt gösterilir. Negatif: stale/tampered/şema uyuşmazlığı reddedilir; secret içeren kanıt maskelenir; onay eylemi izin listesinde yok. Entegrasyon: gerçek `evidence` çıktısı ile Hub modeli. Regresyon: `tests.interfaces.test_evidence_api`, `test_human_approval_contract`, Hub `evidenceModel` testleri, CLI/MCP davranışı.
- **Kabul:** Hub güncel doğrulama kanıtını gösterir; eski/geçersiz kanıt kabul edilmez; insan onayı ve ürün sözleşmesi bozulmaz; hassas veri sızmaz.
- **Kanıt:** `KANIT_LOG.md` FIX-03C girdisi + Hub test çıktısı ve ekran/yapılandırılmış çıktı kaydı.

---

## Yayın

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.

## Güncelleme

- [ ] beta.2 yayınlanırken o sürümün gerçek veri dosyaları `tests/fixtures/releases/0.1.0-beta.2/` altına kopyalanmalı
  (sözleşme §4). `settings.json` 1→2 taşıma adımı (`STEPS`) hazır ve beta.1 fixture'ı ile sınanıyor; sonraki biçim
  değişikliğinde yeni sürüm için yeni adım eklenir, eski adımlar silinmez.
