# Kanıt kaydı

Bu dosya tamamlanan her görevin kanıtını tutar. Kural: **kanıt yoksa görev tamamlanmış sayılmaz.**
Her giriş şu dört parçayı içerir: kapsam, değişen dosyalar, doğrulama komutu ve gerçek çıktı, kalan risk.
Plan ve sıra: `docs/ROADMAP_EXECUTION_PLAN.md`

---

## SEC-01 — Tehdit modeli ve yetki matrisi

- **Durum:** Tamamlandı (doküman görevi). Tarih: 30 Ekim 2026.
- **Kapsam:** Worker ve doğrulama katmanlarının varlıkları, güven sınırları, aktör yetkileri ve saldırı senaryolarının yazılı hale getirilmesi. Kod değişikliği yok; bu görev sonraki güvenlik görevlerinin ölçü tabanını kurar.
- **Çıktı:** `docs/THREAT_MODEL.md` — 10 varlık (A1–A10), 8 güven sınırı (B1–B8), 6 aktör için yetki matrisi, 25 saldırı senaryosu (S-01…S-25), her senaryo için sahip katman / engelleyen katman / beklenen sonuç / bugünkü durum / kanıt.
- **Mimari senkronu:** `docs/ARCHITECTURE.md` içine üç satırlık referans eklendi. Burada açıkça yazıyor: doğrulama sandbox'ı yalnızca motorun çalıştırdığı kabul/doğrulama komutlarını korur; worker süreçleri için OS düzeyinde dosya veya ağ sınırı yoktur. Normal Windows kullanıcısı desteklenir, yükseltilmiş yönetici desteklenmez (aktif ret SEC-03).
- **Değişen dosyalar:**
  - `docs/THREAT_MODEL.md` (yeni)
  - `docs/ARCHITECTURE.md` (referans + kapsam notu)
  - `docs/ROADMAP_EXECUTION_PLAN.md` (yeni, 37 görevin durum tablosu)
  - `docs/ilerleme/KANIT_LOG.md` (bu dosya)

### Doğrulama

Komut (depo kökünde):

```
python -m unittest discover -s tests -t .
```

Gerçek çıktı (30 Ekim 2026, Windows, Python 3.13.15):

```
Ran 337 tests in 596.876s

OK
```

### PoC ölçümü (gerçek çıktı)

Komut:

```
python docs/ilerleme/poc/sec01_probe.py docs/ilerleme/poc/sec01_results.json
```

| PoC | Deneme | Sonuç | Kanıt |
|---|---|---|---|
| P-01 | workspace dışındaki dosyayı okuma | ALLOWED | `TOPSECRET` okundu |
| P-02 | workspace dışına dosya yazma | ALLOWED | `write-ok`, dosya oluştu |
| P-03 | `example.com:443` TCP çıkışı | ALLOWED | `connected` |
| P-04 | worktree içindeki `.env` okuma | ALLOWED | `API_KEY=sk-fake-not-real` |
| P-05 | workspace içindeki junction üzerinden dışarı okuma | ALLOWED | `TOPSECRET` okundu |

Makine okunur çıktı: `docs/ilerleme/poc/sec01_results.json`. Sonuçlar `THREAT_MODEL.md` §8 ile aynıdır ve S-01, S-03, S-04 ve junction satırlarındaki "Yok" ifadesini doğrular. Bu bir açık kaydı değil, bilinen sınırın ölçümüdür; kapatma SEC-02/SEC-03/SEC-04.

### Kabul kriterleri

- [x] En az 12 adversarial vaka (25 vaka: S-01…S-25)
- [x] Her vaka için owner, engel katmanı ve beklenen sonuç
- [x] Windows normal kullanıcı ve admin için destek/ret kararı (§6)
- [x] Açıklanmamış güvenlik vaadi 0 (§7 denetimi)
- [x] Regresyon testleri başarılı (337 `OK`); kod değişikliği olmadığı için ARCHITECTURE ile senkron

### Kanıt haritası

Belgedeki her "korunuyor" iddiası mevcut testlerle eşleştirildi. Testler belge metnine bağlı değildir; eşleşme kodu okuyarak ve testleri çalıştırarak doğrulandı.

| İddia | Kanıtlayan test dosyası | Sonuç |
|---|---|---|
| Motor anahtarı, kanıt ve onay dizinleri kısıtlı belirteçle korunur; sandboxsız kontrol aynı yerlere erişebilir | `tests/engine/test_sandbox.py` (6 test) | Geçti |
| Sahte kanıt anahtar olmadan üretilemez; sandbox kurulumu idempotent, kapatma açık | `tests/engine/test_sandbox.py` | Geçti |
| Kapsam ihlali, kabul testi değişikliği ve eski/oynanmış sonuç reddedilir | `tests/engine/test_runner.py` | Geçti |
| `apply` doğrulanmış sonuç ve tek seferlik uygulama ister; yarım kalan iş kabul edilmez | `tests/engine/test_runner.py` | Geçti |
| Retry bütçesi sınırlı; dal değiştirerek bütçe sıfırlanamaz | `tests/engine/test_runner.py` | Geçti |
| Worker ortamı sırları düşürür (izin listesi dışında) | `tests/engine/test_runner.py` | Geçti |
| Timeout, iptal ve supervisor çökmesi çocuk süreç ağacını öldürür | `tests/engine/test_runner.py`, `tests/engine/test_windows_processes.py` (11 test) | Geçti |
| MCP üzerinden ayrıcalıklı seçenek, otomatik apply ve onaysız uygulama reddedilir | `tests/interfaces/test_mcp_server.py` (8 test) | Geçti |
| Aynı veri kökünde ikinci yazar kilidi reddedilir; ölü süreç kilidi geri alınır | `tests/engine/test_lanes.py` (15 test) | Geçti |
| Güvenli olmayan bağlantı/junction yolları kapsam ihlali sayılır | `tests/engine/test_lanes.py` | Geçti |

### Bilinen sınırlar (SEC-01 sonrası hâlâ açık)

- Worker süreci için OS düzeyinde dosya sistemi veya ağ sınırı **yok**; bugünkü koruma Git worktree, sonuç kapsamı ve `apply` kontrolüdür. → `SEC-02`, `SEC-03`, `SEC-04`
- Codex `workspace-write` sandbox'ı ve `approval_policy=never` ile başlatılır; bu bir worker izin politikası değil, CLI'nin kendi sınırıdır.
- Ortam temizliği isim tabanlıdır; `RESPECTED_WORKER_ENV_ALLOW` ile genişletilebilir.
- Tek veri kökünde tek görev çalışır; paralellik yalnızca ayrı veri kökleri/şeritler düzeyindedir.
- Yükseltilmiş yönetici altında çalışma desteklenmez; bunun **aktif reddi** henüz kodda yok (`SEC-03`).

**Sonraki görev:** `REL-02` — şema değişiklikleri için göç testi kapısı (bağımlılığı yok).

---

## EVAL-01 — Tekrarlanabilir değerlendirme koşucusu

- **Durum:** Tamamlandı (kod + test + ölçüm). Tarih: 30 Ekim 2026.
- **Kapsam:** Aynı küçük yazılım görevinin her koşuda birebir aynı başlangıç commit'iyle kurulabildiğini, hatalı başlangıcın kabul testini geçemediğini ve altın çözümün geçtiğini makine okunur biçimde ölçen koşucu. Bu görev ajan/model başarısını ölçmez; ölçümün kendisinin tekrarlanabilir olduğunu kanıtlar. Model karşılaştırması `EVAL-02`.
- **Tasarım kararları:**
  - Her fixture `tempfile.mkdtemp` altında sıfırdan kurulur ve iş bitince silinir; ürün veri köküne yazılmaz.
  - Git kimliği/tarihi sabit, `GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`, `core.autocrlf=false`, `commit.gpgsign=false`. Bu yüzden başlangıç SHA'sı tekrar edilebilir.
  - Her görev için iki koşu: hatalı kaynak (kabul testi **başarısız olmalı**) ve altın kaynak (kabul testi **geçmeli**). İkisi de doğrulanmadan görev `passed` sayılmaz; böylece "test hiçbir şeyi ölçmüyor" hatası yakalanır.
  - Model/API çağrısı yoktur. Ölçülmeyen maliyet sıfır değil `bilinmiyor` olarak kaydedilir.
  - Rapor yolu `RESPECTED_DATA_DIR`, `RESPECTED_ORCH_DATA` veya `RESPECTED_DATA_ROOT` altına denk gelirse `ValueError` ile reddedilir.
- **Değişen/eklenen dosyalar:**
  - `tests/evals/__init__.py` (yeni)
  - `tests/evals/fixtures.py` (yeni) — RSP-001…RSP-020, her biri hatalı kaynak + altın kaynak + `unittest` kabul testi
  - `tests/evals/start_shas.json` (yeni) — 20 fixture için sabit 40 karakterlik başlangıç SHA'ları
  - `tests/evals/runner.py` (yeni) — kurulum, yalıtım, tekrar, metadata, SHA-256 sonuç hash'i, JSON şeması
  - `tests/evals/test_eval_runner.py` (yeni) — 6 sözleşme testi
  - `docs/ilerleme/poc/eval01_results.json` (yeni) — 3 tekrarlı gerçek koşu raporu
  - `docs/ARCHITECTURE.md` (test tablosu + değerlendirme koşucusu bölümü)
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` (durum)

### Doğrulama

Komut (depo kökünde):

```
python -m tests.evals.runner --repeat 3 --out docs/ilerleme/poc/eval01_results.json
```

Gerçek çıktı:

```
{"total": 20, "passed": 20, "failed": 0, "rejected": 0}
```

Rapor metadata'sı (gerçek):

```json
{"python": "3.13.15", "platform": "Windows-11-10.0.26300-SP0", "machine": "AMD64", "git": "git version 2.55.0.windows.5", "timestamp_utc": "2026-10-30T01:12:42.950954+00:00"}
```

Rapordaki doğrulanmış gerçekler:

- 20 görev × 3 tekrar = 60 koşu; hepsi `start_sha_matches=true`, `baseline_status=expected_failure`, `golden_status=expected_pass`.
- Her görevin üç tekrarı aynı başlangıç SHA'sını üretti (`True` kümesi tek elemanlı).
- Tüm koşularda `cost = "bilinmiyor"`.
- Örnek: RSP-001 başlangıç SHA `a361a96f3f25de1617e956b667b9fdf2b0f21e4e`, beklenen SHA ile eşleşti.

Koşucu sözleşme testleri:

```
python -m unittest tests.evals.test_eval_runner -v
```

Gerçek çıktı:

```
Ran 6 tests in 13.416s

OK
```

Kapsanan senaryolar: 20 fixture/benzersiz kimlik ve sabit SHA; tüm hatalı başlangıçlar başarısız + tüm altın çözümler geçer; 3 tekrar/SHA/metadata; 20 geçersiz varyantın 20/20 deterministik reddi; timeout'un yanlış `passed` üretmemesi; JSON şeması + ürün verisi koruması.

Tam regresyon:

```
python -m unittest discover -s tests -t .
```

Gerçek çıktı:

```
Ran 343 tests in 419.998s

OK
```

### Kabul kriterleri

- [x] İlk 20 görev fixture (`RSP-001`…`RSP-020`, `tests/evals/fixtures.py`)
- [x] Hepsinde sabit başlangıç SHA ve doğrulanabilir kabul koşulu — 60/60 koşuda SHA eşleşti, hatalı/altın ayrımı doğrulandı
- [x] Geçersiz fixture için 20/20 deterministik ret — `test_invalid_fixtures_are_rejected_deterministically_twenty_times`
- [x] En az 3 tekrar koşusu metadata kaydeder — `--repeat 3`, 60 koşu, env metadata raporda
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; `docs/ARCHITECTURE.md` senkron

### Kalan risk / shortcut

- Bu koşucu **harness tekrarlanabilirliğini** ölçer; herhangi bir ajanın veya modelin görevi çözme başarısını ölçmez. Gerçek ajan karşılaştırması `EVAL-02` kapsamındadır.
- Görev tanımındaki "erişilemeyen model" senaryosu bu koşucuda uygulanamaz (model çağrısı yoktur); bu bir eksik değil, kapsam ayrımıdır ve EVAL-02'de ele alınacaktır.
- Fixture'lar sentetik, tek dosyalı ve küçük; gerçek depo karmaşıklığını, bağımlılık kurulumunu veya ağ hatalarını temsil etmez.
- `start_shas.json` elle sabitlenmiştir; bir fixture'ın içeriği değişirse SHA testi kırılır. Bu bilinçli bir regresyon kapısıdır, güncelleme fixture ile birlikte yapılmalıdır.
- Maliyet gerçek kullanımla ölçülmedi (`bilinmiyor`).

---

## REL-02 — Şema değişiklikleri için göç testi kapısı

- Durum: Tamamlandı
- Kapsam: `interfaces/migrate.py` göç kayıt defteri (`STEPS`, `CURRENT`) için regresyon kapısı; iki eski sürümden güncel sürüme taşıma, idempotent ikinci çalıştırma, adım hatasında geri alma ve şema sürümü artırılıp adım eklenmediğinde CI'nın kırmızıya düşmesi.
- Çıktı / değişen dosyalar:
  - `tests/interfaces/test_migrate.py` (4 yeni test) — eski sürüm→güncel, ikinci çalıştırmada byte eşitliği, hata sonrası orijinal byte'ların korunması ve `.bak` oluşmaması, eksik adımda `MigrationError` + yazma yok, `CURRENT`/`SHIPPED` eşitliği ve her dosya için yayın fixture'ı.
  - `docs/ARCHITECTURE.md` (§8 göç kapısı paragrafı)
  - `docs/ilerleme/poc/rel02_gate_proof.txt` (kapı kanıtı)
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` (durum)

### Doğrulama

Komut:

```
python -m unittest tests.interfaces.test_migrate -v
```

Gerçek çıktı:

```
Ran 10 tests in 0.060s

OK
```

Kapı testi (bilerek `CURRENT=2`, `STEPS={}` yapıldı; geri alındı):

```
python -m unittest tests.interfaces.test_migrate.MigrateTest.test_registry_has_a_step_for_every_shipped_older_version
```

Gerçek çıktı (beklenen kırmızı):

```
FAIL: test_registry_has_a_step_for_every_shipped_older_version
AssertionError: ('settings.json', 1) not found in {}

Ran 1 test in 0.001s

FAILED (failures=1)
GATE_REJECTED_UNSTEPPED_BUMP=True
```

Tam regresyon:

```
python -m unittest discover -s tests -t .
```

Gerçek çıktı:

```
Ran 347 tests in 453.610s

OK
```

### Kabul kriterleri

- [x] Mevcut eski fixture sayısı kadar %100 geçiş — her yayın sürümü fixture'ı güncel sürüme taşındı.
- [x] İkinci çalıştırmada byte düzeyinde 0 değişiklik — test dosya byte'larını karşılaştırıyor.
- [x] Başarısız migrate sonrası veri kaybı 0 — hata durumunda orijinal byte'lar korunuyor, `.bak` oluşmuyor.
- [x] Migration yoksa şema değiştiren PR CI tarafından reddedilir — kayıt defteri testi kırmızıya düşüyor (yukarıdaki çıktı).
- [x] Regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; `docs/ARCHITECTURE.md` senkron.

### Kalan risk / shortcut

- Yalnızca bir yayın fixture'ı (`releases/1`) var; gelecekte ikinci bir eski sürüm eklenirse fixture da eklenmelidir, aksi hâlde kapı yeni sürümü kapsamaz.
- CI'da ayrı bir "diff'te `CURRENT` değişti mi" kontrolü yok; koruma tamamen test suite'inin kırılmasına dayanıyor. `shortcut: ayrı CI diff kontrolü yok, yayın hattı kurulunca ekle.`

---

## DOC-01 — Rakip araştırması + ADR karar defteri

- Durum: Tamamlandı (2026-10-30)
- Kapsam: 21 kaynaklı rakip/çerçeve araştırması, 4 çerçeve ve 10 rakip profili, doğrulanmamış iddiaların işaretlenmesi, 6 ADR karar kaydı.
- Çıktı / değişen dosyalar: `docs/COMPETITOR_RESEARCH.md`, `docs/adr/ADR-001…006.md`, `docs/ilerleme/poc/doc01_check.py`, `docs/ilerleme/poc/doc01_check.txt`, `tests/docs/test_decision_records.py`, `docs/ARCHITECTURE.md` (§9 test tablosu).
- Doğrulama komutu: `python docs/ilerleme/poc/doc01_check.py`; `python -m unittest tests.docs.test_decision_records -v`; `python -m unittest discover -s tests -t .`
- Gerçek çıktı:

```
PASS kaynak tablosu: 21 kaynak, tümü https + 2026-10-30
PASS profiller: 4 çerçeve + 10 rakip, alanlar ve kaynaklar tam
PASS doğrulanmamış iddialar: 6 işaretli
PASS benchmark kararları EVAL-01 kanıtına bağlı, ajan başarısı doğrulanmadı olarak işaretli
PASS ADR: 6 karar kaydı, Durum/Bağlam/Karar/Sonuçlar/Kaynaklar alanları tam
RESULT PASS 2026-10-30
```

```
Ran 1 test in 0.070s

OK
```

- Kabul kriteri karşılandı mı (kanıtla): Evet. Kaynakların tamamı HTTPS ve aynı tarih damgalı; profillerde zorunlu alanlar dolu; iddialar doğrulanmış/doğrulanmamış olarak ayrılmış; benchmark kararları EVAL-01 fixture kanıtına bağlanmış, ajan başarısı iddia edilmemiş; ADR alanları testle denetleniyor.
- Kalan risk / shortcut: Mission Control ve Orca ürünlerinin kimlik/özellik sınırları ile bazı ikincil rakip iddiaları yalnızca kamuya açık kaynaklara dayanıyor; doğrulanmamış olarak işaretli. Kaynaklar değişirse `doc01_check.py` tarih/URL denetiminde kırılır.


## QUA-02 — Başarısızlık taksonomisi ve tekrar deneme politikası

- **Durum:** Tamamlandı. Tarih: 30 Ekim 2026.
- **Kapsam:** Başarısız görevlerin tek bir hata sınıfına indirgenmesi yerine sınıflandırılması; sınıfa göre sınırlı retry veya insan kararı; terminal kayıt ve MAF sonuçlarının aynı sözleşmeyi kullanması.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/engine/failures.py` (yeni): 8 sınıf, retry politikası, sağlayıcı durum eşlemesi.
  - `src/respected_orchestrator/engine/runner.py`: başarısız terminal kayıtlara `failure_class`, `retryable`, `retry_policy`; retryable olmayan kayıt için retry reddi.
  - `src/respected_orchestrator/workflows/maf_workflow.py`: `REJECTED` ve `NEEDS_CHANGES` ayrımı; hata sınıfı alanları.
  - `src/respected_orchestrator/context.py`: Windows'ta geçici `PermissionError` için sınırlı `os.replace` tekrarı (atomik yazma korunur).
  - `tests/engine/test_failures.py`, `tests/engine/test_runner.py`, `tests/workflows/test_maf_workflow.py`, `tests/test_context.py`.
  - `docs/adr/ADR-005-failure-taxonomy.md`, `docs/ARCHITECTURE.md` §2.
- **Politika:** `test_failure` sınırlı düzeltme; `timeout`, `infrastructure` sınırlı retry; `policy_denied`, `quota`, `auth`, `stale_patch`, nihai `reviewer_reject` → `manual`, retry yok. `NEEDS_CHANGES` yalnızca bir sınırlı düzeltme turu alır; nihai `REJECTED` onay değildir.
- **Doğrulama komutu:** `python -m unittest tests.test_context tests.engine.test_failures tests.engine.test_runner tests.workflows.test_maf_workflow`
- **Gerçek çıktı:**

```
Ran 50 tests in 94.704s

