# Respected Orchestrator — uygulama planı

> Yürürlükte · 30 Ekim 2026. Bu dosya 37 görevin yürütme sırasını, kapılarını ve durumunu tutar.
> Ayrıntılı görev tanımları: `docs/ilerleme/respected_orchestrator_roadmap_gorev_plani.md`
> Tamamlanan işlerin kanıtı: `docs/ilerleme/KANIT_LOG.md`

## 1. Yürütme kuralları

- Sıra **G0 → G1 → G2 → G3 → G4**. Bir görevin bütün bağımlılıkları kapanmadan o görev başlamaz.
- Her görev dört parçayla yürür: mimari değişiklik, test senaryosu, bağımlılıklar, ölçülebilir kabul kriteri.
- **Kanıt sunulmadan sonraki göreve geçilmez.** Kanıt = çalıştırılan komut, gerçek çıktı, değişen dosyalar, test sonucu.
- Kabul kriteri doğrulanmadan görev `Tamamlandı` sayılmaz; yarım iş `Bekliyor` olarak kalır.
- Ölçüm yoksa iddia yok: ölçülmemiş değer `bilinmiyor` olarak yazılır, sıfır sayılmaz.

## 2. Korunan sözleşmeler

Bunlar mevcut ürünün belgelenmiş tasarım sözleşmeleridir; yeni özellik eklerken bozulmaz.

- `apply`, başarısız veya güncelliğini yitirmiş bir sonucu hiçbir koşulda uygulamaz.
- İnsan onayı (`maf-approve`), ajanın kendi üretebildiği sıradan bir MCP çağrısına dönüşmez.
- Hub isteğe bağlıdır; motor tek başına çalışır.
- Brain entegrasyonu isteğe bağlıdır; iki ürünün kodu birbirine import edilmez.
- Kullanıcı verisini etkileyen görev durumu veya yapılandırma değişikliği sürüm geçişi ve eski sürüm testi ister (`interfaces/migrate.py` STEPS).
- CLI JSON çıktısı, 0/1/2 çıkış kodları, süreç temizliği ve süre sınırları korunur.

## 3. Kapılar

| Kapı | Anlamı | Geçme koşulu |
|---|---|---|
| G0 | Sözleşme ve ölçüm temeli | Tehdit modeli, benchmark koşucusu, veri geçişi testi ve ADR kayıtları doğrulanmış |
| G1 | Worker güvenliği | Sandbox teknolojisi ölçülmüş, fail-closed başlatıcı ve negatif izolasyon testleri yeşil |
| G2 | Yürütme kalitesi | tester rolü, hata taksonomisi, sınırlı düzeltme döngüsü ve benchmark regresyonu yeşil |
| G3 | Ürünleşme | DAG/scheduler, Decision Center, resume ve yönlendirme izin sınırlarıyla çalışıyor |
| G4 | Dış dünya | GitHub PR/CI, API sağlayıcıları, ek MCP, imzalı kurucu ve platform kararı |

