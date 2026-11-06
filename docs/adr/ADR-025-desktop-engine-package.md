# ADR-025 — Masaüstü kabuğu ve motorun tek paketi

## Durum

Kabul edildi (7 Kasım 2026). Görev: B3-09.01. `docs/PRODUCT_CONTRACT.md` metni **değiştirilmedi**: `distribution.json` `schema_version: 1` kalır, yalnızca `files` listesi bir dosya ve isteğe bağlı bir üst düzey anahtar (`desktop`) kazanır.

## Bağlam

Beta.2'ye kadar Orchestrator tek PyInstaller klasörüydü (`respected-orchestrator.exe` + `app\` çalışma zamanı + `distribution.json`). Beta.3 ile
Tauri masaüstü kabuğu (`respected-orchestrator-desktop.exe`) eklenir. Kabuk motoru kendi çocuk süreci olarak başlatır (`_ipc`); ikisi iki ayrı uygulama gibi
kurulmamalı, iki ayrı güncellenmemeli, iki ayrı kayıt tutmamalı.

## Karar

1. **Tek kurucu, tek klasör, tek kurulum kaydı.** Masaüstü exe'si motor başlatıcısının **yanına**, kurulum klasörünün köküne konur:
   `…\RespectedOrchestrator\app\respected-orchestrator.exe` (motor) ve `…\app\respected-orchestrator-desktop.exe` (kabuk). Çalışma zamanı `app\app\` içindeki
   `--contents-directory app` klasöründe kalır; kabuk oraya girmez (güncellemede `{app}\app` bütünüyle silinip yeniden yazıldığı için kabuğun kökte durması
   kilitli dosya yarışını `B3-09.03`'te tek noktaya indirir).
2. **Tek karma zinciri.** `build_dist.py --desktop <exe>` kabuğu hesaba katarak `distribution.json` üretir: kabuk `files` içinde (sha256) yer alır ve üst düzey
   `"desktop": "respected-orchestrator-desktop.exe"` anahtarı onu adlandırır. Kurucu, Hub ve ürünün kendi `_distribution` doğrulaması bu dosyaları zaten
   `files` üzerinden kanıtlar; Hub'ın şeması değişmez.
3. **Kabuk motoru önce kendi yanında arar.** Sıra: `RESPECTED_APP_DIR` (sözleşmenin test/geliştirme yolu) → kabuğun kendi klasörü → `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app`.
   Başka klasördeki bir motoru "kuruluymuş" gibi kullanmaz.
4. **Başlatmadan önce başlatıcı karması.** Kabuk, motoru çalıştırmadan önce `distribution.json`'daki `respected-orchestrator.exe` karmasını diskteki dosyayla karşılaştırır.
   Kurulu yollarda (kabuğun klasörü, `%LOCALAPPDATA%`) `distribution.json` zorunludur; yalnızca `RESPECTED_APP_DIR` geliştirme yolunda dosya yoksa atlanır, **varsa** yine eşleşmelidir.
   Uyuşmazlık `BrokenInstall` olarak "Kurucuyu yeniden çalıştırın (Onar)" ipucuyla gösterilir; motor başlatılmaz. Tüm ağacın doğrulaması motorun `setup`/`repair` komutlarında ve `manifest`in `install_state` değerindedir (karma listesini zaten kanıtlar).
5. **Onarım = kurucuyu yeniden çalıştırmak** (sözleşmedeki mevcut yol). Kabuk dosya yazmaz, kendini güncellemez, hizmet (servis) ya da otomatik başlangıç kaydı oluşturmaz.
6. **Başlangıç menüsü:** kurucu, kabuk paketteyse kabuk için bir kısayol ekler; motor başlatıcısı için kısayol yoktur (komut satırı/MCP içindir).

## Reddedilen seçenekler

- **İki ayrı kurucu / iki kurulum klasörü:** iki sürüm uyumsuzluğu ve iki kayıt demek; Hub'ın "ürün başına bir kurulum" modeline aykırı.
- **Kabuğu `app\app\` içine gömmek:** çalışma zamanı klasörüyle aynı yaşam döngüsüne bağlar, kökteki karma görünümünü bozar.
- **Windows hizmeti ya da otomatik başlangıç:** sözleşmede böyle bir kayıt tanımlı değil ve yönetici izni gerektirir (kurucu `PrivilegesRequired=lowest` ile kullanıcı düzeyinde çalışır); çalışan görevler zaten ayrık süpervizör süreçleridir.
- **Kabukta tam ağaç karması:** her açılışta yüzlerce dosya okumak; motor aynı kanıtı `repair` ve `install_state` ile zaten verir.

## Sonuçlar

- Kabuk ve motor aynı sürümde dağıtılır; sürüm uyuşmazlığı el sıkışmada (`product_version`) ve karma zincirinde görünür (tam sürüm el sıkışması `B3-09.03`).
- Karma zinciri yalnızca "dosya kurulduğu gibi" kanıtlar; imza (Authenticode) ayrı bir koşuldur ve sertifika yoksa "imzalı sürüm" iddiası yapılmaz (`B3-09.04`).
- Kanıtlanmayan: gerçek kurucuyla temiz kullanıcı kurulumu bu makinede çalıştırılmadı (gerçek kurulumun kaydını ve Hub kurulum adımını etkilememek için); kurucunun kopyaladığı kare klasör (`StageDir` → `{app}`) birebir simüle edildi ve kurucu yalnızca derlendi. 

## Kaynaklar

- `packaging/build_dist.py`, `packaging/windows/orchestrator_setup.iss`, `docs/PRODUCT_CONTRACT.md` §2 ve §8, `desktop/src-tauri/src/engine_connector.rs`.
