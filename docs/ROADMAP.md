# Orchestrator: gelecekte yapılacaklar

> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Beta.2 yayın günü

- [ ] Yayın commit'inde `ci` (hosted güvenlik matrisi + kapı) yeşil olmalı; kanıt başka commit'e aitse geçersizdir. Kanıt: `evidence/KANIT_LOG.md` ("FIX-01 / FIX-03A / FIX-03B"), kararlar ADR-017..020.
- [ ] Orchestrated kolun gerçek ajan benchmark'ında (%70, Direct %96,7) 9 başarısızlığının nedenini çözümle (`KANIT_LOG.md` "FIX-02 gerçek koşu"); "orkestratör daha iyi" iddiası bu sonuçla desteklenmiyor.
- [ ] Canlı GitHub testi (`tests/interfaces/test_github_live.py`) en düşük yetkili bir token ile yinelenmeli (bugün `gh` oturumuyla koştu).

### Güncelleme

- [ ] beta.2 yayınlanırken o sürümün gerçek veri dosyaları `tests/fixtures/releases/0.1.0-beta.2/` altına kopyalanmalı
  (sözleşme §4). `settings.json` 1→2 taşıma adımı (`STEPS`) hazır ve beta.1 fixture'ı ile sınanıyor; sonraki biçim
  değişikliğinde yeni sürüm için yeni adım eklenir, eski adımlar silinmez.
---

## İlk sabit sürümü öncesi kontrol edilecek (v.1.0 öncesi)

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.


