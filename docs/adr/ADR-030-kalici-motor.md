# ADR-030 — Kalıcı motor: tek arka plan süreci, CLI, MCP ve masaüstü aynı canlı oturumları görür

## Durum

**Kabul edildi (9 Kasım 2026): D1–D4 önerildiği gibi onaylandı. 1. dilim uygulandı** (daemon iskeleti: kilit, boru, köken çözümü, `rorch daemon`); 2–6. dilimler bekliyor. Kaynak karar: `RAKIP_ESKIKLERI.md` §6 madde 2 (motor tek, kalıcı bir arka plan süreci olur) ve madde 3 (tek işlem kataloğu). Bu belge yalnız madde 2'yi ve onun güvenlik sonuçlarını ele alır; katalog birleştirmesi ayrı dilimdir (§9).

## Bağlam: bugün nasıl çalışıyor (koddan doğrulandı)

| Ön yüz | Motorla nasıl konuşur | Canlı oturumlar nerede |
|---|---|---|
| Masaüstü | Kabuk motoru **kendi çocuğu** olarak başlatır: `rorch _ipc` (görsel) ve ikinci bir `rorch _ipc --human` (yerli onay). Konuşma, çocuğun kendi stdin/stdout borusudur; belirteç ortam değişkeniyle gelir (`local_api.serve`, `engine_connector.rs`). | Çocuk motorun belleğinde (`SessionController`). Masaüstü kapanınca çocuk ölür, **canlı oturum da ölür**; yalnız konuşma kaydı (`session_store`) diskte kalır. |
| CLI | Her komut tek seferlik süreçtir. | Yok. |
| MCP | İstemci başına ayrı `rorch mcp` süreci (stdio). | Yok; oturum başlatamaz, görev/kampanya başlatır. |
| Görev, proje, kampanya | Motor kendini `context.engine_command` ile **ayrık süreç** olarak başlatır (`lanes._spawn_detached`). Tek sahip `supervisor.lock` dosya kilidi, çalışan işler `supervisor-claims.json` kayıtları. | Ayrık süreçler; pencere kapanınca devam ederler (mevcut sözleşme). |

Sonuç: üç ön yüz aynı **kalıcı veriyi** (dosya) görür ama aynı **canlı oturumu** görmez. Masaüstünde açık bir sohbeti CLI'dan sürdüremezsin; masaüstünü kapatmak sohbeti öldürür. Bu, RAKIP_ESKIKLERI'ndeki çekirdek vaadin ("birden çok ajanı çalıştıran") önünde engeldir.

## Karar önerisi

### 1. Tek süreç, tek sahip

`rorch daemon` adlı kalıcı bir süreç, veri kökü başına **tek örnek** olarak çalışır. Tekilliği zaten kanıtlanmış mekanizma sağlar: işletim sistemi dosya kilidi (`Supervisor` ile aynı desen; çökme kilidi bırakır, bayat PID tahmini yok). Kilidi alamayan ikinci süreç "meşgul" der ve çıkar.

Süreç şunların **tek sahibidir**: canlı sohbet oturumları (`SessionController`), kayıtlı oturum deposu, dinleme ucu. Görev/proje/kampanya hatları bugünkü gibi ayrık süreç olarak kalır (pencere kapanınca da devam sözleşmesi bozulmaz); daemon onların kaydını okur ve yönetir.

### 2. Taşıma: kullanıcıya özel yerel uç, port yok

- **Windows:** adlandırılmış boru `\\.\pipe\rorch-<kullanıcı>-<veri kökü özeti>`, erişim listesi (DACL) yalnız mevcut kullanıcı SID'sine verilir (`pywin32` zaten bağımlılık).
- **macOS/Linux (sonra):** kullanıcıya özel (0700) klasörde Unix soketi.
- **TCP yok, port yok.** `test_no_telemetry` "yalnız sağlayıcı istemcisi ağa açılabilir" kuralı korunur; Unix soketi için o testin izin listesine tek satır eklenir ve gerekçe yazılır.
- Protokol **yeni değil:** bugünkü `local_api` satır-satır JSON (`hello`, komutlar, ilişki kimliği). Yeni olan yalnız taşıma. Böylece mevcut yetki matrisi ve testler olduğu gibi işler.

### 3. Kimlik ve yetki (asıl risk)

Bugün "kim konuşuyor" sorusunun cevabı sürecin nasıl başlatıldığıdır: çocuk süreç, babasının borusundan başka kimseyle konuşamaz. Ortak bir uçta **aynı kullanıcının her süreci bağlanabilir**, yani sandbox kalktığı için bir ajan işçisi de. Bu yüzden kurallar:

