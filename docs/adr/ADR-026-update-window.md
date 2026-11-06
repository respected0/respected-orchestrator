# ADR-026 — Güncelleme penceresi: aktif iş varken güncelleme

## Durum

Kabul edildi (7 Kasım 2026). Görev: B3-09.03. Ortak komut listesi ve `docs/PRODUCT_CONTRACT.md` değişmedi: `maintenance` Orchestrator'a özgü bir komuttur ve kurma işlemi yapmaz.

## Bağlam

Kurucu bir güncellemede ürünün tüm süreçlerini `Stop-Process -Force` ile öldürüyordu (ayrık görev, proje ve kampanya süpervizörleri dahil); yeni iş kabulünü
durdurmuyor, çalışanın bitmesini beklemiyordu. Öldürülen iş zaten dürüstçe `interrupted` (yarıda kaldı) görünür ve otomatik uygulanmaz
(`runner.effective_status`, `apply_task`), ama kullanıcıya sormadan iş kesmek ve ortada yeni görev başlatmak istenmeyen bir durumdur. Ayrıca masaüstünün
"çalışma sürüyor" uyarısı `runs.active` üzerinden besleniyordu ve gerçek görevlerde hep boş dönüyordu (hiçbir kod süpervizör talebi yazmıyordu).

## Karar

1. **Güncelleme penceresi** (`engine/maintenance.py`, `data\maintenance.json`, imzalı): `maintenance begin [--ttl SN] [--reason METİN]`, `end`, `status`, `drain [--seconds SN]`.
   Pencere açıkken **yeni iş başlatan her yol reddedilir** (yeni görev, görev başlatma, yama uygulama, proje/kampanya başlatma ve devam ettirme; MCP, masaüstü ve CLI aynı
   `runner`/`project`/`campaign` giriş noktalarından geçer). Okuma, iptal, durum ve onay *reddi* serbesttir.
2. **Önceden kabul edilmiş iş devam eder.** Pencereden önce başlayan süpervizörler (`project-run`, `campaign-run`), işçiler (`_execute`) ve çalışan `maf`,
   kendi sonraki adımlarını (düzeltme turu, sonraki aşama) atabilsin diye süreç bazında "kabul edilmiş" sayılır; aksi halde güncelleme çalışan bir projeyi bozardı.
3. **Pencere kendiliğinden kapanır** (varsayılan 30 dk, en çok 60 dk). Çöken bir kurucu ürünü kilitlemez; süresi dolan işaret "expired" gösterilir ve hiçbir şeyi reddetmez.
   Bozuk işaret ne kilitler ne açar; raporlanır.
4. **`drain` hiçbir şey durdurmaz.** Çalışan iş (`runs`, `projects`, `campaigns`) listelenir; çıkış kodu 0 = hiçbir şey çalışmıyor, 3 = hâlâ çalışan var. Canlılık,
   `effective_status`'ın kullandığı kayıtlarla aynıdır (`running`+canlı pid ya da `queued`+canlı başlatıcı); yalnızca süpervizör talepleri değil.
5. **Sürüm el sıkışması:** proje ve kampanya süpervizör kayıtları `engine_version` taşır; `status`/`drain` çalışan ama **başka sürümden** (ya da sürüm kaydı olmayan) süpervizörleri
   `other_version` olarak adlandırır, kurucu dosyaları sessizce değiştirmesin diye.
6. **Kurucu akışı** (`orchestrator_setup.iss`): `PrepareToInstall` önce eski programa `maintenance begin`, sonra `drain --seconds 120` çağırır. Hâlâ çalışan iş varsa
   **sessiz güncelleme ertelenir** (hiçbir şey değişmez), etkileşimli güncelleme sorar (varsayılan "Hayır"). `maintenance` komutu olmayan eski sürüm (beta.2) önceki davranışı korur (günlüğe yazılır).
   Pencere güncelleme sonrası (yeni program), geri alma sonrası (geri yüklenen program) ve yedek alınamadığında kapatılır; hepsi başarısız olsa bile süre dolunca kendiliğinden kapanır.
   Mevcut güvenlik ağı korunur: program klasörü + `*.json` yedeği, `repair` ve `health` denetimi, başarısızlıkta geri alma.
7. **Belirsiz iş asla otomatik uygulanmaz.** Zorla durdurulan koşu `interrupted` olur; `apply` yalnızca `completed` ve doğrulanmış koşuya açıktır. Proje `resume` yarıda kalan bir projeyi
   yalnızca insan onayıyla sürdürür (Beta.2 yükseltme kanıtında gösterildi).

## Reddedilen seçenekler

- **Pencere olmadan yalnızca "bekle, sonra öldür":** bekleme süresince yeni iş gelmeye devam eder, boşalma hiç gerçekleşmeyebilir.
- **Çalışan işi sessizce devretmek:** bir görevin ortasında başka sürüme geçmek kanıt ve imza zincirini belirsizleştirir; bu sürümde yok.
- **Kalıcı kilit (süresiz bakım kipi):** çöken kurucu ürünü kalıcı kapatırdı.

## Sonuçlar ve sınırlar

- Pencere kurucuya güvenir: kurucu çağırmazsa (ya da eski sürüm komutu bilmiyorsa) eski davranış (zorla durdurma, sonra `interrupted`) geçerlidir.
- `RUN_SCAN_LIMIT` (500): canlılık için en yeni 500 koşu klasörüne bakılır; daha eski ve hâlâ çalışan bir görev bu taramada görünmez (diğer kayıtlar ve süpervizör talepleri yine sayılır).
- Kurucu betiği derlendi ama bu makinede çalıştırılmadı (gerçek kurulum kaydını ve Hub adımını etkilememek için); `Stop-Process` yedeği ve geri alma yolu (mevcut) bu kartta yeniden sınanmadı.
- Gerçek kurulumda dosya değiştirme yarışı (Windows kilitli dosya) ve güç kesintisi Inno'nun kendi işlemine aittir; çalışan süreçler bırakıldığında kilit sorunu `StopRunningProduct`'a düşer.

## Kaynaklar

- `src/respected_orchestrator/engine/maintenance.py`, `packaging/windows/orchestrator_setup.iss`, `engine/runner.effective_status` (erişim: 2026-11-07).
- Kanıt: `tests/engine/test_maintenance.py`, `tests/packaging/test_update_window_script.py`, `docs/evidence/b3-09-03-update-fault-injection.md`, `docs/evidence/KANIT_LOG.md` B3-09.03 (erişim: 2026-11-07).
