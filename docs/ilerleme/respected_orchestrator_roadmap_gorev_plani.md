# Respected Orchestrator — geliştirme görevleri ve ROADMAP eşleştirmesi

> **Taslak / 28 Ekim 2026.** Bu dosya depoya commit edilmedi, gerçek uygulama veya test çalıştırılmadı. Buradaki yeni modül isimleri ve metrikler **öneridir**; mevcut kodun doğrulanmış uygulamaları değildir. Geliştirme öncesinde ilgili dosya ve şema sahipleri teyit edilmelidir.

**Kapsam:** 10 ana ürün önerisi, 9 mevcut ROADMAP açığı, 37 uygulanabilir issue. P0–P2 öncelik, G0–G4 kapı sırası. Her issue: mimari, test, ölçülebilir kabul, bağımlılık.

## 0. Kaynak gerçekleri ve bağlayıcı kurallar

Kaynaklar: [ROADMAP](https://github.com/respected0/respected-orchestrator/blob/main/docs/ROADMAP.md), [ARCHITECTURE](https://github.com/respected0/respected-orchestrator/blob/main/docs/ARCHITECTURE.md), [PRODUCT_CONTRACT](https://github.com/respected0/respected-orchestrator/blob/main/docs/PRODUCT_CONTRACT.md), [AGENTS](https://github.com/respected0/respected-orchestrator/blob/main/AGENTS.md), [README](https://github.com/respected0/respected-orchestrator).

- Mevcut çalışan izolasyonu Git worktree düzeyindedir. `sandbox_exec` Windows kısıtlı belirteci **doğrulama komutları** için kullanır; normal worker süreçleri bu kısıtta çalışmaz. `apply` re-check, güncellik, kapsam ve HMAC doğrulaması korunur.
- Kampanya hatları kendi veri kökleriyle paraleldir; tek veri kökünde tek görev kilidi vardır. `after` bağımlılıkları vardır; farklı hatları birleştirme riskleri ayrıca ele alınır.
- `tester` imzalı, motor sahipliğinde bir doğrulama aşamasıyla yürütülebilir; `coordinator` atanabilir fakat hâlâ çalıştırılamaz. `auto_assign` geçmiş başarı/ortalama token/havuz sırası kullanır, görev zorluğu ve fiyat kullanmaz.
- `maf-approve` bugün etkileşimli terminal ister; MCP yolundan insan onayı sunulmaz. Hub isteğe bağlıdır; Brain yalnızca RPP ile haberleşir, import bağımlılığı yoktur.
- CLI JSON hata sözleşmesi ve 0/1/2 çıkış kodları; `engine_command`, `engine/winproc` ve process cleanup; RPP 1 ve üç repo ürün sözleşmesi korunur.
- Şema değiştiren işlerde `interfaces/migrate.py` STEPS ve gerçek sürüm fixture seti zorunludur. AGENTS.md gereği kullanıcı açıkça istemedikçe commit/push yapılmaz.

## 1. ROADMAP’deki 9 açık başlığın doğrudan karşılığı

| ROADMAP açık maddesi | Görev kodu | Değerlendirme |
|---|---|---|
| OpenCode çalışanı ve MCP kaydı | ADP-01 | Yeni gerçek CLI uyumluluk ve güvenlik testleri |
| OpenRouter / API modelleri | ADP-02, ADP-03, COST-02 | Anahtar ve egress kararı tamamlanmadan canlı provider yok |
| tester aşaması ve coordinator planlama aşaması (tamamlandı) | QUA-01, SCH-04 | Tester imzalı doğrulamaya bağlı; coordinator doğrulanmış plan/atama üretir, shell/apply yetkisi yoktur |
| auto_assign zorluk ve fiyat | COST-02, COST-03, EVAL-03 | Veri eksikliği açık, ölçüm tabanlı routing |
| Gemini ve Cursor token kullanımı | COST-01 | Gerçek CLI doğrulama; bilinmiyor ≠ sıfır |
| CrewAI / AutoGen / LangGraph / OpenHands araştırması | DOC-01 | İddia kaynakları ve ADR |
| Authenticode | REL-01 | İmzalı release ve doğrulama |
| macOS / Linux | REL-04 | Önce güvenlik eşdeğerliği |
| Migration STEPS / release fixtures | REL-02 | Şema değiştiren her issue için bloklayıcı |

## 2. Yeni on önerinin epic karşılıkları

1. **Worker güvenliği:** Gerçek worker sandbox, yetki ve ağ sınırları — `SEC-01, SEC-02, SEC-03, SEC-04`
2. **Doğrulamalı teslimat:** MAF kalite/fix döngüsü, tester, independent review — `QUA-01, QUA-02, QUA-03, QUA-04`
3. **Ölçüm ve benchmark:** Tekrarlanabilir veri ve regresyon ölçümü — `EVAL-01, EVAL-02, EVAL-03`
4. **Akıllı planlama ve paralellik:** DAG, scheduler, coordinator, entegrasyon — `SCH-01, SCH-02, SCH-03, SCH-04`
5. **Kanıt ve karar merkezi:** Evidence contract, Hub görünümü, insan onayı — `UX-01, UX-02, UX-03`
6. **Kalıcı görev devri:** Snapshot ve güvenli resume — `RES-01, RES-02, RES-03`
7. **Telemetri ve model yönlendirme:** Kullanım, fiyat, routing; API adaptörleri ayrı — `COST-01, COST-02, COST-03`
8. **GitHub teslimat hattı:** Issue→patch→PR→CI — `GH-01, GH-02, GH-03`
9. **Skills ve MCP izinleri:** Capability manifest ve izinli araçlar — `EXT-01, EXT-02`
10. **Yayın ve güncelleme:** İmza, migrate, onboarding, POSIX — `REL-02, REL-01, REL-03, REL-04`

`DOC-01` araştırma/ADR işidir; ayrı operasyonel epic. `ADP-01..03` açık ROADMAP’deki adaptör eksikleri için ayrıca bir teknik epic oluşturur.

## 3. Sıralama ve tamamlanma kapıları

- **G0:** Sözleşme ve ölçüm temeli: mevcut veriyi koruyarak doğrulanabilir plan/fixture/ADR.
- **G1:** Worker sandbox kanıtı: güvenliği ölçülmüş, sessiz fallback olmayan başlatıcı.
- **G2:** Yürütme kalitesi: tester, sınıflandırma, bounded fix, benchmark regresyon.
- **G3:** Ürünleşme: DAG/scheduler, Decision Center, resume, yönlendirme ve izinli adaptörler.
- **G4:** Dış dünya: GitHub PR/CI, API sağlayıcıları, ek MCP, imzalı kurucu ve platform kararı.

**Sıralama kuralı:** Bağımlılıkların hepsi kapanmadan issue geliştirmeye alınmaz. Gate adları takvim taahhüdü değildir. Her gate, daha önceki güvenlik ve sözleşme testleri yeşilken geçer. `S/M/L` yalnızca göreli teknik efor tahminidir; takvim veya ekip kapasitesi taahhüdü değildir.

## 4. Issue indeks tablosu

| Issue | Başlık | P | Gate | Boyut | Bağımlılıklar |
|---|---|---|---|---|---|
| `DOC-01` | Rakip araştırması + ADR karar defteri | P0 | G0 | S | — |
| `REL-02` | Şema değişiklikleri için göç testi kapısı | P0 | G0 | M | — |
| `SEC-01` | Tehdit modeli ve yetki matrisi | P0 | G0 | M | — |
| `SEC-02` | Windows worker sandbox teknoloji doğrulaması | P0 | G1 | L | `SEC-01` |
| `SEC-03` | Worker izin politikası ve fail-closed başlatıcı | P0 | G1 | L | `SEC-02`, `REL-02` |
| `SEC-04` | CI zorunlu negatif izolasyon ve kırmızı-takım testleri | P0 | G1 | L | `SEC-03` |
| `EVAL-01` | Tekrarlanabilir değerlendirme koşucusu | P0 | G0 | L | — |
| `EVAL-02` | Doğrudan ajan vs Orchestrator karşılaştırma başlangıcı | P0 | G0 | M | `EVAL-01` |
| `EVAL-03` | Kıyas raporu ve regresyon kapısı | P1 | G2 | M | `EVAL-02` |
| `QUA-01` | tester rolünü yürütülebilir aşamaya bağla | P1 | G2 | M | `SEC-01` |
| `QUA-02` | Başarısızlık taksonomisi ve tekrar deneme politikası | P1 | G2 | M | — |
| `QUA-03` | MAF finite-state verify/review/fix döngüsü | P1 | G2 | L | `QUA-01`, `QUA-02` |
| `QUA-04` | Independent review ve apply değişmezleri | P1 | G2 | M | `QUA-03`, `SEC-04` |
| `SCH-01` | Plan taslağına DAG/ownership doğrulaması ekle | P1 | G2 | M | `EVAL-01` |
| `SCH-02` | Bağımlılık ve risk tabanlı scheduler | P2 | G3 | L | `SCH-01`, `SEC-04` |
| `SCH-03` | İki worktree sonucunu güvenli entegre et | P2 | G3 | L | `SCH-02`, `QUA-04` |
| `SCH-04` | coordinator rolünü iş akışı planlayıcısına bağla | P2 | G3 | M | `SCH-02` |
| `UX-01` | Kanıt paketi görünüm şeması | P2 | G3 | M | `QUA-04` |
| `UX-02` | Hub ve CLI için salt okunur evidence API | P2 | G3 | M | `UX-01`, `REL-02` |
| `UX-03` | Hub Decision Center ve gerçek insan onayı | P2 | G3 | L | `UX-02`, `SEC-04` |
| `RES-01` | Checkpoint ve handoff veri modeli | P1 | G2 | M | `REL-02` |
| `RES-02` | Çökme sonrası kontrollü resume | P2 | G3 | L | `RES-01`, `QUA-04` |
| `RES-03` | Brain ile isteğe bağlı karar hafızası sözleşmesi | P2 | G3 | S | `RES-01` |
| `COST-01` | Gemini/Cursor kullanımını gerçek CLI ile doğrula | P1 | G2 | M | `EVAL-01` |
| `COST-02` | Sürüm kontrollü fiyat kataloğu ve belirsizlik sözleşmesi | P1 | G2 | M | `REL-02` |
| `COST-03` | Risk ve başarım tabanlı auto_assign v2 | P2 | G3 | L | `COST-01`, `COST-02`, `EVAL-03` |
| `ADP-01` | OpenCode CLI çalışanı ve MCP kayıt desteği | P2 | G3 | M | `SEC-04` |
| `ADP-02` | API anahtarı, ağ ve sağlayıcı tehdit modeli | P2 | G3 | L | `SEC-01`, `REL-02` |
| `ADP-03` | OpenRouter/API sağlayıcı adaptörü | P2 | G4 | L | `ADP-02`, `COST-02`, `SEC-04` |
| `GH-01` | GitHub Issue salt okunur içe aktar | P2 | G3 | M | `SCH-01` |
| `GH-02` | Doğrulanmış patch'ten taslak PR aç | P2 | G4 | L | `GH-01`, `QUA-04` |
| `GH-03` | CI/review geri bildirimini sınırlı düzeltmeye bağla | P2 | G4 | L | `GH-02`, `QUA-02` |
| `EXT-01` | Skill/MCP yetenek manifestosu ve izin denetimi | P2 | G3 | M | `SEC-01` |
| `EXT-02` | Serena/context MCP için read-only deneme adaptörleri | P2 | G4 | M | `EXT-01`, `SEC-04` |
| `REL-01` | Authenticode imzalı Windows kurucu hattı | P2 | G4 | M | — |
| `REL-03` | İlk göreve giden kurulum rehberi ve health wizard | P2 | G4 | M | `UX-02`, `REL-01` |
| `REL-04` | macOS/Linux için güvenlik eşdeğerliği ve platform kararı | P2 | G4 | L | `SEC-04` |

## 5. GitHub Issue olarak kullanılabilecek ayrıntılı görev tanımları

### Epic: Araştırma ve karar kayıtları

#### DOC-01 — Rakip araştırması + ADR karar defteri

**Etiketler:** `priority:P0`, `gate:G0`, `epic:ara-t-rma-ve-karar-kay-tlar`, `size:S`  
**Mevcut ROADMAP bağlantısı:** Araştırmaya dayalı tasarım (mevcut)  
**Bağımlılıklar:** Yok

**Mimari değişiklik:** docs/ altında kaynak, tarih, doğrulama düzeyi ve mimari karar şablonu; CrewAI, AutoGen, LangGraph, OpenHands ile doğrudan/komşu rakip ayrımı; araştırma metnini iş sözleşmesinden ayrı tut.

**Test senaryoları:** Eksik kaynak bağlantısı, iddia-durum eşlemesi ve karara götüren benchmark verisi için belge kontrolü.

**Ölçülebilir kabul kriterleri:**
- [x] Dört adı geçen çerçeve + önceki 10 doğrudan rakip için ayrı profil veya kapsam gerekçesi.
- [x] en az 5 ADR.
- [x] her teknik iddiada birincil kaynak ve erişim tarihi.
- [x] doğrulanmamış özellikler açıkça işaretli.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Yayın ve güncelleme

#### REL-02 — Şema değişiklikleri için göç testi kapısı

**Etiketler:** `priority:P0`, `gate:G0`, `epic:yay-n-ve-g-ncelleme`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Güncelleme / migrate.STEPS (mevcut)  
**Bağımlılıklar:** Yok

**Mimari değişiklik:** interfaces/migrate.py içindeki STEPS korunur; `tests/fixtures/releases/<sürüm>/` snapshot sözleşmesi ve CI testleri; biçim sürümü değiştiğinde idempotent taşıma.

**Test senaryoları:** İki eski örnek sürüm biçiminden en yeni biçime, ikinci repair çalıştırması ve kesinti sonrası geri alma denemesi.

**Ölçülebilir kabul kriterleri:**
- [x] Mevcut eski fixture sayısı kadar %100 geçiş.
- [x] ikinci çalıştırmada byte-düzeyinde 0 değişiklik.
- [x] başarısız migrate sonrası veri kaybı 0.
- [x] migration yoksa şema değiştiren PR CI tarafından reddedilir.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### REL-01 — Authenticode imzalı Windows kurucu hattı

**Etiketler:** `priority:P2`, `gate:G4`, `epic:yay-n-ve-g-ncelleme`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yayın / Authenticode (mevcut)  
**Bağımlılıklar:** Yok

**Mimari değişiklik:** packaging/windows/orchestrator_setup.iss ve release CI; sertifika erişimi CI secret store; executable hash/signature verify; kod imzalama sertifikası satın alma operasyonel bağımlılık.

**Test senaryoları:** İmzalı ve bozuk kurucu testleri; değişmiş payload; yanlış signer; cert expire; offline verification.

**Ölçülebilir kabul kriterleri:**
- [ ] Yayınlanan 1/1 kurucu doğru beklenen imzaya sahip.
- [ ] tampered 3/3 engellenir.
- [ ] imzalama anahtarı repository/loglarda 0.
- [ ] sertifika yoksa release signed olarak işaretlenmez.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### REL-03 — İlk göreve giden kurulum rehberi ve health wizard

**Etiketler:** `priority:P2`, `gate:G4`, `epic:yay-n-ve-g-ncelleme`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; Hub opsiyonelliği korunacak  
**Bağımlılıklar:** UX-02, REL-01

**Mimari değişiklik:** Kurulumda Git/worker CLI/izin sağlığı; bağımsız CLI health yolunu ve Hub UX rehberini aynı schema üzerinden göster; salt okunur örnek görev; data konumları açık.

**Test senaryoları:** Git yok, AI CLI yok, yanlış permission, Hub olmadan kurulum, uninstall keep-data, sample task.

**Ölçülebilir kabul kriterleri:**
- [ ] 6/6 senaryo doğru yardım/hata.
- [ ] standart ilk kurulum 1 başarı salt-okunur görevle tamamlanabilir.
- [ ] Hub absent core bozulmaz.
- [ ] kullanıcıya yanlış otomatik izin verilmiyor.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### REL-04 — macOS/Linux için güvenlik eşdeğerliği ve platform kararı

**Etiketler:** `priority:P2`, `gate:G4`, `epic:yay-n-ve-g-ncelleme`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yayın / macOS Linux (mevcut)  
**Bağımlılıklar:** SEC-04

**Mimari değişiklik:** POSIX key confinement, process isolation, installer/uninstaller ve test matrix ADR; Windows ile aynı güvenlik vaatleri sağlanmadan platform GA yapılmaz.

**Test senaryoları:** Linux/macOS permission, symlink, network, child-tree, key read, migration, installer rollback.

**Ölçülebilir kabul kriterleri:**
- [ ] Her OS için en az 10 güvenlik fixture sonucu.
- [ ] açık kırmızı test varsa release=no.
- [ ] parity raporu & build logları kaydedilir.
- [ ] backend missing'de sessiz sandbox-off 0.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Worker güvenliği

#### SEC-01 — Tehdit modeli ve yetki matrisi

**Etiketler:** `priority:P0`, `gate:G0`, `epic:worker-g-venli-i`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; mimari §2 ve §3 açıklığından  
**Bağımlılıklar:** Yok

**Mimari değişiklik:** docs/ARCHITECTURE.md ile uyumlu worker/verification/engine ve trust-boundary matrisi; dosya okuma/yazma, child process, network, secrets, symlink/junction, elevation, MCP ve insan onayı ayrı yazılır.

**Test senaryoları:** Zararsız PoC kodu ile workspace dışı okuma/yazma, HTTP çıkışı, sır okuma, junction ve terminal onayı sahteciliği senaryolarını sınıflandır.

**Ölçülebilir kabul kriterleri:**
- [x] En az 12 adversarial vaka.
- [x] her vaka için owner, engel katmanı ve beklenen sonuç kaydı.
- [x] Windows normal kullanıcı ve admin için destek/ret kararı.
- [x] açıklanmamış güvenlik vaadi 0.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### SEC-02 — Windows worker sandbox teknoloji doğrulaması

**Etiketler:** `priority:P0`, `gate:G1`, `epic:worker-g-venli-i`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut sandbox_exec sadece verify yolunda  
**Bağımlılıklar:** SEC-01  
**Durum:** Tamamlandı (30 Ekim 2026) — kanıt: `KANIT_LOG.md` §SEC-02, `poc/sec02_results.json`.

**Mimari değişiklik:** engine/winproc üzerinden başlatılan gerçek worker ve çocuk süreçleri için düşük ayrıcalıklı token / AppContainer / VM seçenekleri karşılaştırılsın; prototip yalnızca geçici test repolarında; ağ ve HOME erişimi laboratuvar koşullarında ölçülsün.

**Test senaryoları:** Her seçenekle geçici repo yazma, proje dışına yazma, sır okuma, TCP egress, alt süreç, timeout/kill; Codex/Claude CLI başlatma uyumu.

**Ölçülebilir kabul kriterleri:**
- [x] Seçilen teknolojide 5 yasak eylemin 5/5 engellenmesi.
- [x] izinli workspace yazımı 3/3 başarı.
- [x] çocuk süreç 3/3 politika mirası.
- [x] desteklenmeyen CLI için açık unsupported sonucu, sessiz geniş yetkili fallback 0.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### SEC-03 — Worker izin politikası ve fail-closed başlatıcı

**Etiketler:** `priority:P0`, `gate:G1`, `epic:worker-g-venli-i`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; ARCHITECTURE §2 worker yalıtım açığı  
**Bağımlılıklar:** SEC-02, REL-02

**Durum:** Tamamlandı (30 Ekim 2026) - kanıt: `KANIT_LOG.md` §SEC-03, `poc/sec03_focused.log`, `poc/sec03_full_suite.log`.

**Mimari değişiklik:** WorkerPolicy (allowed_roots, readonly_roots, network_mode, secrets, executable_allowlist, ttl); create/start/MAF/campaign bütün girişleri tek engine/winproc launcher yoluna gider; veri kökü ve .engine-key hiçbir worker'a açılmaz.

**Test senaryoları:** Mock worker, gerçek CLI ve campaign child lane'den izinsiz path/network; sandbox initialization fail; timeout/cancel ve child-tree cleanup.

**Ölçülebilir kabul kriterleri:**
- [ ] 3 giriş türünün %100 aynı policy motorunu kullanması.
- [ ] policy uygulanamıyorsa 0 worker start.
- [ ] 0 gizli değer log/brief/evidence sızıntısı (sentinel test).
- [ ] bütün timeout testlerinde child PID kalıntısı 0.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### SEC-04 — CI zorunlu negatif izolasyon ve kırmızı-takım testleri

**Etiketler:** `priority:P0`, `gate:G1`, `epic:worker-g-venli-i`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut tests/engine/test_sandbox.py verify odaklı  
**Bağımlılıklar:** SEC-03

**Durum:** Tamamlandı (31 Ekim 2026) — kanıt: `KANIT_LOG.md` §SEC-04, `poc/sec04_worker_source_final.log`, `poc/sec04_verify_sandbox_final.log`, `poc/sec04_security_gate_final.log`, `poc/sec04_frozen_all_final.log`.

**Mimari değişiklik:** tests/engine/ altında worker güvenlik test paketi; verify sandbox testleri ayrılmadan korunur; Windows gerçek işlem ve junction/UNC/long-path varyantları; nightly gerçek araç smoke koşusu.

**Test senaryoları:** Workspace dışı okuma/yazma, junction, hardlink, env secret, egress, recursive MCP, symlink patch, child process, tampering; kaynak ve frozen exe üzerinde.

**Ölçülebilir kabul kriterleri:**
- [x] En az 15 negatif vaka (21 kayıtlı; 19 worker içi + 2 dış).
- [x] 21/21 reddedilir, 9/9 izinli vaka geçer; 13 zorunlu kategori korunur.
- [x] her güvenlik regresyonu CI bloklar; `continue-on-error` yoktur.
- [x] ayrı worker, verify, güvenlik kapısı ve frozen test takımları raporlanır.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

**Kapsam notu:** Nightly gerçek araç smoke koşusu bu görevde eklenmedi; deterministik AppContainer ve paketlenmiş exe saldırı matrisi kapandı. Sağlayıcı sürüm farkı için ayrı smoke izleme gerekir.

### Epic: Ölçüm ve benchmark

#### EVAL-01 — Tekrarlanabilir değerlendirme koşucusu

**Etiketler:** `priority:P0`, `gate:G0`, `epic:l-m-ve-benchmark`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; araştırma ölçüm eksikliği  
**Bağımlılıklar:** Yok

**Mimari değişiklik:** tests/evals/ altında sabit commit, görev spec, kabul testleri, makine/env bilgisi, kullanılan model profili, sonuç hash ve süre/maliyet veri şeması; evaluation runner ürünün normal kullanıcı verisinden ayrılır.

**Test senaryoları:** Aynı fixture üç çalıştırmada yeniden kuruluyor mu; hatalı fixture, erişilemeyen model, süre aşımı ve JSON çıktı testi.

**Ölçülebilir kabul kriterleri:**
- [x] İlk 20 görev fixture.
- [x] hepsinde sabit başlangıç SHA ve doğrulanabilir kabul koşulu.
- [x] geçersiz fixture için 20/20 deterministik ret.
- [x] en az 3 tekrar koşusu metadata kaydeder.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### EVAL-02 — Doğrudan ajan vs Orchestrator karşılaştırma başlangıcı

**Etiketler:** `priority:P0`, `gate:G0`, `epic:l-m-ve-benchmark`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; nicel referans eksikliği  
**Bağımlılıklar:** EVAL-01

**Mimari değişiklik:** EVAL-01 üzerine direct-vs-orchestrated koşu tanımları; aynı model, commit, görev, makine ve eşit timeout; başarı/güvenlik/müdahale farklı metrikler.

**Test senaryoları:** Her iki modda 10 ortak görev x 3 tekrar; kota dolması, bilinmeyen token, environment drift denemesi.

**Ölçülebilir kabul kriterleri:**
- [ ] En az 60 tam koşu raporu veya tamamlanamayanların ayrı nedenleri.
- [ ] başarı ve güvenlik oranları birbirinden bağımsız.
- [ ] sürüm/tarih/runtime metadata %100 mevcut.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### EVAL-03 — Kıyas raporu ve regresyon kapısı

**Etiketler:** `priority:P1`, `gate:G2`, `epic:l-m-ve-benchmark`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; model seçimi ölçümü için taban  
**Bağımlılıklar:** EVAL-02

**Mimari değişiklik:** JSON/CSV/Markdown raporu, confidence aralıkları ve altyapı varyans uyarısı; ürünün güvenlik gate testleri ile model başarı benchmarklarını ayrı sınıflandır.

**Test senaryoları:** Bilinen 2 artı/eksi senaryoyla medyan ve hata payı; geçersiz karşılaştırmada engelleme.

**Ölçülebilir kabul kriterleri:**
- [ ] 4 ana KPI (kabul başarısı, worker ihlali, maliyet, süre) her raporda bulunur.
- [ ] 0 eksik veriye sahte sıfır atanır.
- [ ] en az 2 koşuda regresyonu gösteren testler geçer.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Doğrulamalı teslimat

#### QUA-01 — tester rolünü yürütülebilir aşamaya bağla

**Etiketler:** `priority:P1`, `gate:G2`, `epic:do-rulamal-teslimat`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Master–worker tester (mevcut)  
**Bağımlılıklar:** SEC-01
**Durum:** Tamamlandı (2026-11-01) — kanıt: `KANIT_LOG.md` §QUA-01

**Mimari değişiklik:** workflows/roles.py ve workflows/maf_workflow.py rol geçişleri; tester motor sahipliğinde, salt doğrulama yetkisiyle AppContainer içinde yalnızca kabul komutlarını bir kez çalıştırır, kod yazmaz ve serbest komut kabul etmez. İmzalı `tester-report.json` run/project/patch/assignment'a bağlıdır; MAF gözden geçirici öncesi doğrular. `ROLE_NOT_EXECUTABLE` yalnızca coordinator planlama aşamasının tek görev rolü olarak kullanılması gibi kapsam dışı kullanımlarda sürer.

**Test senaryoları:** tester var/yok, fallback yok, test komutu izinli/izinsiz, tamper, timeout; roller üzerinde 6 durum.

**Ölçülebilir kabul kriterleri:**
- [x] 6/6 tester runner vakası beklenen sonucu verir; odaklı paket 110/110 `OK`.
- [x] tester'ın workspace dışında yazabilmesi 0 (`test_tester_cannot_write_outside_its_workspace`).
- [x] mevcut implementer/reviewer çıktılarında değişim 0; tam regresyon 400/400 `OK`.
- [x] 0 implicit tool fallback (`test_unavailable_tester_is_refused_without_an_implicit_substitution`).
- [x] İlgili regresyon ve paket testleri başarılı; doküman kapısı `OK`; `docs/ARCHITECTURE.md` ve tehdit modeli senkron.

#### QUA-02 — Başarısızlık taksonomisi ve tekrar deneme politikası

**Etiketler:** `priority:P1`, `gate:G2`, `epic:do-rulamal-teslimat`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut sınırlı retry üzerine  
**Bağımlılıklar:** Yok  
**Durum:** Tamamlandı (2026-10-30) — kanıt: `KANIT_LOG.md` §QUA-02

**Mimari değişiklik:** engine/runner ve workflows/maf_workflow sonuç nedenleri: test_failure, policy_denied, timeout, quota, auth, infrastructure, stale_patch, reviewer_reject; retryable alanı kontrollü enum.

**Test senaryoları:** Her hata sınıfı için sahte worker üret; art arda aynı hata ve kota dolması; insan müdahalesi gerekli durumlar.

**Ölçülebilir kabul kriterleri:**
- [x] En az 8/8 sınıf doğru ayrılır.
- [x] auth/quota/policy durumlarında otomatik retry 0.
- [x] retry sayısı limit aşmaz.
- [x] sınıf JSON'da ve evidence'da korunur.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### QUA-03 — MAF finite-state verify/review/fix döngüsü

**Etiketler:** `priority:P1`, `gate:G2`, `epic:do-rulamal-teslimat`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut MAF genişletmesi  
**Bağımlılıklar:** QUA-01, QUA-02
**Durum:** Tamamlandı (2026-11-01) — kanıt: `KANIT_LOG.md` §QUA-03

**Mimari değişiklik:** MAF step-state: implement -> tester -> independent reviewer -> bounded fix -> reverify; fix'e yalnızca sınıflandırılmış kanıt ver; resume idempotent state machine.

**Test senaryoları:** Test hatası düzelir, aynı hata döner, reviewer reddeder, kullanıcı iptal eder, max rounds biter, patch stale olur.

**Ölçülebilir kabul kriterleri:**
- [x] 6/6 vaka beklenen son state.
- [x] max_fix_rounds default 2 ve üst sınır configurable.
- [x] hiçbir otomatik fix main worktree'ye apply etmez.
- [x] hata nedenleri kanıt bağlantısı taşır.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### QUA-04 — Independent review ve apply değişmezleri

**Etiketler:** `priority:P1`, `gate:G2`, `epic:do-rulamal-teslimat`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; ARCHITECTURE §2-4 güvence testi  
**Bağımlılıklar:** QUA-03, SEC-04
**Durum:** Tamamlandı (2026-11-01) — kanıt: `KANIT_LOG.md` §QUA-04

**Mimari değişiklik:** MAF/engine/apply için imzalı patch + check + human approval invariants; review ile worker profil bağımsızlığı istenirse enforce; tester yalnızca raporlayıcıdır.

**Test senaryoları:** Aynı reviewer profili, sahte imza, değişen HEAD, çalışma anında apply, maliyet retry limit, kullanıcı onaysız akış.

**Ölçülebilir kabul kriterleri:**
- [x] En az 12 invariant testi (12 ret + 1 meşru akış).
- [x] 12/12 doğru ret.
- [x] otomatik merge/apply sayısı 0.
- [x] mevcut check→apply akışı yeşil örnek fixture ile 1/1 sürer.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Akıllı planlama ve paralellik

#### SCH-01 — Plan taslağına DAG/ownership doğrulaması ekle

**Etiketler:** `priority:P1`, `gate:G2`, `epic:ak-ll-planlama-ve-paralellik`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut campaign after, plan ve ownership üzerine  
**Bağımlılıklar:** EVAL-01
**Durum:** Tamamlandı (2026-11-01) — kanıt: `KANIT_LOG.md` §SCH-01

**Mimari değişiklik:** workflows/plan çıkışında node, depends_on, ownership, forbidden, acceptance, budget fields; DAG validator ve cycle path; kullanıcının onayı olmadan plan başlatma yok.

**Test senaryoları:** 3 bağımsız görev, zincir, döngü, çapraz ownership ve geçersiz verify komutu.

**Ölçülebilir kabul kriterleri:**
- [x] 5/5 input sınıfı doğru tanılanır.
- [x] cycle kabulü 0.
- [x] bilinen overlap görevleri işaretleme 100%.
- [x] plan komutu başlattığı worker sayısı 0.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### SCH-02 — Bağımlılık ve risk tabanlı scheduler

**Etiketler:** `priority:P2`, `gate:G3`, `epic:ak-ll-planlama-ve-paralellik`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; campaign lane sistemi kullanılır  
**Bağımlılıklar:** SCH-01, SEC-04
**Durum:** Tamamlandı (2026-11-01) — kanıt: `KANIT_LOG.md` §SCH-02

**Mimari değişiklik:** workflows/campaign scheduler üzerine ready queue, after semantiği, per-lane data root, bounded concurrency; kapsam çakışmalarına serialize; crash/stop; global worker policy zorunlu.

**Test senaryoları:** İki bağımsız + bir bağımlı iş, overlapping iki iş, timeout, cancel, lane fail/skip.

**Ölçülebilir kabul kriterleri:**
- [x] max_parallel=2 testinde bir anda en fazla 2 worker.
- [x] bağımlı başlamadan önce öncül sonucu geçer.
- [x] overlap aynı anda çalışmaz (0 çakışma).
- [x] 6/6 state geçiş testi.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### SCH-03 — İki worktree sonucunu güvenli entegre et

**Etiketler:** `priority:P2`, `gate:G3`, `epic:ak-ll-planlama-ve-paralellik`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut patch freshness/check korunarak  
**Bağımlılıklar:** SCH-02, QUA-04
**Durum:** Tamamlandı (2026-11-01) — kanıt: `KANIT_LOG.md` §SCH-03

**Mimari değişiklik:** Birleştirme için geçici integration worktree, sırayla git apply --check, combined verify ve yeniden kanıt; onay olmadan gerçek repo değişmez.

**Test senaryoları:** Aynı satır çatışması, bağımsız dosyalar, head drift, ilk patch başarılı ikincisi başarısız, doğrulama başarısız.

**Ölçülebilir kabul kriterleri:**
- [x] 5/5 senaryo deterministik.
- [x] herhangi aşamada hata halinde gerçek repo SHA değişimi 0.
- [x] iki bağımsız başarılı patch 1/1 combined verification sonrasında karar için hazır.
- [x] kısmi apply 0.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### SCH-04 — coordinator rolünü iş akışı planlayıcısına bağla

**Etiketler:** `priority:P2`, `gate:G3`, `epic:ak-ll-planlama-ve-paralellik`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Master–worker coordinator (mevcut)  
**Bağımlılıklar:** SCH-02
**Durum:** Tamamlandı (2026-11-02) — kanıt: `KANIT_LOG.md` §SCH-04

**Mimari değişiklik:** `workflows/coordinator.py` ve `coordinate` komutu; coordinator plan verilmişse aynı planner DAG ve project spec validator'larından geçirir, değilse atanan araçla taslak üretir. Yalnızca doğrulanmış plan ve rol ataması döndürür; `command`/`auto_apply`/`allow_apply`/`shell` önerileri reddedilir; geçersiz planda 0 worker başlar ve hiçbir proje/kampanya/apply olmaz. Açık atama kullanılamıyorsa `ROLE_UNAVAILABLE` döner; sessiz override yoktur.

**Test senaryoları:** Geçerli DAG, yetkisiz command/auto_apply önerisi, cycle, assign unavailable, prompt injection input.

**Ölçülebilir kabul kriterleri:**
- [x] 5/5 senaryo.
- [x] geçersiz planlarda 0 worker.
- [x] coordinator doğrudan apply yetkisi 0.
- [x] explicit atamalarda sessiz override 0.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Kanıt ve karar merkezi

#### UX-01 — Kanıt paketi görünüm şeması

**Etiketler:** `priority:P2`, `gate:G3`, `epic:kan-t-ve-karar-merkezi`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut signed evidence read-only görünümü  
**Bağımlılıklar:** QUA-04

**Mimari değişiklik:** engine evidence üzerine ayrı redacted presentation model: patch summary, SHA, check results, reviewer, tests, risks, cost unknown; orijinal HMAC kaydı değişmez.

**Test senaryoları:** Geçerli, eski, başarısız, kurcalanmış, eksik token, gizli env'li 6 evidence fixture.

**Ölçülebilir kabul kriterleri:**
- [ ] 6/6 görünüm durumu doğru.
- [ ] redaksiyon testinde 0 secret.
- [ ] evidence üretimi mevcut imzayı değiştirmez.
- [ ] her status için sebep alanı mevcut.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### UX-02 — Hub ve CLI için salt okunur evidence API

**Etiketler:** `priority:P2`, `gate:G3`, `epic:kan-t-ve-karar-merkezi`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; RPP ürüne özel ops / mevcut MCP evidence  
**Bağımlılıklar:** UX-01, REL-02

**Mimari değişiklik:** interfaces/rpp.py ürüne özel read-only sonuçları; RPP1/JSON sözleşmesini gözet; Hub yalnızca çağırır, kalıcı kopya tutmaz; CLI karşılığı bulunur.

**Test senaryoları:** RPP/CLI aynı görevden aynı normalize görünüm üretir; denied traversal; olmayan task; locked evidence; schema mismatch.

**Ölçülebilir kabul kriterleri:**
- [ ] 5/5 hata ve başarı vakası.
- [ ] Hub kaldırıldığında CLI çalışır.
- [ ] hiçbir GET read-only çağrı main repo hash değiştirmez.
- [ ] conformance yeşil.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### UX-03 — Hub Decision Center ve gerçek insan onayı

**Etiketler:** `priority:P2`, `gate:G3`, `epic:kan-t-ve-karar-merkezi`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; Hub-only alternatif işlem güven sınırı  
**Bağımlılıklar:** UX-02, SEC-04

**Mimari değişiklik:** Hub repo arayüz; gösterim ve kullanıcı etkileşimi ayrı. Onay için yalnızca güvenilir yerel OS-kimlikli süreç veya mevcut etkileşimli terminal üzerinden kanıtlanmış insan eylemi; MCP ve agent üzerinden onay token'ı yok. Önce ADR + threat model.

**Test senaryoları:** Sahte MCP onayı, replay token, user session lock, ekran drift, başarılı confirm, cancel, outdated evidence.

**Ölçülebilir kabul kriterleri:**
- [ ] 0 MCP self-approval.
- [ ] 0 replay.
- [ ] imza/HEAD değişirse onay geçersiz.
- [ ] en az 7/7 senaryo.
- [ ] Hub yokken terminal maf-approve yolu çalışır.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Kalıcı görev devri

#### RES-01 — Checkpoint ve handoff veri modeli

**Etiketler:** `priority:P1`, `gate:G2`, `epic:kal-c-g-rev-devri`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; project-resume ve imzalı veri üzerine  
**Bağımlılıklar:** REL-02
**Durum:** Tamamlandı — kanıt: `KANIT_LOG.md` §RES-01

**Mimari değişiklik:** Runner/campaign/proje için atomic state snapshot: commit, role, rounds, next action, check hashes, limits; kullanıcı verisi sürümlenir, RESUMABLE/NEEDS_REVIEW semantiği.

**Test senaryoları:** İş ortasında SIGTERM, bozuk geçici dosya, yarım state, eski versiyon, farklı repo HEAD.

**Ölçülebilir kabul kriterleri:**
- [x] 5/5 durum doğru yönetilir.
- [x] atomik işlemde bozuk JSON okuması 0.
- [x] snapshot şema migrate testi geçer.
- [x] sır/worker prompt dump sızıntısı 0.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### RES-02 — Çökme sonrası kontrollü resume

**Etiketler:** `priority:P2`, `gate:G3`, `epic:kal-c-g-rev-devri`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; project-resume genişletilir  
**Bağımlılıklar:** RES-01, QUA-04
**Durum:** Tamamlandı — kanıt: `KANIT_LOG.md` §RES-02

**Mimari değişiklik:** engine_command ile başlatma, kilit temizleme ve resumable FSM; tekrar çalıştırılabilecek adım whitelist; bilinmeyen step veya HEAD drift durumunda insan onayı.

**Test senaryoları:** 5 farklı noktada kill/restart, eski patch, aynı operation_id tekrar, reviewer tamamlama, açık süreç ağacı.

**Ölçülebilir kabul kriterleri:**
- [x] 5/5 geçerli kurtarma senaryosu.
- [x] onay olmadan apply 0.
- [x] aynı operasyon çift ücretli çalıştırma 0 (simülasyonda).
- [x] timeout çocuk süreç kalıntısı 0.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### RES-03 — Brain ile isteğe bağlı karar hafızası sözleşmesi

**Etiketler:** `priority:P2`, `gate:G3`, `epic:kal-c-g-rev-devri`, `size:S`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut memory use explicit korunarak  
**Bağımlılıklar:** RES-01
**Durum:** Tamamlandı — kanıt: `KANIT_LOG.md` §RES-03

**Mimari değişiklik:** RPP memory.note ile yalnızca kullanıcı izinli ve kalıcı tasarım kararı özeti; operasyonel checkpoint local kalır; bağlantısız motor aynı işlevi görür.

**Test senaryoları:** Brain absent, read-only grant, write grant, opt-out, prompt injection içerikli not.

**Ölçülebilir kabul kriterleri:**
- [x] Bağlantısız 3/3 resume.
- [x] opt-out akışında Brain çağrısı 0.
- [x] write izni yokken not yazımı 0.
- [x] 5/5 grant durumu.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Telemetri ve model yönlendirme

#### COST-01 — Gemini/Cursor kullanımını gerçek CLI ile doğrula

**Etiketler:** `priority:P1`, `gate:G2`, `epic:telemetri-ve-model-y-nlendirme`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Token tasarrufu (mevcut)  
**Bağımlılıklar:** EVAL-01

**Mimari değişiklik:** engine token_usage parser değerleri known/unknown; Win .cmd bypass denemeden güvenli wrapper veya resmi exe yolunu araştır; platform/CLI sürüm metadata; 0 uydurma tahmin.

**Test senaryoları:** Gerçek Gemini ve Cursor oturumları, JSON çıktı varyantları, quota/auth, .cmd güvenlik reddi.

**Ölçülebilir kabul kriterleri:**
- [ ] İki araçtan her biri için en az 3 gerçek canlı koşu veya blocked/reason açık raporu.
- [ ] unknown→0 dönüşümü 0.
- [ ] mevcut güvenli cmd kuralına istisna 0.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### COST-02 — Sürüm kontrollü fiyat kataloğu ve belirsizlik sözleşmesi

**Durum:** Tamamlandı — kanıt: `KANIT_LOG.md` §COST-02

**Etiketler:** `priority:P1`, `gate:G2`, `epic:telemetri-ve-model-y-nlendirme`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Otomatik atama fiyatı + OpenRouter bekliyor (mevcut)  
**Bağımlılıklar:** REL-02

**Mimari değişiklik:** Fiyat/verim verisi sağlayıcı kataloğunda; currency, unit, effective_from, model_version, observed_tokens, estimate_only, confidence; gizli API key asla state'e kopyalanmaz.

**Test senaryoları:** Model unknown, fiyat değişti, input/output ayrı, eksik kullanım, sağlayıcı downtime.

**Ölçülebilir kabul kriterleri:**
- [x] 5/5 durum deterministik.
- [x] bilinmeyen ücret için unknown gösterimi %100.
- [x] her rakamsal fiyat hesaplamasında timestamp+model version mevcut.
- [x] canlı fiyat zorunlu tutulmaz.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### COST-03 — Risk ve başarım tabanlı auto_assign v2

**Etiketler:** `priority:P2`, `gate:G3`, `epic:telemetri-ve-model-y-nlendirme`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Otomatik atama zorluğu/fiyat (mevcut)  
**Bağımlılıklar:** COST-01, COST-02, EVAL-03

**Mimari değişiklik:** workflows/roles.py + track_record.py geçmişi; görev sınıfı, güvenlik risk seviyesi, başarı oranı, maliyet, review bağımsızlığı; açık rol atamasını hiçbir zaman override etme.

**Test senaryoları:** Yetersiz veri, eşit skor, blocked profile, izin verilmeyen model, model/kota kaybı, pahalı fallback.

**Ölçülebilir kabul kriterleri:**
- [ ] 6/6 karar testinde deterministik seçim.
- [ ] <3 kayıt durumunda pool_order davranışı açık.
- [ ] explicit override 0.
- [ ] karar gerekçesi %100 role_assignments içine raporlanır.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Adaptörler ve API

#### ADP-01 — OpenCode CLI çalışanı ve MCP kayıt desteği

**Durum:** Tamamlandı — kanıt: `KANIT_LOG.md` §ADP-01

**Etiketler:** `priority:P2`, `gate:G3`, `epic:adapt-rler-ve-api`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Her AI ile çalışma / OpenCode (mevcut)  
**Bağımlılıklar:** SEC-04

**Mimari değişiklik:** Mevcut engine worker adapter sözleşmesi ve interfaces/integrations.py; shell injection yasakları değişmez; kurulum yoksa NOT_INSTALLED.

**Test senaryoları:** Gerçek OpenCode sürümü Windows üzerinde create/start/inspect/check; invalid CLI, auth missing, timeout, fail status, MCP setup/rollback.

**Ölçülebilir kabul kriterleri:**
- [x] En az 5 gerçek uçtan uca OpenCode denemesi (başarı+ret): read/write `completed`, invalid_model/acceptance_failure/auth_missing `failed`, timeout `timed_out`.
- [x] sahte başarısız status kabulü 0.
- [x] diğer MCP kayıtları değişmez.
- [x] test makinesi sürümü raporlanır: `opencode v2.2.3`, model `amd/DeepSeek-V4.1-Flash`.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### ADP-02 — API anahtarı, ağ ve sağlayıcı tehdit modeli

**Durum:** Tamamlandı — kanıt: `KANIT_LOG.md` §ADP-02

**Etiketler:** `priority:P2`, `gate:G3`, `epic:adapt-rler-ve-api`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Her AI ile çalışma / API (mevcut)  
**Bağımlılıklar:** SEC-01, REL-02

**Mimari değişiklik:** Keyring/credential store seçenekleri için ADR; engine→provider gateway ve HTTP egress policy; secrets yalnızca request zamanı erişilir; fail-closed; privacy ve log redaction; user opt-in.

**Test senaryoları:** Kasıtlı 401, HTTP redirect, proxy, log exposure, secret persistence, denied domain.

**Ölçülebilir kabul kriterleri:**
- [x] En az 6 tehdit senaryosu test planıyla karara bağlanır: ADR-007 + 6/6 politika testi.
- [x] 0 key JSON/log/evidence: anahtar maskelenir, kalıcı ayara yazılmaz.
- [x] opt-in kapalıyken ağ çağrısı 0: `ProviderDenied` soket öncesi.
- [x] provider code gate olmadan canlı API kullanılmaz: `RESPECTED_PROVIDER_CODE_GATE=1` zorunlu.
- [x] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### ADP-03 — OpenRouter/API sağlayıcı adaptörü

**Etiketler:** `priority:P2`, `gate:G4`, `epic:adapt-rler-ve-api`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Her AI ile çalışma / OpenRouter (mevcut)  
**Bağımlılıklar:** ADP-02, COST-02, SEC-04

**Mimari değişiklik:** ADP-02 güvenlik kararı uygulanır; model_catalog ve provider invoke adapter; idempotent request tracking, timeout/rate-limit, key storage; kullanım/fiyat bilinmeyen durumları korunur.

**Test senaryoları:** Yerel mock API; 200/401/429/500/timeout; partial stream; gerçek opt-in bir test modelinde yazma görevi.

**Ölçülebilir kabul kriterleri:**
- [ ] 6/6 mock API koşulu.
- [ ] 401/429 için yetkisiz sessiz provider fallback 0.
- [ ] 1 gerçek e2e smoke.
- [ ] anahtarların diske düz metin sızması 0.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: GitHub teslimat hattı

#### GH-01 — GitHub Issue salt okunur içe aktar

**Etiketler:** `priority:P2`, `gate:G3`, `epic:github-teslimat-hatt`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; mevcut planlama üzerine  
**Bağımlılıklar:** SCH-01

**Mimari değişiklik:** GitHub ayrı connector; issue title/body ve permitted labels plan taslağına dönüştürülür; issue metni güvenilmeyen veri; token low-scope ve local secure store; otomatik worker başlatma yok.

**Test senaryoları:** Issue injection, 404, restricted repo, markdown command, revocation, rate-limit.

**Ölçülebilir kabul kriterleri:**
- [ ] 6/6 senaryo doğru.
- [ ] issue okuma sonrası çalışan görev sayısı 0.
- [ ] GitHub yazma isteği 0.
- [ ] kaynak issue id ve revision %100 kayıtta.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### GH-02 — Doğrulanmış patch'ten taslak PR aç

**Etiketler:** `priority:P2`, `gate:G4`, `epic:github-teslimat-hatt`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; verify/review sonrası  
**Bağımlılıklar:** GH-01, QUA-04

**Mimari değişiklik:** GitHub connector; sadece imzalı ve check success sonucunda kullanıcı izinli branch/push ve DRAFT PR; `apply` ile PR açma karıştırılmaz; remote izinleri ayrı ayardır.

**Test senaryoları:** Tamamlanan görev PR, expired patch, denied auth, conflict, duplicate request, secret diff.

**Ölçülebilir kabul kriterleri:**
- [ ] 6/6 senaryo.
- [ ] failed/stale evidence durumunda PR 0.
- [ ] operation_id tekrarında PR duplicate 0.
- [ ] diff/CI linkleri izlenebilir.
- [ ] varsayılan otomatik merge 0.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### GH-03 — CI/review geri bildirimini sınırlı düzeltmeye bağla

**Etiketler:** `priority:P2`, `gate:G4`, `epic:github-teslimat-hatt`, `size:L`  
**Mevcut ROADMAP bağlantısı:** Yeni; MAF ve PR hattı  
**Bağımlılıklar:** GH-02, QUA-02

**Mimari değişiklik:** GitHub statuses/review comments read-only; error classifier üzerinden yeni bounded worker task; PR yazma/yorumları için ayrı insan izni; branch başı yeniden check.

**Test senaryoları:** CI failing, flaky test, unauthorized reviewer, old revision, exceeded rounds, approval revoked.

**Ölçülebilir kabul kriterleri:**
- [ ] 6/6 senaryo.
- [ ] 0 unlimited retry.
- [ ] eski SHA için fix yok.
- [ ] CI yeşil olmadan merge denemesi 0.
- [ ] gerekçe kanıt paketine kayıtlı.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

### Epic: Skills ve MCP izinleri

#### EXT-01 — Skill/MCP yetenek manifestosu ve izin denetimi

**Etiketler:** `priority:P2`, `gate:G3`, `epic:skills-ve-mcp-izinleri`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; MCP güven sınırlarının genişletilmesi  
**Bağımlılıklar:** SEC-01

**Mimari değişiklik:** Manifestte tool, işlemler, read/write/net erişimi, veri kapsamı, sürüm, trust level; görev planında izin beyanı ve kullanıcı onayı; Brain/Hub bağımsız.

**Test senaryoları:** Manifest yok, fazla izin, değiştirilen hash, untrusted skill, malicious description.

**Ölçülebilir kabul kriterleri:**
- [ ] 5/5 engelleme/geçiş.
- [ ] bildirilmeyen yetenek otomatik yetkilendirilmez.
- [ ] her manifest hash ve provenance taşıyor.
- [ ] varsayılan kapalı.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

#### EXT-02 — Serena/context MCP için read-only deneme adaptörleri

**Etiketler:** `priority:P2`, `gate:G4`, `epic:skills-ve-mcp-izinleri`, `size:M`  
**Mevcut ROADMAP bağlantısı:** Yeni; HTML'deki tamamlayıcı araçlara açık mimari  
**Bağımlılıklar:** EXT-01, SEC-04

**Mimari değişiklik:** Orchestrator kendi yeniden yazdığı kod zekası değil, izinlenmiş keşif yeteneği sunar; metin/araç sonucu tainted input kabul edilir; worker sandbox ve mcp recursion sınırı geçerli.

**Test senaryoları:** Repo içi sembol arama, prompt injection tool response, secret leak, wrong path, provider missing.

**Ölçülebilir kabul kriterleri:**
- [ ] 5/5 test.
- [ ] ilk sürümde repo dışına yazma 0.
- [ ] MCP çıktılarına otomatik privileged command izni 0.
- [ ] tool yokken orchestrator core işler.
- [ ] İlgili regresyon ve paket testleri başarılı; güvenlik/ürün sözleşmesi bozulmamış; uygulanan kod değişikliğiyle `docs/ARCHITECTURE.md` senkron.

## 6. Küresel Definition of Done

- [ ] Mevcut `python -m unittest discover -s tests -t .` başarılı; paket etkileniyorsa `python packaging/build_dist.py` ve `python -m unittest tests.packaging.test_frozen_build` başarılı.
- [ ] RPP/ayar sözleşmesi değişirse üç repo `docs/PRODUCT_CONTRACT.md` aynı kopyaya güncellenir ve Hub common/conformance çalıştırılır.
- [ ] Şema sürümü değişirse migration STEPS, çıkmış sürümlerin fixture’ları, idempotence ve rollback testleri tamamdır.
- [ ] Bir görevde gerçek güvenlik sınırı kanıtlanmadıysa doküman açıkça söyler; hiçbir seçenek korumasız çalışmayı güvenli olarak göstermez.
- [ ] Her görevde gerekçelendirilmiş başarısızlık nedenleri, yeniden üretim komutları, örnek raporlar ve user-visible hatalar kaydedilir.
- [ ] Bilinen güvenlik ihlali, gizli anahtar sızıntısı, izinsiz apply veya kontrolsüz retry açıkken hiçbir gate tamamlanmış sayılmaz.

## 7. Başlangıç sprinti — hemen alınabilecek bağımsız işler

1. `SEC-01` — Worker güvenlik tehdit modeli; gerçek sandbox kararı için bloklayıcı.
2. `EVAL-01` — Değerlendirme fixture standardı; rakiplerden farkı ölçmek için.
3. `REL-02` — Veri migrasyon kontrolü; sonraki tüm şema değişikliklerini korumak için.
4. `DOC-01` — Rakip araştırması/ADR; tasarım kararlarının kaynak kaydı.
5. `QUA-02` — MAF hata sınıflandırması; sandbox'dan bağımsız, davranış değişimi ölçülebilir.

> **Not:** Geliştirme başlangıcında gerçek repoda değişiklik yapılmadı; burada önerilen hiçbir kabul kriteri henüz geçmiş kabul edilmemelidir. Gerçek Windows çalışan/CI ve derlenmiş paket testleri üretim makinesinde yürütülmelidir.
