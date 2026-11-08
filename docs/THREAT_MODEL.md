# Respected Orchestrator tehdit modeli ve yetki matrisi

Durum: SEC-01 · 30 Ekim 2026 (son güncelleme 8 Kasım 2026) · Windows beta
Kapsam: motor, worker süreçleri, doğrulama komutları, sonuç/onay zinciri, MCP ve masaüstü uygulaması sınırı.
Bağlayıcı mimari: [ARCHITECTURE.md](ARCHITECTURE.md). Bu belge yeni bir güvenlik özelliği vaat etmez; bugün
uygulanan sınırları, uygulanmayanları ve sıradaki işlerin hedeflerini ayırır.

## 1. Amaç ve iddia disiplini

Bu belge iki soruya yanıt verir:

1. Hangi varlık, hangi aktörden, hangi katmanda korunuyor?
2. Bugün korunmayan bir şey, hangi görevle kapatılacak?

Kural: bir koruma test edilmiş ya da kodda açıkça uygulanmış değilse "korunuyor" denmez. Motor işçiyi ve doğrulama komutlarını işletim
sistemi düzeyinde bir kutuya koymaz: işçiler kullanıcı olarak, ajanın kendi izin kipiyle çalışır. Motorun sınırı
kapsam denetimi, yama doğrulaması, süre sınırları, süreç ağacı temizliği ve imzalı kanıttır (bölüm 3, B2–B5).

## 2. Varlıklar

| Kimlik | Varlık | Neden önemli |
|---|---|---|
| A1 | `.engine-key` | Kanıt ve onay imzası; ele geçerse sahte sonuç üretilir |
| A2 | İmzalı kanıt (`request/result/status/maf-result`) | Teslimatın doğrulanabilir kaydı |
| A3 | `settings.json` ve gizli değerler | API anahtarı, hafıza jetonu, sağlayıcı ayarları |
| A4 | `maf-approval.json` | İnsan kararının değişmez kaydı |
| A5 | Proje kaynak ağacı ve çalışma ağacı | Kullanıcının gerçek kodu |
| A6 | Workspace dışındaki kullanıcı dosyaları | Profil kimlik bilgileri, özel belgeler |
| A7 | Brain not kasası | Ayrı ürün; yalnızca `rpp` sözleşmesiyle erişilir |
| A8 | Ağ uçları ve bulut kimlik bilgileri | Dışarı sızma ve izinsiz eylem |
| A9 | Süre/bütçe/iptal denetimi ve süreç ağacı | Kaynak tükenmesi, artık süreç |
| A10 | Benchmark/eval verisi (gelecek) | Yanlış başarı iddiası |

## 3. Güven sınırları

| Kimlik | Sınır | Bugünkü durum |
|---|---|---|
| B1 | İnsan/kullanıcı → CLI, masaüstü uygulaması, MCP | CLI ve MCP girdileri şema ve izin denetiminden geçer; MCP ayrıcalıklı anahtarları varsayılan reddeder |
| B2 | Motor → worker CLI süreci | Süreç kullanıcı olarak başlar; **işletim sistemi düzeyinde dosya veya ağ sınırı yoktur**. Sınırı ajanın kendi izin kipi çizer (Codex `--sandbox`, Claude `--permission-mode`, OpenCode/Cursor kendi kipleri); `custom` keyfi komuttur. Motor ortamdan sır adlı değişkenleri çıkarır, süre sınırı koyar ve süreç ağacını temizler. macOS/Linux'ta henüz doğrulanmadı |
| B3 | Worker çıktısı → kapsam ve yama doğrulaması | Çalışma ağacındaki değişiklikler çalışmadan sonra denetlenir; kapsam dışı değişiklik ve `120000`/`160000` yamaları reddedilir. Ağaç dışına yazımı motor engellemez, yalnız yamaya girmesini engeller |
| B4 | Worker'ın yazdığı kabul/verify kodu → motor yürütmesi | Kullanıcı olarak, ortamı süzülmüş ayrı bir süreçte çalışır (`processes.run_check`); kutu yoktur. Kodun motorun sırlarını okuyabileceği varsayılır (B2) |
| B5 | Motor → gerçek proje ağacı (`apply`) | Yalnızca doğrulanmış, taze, imzalı ve gerekliyse insan onaylı yama; `git apply --check` sonrası yazım |
| B6 | Motor → MCP/masaüstü uygulaması | MCP, motorun kendi onaylarını üretemez; `maf-approve` MCP'de yoktur |
| B7 | Motor → Brain | Kod bağımlılığı yok; yalnızca `rpp` ve izinli `memory.write` |
| B8 | Motor → alt süreçler | Windows job object; timeout/iptal/supervisor çöküşünde ağaç öldürülür |

