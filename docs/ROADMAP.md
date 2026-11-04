# Orchestrator: gelecekte yapılacaklar

> Yürütme sırası, kapılar ve görev durumu: `ROADMAP_EXECUTION_PLAN.md`.
> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`. Tamamlanan görevlerin özeti: `ROADMAP_EXECUTION_PLAN.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Yayın

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.

## Güncelleme

- [ ] Biçimi değiştiren ilk sürümde `interfaces/migrate.py` içindeki `STEPS` tablosuna eski sürüm için taşıma adımı
  eklenmeli (mekanizma ve test hazır; bugün gönderilmiş tüm biçimler güncel olduğu için adım yok).
  Her yayında o sürümün gerçek veri dosyaları `tests/fixtures/releases/<sürüm>/` altına da kopyalanır (sözleşme §4).