OK
```

- **Tam regresyon komutu:** `python -m unittest discover -s tests -t .`
- **Gerçek çıktı:**

```
Ran 357 tests in 443.235s

OK
```

- **Windows yarış düzeltmesi:** `atomic_write_json` önceden `os.replace` üzerinde AV/okuyucu kilidi nedeniyle `WinError 5` alabiliyordu. Artık yalnızca `PermissionError` durumunda, en fazla 10 deneme ve artan 20 ms bekleme var; diğer hatalar hemen yükselir. `tests/test_context.py` iki ardışık hatadan sonra başarıyı doğrular.
- **Kabul kriteri karşılandı mı (kanıtla):** Evet. Sekiz sınıfın her biri tek bir politikaya eşleniyor; retryable olmayan kayıt reddediliyor; MAF reddi onay sayılmıyor; tam suite yeşil.
- **Kalan risk / shortcut:** Sınıflandırma mevcut `reason` metinlerine ve sağlayıcı durum kodlarına dayanıyor; yeni bir sağlayıcı farklı metin üretirse `unknown` olarak kalır ve alan eklenmez. `shortcut: yeni sağlayıcı metinleri eklendiğinde failures.py eşlemesi genişletilmeli.`


## SEC-02 — Windows worker sandbox teknoloji doğrulaması

- **Durum:** Tamamlandı. Tarih: 30 Ekim 2026.
- **Kapsam:** Gerçek worker ve alt süreçler için Windows'ta dosya, ağ ve süreç sınırı sağlayan teknolojiyi seçmek; prototipi geçici repoda ölçmek. Üretim başlatıcısına bağlama SEC-03.
- **Çıktı / değişen dosyalar:**
  - `docs/ilerleme/poc/sec02_probe.py` (yeni): AppContainer profilini oluşturan, çalışma alanı/Python dizinine ACL veren, üç kez gerçek süreç başlatan ve sonuçları JSON'a yazan prototip.
  - `docs/ilerleme/poc/sec02_results.json` (yeni): ham ölçüm.
  - `docs/ilerleme/poc/SEC02_SANDBOX_COMPARISON.md` (yeni): dört seçeneğin karşılaştırması ve sınırlar.
  - `docs/ARCHITECTURE.md` §2: SEC-02 doğrulaması ve SEC-03'e kadar geçerli sınır.
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`, `docs/ilerleme/respected_orchestrator_github_issues.csv`: SEC-02 tamamlandı.
- **Seçim:** Yetenek SID'i olmayan **AppContainer**. Kısıtlı belirteç ayrı dosya güvenlik sınırı olmadığı için reddedildi; Windows Sandbox VM'i başlangıç maliyeti ve dosya paylaşımı nedeniyle ertelendi.
- **Doğrulama komutu:** `python docs/ilerleme/poc/sec02_probe.py docs/ilerleme/poc/sec02_results.json`
- **Gerçek çıktı:**

```
{
  "forbidden_blocked": "15/15",
  "allowed_workspace_writes": "9/9",
  "child_policy_inherited": "9/9",
  "network_baseline_connected": true,
  "codex_launched": true,
  "codex_exit_code": 0,
  "windows_sandbox_binary": true,
  "pass": true
}
```

- **Ölçüm ayrıntısı:** Üç çalıştırmada beş yasak eylem (dış okuma, dış yazma, `.engine-key` okuma, TCP egress, dış silme) 15/15 engellendi; üç izinli yazma 9/9 başarılı; üç torun süreçte politika 9/9 miras alındı. Sandbox dışı ağ ön koşulu bağlandı. Olmayan CLI `CreateProcess` hata 2 ile açıkça unsupported döndü; geniş yetkili fallback yok.
- **Kabul kriteri karşılandı mı (kanıtla):** Evet. 5 yasak eylem 15/15; izinli yazma 9/9; çocuk süreç 9/9; unsupported CLI açık; sessiz fallback 0. Codex `--version` konteynerde 0 ile çalıştı; oturum açma/gerçek görev kapsam dışı.
- **Regresyon:** Kaynak kodu değişmedi; QUA-02 tam suite sonucu bu ağaç için geçerli (`Ran 357 tests in 443.235s / OK`). Doküman testi ayrıca `Ran 1 test in 0.070s / OK`.
- **Kalan risk / shortcut:** `icacls` ACL'leri prototipte elle verilip geri alınıyor; üretimde tek launcher yönetmeli. AppContainer ortam değişkenlerini temizlemez ve izinli dizindeki çalıştırılabilirleri ayırt etmez; sır ayıklama ve executable allowlist SEC-03'te. `shortcut: prototip yalnızca Windows AppContainer; SEC-03 gelene kadar normal worker yolu değişmedi.`

---

## SEC-03 — Worker izin politikası ve fail-closed başlatıcı

- **Durum:** Tamamlandı (kod + test + tam regresyon). Tarih: 30 Ekim 2026.
- **Kapsam:** Her worker ve inceleme sürecinin tek bir politika doğrulamasından ve Windows AppContainer başlatıcısından geçmesi; politika kurulamazsa hiçbir sürecin başlamaması; veri kökü ve `.engine-key` erişiminin hiçbir worker'a açılmaması. `create`, `start`, MAF araç çağrıları ve kampanya alt şeritleri aynı yolu kullanır.
- **Tasarım kararları:**
  - `WorkerPolicy` yazılabilir kökleri, salt-okunur araç köklerini, ağ modunu, sır adlarını, çalıştırılabilir allowlist'ini ve TTL'i taşır; boş/çakışan/eksik kök, bilinmeyen ağ modu ve geçersiz TTL reddedilir.
  - Veri kökü ve `.engine-key` içeren kökler politika kurulurken reddedilir; veri kökünün altındaki çalışma alanı desteklenen tek iç içe biçimdir.
  - `.cmd`/`.bat` şimleri worker olarak kabul edilmez; çözümlenen çalıştırılabilir mutlak yol olarak sabitlenir.
  - AppContainer profili her çalıştırmada oluşturulur, izinler yalnızca worktree ve geçici köke verilir, kapanışta geri alınır. Python/araç dizini `ALL APPLICATION PACKAGES` ile makine genelinde salt-okunur paylaşılır; bu grant kullanıcı profilini veya veri kökünü kapsamaz.
  - AppContainer `TEMP`/`TMP` değişkenlerini kendi profiline yönlendirdiği için politikanın verdiği geçici kök `RESPECTED_WORKER_TMP` olarak açıkça yayınlanır; aksi hâlde verilen izin worker tarafından kullanılamıyordu.
  - Başlatma zinciri: `runner.execute_task` → `processes.execute(policy=...)` → `appcontainer.spawn`. Politika veya AppContainer hatası `sandbox_unavailable` terminal nedeni üretir; sandbox'sız geri dönüş yoktur.
- **Değişen/eklenen dosyalar:**
  - `src/respected_orchestrator/engine/worker_policy.py` (yeni) — politika doğrulaması, ortam temizliği, TTL kontrolü.
  - `src/respected_orchestrator/engine/appcontainer.py` (yeni) — AppContainer profili, ACL grant/geri alma, boru ve süreç başlatma.
  - `src/respected_orchestrator/engine/processes.py` — `policy` parametresi; AppContainer üzerinden başlatma; süre bütçesi süreç oluştuktan sonra başlar.
  - `src/respected_orchestrator/engine/runner.py` — worker için `default_policy`; fail-closed `sandbox_unavailable`.
  - `src/respected_orchestrator/engine/codex.py` — Codex çağrısına politika aktarımı.
  - `src/respected_orchestrator/workflows/maf_workflow.py` — araç inceleme yolu ve Codex incelemesi aynı politika/başlatıcıdan geçer.
  - `src/respected_orchestrator/context.py` — `read_text_retry`: Windows'ta delete-pending/AV penceresinde sınırlı okuma tekrarı.
  - `src/respected_orchestrator/engine/evidence.py` — imzalı kanıt okuması `read_text_retry` kullanır.
  - `tests/engine/test_worker_policy.py` (yeni, 18 test) — politika, fail-closed worker ve MAF inceleme yolu, gerçek AppContainer negatif/pozitif vakaları, timeout sonrası süreç temizliği, sentinel sır.
  - `tests/engine/test_runner.py` — worker pid dosyasının kendi worktree'sinde kalması.
  - `tests/workflows/test_campaign.py` — kampanya alt şeridinin worker'ı doğrudan değil `engine maf` üzerinden çalıştırdığı.
  - `tests/workflows/test_reviewer_reliability.py` — gerçek worker sayacı izinli geçici köke taşındı (sandbox gevşetilmedi).
  - `tests/test_context.py` — okuma tekrarı testi.
  - `docs/ARCHITECTURE.md` §2 — SEC-03 sınırı, kanıt eşlemesi ve kalan sınır.
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`, `docs/ilerleme/respected_orchestrator_github_issues.csv` — durum.
- **Doğrulama komutu (odak):**

  ```
  python -m unittest tests.engine.test_worker_policy tests.workflows.test_campaign tests.workflows.test_reviewer_reliability tests.engine.test_token_budget tests.test_context
  ```

  Gerçek çıktı (`docs/ilerleme/poc/sec03_focused.log`):

  ```
  Ran 65 tests in 74.373s

  OK
  ```

- **Tam regresyon komutu:**

  ```
  python -m unittest discover -s tests -t .
  ```

  Gerçek çıktı (`docs/ilerleme/poc/sec03_full_suite.log`):

  ```
  Ran 378 tests in 531.768s

  OK
  ```

- **Kabul kriterleri:**
  - [x] Üç giriş türü aynı policy motorunu kullanıyor: worker (`test_runner_marks_sandbox_unavailable_and_leaves_project_untouched`), MAF inceleme yolu (`test_maf_reviewer_is_fail_closed_when_the_sandbox_cannot_start`), kampanya alt şeridi (`test_a_lane_delegates_to_the_engine_maf_pipeline_instead_of_launching_a_worker` + `engine maf` → runner testi).
  - [x] Politika uygulanamıyorsa 0 worker başlıyor: `test_spawn_failure_raises_and_creates_no_worker_output`, `test_runner_marks_sandbox_unavailable_and_leaves_project_untouched`; proje dosyası değişmiyor.
  - [x] 0 sır sızıntısı: `test_sentinel_secret_never_appears_in_output` (iki sentinel adı da `None`, değer çıktıda yok); `test_environment_scrubs_secrets_and_redirects_temp`.
  - [x] Timeout sonrası child PID kalıntısı 0: `test_timeout_leaves_no_child_process` (parent ve torun süreç ölü).
  - [x] Gerçek AppContainer negatifleri: dış okuma/yazma, `.engine-key`, varsayılan ağ reddi, alt süreç mirası; pozitifler: worktree yazma/okuma, alt süreç.
  - [x] Regresyon yeşil (378 `OK`); `docs/ARCHITECTURE.md` aynı değişiklikte senkron.

- **Kanıt artefaktları (SHA-256):**
  - `docs/ilerleme/poc/sec03_focused.log` → `1D4C0B1547F0055EA2144D4975352CF06EE7AE8EA75107B7CA602B6C864CC843`
  - `docs/ilerleme/poc/sec03_full_suite.log` → `3D835D18722BE9E49AF529521FBFA18D8AC058DC62A727D85283EF1281BBF729`
  - `worker_policy.py` → `A912F0FD17C107980EFB030B3DB4ABC7F50AFB1B84D116756FE3C4AF3BDDC01C`
  - `appcontainer.py` → `E6114F9803795FB6C7E6EBB357E356F3702D1F7B2A5C6B8CB610699B79B4B98A`
  - `processes.py` → `A564DD1B05A3131B93F9067C2BB878733D6C9B496AF58E6BF973B6541E558AFA`
  - `runner.py` → `2CFB2EDE51914F1705764819363068D5061DAA95B33422D863C80F4FC7B99528`
  - `codex.py` → `4717E9A3617A2AF0C2EF9C103F99049BBDDDB499906D9D47DE1E47B3385DD2F5`
  - `maf_workflow.py` → `2D070E0073F1B7B34D56BA03A77DFE9CF9BDAED3AA3BB5718B1D31E951725B78`
  - `context.py` → `1E1F1BCD69D361872E743921B9737893C28A8C88239EEE8BF121464FAFC95C3A`
  - `evidence.py` → `490F65122C879F5C03BE2C6DFD8CF7BF89AF21CA0A4068203A0D6FE256894773`
  - `test_worker_policy.py` → `A3DA69A5A11AC58CA2E1D1714DCCCD5C9670EF5232F2D62D0914A0D177647083`
  - `test_campaign.py` → `49C9819CC6320FB98F78B98E0D2F43DBA8DC37C8278CF693B0ABF900ABD108D6`
  - `test_reviewer_reliability.py` → `D06A68B77A2EF2BEA2FE6132FECF54EFC5140343B38C8F4937B2BF33E13EC6DF`
  - `test_context.py` → `07A5CEA148FC3EF6DCAFDA7CBF7643E44DDF0E570AFF200E13D644E39D264656`
  - `ARCHITECTURE.md` → `0AA775023DCEA8CA4B365C8BDBE5CE02FC268EFEE20C1DD495B90881223112BE`

- **Kalan risk / shortcut:**
  - AppContainer Windows'a özgüdür; Windows dışında worker başlatılmaz (REL-04 platform kararı). Yükseltilmiş yönetici altında çalışan motor bu modelin dışındadır ve kodda aktif ret henüz yoktur.
  - `sys.prefix` altındaki araç zinciri makine genelinde `ALL APPLICATION PACKAGES` ile salt-okunur açılır; bu, aynı makinedeki diğer AppContainer'ların da Python dizinini okuması demektir (yalnızca çalıştırılabilir/kütüphane, veri değil).
  - İzin verilen araç dizinindeki ek çalıştırılabilirler varsayılan olarak allowlist'te değildir; `RESPECTED_WORKER_READONLY_ROOTS` ile salt-okunur kök eklenebilir, yazılabilir kök eklenemez.
  - AppContainer `TEMP`'i kendi profiline yönlendirir; worker'ın kalıcı geçici alanı `RESPECTED_WORKER_TMP` sözleşmesiyle verilir.
  - ACL geri alma kapanışta `icacls` ile yapılır ve hata yutulur; profil silinemezse artık profil kalabilir. `shortcut: kapanış ACL hataları yalnızca sessizce yutuluyor; artık profil/ACE izleme eklenmeli.`
  - Önceki tam koşudaki 8 kırık, testlerin sayaç dosyasını izinli köklerin dışına yazmasından kaynaklanıyordu; sandbox gevşetilmedi, sayaç izinli geçici köke taşındı. Windows'ta `status.json` okumasında görülen tek `PermissionError` yarışı `read_text_retry` ile sınırlı biçimde giderildi.

---

## SEC-04 — CI zorunlu negatif izolasyon ve kırmızı-takım testleri

- **Durum:** Tamamlandı (31 Ekim 2026).
- **Kapsam:** Worker AppContainer negatif izolasyon matrisi, restricted-token verify hattı, recursive MCP reddi, symlink/gitlink yama reddi, kaynak ve paketlenmiş exe üzerinde saldırı matrisi, CI'da ayrı ve zorunlu güvenlik adımları.
- **Doğrulanan açık:** Windows'ta symlink oluşturma imtiyazı olmasa bile Git indeksine `120000` modu yazılabiliyor; aynı yola normal dosya yazıldığında working-tree `is_symlink()` kontrolü bunu maskeliyordu. Yalnızca dosya sistemine bakmak fail-open davranışa yol açıyordu.
- **Düzeltme (`src/respected_orchestrator/engine/lanes.py`):**
  - `collect_worker_changes`, baseline'a göre `git diff --raw --no-renames --full-index -z` çıktısındaki eski/yeni modları tarar; `120000` (symlink) veya `160000` (gitlink/submodule) içeren yollar doğrudan `unsafe_paths` listesine girer.
  - Bu yollar export öncesinde reddedilir; kapsam doğrulamasında `scope_violation` üretir. Çalışma ağacındaki normal dosya, indeks modunu maskeleyemez.
  - Apply öncesi yama metni ayrıca `old mode`/`new mode`/`new file mode`/`deleted file mode`/`create mode`/`delete mode` başlıklarında `120000` veya `160000` arar; eşleşme `INTEGRATION_CONFLICT` ile fail-closed sonuçlanır.
- **Test kaydı (`tests/engine/security_cases.py`):**
  - 21 negatif vaka: 19 worker içi probe + 2 harici vaka (`symlink_patch`, `recursive_mcp`).
  - 9 izinli vaka ve 13 zorunlu saldırı kategorisi.
  - `tests/engine/test_security_gate.py`, probe/harici ayrımının eksiksiz ve tekrarsız olduğunu, minimum sayıyı, zorunlu kategorileri ve CI adımlarını doğrular.
- **CI sınırı (`.github/workflows/ci.yml`):** Worker AppContainer matrisi, restricted-token verify matrisi, güvenlik kayıt kapısı ve frozen exe güvenlik matrisi ayrı zorunlu adımlardır; `continue-on-error` yoktur. Tam keşif ayrıca bloklayıcı son adım olarak çalışır.

- **Doğrulama komutları ve gerçek çıktılar:**

  ```
  python -m unittest tests.engine.test_worker_security -v
  ```

  `docs/ilerleme/poc/sec04_worker_source_final.log`:

  ```
  Ran 4 tests in 4.400s

  OK
  ```

  ```
  python -m unittest tests.engine.test_sandbox -v
  ```

  `docs/ilerleme/poc/sec04_verify_sandbox_final.log`:

  ```
  Ran 6 tests in 4.069s

  OK
  ```

  ```
  python -m unittest tests.engine.test_security_gate -v
  ```

  `docs/ilerleme/poc/sec04_security_gate_final.log`:

  ```
  Ran 4 tests in 0.000s

  OK
  ```

  ```
  python -m unittest tests.engine.test_lanes -v
  ```

  `docs/ilerleme/poc/sec04_lanes_regression_final.log`:

  ```
  Ran 15 tests in 4.947s

  OK
  ```

  ```
  python -m unittest tests.packaging.test_frozen_security.FrozenSecurityTest.test_frozen_engine_rejects_a_symlink_mode_patch_staged_without_symlink_privilege -v
  ```

  `docs/ilerleme/poc/sec04_frozen_symlink_fixed.log`:

  ```
  Ran 1 test in 15.734s

  OK
  ```

  ```
  python -m unittest tests.packaging.test_frozen_security -v
  ```

  `docs/ilerleme/poc/sec04_frozen_security_final.log`:

  ```
  Ran 3 tests in 35.553s

  OK
  ```

  ```
  python packaging/build_dist.py --output dist
  ```

  `docs/ilerleme/poc/sec04_build_final.log`: build tamamlandı; çıktı `dist\RespectedOrchestrator`.

  ```
  python -m unittest tests.packaging.test_frozen_build tests.packaging.test_frozen_security -v
  ```

  `docs/ilerleme/poc/sec04_frozen_all_final.log`:

  ```
  Ran 7 tests in 54.087s

  OK
  ```

  ```
  python -m unittest tests.docs.test_decision_records -v
  ```

  `docs/ilerleme/poc/sec04_docs_gate_final.log`:

  ```
  Ran 1 test in 0.103s

  OK
  ```

  ```
  python -m unittest discover -s tests -t .
  ```

  `docs/ilerleme/poc/sec04_full_suite.log`:

  ```
  Ran 389 tests in 469.282s

  OK
  EXIT_CODE=0
  ```

- **Kabul kriterleri:**
  - [x] En az 15 negatif vaka: 21 kayıtlı (19 probe + 2 harici); kayıt kapısı yeşil.
  - [x] 21/21 saldırı reddedilir, 9/9 izinli işlem geçer; 13 zorunlu kategori korunur (`test_every_registered_negative_is_denied_and_every_allowed_case_passes`, `test_registry_meets_the_security_minimum_and_is_unique`, `test_every_required_attack_category_is_registered`).
  - [x] Symlink-index saldırısı export/apply öncesi reddedilir; testte durum `failed`/`scope_violation`, değişen yol `src/escape`, `worker.patch` yoktur.
  - [x] Recursive MCP araç sunmaz ve `tools/call` reddedilir; sandbox dışı kontrol aynı saldırıların gerçek olduğunu gösterir.
  - [x] Worker, verify, güvenlik kayıt kapısı ve frozen exe matrisleri CI'da ayrı zorunlu adımlardır; `continue-on-error` yoktur.
  - [x] Kaynak ve paketlenmiş exe güvenlik matrisleri yeşildir; ilgili lanes regresyonu 15/15 `OK`.
  - [x] Doküman kapısı `OK`; tam regresyon 389/389 `OK`, `EXIT_CODE=0`.
  - [x] `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, yol haritası ve issue CSV durumu aynı değişiklikte senkron edildi.

