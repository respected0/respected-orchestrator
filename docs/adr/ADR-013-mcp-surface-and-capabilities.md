# ADR-013 — MCP sunucusu izinleri ve salt-okunur MCP istemcisi

## Durum

Kabul edildi.

## Bağlam

Orchestrator'ın MCP sunucusu prompt enjeksiyonuna uğramış bir modelin isteğini alabilir; dış MCP araçlarının çıktısı da güvenilmeyen veridir.

## Karar

1. MCP üzerinden `custom` worker, serbest `command`, `apply_root`, `engine_source` ve onaylanmamış `verify` komutları, sunucu `--allow-privileged` ile kaydedilmedikçe reddedilir. `--allow-auto-apply` yalnızca `auto_apply` reddini kaldırır.
2. Doğrulama komutları `mcp_acceptance_allow` ön eklerinden biriyle kelimesi kelimesine başlamak zorundadır; varsayılan liste boştur.
3. Özyineleme yoktur: `RESPECTED_ORCH_CHILD` ya da `RESPECTED_ORCH_DELEGATED` tanımlıyken bütün araçlar gizlenir ve reddedilir.
4. İnsan onayı (`maf-approve`, `project-approve`) MCP'den sunulmaz.
5. Dış MCP sunucusuna bağlanan istemci (`StdioMcpClient`) yalnızca yetenek manifestosunda `read` izinli araçları çalıştırır; zaman aşımı, bayt sınırı, yol kaçışı ve sır sızıntısı fail-closed'dır. Araç çıktısı güvenilmeyen veridir.
6. Belirli bir MCP sunucusuna bağımlılık yoktur.

## Sonuçlar

- Hub, MCP sunucusunu ayrıcalıklı bayraklarla hiç kaydetmez.
- Ön ek izin listesi her argümana izin verir; dar ön ekler yazılmalıdır (belgelenmiş sınır).
- MCP'ye yeni araç eklemek bu izin matrisini güncellemeyi gerektirir.

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §6 ve §11 (EXT-02) (erişim: 2026-11-04).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §EXT-01, §EXT-02 (erişim: 2026-11-04).
