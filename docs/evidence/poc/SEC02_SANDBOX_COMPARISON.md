# SEC-02 — Windows worker sandbox teknoloji doğrulaması

Tarih: 30 Ekim 2026. Makine: Windows 11 (10.0.26300), normal kullanıcı, Python 3.13.15.

## Seçenekler

| Seçenek | Dosya sınırı | Ağ sınırı | Alt süreç | Otomasyon | Karar |
|---|---|---|---|---|---|
| Normal süreç (bugün) | Yok | Yok | Aynı kullanıcı | Kolay | Reddedildi; SEC-01 5/5 izin verdi |
| Kısıtlı belirteç | Ayrı güvenlik sınırı değil; aynı kullanıcı ACL'leri geçerli | Yok | Miras alınır | Orta | Reddedildi; dosya/ağ sınırı ölçülemez |
| AppContainer, yetenek yok | ACL verilmeyen yollar reddedilir | Varsayılan kapalı | Token miras alınır | Orta; Win32 başlatıcı | **Seçildi ve ölçüldü** |
| Windows Sandbox VM | VM içinde | VM politikası | VM içinde | Yavaş, yönetici/özellik bağımlı | Şimdilik ertelendi; `WindowsSandbox.exe` var, özellik durumu yönetici gerektirdiği için doğrulanamadı |

Kısıtlı belirteç, kullanıcının kendi dosyalarına erişimini kaldırmaz; bu nedenle "sandbox" olarak sayılmadı. AppContainer'ın dosya sınırı, container SID'ine verilen açık ACL'lere dayanır: çalışma alanı yazılabilir, Python dizini salt okunur, diğer kullanıcı yolları kapalı.

## Ölçüm

Komut:

```
python docs/evidence/poc/sec02_probe.py docs/evidence/poc/sec02_results.json
```

Üç bağımsız çalıştırmada, yetenek SID'i olmayan AppContainer içinde:

| Ölçüm | Sonuç |
|---|---|
| Yasak: dış dosya okuma, dış dosya yazma, `.engine-key` okuma, TCP 1.1.1.1:443, dış dosya silme | 15/15 engellendi |
| İzinli çalışma alanı yazma + geri okuma | 9/9 başarılı |
| Alt süreç (3 torun) politika mirası: dış yazma engelli + iç yazma başarılı | 9/9 |
| Ağ ön koşulu: sandbox dışından 1.1.1.1:443 | Bağlandı |
| Codex CLI (`codex.exe --version`) AppContainer içinde | Başladı, çıkış 0; "Could not find home directory" uyarısı |
| Olmayan CLI | `CreateProcess` hata 2; sessiz geniş yetkili fallback yok |
| Windows Sandbox ikilisi | Var; özellik durumu yönetici gerektirdiği için test edilmedi |

Codex'in 0 çıkışı yalnızca başlatma uyumunu gösterir; oturum açma, gerçek görev ve `.codex` yapılandırması bu prototipte sınanmadı. Ana dizin verilmediği için uyarı çıkması beklenen ve kabul edilen sonuçtur.

## Sınırlar

- AppContainer ortam değişkenlerini kendiliğinden temizlemez; sır ayıklama ve izin politikası SEC-03'ün işi.
- ACL'ler prototipte `icacls` ile verilir ve her çalıştırmadan sonra geri alınır. Üretimde tek launcher bunu yönetmeli.
- AppContainer, izin verilen dizin içindeki her çalıştırılabilir dosyayı ayırt etmez; çalıştırılabilir beyaz liste SEC-03'te gelecek.
- Windows Sandbox VM'i, her görev için dosya paylaşımı ve başlangıç maliyeti nedeniyle ilk sürüm için uygun değil.

Makine okunur sonuç: `docs/evidence/poc/sec02_results.json`.
