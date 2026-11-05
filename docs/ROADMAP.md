# Orchestrator: gelecekte yapılacaklar

> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Güncelleme

- [ ] Kurucu düzeyinde beta.1 → beta.2 yerinde güncelleme (Inno: yedek, `update-backup`, geri alma) gerçek kurulumla denenmedi; motor düzeyi kanıtlı (`tests/tools/upgrade_proof.py`). Kurucu betiği beta.1'den yalnızca `CloseApplications` ve işçi listesi satırlarında farklı.
- Sonraki biçim değişikliğinde yeni sürüm için `migrate.STEPS`'e yeni adım ve `tests/fixtures/releases/<sürüm>/` eklenir; eski adımlar silinmez.

---

## İlk sabit sürümü öncesi kontrol edilecek (v.1.0 öncesi)

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.


