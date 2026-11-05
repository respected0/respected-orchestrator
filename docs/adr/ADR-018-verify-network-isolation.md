# ADR-018 — Verify ve kabul kodunun ağ izolasyonu

## Durum

Kabul edildi (5 Kasım 2026). Uygulandı (FIX-04, 5 Kasım 2026): `engine/sandbox.run_check`; karar ölçüme dayanır.

## Bağlam

Worker, AppContainer içinde ve ağ kapalı çalışır (ADR-007, SEC-03). Motorun kendi çalıştırdığı kabul ve proje
doğrulama komutları ise kısıtlı belirteçle (`engine/sandbox.py`) koşar. Bu belirteç motorun anahtarını ve kanıtını
korur ama ağı kapatmaz: `THREAT_MODEL.md` S-24 "Yok". Worker'ın bıraktığı kod verify sırasında veri sızdırabilir.

## Seçenekler

| Seçenek | Ağ sınırı | Yönetici gerekir mi | Karar |
|---|---|---|---|
| Kısıtlı belirteç (bugün) | Yok | Hayır | Tek başına yetersiz |
| Windows Güvenlik Duvarı / WFP kuralı | Süreç ya da SID başına | **Evet** | Reddedildi: ürün yönetici istemez (`PRODUCT_CONTRACT.md`) |
| Windows Sandbox VM | VM politikası | Evet (özellik), yavaş | Reddedildi |
| **Verify'ı worker'la aynı AppContainer yolundan, ağ kapalı çalıştırmak** | Varsayılan kapalı | Hayır | **Seçildi** |

## Ölçüm (5 Kasım 2026, yükseltilmemiş Windows 11, Python 3.13.15)

`docs/evidence/poc/fix04_verify_appcontainer_probe.py` her komutu önce sarmalamasız (kontrol), sonra üretimdeki
`default_policy` + `processes.execute` (AppContainer, `network_mode="deny"`) yolundan çalıştırır. Sonuç
`docs/evidence/poc/fix04_results.json`:

| Komut | Kontrol | AppContainer |
|---|---|---|
| `python -c`, `python -m unittest` | çalışır | **çalışır** |
| `git status`, `git rev-parse HEAD` | çalışır | **çalışır** |
| `node --version`, `cmd /c echo` | çalışır | **çalışır** |
| `npm.cmd test` | çalışır | **reddedilir**: `WorkerPolicyError: Shell shims are not executable workers` (politika kararı, AppContainer sınırı değil) |
| Dış IP (1.1.1.1:443) | bağlanır | **engellenir** (WinError 10013) |
| DNS (`example.com`) | çözülür | **engellenir** (`getaddrinfo failed`) |
| Yerel dinleyici (127.0.0.1) | bağlanır | **engellenir** (zaman aşımı) |
| Alt süreçten dış IP | bağlanır | **engellenir** |

Kullanıcı profilindeki Python (`AppData\Local\Programs\Python313`) ek ayar olmadan çalıştı; çünkü yorumlayıcı
dizini `default_policy` içinde salt-okunur verilir.

### Araç zinciri takip ölçümü

`docs/evidence/poc/fix04_toolchain_probe.py` → `fix04_toolchain_results.json` (yerel) ve
`docs/evidence/poc/fix01_hosted_followup.log` (hosted, geçici standart kullanıcı altında):

| Durum | Yerel | Hosted | Anlam |
|---|---|---|---|
| `sys.prefix` dışında venv, ek kök yok | rc=106, `pyvenv.cfg` bulunamadı (erişim engellendi) | aynı | Reddedilir, fail-closed |
| Aynı venv, kökü salt-okunur verilince | çalışır | çalışır | Operatör onayıyla çalışır |
| `node npm-cli.js test` (shim yerine) | rc=1, `EPERM lstat 'C:\\'` | rc=1 (aynı sınıf hata) | **Çalışmaz**: npm üst dizinleri `lstat` eder, sürücü kökü AppContainer'a kapalı |
| `node --version`, `node betik.js` | çalışır | çalışır | Düz node çalışır |
| `git status` (politika yorumlayıcıdan kuruldu) | çalışır | **rc=128**, `could not open '/dev/null'` | Hosted git görüntüsünde çalışmıyor |
| Politika `git.exe`/`node.exe` dizininden kuruldu (`default_policy` `command[0]` dizinini ekler) | `SandboxStartError: ACL grant failed` (Program Files) | aynı | Fail-closed; kod değişikliği gerekir |

Sonuncusu bir tasarım bulgusudur: `Program Files` altındaki araçlar AppContainer tarafından zaten okunabilir, ama
`default_policy` o dizini "verilecek kök" saydığı için DACL değiştirmeye çalışır ve yönetici olmadan başarısız olur.

## Karar

1. **Varsayılan kapalı ağ.** Windows'ta kabul ve proje verify komutları AppContainer yolundan (`appcontainer.spawn`,
   `network_mode="deny"`) çalışır. Kısıtlı belirteç AppContainer'ın içinde ayrıca gerekmez: AppContainer motorun
   anahtarına ve veri köküne izin verilmeyen yolları zaten reddeder (S-01..S-04 testleri yeniden koşturulur).
