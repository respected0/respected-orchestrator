# Kalan işler

Orchestrator deposundaki açık işlerin **tek listesi** (Hub ve Brain kapsam dışıdır; `ROADMAP.md` bu listenin dışındadır, buradaki işler onun dışında yürüyen ek işlerdir). Bir iş bitince buradan silinir. Son güncelleme: 10 Kasım 2026.

Her maddede rakiplerin aynı işi **nasıl** yaptığı yazılıdır. Rakip bilgisi 10 Kasım 2026'da resmî belgelerden ve depolardan okundu (kaynaklar ve ayrıntı: [RAKIP_ESKIKLERI.md](RAKIP_ESKIKLERI.md) §0 ve §1c); hiçbir rakip ürün çalıştırılıp denenmedi.

**Etiketler:** `[K]` yalnız kod ya da belge işi, şimdi yapılabilir · `[A]` gerçek ajan koşusu ister (token harcar, önce sorulur) · `[O]` gerçek ortam, donanım ya da dış hesap ister · `[S]` önce sizin kararınız gerekir.

Kısaltmalar: **CC** Claude Code (CLI ve masaüstü), **Cx** Codex (CLI ve ChatGPT masaüstü uygulaması), **dsh** DeepSeek Harness, **AO** Orchestrator.inc.

## Yön kararı (10 Kasım 2026, kullanıcı)

**Bundan sonra her şeyi, yapacağımız ve var olan özellikleri, rakiplerdeki gibi yaparız.** Bir iş için tasarım seçerken önce rakiplerin nasıl yaptığına bakılır ve o yol izlenir; kendi yolumuzu ancak rakip yolu aşağıdaki istisnalarla çatışırsa seçeriz. Bu karar bağlayıcıdır ve bu listedeki her maddenin "Yapılacak" satırını belirler.

**Birincil kaynak Orchestrator.inc'tir (AO).** Bir özelliğin nasıl yapılacağına önce AO'ya bakarak karar verilir: mimari, veri akışı ve ekran davranışı ondan alınır. Diğer rakipler (Claude Code, Codex, dsh, Herdr, Orca ve diğerleri) özelliği **daha iyi** yapmak için örnek alınır: AO'nun yaptığını bir başkası daha iyi çözmüşse o çözüm eklenir. AO'da hiç olmayan bir özellikte diğer rakiplere bakılır. İki kaynak çelişirse AO'nun yolu temel alınır, fark bu listede yazılır.

**Sandbox yok ve eklenmeyecek.** Bu kesin karardır, açık iş ya da ileride yapılacak bir şey değildir. AO'da da kendi sandbox'ı yoktur. İşçiler ve sohbet ajanları kullanıcı olarak, ajanın kendi izin kipi ve (varsa) ajanın kendi sandbox'ı ile çalışır; motor buna bir yalıtım katmanı eklemez ve belgelerde yalıtım iddiası yazılmaz. Rakip tablolarında Claude Code, Codex ya da dsh'nin sandbox'ından söz edilmesi yalnız bilgidir; bizim için yapılacak iş anlamına gelmez. Bu belgeleri okuyan ajan sandbox, AppContainer, kapsayıcı ya da benzeri bir yalıtım önermez, eklemez, "eksik" olarak işaretlemez.

Bu kararla kesinleşenler:

1. **Arka plan süreci ve tek komut tablosu:** rakiplere göre eksik olan her şey tamamlanır: canlı akış (4.4; yapıldı, ADR-034), tablo satırlarında girdi şeması ve üretilmiş tipler (1.2), görev/proje/kampanya komutlarının motora taşınması (1.1), Unix soketi (1.4), güncellemede çalışan işin korunması (1.6).
2. **Ajanın kendi terminali Orchestrator.inc'teki gibi yapılır** (3.4): yapılandırılmış sohbet **ve** ajanın kendi terminal arayüzü, aralarında geçiş; terminal ayrı bir süreçte yaşar, arayüz kapanınca kapanmaz.
3. **Çok ajan desteği ACP ile yapılır** (3.2): Codex kendi `app-server`'ı ile, Claude Code dahil geri kalan herkes tek ACP adaptörüyle. Ajan başına ayrı adaptör yazılmaz.
4. **Pano durumu saklanmaz, olgulardan türetilir** (4.2); **worktree kuralları rakiplerle aynıdır** (`.worktreeinclude`, kurulum betiği, süpürme; 4.3).
5. **İnceleme kuyruğu ve geri bildirimin sahibi işçiye dönmesi** Orchestrator.inc ve Codex'teki gibi yapılır (4.8, 4.16).
6. **Onay devretme (`auto_review`), eklenti, hook ve alt ajan:** rakiplerdeki gibi ajanın kendi özelliği olarak sunulur; kendi katmanımızı yazmayız.
7. **Güncelleme çalışan işi kesmez** (1.6): Herdr ve Orchestrator.inc'teki gibi. ADR-031'in "güncellemede koruma yoktur" maddesi bu kararla değişir.
8. **Uzak ve mobil erişim yapılır**, Orchestrator.inc'in yerel öncelikli yoluyla (oturum makinede kalır, telefon istemcidir, dinleyici isteğe bağlı ve kimlik doğrulamalıdır); sıranın sonundadır.
9. Aşağıdaki sıra onaylanmıştır.
10. **Onay ve uygulama rakiplerdeki gibi yapılır** (1.7): onay, motorun istemciye yolladığı istek olur ve uygulamanın kendi ekranında (ileride telefonda) yanıtlanır; ayrı `apply` komutu yerine "dala çevir / yerele al / PR aç" gelir. Korunan iki şey: doğrulama geçmemiş işte bu eylemler kapalıdır, işçi soyundan gelen bağlantı onay veremez. ADR-004 bu kararla değişir.

