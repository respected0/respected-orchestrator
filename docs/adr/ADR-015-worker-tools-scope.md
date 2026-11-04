# ADR-015 — Desteklenen çalışan araçları ve Gemini CLI'nin kapsam dışı olması

## Durum

Kabul edildi.

## Bağlam

Her yeni çalışan aracı kota, onay modeli, kullanım bildirimi ve izolasyon yüzeyi getirir. Google artık Gemini CLI yerine Antigravity'yi kullanıyor; Gemini CLI eskidi ve Google modelleri `agy` (Antigravity) üzerinden kullanılabiliyor.

## Karar

1. Desteklenen araçlar: `codex`, `claude`, `agy` (Antigravity), `cursor`, `opencode`, `openrouter` ve ayrıcalıklı `custom`. Gemini CLI kapsam dışıdır, çünkü Google'ın aracı Antigravity ile değişti. Çalışan, MCP kaydı, kullanım ayrıştırma, belge ve kurucu metinlerinden kaldırıldı; kaynakta, paketlemede ve testlerde Gemini'ye atıf kalmadı.
2. Bir araç ancak gerçek CLI ile canlı doğrulanırsa desteklenir; doğrulanmamış iddia belgeye yazılmaz.
3. Cursor çalışanı AppContainer kum havuzunda çalışır. Kök neden: AppContainer adlandırılmış boruyu yalnız `\\.\pipe\LOCAL\` altında açabilir, libuv boruları reddedilir. Çözüm bir node-shimdir (`appcontainer-pipes.js`); güvenlik sınırları aynı kalır.
4. OpenRouter çalışanı araçsız bir modeldir: tam dosya içeriği döndürür, motor yolları kapsamla denetleyip yazar. Anahtar ve ağ kapısı ADR-007'ye tabidir.
5. Belirteç kullanımını bildirmeyen araçlarda kullanım `bilinmiyor` kaydedilir, sıfır sayılmaz.

## Sonuçlar

- Gemini CLI kullanan bir kurulum desteklenmez; Google modelleri için Antigravity (`agy`) kullanılır. Yeniden eklemek yeni bir karar ve canlı kanıt gerektirir.
- Otomatik atamada yazma rolleri için aday araçlar `codex`, `claude`, `agy`/`antigravity` ve `openrouter`dır; `cursor` ve `opencode` açık atamayla kullanılır.
- Her araç için ayrı kullanım ayrıştırıcısı ve izolasyon testi gerekir.

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §4 ve §10 (erişim: 2026-11-04).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §ADP-01, §ADP-03, §CUR-01, §COST-01 (erişim: 2026-11-04).
