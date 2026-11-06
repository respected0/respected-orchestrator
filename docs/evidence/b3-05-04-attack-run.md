# B3-05.04 — Onay merkezi saldırı koşusu raporu

- Tarih: 6 Kasım 2026. Test edilen commit: `9bf5935271d4753509de9045846a4c53b893df92` (kod `4709ab1` ile aynı; sonrasında yalnız saldırı testi dosyası eklendi).
- Paketli exe: `dist/RespectedOrchestrator/respected-orchestrator.exe`, SHA-256 `d7a3cd840c7a79b3fc1b67deb0d9eee7e629164c56d6dbcedadb6e6077c396b7`, `packaging/build_dist.py` ile 22:32'de derlendi (`approval.open` yalnız bu derlemede vardır).
- Yöntem: `tests/engine/test_approval_attacks.py`, her bağlantı ayrı süreç ve ayrı oturum tokenı (`_ipc` = renderer, `_ipc --human` = native presence), gerçek stdio; `RESPECTED_ATTACK_EXE` ile aynı paket exe'ye yöneltilir.
- Sonuç: kaynak (python -m) 19/19 OK, paketli exe 19/19 OK. Her saldırıda reddedilme **ve** projenin (HEAD + indeks + durum + dosya baytı) birebir aynı kalması denetlenir.

| # | Saldırı | Beklenen |
|---|---|---|
| 01 | renderer connection cannot decide | reddedildi, proje değişmedi |
| 02 | renderer connection cannot apply even with a stolen token | reddedildi, proje değişmedi |
| 03 | orchestrated process cannot pose as the human | reddedildi, proje değişmedi |
| 04 | wrong or missing session token is unauthenticated | reddedildi, proje değişmedi |
| 05 | human connection exposes nothing beyond approval | reddedildi, proje değişmedi |
| 06 | wrong run id gets no challenge | reddedildi, proje değişmedi |
| 07 | patch swapped after the challenge is refused at decision time | reddedildi, proje değişmedi |
| 08 | forged signed patch outside the grant never gets a challenge | reddedildi, proje değişmedi |
| 09 | request id reuse with a different payload is a conflict | reddedildi, proje değişmedi |
| 10 | replayed decision changes nothing a second time | reddedildi, proje değişmedi |
| 11 | replayed token cannot apply twice | reddedildi, proje değişmedi |
| 12 | forged and malformed tokens and ids are rejected | reddedildi, proje değişmedi |
| 13 | binding of another challenge is a wrong window | reddedildi, proje değişmedi |
| 14 | token for one run cannot apply another | reddedildi, proje değişmedi |
| 15 | oversized and garbage requests are refused cleanly | reddedildi, proje değişmedi |
| 16 | denial applies nothing and cannot be flipped | reddedildi, proje değişmedi |
| 17 | crash between decision and apply never auto applies | reddedildi, proje değişmedi |
| 18 | the legitimate path applies once and nothing secret is left behind | kabul: meşru yol, tam bir kez uygulandı; ikinci uygulama reddedildi |
| 19 | token burned by a failed apply cannot be replayed after the attacker restores the state | reddedildi, proje değişmedi |

- Mutasyon (aynı suite ile): renderer'a PRIVILEGED yetkisi verildi → test 01 ve 02 kırıldı; binding kontrolü kaldırıldı → test 13 kırıldı; `.used` token talebi kaldırıldı → test 19 kırıldı (yama, repo eski haline getirilince token tekrar kullanılarak **gerçekten uygulandı**); kaynak her seferinde aynen geri yüklendi.
- Günlük/sır taraması (test 18): veri kökündeki hiçbir dosyada onay tokenı veya iki oturum tokenı yok; asker bağlantısı tokenı hiç görmez; her iki süreçte stderr boş.
- Sınır: gerçek bir insanın tıkladığı native `MessageBoxW` bu koşuya dahil değil (sahte Presence ile Rust testinde); oturum müdahale saldırıları (terminal input injection, spoofed approval) B3-03.04'e bağlıdır ve henüz kapsanmadı.
