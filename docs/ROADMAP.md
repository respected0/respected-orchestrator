# Orchestrator: gelecekte yapılacaklar

> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Güncelleme

- [ ] Kurucunun geri alma yolu (beta.2 `repair` başarısız olunca beta.1'in geri gelmesi) temiz bir senaryoyla kanıtlanmadı; mutlu yol kanıtlı (`KANIT_LOG.md` "kurucu düzeyi güncelleme").
- Sonraki biçim değişikliğinde yeni sürüm için `migrate.STEPS`'e yeni adım ve `tests/fixtures/releases/<sürüm>/` eklenir; eski adımlar silinmez.

---

## İlk sabit sürümü öncesi kontrol edilecek (v.1.0 öncesi)

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.


