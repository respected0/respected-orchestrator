# ADR-002 — Tekrarlanabilir değerlendirme koşucusu

## Durum

Kabul edildi ve uygulandı (EVAL-01). Ajan başarısı karşılaştırması henüz yok (`EVAL-02` tamamlandı, ama yalnızca harness tutarlılığını ölçer; model kalitesi iddiası değildir). Gerçek ajanlı karşılaştırmanın kuralları ADR-019'dadır (FIX-02, henüz uygulanmadı).

## Bağlam

Benchmark sonucu; makine, ortam ve rastgelelik değişince yanıltıcı olabilir. Ürün kararını "daha iyi ajan" iddiasına değil, yeniden üretilebilir bir koşuya dayandırmak gerekiyor.

## Karar

1. Her fixture sabit başlangıç SHA'sı, izinli dosya kümesi ve kabul testi taşır.
2. Hatalı başlangıç **başarısız olmak zorundadır**; altın çözüm **geçmek zorundadır**. İkisinden biri beklenenden saparsa koşu reddedilir.
3. Git kimliği, tarihi ve global/system config sabitlenir; sonuç SHA-256 ile özetlenir.
4. Koşucu ürün veri köküne rapor yazmayı reddeder.
5. Model çağrısı yoksa maliyet `bilinmiyor` yazılır; sıfır sayılmaz.
6. Bu koşucunun ölçtüğü şey harness tekrarlanabilirliğidir; ajan kalitesi iddiası `EVAL-02` olmadan kurulamaz.

## Sonuçlar

- 20 fixture × 3 tekrar = 60 koşu; 60/60 sabit SHA ve beklenen hatalı/altın ayrımı.
- `tests/evals/` regresyon kapısı oldu; fixture değişirse SHA testi kırılır.
- Benchmark tabanlı ürün iddiası `EVAL-02` tamamlanana kadar yasaktır.

## Kaynaklar

- [EVAL-01 kanıtı](../evidence/KANIT_LOG.md) §EVAL-01 (erişim: 2026-10-30).
- [eval01_results.json](../evidence/poc/eval01_results.json) — 60 koşu özeti (erişim: 2026-10-30).