**Not:** İmza anahtarı (`.engine-key`) kullanıcı ACL'iyle korunur ama işçi aynı kullanıcı olduğu için okuyabilir. Kanıt ve onay bütünlüğü imza
ve motorun yeniden doğrulamasıyla sağlanır; anahtarın gizliliği için ek bir garanti verilmez.

## 4. Yetki matrisi

| Eylem | Operatör | MAF Master | Worker | Reviewer | Kabul/verify kodu | MCP istemcisi | Masaüstü uygulaması |
|---|---|---|---|---|---|---|---|
| Proje çalışma ağacını değiştirme | Evet | Hayır | Evet (yalnızca kendi lane'i) | Hayır | Hayır | Görev başlatma ile | Görev başlatma ile |
| Gerçek proje ağacına `apply` | Evet | Hayır | Hayır | Hayır | Hayır | Koşullu: doğrulanmış `patch_sha256` ve yetki | Bugün düğme yok |
| `.engine-key` okuma/yazma | Hayır (motor yapar) | Hayır | **Okuyabilir (ek koruma yok)** | Hayır | **Okuyabilir** | Hayır | Hayır |
| Kanıt yazma/değiştirme | Hayır (motor yapar) | Hayır | Yazabilir ama imza tutmaz; `check` reddeder | Hayır | Yazabilir ama imza tutmaz | Hayır | Hayır |
| `maf-approval.json` üretme | **Yalnızca etkileşimli TTY** | Hayır | Hayır | Hayır | Hayır | Hayır | Hayır |
| Workspace dışına yazma | İşletim sistemi izinleri | Sağlayıcıya bağlı | Ajanın kendi kipine bağlı | Sağlayıcıya bağlı | Serbest | — | — |
| Ağ erişimi | İşletim sistemi | Sağlayıcıya bağlı | Ajanın kendi kipine bağlı | Sağlayıcıya bağlı | **Serbest** | Motorun kendi çağrıları | Masaüstünün kendi çağrıları |
| Alt süreç başlatma | Evet | Sağlayıcıya bağlı | Evet | Sağlayıcıya bağlı | Evet (job object içinde) | Hayır | Hayır |
| Görevi iptal/süre sınırı | Evet | Kendi run'ı | Hayır | Hayır | Hayır | Evet (araç varsa) | Evet (araç varsa) |
| Ayrıcalıklı MCP anahtarı (`custom`, `apply_root`, `engine_source`) | `--allow-privileged` ile | Hayır | Hayır | Hayır | Hayır | Varsayılan red | — |

Not: "MAF Master" kod teslim edemez; `workflows/project.py` içinde master yalnızca nihai değerlendirme yapar.
## 5. Saldırı senaryoları

Durum kodları: **Engellenir (test)** = sınır var ve testle kanıtlı; **Engellenir (kod)** = kodda açık ret, testi
ilgili dosyada; **Kısmi** = bazı koşullarda korur; **Yok** = bugün motor engellemez.

| ID | Saldırı | Sahip | Engel katmanı | Beklenen sonuç | Bugünkü durum | Kanıt |
|---|---|---|---|---|---|---|
| S-03 | Worker ya da doğrulama kodu proje içindeki `.env` dosyasını, profili veya `.engine-key` dosyasını okur | Worker / kabul kodu | Ajanın kendi kipi | Sır yoksa sorun yok | **Yok**; süreç kullanıcı olarak çalışır, motor okumayı engellemez. Bütünlük imzaya dayanır, gizlilik için garanti verilmez | B2; bölüm 7 |
| S-10 | Worker imzalı sonucu/kanıtı kurcalar veya uydurur | Worker | B3 HMAC doğrulama | `check`/`apply` reddi | **Engellenir (test)** | `test_runner.py::test_result_and_request_envelopes_refuse_tampering` |
| S-11 | Worker kendi yamasını `apply` etmeye çalışır | Worker | B5 çocuk süreç reddi | Red | **Engellenir (test)** | `test_runner.py` (`RESPECTED_ORCH_CHILD`) |
| S-12 | Doğrulamadan sonra proje değişir; eski yama uygulanır | Motor | B5 tazelik + `git apply --check` | Red | **Engellenir (test)** | `test_runner.py::test_stale_or_tampered_results_are_rejected` |
| S-13 | Worker izinli kapsam dışına dosya ekler/değiştirir | Worker | B3 kapsam | Red | **Engellenir (test)** | `test_runner.py::test_scope_violation_and_acceptance_mutation_are_rejected` |
| S-14 | Worker/alt süreç insan onayı üretir | Worker | B5 + B6 | Red | **Engellenir (test)** | `test_maf_coding.py::test_approval_is_bound_to_patch_immutable_and_operator_only`; MCP'de onay aracı yok |
| S-15 | Onay başka yamaya/başka run'a kopyalanır | Saldırgan / hata | B5 `patch_sha256` + `root_run_id` | Red | **Engellenir (test)** | `test_maf_coding.py::test_cross_run_approval_is_rejected`, `test_approval_without_patch_binding...` |
| S-16 | Otomasyon/pipe TTY olmadan onay verir | Otomasyon | B5 TTY | Red | **Engellenir (test)** | `test_maf_coding.py::test_approval_refuses_non_interactive_callers` |
| S-17 | Timeout/iptal sonrası alt süreç yaşar | Worker | B8 job object | Ağaç tamamen ölür | **Engellenir (test, Windows)** | `test_windows_processes.py::test_timeout_kills_the_whole_tree`, `test_cancel...`, `test_an_orphan...` |
| S-18 | Sır gibi görünen ortam değişkeni worker'a geçer | Motor | B2 ortam temizliği | Adı sır olan değişken çıkarılır | **Kısmi**; ad tabanlı, `RESPECTED_WORKER_ENV_ALLOW` istisnası | `test_runner.py::test_worker_environment_drops_secrets_unless_allowed` |
| S-21 | MCP istemcisi `custom` worker, `apply_root` veya `engine_source` ister | MCP istemcisi | B1 MCP izin listesi | Varsayılan red | **Engellenir (test)** | `tests/interfaces/test_mcp_server.py` |
| S-22 | MCP istemcisi yanlış/eski `patch_sha256` ile `apply` çağırır | MCP istemcisi | B5 + B6 | Red | **Engellenir (test)** | `tests/interfaces/test_mcp_server.py` |
| S-23 | Worker, worktree dışına işaret eden symlink içeren yama üretir | Worker | B3/B5 yama güvenliği | Red | **Engellenir (test)**; `120000`/`160000` indeks modu güvensiz sayılır, kapsam ve export reddeder, apply çakışma döner | `test_apply_hardening.py`; `test_frozen_security.py::test_frozen_engine_rejects_a_symlink_mode_patch_staged_without_symlink_privilege`; `engine/lanes.py` |
| S-25 | Masaüstü uygulaması/MCP üzerinden insan onayı sahte bir düğmeyle verilir | Masaüstü uygulaması/MCP | B5/B6 | Yalnızca gerçek TTY oturumu | **Engellenir (test)** | `test_maf_coding.py`; MCP araç listesinde `maf-approve` yok |
## 6. Windows kullanıcı ve yönetici kararı

| Çalışma bağlamı | Karar | Gerekçe | Bugünkü uygulama |
|---|---|---|---|
| Windows normal kullanıcı (yükseltilmemiş) | **Desteklenir** | İşçiler bu kullanıcıyla çalışır | Testli |
| Windows yönetici / UAC ile yükseltilmiş | **Desteklenmez** | İşçiler yönetici yetkisiyle çalışırdı | **Aktif ret:** supervisor yükseltilmiş belirteçte başlamaz (`winproc.is_elevated`) |
| macOS/Linux | **Henüz doğrulanmadı (GA dışı)** | Kod yolları var, kanıt yok | ARCHITECTURE §10; ADR-008 |

Yükseltilmiş bağlam bu ürünün tehdit modelinin dışındadır.

## 7. Açıklanmamış güvenlik vaadi denetimi

Aşağıdaki tablo, ürünün güvenlik iddialarını tek yerde toplar. "Yok" satırları pazarlama metninde iddia edilmemelidir.

| İddia | Durum | Kanıt / sınır |
|---|---|---|
| `apply` doğrulanmamış, bayat veya kurcalanmış sonucu uygulamaz | **Var** | HMAC, `patch_sha256`, tazelik, `git apply --check`; `test_runner.py` |
| İnsan onayı ajan tarafından üretilemez | **Var (kimlik doğrulama değil)** | `RESPECTED_ORCH_CHILD`, TTY, patch bağı; `test_maf_coding.py` |
| Doğrulama kodu ve worker motorun sırlarını okuyamaz | **Yok** | İşçi ve doğrulama komutu kullanıcı olarak çalışır; bütünlük imzaya dayanır (B2) |
| Worker işletim sistemi düzeyinde kapatılmıştır | **Yok** | Sınırı ajanın kendi izin kipi çizer |
| Worker ve doğrulama kodu ağa çıkamaz | **Yok** | Ağ kuralını ajanın kendi ayarı belirler |
| Sırlar her yoldan temizlenir | **Kısmi** | Ad tabanlı ortam temizliği; dosya sistemi ve profil kapsanmaz |
| Aynı veri kökünde tek görev çalışır | **Var** | Kilit; ARCHITECTURE §2 |
| Yükseltilmiş yönetici desteklenir | **Yok** | Bölüm 6; supervisor yükseltilmiş belirteçte başlamaz |
| Masaüstü uygulaması/MCP insan onayı üretemez | **Var** | MCP araçlarında `maf-approve` yok; `orchestrator_apply` digest ister |

Bu tabloda "Yok" ya da "Kısmi" olan bir satır, tamamlanmış bir güvenlik özelliği gibi sunulmamalıdır. SEC-01'in
"0 açıklanmamış güvenlik vaadi" kriteri bu tabloyla karşılanır.

## 8. PoC ölçümü (30 Ekim 2026)

Motorun kendi çocuk süreç başlatıcısıyla (`engine/winproc.run`) çalıştırılan zararsız PoC'ler.
Betik: `evidence/poc/sec01_probe.py` · Çıktı: `evidence/poc/sec01_results.json`

| PoC | Deneme | Sonuç | Ölçüm |
|---|---|---|---|
| P-01 | workspace dışındaki dosyayı okuma | ALLOWED | dış dosyanın içeriği okundu |
| P-02 | workspace dışına dosya yazma | ALLOWED | dış klasörde dosya oluştu |
| P-03 | `example.com:443` TCP çıkışı | ALLOWED | bağlantı kuruldu |
| P-04 | worktree içindeki `.env` okuma | ALLOWED | sahte anahtar okundu |
| P-05 | workspace içindeki junction üzerinden dışarı okuma | ALLOWED | dış dosyanın içeriği okundu |

**Yorum:** Bu beş deneme bugünkü motor için de geçerlidir: işçi işletim sistemi düzeyinde kısıtlanmaz (S-03). Betik bugünkü motoru ölçmez; tarihsel ölçümdür.

## 9. Kanıt haritası

| Kanıt | Kapsadığı senaryolar |
|---|---|
| `tests/packaging/test_frozen_security.py` | Symlink yaması ve özyinelemeli MCP reddi paketlenmiş exe üzerinde |
| `tests/engine/test_runner.py` | S-10, S-11, S-12, S-13, S-18; kapsam, tazelik, imza, `apply` |
| `tests/engine/test_windows_processes.py` | S-17, S-20 (öldürme kısmı) |
| `tests/workflows/test_maf_coding.py` | S-07, S-14, S-15, S-16, S-25 |
| `tests/interfaces/test_mcp_server.py` | S-21, S-22 |
| `tests/packaging/test_frozen_build.py` | Paketlenmiş exe'de kabul doğrulaması |

Doğrulama komutu: `python -m unittest discover -s tests -t .` (paketleme değişikliği yoksa build gerekmez).
Kanıt, test adı + çalışma tarihiyle birlikte sunulur; test adı belge cümlesine bağlanmaz.

## 10. Açık riskler ve sonraki görevler

| Risk | Etki | Kapatacak görev |
|---|---|---|
| Worker'ın ağaç dışı yazması, ağ erişimi ve sır okuması | Kullanıcı dosyaları, dış sistemler, imza anahtarı | **Açık (bilinçli):** motor kutu koymaz; ajanın kendi kipi ve izin kipleri (RAKIP_ESKIKLERI B3) belirler |
| Symlink/gitlink yama varyantları | Workspace dışına yazım | **Kapandı (SEC-04, test):** `120000`/`160000` kapsam, export ve apply öncesi reddedilir |
| Ajan kiplerinin sürüm farkı | Sessiz güven kaybı | Sürüm ve CLI smoke testi |
| Onayın kimlik doğrulaması olmaması | Aynı kullanıcı hesabındaki başka süreç | Bilinen sınır; kimlik modeli ayrı ürün kararı |
| Tek veri kökünde tek görev | Paralellik kısıtı | EVAL/orkestrasyon görevleri |

## 11. Bakım kuralı

- Her yeni güvenlik iddiası bu belgeye bir satır ekler; testi yoksa "Kısmi" veya "Yok" yazılır.
- `runner.py` (`apply`, `approve_maf_task`), `processes.py` veya MCP izin listesi değişirse bu belge
  aynı değişiklikte güncellenir.
- S-03 "Yok"tur ve öyle kalır; yeni iddia testsiz "Yok" ya da "Kısmi" yazılır.

## 12. Masaüstü (Beta.3) tehdit modeli taslağı — B3-00.02

Durum: **taslak/plan**. Bu bölümdeki hiçbir satır "Engellenir" değildir; masaüstü uygulaması henüz yoktur, durum
her satırda **Planlı** yazılır ve ancak ilgili görev testiyle yükseltilir (§11 bakım kuralı). Varsayılan: **fail-closed**.

### 12.1 Yeni güven sınırları

| Kimlik | Sınır | Kural |
|---|---|---|
| B9 | Renderer (WebView, React) → Tauri native kabuk | Renderer güvenilmez girdidir; yalnızca tipli, izin listeli komut çağırır; dosya, süreç ve ağ yetkisi doğrudan yok |
| B10 | Native kabuk → motor/supervisor (yerel servis) | Yerel kimlik doğrulamalı kanal (rastgele oturum belirteci, yalnızca loopback/named pipe); her komut yetki sınıfı taşır |
| B11 | İşletim sistemi/başka uygulama → masaüstü (deep link, protokol, pano, sürükle-bırak) | Tüm girdi veri sayılır; eylem başlatamaz, yalnızca taslak üretebilir |
| B12 | İnsan varlığı (human-presence authority) → onay/apply | Renderer, MCP, worker ve çocuk süreç bu sınırı üretemez; onay iki ayrı doğrulamayla (insan eylemi + patch digest) bağlanır (B3-00.03) |

### 12.2 Negatif tehdit senaryoları (en az 12)

| ID | Tehdit | Sahip | Engel katmanı | Beklenen sonuç | Durum | Test planı (görev) |
|---|---|---|---|---|---|---|
| D-01 | Renderer'dan `approve`/`apply` komutu taklidi | Renderer | B9, B12 | Native kabuk komutu yetki sınıfı yok diye reddeder; onay dosyası oluşmaz | Planlı | B3-05.02, B3-05.04 |
| D-02 | IPC spoofing: başka yerel süreç IPC kanalına bağlanır | Yerel süreç | B10 | Oturum belirteci yoksa bağlantı reddedilir | Planlı | B3-01.02 |
| D-03 | Localhost CSRF: tarayıcı sayfası yerel servise istek atar | Web sayfası | B10 | Origin/belirteç denetimi; yoksa 403, yan etki yok | Planlı | B3-01.03 |
| D-04 | Deep link enjeksiyonu (`respected://…`) ile görev/onay başlatma | Başka uygulama | B11 | Link yalnızca taslak açar; yetkili eylem yok | Planlı | B3-01.04 |
| D-05 | XSS: ajan çıktısı veya diff içeriği UI'de betik çalıştırır | Ajan çıktısı | B9 | Çıktı kaçışlanır, CSP betiği engeller | Planlı | B3-06.02 |
| D-06 | Ele geçirilmiş renderer yetkisiz Tauri komutu çağırır | Renderer | B9 | Capability izin listesi dışı komut reddedilir | Planlı | B3-01.01 |
| D-07 | Replay: eski onay/komut tekrar gönderilir | Ağ/süreç | B12 | Tek kullanımlık nonce; ikinci kullanım reddedilir | Planlı | B3-00.03, B3-05.04 |
| D-08 | Yetki yükseltme: salt-okunur oturum `settings`/`privileged` komut çağırır | Renderer | B10 | Yetki sınıfı uyuşmazlığı → ret | Planlı | B3-00.03 |
| D-09 | Onaydan sonra patch değişir (patch drift / TOCTOU) | Ajan/süreç | B12, B5 | Digest uyuşmazlığı → apply reddi, yazım yok | Planlı | B3-05.03 |
| D-10 | Symlink/junction ile diff veya dosya inspector çalışma ağacı dışını okur | Worker çıktısı | B3, B9 | Kök dışı yol reddedilir | Planlı | B3-06.02 |
| D-11 | Başka kullanıcı bağlamından/yükseltilmiş süreçten gelen komut | Yerel süreç | B10 | Kullanıcı kimliği/oturum eşleşmezse ret | Planlı | B3-02.03 |
| D-12 | Pano/sürükle-bırak ile gizli anahtar sızdırma veya komut yapıştırma | Kullanıcı hatası/başka uygulama | B11 | Gizli değer redakte edilir; yapıştırılan metin çalıştırılmaz | Planlı | B3-03.05 |
| D-13 | Terminal oturumu izinsiz süreç açar | Renderer/ajan | B2, B9 | Oturum yalnızca motor üzerinden açılır; turdaki dosya değiştiren, komut çalıştıran ve ağ araçları reddedilir (izin kipleri gelene kadar), proje yapılandırması yok sayılır, süreç `RESPECTED_ORCH_CHILD` ile işaretlenir | Planlı (Chat için kısmen önlem alındı). PTY oturumu henüz yok | B3-03.02; `test_session_control.py`, `test_session_live.py` (isteğe bağlı) |

### 12.3 Yetkili eylem tablosu (sahip, kayıt, ret durumu)

| Eylem | Sahip | Kayıt | Reddedilme durumu |
|---|---|---|---|
| Okuma/durum | Renderer (salt okunur sınıf) | Denetim olayı | Belirteç yok → ret |
| Görev başlat/iptal | İnsan oturumu | Olay günlüğü | Yetki sınıfı yok → ret |
| Ayar değiştir | İnsan oturumu | Olay günlüğü | Sınıf uyuşmazlığı → ret |
| Onay/apply | Yalnızca human-presence authority | `maf-approval.json` + olay | Renderer/MCP/worker → ret, dosya oluşmaz |

Bu tablonun tamamlayıcısı B3-00.03'teki komut/yetki matrisidir.
