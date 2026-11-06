# ADR-024 — ConPTY + AppContainer: interaktif oturum go/no-go

## Durum

Kabul edildi (6 Kasım 2026). Görev: B3-03.02. Karar: **GO, koşullu** — yalnızca aşağıdaki sınırlarla; koşullar sağlanmadan PTY modu açılmaz.

## Bağlam

Beta.3 etkileşimli ajan oturumları (Chat'in yanında terminal) ister. Worker sınırı AppContainer'dır ve sessizce korumasız süreç açmak yasaktır (ADR-008, ROADMAP §4.1). Soru: gerçek bir ConPTY (sahte konsol) ile bağlı süreç, aynı AppContainer içinde aynı negatif garantilerle çalışabilir mi?

Deney: `tests/engine/conpty_experiment.py` (yalnız test; `engine.appcontainer.spawn` ile aynı profil, aynı ACL verme, aynı yetenek kuralı; yalnızca `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` eklendi). Kapı testleri: `tests/engine/test_conpty_feasibility.py`.

## Karar

1. ConPTY, AppContainer içindeki süreçle çalışır (gerçek tty, `isatty` doğru, boyut doğru). Aşağıdaki **ölçülen** davranışlar desteklenen moddur:
   - Dış dosya okuma/yazma reddedilir; çalışma kökü içi yazma çalışır.
   - Ağ varsayılan kapalıdır (loopback sunucuya bağlanılamaz, sunucu bağlantı görmez).
   - Çocuk (torun) süreç de aynı kum havuzundadır.
   - Boyut değişikliği (`ResizePseudoConsole`) çocuğa ulaşır; 1 MiB çıktı kilitlenmeden gelir; broker'ın yazdığı girdi çocuğa ulaşır.
2. **Bulgu (zorunlu koşul): std handle sızıntısı.** `STARTF_USESTDHANDLES` olmadan, üst sürecin stdout/stderr'i yönlendirilmişse (boru/dosya) AppContainer çocuğu çıktısını **PTY yerine üst sürecin stdout'una** yazdı. `STARTF_USESTDHANDLES` ile üç handle'ı `NULL` vermek bunu kapatır; PTY tek kanal olur (`test_real_tty_and_only_channel_is_the_pty`). Üretim broker'ı bunu **her zaman** uygulamalıdır.
3. **Bulgu: Ctrl-C sinyali AppContainer içinde iletilmiyor.** PTY'ye `0x03` yazmak, "cooked" (işlenmiş girdi) modundaki bir çocuğa `SIGINT`/`CTRL_C_EVENT` üretmez (20 sn boyunca görülmedi). Ham modda çalışan programlar (ajan TUI'leri) `0x03`'ü girdi olarak okur ve çalışır. **Karar:** "interrupt" = ham modlu ajana `0x03` baytı + diğer her durumda **sert durdurma** (süreç/Job sonlandırma). Sinyal tabanlı kesme vaat edilmez. Sinyal teslimi bir Windows sürümünde çalışmaya başlarsa test bunu fark ettirir (`test_ctrl_c_signal_is_not_delivered…` düşer) ve bu ADR güncellenir. Neden bu sınırın AppContainer'a mı ConPTY'ye mi bağlı olduğu ayrıştırılmadı.
4. Terminal kaçış dizileri (OSC başlık, SGR, imleç) **ham olarak** PTY akışında gelir. Renderer'a giden akışı broker süzer (B3-03.05); ham akış asla doğrudan görüntülenmez.
5. **Asla korumasız yedek yok:** PTY başlatma herhangi bir adımda başarısız olursa istisna fırlatılır; çalışan süreç yoktur. Yükseltilmiş oturumda `unsupported_elevated`.

## Sonuçlar

- Deney kodu henüz üretim yolunda değildir ve `engine/agent_adapters.py` matrisinde `pty` **`unsupported`** kalır. Üretim broker'ı (B3-03.04/05) bu ADR'nin 2–5. maddelerini koruyarak `appcontainer.spawn` içine/yanına taşınır ve matrisin `pty` durumu ancak o zaman `verified` olur.
- Kanıtlanmamış kalanlar: ağın **açık** (internetClient) olduğu PTY modu denenmedi (loopback AppContainer'da ayrıca engellidir; pozitif kontrol yapılamadı); gerçek ajan CLI'sinin (codex/claude/…) PTY içinde çalışması denenmedi; Job Object ile PTY birlikte denenmedi (çocuğun Job'a atanması kodda var ama test edilmedi).
- Kapsam dışı: POSIX (worker yalnız Windows'ta başlar).

## Kaynaklar

- Microsoft, "Pseudoconsole functions" — CreatePseudoConsole, ResizePseudoConsole (erişim: 2026-11-06).
- `tests/engine/test_conpty_feasibility.py` (10 test), `docs/evidence/KANIT_LOG.md` B3-03.02.