- **Kanıt artefaktları (SHA-256):**
  - `docs/ilerleme/poc/sec04_worker_source_final.log` → `A6B4899950AEF6595E83606C7E0A60D1329C608A8D3DE3D362ADFAD3EC61CC98`
  - `docs/ilerleme/poc/sec04_verify_sandbox_final.log` → `83C391BAB8358656F5D551285B48A553028D733D11E51F6915C87572C115F1E7`
  - `docs/ilerleme/poc/sec04_security_gate_final.log` → `C102B2516AEDA62A87A8E6BFF9BBF8C0537991A098C831D730677B39C84E857B`
  - `docs/ilerleme/poc/sec04_lanes_regression_final.log` → `196E0312291FF450D08338299BE7FF16A408D96DC0C7DAD4F85443B3BFBB4417`
  - `docs/ilerleme/poc/sec04_frozen_symlink_fixed.log` → `2C89936C0590C19BF5A59A44ECA824A5C83CC67F607962D94F86CBBCD1F66EF5`
  - `docs/ilerleme/poc/sec04_frozen_security_final.log` → `18EAB2F62BB1443BB61631B1C15283B645CFBE11B1DFB01D8BD551754D6C786C`
  - `docs/ilerleme/poc/sec04_build_final.log` → `9A6ADA2259D0E5DEEFE7CAFF437B0084B7CD277CEE6E8E96DBD7738D3E4158AC`
  - `docs/ilerleme/poc/sec04_frozen_all_final.log` → `CE5379121AC1DF1A769A41D634A61D8D58AE641A69899E3F9DFC63C3B822FC87`
  - `docs/ilerleme/poc/sec04_docs_gate_final.log` → `28747187822C788FBA68E9F01CF66A7FFDB03BCD69E66EE1ED4E9E3A3EABEC17`
  - `docs/ilerleme/poc/sec04_full_suite.log` → `94988541A2177179AA708DA882A2659D0F5BE3BE7B281314BA0C94DF2F0A2968`
  - `tests/engine/security_cases.py` → `F96FC4D453DF707D5438EADFF99B57182262D861E15C330FF3DFC6B0AD7A70D9`
  - `tests/engine/test_worker_security.py` → `C8919E71DEA85337BD1DB216BB7FC225A547C2E369E77F015BCDD8010532A61E`
  - `tests/engine/test_security_gate.py` → `24035E715CD5FD04FE8AA2B8C03A31E1FD1A24A5CAAF7425F2AAD5D27C13382A`
  - `tests/packaging/test_frozen_security.py` → `5C089FC0E527C4E1800E342A2F71EC5D9232E103CFD74D7C8351AB75948446DA`
  - `src/respected_orchestrator/engine/lanes.py` → `B4E87F122F5E0F91ADE758A81C84E26430CF5B3A69E52F1AE74A248A575B324F`
  - `.github/workflows/ci.yml` → `5EB3470F7B9AFC845016F1EB28808441EDBDE580011D07A2584406A7CE3F2C93`
  - `docs/ARCHITECTURE.md` → `B743BCEEF460AC9605F1A7CA64E79D03DD8B860702EC63C9114E3DD2C1811341`
  - `docs/THREAT_MODEL.md` → `83579D281921EE0051E12077B5DB698345A77ED34C0025F85296A26125133ACF`
  - `docs/ROADMAP_EXECUTION_PLAN.md` → `2D92A11554AC252E9A831E4FB54A19B70DCE84FE14FF79A09B42B2C74F4E8F44`
  - `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` → `E43BAE6D72F003AA9A9096D867A65609E45BEA4ABC73BBEC73C145391B300D57`
  - `docs/ilerleme/respected_orchestrator_github_issues.csv` → `4029911DDEF5A409D3FD1EDBA23A67867CBF6A3AD7714F837094B7335408AB94`

- **Harness sınırı (dürüst not):** Frozen symlink testinde AppContainer worker'ı linked worktree'nin `.git` dizinine erişemez. Bu nedenle saldırı indeks modu harness tarafından `git update-index --cacheinfo 120000` ile hazırlanır; worker yalnızca aynı yolu normal dosyayla maskeler. Frozen exe'nin reddetme yolu gerçek olarak test edilir, ancak indeks yazımı saldırganın kendisi tarafından AppContainer içinde yapılmaz. İlk denemede bu nedenle `fatal: not a git repository: (NULL)` alınmıştı; test harness'i düzeltildi ve doğru saldırı modeli korundu.

- **Kalan risk / shortcut:**
  - Nightly gerçek araç smoke koşusu bu görevde eklenmedi; deterministik AppContainer ve paketlenmiş exe matrisi kapandı, sağlayıcı sürüm farkları için ayrı smoke izleme gerekli.
  - AppContainer Windows'a özgüdür; macOS/Linux güvenlik eşdeğerliği REL-04 kapsamında bekliyor.
  - İzin verilen araç dizinindeki ek çalıştırılabilirler varsayılan allowlist'te değildir; gerektiğinde salt-okunur kök olarak açıkça eklenmelidir.
  - Frozen symlink testinin indeks hazırlama adımı harness'ta çalışır; bu, saldırının motor tarafındaki reddini doğrular ama worker'ın `.git` yazma denemesini kapsamaz.

---

## QUA-01 — tester rolünü imzalı, motor sahipliğinde doğrulama aşamasına bağla

- **Durum:** Tamamlandı (kod + doküman). Tarih: 1 Kasım 2026.
- **Kapsam:** `tester` rolü artık serbest komut çalıştıran bir model çağrısı değil, motorun sahip olduğu imzalı doğrulama aşamasıdır.
  Tester atanmışsa görevin kabul komutları AppContainer içinde tam olarak bir kez çalışır; sonuç run/project fingerprint, patch
  SHA-256 ve rol atamasına bağlı imzalı `tester-report.json` olarak yazılır. MAF, reviewer çağrılmadan önce bu kanıtı doğrular.
  Tester için serbest komut, örtük araç ikamesi veya otomatik apply yoktur; atama yoksa mevcut evidence-only doğrulama yolu korunur.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/engine/runner.py` — tester ataması, tek seferlik AppContainer kabul koşusu, imzalı rapor ve
    `check_result` içinde rapor doğrulaması.
  - `src/respected_orchestrator/workflows/maf_workflow.py` — reviewer öncesi tester kanıt zorunluluğu ve kanıtın prompt'a bağlanması.
  - `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/THREAT_MODEL.md` — yürütülebilir tester aşaması ve S-19 fail-closed davranışı.
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`,
    `docs/ilerleme/respected_orchestrator_github_issues.csv` — QUA-01 durumu `done`.
  - `tests/engine/test_runner.py`, `tests/workflows/test_maf_coding.py`, `tests/workflows/test_roles.py` — tester ve reviewer kapıları.

### Doğrulama

Odaklı QUA-01 paketi (`tests.engine.test_runner`, `tests.workflows.test_maf_coding`, `tests.workflows.test_roles`,
`tests.engine.test_generated_artifacts`):

```text
python -m unittest ... -v
Ran 110 tests in 216.705s
OK
FOCUSED_EXIT_CODE=0
```

Doküman kapısı:

```text
python -m unittest tests.docs.test_decision_records -v
Ran 1 test in 0.146s
OK
DOCS_EXIT_CODE=0
```

Doküman kaydı eklendikten sonra yeniden çalıştırılan kapı:

```text
python -m unittest tests.docs.test_decision_records -v
Ran 1 test in 0.077s
OK
DOCS_AFTER_EXIT_CODE=0
```

Tam regresyon:

```text
python -m unittest discover -s tests -t .
Ran 400 tests in 564.741s
OK
FULL_EXIT_CODE=0
```

PowerShell'in `Tee-Object` ile yakaladığı `NativeCommandError` satırı harness gürültüsüdür; unittest süreci `OK` ve
`LASTEXITCODE=0` ile bitmiştir. Test hatası değildir.

### Tester senaryoları (6/6)

| # | Senaryo | Kanıtlanan davranış | Test |
|---|---|---|---|
| 1 | Tester atanmış ve kabul komutu başarılı | İmzalı `tester-report.json`; kabul komutu tam bir kez; `verified` | `test_tester_is_a_signed_engine_stage_and_acceptance_runs_once` |
| 2 | Tester atanmamış | Mevcut evidence-only yol değişmez; tester raporu üretilmez | `test_no_tester_assignment_keeps_the_evidence_only_path_unchanged` |
| 3 | Tester aracı kullanılamıyor | `ROLE_UNAVAILABLE`; örtük fallback yok | `test_unavailable_tester_is_refused_without_an_implicit_substitution` |
| 4 | Tester'a serbest komut verilmiş | `BAD_ASSIGNMENT`; komut çalışmaz, işaret dosyası oluşmaz | `test_tester_command_cannot_be_supplied_or_run` |
| 5 | Zaman aşımı veya oynanmış/silinmiş kanıt | Fail-closed; imzalı rapor yoksa/bozuksa `check_result` reddeder | `test_tester_timeout_and_tampering_fail_closed` |
| 6 | Tester çalışma alanı dışına yazmayı deniyor | AppContainer dışına yazma 0; dış hedef dosya oluşmaz | `test_tester_cannot_write_outside_its_workspace` |

Ek reviewer kapıları: tester kanıtı yoksa veya oynanmışsa reviewer hiç çağrılmaz; `review_failure.cause` değeri
`tester_evidence_invalid`, `review_decisions` boştur.

### Kabul kriterleri

- [x] Tester var/yok, fallback yok, serbest komut reddi, tamper, timeout ve worktree dışına yazma: 6/6 beklenen sonuç.
- [x] Tester çalışma alanı dışına yazabildi: 0 vaka.
- [x] Örtük araç fallback'i: 0; kullanılamayan tester açıkça reddedilir.
- [x] Reviewer yalnızca imzası ve bağlamı doğrulanmış tester kanıtı gördüğünde çalışır.
- [x] Mevcut implementer/reviewer yolları gerilemeden tam regresyon 400/400 `OK`.
- [x] `ARCHITECTURE.md`, `THREAT_MODEL.md`, yol haritası ve issue CSV aynı değişiklikte senkron edildi.

### Kanıt artefaktları (SHA-256)

- `docs/ilerleme/poc/qua01_focused_final.log` → `98F5AEF657BBA630FD9E09634E9A1B5447F0667F8DD7918BD70F52472EC74F64`
- `docs/ilerleme/poc/qua01_docs_gate_final.log` → `128FFCA2D72C9AE111CE47CD0D182F3E93FDA9AB3EEE1523F718482F3214F2A1`
- `docs/ilerleme/poc/qua01_docs_gate_after_docs.log` → `4E0675BD217A1DCBB9A21DA31534A112E570974ED36F3CB987B03537C7259A2A`
- `docs/ilerleme/poc/qua01_full_suite_final.log` → `4C9F43373FEDAC86438D67BDCCE422415FCE3D8FB32D149FECE311A2799A8CC1`
- `_qua01_roles.log` → `63A3B0D90BB911B75A1BFF24BDA3A8C513EE2536B259CD0A5F714CDE62590823`
- `_qua01_runner_tester.log` → `BA6B00155D97FEC9782B6135BE23E77955ECA202F9E92D5298C3A7E5C512303D`
- `_qua01_failclosed.log` → `930C0E9ED4D6C152D95D48AAFD6147DE3850BF537F305D71DD6B9D4EDE4A4F23`
- `_qua01_maf.log` → `5C09EDA8A64DB7FF24FAD8FAA22ED82AEFB31C1B6CA100DD609D870B4FFEB210`
- `_qua01_focused.log` → `DE2D6C31EC49DEDF3F31F849A02FA21D8F4B10365B7A5E736D341F97B8D1C791`

Senkron dokümanların son doğrulama öncesi SHA-256 değerleri:

- `docs/THREAT_MODEL.md` → `38EC9554E62049716CADB8CDE454AA689E5C4ADFA68CB69D6FEE340A5300E930`
- `docs/ARCHITECTURE.md` → `0A58DFD4026DA58DB227B13CE2E85349280C30EE71A799D2D916D083A2E2E874`
- `docs/ROADMAP.md` → `38BB640D48217FD13800BFD13C0B1FAE8CBA1FF044C6E5F49727E3942D96BE91`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `7580C0FF4295A00D8FB5181277F2082A0BB6BBFD6D78AD254389328C92CD4B95`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` → `0D08267532BCF0A8AB2FC86BEDF973262D40FC0575FF85D3DFC5BD6F0F6CDCC0`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` → `0338E690723DD65F7B5E9D3B016865A0E93483FA23D79A31F1F752176EA4E801`

### Kalan risk / shortcut

- Tester aşaması Windows AppContainer sınırına bağlıdır; Windows dışı platform kararı REL-04'te açıktır.
- Tester, kabul komutlarını yalnızca bir kez çalıştırır; bu görev model tabanlı keşifsel test üretimini kapsamaz.
- QUA-03'ün sınırlı düzeltme döngüsü bu görevde değil, sonraki görevde ele alınır.

---

## QUA-03 — MAF finite-state verify/review/fix döngüsü

- **Durum:** Tamamlandı (2026-11-01). Commit/push/branch/reset/clean yapılmadı; çalışma ağacı bilinçli olarak kirli bırakıldı.
- **Kapsam:** `implement → tester doğrulaması → bağımsız reviewer → sınırlı fix → yeniden doğrulama` akışı sonlu durum makinesine bağlandı. `max_corrections` kaldırıldı; kanonik alan `max_fix_rounds` (varsayılan 2, izinli aralık 0–5). `NEEDS_CHANGES` artık terminal değil, yalnızca ara durumdur.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/workflows/maf_workflow.py`: sonlu durum makinesi, terminal durumlar, sanitize fix kanıtı, aynı test hatasının normalize tekrarı, patch mirası ve idempotent yeniden çağrı.
  - `src/respected_orchestrator/engine/runner.py`: `max_fix_rounds` doğrulaması (0–5), `max_corrections` açık reddi, `fix_evidence` şeması.
  - `src/respected_orchestrator/workflows/planner.py`: plan formatı `max_fix_rounds` kullanıyor.
  - `tests/workflows/test_maf_state_machine.py`: 6 vaka + kanonik sınır testi.
  - `tests/workflows/test_reviewer_reliability.py`: terminal başarısız koşunun yeniden çalıştırılmadığı ve kayıt çoğaltmadığı doğrulandı.
  - `docs/ARCHITECTURE.md`, `docs/COMMANDS.md`, `docs/USAGE.md`, `docs/adr/ADR-005-failure-taxonomy.md`, yol haritası ve issue CSV senkron edildi.

### Sonlu durum makinesi

```text
START
  -> WORKER (round 0)
  -> TEST_FAILURE? -> sınırlı fix -> WORKER (yeniden doğrula)
  -> REVIEW
       APPROVED                -> MASTER_APPROVED
       HUMAN_APPROVAL_REQUIRED -> HUMAN_APPROVAL_REQUIRED
       REJECTED                -> REJECTED
       CANCELLED               -> CANCELLED
       STALE_PATCH             -> STALE_PATCH
       REPEATED_TEST_FAILURE   -> REPEATED_TEST_FAILURE
       NEEDS_CHANGES           -> sınırlı fix -> WORKER -> REVIEW
       sınır doldu             -> FIX_ROUNDS_EXHAUSTED