## 4. Görev durumu
| Issue | Başlık | P | Gate | Bağımlılıklar | Durum |
|---|---|---|---|---|---|
| `DOC-01` | Rakip araştırması + ADR karar defteri | P0 | G0 | — | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §DOC-01 |
| `REL-02` | Şema değişiklikleri için göç testi kapısı | P0 | G0 | — | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §REL-02 |
| `SEC-01` | Tehdit modeli ve yetki matrisi | P0 | G0 | — | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §SEC-01 |
| `EVAL-01` | Tekrarlanabilir değerlendirme koşucusu | P0 | G0 | — | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §EVAL-01 |
| `SEC-02` | Windows worker sandbox teknoloji doğrulaması | P0 | G1 | `SEC-01` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §SEC-02 |
| `SEC-03` | Worker izin politikası ve fail-closed başlatıcı | P0 | G1 | `SEC-02`, `REL-02` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §SEC-03 |
| `SEC-04` | CI zorunlu negatif izolasyon ve kırmızı-takım testleri | P0 | G1 | `SEC-03` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §SEC-04 |
| `QUA-01` | tester rolünü yürütülebilir aşamaya bağla | P1 | G2 | `SEC-01` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §QUA-01 |
| `QUA-02` | Başarısızlık taksonomisi ve tekrar deneme politikası | P1 | G2 | — | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §QUA-02 |
| `QUA-03` | MAF finite-state verify/review/fix döngüsü | P1 | G2 | `QUA-01`, `QUA-02` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §QUA-03 |
| `QUA-04` | Independent review ve apply değişmezleri | P1 | G2 | `QUA-03`, `SEC-04` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §QUA-04 |
| `SCH-01` | Plan taslağına DAG/ownership doğrulaması ekle | P1 | G2 | `EVAL-01` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §SCH-01 |
| `SCH-02` | Bağımlılık ve risk tabanlı scheduler | P2 | G3 | `SCH-01`, `SEC-04` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §SCH-02 |
| `SCH-03` | İki worktree sonucunu güvenli entegre et | P2 | G3 | `SCH-02`, `QUA-04` | Tamamlandı — kanıt: `ilerleme/KANIT_LOG.md` §SCH-03 |
| `SCH-04` | coordinator rolünü iş akışı planlayıcısına bağla | P2 | G3 | `SCH-02` | Tamamlandı — kanıt: `KANIT_LOG.md` §SCH-04 |
| `RES-01` | Checkpoint ve handoff veri modeli | P1 | G2 | `REL-02` | Tamamlandı — kanıt: `KANIT_LOG.md` §RES-01 |
| `RES-02` | Çökme sonrası kontrollü resume | P2 | G3 | `RES-01`, `QUA-04` | Tamamlandı — kanıt: `KANIT_LOG.md` §RES-02 |
| `RES-03` | Brain ile isteğe bağlı karar hafızası sözleşmesi | P2 | G3 | `RES-01` | Tamamlandı — kanıt: `KANIT_LOG.md` §RES-03 |
| `ADP-01` | OpenCode CLI çalışanı ve MCP kayıt desteği | P2 | G3 | `SEC-04` | Tamamlandı — kanıt: `KANIT_LOG.md` §ADP-01 |
| `ADP-02` | API anahtarı, ağ ve sağlayıcı tehdit modeli | P2 | G3 | `SEC-01`, `REL-02` | Tamamlandı — kanıt: `KANIT_LOG.md` §ADP-02 |
| `ADP-03` | OpenRouter/API sağlayıcı adaptörü | P2 | G4 | `ADP-02`, `COST-02`, `SEC-04` | Tamamlandı — kanıt: `KANIT_LOG.md` §ADP-03 |
| `EXT-01` | Skill/MCP yetenek manifestosu ve izin denetimi | P2 | G3 | `SEC-01` | Tamamlandı — kanıt: `KANIT_LOG.md` §EXT-01 |
| `EXT-02` | Serena/context MCP için read-only deneme adaptörleri | P2 | G4 | `EXT-01`, `SEC-04` | Tamamlandı — gerçek stdio istemcisi; Serena/context sunucusu bu makinede yok: `KANIT_LOG.md` §EXT-02 |
| `REL-01` | Authenticode imzalı Windows kurucu hattı | P2 | G4 | — | Tamamlandı — self-signed test sertifikasıyla gerçek hat; üretim sertifikası yok: `KANIT_LOG.md` §REL-01 |
| `REL-03` | İlk göreve giden kurulum rehberi ve health wizard | P2 | G4 | `UX-02`, `REL-01` | Tamamlandı — kanıt: `KANIT_LOG.md` §REL-03 |
| `REL-04` | macOS/Linux için güvenlik eşdeğerliği ve platform kararı | P2 | G4 | `SEC-04` | Tamamlandı — karar kapısı; Windows go, Linux/macOS no-go: `KANIT_LOG.md` §REL-04 |
## 5. İlk grup

Bağımsız başlangıç işleri, bu sırayla:

1. `SEC-01` — tehdit modeli ve yetki matrisi (tamamlandı)
2. `EVAL-01` — tekrarlanabilir değerlendirme koşucusu (tamamlandı)
3. `REL-02` — şema değişiklikleri için göç testi kapısı (tamamlandı)
4. `DOC-01` — rakip araştırması + ADR karar defteri (tamamlandı)
5. `QUA-02` — başarısızlık taksonomisi ve tekrar deneme politikası

## 6. Ölçüm

Her görev kapanışında en az şunlar kaydedilir: doğrulama komutu ve sonucu, süre, varsa bilinen risk.
Benchmark görevlerinde ayrıca: işlevsel başarı, kapsam uyumu, güvenlik ihlali sayısı, süre, maliyet (bilinmiyorsa `bilinmiyor`) ve kanıtın yeniden doğrulanabilirliği.
