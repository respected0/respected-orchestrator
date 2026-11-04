# ADR-019 — Gerçek ajan benchmark'ı ve ücretsiz çalışma kuralı

## Durum

Kabul edildi (5 Kasım 2026). Uygulama FIX-02 ile yapılır. ADR-002'yi değiştirmez, tamamlar.

## Bağlam

`tests/evals/compare.py` sentetiktir: orkestre kolda `fixture.fixed_source` yazılır, doğrudan kolda hiçbir şey
yapılmaz. Bu harness'in tutarlılığını ölçer, ajan başarısını değil (EVAL-02/03 "Kalan risk"). Gerçek karşılaştırma
gerçek ajan çağrısı demektir; bu token, kota ve para riski taşır. Sahibin kuralı: **cebinden para çıkmaz**.

## Karar

1. **İki ayrı ürün.** Sentetik harness aynen kalır, çıktısına `kind: "synthetic"` yazılır. Gerçek benchmark ayrı
   şema (`respected.eval.bench.v1`), ayrı dosya ve `kind: "real"` ile üretilir. Sentetik rapor gerçek olarak sunulmaz.
2. **Altın çözüm yasağı.** Gerçek koşuda `fixed_source` ajana, komuta, ortam değişkenine ya da çalışma dizinine
   girmez. Yalnızca gizli kabul komutu çalışır. Sızıntıyı yakalayan test zorunludur.
3. **Ücretsiz yol kuralı.** Yalnızca marjinal maliyeti **0 TL** olan ajan/model kombinasyonu koşar:
   - ücretsiz katmandaki modeller (OpenRouter `:free` modelleri, OpenCode'un ücretsiz modelleri),
   - kullanıcının hâlihazırda ödediği abonelik kotası içindeki CLI'lar; **yalnızca** kullanımın kotadan düştüğü ve
     ek faturaya gitmediği kullanıcı tarafından doğrulandıysa (aşağıdaki Claude Code ölçümüne bakın),
   - kullanım başına faturalı API anahtarı **kullanılmaz**.
   Maliyet çıktısı `engine/pricing.py` ile yoksa ya da fiyatı sıfır olarak doğrulanamıyorsa koşu başlamaz.
4. **Parti öncesi onay.** Her koşu partisi (ajan x model x görev kümesi) başlamadan önce kullanıcıya sorulur
   (hafıza kuralı). Kota hatası (429) ya da fatura belirtisi görülürse parti durur; yeniden denemeyle üstüne gidilmez.
5. **Ölçülemeyen değer uydurulmaz.** Token/maliyet bilinmiyorsa `unknown`; `0` yazılmaz. Mevcut `compare.py`'deki
   `"bilinmiyor"` yazımı ile `evidence_view`'daki `unknown` yazımı gerçek rapor şemasında tek biçime bağlanır
   (`unknown`); sentetik rapor değişmez.
6. **Temsilî görev ölçütü.** 20 fixture arasından şunları sağlayan ≥10 görev seçilir: gerçek bir bug ya da küçük
   özellik, yalnızca standart kütüphane ile doğrulanabilir (ağsız, ADR-018 ile uyumlu), tek komutla kabul edilir,
   başlangıç SHA'sı `start_shas.json` içinde sabit. Seçimin gerekçesi rapora yazılır.
7. **Kol eşitliği.** Aynı ajan sürümü, model kimliği, başlangıç commit'i, timeout ve makine; ikisi için de kayıtlı.
   Direct kol kum havuzsuz çalışır; bu yüzden güvenlik ihlali sayacı yalnızca Orchestrated kolun sınırını ölçer ve
   raporda böyle etiketlenir.
8. **Tekrar.** Görev başına ≥3 tekrar; rapor ham koşuları ve dağılımı verir, tek eşik karar vermez.

## Ölçüm: Claude Code CLI çıktısı (5 Kasım 2026, claude 2.1.318, tek çağrı, kullanıcı onaylı)

`claude -p "ok" --output-format json --max-budget-usd 0.05` makine okunur JSON döndürdü. Bulgular:

- Tutarlı sayılar `modelUsage.<model>` altında (`inputTokens`, `outputTokens`, `cacheReadInputTokens`,
  `cacheCreationInputTokens`, `costUSD`). Üst düzey `usage` alanı bu çağrıda **sıfır** gösterdi, yani yanıltıcı;
  adaptör yalnızca `modelUsage`'a güvenmeli ve iki kaynak çelişirse `unknown` yazmalı.
- `total_cost_usd` ve `costBasis: "list"`: liste fiyatı üzerinden varsayımsal tutar; aboneliğin gerçek faturasını
  göstermez. Rapora "liste fiyatı tahmini" olarak yazılır, harcanan para diye sunulmaz.
- Çağrı başına sabit yük büyük: yaklaşık 58 bin önbellek tokeni için "ok" tek kelimesi liste fiyatıyla 0,129 USD
  çıktı ve `--max-budget-usd 0.05` sınırı aşıldı (`subtype: error_max_budget_usd`, `is_error: true`). Küçük bütçe
  sınırı CLI'ı daha ilk turda keser; benchmark koşusunda bütçe sınırı gerçekçi seçilmeli ya da kota kullanılmalı.
- Bu çağrının abonelik kotasından mı yoksa ücretli krediden mi düştüğü **CLI çıktısından anlaşılamadı** (`provider:
  firstParty`). Bu yüzden Claude Code, "marjinal maliyeti sıfır" kuralını sağladığı kanıtlanana kadar benchmark'ta
  varsayılan ajan olmaz; kullanıcı hesabında ödeme yöntemi/kredi durumunu kendisi doğrular.

## Sonuçlar

- Ücretsiz model kalitesi düşük olabilir; sonuç "ürün başarısı" değil "bu model ile ölçüm" olarak sunulur.
- Claude Code CLI'ın JSON çıktısı makine okunurdur ama sayılar `modelUsage` altında güvenilir, üst düzey `usage`
  sıfır olabilir; çelişkide `unknown` yazılır.
- Beta.2 kapısı en az bir ücretsiz ajanla tamamlanmış gerçek koşu ister; her ajan zorunlu değildir.

## Kaynaklar

- [ADR-002](ADR-002-reproducible-evaluation.md), [ADR-007](ADR-007-provider-key-network-threat-model.md).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §EVAL-02, §EVAL-03, §COST-02 (erişim: 2026-11-05).