```

Terminal durum kümesi: `MASTER_APPROVED`, `HUMAN_APPROVAL_REQUIRED`, `REJECTED`, `CANCELLED`, `STALE_PATCH`,
`REPEATED_TEST_FAILURE`, `FIX_ROUNDS_EXHAUSTED`. Her sonuç `state`, `reason`, `fix_rounds`, `transitions`,
`evidence`, `failure_class` ve `retryable` alanlarını taşır. `fix_rounds` her durumda
`{"limit": N, "used": U, "remaining": R}` biçimindedir.

### 6/6 vaka tablosu

| # | Senaryo | Beklenen son state | Kanıtlayan test |
|---|---|---|---|
| 1 | Test hatası düzelir | `MASTER_APPROVED` | `test_a_test_failure_is_fixed_from_sanitized_evidence_and_approved` |
| 2 | Aynı normalize test hatası döner | `REPEATED_TEST_FAILURE` | `test_the_same_normalized_test_failure_stops_before_the_reviewer` |
| 3 | Reviewer reddeder | `REJECTED` | `test_a_reviewer_rejection_is_terminal_and_never_fixed` |
| 4 | Kullanıcı iptal eder | `CANCELLED` | `test_cancellation_before_a_fix_is_reported_without_starting_it` |
| 5 | Maksimum tur biter | `FIX_ROUNDS_EXHAUSTED` | `test_fix_rounds_are_bounded_and_a_review_correction_inherits_verified_patch` |
| 6 | Patch stale olur | `STALE_PATCH` | `test_a_stale_project_blocks_the_fix_before_it_starts` |

Ek sınır kanıtı: `test_max_fix_rounds_is_canonical_and_bounded` varsayılan 2, üst sınır 5 ve `max_corrections`
reddini doğrular. State machine dosyasında 7/7 test `OK`; odaklı genişletilmiş batarya 102/102 `OK`.

### Fix kanıt sözleşmesi

Fix çıktısı yalnızca şu anahtar kümesini taşır:
`run_id`, `checks`, `reason`, `failure_class`, `evidence_paths`. Ham `stdout`, `stderr` ve `error` alanları fix
kanıtına girmez. Aynı test hatası anahtarı `failure_class + komut + returncode` ile normalize edilir; ikinci kez
görüldüğünde reviewer çağrılmadan `REPEATED_TEST_FAILURE` döner. Reviewer kaynaklı düzeltme önceki doğrulanmış
`patch_sha256` değerini miras alır; test-hatası düzeltmesi başarısız patch'i miras almaz.

### Gerçek test çıktıları

```text
python -m unittest tests.workflows.test_maf_state_machine -v
Ran 7 tests in 7.127s
OK
STATE_EXIT_CODE=0
```

```text
python -m unittest tests.workflows.test_maf_workflow tests.workflows.test_maf_coding tests.workflows.test_maf_state_machine tests.engine.test_runner tests.workflows.test_reviewer_reliability -v
Ran 102 tests in 224.266s
OK
FOCUSED_EXIT_CODE=0
```

```text
python -m unittest tests.docs.test_decision_records -v
Ran 1 test in 0.077s
OK
DOCS_EXIT_CODE=0
```

```text
python -m unittest discover -s tests -t .
Ran 407 tests in 560.837s
OK
FULL_EXIT_CODE=0
```

PowerShell'in `Tee-Object` ile ürettiği `NativeCommandError` satırları harness gürültüsüdür; unittest `OK` ve
`EXIT_CODE=0` ile bitmiştir. Test hatası değildir.

### Kabul kriterleri

- [x] 6/6 vaka beklenen son state; state machine 7/7 `OK`.
- [x] `max_fix_rounds` varsayılan 2, üst sınır 5 ve yapılandırılabilir; `max_corrections` açıkça reddedilir.
- [x] Hiçbir otomatik fix main worktree'ye apply etmez; her vaka sonunda `calculator.py` değişmeden `value = 0` kalır.
- [x] Hata nedenleri imzalı `maf-result.json` ve sanitize `fix_evidence` üzerinden kanıt bağlantısı taşır.
- [x] İlgili regresyon ve paket testleri başarılı; tam regresyon 407/407 `OK`; `docs/ARCHITECTURE.md` ve ADR-005 senkron.
- [x] Resume idempotent: terminal başarısız koşu yeniden çalıştırılmaz ve yeni başarısız kayıt eklemez.

### Kanıt artefaktları (SHA-256)

- `docs/ilerleme/poc/qua03_focused_final.log` → `C37537CECB8F69C11256BBF0B4ED1AFF29078B16E296C6C577F92C50B9D657B4`
- `docs/ilerleme/poc/qua03_docs_gate_final.log` → `B859CBE6A7F40085E3671F63F793BA2D1BCE4D17827C24ED4D63FBBED68E5A29`
- `docs/ilerleme/poc/qua03_docs_gate_after_log.log` → `4AFCC149CB5D426186DF417C37C69CE5CE3311C5FF04B1CD6173750A80D4CB5A` (son KANIT_LOG düzenlemesinden sonra yeniden çalıştırıldı: 1/1 `OK`, exit 0)
- `docs/ilerleme/poc/qua03_full_suite_final.log` → `0BC04B86114FCD8381810C847013400231EB50447FF4F2466CD86D26DE14DEF3`

Doğrulama öncesi kaynak/test dosyaları:

- `src/respected_orchestrator/workflows/maf_workflow.py` → `5F240A0077F409EAECD6EC54EC2B59EFE5C3556919BC11363EE9FE2BC65F6340`
- `src/respected_orchestrator/engine/runner.py` → `205D3D9DD620B6F1874664C35BE7F1220A208220949450082618C98B7FD83DB6`
- `tests/workflows/test_maf_state_machine.py` → `5B72D8511B2642F393627C215290BE932E9EF2C54D7E02A1E72A627E4E8AB2C3`
- `tests/workflows/test_reviewer_reliability.py` → `33D85C370FD724B60BD0A457D6AE0597C039E9B42E5F071D2034480424360D48`
- `docs/ARCHITECTURE.md` → `0365BE93D8621119E314D3CCC1AC270D83A6D2FDBF824C05A918F0256938A0C2`

### Kalan risk / shortcut

- Fix turları aynı veri kökünde tek yazıcı kilidi altında çalışır; paralel proje hatları bu görevde genişletilmedi.
- Aynı normalize test hatası yalnızca `failure_class + komut + returncode` ile saptanır; serbest metin farkı yeni
  hata sayılır. Bu bilinçli bir sınırlamadır.
- QUA-04 bağımsız review/apply değişmezleri bu bölümün kapsamı dışındadır.

---

## QUA-04 — Bağımsız review ve apply değişmezleri

- **Durum:** Tamamlandı (2026-11-01). Commit/push/branch/reset/clean yapılmadı; çalışma ağacı bilinçli olarak kirli bırakıldı.
- **Kapsam:** Mevcut review/apply sözleşmesinin bağımsız, saldırgan testlerle ölçülmesi. Üretim kodu değiştirilmedi; yeni test dosyası ve doküman senkronu eklendi. Testler hem reddi hem de reddin yan etkisizliğini doğrular: başarısız senaryolarda `applied.json` oluşmaz ve proje dosyası değişmez.
- **Çıktı / değişen dosyalar:**
  - `tests/engine/test_review_apply_invariants.py` (yeni): 12 saldırgan ret + 1 meşru check→apply akışı.
  - `docs/ARCHITECTURE.md`: QUA-04 değişmezleri ve test kanıtı.
  - `docs/ROADMAP.md`: bağımsız review/apply maddesi tamamlandı.
  - `docs/ROADMAP_EXECUTION_PLAN.md` ve `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`: görev durumu ve kabul kutuları güncellendi.
  - `docs/ilerleme/respected_orchestrator_github_issues.csv`: QUA-04 `done`.
  - `docs/ilerleme/KANIT_LOG.md` (bu bölüm).

### 12/12 saldırgan ret + 1/1 meşru akış

| # | Senaryo | Beklenen ret | Kanıtlayan test |
|---|---|---|---|
| 1 | Bağımsızlık istenirken reviewer profili implementer ile aynı | `ROLE_INDEPENDENCE` | `test_01_same_reviewer_profile_is_rejected_when_independence_is_required` |
| 2 | Kanıt imzası sahte | `tampered` | `test_02_forged_evidence_signature_is_rejected` |
| 3 | Sonuç üretildikten sonra HEAD değişmiş | `stale` | `test_03_changed_head_makes_the_result_stale` |
| 4 | Precheck sonrası kaynak yarışta değişmiş | apply reddi | `test_04_apply_race_after_precheck_writes_nothing` |
| 5 | Token/retry bütçesi aşılmış | ödenmiş reviewer çağrısı yok | `test_05_token_retry_limit_stops_before_another_paid_review` |
| 6 | İnsan onayı gerekli fakat onay yok | `MAF approval` | `test_06_human_approval_required_flow_is_rejected_without_approval` |
| 7 | Patch SHA'sı kurcalanmış | `Patch tampered` | `test_07_patch_sha_mismatch_is_rejected` |
| 8 | Onay başka patch SHA'sına bağlı | `not bound` | `test_08_approval_bound_to_a_different_patch_is_rejected` |
| 9 | Aynı patch ikinci kez uygulanıyor | `already applied` | `test_09_second_apply_is_rejected` |
| 10 | Reviewer aynı implementer olarak atanmış | `ROLE_INDEPENDENCE` | `test_10_reviewer_cannot_be_the_implementer` |
| 11 | Tester serbest komut sağlamaya çalışıyor | `BAD_ASSIGNMENT` | `test_11_tester_is_report_only_and_cannot_supply_commands` |
| 12 | Execution/check tamamlanmadan apply | `Unsuccessful or pending` | `test_12_apply_before_check_or_execution_is_rejected` |
| +1 | Yeşil check→apply akışı | tam bir kez `applied` | `test_verified_check_then_apply_succeeds_once` |

Her ret testi ayrıca `applied.json` bulunmadığını ve `calculator.py` içeriğinin değişmediğini doğrular. Meşru testte patch SHA'sı imzalı `applied.json` içindeki SHA ile eşleşir.

### Gerçek test çıktıları

```text
python -m unittest tests.engine.test_review_apply_invariants -v
Ran 13 tests in 30.767s
OK
INVARIANTS_EXIT_CODE=0
```

```text
python -m unittest tests.engine.test_runner tests.engine.test_token_budget tests.workflows.test_maf_coding tests.workflows.test_reviewer_reliability -v
Ran 103 tests in 228.513s
OK
FOCUSED_EXIT_CODE=0
```

PowerShell'in `*>` ile yakaladığı `NativeCommandError` satırları unittest'in stderr yazımından kaynaklanan harness gürültüsüdür; komutlar `OK` ve exit kodu 0 ile tamamlanmıştır.

```text
python -m unittest discover -s tests -t .
Ran 420 tests in 651.727s
OK
FULL_EXIT_CODE=0
```

Tüm keşif (unit + workflow + security + packaging) 420/420 `OK`. Testlerin stderr ürettiği beklenen CLI kullanım
hataları yukarıdaki PowerShell `NativeCommandError` gürültüsünü oluşturur; sürecin sonucu `OK` ve exit kodu 0'dır.

### Kabul kriterleri

- [x] En az 12 invariant testi: 12 saldırgan ret + 1 meşru akış.
- [x] 12/12 doğru ret; her rette yan etkisizlik doğrulandı.
- [x] Otomatik merge/apply sayısı 0; ikinci apply ve execution öncesi apply reddedildi.
- [x] Mevcut check→apply akışı yeşil fixture ile 1/1 sürdü.
- [x] Tam regresyon 420/420 `OK`; doküman kapısı ve sonrasındaki yeniden doğrulama kanıt artefaktlarında kayıtlı.
- [x] `docs/ARCHITECTURE.md` ile ürün/güvenlik sözleşmesi senkron.

### Kanıt artefaktları (SHA-256)

- `docs/ilerleme/poc/qua04_invariants.log` → `077CE8702C69FF31E2AB4DE0E36BF4CCD772DAF28E6A4562639436E9A9E0DAB4`
- `docs/ilerleme/poc/qua04_focused.log` → `275F5459DABD836CA85C103652485B82CFEF6EA7BDB1872F24C118E30C6886EE`
- `docs/ilerleme/poc/qua04_docs_gate.log` → `55B8C366A4827A3F53EA50372185D3D1B332D779C9E18D22263CCB704F7F1DCC`
- `docs/ilerleme/poc/qua04_full_suite.log` → `7F94517029101A119C7E216010D71279CC7CBF764892EA125CF8D0066B7E2E8B`
- `tests/engine/test_review_apply_invariants.py` → `9CF0F2305B40647FBA56349F90BBCE5D0598CF7BB8C82C783765DF84085CB5BC`

Doğrulanan mevcut sözleşme kaynakları:

- `src/respected_orchestrator/engine/runner.py` → `205D3D9DD620B6F1874664C35BE7F1220A208220949450082618C98B7FD83DB6`
- `src/respected_orchestrator/engine/evidence.py` → `490F65122C879F5C03BE2C6DFD8CF7BF89AF21CA0A4068203A0D6FE256894773`
- `src/respected_orchestrator/workflows/roles.py` → `4AD4F1718251ED4937E2EDA18DA0894902B61878867E517C13EDA4F4B84BC5C9`
- `src/respected_orchestrator/workflows/maf_workflow.py` → `5F240A0077F409EAECD6EC54EC2B59EFE5C3556919BC11363EE9FE2BC65F6340`

Doküman/senkron dosyaları:

- `docs/ARCHITECTURE.md` → `187F36B64C24242000E746A0458354380AB2B8D389871B76F1312FA0B13CFCB8`
- `docs/ROADMAP.md` → `BF97FED144784F8FC86E572602FEB27B0C77DAEB740430AD88D735CA12EC5909`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `8A1333D07BC506598D581BE6FEB751766ABDBDADC28F39748B50F4800C8DA408`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` → `273DC2A086984114C358EACA1769CBECE0505E7238DC3F135EA40E35D0C1F0EE`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` → `CD1ABD5EDE3B9A438AEB072A799F5F13F103A957AB392A98E788274EAC63E967`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/ilerleme/poc/qua04_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
`KANIT_LOG.md` kendi hash listesine dahil edilmez (kendine referans döngüsünü önlemek için).

### Kalan risk / shortcut

- Bu görev yeni otomatik apply veya auto-merge yeteneği eklemez; yalnızca mevcut sözleşmeyi saldırgan testlerle sabitler.
- Testler geçici fixture depolarında çalışır; gerçek kullanıcı deposunda canlı yarış simülasyonu yapılmaz.
- Tester'ın yalnızca rapor üretmesi bu görevde doğrulandı; model tabanlı keşifsel test üretimi QUA-01 kapsamı dışındadır.

---

## SCH-01 — Plan taslağına DAG/ownership doğrulaması ekle

- **Durum:** Tamamlandı (2026-11-01). Commit/push/branch/reset/clean yapılmadı; çalışma ağacı bilinçli olarak kirli bırakıldı.
- **Kapsam:** `plan` taslağını düğüm/kenar DAG'ına normalize etmek; `id`, `depends_on`, `ownership`, `forbidden`, `acceptance` ve `budget` alanlarını üretmek; aşama ve hat `after` bağlantılarını genişletmek; döngü, bilinmeyen bağımlılık, geçersiz komut/zaman aşımı ve paralel ownership çakışmalarını motor tarafından reddetmek. `plan` yalnızca doğrulanmış taslak üretir; worker, proje veya kampanya başlatmaz.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/workflows/planner.py`: deterministik `_dag()` doğrulayıcısı, tam döngü yolu, toplu ownership tanısı, fail-closed tip/kapsam denetimi ve `dag` alanlı taslak.
  - `tests/workflows/test_planner.py`: 5 kabul senaryosu + tüm çakışan çiftlerin tek tanısı + bozuk tip sınıflarının çökme yerine `invalid` taslak üretmesi.
  - `docs/ARCHITECTURE.md`: §4/§5 DAG alanları, `after` genişlemesi, döngü/çakışma reddi ve sıfır worker sözleşmesi.
  - `docs/COMMANDS.md`, `docs/USAGE.md`: `plan` çıktısında `spec` ve `dag`; doğrulama ve başlatmama davranışı.
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`: SCH-01 durumu ve kabul kutuları.
  - `docs/ilerleme/respected_orchestrator_github_issues.csv`: SCH-01 `done`.
  - `docs/ilerleme/KANIT_LOG.md` (bu bölüm).

### 5/5 input sınıfı

| # | Girdi sınıfı | Beklenen tanı | Kanıtlayan test |
|---|---|---|---|
| 1 | Aynı aşamada 3 bağımsız hat | `drafted`; deterministik topolojik sıra; bağımlılık yok | `test_three_independent_nodes_are_valid_and_start_nothing` |
| 2 | `one -> two -> three` zinciri | `drafted`; sıra korunur | `test_a_chain_preserves_dependency_order` |
| 3 | `one -> two -> one` döngüsü | `invalid`; `Cycle detected: p/one -> p/two -> p/one`; `dag: null` | `test_a_cycle_is_rejected_with_its_path` |
| 4 | Paralel çapraz ownership (`src`, `src/a.py`, `src/b.py`) | `invalid`; bütün çakışan çiftler tek tanı | `test_overlapping_parallel_ownership_marks_every_conflict`, `test_all_overlap_pairs_are_reported_in_one_diagnostic` |
| 5 | `verify.command` argv dizi değil | `invalid`; `Command must be a non-empty JSON string array`; `dag: null` | `test_an_invalid_verify_command_is_rejected` |

Ek fail-closed testi (`test_malformed_spec_types_are_invalid_drafts_not_crashes`) `verify: null`, `project_root: null` ve metin
`budget.max_weighted_tokens` girdilerinin çökme veya kısmi geçerli DAG üretmediğini doğrular. Bu, `_dag()` başarılı olsa
bile `project._spec()` reddettiğinde `dag` alanının yayımlanmadığı düzeltmesini kapsar.

### Gerçek test çıktıları

```text
python -m unittest tests.workflows.test_planner -v
Ran 13 tests in 2.399s
OK
EXIT_CODE=0
```

```text
python -m unittest tests.workflows.test_planner tests.workflows.test_project tests.workflows.test_project_adversarial tests.workflows.test_project_recovery tests.workflows.test_campaign tests.workflows.test_roles -v
Ran 78 tests in 135.170s
OK
ELAPSED_SECONDS=136.157
EXIT_CODE=0
```

```text
python -m unittest tests.docs.test_decision_records -v
Ran 1 test in 0.119s
OK
EXIT_CODE=0
```

```text
python -m unittest discover -s tests -t .
Ran 427 tests in 584.750s
OK
ELAPSED_SECONDS=585.636
EXIT_CODE=0
```

Tam keşifte görülen beklenen `unittest` kullanım hatası satırları CLI argüman doğrulama testlerinin stderr çıktısıdır;
sürecin sonucu 427/427 `OK` ve exit kodu 0'dır.

### Kabul kriterleri

- [x] 5/5 input sınıfı doğru tanılanır.
- [x] Döngü kabulü 0; döngü tam yoluyla reddedilir ve hiçbir DAG yayımlanmaz.
- [x] Bilinen paralel ownership çakışmaları %100 işaretlenir; bütün çiftler tek tanıda listelenir.
- [x] `plan` komutunun başlattığı worker sayısı 0; `projects/`, `campaigns/` ve `runs/` oluşmaz.
- [x] İlgili regresyon 78/78 ve tam regresyon 427/427 `OK`; doküman kapısı `OK`; `docs/ARCHITECTURE.md` senkron.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/workflows/planner.py` → `CDE8112AE1A155ACF25DA713385DFA2613130D62C1F6B82A0B50ABC1903FE5CE`
- `tests/workflows/test_planner.py` → `31A0E1E4608B5AB2B63EAEFFA9E89946DE12AF81FB85F9823C416F5E5E058963`
- `docs/ARCHITECTURE.md` → `ED9652A2DDDEC49E0C9DD81A6A864EDABB074AE9B9E2D52EB87596C5FD8314A8`
- `docs/COMMANDS.md` → `C3B8A7FF1CBD6BEA93F928FF91DC15CEE4B960DFB56793BAC9046ACA41E94D8C`
- `docs/USAGE.md` → `4AA4B3B6BEF6206187091F6E549DDF5D3B68624FE6680652E41FB7D638937F70`
- `docs/ROADMAP.md` → `ED025731FBCD8EE4511B98344523BB7ACAF48F63C1EE5C7910B379B1B43EB58B`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `1C4FD562BA374BA7BB4D0FC78678943CE219724FCE65CEFAA52A19491402F538`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` → `CFE976AB981D6944A775BE78A917D8BD8305A1E5BB3EFE4EF53DEE7D075EE5A6`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` → `33023C72A5D487D33F321FAA67F5172A997FDBC4217BDB3C75B67A4A89680E4B`
- `docs/ilerleme/poc/sch01_planner_focused.log` → `6C252CB037F59206D98F5648C142A968916A4D15B515FFD4DBA530A839711DE7`
- `docs/ilerleme/poc/sch01_related_regression.log` → `D05E348DE2168FC0098DD5C160914694811EAAC7C45A23951D8544C88D639762`
- `docs/ilerleme/poc/sch01_docs_gate.log` → `6E4172ABA50A8A3A4C0FDCC57D44A4186100CE17B23284B719F3249403AB19CF`
- `docs/ilerleme/poc/sch01_full_suite.log` → `5AB795D15F6391EA10AA5E0671FCE6BAA957C2191D9A306C06182DAF84957E68`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/ilerleme/poc/sch01_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
`KANIT_LOG.md` kendi hash listesine dahil edilmez (kendine referans döngüsünü önlemek için).

