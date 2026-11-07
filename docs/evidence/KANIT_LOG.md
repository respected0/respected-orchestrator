# Kanıt kaydı

Bu dosya tamamlanan her görevin kanıtını tutar. Kural: **kanıt yoksa görev tamamlanmış sayılmaz.**
Her giriş şu dört parçayı içerir: kapsam, değişen dosyalar, doğrulama komutu ve gerçek çıktı, kalan risk.
Açık işler: `docs/ROADMAP.md`. Kararların gerekçesi: `docs/adr/`.

> **Not (4 Kasım 2026):** `evidence/poc/` altındaki koşu günlükleri (`*_focused.log`, `*_full_suite.log`, `*_packaging.log`, `*_docs_gate*.log` vb.) repodan çıkarıldı ve repo dışında `respected-orchestrator-evidence-logs.zip` arşivine taşındı. Aynı tarihte plan taslakları, rakip araştırması (`COMPETITOR_RESEARCH.md`) ve `ROADMAP_EXECUTION_PLAN.md` kaldırıldı; içerikleri git geçmişindedir ve kararlar `docs/adr/` altında özetlenmiştir. Aşağıda adı geçen ama `evidence/poc/` içinde bulunmayan günlükler bu arşivdedir. Betikler, sonuç JSON'ları ve canlı doğrulama kanıtları yerinde kalır.

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
  - `docs/evidence/KANIT_LOG.md` (bu dosya)

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
python docs/evidence/poc/sec01_probe.py docs/evidence/poc/sec01_results.json
```

| PoC | Deneme | Sonuç | Kanıt |
|---|---|---|---|
| P-01 | workspace dışındaki dosyayı okuma | ALLOWED | `TOPSECRET` okundu |
| P-02 | workspace dışına dosya yazma | ALLOWED | `write-ok`, dosya oluştu |
| P-03 | `example.com:443` TCP çıkışı | ALLOWED | `connected` |
| P-04 | worktree içindeki `.env` okuma | ALLOWED | `API_KEY=sk-fake-not-real` |
| P-05 | workspace içindeki junction üzerinden dışarı okuma | ALLOWED | `TOPSECRET` okundu |

Makine okunur çıktı: `docs/evidence/poc/sec01_results.json`. Sonuçlar `THREAT_MODEL.md` §8 ile aynıdır ve S-01, S-03, S-04 ve junction satırlarındaki "Yok" ifadesini doğrular. Bu bir açık kaydı değil, bilinen sınırın ölçümüdür; kapatma SEC-02/SEC-03/SEC-04.

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
  - `docs/evidence/poc/eval01_results.json` (yeni) — 3 tekrarlı gerçek koşu raporu
  - `docs/ARCHITECTURE.md` (test tablosu + değerlendirme koşucusu bölümü)
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` (durum)

### Doğrulama

Komut (depo kökünde):

```
python -m tests.evals.runner --repeat 3 --out docs/evidence/poc/eval01_results.json
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
  - `docs/evidence/poc/rel02_gate_proof.txt` (kapı kanıtı)
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` (durum)

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
- Çıktı / değişen dosyalar: `docs/COMPETITOR_RESEARCH.md`, `docs/adr/ADR-001…006.md`, `docs/evidence/poc/doc01_check.py`, `docs/evidence/poc/doc01_check.txt`, `tests/docs/test_decision_records.py`, `docs/ARCHITECTURE.md` (§9 test tablosu).
- Doğrulama komutu: `python docs/evidence/poc/doc01_check.py`; `python -m unittest tests.docs.test_decision_records -v`; `python -m unittest discover -s tests -t .`
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
  - `docs/evidence/poc/sec02_probe.py` (yeni): AppContainer profilini oluşturan, çalışma alanı/Python dizinine ACL veren, üç kez gerçek süreç başlatan ve sonuçları JSON'a yazan prototip.
  - `docs/evidence/poc/sec02_results.json` (yeni): ham ölçüm.
  - `docs/evidence/poc/SEC02_SANDBOX_COMPARISON.md` (yeni): dört seçeneğin karşılaştırması ve sınırlar.
  - `docs/ARCHITECTURE.md` §2: SEC-02 doğrulaması ve SEC-03'e kadar geçerli sınır.
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`, `docs/evidence/respected_orchestrator_github_issues.csv`: SEC-02 tamamlandı.
- **Seçim:** Yetenek SID'i olmayan **AppContainer**. Kısıtlı belirteç ayrı dosya güvenlik sınırı olmadığı için reddedildi; Windows Sandbox VM'i başlangıç maliyeti ve dosya paylaşımı nedeniyle ertelendi.
- **Doğrulama komutu:** `python docs/evidence/poc/sec02_probe.py docs/evidence/poc/sec02_results.json`
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
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`, `docs/evidence/respected_orchestrator_github_issues.csv` — durum.
- **Doğrulama komutu (odak):**

  ```
  python -m unittest tests.engine.test_worker_policy tests.workflows.test_campaign tests.workflows.test_reviewer_reliability tests.engine.test_token_budget tests.test_context
  ```

  Gerçek çıktı (`docs/evidence/poc/sec03_focused.log`):

  ```
  Ran 65 tests in 74.373s

  OK
  ```

- **Tam regresyon komutu:**

  ```
  python -m unittest discover -s tests -t .
  ```

  Gerçek çıktı (`docs/evidence/poc/sec03_full_suite.log`):

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
  - `docs/evidence/poc/sec03_focused.log` → `1D4C0B1547F0055EA2144D4975352CF06EE7AE8EA75107B7CA602B6C864CC843`
  - `docs/evidence/poc/sec03_full_suite.log` → `3D835D18722BE9E49AF529521FBFA18D8AC058DC62A727D85283EF1281BBF729`
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

  `docs/evidence/poc/sec04_worker_source_final.log`:

  ```
  Ran 4 tests in 4.400s

  OK
  ```

  ```
  python -m unittest tests.engine.test_sandbox -v
  ```

  `docs/evidence/poc/sec04_verify_sandbox_final.log`:

  ```
  Ran 6 tests in 4.069s

  OK
  ```

  ```
  python -m unittest tests.engine.test_security_gate -v
  ```

  `docs/evidence/poc/sec04_security_gate_final.log`:

  ```
  Ran 4 tests in 0.000s

  OK
  ```

  ```
  python -m unittest tests.engine.test_lanes -v
  ```

  `docs/evidence/poc/sec04_lanes_regression_final.log`:

  ```
  Ran 15 tests in 4.947s

  OK
  ```

  ```
  python -m unittest tests.packaging.test_frozen_security.FrozenSecurityTest.test_frozen_engine_rejects_a_symlink_mode_patch_staged_without_symlink_privilege -v
  ```

  `docs/evidence/poc/sec04_frozen_symlink_fixed.log`:

  ```
  Ran 1 test in 15.734s

  OK
  ```

  ```
  python -m unittest tests.packaging.test_frozen_security -v
  ```

  `docs/evidence/poc/sec04_frozen_security_final.log`:

  ```
  Ran 3 tests in 35.553s

  OK
  ```

  ```
  python packaging/build_dist.py --output dist
  ```

  `docs/evidence/poc/sec04_build_final.log`: build tamamlandı; çıktı `dist\RespectedOrchestrator`.

  ```
  python -m unittest tests.packaging.test_frozen_build tests.packaging.test_frozen_security -v
  ```

  `docs/evidence/poc/sec04_frozen_all_final.log`:

  ```
  Ran 7 tests in 54.087s

  OK
  ```

  ```
  python -m unittest tests.docs.test_decision_records -v
  ```

  `docs/evidence/poc/sec04_docs_gate_final.log`:

  ```
  Ran 1 test in 0.103s

  OK
  ```

  ```
  python -m unittest discover -s tests -t .
  ```

  `docs/evidence/poc/sec04_full_suite.log`:

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
  - `docs/evidence/poc/sec04_worker_source_final.log` → `A6B4899950AEF6595E83606C7E0A60D1329C608A8D3DE3D362ADFAD3EC61CC98`
  - `docs/evidence/poc/sec04_verify_sandbox_final.log` → `83C391BAB8358656F5D551285B48A553028D733D11E51F6915C87572C115F1E7`
  - `docs/evidence/poc/sec04_security_gate_final.log` → `C102B2516AEDA62A87A8E6BFF9BBF8C0537991A098C831D730677B39C84E857B`
  - `docs/evidence/poc/sec04_lanes_regression_final.log` → `196E0312291FF450D08338299BE7FF16A408D96DC0C7DAD4F85443B3BFBB4417`
  - `docs/evidence/poc/sec04_frozen_symlink_fixed.log` → `2C89936C0590C19BF5A59A44ECA824A5C83CC67F607962D94F86CBBCD1F66EF5`
  - `docs/evidence/poc/sec04_frozen_security_final.log` → `18EAB2F62BB1443BB61631B1C15283B645CFBE11B1DFB01D8BD551754D6C786C`
  - `docs/evidence/poc/sec04_build_final.log` → `9A6ADA2259D0E5DEEFE7CAFF437B0084B7CD277CEE6E8E96DBD7738D3E4158AC`
  - `docs/evidence/poc/sec04_frozen_all_final.log` → `CE5379121AC1DF1A769A41D634A61D8D58AE641A69899E3F9DFC63C3B822FC87`
  - `docs/evidence/poc/sec04_docs_gate_final.log` → `28747187822C788FBA68E9F01CF66A7FFDB03BCD69E66EE1ED4E9E3A3EABEC17`
  - `docs/evidence/poc/sec04_full_suite.log` → `94988541A2177179AA708DA882A2659D0F5BE3BE7B281314BA0C94DF2F0A2968`
  - `tests/engine/security_cases.py` → `F96FC4D453DF707D5438EADFF99B57182262D861E15C330FF3DFC6B0AD7A70D9`
  - `tests/engine/test_worker_security.py` → `C8919E71DEA85337BD1DB216BB7FC225A547C2E369E77F015BCDD8010532A61E`
  - `tests/engine/test_security_gate.py` → `24035E715CD5FD04FE8AA2B8C03A31E1FD1A24A5CAAF7425F2AAD5D27C13382A`
  - `tests/packaging/test_frozen_security.py` → `5C089FC0E527C4E1800E342A2F71EC5D9232E103CFD74D7C8351AB75948446DA`
  - `src/respected_orchestrator/engine/lanes.py` → `B4E87F122F5E0F91ADE758A81C84E26430CF5B3A69E52F1AE74A248A575B324F`
  - `.github/workflows/ci.yml` → `5EB3470F7B9AFC845016F1EB28808441EDBDE580011D07A2584406A7CE3F2C93`
  - `docs/ARCHITECTURE.md` → `B743BCEEF460AC9605F1A7CA64E79D03DD8B860702EC63C9114E3DD2C1811341`
  - `docs/THREAT_MODEL.md` → `83579D281921EE0051E12077B5DB698345A77ED34C0025F85296A26125133ACF`
  - `docs/ROADMAP_EXECUTION_PLAN.md` → `2D92A11554AC252E9A831E4FB54A19B70DCE84FE14FF79A09B42B2C74F4E8F44`
  - `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` → `E43BAE6D72F003AA9A9096D867A65609E45BEA4ABC73BBEC73C145391B300D57`
  - `docs/evidence/respected_orchestrator_github_issues.csv` → `4029911DDEF5A409D3FD1EDBA23A67867CBF6A3AD7714F837094B7335408AB94`

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
  - `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
    `docs/evidence/respected_orchestrator_github_issues.csv` — QUA-01 durumu `done`.
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

- `docs/evidence/poc/qua01_focused_final.log` → `98F5AEF657BBA630FD9E09634E9A1B5447F0667F8DD7918BD70F52472EC74F64`
- `docs/evidence/poc/qua01_docs_gate_final.log` → `128FFCA2D72C9AE111CE47CD0D182F3E93FDA9AB3EEE1523F718482F3214F2A1`
- `docs/evidence/poc/qua01_docs_gate_after_docs.log` → `4E0675BD217A1DCBB9A21DA31534A112E570974ED36F3CB987B03537C7259A2A`
- `docs/evidence/poc/qua01_full_suite_final.log` → `4C9F43373FEDAC86438D67BDCCE422415FCE3D8FB32D149FECE311A2799A8CC1`
- `docs/evidence/poc/qua01_roles.log` → `63A3B0D90BB911B75A1BFF24BDA3A8C513EE2536B259CD0A5F714CDE62590823`
- `docs/evidence/poc/qua01_runner_tester.log` → `BA6B00155D97FEC9782B6135BE23E77955ECA202F9E92D5298C3A7E5C512303D`
- `docs/evidence/poc/qua01_failclosed.log` → `930C0E9ED4D6C152D95D48AAFD6147DE3850BF537F305D71DD6B9D4EDE4A4F23`
- `docs/evidence/poc/qua01_maf.log` → `5C09EDA8A64DB7FF24FAD8FAA22ED82AEFB31C1B6CA100DD609D870B4FFEB210`
- `docs/evidence/poc/qua01_focused.log` → `DE2D6C31EC49DEDF3F31F849A02FA21D8F4B10365B7A5E736D341F97B8D1C791`

Senkron dokümanların son doğrulama öncesi SHA-256 değerleri:

- `docs/THREAT_MODEL.md` → `38EC9554E62049716CADB8CDE454AA689E5C4ADFA68CB69D6FEE340A5300E930`
- `docs/ARCHITECTURE.md` → `0A58DFD4026DA58DB227B13CE2E85349280C30EE71A799D2D916D083A2E2E874`
- `docs/ROADMAP.md` → `38BB640D48217FD13800BFD13C0B1FAE8CBA1FF044C6E5F49727E3942D96BE91`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `7580C0FF4295A00D8FB5181277F2082A0BB6BBFD6D78AD254389328C92CD4B95`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` → `0D08267532BCF0A8AB2FC86BEDF973262D40FC0575FF85D3DFC5BD6F0F6CDCC0`
- `docs/evidence/respected_orchestrator_github_issues.csv` → `0338E690723DD65F7B5E9D3B016865A0E93483FA23D79A31F1F752176EA4E801`

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

- `docs/evidence/poc/qua03_focused_final.log` → `C37537CECB8F69C11256BBF0B4ED1AFF29078B16E296C6C577F92C50B9D657B4`
- `docs/evidence/poc/qua03_docs_gate_final.log` → `B859CBE6A7F40085E3671F63F793BA2D1BCE4D17827C24ED4D63FBBED68E5A29`
- `docs/evidence/poc/qua03_docs_gate_after_log.log` → `4AFCC149CB5D426186DF417C37C69CE5CE3311C5FF04B1CD6173750A80D4CB5A` (son KANIT_LOG düzenlemesinden sonra yeniden çalıştırıldı: 1/1 `OK`, exit 0)
- `docs/evidence/poc/qua03_full_suite_final.log` → `0BC04B86114FCD8381810C847013400231EB50447FF4F2466CD86D26DE14DEF3`

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
  - `docs/ROADMAP_EXECUTION_PLAN.md` ve `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`: görev durumu ve kabul kutuları güncellendi.
  - `docs/evidence/respected_orchestrator_github_issues.csv`: QUA-04 `done`.
  - `docs/evidence/KANIT_LOG.md` (bu bölüm).

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

- `docs/evidence/poc/qua04_invariants.log` → `077CE8702C69FF31E2AB4DE0E36BF4CCD772DAF28E6A4562639436E9A9E0DAB4`
- `docs/evidence/poc/qua04_focused.log` → `275F5459DABD836CA85C103652485B82CFEF6EA7BDB1872F24C118E30C6886EE`
- `docs/evidence/poc/qua04_docs_gate.log` → `55B8C366A4827A3F53EA50372185D3D1B332D779C9E18D22263CCB704F7F1DCC`
- `docs/evidence/poc/qua04_full_suite.log` → `7F94517029101A119C7E216010D71279CC7CBF764892EA125CF8D0066B7E2E8B`
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
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` → `273DC2A086984114C358EACA1769CBECE0505E7238DC3F135EA40E35D0C1F0EE`
- `docs/evidence/respected_orchestrator_github_issues.csv` → `CD1ABD5EDE3B9A438AEB072A799F5F13F103A957AB392A98E788274EAC63E967`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/evidence/poc/qua04_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
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
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`: SCH-01 durumu ve kabul kutuları.
  - `docs/evidence/respected_orchestrator_github_issues.csv`: SCH-01 `done`.
  - `docs/evidence/KANIT_LOG.md` (bu bölüm).

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
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` → `CFE976AB981D6944A775BE78A917D8BD8305A1E5BB3EFE4EF53DEE7D075EE5A6`
- `docs/evidence/respected_orchestrator_github_issues.csv` → `33023C72A5D487D33F321FAA67F5172A997FDBC4217BDB3C75B67A4A89680E4B`
- `docs/evidence/poc/sch01_planner_focused.log` → `6C252CB037F59206D98F5648C142A968916A4D15B515FFD4DBA530A839711DE7`
- `docs/evidence/poc/sch01_related_regression.log` → `D05E348DE2168FC0098DD5C160914694811EAAC7C45A23951D8544C88D639762`
- `docs/evidence/poc/sch01_docs_gate.log` → `6E4172ABA50A8A3A4C0FDCC57D44A4186100CE17B23284B719F3249403AB19CF`
- `docs/evidence/poc/sch01_full_suite.log` → `5AB795D15F6391EA10AA5E0671FCE6BAA957C2191D9A306C06182DAF84957E68`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/evidence/poc/sch01_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
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
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`: SCH-02 durumu ve kabul kutuları.
  - `docs/evidence/respected_orchestrator_github_issues.csv`: SCH-02 `done`.
  - `docs/evidence/KANIT_LOG.md` (bu bölüm).

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
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` → `E4897582D2A5639A0C6F3994B5FFE6E4BD42A28D7C1C6FE73585EF56D23862F5`
- `docs/evidence/respected_orchestrator_github_issues.csv` → `C964AE653F85262CFB9DAFFB1BECB11C6D4DD9A64992838814BAF99ECC35B062`
- `docs/evidence/poc/sch02_campaign_baseline.log` → `88A1E206019F67CC51B1442CAA68B4D42FCFA6D95F7B92088D19E10C2988BBCD`
- `docs/evidence/poc/sch02_scheduler_focused.log` → `07967650F7B599E2C953851F005F3CF4584EB61E551A5F76B07A4B4989D5FABA`
- `docs/evidence/poc/sch02_related_regression.log` → `68877F60DAF51C49CA3D2A4029D9246938688F9DE653D85B430C204BB8235293`
- `docs/evidence/poc/sch02_docs_gate.log` → `16B88813FDA7141CD3CE60CC1E17D2E1F9F296A1DCCC83107CC02815CEE1E02A`
- `docs/evidence/poc/sch02_full_suite.log` → `06158FB03ED365C2FB28B16390E0978A86D6D00ABEF9FF5278C842BB7E4DACCC`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/evidence/poc/sch02_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
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
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`: SCH-03 durumu ve kabul kutuları.
  - `docs/evidence/respected_orchestrator_github_issues.csv`: SCH-03 `done`.
  - `docs/evidence/KANIT_LOG.md` (bu bölüm).

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
- `docs/evidence/respected_orchestrator_github_issues.csv` → `42D8C006072B2CF19F037DB391B47135E748DD61A914517F7609AEF31A7AC544`
- `docs/evidence/poc/sch03_integration_focused.log` → `386FFFEAA7A213932341E490A52946CA2B20098DAFB6431F59D88CD0AC7DEBF0`
- `docs/evidence/poc/sch03_related_regression.log` → `C71FA770C89AB7616B6619A87C5A5A2AC9FA6762E8F4832452DDAC95ABC64D26`
- `docs/evidence/poc/sch03_full_suite.log` → `9F285834B5CE0F8207321A2731DC7D434563D801149EEEAEC82551506B1D137F`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/evidence/poc/sch03_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
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
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`: SCH-04 durumu ve kabul kutuları.
  - `docs/evidence/respected_orchestrator_github_issues.csv`: SCH-04 `done`.
  - `docs/evidence/KANIT_LOG.md` (bu bölüm).

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
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` → `796EB0008367AE21DB0560F0D061D58B7E290B1DC4F8FD4A7D0D04D554163453`
- `docs/evidence/respected_orchestrator_github_issues.csv` → `FC37BE78574550D422A8A394F2495F7E74BCF17B79F8CA5183C493F80A0F123B`
- `docs/evidence/poc/sch04_coordinator_focused.log` → `790D70DCBBFD071D3598C92006C338011368E1F7757BE089513524890EC20142`
- `docs/evidence/poc/sch04_related_regression.log` → `8917982DB6B1E0C7ABD9E49CB02A954025B1E5E5DB1E84C972E91B365F4DE4BC`
- `docs/evidence/poc/sch04_full_suite.log` → `1EEA3F0AEC1A4DED3617477E1BE2EF371EF6B7507878698635D90BEAB274D9B7`

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/evidence/poc/sch04_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
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
  - `docs/ROADMAP.md`, `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`: görev durumu ve kabul kutuları.
  - `docs/evidence/respected_orchestrator_github_issues.csv`: RES-01 `done`.
  - `docs/evidence/KANIT_LOG.md` (bu bölüm).

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
- `src/respected_orchestrator/workflows/checkpoint.py` -> `39D620BEC0A53DD21D06A3A739B3DFE80158FBEC4646C147D23DA13BCC5CFB6D`
- `tests/workflows/test_checkpoint.py` -> `6EA63522778243F4844585BD97810683184616A4DF25820690BA881CEF64527F`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/ROADMAP.md` -> `4773B6AC7349AA203B8676BEB7C0842C87C104472468505242B1D4EC8833A94E`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `F759DBF55ED98527325E1854EC60D33CF239E9AE98109FF88FC2B13FA14CEE57`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
- `docs/evidence/poc/res01_checkpoint_focused_after_fix.log` -> `FDFE02EBE9C5554524AD02DE608772BCF25100437B6BD608D60F79BF01EDED31`
- `docs/evidence/poc/res01_related_regression.log` -> `63B04555A96BC7513C0787C8DD9B61EC820F5EABDF6512954FB98471269B29C9`
- `docs/evidence/poc/res01_full_suite.log` -> `BA115B1DBBCEEF5E6B44F7B5C5C259B9CFB16B2CF93391F9D8C41F6A687789BD`
<!-- RES01_HASHES_END -->

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/evidence/poc/res01_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında tutulur.
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
    `docs/ROADMAP_EXECUTION_PLAN.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
    `docs/evidence/respected_orchestrator_github_issues.csv`: RES-02 sözleşmesi ve durum senkronu.

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
- `src/respected_orchestrator/engine/runner.py` -> `48200B47CB1732F0EB1BCEDF06D416AAB448E7B6EB5D46F16423BA7E662F7BAD`
- `src/respected_orchestrator/__main__.py` -> `4455B23D9A934A86EDED7548A1957AC8630C3D76D84F1AE4CE90A33F6322371A`
- `tests/workflows/test_project_resume.py` -> `2F8887923B5A58201712A99B69688F4E13080F8EDC8E38606D9C192E2AE0DCC3`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/COMMANDS.md` -> `6F0CCDA08E1B7C7C36A915A58AF4A6C232E4A09669D1D791DD7C85F06A097FBA`
- `docs/USAGE.md` -> `4EA459BEF0F8A50B96AC1899EB69B7E63C1DD1B58DDA714B9134B04970BE8F39`
- `docs/ROADMAP.md` -> `4773B6AC7349AA203B8676BEB7C0842C87C104472468505242B1D4EC8833A94E`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `F759DBF55ED98527325E1854EC60D33CF239E9AE98109FF88FC2B13FA14CEE57`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
- `docs/evidence/poc/res02_invariants.log` -> `A042271F883C4E7CC69BCB00C6C164CDA0C376EA94491FB38AA240794940CE47`
- `docs/evidence/poc/res02_focused.log` -> `7835A6B358E8ED9A2F02DAC45FEB05579A676D1FE0D1747CA232D315EE20B727`
- `docs/evidence/poc/res02_related.log` -> `F7CDE08DD75D9FBB99AE9B35FAB0CDBC37777F1900CB4270C293684AE080A831`
- `docs/evidence/poc/res02_full_suite.log` -> `F3CFD9362DB317C9864531D81CE431919CA5361F0C6986D372F0B2E887F4A866`
<!-- RES02_HASHES_END -->

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/evidence/poc/res02_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında
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
  `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/evidence/respected_orchestrator_github_issues.csv`.
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
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/ROADMAP.md` -> `4773B6AC7349AA203B8676BEB7C0842C87C104472468505242B1D4EC8833A94E`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `F759DBF55ED98527325E1854EC60D33CF239E9AE98109FF88FC2B13FA14CEE57`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
- `docs/evidence/poc/res03_focused.log` -> `EDBFCA902AFEEBF47E558EC597311293EF7375A9EBE44F679704014F7D1DCBFD`
- `docs/evidence/poc/res03_packaging.log` -> `612F405ED5229D45EC3015F6A8020A53A503E45D4D3EF4B577EF48ADA6CCFBEE`
- `docs/evidence/poc/res03_full_suite.log` -> `18D3800BB82200BDE9D60E5BBD51F2B0F29726ADFA328F2ED99C42A40797DD10`
<!-- RES03_HASHES_END -->

Bu bölümün son düzenlemesinden sonra doküman kapısı yeniden çalıştırılır; gerçek çıktı
`docs/evidence/poc/res03_docs_gate_after_log.log` içinde, SHA-256 değeri aynı adlı `.sha256` sidecar dosyasında
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
  `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`, `docs/evidence/poc/adp01_*`.
- Doğrulama komutu:

```text
$env:PYTHONPATH='src'
py -m unittest tests.engine.test_opencode_acp tests.engine.test_runner tests.engine.test_opencode_auth
$env:RESPECTED_OPENCODE_NETWORK='allow'
py docs/evidence/poc/adp01_real_e2e.py
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
`docs/evidence/poc/adp01_timeout_decision.md`. ACP kimlik köprüsünde değişiklik gerekmedi.

### Test sonuçları

- Odaklı: `Ran 63 tests ... OK` (`docs/evidence/poc/adp01_fenced_focused.log`).
- Tam regresyon: `Ran 603 tests ... OK` (`docs/evidence/poc/adp01_full_suite.log`).
- Paketleme: `py packaging/build_dist.py` başarılı (`adp01_packaging.log`); frozen build/security
  `Ran 7 tests ... OK` (`docs/evidence/poc/adp01_packaging_tests.log`).
- Ortam: `opencode v2.2.3`, model `amd/DeepSeek-V4.1-Flash`, Windows.

### Kanıt artefaktları (SHA-256)

<!-- ADP01_HASHES_START -->
- `src/respected_orchestrator/engine/opencode_acp.py` -> `8FA34A34F19D2FB0B1A6E9D90D2156A4E574ED68BFCFA2AF2F35C581E6167A00`
- `src/respected_orchestrator/engine/opencode_auth.py` -> `7DB2AE187168363A853C9E52B70D95A07B612D21C16268C8269ED6DD5FA0E9B9`
- `src/respected_orchestrator/engine/runner.py` -> `48200B47CB1732F0EB1BCEDF06D416AAB448E7B6EB5D46F16423BA7E662F7BAD`
- `tests/engine/test_opencode_acp.py` -> `ED1D72BB2EE8A78752C2E268D3C68FEF028CB9684AAD1F509369C569D471CBFA`
- `docs/evidence/poc/adp01_fenced_focused.log` -> `36051B9C2332D1E0A671E4100433AF1CF74BC6F1C11D8FA63C9C55DD064C14B5`
- `docs/evidence/poc/adp01_full_suite.log` -> `3523ECEBB966623FE6B617367A3011B5EBC6948FC3A960721783E06BDFFF431C`
- `docs/evidence/poc/adp01_packaging.log` -> `26EC259AA977D423F97B86C28734887896F29B5EBD8DF5BC8DCDEE58BE720F17`
- `docs/evidence/poc/adp01_packaging_tests.log` -> `980BB980AF09C9BD3D17E92C48424774D49956C0A82C2035C071FBF9E93AA4C8`
- `docs/evidence/poc/adp01_timeout_decision.md` -> `14F27087CE7DD71255F9AF85599B4FDD419D0B27314FE6EBCD71D444870D5A80`
- `docs/evidence/poc/adp01_real_e2e.py` -> `44BEBE12C1198D12F5748447FEA14E9E53A1C2B2DA0B424990CC3ADFE926E49A`
- `docs/evidence/poc/adp01_real_e2e_run.log` -> `77D4173588309AA9D109B7AA314FFE0166DA68D9A70666ADD56B5046C187A7BD`
- `docs/evidence/poc/adp01_real_read.log` -> `3CFDCE5ED41D238991410F8DC81A1CBF69666C7BDDA0A19F21B175335F7CA113`
- `docs/evidence/poc/adp01_real_write.log` -> `3A1A389847B01800A76795928137E418AB3DED8894BBE4D1F9E301B8482C2367`
- `docs/evidence/poc/adp01_real_invalid_model.log` -> `553F314EBC8A9811717229C02C7911D01676851602A9E8009278422575EF72D0`
- `docs/evidence/poc/adp01_real_timeout.log` -> `001E610C3A2C1C7A4E618DDFD800E6A52FC379104E3B7BE6A2DEC7B92394F267`
- `docs/evidence/poc/adp01_real_acceptance_failure.log` -> `16C6526483DD1CE13F63604B8C43A7FE47D82B1535247BEB872581A1CA601A2D`
- `docs/evidence/poc/adp01_real_auth_missing.log` -> `86909347E3A2BC5D76EC802A1D663E2593C613CCE504CA727AFEC8109879D548`
- `docs/evidence/poc/adp01_real_mcp.log` -> `C4311EA426FE6C7487340B7011C7D2EAA796D4F0A8D656211877A756DF8BF76E`
- `docs/evidence/poc/adp01_real_summary.log` -> `0CF25F7A8B4EFCE77C3AFA246E42EC2D203F4237C24A888A750D3E56504B0483`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/COMMANDS.md` -> `6F0CCDA08E1B7C7C36A915A58AF4A6C232E4A09669D1D791DD7C85F06A097FBA`
- `docs/USAGE.md` -> `4EA459BEF0F8A50B96AC1899EB69B7E63C1DD1B58DDA714B9134B04970BE8F39`
- `docs/ROADMAP.md` -> `4773B6AC7349AA203B8676BEB7C0842C87C104472468505242B1D4EC8833A94E`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `F759DBF55ED98527325E1854EC60D33CF239E9AE98109FF88FC2B13FA14CEE57`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
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
  `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/evidence/respected_orchestrator_github_issues.csv`, `docs/evidence/poc/adp02_*`.
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

