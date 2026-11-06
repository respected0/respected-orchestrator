# B3-09.01 — Desktop+engine paket sözleşmesi: paketleme smoke ve manifest denetimi

- Tarih: 7 Kasım 2026. Strateji: `docs/adr/ADR-025-desktop-engine-package.md` (tek kurucu, tek klasör, tek karma zinciri).
- Paket: `dist/RespectedOrchestrator` (taze PyInstaller, motor 0.1.0b2) kopyalanıp `build_dist.py --no-freeze --desktop <exe>` ile masaüstü kabuğu eklendi. Kabuk SHA-256 `dc583babbd35c75b6a0bf5d59c898b6ce0200a3cb92f71bad96016e102d8d287`, motor başlatıcısı `4a0679164f86a2794789657dbc5d5bef4c55f81ebeecf478f6d840c1968221b1`. `distribution.json`: 128 dosya, `launcher` ve `desktop` adlandırılmış, kökte yalnız iki exe; `build_dist.py --audit` → `problems: []`.
- Yöntem: kurucunun `[Files]` bölümü `StageDir\*` → `{app}` kopyalar; bu kare klasör temiz bir kullanıcı kurulumu olarak birebir simüle edildi. `LOCALAPPDATA` boş bir klasöre yönlendirildi ve `RESPECTED_APP_DIR` kaldırıldı (gerçek kuruluma erişilemez), `RESPECTED_DATA_DIR` geçici (gerçek veriye dokunulmaz). Gerçek pencere `tests/packaging/desktop_smoke.ps1` ile UI Automation üzerinden okundu (motor rozeti + hata metni).

| # | Senaryo | Sonuç (gerçek pencere) | Denetim |
|---|---|---|---|
| A | Temiz kurulum klasörü, Hub yok | rozet `Motor 0.1.0b2`, hata yok | `problems: []` |
| B | Başlatıcıya 1 bayt eklendi (kurcalama) | `Motor yok` + "Motora bağlanılamadı (BrokenInstall)" + ipucu "Respected Orchestrator kurucusunu yeniden çalıştırın (Onar)."; motor **başlatılmadı** | `hash mismatch: respected-orchestrator.exe` |
| C | `app\` çalışma zamanı klasörü yok (başlatıcı sağlam) | `Motor yok` + "(Disconnected)" | eksik dosyalar adlarıyla |
| D | Onarım (çalışma zamanı geri kondu) | rozet `Motor 0.1.0b2` | `problems: []` |
| E | Kabuk motorsuz boş klasörde | `Motor yok` + "(NotInstalled)" | — |
| F | `distribution.json` yok | `Motor yok` + "(BrokenInstall)" (kurulu klasörde bildirim zorunlu) | `distribution.json is missing or unreadable` |
| G | Temiz hale dönüş | `Motor 0.1.0b2` | `problems: []` |

- Motor `health` (RPP) aynı kopyadan (ağaç karması kanıtı değil, yalnız motorun ayakta olduğu): `status: healthy`, sürüm 0.1.0b2.
- Kurucu **kurulmadan derlendi** (ISCC → geçici klasör): kabukla `RespectedOrchestrator-Windows-Setup.exe` 16,5 MB, kabuksuz da derleniyor (kısayol bölümü `#ifexist` ile yalnız kabuk paketteyse eklenir).
- Sınırlar: (1) **gerçek kurucu bu makinede çalıştırılmadı**: aynı `AppId` kullanıcının gerçek kurulum kaydını, ve kurucu Hub kurulum adımını etkileyebilir; kurulum yerine kurucunun kopyaladığı klasör simüle edildi. (2) Kabuğun kendi karması çalışırken doğrulanmaz (çalışan program kendini doğrulayamaz); kabuğu kurucu ve Hub/`_distribution` zinciri doğrular. (3) Başlatıcı dışındaki dosyaların karması kabukta açılışta kontrol edilmez; motorun `setup`/`repair` komutları ve `manifest.install_state` tüm ağacı doğrular. (4) Başlangıç menüsü kısayolunun gerçek kurulumda oluştuğu doğrulanmadı (yalnız betik derlendi). (5) Authenticode imzası B3-09.04'ün konusudur; bu pakette imza yok.
