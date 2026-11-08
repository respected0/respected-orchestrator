# ADR-001 — Kontrollü yürütme sınırı

## Durum

Kabul edildi ve uygulandı (Windows). Motor işletim sistemi düzeyinde kutu koymaz; işçiler kullanıcı olarak, ajanın kendi izin kipiyle çalışır (bkz. ADR-008).

## Bağlam

Ajanlar izole Git worktree'lerinde çalışıyor ve sonuç yaması kapsam (`ownership`/`forbidden`), testler, tazelik ve imza ile denetleniyor. Ancak bu denetim yamaya bakar; çalışan süreç worktree dışına yazarsa veya ağa çıkarsa yamada görünmez. SEC-01 PoC'si beş izin denemesinin de engellenmediğini gösterdi.

## Karar

1. Bugünkü güvence worktree + sonuç kapsamı + `check/apply` olarak kalır ve bu sınır belgelenir.
2. Worker başlatma tek süreç başlatıcıdan (`processes.execute`) geçecek; süre sınırı, süreç ağacı temizliği ve ortam süzme orada uygulanır.
3. Sonuç bir iddiadır: kapsam, doğrulama ve imzalı kanıt çalışmadan sonra motorca denetlenir.
4. İnsan onayı yalnızca yüksek riskli değişiklik ve gerçek projeye uygulama için istenecek.

## Sonuçlar

- Ürün "yalıtılmış" diye pazarlanmaz; güvence kapsam denetimi, doğrulama ve imzalı kanıttır.
- Mevcut `apply` değişmezleri korunur; yeni politika onları zayıflatamaz.

## Kaynaklar

- [Tehdit modeli](../THREAT_MODEL.md), özellikle §8 PoC ve S-01…S-25 senaryoları (erişim: 2026-10-30).
- [Mimari](../ARCHITECTURE.md) §2 ve §10 (erişim: 2026-10-30).
- [KANIT_LOG](../evidence/KANIT_LOG.md) §SEC-01 (erişim: 2026-10-30).