- Odaklı: `Ran 7 tests ... OK` (`docs/evidence/poc/adp02_focused.log`; politika 6/6 + ADR kapısı).
- Tam regresyon: `Ran 506 tests ... OK` (`docs/evidence/poc/adp02_full_suite.log`).
- Paketleme: `py packaging/build_dist.py` başarılı; `Ran 7 tests ... OK`
  (`docs/evidence/poc/adp02_packaging.log`).
- Canlı sağlayıcı çağrısı bu görevde yapılmadı; ADP-03 adaptörü `require_access` çağırmadan istek başlatamaz.

### Kanıt artefaktları (SHA-256)

<!-- ADP02_HASHES_START -->
- `src/respected_orchestrator/engine/provider_policy.py` -> `A4904EA9FED3B59ED61E6A1F453ECD32C1894ED210E7495E3EB2F8406EE5D3CE`
- `tests/engine/test_provider_policy.py` -> `77CB4CA5BE5ACF916C647F5A05C23A257C61144AFE9518846932E68FD4E3F920`
- `docs/adr/ADR-007-provider-key-network-threat-model.md` -> `41735F348DA4F25089F0524A9A6946CA9453D83179297B483A37D9964D2F724C`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `F759DBF55ED98527325E1854EC60D33CF239E9AE98109FF88FC2B13FA14CEE57`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
- `docs/evidence/poc/doc01_check.py` -> `9D765DB66BA2C49D9157FEEDF81C364D79B3B3D67957E4A5C0F2E6C998EEDC9F`
- `docs/evidence/poc/adp02_focused.log` -> `252A7CCE280B94CE4C8CF9C7E3CA7C4C6EF16FEA271D5CEBDF1368D8A5F48A8B`
- `docs/evidence/poc/adp02_full_suite.log` -> `BEE08E716D408688F91A4FA52241657E5A7197377DBAB52F36909FEFDD6FA079`
- `docs/evidence/poc/adp02_packaging.log` -> `71256C6B5EB217111E373BECEE08A800C04462B56F1ACAD0ABE4800E802DB423`
<!-- ADP02_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

### Kalan risk / shortcut

- ADP-02 kararı uygulama değil sözleşmedir; canlı adaptör, DPAPI kasası ve gerçek 401/429/5xx davranışı ADP-03'te
  test edilecektir.
- Allowlist tam alan adı eşleşmesidir; alt alan adı veya joker desteği bilinçli olarak yoktur.
- Sağlayıcıya giden görev metni ve dosya içeriği sağlayıcı tarafından görülür; opt-in bunu kabul etmek demektir.
- `docs/evidence/poc/doc01_check.py` ADR erişim tarihini artık herhangi bir ISO tarihi olarak doğrular; araştırma
  kaynak tablosunun ortak erişim tarihi (`2026-10-30`) değişmedi.

---

## COST-02 — Sürüm kontrollü fiyat kataloğu ve belirsizlik sözleşmesi

- Durum: Tamamlandı.
- Kapsam: Model fiyatını sürüm ve zaman damgasına bağlı, deterministik ve belirsizliği açıkça gösteren bir katalog
  sözleşmesi. Canlı fiyat çağrısı zorunlu değildir; hiçbir eksik veri sıfır maliyet sayılmaz.
- Çıktı / değişen dosyalar: `src/respected_orchestrator/engine/pricing.py`, `tests/engine/test_pricing.py`,
  `docs/ARCHITECTURE.md`, `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/evidence/respected_orchestrator_github_issues.csv`, `docs/evidence/poc/cost02_*`.
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

- Odaklı: `Ran 6 tests ... OK` (`docs/evidence/poc/cost02_focused.log`).
- Tam regresyon: `Ran 512 tests ... OK` (`docs/evidence/poc/cost02_full_suite.log`).
- Paketleme: `py packaging/build_dist.py` başarılı; `Ran 7 tests ... OK`
  (`docs/evidence/poc/cost02_packaging.log`).

### Kanıt artefaktları (SHA-256)

<!-- COST02_HASHES_START -->
- `src/respected_orchestrator/engine/pricing.py` -> `E552300D521F83DEEDCAEE68BD7FDEED61BCB4BFF9D9EE444E91D2C2177ACF42`
- `tests/engine/test_pricing.py` -> `E44B09E8F87DCDAA269F310B9CBAFE3C8B76B1EB410F28B7E28774E53CB3788F`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
- `docs/evidence/poc/cost02_focused.log` -> `865297ED1702FE8621131A866B14CD6C839126F2BD3D8E9B7CDFED34DA82AEDA`
- `docs/evidence/poc/cost02_full_suite.log` -> `806EC65EB48EFE808E6B5BD7207FDADBC3364ECB49B4B1B9E97C409DF77C971B`
- `docs/evidence/poc/cost02_packaging.log` -> `9A2C4220BC6340F5DD05DBBB76BCD1D301B670D5C2F45B8665E6208ECF56696A`
<!-- COST02_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

### Kalan risk / shortcut

- Katalogda gerçek sağlayıcı fiyatları yok; operatör sürümlü veri sağlamalıdır. Canlı fiyat çekilmediği için
  liste fiyatı ile faturalanan tutar arasında fark olabilir (`estimate_only`).
- Fiyat seçimi `effective_from` sırasına dayanır; aynı zaman damgasına sahip iki girdi varsa belirsizlik vardır ve
  katalog verisi bunu üretmemelidir.
- Para birimi dönüşümü yapılmaz; farklı para birimleri toplanmaz.

---

## ADP-03 — OpenRouter/API sağlayıcı adaptörü

- Durum: Tamamlandı.
- Kapsam: ADP-02 ağ kapısını uygulayan OpenRouter adaptörü; DPAPI anahtar kasası, model kataloğu okuma, idempotent
  istek, zaman aşımı/rate-limit/hata sınıflandırması, kısmi akış reddi ve bilinmeyen kullanımın korunması.
  Adaptör henüz CLI'ye bağlanmadı; sözleşme ve test edilebilir istemci hazırdır.
- Çıktı / değişen dosyalar: `src/respected_orchestrator/engine/provider.py`,
  `src/respected_orchestrator/engine/secret_vault.py`, `tests/engine/test_provider.py`,
  `docs/evidence/poc/adp03_real_smoke.py`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_EXECUTION_PLAN.md`,
  `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/evidence/respected_orchestrator_github_issues.csv`, `docs/evidence/poc/adp03_*`.
- Doğrulama komutu:

```text
$env:PYTHONPATH='src'
py -m unittest tests.engine.test_provider
$env:RESPECTED_PROVIDER_NETWORK='allow'
$env:RESPECTED_PROVIDER_CODE_GATE='1'
py docs/evidence/poc/adp03_real_smoke.py
py -m unittest discover -s tests -t .
py packaging/build_dist.py
py -m unittest tests.packaging.test_frozen_build tests.packaging.test_frozen_security
```

### Adaptör davranışı

- Her `complete`, `complete_stream` ve `models` çağrısı önce `require_access` ile opt-in, kod kapısı, `https` ve
  `openrouter.ai` allowlist'ini doğrular. Kapı geçilmeden transport çağrılmaz.
- Anahtar `SecretVault` içinde Windows DPAPI ile kullanıcıya bağlı şifreli blob olarak saklanır; kasa yoksa
  `auth_missing` döner. Test, dosya byte'larında düz metin anahtar olmadığını doğrular.
- Aynı `idempotency_key` ikinci kez geldiğinde önbellekteki sonuç döner ve ağ çağrısı sayısı artmaz.
- Durum sınıfları: 401 `unauthorized`, 429 `rate_limited`, 5xx `provider_error`, ağ/süre `timeout` veya `network`,
  `[DONE]` görmeden biten akış `stream_incomplete`, bozuk gövde `invalid_response`. Hiçbiri başka sağlayıcıya veya
  modele sessiz fallback yapmaz.
- Sağlayıcı `usage` bildirmezse sonuç `usage=None`, `usage_status=UNKNOWN` olur; sıfır varsayılmaz.

### Mock API senaryoları (6/6)

| Senaryo | Beklenen | Sonuç |
|---|---|---|
| 200 | `completed`, içerik korunur, bilinen kullanım aktarılır | geçti |
| 401 | `unauthorized`; tek çağrı, fallback yok | geçti |
| 429 | `rate_limited`; tek çağrı, fallback yok | geçti |
| 500 | `provider_error` | geçti |
| timeout | `timeout` | geçti |
| partial stream | `[DONE]` yoksa `stream_incomplete` | geçti |

Ek olarak idempotent tekrar (1 ağ çağrısı), eksik anahtar (`auth_missing`, 0 çağrı), bilinmeyen kullanım ve DPAPI
kasa round-trip'i test edildi.

### Gerçek E2E smoke

- `adp03_real_smoke.py` gerçek `https://openrouter.ai/api/v1/models` isteğini aynı kapıdan yaptı:
  451 model, liste SHA-256 `8391D3BFA965DC13497A85C98E3D447F20A905E17971AFF437121E6C5C11BEAC`.
- Ortamda OpenRouter API anahtarı yok; kimlikli sohbet/yazma smoke'u çalıştırılamadı. 200 yazma yolu yerel mock ile,
  anahtar yokluğu `auth_missing` testiyle kanıtlandı. Bu bir başarı sayılmadı; gerçek anahtarlı smoke kalan iştir.

### Test sonuçları

- Odaklı: `Ran 11 tests ... OK` (`docs/evidence/poc/adp03_focused.log`).
- Tam regresyon: `Ran 523 tests ... OK` (`docs/evidence/poc/adp03_full_suite.log`).
- Paketleme: `py packaging/build_dist.py` başarılı; `Ran 7 tests ... OK`
  (`docs/evidence/poc/adp03_packaging.log`).
- Gerçek smoke: `docs/evidence/poc/adp03_real_smoke.log`.

### Kanıt artefaktları (SHA-256)

<!-- ADP03_HASHES_START -->
- `src/respected_orchestrator/engine/provider.py` -> `959492EBE99A73A4C3863153FC2A60398DF2D12E0FEFFF7FF3C70A3836E81601`
- `src/respected_orchestrator/engine/secret_vault.py` -> `806E7A177FBACCECC236DFFC203BE81FF7C5B14989F2587252FD65FDCD598BB6`
- `tests/engine/test_provider.py` -> `40AA45CD1EA79DA951E566EDA58164A3E7E5D723FE003E237D298D5EEF61ED83`
- `docs/evidence/poc/adp03_real_smoke.py` -> `A739714CEF74D5D81CD235046329409ED197A3C3100D645909979F5AA1D2583A`
- `docs/evidence/poc/adp03_focused.log` -> `258E13E4EB477D88B0C1CBE7E8DB0090101D1AE3848FA4519DC2C5675A2EF7F7`
- `docs/evidence/poc/adp03_real_smoke.log` -> `824079B8246AE99866B768904A226654BF06E72247576B353FE940EC8165E80A`
- `docs/evidence/poc/adp03_full_suite.log` -> `A78BC5DEF3D2BBA509B57BB1A0545E7FE879BCF85CA3F98EEFACC121E9BF2772`
- `docs/evidence/poc/adp03_packaging.log` -> `50731967B9DC86B46BB0D5A80175C80B8C05AF69C89FA1029E0F91DA55B6992B`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `F759DBF55ED98527325E1854EC60D33CF239E9AE98109FF88FC2B13FA14CEE57`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
<!-- ADP03_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

### Kalan risk / shortcut

- Kimlikli gerçek yazma smoke'u anahtar olmadığı için yapılmadı; adaptörün gerçek sağlayıcıda 200 gövde biçimi ve
  streaming davranışı ilk anahtarlı koşuda doğrulanmalıdır.
- `complete_stream` SSE olaylarının satır sınırında geldiğini varsayar; gerçek sağlayıcı olayı parçalarsa artımlı
  tampon gerekir (`shortcut: satır sınırı varsayımı, gerçek akış parçalarsa`).
- Adaptör CLI/MAF akışına bağlı değildir; bağlanana kadar ürün davranışı değişmez.
- Rate-limit için otomatik yeniden deneme yok; `retryable` işareti çağırana bırakılır.

---

## EXT-01 — Skill/MCP yetenek manifestosu ve izin denetimi

- Durum: Tamamlandı.
- Kapsam: Skill ve MCP araçları için fail-closed yetenek manifestosu; araç/işlem, okuma-yazma-ağ erişimi, veri
  kapsamı, sürüm, provenance ve güven düzeyi. Görev planındaki açık araç onayı olmadan hiçbir araç çalışmaz.
  Brain ve Hub'dan bağımsızdır; yalnızca standart kütüphane kullanır.
- Çıktı / değişen dosyalar: `src/respected_orchestrator/engine/capability_manifest.py`,
  `tests/engine/test_capability_manifest.py`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_EXECUTION_PLAN.md`,
  `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/evidence/respected_orchestrator_github_issues.csv`, `docs/evidence/poc/ext01_*`.
- Doğrulama komutu:

```text
$env:PYTHONPATH='src'
py -m unittest tests.engine.test_capability_manifest
py -m unittest discover -s tests -t .
py packaging/build_dist.py
py -m unittest tests.packaging.test_frozen_build tests.packaging.test_frozen_security
```

### Sözleşme

- Manifest zorunlu alanları: `name`, `version`, `provenance`, `trust`, `tools`, `read`, `write`, `net`, `data_scope`;
  isteğe bağlı `description` ve zorunlu `sha256`.
- `sha256`, manifestin `sha256` hariç kanonik JSON gövdesi üzerinden hesaplanır. İçerik sonradan değişirse veya
  onay kaydındaki digest eşleşmezse `MANIFEST_HASH_CHANGED` ile reddedilir.
- `trust` yalnızca `trusted`; provenance boş olamaz ve onay kaydındaki provenance ile eşleşmelidir. Eşleşmezse
  `UNTRUSTED_SKILL` / `PROVENANCE_MISMATCH` döner.
- Araç allowlist'i `repo.search`, `repo.patch`, `test.run`, `mcp.serena`, `mcp.context`. `exec` kapalıdır; yazma
  yalnızca `workspace`, okuma `repo`/`docs`/`evidence`, ağ `none`/`loopback`/`allowlist` olabilir.
- `tools` içindeki her işlem ilgili üst düzey izinle desteklenmek zorundadır; yoksa `EXCESS_PERMISSION`. Veri kapsamı
  mutlak yol, sürücü harfi veya `..` içeremez.
- `authorize()` yalnızca manifestte bildirilen ve görev planında açıkça onaylanan araçları döndürür; bildirilmeyen
  araç `CAPABILITY_NOT_DECLARED`, onaysız araç `CAPABILITY_NOT_APPROVED` ile engellenir. Varsayılan kapalıdır.
- `description` yalnızca metindir; içindeki talimatlar yetki üretmez.

### Test senaryoları (5/5)

| Senaryo | Beklenen | Sonuç |
|---|---|---|
| Manifest yok | `MANIFEST_MISSING` | geçti |
| Fazla izin (yazma izni yokken yazma işlemi) | `EXCESS_PERMISSION` | geçti |
| Değiştirilen hash / yanlış onay digest'i | `MANIFEST_HASH_CHANGED` | geçti |
| Untrusted skill | `UNTRUSTED_SKILL` | geçti |
| Zararlı açıklama | metin yetki vermez; bildirilmeyen araç `CAPABILITY_NOT_DECLARED` | geçti |

### Test sonuçları

- Odaklı: `Ran 5 tests ... OK` (`docs/evidence/poc/ext01_focused.log`).
- Tam regresyon: `Ran 528 tests ... OK` (`docs/evidence/poc/ext01_full_suite.log`).
- Paketleme: `py packaging/build_dist.py` başarılı; `Ran 7 tests ... OK`
  (`docs/evidence/poc/ext01_packaging.log`).

### Kanıt artefaktları (SHA-256)

<!-- EXT01_HASHES_START -->
- `src/respected_orchestrator/engine/capability_manifest.py` -> `362F41C6519A9152845CFF6F81FBC223691DC57ECD5323517A49ADE54B5CACEA`
- `tests/engine/test_capability_manifest.py` -> `1622D43E787CEAECB20E3C2CDA33996F66B86D1295BA008C71D16C8F6B3CB106`
- `docs/evidence/poc/ext01_focused.log` -> `399507809DD42F7E79A71B1C035827D2BFAED05406C89EED7B033189EDB2E818`
- `docs/evidence/poc/ext01_full_suite.log` -> `55A3C307FB02C3147DD37E4CE1FA934E8E467E3FE11EAE2E00D74CA42FF2EB30`
- `docs/evidence/poc/ext01_packaging.log` -> `A5B09FD7C0BBA0525214A75015AC584A217CECFCFC7B05449D9A5E404913DECD`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/ROADMAP_EXECUTION_PLAN.md` -> `F759DBF55ED98527325E1854EC60D33CF239E9AE98109FF88FC2B13FA14CEE57`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
<!-- EXT01_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

### Kalan risk / shortcut

- Manifest imzası yoktur; güven, kurulum sırasında kaydedilen provenance ve digest kaydına dayanır. Anahtar imzalı
  manifest ileride ayrı bir görevdir.
- Onay kaydı çağıran tarafından sağlanır; bu modül kaydın kendisini üretmez, yalnızca eşleşmeyi denetler.
- Araç allowlist'i sabittir; yeni MCP aracı eklemek kod değişikliği ister (`shortcut: sabit allowlist, yeni araç
  kaydı ürünleşince`).

---

## EVAL-02 — Doğrudan ajan vs Orchestrator karşılaştırma başlangıcı

- Durum: Tamamlandı.
- Kapsam: Aynı fixture, commit, makine ve eşit timeout ile doğrudan ve orkestre kolların karşılaştırılması.
  Doğrudan kol bir değişiklik uygulamaz; orkestre kol doğrulanmış altın yamayı uygular. Bu koşu harness
  tutarlılığını ölçer; model kalitesi iddiası değildir.
- Çıktı / değişen dosyalar: `tests/evals/compare.py`, `tests/evals/test_compare.py`,
  `docs/evidence/poc/eval02_real.py`, `docs/evidence/poc/eval02_results.json`, `docs/evidence/poc/eval02_real.log`,
  `docs/evidence/poc/eval02_eval03_focused.log`, `docs/ARCHITECTURE.md`,
  `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/evidence/respected_orchestrator_github_issues.csv`.
- Doğrulama komutu:

```text
$env:PYTHONPATH='src'
py -m unittest tests.evals.test_compare tests.evals.test_report
py docs/evidence/poc/eval02_real.py
```

### Gerçek koşu

- 20 fixture x 3 tekrar x 2 kol = 120 tam koşu.
- Doğrudan kol: 60 koşu, başarı `0.0`, güvenlik ihlali `0`, süre `7.1011 sn`, maliyet `bilinmiyor`.
- Orkestre kol: 60 koşu, başarı `1.0`, güvenlik ihlali `0`, süre `6.9339 sn`, maliyet `bilinmiyor`.
- Metadata: Python, platform, makine, git sürümü, UTC zaman damgası ve `model=golden-fixture` her raporda mevcut.

### Test sonuçları

- Odaklı: `Ran 9 tests ... OK` (`docs/evidence/poc/eval02_eval03_focused.log`).
- Gerçek koşu: `docs/evidence/poc/eval02_real.log`, rapor `docs/evidence/poc/eval02_results.json`.

### Kalan risk / shortcut

- Koşu gerçek bir modeli değil, altın yama kolunu kullanır; model karşılaştırması için kimlikli sağlayıcı ve kota
  gerekir. Bu nedenle sonuç ürün başarısı olarak sunulmaz (`shortcut: model yerine altın fixture, kimlikli koşu
  sağlanınca`).
- Güvenlik ihlali sayacı bu harness'ta her iki kolda da sıfırdır; gerçek izolasyon testleri SEC serisindedir.

### Kanıt artefaktları (SHA-256)

<!-- EVAL02_HASHES_START -->
- `tests/evals/compare.py` -> `931FA1F82662628E147A85B78332F9C4CAE1F856AEA69BC285E6D3D6E9F90972`
- `tests/evals/test_compare.py` -> `83552BCADD9306FE5A311F4F157C2C7DF6F2940F10A93AF4FE09A0026DD08920`
- `docs/evidence/poc/eval02_real.py` -> `52D1B5FD9DE5666F00662D43F9B2E9EED9AD8B7D673CE56D4CA0E784BCFBC840`
- `docs/evidence/poc/eval02_results.json` -> `02EC598D4562B8B1553F08267DC0F927F94E0A0D6827B2E4BAA7C288454C7B22`
- `docs/evidence/poc/eval02_real.log` -> `F020F5E057820EB8ED167EEB9A3E7025EA51177747E88A5F7F38A0B26CEFE559`
- `docs/evidence/poc/eval02_eval03_focused.log` -> `95E354833E2418305AFA98C394A00FD9242369851E798DC0000F5FFFD8A68B6F`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
<!-- EVAL02_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

---

## EVAL-03 — Kıyas raporu ve regresyon kapısı

- Durum: Tamamlandı.
- Kapsam: JSON/Markdown rapor, dört KPI (kabul başarısı, worker ihlali, maliyet, süre) ve iki koşu arası regresyon
  kapısı. Eksik veri sahte sıfır üretmez; farklı fixture/repeat/timeout raporları engellenir.
- Çıktı / değişen dosyalar: `tests/evals/report.py`, `tests/evals/test_report.py`,
  `docs/evidence/poc/eval03_report.json`, `docs/evidence/poc/eval03_report.md`,
  `docs/evidence/poc/eval02_eval03_focused.log`, `docs/ARCHITECTURE.md`,
  `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md`,
  `docs/evidence/respected_orchestrator_github_issues.csv`.
- Doğrulama komutu:

```text
$env:PYTHONPATH='src'
py -m unittest tests.evals.test_compare tests.evals.test_report
py docs/evidence/poc/eval02_real.py
```

### Rapor ve kapı

- Üretilen gerçek rapor: `eval03_report.json` (KPI + kapı sonucu) ve `eval03_report.md` (insan okunur tablo).
- KPI'lar: kabul başarısı `1.0`, worker ihlali `0`, maliyet `bilinmiyor`, süre `6.9339 sn`.
- Kendisiyle karşılaştırma kapısı geçti (`ok=true`); regresyon testleri başarı düşüşünü ve ihlal artışını ayrı ayrı yakalar.
- Eksik `cost` alanı `missing_kpi` hatası verir; `0` üretmez. Farklı fixture listesi, repeat veya timeout
  `incomparable` ile reddedilir.

### Test sonuçları

- Odaklı: `Ran 9 tests ... OK` (`docs/evidence/poc/eval02_eval03_focused.log`).

### Kalan risk / shortcut

- Gerçek rapor altın fixture kolundan üretildi; model başarısı değildir. Kimlikli model koşusu sağlanınca aynı
  rapor şeması kullanılmalıdır.
- Regresyon eşiği yalnızca kesin düşüş/artış arar; istatistiksel güven aralığı hesaplamaz (`shortcut: kesin eşik,
  tekrarlı örneklem büyüyünce`).

### Kanıt artefaktları (SHA-256)

<!-- EVAL03_HASHES_START -->
- `tests/evals/report.py` -> `1FB26693D95C1CD59ED1F6A63CF0F22AA69DD80675EDD3D8C6FD1F4500CC8FE9`
- `tests/evals/test_report.py` -> `44AC155A1EF14B7D62F9F4821DB474DC635F5D8EFF23408B134BF082C70407C3`
- `docs/evidence/poc/eval03_report.json` -> `8664A080FC9E4E2D96040C8A694DD19B1450F41A3C2FF37D262F5D3EBE9EFC47`
- `docs/evidence/poc/eval03_report.md` -> `F06E5F2092B22A45C65EF1CB379188C0F2E7B6267802657FDCC01E561D1F1306`
- `docs/evidence/poc/eval02_eval03_focused.log` -> `95E354833E2418305AFA98C394A00FD9242369851E798DC0000F5FFFD8A68B6F`
- `docs/ARCHITECTURE.md` -> `81B03B0A99298E4BDF14DDC2738C8F29E58589EC4163AE1F0F95C1A48D3A67DF`
- `docs/evidence/respected_orchestrator_roadmap_gorev_plani.md` -> `325DDA701A9275182831710A37C85E8E47A721037A54EF706D58C18CEC7524CF`
- `docs/evidence/respected_orchestrator_github_issues.csv` -> `DA22AAA57DA1985B4EAD8C5A0D0A78C2BB361932E42CADF035F88618BF073560`
<!-- EVAL03_HASHES_END -->

`KANIT_LOG.md` kendi hash listesine dahil edilmez.

---

## UX-01 — Kanıt paketi görünüm şeması

- Durum: Tamamlandı.
- Kapsam: `interfaces/evidence_view.py`, imzalı engine kanıtı üzerinde salt-okunur ve redakte sunum modeli.
  `view(ctx, run_id)` yalnızca okur: schema_version, task_id, status, reason, patch_summary (SHA + değişen
  dosyalar), checks, reviewer, tester, usage, risks ve cost. Kanıt dosyalarına yazmaz, HMAC kaydını değiştirmez.
  Geçerli, eski (patch/proje değişmiş), başarısız ve kurcalanmış kanıt ayrı durum ve sebep üretir; ortam
  değişkenlerindeki secret değerler redakte edilir. Değer import anında değil `view()` çağrısında okunur.
- Doğrulama: `tests.interfaces.test_evidence_view` — geçerli/stale/failed/tampered ve env-secret senaryoları
  (`Ran 2 tests ... OK`; 6 görünüm durumu).
- Kalan risk: Hub görsel katmanı bu depoda değil; evidence'ta maliyet yoksa `cost=unknown` döner, sıfır üretilmez.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/interfaces/evidence_view.py` -> `A30C024E1722A6D385A56096023CCD4BB4005DB3FBAA771C2A52F60DFB28538C`
- `tests/interfaces/test_evidence_view.py` -> `E8113016330CD935B84E3613B494A8B829FECB33B4CB7CCD7540F78998BB00F8`
- `docs/evidence/poc/ux01_focused.log` -> `C04969C576A34C9B1FB5D7920FAAEA49DDC248063B5DEFB33FC91576F387323E`

---

## UX-02 — Hub ve CLI için salt okunur evidence API

- Durum: Tamamlandı.
- Kapsam: RPP `evidence.view` operasyonu ve CLI `evidence <run_id>` komutu aynı normalize görünümü üretir.
  `run-...` kimliği doğrulanır; traversal, olmayan görev, kilitli/kurcalanmış kanıt ve şema uyuşmazlığı
  yapılandırılmış hata döndürür. GET benzeri çağrı kanıt dosyalarını veya repo durumunu değiştirmez.
- Doğrulama: `tests.interfaces.test_evidence_api` — 5/5 vaka, RPP/CLI eşitliği ve kanıt hash'inin sabit kaldığı
  kontrolü (`Ran 24 tests ... OK` evidence_view/evidence_api/startup_cost birlikte).
- Kalan risk: Hub bu API'yi çağırmıyor; Hub kaldırıldığında CLI yolu tek başına çalışır.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/interfaces/rpp.py` -> `342D273F3E6793FDD3A8EA31CFE7817C86D9CD02A0737326A5AC4FCDD84AA891`
- `src/respected_orchestrator/__main__.py` -> `4455B23D9A934A86EDED7548A1957AC8630C3D76D84F1AE4CE90A33F6322371A`
- `tests/interfaces/test_evidence_api.py` -> `EE1996D0DF39831C05F88A5DDB4DBD21724B2092563457C5D6DB441211CDCEAE`
- `docs/evidence/poc/ux02_focused.log` -> `934D70DE616EEB83DD03F349DB811D15DE4B81747536547AB0D45E9D7E4579E2`

