# Orchestrator: gelecekte yapılacaklar

> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Yayın

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.

## Güncelleme

- [ ] beta.2 yayınlanırken o sürümün gerçek veri dosyaları `tests/fixtures/releases/0.1.0-beta.2/` altına kopyalanmalı
  (sözleşme §4). `settings.json` 1→2 taşıma adımı (`STEPS`) hazır ve beta.1 fixture'ı ile sınanıyor; sonraki biçim
  değişikliğinde yeni sürüm için yeni adım eklenir, eski adımlar silinmez.