1. **Köken istemciden alınmaz.** Daemon, bağlantı kuran sürecin kimliğini kendisi çözer (Windows'ta `GetNamedPipeClientProcessId`); istemcinin "ben insanım" beyanı bir şey ifade etmez.
2. **İşçi soyundan gelen süreç hiçbir hak almaz.** Daemon kendi başlattığı işçilerin süreç ağacını bilir; bağlanan süreç bunlardan birinin soyundansa bağlantı `CHILD` olarak sınıflanır (`authority.py`: hiçbir eylem yok). Mevcut `RESPECTED_ORCH_CHILD` işareti ikinci kemer olarak kalır.
3. **Ortak uçta `PRIVILEGED` (onayla, uygula, ayrıcalıklı MCP anahtarı) hiç sunulmaz.** Daemon'daki `LocalApi`, yetkili komutları kataloğundan çıkarılmış olarak kurulur (`only=` izin listesi, bugün `--human` bağlantısında kullanılan aynı mekanizma). Onay ve uygulama bugünkü yoldan gider: masaüstünde kabuğun özel `_ipc --human` çocuğu (kimseye açık olmayan stdio), CLI'da TTY kontrollü süreç içi çalışma. Daemon **izin kipini de yükseltemez**; kip seçimi yerli pencereden gelir (karar 4).
4. **Ayrı belirteç yok:** işçi aynı kullanıcı olduğu için belirteç dosyasını da okuyabilir; belirteç yalan bir güvenlik verir. Güvence erişim listesi + sunucu tarafı köken çözümü + yetkili komutların hiç sunulmamasıdır.
5. **Dürüst sınır (karar 5'in devamı):** aynı kullanıcı olarak çalışan bir işçi veri kökünü ve kullanıcı dosyalarını zaten okuyup yazabilir. Daemon bunu kapatmaz ve kapattığını iddia etmez; kapattığı şey, işçinin insan onayı olmadan **onay/uygulama komutunu** tetikleyememesidir. Kanıt ve onay bütünlüğü imza ve motor doğrulamasıyla sağlanmaya devam eder.

Bu madde §6'daki açık sorunun cevabına bağlıdır: onay durumu iki süreç arasında gerçekten dosya tabanlı mı (`approval.py` bellekte `used_nonces` gibi şeyler tutuyor mu)? İlk dilim bunu **doğrulamadan başlamaz**.

### 4. Yaşam döngüsü

- **İstek üzerine başlar.** İlk istemci (CLI, MCP, masaüstü) daemon'u bulamazsa `rorch _daemon`'u gizli konsolla ayrık başlatır (`_spawn_detached` ile aynı seçenekler) ve hazır olmasını bekler (üst sınır birkaç saniye). Windows servisi yok, açılışta otomatik başlama yok, zamanlanmış görev yok.
- **Durur:** `rorch daemon stop`, ya da (öneri) canlı oturum, canlı çalışma ve bağlantı olmadan sabit bir boşta süresi sonunda kendiliğinden çıkar (bkz. karar D2).
- **Komutlar:** `rorch daemon start|stop|restart|status`. Çıktı JSON, hata `{"error":{code,message,hint}}`, çıkış kodu 0/1/2 (depo kuralı).
- **Çökme:** ayrık hatlar etkilenmez. Sohbet oturumlarının ajan çocukları Windows'ta "kapanınca öldür" iş nesnesine (job object) bağlanır; yetim ajan kalmaz. Oturum kaydı diskte olduğundan `resume` ile ajanın kendi oturum kimliğiyle sürdürülür.
- **Yükseltme/kurulum:** kurucu dosyaları değiştirmeden önce `rorch daemon stop` çalıştırır; sürüm ya da paket karması uyuşmayan daemon'a bağlanan istemci açık bir hata alır ("yeniden başlatın"). Uyumluluk katmanı, eski sürümle konuşma yok (depo kuralı).
- **Daemon olmadan çalışanlar:** `--version`, `setup`, `repair`, `uninstall`, `config`, `health` — kurucu ve onarım motor kapalıyken de çalışmalı.

### 5. İstemci davranışları

- **Masaüstü:** önce mevcut daemon'a bağlanır, yoksa başlatır; görsel çocuk motoru (`_ipc`) kalkar. Yerli onay için özel `_ipc --human` çocuğu kalır (§3). Daemon ulaşılamazsa ekran "motor yok" der ve **sahte/yedek veri çizmez** (ürün ilkesi, `engine_owns.test.ts`).
- **CLI:** oturum, görev ve durum komutları daemon'a gider; ulaşılamazsa `ENGINE_UNAVAILABLE` hatasıyla biter.
- **MCP:** `rorch mcp` ince bir köprüye dönüşür; araç çağrılarını daemon'a iletir. Özyineleme koruması (`RESPECTED_ORCH_DELEGATED`) aynen kalır.

### 6. Teknik sorular (1. dilimde cevaplandı)

1. *Cevap:* onay durumu (`approval.py`: meydan okuma, karar, hibe) imzalı dosyalardadır, bellekte değil; iki süreç tutarlıdır. `session_control.py` durumu bellektedir ve 2. dilimde daemon'a taşınır. (Soru: `approval.py` ve `session_control.py` durumunun hangi kısmı bellektedir?) İki süreçli yapıda (daemon + özel `--human` çocuk) tutarlılık için onay durumunun dosya tabanlı olması gerekir.
2. Bugün masaüstü ve CLI aynı veri köküne aynı anda yazıyor; kilitler yeterli mi? (`supervisor.lock` yalnız *çalışma başlatmayı* kilitler.)
3. *Cevap:* `winproc.ancestors` her halkada ebeveynin başlangıç zamanının çocuktan eski olmasını ister; yeniden kullanılmış PID zinciri keser (testli).
4. *Cevap:* ikisinde de çalışır (`context.engine_command`); paketlenmiş exe ile başlat/durdur uçtan uca testlidir.

## Reddedilen seçenekler

- **Yerel TCP + belirteç:** her platformda kolay ama bir port açar, aynı kullanıcının her süreci denetimsiz bağlanır ve belirteç dosyası işçiye de okunur; "yerel öncelikli, ağ yok" ilkesine ters.
- **Windows servisi / açılışta başlama:** yönetici hakkı ve kurucu karmaşıklığı ister; ürün "kullanıcı olarak, kurulumsuz" ilkesine uymaz.
- **Her ön yüzde ayrı motor, ortak dosya:** bugünkü durum; canlı oturum paylaşımını çözmez.

## Kararlar (onaylandı: hepsi öneri yönünde)

- **D1 — Taşıma:** adlandırılmış boru / Unix soketi (öneri) mi, yerel TCP + belirteç mi?
- **D2 — Ömür:** boşta kalınca otomatik çıkış mı (öneri: canlı oturum ve çalışma yokken 30 dk), hiç çıkmama mı?
- **D3 — Yetkili komutlar:** ortak uçta hiç sunulmasın, onay yalnız yerli pencere ve CLI TTY'den gitsin (öneri) mi?
- **D4 — Başlatma:** yalnız istek üzerine (öneri) mi, açılışta da mı?

## Dilimler (her biri motor + CLI + MCP/masaüstü karşılığı + test + belge ile biter)

1. **Daemon iskeleti:** `rorch daemon start|stop|status|restart`, tek örnek kilidi, boru + DACL, `hello` ve `engine.health`, sunucu tarafı köken çözümü, soy sınıflama, ayrıntılı güvenlik testleri; §6'daki sorular burada cevaplanır. Hiçbir ön yüz henüz taşınmaz.
2. **Oturumlar daemon'da:** `SessionController` ve `session_store` daemon'a taşınır; CLI `sessions` komutları; iş nesnesi ile yetim koruması.
3. **Masaüstü bağlanır:** görsel çocuk motoru kalkar, `--human` çocuk kalır; "motor yok" durumu; `engine_owns` testi güncellenir.
4. **MCP köprüsü.**
5. **Kurucu ve yükseltme:** durdurma adımı, sürüm uyuşmazlığı, `FOOTPRINT`/`ARCHITECTURE` güncellemesi.
6. **Tek işlem kataloğu** (karar 3): `catalog.list`, CLI/MCP/masaüstü komutlarının tek tablodan üretilmesi. Daemon'un bir sonucu, ayrı iş.

## İlerleme (her dilim bitince güncellenir)

Durum: `[x]` bitti ve doğrulandı, `[~]` yapıldı ama bir kısmı doğrulanmadı, `[ ]` yapılmadı. Son güncelleme: 9 Kasım 2026.

| Dilim | Görev | Durum | Not / doğrulanmayan |
|---|---|---|---|
| 1. İskelet | `rorch daemon start\|stop\|restart\|status`, tek örnek kilidi, kullanıcıya özel boru, sunucu tarafı köken çözümü, yetkili komutların sunulmaması, boşta çıkış | `[x]` | Başka kullanıcı hesabıyla erişim reddi ve gerçek ajan işçisi soyundan bağlanma uçtan uca denenmedi |
| 2. Oturumlar | Tek `SessionController`, `rorch session ...`, tur sürerken boşta çıkmama, iş nesnesiyle yetim koruması | `[~]` | Gerçek ajanla (opencode) uçtan uca oturum çalıştırılmadı (token harcar, onay ister) |
| 3. Masaüstü | Kabuk motora boruyla bağlanır, motor masaüstü programını dosya ve karmayla tanır (`renderer` düzeyi), onay bağlantısı özel çocukta kalır | `[~]` | Gerçek uygulamayla bağlantı, tanıma ve "uygulama kapanınca motor kalır" görüldü; ekrandaki rozet ve `session.defaults.set`'in uygulamadan çağrılması görülmedi |
| 4. MCP oturum araçları | `rorch mcp`'ye 8 `orchestrator_session_*` aracı; çağrı motora iletilir (motor yoksa başlatılır), özyineleme koruması korunur | `[~]` | **Kapsam değişti:** mevcut araçlar (görev, proje, kampanya, apply, not) canlı durum tutmaz ve `apply` yetkili komuttur (ortak uçta sunulmaz), bu yüzden motora yönlendirilmedi; yarar yeni oturum araçlarındadır. Gerçek bir AI istemcisiyle (Claude Code) bağlanıp denenmedi |
| 5. Kurucu ve yükseltme | Kurucu dosyaları değiştirmeden önce `daemon stop`; sürüm/paket karması uyuşmazlığında açık hata; `FOOTPRINT`/`ARCHITECTURE` | `[ ]` | |
| 6. Tek katalog | `catalog.list`; CLI, MCP ve masaüstü komutlarının tek tablodan üretilmesi (karar 3) | `[ ]` | Ayrı iş |

Dilimler arası kalan işler: Unix soketi (Windows dışı), `session.defaults.set` dışında masaüstünün ayar ihtiyacı doğarsa yeniden değerlendirme, `daemon` günlüğünün dönmesi/boyutu.

## Doğrulama planı

Birim: tek örnek, ikinci başlatma, durdur/yeniden başlat idempotent, bayat uç temizliği. Güvenlik: işçi soyundan gelen bağlantı hiçbir komut çalıştıramaz; ortak uçta yetkili komut bulunmaz (katalog testi); başka kullanıcı erişim listesi denetimi; sürüm uyuşmazlığı reddi. Paket: donmuş `rorch.exe` ile başlat/durdur uçtan uca. Çökme: daemon öldürülünce yetim ajan kalmaz, `resume` çalışır.

## Sonuçlar ve sınırlar

- 2. dilim sonrası: tek kalıcı motor süreci, kullanıcıya özel boru, sunucu tarafı köken çözümü, `rorch daemon` ve `rorch session` komutları vardır; canlı sohbet oturumları motordadır ve bağlantılar arasında ortaktır. MCP henüz taşınmadı.
- 3. dilimde `session.defaults.set` için karar: ayar komutları ortak uçta herkese açılmaz; yalnız **kurulu masaüstü programı** (dosya yolu ve `distribution.json` karması eşleşen süreç) `RENDERER` düzeyi alır. Masaüstünün başka ayar komutu yoktur. Bu, 'ayar yoktur' ilkesinden bilinçli ve dar bir sapmadır.
- Gerçek bir ajanla (opencode) uçtan uca oturum bu dilimde çalıştırılmadı (token harcar, ayrıca onay ister); paylaşım sahte kayıtla, kapsama gerçek süreçlerle test edildi.
- Aynı kullanıcı olarak çalışan işçi veri kökünü okuyabilir; motor bunu kapatmaz. Kapattığı şey, işçinin insan onayı olmadan onay/uygulama komutunu tetiklemesidir.
- Başka kullanıcı hesabıyla erişim reddi ve gerçek bir ajan işçisinin soyundan bağlanma uçtan uca denenmedi; erişim listesi içeriği ve sınıflama birim testle doğrulandı.
- Windows dışı (Unix soketi), oturumların taşınması, masaüstü/MCP bağlanması, kurucu durdurma adımı ve tek katalog sonraki dilimlerdir.

## Kaynaklar

- `src/respected_orchestrator/engine/daemon.py`, `daemon_client.py`, `winproc.py`, `supervisor.py`, `local_api.py`, `authority.py` (erişim: 2026-11-09).
- `desktop/src-tauri/src/engine_connector.rs`, `approval.rs` (erişim: 2026-11-09).
- Kanıt: `tests/engine/test_daemon.py` (18), `tests/packaging/test_frozen_build.py`, `cargo test` (38) (erişim: 2026-11-09).
