# Respected Orchestrator — uygulama planı

> Yürürlükte · 30 Ekim 2026 · tüm görevler tamamlandı (4 Kasım 2026). Bu dosya yürütme kurallarını, korunan sözleşmeleri ve kapıları tutar; yeni iş eklenirse bu kurallarla yürür.
> Ayrıntılı görev tanımları: `docs/archive/respected_orchestrator_roadmap_gorev_plani.md`
> Tamamlanan işlerin kanıtı: `docs/evidence/KANIT_LOG.md`

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

Planlanan 37 görevin ve sonradan eklenen `CUR-01`'in hepsi tamamlandı. Her görevin kanıtı (komut, çıktı, değişen dosyalar, kalan risk) `evidence/KANIT_LOG.md` içinde görev kimliğiyle bulunur. Açık kalan işler yalnızca `ROADMAP.md` içindedir.

| Kapı | Tamamlanan görevler |
|---|---|
| G0 | `DOC-01`, `REL-02`, `SEC-01`, `EVAL-01` |
| G1 | `SEC-02`, `SEC-03`, `SEC-04` |
| G2 | `QUA-01`, `QUA-02`, `QUA-03`, `QUA-04`, `SCH-01`, `RES-01` |
| G3 | `SCH-02`, `SCH-03`, `SCH-04`, `RES-02`, `RES-03`, `ADP-01`, `ADP-02`, `EXT-01` |
| G4 | `ADP-03`, `EXT-02`, `REL-01`, `REL-03`, `REL-04`, `CUR-01` |

Kanıtın ilk bakışta bilinmesi gereken sınırları:

- `REL-01`: imzalama hattı self-signed test sertifikasıyla gerçek çalıştırıldı; üretim sertifikası yok (`ROADMAP.md` §Yayın).
- `REL-04`: karar kapısı. Windows go, Linux/macOS no-go.
- `EXT-02`: gerçek stdio istemcisi context-mode ile canlı doğrulandı; Serena gerekmez.
- `ADP-03`: adaptör, ağ kapısı ve okuma çalışanı olarak CLI bağlantısı.
- `CUR-01`: canlı Cursor işçisi AppContainer kum havuzunda yazma görevini tamamladı.

Görev bağımlılıkları ve ayrıntılı tanımlar: `docs/archive/respected_orchestrator_roadmap_gorev_plani.md`.

## 5. Ölçüm

Her görev kapanışında en az şunlar kaydedilir: doğrulama komutu ve sonucu, süre, varsa bilinen risk.
Benchmark görevlerinde ayrıca: işlevsel başarı, kapsam uyumu, güvenlik ihlali sayısı, süre, maliyet (bilinmiyorsa `bilinmiyor`) ve kanıtın yeniden doğrulanabilirliği.
