# ADR-001 — Kontrollü yürütme sınırı

## Durum

Kabul edildi ve uygulandı (Windows). İşletim sistemi düzeyinde sandbox `SEC-02`/`SEC-03`/`SEC-04` ile geldi (AppContainer, fail-closed başlatıcı, negatif izolasyon testleri); macOS/Linux'ta yoktur (bkz. ADR-008).

## Bağlam

Ajanlar izole Git worktree'lerinde çalışıyor ve sonuç yaması kapsam (`ownership`/`forbidden`), testler, tazelik ve imza ile denetleniyor. Ancak bu denetim yamaya bakar; çalışan süreç worktree dışına yazarsa veya ağa çıkarsa yamada görünmez. SEC-01 PoC'si beş izin denemesinin de engellenmediğini gösterdi.

## Karar

1. Bugünkü güvence worktree + sonuç kapsamı + `check/apply` olarak kalır ve bu sınır belgelenir.
2. Worker başlatma, izin politikası ve süreç başlatıcı tek kapıdan geçecek; politika kurulamazsa worker başlamayacak (fail-closed).
3. Dosya, ağ, program ve kimlik erişimi işletim sistemi düzeyinde sınırlandırılacak; onay istemek sandbox yerine geçmeyecek.
4. İnsan onayı yalnızca yüksek riskli değişiklik ve gerçek projeye uygulama için istenecek.

## Sonuçlar

- Bu ADR tamamlanana kadar ürün "sandbox'lı" diye pazarlanmayacak.
- `SEC-02` teknoloji doğrulaması, `SEC-03` fail-closed başlatıcı, `SEC-04` negatif izolasyon testleri bağımlı işlerdir.
- Mevcut `apply` değişmezleri korunur; yeni politika onları zayıflatamaz.

## Kaynaklar

- [Tehdit modeli](../THREAT_MODEL.md), özellikle §8 PoC ve S-01…S-25 senaryoları (erişim: 2026-10-30).
- [Mimari](../ARCHITECTURE.md) §2 ve §10 (erişim: 2026-10-30).
- [KANIT_LOG](../evidence/KANIT_LOG.md) §SEC-01 (erişim: 2026-10-30).
