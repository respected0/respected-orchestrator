# ADR-028 — Ekran görüntüsü ekleme ve modele aktarım

## Durum

Kabul edildi (8 Kasım 2026). Görevler: B4-07.01, B4-07.02, B4-07.03. Özellik **kapalı gelir** (`screenshot_enabled=false`).

## Bağlam

Ekran görüntüsü kişinin en hassas verilerinden biri olabilir (parola, belirteç, özel yazışma, konum üstverisi). Gereksinim: kullanıcı istemedikçe ekran yakalama ve modelle paylaşım yok; dosya göreve eklenmeden önce açıkça incelenir; silme ve iptal çalışır.

## Karar

Yakalama, göreve ekleme ve modelle paylaşım **üç ayrı karardır**; her biri varsayılan olarak reddeder (`engine/attachment.py`).

1. **Yakalama (`CaptureSession`)**: ayar + OS izni + kişinin yakalamayı başlatması (`arm`) gerekir; görüntü yalnız o pencerede (120 sn) ve tek seferlik kabul edilir.
   Kendiliğinden yakalayan hiçbir çağrı yoktur (arka plan yakalama = 0). İptal, izin geri alınması, süre dolması ya da denetim hatası görüntüyü atar; oturum görüntüyü tutmaz.
   Çoklu ekran/DPI yalnız etiket olarak doğrulanır (`monitor` 0–15, `dpi_scale` 0,5–6).
2. **Göreve ekleme (`attach`)**: yalnız PNG ve JPEG; 8 MB, kenar 8192, 36 megapiksel sınırı; SVG, GIF, WebP, PDF, çalıştırılabilir ve her şey reddedilir; bozuk yapı
   (taşan parça, eksik bitiş) reddedilir. **Metaveri silinir** (PNG'de kritik olmayan tüm parçalar: metin, EXIF, zaman, özel; JPEG'de APP1–APP15 ve yorum) ve temizlenmiş baytların
   özeti saklanır. Kişi **aynı baytları önizlemiş** olmalıdır (`previewed_sha256` temizlenmiş baytların özetiyle eşleşmeli) ve İNSAN olmalıdır. Görüntü yalnızca henüz
   başlamamış (`queued`) tek bir koşunun `attachments/` klasörüne, imzalı zarfla yazılır (`task_only`, `shared_with_model: false`, 24 saat TTL); yanlış koşu, yol atlatma ve
   başka koşudan okuma reddedilir; işçi ve alt süreçler okuyamaz. **Karartma (redaksiyon) arayüzde, önizlemeden önce yapılır**; motor görüntüyü çözmediği için pikselleri
   göremez, yalnız önizlenen baytların özetini bağlar ve kişinin kaç bölge karardığını kaydeder.
3. **Modele aktarım (`share` / `bytes_for_model`)**: ayrı bir rıza kaydı — hangi sağlayıcı, hangi görüntü (özet), hangi koşu, 10 dakika, açıklama metniyle ("ekranınız dışına
   gönderilir, saklanabilir"). `bytes_for_model` HER çağrıda rızayı yeniden denetler: iptal, süre, başka sağlayıcı/koşu/görüntü veya bozulma anında durdurur. `purge` koşunun
   tüm görüntü ve rızalarını siler; `sweep` süresi dolanları siler.
4. **Sızıntı yok**: `attachment` modülünü başka hiçbir modül içe aktarmaz (testle korunur); bu yüzden günlük, kanıt görünümü, kontrol noktası ve işçi isteminde görüntü yer alamaz.
   Bir sağlayıcı bağdaştırıcısı görüntü kullanmak isterse `bytes_for_model`'i çağırmak zorundadır.

## Sonuçlar ve sınırlar

### Ölçülen / doğrulanan

PNG/JPEG metaveri silme, 6 geçersiz biçim, 4 bozuk yapı, aşırı boyut, 22 test; örnek karartılmış görüntü: `docs/evidence/b4-07-02-masked-sample.png` (içindeki gizli metin parçası silindi).

### Kalan sınırlar

- OS ekran yakalama seçicisi, bölge seçimi ve karartma arayüzü bu depoda **bağlı değildir** (masaüstü); motor yalnız kabul/doğrulama/saklama/rıza tarafıdır.
- Hiçbir çalışan bağdaştırıcı görüntü iletmez; bu nedenle "dışarı görüntü = 0" bugün yapı gereğidir, ağ denetimiyle bir bağdaştırıcı üzerinde sınanmamıştır.
- Karartmanın pikselde gerçekten gizli veriyi kapattığı doğrulanamaz (motor çözmez); kişinin önizlemesine dayanır.

## Kaynaklar

- `src/respected_orchestrator/engine/attachment.py`, `engine/authority.py`, `engine/evidence.py` (erişim: 2026-11-08).
- Kanıt: `tests/engine/test_attachment.py` (22), `docs/evidence/b4-07-02-masked-sample.png`, `docs/evidence/KANIT_LOG.md` B4-06/B4-07 (erişim: 2026-11-08).
