# ADR-012 — İmzalı checkpoint ve kontrollü resume

## Durum

Kabul edildi.

## Bağlam

Süreç çökmesi ya da makine kapanması sonrası yarım proje iki kez ücretlendirilmeden, onaysız apply olmadan ve bayat patch zorlanmadan sürdürülebilmeli.

## Karar

1. Run, kampanya ve proje için ortak, sürümlü ve kapalı şemalı (v2) checkpoint tanımlanır; prompt, ortam, anahtar, parola, belirteç, stdout/stderr ve transkript yazımdan önce reddedilir.
2. Checkpoint motorun imza anahtarıyla imzalanır ve geçici dosya + atomik değiştirmeyle yazılır.
3. İnceleme sonucu `RESUMABLE` ya da `NEEDS_REVIEW`'dur. Eksik, bozuk, imzası geçersiz, daha yeni şemalı, repo kökü erişilemez ya da HEAD'i değişmiş checkpoint otomatik resume edilmez.
4. `project-resume` yalnızca `resume`, `campaign`, `apply`, `verify`, `review` ve `complete` sınırlarından birini yeniden çalıştırır; aynı `operation_id` korunur, yarım kampanya yeniden ücretlendirilmez, canlı kilit sahibi varken resume reddedilir.
5. `NEEDS_REVIEW` durumunda devam yalnızca etkileşimli terminalden `project-approve` ile olur; MCP'de onay aracı yoktur ve alt süreçlerde reddedilir.

## Sonuçlar

- Kill/restart sonrası devam, onay sınırını aşmaz.
- Git olmayan kaynakta içerik kayması HEAD ile algılanamaz; bu durum insan incelemesi ister.
- Şema değişikliği ADR-003'teki göç kapısına tabidir (v1 bir kez v2'ye taşınır).

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §5 (RES-01, RES-02) (erişim: 2026-11-04).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §RES-01, §RES-02 (erişim: 2026-11-04).