**İstisnalar (rakipler yapsa da biz yapmayız; §8):** telemetri yok, hesap zorunluluğu yok. Bunlar ürünün farkıdır; yön kararı bunları kaldırmaz.

**İstisna sanılan ama rakiplerle aynı olan iki şey** (10 Kasım 2026'da rakip belgelerinden bakıldı; sandbox için yukarıdaki kesin karara bakın):

| Konu | Rakipler | Biz | Sonuç |
|---|---|---|---|
| Kipi yalnız kullanıcı seçer | CC: kipi kullanıcı seçer (seçici, `Shift+Tab`); izin sorusunda "evet ve otomatik kipe geç" seçeneği kullanıcıya sunulur. Cx: seçici istem kutusunun altında; ajan `request_permissions` ile **ek izin isteyebilir**, kullanıcı istenenin bir kısmını tur ya da oturum için verir. AO: kullanıcı seçer | Yalnız kullanıcı seçer; ajan isteyemez | Aynı. Eksiğimiz: ajanın ek izin **istemesi** ve kullanıcının yerinde vermesi (4.6'ya eklendi) |
| Onaysız gerçek ağaca uygulanmaz | Worktree oturumunda iş dalda kalır; gerçek ağaca **git ile** geçer: Cx'te "Hand off" ya da "Create branch here", CC'de PR, AO'da PR ve `POST /prs/{id}/merge`. Yerel oturumda ajan gerçek ağacı kipe göre doğrudan düzenler. Otomatik birleştirme isteğe bağlıdır (CC "Merge when ready" = GitHub'ın otomatik birleştirmesi). **Hiçbirinde doğrulama kapısı yok** | Yama, doğrulama geçmeden ve onaysız uygulanmaz; ayrı `apply` komutu | Sonuç aynı (kullanıcı karar verir), yol farklı. Bizim eklediğimiz tek şey doğrulama ve imzalı kanıt; o korunur |

## 0. Sıra

Sıra `RAKIP_ESKIKLERI.md` §3'teki sıradır; rakip karşılaştırmasından gelen üç değişiklik **kalın** yazıldı (onaylandı).

1. ~~Belge borcu (§6)~~ yapıldı (10 Kasım 2026).
2. ~~`agent.describe` şeması (§3.1)~~ yapıldı (10 Kasım 2026, ADR-033).
3. A1 görev başlatma → A2 pano → A3 worktree ve geri alma (§4.1–4.3). `[K]`
4. ~~B1 canlı akış (§4.4)~~ yapıldı (10 Kasım 2026, ADR-034); kalanlar 4.4'te.
5. **Ajanın kendi terminal paneli (§3.4): orkestratör sınıfındaki rakiplerin hepsinde var; ajan başına adaptör yazmadan bütün ajanları kullanılır kılar.** `[K]` Yapıldı (10 Kasım 2026, ADR-035: motor, bölme, geçiş); gerçek uygulamada görülmedi, kalanlar 3.4'te.
6. E1 ayarlar ve bağlantı ekranı + C3 talimat dosyası + B3 izin kipleri (§4.5–4.7). `[K]` Ayarlar formu yapıldı (10 Kasım 2026); bağlantı ekranı, talimat dosyası ve kipler sırada.
7. C1 bağlam göstergesi + E2 bildirim + E3 kısayollar; **G1 inceleme kuyruğu buraya alınır (AO ve Cx'te ürünün merkezi; bizim "kanıtla ve onayla" odağımızın ekrandaki karşılığı).** `[K]`
8. B4 çoklu ajan + E4 geçmiş araçları → B2 → D1 + C2 → A4 + D4 → D2/D3/D5 → B5/B6 → E7.

## 1. Motor

- [ ] **1.1 Görev, proje ve kampanya komutlarını motora taşı** `[K]`, `apply` için `[S]`
  - Bizde: motor komutları tek tabloda (`engine/catalog.py`, ADR-032). Tek görev koşusu motora taşındı (10 Kasım 2026): `task.start|status|cancel|retry`, `rorch task …` ve masaüstü "Yeni görev" bunları kullanır. Süreç içi MCP araçları (`orchestrator_task_start`, `_project_start`, `_progress`, …) ve eski CLI komutları (`create`, `start`, `project-*`, `campaign-*`, …) hâlâ kendi listelerinde, süreç içinde çalışıyor; aynı kayıtları yazdıkları için koşular her yüzde görünür.
  - Rakipler: AO'da oturumun bütün yaşam döngüsü (başlat, öldür, geri yükle, yeniden adlandır) arka plan sürecinin HTTP ucundan geçer; CLI, masaüstü ve mobil aynı ucu kullanır. Cx'te her şey `codex app-server` üzerindendir (`thread/start`, `turn/start`, `review/start`). CC'de arka plan oturumlarını "supervisor" süreci tutar.
  - Yapılacak: (a) MCP görev araçlarını motor komutlarına yönlendir (`--allow-privileged` ve `--allow-auto-apply` kayıt bayraklarının motora nasıl taşınacağı çözülmeli; bugün bu yüzden süreç içinde); (b) proje ve kampanya başlatmayı motor komutu yap (plan taslağı yolu `plan.create|edit|start` zaten motorda); (c) eski süreç içi CLI komutlarını `rorch task|project|campaign` altında motora bağla ve eskilerini sil; (d) `rorch task` terminaldeki kişiyi operatör saymıyor (boruya bağlanan her süreç MCP düzeyinde), bu yüzden `custom` işçi yalnız eski `create` ile seçilebiliyor. `apply` 1.7'de çözülür.
- [ ] **1.2 Katalog satırlarına girdi şeması** `[K]`
  - Bizde: tablo komut adını ve yetki sınıfını taşıyor; girdi şeması yalnız MCP yüzü olan 8 komutta var.
  - Rakipler: AO OpenAPI tanımını Go veri tiplerinden, TypeScript tiplerini de ondan üretir ve ayrışmayı CI'da denetler (bizim katalog testiyle aynı yöntem). Cx `codex app-server generate-ts` ile tipleri üretir. Herdr `hc schema` ile API'yi OpenRPC olarak verir.
  - Yapılacak: her komuta girdi şeması; `catalog.ts` komut adlarının yanında girdi tiplerini de üretsin. Acil değil; yeni ekran yazarken elle tip yazmayı bitirir.
- [ ] **1.3 Masaüstü `catalog.list`'i kullanmıyor** `[K]`: komut hazır; ekranların motorun sunduğuna göre açılıp kapanması gerektiğinde bağlanacak. Bugün ihtiyaç yok.
- [ ] **1.4 Unix soketi (macOS/Linux)** `[K]` yazım, `[O]` doğrulama
  - Bizde: motor yalnız Windows'ta (adlandırılmış boru).
  - Rakipler: Cx app-server `unix://` soketini destekler; AO Unix'te yerel soket kullanır. Hepsi üç işletim sisteminde çalışır.
  - Yapılacak: kullanıcıya özel (0700) klasörde soket; `test_no_telemetry` izin listesine gerekçeli satır. Bu makinede denenemez.
- [ ] **1.5 Bağlantı başına durum** `[K]`: sesli giriş ve ekran görüntüsü hazırlığı bağlantıya bağlı; kabuk yeniden bağlanırsa yarım hazırlık düşer. Motora alınabilir.
- [ ] **1.6 Güncellemede çalışan iş korunmuyor** `[K]` (yön kararı 7: korunacak)
  - Bizde (ADR-031 kararı): kurucu açık süreçleri kapattırır; çalışan görev yarıda kalır ve "yarıda kaldı" işaretlenir. Yedek ve geri alma yok.
  - Rakipler: Herdr'de `hc update` çalışan terminalleri kapatmadan çekirdeği günceller. AO'da sohbet sağlayıcıları oturum başına ayrı, kopuk süreçlerde çalışır; masaüstü kapanınca ve güncelleyici arka plan sürecini değiştirince sağlayıcı yeniden başlatılmadan yeniden bağlanılır. CC supervisor'ı oturumu kaldığı yerden yeniden başlatır.
  - Yapılacak: işçi ve terminal süreçleri motordan ayrı, kopuk süreçlerde yaşar; yeni motor açılınca onlara yeniden bağlanır. Kurucunun `CloseApplications=force` davranışı işçileri kapatmayacak biçimde daraltılır. ADR-031 madde 6 güncellenir; tasarım notu önce yazılır.

- [ ] **1.7 Onay ve uygulamayı rakiplerdeki gibi yap** `[K]` (yön kararı 10)
  - Bizde: `approval.decide` ve `approval.apply` `PRIVILEGED`; ortak uçta sunulmaz, yalnız kabuğun özel `--human` sürecindeki yerel pencereden verilir (ADR-004, ADR-030 karar 3).
  - Rakipler: Cx'te sunucu istemciye istek yollar (`item/commandExecution/requestApproval`, `item/fileChange/requestApproval`); yanıt `accept` / `acceptForSession` / `decline` / `cancel`; bağlı her istemci yanıtlayabilir. CC'de SDK `canUseTool`. AO'da oturum `waiting_input` olur ve yanıt dört biçimdedir: `allow_once` / `allow_always` / `reject_once` / `reject_always` (ACP'nin biçimleriyle aynı; AO kaynağı `ports/chat.go`, 10 Kasım 2026). `apply` komutu yoktur; iş dalda durur ve "Hand off", "Create branch here" ya da PR ile gerçek ağaca geçer.
  - Yapılacak, önce tasarım notu (ADR-004'ün yerine geçecek yeni ADR): (a) onay isteği motordan istemciye; tanınan masaüstü (`RENDERER`) yanıtlar, `CHILD` yanıtlayamaz, `MCP` kökeni için ayrıca karar; (b) dört yanıt biçimi AO'daki adlarla (`allow_once`, `allow_always`, `reject_once`, `reject_always`); Codex'in `accept` / `acceptForSession` / `decline` / `cancel` yanıtlarına Codex adaptörü çevirir; (c) `apply` yerine dala çevir / yerele al / PR aç, doğrulama ve imzalı kanıt ön koşul; (d) yerel onay penceresi, `--human` süreci ve ilgili testler kalkar; `THREAT_MODEL.md` ve `ARCHITECTURE.md` aynı değişiklikte güncellenir. Ön koşul hazır: istek, `events.subscribe` akışından (ADR-034) yeni bir bildirim adıyla istemciye yollanır; yanıt olağan komutla gelir.

## 2. Kurulum

- [ ] **2.1 Authenticode imzası** `[O]`: kurucu imzasız, SmartScreen uyarı gösterebilir. Sertifika ister.
- [ ] **2.2 Masaüstünden kaldırma** `[K]`: kaldırmadan önce `rorch uninstall` elle çalıştırılmalı; yoksa AI araçlarındaki MCP girdileri olmayan programı gösterir. E1 ekranına "Kaldırmaya hazırla" eklenir (§4.5).
- [ ] **2.3 Ürün sözleşmesinin Hub ve Brain kopyaları eski** (`/SET=`, `/PURGE=` kalktı; ADR-023, ADR-031): o depolar kapsam dışı, sahibi karar verir. `[S]`

## 3. Ajan adaptörü

- [ ] **3.1 `agent.describe` kalanları** `[K]` (şema ve komut yapıldı: ADR-033)
  - Masaüstü yalnız yeni sohbet sayfasında varsayılan ajanın durum satırını gösteriyor; ajan seçici yok, çünkü sohbet tek ajanla (`opencode`) çalışıyor. Seçici 3.2 ile gelir.
  - `openrouter` adaptör tablosunda (`agent_adapters.ADAPTERS`) yok, bu yüzden cevapta da yok. Cursor ve Antigravity için kip eşlemesi yazılmadı (`modes: unsupported`). Codex'te yalnız yardım metninde görülen iki kip var (`default`, `bypass-permissions`).
  - AO'nun tazelik durumları (`fresh` / `stale` / `checking`) alınmadı; 30 saniyelik önbellek var. İlk çağrı altı ajanı sırayla yoklar.
- [ ] **3.2 Adaptör yolları: üç yol yeter** `[K]` tasarım, `[A]` doğrulama
  - Rakipler: AO sohbet için iki yol kullanır: Codex'e yerel `app-server`, **Claude Code dahil** geri kalan herkese ACP (Claude Code için `claude-agent-acp`; ayrıca Cursor, OpenCode, Droid, Kimi, Pi, Qwen, DeepSeek Harness, GitHub Copilot). dsh de `acp` profiliyle kendini ACP sunucusu olarak açar.
  - Karar (yön kararı 3): ajan başına ayrı adaptör yerine (a) Codex: `codex app-server`, (b) geri kalanlar: tek ACP adaptörü (`opencode` ACP istemcimiz var; Claude Code, `dsh`, `agy`, `cursor` buradan gelir), (c) Claude Code'da ACP'nin vermediği alanlar (bağlam doluluğu, `/compact`) için üstüne `stream-json` / Agent SDK. `RAKIP_ESKIKLERI.md` §7'deki ajan başına sıra bununla değişti.
  - Codex için ajan koşusu olmadan bilinenler (resmî `app-server` belgesi): `model/list` model ve çaba listesini verir, `thread/compact/start` sıkıştırır, `turn/steer` çalışan tura mesaj ekler, `turn/interrupt` keser, `thread/revert` geçmişi geri sarar, `account/usage/read` kullanım verir, onaylar sunucudan istemciye istek olarak gelir. Claude Code'da belgelenmiş model listesi sorgusu hâlâ yok.
- [ ] **3.3 Claude Code adaptörünün alan doğrulaması** `[A]` (`agent.describe` içinde `commands` ve `context` bu doğrulamaya kadar boş ve `unverified`): `init` mesajının şeması (`slash_commands`, `skills`, `model`, `permissionMode`), `compact_boundary`, `get_context_usage` ya da `statusLine` yolu; etkileşimsiz yolu doğrulanmamış komutlar (`/usage`, `/goal`, `/fork`, `/resume`, `/add-dir`, …; tablo `RAKIP_ESKIKLERI.md` §7).
- [ ] **3.4 Ajanın kendi terminal arayüzü: kalanlar** `[K]` (motor tarafı, masaüstü bölmesi ve geçiş yapıldı, 10 Kasım 2026, ADR-035)
  - Bizde: her terminal ayrı, kopuk bir süreçte ConPTY ile yaşar (`rorch _pty-host`); motor `terminal.start|list|input|resize|kill|attach` komutlarıyla başlatır, yazar ve çıktıyı akıtır; motor kapansa da terminal çalışır. Masaüstünde Terminal bölmesi seçili klasörde "Ajan terminali aç" ile xterm.js (WebGL çizicisi) terminali açar. Motor yalnız sahte programla sınandı; **bölme gerçek uygulamada ve gerçek ajan arayüzüyle hiç görülmedi** (tarayıcı önizlemesi kabuk olmadan çalışmıyor; ayrıca terminal komutları yalnız kurulu, tanınan masaüstüne açık).
  - Kalan: (a) gerçek uygulamada doğrulama: WebView2'de WebGL, yazma, yeniden boyutlandırma, yapıştırma, kopyalama; (b) geçiş yalnız boştaki oturumda ve yalnız `opencode` için var ("Diğer → Terminalde sürdür", terminalde "Sohbete dön"); AO'daki "çalışan turu bekle ya da kes" seçenekleri ve kalıcı geçiş aşamaları yok, sohbet dökümü terminalde yapılanları içermiyor, `opencode --session` gerçek ajanla denenmedi `[A]`; (c) `agent.describe` `interfaces.terminal`'i program bulunduğunda `native` gösteriyor, ama yalnız `.cmd` kabuğu bulunan kurulumda terminal açılmaz; bölmede ajan seçici yok (varsayılan ajan açılır); (d) terminaldeki ajanın durumu (hook) okunmuyor, kendi kendine biten terminal `terminal.state` bildirmiyor (izleyen `terminal.exit` alır); (e) `rorch terminal` yalnız `list` (1.1 d çözülünce başlatma ve bağlanma eklenir); (f) çizilmiş ekran yerine ham son 256 KB saklanıyor; (g) klasör başına tek terminal gösteriliyor, sekme yok; (h) Unix yok (1.4).
- [ ] **3.5 `/model` kaydı** `[K]`: terminalde seçilen model kullanıcının varsayılanı olarak kaydediliyor; motor yalnız oturum içi yolu kullanmalı. Rakipler: CC'de arka plan oturumunun modeli gönderildiği yerden gelir ve ayara yazılmaz; Cx'te model tur başına verilir.
- [ ] **3.6 Sohbet yalnız `opencode` için doğrulanmış** `[A]`: codex, claude, cursor akışları hiç yakalanmadı.
- [ ] **3.7 Cursor sürüm tabanı sabitlenmedi** (`AGENT_ADAPTER_MATRIX.md`, `unpinned`) `[K]`.

## 4. Masaüstü özellikleri

Bağlayıcı kurallar (`RAKIP_ESKIKLERI.md` §6): ajanın kendi özellikleri ajandan gelir, biz yeniden üretmeyiz; telemetri yok; kipi yalnız kullanıcı seçer; sandbox yok ve eklenmeyecek. Her maddede birincil örnek AO'dur; diğer rakipler iyileştirme içindir ("Yön kararı").

- [ ] **4.1 A1 Görev ve plan başlatma ekranı** `[K]`
  - Bizde: masaüstü tek görev başlatabiliyor (10 Kasım 2026): Görevler sayfasında "Yeni görev" formu (klasör, görev, tür, ajan, kapsam, kabul komutları) `task.start`'ı çağırır; ajan listesi `agent.describe`'tan gelir. Gerçek uygulamada ve gerçek ajanla denenmedi.
  - Rakipler: CC'de istem kutusunun altındaki satırda ortam, klasör, izin kipi ve model seçilir. AO'da projenin "ana ajanı"na hedef yazılır; o planlar ve her parça için kendi worktree'sinde bir işçi başlatır. Vi3ecode'da hedef bir kez yazılır, lider yönlendirir.
  - Yapılacak: (a) AO'daki gibi hedef yazıp planlatma: plan taslağı ekranı (`plan.create|edit|start` motorda hazır, ekranı yok) ve proje başlatma; (b) formda izin kipi ve model seçimi (`agent.describe` kipleri veriyor; işçiye kip geçirme yolu yok); (c) kabul komutu satırı boşluklardan bölünüyor, tırnaklı argüman yazılamıyor; (d) `mcp_acceptance_allow` listesini ekrandan düzenleme (4.5 ayarlar ekranı).
- [ ] **4.2 A2 Pano: kalanlar** `[K]` (pano yapıldı, 10 Kasım 2026)
  - Bizde: Görevler sayfası dört şeritli pano açıyor (Sizi bekliyor, Çalışıyor, Onaya hazır, Arşiv); şeridi motor her okumada koşunun dosyalarından türetir (`read_model.lane_of`), saklamaz. Kartta iptal ve yeniden dene var; sürükle-bırak yok. Gerçek uygulamada görülmedi.
  - AO ile fark: AO'nun sütunları `building`, `validating`, `needs_review`, `ready`, `archive`'dır ve PR, CI, inceleme olgularından türer. Bizde PR ve inceleme olgusu panoya girmedi (4.8, 4.16), bu yüzden `validating` ve `needs_review` yok.
  - Kalan: (a) projeler ve sohbet oturumları panoda yok, yalnız tek görev koşuları var; (b) pano en yeni 100 koşuyu gösterir, şeride göre süzme ve sayfalama yok; (c) karttan kanıta ve değişikliğe gitme (4.3, 4.8); (d) kartta son olay metni (bugün durum metni var).
- [ ] **4.3 A3 Worktree, dal ve değişiklik görünümü, geri alma** `[K]`
  - Bizde: motorda worktree ve `checkpoint.py` var, ekranda yok. İşçinin yaması siz onaylamadan gerçek ağaca uygulanmaz. `.worktreeinclude` tanınıyor (10 Kasım 2026, `lanes.copy_worktree_includes`): gitignore'da olup dosyada adı geçenler yeni worktree'ye kopyalanır, yamaya girmez.
  - Rakipler: CC worktree'leri `.claude/worktrees/` altında açar; `.worktreeinclude` dosyası gitignore'daki dosyaları (`.env` gibi) yeni worktree'ye kopyalar; süresi dolanları düzenli süpürür. Cx `$CODEX_HOME/worktrees` kullanır, aynı `.worktreeinclude` kuralını tanır, "Hand off" ile sohbeti worktree ↔ yerel arasında taşır, worktree sayısını sınırlar. Geri alma: CC her istemde yalnız kendi düzenleme araçlarının değiştirdiği dosyaları kaydeder (`/rewind`; kabuk komutlarının değiştirdiği dosyalar dışarıda). Cx `thread/revert` ile konuşma geçmişini geri sarar.
  - Yapılacak: ekranda dal, değişen dosyalar ve "uygulamayı geri al" (uygulanan yama için git ile). `.worktreeinclude` yapıldı; G12 kurulum betiği kaldı (AO'nun okunan belgelerinde ikisinin de karşılığı yok, örnek CC ve Cx'tir). "Uygulamayı geri al" gerçek ağaca yazdığı için 1.7 ile birlikte tasarlanır. Süpürmede AO'nun kuralı temel alınır: değişiklik içeren worktree zorla silinmez.
- [ ] **4.4 B1 Canlı akış: kalanlar** `[K]` (akış yapıldı, 10 Kasım 2026, ADR-034)
  - Bizde: ajanın çıktısı satır satır okunur; `events.subscribe` ile açılan ayrı bağlantıdan `session.event` ve `session.state` bildirimleri akar (AO'nun tek yönlü akışı gibi); `rorch session watch`, `session.events` içinde `live`, sayfalı `session.transcript`. Sohbet ekranı artık yoklamıyor. Gerçek uygulamada ve gerçek ajanla görülmedi.
  - Kalan: (a) görev panosu hâlâ 4 saniyede bir yokluyor: koşular ayrı süreçlerde dosyaya yazdığı için motorun dosya değişikliğini izleyip `run.state` bildirmesi gerekir (AO'daki CDC); (b) harf harf akış yok, `opencode run` metni parça tamamlanınca verir (3.2 ile); (c) kayıtlı konuşmanın silinmesi bildirilmiyor; (d) sayfa imleci konum numarası, 200 turu aşan konuşmada kayar; (e) kenar çubuğu sohbet sayfası açık değilken güncellenmiyor (dinleyici o sayfada).
- [ ] **4.5 E1 Ayarlar ve bağlantı ekranı: kalanlar** `[K]` (ayarlar formu yapıldı, 10 Kasım 2026)
  - Bizde: Ayarlar → Genel'de "Motor ayarları" formu motorun şemasından çizilir (etiket, yardım, tür), yalnız değişen anahtarları yollar. Kaydetme yerel bir onay penceresinden geçer: ekran `settings_request` ile ister, kabuk motora doğrulatır, kişiye eski → yeni değerleri gösterir, Evet'te uygular. `settings.apply` ekrandan iletilmez. Gerçek uygulamada görülmedi.
  - Rakiplerle fark: AO, CC ve dsh'de ayar ekranı doğrudan yazar; bizde araya onay penceresi girer, çünkü önizleme, mikrofon, ekran yakalama, konuşma programı ve kabul komutu listesi WebView'ın kendi açamaması gereken izinlerdir. 1.7 yerel onay penceresini kaldırırsa bu da onunla birlikte karara bağlanır `[S]`.
  - Kalan: (a) bağlantı ekranı: `integrations` (AI araçlarına MCP girdisi) ve `memory connect|disconnect|status` hâlâ yalnız CLI'da; (b) G14 sağlayıcı ve model ayarı, AO'daki ajan başına ayar sayfası ve hesap sekmesi; (c) 2.2 "Kaldırmaya hazırla"; (d) form düz bir liste: gruplama, arama ve `default_roles` gibi JSON alanları için özel düzenleyici yok; (e) geliştirme kipinde (tanınmayan masaüstü) kaydetme `FORBIDDEN` döner.
- [ ] **4.6 B3 İzin kipleri (+ G11 kural dosyası ve korunan yollar)** `[K]`
  - Bizde: karar verildi (tüm kipler sunulur, kullanıcı seçer), ekranda yok.
  - Rakipler: CC ve Cx'te kip seçici istem kutusunun altındadır ve oturum sürerken değişir. Cx'te komut kuralları Starlark `.rules` dosyasıdır, `codex execpolicy check` ile sınanır. dsh'de `permission-presets` ve `guard` var.
  - Yapılacak: AO'daki gibi dört ortak kip adı (`default`, `accept-edits`, `auto`, `bypass-permissions`) kullanılır ve adaptör bunu ajanın kendi adına çevirir; ajanın bu dördün dışındaki kipleri (ör. `plan`) kendi adıyla listelenir. Liste 3.1'den gelir; kural dosyasını biz yazmayız, ajanınkini gösteririz (karar 8). Ajanın ek izin isteği (Cx `request_permissions`, ACP `session/request_permission`) ekranda sorulur; kullanıcı tur ya da oturum için verir. Kipi yine yalnız kullanıcı değiştirir.
- [ ] **4.7 C3 Proje talimat dosyası** `[K]`: `AGENTS.md` / `CLAUDE.md` görüntüleme ve düzenleme. Rakiplerin hepsi ajanın kendi dosyasını kullanır; Herdr kendi ayar klasörüne ajan için bir `AGENTS.md` koyar.
- [ ] **4.8 G1 İnceleme kuyruğu ve satır yorumlu diff** `[K]`
  - Bizde: diff paneli ve motorda `review.view` var; yorum, kabul, reddet, kuyruk yok.
  - Rakipler: Cx'in inceleme bölmesinde satıra yorum yazılır, dosya dosya "görüldü" işaretlenir, dosya sahnelenir ya da geri alınır; yorumlar ajana gider. AO'da başarısız CI, inceleme yorumu ve birleştirme çakışması **dalın sahibi işçiye** geri yollanır; bir inceleyici ajan PR'ı insandan önce okuyabilir. CC'de diff görünümü ve `/code-review` var.
  - Yapılacak: her işçi çıktısı kuyruğa düşer; satır yorumu ve başarısız doğrulama AO'daki gibi dalın sahibi işçiye geri gider; onay ve gerçek ağaca geçiş 1.7'deki yolla yapılır.
- [ ] **4.9 C1 Bağlam göstergesi ve G8 oturum ayrıntı paneli** `[K]` ekran, `[A]` veri yolu
  - Rakipler: CC'de sohbetin yanında kartlar var (nerede çalışıyor, ne değiştirdi, ne çalıştırıyor, bağlam doluluğu). Cx'te `/status`. dsh'de `token-meter`.
  - Yapılacak: veri 3.1'den; ajan vermiyorsa kart çıkmaz, "bilinmiyor" uydurulmaz.
- [ ] **4.10 E2 Bildirimler** `[K]`
  - Rakipler: CC, oturum bir işi bitirdiğinde ve o oturuma bakmıyorsanız işletim sistemi bildirimi yollar. AO `girdi bekliyor`, `birleştirmeye hazır` gibi durumlar için kalıcı bildirim ve uygulama içi bildirim merkezi tutar. Cx'te tur bitiş uyarısı ayarlardan açılır.
  - Yapılacak: tur bitti / onay bekliyor / hata; yalnız pencere o oturumda değilken; bildirime kod ya da istem yazılmaz.
- [ ] **4.11 E3 Kısayollar ve komut paleti** `[K]`: CC'de `Ctrl+/` tüm kısayolları gösterir; Orca tek kısayolla her çalışma alanına atlar.
- [ ] **4.12 B4 Çoklu ajan sohbeti ve G9 oturumlar arası mesajlaşma** `[K]`
  - Bizde: motorda takım, devir ve posta kutusu var (`team_profiles`, `handoff`, `team_loop`); ekran salt okunur.
  - Rakipler: CC'de bir oturum diğerlerini listeler, okur, mesaj yollar. Herdr'de bir ajan yardımcı ajan başlatır ve raporu kendi girdisine düşer. Vi3ecode'da roller tek konuşmayı paylaşır; otomatik devir "sıçrama sınırı" ve bütçe ile durur. Munder Difflin'de ajanlar ortak posta kutusu ve kara tahta paylaşır.
  - Yapılacak: var olan devir ve sınır mantığını ekrana bağla; yeni koordinasyon katmanı yazma.
- [ ] **4.13 E4 Geçmiş araçları** `[K]`: arama, yeniden adlandırma, sabitleme, arşiv, dışa aktarma. AO'da listeleme, yeniden adlandırma, öldürme ve geri yükleme arka plan sürecinin HTTP ucundadır; temel budur (motor komutu olarak, katalogda). Arama, sabitleme ve bölümler için örnek Cx'tir (`thread/list` süzgeçleri, `threadSection/*`, `thread/archive`); CC'de gruplama, sıralama, arşiv var.
- [ ] **4.14 B2 Sohbette dosya düzenleme ve komut çalıştırma** `[K]`: karar verildi (ajanın izin kipiyle açılır); 4.6'dan sonra.
- [ ] **4.15 D1 MCP yönetimi ve C2 sıkıştırma** `[K]` ekran, `[A]` doğrulama: MCP'de bugün salt liste var. Sıkıştırmayı ajan yapar (CC `/compact`, Cx `thread/compact/start`); biz yalnız tetikleriz.
- [ ] **4.16 A4 PR ve CI akışı** `[K]` kod, `[O]` gerçek uzak PR
  - Bizde: taslak PR ve CI yoklama motorda (ADR-014, ADR-020); gerçek uzak PR ve canlı CI hiç denenmedi.
  - Rakipler: AO'nun gözlemcisi GitHub ve GitLab'ı 30 saniyede bir yoklar, PR olgularını saklar, geri bildirimi işçiye yollar; birleştirme API'den yapılır. CC'de "Auto-fix" ve "Merge when ready" var. Cx PR incelemesini bir eklentiyle yapar; sohbette inceleme PR'a yorum yazmaz, onaylamaz, birleştirmez.
  - Yapılacak: yoklama yolumuz AO ile aynı yönde; eksik olan geri bildirimi sahibi işçiye yollamak. Otomatik birleştirme eklenmez (onay sınırı).
- [ ] **4.17 D5 ve G3 Zamanlanmış görevler** `[K]`: AO'da tekrarlayan otomasyon, çalışma geçmişi ve zamanlayıcı arka plan sürecinde. Cx'te "Scheduled" görünümü bir gelen kutusudur, Gmail/Slack/GitHub olayları tetikleyebilir, gözetimsiz koşu varsayılan izinlerle çalışır. CC'de masaüstü ve bulut zamanlanmış görevleri var. Bizde motor kalıcı olduğu için zamanlayıcı oraya girer; sonuç inceleme kuyruğuna (4.8) düşer.
- [ ] **4.18 Diğerleri (öncelik sırasıyla, hepsi `[K]` ya da karar)**: G2 yan sohbet (CC ve Cx'te var; ana bağlamı kullanır, geri yazmaz) · G10 ağ proxy ve alan adı listesi (ajanınki gösterilir) · D2/D3/D4 eklenti, hook, alt ajan (§7 karar) · G6 başsız kip · B5/B6 mesaj düzenleme ve oturumda model değiştirme · G5 CLI oturumunu uygulamaya alma (CC'de `/resume`, Cx'te "Import"; motorda `resume_session` var) · G12 kurulum betiği (4.3 ile) · E5 taslak kalıcılığı · E6 eski sohbetlerin taşınması · E8 erişilebilirlik ve dil · B7, C4, D6, D7, G4, G16 · G13 bilgisayar kullanımı ve G15 pazar/SDK ürün kararı olmadan başlanmaz.
- [ ] **4.19 Küçük ekran eksikleri** `[K]`: arama, arka plan görevleri bölmesi, "bilgisayarı uyanık tut" (AO'da masaüstü ve mobil için var), proje ayrıntısı.

## 5. Doğrulanmayanlar (kod var, gerçek ortamda görülmedi)

- [ ] `[A]` Gerçek ajanla (opencode) uçtan uca sohbet: başlat, gönder, olayları oku, kes, sürdür.
- [ ] `[A]` Gerçek ajanlı karşılaştırma (60 koşu; ADR-002, ADR-019): akıllı yönlendirmenin kazancı bu yüzden kanıtsız. opencode token sayısı vermediği için token tasarrufu iddiası başka bir ajan ister.
- [ ] `[A]` Gerçek bir ajan işçisinin soyundan motora bağlanmanın reddi (sahte kayıtla test edildi).
- [ ] `[O]` Gerçek AI istemcisiyle (Claude Code) `rorch mcp` ve `orchestrator_session_*` araçları.
- [ ] `[O]` Masaüstünde "Motor <sürüm>" rozeti ve `session.defaults.set`'in uygulamadan çağrılması.
- [ ] `[O]` Başka kullanıcı hesabıyla boruya erişimin reddi (yalnız erişim listesinin içeriği test edildi).
- [ ] `[O]` Paketli sürümde aynı sürüm numaralı farklı paketin motorunun reddi (`daemon status` → `build`).
- [ ] `[O]` Ses: makinede çevrimdışı konuşma tanıma modeli yok (indirme izin ister); Türkçe teknik terim doğruluğu ölçülmedi; mikrofon izni ve kayıt arayüzü yok (ADR-027).
- [ ] `[O]` Ekran görüntüsü: işletim sistemi yakalama seçicisi, karartma ve önizleme arayüzü, yerel insan-varlığı köprüsü yok (ADR-028).
- [ ] `[O]` macOS ve Linux: POSIX fixture koşusu hiç yapılmadı; sürüm kapısı her durumda `no-go` (ADR-008).
- [ ] `[O]` Hub'ın kurucuyu başlatışı, Defender ve SmartScreen davranışı (ADR-025, ADR-031).
- [ ] `[K]` `desktop_smoke.ps1` ve `preview_e2e.ps1` rozeti bulamıyor; pencere okuma yöntemi düzeltilmeli.
- [ ] `[K]` Tam Python süiti: 10 Kasım değişikliklerinden (maintenance silme, günlük dönmesi, paket karması, katalog) sonra çalıştırılmadı; işlerin sonunda çalıştırılacak. Paketli exe testleri de aynı.

## 6. Belge borcu `[K]`

10 Kasım 2026'da temizlendi: `ARCHITECTURE.md` (MCP cümlesi, B4 başlıkları, ekran kaynakları), `ADR-030`, `RAKIP_ESKIKLERI.md` §6 ve §7, `ADR-021`, `README.md`; `tempnotes.md` içeriği `ARCHITECTURE.md`'ye taşınıp silindi. Kalan:

- [ ] `THREAT_MODEL.md` §12 (masaüstü): "taslak" notu güncellendi ama satırlar tek tek yeniden değerlendirilmedi. 1.7 (onay yolunun değişmesi) bu bölümü zaten yeniden yazdıracağı için onunla birlikte yapılır.
- [ ] `ARCHITECTURE.md` B4 başlıklarında modüllerin nereden çağrıldığı yazıldı; paragrafların geri kalanı kodla satır satır karşılaştırılmadı.

## 7. Sizin kararınızı bekleyenler `[S]`

Yön kararıyla kapananlar (gerekçe olarak duruyor): onay devretme, adaptör yolu, güncellemede çalışan iş, eklenti/hook/alt ajan, uzak ve mobil. Onay ve `apply` da kapandı (yön kararı 10). **Bekleyen karar yok.**

- **Ajana onay devretme (`auto_review`)** (kapandı: ajanın kendi kipi olarak sunulur, varsayılan kapalı). Cx'te kip seçicide "Approve for me" olarak duruyor: ana ajan bir eylem önerir, ayrı bir inceleyici ajan onay isteğini değerlendirir, ret sıradan hata sayılmaz. (AO'daki `autoReview` farklı bir şeydir: PR'ı inceleyici ajana otomatik okutur, onay devretmez.) Öneri: kendi inceleyicimizi yazmayalım; ajanın kendi kipi olarak 3.1 listesinde görünür, varsayılan kapalı, kullanıcı açıkça seçer (karar 8 ile uyumlu).
- **Adaptör yolu** (3.2): ajan başına adaptör mü, Codex `app-server` + tek ACP (+ Claude Code'a özel ekler) mi?
- **Güncellemede çalışan iş** (1.6; kapandı: korunacak).
- **Onay ve `apply`'ın motordaki yeri** (kapandı: rakipler gibi, iş 1.7):
  - Rakiplerde onay ayrı bir kanal değildir. Cx'te sunucu istemciye istek yollar (`item/commandExecution/requestApproval`, `item/fileChange/requestApproval`), istemci `accept` / `acceptForSession` / `decline` / `cancel` ile yanıtlar; uygulama, IDE ya da telefon, bağlı hangi istemci olursa yanıtlayabilir. CC'de SDK'nın `canUseTool` geri çağrısı aynı işi yapar. AO'da ajanın isteği oturumu `waiting_input` yapar, masaüstü ya da mobil yanıtlar.
  - Rakiplerde `apply` diye bir komut yoktur: iş dalda durur, gerçek ağaca dal değiştirerek, "Hand off" ile ya da PR birleştirerek geçer.
  - Bizde onay ve uygulama `PRIVILEGED` komutlardır, ortak uçta hiç sunulmaz, yalnız kabuğun özel sürecindeki yerel pencereden verilir (ADR-004, ADR-030).
  - Karar (10 Kasım 2026): rakip yolu izlenir; ayrıntı 1.7.
- **Eklenti, hook, alt ajan (D2–D4):** ajan CLI'ından geçirmek mi, kendi katmanımız mı? Rakiplerde AO kendi katmanını yazmaz, ajanın hook'larını kullanır; Herdr yalnız terminal çalıştırır. Öneri: ajandan geçir.
- **Uzak ve mobil (E7):** baktığım orkestratörlerin neredeyse hepsinde var (AO, Herdr, Orca, MXterm, AgentSpace; CC "Remote Control", Cx "Remote connections"). Yerel öncelikle bağdaşan örnek AO'nunki: oturumlar başladığı makinede kalır, telefon yalnız istemcidir, LAN dinleyicisi isteğe bağlı ve kimlik doğrulamalıdır, ev dışı erişim ayrı bir tünelle. Bizde ADR-029 yalnız araştırma kararıdır (kullanıcı araştırması ve sızma testi yok).
- **İsim ve ticari marka kontrolü:** şimdilik gerek yok (10 Kasım 2026, kullanıcı); yayın öncesinde yeniden bakılır.

## 8. Rakiplerde olmayan, bizde olan (korunacak)

- **İmzalı kanıt ve onay sınırı:** yama, doğrulama geçmeden ve siz onaylamadan gerçek ağaca uygulanmaz. Okuduğum sayfalarda hiçbir rakip imzalı kanıt anlatmıyor; AO birleştirmeyi API'den yapar, CC'de "Merge when ready" var.
- **Telemetri yok:** AO kurulum kimliği ve GitHub kullanıcı adıyla kullanım telemetrisi toplar (PostHog); dsh'de `telemetry` ve `otel` paketleri var; CC ve Cx hesap ister.
- **Hesap yok, tamamen yerel:** CC ve Cx hesap ve bulut ister; AO ve Orca bulut seçeneği sunar.
- Kipi kullanıcının seçmesi fark değildir; rakiplerle aynıdır ("Yön kararı" tablosu). Sandbox konusu fark ya da eksik olarak ele alınmaz: yok ve eklenmeyecek ("Yön kararı").