---

## UX-03 — Hub Decision Center ve gerçek insan onayı

- Durum: Tamamlandı (sözleşme ve terminal yolu; Hub UI kapsam dışı).
- Kapsam: İnsan onayı sınırını genişletmeyen sözleşme testleri. MCP/agent kendini onaylayamaz; onay yalnızca
  etkileşimli TTY üzerinden alınır. Onay patch SHA'sına, proje parmak izine ve onay anındaki git HEAD'ine bağlanır;
  replay, ekran drift'i, iptal, eski sonuç ve review sonrası değişen HEAD/çalışma ağacı reddedilir. `approve_maf_task`
  onay dosyasını yalnızca güncel proje durumu request ve result ile eşleşiyorsa yazar; yeni yetki yolu açılmadı.
- Doğrulama: `tests.interfaces.test_human_approval_contract` — 8/8 senaryo (`Ran 8 tests ... OK`);
  HEAD değişimi ve bayat proje parmak izi ayrıca reddedildi (`docs/evidence/poc/ux03_focused_final.log`).
  Geniş odaklı paket: `Ran 107 tests ... OK` (`docs/evidence/poc/remaining_tasks_focused_final.log`).
- Kalan risk: Hub Decision Center ekranı ayrı depoda; buradaki kanıt terminal `maf-approve` yolunun sözleşmesidir.
  Git deposu olmayan projede HEAD bağı kurulamaz.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/engine/runner.py` -> `48200B47CB1732F0EB1BCEDF06D416AAB448E7B6EB5D46F16423BA7E662F7BAD`
- `tests/interfaces/test_human_approval_contract.py` -> `79D5DD43857436FDE01397AA51580126F2AE2035C3256C662A6B8470346AB7F8`
- `docs/evidence/poc/ux03_focused_final.log` -> `BBA853145F4F00B7F8FDF23B0FF946295B531521E166B74884DBA7091665E269`
- `docs/evidence/poc/remaining_tasks_focused_final.log` -> `D9A1349F708E2273860CE596233453273251B6638B2F5834CEFA7935D6F2389F`


## COST-01 — Gemini/Cursor kullanımını gerçek CLI ile ölç

- Durum: Engelli — sağlayıcı CLI'ları bu makinede kurulu değil.
- Probe: `where.exe gemini` -> NOT_FOUND, `cursor` -> NOT_FOUND, `cursor-agent` -> NOT_FOUND,
  `opencode` -> `C:\Users\Furkan\AppData\Roaming\npm\opencode(.cmd)`.
- Karar: Kullanım/token verisi uydurulmadı; bilinmeyen değer `0` yazılmadı. Gemini/Cursor CLI'ları kurulup
  gerçek kullanım çıktısı alınana kadar görev engelli kalır; OpenCode tarafı ADP-01/COST-03 ile ölçülebilir.
- Doğrulama: `docs/evidence/poc/cost01_cli_probe.log`.
- Kalan risk: Sağlayıcı başına maliyet ve token sayısı bilinmiyor; raporlarda `unknown` olarak kalmalı.

- Güncelleme 2026-11-04: Gemini desteği kapsam dışı (kullanıcı kararı). Cursor CLI 2026.10.22-27dcf5f kuruldu ve
  Free planla gerçek ölçüm alındı: `auto` ×2 ve `grok-4.7-medium` ×1 başarılı; her birinde JSON
  `usage{inputTokens, outputTokens, cacheReadTokens, cacheWriteTokens}` geldi. `gpt-5-mini`, `gemini-3-flash`,
  `grok-4.7-low`, `cursor-grok-4.6-high` Free planda `ActionRequiredError` ile reddedildi (kullanım `unknown`, 0 yazılmadı).
- Bulgular: (1) `agent.cmd`/`cursor-agent.cmd` powershell zincirine gider, orchestrator `.cmd`'yi reddeder; resmî
  doğrudan yol `versions\<sürüm>\node.exe index.js`. (2) Çalışan `runner` cursor için `--output-format json`/`--trust`
  vermiyor ve `usage` ayrıştırmıyor. (3) `inputTokens`'ın önbelleği içerip içermediği çıktıdan kanıtlanamıyor.
- Durum: Tamamlandı (ölçüm + adaptör): `clis.cursor_entry` şimin yanındaki `versions\<sürüm>
ode.exe`+`index.js` girişini çözer, `.cmd` hiç çalıştırılmaz; `runner.command_for` `--trust --output-format json` verir; `tool_result("cursor")` `usage`'ı ayrıştırır, `cacheReadTokens` yoksa `unknown` (0 değil). Testler: `test_cursor_shim_resolves_to_its_own_node_entry...`, `test_usage_comes_from_each_tools_envelope...` — `tests.workflows.test_roles` + `tests.engine.test_runner` 73 test OK.
- Kalan risk: (a) `inputTokens`'ın önbelleği içerdiği varsayımı doğrulanmadı; (b) sandbox ağı kapalı ve Cursor oturumu kullanıcı profilinde olduğundan gerçek bir Cursor işçisi koşusu henüz yok (OpenCode'daki ADP-01/ADP-02 benzeri ayrı iş); (c) Free planda yalnızca `auto` ve Grok 4.7/4.6 çalışır.
- Doğrulama: `docs/evidence/poc/cost01_cursor_live.log`.
- Güncelleme 2026-11-04 (kalan risk a kapandı): aynı uzun istem `--model auto` ile 4 kez koşuldu
  (`poc/cursor_cache_probe.log`). 3. koşuda `inputTokens` 39 iken `cacheReadTokens` 18048 geldi; girdi önbelleği içerseydi
  önbellek okuması girdiyi aşamazdı. Sonuç: `inputTokens` önbellek okumasını **içermez**. Önceki varsayım (içerir) yanlıştı:
  ham girdiyi eksik sayıyor ve böyle bir koşuyu `unknown` yapıyordu. `runner.tool_result("cursor")` artık ham girdiyi
  `inputTokens + cacheWriteTokens + cacheReadTokens` alır, ağırlıklı toplam `inputTokens + 0.03·cacheRead + output`dır;
  `cacheReadTokens` yoksa hâlâ `unknown` (0 değil). Testler: `tests.workflows.test_roles` (canlı kaydedilen iki vaka), 75 test OK
  (`test_roles` + `test_runner`). Gemini kapsam dışı olduğundan canlı doğrulanmadı.

### Kanıt artefaktları (SHA-256)

- `docs/evidence/poc/cost01_cursor_live.log` -> `768A1099A62E77A6EE5C74FEFC683EE142BD4F95F8BC5083FD268368C5068DF3`
- `docs/evidence/poc/cost01_cli_probe.log` -> `BB8E5C20F27CD086EFE31802BDCE4AB1D677781408F618D379E3526AE73AA935`

---

## COST-03 — Risk ve başarım tabanlı auto_assign v2

- Durum: Tamamlandı.
- Kapsam: `workflows/roles.recommend` ölçülen track record ile adayları sıralar. Yetersiz geçmişte havuz sırası
  kullanılır ve bunun ölçülmüş öneri olmadığı gerekçede yazılır; eşit skorlar havuz sırasıyla deterministik;
  engelli profil sessizce kullanılmaz; write rolüne salt-okunur araç verilmez; kayıp modelde yalnızca açık
  fallback; eşit kayıtta pahalı aday kaybeder; açık kullanıcı ataması ezilmez.
- Doğrulama: `tests.workflows.test_auto_assign_v2` + `test_roles` + `test_track_record` — 31 test OK
  (`docs/evidence/poc/cost03_focused_final.log`).
- Kalan risk: Geçmiş yalnızca runs/ok/tokens/seconds taşır; model kalitesi ve görev zorluğu ayrı ölçülmez.

### Kanıt artefaktları (SHA-256)

- `tests/workflows/test_auto_assign_v2.py` -> `5B6BA3449746A69B29E1CCEB7C3F3CC67D23939E947A8F44891CBED3D28E4C38`
- `src/respected_orchestrator/workflows/roles.py` -> `4AD4F1718251ED4937E2EDA18DA0894902B61878867E517C13EDA4F4B84BC5C9`
- `docs/evidence/poc/cost03_focused_final.log` -> `8190CBF12E8378C9ED084FA6C9A5F5745435BFD625C747E12E129BB30EF15652`


## GH-01 — GitHub Issue salt okunur içe aktar

- Durum: Tamamlandı (adaptör + RPP/CLI).
- Kapsam: `interfaces/github_connector.import_issue`, `gh issue view` ile tek issue okur; başlık/gövde
  güvenilmeyen plan girdisidir, izin listesi dışındaki etiketler atılır. Kaynak repo/issue/revision/url kayda
  geçer. Issue metninden worker başlatılmaz; GitHub yazma isteği yoktur. 404, kısıtlı repo, iptal ve rate-limit
  hata olarak döner; repo/issue biçimi `gh` çağrısından önce doğrulanır. RPP `github.issue_import` ve CLI
  `github-import-issue` aynı sözleşmeyi kullanır.
- Doğrulama: `tests.interfaces.test_github_connector` + `test_github_rpp`; geniş odaklı paket 107/107 OK.
  Canlı read-only kontrol: `gh 2.102.0`, hesap `respected0`, `gh issue view 1 --repo cli/cli` gerçek JSON;
  hiçbir push/PR/yorum çalıştırılmadı (`docs/evidence/poc/gh_live_readonly.log`).
- Kalan risk: Issue gövdesi prompt enjeksiyonu taşıyabilir; otomatik worker başlatma bilinçli olarak yoktur.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/interfaces/github_connector.py` -> `35C1ED0DE2F050CF4F484DA2649B7026AF4E7D644FCB081C190DFB286B1CB330`
- `src/respected_orchestrator/interfaces/rpp.py` -> `342D273F3E6793FDD3A8EA31CFE7817C86D9CD02A0737326A5AC4FCDD84AA891`
- `src/respected_orchestrator/__main__.py` -> `4455B23D9A934A86EDED7548A1957AC8630C3D76D84F1AE4CE90A33F6322371A`
- `tests/interfaces/test_github_connector.py` -> `1193A3A0FC5980BB949322E212954E5FAF1480132123455C621266A41AD3D91F`
- `tests/interfaces/test_github_rpp.py` -> `51AC743BFB3216DA90C2DCAA3EFC9DE28BBE2183E091523E166618064846134C`
- `docs/evidence/poc/gh_live_readonly.log` -> `113EF393948797893C1832C280BEC17BFAC142A70F099F90F75AFFE05987603C`
- `docs/evidence/poc/remaining_tasks_focused_final.log` -> `D9A1349F708E2273860CE596233453273251B6638B2F5834CEFA7935D6F2389F`


## GH-02 — Doğrulanmış patch'ten taslak PR aç

- Durum: Tamamlandı (adaptör + RPP/CLI; push açık onay ister).
- Kapsam: `plan_draft_pr` yalnızca imzalı `completed`, secret içermeyen ve doğrulaması geçmiş sonuçtan plan üretir;
  `create_draft_pr` RPP `github.pr_create` ile açık `operation_id`, `confirm: true` ve operatörün verdiği
  `project_root` olmadan çalışmaz. Branch push yalnızca bu açık çağrıda yapılır; merge komutu üretilmez.
  CLI yüzeyi `github-pr-plan` ve `github-pr-create` aynı RPP sözleşmesini kullanır.
- Doğrulama: `test_github_connector` + `test_github_rpp`; 107/107 odaklı paket OK. Eksik onay, yanlış run,
  başarısız/secret'lı sonuç ve operation_id sınırları reddedilir.
- Kalan risk: Gerçek uzak PR açma yazma yetkisi verilmediği için canlı uçta denenmedi; plan/oluşturma sınırı
  test ve kod düzeyinde kanıtlandı. Otomatik merge yoktur.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/interfaces/github_connector.py` -> `35C1ED0DE2F050CF4F484DA2649B7026AF4E7D644FCB081C190DFB286B1CB330`
- `src/respected_orchestrator/interfaces/rpp.py` -> `342D273F3E6793FDD3A8EA31CFE7817C86D9CD02A0737326A5AC4FCDD84AA891`
- `src/respected_orchestrator/__main__.py` -> `4455B23D9A934A86EDED7548A1957AC8630C3D76D84F1AE4CE90A33F6322371A`
- `tests/interfaces/test_github_rpp.py` -> `51AC743BFB3216DA90C2DCAA3EFC9DE28BBE2183E091523E166618064846134C`
- `docs/evidence/poc/remaining_tasks_focused_final.log` -> `D9A1349F708E2273860CE596233453273251B6638B2F5834CEFA7935D6F2389F`


## GH-03 — CI/review geri bildirimini sınırlı düzeltmeye bağla

- Durum: Tamamlandı (adaptör + RPP/CLI).
- Kapsam: `plan_ci_fix` CI/review geri bildirimini sınırlı düzeltme planına çevirir; round bütçesi aşılırsa,
  SHA eskiyse, reviewer yetkisizse veya insan onayı yoksa düzeltme üretmez. Sınırsız retry yok; gerekçe kanıt
  paketine yazılabilir biçimde döner. PR'a yorum/merge yazılmaz. RPP `github.ci_plan` ve CLI `github-ci-plan`
  yüzeyi eklendi; `max_rounds`/`used_rounds` negatif veya bool olamaz.
- Doğrulama: `test_github_connector` sınırlı senaryoları + `test_github_rpp`; 107/107 odaklı paket OK.
- Kalan risk: Canlı CI webhook'una bağlanmadı; geri bildirim çağıran tarafından sağlanır. Bu teslimde GitHub
  yazma işlemi yapılmadı.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/interfaces/github_connector.py` -> `35C1ED0DE2F050CF4F484DA2649B7026AF4E7D644FCB081C190DFB286B1CB330`
- `src/respected_orchestrator/interfaces/rpp.py` -> `342D273F3E6793FDD3A8EA31CFE7817C86D9CD02A0737326A5AC4FCDD84AA891`
- `tests/interfaces/test_github_rpp.py` -> `51AC743BFB3216DA90C2DCAA3EFC9DE28BBE2183E091523E166618064846134C`
- `docs/evidence/poc/remaining_tasks_focused_final.log` -> `D9A1349F708E2273860CE596233453273251B6638B2F5834CEFA7935D6F2389F`


## EXT-02 — Serena/context MCP için read-only deneme adaptörleri

- Durum: Tamamlandı (adaptör + gerçek stdio MCP istemcisi); Serena/context sunucusu bu makinede kurulu değil.
- Kapsam: `interfaces/mcp_client.StdioMcpClient` gerçek alt süreçle JSON-RPC `initialize`, `tools/list`,
  `tools/call` ve kontrollü kapanış yapar; yanıt kimliği, protokol biçimi, zaman aşımı ve maksimum bayt sınırı
  fail-closed'dır. Alt süreç `winproc.popen` ile gizli pencerede başlatılır. `readonly_probe.query_repo`, EXT-01
  yetenek manifestosu arkasında yalnızca `mcp.serena`/`mcp.context` araçlarını `read` izniyle çalıştırır; sağlayıcı
  yoksa `PROVIDER_MISSING`, araç onaysız veya yazma izinliyse hata verir. Mutlak yol, sürücü harfi, UNC ve `..`
  kaçışları reddedilir; çıktı 20.000 karakterle sınırlanır ve secret redaksiyonu uygulanır.
- Doğrulama: `tests.interfaces.test_mcp_client` + `test_readonly_probe` + `test_capability_manifest`;
  `ext02_mcp_focused.log` 14/14 OK, geniş paket 107/107 OK. Sağlayıcı probe: `serena`, `serena-mcp-server`,
  `uvx` MISSING; `npx`/`codex` var. Gerçek sunucu yokken sahte başarı yazılmadı
  (`docs/evidence/poc/ext02_provider_probe.log`).
- Güncelleme 2026-11-04: Serena bağımlılığı kaldırıldı (`mcp.serena` izin listesinden çıktı; yalnızca `mcp.context`).
  `query_via_stdio` yeni `build_args` ile sunucunun kendi parametre adını kullanır. Canlı doğrulama bu makinedeki
  context-mode MCP sunucusuyla: `initialize` + 11 araç listelendi; boş bilgi tabanında `ctx_search` `isError`
  döndü ve probe fail-closed `PROVIDER_FAILED` verdi; test-içi `ctx_index` ile tohumlanınca salt-okunur `ctx_search`
  başarılı, `untrusted=True`. `CONTEXT_MODE_SERVER=<start.mjs>` ile açılan test: 15/15 OK
  (`docs/evidence/poc/ext02_context_mode_live.log`).