### Kalan risk / shortcut

- Bu görev statik DAG/ownership doğrulamasıdır; hazır kuyruk, eşzamanlılık sınırı ve risk tabanlı çalıştırma SCH-02 kapsamındadır.
- Ownership çakışması yol kapsayıcılığıyla ölçülür; sembolik bağlantı veya üretim sırasında değişen dosya kümeleri çalışma anında yeniden doğrulanmaz.
- Düğüm sayısı 12 aşama × 8 hat ile sınırlıdır; döngü taraması bu sınır içinde özyinelemeli ve deterministiktir.

---

## SCH-02 — Bağımlılık ve risk tabanlı scheduler

- **Durum:** Tamamlandı (2026-11-01). Commit/push/branch/reset/clean yapılmadı; çalışma ağacı bilinçli olarak kirli bırakıldı.
- **Kapsam:** Kampanya hatlarını deterministik hazır kuyruktan sınırlı eşzamanlılıkla çalıştırmak; `after` bağımlılıklarını yalnızca bütün öncüller `MASTER_APPROVED` olduğunda açmak; hata/timeout/iptal durumlarını kalıcı state geçişleriyle kaydetmek; aynı proje kökünde ownership kapsamı çakışan hatları serialize etmek ve bekleyen/çalışan kampanyayı güvenli biçimde iptal etmek.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/workflows/campaign.py`: `max_parallel` 1–8 doğrulaması, varsayılan `min(4, hat sayısı)`, deterministik hazır kuyruk, sınırlı eşzamanlılık, bağımlılık/ownership serileştirmesi, state geçişleri, timeout/hata sınıflandırması ve `cancel_campaign()`.
  - `src/respected_orchestrator/__main__.py`: `campaign-cancel` CLI yönlendirmesi.
  - `tests/workflows/test_campaign_scheduler.py`: 10 scheduler testi; altı temel state geçişi, bağımlılık hatası, runner hatası, timeout, iptal ve sınır/serialization senaryoları.
  - `tests/test_main.py`: `campaign-cancel` CLI dispatch testi.
  - `docs/ARCHITECTURE.md`: scheduler sözleşmesi, state geçişleri ve iptal davranışı.
  - `docs/COMMANDS.md`, `docs/USAGE.md`: `campaign-run` seçenekleri ve `campaign-cancel` kullanımı.
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`: SCH-02 durumu ve kabul kutuları.
  - `docs/ilerleme/respected_orchestrator_github_issues.csv`: SCH-02 `done`.
  - `docs/ilerleme/KANIT_LOG.md` (bu bölüm).

### 6/6 state geçişi

| # | Geçiş | Beklenen sonuç | Kanıtlayan test |
|---|---|---|---|
| 1 | `QUEUED → RUNNING` | Hat başlar ve zaman damgalı transition yazılır | `test_scheduler_records_queued_to_running` |
| 2 | `RUNNING → MASTER_APPROVED` | Başarılı hat onaylanır | `test_scheduler_records_running_to_approved` |
| 3 | `QUEUED → SKIPPED` | Başarısız öncülün bağımlı zinciri başlamaz | `test_scheduler_records_dependency_failure_to_skipped` |
| 4 | `RUNNING → FAILED` | Runner hatası `lane_error` nedeniyle kaydedilir | `test_scheduler_records_runner_error_to_failed` |
| 5 | `RUNNING → TIMED_OUT` | Timeout hata olarak kaydedilir; son master başlamaz | `test_scheduler_records_timeout_to_timed_out` |
| 6 | `RUNNING/QUEUED → CANCELLED` | İptal işareti bekleyen ve dönen çalışan hatları `CANCELLED` yapar | `test_scheduler_records_cancel_to_cancelled` |

Ek scheduler testleri: `test_max_parallel_two_and_dependent_starts_after_approval` gerçek eşzamanlılık zirvesini `2` tutar ve
bağımlı hattın `a` `MASTER_APPROVED` olmadan başlamadığını doğrular; `test_overlapping_ownership_is_serialized_even_with_free_capacity`
çakışan iki hattın boş kapasiteye rağmen eşzamanlılığını `1` tutar; `test_max_parallel_is_validated` geçersiz değerleri reddeder;
`test_cancel_before_run_never_launches_the_final_master` çalıştırma öncesi iptalde `QUEUED → CANCELLED` geçişini ve final master
sayısının `0` olduğunu doğrular.

### Gerçek test çıktıları

```text
python -m unittest tests.workflows.test_campaign -v
Ran 11 tests in 22.353s
OK
ELAPSED_SECONDS=23.063
EXIT_CODE=0
```

```text
python -m unittest tests.workflows.test_campaign_scheduler -v
Ran 10 tests in 28.470s
OK
ELAPSED_SECONDS=29.186
EXIT_CODE=0
```

```text
python -m unittest tests.workflows.test_campaign tests.workflows.test_campaign_scheduler tests.workflows.test_project tests.workflows.test_project_adversarial tests.workflows.test_project_recovery tests.workflows.test_planner tests.workflows.test_roles tests.engine.test_worker_policy tests.test_main -v
Ran 116 tests in 171.621s
OK
ELAPSED_SECONDS=172.347
EXIT_CODE=0
```

```text
python -m unittest tests.docs.test_decision_records -v
Ran 1 test in 0.077s
OK
ELAPSED_SECONDS=0.310
EXIT_CODE=0
```

```text
python -m unittest discover -s tests -t .
Ran 437 tests in 605.860s
OK
ELAPSED_SECONDS=606.676
EXIT_CODE=0
```

Tam keşifte görülen `unittest: error: argument command: invalid choice: 'update'` satırı CLI argüman doğrulama testinin
beklenen stderr çıktısıdır; sürecin sonucu 437/437 `OK` ve exit kodu 0'dır.

### Kabul kriterleri

- [x] Hazır kuyruk deterministiktir ve `max_parallel` 1–8 aralığında doğrulanır.
- [x] Bağımlı hat yalnızca bütün öncülleri `MASTER_APPROVED` ise başlar; başarısız öncül bağımlı zinciri `SKIPPED` yapar.
- [x] Aynı proje kökünde ownership kapsamı çakışan hatlar serileştirilir.
- [x] Hata, timeout ve iptal durumları `result.json` içinde zaman/neden taşıyan state geçişleriyle raporlanır.
- [x] İptal edilen kampanyada bekleyen/çalışan hatlar `CANCELLED` olur ve son master başlatılmaz.
- [x] Odaklı scheduler testleri 10/10, ilgili regresyon 116/116 ve tam regresyon 437/437 `OK`; doküman kapısı `OK`.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/workflows/campaign.py` → `A84BF5617E53BB9AA6262E0A32C43368C7CB2B70C5DAF1455E43B2C8419A0E62`
- `src/respected_orchestrator/__main__.py` → `9E487F9D4D43AC6DC803B6FB61ADF707D94C1AD03872A5DE868E9BC162748679`
- `tests/workflows/test_campaign_scheduler.py` → `218130D5A8793207E948E4133E65EB0D10112B6BCA2D1A843C5DC87A2B703C38`
- `tests/test_main.py` → `C230401BA800F79413DBFFCC31B695D125E907EA115FB9DE9200B84EC46EE995`
- `docs/ARCHITECTURE.md` → `A2C5C60A072D44A0941618357A2D8453AF40CFB462FB1D645DA9FA966F87B4A5`
- `docs/COMMANDS.md` → `9A0ABEBAB1234173BDA04048C43B47B6B8754C004D1F1F72F03CDC3CB0D0D975`
- `docs/USAGE.md` → `5498611E02C900F8C6830E93AC0F4FC803CE39245F11D24B7593533FE03AB694`
- `docs/ROADMAP.md` → `74EE6ABA9E342D121DDFC04B5752F927F88DC55E804002966498004A7D9A762F`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `3470BA1D7BF1CAD3C5D9ED3BCB7720D7ACE44F43C056567576B1BCDB664636A0`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` → `E4897582D2A5639A0C6F3994B5FFE6E4BD42A28D7C1C6FE73585EF56D23862F5`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` → `C964AE653F85262CFB9DAFFB1BECB11C6D4DD9A64992838814BAF99ECC35B062`
- `docs/ilerleme/poc/sch02_campaign_baseline.log` → `88A1E206019F67CC51B1442CAA68B4D42FCFA6D95F7B92088D19E10C2988BBCD`
- `docs/ilerleme/poc/sch02_scheduler_focused.log` → `07967650F7B599E2C953851F005F3CF4584EB61E551A5F76B07A4B4989D5FABA`
- `docs/ilerleme/poc/sch02_related_regression.log` → `68877F60DAF51C49CA3D2A4029D9246938688F9DE653D85B430C204BB8235293`
- `docs/ilerleme/poc/sch02_docs_gate.log` → `16B88813FDA7141CD3CE60CC1E17D2E1F9F296A1DCCC83107CC02815CEE1E02A`
- `docs/ilerleme/poc/sch02_full_suite.log` → `06158FB03ED365C2FB28B16390E0978A86D6D00ABEF9FF5278C842BB7E4DACCC`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/ilerleme/poc/sch02_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
`KANIT_LOG.md` kendi hash listesine dahil edilmez (kendine referans döngüsünü önlemek için).

### Kalan risk / shortcut

- Scheduler risk tabanlı önceliği mevcut `after` DAG'si ve ownership çakışması üzerinden uygular; dinamik maliyet tahmini COST görevlerinin kapsamındadır.
- Ownership kapsamı çalışma başında normalize edilir; hat çalışırken dışarıdan değişen dosya kümeleri yeniden keşfedilmez.
- İptal işareti işbirlikli bir dosya sinyalidir; sert süreç sonlandırması ayrı bir güvenlik/operasyon kararıdır.

---

## SCH-03 — İki worktree sonucunu güvenli entegre et

- **Durum:** Tamamlandı (2026-11-01). Commit/push/branch/reset/clean yapılmadı; çalışma ağacı bilinçli olarak kirli bırakıldı.
- **Kapsam:** İki imzalı/doğrulanmış run sonucunu geçici detached Git worktree içinde birleştirmek; patch'leri sırayla `git apply --check` ve `git apply` ile denemek; tek bir combined verification grubu çalıştırmak; başarıda imzalı `integration.json` ve `combined.patch` üretmek; hiçbir durumda gerçek repoyu otomatik apply/commit etmemek.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/engine/integration.py`: geçici worktree, sıralı apply/check, combined verification, imzalı karar kanıtı ve fail-closed hata sınıflandırması (`integration_conflict`, `head_drift`, `verification_failed`, `invalid_input`, `base_mismatch`, `engine_error`, `real_repo_mutation`).
  - `src/respected_orchestrator/__main__.py`: `integrate` CLI komutu ve stdin JSON yönlendirmesi.
  - `tests/engine/test_integration.py`: 5 zorunlu entegrasyon senaryosu.
  - `tests/test_main.py`: `integrate` CLI dispatch testi.
  - `docs/ARCHITECTURE.md`: geçici integration worktree, sıralı apply/check, fail-closed davranış ve gerçek repoyu değiştirmeme sözleşmesi.
  - `docs/COMMANDS.md`, `docs/USAGE.md`: `integrate` komutu ve kullanıcı akışı.
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`: SCH-03 durumu ve kabul kutuları.
  - `docs/ilerleme/respected_orchestrator_github_issues.csv`: SCH-03 `done`.
  - `docs/ilerleme/KANIT_LOG.md` (bu bölüm).

### 5/5 entegrasyon senaryosu

| # | Senaryo | Beklenen sonuç | Kanıtlayan test |
|---|---|---|---|
| 1 | Aynı satırı değiştiren iki patch | `integration_conflict`; karar kanıtı yok; gerçek repo değişmez | `test_01_same_line_conflict_is_rejected_without_real_mutation` |
| 2 | Bağımsız dosyalar | İki patch sırayla uygulanır; 1/1 combined verification geçer; imzalı karar üretilir | `test_02_independent_patches_are_combined_after_one_verification` |
| 3 | Base HEAD drift | `head_drift`; staging başlamadan reddedilir | `test_03_head_drift_is_rejected_before_staging` |
| 4 | İlk patch başarılı, ikincisi başarısız | Kısmi apply 0; gerçek repo değişmez; karar kanıtı yok | `test_04_first_patch_applies_and_second_fails_without_partial_real_apply` |
| 5 | Combined verification başarısız | `verification_failed`; gerçek return code'lar korunur; karar kanıtı yok | `test_05_combined_verification_failure_publishes_no_decision_evidence` |

Doğrulama hatası ayrıntısı `_Stop(details=...)` üzerinden sonuç nesnesine taşınır; böylece `verification` listesi ve gerçek
return code'lar (örneğin `[0, 7]`) kaybolmaz.

### Gerçek test çıktıları

```text
python -m unittest tests.engine.test_integration -v
Ran 5 tests in 35.735s
OK
ELAPSED_SECONDS=36.036
EXIT_CODE=0
```

```text
python -m unittest tests.engine.test_integration tests.engine.test_runner tests.engine.test_lanes tests.engine.test_review_apply_invariants tests.engine.test_worker_policy tests.test_main -v
Ran 104 tests in 172.949s
OK
EXIT_CODE=0
```

```text
python -m unittest discover -s tests -t .
Ran 442 tests in 584.373s
OK
ELAPSED_SECONDS=585.018
EXIT_CODE=0
```

İlgili regresyon logunda PowerShell'in `2>&1 | Tee-Object` davranışından kaynaklanan `NativeCommandError` sarmalama satırları
bulunur; `Ran 104 tests` ve `OK` satırları ile exit kodu `0` gerçek sonucu doğrular. Tam keşifte görülen
`unittest: error: argument command: invalid choice: 'update'` satırı CLI argüman doğrulama testinin beklenen stderr çıktısıdır.

### Kabul kriterleri

- [x] 5/5 senaryo deterministik; her rette `applied.json` oluşmadı ve proje dosyası değişmedi.
- [x] Herhangi aşamada hata halinde gerçek repo SHA değişimi 0.
- [x] İki bağımsız başarılı patch 1/1 combined verification sonrasında karar için hazır.
- [x] Kısmi apply 0.
- [x] Odaklı entegrasyon 5/5, ilgili regresyon 104/104 ve tam regresyon 442/442 `OK`; doküman kapısı `OK`; `docs/ARCHITECTURE.md` senkron.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/engine/integration.py` → `11D2A51681914C86E8E7DD87E5A6558AA83A2610FE3B6BF314BF21786F95A48C`
- `src/respected_orchestrator/__main__.py` → `3EFEE425FAC1D21DD69A5BDAADB03E3950F8B0CE0C9E9028C4E0A59132546EA4`
- `tests/engine/test_integration.py` → `DB5FE0C9767C3F6D9C32FA4EB3A33543889BEA6565182061663014B88E91FA9A`
- `tests/test_main.py` → `BA4DA1E55383D3AD6AE985BF30A71D9915B1AFD68936510C2583B0E291FAD91B`
- `docs/ARCHITECTURE.md` → `35107969CD8608DB81D846139B1EA392A4B9234DDD17610946CE7FAA0DA26D82`
- `docs/COMMANDS.md` → `FE21385B150C237D5A064C3A01CBE6B77435F032B7FF38F546E9E05489AEC975`
- `docs/USAGE.md` → `4A54153905D08CC6609AA150FB26A60E26440E5976B2A082AA36AF076AC9D67A`
- `docs/ROADMAP.md` → `F3CCC568A21F027B893EB5D0AEB4DF43F197617F5C49F748B59CB8F363A980C5`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `41F6FB732728C45B87AB6833FD1070729DCC266BBC55F9B408E91C0CCE4137FB`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` → `42D8C006072B2CF19F037DB391B47135E748DD61A914517F7609AEF31A7AC544`
- `docs/ilerleme/poc/sch03_integration_focused.log` → `386FFFEAA7A213932341E490A52946CA2B20098DAFB6431F59D88CD0AC7DEBF0`
- `docs/ilerleme/poc/sch03_related_regression.log` → `C71FA770C89AB7616B6619A87C5A5A2AC9FA6762E8F4832452DDAC95ABC64D26`
- `docs/ilerleme/poc/sch03_full_suite.log` → `9F285834B5CE0F8207321A2731DC7D434563D801149EEEAEC82551506B1D137F`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/ilerleme/poc/sch03_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
`KANIT_LOG.md` kendi hash listesine dahil edilmez (kendine referans döngüsünü önlemek için).

### Kalan risk / shortcut

- Entegrasyon yalnızca karar kanıtı üretir; gerçek repoya apply/commit ayrı ve insan onaylı bir adımdır.
- Patch sırası girdi sırasıdır; bağımsız patch'ler arasında semantik çakışma analizi yapılmaz, combined verification esas alınır.
- Geçici worktree temizliği hata yollarında da denenir; işletim sistemi kilidi nedeniyle kalıntı oluşursa sonraki çalıştırma yeni worktree kullanır.

---

## SCH-04 — coordinator rolünü iş akışı planlayıcısına bağla

- **Durum:** Tamamlandı (2026-11-02). Commit/push/branch/reset/clean yapılmadı; çalışma ağacı bilinçli olarak kirli bırakıldı.
- **Kapsam:** `coordinator` rolünü yalnızca plan ve rol ataması üreten yürütülebilir bir planlama aşamasına bağlamak. Coordinator; aynı planner DAG ve project spec doğrulayıcılarından geçen taslak üretir, açık rol atamalarını sessizce değiştirmez, shell/apply/worker başlatma yetkisi kullanamaz.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/workflows/coordinator.py`: coordinator promptu, yetki reddi, DAG/project doğrulaması, rol çözümlemesi, atomik `drafts/coordinator-*.json` kaydı ve `{shell:false, apply:false, workers:false}` yetki sözleşmesi.
  - `src/respected_orchestrator/__main__.py`: `coordinate` CLI komutu ve stdin JSON yönlendirmesi.
  - `src/respected_orchestrator/engine/runner.py`: coordinator bir görev rolü olarak atanırsa `ROLE_NOT_EXECUTABLE`; doğru komut olarak `coordinate` önerilir.
  - `tests/workflows/test_coordinator.py`: 5 zorunlu senaryo.
  - `tests/test_main.py`, `tests/workflows/test_roles.py`: CLI dispatch ve rol sınırı regresyonları.
  - `docs/ARCHITECTURE.md`, `docs/COMMANDS.md`, `docs/USAGE.md`: coordinator sözleşmesi ve `coordinate` kullanımı.
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`: SCH-04 durumu ve kabul kutuları.
  - `docs/ilerleme/respected_orchestrator_github_issues.csv`: SCH-04 `done`.
  - `docs/ilerleme/KANIT_LOG.md` (bu bölüm).

### 5/5 coordinator senaryosu

| # | Senaryo | Beklenen sonuç | Kanıtlayan test |
|---|---|---|---|
| 1 | Geçerli, birbirinden bağımsız iki lane | Doğrulanmış DAG ve rol atamaları; 0 worker/proje/kampanya; shell/apply/workers `false` | `test_valid_dag_yields_a_plan_and_assignments_without_starting_workers` |
| 2 | Worker `command` ve faz `auto_apply` önerisi | İkisi de `invalid`; 0 worker; uygulama yetkisi yok | `test_command_and_auto_apply_proposals_are_rejected_with_zero_workers` |
| 3 | Döngüsel DAG | `invalid`; DAG/atama üretilmez; 0 worker | `test_a_cycle_is_rejected_with_no_work` |
| 4 | Kullanılamayan açık rol ataması | `ROLE_UNAVAILABLE`; sessiz fallback/override yok | `test_an_unusable_explicit_assignment_is_an_error_not_a_silent_override` |
| 5 | Prompt injection ve sahte `command`/`auto_apply` çıktısı | `invalid`; yetki artışı yok; sahte delimiter kapanışı promptta etkisiz | `test_prompt_injection_cannot_grant_shell_or_apply_authority` |

Coordinator plan doğrulaması `command`, `auto_apply`, `allow_apply` ve `shell` alanlarını reddeder; yalnızca motor sahipli aşama
`verify` komutlarındaki `command` alanına izin verir. Geçersiz planda `0` worker başlar ve karar taslağı `invalid` kaydedilir.

### Gerçek test çıktıları

```text
python -m unittest tests.workflows.test_coordinator -v
Ran 5 tests in 0.588s
OK
ELAPSED_SECONDS=0.883
EXIT_CODE=0
```

```text
python -m unittest tests.workflows.test_coordinator tests.workflows.test_roles tests.test_main tests.workflows.test_planner tests.workflows.test_project tests.engine.test_runner -v
Ran 75 tests in 86.122s
OK
ELAPSED_SECONDS=86.682
EXIT_CODE=0
```

```text
python -m unittest discover -s tests -t .
Ran 447 tests in 587.998s
OK
ELAPSED_SECONDS=588.631
EXIT_CODE=0
```

Tam keşifte görülen `unittest: error: argument command: invalid choice: 'update'` satırı CLI argüman doğrulama testinin beklenen stderr çıktısıdır.

### Kabul kriterleri

- [x] 5/5 senaryo deterministik.
- [x] Geçersiz planlarda `0` worker/proje/kampanya başladı.
- [x] Coordinator doğrudan shell/apply/worker yetkisi `0`.
- [x] Açık atamalarda sessiz override `0`; kullanılamayan atama hata verdi.
- [x] Odaklı 5/5, ilgili regresyon 75/75 ve tam regresyon 447/447 `OK`; doküman kapısı `OK`; `docs/ARCHITECTURE.md` senkron.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/workflows/coordinator.py` → `DDBEAB7100C5FB3AED04308AEFDB6E96A7F8D08DE5276A3C8214E4F42635C5DA`
- `src/respected_orchestrator/__main__.py` → `FC5F0583D1F5297D40DD55C140234B4994E0A8D106530250D838B00A8B6492C9`
- `src/respected_orchestrator/engine/runner.py` → `EEBAF1B5FA4EC8ED68042812606A8565279D9C33CC467C01406EAEBE9C011B2A`
- `tests/workflows/test_coordinator.py` → `4CBF9ABE1D2FFA3E2F9410944D7CB0A94EB90E86AB904BE543131B97898C8F2E`
- `tests/test_main.py` → `ADB4D9CB5F9C5043D74EF5325A7423CC8C1646A9E29428DD521ED36E253A7C4B`
- `tests/workflows/test_roles.py` → `E982A51838E12270A61723F5AC5691AA5BCD02F46D27B7E1C54D7002743E4F46`
- `docs/ARCHITECTURE.md` → `CFD7DA64ED14EBAD545027F8B57F9BB06E6D739FE8ADF8384A2C584446886538`
- `docs/COMMANDS.md` → `DDD0306306A2CBAB4E820D7DC64049A74D09053D4D8CF63B02D22E491E0E121B`
- `docs/USAGE.md` → `0D62136CF680005A91898E9648055C5CBE0A1B8CD26E40DB0B37379F5336003E`
- `docs/ROADMAP.md` → `513C10C849B5E01859A063365ADFB8D55F3CA1B980BE3FE6F62D23117EB5CAE4`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `83FD4BA7BDF866E3F107F21C99FC0F95E64A2D8B3D7A9E159D831582338268B5`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` → `796EB0008367AE21DB0560F0D061D58B7E290B1DC4F8FD4A7D0D04D554163453`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` → `FC37BE78574550D422A8A394F2495F7E74BCF17B79F8CA5183C493F80A0F123B`
- `docs/ilerleme/poc/sch04_coordinator_focused.log` → `790D70DCBBFD071D3598C92006C338011368E1F7757BE089513524890EC20142`
- `docs/ilerleme/poc/sch04_related_regression.log` → `8917982DB6B1E0C7ABD9E49CB02A954025B1E5E5DB1E84C972E91B365F4DE4BC`
- `docs/ilerleme/poc/sch04_full_suite.log` → `1EEA3F0AEC1A4DED3617477E1BE2EF371EF6B7507878698635D90BEAB274D9B7`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/ilerleme/poc/sch04_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
`KANIT_LOG.md` kendi hash listesine dahil edilmez (kendine referans döngüsünü önlemek için).

