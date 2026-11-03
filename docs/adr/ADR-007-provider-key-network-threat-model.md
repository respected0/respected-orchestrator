# ADR-007 — API anahtarı, ağ ve sağlayıcı tehdit modeli

## Durum

Kabul edildi (ADP-02). Uygulama kapısı `engine/provider_policy.py`; canlı sağlayıcı adaptörü ADP-03'tür.

## Bağlam

ADP-03 ile dış API sağlayıcıları eklenecek. Anahtarın diske düz metin yazılması, log/kanıta sızması, sessiz
fallback, yönlendirme (redirect) ve proxy üzerinden beklenmeyen alan adına çıkış gerçek risklerdir. Bugün
çalışanlar yalnızca kendi CLI oturumlarını kullanır; motor kendi sağlayıcı isteğini yapmaz.

## Karar

1. **Anahtar deposu:** Anahtar kalıcı ayar JSON'una, kanıta veya loga yazılmaz. Windows'ta işletim sisteminin
   kullanıcıya özel koruması (DPAPI) altındaki ayrı bir kasadan yalnızca istek anında okunur; süreç ortamına
   kalıcı olarak konmaz. Kasa yoksa adaptör çalışmaz; sessiz düz metin fallback yoktur.
2. **Opt-in:** Ağ varsayılan kapalıdır. Yalnızca `RESPECTED_PROVIDER_NETWORK=allow` açıkça verildiğinde istek
   yapılabilir. Kapalıyken ağ çağrısı `0`; adaptör soket açmadan reddeder.
3. **Kod kapısı:** Canlı sağlayıcı yolu `RESPECTED_PROVIDER_CODE_GATE=1` olmadan çalışmaz. Bu, yanlışlıkla
   yayınlanan bir adaptörün anahtar olmadan canlıya çıkmasını engeller.
4. **Egress:** Yalnızca `https`, kimlik bilgisi içermeyen URL ve açık allowlist'teki tam alan adı kabul edilir.
   Proxy de aynı allowlist'ten geçer. Her redirect hedefi `require_access` ile yeniden doğrulanır; güvenilen
   alan adından yabancı alan adına yönlendirme reddedilir.
5. **401/429/5xx:** 401 kimlik hatası, 429 kota ve 5xx sağlayıcı hatası ayrı sınıflanır; hiçbiri başka
   sağlayıcıya sessiz fallback yapmaz. Kullanıcı açıkça seçmedikçe model değişmez.
6. **Sızıntı:** Anahtar değeri log, kanıt, `settings.json`, `result.json`, hata metni ve görev metninde
   `***set***` olarak maskelenir. Hata gövdeleri de maskelenir; sağlayıcı gövdesi olduğu gibi saklanmaz.
7. **Kalıcılık:** İstek/yanıt gövdeleri varsayılan olarak saklanmaz; yalnızca kullanım sayaçları ve durum
   sınıfı tutulur. Hata ayıklama için gövde saklanacaksa açık opt-in ve redaction zorunludur.

## Test senaryoları (6/6 karara bağlandı)

| Senaryo | Karar | Kanıt |
|---|---|---|
| Opt-in kapalı | Soket öncesi `ProviderDenied`; ağ çağrısı `0` | `test_opt_in_off_denies_before_any_request` |
| Kod kapısı kapalı | Canlı sağlayıcı reddedilir | `test_code_gate_off_denies_live_provider` |
| Yasak alan adı | Allowlist dışı host reddedilir | `test_denied_domain_is_rejected` |
| HTTP redirect | Hedef yeniden doğrulanır; yabancı host reddedilir | `test_redirect_target_must_pass_the_same_gate` |
| Proxy / URL'de kimlik | `http` ve `user:pass@host` reddedilir | `test_http_proxy_or_credentials_in_url_are_rejected` |
| Log/kanıt sızıntısı | Anahtar `***set***` ile maskelenir | `test_secret_is_redacted_before_logging` |

## Sonuçlar

- ADP-03 adaptörü `require_access` çağırmadan istek başlatamaz; kapı test edilir.
- Anahtarın DPAPI kasası ADP-03 ile birlikte gelecek; bu ADR depo biçimini ve sınırları sabitler.
- Proxy istemcisi allowlist dışına çıkamaz; kurumsal proxy kullanılıyorsa proxy host'u da allowlist'e eklenir.
- Sağlayıcıya giden görev metni ve dosya içeriği yine sağlayıcıya görünür; opt-in bunu kabul etmek demektir.

## Kaynaklar

- [ADP-02 kanıtı](../ilerleme/KANIT_LOG.md) §ADP-02 (erişim: 2026-11-03).
- [Mimari](../ARCHITECTURE.md) §2 (erişim: 2026-11-03).
- [Tehdit modeli](../THREAT_MODEL.md) (erişim: 2026-11-03).
