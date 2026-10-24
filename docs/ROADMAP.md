# Orchestrator: gelecekte yapılacaklar

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Her AI ile çalışma

- [ ] **OpenCode** çalışanı ve MCP kaydı (`interfaces/integrations.py` bugün claude-code, codex, cursor, gemini, windsurf).
  Geliştirme makinesinde OpenCode kurulu değil; gerçek çalıştırmayla doğrulanamadığı için yazılmadı.
- [ ] **OpenRouter / API tabanlı modeller**: bugün çalışanlar yalnızca komut satırı araçları (codex, claude, gemini, agy,
  cursor, custom). Çin modelleri (GLM, DeepSeek, Qwen, Kimi) yalnızca bir aracın profili üzerinden çalışıyor; kendi
  desteği yok. Anahtarın saklanması ve sağlayıcı/fiyat seçimi karar bekliyor.

## Master–worker rolleri

- [ ] `tester` ve `coordinator` rolleri için aşama yok; bugün atanırlarsa `ROLE_NOT_EXECUTABLE` döner (`ARCHITECTURE.md` §4).
- [ ] Otomatik atama görev zorluğunu ve fiyatı modellemiyor.

## Token tasarrufu

- [ ] Gemini ve Cursor token kullanımı doğrulanamadı: Claude ve agy kullanımı gerçek çalıştırmayla doğrulandı
  (Claude modeli de bildiriyor, agy modeli bildirmiyor, o yüzden agy incelemelerinde `model: null` doğru).
  Gemini çalışanı Windows'ta npm'in `.cmd` kabuğu olarak kurulduğunda kullanılamıyor (cmd.exe komut enjeksiyonu
  kuralı); Cursor geliştirme makinesinde kurulu değil. İkisi için ölçüm yolu gerçek araçla denenmeli.

## Araştırmaya dayalı tasarım

- [ ] Rakip analizi ve araştırma belgesi: CrewAI, AutoGen, LangGraph, OpenHands gibi orkestrasyon ürünleriyle karşılaştırma
  ve kararların dayandığı makaleler/ölçümler yazılı değil.

## Yayın

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.

## Güncelleme

- [ ] Biçimi değiştiren ilk sürümde `interfaces/migrate.py` içindeki `STEPS` tablosuna eski sürüm için taşıma adımı
  eklenmeli (mekanizma ve test hazır; bugün gönderilmiş tüm biçimler güncel olduğu için adım yok).
  Her yayında o sürümün gerçek veri dosyaları `tests/fixtures/releases/<sürüm>/` altına da kopyalanır (sözleşme §4).