### Kalan risk / shortcut

- Coordinator yalnızca doğrulanmış plan ve rol ataması üretir; planı başlatmak ayrı ve insan onaylı normal `project-start` yolundan geçer.
- Model çıktısındaki yapısal yetki reddi fail-closed'dır; ancak modelin plan kalitesi/ölçümü bu görevin kapsamı dışındadır.
- Aynı saniyede iki taslak üretilirse dosya adı çakışabilir; atomik yazım bozuk JSON üretmez, fakat taslak kimliği için ek benzersizlik ileride ele alınmalıdır.

---

## RES-01 — Checkpoint ve handoff veri modeli

- **Durum:** Tamamlandı (2026-11-02). Commit/push/branch/reset/clean yapılmadı; çalışma ağacı bilinçli olarak kirli bırakıldı.
- **Kapsam:** run, kampanya ve proje için ortak; imzalı, atomik ve sürümlü kurtarma anlık görüntüsü. Snapshot yalnızca repo kimliği, rol/tur, sıradaki eylem, tamamlanan kontrollerin hash'leri ve sert limitleri taşır; worker promptu veya istek gövdesi taşımaz. Gerçek kill/restart ve FSM entegrasyonu bu görevde değil, RES-02 kapsamındadır.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/workflows/checkpoint.py`: v2 kapalı şema, doğrulama, imzalı/atomik yazma, veri kökü sınırı, `RESUMABLE`/`NEEDS_REVIEW`, HEAD kontrolü ve v1→v2 tek seferlik göç.
  - `tests/workflows/test_checkpoint.py`: 11 test; SIGTERM, bozuk geçici dosya, yarım state, v1 göçü, HEAD drift, atomik değiştirme kesintisi, sır/prompt reddi, üç görev türü, yeni şema/tamper/bozuk JSON/eksik dosya ve path escape.
  - `src/respected_orchestrator/workflows/checkpoint.py`: Git HEAD okuması `engine/winproc.run` üzerinden yapılır; ilk tam suite'in yakaladığı görünür pencere regresyonu böylece kapandı.
  - `docs/ARCHITECTURE.md`: checkpoint sözleşmesi, atomiklik, fail-closed durumlar, gizli veri yasağı ve v1 göçü.
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`: görev durumu ve kabul kutuları.
  - `docs/ilerleme/respected_orchestrator_github_issues.csv`: RES-01 `done`.
  - `docs/ilerleme/KANIT_LOG.md` (bu bölüm).

### Senaryo matrisi

| # | Senaryo | Beklenen sonuç | Kanıtlayan test |
|---|---|---|---|
| 1 | İş ortasında SIGTERM | Son tam snapshot `RESUMABLE`; yarım dosya okunmaz | `test_sigterm_mid_operation_leaves_the_last_atomic_snapshot_resumable` |
| 2 | Bozuk `.state-*.tmp` | Geçici dosya yok sayılır; önceki snapshot `RESUMABLE` | `test_a_corrupt_temporary_file_is_never_read_and_cannot_damage_the_snapshot` |
| 3 | Yarım ama imzası geçerli state | `NEEDS_REVIEW` / `incomplete_snapshot` | `test_half_of_a_validly_signed_state_is_needs_review` |
| 4 | v1 snapshot | Bir kez v2'ye göç; ikinci inceleme byte-stabil; `.v1.bak` korunur | `test_v1_migrates_once_and_the_second_inspection_is_byte_stable` |
| 5 | Farklı repo HEAD | `NEEDS_REVIEW` / `repo_head_changed`; otomatik devam yok | `test_a_different_git_head_is_needs_review` |
| 6 | `os.replace` ortasında kesinti | Önceki tam snapshot korunur; geçici dosya kalmaz | `test_interrupted_replace_keeps_the_previous_complete_snapshot` |
| 7 | Prompt, env, API anahtarı, request body, sır deseni | Yazımdan önce ret; dosya oluşmaz | `test_prompt_secret_api_key_and_environment_dumps_are_rejected_before_writing` |
| 8 | Kapalı şema taraması | Prompt/sır alanı yok; yalnızca v2 alanları | `test_the_closed_schema_contains_no_prompt_or_secret_payload` |
| 9 | run / campaign / project | Üç tür de aynı sözleşmeyle `RESUMABLE` | `test_run_campaign_and_project_use_the_same_contract` |
| 10 | Yeni şema, tamper, bozuk JSON, eksik dosya | Sırasıyla `unsupported_schema`, `signature_invalid`, `checkpoint_unreadable`, `checkpoint_missing`; hiçbiri otomatik resume değil | `test_newer_schema_tamper_broken_json_and_missing_files_are_never_resumed` |
| 11 | Veri kökü dışındaki yol | `path_refused`; dosya oluşmaz | `test_a_path_outside_the_private_data_root_is_refused` |

İlk tam suite, `checkpoint.py` içindeki doğrudan `subprocess.run` çağrısını Windows gizli-pencere sözleşmesine aykırı buldu. Kök neden `engine/winproc.run` ile düzeltildi; aşağıdaki sonuçlar düzeltme sonrası odaklı, ilgili ve tam regresyon çalıştırmalarıdır.

### Gerçek test çıktıları

```text
python -m unittest tests.workflows.test_checkpoint tests.engine.test_windows_processes -v
Ran 22 tests in 8.686s
OK
ELAPSED_SECONDS=9.022
EXIT_CODE=0
```

```text
python -m unittest tests.workflows.test_checkpoint tests.workflows.test_project tests.workflows.test_project_recovery tests.workflows.test_campaign tests.interfaces.test_migrate tests.test_context -v
Ran 51 tests in 83.796s
OK
ELAPSED_SECONDS=84.467
EXIT_CODE=0
```

```text
python -m unittest discover -s tests -t .
Ran 458 tests in 657.929s
OK
ELAPSED_SECONDS=658.707
EXIT_CODE=0
```

Tam keşifte görülen `unittest: error: argument command: invalid choice: 'update'` satırı CLI argüman doğrulama testinin beklenen stderr çıktısıdır.

### Kabul kriterleri

- [x] 5/5 zorunlu durum doğru yönetildi; 11 testte ek atomiklik, sır, şema, yol ve tür senaryoları da geçti.
- [x] Atomik işlemde bozuk JSON okuması `0`; yarım/bozuk/tamper state `NEEDS_REVIEW` oldu.
- [x] Snapshot şema göçü geçti; v1→v2 bir kez yapıldı ve ikinci inceleme byte-stabil kaldı.
- [x] Sır/worker prompt dump sızıntısı `0`; yasak alan ve sır deseni yazımdan önce reddedildi.
- [x] Odaklı `22/22`, ilgili regresyon `51/51` ve tam regresyon `458/458` `OK`; doküman kapısı aşağıda `OK`; `docs/ARCHITECTURE.md` senkron.

### Kanıt artefaktları (SHA-256)

<!-- RES01_HASHES_START -->
- `src/respected_orchestrator/workflows/checkpoint.py` -> `1B3537644A3218AC7DD0AD094580B00FD9501E3352E1A2201E3BD2DDC28C1BB4`
- `tests/workflows/test_checkpoint.py` -> `6EA63522778243F4844585BD97810683184616A4DF25820690BA881CEF64527F`
- `docs/ARCHITECTURE.md` -> `AFBD3383B05D1F790C992B42B24C12EA1A0CE27EA12524DD7424867286ACC11E`
- `docs/ROADMAP.md` -> `9CCA33112BD48251AAFCC574F6B4D78D8BE6678D5E1D68BC9081DE058E08CB60`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `ACC7267E8F1C869C62C1EAEE73A03BE4BB946B8DC33115BB7D48CBD53B3F7C26`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` -> `A0FB7FC6B88A3A1D3491848C663D095DBC4E62375E2407FCA284FA1F101C4280`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` -> `5524C65C5A751FB6DF73CE09F70E0B15FDF1054EFC50DFA373268F70AED223FC`
- `docs/ilerleme/poc/res01_checkpoint_focused_after_fix.log` -> `FDFE02EBE9C5554524AD02DE608772BCF25100437B6BD608D60F79BF01EDED31`
- `docs/ilerleme/poc/res01_related_regression.log` -> `63B04555A96BC7513C0787C8DD9B61EC820F5EABDF6512954FB98471269B29C9`
- `docs/ilerleme/poc/res01_full_suite.log` -> `BA115B1DBBCEEF5E6B44F7B5C5C259B9CFB16B2CF93391F9D8C41F6A687789BD`
<!-- RES01_HASHES_END -->

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/ilerleme/poc/res01_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
`KANIT_LOG.md` kendi hash listesine dahil edilmez (kendine referans döngüsünü önlemek için).

### Kalan risk / shortcut

- Git olmayan kaynakta commit `None` olabilir; bu durumda içerik drifti HEAD ile algılanamaz. Gerçek resume için içerik/parmak izi denetimi RES-02'de eklenmelidir.
- Bu görev yalnızca veri modeli ve inceleme sözleşmesini kurar; süreç yeniden başlatma, kilit temizleme, bilinmeyen adım onayı ve çift ücretli çalıştırma koruması RES-02 kapsamındadır.
- v1 göçünde eski imzalı payload `.v1.bak` olarak saklanır; otomatik saklama/temizleme politikası yoktur. Yedek de aynı veri kökünde ve imzalıdır.

---

## RES-02 — Çökme sonrası kontrollü resume

- **Durum:** Tamamlandı (2026-11-02). Commit/push/branch/reset/clean yapılmadı; çalışma ağacı bilinçli olarak kirli bırakıldı.
- **Kapsam:** Proje checkpoint'inden kontrollü FSM resume; kaynak ve Git HEAD drift denetimi; ölü/canlı kilit ayrımı;
  imzalı apply işaretçisiyle çökme penceresini açıklama; terminal-only insan onayı; MCP/alt süreç self-approval reddi.
- **Çıktı / değişen dosyalar:**
  - `src/respected_orchestrator/workflows/project.py`: resume adım whitelist'i (`resume`, `campaign`, `apply`, `verify`,
    `review`, `complete`), onay kaydı ve kimlik bağlama, kaynak snapshot'ı, canlı/ölü kilit ayrımı, stale patch
    sınıflandırması, `auto_apply=false` sınırı ve idempotent çökme kurtarma.
  - `src/respected_orchestrator/workflows/checkpoint.py`: Windows gizli-pencere süreç çağrısı için eksik `subprocess`
    importu düzeltildi.
  - `src/respected_orchestrator/engine/runner.py`: imzalı `applied.json` içine kaynak parmak izi eklendi;
    `source_fingerprint()` Git ve düz dizin kaynaklarını fail-closed hesaplar.
  - `src/respected_orchestrator/__main__.py`: `project-approve ID` komutu.
  - `tests/workflows/test_project_resume.py`: 13 senaryo.
  - `docs/ARCHITECTURE.md`, `docs/COMMANDS.md`, `docs/USAGE.md`, `docs/ROADMAP.md`,
    `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`,
    `docs/ilerleme/respected_orchestrator_github_issues.csv`: RES-02 sözleşmesi ve durum senkronu.

### Resume güvenlik sözleşmesi

- Checkpoint yalnızca `resume`, `campaign`, `apply`, `verify`, `review`, `complete` adımlarından birini çalıştırır;
  bilinmeyen adım hiçbir worker/kampanya başlatmadan insan onayı ister.
- Kaynak içerik parmak izi, Git HEAD, ham checkpoint SHA-256'sı, checkpoint durumu, operation kimliği veya neden
  değişirse onay geçersizdir. Onay `data/projects/<project_id>/resume-approval.json` altında proje, operation,
  checkpoint SHA-256'sı, aggregate kaynak parmak izi, repo commit'i, onaylayan ve UTC zaman damgasına bağlanır.
- Onay yalnızca etkileşimli terminalden alınır. `RESPECTED_ORCH_CHILD=1` ve `RESPECTED_ORCH_DELEGATED=1` reddedilir.
  MCP araç listesinde onay aracı yoktur; onaysız `orchestrator_resume` fail-closed döner.
- Canlı kilit sahibi varken hiçbir süreç başlatılmaz. Yalnızca ölü PID veya bozuk kilit temizlenir.
- Aynı operation kimliği korunur; checkpoint atomik olarak tek kayıt üzerine yazılır. Başarılı kampanya sonucu,
  muhasebe ve timeout reviewer tamamlaması yeniden çalıştırıldığında worker/ücret çoğaltılmaz.
- `apply_task` sonrası imzalı `applied.json` yazılıp süreç öldüyse kaynak parmak izi bu marker ile açıklanıyorsa apply
  tekrar edilmez. Dış kaynak değişikliği veya çakışan eski patch onaylansa bile zorlanmaz; `stale patch` ile bloke olur.
- Resume onayı `auto_apply=false` aşamasının apply yetkisini genişletmez; apply sayısı `0` kalır.

### Senaryo matrisi

| # | Senaryo | Beklenen | Test |
|---|---|---|---|
| 1 | Kampanya oluşturulmadan önce kill/restart | Tek operation, tek kampanya, tek apply, `complete` | `test_kill_before_campaign_resumes_once_and_keeps_one_operation_id` |
| 2 | Kampanya sonucu yazıldıktan, muhasebeden önce kill | `apply` sınırından devam; kampanya yeniden çalışmaz | `test_kill_after_campaign_result_before_accounting_does_not_rerun_the_campaign` |
| 3 | Muhasebe sonrası, apply öncesi kill | Tek ücret, tek apply, tek checkpoint | `test_kill_after_accounting_reuses_the_charge_and_applies_once` |
| 4 | Apply sonrası, proje durumu yazılmadan kill | İmzalı marker apply'ı açıklar; ikinci apply yok | `test_kill_after_apply_is_explained_by_the_signed_marker_without_reapplying` |
| 5 | Verify sonrası kill | `verify` yeniden çalışır; final review bir kez | `test_kill_after_verify_restarts_at_verify_then_completes_review` |
| 6 | Kaynak değişikliği + eski patch | Onay ister; onaydan sonra da stale patch reddedilir | `test_an_old_patch_needs_approval_and_is_still_refused_as_stale` |
| 7 | Reviewer timeout tamamlaması | Aynı lane veri kökünde bir worker çalışır, ikinci deneme tamamlanır | `test_reviewer_completion_retries_the_same_lane_and_runs_the_worker_once` |
| 8 | Kaynak içerik drifti | Onay ister; onaylı yeni kaynakta tamamlanır | `test_source_drift_needs_approval_and_then_runs_on_the_new_source` |
| 9 | Git HEAD drifti | Onay HEAD'e bağlanır; onaylı akış tamamlanır | `test_repo_head_drift_needs_approval_and_the_approval_is_bound_to_it` |
| 10 | Bilinmeyen checkpoint adımı | Hiçbir süreç başlamaz; onay dosyası yok | `test_unknown_checkpoint_action_needs_approval_and_launches_nothing` |
| 11 | Ölü ve canlı kilit | Ölü kilit temizlenir; canlı kilit spawn `0` ile reddedilir | `test_resume_clears_only_a_dead_lock_and_refuses_a_live_one` |
| 12 | `auto_apply=false` + resume onayı | Apply `0`; proje `blocked` kalır | `test_auto_apply_false_stays_blocked_even_after_resume_approval` |
| 13 | Alt süreç/MCP onayı | İki ortam değişkeni reddedilir; MCP onay aracı yok, resume onaysız reddedilir | `test_approval_is_not_available_to_children_or_mcp` |

### Gerçek test çıktıları

```text
python -m unittest tests.workflows.test_project_resume -v
Ran 13 tests in 55.571s
OK
EXIT_CODE=0
```

```text
python -m unittest tests.workflows.test_project tests.workflows.test_project_recovery tests.workflows.test_project_adversarial tests.workflows.test_checkpoint tests.engine.test_windows_processes tests.workflows.test_project_resume -v
Ran 68 tests in 168.749s
OK
EXIT_CODE=0
```

```text
python -m unittest tests.interfaces.test_mcp_server tests.workflows.test_reviewer_reliability tests.engine.test_review_apply_invariants tests.engine.test_runner -v
Ran 82 tests in 173.844s
OK
EXIT_CODE=0
```

```text
python -m unittest discover -s tests -t .
Ran 471 tests in 717.965s
OK
FULL_SUITE_EXIT=0 ELAPSED_SECONDS=718.922
```

PowerShell `2>&1 | Tee-Object` sarmalayıcısındaki `NativeCommandError` satırları test sürecinin beklenen uyarı
akışıdır; gerçek sonuç `Ran ...`, `OK` ve exit `0` satırlarıdır. Tam suite'teki `unittest: error: no command` ve
`invalid choice: 'update'` satırları CLI negatif doğrulama testlerinin beklenen stderr çıktısıdır.

### Kabul kriterleri

- [x] 5/5 kill/restart noktası doğru sınırdan kurtarıldı; her birinde tek operation ve tek kampanya korundu.
- [x] Onay olmadan apply `0`; `auto_apply=false` onay sonrasında da apply `0`.
- [x] Aynı operation için çift ücret `0` (simülasyonda); ücret yalnızca imzalı aşama üzerinden bir kez sayıldı.
- [x] Timeout çocuk süreç kalıntısı `0`; `test_timeout_kills_worker_descendants` ve süreç ağacı testleri geçti.
- [x] Eski/çakışan patch zorla apply edilmedi; kaynak dosyası değişmeden `stale patch` ile bloke kaldı.
- [x] Canlı kilit reddedildi ve spawn `0`; ölü/bozuk kilit temizlendi.
- [x] Alt süreç ve MCP onayı reddedildi; onay dosyası oluşmadı.
- [x] Odaklı regresyon `68/68`, ilgili regresyon `82/82`, tam regresyon `471/471` `OK`; doküman kapısı aşağıda `OK`;
  `docs/ARCHITECTURE.md` senkron.

### Kanıt artefaktları (SHA-256)

<!-- RES02_HASHES_START -->
- `src/respected_orchestrator/workflows/project.py` -> `51F9C6D69A799980E91BCE0D7A5518ADE403FACF056723FF51ACA4656DE97674`
- `src/respected_orchestrator/workflows/checkpoint.py` -> `39D620BEC0A53DD21D06A3A739B3DFE80158FBEC4646C147D23DA13BCC5CFB6D`
- `src/respected_orchestrator/engine/runner.py` -> `DDAD4BD86E8995C3ADA15CBAE5F1C5A6AA0B99E9746F226C64EEE40BCD69FD9C`
- `src/respected_orchestrator/__main__.py` -> `ECB053CC6DE239E78E7EBB5C4B7F91150A164FA85F6D92A6AE69F7CFC4FFF64B`
- `tests/workflows/test_project_resume.py` -> `115BEA9EA2E997F81563379F11708C76ADA21C7230614BA4608C18520948FACC`
- `docs/ARCHITECTURE.md` -> `A5C2BDC0C3E95AD99B0E7A3E5C184ACF61496BE875D259B21C0F2771D9475AAC`
- `docs/COMMANDS.md` -> `BF268283D1A04708C9D0DBC68CF606DE4C39E5107863C9C208BEE8C1382CEDC9`
- `docs/USAGE.md` -> `CD64C185E19B79D44399A3871C43F763C700538F9456187C5923EE07D924BCD1`
- `docs/ROADMAP.md` -> `3B4ABD47D8E961EF081B1CF06380CDA64146A992D3CD820BDA3211D460D7F33C`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `2F73C6E8F473D9C0C7475B9CA86C7B0BF5AB37AB3C19C79C614CB9FB77F9B01D`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` -> `A11BEE480874BB24709759D2641EED8A14A8DE65EAD0F3336947B5C2F0FCBF83`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` -> `E3B924B021AE47E9948C3B3BA06A42675570A2B22CE10EC5CC47C6A042637EC4`
- `docs/ilerleme/poc/res02_invariants.log` -> `A042271F883C4E7CC69BCB00C6C164CDA0C376EA94491FB38AA240794940CE47`
- `docs/ilerleme/poc/res02_focused.log` -> `7835A6B358E8ED9A2F02DAC45FEB05579A676D1FE0D1747CA232D315EE20B727`
- `docs/ilerleme/poc/res02_related.log` -> `F7CDE08DD75D9FBB99AE9B35FAB0CDBC37777F1900CB4270C293684AE080A831`
- `docs/ilerleme/poc/res02_full_suite.log` -> `F3CFD9362DB317C9864531D81CE431919CA5361F0C6986D372F0B2E887F4A866`
<!-- RES02_HASHES_END -->

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/ilerleme/poc/res02_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında
tutulur. `KANIT_LOG.md` kendi hash listesine dahil edilmez (kendine referans döngüsünü önlemek için).

### Kalan risk / shortcut

- Onay kimliği OS kullanıcısı ve TTY sınırına dayanır; ayrı bir kriptografik insan kimliği modeli yoktur. Bu, alt
  süreç/MCP self-approval'i engeller ancak aynı kullanıcının terminalinde çalışan kötü amaçlı bir süreci ayırt etmez.
- Kaynak parmak izi tüm düz dosyaları okur; çok büyük veya sürekli değişen kaynaklarda resume değerlendirmesi daha
  yavaş olabilir. Okunamayan veya bağlantılı içerik sessizce atlanmaz, resume fail-closed olur.
- Gerçek makine kapanması simülasyonla değil süreç kesme noktalarıyla test edildi; OS düzeyinde güç kaybı ve dosya
  sistemi dayanıklılığı bu görevin kapsamı dışındadır.

---

## RES-03 — Brain ile isteğe bağlı karar hafızası sözleşmesi

- Durum: Tamamlandı.
- Kapsam: Üretim kodu değiştirilmedi. Mevcut Brain sözleşmesi, bağlantısız motor davranışı ve grant sınırları kanıt
  testleriyle güçlendirildi; `docs/ARCHITECTURE.md` §7, yol haritası ve issue durumu senkronlandı.
- Çıktı / değişen dosyalar: `tests/workflows/test_project_resume.py`,
  `tests/interfaces/test_memory_integration.py`, `tests/interfaces/test_installation.py`, `docs/ARCHITECTURE.md`,
  `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`,
  `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/ilerleme/respected_orchestrator_github_issues.csv`.
- Doğrulama komutu:

```text
python -m unittest tests.interfaces.test_memory tests.interfaces.test_memory_integration tests.interfaces.test_installation tests.interfaces.test_mcp_server tests.workflows.test_project_resume -v
python -m unittest tests.packaging.test_frozen_security -v
python -m unittest discover -s tests -t .
python -m unittest tests.docs.test_decision_records -v
```

### Senaryo sonuçları

| Senaryo | Beklenen | Kanıt |
|---|---|---|
| Bağlantısız resume: campaign sınırı | Brain `run` çağrısı `0`; resume bir kez | `test_kill_before_campaign_resumes_once_and_keeps_one_operation_id` |
| Bağlantısız resume: apply sınırı | Brain `run` çağrısı `0`; apply bir kez | `test_kill_after_accounting_reuses_the_charge_and_applies_once` |
| Bağlantısız resume: verify sınırı | Brain `run` çağrısı `0`; verify/review bir kez | `test_kill_after_verify_restarts_at_verify_then_completes_review` |
| Opt-out | Brain `run` çağrısı `0`; `memory` alanı yok | `test_enabling_memory_is_a_permission_not_a_default` |
| Write izni yok | Not yazımı `0`; Brain alt süreci yok | `test_write_needs_its_own_permission_and_never_leaks_the_token` |
| Prompt injection | Enjeksiyon yalnızca güvenilmeyen `text` bloğunda; uyarı önce; token sızmaz | `test_prompt_injection_notes_stay_in_the_untrusted_data_block` |

Grant matrisi 5/5:

| Durum | Sonuç |
|---|---|
| Brain yok | `NOT_INSTALLED`; ayar dosyası oluşmaz |
| Read grant | Bağlı/read-only; write izni kapalı |
| Write grant | Bağlı/yazılabilir; tek `memory.write` notu gönderilir |
| Revoke/disconnect | Grant iptal edilir; token ve bağlantı temizlenir |
| Denied/geçersiz grant | Mevcut ayarlar byte düzeyinde korunur; token yazılmaz |

### Gerçek test çıktıları

```text
python -m unittest tests.interfaces.test_memory tests.interfaces.test_memory_integration tests.interfaces.test_installation tests.interfaces.test_mcp_server tests.workflows.test_project_resume -v
Ran 59 tests in 83.606s
OK
FOCUSED_EXIT=0
```

```text
python -m unittest tests.packaging.test_frozen_security -v
Ran 3 tests in 39.013s
OK
PACKAGING_EXIT=0
```

```text
python -m unittest discover -s tests -t .
Ran 475 tests in 722.421s
OK
FULL_EXIT=0
```

PowerShell `NativeCommandError` ve suite içindeki beklenen CLI negatif stderr satırları sarmalayıcı gürültüsüdür;
gerçek sonuç `Ran`, `OK` ve exit `0` satırlarıdır.

### Kabul kriterleri

- [x] Bağlantısız 3/3 resume: campaign, apply ve verify sınırlarında Brain çağrısı `0`; her senaryo bir kez tamamlandı.
- [x] Opt-out akışında Brain çağrısı `0`; görev açık izin vermeden hafıza okunmadı.
- [x] Write izni yokken not yazımı `0`; Brain alt süreci başlatılmadı ve yan dosya oluşmadı.
- [x] 5/5 grant durumu doğrulandı; denied/geçersiz grant mevcut ayarları ve token durumunu değiştirmedi.
- [x] Odaklı regresyon `59/59`, paket güvenliği `3/3`, tam regresyon `475/475` `OK`; doküman kapısı aşağıda `OK`;
  üretim kodu değişmediği için `docs/ARCHITECTURE.md` mevcut sözleşmeyle senkron.
- [x] Operasyonel checkpoint ve handoff yerel kaldı; Brain kod importu eklenmedi (ADR-006) ve bağlantısız motor aynı
  işlevi gördü.

### Kanıt artefaktları (SHA-256)

<!-- RES03_HASHES_START -->
- `tests/workflows/test_project_resume.py` -> `2F8887923B5A58201712A99B69688F4E13080F8EDC8E38606D9C192E2AE0DCC3`
- `tests/interfaces/test_memory_integration.py` -> `11A3811127743EE4B0546ECB9D9C9751758065F190BC08FE9E78A13C6DC08824`
- `tests/interfaces/test_installation.py` -> `20EC6A139DB8FC212027A2699AF7859BC2FB33641400F1973AFDBD1EC3F8CBFC`
- `docs/ARCHITECTURE.md` -> `52C46D120CF6829F4EF6CFE1DEC0425DD8E67B43BD8C994C57D491A14F594DA5`
- `docs/ROADMAP.md` -> `169C206970367B500AF7D9B09120AB3D7A7491543CA14E8AD7986D424654AE0A`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `8464DD79EDB14374161865BAF8393D8984C504C5B8FD602A391890F05D37ED6D`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` -> `3C03F7711B654FF4FA8E3FAD48043B05100149A84F5A655DCEF4CF4CF3218AC8`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` -> `8DDE0C663DC5E03965F365A7E27BD1AADA0295DA734CA7CB508A406A1EA7DFD2`
- `docs/ilerleme/poc/res03_focused.log` -> `EDBFCA902AFEEBF47E558EC597311293EF7375A9EBE44F679704014F7D1DCBFD`
- `docs/ilerleme/poc/res03_packaging.log` -> `612F405ED5229D45EC3015F6A8020A53A503E45D4D3EF4B577EF48ADA6CCFBEE`
- `docs/ilerleme/poc/res03_full_suite.log` -> `18D3800BB82200BDE9D60E5BBD51F2B0F29726ADFA328F2ED99C42A40797DD10`
<!-- RES03_HASHES_END -->

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/ilerleme/poc/res03_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında
tutulur. `KANIT_LOG.md` kendi hash listesine dahil edilmez (kendine referans döngüsünü önlemek için).

### Kalan risk / shortcut

- Bu görevdeki Brain yokluk ve grant senaryoları sahte RPP alt süreci ve izole `winproc` mock'u kullanır; canlı Brain
  kurulumuyla uçtan uca kurulum testi bu odaklı paketin parçası değildir.
- Prompt-injection notu güvenilmeyen veri bloğunda ve açık uyarıdan sonra tutulur; ancak içerik çalışan modele
  görünür. Modelin talimatı yok sayacağı kriptografik olarak garanti edilmez.
- Disconnect, Brain erişilemezken yerel token/grant temizliğini yapar; uzak tarafta iptal edilemeyen grant için
  operatörün Brain tarafındaki durumu ayrıca denetlemesi gerekebilir.

---

## ADP-01 — OpenCode CLI çalışanı ve MCP kayıt desteği

- Durum: Tamamlandı.
- Kapsam: Gerçek OpenCode CLI (`opencode v2.2.3`) ile read, write, invalid model, timeout, acceptance failure ve eksik
  kimlik senaryoları; güvenli final JSON ayrıştırması; OpenCode MCP kaydı, kurulum/geri alma ve secret scan. Model:
  `amd/DeepSeek-V4.1-Flash`. Üretimde eski Codex davranışı korunur; OpenCode ayrı bir uyarlayıcıdır.
- Çıktı / değişen dosyalar: `src/respected_orchestrator/engine/opencode_acp.py`,
  `src/respected_orchestrator/engine/opencode_auth.py`, `src/respected_orchestrator/engine/runner.py`,
  `src/respected_orchestrator/interfaces/integrations.py`, `tests/engine/test_opencode_acp.py`,
  `tests/engine/test_opencode_auth.py`, `docs/ARCHITECTURE.md`, `docs/COMMANDS.md`, `docs/USAGE.md`,
  `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`,
  `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`, `docs/ilerleme/poc/adp01_*`.
- Doğrulama komutu:

```text
$env:PYTHONPATH='src'
py -m unittest tests.engine.test_opencode_acp tests.engine.test_runner tests.engine.test_opencode_auth
$env:RESPECTED_OPENCODE_NETWORK='allow'
py docs/ilerleme/poc/adp01_real_e2e.py
py -m unittest discover -s tests -t .
py packaging/build_dist.py
py -m unittest tests.packaging.test_frozen_build tests.packaging.test_frozen_security
```

### ACP ve final JSON kararı

- OpenCode çalışanı sahte bir CLI yerine gerçek `opencode acp` stdio oturumu kullanır. ACP yanıtlarındaki oturum
  kimliği, model seçimi ve dönüş sınırı izlenir; süreç sağlıklı kapanmadan başarı kabul edilmez.
- Final mesaj ayrıştırması fail-closed'dır ve Codex'in `runner.py._final_json` sözleşmesiyle hizalanır. Kabul edilen
  biçimler: çıplak JSON nesnesi; fence dışında yalnızca açıklama metni bulunan **tek** bir ```json/``` bloğu.
  Fence dışındaki serbest metinden JSON çıkarılmaz. Çoklu ya da yarım fence, bozuk JSON, JSON dizisi ve geçersiz
  `status` reddedilir. Bu, OpenCode'un Markdown fence içinde döndürdüğü gerçek yazma yanıtının yanlış
  `WORKER_FAILED` sayılmasını düzeltir; başarısız çıktı hâlâ başarı sayılmaz.
- Sahte sunucu testleri tek fenced JSON'un (`json` etiketli ve etiketsiz) kabul edildiğini; çoklu fence, prose içinde
  çıplak JSON, bozuk JSON, JSON dizisi, yarım fence ve geçersiz status'un `failed` kaldığını doğrular
  (`tests/engine/test_opencode_acp.py`).

### Çalışan izolasyonu ve kimlik

- OpenCode alt süreci proje yapılandırmasını okumaz: `OPENCODE_DISABLE_PROJECT_CONFIG=1`.
- İzole HOME: `APPDATA` ve `LOCALAPPDATA` görev scratch köküne yönlendirilir; kişinin gerçek OpenCode yapılandırması
  ve proje `opencode.json` dosyası çalışana görünmez.
- Credential bridge: ana kullanıcı deposundaki kimlik `opencode auth export --standalone` ile alınır, yalnızca
  çalışanın izole HOME'una `opencode auth import --standalone` ile aktarılır. Sır görev metnine, loga, kanıta ve
  `memory-context.json` içine yazılmaz; secret scan `passed` döndü.
- Ağ erişimi varsayılan kapalıdır; yalnızca açık opt-in `RESPECTED_OPENCODE_NETWORK=allow` ile açılır. E2E bu
  bayrakla çalıştırıldı.

### MCP kaydı

- `opencode` istemcisi `interfaces/integrations.py` içinde desteklenir. Girdi
  `~/.config/opencode/opencode.json` altındaki `mcp.servers` haritasına `{"type": "local", "command": [...]}`
  biçiminde yazılır; diğer sunucular ve kullanıcı ayarları korunur.
- E2E'de geçici bir HOME üzerinde kurulum yapıldı: yabancı `probe` sunucusu ve yabancı ayarlar korundu,
  `respected-orchestrator` girdisi eklendi. Geri alma sonrası dosya byte düzeyinde eski hâline döndü
  (`rollback_bytes_restored=true`, `real_user_config_unchanged=true`).

### E2E sonuçları

| Senaryo | Beklenen | Gerçek |
|---|---|---|
| read | `completed` | `completed` (yaklaşık 12,7 sn) |
| write | `completed`; `owned.txt` tam `changed\n` | `completed`; dosya `changed\n`, apply `applied` |
| invalid_model | `failed` | `failed` |
| timeout | `timed_out` | `timed_out` |
| acceptance_failure | `failed` | `failed` |
| auth_missing | `failed` | `failed` |
| MCP setup/rollback | yabancılar korunur; byte düzeyinde geri dönüş | geçti |
| Secret scan | sır yok | geçti |

Timeout bütçesi: ilk 20 sn'lik bütçe model erken yanıt verdiği için `completed` döndü; sahte başarı sayılmadı.
3/5/8 sn denemelerinin üçü de `timed_out` verdi ve `AUTH_REQUIRED` görülmedi. Bu nedenle harness bütçesi 8 sn'ye
çekildi; kimlik köprüsü tamamlanıyor fakat model yanıtından önce kesiliyor. Ayrıntı:
`docs/ilerleme/poc/adp01_timeout_decision.md`. ACP kimlik köprüsünde değişiklik gerekmedi.

### Test sonuçları

- Odaklı: `Ran 63 tests ... OK` (`docs/ilerleme/poc/adp01_fenced_focused.log`).
- Tam regresyon: `Ran 500 tests ... OK` (`docs/ilerleme/poc/adp01_full_suite.log`).
- Paketleme: `py packaging/build_dist.py` başarılı; `Ran 7 tests ... OK`
  (`docs/ilerleme/poc/adp01_packaging.log`).
- Ortam: `opencode v2.2.3`, model `amd/DeepSeek-V4.1-Flash`, Windows.

### Kanıt artefaktları (SHA-256)

<!-- ADP01_HASHES_START -->
- `src/respected_orchestrator/engine/opencode_acp.py` -> `8FA34A34F19D2FB0B1A6E9D90D2156A4E574ED68BFCFA2AF2F35C581E6167A00`
- `src/respected_orchestrator/engine/opencode_auth.py` -> `7DB2AE187168363A853C9E52B70D95A07B612D21C16268C8269ED6DD5FA0E9B9`
- `src/respected_orchestrator/engine/runner.py` -> `EA5768223B5C5FE3DF4F7951559C993D5098661FE7E352DAA716F73B80E2E37A`
- `tests/engine/test_opencode_acp.py` -> `ED1D72BB2EE8A78752C2E268D3C68FEF028CB9684AAD1F509369C569D471CBFA`
- `docs/ilerleme/poc/adp01_fenced_focused.log` -> `0A97D79ADD31E81CD6EFF260A8B83D0304A2F671D19B508FE988449E6FD1F94D`
- `docs/ilerleme/poc/adp01_full_suite.log` -> `743BA7A567C07375C9C82773F3165592E9F14436CA2D35F8B8CB087F72496079`
- `docs/ilerleme/poc/adp01_packaging.log` -> `CCEC94CE25F5C63E1EAF9ED326B25D0B2C6BC2184CF71C5DB610D4D69B21E335`
- `docs/ilerleme/poc/adp01_timeout_decision.md` -> `14F27087CE7DD71255F9AF85599B4FDD419D0B27314FE6EBCD71D444870D5A80`
- `docs/ilerleme/poc/adp01_real_e2e.py` -> `44BEBE12C1198D12F5748447FEA14E9E53A1C2B2DA0B424990CC3ADFE926E49A`
- `docs/ilerleme/poc/adp01_real_e2e_run.log` -> `77D4173588309AA9D109B7AA314FFE0166DA68D9A70666ADD56B5046C187A7BD`
- `docs/ilerleme/poc/adp01_real_read.log` -> `3CFDCE5ED41D238991410F8DC81A1CBF69666C7BDDA0A19F21B175335F7CA113`
- `docs/ilerleme/poc/adp01_real_write.log` -> `3A1A389847B01800A76795928137E418AB3DED8894BBE4D1F9E301B8482C2367`
- `docs/ilerleme/poc/adp01_real_invalid_model.log` -> `553F314EBC8A9811717229C02C7911D01676851602A9E8009278422575EF72D0`
- `docs/ilerleme/poc/adp01_real_timeout.log` -> `001E610C3A2C1C7A4E618DDFD800E6A52FC379104E3B7BE6A2DEC7B92394F267`
- `docs/ilerleme/poc/adp01_real_acceptance_failure.log` -> `16C6526483DD1CE13F63604B8C43A7FE47D82B1535247BEB872581A1CA601A2D`
- `docs/ilerleme/poc/adp01_real_auth_missing.log` -> `86909347E3A2BC5D76EC802A1D663E2593C613CCE504CA727AFEC8109879D548`
- `docs/ilerleme/poc/adp01_real_mcp.log` -> `C4311EA426FE6C7487340B7011C7D2EAA796D4F0A8D656211877A756DF8BF76E`
- `docs/ilerleme/poc/adp01_real_summary.log` -> `0CF25F7A8B4EFCE77C3AFA246E42EC2D203F4237C24A888A750D3E56504B0483`
- `docs/ARCHITECTURE.md` -> `7DB03E98CD9BBF9118F9D1AF27B4A760E72B0CE0B722FCCBCF7BC5F9E1DE2588`
- `docs/COMMANDS.md` -> `F0A68CCE1B931346A11A9FEB79F16D842AD8777ED2983CD1417C96C63A910E09`
- `docs/USAGE.md` -> `FCDEC94499F78230E305C0FBE75B21BEB246047FBD5FA91698FFDB05963B873D`
- `docs/ROADMAP.md` -> `4773B6AC7349AA203B8676BEB7C0842C87C104472468505242B1D4EC8833A94E`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `30254E4A54BD5A3DF9C5C1AD7A80B208CC3B2F04599199819C01CCC95DB3894D`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` -> `37A05BB2235C96B8D64D1E2CC329B6B209DEE64B388B6DFE3D5853E8DF3B98A3`
<!-- ADP01_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

