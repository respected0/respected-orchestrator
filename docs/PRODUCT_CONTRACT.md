# Respected ürün sözleşmesi v1

Durum: **uygulandı** (2026-10-22). Üç repo (Hub, Brain, Orchestrator) buna uyar; her depoda aynı kopya durur. Uyum Hub deposundaki `conformance/` ile ölçülür
(`python -m unittest discover -s conformance`, kaynakta ya da `RESPECTED_CONFORMANCE_<ÜRÜN>_EXE` ile derlenmiş programda; üç kopyanın aynı olduğunu da denetler).
Geçiş dönemi, eski sürüm desteği ya da uyumluluk katmanı yoktur: bir şey değiştiğinde her yerde değişir, eski yolu silinir.
**Tek istisna kişinin verisidir** (ilk yayından, 0.1.0-beta.1'den beri): ayar, kurulum kaydı ve çalışma verisinin biçimi
(`schema_version`) değişirse yeni sürümün `repair`'i eski biçimi yerinde taşır; güncelleme kişiden hiçbir şey istemez.

## 1. İlke

- **Her ürün Hub'dan bağımsızdır.** Kurma, onarma, güncelleme, kaldırma, ayar değiştirme ve ürünlerin birbirine bağlanması
  Hub olmadan yapılabilir: kurucuyu yeniden çalıştırarak ya da ürünün komutlarıyla.
- **Hub yalnızca kolaylıktır:** katalog, indirme, ürünün kurucusunu çalıştırma ve görsel arayüz. Hub'ın yaptığı her işin Hubsız
  bir karşılığı vardır ve Hub o karşılığı çağırır. Hub ürün hakkında hiçbir şey saklamaz.
- Sonradan Hub kurulursa hiçbir şey taşınmaz ve sorulmaz: Hub, ürünü ve ayarlarını ürünün kendisinden okur.
- Ortak kod çalışma zamanı bağımlılığı değildir. Ortak olan bu belge (üç depoda aynı kopya), Hub deposundaki `conformance/` ve kurucuların ortak bölümüdür.

## 2. Klasörler

```
%LOCALAPPDATA%\Respected\
  RespectedBrain\        app\ (program, distribution.json, unins000.exe)   data\ (ayarlar, kayıtlar, yedekler)
  RespectedOrchestrator\ app\ (program, distribution.json, unins000.exe)   data\ (ayarlar, görev çalışmaları)
  RespectedHub\          app\                                              managed\ (indirilen kurucular, Hub'ın işlem günlüğü)
Not kasası: kullanıcının seçtiği yer, varsayılan  %USERPROFILE%\Documents\RespectedOS; hiçbir işlemde silinmez.
```

- Program klasörü sabittir; kurucu sormaz. Geliştirme ve test için tek kök seçimi `RESPECTED_APP_DIR` + `RESPECTED_DATA_DIR`.
- Orchestrator'ın `--data-root` bayrağı yalnızca motorun kendi alt süreçleri içindir (her kampanya hattının kendi kökü var);
  yardımda görünmez, kişiler kullanmaz.

## 3. Dosya sahipliği

- **Program dosyalarını kurucu yazar ve siler** (Windows'ta Inno; Linux/macOS'ta `setup.sh` / `setup.command`, ikisi de
  `--uninstall [--purge]` ile kaldırır). Güncelleme = yeni sürümün kurucusunu çalıştırmak.
- **Ürün** kendi veri klasörünü, kasayı ve dış entegrasyonları (AI araçlarının ayar dosyaları, MCP kayıtları, zamanlanmış
  görev, kısayol) yönetir; bunların sahiplik kaydı, işlem günlüğü ve geri alma koruması üründedir. Kurulu program, build'in
  `distribution.json`'ıyla doğrulanır; kurulum kaydı Brain'de `data\install-manifest.json`, Orchestrator'da
  `app\.respected\install.json`.
- Yüklü uygulamalar girdisini yalnızca ürünün kurucusu yazar ve siler.

## 4. Kurucu

Dosya adı `<Ürün>-Windows-Setup.exe`, kullanıcı başına, yönetici izni istemez, varsayılan (açık) Inno görünümü, Türkçe.
Orchestrator kurucusunun ortak bölümü Brain'inkinden üretilir; `conformance/` iki bölümün aynı olduğunu denetler.

| Durum | Sayfalar |
|---|---|
| İlk kurulum | Kurulum yolu (Hub ile / Yalnızca ürün) → ürünün soruları → kur → ürünün `setup` komutu |
| Ürün kurulu | **Onar / güncelle** (dosyalar + `repair`) · **Ayarları değiştir** (`config get` ile dolar, `config set` ile kaydeder) · **Kaldır** |
| Kaldırma | "Ayarlar ve çalışma verileri de silinsin mi?" (varsayılan Hayır); kasa asla |

Brain'in soruları: Kimlik (ad, asistan adı, kısa tanıtım), Not kasası, Bağlantılar. Orchestrator'ın: varsayılan çalışan,
Brain hafızasına bağlanma (okuma / yazma).

| Sessiz anahtar | Anlam |
|---|---|
| `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` | soru sormadan; ürün kuruluysa onar/güncelle |
| `/HUB=1` | Hub'ı indirip kur, ürünü Hub'da aç |
| `/HUBURL=<url>` | Hub kurucusunu buradan indir (test) |
| `/SET=<anahtar>=<değer>` (tekrarlanabilir) | ürün ayarı, `config set` ile aynı anahtarlar |
| `/VAULT=<yol>` | Brain'in not kasası |
| `/PURGE=1` | kaldırırken ayarları ve verileri de sil |

## 5. Komutlar

Ortak komutlar iki üründe aynı adla, aynı bayraklarla, aynı çıktı biçimiyle vardır:

| Komut | Ne yapar |
|---|---|
| `--version` | `respected-<ürün> <sürüm>` |
| `--help`, `<komut> --help` | hiçbir şey kurmaz |
| `setup` | kurucunun yazdığı programı doğrular ve kaydeder, veriyi hazırlar (Brain: `--vault`, `--set k=v`) |
| `repair` | programı doğrular (bozuksa kurucuyu yeniden çalıştırmayı söyler), kaydı ve entegrasyonları yeniler |
| `uninstall [--purge]` | entegrasyonları ve kurulum kaydını kaldırır; `--purge` ayarları ve verileri de siler |
| `config` / `config get <k>` / `config set <k>=<v>...` | ayarlar, RPP `settings.*` ile aynı kod |
| `health` | RPP `health`; sağlıklıysa 0 |
| `rpp` | stdin'den bir RPP isteği, stdout'a bir yanıt |
| `mcp` | AI araçları için MCP sunucusu |

- Çıktı UTF-8 JSON'dur. Hata çıktısı `{"error": {"code", "message", "hint"}}`. Çıkış kodları: `0` başarı, `1` işlem başarısız,
  `2` kullanım ya da geçersiz ayar.
- `update` komutu, gizli takma ad (`--keep-data`, `--purge-data`) ve kendini güncelleme yardımcısı yoktur.
- Ürüne özel komutlar serbesttir. Brain: `vault`, `search`, `compile`, `briefing`, `hook`… Orchestrator: görev ve kampanya
  komutları, `memory connect [--write] | disconnect | status` (Brain hafızasına Hubsız bağlanma: Brain'in `rpp`
  sunucusundan izin alır, kendi ayarına yazar), `integrations [set <istemci>=on|off...]` (kendini AI araçlarına MCP sunucusu
  olarak kaydeder).

## 6. Ayarlar

- Kişinin girdiği her şey ürünün ayarıdır; tek kaynak ürünün şemasıdır (`settings.schema`). `config`, kurucunun sayfaları ve
  `/SET=`, Hub'ın formu aynı şemayı ve aynı doğrulamayı kullanır. Hub kendi etiket ya da yardım metni tutmaz.
- Şema alanı: `key`, `type` (`string|integer|boolean|enum`), `label` ve `help` (Türkçe), `default`, `secret`, gerekirse
  `enum` / `min` / `max` / `max_length` / `hidden`.
- Brain: `user_name`, `user_bio`, `assistant_name`, `summary_provider`, `provider_fallback`, `capture_mode`, `briefing_time`,
  `mcp_write`, `archive_transcripts`, `transcript_retention_days`, `integrations.global|clients|mcp|mcp_clients|schedule|shortcut`.
  Adlar, bağlantılar ya da sabah özeti saati değişince ürün AI araçlarındaki kendi kayıtlarını aynı işlemde günceller.
- Orchestrator: `default_worker`, `default_worker_profile`, `default_reviewer_profile`, `default_timeout_seconds`, rol alanları,
  gizli hafıza alanları (`memory connect` yazar).

## 7. Protokol (RPP 1)

- Tek sürüm `"1"`. Başka sürümle gelen istek `UNSUPPORTED_VERSION`.
- İstek `{"rpp", "op", "payload", "operation_id"}`; yanıt `{"rpp", "ok", "operation_id", "result", "error"}`; hata
  `{"code", "message", "hint"}`.
- Her ürün: `manifest`, `health`, `settings.schema|validate|apply|readback`. `manifest` sonucu: `product_id`, `product_version`,
  `rpp`, `capabilities` (ürünün sunduğu işlem adları, sıralı), `installed`, `install_state` (`absent|installed|repair-needed`),
  `roots` (`app`, `data`, `vault`).
- Ürüne özel işlemler ad alanıyla: Brain `integrations.plan`, `memory.*`; Orchestrator `integrations.plan|apply|rollback`,
  `memory.connect|disconnect|status`.
- Kurma, onarma, kaldırma protokol işlemi değildir (`lifecycle.*`, `operation.receipt` yoktur).

## 8. Hub

- Katalogda yalnızca kurucu paketi vardır (`kind: installer`: imzalı `bundle.json` + `payload/<Ürün>-Windows-Setup.exe`).
- Kurulu olanı ürünlerden okur (`app\distribution.json` sürümü + ürünün kurulum kaydı). Kur/güncelle/onar: kurucuyu indir,
  imzayı doğrula, sessiz çalıştır (`/VAULT=`, `/SET=`), ardından ürünün `manifest`'iyle doğrula. Kaldır: ürünün kaldırıcısı
  (`/PURGE=1` seçilirse).
- Ayarlar: ürünün şeması ve `settings.apply`. Brain bağlantıları: `integrations.plan` önizlemesi + `settings.apply`.
  Orchestrator–Brain bağlantısı: Orchestrator'ın `memory.connect`'i. Orchestrator'ın AI araçlarına MCP kaydı kurulu
  programı gösterir (`...\RespectedOrchestrator\app\respected-orchestrator.exe mcp`).
- Hub'ın sakladığı: pencere verisi, indirme önbelleği ve kendi işlem günlüğü (`managed\`). Ürünlere klasör geçirmez, Yüklü
  uygulamalar girdisi yazmaz, yönetilen kopya tutmaz. Hub kaldırılınca ürünler olduğu gibi kalır.

## 9. Repo düzeni

Üç repoda aynı adlar: `src/`, `packaging/windows/<ürün>_setup.iss`, `packaging/build_installer.py`, `tests/`, `docs/`,
`AGENTS.md`. Hub'da `packaging/build_installer.py` yoktur; kurucusunu `release/tools/build/build_hub_installer.py` üretir.
Yayın: `respected-hub/release/tools/build/publish_release.py` her ürünün kendi kurucusunu kendi reposunun
sürümüne, kurucu paketini kataloğa koyar; Hub sürümünde yalnızca `RespectedHub-Windows-Setup.exe` vardır.

## 10. Doğrulama (2026-10-22)

- Hub deposundaki `conformance/`: 8/8, ürün kaynaklarında ve derlenmiş programlarda.
- Hub'ın gerçek kurucularla uçtan uca testi (`installer_e2e`, elle): iki ürün de Hub'dan kuruldu (kasa ve ayarlar kurucuya
  `/VAULT=`/`/SET=` ile gitti, ürün geri okudu), sonra `/PURGE=1` ile kaldırıldı; kasa kaldı, Yüklü uygulamalar girdisi kalmadı.
- Hub'ın arayüz sürücüsü (`respected-hub/tests/native/hub_native_e2e.mjs`, derlenmiş Hub, Python PATH'te yok): kart ve
  sihirbazdan iki ürünün gerçek kurucuyla kurulması, ayar değiştirme (ürün CLI'siyle geri okundu), MCP ve hafıza bağlantısı
  aç/kapat, not yakala/ara/oku, değiştirilmiş program dosyası → "Onarım gerekli" → Onar, veriyi tutarak ve silerek kaldırma:
  29 kontrolün ve tüm arayüz adımlarının hepsi geçti. Test ev klasörü verildiğinde Windows kullanıcı klasörlerini ondan
  türettiği için ürünler de o klasöre kurulur; gerçek makinede yalnız Yüklü uygulamalar girdisi oluşur ve test sonunda
  kaldırılır.
- Ürün ve Hub test takımları: sayılar teslim notunda.
