# Orchestrator: gelecekte yapılacaklar

Ürün beklentisiyle bugünkü durum arasındaki açıklar (2026-10-22 değerlendirmesi). Yapılan madde işaretlenir ya da silinir.

## Her AI ile çalışma

- [ ] **OpenCode** çalışanı ve MCP kaydı (`interfaces/integrations.py` bugün claude-code, codex, cursor, gemini, windsurf).
- [ ] **OpenRouter / API tabanlı modeller**: bugün çalışanlar yalnızca komut satırı araçları (codex, claude, gemini, agy,
  cursor, custom). Çin modelleri (GLM, DeepSeek, Qwen, Kimi) yalnızca bir aracın profili üzerinden çalışıyor; kendi
  desteği yok.

## Master–worker rolleri

- [ ] `tester` ve `coordinator` rolleri tanımlı ama hiçbir aşamada kullanılmıyor (`ARCHITECTURE.md` §4).
- [ ] Otomatik atama görev zorluğunu ve fiyatı modellemiyor.

## Token tasarrufu

- [ ] Claude, Gemini ve Cursor token kullanımını bildirmiyor; kullanım "bilinmiyor" kaydediliyor ve bütçeden varsayılan
  miktar düşülüyor. Bu çalışanlarda gerçek ölçüm yolu bulunmalı.
- [ ] İncelemelerde `model: null` görünüyor (sağlayıcı olayı modeli bildirmiyor).

## Araştırmaya dayalı tasarım

- [ ] Rakip analizi ve araştırma belgesi: CrewAI, AutoGen, LangGraph, OpenHands gibi orkestrasyon ürünleriyle karşılaştırma
  ve kararların dayandığı makaleler/ölçümler yazılı değil.

## Yayın

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı).
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok.