- Kalan risk: yok bilinen; canlı test yalnızca `CONTEXT_MODE_SERVER` verilince koşar (testler HOME'u bilerek izole eder).

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/interfaces/readonly_probe.py` -> `E2E289C788C423B22957EC774B752BDB5F38E595BC58C7EDF7BA40DBF0F0C0D1`
- `src/respected_orchestrator/interfaces/mcp_client.py` -> `E7C6B21011EBF6B3CF100CD3A4029398F19539663B156969C37345882E7FA846`
- `tests/interfaces/test_mcp_client.py` -> `3231BC8D6E04300EC9BC4F6DF5AA9376590B46894E4F970C645BA3DC9C62107E`
- `docs/evidence/poc/ext02_context_mode_live.log` -> `658ADEC4DCEAAC3D50DCFF0A703FF85DE52EEA92BEA686BFB67107AEE2C98251`
- `docs/evidence/poc/ext02_mcp_focused.log` -> `DFBCC912CEC7948C0099890D47719E250C6BA477F635A4502FACD3FD0C03C616`
- `docs/evidence/poc/ext02_provider_probe.log` -> `3AD8FCA85E2168C9DE83C154502D0B6D8D0D02BE0393F88BAD8F8D417923DF57`
- `docs/evidence/poc/remaining_tasks_focused_final.log` -> `D9A1349F708E2273860CE596233453273251B6638B2F5834CEFA7935D6F2389F`


## REL-01 — Authenticode imzalı Windows kurucu hattı

- Durum: Tamamlandı (gerçek imza hattı; üretim güvenilir sertifikası yok).
- Kapsam: `release_signature.verify` yalnızca geçerli Authenticode durumunda `signed=True` döner; eksik dosya,
  beklenen SHA uyuşmazlığı (tampered), desteklenmeyen platform, çevrimdışı/bilinmeyen durum, geçersiz imza,
  yanlış imzalayan ve süresi dolmuş sertifika reddedilir. `sign` modern `signtool sign /fd SHA256 /f <pfx>`
  biçimini kullanır; sertifika yalnızca operatör girdisinden gelir. `build_installer.py --sign-cert` ve
  `--require-signed` imzasız artefaktı başarı saymaz.
- Doğrulama: `tests.packaging.test_release_signature` — 7/7 OK (`rel01_signature_tests.log`).
  Gerçek koşu: repo dışındaki self-signed test sertifikası (`CN=Respected Test Signer`, thumbprint
  `C888E6DEEDD43B89C5B211953AEEB316005DAD42`, NotAfter `2026-12-03`) ile kurucu imzalandı;
  `signed=true`, SHA-256 `BE996EBB...A4F29D`. Tampered (`68C0C7...AB`) ve yanlış imzalayan
  (`wrong_signer`) reddedildi. Loglar: `rel01_real_build.log`, `rel01_real_verify.log`,
  `rel01_real_tamper.log`, `rel01_real_wrong_signer.log`.
- Kalan risk: Test sertifikası güvenilir dağıtım sertifikası değildir; zaman damgası ve üretim imzalı yayın
  artefaktı yoktur. "Üretim imzalı" iddia edilmez; sertifika temini operasyonel bağımlılıktır.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/release_signature.py` -> `0E2E8D23D5A20FD749C07392701E01229EA2D51F1EFD9163500928041F350B8D`
- `packaging/build_installer.py` -> `4E973860CABD9DEB876B40C302D03AE1D7DAE19555CDA65D1BB771F6EE0A30DF`
- `tests/packaging/test_release_signature.py` -> `DE980B94230C7C85FBBFFB905019656DE4F884EDB643907896B73509A38E525D`
- `docs/evidence/poc/rel01_real_build.log` -> `FFD1545EC1F75137D97ED0E6386F3A670867A9D85EC6FE3596C5007D20B50D44`
- `docs/evidence/poc/rel01_real_verify.log` -> `AFDCC14366B5A93787242E92640A59918D2145281160E86E41B64B63313379A3`
- `docs/evidence/poc/rel01_real_tamper.log` -> `89C27A6C01B71FC764D9A5A119260A7A486F86C39B9BB871BC62AAE91863A951`
- `docs/evidence/poc/rel01_real_wrong_signer.log` -> `22A106DD4EEC79F96F8D2323BA010DD9B7B273B9D3647D1EF016FF51AB934785`
- `docs/evidence/poc/rel01_signature_tests.log` -> `BDE96833580F5476E44D42613369CB652F0B31401B450885997AF52458910920`


## REL-03 — İlk göreve giden kurulum rehberi ve health

- Durum: Tamamlandı.
- Kapsam: `interfaces/health_wizard.guide(checks, data_root)` rpp `health` yanıtına `wizard` alanı ekler:
  sonraki adım, salt-okunur örnek görev ve platform ipucu. Örnek görev yalnızca okuma yapar; Hub yokken core
  çalışır; kaldırma veriyi purge edilmedikçe korur.
- Doğrulama: `test_health_wizard + test_rpp + startup_cost` — 28 test OK (`rel03_focused.log`).
  Gerçek CLI: `py -m respected_orchestrator health` → `status=healthy`, `hub_required=false`,
  `worker_cli` içinde `opencode`, salt-okunur `sample_task` (`docs/evidence/poc/rel03_real_health.log`).
  Geniş odaklı paket 107/107 OK.
- Kalan risk: Rehber metinseldir; otomatik onarım/onboarding yapmaz. Sağlıklı kurulumda `steps` boş kalır.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/interfaces/health_wizard.py` -> `4D90FF2CF21C374EAB19A329B95E827C2D5A62C84CA3795E991A65EE5BB30A7C`
- `src/respected_orchestrator/interfaces/rpp.py` -> `342D273F3E6793FDD3A8EA31CFE7817C86D9CD02A0737326A5AC4FCDD84AA891`
- `tests/interfaces/test_health_wizard.py` -> `9700E059804B784D0E72CF3EFC4A5CF542236410D2CF68D4A919B1C557918CCF`
- `docs/evidence/poc/rel03_real_health.log` -> `190404542E536DF12BFE83BEF73DB7F3AD70A76AC7B85D406356763D2761E6EE`
- `docs/evidence/poc/rel03_focused.log` -> `D10019731E4C005A5037A3BCA2D96B4019840CB56DCBE430BF124DAAC3DB3C9F`
- `docs/evidence/poc/remaining_tasks_focused_final.log` -> `D9A1349F708E2273860CE596233453273251B6638B2F5834CEFA7935D6F2389F`


## REL-04 — macOS/Linux güvenlik eşdeğerliği ve platform kapısı

- Durum: Tamamlandı (karar kapısı); POSIX GA değil.
- Kapsam: `release_platform.decide` yalnızca Windows'u GA sayar ve 10 güvenlik fixture'ının tamamı `pass`
  değilse `no-go` döner. Fixture matrisi gerçek testleri çalıştırır; Windows-only bağımlılık veya skip
  `blocked` sayılır, asla `pass` değil. macOS/Linux tüm fixture'lar geçse bile "platform parity not proven"
  gerekçesiyle `no-go` kalır. Karar `docs/ADR-REL04-platform-parity.md` içinde.
- Doğrulama: `tests.packaging.test_release_platform` — 6 test OK. Gerçek matris:
  Windows 10/10 `pass`, `release=go` (`rel04_fixture_windows.log`);
  Linux WSL Python 3.14.4: `migration`, `installer_rollback`, `mcp_recursion` pass, 7 fixture `msvcrt`
  yokluğundan `blocked`, `release=no-go` (`rel04_fixture_linux.log`);
  macOS bu makinede yok, fixture koşulmadı, `release=no-go` (`rel04_fixture_macos.log`).
  MCP spawn gizli pencere düzeltmesi sonrası odaklı paket 19/19 OK (`rel04_mcp_spawn_focused.log`); geniş paket 107/107.
- Kalan risk: POSIX'te gerçek sandbox/izin eşdeğerliği kanıtlanmadı; `blocked` pass sayılmaz. macOS fiziksel
  olarak koşulmadı. GA yalnızca Windows'tur.

### Kanıt artefaktları (SHA-256)

- `src/respected_orchestrator/release_platform.py` -> `B50167A8CB86A1A40DA4A0F8E02235CCE6F6E9A468C091E344293FF918B3FDF8`
- `tests/packaging/test_release_platform.py` -> `42E7918C294A38FF1CFC385929C91B74D3C2F041A41F5C51113E2D9DFA7ADDAF`
- `docs/ADR-REL04-platform-parity.md` -> `56A29A646A53E22B7D1F5CEEC746046C08E9C4EDC007F18870565E36440F4034`
- `docs/evidence/poc/rel04_fixture_matrix.py` -> `1FC935A2DAFC8926F04B13FA62A2EDE4920DF0331EB015D8DF46909E260BE7AB`
- `docs/evidence/poc/rel04_fixture_windows.log` -> `AFC206685AF559EF857ADA4DD52D033620B97CFC96942FA36D48EAB1E006C523`
- `docs/evidence/poc/rel04_fixture_linux.log` -> `D3EC4B86A62A3E0B1AFC74491B55298A7BDD9D6DB42D4A7C7856D0D3A821A1B2`
- `docs/evidence/poc/rel04_fixture_macos.log` -> `FAE2C5A300B4D42206B0BBB5B6D71ADC16F3F5F39820EC89EFB2E94D66FD1622`
- `docs/evidence/poc/rel04_mcp_spawn_focused.log` -> `F049E82C91CA5BB084847EE4DDB3A81AFBE660DD267161406B6104C69E2FBB0C`


### Kapanış hash düzeltmesi (ADP-01 sonrası son doğrulama)

Yukarıdaki kronolojik kayıtlarda aynı dosya birden çok kez farklı hash ile görünür; bunlar görev kapandıktan sonra yapılan senkron düzenlemelerin tarihsel izleridir. Aşağıdaki değerler ADP-01 kapanışı sonrası çalışma ağacının geçerli SHA-256 değerleridir ve doğrulamada bunlar esas alınır:

- `src/respected_orchestrator/engine/appcontainer.py` → `30B8084D552518CC727DA4C8685C84EA0E0A749947159A2A30D287F9D069C568`
- `src/respected_orchestrator/engine/processes.py` → `FC674E411841B6629CD8F8D711B5E0C40336B46BCCE369AC153778D0714BC011`
- `src/respected_orchestrator/engine/runner.py` → `C3B522CDA97ABAD7552A9E28E28A71FF9376FC4DBB03806E4D6CB3A1C8F216A0`
- `src/respected_orchestrator/workflows/maf_workflow.py` → `5F240A0077F409EAECD6EC54EC2B59EFE5C3556919BC11363EE9FE2BC65F6340`
- `tests/engine/test_worker_policy.py` → `E527F77513D934D995F97854C9E39A4CA54A90761CDDE0FDCCE2F0BEF7D07378`
- `tests/workflows/test_campaign.py` → `4224292F0DC67974F55DD3508A6F1636C7BCAE78358153594A00487EADDAFF5D`
- `tests/workflows/test_reviewer_reliability.py` → `33D85C370FD724B60BD0A457D6AE0597C039E9B42E5F071D2034480424360D48`
- `docs/ARCHITECTURE.md` → `A3C76C2B92FDC3B765B3FE65D510637E8CB9CD34C728092723B6C2165659841B`
## FIX-01 / FIX-04 / FIX-02 / FIX-03 — beta.2 öncesi ölçümler (ön çalışma, 5 Kasım 2026)

- Durum: **Görevler açık.** Bu girdi yalnızca ölçüm ve karar kaydıdır; hiçbir FIX tamamlanmadı, hiçbir güvenlik açığı
  kapatılmadı. Tamamlanma girdileri FIX-01..FIX-04 için ayrıca yazılacaktır.
- Kapsam: beta.2 öncesi dört düzeltmenin dayandığı varsayımların gerçek ortamda ölçülmesi. Kararlar ADR-017..020.
- Ortam: yerel Windows 11 (10.0.26300), yükseltilmemiş oturum, Python 3.13.15, git 2.55.0; hosted: GitHub Actions
  `windows-latest` (Windows Server 2025, 10.0.26100), runner git 2.56.0. Hosted ölçümler public depoda geçici
  `probe/fix01-elevation` ve `probe/fix01-followup` dallarında yapıldı; dallar ölçümden sonra silindi, `main` değişmedi,
  Actions public depoda ücretsizdir.
- Doğrulama komutları:

```text
python docs/evidence/poc/fix01_deelevate_probe.py info
python docs/evidence/poc/fix01_deelevate_probe.py run -- python -m unittest tests.engine.test_worker_security tests.engine.test_worker_policy.RealSandboxTests
python docs/evidence/poc/fix04_verify_appcontainer_probe.py docs/evidence/poc/fix04_results.json
python docs/evidence/poc/fix04_toolchain_probe.py docs/evidence/poc/fix04_toolchain_results.json
```

### Bulgular (gerçek çıktı özeti)

- Hosted runner belirteci yükseltilmiş: `token_elevation=1`, integrity High, Administrators etkin
  (`fix01_hosted_probe.log`). Administrators'ı deny-only yapıp integrity'yi Medium'a düşüren kısıtlı çocuk
  belirteçte `token_elevation` **hâlâ 1**; motor `unsupported_elevated` verir, 13 testte 12 ERROR. Bu yol çalışmaz.
- Runner'ın oluşturduğu geçici standart yerel kullanıcı altında `token_elevation=0`, `_is_elevated()=False`;
  AppContainer matrisi (`test_worker_security` + `RealSandboxTests`) 13 test: 12 geçti, 1 skip (Cursor CLI yok), 0 hata.
  Yetki yalnızca çalışma alanı + Python dizinine verilince 16 sn; tüm `hostedtoolcache` ağacına verilince ~10 dk
  (`fix01_hosted_followup.log`).
- Verify, AppContainer'da ağ kapalı: dış IP, DNS, loopback ve alt süreç çıkışı engellendi; Python, unittest, node,
  cmd çalıştı (`fix04_results.json`). `npm.cmd` shim politikasıyla reddedildi; `node npm-cli.js test` sürücü kökü
  `lstat` EPERM ile çalışmadı; sys.prefix dışındaki venv yalnızca kökü salt-okunur verilince çalıştı;
  `default_policy` `Program Files` altındaki `command[0]` dizini için ACL denemesi yapıp `SandboxStartError` verdi
  (`fix04_toolchain_results.json`).
- Hosted'da AppContainer içindeki `git` `rc=128`: `could not open '/dev/null'` (yerelde çalışıyor; sebep git sürümü mü
  görüntü mü ayrıştırılmadı).
- Claude Code CLI 2.1.318 `--output-format json` makine okunur; güvenilir sayılar `modelUsage` altında, üst düzey
  `usage` sıfırdı; `total_cost_usd` liste fiyatı tahmini; çağrının kotadan mı ücretli krediden mi düştüğü anlaşılamadı.
  Tek çağrı, kullanıcı onaylıydı.

### Kalan risk / ölçülmeyenler

- Hosted ölçüm tek runner görüntüsünde yapıldı; görüntü değişirse sonuç değişebilir.
- AppContainer'da Python/node/cmd dışındaki araç zincirleri ölçülmedi.
- `git` farkının nedeni ayrıştırılmadı.
- Hub tarafı (FIX-03C), gerçek PR (FIX-03A), webhook/yoklama (FIX-03B) ve gerçek ajan benchmark'ı (FIX-02) için
  hiçbir koşu yapılmadı.

### Kanıt artefaktları (SHA-256)

- `docs/evidence/poc/fix01_deelevate_probe.py` -> `83993761BE250171E680BE8ACC5F61549FE45F778676C6785EBD828CEC918478`
- `docs/evidence/poc/fix01_hosted_probe.log` -> `1916DEBE198FF5D046EB5B88429610B6E5E74B102E9B6146C2C833A4DCEFD826`
- `docs/evidence/poc/fix01_hosted_followup.log` -> `24E2B7BDA11DE0DD364CA95032218216A0AE6B8735CBBE04F3EFB7AEE29F1605`
- `docs/evidence/poc/fix04_verify_appcontainer_probe.py` -> `99B028401C1568C9C7F53A59C4457ABA64FC43E0FA1F9A95DC0905AB614265A4`
- `docs/evidence/poc/fix04_results.json` -> `CA62AEF215B479F81219D58B5D28CE45EA34E1AEA80DC262E674ED6423B010F0`
- `docs/evidence/poc/fix04_toolchain_probe.py` -> `9D9B52421ABCA84E67868B874458E4952BAB06F7D20829CD102AE341096D8072`
- `docs/evidence/poc/fix04_toolchain_results.json` -> `C40F0BD3D1F6797D4E9F8ABDF2C4BB75BE5A3596C1B399FC276BD3E694C0AA5E`

---

## FIX-01 / FIX-04 / FIX-02 / FIX-03 — uygulama (5 Kasım 2026)

- Durum: **Kod ve yerel testler tamam; dört görevin dış girdi isteyen kısmı açık** (ROADMAP "Durum" tablosu). Hiçbir release
  kapısı kutusu bu girdiyle işaretlenmedi: kapı tek bir yayın SHA'sı için kanıt ister.
- Kapsam: FIX-01 (güvenlik koşusu: sıfır skip, manifest, kapı, geçici standart kullanıcı betiği), FIX-04 (verify/kabul AppContainer'da,
  ağ kapalı, fail-closed, S-24), FIX-02 (gerçek ajan yürütücüsü, sızıntı denetimi, plan, kapı), FIX-03A/B (PR geri okuma, CI içe
  aktarma/yoklama), FIX-03C (Hub `evidence`).
- Ortam: yerel Windows 11, yükseltilmemiş oturum, Python 3.13.15, git 2.55.0, node/cargo yerel.
- Doğrulama komutları:

```text
python tests/tools/run_ci.py
python tests/tools/run_security_ci.py run %TEMP%\m.json ; python tests/tools/run_security_ci.py verify %TEMP%\m.json
python -m unittest tests.evals.test_bench tests.interfaces.test_github_ci_ingest tests.interfaces.test_github_connector
python -m tests.evals.bench plan docs/evidence/poc/fix02_plan.json
python docs/evidence/poc/fix04_toolchain2_probe.py
(respected-hub) npm run check ; cargo test --test campaign_e2e
```

- Gerçek çıktı (özet):

```text
Ran 658 tests in 1059.977s | OK (skipped=1) [skip = Cursor CLI yok, ADR-017 ile güvenlik kümesi dışında]
--- güvenlik koşusu ---
Ran 28 tests in 98.389s | OK | security run: OK | security gate: OK (manifest: failed=0 errors=0 skipped=0 elevated=false)
--- Hub ---
npm run check: tsc temiz; node --test 131 pass / 1 fail (tests/shell/installFacts.test.ts 'orchestrator installer notice', degisiklikten ONCE de basarisiz: 126 pass / 1 fail); cargo test --test campaign_e2e invalid_campaign_identity: ok
```

- Kabul kriteri karşılandı mı:
  - FIX-04: **evet (yerel)**. Aynı betik sandbox'sız bağlanır (kontrol), AppContainer'da IP/DNS/loopback/alt süreç reddedilir;
    anahtar ve veri kökü erişilemez; AppContainer kurulamazsa, `.cmd` shim'inde ve Windows dışında `SandboxError`;
    `RESPECTED_ORCH_SANDBOX=off` yok sayılır; ağ istisnası yalnızca listedeki görevde `allow`; kanıtta `network` alanı.
  - FIX-03C: **evet**. Gerçek `evidence` çıktısı (`fix03c_real_evidence_view.json`) Hub modelinden geçirildi; stale/failed/tampered ve
    bilinmeyen şema onaya hazır görünmez; sızıntı ve onay-yok testleri; Rust izin listesi testi.
  - FIX-01: **kısmen**. Manifest/kapı yerelde (25 test, 0 skip) ve sahte manifestlerle kırmızı; `ci.yml` değişti. **Hosted GitHub koşusu
    yapılmadı**; geçici kullanıcı betiği hosted'da denenmedi.
  - FIX-02: **kısmen**. Stub ajanla iki kol uçtan uca, sızıntı geçersiz kılar, kota durdurur, bilinmeyen `unknown`. **Gerçek ajanla
    60 koşu yapılmadı** (ücretsiz ajan doğrulaması ve parti onayı gerekir).
  - FIX-03A/B: **kısmen**. Kod ve mock'lu `gh` ile testler; **gerçek taslak PR ve gerçek check-run yok** (test deposu + token gerekir).
- Kalan risk / shortcut: hosted `git` farkı ve runner görüntüsü kayması ölçülmedi; merge koruması/etiket kapısı repo ayarı;
  `pytest/ruff/mypy/gcc/go/tsc` bu makinede kurulu olmadığından ölçülemedi; `RESPECTED_VERIFY_NETWORK_TASKS` operatör
  anahtarıdır (görev başına insan onayı kanıtı yoktur, yalnızca operatörün adını yazması); webhook gövdesi dize olarak gelirse
  imza UTF-8 yeniden kodlamasıyla doğrulanır.

### Artefakt SHA-256

- `tests/tools/run_security_ci.py` -> `6FF4A3BDD5CB868367952F5B00B9F421FAEFBF40F33CF728B0D74F1C1B80A8E3`
- `tests/tools/run_security_as_user.ps1` -> `BDBE7969AC13B42AA1F245A8CF8CDD3294D3136A26A00269A5C1BC3020246C8F`
- `.github/workflows/ci.yml` -> `25A0DA1DD48FE7D4370B02298AD97FD26AD043934E59B1B3387A134683615696`
- `src/respected_orchestrator/engine/sandbox.py` -> `12FB768E77C9377B6D266579B89BD0FA27091213CB66794C46B56FED7EC9F968`
- `tests/engine/test_sandbox.py` -> `631D83EEC986AAA6DF231DBA54A042493F8E3CCFFE8DB69F6AEE26D556901201`
- `tests/evals/bench.py` -> `24A2D4C91D1DAAAB0011C520C3C36C0015CD78A020E08142BFD21B79A042CAB8`
- `tests/evals/test_bench.py` -> `954B0796894609844E5EE56D1D6E70E90F84F5865181C6B69829F55855BA1965`
- `docs/evidence/poc/fix02_plan.json` -> `C1C40C472B8776F305A65D38E637AB56FE402295B6896AB5D2E95C1076ACF75F`
- `docs/evidence/poc/fix04_toolchain2_results.json` -> `FB133A884E0048BD59B82C8CA9F50BD7F12CD53567FCA45FEE60573F80B209A2`
- `docs/evidence/poc/fix03c_real_evidence_view.json` -> `378E74418F2501090A1C82ECF29BD1B63DF52C39CD22EC7B659C578E2F5D99B4`
- `src/respected_orchestrator/interfaces/github_connector.py` -> `1062EA7BB069E3AE1D6397062D1475151414542E7F1162DA6214971576C8CCD1`
- `tests/interfaces/test_github_ci_ingest.py` -> `DD838C1B3DCAE614A0C89404568D6BC6F1B0075DF81F90AA6018B4CFDD65EB9C`

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

## CUR-01 — Cursor çalışanı AppContainer kum havuzunda

- Durum: TAMAM (2026-11-04). Gerçek Cursor işçisi (`--model auto`, Free plan) AppContainer içinde bir yazma görevini tamamladı; kök neden kanıtlandı ve giderildi.
- Kapsam: `runner.get_cli_command` ve çalışan politikası, yeni `resources/node-shim/appcontainer-pipes.js`, testler, ARCHITECTURE/THREAT_MODEL (ağ anahtarı, izole HOME ve `engine/cursor_auth.py` önceki oturumdan).
- Kök neden (kanıt: `poc/cursor01_pipe_rootcause.log`): AppContainer jetonu adlandırılmış boruyu yalnız `\\.\pipe\LOCAL\` altında oluşturabilir (`CreateNamedPipeW` diğer adlarda `ERROR_ACCESS_DENIED`). Node/libuv `child_process` borularını `\\?\pipe\uv\*` adıyla kurar, `ACCESS_DENIED`'ı ad çakışması sayıp sonsuza dek yeniden dener; `uv_spawn` hiç dönmez. `stdio:'inherit'/'ignore'` çalışır, `'pipe'` (execFile, spawn, spawnSync) asılır; job object ve handle devralma etkisizdir (job'sız aynı sonuç). Önceki oturumun "git asılıyor" belirtisi bu nedenin sonucuydu; `.running` EPERM notu yeni koşuda engel olmadı.
- Düzeltme (en küçük): Cursor komutuna `--require <resources/node-shim/appcontainer-pipes.js>` eklendi (`runner.NODE_PIPE_SHIM`); yalnız bu dizin Cursor çalışanına salt-okunur verilir. Shim: `child_process` borularını `LOCAL\` altında kurar, `spawnSync/execSync` çıktısını `RESPECTED_WORKER_TMP` içindeki geçici dosyalardan alır, IPC (`fork`) kanalını `EACCES` ile reddeder, JS `fs.realpath` yerine `native` olanı kullanır (JS sürümü `C:\` üzerinde lstat EPERM verir; yalnız boru shim'iyle yapılan ilk canlı koşuda Cursor'un yazma aracı "kanonik yol doğrulaması" ile reddedildi → `test_failed`; realpath yaması sonrası düzeldi).
- Çıktı / değişen dosyalar: `src/respected_orchestrator/engine/runner.py`, `src/respected_orchestrator/resources/node-shim/appcontainer-pipes.js` (yeni), `tests/engine/test_worker_policy.py` (+1 gerçek AppContainer testi), `tests/engine/test_runner.py`, `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, `docs/evidence/poc/cursor01_{pipe_rootcause,fixed_write}.log`, `cursor01_write_only.py`.
- Doğrulama komutu: `python docs\evidence\poc\cursor01_write_only.py <çıktı.log>` (canlı, Cursor Free); `python -m unittest tests.engine.test_worker_policy tests.engine.test_runner`; `python -m unittest discover -s tests -t .`.
- Gerçek çıktı: canlı koşu `status=completed`, `changed_files=[owned.txt]`, kabul komutu returncode 0, `check` → `verified`, süre 44,5 sn, izole HOME silindi, token sızıntı taraması (`scan_for_secrets`) hata vermedi. Yeni test (`test_node_worker_can_start_piped_children_and_resolve_paths`) AppContainer içinde Cursor'un node'uyla `spawnSync`, `execFileSync(input)`, `spawn(stdin→stdout)` ve `realpathSync` çağırır; shim yoksa asılır (zaman aşımı).
- Yasak erişim yeniden doğrulaması (shim sonrası, 2026-11-04): (a) `deny` senaryosu (`RESPECTED_CURSOR_NETWORK` yok) artık zaman aşımı yerine hızlıca fail-closed: `status=failed`, `reason=worker_failed`, `provider_status=AUTH_REQUIRED`, stderr "Authentication required"; auth.json kopyalanmadı, ağ açılmadı, izole HOME silindi (`poc/cursor01_deny.log`; eski kayıt `timed_out` idi). (b) `poc/cursor01_deny_probe.py` Cursor'un node'u + shim ile AppContainer içinde (ağ kapalı politika) çalışır: dışarıdaki dosyayı okuma/yazma/üzerine yazma, `.engine-key` okuma, veri kökü listeleme, kullanıcının `%APPDATA%\Cursoruth.json` okuması hepsi `EPERM`; shim'in başlattığı alt süreç dışarıdaki dosyayı okuyamadı (`status=1`); dışa TCP bağlantısı `EACCES`; kendi çalışma alanına yazma OK (`poc/cursor01_deny_probe.log`). Sızıntı yok, gevşetme gerekmedi. Not: probe'daki `PROBE_*` ad seçimi, `scrub_environment` "KEY/AUTH" adlı değişkenleri sildiği için ilk koşuda iki satırı `ERR_INVALID_ARG_TYPE` yaptı; adlar düzeltilip yeniden koşuldu.
- Kabul kriteri karşılandı mı (kanıtla): EVET — `poc/cursor01_fixed_write.log` (`status: completed`, `check.status: verified`). Güvenlik sınırları gevşemedi: ağ yalnız `RESPECTED_CURSOR_NETWORK=allow`, `.cmd/.bat` reddi, kimlik yalıtımı ve ACL kapsamı aynı.
- Kalan risk / shortcut: (1) Yasak erişim kanıtı aşağıdaki "Yasak erişim yeniden doğrulaması" maddesindedir. (2) `fork`/IPC kullanan bir Cursor özelliği artık `EACCES` alır; hangi özelliklerin buna ihtiyaç duyduğu doğrulanmadı. (3) Cursor'un shell aracı koşuda "reddedildi" dedi; nedeni (onay modeli mi, shim mi) doğrulanmadı. (4) `shortcut: shim yalnız Cursor için yüklenir; node tabanlı yeni işçi eklenirse aynı --require gerekir.` (5) sha256 ön ekleri: `cursor01_fixed_write.log` 7aeb758a3ac278aa, `cursor01_pipe_rootcause.log` 15db4e0da701fc86, `cursor01_write_only.py` 2eb1e4a4572a2800, `appcontainer-pipes.js` 362f75197c7f89a9, `runner.py` 8ae846a6a18f065b, `test_worker_policy.py` 6f12ddf68e6f74de, `test_runner.py` 465f97b4416c7518, `ARCHITECTURE.md` 6b19978729f41945, `THREAT_MODEL.md` af39df1b152e74c0, `cursor01_deny.log` dc8b9c8453a1de2e, `cursor01_deny_probe.log` d3d6889e8bd3603c, `cursor01_deny_probe.py` 2099df89ef6e6177; `cursor01_write_only.py` artık 2. argüman (`write|deny`) alır: b6274725dc1384a0 (yukarıdaki 2eb1e4a4572a2800 değerinin yerine).

## Kapanış hash düzeltmesi 2 (2026-11-04: Cursor token, ilerleme -> evidence taşıma)

- `docs/ilerleme/` klasörü `docs/evidence/` olarak yeniden adlandırıldı; tüm yol atıfları güncellendi. Aşağıdaki hash'ler bu işlemden sonraki güncel dosya içerikleridir ve önceki bloklardaki aynı dosyaların hash'lerinin yerine geçer.

- `docs/ARCHITECTURE.md` → `5331A606A0EAC82187ED4E145C073A02C67D3D42F2724A5875F0D19AC33CE2FB`
- `docs/COMPETITOR_RESEARCH.md` → `1B70D72AFC367A59A56D929D4FCEAA83E73FF155E574842F6338EBA06D05FDC9`
- `docs/ROADMAP.md` → `E8A6E802F22AEB28C5B3555585905DB55FC493ACEADF7CB42AEBDA850A46063F`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `375CE86DE8D2AF9209EA75D6800101B127CE358734D17283D8107162EC7D41DC`
- `docs/THREAT_MODEL.md` → `1761116632181F1F54DC020A9758E8765A253104AA790887945B0747001F365F`
- `docs/adr/ADR-001-controlled-execution.md` → `BDD4C79D63D4702C0CA923B5895DCFFBFD996F541C0B7D4C5CF6429285BD8352`
- `docs/adr/ADR-002-reproducible-evaluation.md` → `2C12DB32594A4D249FDF3E9B16EBADFBDC9ED1DBC55F19C47D3089B17B94A9E0`
- `docs/adr/ADR-003-migration-gate.md` → `A3A562ADF3F16273CEB8C569EA64C95C8FC392F4225C3C097C7AE383F7BAAE13`
- `docs/adr/ADR-004-human-approval-boundary.md` → `3FBBF26E552C3055754D7694D4FEA2323AB3FEBBEB578BC84844A37B6CD75CC0`
- `docs/adr/ADR-005-failure-taxonomy.md` → `7973FF5AAE0306AE8E1BF50540BCCEF0E14E9CC4EA3C9FE905A9EB4D3256B218`
- `docs/adr/ADR-007-provider-key-network-threat-model.md` → `6099FA2EB8C7439A843C1A722EEBFB1F9F14CF1EC254F1F0A58A20F0D5D925AF`
- `src/respected_orchestrator/engine/runner.py` → `48AD809631C6713063C3266D8ECA1BC821DBEAF261332E60F5D0BC49283C3EBB`
- `tests/docs/test_decision_records.py` → `417CABB93D57ACE8C8E5195CF44AC2C5F7FD302DE84B3A2FA3FF7EE138E04110`
- `tests/engine/test_worker_policy.py` → `3A18451497A89AD68F890F5F6F3013BFEE0893F47652A288563E6469E57F4F43`
- `tests/evals/runner.py` → `6A151EC5784990FF5AE58FF973E0264FC9EE4893C17139A13CE82E3D7DD580A7`
- `tests/workflows/test_roles.py` → `078358CEE57819AD8C92950BB329B1C57C96E3757B4CC5F87CCF3C62C8AA069F`
- `docs/evidence/poc/cursor_cache_probe.log` → `3BFEB51FB7B7B7959B2D1E3718AFC518F2FA90DECAD3B891F1B27D73B1D901CF`

## Kapanış hash düzeltmesi 3 (2026-11-04: belge denetimi)

- `docs/ADR-REL04-platform-parity.md` -> `docs/adr/ADR-008-platform-parity.md` taşındı ve numaralandı; atıflar (`ARCHITECTURE.md`, `health_wizard.py`, `release_platform.py`) güncellendi. ADR-001/ADR-007 durum satırları, ROADMAP üç madde, USAGE/FOOTPRINT/COMMANDS (Cursor, OpenCode, Gemini kapsam dışı, `artifact`), uygulama planı (CUR-01) düzeltildi. Aşağıdaki hash'ler önceki blokların yerine geçer.

- `docs/COMMANDS.md` → `42CCAE6C061B141A47E3C98DC4F4E2C8F0EEB01F597A21246F0829DCC2E2F8A5`
- `docs/USAGE.md` → `FBF728AD4C98E3A1D113088683DF663AB4EBAB4AA81114FD6E0E4521261CA395`
- `docs/FOOTPRINT.md` → `19C3FCB5F740E8AE902DB598B04481D3489F75140A3D7B9B6F08E74BCE42802A`
- `docs/ROADMAP.md` → `A626EC66400159D352756B7223AE73642C12649FACBD13FC28C720A7E65EFC53`
- `docs/ROADMAP_EXECUTION_PLAN.md` → `E812588B7511F6A322C033176EA1BADE9573EAF3C211C74FEE7FBC6F442EE7C1`
- `docs/THREAT_MODEL.md` → `E653B88C39C91BACD1CB4860CEC1C8BA06190B4CC18A8B9F993BE1DA4509CB99`
- `docs/ARCHITECTURE.md` → `4245FAA91AC880D5C5C178E9B257FCCB6D0EBA6BB9426BEACC19DB1A6477888E`
- `docs/adr/ADR-001-controlled-execution.md` → `F215301CB2C0A8C6EA0A0C1E9A06D5540B9F945D81A3AAC85C1D7E38110E760D`
- `docs/adr/ADR-007-provider-key-network-threat-model.md` → `2F5F1C3F979AE4BFC72CB2280FCBF7F0866A14D039FD157ED14C9B0C5C311BCF`
- `docs/adr/ADR-008-platform-parity.md` → `F535A3E3B92E1EE13D6F76A1AC30AA288095892177CAA5F632E78980DDE5F80F`
- `src/respected_orchestrator/interfaces/health_wizard.py` → `A41E973CE020011ECC52B21825D00941778A6325AAC196477367445820EF98F7`
- `src/respected_orchestrator/release_platform.py` → `030F38D26738FB8937BFB53C4A3C2F0C7792058FF51A2F95B3F91F95F81B4BA6`

## Kapanış hash düzeltmesi 4 (2026-11-04: tüm .md denetimi)

- THREAT_MODEL (B2, B3, S-01/02/04/20, §7, §8 tarihsel not, §10, §11), ARCHITECTURE §3/§4, FOOTPRINT sınır paragrafı, README, PRIVACY (AppContainer, GitHub ve Cursor/OpenCode ağ satırları), ADR-002/007, COMPETITOR_RESEARCH B-02, SKILL.md (`--data-root` kaldırıldı), UPDATE_NOTES güncellendi. Aynı dosyaların önceki bloklardaki hash'lerinin yerine geçer.
- Bilerek değiştirilmeyenler: `docs/PRODUCT_CONTRACT.md` (üç depoda aynı kopya olmak zorunda; §7 Orchestrator RPP listesi `evidence.view` ve `github.*` işlemlerini içermiyor, Hub/Brain kopyalarıyla birlikte güncellenmeli).

- `docs/THREAT_MODEL.md` → `2BDECEB7AB822D5AE58519F693F77849EBC4E784BE3B244808BA50A9A397875F`
- `docs/ARCHITECTURE.md` → `78FF8367B0490E9BCF894F70ED403FF4D6F1BCE85B40BD683E14CE456ADAAF75`
- `docs/FOOTPRINT.md` → `19C3FCB5F740E8AE902DB598B04481D3489F75140A3D7B9B6F08E74BCE42802A`
- `docs/COMPETITOR_RESEARCH.md` → `4328D090BF0027E56109D53D7650DE0C68E0E9B2CA81E407FF5CD8596E12190B`
- `docs/adr/ADR-002-reproducible-evaluation.md` → `9F46835D260440967B5AA26D549256EF1277A6F671018B99C244CBEBEC2D7BEC`
- `docs/adr/ADR-007-provider-key-network-threat-model.md` → `D529C02BD525131C63E67BBF0831B2E3289A1493282BB21AA1C60BD1072CBE1A`
- `README.md` → `96B2FB48D55083D7D8BB52F6B6DF9A8455A9E4A1912A5A859F6AF2E591C29192`
- `PRIVACY.md` → `BD68E38E522F9CB5EE10BD8A1B2D782EF7668E5701484B98C7E3BD377588BAF9`
- `packaging/windows/UPDATE_NOTES.md` → `91BF9503BC86442A0B62AB68C4F026FDE467CA37ADBA11BDBA08A2E942C40AA4`
- `src/respected_orchestrator/resources/skills/kod-orkestrasyon/SKILL.md` → `D4A4DC3406266436077BEC0C56C3462E66E9949DA0884CEA0FEA53BD7A4DC573`


## Kapanış hash düzeltmesi 5 (2026-11-05: beta.2 öncesi ölçümler ve kararlar)

- ROADMAP (Beta.2 Öncesi Kalan Kritik Düzeltmeler bölümü), THREAT_MODEL (S-24 satırı, §11 CI sınırı), ARCHITECTURE (CI sınırı, verify planı, EVAL/GH/UX sınırları), README (ADR aralığı), PRIVACY (verify'ın ağ sınırı), ADR-002/014 (işaretçi), yeni ADR-017..020. Önceki girdilerdeki bu dosyalara ait hash'ler bu tarihten sonra geçersizdir; güncel değerler aşağıdadır.
- Bilerek değiştirilmeyenler: `docs/PRODUCT_CONTRACT.md` (üç depoda aynı kopya), kaynak kod, testler, `ci.yml`.

- `docs/ROADMAP.md` -> `88158D8E8216E5723A7606BED97B09D836284F6CEDB9F48EE783DCA9CE7DE212`
- `docs/THREAT_MODEL.md` -> `FCDFB0955E485216DF1FABFC99F0F2BBEAC22D9C6F07D7FF6ADCA456305E70DB`
- `docs/ARCHITECTURE.md` -> `445C53949114A40900E080EE4626748B86C99798FD9D6BBD8E75F1690A353A5A`
- `README.md` -> `25205863AD5D6D9F0796AC73AC6304F4306D86076134CA33C19C0BBA29F44C92`
- `PRIVACY.md` -> `ADB773AD7DC648228ECDEADC8C5037EB425ED164EC872638F76702FDC6BDA08B`
- `docs/adr/ADR-002-reproducible-evaluation.md` -> `7B46F68F606695260C9650D9EEF767E5E2045FF5C65BBF9A59A9CF5915A31010`
- `docs/adr/ADR-014-github-boundary.md` -> `3A20192C70E27035A971110FF2C9E7FE287FB14E01267454F2A688FF2EE1178D`
- `docs/adr/ADR-017-ci-security-run.md` -> `3AF6001D51C9B24FB84AA5B4EEACDBF4BFA9F5A0A131B6A7D7F3B01253D18A5E`
- `docs/adr/ADR-018-verify-network-isolation.md` -> `9F0AC15F551CDA7A8AD0852A10983F8C074FDF228DF311892A7909FBBD3B59C6`
- `docs/adr/ADR-019-real-agent-benchmark.md` -> `4B05B480A17316F3546A74F973375F6D1518BC79D918BE2687A8DE4FFCF75F49`
- `docs/adr/ADR-020-ci-feedback-ingestion.md` -> `E351E1B1D644AB04A98E1860D81862C5B4DBC82E6B1F67B9BCE1CF2BCB1B3C38`

## FIX-02 gerçek koşu denemesi (5 Kasım 2026) — GEÇERSİZ

- Ajan/model: opencode/deepseek-v4.1-flash-free (kullanıcı onaylı, 0 maliyet). Komut: `RESPECTED_TEST_SANDBOX=real RESPECTED_OPENCODE_NETWORK=allow python -m tests.evals.bench run ... --confirm-free`.
- Sonuç: 60 koşu yazıldı ama OpenCode "Free usage limit reached" verdi; 26 Direct `agent_error`, 27 Orchestrated `worker_failed`, geçerli koşular (ilk ~4 görev): Direct 0/3 geçti, Orchestrated 3/3 (RSP-001) — örnek küçük, kanıt değil. Rapor `fix02_real_opencode_deepseek_INVALID.json`.
- Ders: kota ifadesi regex'inde kaçtı; "usage limit" eklendi ve testlendi, parti artık ilk işarette durur. Bu hata düzelmeden koşu yeniden yapılmadı (kota bitti).
- FIX-02 kutusu açık: kota yenilenince yeniden koşulmalı.

## FIX-02 gerçek koşu — GEÇERLİ (5 Kasım 2026)

- Ajan: OpenCode, model `amd/DeepSeek-V4.1-Flash`, ücretsiz yol (ADR-019 §3, `--confirm-free`, kullanıcı onaylı). 10 görev x 3 tekrar x 2 kol = 60 koşu, zaman aşımı 300 sn.
- Rapor: `docs/evidence/poc/fix02_real_opencode_amd_deepseek.json`, SHA-256 `efc54aa6647891acd1f8f75f898281e795c2bbd8c1a0c66c65aaa54a0e5f6a9c`. `bench.validate`: hata yok (durum complete, kind real, sızıntı yok, geçersiz koşu yok, ölçülmeyen değer 0 yazılmadı).
- Sonuç: direct 29/30 geçti (%96,7; 1 zaman aşımı); orchestrated 21/30 geçti (%70; 9 başarısız). Orchestrated güvenlik ihlali 0, direct güvenlik ölçümü `unknown`. Token ve maliyet `unknown` (OpenCode ücretsiz yolu vermiyor).
- Yorum: bu ölçümde orkestratör kolu doğrudan ajandan **daha başarısız** ve ~2,4 kat yavaş (5580 sn / 2361 sn). Bu, "orkestratör daha iyi" iddiasını desteklemez; tek model, tek ajan, küçük görevler. 9 başarısızlığın nedeni bu girdide çözümlenmedi.
- Önceki geçersiz kayıt: `fix02_real_opencode_amd_deepseek_INVALID.json` (direct kol, OpenCode'un `PWD` mirası yüzünden repo kökünde çalıştı; 0/30). Düzeltme: `runner._execute` artık `PWD`'yi `cwd`'ye ayarlar, regresyon testi eklendi; yanlışlıkla commit edilen kök `solution.py` silindi.

## FIX-01 / FIX-03A / FIX-03B — hosted ve canlı kanıt (5 Kasım 2026)

- FIX-01: hosted koşu https://github.com/respected0/orchestrator-e2e-test'ten bağımsız olarak `respected0/respected-orchestrator` koşu 42006314204 (commit a700aff): güvenlik matrisi standart kullanıcı altında 28/28, skipped 0, failed 0, `elevated: false`; kapı yeşil; genel adım 660 test OK (127 skip = yalnızca genel adımdaki yükseltilmiş-skip listesi, güvenlik testleri ayrı adımda koşar). Manifest: `docs/evidence/poc/fix01_hosted_security_manifest.json` (SHA-256 4a9907a5b2f1494a99d51596cf0c26a2ca5a251e32e3cbb0b7ada162f9ff649a). Düzeltmeler: `Start-Process` yönlendirmesi hosted'da "parameter is incorrect" verdi, iç betik dosyasına geçildi; hosted git rc=128 nedeniyle Program Files testi rc 0/128 kabul eder (ACL iddiası aynı); sandbox testleri genel adımın skip listesine alındı. `main` dal koruması: zorunlu kontrol `tests (windows, Python 3.13)`.
- FIX-03A/B: `tests/interfaces/test_github_live.py` (opt-in), `respected0/orchestrator-e2e-test`: gerçek `git push`, `gh pr create --draft` (PR #1, #2), geri okuma head SHA eşleşti, geçersiz token ve eksik dal yapılandırılmış hata (receipt yok), aynı operation_id ikinci kez push/PR üretmedi, merge yok, PR'lar kapatıldı. `gh api` yoklaması gerçek check-run: ilk `pending`, sonra `success` kabul, yeniden yoklama `duplicate`, eski olay `stale_event`. Günlük: `docs/evidence/poc/fix03_live_run.log`.
- Kalan risk: imzalı çalıştırma fixture'dır (`check_result` yamalı; gerçek worker konusu değil); token en düşük yetkili değil; kanıt yayın commit'i için yinelenmeli.

## beta.1 → beta.2 güncelleme kanıtı (5 Kasım 2026)

- Kapsam: beta.1 etiketinin (`v0.1.0-beta.1`) kendi kaynağıyla yazılan veri, bu checkout ile aynı klasörlerde okunur/çalışır. Yalıtılmış HOME/APPDATA/veri kökü; kişinin gerçek kurulumuna dokunulmaz.
- Komut: `python tests/tools/upgrade_proof.py --out docs/evidence/poc/upgrade_beta1_to_beta2.json` → 25 adım, hepsi PASS (ham: `upgrade_beta1_to_beta2.json`).
- Kanıtlanan: Gemini varsayılanları (`default_worker`, `default_reviewer_tool`) `setup` ile agy'ye taşındı, diğer anahtarlar korundu, `settings.json.v1.bak` oluştu, `repair` idempotent; beta.1'in bitmiş görevi `check` ile `verified`, `inspect`/`evidence`/`list` okur; başlatılmamış eski görev yeni sürümde başlayıp sonuçlandı; eski kampanya ve proje durumu aynı okunur; beta.1'in yazdığı Gemini MCP girdisi `integrations set gemini=off` ile kaldırıldı, kullanıcının kendi girdileri korundu; yeni görev uçtan uca çalıştı; `uninstall` sonrası listede gemini yok.
- Bulunan ve düzeltilen: sürüm numarası hâlâ `0.1.0b1` idi (kurucu aynı sürümü "güncelleme" saymazdı); `0.1.0b2`/`0.1.0-beta.2` yapıldı (`__init__`, `pyproject`, `.iss`, PRIVACY, FOOTPRINT). `UPDATE_NOTES.md` "ilk beta" diyordu, beta.2 değişiklikleriyle yenilendi. `tests/fixtures/releases/0.1.0-beta.2/settings.json` eklendi (beta.2'nin gerçek `config set` çıktısı).
- Kalan risk: Inno kurucusunun yedek/geri alma yolu gerçek iki kurulumla koşulmadı (kayıt defteri/Programs yolu kişinin makinesini değiştirir); işçi/durmuş çalışan süreç ve ortada kesilmiş (supervisor çalışırken) proje/kampanyanın beta.2'de sürdürülmesi denenmedi, yalnızca durağan durumlar.

## beta.1 → beta.2 kurucu düzeyi güncelleme (5 Kasım 2026)

- Kapsam: beta.1 kurucusu (`v0.1.0-beta.1` etiketinden derlendi) `/VERYSILENT` ile gerçek `%LOCALAPPDATA%\Respected\RespectedOrchestrator` altına kuruldu; Gemini varsayılanları, gerçek Gemini MCP girdisi ve doğrulanmış bir görev üretildi; üstüne beta.2 kurucusu (`/VERYSILENT`) kuruldu. Test öncesi veri klasörü, AI araçlarının ayar dosyaları ve `HKCU ...\Uninstall` yedeklendi; test sonrası aynen geri yüklendi (kayıt defteri dışa aktarımı öncesiyle özdeş).
- Sonuç: kurucu çıkış kodu 0; `--version` 0.1.0b2; `default_worker`/`default_reviewer_tool` gemini→agy, `schema_version` 2, `settings.json.v1.bak` oluştu; `health` healthy; beta.1'in görevi `check` ile `verified`; `update-backup` başarıdan sonra silindi; `integrations set gemini=off` Gemini girdisini kaldırdı; `uninstall` `removed`, çakışma yok.
- Denenmedi/kanıtlanmadı: kurucunun **geri alma** yolu. Bozuk `settings.json` ile üstüne kurma denemesinde beta.1 kurucusu da aynı bozuk veriyi görüp `setup` hatasıyla (`DATA_FORMAT`, çıkış 8) bitti; temiz bir "beta.2 başarısız, beta.1 geri geldi" kanıtı çıkmadı. Kullanıcı kurucuların tekrar açılmasını istemediği için durduruldu.

## beta.1 → beta.2 geri alma ve yarıda kalan proje (5 Kasım 2026)

- Geri alma (gerçek kurucu): beta.1 kurulu, `settings.json` `schema_version: 99` (beta.2'nin reddettiği "daha yeni veri"), üstüne beta.2 kurucusu `/VERYSILENT`: kurucu çıkış kodu **8**, günlükte `repair failed with exit code 1`; sonra `--version` 0.1.0b1, `respected-orchestrator.exe` SHA-256 beta.1 ile **aynı**, `settings.json` SHA-256 **aynı**, `health` healthy, `update-backup` silindi. Kayıt defteri, veri klasörü ve AI araç ayarları test sonunda yedekten geri yüklendi.
- Yarıda kalan proje: `tests/tools/upgrade_proof.py` beta.1'in kendi kodunun yazdığı, ikinci aşaması çalışırken sert öldürülmüş (`os._exit`) bir proje üretir. beta.2: `project-status` okur (`running`, yanlışlıkla `completed` değil); `project-resume` **insan onayı ister** (`checkpoint_missing`, `project-approve` etkileşimli terminalde) ve kendiliğinden sürdürmez — beta.1'in doğrulanmış sürdürme noktası yoktur; `project-cancel` çalışır. Bu tasarım gereğidir (otomatik sürdürme yok), hata değil.
- Kanıt: `docs/evidence/poc/upgrade_beta1_to_beta2.json` (29 adım, hepsi PASS).
- Kalan risk: güncelleme sırasında çalışan proje/kampanya durdurulur; beta.1'de başlayan proje beta.2'de elle `project-approve` ister. Kanıt yayın commit'i için, kurucu o commit'ten derlenip `--version`/`health` ile bir kez bakılarak yinelenmeli.

## B3-00.01 — Beta.3 sürüm bazı ve değişmez ilke matrisi (6 Kasım 2026)

- Kapsam: ROADMAP §4.1'deki 8 değişmez ilke mevcut testlere eşlendi (`docs/adr/ADR-021-desktop-boundary-baseline.md`); 4 boşluk (G-1..G-4) sahibi görevle kayıtlı. Baz commit `ec9e599`.
- Değişen dosyalar: `docs/adr/ADR-021-desktop-boundary-baseline.md` (yeni), `tests/engine/test_review_apply_invariants.py` (I-02: apply sonrası HEAD değişmez), ROADMAP kutusu.
- Doğrulama (Windows 11, normal kullanıcı, Python 3.13):
  - `python -m unittest tests.engine.test_review_apply_invariants` → 13 test OK (yeni assertion dahil).
  - `python docs/evidence/poc/doc01_check.py` → `PASS ADR: 21 karar kaydı`, `RESULT PASS 2026-11-06`.
  - Tam suite `python -m unittest discover -s tests -t .` → 661 test, 797 sn, **errors=2, skipped=2**. İki hata aynı testin (test + temizlik) kaydıdır: `EngineTests.test_supervisor_crash_kills_owned_descendants`, `supervisor.log` WinError 32. Tek başına ve değişiklik stash'lenmişken tekrar koşuldu: ikisi de OK. Neden: suite sürerken aynı makinede başka testler paralel koşturuldu (yük kaynaklı yarış); kök neden ayrıca araştırılmadı.
  - Skip'ler: biri `test_live_context_mode_search_when_installed` (CONTEXT_MODE_SERVER gerekir, isteğe bağlı canlı yoklama); ikincisi izole edilmedi. AppContainer dosyaları (`test_sandbox`, `test_worker_policy` vb.) ayrı koşuda 0 skip.
- Kalan risk: tam suite yeşil bir temiz koşu olarak kaydedilmedi (yukarıdaki yarış); G-1..G-4 açık; ikinci skip'in nedeni bilinmiyor.

## B3-00.02 — Masaüstü tehdit modeli ve güven sınırları (6 Kasım 2026)

- Kapsam: `docs/THREAT_MODEL.md` §12: yeni sınırlar B9–B12, 13 negatif senaryo (D-01..D-13; IPC spoofing, localhost CSRF, deep link, XSS, renderer ele geçirme, replay, yetki yükseltme, symlink, patch drift, pano), yetkili eylem tablosu. Tüm satırlar **Planlı**; masaüstü uygulaması yok, koruma iddiası yok.
- Test: `tests/docs/test_desktop_threat_model.py` (≥12 senaryo, her satırda sahip/katman/test planı görev kimliği, hiçbir satır testsiz "Engellenir" demez, renderer onay taklidi kapsanır). Çalıştırma: 3 test + `test_decision_records` OK; negatif kontrol: D-05 satırı "Engellenir" yapılınca test FAIL verdi, geri alındı.
- Kalan risk: renderer taklit testi gerçek renderer olmadığından henüz yürütülemez (B3-05.04'te yürütülecek); senaryolar belge düzeyindedir.

## B3-00.03 — Komut/yetki matrisi ve onay otoritesi sözleşmesi (6 Kasım 2026)

- Kapsam: `engine/authority.py` (saf politika: 5 köken × 4 yetki sınıfı, `effective_origin`, `Grant`/`check_grant`) ve `docs/adr/ADR-022-command-authority-matrix.md`. Henüz hiçbir yola bağlanmadı; CLI/MCP/runner davranışı değişmedi.
- Test: `tests/engine/test_authority.py` (tam matris 20 hücre; yalnızca HUMAN ayrıcalıklı; `RESPECTED_ORCH_CHILD=1` HUMAN iddiasını CHILD'a düşürür; yanlış kapsam/run/patch reddi ve ret'in nonce'u tüketmemesi; tekrar oynatma reddi). Çalıştırma: `tests.engine.test_authority tests.engine.test_security_gate tests.docs tests.interfaces.test_human_approval_contract` → 19 test OK; `doc01_check.py` RESULT PASS (22 ADR).
- Kalan risk: politika henüz zorlanmıyor (B3-05.02'de bağlanacak); nonce deposu bellek içi; kabuk kimliği/imzası yok (kimlik doğrulama iddiası yok).

## B3-00.04 — Ürün sözleşmesi ve uyumluluk karar kaydı (6 Kasım 2026)

- Kapsam: `docs/adr/ADR-023-desktop-product-contract.md`: GUI için sözleşme değişikliği gerekmez, hesap/çevrimiçi/başka uygulama koşulu yok, gelecekteki değişiklik kuralı. ADR-021 I-08 satırı düzeltildi (conformance testi Hub deposunda).
- Doğrulama: `python docs/evidence/poc/doc01_check.py` RESULT PASS (23 ADR). Salt-okunur conformance koşusu (Hub deposu, hiçbir dosya değiştirilmedi): `common.conformance.test_product_contract.ProductContract.test_every_repo_carries_the_same_contract` → **FAILED** `2 != 1`; `diff` Brain kopyasının 71–74. satırlarda (BR-028) Hub/Orchestrator'dan ilerde olduğunu gösterir.
- Kalan risk: **üç sözleşme kopyası bugün eşit değil** (başka depolarda; izinsiz değişiklik yapılmadı). Eşitleme sahibinin kararı gerekir; Beta.3 kararı bundan etkilenmez.

## B3-01.01 — Tauri/React build ve güvenli başlangıç PoC (6 Kasım 2026)

- Kapsam: `desktop/` (Tauri 2 + React 19 + TS, Vite 7): tek pencere `main`, kapalı CSP (`default-src 'self'`, uzak köken yok, `unsafe-*` yok, `object-src 'none'`), `withGlobalTauri=false`, boş capability izin listesi, özel invoke komutu ve eklenti yok, `on_navigation` koruması (yalnızca paketli köken; geliştirme sunucusu yalnızca debug derlemesinde ve 127.0.0.1:1430).
- Doğrulama (Windows 11, yükseltilmemiş kullanıcı):
  - `cargo test --lib` (desktop/src-tauri) → 1 test OK (`bundled_origin_only`: `https://example.com`, `file:///…`, `javascript:`, `about:blank`, `http://127.0.0.1:8080`, `http://tauri.localhost.evil.com` reddedildi).
  - `python -m unittest tests.desktop.test_shell_policy` → 5 test OK (CSP, tek pencere, capability yasakları, invoke/eklenti yokluğu, navigation guard kaydı).
  - `npx tauri build --no-bundle` → exit 0, `respected-orchestrator-desktop.exe` 8,7 MB.
  - Smoke: exe başlatıldı, 6 sn sonra süreç canlı, `MainWindowTitle='Respected Orchestrator'`, pencere tutamacı var, `elevated=False`; süreç sonlandırıldı.
- Kalan risk: pencere içeriğinin (React sayfası) görsel olarak yüklendiği ekran görüntüsüyle doğrulanmadı; navigation guard'ın canlı WebView'de gerçek bir yasak gezinmeyi engellediği Rust birim testiyle (URL kararı) kanıtlı, uçtan uca değil; "signed asset/integrity" tasarımı ve temiz makine testi B3-09'a kalır; kurucu dışı build.

## B3-01.02 — Tipli IPC şeması, istemci ve sunucu (6 Kasım 2026)

- Kapsam: `engine/local_api.py` (RPP'yi sarar, değiştirmez): sürüm `ipc:"1"`, korelasyon `id`, oturum belirteci (sabit zamanlı karşılaştırma), 9 komutluk izin listesi, `authority.authorize` ile yetki sınıfı denetimi, 64 KiB sınırı, 8 hata kodu, aynı `id` için idempotent yanıt / farklı istek `REPLAY_CONFLICT`. TS sözleşmesi `desktop/src/contracts/ipc.ts`.
- Test: `tests/engine/test_local_api.py` 9 test (bilinmeyen/izin listesi dışı komut `github.pr_create`, `maf-approve`, `apply` dahil reddi; yanlış/eksik belirteç; sürüm uyumsuzluğu; bozuk JSON, iç içe `[`×60000, aşırı büyük yük; replay; WORKER/MCP yetki reddi; 500 rastgele bozuk istek hiç istisna fırlatmadan hep `ok=false`; Python↔TS komut/hata listesi eşitliği). `unittest tests.engine.test_local_api tests.interfaces.test_rpp tests.desktop` → 28 test OK; `npm run build` (tsc) OK.
- Kalan risk: taşıma katmanı (named pipe/loopback ve Tauri tarafı) yok; belirteç üretimi/dağıtımı ve gerçek istemci B3-01.03'te; replay önbelleği bellek içi, 256 girişli.

## B3-01.03 — Engine connector ve health/version handshake (6 Kasım 2026)

- Kapsam: motor tarafı gizli `_ipc` girişi (`local_api.serve`: satır tabanlı, belirteç `RESPECTED_IPC_TOKEN` ortamından alınıp ortamdan silinir, belirteç yoksa çıkış kodu 2). Kabuk tarafı `desktop/src-tauri/src/engine_connector.rs`: motoru `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app\` (veya `RESPECTED_APP_DIR`) altında bulur, alt süreç olarak kendisi başlatır (kendi stdio'su: dinlenen port/pipe yok → yanlış sahipli servis mümkün değil), `hello` + `engine.manifest` ile ürün kimliği ve IPC sürümünü doğrular, `engine.health` verir; ham komut iletimi yok. Renderer'a açılan tek komut `engine_status` (argümansız, salt okunur); arayüz üç durumu gösterir.
- Test: `cargo test --lib` → 6 OK, içinde motor yok (`NotInstalled`), çöp çıktı (`BrokenInstall`), motor hemen çıkıyor (`Disconnected`), başka ürün (`WrongOwner`), farklı IPC sürümü (`VersionMismatch`) ve gerçek motorla el sıkışma + süreç öldürme + yeniden bağlanma. `tests.engine.test_ipc_serve` 2 OK (satır başına bir yanıt, yanlış belirteç reddi, belirtecsiz başlamama). `tests.test_main tests.engine.test_ipc_serve tests.engine.test_local_api tests.desktop.test_shell_policy tests.interfaces.test_rpp` → 43 OK. `tests/desktop/test_shell_policy.py` artık tam olarak bir komut (`engine_status`) şartı koşar.
- E2E (gerçek release exe, UI Automation ile pencere metni): motor klasörü yok → "Motora bağlanılamadı (" + "Run the Respected Orchestrator installer again (repair)."; paketli **eski** beta.2 motoru (`dist/RespectedOrchestrator`, `_ipc` bilmez) → "Motora bağlanılamadı (" (hata çıkışı, GUI çökmedi).
- Sürüm matrisi: ipc "1"↔"1" kabul; ipc "2" → `VersionMismatch`; ürün `respected-hub` → `WrongOwner`; beta.2 motoru → bağlanamaz.
- Kalan risk: **olumlu uçtan uca (GUI + paketli motor "sağlıklı") gösterilemedi**, çünkü paketli motor `_ipc` içeren sürümle yeniden derlenmedi; olumlu yol yalnızca cargo testinde `python -m` ile kanıtlı → B3-09.01'de paketli motorla yinelenecek. Ekran görüntüsü alınmadı/okunmadı; metin UI Automation'dan.

## B3-01.04 — Temel gezinme, erişilebilirlik ve hata durumları (6 Kasım 2026)

- Kapsam: `desktop/src/shell.ts` (5 rota: Projeler, Çalıştırmalar, İncelemeler, Ajanlar, Ayarlar; `screenView` motor durumundan loading/error/empty türetir; hash yönlendirme; klavye sırası), `main.tsx` (ana gezinme `nav`, `main` + `h1`, atlama bağlantısı, `aria-current`, `role=status/alert`, odak halkası), `style.css` (açık/koyu tema `prefers-color-scheme`).
- Test: `npm run check` (desktop/) → `tsc --noEmit` temiz + `node --test` 5/5 (boş kurulumda her rota anlaşılır boş durum; motor yok/sağlıksız hiçbir rotada başarı gibi görünmez; bilinmeyen/enjekte hash `projects`'e düşer; ok/Home/End sarmalı).
- E2E (gerçek release exe, motor klasörü yok, UI Automation + SendKeys): bağlantılar `İçeriğe geç | Projeler | Çalıştırmalar | İncelemeler | Ajanlar | Ayarlar`; ekranda "Motor yok" ve "Motora bağlanılamadı (NotInstalled)."; Tab×3 sonrası odak `Çalıştırmalar`, ↓ ile `İncelemeler`'e geçti.
- Kalan risk: yavaş motor (zaman aşımı/ilerleme) durumu ve kontrast/ekran okuyucu denemesi yapılmadı; bileşen düzeyinde (DOM) test yok, yalnızca saf mantık + UIA smoke; ekran görüntüsü seti/video üretilmedi (UIA metni kanıt). Rota ekranları iskelet; veri B3-04 ve sonrasında.

## B3-02.01 — Mevcut ayrık kontrolcüleri denetleyen supervisor (6 Kasım 2026)

- Kapsam: `engine/supervisor.py`: veri kökü başına tek sahip, süreç ömrüne bağlı OS dosya kilidi (`msvcrt.locking` / `flock`; çökme kilidi otomatik bırakır, PID tahmini ve PID yeniden kullanımı yok), yükseltilmiş oturumda ret (`appcontainer._is_elevated`), çalıştırma sahiplenmeleri `supervisor-claims.json` (canlı işçi varken ikinci başlatma `RunAlreadyClaimed`, ölü işçide yeniden sahiplenme). Mevcut campaign/project kodu değiştirilmedi.
- Test: `tests/engine/test_supervisor.py` 6 test, art arda 3 koşuda OK: aynı veri kökünde ikinci supervisor reddi; sahip süreç öldürülünce kilit serbest; **6 eşzamanlı süreçten tam 1 sahip, 5 `busy`**; yükseltilmiş oturum reddi; sahip olmadan claim reddi, yinelenen başlatma reddi, ölü işçi sonrası yeniden claim; supervisor öldürülünce çalışma süreci yaşar ve yeni supervisor aynı run'ı ikinci kez başlatamaz.
- Kalan risk: supervisor henüz hiçbir başlatma yoluna bağlı değil (B3-04.04/B3-02.04 bağlayacak); "iki GUI penceresi" yalnızca iki süreç/iki sahip denemesiyle sınandı, gerçek iki GUI örneği değil; orphan alt süreç ağacı temizliği (Job Object) bu görevde eklenmedi, mevcut `winproc` sahipliğine bırakıldı.

## B3-02.02 — Sürümlü event journal ve outbox (6 Kasım 2026)

- Kapsam: `engine/journal.py`: yalnızca-ekleme `<crc32> <json>` satırları (`v`, `seq`, `ts`, `op`=operation_id, `run`, `type`, `p`), her yazım `fsync`; aynı (operation_id, event_type) bir kez saklanır (yeniden başlatmada da); yük 16 KiB sınırı; anahtar adı/değer desenli sır maskeleme yazımdan önce; bozuk kuyruk (yarım yazım) kesilir, ortadaki bozulma kanıt olarak dokunulmadan bırakılır, `corrupt` bayrağı yazmayı reddeder, `replay` yalnızca güvenilir öneki döndürür; saklama = döndürme (`archive`), seq dosyalar arasında monoton kalır.
- Test: `tests/engine/test_journal.py` 8 test OK: 10000 olay monoton seq ve idempotent yeniden okuma; yinelenen olay; yarım yazım kuyruğu; ortadaki bayt bozulması (önek dönüşü, yazma reddi, dosya baytları değişmedi); disk dolu (`ENOSPC`) seq ilerlemez ve sonraki başarılı yazım çalışır; sır maskeleme (`sk-`, `ghp_`, `Bearer`, `api_key`, iç içe `Authorization`); döndürme sonrası seq; bilinmeyen kayıt sürümü güvenilmez.
- Kalan risk: kısmi saklama (en yeni N kaydı tutma) yok; yalnızca dosya döndürme. Her olayda `fsync` yaptığından 10000 olay ≈ 10 sn (yüksek hacimde toplu yazım gerekebilir). Veri geçişi: ilk sürüm `v=1`, geçiş adımı henüz gerekmiyor. Journal henüz üreticilere bağlı değil (B3-02.03). Maskeleme desen tabanlıdır; bilinmeyen biçimli sırlar sızabilir.

## B3-02.03 — Olay akışı ve reconnect imleci (6 Kasım 2026)

- Kapsam: IPC'ye `events.snapshot` (son seq + run başına son olay + durum özeti `state_hash`) ve `events.since {after, limit}` (en çok 500 olaylık sayfa; çekme tabanlı → yavaş tüketici doğal geri basınç; `gap` bayrağı: imleç journal'ın ilerisinde veya döndürme/boşluk yüzünden sonraki olay `after+1` değil; `has_more`). `_ipc` süreci journal'ı `state/events.log`'dan açar. İstemci: `desktop/src/events.ts` (snapshot'tan başlar, yinelenen seq'i yok sayar, boşlukta `needsResync` ile durur, tahmin etmez).
- Test: `tests/engine/test_local_api.py::EventStreamTests` 4 test (1200 olaylık patlama sayfalarla tam bir kez, sayfa ≤500; 3 yeniden açılışta aynı `state_hash`; imleç ilerde ve döndürülmüş journal gap; kötü imleç/journal yok). `tests/engine/test_ipc_serve.py::test_three_reopens_of_the_real_process_see_the_same_state_hash` gerçek `_ipc` sürecini 3 kez başlatıp öldürerek aynı `last_seq=25` ve `state_hash`'i doğrular. `desktop npm run check`: tsc + `node --test` 8/8 (yinelenen/sıralı, boşlukta resync, snapshot+kaçırılan olaylar = tam replay). Toplam: `unittest` test_ipc_serve + test_local_api + test_journal → 24 OK.
- Kalan risk: üreticiler henüz journal'a yazmıyor (supervisor/kampanya olayları B3-04/B3-06'da bağlanır), bu yüzden gerçek bir görev olayıyla uçtan uca "yeniden aç" kanıtı yok; GUI tarafı yalnızca saf indirgeyici (React bağlaması ve video yok). Abonelik itme modeli yok, çekme yoklaması.

## B3-02.04 — Resume ve shutdown davranışı (6 Kasım 2026)

- Kapsam: pencere kapatma, uygulamadan çıkış ve motoru durdurma ayrıldı. Kapatma/çıkış **hiçbir çalıştırmayı durdurmaz** (çalıştırmalar ayrık motor süreçleri); etkin iş varken kabuk kapatmayı tutar (`must_ask`), `close-blocked` olayı ile arayüzde "N çalıştırma sürüyor… arka planda devam ederler" modali (`closeDecision`, Açık kal / Yine de kapat) çıkar; ikinci renderer komutu `confirm_close`. Etkin işler IPC `runs.active` ile (yalnızca canlı işçili sahiplenmeler). Motoru/işi durdurma GUI'den **yok** (B3-04.04'te, onayla). Resume yolu değişmedi: mevcut `project-resume`/`approve_project_resume`/`_require_resume_clearance` ve checkpoint doğrulaması tek kaynak; GUI yeni, güvensiz bir resume yolu açmaz.
- Test: `cargo test --lib` 7 OK (`close_asks_only_when_runs_are_active_and_not_yet_confirmed`); `desktop npm run check` tsc + 9/9 (`closeDecision`); `tests.engine.test_local_api` 14 OK (`runs.active` yalnızca canlı işçileri listeler); `tests.engine.test_supervisor` 7 OK iki koşuda (**supervisor 5 kez yazım ortasında öldürüldü: claims dosyası hep geçerli, 7 giriş tam**); mevcut kapılar yeniden koşuldu: `tests.engine.test_review_apply_invariants` + `tests.workflows.test_checkpoint` 24 OK (checkpoint kurcalama/yeni şema/farklı HEAD → resume yok, bayat yama reddi, ikinci apply reddi). `tests.desktop.test_shell_policy` tam iki komut şartı. Gerçek release exe: pencere açıldı; boşta `CloseMainWindow` ile süreç çıktı (modal çıkmadı).
- Kalan risk: **modalın gerçek pencere üzerinde etkin işle çıktığı uçtan uca gösterilmedi** (paketli motor `_ipc`'siz olduğundan GUI etkin iş göremez; B3-09.01'de paketli motorla yinelenecek); "çift ücretlendirme" için yeni test eklenmedi, mevcut apply/retry testlerine dayanıldı; "elle shutdown seçeneği" (motoru durdur) kapsam dışı bırakıldı.

## B3-02 ek kanıt — paketli motorla uçtan uca (6 Kasım 2026)

- Kapsam: B3-01.04 ve B3-02.04'te "kalan risk" olarak B3-09.01'e ertelenen iki uçtan uca gösterim, güncel kaynaktan derlenen paketli motorla yapıldı (`python packaging/build_dist.py --output %TEMP%\dist_b3`, çıkış 0).
- Paketli exe `_ipc`: geçerli jetonla `hello` ve `engine.health` ok=true döndü (`runs.active` boş); yanlış jeton `UNAUTHENTICATED`, 16 karakterden kısa jeton `IPC_TOKEN` ile reddedildi.
- Pozitif GUI+motor: release GUI `RESPECTED_APP_DIR` ile paketli motora yönlendirildi; UI Automation rozeti `Motor 0.1.0b2`, boş durum metni ve beş gezinme öğesini okudu; GUI'nin alt süreci `respected-orchestrator.exe _ipc`.
- Kapatma modalı: motorun `supervisor-claims.json` dosyasına canlı bir pid ("çalıştırma") yazıldı; pencere kapatma isteğinde GUI açık kaldı, modal "1 çalıştırma sürüyor. Pencereyi kapatmak bunları durdurmaz…" gösterdi; "Yine de kapat" InvokePattern ile basılınca GUI çıktı, çalıştırma süreci **yaşamaya devam etti**, artakalan motor süreci yok.
- Tam paket: `python -m unittest discover -s tests -t .` → 705 test OK, skipped=2 (Cursor CLI kurulu değil; `CONTEXT_MODE_SERVER` istenen canlı yoklama). Önceki 2 hata (yük altında kırılan `test_supervisor_crash_kills_owned_descendants`) bekleme süresi 3→20 sn ile giderildi.
- PRODUCT_CONTRACT.md: Brain'deki güncel metin Hub ve Orchestrator'a kopyalandı, üç md5 eşit; Hub `common.conformance.test_product_contract` 9 OK.
- Kalan risk: kapatma testindeki "çalıştırma" gerçek bir görev değil, claims dosyasına yazılmış canlı pid'dir (supervisor henüz runner'a bağlı değil, B3-04/05). Paketli motor sürümü kaynak pyproject'ini (0.1.0b2) yansıtır; Beta.3 sürüm yükseltmesi B3-09'da.

## B3-03.01 — Ajan destek/yetenek matrisi (6 Kasım 2026)

- Kapsam: `engine/agent_adapters.py` (codex, claude, cursor, opencode, antigravity, custom × chat/pty/send_input/interrupt/resume/usage/auth/approval); her yetenek `verified | source | advertised_missing | unsupported`. `verified` = bayrak kurulu CLI'nin kendi `--help` çıktısında bulundu (bir model oturumu değildir); PTY hiçbir ajanda açık değil. `usable` = verified + ikili var + giriş ok.
- Test: `python -m unittest tests.engine.test_agent_adapters -v` → 9 OK (8 sahte-yoklama senaryosu: yanlış mod bildirimi, ikili yok, sürüm düşürme, giriş gerekli, yoklama zaman aşımı, PTY asla usable, custom/antigravity iddiasız; 1 canlı test kurulu CLI'lerde chat'in `advertised_missing` olmadığını doğrular).
- Canlı koşu (salt-okunur `--version/--help/auth status`): codex 0.160.1, claude 2.1.318, cursor 2026.10.22-27dcf5f, opencode 2.2.3 hepsi bulundu ve giriş ok; chat dördünde de `verified`; antigravity ikilisi yok → `unsupported`. Tablo `docs/AGENT_ADAPTER_MATRIX.md`.
- Kalan risk: `verified` yalnızca bayrak varlığını kanıtlar; gerçek oturum akışı B3-03.03'te. interrupt/usage/send_input (claude hariç) `source`. Cursor sürüm tabanı sabitlenmedi. Giriş durumu çıktısındaki e-posta vb. kimlik alanları matrise yazılmaz.

## B3-03.02 — ConPTY + AppContainer fizibilite kapısı (6 Kasım 2026)

- Kapsam: gerçek ConPTY'ye bağlı AppContainer süreci denendi (`tests/engine/conpty_experiment.py`, yalnız test; üretim `spawn` değişmedi). Karar: `ADR-024` — koşullu GO; `agent_adapters` matrisinde `pty` üretim broker'ı gelene kadar `unsupported`.
- Test: `python -m unittest tests.engine.test_conpty_feasibility -v` → 10 OK (dış dosya okuma/yazma reddi, ağ varsayılan kapalı [loopback sunucu bağlantı görmedi], torun süreç kum havuzunda, boyut değişikliği, 1 MiB çıktı, terminal kaçış dizileri ham gelir, broker girdisi çocuğa ulaşır, ham modda 0x03 okunur, cooked modda SIGINT gelmez + sert durdurma çalışır, çıktı yalnız PTY kanalından). Hiçbiri skip değil.
- Gerçek bulgular (deneyde ölçüldü): (1) `STARTF_USESTDHANDLES` olmadan çocuk çıktısını üst sürecin yönlendirilmiş stdout dosyasına yazdı; null std handle ile kapandı (üst süreç stdout'u boş, çıktı PTY'de). (2) Ctrl-C sinyali AppContainer içindeki cooked süreçte teslim edilmiyor (20 sn); ham modlu süreç 0x03'ü girdi olarak okuyor.
- Birlikte koşan belge/ek testler: `tests.docs.*` + `tests.engine.test_agent_adapters` ile 23 test OK.
- Kalan risk: ağ-açık PTY ve gerçek ajan CLI'sinin PTY içinde çalışması denenmedi; Job Object+PTY denenmedi; Ctrl-C sınırının nedeni (AppContainer mı ConPTY mi) ayrıştırılmadı; deney kodu üretim yoluna henüz taşınmadı.

## B3-04.01 — Project/Run read model + filtreler (6 Kasım 2026)

- Kapsam: `engine/read_model.py` salt-okunur DTO'lar (run: durum sınıfı queued/in_progress/done/failed/cancelled/stale/invalid, ajan, bağımlılıklar [retry_of/correction_of/inherited_patch_run_id], kanıt referansı [patch var mı, log adları — içerik yok]; proje: aşamalar + `after` bağımlılıkları + alive). Anahtar-kümesi sayfalama (run kimliği zamanı içerir, sıra sabit), durum/metin filtresi, eski/yeni sıralama. Durum kararı `runner.effective_status` ile **CLI ile tek yerde** (`inspect_task` buna taşındı, davranış aynı). IPC: `runs.list`, `projects.list` (READ, giriş doğrulamalı); `desktop/src/contracts/ipc.ts` eşlendi.
- Test: `tests.engine.test_read_model` + `test_local_api` → 22 OK (UI durumu = `inspect_task`/`list_tasks` durumu; ölü pid'li "running" → stale, canlı → in_progress; bozuk JSON, kimlik uyuşmazlığı, bilinmeyen durum, boş/kötü dizin → `invalid` satır, çökme yok, bilinmeyen durum sağlıklıya eşlenmez; filtre/arama/sıra; 10 000 run 200'lük 50 sayfada tam bir kez, azalan sıra, <120 sn [en kötü durum: hepsi imzasız→invalid]; kötü cursor/filtre BAD_REQUEST). `tests.engine.test_runner` 54 OK (refactor regresyonu). `desktop npm run check` tsc + 9/9.
- Kalan risk: 10k testi imzasız (invalid) satırlarla ölçüldü; imzalı 10k geçerli run'ın süresi ölçülmedi. Kullanıcı arayüzü (liste ekranı) henüz bu komutları çağırmıyor (B3-04.02+). `counts` (durum başına toplam) bilinçli eklenmedi.

## B3-04.02 — DAG görselleştirme ve kapsam çatışması (6 Kasım 2026)

- Kapsam: `workflows/dag_view.py` motorun `planner._dag` kararını **aynen** taşır (`valid` = motor kabul etti); reddedilen planı okunabildiği kadar çizer ve yapılandırılmış bulgular verir: `cycle` (düğümler + kenarlar), `unknown_dependency`, `duplicate_name`, `ownership_collision` (yalnız birbirinin atası olmayan paralel düğümler), `too_large`; hiçbirine uymayan motor reddi `engine` bulgusu olarak motor mesajıyla gelir (sessiz kalmaz). Katman/sıra yerleşimi belirleyici. IPC `plan.view` (READ, girdi doğrulamalı, worker/dosya oluşturmaz). `desktop/src/dag.ts`: konum, klavye gezinmesi (oklar, Home/End), kaçışlı belirleyici SVG.
- Test: `tests.workflows.test_dag_view` 10 OK (geçerli plan katmanları; döngü düğüm+kenar vurgusu; bilinmeyen kenarlar; paralel çakışma işaretli, sıralı aynı dosya serbest; yinelenen ad ve açıklanamayan motor reddi sessiz değil; çöp spec'ler çökmez; **görünüm kararı = motor kararı** 5 fikstürde; 96 düğüm / ≥200 kenar; belirleyicilik; `plan.view` BAD_REQUEST + hiç run oluşmaz). `desktop npm run check` tsc + 12/12 (klavye gezinmesi, SVG determinizmi ve kaçışlama, vurgulu düğüm/kenar, 100 düğüm). `tests.engine.test_local_api` TS sözleşme eşlemesi yeşil.
- Kalan risk: "görsel snapshot" **SVG metin** snapshot'ıdır, piksel ekran görüntüsü değil. `dag.ts` henüz React ekranına bağlı değil ve renderer'ın motora IPC çağrısı yapan yolu yok (B3-04.03+ ve B3-01 köprüsü). Bütçe/bekleyen insan eylemi düğüm başına yalnız bütçe alanları olarak taşınıyor; bekleyen onay gösterimi B3-05'e bağlı.

## B3-04.03 — Taslak düzenleme ve sunucu tarafı revalidate (6 Kasım 2026)

- Kapsam: `workflows/plan_draft.py`. UI yalnızca bir revizyona karşı düzenleme **önerir** (`set_lane` [after/task/worker/ownership/forbidden], `set_phase_after`, `rename_lane`, ≤50); motor kopyaya uygular ve **tüm planı** koordinatörün kendi doğrulayıcısıyla (`coordinator._validate` = DAG + proje şeması + yetki anahtarı reddi) ve kurulu/destekli ajan denetimiyle yeniden doğrular, imzalı yeni revizyon yazar (içerik SHA-256). Geçersiz plan düzeltilsin diye saklanır (`valid=false` + motor nedeni) ama başlatılamaz. Başlatma ayrı eylem: en son revizyon + içerik hash'inin operatör tarafından geri yazılması + TASK yetkisi; imzalı taslaktan yeniden doğrulanır; "started" işareti başlatmadan **önce** yazılır (tam bir kez). IPC `plan.create/edit/start` (TASK; `plan.start` yalnız HUMAN/RENDERER, MCP/WORKER/CHILD reddedilir).
- Test: `tests.workflows.test_plan_draft` 10 OK: geçerli düzenleme yeni revizyon+hash; 7 geçersiz düzenleme (döngü, paralel çakışma, bilinmeyen bağımlılık, kimlik çakışması, kötü slug, **rol kullanılamaz** ("Role unavailable"), sahiplik yok) kaydedilir ama invalid; 10 bozuk düzenleme `ValueError` ve **hiçbir revizyon kaydetmez**; spekülatif plan (`auto_apply`, `command` anahtarı) invalid; bayat revizyon reddi ve 6 eşzamanlı düzenlemede tam 1 kazanan; geçersiz/bayat/yanlış-hash/WORKER/CHILD başlatma → **başlatıcı hiç çağrılmaz** ve proje/run dizini oluşmaz; başlatma tam bir kez, sonrasında taslak donar; elle değiştirilen taslak dosyası `Evidence tampered`; kimlik doğrulama; IPC akışı (geçersiz revizyonda start reddi, MCP/WORKER FORBIDDEN, hiçbir proje başlamadı). `test_local_api` (yetki matrisi + TS sözleşmesi) ve `desktop npm run check` yeşil.
- Kalan risk: başlatma testleri başlatıcıyı taklit eder (gerçek `project.start_project` ve çalışan süreçler B3-04.04 uçtan uca günlüğünde); başlatma çağrısı çökerse taslak "started" kalır ve yeniden başlatılmaz (yeni taslak gerekir — bilinçli, çift başlatmayı önlemek için). Düzenleme kilidi dosya tabanlıdır (aynı makine); çökmüş bir süreçten kalan `.lock` 5 sn sonra "busy" verir, otomatik temizlenmez.

## B3-04.04 — Başlat, durdur, devam ettir ve durum açıklaması (6 Kasım 2026)

- Kapsam: `workflows/project_control.py` (durum makinesi `project.py`'de kalır): `status` (durum + Türkçe açıklama + `retryable` + `next_action`; bilinmeyen durum sağlıklı gösterilmez), `cancel` (idempotent: ikinci çağrı `repeat: true`, tek geçiş, tek denetim olayı), `resume` (bitmiş/çalışan/bayat kontrol noktalı proje `project.py`'nin kendi kurallarıyla reddedilir; plan **rolü/ajanı artık kurulu değilse** hiçbir şey başlatılmadan reddedilir). Kabul edilen her geçiş `engine/journal.py`'ye `project.cancel_requested` / `project.resumed` olarak yazılır (operation_id = IPC istek kimliği). IPC: `project.status` (READ), `project.cancel`/`project.resume` (TASK; WORKER/CHILD FORBIDDEN).
- Test: `tests.workflows.test_project_control` 9 OK (durum açıklamaları; cancel idempotent+tek denetim olayı+bitmişte red; resume tam bir kez [ikinci tıklama "already running", tek süpervizör, tek olay]; rol eksik → sıfır süpervizör ve olay yok; bayat kontrol noktası → sıfır süpervizör; kötü kimlikler; IPC create→resume→resume→cancel akışı; yetkisiz origin hiçbir şey değiştirmez; hata kodları).
- Gerçek e2e (taklit yok, `project.start_project` gerçek ayrık süpervizör süreci, özel [LLM'siz] işçi, geçici dizin, 6 Kasım 2026): `START {'status': 'started', 'pid': …}` → `project.cancel` canlı süpervizöre → `cancel_requested repeat=False` → tekrar `repeat=True` → durum izlemede "İptal istendi; süpervizör kapanışı bekleniyor." → `cancelled`, `alive=false`, kaynak dosya `old` (değişmedi) → bitmiş projede `cancel`/`resume` → `ENGINE_ERROR "Project is cancelled; nothing to cancel/resume"`. İkinci koşu iptal edilmeden bırakıldı: süpervizör gerçekten çalıştı ve `blocked` ("lanes not approved: one: FAILED/unknown") ile bitti, açıklama IPC'den okundu.
- Kalan risk: **tam başarı yolunu (create→plan.start→completed→resume) gerçek süpervizörle göstermedik**: bir lane'in onaylanması master inceleyicisi (LLM) ister; bu, token harcayan koşuyu onayınızla yaptığımızda B3-03.03 ile birlikte yapılacak. Birim testlerde `_spawn` taklittir. "Scheduling queue" gösterimi yok (tek proje başına tek süpervizör; kuyruk modeli B3-05+). `plan.start` → `project.start_project` bağı B3-04.03 testlerinde taklit başlatıcıyla.

## B3-05.01 — Evidence/Diff/PR-CI okuma modeli (6 Kasım 2026)

- Kod: `engine/review_model.py` (`review_dto`, `parse_patch`), IPC `review.view` (READ; tüm origin'ler okur). Tek doğruluk kaynağı: `interfaces/evidence_view.view` (redaksiyon + PR/CI) ve `runner.check_result` (tamper, bayat, çakışma, kabul, tester ve MAF bağı). Yeni karar mantığı yok; yalnız `blockers` (onaylanamaz) ve `warnings` (görünür ama engellemez) listesi. `approvable = blockers boş`.
- Gösterilenler: patch sha256 (diskteki ve imzalı), dosya listesi (+/- satır, symlink, ikili, mod değişimi, kapsam sorunu), proje parmak izi (koşu anı / şimdi), testler, reviewer, politika (ownership/forbidden), PR/CI, `checked_at` zaman damgası, 200 KB sınırlı ve secret-redakte diff önizlemesi.
- Engelleyiciler: `evidence_unreadable`, `check_failed`, `already_applied`, `patch_hash_mismatch`, `changed_files_mismatch`, `empty_patch`, `diff_too_large` (>2 MB), `symlink`, `outside_project` (.., mutlak, sürücü, .git), `forbidden`, `outside_ownership`, `no_tests`, `delivery_tampered`, `ci_not_green`. Uyarılar: `no_pr`, `ci_missing` (bilinmeyen ≠ geçti), `binary`, `mode_change`, `secret_redacted`.
- Test (gerçek koşu, model çağrısı yok, özel worker): `tests.engine.test_review_model` 13 OK. Doğrulanan: doğrulanmış koşu approvable + alanlar; okuma sıfır yazma (run dizini ve repo aynı); imza kurcalama; imzadan sonra patch değiştirme (hash + symlink); bayat HEAD; applied; 2 MB üstü patch + sınırlı önizleme; sızan secret gizli + uyarı; kurcalı PR makbuzu / CI eksik / CI başarısız; bilinmeyen koşu çökmez; `parse_patch` kapsam/symlink/ikili/mod/çöp girdi; IPC her origin okur, kötü id BAD_REQUEST.
- Kalan risk: "UI snapshot" henüz yok (React ekranı bağlı değil; DTO metin/JSON). Gerçek GitHub PR/CI yalnız makbuz dosyasından okunur, canlı sorgu yok. Symlink tespiti patch metninden (mod 120000); çalışma ağacındaki mevcut symlink'in üzerinden geçen yol `check_result`/git apply'a bırakılır.
- Tam paket (6 Kasım 2026): 774 test, 1 kırmızı: `test_windows_processes.SpawnSitesTests` — B3-03.02'den kalan gerçek hata: `agent_adapters._run` doğrudan `subprocess.run` çağırıyordu (Windows'ta `--help` çağrısı konsol penceresi açardı). `winproc.run`'a alındı; `test_windows_processes` + `test_agent_adapters` + `test_review_model` 33 OK.

## B3-05.02 — Gerçek kullanıcı onayı için native authority (6 Kasım 2026)

- Kod: `engine/approval.py` (`open_challenge` TASK, `decide`/`consume`/`apply_with_grant` PRIVILEGED = yalnız HUMAN), IPC `approval.open/decide/apply`, `local_api.serve(human=True)` + `_ipc --human` (yalnız `hello`, `engine.manifest`, `review.view`, `approval.decide`, `approval.apply`; `RESPECTED_ORCH_CHILD=1` olan süreç HUMAN iddia etse de CHILD olur). Rust: `desktop/src-tauri/src/approval.rs` (`request_apply`, `Pair` = renderer-origin + human-origin iki ayrı motor süreci, ayrı oturum tokenı; `NativeDialog` = `MessageBoxW`, sahipsiz, topmost, varsayılan düğme Hayır), Tauri komutu `request_apply` (renderer yalnız *ister*; token ve human bağlantısı renderer'a hiç verilmez).
- Protokol: sorgu → motor `approval.open` yalnız approvable koşuya meydan okuma verir (`binding` = sha256(run, patch, proje parmak izi, challenge id)) → diyalog metni yalnız motorun meydan okumasından kurulur (kontrol karakterleri atılır, 12 dosya) → Evet ise `decide`: önce `O_EXCL` ile claim, sonra süre (120 sn), binding, yeniden `review_dto` (patch/parmak izi değişmedi mi) → tek kullanımlık 256-bit token (diskte yalnız sha256 adı; token saklanmaz) → `apply_with_grant`: token yakılır (`O_EXCL`), koşu/süre/yeniden doğrulama, sonra motorun kendi `apply_task`. Her hata claim'i yakar: yeniden onay gerekir.
- Python testleri (gerçek koşular, model çağrısı yok): `tests.engine.test_approval` 14 OK — tek meşru yol bir kez uygular, ikinci kullanım "already used"; RENDERER/MCP/WORKER/CHILD decide ve apply yapamaz (FORBIDDEN, claim bile oluşmaz); IPC'den renderer/MCP `open` yapabilir `decide/apply` FORBIDDEN; human bağlantısı yalnız kendi komutlarını açar, ORCH_CHILD insan sayılmaz; onaylanamaz (kurcalı) koşuya challenge yok; deny yan etkisiz ve sonradan approve'a çevrilemez; yanlış binding ("yanlış pencere") reddedilir ve challenge yanar; diyalog açıkken repo değişirse grant yok; karar–apply arası değişirse sıfır apply; süresi dolan challenge ve grant; başka koşunun tokenı / sahte token; 8 eşzamanlı decide → 1 kazanan; 6 eşzamanlı apply → 1 uygulanan; token diskte yok.
- Mutasyon: `_claim` her zaman True yapıldığında yarış/replay/apply testleri kırılıyor (4/4 test kırıldı) → korumaları gerçekten bu testler tutuyor.
- Rust testleri: `cargo test --lib` 15 OK (8 yeni): Evet→open(asker)+decide(human)+apply(human); Hayır→apply yok, deny gider; reddedilen challenge'da diyalog hiç gösterilmez; motor reddi yutulmaz; aynı anda tek diyalog (Busy) ve her sonuçtan sonra kapı yeniden açılır; diyalog metni sahte satır içeremez; taşıma hatasında hiçbir şey uygulanmaz; **gerçek iki motor süreci**: asker bağlantısı `approval.decide` → FORBIDDEN, human bağlantısı yalnız kendi komutlarında ENGINE_ERROR, diğerlerinde FORBIDDEN.
- Diğer: `engine_connector::Connection::raw` (motor reddini veri olarak döndürür), `tests.engine.test_local_api/test_ipc_serve/test_authority` + yeni testler birlikte 48 OK; `npm run check` (tsc + 12 test) OK.
- Kalan risk / doğrulanmayanlar: (1) **`MessageBoxW` hiç gerçek insanla tıklanmadı**; derlendi, mantık sahte Presence ile test edildi. (2) React ekranı `request_apply`'ı çağırmıyor (UI bağlı değil). (3) Aynı kullanıcı oturumunda sandbox dışı kötü amaçlı yazılım (girdi enjeksiyonu, süreç belleği) kapsam dışı. (4) Onay izi dosyaları (`approvals/*.decision.json`, imzalı) var ama olay günlüğüne (journal) yazılmıyor. (5) Apply anındaki TOCTOU (tam repo digest, kopya apply koruması) B3-05.03'ün işi; burada yalnız `consume` yeniden doğrular ve `apply_task`'ın kendi `check_result`/`git apply --check` kontrolü çalışır.

## B3-05.03 — TOCTOU-safe apply ve işlem sonucu (6 Kasım 2026)

- Kod: `runner.apply_task` sertleştirildi (CLI, supervisor ve `approval.apply_with_grant` aynı yolu kullanır): (1) `applying` talebi `O_EXCL` ile alınır — iki çağrı asla birlikte yazamaz; (2) `check_result` (tamper/bayat/çakışma/kabul/MAF) yeniden çalışır; (3) patch `review_model.parse_patch` ile yeniden taranır: kapsam dışı, forbidden, `.git`, symlink → red (geçerli imzayla bile); (4) **tam proje parmak izi** `git apply --check` öncesi ve sonrası alınır, aralarında *herhangi* değişiklik (patch'in hâlâ uyacağı bir kullanıcı düzenlemesi dahil) → red, sıfır yazma; (5) `git apply` (hepsi ya da hiç, indeks/commit yok) + `git apply --reverse --check` ile patch'in gerçekten uygulandığı doğrulanır; (6) `applied.json`: önce/sonra parmak izi, `committed=false`, `staged=false`, çalışan **geri alma** komutu; (7) başarısızlıkta imzalı `apply-failed.json` (neden, önce/sonra parmak izi, `project_changed`) ve yazma başlamadıysa/proje değişmediyse talep bırakılır (yeniden denenebilir); yazıdan sonra çökme olursa talep kalır → insan bakmadan ikinci yazma yok.
- Test: `tests.engine.test_apply_hardening` 7 OK (gerçek koşular, gerçek git, model çağrısı yok): başarı = tek, indekslenmemiş, commit'siz değişiklik (`git status`: `M calculator.py`, HEAD aynı, `diff --cached` boş) + `undo` komutu gerçekten eski içeriği getirir; kontrol ile apply arasında kullanıcı düzenlemesi (patch bağlamı hâlâ uyuyor) → "changed while the patch was being checked", kullanıcının dosyası dokunulmamış, `applied.json` yok, talep bırakıldı; 8 eşzamanlı tıklama → 1 applied + 7 refused, tek diff; başarısız (bayat) apply → repo/indeks/HEAD karması (`tree_hash`) önce=sonra, `apply-failed.json` `project_changed=false`; geçerli imzalı ama kapsam dışı / symlink / `.git/hooks` patch'leri reddedilir (3 durum, karma değişmez); iptal edilmiş koşu uygulanamaz, tamamlanmış koşuya geç `cancel` etkisiz; `applied.json` yazılırken çökme → dosya bir kez yazıldı ve ikinci apply "did not finish" ile durdu.
- Eski invariants: `test_review_apply_invariants` (12+1) hâlâ yeşil; yalnız `test_04` beklenen istisna kümesine `ValueError` eklendi (yarış artık git'ten önce, daha erken yakalanıyor; aynı değişmez: sıfır yazma, kullanıcı içeriği korunur).
- **Mutasyon testi** (kaynak geçici bozuldu, sonra aynen geri yüklendi, `cmp` ile doğrulandı): talep kaldırıldı → 2 test kırıldı; parmak izi yeniden kontrolü kaldırıldı → kırıldı; kapsam/symlink taraması kaldırıldı → kırıldı. 3/3 mutant öldü.
- Kalan risk: parmak izi karşılaştırması ile `git apply` arasında milisaniyelik bir pencere teorik olarak kalır (dosya sistemi kilidi yok); `git apply` hepsi-ya-hiç olduğu için sonuç "kullanıcının eşzamanlı düzenlemesi + patch" olabilir ve bu yalnızca bu pencerede mümkündür. Non-git projelerde `--reverse --check` ve `git apply` yoktur (apply zaten git ister). Sert çökmeden kalan `applying` dosyasını temizleyen bir "kurtarma" komutu yok; kullanıcıya bırakılır.
- Tam paket (B3-05.02+.03 sonrası, 6 Kasım 2026): 795 test, 2 atlandı, 1 kırmızı: `tests.desktop.test_shell_policy` — renderer'ın çağırabileceği Tauri komut kümesini sabitleyen politika testi `request_apply` eklenince (bilinçli genişleme) kırıldı. Test üç komuta güncellendi ve `request_apply` imzasının yalnız `run_id` aldığını (token/decision/binding/challenge parametresi yok) ayrıca doğruluyor; o dosya yeniden çalıştırıldı: 5 OK. Diğer 794 test tam paket koşusunda yeşildi (güncellemeden sonra tam paket yeniden koşulmadı).

## B3-05.04 — Onay merkezi uçtan uca saldırı testi (6 Kasım 2026)

- Test: `tests/engine/test_approval_attacks.py` — 19 senaryo, gerçek stdio protokolüyle ayrı süreçler (renderer `_ipc`, native `_ipc --human`, ayrı oturum tokenları). Her saldırıda red **ve** proje (HEAD + indeks + durum + dosya baytı) birebir aynı. 18 saldırgan (yetkisiz origin ×3, kimlik doğrulamasız, yanlış/geçersiz run_id, challenge sonrası patch değişimi, imzalı ama kapsam dışı/symlink/`..` patch, istek kimliği çakışması, karar tekrarı, token tekrarı, sahte/biçimsiz token ve kimlikler, başka challenge'ın binding'i, başka koşunun tokenı, aşırı büyük/çöp istek, ret'in onaya çevrilmesi, kararla apply arası çökme, başarısız apply'da yanan token'ın tekrar kullanımı) + 1 meşru yol (tam bir kez uygular, ikinci denemede red, veri kökünde token/oturum sırrı yok, stderr boş).
- Sonuç: kaynak 19/19, **paketli exe** 19/19 (taze `build_dist.py`, exe SHA-256 `d7a3cd84…396b7`), commit `9bf5935`. Rapor: `docs/evidence/b3-05-04-attack-run.md`.
- Mutasyon: renderer'a PRIVILEGED → 01/02 kırıldı; binding kontrolü kaldırıldı → 13 kırıldı; token `.used` talebi kaldırıldı → 11 hayatta kaldı (apply'ın kendi `applied.json` koruması yakaladı: iç içe savunma), bu yüzden doğrudan ölçen 19 eklendi → artık kırılıyor (mutant ile token repo eski haline getirilince yamayı **gerçekten tekrar uyguladı**).
- Kalan risk: gerçek insan tıklaması ve native diyalog bu koşuda yok; **B3-03.04 bağımlılığı yapılmadı** (oturum içi terminal input injection / spoofed approval kapsam dışı, o kartta kanıtlanacak); React ekranı bağlı değil.

## B3-06.01 — Event timeline ve arama/filtre (6 Kasım 2026)

- Kod: `engine/activity.py` (`timeline`, `stage_of`, `clean`), `Journal.scan` (kayıtları liste kurmadan akıtır; `replay` buna dayanır), IPC `activity.list` (READ; tüm origin'ler okur; journal yoksa ENGINE_ERROR). Tek kaynak journal; yeni depo yok. Sayfalama `seq` imleciyle (rotasyonda bile monoton), limit en çok 200. Süzgeçler: run, op (operation correlation), aşama (queued/running/review/approval/done/failed/cancelled/other/unknown), tür (tam ya da `önek.*`), ajan, serbest metin.
- Güvenlik/dürüstlük: bilinmeyen tür atılmaz, `stage:"unknown"` olarak ve temizlenmiş yük ile gösterilir; her dize ANSI CSI/OSC dizilerinden ve kontrol karakterlerinden arındırılır, 300 karakter / 40 öğe sınırı; sırlar yazımda `journal.mask` ile maskelidir ve okumada da görünmez; sıra dışı zaman damgası `out_of_order` ile işaretlenir ama sıra `seq`'dir; rotasyonla yok olan olaylar `missing_before: true` ile açıkça bildirilir; bozuk kuyruk `corrupt: true` ve güvenilir önek döner.
- Test: `tests.engine.test_activity` 10 OK (gerçek journal dosyaları): 10.000 olay 50 sayfada eksiksiz, tekrarsız, sıralı; filtreler; bilinmeyen tür + düşman yük; sır maskesi; sıra dışı ts; rotasyon; bozuk kuyruk; kötü imleç/limit; boş journal; IPC her origin okur, kötü imleç BAD_REQUEST. İlgili `test_journal/test_local_api/test_ipc_serve/test_shell_policy` 30 OK, `npm run check` 12 OK.
- Ölçüm (10.000 olay, bu makine): ilk sayfa 11 ms, son sayfa 65 ms, eşleşmeyen metin aramasında tam tarama 205 ms.
- Test sırasında yakalanan gerçek hata: temizleyici önce tek `\x1b`'yi silip `[31m` metnini bırakıyordu; desen tam CSI/OSC dizilerini önce yakalayacak şekilde düzeltildi.
- Kalan risk: bugün journal'a yazan üretici az (proje denetimi, rotasyon) — runner/worker olayları henüz journal'a yazılmıyor, bu yüzden "queued/running/review" aşamaları anahtar kelimeyle çıkarılır ve gerçek koşu olayları ekleninceye kadar timeline yalnız var olanı gösterir. "UI snapshot" yok (React bağlı değil). Her sayfa dosyayı baştan okur (O(n)); 10k'da ms mertebesinde, çok daha büyük journal için indeks gerekir (rotasyon bunu sınırlar).

## B3-06.02 — Dosya diff/çıktı/kanıt inspector (6 Kasım 2026)

- Kod: `engine/artifact_view.py` (`list_artifacts`, `read_chunk`), IPC `artifact.list` / `artifact.read` (READ; tüm origin'ler). UI bir yol vermez; yalnız motorun o koşu için listelediği ad (`worker.patch`, `result.json`, `*.log`, `artifacts/<ad>`) açılır. Liste: yalnız `[A-Za-z0-9._-]` adlı, bilinen uzantılı (.json/.log/.patch/.txt/.md/görsel) düz dosyalar; `.` ile başlayan, `applying` gibi kontrol dosyaları ve bağlar yok. Okuma: en çok 64 KB parça, `safe_path` (symlink/reparse/junction red) + çözümlenmiş yolun koşu dizini içinde olması, ikili/görsel içerik gönderilmez (`binary:true, content:null`), satır sonunda kesilir. Redaksiyon: parça sınırının iki yanından 512 bayt bakan, uzunluğu koruyan bayt maskeleme (api_key/token/password/secret/Bearer atamaları, sk-/ghp_/AKIA değerleri, ortam sırları) + `evidence_view._clean` + `activity.clean` (ANSI CSI/OSC, kontrol karakteri). Denetim: her okuma journal'a `artifact.read` (run, ad, offset, bayt, boyut, **dosyanın sha256'sı**) yazar; 32 MB üstü dosyada özet `null` (tahmin edilmez).
- Test: `tests.engine.test_artifact_view` 12 test, 11 OK + 1 atlandı (aşağıda). Gerçek koşu dosyaları: liste yalnız kanıtı gösterir; patch parça parça okununca baytı baytına aynı ve özet doğru, journal'da denetim kaydı; 14 geçiş/mutlak/biçimsiz/listede olmayan ad ve 4 kötü run kimliği red; **gerçek junction** (`mklink /J`, `artifacts` → dış klasör) hiçbir şey sızdırmaz; ANSI/OSC/kontrol kodları temizlenir; 7–1000 baytlık parçalarla okunan gizli anahtar hiçbir parça sınırında görünmez; 5 MB dosya tek istekte en çok 64 KB döner; ikili ve görsel dosya içerik vermez; kötü offset/uzunluk; IPC canlı journal'a denetim yazar. Birlikte `test_activity/local_api/ipc_serve/journal/shell_policy` dahil 52 test OK, `npm run check` 12 OK.
- Mutasyon: sınır arama kapatıldı → kırıldı; kontrol temizliği kapatıldı → kırıldı; ad beyaz listesi kapatıldı → kırıldı; junction korumaları (okuma tarafı iki katman / listeleme katmanı / hepsi) kapatıldı → 3/3 kırıldı (tek katman kapalıyken diğeri yakalıyordu, bu iç içe savunmadır). İlk koşuda sır sınır testi gerçekten kırmızıydı (anahtar adı ile değeri farklı parçalara düşüyordu): bayt düzeyinde bakışla düzeltildi.
- Atlanan: `test_file_swapped_for_a_link_after_listing_is_refused` — bu kullanıcının sembolik bağ ayrıcalığı yok (WinError 1314); **gerçek symlink bu makinede denenmedi**, yalnız junction (aynı reparse-point denetimi `safe_path` üzerinden). Symlink ayrıcalıklı bir CI/geliştirici makinesinde koşturulmalı.
- Kalan risk: 512 bayttan uzun tek bir gizli değer sınırdan kesilirse kuyruğu görünebilir; run dizini dışındaki kanıt (Hub makbuzları vb.) bu görünüme dahil değil; UI (React) bağlı değil; "tam kanıt bağlantısı" yalnız `result.json` listesi olarak var.

## B3-07.01 — CLI binary/sürüm/auth keşfi (6 Kasım 2026)

- Kod: `engine/agent_discovery.py` (`discover`, `discover_all`, `classify`, `ledger`, `Probe`), IPC `agents.discover` (READ; WORKER/CHILD FORBIDDEN). `agent_adapters.verify` üzerine kurulu; dört durum: `unavailable` / `installed` / `configured` / `verified`, her biri `reason` ile (`not_found`, `binary_missing_on_disk`, `renamed_executable`, `timeout`, `enterprise_policy`, `version_probe_failed`, `unexpected_output`, `auth_required`, `auth_unknown`, …). `verified` = oturum açık + sohbet bayrağı yardımda; her sonuç `proof` alanında bunun gerçek model oturumu olmadığını söyler. Probe'lar yalnız salt-okunur komutlar çalıştırır, `scrub_environment` ile anahtar/token/sır adlı ortam değişkenleri çıkarılmış olarak, stdin kapalı, zaman aşımlı; ağ gerektirmez. opencode'un saklı kimlik bilgisi en çok `configured` verir. 30 sn önbellek yalnız gerçek makine görünümü için (sahte probe/which asla önbelleğe girmez).
- Test: `tests.engine.test_agent_discovery` 18 OK (sahte CLI çıktıları + gerçek süreç): verified; binary yok; taşınmış/silinmiş yol; yeniden adlandırılmış yürütülebilir; zaman aşımı; beklenmeyen/boş/hatalı sürüm çıktısı; oturum yok/okunamıyor; kurumsal politika; eksik bayrak ve eski sürüm → configured; opencode saklı kimlik → configured; custom probe etmez; antigravity `agy` adıyla bulunur; her sonuç kapalı kümeden durum + gerekçe; **gerçek süreçte** probe ortamında `OPENAI_API_KEY`/`*_TOKEN` yok; asılı CLI 1 sn'de zaman aşımı; olmayan exe istisna değil değer döner; IPC. Birlikte `test_local_api/test_agent_adapters/test_windows_processes/test_shell_policy` 58 OK.
- Mutasyon 5/5 öldü: yeniden adlandırma denetimi, sürüm numarası denetimi, ortam temizliği, opencode sınırı, politika denetimi kapatılınca ilgili test kırıldı.
- Testin yakaladığı gerçek hata: "hello world" gibi sürüm numarası olmayan çıktı `unpinned` sayılıp **verified** çıkıyordu; sürüm ayrıştırılamıyorsa artık `unavailable / unexpected_output`.
- Gerçek makinede bulunan B3-03.01 hatası: `agy` kurulu (`AppData/Local/agy/bin`) iken matris `antigravity` adını arayıp "yok" diyordu; ikili adları `["agy","antigravity"]` yapıldı (`test_agent_adapters` 9 OK). Gerçek defter: `docs/evidence/agent-compat-ledger-2026-11-06.txt` (codex, claude, cursor verified; opencode configured; antigravity installed/auth_unknown; custom configured).
- Kalan risk: sırsız ortamda yalnız ortam değişkeniyle oturum açan bir CLI `installed/auth_required` görünür (bilerek: sır okumamak öncelikli); antigravity'nin oturum durumunu okuyan salt-okunur bir komutu doğrulanmadı; enterprise policy tespiti çıktı metni desenidir (gerçek bir kurumsal ortamda denenmedi); React ekranı bağlı değil.

## B3-07.02 — Role, tool, profile ayrımı ve düzenleme (6 Kasım 2026)

- Kod: `workflows/role_editor.py` (`view`, `plan_edit`), IPC `roles.view` ve `roles.plan_edit` (ikisi de READ; **hiçbir şey yazmaz**). `view`: her rol için atama + `origin` (`default_roles` / `default_worker` / `default_reviewer_profile` / yok), araç durumu (B3-07.01 keşfinden; keşif verilmezse `tool_unchecked`, asla "tamam" değil), yedekler (fallbacks) ve uyarılar (`tool_unavailable`, `tool_not_verified`, `stale_version`, `profile_blocked`, `fallback_changes_tool`, `tool_cannot_write/review`, `same_profile_as_implementer` / `independence_violation`), ayrıca otomatik **öneri** ayrı alanda (`applied:false`); öneri atamanın yerine geçmez, boş role de yazılmaz. `plan_edit`: `set`/`clear` düzenlemelerini kopya üzerinde doğrular (`roles.normalize`, engelli profil, araç zorunlu, en çok 5 yedek, bağımsız inceleme kuralı), **fark** (added/changed/removed) ve aday `default_roles` metnini döndürür; uygulama operatörün normal ayar çağrısıyla. `source`/`fallback_of`/`reason` alanları düzenlemeyle yazılamaz. `agent_discovery` sonucuna `version_state` eklendi.
- Test: `tests.workflows.test_role_editor` 16 OK: köken etiketleri; araç durum uyarıları; keşifsiz hiçbir şey doğrulanmış sayılmaz; yedek görünürlüğü ve araç değiştirme riski; bağımsızlık ihlali yalnız zorunluyken; engelli profil; öneri yan yana ama uygulanmaz; fark yalnız değişeni gösterir, dokunulmayan roller baytı baytına aynı; geçersiz düzenlemeler (9 tür) gerekçeli ve aday yok; provenance sahteciliği 3 yolla reddedilir; bağımsızlık kuralı sonuç plana uygulanır; düzenleme sınırı; **öncelik değişmedi** (görev isteği > kayıtlı varsayılan > auto; öneri kullanıcının seçimini değiştirmez); IPC salt-okunur (ayar dosyası baytı aynı), WORKER/CHILD FORBIDDEN. Birlikte `test_local_api/test_agent_discovery/test_shell_policy` 54 OK, `npm run check` 12 OK.
- Mutasyon 6/6 öldü: provenance denetimi, araç zorunluluğu, bağımsızlık denetimi, engelli profil denetimi, öneriyi "uygulandı" işaretleme, kullanılamayan araç uyarısı kapatılınca ilgili test kırıldı.
- Yan düzeltme: `test_typescript_contract_matches_python` komut adı deseni alt çizgiyi (`roles.plan_edit`) görmüyordu; `[a-z._]+` yapıldı.
- Kalan risk: bayat sürüm yalnız `older_than_verified` eşiğiyle (kart kendi sürüm sabitleri olan CLI'lar için); `roles.view` keşif sonuçlarını yalnız `discover:true` ile alır (süreç başlatır), aksi halde araç durumu "bilinmiyor"; Hub'ın mevcut ayar ekranı ile bu düzenleyicinin aynı ayarı eşzamanlı yazması durumunda son yazan kazanır (aday ayar tam `default_roles` metnidir); React ekranı bağlı değil.

## B3-07.03 — Canlı yetenek/uyumluluk matrisi (6-7 Kasım 2026)

- Kod: `engine/capability_matrix.py` (`build`, `to_markdown`), IPC `capabilities.matrix` (READ; 30 sn önbellek yalnız gerçek makine görünümü için). Her ajan × 6 kip (terminal, chat, interactive_input, usage, resume, model_switch); her hücre `verified` / `unverified` (gerekçeli: "belgelendi, yoklanmadı", "iddia edildi ama CLI'da yok", "bayrak var ama araç installed/configured") / `unsupported`, ayrıca `version`, `checked_at` ve `enabled`. **`enabled` yalnız `verified` ise doğrudur**; araç oturum açık değilse, sürüm eskiyse veya yardım metninde bayrak yoksa hiçbir düğme açılmaz. Terminal her araç için `unsupported` (üretim PTY aracısı yok). `model_switch` CLI'nin kendi `--help` çıktısında `--model` aranarak yoklanır. Çıktı: `to_markdown` ile sürüm artefaktı `docs/evidence/capability-matrix-2026-11-06.md` (gerçek makine; codex/claude/cursor chat+resume+model V; opencode yalnız configured → hepsi ?; antigravity installed; custom kapalı).
- Düzeltme (B3-03.01 kalıntısı): bulunan ama yeteneği tanımsız araçlar (antigravity) "binary not found" gerekçesi gösteriyordu; artık "no adapter contract for this capability yet".
- Test: `tests.engine.test_capability_matrix` 9 OK: doğrulanmış araç yalnız kendi yardımının kanıtladığını açar (interactive_input/usage "yoklanmadı" kalır); sahte yetenek iddiası unverified + gerekçe; eski sürüm hiçbir şeyi açmaz; oturum açık değilken her kip kapalı; hiçbir şey kurulu değilken (çevrimdışı) matris tam ve hepsi kapalı; 4 senaryoda değişmez (enabled ⇔ verified, her hücrede gerekçe ve zaman, terminal asla açık değil); markdown artefaktı doğrulanmışa gerekçe yazmaz; sahte matris önbelleğe girmez, IPC salt-okunur ve WORKER FORBIDDEN. Birlikte `test_local_api/test_agent_discovery/test_role_editor/test_shell_policy/test_windows_processes` 74 OK.
- Mutasyon 4/4 öldü (enabled kuralı, oturum şartı, "source"un verified sayılması, model bayrağı denetimi).
- Not: `tests.engine.test_agent_adapters` (canlı CLI sondaları, ~70 sn) bir koşuda 1 başarısız verdi, hemen yeniden koşuda 9/9 OK; yük altında zaman aşımına bağlı olduğu düşünülüyor, nedeni ayrıca izole edilmedi.
- Kalan risk: "verified" yine yalnız bayrağın yardımda olması + oturum açık olması demektir, gerçek model oturumu değildir (B3-03.03 sonrası güçlenecek); `usage`/`interactive_input` hiçbir araçta yoklanmış değil (kasıtlı: "unverified"); önbellek 30 sn; React ekranı bağlı değil.

## B3-08.01 — Desteklenen istemcilerin config yolu matrisi (7 Kasım 2026)

- Kod: `engine/capabilities/paths.py` (`matrix`, `scan`, hata sınıfları `ERROR_CLASSES`), IPC `capabilities.scan` (READ; MCP/RENDERER okur, WORKER/CHILD FORBIDDEN; `project_root` verilirse mutlak ve var olan klasör olmalı). Matris: claude-code (`~/.claude.json` mcpServers, `~/.claude/skills`), codex (`~/.codex/config.toml` mcp_servers, `~/.codex/skills`), cursor (`~/.cursor/mcp.json`, `~/.cursor/skills-cursor`), opencode (`~/.config/opencode/opencode.json` mcp), paylaşılan `~/.agents/skills`, proje kapsamı (`.mcp.json`, `.claude/skills`, `.codex/config.toml`, `.cursor/mcp.json`, `opencode.json`). Her satırın `source` alanı yolun nereden geldiğini söyler: `code` (kayıt kodunun zaten yazdığı yer: `interfaces/integrations.py`), `observed` (bu makinede görüldü), `documented` (istemci belgesi, burada görülmedi), `unconfirmed`. **Antigravity'nin MCP yapılandırma dosyası doğrulanamadı** (`~/.gemini/antigravity*` altında yalnız sunucu klasörleri ve `mcp_oauth_tokens.json` var); tahmin edilmedi, `location_unknown`.
- Tarama yalnız bakar: var mı, okunabilir/ayrıştırılabilir mi, boyut, SHA-256, üst düzey anahtar ve giriş **adları**; değerler (token'ların durduğu yer) dönmez. Beceri klasörlerinde yalnız güvenli adlı alt klasörler ve `SKILL.md` varlığı. Hata sınıfları: `not_found`, `unreadable`, `link_refused`, `outside_root`, `too_large` (>2 MB), `sensitive_file` (token/oauth/credential… adlı dosya hiç okunmaz), `bad_encoding`, `malformed_json`, `malformed_toml`, `unsupported_shape`, `location_unknown`. Kök (ev/proje) altındaki her bileşen link/reparse için lstat ile denetlenir; üstteki profil bağlantısı engel değildir. Modül `subprocess`/yazma/`open(` içermez (kaynak testi).
- Test: `tests.engine.test_capability_paths` 14 OK: matris kapsamı ve dürüst kaynaklar; geçerli yapılandırmalar yalnız adları verir (gizli değer, komut ve env adı çıktıda yok); yokluk hata değildir; bozuk JSON/TOML/şekil/BOM/Unicode (`kullanıcı-ünlü`, `proje-çalışma`, `ünlü-sunucu`) adlandırılmış sınıfla döner ve istisna atmaz; 2 MB üstü ve duyarlı dosya okunmaz (okuma çağrılırsa test düşer); izin hatası sınıf olarak döner; **gerçek junction** `.codex` → dış klasör `link_refused` ve dışarıdaki giriş çıktıda yok; bağlı beceri klasörü, gizli ve tuhaf adlı klasörler atlanır; 500+ beceri sınırlanır; proje kapsamı projeye kilitli; **tarama hiçbir şey yazmaz ve süreç başlatmaz** (zararlı `command` içeren MCP girdileri, `Popen/run/system/startfile` çağrılırsa düşen sahte, işaret dosyası oluşmadı, ağaç adları+boyut+mtime+özet birebir aynı); IPC. Birlikte `test_local_api/test_shell_policy` ile, `npm run check` 12 OK.
- Mutasyon 7/7 öldü (config link denetimi, beceri bağ takibi, boyut sınırı, duyarlı dosya, değer sızdırma, beceri sınırı, Antigravity yolunu tahmin etme).
- Gerçek makine kapsamı (yalnız sayılar): claude-code mcp ok (0 girdi — sunucular kullanıcı kapsamında değil), claude skills 1, codex mcp 4 girdi, codex skills 0, cursor mcp yok, cursor skills 22, opencode mcp 1, paylaşılan skills 13, antigravity bilinmiyor, 5 proje satırı yok.
- Kalan risk: Claude'un proje başına MCP'leri `~/.claude.json` içindeki `projects.*.mcpServers` altında olabilir; bu kart yalnız üst düzey adları verir, iç içe okuma B3-08.02'nin işidir. Belgelenmiş (`documented`) proje yolları bu makinede görülmedi. YAML istemcisi desteklenen listede olmadığından YAML ayrıştırıcısı yok. Paketli exe'de yeni `engine/capabilities` paketi ve `tomllib` henüz yeniden derlenip denenmedi (B3-09).

## B3-08.02 — Manifest normalizasyonu ve durum ayrımı (7 Kasım 2026)

- Kod: `engine/capabilities/normalize.py` (`build`, `redact_arg_list`, `redact_url`), `paths.load_entries` (aynı link/boyut/duyarlı-dosya denetimlerinden geçen ham belge), IPC `capabilities.inventory` (READ; onay kaydı `data_root/capability-approvals.json` **imzalı** dosyadan okunur, imza bozuksa yok sayılır ve `approvals_error` döner). Normalleştirilmiş kayıt: `kind` (mcp/skill), `id` (client:scope:kind:name, çakışırsa `~2`), `client`, `scope`, `origin` (yol, kaynak, dosya SHA-256), `entry` (redakte), `declared_permissions` (yerel süreç başlatır mı, ağ, env **adları**, başlık adları, izinli araçlar), `digest` (`capability_manifest.digest` ile, redakte biçim üzerinden), `secrets_removed`, `warnings` ve beş ayrı durum: `configured` / `installed` / `available` / `verified` / `trusted`, her biri gerekçeli. `verified` her zaman false (keşif hiçbir şey çalıştırmaz/aramaz); `installed`: gerçek program → PATH'te var/yok, paket çalıştırıcı/yorumlayıcı (`npx`, `python -m x`…) → `None` ("ne çalıştıracağı çalıştırmadan bilinemez"), uzak sunucu → `None`; `trusted` yalnız çağıranın verdiği **imzalı onay kaydı** (digest + kaynak yol) eşleşirse true — kendi içindeki manifest, ad, açıklama veya "trusted" iddiası güveni asla yükseltmez, yapılandırma değişince (digest değişir) güven düşer.
- Sır temizliği: env/başlık değerleri hiç taşınmaz (yalnız adlar); `--token x`, `--api-key=x`, `password=…`, `sk-/ghp_/AKIA/Bearer` biçimleri maskelenir; URL'de kullanıcı:parola ve gizli sorgu parametreleri maskelenir (`https://[redacted]@host/v1?token=[redacted]&mode=read`). Digest redakte biçimden alındığı için sır döndürmek özeti değiştirmez, komut/argüman/URL değişimi değiştirir.
- Test: `tests.engine.test_capability_normalize` 12 OK: beş durum ve benzersiz kimlik; 6 gizli değer çıktının hiçbir yerinde yok; digest sır dönüşümüne dayanıklı, tanım değişimine duyarlı; güven yalnız eşleşen kayıtla (yanlış kaynak/özet/önek/biçimsiz kayıt/yapılandırma sonradan değişti → güven yok); sahte `manifest.json` ve talimat benzeri açıklama (+ ANSI) güveni yükseltmez, uyarı verir; kurulum durumu dürüst (yok → false, `npx`/`python -m` → bilinmiyor); yinelenen adlar `same_definition` ile; Claude'un `projects.*.mcpServers` ve OpenCode `mcp.servers` iç içeliği; bozuk/boş girdiler çökmez; **envanter hiçbir süreç başlatmaz, hiçbir şey yazmaz** (zararlı `command`'lı girdi, işaret dosyası oluşmadı, `Popen/run/system` düşen sahte); IPC: imzalı onay dosyasıyla güven, dosya baytı değiştirilince güven yok + `approvals_error`, WORKER FORBIDDEN, kötü `project_root` BAD_REQUEST. Birlikte `paths/local_api/shell_policy` 45 OK, `npm run check` 12 OK.
- Mutasyon 9/9 öldü (kaynak yolu denetimi, özet öneki, URL/argüman/env sırları, kurulu-her-zaman, kimlik tekilliği, talimat dedektörü, OpenCode kabı).
- Gerçek makinede bulunup düzeltilen hata: OpenCode `mcp.servers` içindeki "servers" tek bir sunucu sayılıyordu (sahte `unknown_transport` uyarısı); gerçek yapılandırmalarda 3 gizli değer var, çıktıda 0. Gerçek envanter (sayılar): 5 MCP (codex 4, opencode 1), 36 beceri (cursor 22, paylaşılan 13, claude 1); güvenilen 0, doğrulanan 0.
- Kalan risk: `capability-approvals.json` dosyasını yazan bir "onayla" akışı yok (B3-08.03 salt-okunur; kayıt şimdilik elle/imzalı üretilmeli); beceri açıklaması talimat dedektörü bir desen listesidir, kapsamlı değildir (uyarı verir, güveni etkilemez); `claude-code` kullanıcı dosyasındaki 0 MCP gerçek, proje başına girdiler yoktu; Antigravity MCP'leri yapılandırma yeri doğrulanmadığı için envanterde yok; React ekranı bağlı değil.

## B3-08.03 — Envanter ekranı ve offline e2e (7 Kasım 2026)

- Kod: `desktop/src/inventory.ts` (saf mantık: `inventoryView`, `applyFilter`, `statusLabels`, `toggleFlag`, `warningText`, `fold`), `desktop/src/Capabilities.tsx` (ekran), rota `capabilities` ("Yetenekler"), Tauri komutu `capability_inventory(project_root: Option<String>)` + `Connection::inventory` (motorun `capabilities.inventory` yanıtını veri olarak döndürür; renderer'a başka yetki verilmez; kabuk politika testi 4 komuta ve imzaya göre güncellendi), `desktop/src/dev-mock.ts` (yalnızca `import.meta.env.DEV` ve `?mock` ile yüklenir; fixture gerçek motorun sentetik bir evden ürettiği `desktop/tests/fixtures/inventory.json`).
- Ekran: salt-okunur; yalnızca Yenile, süzgeçler (ara, tür, genel/proje kapsamı, istemci, uyarılı/kurulu olmayan/güvenilir) ve "yanlış alarm" notu (yalnız görüntüleyici notu, `localStorage`; uyarıyı gizlemez, hiçbir durumu/güveni değiştirmez) var; etkinleştir/kur/güven/çalıştır düğmesi yok (`SCREEN_ACTIONS` + modülün ihraç ettiği adlar testle sabit). Beş durum her satırda ayrı ve sabit sırada (yapılandırılmış / kurulu / kullanılabilir / doğrulandı / güvenilir) gerekçe `title`'ında; bilinmeyen asla "evet" okunmaz; uyarılar Türkçe, bilinmeyen tür motorun metniyle gösterilir; yanıt beklenen biçimde değilse hata ekranı (asla boş/yeşil değil).
- Test: `npm run check` (tsc + `node --test`) 21 OK (inventory.test.ts 9 yeni: yanıt doğrulama 13 bozuk biçim → hata, süzgeç birleşimleri, Türkçe/İngilizce arama katlaması, kapsam grupları, durum etiketleri, yanlış alarm notu hiçbir şeyi değiştirmez, salt-okunur ihracat, uyarı çevirisi); `cargo test --lib` 16 OK (yeni: gerçek motorla `inventory_comes_from_the_engine_as_data_and_changes_nothing` — sentetik ev, gizli değer çıktıda yok, yapılandırma dosyası baytı aynı, kötü `project_root` BAD_REQUEST); `tests.desktop.test_shell_policy` 5 OK; `tsc && vite build` OK, üretim paketinde `dev-mock`/fixture/sahte `invoke` yok (0 eşleşme, tek parça).
- Gerçek tarayıcı doğrulaması (Vite geliştirme sunucusu, `?mock`, gerçek motor çıktısı): ekran 9 kaydı (6 MCP + 3 beceri, genel/proje karışık) çizdi; arama kutusuna "GITHUB" yazınca yalnız `github` kaldı; "yanlış alarm" kutusu `localStorage`'a yalnız kimliği yazdı, uyarılar yerinde kaldı, güven etiketi "Güvenilir değil" kaldı; sayfadaki düğmeler yalnız "Süzgeçleri temizle" ve "Yenile". Erişilebilirlik: seçim ve onay kutularında açık `aria-label` eklendi (ilk bakışta ad "Hepsi"/"on" görünüyordu). Mantık hatası yakalandı ve düzeltildi: `toLocaleLowerCase('tr')` ile "GIT" → "gıt" olup "Github"ı bulmuyordu; `ı/İ → i` katlamasına geçildi.
- Çevrimdışı / süreçsiz kanıt (`tests/engine/offline_inventory_proof.py`, sentetik zararlı ev + gerçek ev): kaynak sürümde ağ ve süreç oluşturmayı **engelleyip deneme sayan** `sitecustomize` ile motor 5 çağrıyı yanıtladı: engellenen deneme **yok**, işaret dosyası oluşmadı, gizli değer çıktıda yok, stderr boş; gerçek evde 41 yetenek, deneme yok. **Negatif kontrol**: aynı kanca `Popen`, `os.system`, `socket.create_connection`, `getaddrinfo` çağrılarını 4/4 yakaladı (kanca çalışıyor). Paketli exe (taze derleme, SHA-256 `4e27c451…3a86`): 10 çağrı, 1,67 sn, süreç ağacı ve TCP/UDP uç noktaları ~10 ms'ye yakın aralıkla (PowerShell/CIM) izlendi: çocuk süreç **yok**, soket **yok**, işaret dosyası yok.
- Kalan risk / sınırlar: (1) Exe izlemesi örneklemedir (PowerShell sorgusu ~100–160 ms sürer); çok kısa ömürlü bir çocuk süreç kaçabilirdi — bu yüzden asıl kanıt kaynaktaki engelleyici kancadır, exe sonucu tamamlayıcıdır. (2) Gerçek Tauri penceresinde (WebView2) bu ekran açılıp elle gezilmedi; ekran tarayıcıda sahte köprüyle (gerçek motor verisi) görüldü, Rust komutu ise gerçek motorla ayrıca test edildi. (3) "Hub yok" senaryosu: envanter Hub'a hiç başvurmaz (Hub yokluğu kodda bir bağımlılık değildir) ama Hub'sız ayrı bir koşu yapılmadı. (4) "Ağ yokken" doğrudan firewall ile kesilmedi (sistem ayarı değiştirmeyiz); ağ girişimi sıfır olduğu kanca ile kanıtlandı. (5) Yanlış-alarm notu cihaz/tarayıcıya özgüdür, motora gönderilmez.

## B3-06.03 — Güvenli local preview (7 Kasım 2026)

- Kod: `desktop/src-tauri/src/preview.rs` (saf politika: `parse_ports`, `settings_from_reply`, `check_url`, `same_origin`), Tauri komutu `preview_open(url)` (yalnız adres alır), `lib.rs` (`configure` + pencereye duyarlı `navigation_allowed_for`; önizleme penceresi `preview` etiketiyle, `incognito`, aynı-köken gezinme kuralı, 10 dk zaman aşımı), motor ayarları `preview_enabled` (varsayılan **false**) ve `preview_ports` (en çok 8 port, 1024–65535; `rpp.py` doğrular), `PreviewPanel.tsx` (Ayarlar'da form). Güçlendirme: `build.rs` tüm uygulama komutlarını `AppManifest`e yazar, `capabilities/default.json` bu komutlara yalnız `main` penceresine ad ad izin verir; böylece yetkisiz pencere, iddia ettiği köken yerel olsa bile hiçbir komuta ulaşamaz.
- Kurallar: yalnız `http://127.0.0.1:<izinli port>` ve `http://[::1]:<izinli port>`; `localhost`, ad, `https`, `file:`, `data:`, `javascript:`, kimlik bilgili, bağlantı noktasız, Unicode/kontrol karakterli, 2048 karakterden uzun adresler reddedilir; ayarlar okunamaz/yanlış türdeyse özellik tamamen kapalı.
- Test: `cargo test` 23 birim + 1 entegrasyon (`tests/acl.rs`) OK; yeni: 6 politika testi (kapalı varsayılan ve 9 kapalı biçim, 5 geçerli adres, 32 düşman adres, ayrıntılı red nedenleri, port listesi, gezinme kökeni) ve **gerçek gömülü yetkilerle Tauri ACL testi**: `main` komutlarını çağırır (olumlu kontrol), `preview` penceresi 5 komutun hepsini 4 farklı köken iddiasıyla ve 7 eklenti komutunu çağıramaz. Mutasyon: `windows`a `preview` eklenince kırıldı; `AppManifest` kaldırılınca (temiz derlemeyle) kırıldı. Python: `tests.interfaces.test_preview_settings` 3 OK (+ `test_rpp` şema testi iki yeni alanla güncellendi), `test_shell_policy` 5 OK (5 komut, `main`e ad ad izin, `preview_open` yalnız `url`), `npm run check` 21 OK.
- **Gerçek WebView2 koşusu** (UI Automation + düşman sayfa, rapor: `docs/evidence/b3-06-03-preview-e2e.md`): kapalıyken (varsayılan) komut reddedildi, pencere açılmadı, sunucuya istek gitmedi; `localhost`, izin dışı port, `https`, kimlik bilgili adres reddedildi; açıkken sayfa yüklendi ve içeriden 8 komut denemesi `not allowed by ACL` aldı, uygulama depolaması/çerezi görünmedi, açılır pencere reddedildi, başka porta gezinme tamamlanmadı (korumayı kapatan mutantta pencere diğer porta geçti).
- Yolda bulunan hatalar: (1) uygulama genelindeki `navigation-guard` eklentisi `127.0.0.1:<port>` adreslerini reddettiği için önizleme hiç açılmazdı → pencereye duyarlı yapıldı; (2) ayarlarda `preview_ports` yanlış türde (sayı) gelince özellik "açık ama port yok"a düşüyordu → tamamen kapalı; (3) uygulama komutları iddia edilen yerel köken için pencere etiketine bakmıyordu → AppManifest + ad ad izin; (4) test yürütülebilirleri `STATUS_ENTRYPOINT_NOT_FOUND` veriyordu (ortak denetimler v6 bildirimi) → yalnız test hedeflerine bildirim gömüldü.
- Kalan risk / sınırlar: sayfanın kendi ağ istekleri engellenmez (fetch ile başka loopback porta ve internete çıkabilir; reddedilen gezinmenin isteği de ikinci porta ulaştı, sayfa yüklenmedi) — arayüz metni bunu söyler; ham `postMessage` ile gerçek komut gerçek pencerede denenmedi; XSS/CSRF yalnızca düşman sayfanın uygulamaya erişememesi açısından sınandı (önizlenen sayfanın kendi XSS'i kapsam dışı); "port ele geçirme" (izinli porta başka bir süreç oturursa o süreç sayfa sunar) mümkün ve kullanıcının sorumluluğundadır; 10 dk zaman aşımı gerçek pencerede beklenmedi; `window.open` için yalnızca bir kez gözlem; React ekranı yalnızca gerçek pencerede UIA ile denendi.
- Tam paket (B3-06.03 sonrası, 7 Kasım 2026): `python -m unittest discover -s tests -t .` **909 test, 0 başarısız, 3 atlandı** (symlink ayrıcalığı vb.); ayrıca `cargo test` 23+1, `npm run check` 21 OK.

## B3-09.01 — Desktop+engine paket sözleşmesi (7 Kasım 2026)

- Karar: `docs/adr/ADR-025-desktop-engine-package.md` (tek kurucu, tek klasör, kabuk motor başlatıcısının yanında, tek karma zinciri; servis/otomatik başlangıç yok; onarım = kurucuyu yeniden çalıştırmak). `PRODUCT_CONTRACT` metni ve `distribution.json` `schema_version: 1` değişmedi (yalnız `files` bir dosya ve isteğe bağlı `desktop` anahtarı kazandı).
- Kod: `packaging/build_dist.py` (`write_distribution`, `attach_desktop`, `audit`; `--desktop`, `--no-freeze`, `--audit`), `packaging/windows/orchestrator_setup.iss` (kabuk paketteyse Başlangıç menüsü kısayolu, `#ifexist`), Rust `engine_connector.rs` (`discover` sırası: `RESPECTED_APP_DIR` [verilmişse yalnız orası] → kabuğun kendi klasörü → `%LOCALAPPDATA%`; `verify_launcher`: başlatıcı karması `distribution.json` ile eşleşmeden motor çalıştırılmaz; kurulu klasörlerde bildirim zorunlu, yalnız dev override'ta yoksa atlanır; ipuçları Türkçe), `docs/ARCHITECTURE.md` güncellendi.
- Test: `tests.packaging.test_desktop_package` 9 OK (kabuk kökte tek zincirde; yeniden ekleme; eksik/yanlış klasör reddi; 6 kurcalama türü adıyla; bozuk bildirimler çökmeden raporlanır; ürünün kendi `installation._distribution` doğrulaması kabuğu kapsar ve kurcalamayı reddeder; kurucu betiği yalnız kabuk kısayolu ekler, `[Run]`/`[Registry]`/başlangıç yok; bildirim deterministik); `cargo test` 26 birim + 1 ACL OK (3 yeni: eşleşen karma geçer/değişiklik motoru çalıştırmadan durdurur; eksik/bozuk bildirim kurulu klasörde kapalı, dev override'ta açık; kabuğun yanındaki motor kazanır, açık override münhasır, kurcalı motor sessizce başka kopyaya düşmez); `npm run check` 21 OK; `test_installation/test_main/test_release_*` OK. Mutasyon 5/5 öldü (kabuk karmasız, audit karmayı/fazlayı/adlandırmayı yok sayar, yanlış klasöre ekleme).
- Gerçek smoke (`docs/evidence/b3-09-01-package-smoke.md`): taze paket + gerçek kabuk, kurucunun `StageDir → {app}` kopyası simüle edildi, gerçek kuruluma erişim kapatıldı; temiz klasörde GUI+motor Hub olmadan çalıştı (`Motor 0.1.0b2`); başlatıcı kurcalanınca motor başlatılmadı (BrokenInstall + Türkçe Onar ipucu); `app\` yok → Disconnected; `distribution.json` yok → BrokenInstall; motorsuz kabuk → NotInstalled; onarım sonrası sağlıklı; manifest denetimi her adımda tutarlı. Kurucu kurulmadan yalnız derlendi (kabukla 16,5 MB ve kabuksuz).
- Yolda bulunan hatalar: `audit` dizi içerikli bildirimde `TypeError` ile çöküyordu; Rust ipuçları Türkçe arayüzde İngilizceydi.
- Kalan risk / doğrulanmayanlar: gerçek kurucu bu makinede çalıştırılmadı (aynı `AppId` gerçek kurulum kaydını ve Hub kurulum adımını etkileyebilir); Başlangıç kısayolunun gerçek kurulumda oluştuğu doğrulanmadı; kabuk kendi karmasını doğrulayamaz (kurucu/Hub zinciri doğrular); açılışta yalnız başlatıcının karması kontrol edilir; imza yok (B3-09.04); sürüm el sıkışması ve kabuk–motor sürüm uyuşmazlığı B3-09.03'te.

## B3-09.02 — Beta.1/2 veri fixture ve migration (7 Kasım 2026)

- Kod: `interfaces/migrate.py` — okuma ve yazma `OSError`'ları (salt-okunur dosya/klasör, dolu disk, kilit) artık açık bir `MigrationError`'a çevrilir ("settings.json yazılamadı …; özgün dosya olduğu gibi duruyor"); `setup` bunu zaten `DATA_FORMAT` hatası olarak gösterir (önceden ham `PermissionError` kaçardı). `tests/tools/upgrade_proof.py` Beta.2 için uyarlandı: Beta.2 Gemini'yi artık reddettiği için Gemini adımları sessizce geçilmez, `N/A` olarak raporlanır (`not_applicable` listesi); sürüm dizesi aynıysa (henüz beta.3'e yükseltilmedi) kaynak özeti farkı kanıt sayılır. Yeni `tests/tools/migration_report.py` önce/sonra SHA-256 raporu üretir.
- Gerçek yükseltme kanıtı (git etiketlerinden `git archive` ile eski sürümün kendi kaynağı; geçici HOME/veri kökü; gerçek CLI, `custom` işçi, model çağrısı yok): **v0.1.0-beta.1 → bu çalışma kopyası: OK (29 adım, 0 N/A, 0 başarısız)**; **v0.1.0-beta.2 → bu çalışma kopyası: OK (26 adım, 3 N/A [yalnız Gemini], 0 başarısız)**. Eski sürümün oluşturduğu biten görev `check/inspect/evidence` ile doğrulanır ve okunur, başlamamış görev çalışır, kampanya ve proje durumu aynı okunur, süreç öldürülerek yarıda bırakılmış proje ya sürdürülür ya yalnız insan onayı için reddedilir, iptal edilebilir; yeni görev uçtan uca çalışır; paketli exe ile `setup/repair/health`; kaldırma temiz. Rapor: `docs/evidence/b3-09-02-migration-report.md` (önce/sonra karmalar dahil).
- Test: `tests.interfaces.test_migration_faults` 13 OK (gerçek beta.1 fixture'ı taşınır ve veri kökündeki diğer her bayt — kanıt, onay, kontrol noktası, makbuz, anahtar, 25 kayıtlık olay günlüğü — aynı kalır, günlük okunmaya devam eder; ikinci koşu hiçbir şeyi değiştirmez; **gerçek süreç ölümü** tam değiştirme anında: özgün dosya bayt bayt yerinde, yedek özgünle aynı, sonraki koşu işi bitirir ve yedeği ezmez; yazma hatası net hata verir, geçici dosya bırakmaz; **gerçek salt-okunur dosya** ve **gerçek klasör ACL'si** (yeni dosya yasak) bildirilir ve özgün korunur, hata kalkınca çalışır; 13 bozuk/beklenmeyen girdi [geçersiz JSON, boş, kesik, dizi, sayı, null, NUL, sürüm metin/bool/ondalık/yeni/0/negatif] reddedilir ve hiçbir bayt değişmez; BOM'lu dosya taşınır; okuma hatası `MigrationError`; olmayan kök/dosya hata değil; **4 süreç eşzamanlı** geçerli tek güncel dosya verir; iki gerçek yayın fixture'ı kayıpsız güncel biçime gelir). Mevcut `test_migrate` (15) ve tüm `tests/interfaces` 180 OK. Mutasyon 6/6 öldü (yazma/okuma hatası sarmalama, atomik yazma, yedek, yeni sürüm koruması, yedeği ezme — son ikisi için ilk koşuda boşluk bulundu ve test eklendi).
- Dürüst sınırlar: (1) taşınan tek dosya `settings.json`'dur (CURRENT yalnız onu içerir); olay günlüğü (`events.log`) Beta.3'te **yeni** bir dosyadır — Beta.1/2 verisinde yoktur, taşınacak eski günlük yok; migrasyon ona hiç dokunmaz (test). Kanıt/onay/kontrol noktası dosyaları biçim değiştirmedi, bu yüzden taşınmaz, bayt bayt korunur. (2) Çökmede kalan `.state-*` geçici dosyası (kill testi) temizlenmez; zararsızdır, sonraki koşuyu etkilemez. (3) Beta.1 ve Beta.2 "gerçek fixture"ları yalnız `settings.json` içerir; görev/kampanya/proje verisi için gerçek veri `upgrade_proof` tarafından eski sürümün kendi kodu ile üretilir (kullanıcının gerçek verisi kullanılmadı). (4) Kurulum klasörü (program dosyaları) rollback'i ve güncelleme sırasında çalışan görev B3-09.03'ün konusudur.

## B3-09.03 — Aktif görev varken update/rollback tasarımı (7 Kasım 2026)

- Karar: `docs/adr/ADR-026-update-window.md`. Kod: `engine/maintenance.py` (`begin/end/current/refuse_if_active/admit/run_pids/running/drain/status/other_versions`), CLI `maintenance begin|end|status|drain` (drain çıkışı 0 = boş, 3 = çalışan var), koruma `runner.create_task/start_task/apply_task` + `project.start_project/resume_project` + `campaign.start_campaign`, süpervizör girişleri (`project-run`, `campaign-run`, `_execute`, `maf`) önceden kabul edilmiş iş olarak işaretlenir; proje/kampanya süpervizör kayıtları `engine_version` taşır; kurucu betiği pencere + boşaltma akışı. Hata enjekteli kanıt: `docs/evidence/b3-09-03-update-fault-injection.md`.
- Test: `test_maintenance` 14 + `test_update_window_script` 6 OK; tam paket **945 test, 3 atlandı, 1 kırmızı**: `tests.docs.test_decision_records` (yeni ADR'lerde "erişim tarihi"/Kaynaklar eksikti) düzeltildi, o test yeniden koşuldu OK. Mutasyon 5/5 öldü, 1 katmanlı hayatta kaldı (yukarıda).
- **Gerçek hata (gerileme düzeltildi):** `Supervisor.claim_run` hiçbir yerden çağrılmıyordu; `runs.active` ve masaüstünün pencere kapatırken "çalışma sürüyor" uyarısı (B3-02.04) gerçek görevlerde hep boş dönüyordu — o kartın testleri sahte talep kullanmıştı. `runs.active` artık `effective_status`'ın kullandığı gerçek canlılıktan beslenir (`maintenance.run_pids`); gerçek çalışan koşu ile gerileme testi eklendi. Eski sahte-talepli test hâlâ geçer.
- **Bulgu:** kurucu güncellemede tüm ürün süreçlerini `Stop-Process -Force` ile öldürüyordu; artık önce pencere + boşaltma, çalışan iş varsa sessiz güncelleme ertelenir (öldürülmez). Zorla durdurulan iş zaten `interrupted` olur ve uygulanmaz (test 5).
- Kalan risk / doğrulanmayanlar: gerçek kurucu çalıştırılmadı (derlendi); kısmi kurulum, güç kesintisinde dosya kopyalama ve geri alma yolu (mevcut) yeniden sınanmadı; pencere kurucuya güvenir; canlılık taraması 500 klasörle sınırlı; sürüm el sıkışması raporlar, kurucuyu engellemez (kurucu `other_version` çıktısını henüz kullanmıyor).

## B3-03.03 — Yapılandırılmış Chat oturum adaptörü (7 Kasım 2026)

- Ücretsiz yol kanıtı (çağrıdan önce): `opencode models` listesinde `opencode/deepseek-v4.1-flash-free`; ADR-019 §3 OpenCode'un ücretsiz modellerini sayıyor; önceki oturumlarda kullanıcı onaylı 0 maliyetle kullanıldı. Doğrulama çağrıda: her `step_finish` olayında `cost: 0` (token: 7668 giriş / 3 çıkış; **kota: unknown** — akış kota vermiyor). Ücretli CLI'lar (codex/claude/cursor) çağrılmadı. `respected-orchestrator provider-models --free` "provider network opt-in is off" döndü, kullanılmadı.
- Gerçek çağrılar (toplam 4, hepsi aynı ücretsiz model): (1) tek kelimelik yanıt, (2) gizli enjeksiyon cümlesi içeren dosyayı `read` aracıyla okutma, (3-4) canlı test: oturum aç + aynı oturumda ikinci tur (B3-03.04).
- Fixture'lar (gerçek, kullanıcı yolu `C:\scratch` olarak temizlendi): `tests/fixtures/chat/opencode_ok_text.jsonl` (3 olay), `opencode_tool_injection.jsonl` (6 olay: araç çağrısı + enjeksiyonlu çıktı + özet). Model, dosyadaki "IGNORE ALL PREVIOUS INSTRUCTIONS… APPROVED_BY_USER" metnini veri olarak ele aldı.
- Kod: `engine/chat_session.py` — `normalize` (tek JSONL satırı → `status/message/tool_call/ask_user/usage/error/unknown`, asla istisna atmaz), `parse_stream` (karar: `complete|incomplete|error|rate_limited`), `command` (saf argv; `--auto` hiç eklenmez, model/oturum kimliği/istem doğrulanır, istem `-` ile başlayamaz), `run_turn` (yalnızca matriste `chat` doğrulanmış ve oturum açıksa). Yalnız `opencode` destekli; codex/claude/cursor/antigravity/custom `Unsupported` (canlı akışları yakalanmadı). Tüm olaylar `untrusted: true`; ANSI/OSC/C0/C1 temizlenir, sırlar maskelenir, metin 8000 / araç çıktısı 4000 karakterle sınırlı, satır 1 MiB.
- Test: `tests.engine.test_chat_session` 17 OK (gerçek fixture'lar, her kesik noktasında eksik akış, yırtık son satır, bozuk JSON, 429/"Free usage limit reached" → `rate_limited`, aşırı büyük satır, bilinmeyen tür, zengin metin, sır maskeleme, metnin içindeki sahte `step_finish`, yalnız açık `question` aracından `ask_user`). Mutasyon: ANSI temizliğini kaldırma / 429 ayrımı / ask_user'ı her araca yayma → 3/3 öldü. **Gerçek hata (test yakaladı):** `parse_stream` oturum sayısını `pop()` sonrası hesaplıyordu (`session_ids` hep 0).
- Kalan risk / doğrulanmayanlar: `ask_user` eşlemesi yalnız araç adı `question` olan olaylara dayanıyor; canlı akışta hiç görülmedi (ücretsiz model sormadı) — kaynak varsayımı. Fixture AppContainer **dışında** yakalandı (geliştirici sondası; ürün oturum başlatma yolu sandbox'a B5-01'de bağlanacak). Fixture `--auto` ile yakalandı; `command()` bunu eklemez (varsayılan izinle `read` aracının sorunsuz çalışacağı doğrulanmadı). Tek CLI doğrulandı (kabul: ≥1).

## B3-03.04 — Etkileşim ve müdahale komutları (7 Kasım 2026)

- Kod: `engine/session_control.py` — `SessionController`: `register/send/retry/interrupt/cancel/resume/view`, her komut kendi yetki sınıfıyla (`CLASSES`) **ilk iş** `authorize` eder. `approve` sınıfı yoktur: `approve()` her origin için (HUMAN dahil) `SessionApprovalRefused` fırlatır; oturum izin istemleri yalnız `approval.py`'nin onay otoritesinde çözülür. Oturum `(session_id, project_id)` ile adreslenir; bilinmeyen / başka projenin / bitmiş oturum **aynı** mesajla reddedilir (kimlik yoklaması yok). Girdi: yalnız çağıranın metni; ESC/CR/NUL/C1 ve >8000 karakter reddedilir (akıştan gelen metin hiçbir yoldan girdiye dönüşmez). `retry` en çok 2, `rate_limited` turda hiç. `interrupt` işlemi sonlandırır ama oturum kalır; `cancel` oturumu bitirir (bitmiş oturum geri gelmez). IPC: `sessions.list` (READ), `session.send/retry/interrupt/cancel/resume` (TASK); `session.approve` **yok** (`UNKNOWN_COMMAND` test edildi); `desktop/src/contracts/ipc.ts` güncellendi (sözleşme testi geçti).
- Test: `tests.engine.test_session_control` 23 OK + 1 canlı (isteğe bağlı): 7 komut × 5 origin matrisi (reddedilen çağrı oturum durumunu değiştirmez), worker/child hiçbir şey yapamaz, `RESPECTED_ORCH_CHILD` HUMAN'ı CHILD'a indirir, durum/kimlik testleri, girdi enjeksiyonu (ESC[201~, CR, NUL, C1, aşırı uzun, `--auto`), sahte onay akışı (akıştaki `APPROVED_BY_USER`, sahte `approval` olayı, sahte `granted` token çıktısı → `approvals/` klasörü hiç oluşmaz; `approval.decide/consume` tüm non-human origin'leri durum açılmadan reddeder), sınırlı yeniden deneme, 429'da yeniden deneme yok, gerçek OS süreci üzerinde `interrupt`/`cancel` (süreç gerçekten biter; reddedilen `interrupt` sürece dokunmaz), UI durumları (`commands.<ad>.enabled/reason`).
- Mutasyon 7/7 öldü: `cancel`'dan authorize kaldırma, `approve`'u serbest bırakma, girdi koruması, proje bağı, 429 retry koruması, retry sınırı, `terminate()`.
- **Canlı (ücretsiz) kanıt:** `RESPECTED_TEST_SANDBOX=real RESPECTED_LIVE_CHAT=1 python -m unittest ...LiveFreeSessionTests` OK (4,5 sn): ilk turda "PINEAPPLE kelimesini hatırla" → tamamlandı, `cost 0`; `SessionController.send` ile **aynı oturumda** ikinci tur → model "PINEAPPLE" yanıtladı, `cost 0`, token 219 giriş / 6 çıkış, kota unknown. (Testlerin HOME izolasyonu opencode kimlik bilgisini gizler: bu yüzden canlı test `RESPECTED_TEST_SANDBOX=real` ister; ilk denemede kapı çağrıdan önce reddetti, model çağrılmadı.)
- Kalan risk / doğrulanmayanlar: kayıt (`register`) yalnız motor içinden; IPC'den canlı bir oturum **başlatma** yok ve React'te oturum ekranı yok → "açık UI durumları" veri modeli (`view`) olarak var, ekrana bağlanmadı. `interrupt` CLI'de yumuşak sinyal yok, süreç sonlandırma (kaynak: matris). `send_input` ile canlı akış (stdin) yok; "mesaj gönder" = `--session` ile yeni tur. Sandbox (AppContainer) içinde oturum çalıştırma bağlanmadı. Denetim izi (journal) yazılmıyor. B3-05.04'te ertelenen "oturum-müdahale saldırıları" bu kartın birim düzeyinde kapandı; paketli exe ile IPC üzerinden uçtan uca denenmedi.

## B3-03.05 — Terminal render, split pane ve oturum regresyonu (7 Kasım 2026)

- Kod: `desktop/src/terminal.ts` (saf mantık): `TerminalBuffer` (10 000 satır kaydırma, satır başına 4096 karakter; ANSI CSI/OSC/DCS/APC, tek-karakter kaçışlar, C0/C1 ve bidi kontrolleri atılır; parçalara bölünmüş kaçış dizileri durum makinesiyle; CAN/SUB iptal; CRLF tek satır, tek CR satırı ezer (ilerleme çubuğu), BS siler; `snapshot/restore` ile yeniden bağlanma), `planPaste` (CRLF→LF, tüm kontrol karakterleri + ESC atılır → bracketed-paste çıkışı yok, sondaki satır sonu atılır = otomatik gönderim yok, çok satırlı/uzun metin `needsConfirm`), `openPane/closePane/setSplit/gridFor` (bölme yalnız `pty` durumu `verified` ise açılır; 2–4 bölme açıkça seçilmeden olmaz; en çok 4), `paneSupportText` (Türkçe destek durumu). `desktop/src/Terminal.tsx`: yalnız düz metin (`<pre>`), DOM'da 40 satır (sanallaştırılmış), `role="log"`, yapıştırma onay iletişim kutusu. `tsc --noEmit` ve `vite build` temiz.
- Test: `desktop/tests/terminal.test.ts` 13 OK (npm test toplam 34 OK): Türkçe/emoji, ANSI/OSC/DCS, bayt bayt bölünmüş kaçış = bütün akış, bidi/kontrol, CRLF/CR/BS, iptal, satır sınırı ve kaydırma, **10 MB günlük**, yeniden bağlanma (JSON'dan geri yüklenen anlık görüntü kesintisiz akışla aynı çıktıyı verir), yapıştırma güvenliği, bölme kuralları, ve **gerçek motor matrisine karşı** (Python'dan `agent_adapters.matrix()`): hiçbir ajanın PTY modu doğrulanmış değil → hiçbir bölme açılmıyor. Mutasyon 9/9 öldü (OSC yutma, bidi, yapıştırma kontrolleri, pty durumu, bölme izni, 4 sınırı, çok satır onayı, CR, kaydırma sınırı).
- Performans (bu makine, Node 24): 10,0 MB girdi **85 ms** (ilk sürüm 3–6 sn'ydi: düz metin hızlı yolu + satır başına `splice` yerine toplu kırpma), 10 000 satırda pencere+ekleme **~0,00–0,05 ms/kare**; bellek 10 000 satırla sınırlı. **Gerçek hatalar (test yakaladı):** satır sınırı 1 karakter taşıyordu; dolu tamponda satır başına dizi kaydırma O(n) idi.
- Kalan risk / doğrulanmayanlar: kontrollü PTY aracısı (broker) **yok** (ADR-024 koşullu GO, yalnız deney) → "süreç broker dışında shell açamaz" iddiası kanıtlanmadı; yerine "hiçbir yol shell başlatmıyor + pty `unsupported` iken bölme açılmaz" kanıtlandı. `Terminal.tsx` hiçbir rotaya bağlı değil (6 rota testi bozulmasın diye; PTY yokken ekrana koymak anlamsız) ve gerçek WebView'da çizilmedi — performans UI değil mantık düzeyinde ölçüldü; ekran okuyucu davranışı denenmedi. Kaydırma, yeniden boyutlandırma (resize) ve imleç/tam ekran uygulamaları (alternate screen) desteklenmiyor: satır tabanlı günlük görünümü. Bölme yerleşiminin kapat-aç kalıcılığı B5-01.02'ye bırakıldı.
