# ADR-035: Ajanın kendi terminal arayüzü

## Durum

Kabul edildi (10 Kasım 2026, kullanıcı; aşağıdaki üç karar önerildiği gibi onaylandı). **Motor tarafı uygulandı; masaüstü bölmesi ve sohbet ↔ terminal geçişi yapılmadı.** KALAN_ISLER 3.4, yön kararı 2 ve karar 11'in tasarım notudur. Kod: `engine/conpty.py`, `engine/pty_host.py`, `engine/terminals.py`, `engine/daemon.py` (`accept_loop`, `_relay`); test: `tests/engine/test_terminals.py`.

## Bağlam

Sohbet yalnız `opencode` ile ve yalnız yapılandırılmış akışla çalışıyor. Normalleştirmediğimiz her şey (ajanın kendi komutları, giriş, kip seçimi, diğer ajanlar) için kullanıcının uygulamadan çıkıp ayrı bir terminal açması gerekiyor. Masaüstündeki terminal bölmesi yalnız düz metin satırı çizer (`terminal.ts` kaçış dizilerini siler), yani bir ajanın tam ekran arayüzünü gösteremez.

## Orchestrator.inc nasıl yapmış

Kaynak: AO deposu `main`, 10 Kasım 2026'da okundu (`backend/internal/terminal/doc.go`, `protocol.go`, `adapters/runtime/conpty/proto.go`, `host.go`, `ring.go`, `ptyregistry/registry.go`, `cli/ptyhost.go`, `ports/terminal_surface.go`, `domain/session_interface_transition.go`, `frontend/package.json`). Ürün çalıştırılmadı.

- **Oturum başına ayrı, kopuk bir süreç** (`ao pty-host`, gizli alt komut) PTY'nin sahibidir (Windows'ta ConPTY). Arka plan süreci ve arayüz kapansa da yaşar.
- Bu süreç bir **yerel bağlantı noktasında** ikili çerçevelerle konuşur (`[tür][uzunluk][gövde]`): çıktı, girdi, yeniden boyutlandırma, durum, öldürme. Son 1000 satırı tutar ve yeni bağlanana yeniden oynatır. Program çıkınca süreç kapanmaz, durumu bildirir.
- Canlı sürecin kaydı diskte bir dosyadadır; oturum kaydı kaybolsa da bulunup kapatılabilir.
- Arka plan süreci baytları WebSocket'e köprüler (base64); **ham terminal baytları değişiklik akışına (CDC) girmez**. PTY'nin boyutunu birincil istemci belirler.
- Arayüz **xterm.js**'tir (`@xterm/xterm`).
- Sohbet ↔ terminal geçişi kalıcı aşamaları olan bir işlemdir (kaynak arayüz boşalana kadar bekle ya da kes, durdur, hedefi aynı ajan oturumuyla başlat). Ajanın durumunu hook olaylarından ve ajan arayüzünün ekranını yorumlayarak okur.

## Karar

