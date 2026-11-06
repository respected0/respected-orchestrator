# ADR-022 — Komut/yetki matrisi ve onay otoritesi sözleşmesi

## Durum

Kabul edildi (6 Kasım 2026). Görev: B3-00.03. Uygulama: `src/respected_orchestrator/engine/authority.py` (saf politika).
Henüz CLI/MCP/runner'a bağlanmadı; mevcut davranış değişmedi. Bağlama B3-05.02'de yapılır.

## Bağlam

Bugünkü onay: `approve_maf_task` yalnızca `RESPECTED_ORCH_CHILD` olmayan ve etkileşimli TTY'li süreçte çalışır; onay
kaydı run, patch digest, proje parmak izi ve HEAD'e bağlıdır, ikinci onay reddedilir (ADR-004). GUI'de bu iki işaret
(TTY, ortam değişkeni) yoktur; renderer güvenilmezdir. Ayrı bir yetki sınıfı modeli gerekir.

## Karar

Dört yetki sınıfı ve beş köken. Varsayılan ret.

| Köken \ Sınıf | READ (durum/okuma) | TASK (başlat/iptal) | SETTINGS | PRIVILEGED (approve, apply, ayrıcalıklı anahtar) |
|---|---|---|---|---|
| HUMAN (TTY operatör veya yerel human-presence authority) | Evet | Evet | Evet | Evet |
| RENDERER | Evet | Evet | Evet | **Hayır** |
| MCP | Evet | Evet | Hayır | **Hayır** |
| WORKER | Hayır | Hayır | Hayır | **Hayır** |
| CHILD (orkestre edilen herhangi süreç) | Hayır | Hayır | Hayır | **Hayır** |

Kurallar:

1. `RESPECTED_ORCH_CHILD=1` olan süreç hangi kökeni iddia ederse etsin CHILD sayılır (`effective_origin`; devredilmiş child-origin).
2. Onay `Grant(scope, run_id, patch_sha256, nonce)` ile verilir; üçü de eşleşmeli ve nonce tek kullanımlıktır (`check_grant`). Başarısız denetim nonce'u tüketmez.
3. İnsan varlığı kanıtı renderer'dan gelemez: B3-05.02'de native kabuk, renderer'ın erişemediği bir onay penceresiyle HUMAN kökenini üretir.
4. Mevcut `check`/`apply`/`maf-approve` akışı değişmez; GUI yalnızca bu akışı çağıran ek bir giriştir.

Protokol örneği (`apply`): native kabuk onay penceresinde patch digest'i gösterir → insan onaylar → kabuk `Grant("apply", run, digest, rastgele_nonce)` üretir → motor `authorize(HUMAN, PRIVILEGED)` + `check_grant(...)` + mevcut `check_result`/`apply_task` yeniden denetimini çalıştırır. Renderer'dan gelen aynı çağrı `PermissionError` alır.

## Sonuçlar

- AI/MCP/renderer insanın yerine geçemez; yanlış patch, yanlış run, farklı kapsam ve tekrar oynatma reddedilir.
- Politika tek yerde ve tam matris testlidir (5 köken × 4 sınıf).
- Risk: nonce deposu şimdilik çağıranın belleğindedir; kalıcı depo ve imzalı kabuk kimliği B3-05.02'de gerekir. Bu ADR kimlik doğrulama iddia etmez (bkz. `approve_maf_task` notu).

## Kaynaklar

- [ADR-004](ADR-004-human-approval-boundary.md), [ADR-021](ADR-021-desktop-boundary-baseline.md).
- `docs/THREAT_MODEL.md` §4 ve §12 (erişim: 2026-11-06).
- `docs/ROADMAP.md` B3-00.03 (erişim: 2026-11-06).
