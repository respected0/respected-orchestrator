# ADR-021 — Masaüstü (Beta.3) sürüm bazı ve değişmez ilke matrisi

## Durum

Kabul edildi (6 Kasım 2026). Görev: B3-00.01. Sözleşme değişikliği içermez; yalnızca mevcut durumu dondurur.
Sonraki görevler (B3-00.02..04) bu bazı değiştirmeden genişletir.

## Bağlam

Beta.3, motorun CLI/MCP'deki insan-onayı güven sınırını GUI'ye taşır. Bunun gevşememesi için önce **bugün neyin
korunduğunu ve hangi testin korumasını** kayda geçirmek gerekir. ROADMAP §4.1'deki sekiz değişmez ilke tek tek
mevcut testlerle eşlendi; testi olmayanlar boşluk olarak işaretlendi. Hiçbir Beta.2 işi Beta.3 tamamlandı diye sayılmaz.

Baz: depo commit `ec9e599` (main), sürüm beta.2.

## Karar

1. **Baz dondurulur:** `ec9e599` + bu ADR'nin commit'i. Beta.3 işleri bu bazın testlerini kırmadan ilerler.
2. **Mevcut insan-onayı yolu aynen korunur:** `maf-approval.json` yalnızca etkileşimli TTY'den; `apply` yeniden denetler.
3. **GUI bu yolu atlayan ikinci bir yürütme yolu açmaz.** GUI için ayrı human-presence authority B3-00.03 / B3-05.02'de tasarlanır; o zamana kadar GUI salt okunurdur.
4. **Boşluklar sessizce kapatılmaz;** aşağıdaki tabloda sahibi olan göreve bağlanır.

### Değişmez ilke matrisi

| ID | İlke (ROADMAP §4.1) | Mevcut test kaynağı | Durum |
|---|---|---|---|
| I-01 | Worker AppContainer/sandbox fail-closed; yeni oturum korumasız süreç açamaz | `tests/engine/test_sandbox.py`, `tests/engine/security_cases.py` + `test_worker_security.py`, `tests/packaging/test_frozen_security.py`, `tests/engine/test_security_gate.py` | Kaynakta var. PTY/Chat oturumu henüz yok → B3-03.02 yeni testi getirmeli |
| I-02 | `check`, imzalı kanıt, kapsam, tazelik, `git apply --check`; `apply` yeniden denetler; otomatik commit/merge yok | `tests/engine/test_review_apply_invariants.py` (12 ret + `test_verified_check_then_apply_succeeds_once`), `tests/engine/test_runner.py` | Var. **Boşluk kapandı:** "apply HEAD'i değiştirmez" iddiasını doğrulayan assertion bu commit'te eklendi |
| I-03 | MCP, worker, renderer, yetkisiz child insan onayı veremez; GUI için ayrı authority | `tests/interfaces/test_human_approval_contract.py` (8 test: kendi onayı, TTY şartı, replay, drift, iptal, head değişimi), `tests/interfaces/test_mcp_server.py::test_privileged_task_options_are_refused_over_mcp_and_bypass_flags_are_not_commands` | CLI/MCP için var. **Boşluk G-1:** renderer/GUI authority yok (henüz GUI yok) → B3-00.03, B3-05.02 |
| I-04 | Başka uygulama olmadan tam kullanım | Hub'sız çalışan CLI/MCP testlerinin tümü (`tests/interfaces`, `tests/test_main.py`) | Kısmen. **Boşluk G-2:** "Hub/Brain yokken uçtan uca" adlandırılmış tek bir test yok → B3-00.04 / B3-09 |
| I-05 | Keşif ≠ doğrulanmış kullanılabilirlik ≠ güven ≠ etkinleştirme; otomatik kurulum yok | Yok (envanter henüz yok) | **Boşluk G-3:** B3-08.02 durum ayrımını testle başlatmalı |
| I-06 | Bilinmeyen maliyet/token `unknown`, asla 0 | `tests/engine/test_pricing.py::test_unknown_model_is_never_zero`, `::test_missing_usage_is_unknown_not_zero` | Var |
| I-07 | Veri şeması değişirse sürümlü migration + gerçek eski fixture + rollback | `tests/interfaces/test_migrate.py` (eski sürüm taşıma, bozuk adım sıfır yazım, daha yeni veri reddi), `tests/workflows/test_checkpoint.py`; kurucu geri alma kanıtı `docs/evidence/poc/upgrade_beta1_to_beta2.json` | Var; yeni şema eklendiğinde geçerli |
| I-08 | `PRODUCT_CONTRACT.md` kopya/conformance etkisi planlanır; başka ürün koduna dokunulmaz | `docs/PRODUCT_CONTRACT.md` (3 kopya kuralı) | **Boşluk G-4:** bu depoda kopya eşitliğini denetleyen test bulunamadı → B3-00.04 |

### Beta.2 kapılarının gerçek durumu (belgeden değil kanıt kaydından)

| Kapı | Durum | Kaynak |
|---|---|---|
| AppContainer testleri skip=0 | Hosted koşu 28/28, skipped 0 (koşu 42006314204, commit a700aff) | KANIT_LOG §FIX-01 |
| Verify ağ sınırı | Kapandı (ADR-018, S-24) | THREAT_MODEL §11 |
| Gerçek ajan kıyası | FIX-02 geçerli koşu kayıtlı; `compare.py` sentetik, kıyas sayılmaz | KANIT_LOG §FIX-02 |
| PR/CI geri bildirimi | Canlı kanıt kayıtlı (FIX-03A/B) | KANIT_LOG §FIX-03 |
| Güncelleme/geri alma | beta.1→beta.2, 29 adım PASS | KANIT_LOG §beta.1 → beta.2 |

## Sonuçlar

- Dört açık boşluk (G-1..G-4) sahibi görevlerle eşlendi; hiçbiri sessizce "tamam" sayılmaz.
- Beta.3 GUI, I-03 için testli bir human-presence authority olmadan onay/apply eylemi sunamaz.
- Bu ADR kod davranışını değiştirmez; tek kod değişikliği I-02 için eklenen testtir.

## Kaynaklar

- `docs/ROADMAP.md` §4.1, §7 B3-00.01 (erişim: 2026-11-06).
- `docs/THREAT_MODEL.md` §4, §9, §10 (erişim: 2026-11-06).
- [ADR-004](ADR-004-human-approval-boundary.md), [ADR-018](ADR-018-verify-network-isolation.md).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §B3-00.01 (erişim: 2026-11-06).
