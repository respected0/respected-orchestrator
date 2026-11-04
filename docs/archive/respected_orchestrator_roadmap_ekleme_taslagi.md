# ROADMAP.md için önerilen EK — YENİ AÇIKLAR

> Buradaki maddeleri var olan `docs/ROADMAP.md` sonuna ekleyebilirsin. Var olan dokuz madde silinmemeli; bunlar onların tamamlayıcısıdır. Ayrıntılı issue tanımları `docs/ROADMAP_EXECUTION_PLAN.md` dosyasına konulabilir.

## Worker güvenliği
- [ ] Worker süreçleri için işletim sistemi seviyesinde sandbox, izin politikası ve negatif güvenlik testleri (`SEC-01`..`SEC-04`).
## Ölçüm ve doğrulamalı teslimat
- [ ] Tekrarlanabilir benchmark ve başarı/güvenlik/maliyet raporu (`EVAL-01`..`EVAL-03`).
- [ ] Tester rolü, hata sınıflandırması, sınırlı otomatik düzeltme ve apply değişmezleri (`QUA-01`..`QUA-04`).
## Planlama ve paralellik
- [ ] Plan DAG/ownership, bağımlılık tabanlı scheduler ve güvenli patch entegrasyonu (`SCH-01`..`SCH-03`); mevcut coordinator açığı `SCH-04` ile kapatılır.
## Kanıt ve kullanıcı onayı
- [ ] Salt okunur kanıt görünümü ve Hub Decision Center; MCP üzerinden insan onayı üretilmeyecek (`UX-01`..`UX-03`).
## Devamlılık ve hafıza
- [ ] Sürümlü checkpoint, güvenli resume ve isteğe bağlı Brain karar notları (`RES-01`..`RES-03`).
## GitHub ve yetenek ekosistemi
- [ ] Salt okunur issue içe alma, kullanıcı izinli taslak PR ve CI geri bildirimleri (`GH-01`..`GH-03`).
- [ ] Skill/MCP yetenek bildirimi ve kısıtlı arama adaptörleri (`EXT-01`..`EXT-02`).
## İlk kullanım
- [ ] CLI/Hub bağımsız, güvenli ilk görev onboarding ve health wizard (`REL-03`).

> Var olan ROADMAP maddelerinin ayrı eşlemesi: OpenCode=`ADP-01`; API=`ADP-02/03`; tester=`QUA-01`; coordinator=`SCH-04`; routing=`COST-02/03`; kullanım=`COST-01`; araştırma=`DOC-01`; imza=`REL-01`; POSIX=`REL-04`; migration=`REL-02`.
