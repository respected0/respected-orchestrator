# B3-09.03 — Güncelleme sırasında aktif iş: hata enjekteli koşu

Tarih: 7 Kasım 2026. Karar: `docs/adr/ADR-026-update-window.md`. Testler: `tests/engine/test_maintenance.py` (14), `tests/packaging/test_update_window_script.py` (6). Gerçek süreçler, gerçek `taskkill`, gerçek CLI; model çağrısı yok (`custom` işçi).

| # | Enjekte edilen durum | Gözlenen (gerçek) | Sonuç |
|---|---|---|---|
| 1 | Pencere açıkken 6 giriş yolu (yeni görev, başlatma, uygulama, proje başlat/devam, kampanya başlat) | hepsi "Güncelleme sürüyor; … şimdi kabul edilmiyor"; hiçbir koşu klasörü oluşmadı | yeni iş kabulü durur |
| 2 | Pencere 60 sn TTL, süre doldu | `expired`, hiçbir şey reddedilmez | kurucu çökse ürün kilitlenmez |
| 3 | Bozuk (imzasız) pencere işareti | `damaged`, ne kilitler ne açar | raporlanır |
| 4 | 5 sn'lik gerçek bir koşu çalışırken pencere açıldı | yeni görev reddedildi; `drain 0` çalışanı **listeledi, durdurmadı** (`remaining.runs=[run]`); `drain 60` bitişi bekledi; koşu `completed`, `check` → `verified`; pencere açıkken `apply` reddedildi, kapanınca `applied` | çalışan iş bitirilir, bozulmaz |
| 5 | Çalışan koşuya **sert öldürme** (`taskkill /F /T`, kurucunun zorla durdurması / güç kesintisi) | durum `interrupted`; `drain` boş; `apply` → "Unsuccessful or pending"; `applied.json` yok; proje dosyası değişmedi | belirsiz iş otomatik uygulanmaz |
| 6 | CLI: `maintenance begin` → `create` | çıkış 1, "Güncelleme sürüyor"; `end` sonrası `create` çıkış 0 | kurucunun kullandığı yüzey çalışır |
| 7 | CLI: 8 sn'lik koşu varken `maintenance drain --seconds 1` | çıkış **3**, `remaining.runs=[run]`; koşu sonra `completed` | `drain` hiç öldürmez |
| 8 | Kullanım hataları (6 biçim) | çıkış 2; geçerli sayı ama aralık dışı → çıkış 1 | çökme yok |
| 9 | Çalışan süpervizör başka motor sürümüyle (ya da sürüm kaydı yok) | `other_version` listesinde adlarıyla; aynı sürüm listelenmez | sürüm uyuşmazlığı görünür |
| 10 | `runs.active` (masaüstü) gerçek çalışan koşu ile | koşuyu gösterdi, bitince `{}` | **gerileme düzeltildi**: önceden hiçbir kod süpervizör talebi yazmadığı için hep boştu |
| 11 | Pencereden önce kabul edilmiş süreç (`admit`) | sonraki adımlarını (yeni görev yaratma) sürdürebilir | çalışan proje güncellemeyle bozulmaz |

- Kurucu betiği (`orchestrator_setup.iss`): `PrepareToInstall` → `maintenance begin`, `drain --seconds 120`; çıkış 3 ise sessiz güncelleme **ertelenir** (hiçbir şey değişmez), etkileşimli güncelleme sorar (varsayılan Hayır); komutu olmayan eski sürüm önceki davranışı korur; pencere güncelleme sonrası, geri alma sonrası ve yedek alınamadığında kapanır. ISCC ile **derlendi** (başarılı); statik testler akışı sabitler. **Çalıştırılmadı.**
- Mutasyon: `create`/`apply` koruması kaldırılınca, süre sonu yok sayılınca, `admit` yok sayılınca, sürüm raporu kaldırılınca ilgili test kırıldı (5/5). "Canlılığı yalnızca `running` dalıyla ölçme" mutantı tek başına hayatta kaldı, çünkü aynı koşuyu `queued`+canlı başlatıcı dalı da yakalar (katmanlı).
- Sınırlar: (1) gerçek kurucu çalıştırılmadı, kısmi kurulum / güç kesintisi sırasında dosya kopyalama ve rollback (mevcut Inno + `robocopy` yedeği) bu kartta yeniden sınanmadı. (2) Pencere kurucuya güvenir; çağırmazsa eski davranış (zorla durdurma → `interrupted`) geçerlidir. (3) Canlılık taraması en yeni 500 koşu klasörüne bakar. (4) Öldürülen işin ardında bir süre dosya tutan süreç olabilir (test temizliği bunu bekler); işçiler ağaçla birlikte ölür (ölçüldü).
