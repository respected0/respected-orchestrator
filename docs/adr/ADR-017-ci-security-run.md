# ADR-017 — CI güvenlik koşusu: yükseltilmemiş ortam ve sıfır skip

## Durum

Kabul edildi (5 Kasım 2026). Uygulama FIX-01 ile yapılır; karar GitHub Actions üzerinde yapılan gerçek ölçüme dayanır.

## Bağlam

AppContainer sınırı yükseltilmiş oturumu reddeder (`unsupported_elevated`, SEC-03, S-19). GitHub'ın hosted Windows
runner'ı yükseltilmiş çalıştığı için `ci.yml` üç adımda `ORCH_ALLOW_ELEVATED_SKIP=1` kullanır ve `tests/elevated_ci_skips.txt`
içindeki 109 test atlanır; CI sandbox'ı hiç ölçmeden yeşil olabilir. `test_security_gate.py` yalnızca `ci.yml`
metnine bakar.

## Ölçüm (public depoda geçici `probe/fix01-elevation` dalı; Actions ücretsiz; dal sonra silindi)

Kanıt: `docs/evidence/poc/fix01_hosted_probe.log`, betik `docs/evidence/poc/fix01_deelevate_probe.py`.

| Deneme (windows-latest, Server 2025) | Sonuç |
|---|---|
| Runner'ın kendi belirteci | `TokenElevation=1`, integrity High, Administrators etkin: yükseltilmiş |
| Aynı belirteçten türetilmiş kısıtlı çocuk (Administrators deny-only, ayrıcalıklar atıldı, Medium integrity) | **`TokenElevation` yine 1**; motor `_is_elevated()` True der, 12 test `unsupported_elevated` ile ERROR. **Çalışmaz.** |
| Runner'ın oluşturduğu geçici **standart yerel kullanıcı** (`New-LocalUser`, Administrators üyesi değil) altında süreç | `TokenElevation=0`, `_is_elevated()` False |
| Aynı kullanıcıyla AppContainer matrisi (`test_worker_security` + `RealSandboxTests`) | 13 test: **12 geçti, 1 skip, 0 hata**. Skip, kurulu olmayan Cursor CLI'ya bağlı `test_node_worker_can_start_piped_children_and_resolve_paths` |
| Aynı kullanıcıyla verify probe (ADR-018) | Python, unittest, node, cmd çalıştı; IP/DNS/loopback/alt süreç ağı engellendi. `git` AppContainer içinde `rc=128` (sebep ölçülmedi) |

Yerelde (yükseltilmemiş makine) aynı de-elevate betiği altında 13 test, 0 skip geçti.

İkinci hosted koşu (`docs/evidence/poc/fix01_hosted_followup.log`, geçici `probe/fix01-followup` dalı, silindi):

| Soru | Sonuç |
|---|---|
| Tüm `C:\hostedtoolcache` yerine yalnızca çalışma alanı + Python kurulum dizinine yetki yeterli mi? | **Evet.** Yetki verme 16 sn; AppContainer matrisi 50 sn; 13 test: 12 geçti, 1 skip, 0 hata. (İlk probe'daki ~10 dk, tüm ağaca yetki vermekten geliyordu.) |
| Skip eden test | `test_node_worker_can_start_piped_children_and_resolve_paths`: Cursor CLI kurulu değil. Cursor oturumu/kimliği gerektirdiği için CI'a kurulmaz (ücret/hesap). |
| Hosted'da AppContainer içinde `git` | `rc=128`: `fatal: could not open '/dev/null' for reading and writing: Permission denied`. Runner'da git 2.56.0, yerel makinede 2.55.0 ve orada çalışıyor; fark git sürümünden mi görüntüden mü geliyor **ayrıştırılmadı**. |

## Karar

1. **Ayrı self-hosted runner gerekmez.** Hosted runner üzerinde güvenlik matrisi, iş sırasında oluşturulan geçici
   standart yerel kullanıcı altında koşar. Runner VM'i iş bitince yok edildiği için hesap kalıcı değildir; gizli
   anahtar ve yetki gerekmez; maliyet 0'dır (public depo).
2. **Belirteç "ince ayarı" kullanılmaz.** Administrators'ı kapatıp integrity düşürmek `TokenElevation` bitini
   temizlemez; güvenlik varsayımı olarak kabul edilmez. `fix01_deelevate_probe.py` yalnızca bu olumsuz sonucu kanıtlar.
3. **Sıfır skip politikası.** Zorunlu güvenlik kümesi `tests/engine/security_cases.py` kayıt defterinden, `RealSandboxTests`
   ve frozen exe matrisinden türetilir. Koşu bittiğinde manifest `skipped == 0`, `errors == 0`, `failed == 0` ve beklenen
   test sayısı doğrulanmadan kapı geçmez. **Karar:** Cursor CLI'a bağlı `test_node_worker_can_start_piped_children_and_resolve_paths`
   zorunlu güvenlik kümesinden **adıyla** çıkarılır ve manifestte `excluded` altında gerekçesiyle listelenir (Cursor
   hesap/oturum ister, CI'a kurulmaz). Bu test yalnızca Cursor CLI'ı olan yerel makinede koşar ve release öncesi
   yerel kanıt listesinde yer alır. Başka hiçbir test sessizce atlanamaz; manifestte listelenmemiş skip kapıyı kırar.
4. **Güvenlik adımlarında `ORCH_ALLOW_ELEVATED_SKIP` kullanılmaz.** Yükseltilmiş oturumda güvenlik adımı fail eder.
   `tests/tools/run_ci.py` ve `elevated_ci_skips.txt` yalnızca güvenlik dışı, sandbox gerektiren genel testler
   için kalır ve bu testler de ayrı bir yükseltmesiz adımda koşturulduğunda atlanmaz; hedef, listenin boşalmasıdır.
5. **Fail-closed.** Kullanıcı oluşturma, ACL verme, süreç başlatma, timeout ya da manifest üretiminin herhangi biri
   başarısız olursa iş kırmızıdır.
6. **Kanıt.** Manifest commit SHA'sı, runner imajı sürümü, `elevated`, test sayıları ve atlanan/çıkarılan test adlarını
   taşır ve artefakt olarak yüklenir; `test_security_gate.py` bu manifesti doğrular.

## Sonuçlar

- Geçici kullanıcı, AppContainer için Python kurulum dizininin DACL'ini değiştirebilmelidir; bu yüzden o dizinde ve
  çalışma alanında tam yetki gerekir (hosted VM'de tek kullanımlık; kalıcı makinede böyle bir yetki verilmez).
  Yalnızca bu iki yola verildiğinde ölçülen süre 16 sn'dir.
- `git` AppContainer içinde hosted görüntüde çalışmadığı için zorunlu güvenlik kümesi `git`'e dayanamaz; motorun
  kendi `git` çağrıları sandbox dışında koştuğundan etkilenmez (ADR-018 §4).
- Windows dışı kod yolları bu kararın kapsamı değildir (ADR-008).
- Ölçüm tek runner imajında yapıldı; GitHub imajı değişirse manifest ve fail-closed kapı bunu kırmızı yakalar.

## Kaynaklar

- [Tehdit modeli](../THREAT_MODEL.md) S-19, §6 (erişim: 2026-11-05).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §SEC-03, §SEC-04 (erişim: 2026-11-05).
- `docs/evidence/poc/fix01_hosted_probe.log`; [ADR-018](ADR-018-verify-network-isolation.md).
