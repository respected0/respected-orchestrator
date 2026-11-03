# ADR-006 — Brain isteğe bağlıdır, kod bağımlılığı yoktur

## Durum

Kabul edildi.

## Bağlam

Respected Brain uzun vadeli bilgi tutuyor; Orchestrator ise operasyonel görev durumu üretiyor. İki ürünün kodunu doğrudan bağlamak kurulumu ve hata yüzeyini büyütür.

## Karar

1. Brain entegrasyonu isteğe bağlıdır; yoksa motor tek başına çalışır.
2. Orchestrator, Brain kodunu import etmez; sözleşme dosya/HTTP sınırından yürür.
3. Operasyonel durum (görev, kilit, kanıt, handoff) motorda kalır.
4. Brain'e yalnızca uzun vadede değerli mimari kararlar ve öğrenimler, izinli biçimde aktarılır.

## Sonuçlar

- Brain kapalıyken görev akışı bozulmaz.
- `RES-03` bu sınırı genişletse bile kod importu eklememelidir.
- İki ürün ayrı sürümlenebilir.

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §7 (erişim: 2026-10-30).
- [Ürün sözleşmesi](../PRODUCT_CONTRACT.md) (erişim: 2026-10-30).