2. **Fail-closed.** AppContainer kurulamazsa (yükseltilmiş oturum, ACL hatası, bilinmeyen durum) güvenilmeyen verify
   **çalışmaz**; kısıtlı belirtece ya da sarmalamasız çalıştırmaya sessiz geri dönüş yoktur.
   `RESPECTED_ORCH_SANDBOX=off` bu yolda ağ garantisi vermez; verify için kabul edilmez.
3. **Ağ istisnası ya hep ya hiç.** AppContainer'ın `internetClient` yeteneği host bazında süzemez; host/port izin
   listesi yönetici gerektiren Güvenlik Duvarı olmadan işletim sistemi düzeyinde **uygulanamaz**. Bu yüzden istisna
   görev başına, insan onaylı ve yalnızca o görevin verify'ı içindir; tam ağ açılır, kanıt paketine yazılır
   (`network: allowed`, onay kimliği). "Yalnızca şu host'a" vaadi verilmez.
4. **Araç uyumu (ölçüme göre).**
   - Verify politikası **yorumlayıcıdan** kurulur; `Program Files` gibi sistem altındaki araçların dizini "verilecek
     kök" olarak eklenmez (zaten okunabilir). FIX-04, `default_policy`'nin bu durumda ACL denemesi yapmamasını
     (ya da dizinin AppContainer tarafından zaten okunabildiğini `icacls /findsid` ile görüp atlamasını) sağlar.
   - `.cmd`/`.bat` shim'leri reddedilmeye devam eder. `npm test` gibi npm betikleri **desteklenmez** (npm sürücü
     kökünü `lstat` eder, AppContainer'a kapalı); Node doğrulaması `node betik.js` biçiminde olmalıdır. Sürücü kökünü
     açmak bu kararın dışında tutuldu.
   - `sys.prefix` dışındaki venv/yorumlayıcı yalnızca operatörün onayladığı `extra_readonly_roots` ile çalışır;
     kullanıcı profili toptan açılmaz.
   - `git` AppContainer içinde hosted görüntüde çalışmaz (`/dev/null` açılamıyor); verify komutları `git`'e güvenemez.
     Motorun kendi `git` çağrıları sandbox dışında koşar ve etkilenmez. Yerelde çalışması garanti değildir, sürüme bağlıdır.
5. **S-24 kapanışı** yalnızca FIX-04 testleri geçtiğinde ve THREAT_MODEL §11'deki "Yok kalmalıdır" cümlesi
   güncellendiğinde yapılır.

## Sonuçlar

- Ağ gerektiren testler (paket indirme, canlı servis) varsayılan olarak başarısız olur; kullanıcı onaylı istisna şart.
- Verify'ın bağımlılığı olan araçların bir kısmı AppContainer'da çalışmaz (npm betikleri, hosted'da git, kök
  `lstat` isteyen araçlar). FIX-04 bunları listeleyen bir uyumluluk testi içerir; ölçülmeyen araç için "çalışır" denmez.
- Uygulama sonrası: verify ve kabul AppContainer'da, ağ kapalı koşar; kısıtlı belirteç yolu (`sandbox_exec`) kaldırıldı; S-24
  "Engellenir". Ağ istisnası: operatörün `RESPECTED_VERIFY_NETWORK_TASKS` ile görev kimliğini yazması.
- Ölçüm tek makinede ve yükseltilmemiş oturumda yapıldı; hosted CI ayrı sorudur (ADR-017).

## Araç zinciri ölçümü 2 (5 Kasım 2026, üretim yolu `sandbox.run_check`, ağ kapalı)

`docs/evidence/poc/fix04_toolchain2_probe.py` → `fix04_toolchain2_results.json`. Kontrol = sarmalamasız aynı komut.

| Araç | Kontrol | AppContainer | Sonuç |
|---|---|---|---|
| `python -m pip --version`, `pip list` | çalışır | çalışır | Desteklenir |
| `python -m compileall` | çalışır | çalışır | Desteklenir |
| `dotnet --version` | çalışır | çalışır | Desteklenir |
| `git --version` | çalışır | çalışır | Desteklenir (hosted'da `status` çalışmaz, bkz. yukarı) |
| `python -m venv v` | çalışır | **başarısız** (rc=1) | Desteklenmez: ağaç içinde venv oluşturma |
| `cargo --version` | çalışır | **başarısız** (rc=1, `.rustup` ana dizini yazılamaz) | Desteklenmez |
| `pytest`, `ruff`, `mypy` | kurulu değil (kontrol de rc=1) | — | **Ölçülemedi**: bu makinede kurulu değil; "çalışır" denmez |
| `gcc`, `go`, `tsc` | kurulu değil | — | **Ölçülemedi** |

Listede olmayan araç için "çalışır" denmez; yeni bir araç eklemek aynı betikle ölçmeyi gerektirir.

## Kaynaklar

- [Tehdit modeli](../THREAT_MODEL.md) S-24, §6, §11 (erişim: 2026-11-05).
- [SEC-02 karşılaştırması](../evidence/poc/SEC02_SANDBOX_COMPARISON.md); [ADR-007](ADR-007-provider-key-network-threat-model.md).
- `docs/evidence/poc/fix04_verify_appcontainer_probe.py`, `docs/evidence/poc/fix04_results.json`.
