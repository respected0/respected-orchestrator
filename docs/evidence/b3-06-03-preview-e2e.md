# B3-06.03 — Yerel önizleme: gerçek pencere güvenlik koşusu

- Tarih: 7 Kasım 2026. Uygulama: `desktop/src-tauri/target/release/respected-orchestrator-desktop.exe` (SHA-256 `3b7f27f9809cc9a7174b8aeca27751c8d2f45b5e393cca9e0a7aae32366645aa`), motor: taze paketli `dist/RespectedOrchestrator` (ayar alanlarıyla).
- Yöntem: `tests/desktop/preview_e2e.ps1` gerçek WebView2 penceresini UI Automation ile sürer (Ayarlar → adres → "Önizlemeyi aç"); `tests/desktop/preview_hostile_server.py` 127.0.0.1'de düşman bir sayfa sunar ve izin listesinde olmayan ikinci bir loopback portu dinler. Önizleme ayarları motorun `settings.json` dosyasından okunur (`preview_enabled`, `preview_ports`).

## Senaryolar (gerçek pencere)

| # | Ayar | Adres | Kabuğun yanıtı | Sunucuya gelen istek |
|---|---|---|---|---|
| 1 | açık | `http://127.0.0.1:47731/` | Açıldı | GET, GET, other-port-request, other-port-request, POST |
| 2 | KAPALI (varsayılan) | `http://127.0.0.1:47731/` | Yerel önizleme kapalı | yok |
| 3 | açık | `http://localhost:47731/` | Yalnızca 127.0.0.1 ve [::1] açılabilir | yok |
| 4 | açık | `http://127.0.0.1:47799/` | 47799 portu izin listesinde yok | yok |
| 5 | açık | `https://127.0.0.1:47731/` | Yalnızca http:// yerel adresleri açılabilir | yok |
| 6 | açık | `http://user:pw@127.0.0.1:47731/` | Adreste kullanıcı adı veya parola olamaz | yok |

## Senaryo 1: düşman sayfanın içeriden yaptıkları (sayfanın kendi raporu)

| Deneme | Sonuç |
|---|---|
| has __TAURI_INTERNALS__ | true |
| invoke engine_status | blocked: Command engine_status not allowed by ACL |
| invoke confirm_close | blocked: Command confirm_close not allowed by ACL |
| invoke request_apply | blocked: Command request_apply not allowed by ACL |
| invoke capability_inventory | blocked: Command capability_inventory not allowed by ACL |
| invoke preview_open | blocked: Command preview_open not allowed by ACL |
| invoke plugin:event|listen | blocked: Command plugin:event|listen not allowed by ACL |
| invoke plugin:window|close | blocked: Command plugin:window|close not allowed by ACL |
| invoke plugin:webview|create_webview_window | blocked: Command plugin:webview|create_webview_window not allowed by ACL |
| window.ipc.postMessage | ALLOWED: undefined |
| chrome.webview.postMessage | ALLOWED: undefined |
| read app localStorage key | blocked: empty (not shared) |
| document.cookie of the app origin | blocked: no cookies |
| fetch other loopback port | ALLOWED: opaque |
| fetch internet | ALLOWED: opaque |
| fetch app origin | ALLOWED: opaque |
| window.open another origin | blocked: popup refused |
| top navigation to another port | ALLOWED: asked |
| final origin after the navigation attempt | http://127.0.0.1:47731 |

## Yorum

- **IPC:** 8 komut denemesinin (4 kabuk komutu, `request_apply`, `preview_open`, 3 eklenti komutu) hepsi gerçek WebView2'de `not allowed by ACL`. Sayfa `__TAURI_INTERNALS__` köprüsünü görür (her Tauri penceresinde bulunur) ama hiçbir komut çalışmaz. `window.ipc` / `chrome.webview.postMessage` ham köprüleri de vardır; Tauri'de tüm taşıyıcılar aynı iletişim işleyicisine ve ACL denetimine çıkar; `tests/acl.rs` bu işleyiciyi (iddia edilen yerel köken dahil) reddettirir. Gerçek pencerede ise ham `postMessage` ile gerçek bir komut gönderilmedi (yalnızca `{}` gönderildi), bu yüzden bu yol ayrıca doğrulanmış sayılmaz.
- **Depolama/çerez:** uygulamanın `localStorage` anahtarı ve çerezleri sayfaya görünmez (gizli mod profili).
- **Gezinme:** başka porta gezinme **tamamlanmadı**: önizleme penceresi düşman sayfada kaldı (UIA metni: `hostile page finished…`). Korumayı kapatan mutantta aynı deneme pencereyi `127.0.0.1:47732/stolen` sayfasına taşıdı → koruma gerçekten `on_navigation` kuralından geliyor. Açılır pencere (`window.open`) reddedildi.
- **Sınır (bilinçli ve arayüzde yazılı):** sayfa, sıradan bir tarayıcı sekmesi gibi ağ isteği yapabilir: `fetch` ile başka loopback portuna ve internete (opak yanıt) ulaştı; reddedilen gezinmenin isteği de ikinci porta ulaştı (sayfa yüklenmedi). Bunu WebView düzeyinde engelleyemiyoruz; bu yüzden metin "yalnızca güvendiğiniz sayfaları açın" der. İzin verilen proje dışına dosya erişimi yoktur (yalnız `http://127.0.0.1:<izinli port>`), `file:` ve diğer şemalar reddedilir.
- **Kapalıyken:** varsayılan kapalı (senaryo 2): komut reddedilir, pencere açılmaz, sunucuya hiç istek gitmez; motor/uygulama normal çalışır (ana pencere ve motor rozeti sağlıklı). Görev akışı koduna dokunulmadı; önizleme yalnızca `preview_open` komutu çağrıldığında devreye girer.
