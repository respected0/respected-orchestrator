# ADR-016 — Kurucu imzalama hattı fail-closed olmalıdır

## Durum

Kabul edildi.

## Bağlam

İmzasız kurucu SmartScreen uyarısı verir; imza kontrolü sessizce atlanırsa imzalı olmayan bir artefakt yayına çıkabilir. Üretim sertifikası yoktur.

## Karar

1. Authenticode doğrulaması fail-closed'dır: sertifika yoksa artefakt imzasız kalır ve `--require-signed` başarısız olur.
2. İmzalama hattı (`signtool sign /fd SHA256`) self-signed test sertifikasıyla gerçek kurucu üzerinde kanıtlandı; kurcalanmış artefakt ve yanlış imzalayan reddedildi.
3. Üretim sertifikası ve zaman damgası operasyonel bağımlılıktır; sertifika alınana kadar yayın imzasız çıkar ve bu açıkça belirtilir.

## Sonuçlar

- Gerçek kullanıcılar SmartScreen uyarısı görür.
- Sertifika alındığında yalnızca yapılandırma gerekir, hat hazırdır.

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §10 ve §11 (REL-01) (erişim: 2026-11-04).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §REL-01 (erişim: 2026-11-04).
