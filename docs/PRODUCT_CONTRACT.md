# Respected Orchestrator ürün sözleşmesi

Durum: **uygulandı**. Bu belge yalnız Orchestrator'ı bağlar; başka bir depoyla ortak kopya ya da ortak uyum testi yoktur. Uyum bu
depodaki `tests/interfaces/test_product_contract.py` ile ölçülür (kaynakta ya da `RESPECTED_CONFORMANCE_ORCHESTRATOR_EXE` ile
derlenmiş programda). Geçiş dönemi, eski sürüm desteği ya da uyumluluk katmanı yoktur: bir şey değiştiğinde her yerde değişir,
eski yolu silinir.
**Tek istisna kişinin verisidir** (ilk yayından, 0.1.0-beta.1'den beri): ayar, kurulum kaydı ve çalışma verisinin biçimi
(`schema_version`) değişirse yeni sürümün `repair`'i eski biçimi yerinde taşır; güncelleme kişiden hiçbir şey istemez.

## 1. İlke

- **Orchestrator tek başına bir üründür.** Kurma, onarma, güncelleme, kaldırma ve ayar değiştirme kurucuyu çalıştırarak ya da
  ürünün kendi komutlarıyla yapılır; başka bir programa ihtiyaç yoktur.
- **Brain yalnız isteğe bağlı bir bağlantıdır.** Kişi isterse Orchestrator Brain hafızasını okur ya da gelen kutusuna not yazar
  (`memory connect`). Bağlantı Brain'in kendi `rpp` komutuyla yapılır; Brain'in kodu içe aktarılmaz, Brain kurulu değilse
  Orchestrator eksiksiz çalışır.
- Ortak kod ya da başka bir ürünle ortak belge çalışma zamanı bağımlılığı değildir.

## 2. Klasörler

```
%LOCALAPPDATA%\Respected\RespectedOrchestrator\
  app\   (program, distribution.json, unins000.exe)
  data\  (ayarlar, görev çalışmaları)
```

- Program klasörü sabittir; kurucu sormaz. Geliştirme ve test için tek kök seçimi `RESPECTED_APP_DIR` + `RESPECTED_DATA_DIR`.
- `--data-root` bayrağı yalnızca motorun kendi alt süreçleri içindir (her kampanya hattının kendi kökü var); yardımda görünmez,
  kişiler kullanmaz.

## 3. Dosya sahipliği

- **Program dosyalarını kurucu yazar ve siler** (Windows'ta Inno). Güncelleme = yeni sürümün kurucusunu çalıştırmak.
- **Ürün** kendi veri klasörünü ve dış entegrasyonları (AI araçlarının ayar dosyaları, MCP kayıtları) yönetir; bunların sahiplik
  kaydı, işlem günlüğü ve geri alma koruması üründedir. Kurulu program, build'in `distribution.json`'ıyla doğrulanır; kurulum
  kaydı `app\.respected\install.json`'dır.
- Yüklü uygulamalar girdisini yalnızca ürünün kurucusu yazar ve siler.

## 4. Kurucu

Derleme çıktısı `RespectedOrchestrator-Windows-Setup.exe`; yayında dosya adı `Respected-Orchestrator-<sürüm>-Windows-x64-Setup.exe`.
Kullanıcı başına, yönetici izni istemez, varsayılan (açık) Inno görünümü, Türkçe.

| Durum | Sayfalar |
|---|---|
| İlk kurulum | Varsayılan çalışan → Brain hafızası → kur → ürünün `setup` komutu |
| Ürün kurulu | **Onar / Güncelle** (dosyalar + `repair`) · **Ayarları değiştir** (`config get` ile dolar, `config set` ile kaydeder) · **Kaldır** |
| Kaldırma | "Ayarlar ve çalışma verileri de silinsin mi?" (varsayılan Hayır) |

| Sessiz anahtar | Anlam |
|---|---|
| `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` | soru sormadan; ürün kuruluysa onar/güncelle |
| `/SET=<anahtar>=<değer>` (tekrarlanabilir) | ürün ayarı, `config set` ile aynı anahtarlar |
| `/PURGE=1` | kaldırırken ayarları ve verileri de sil |

**Güncelleme güvenlidir ve her sürümden en yeniye doğrudandır.** Kurucu güncellemeden önce önceki program klasörünü ve
veri kökündeki `*.json` dosyalarını `update-backup\` altına yedekler; yedek alınamazsa güncelleme başlamaz. `repair`
başarısız olursa ya da ürün güncellemeden önce sağlıklıyken sonra sağlıklı değilse yedek geri yüklenir, güncelleme
başarısız sayılır ve kurulu sürüm değişmez; başarılıysa yedek silinir. Kurucu bu durumda ve ürünün `setup` komutu
başarısız olduğunda sıfırdan farklı bir çıkış koduyla (8) biter. Veri biçimi değişirse her eski biçim için `STEPS` tablosuna bir
adım eklenir ve **adımlar hiç silinmez**; tablo yalnızca `SHIPPED` ile `CURRENT` arasındaki gerçek boşlukları içerir, ileriye
dönük spekülatif adım taşımaz. Her yayında o sürümün gerçek veri dosyaları `tests/fixtures/releases/<sürüm>/` altına kopyalanır,
CI hepsini en yeniye taşıyıp ikinci çalıştırmanın hiçbir şeyi değiştirmediğini ve yayın klasöründe tanınmayan veri dosyası
olmadığını doğrular.

Kendiliğinden güncelleme yoktur: yeni sürüm GitHub sürüm sayfasından indirilen kurucuyla gelir (bölüm 8).

## 5. Komutlar

| Komut | Ne yapar |
|---|---|
| `--version` | `respected-orchestrator <sürüm>` |
| `--help`, `<komut> --help` | hiçbir şey kurmaz |
| `setup` | kurucunun yazdığı programı doğrular ve kaydeder, veriyi hazırlar |
| `repair` | programı doğrular (bozuksa kurucuyu yeniden çalıştırmayı söyler), kaydı ve entegrasyonları yeniler |
| `uninstall [--purge]` | entegrasyonları ve kurulum kaydını kaldırır; `--purge` ayarları ve verileri de siler |
| `config` / `config get <k>` / `config set <k>=<v>...` | ayarlar, RPP `settings.*` ile aynı kod |
| `health` | RPP `health`; sağlıklıysa 0 |
| `rpp` | stdin'den bir RPP isteği, stdout'a bir yanıt |
| `mcp` | AI araçları için MCP sunucusu |

- Çıktı UTF-8 JSON'dur. Hata çıktısı `{"error": {"code", "message", "hint"}}`. Çıkış kodları: `0` başarı, `1` işlem başarısız,
  `2` kullanım ya da geçersiz ayar.
- `update` komutu, gizli takma ad (`--keep-data`, `--purge-data`) ve kendini güncelleme yardımcısı yoktur.
- Ürüne özel komutlar serbesttir: görev ve kampanya komutları, `memory connect [--write] | disconnect | status` (Brain
  hafızasına bağlanma: Brain'in `rpp` sunucusundan izin alır, kendi ayarına yazar), `integrations [set <istemci>=on|off...]`
  (kendini AI araçlarına MCP sunucusu olarak kaydeder).

## 6. Ayarlar

- Kişinin girdiği her şey ürünün ayarıdır; tek kaynak ürünün şemasıdır (`settings.schema`). `config`, kurucunun sayfaları,
  `/SET=` ve masaüstü uygulaması aynı şemayı ve aynı doğrulamayı kullanır.
- Şema alanı: `key`, `type` (`string|integer|boolean|enum`), `label` ve `help` (Türkçe), `default`, `secret`, gerekirse
  `enum` / `min` / `max` / `max_length` / `hidden`.
- Alanlar: `default_worker`, `default_worker_profile`, `default_reviewer_tool`, `default_reviewer_profile`,
  `default_timeout_seconds`, rol alanları, gizli hafıza alanları (`memory connect` yazar).

## 7. Protokol (RPP 1)

- Tek sürüm `"1"`. Başka sürümle gelen istek `UNSUPPORTED_VERSION`.
- İstek `{"rpp", "op", "payload", "operation_id"}`; yanıt `{"rpp", "ok", "operation_id", "result", "error"}`; hata
  `{"code", "message", "hint"}`.
- `manifest`, `health`, `settings.schema|validate|apply|readback` her zaman vardır. `manifest` sonucu: `product_id`,
  `product_version`, `rpp`, `capabilities` (sunulan işlem adları, sıralı), `installed`, `install_state`
  (`absent|installed|repair-needed`), `roots` (`app`, `data`, `vault`).
- Ürüne özel işlemler ad alanıyla: `integrations.plan|apply|rollback`, `memory.connect|disconnect|status`.
- Aynı zarf Brain ile konuşmak için de kullanılır (Orchestrator istemcidir: `memory.recall`, `memory.write`).
- Kurma, onarma, kaldırma protokol işlemi değildir (`lifecycle.*`, `operation.receipt` yoktur).

## 8. Yayın ve güncelleme

- Yayın `packaging/release.py` ile hazırlanır: kurucu derlenir, `SHA256SUMS.txt` yazılır ve GitHub'a yükleyecek `gh` komutları
  yazdırılır; yüklemek için `--yes` gerekir. Katalog, yayın anahtarı ya da kasa yoktur.
- Yayın dosyaları `respected0/respected-orchestrator` deposunun `v<sürüm>` etiketindedir: kurucu ve `SHA256SUMS.txt`.
- Yayınlanmış bir sürüm numarası bir daha kullanılmaz; düzeltme yeni numara ister.
- Kurucunun Authenticode imzası ilk kararlı sürüme bırakılmıştır (`docs/evidence/KANIT_LOG.md`, `SIGNING-01`).

## 9. Repo düzeni

`src/`, `packaging/windows/orchestrator_setup.iss`, `packaging/build_installer.py`, `packaging/release.py`, `tests/`, `docs/`,
`desktop/` (masaüstü uygulaması), `AGENTS.md`.
