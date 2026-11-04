# ADR-005 — Başarısızlık taksonomisi ve tekrar deneme politikası

## Durum

Kabul edildi ve QUA-02 kapsamında uygulandı (2026-10-30); QUA-03 ile sonlu durum makinesine bağlandı (2026-11-01).

## Bağlam

Test hatası, ortam arızası, kota, kimlik doğrulama ve kapsam ihlali aynı retry politikasıyla ele alınırsa gereksiz maliyet ve tekrar eden hata üretilir.

## Karar

Sekiz sınıf kullanılacak: `test_failure`, `policy_denied`, `timeout`, `quota`, `auth`, `infrastructure`, `stale_patch`, `reviewer_reject`.

- `test_failure` ve `NEEDS_CHANGES` yalnızca `max_fix_rounds` (varsayılan 2, üst sınır 5) kadar kanıta dayalı düzeltme alabilir. `NEEDS_CHANGES` ara durumdur; sınır dolduğunda `FIX_ROUNDS_EXHAUSTED`, aynı normalize test hatası tekrarladığında `REPEATED_TEST_FAILURE` terminal durumudur. Nihai `REJECTED` kararı otomatik düzeltmeye alınmaz; insan kararı gerekir.
- `timeout` ve `infrastructure` sınırlı yeniden deneme alabilir.
- `auth`, `quota` ve `policy_denied` **otomatik yeniden denenmez**; insan veya yapılandırma müdahalesi gerekir.
- `stale_patch` otomatik yeniden uygulanmaz; yeni yama gerekir.
- Sınıf, JSON sonucunda ve kanıtta korunur; retry sayısı üst sınırı aşamaz.

## Sonuçlar

- Sınıflar `engine/failures.py` içinde tek kaynakta tanımlıdır; motor ve MAF aynı eşlemeyi kullanır.
- Hata sınıfı kaybolursa retry kararı verilemez; bu bir kabul kriteridir.
- Kota/kimlik hatalarında otomatik retry sayısı sıfırdır; `retry_task` bu kayıtları açık hatayla reddeder.

## Kaynaklar

- [Kanıt kaydı](../evidence/KANIT_LOG.md) §QUA-02 (erişim: 2026-10-30).
- [Mimari](../ARCHITECTURE.md) §2 Codex sonucu ve hata sınıfları (erişim: 2026-10-30).
