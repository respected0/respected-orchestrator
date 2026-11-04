# ADR-010 — İki doğrulanmış sonucun güvenli birleştirilmesi

## Durum

Kabul edildi.

## Bağlam

Paralel hatlar ayrı sonuçlar üretir. Bunları gerçek repoya doğrudan uygulamak kısmi apply ve çakışma riski taşır.

## Karar

1. `integrate` iki farklı `run_id` ve 1–16 birleşik doğrulama komutu alır. Motor gerçek çalışma ağacının temiz ve run parmak iziyle aynı olduğunu doğrular.
2. Patch'ler `state/integrations/` altındaki geçici detached Git worktree'de sırayla `git apply --check` ve `git apply` ile denenir.
3. Satır/dosya çakışması, HEAD kayması, güvenlik ihlali ya da birleşik doğrulama hatasında hiçbir kanıt yayımlanmaz ve gerçek repo değişmez.
4. Başarıda yalnızca imzalı `integration.json` ile `combined.patch` yayımlanır. Gerçek repoya uygulamak ayrı bir operatör kararıdır (`apply`).
5. Geçici worktree ve staging her çıkışta temizlenir; sonrasında gerçek repo HEAD'i ve parmak izi yeniden doğrulanır.

## Sonuçlar

- Entegrasyon hiçbir zaman gerçek repoyu kendiliğinden değiştirmez.
- Birleştirme kararı ADR-004'teki insan onayı sınırının dışına çıkmaz.
- İkiden fazla sonucu tek seferde birleştirme kapsam dışıdır.

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §5 (`integrate`) (erişim: 2026-11-04).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §SCH-03 (erişim: 2026-11-04).
