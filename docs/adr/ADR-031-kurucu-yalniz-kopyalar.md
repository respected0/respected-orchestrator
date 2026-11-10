# ADR-031 — Kurucu yalnızca dosya kopyalar; kurulum ve ayar ürünün işidir

## Durum

Kabul edildi (9 Kasım 2026, kullanıcı kararı). ADR-026'nın (güncelleme penceresi, yedek ve geri alma) kurucu tarafını geçersiz kılar. Kalıcı motor (ADR-030) dilim 5'in yerine geçer.

## Bağlam

Kurucu betiği (`orchestrator_setup.iss`) 500 satırı aşıyordu ve ürünün işlerini yapıyordu: kurulu ürün için bakım sayfası (onar/güncelle, ayarları değiştir, kaldır), varsayılan çalışan ve Brain hafızası sayfaları, `/SET=` ve `/PURGE=` anahtarları, güncellemeden önce çalışan işlerin bitmesini bekleme (`maintenance drain`), program ve veri dosyalarını yedekleme, sağlıksızsa geri yükleme, çalışan süreçleri PowerShell ile öldürme, kurulumdan sonra `setup` ve `config set` çağırma, kaldırırken `uninstall` çağırma. Ürün kuralları ikinci bir yerde (Pascal) yaşıyor, komutlarla aynı işi yapıyor ve motor-sahibi-her-şeyi ilkesine (RAKIP_ESKIKLERI §6) ters düşüyordu. Kalıcı motor da kurucudan ayrı bir "motoru durdur" adımı isterdi.

## Karar

1. **Kurucu yalnızca program dosyalarını yazar ve siler.** `[Setup]`, `[Files]`, `[Icons]`, `[InstallDelete]` (eski sürümden kalan `app\` silinir), `[UninstallDelete]`. `[Code]`, `[Run]`, `[UninstallRun]`, `[Registry]`, özel sayfa, yedek, geri alma yoktur.
2. **Açık süreçleri Windows kapatır:** `CloseApplications=force`. Kurucu, değiştireceği dosyaları kullanan masaüstü uygulamasını, motoru ve AI aracının MCP sunucusunu kendisi kapattırır (gerçek kurucuyla çalışan motor ve uygulamanın üstüne güncelleme denendi).
3. **Kurulumu motor tamamlar:** kalıcı motor her açılışta (yalnız paketli sürümde) kurulum kaydını denetler; "yok" ya da "onarım gerekli" ise `distribution.json` ile doğrulayıp `setup` işini yapar ve eski biçimli veriyi taşır. `distribution.json` ile uyuşmayan klasörü kaydetmez, yalnız bildirir. `rorch setup` ve `rorch repair` aynı işi elle yapar.
4. **Ayarlar ve bağlantılar** `rorch config`, `rorch integrations`, `rorch memory connect` ile yapılır; kurucu sormaz. **Masaüstünde ayar ve bağlantı ekranı henüz yoktur** (RAKIP_ESKIKLERI E1); o gelene kadar bu komutlar tek yoldur.
5. **Kaldırmadan önce `rorch uninstall [--purge]`:** kaldırıcı yalnızca program dosyalarını siler; AI araçlarındaki MCP girdilerini geri alan komut kaldırıcıdan çağrılmaz.
6. **Güncellemede koruma yoktur:** çalışan görevleri beklemek, yedek almak ve geri yüklemek kalktı. Çalışan görevler yarıda kalır ve "yarıda kaldı" olarak işaretlenir (otomatik uygulanmaz).
7. **Ortak ürün sözleşmesi:** sessiz kurulum anahtarları `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART` kalır; `/SET=` ve `/PURGE=` kalktı. Sözleşme metni bu depodaki kopyada güncellendi, diğer depolarınki güncellenmedi.

## Sonuçlar ve sınırlar

- Kurucu 520 satırdan 80 satıra indi; ürün kuralının tek yeri ürünün kendisidir.
- **Kaybedilen güvenlik ağı:** başarısız bir güncellemeden otomatik dönüş yok. Veri taşıma eski dosyayı yerinde `.bak` olarak saklar, ama program dosyaları için yedek yoktur.
- **Kaldırmadan önce `uninstall` çalıştırılmazsa** AI araçlarındaki MCP girdileri artık olmayan programı gösterir (kaldırıcı bunu yapmaz).
- `maintenance begin|drain|end|status` komutu, modülü, testi ve ADR-026 silindi (10 Kasım 2026); güncelleme penceresi yoktur. Çalışan koşuları bulan `run_pids` `engine/supervisor.py`'ye taşındı.
- Gerçek kurucuyla denendi: temiz kurulum, çalışan motor ve uygulamanın üstüne güncelleme (ikisi kapatıldı, çıkış kodu 0), kaldırma (program silindi, veri kaldı). İmzalama (Authenticode), Hub'ın kurucuyu başlatış biçimi ve Windows Defender/SmartScreen davranışı denenmedi.

## Kaynaklar

- `packaging/windows/orchestrator_setup.iss`, `engine/daemon.py` (`_complete_install`), `interfaces/installation.py` (erişim: 2026-11-09).
- Kanıt: `tests/engine/test_daemon.py`, `tests/interfaces/test_product_contract.py` (kurucu yalnız kopyalar), elle çalıştırılan gerçek kurucu denemesi (erişim: 2026-11-09).