1. **Terminal sunucusu ayrı süreçtir.** `rorch _pty-host` (gizli; `context.engine_command` ile başlar, `winproc` üzerinden kopuk). ConPTY'yi açar, ajanı içinde çalıştırır, son 1000 satırı tutar, program çıkınca yaşamaya devam eder. Motor kapansa ya da yeniden başlasa da çalışır; bu 1.6'nın (güncellemede işin korunması) ilk parçasıdır.
2. **Bağlantı noktası yok, adlandırılmış boru var** (AO'dan fark; ADR-030 "port yok" kuralı). Terminal sunucusu yalnız geçerli kullanıcıya açık kendi borusunu açar ve **yalnız kalıcı motoru kabul eder**. Böylece bir işçi süreci kullanıcının terminaline yazamaz; kimin bağlandığına tek yerde, motorda karar verilir.
3. **Motor komutları (katalogda):** `terminal.start {project_id, project_root, agent, cols, rows}`, `terminal.list`, `terminal.input {terminal_id, data}`, `terminal.resize`, `terminal.kill`, ve `terminal.attach {terminal_id}`. `terminal.attach` ADR-034'teki gibi bağlantıyı tek yönlü akışa çevirir: önce saklanan satırlar, sonra canlı çıktı (base64). Girdi olağan komutla gider. Ham baytlar `events.subscribe` akışına girmez; oraya yalnız `terminal.state` (başladı, çıktı) girer.
4. **Yetki:** `terminal.start|input|resize|kill|attach` yeni `TERMINAL` yetki sınıfındadır: yalnız tanınan masaüstü (`RENDERER`) ve insan kökeni; `MCP` kökeni yalnız `terminal.list` görür, `CHILD` hiçbirini. Boruya bağlanan `rorch` komutu MCP düzeyinde sayıldığı için (KALAN_ISLER 1.1 d) CLI'da bugün yalnız `rorch terminal list` vardır. Gerekçe: terminale yazmak, kullanıcı adına komut çalıştırmaktır.
5. **Canlı terminallerin kaydı** veri kökünde `state/terminals.json` (kimlik, süreç, boru adı, klasör, ajan). Motor açılırken okur, ölü kayıtları siler, yaşayanlara yeniden bağlanır.
6. **Masaüstü:** xterm.js ile gerçek terminal bölmesi. Kabuk `terminal.attach` akışını kendi bağlantısında açar ve baytları yalnız `main` penceresine iletir (`engine_subscribe` ile aynı kalıp). Var olan düz metin bölmesi (`terminal.ts`, `TerminalPane.tsx`) sohbet dökümü için kalır.
7. **`agent.describe`:** `interfaces.terminal`, ajanın çalıştırılabilir programı bulunduğunda `native` olur. Durum (çalışıyor / sizi bekliyor) ajanın kendi hook'undan gelir; hook yoksa "bilinmiyor". Ekran kazıma yok (AO'dan fark; KALAN_ISLER 3.4'teki karar).
8. **Sohbet ↔ terminal geçişi ikinci dilimdir.** Yalnız oturum boştayken: kaynak durdurulur, hedef aynı ajan oturum kimliğiyle başlatılır (`opencode --session ses_…`). AO'nun "çalışan turu bekle ya da kes" seçenekleri ve kalıcı aşamaları sonraya kalır.

## Verilen üç karar (10 Kasım 2026, kullanıcı: önerildiği gibi)

1. **xterm.js bağımlılığı** (`@xterm/xterm` ve `@xterm/addon-fit`, MIT). Masaüstüne giren ilk çalışma zamanı bağımlılığı olur (bugün yalnız React ve Tauri var). Öneri: evet; ajan arayüzünü çizmenin başka makul yolu yok ve AO da bunu kullanıyor.
2. **Terminaldeki ajan gerçek ağaçta, kendi izin kipiyle çalışır.** Sohbette dosya değiştiren ve komut çalıştıran araçlar bugün kapalı; terminalde ajan kendi arayüzünde kendi kurallarıyla sorar ve proje klasöründe doğrudan düzenler. Bu, 8 Kasım izin kipi kararı ve "sandbox yok" kararıyla uyumlu, ama ekranda ilk kez gerçek ağaca yazan bir yol açılır. Öneri: evet, ajanın varsayılan kipiyle; kip seçimi 4.6'da.
3. **İlk dilimin kapsamı.** Öneri: terminal sunucusu + motor komutları + `rorch terminal` + masaüstü bölmesi + "bu klasörde ajan terminali aç". Sohbet ↔ terminal geçişi (madde 8) ayrı commit.

## Sonuçlar ve yapılmayacaklar (ilk dilimde)

- Unix (`forkpty`): 1.4 ile birlikte.
- Telefondan izleme ve ikincil istemci boyutlandırması.
- Genel kabuk terminali (AO'da "shell terminal" ayrı bir özelliktir); yalnız ajan başlatılır.
- Çalışan tur varken geçiş, geçiş geçmişi kaydı.

## Uygulamada netleşenler

- ConPTY `ctypes` ile açılır; yeni Python bağımlılığı yoktur. Programın standart tutamaçları boş verilir, yoksa motorun yönlendirilmiş tutamaçlarını alır.
- Terminal sunucusu ile motor arasındaki biçim satır başına bir JSON'dur (AO'daki ikili çerçeve yerine): `{"op": "attach"}` bağlantıyı tek yönlü yapar (`{"data"}`, `{"exit"}`, iki saniyede bir `{"ping"}`); `input`, `resize`, `status`, `kill` tek satırlık yanıt alır.
- Sunucu, bağlananın sürecini motorun kendi borusundan sorduğu süreç numarasıyla karşılaştırır; başka süreç yanıt alamaz.
- Çıktının son 256 KB'ı ham olarak saklanır (AO'daki gibi çizilmiş ekran değil); yeni bağlanan bunu alır ve boyut yollayınca tam ekran program kendini yeniden çizer.
- Program bitince sunucu, son izleyici ayrıldıktan 30 saniye sonra kapanır; `terminal.kill` hemen kapatır.
- Motor akışı istemciye `terminal.data` / `terminal.exit` / `terminal.ping` bildirimleri olarak geçirir; `events.subscribe` akışına yalnız `terminal.state` girer.

## Doğrulama planı

Sahte bir program (`python -c`) ConPTY içinde çalıştırılır: çıktı akışı, girdi, yeniden boyutlandırma, yeniden bağlanınca son satırlar, motor yeniden başlayınca terminalin yaşaması, işçi soyundan gelen bağlantının reddi. Gerçek ajan arayüzü (`opencode`) token harcamadan açılabildiği ölçüde elle; gerçek uygulamada görülmesi size kalır.

## Kaynaklar

- Orchestrator.inc deposu, `main` dalı: https://github.com/OrchestratorInc/agent-orchestrator (erişim: 2026-11-10). Okunan dosyalar yukarıda sayıldı.
- `desktop/src/terminal.ts`, `engine/agent_describe.py`, `docs/KALAN_ISLER.md` 3.4 (erişim: 2026-11-10).