### Kalan risk / shortcut

- E2E geçici HOME ve geçici proje kullanır; kişinin gerçek OpenCode oturumunda farklı sağlayıcı/oturum durumu
  görülebilir.
- OpenCode ağ erişimi opt-in olsa da model yanıtı dış servise gider; görev metni ve dosya içeriği sağlayıcıya
  görünür. Dışa çıkacak veriyi operatör seçer.
- Fenced JSON sözleşmesi yalnızca son ajan mesajını doğrular; modelin görevi gerçekten doğru yaptığı ayrıca kabul
  komutları, patch ve insan onayıyla sınanır.
- Timeout bütçesi 8 sn E2E harness'ına özgüdür; üretim varsayılan görev süreleri değişmez.

---

## ADP-02 — API anahtarı, ağ ve sağlayıcı tehdit modeli

- Durum: Tamamlandı.
- Kapsam: Canlı sağlayıcı adaptöründen (ADP-03) önce anahtar saklama, ağ opt-in'i, kod kapısı, egress/redirect/proxy
  allowlist'i, 401/429/5xx sessiz fallback yasağı, sır maskeleme ve kalıcılık sınırlarının ADR ile karara
  bağlanması. Bu görev canlı API çağrısı yapmaz; yalnızca fail-closed politika kapısını ve test planını sabitler.
