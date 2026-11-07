# ADR-029 — Uzaktan salt-okunur gözlemci: tehdit modeli, prototip ve genişleme kapısı

## Durum

Kabul edildi (8 Kasım 2026). Görevler: B4-09.01, B4-09.02, B4-09.03. Beta.4'ü bloke etmez. **Uzak erişim varsayılan kapalıdır ve hiçbir uzak dinleyici yoktur.**

## Bağlam

Beta.4 yerel ürünü doğrular; uzak/mobil erişim ayrı bir güvenlik projesidir ve yalnızca yerel güvenlik kanıtları sağlamlaşınca değerlendirilir. Bu ADR üç karta (B4-09.01…03) tek karar kaydıdır.

## Karar

### B4-09.01 — Tehdit modeli, maliyet/yarar, karar

Kullanım senaryosu (tek): kişi evde değilken çalışan işlerin **durumunu okumak**. Eylem (başlatma, onay, uygulama, iptal, ayar) kapsam dışıdır.

| Saldırı | Etki | Prototipteki karşılık |
|---|---|---|
| Ağ sahteciliği / araya girme (LAN/WAN) | belirteç ve veri okunur | **Uzak dinleyici yok**: `serve` yalnız döngü adresine bağlanır, aksi `NO_REMOTE_LISTENER`. Taşıma şifresi (TLS) ve doğrulanmış kimlik olmadan uzak dinleyici yazılmaz. |
| Çalınan telefon | kalıcı erişim | Cihaz sırrı yalnız özet olarak saklanır; `revoke` cihazı ve canlı belirteçlerini anında öldürür (İNSAN gerekir). En çok 5 cihaz. |
| Yeniden oynatma (replay) | eski eşleştirme/belirteç | Eşleştirme kodu tek kullanımlık, 2 dk, bir yanlış denemede yanar; belirteç 10 dk ve yalnız bellekte (yeniden başlatma hepsini düşürür). |
| Kod tahmini | eşleşme | 8 karakter (~40 bit), 5 hatada 5 dk kilit. |
| Çevrimdışı ana makine | veri yok | Hiçbir şey kuyruğa alınmaz; istek reddedilir. |
| Yetki yükseltme | değişiklik | Yalnız `GET /status|/runs|/events`; başka yöntem 405, başka yol 404; modül yazan/başlatan hiçbir şeyi içe aktarmaz (testle korunur). Olay gövdeleri günlük maskesiyle maskelenir. |

**Maliyet/yarar:** Yarar, uzaktan durum görmek (rahatlık). Maliyet: yeni kimlik/cihaz/taşıma yüzeyi, sertifika yönetimi, kalıcı saldırı yüzeyi ve her platformda test. Yerel
ürünün temel değeri (güvenli yerel çalıştırma) bundan bağımsızdır. **Karar:** uzak dinleyici **NO-GO** (bu sürüm ve TLS kanıtı gelene kadar); yalnızca döngü adresi prototipi tutulur.
Alternatif (SSH ile salt-okunur geçit) daha ucuz ve kişinin zaten güvendiği bir kanaldır; ayrıca değerlendirilmelidir.

**Kullanıcı araştırması:** yapılmadı. Bu karar kullanıcı verisine değil tehdit analizine dayanır; talep kanıtı yoktur (açık kalan madde).

### B4-09.02 — Prototip

`interfaces/observer.py`: eşleştirme, kısa ömürlü belirteç, iptal, salt-okunur işleyici (`Observer.handle`), isteğe bağlı döngü adresi sunucusu (`serve`). **Hiçbir yer onu başlatmaz**, CLI
komutu yoktur. 14 test (çoğu saldırı: yetkisiz değişiklik, yeniden oynatma, kaba kuvvet, iptal edilmiş cihaz, bozuk belirteç, uzak adrese bağlanma, gerçek HTTP ile döngü adresi). Bu
**iç saldırı testidir, bağımsız bir sızma testi değildir**; TLS yoktur ve LAN/WAN testi yapılmamıştır (dinleyici yoktur).

### B4-09.03 — Genişleme kapısı: kontrol ve mobil

**NO-GO.** Uzaktan başlatma/onay/uygulama, ayrı bir yetki ve rıza modeli (mobil kimlik, cihaz bağlama, kaynak sapması denetimi, çalınmış/yeniden oynatılmış onay, eski cihaz, WAN
kesintisi) ve bağımsız sızma testi gerektirir. Bunlar yok. Beta.4'te hiçbir uzaktan eylem yoktur; en erken ayrı bir sürüm önerisiyle (Beta.6 `B6-02`) ele alınır.

Backlog: (1) SSH üzerinden salt-okunur geçit değerlendirmesi, (2) TLS + cihaz sertifikası tasarımı, (3) bağımsız sızma testi, (4) gerçek talep araştırması, (5) uzaktan onay için yeni `authority` kaynağı.

## Sonuçlar ve sınırlar

- Beta.4'te uzaktan hiçbir eylem yoktur; uzak dinleyici hiçbir yerden başlatılmaz ve yalnız döngü adresine bağlanabilir.
- Prototip iç saldırı testidir; bağımsız sızma testi, TLS, LAN/WAN testi ve gerçek kullanıcı araştırması yapılmadı.
- Genişleme (uzaktan başlatma/onay/uygulama) ayrı bir sürüm önerisi, yeni yetki/rıza modeli ve bağımsız sızma testi olmadan ele alınmaz.

## Kaynaklar

- `src/respected_orchestrator/interfaces/observer.py`, `engine/authority.py`, `engine/read_model.py`, `engine/journal.py` (erişim: 2026-11-08).
- Kanıt: `tests/interfaces/test_observer.py` (14), `docs/evidence/KANIT_LOG.md` B4-09 (erişim: 2026-11-08).
