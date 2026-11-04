# ADR-020 — CI geri bildirimi: yoklama (poll) birincil, webhook alıcısı yok

## Durum

Kabul edildi (5 Kasım 2026). Uygulama FIX-03B ile yapılır. ADR-014'ü değiştirmez, GH-03'ün "canlı bağlantı" boşluğunu
kapatma yöntemini belirler.

## Bağlam

`plan_ci_fix` CI geri bildirimini çağıranın verdiği veriden planlar; canlı kaynağa bağlı değil. İki yol var:
(a) ürün yerelde bir port açıp GitHub webhook'u dinler, (b) ürün GitHub'ı kendi kimliğiyle sorgular. Orchestrator
yerel, yönetici istemeyen, gelen bağlantı kabul etmeyen bir uygulamadır; webhook için ya port açmak ya da ayrı bir
tünel/forward aracı gerekir. Bu yeni ağ yüzeyi ve çoğu yolda ücretli ya da üçüncü taraf bir hizmet demektir.

## Karar

1. **Birincil yol yoklamadır.** Motor, operatörün zaten kullandığı `gh` oturumuyla (`gh api`) PR'ın head SHA'sına ait
   check-run durumunu ister. Gelen bağlantı, port, tünel ve üçüncü taraf hizmet yoktur; maliyet 0'dır.
2. **Eşleme kuralları** (yoklama ve içe aktarma için aynıdır): olayın `head_sha` değeri görevin doğrulanmış SHA'sına
   eşit olmalı; depo ve PR numarası kayıtla eşleşmeli; farklıysa reddedilir. Aynı `check_run.id` / `delivery id` bir
   kez işlenir (idempotent). Eski SHA'lı ya da daha eski `completed_at`'li sonuç mevcut durumu geri almaz. Bilinmeyen
   ya da eksik durum fail-closed: düzeltme planı üretilmez.
3. **Durumlar:** `success`, `failure`, `cancelled`, `timed_out`, `neutral`, `in_progress`/`queued` (bekle). Hiçbiri
   otomatik düzeltme, yorum ya da merge üretmez; çıktı yalnızca `plan_ci_fix` sınırlarını (tur bütçesi, yetkili
   reviewer, insan onayı) besler.
4. **İmza doğrulayıcısı yine yazılır.** `X-Hub-Signature-256` HMAC-SHA256 doğrulaması (sabit zamanlı karşılaştırma,
   `sha256=` biçimi zorunlu, boş/eksik gizli anahtar = ret) saf bir işlev olarak eklenir ve bir webhook yükünü
   dosya/stdin'den içe aktaran komutta (ad önerisi `github-ci-ingest`) kullanılır. Böylece operatör isterse
   kendi forward aracıyla gelen yükü motor dışı bir kanaldan besleyebilir ve sahte imza, tekrar, yanlış SHA, bozuk
   JSON ve aşırı büyük gövde testleri gerçek kodu sınar. Motor bir dinleyici **açmaz**.
5. **Gizli anahtar** ADR-007'deki kasa kurallarına uyar: diske düz metin yazılmaz, kanıta ve loga sızmaz.
6. Webhook dinleyicisi beta.2 kapsamında değildir. İleride istenirse ayrı bir ADR ve PRODUCT_CONTRACT değişikliği
   gerekir.

## Sonuçlar

- Sonuç, olaydan saniyeler değil yoklama aralığı kadar geç görülür; CI düzeltme akışı için kabul edilebilir.
- `gh` oturumu yoksa ya da rate-limit varsa komut yapılandırılmış hata verir; sessiz boş sonuç dönmez.
- Gerçek uçtan uca doğrulama için ücretsiz, public bir test deposu kullanılır (Actions public depoda ücretsiz).

## Kaynaklar

- [ADR-014](ADR-014-github-boundary.md), [ADR-007](ADR-007-provider-key-network-threat-model.md).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §GH-03 (erişim: 2026-11-05).
