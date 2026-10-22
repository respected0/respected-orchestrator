# Respected Orchestrator deposu: çalışma kuralları

Bu, bağımsız Respected Orchestrator kaynağıdır. Belgeler: `README.md` (giriş), `docs/USAGE.md` (kullanım), `docs/COMMANDS.md` (komutlar ve istek biçimleri),
`docs/ARCHITECTURE.md` (bağlayıcı kurallar ve güvenlik sınırları). Üç ürünün ortak sözleşmesi ekosistem kökündeki `docs/PRODUCT_CONTRACT.md` dosyasındadır ve
`conformance/` ile ölçülür.

## Yasaklar

- SecondBrain'in kodunu içe aktarma (onunla yalnızca `rpp` komutuyla konuş), not kasası isteme, global bağımlılık kurma,
  kişinin gerçek verisini değiştirme.
- Kullanıcı açıkça istemedikçe commit, push ya da paralel ajan yok.
- Geçiş dönemi, eski sürüm desteği, takma ad ya da uyumluluk katmanı ekleme.

## Sınırlar

- Ortak komutlar: `--version`, `setup`, `repair`, `uninstall [--purge]`, `config [get|set]`, `health`,
  `memory connect|disconnect|status`, `integrations [set]`, `rpp`, `mcp`. Çıktı JSON, hata `{"error": {code, message, hint}}`,
  çıkış kodu 0/1/2.
- Program dosyaları kurucunundur (`packaging/windows/orchestrator_setup.iss`; ortak bölümleri SecondBrain'inkinden
  üretilir). `update` komutu ve protokol üzerinden kurma işlemi yoktur.
- `--data-root` yalnızca motorun kendi alt süreçleri içindir; kişiler `RESPECTED_DATA_DIR` kullanır.
- Kapsam denetimleri, süre sınırları, süreç ağacı temizliği, başarısız/bayat/kurcalanmış sonuçların reddi ve açık sınırlı
  yeniden denemeler korunur.
- Motorun her yeniden başlatılması `context.engine_command` üzerinden (paketlenmiş exe'de de çalışmalı), her alt süreç
  `engine/winproc` üzerinden geçer. Çalışan test verileri ve Git işlemleri geçici projelerde yapılır.

## Değişiklik disiplini

- Tamamlandı demeden önce: `python -m unittest discover -s tests -t .`; paketleme değişikliğinde ayrıca
  `python packaging/build_dist.py` ve `python -m unittest tests.packaging.test_frozen_build`.
- `docs/ARCHITECTURE.md` koda bağlayıcıdır; aynı değişiklikte doğru tut. Belgeler Türkçedir; testler belge cümlelerine bağlanmaz.
- Süreç aracı adını taşıyan klasör açma.