- Çıktı / değişen dosyalar: `src/respected_orchestrator/engine/provider_policy.py`,
  `tests/engine/test_provider_policy.py`, `docs/adr/ADR-007-provider-key-network-threat-model.md`,
  `docs/ARCHITECTURE.md`, `docs/ROADMAP_EXECUTION_PLAN.md`,
  `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/ilerleme/respected_orchestrator_github_issues.csv`, `docs/ilerleme/poc/adp02_*`.
- Doğrulama komutu:

```text
$env:PYTHONPATH='src'
py -m unittest tests.engine.test_provider_policy tests.docs.test_decision_records
py -m unittest discover -s tests -t .
py packaging/build_dist.py
py -m unittest tests.packaging.test_frozen_build tests.packaging.test_frozen_security
```

### Karar (ADR-007)

- **Anahtar deposu:** Anahtar ayar JSON'una, loga veya kanıta yazılmaz. Windows'ta kullanıcıya özel DPAPI kasasından
  yalnızca istek anında okunur; süreç ortamına kalıcı konmaz. Kasa yoksa adaptör çalışmaz, düz metin fallback yoktur.
- **Opt-in ve kod kapısı:** Ağ varsayılan kapalıdır. Canlı sağlayıcı yolu ancak
  `RESPECTED_PROVIDER_NETWORK=allow` ve `RESPECTED_PROVIDER_CODE_GATE=1` birlikte verildiğinde açılır;
  `require_access` soket açmadan `ProviderDenied` fırlatır.
- **Egress:** Yalnızca `https`, URL'de kimlik bilgisi olmayan ve açık allowlist'teki tam alan adı kabul edilir.
  Her redirect hedefi aynı kapıdan yeniden geçer; proxy host'u da allowlist'te olmak zorundadır.
- **Hata sınıfları:** 401, 429 ve 5xx ayrı sınıflandırılır; hiçbiri başka sağlayıcıya sessiz fallback yapmaz.
  Kullanıcı açıkça seçmedikçe model değişmez.
- **Sızıntı ve kalıcılık:** Anahtar değeri log, kanıt, `settings.json`, `result.json` ve hata metninde
  `***set***` olarak maskelenir. İstek/yanıt gövdeleri varsayılan olarak saklanmaz; yalnızca kullanım sayıları ve
  durum sınıfı tutulur.

### Test senaryoları (6/6)

| Senaryo | Beklenen | Sonuç |
|---|---|---|
| Opt-in kapalı | Soket öncesi `ProviderDenied`; ağ çağrısı 0 | geçti |
| Kod kapısı kapalı | Canlı sağlayıcı reddedilir | geçti |
| Yasak alan adı | Allowlist dışı host reddedilir | geçti |
| HTTP redirect | Hedef yeniden doğrulanır; yabancı host reddedilir | geçti |
| Proxy / URL'de kimlik | `http` ve `user:pass@host` reddedilir | geçti |
| Log/kanıt sızıntısı | Anahtar `***set***` ile maskelenir | geçti |

### Test sonuçları

- Odaklı: `Ran 7 tests ... OK` (`docs/ilerleme/poc/adp02_focused.log`; politika 6/6 + ADR kapısı).
- Tam regresyon: `Ran 506 tests ... OK` (`docs/ilerleme/poc/adp02_full_suite.log`).
- Paketleme: `py packaging/build_dist.py` başarılı; `Ran 7 tests ... OK`
  (`docs/ilerleme/poc/adp02_packaging.log`).
- Canlı sağlayıcı çağrısı bu görevde yapılmadı; ADP-03 adaptörü `require_access` çağırmadan istek başlatamaz.

### Kanıt artefaktları (SHA-256)

<!-- ADP02_HASHES_START -->
- `src/respected_orchestrator/engine/provider_policy.py` -> `A4904EA9FED3B59ED61E6A1F453ECD32C1894ED210E7495E3EB2F8406EE5D3CE`
- `tests/engine/test_provider_policy.py` -> `77CB4CA5BE5ACF916C647F5A05C23A257C61144AFE9518846932E68FD4E3F920`
- `docs/adr/ADR-007-provider-key-network-threat-model.md` -> `41735F348DA4F25089F0524A9A6946CA9453D83179297B483A37D9964D2F724C`
- `docs/ARCHITECTURE.md` -> `532B8AADE7B2CCE28F197AB59B0487348CA9E11EB27AF1C5579F625C4B6A5036`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `EE222E81701B220777817B178F782CA39BA3E3BCB015ECE1C92B2EA1D39C721B`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` -> `F6DD4CCCE3BFDC2D0B0FF1BD3BB50CCC04C1B1A8723A9B89F1A9E91F6162F8BF`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` -> `DDA55676F010B4A4B8BCA9C7C52B9A4F9C6EB1A50B88711F6791D23A388F04EB`
- `docs/ilerleme/poc/doc01_check.py` -> `9D765DB66BA2C49D9157FEEDF81C364D79B3B3D67957E4A5C0F2E6C998EEDC9F`
- `docs/ilerleme/poc/adp02_focused.log` -> `252A7CCE280B94CE4C8CF9C7E3CA7C4C6EF16FEA271D5CEBDF1368D8A5F48A8B`
- `docs/ilerleme/poc/adp02_full_suite.log` -> `BEE08E716D408688F91A4FA52241657E5A7197377DBAB52F36909FEFDD6FA079`
- `docs/ilerleme/poc/adp02_packaging.log` -> `71256C6B5EB217111E373BECEE08A800C04462B56F1ACAD0ABE4800E802DB423`
<!-- ADP02_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

### Kalan risk / shortcut

- ADP-02 kararı uygulama değil sözleşmedir; canlı adaptör, DPAPI kasası ve gerçek 401/429/5xx davranışı ADP-03'te
  test edilecektir.
- Allowlist tam alan adı eşleşmesidir; alt alan adı veya joker desteği bilinçli olarak yoktur.
- Sağlayıcıya giden görev metni ve dosya içeriği sağlayıcı tarafından görülür; opt-in bunu kabul etmek demektir.
- `docs/ilerleme/poc/doc01_check.py` ADR erişim tarihini artık herhangi bir ISO tarihi olarak doğrular; araştırma
  kaynak tablosunun ortak erişim tarihi (`2026-10-30`) değişmedi.

---

## COST-02 — Sürüm kontrollü fiyat kataloğu ve belirsizlik sözleşmesi

- Durum: Tamamlandı.
- Kapsam: Model fiyatını sürüm ve zaman damgasına bağlı, deterministik ve belirsizliği açıkça gösteren bir katalog
  sözleşmesi. Canlı fiyat çağrısı zorunlu değildir; hiçbir eksik veri sıfır maliyet sayılmaz.
- Çıktı / değişen dosyalar: `src/respected_orchestrator/engine/pricing.py`, `tests/engine/test_pricing.py`,
  `docs/ARCHITECTURE.md`, `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/ilerleme/respected_orchestrator_github_issues.csv`, `docs/ilerleme/poc/cost02_*`.
- Doğrulama komutu:

```text
$env:PYTHONPATH='src'
py -m unittest tests.engine.test_pricing
py -m unittest discover -s tests -t .
py packaging/build_dist.py
py -m unittest tests.packaging.test_frozen_build tests.packaging.test_frozen_security
```

### Sözleşme

- `pricing.quote(catalog, model, input_tokens, output_tokens, at=...)` yalnızca `effective_from` değeri `at`'dan
  büyük olmayan en yeni katalog girdisini seçer. Aynı girdi her zaman aynı sonucu verir.
- Her rakamsal teklif `at`, `model_version`, `effective_from`, `currency` ve `unit` taşır; liste fiyatı olduğu için
  `estimate_only=true`. `observed_tokens` verilirse `confidence=observed`, verilmezse `estimated` olur.
- Model katalogda yoksa, kullanım eksik/negatifse veya sağlayıcı erişilemezse `amount=None`, `status=unknown` ve
  gerekçe (`model_unknown`, `usage_unknown`, `provider_unavailable`, `not_yet_effective`) döner. `display()` bunu
  `"unknown"` olarak gösterir; sıfır gösterilmez.
- Gizli API anahtarı bu modüle girmez; fiyat kataloğu anahtar veya sağlayıcı durumu saklamaz.

### Test senaryoları (5/5)

| Senaryo | Beklenen | Sonuç |
|---|---|---|
| Model unknown | `unknown`, tutar `None`, gösterim `"unknown"` | geçti |
| Fiyat değişti | Zaman damgasına göre `v1`/`v2` ve farklı tutar | geçti |
| Input/output ayrı | Girdi ve çıktı ayrı birim fiyatla toplanır (`9.0 USD`) | geçti |
| Eksik kullanım | `usage_unknown`, tutar `None` | geçti |
| Sağlayıcı downtime | `provider_unavailable`, sessiz fallback yok | geçti |

### Test sonuçları

- Odaklı: `Ran 6 tests ... OK` (`docs/ilerleme/poc/cost02_focused.log`).
- Tam regresyon: `Ran 512 tests ... OK` (`docs/ilerleme/poc/cost02_full_suite.log`).
- Paketleme: `py packaging/build_dist.py` başarılı; `Ran 7 tests ... OK`
  (`docs/ilerleme/poc/cost02_packaging.log`).

### Kanıt artefaktları (SHA-256)

<!-- COST02_HASHES_START -->
- `src/respected_orchestrator/engine/pricing.py` -> `E552300D521F83DEEDCAEE68BD7FDEED61BCB4BFF9D9EE444E91D2C2177ACF42`
- `tests/engine/test_pricing.py` -> `E44B09E8F87DCDAA269F310B9CBAFE3C8B76B1EB410F28B7E28774E53CB3788F`
- `docs/ARCHITECTURE.md` -> `92F69502A605B6FAD58C6314EEB05143496472D1E8CF4E19E5FA3CF57C63DA2C`
- `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md` -> `27DFB4494D43BD0A11CC6F22BD456DECF6908D8E2D47A5E42085E58F41BF9CD8`
- `docs/ilerleme/respected_orchestrator_github_issues.csv` -> `6F30FEB0E563C9E2A9D4387338C70467EC43B94DF94098C74C7D10D8AA5B7AF0`
- `docs/ilerleme/poc/cost02_focused.log` -> `865297ED1702FE8621131A866B14CD6C839126F2BD3D8E9B7CDFED34DA82AEDA`
- `docs/ilerleme/poc/cost02_full_suite.log` -> `806EC65EB48EFE808E6B5BD7207FDADBC3364ECB49B4B1B9E97C409DF77C971B`
- `docs/ilerleme/poc/cost02_packaging.log` -> `9A2C4220BC6340F5DD05DBBB76BCD1D301B670D5C2F45B8665E6208ECF56696A`
<!-- COST02_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

### Kalan risk / shortcut

- Katalogda gerçek sağlayıcı fiyatları yok; operatör sürümlü veri sağlamalıdır. Canlı fiyat çekilmediği için
  liste fiyatı ile faturalanan tutar arasında fark olabilir (`estimate_only`).
- Fiyat seçimi `effective_from` sırasına dayanır; aynı zaman damgasına sahip iki girdi varsa belirsizlik vardır ve
  katalog verisi bunu üretmemelidir.
- Para birimi dönüşümü yapılmaz; farklı para birimleri toplanmaz.

---

## Şablon (sonraki görevler)

```
## <GÖREV-KODU> — <başlık>

- Durum:
- Kapsam:
- Çıktı / değişen dosyalar:
- Doğrulama komutu:
- Gerçek çıktı:
- Kabul kriteri karşılandı mı (kanıtla):
- Kalan risk / shortcut:
```
