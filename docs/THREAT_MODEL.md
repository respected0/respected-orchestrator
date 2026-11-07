# Respected Orchestrator tehdit modeli ve yetki matrisi

Durum: SEC-01 · 30 Ekim 2026 (son güncelleme 4 Kasım 2026, CUR-01) · Windows beta
Kapsam: motor, worker süreçleri, doğrulama kum havuzu, sonuç/onay zinciri, MCP ve Hub sınırı.
Bağlayıcı mimari: [ARCHITECTURE.md](ARCHITECTURE.md). Bu belge yeni bir güvenlik özelliği vaat etmez; bugün
uygulanan sınırları, uygulanmayanları ve sıradaki işlerin hedeflerini ayırır.

## 1. Amaç ve iddia disiplini

Bu belge iki soruya yanıt verir:

1. Hangi varlık, hangi aktörden, hangi katmanda korunuyor?
2. Bugün korunmayan bir şey, hangi görevle kapatılacak?

Kural: bir koruma test edilmiş ya da kodda açıkça uygulanmış değilse "korunuyor" denmez. Sağlayıcının (Codex,
Claude, Cursor) kendi kum havuzu bu motorun garantisi değildir; yalnızca sağlayıcıya bağlı bir katman olarak
kaydedilir. Motorun kendi sınırı, worker'ı Windows AppContainer içinde başlatmasıdır (bölüm 3, B2).

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
| B1 | İnsan/kullanıcı → CLI, Hub, MCP | CLI ve MCP girdileri şema ve izin denetiminden geçer; MCP ayrıcalıklı anahtarları varsayılan reddeder |
| B2 | Motor → worker CLI süreci | **Windows'ta AppContainer (SEC-03/SEC-04, test):** varsayılan olarak yalnızca görevin çalışma ağacı ve geçici kökü yazılabilir, ağ kapalıdır, veri kökü ve kullanıcı profili okunamaz; kum havuzu kurulamazsa worker başlamaz. Codex ayrıca kendi `workspace-write` kum havuzunu ister; Claude/Cursor kendi izin modellerini korur; `custom` keyfi komuttur ve aynı AppContainer politikasından geçer. Windows dışında worker başlatılmaz |
| B2a | Cursor çalışanı → ağ/kimlik bilgisi | Ağ yalnızca operatör anahtarı `RESPECTED_CURSOR_NETWORK=allow` ile açılır (modelden kontrol edilemez); yalnızca `auth.json` izole HOME'a kopyalanır, kanıta/log'a yazılmaz, çalışma sonunda silinir. Açık risk: açık ağda çalışan süreç kopyalanan token'ı kullanabilir/sızdırabilir (OpenCode ile aynı sınıf). Cursor AppContainer içinde çalışır (boru shim'i, ARCHITECTURE.md, CUR-01); shim yalnız alt süreç borularının adını `LOCAL\` altına alır, izin sınırını genişletmez |
| B3 | Worker çıktısı → kapsam ve yama doğrulaması | Çalışma ağacındaki değişiklikler sonradan denetlenir; ağaç dışına yazım AppContainer tarafından işletim sistemi düzeyinde engellenir (B2), yama denetimi buna ek bir katmandır |
| B4 | Worker'ın yazdığı kabul/verify kodu → motor yürütmesi | Windows'ta worker ile aynı AppContainer yolu, ağ varsayılan kapalı (ADR-018, FIX-04); kurulamazsa verify çalışmaz |
| B5 | Motor → gerçek proje ağacı (`apply`) | Yalnızca doğrulanmış, taze, imzalı ve gerekliyse insan onaylı yama; `git apply --check` sonrası yazım |
| B6 | Motor → MCP/Hub | MCP, motorun kendi onaylarını üretemez; `maf-approve` MCP'de yoktur |
| B7 | Motor → Brain | Kod bağımlılığı yok; yalnızca `rpp` ve izinli `memory.write` |
| B8 | Motor → alt süreçler | Windows job object; timeout/iptal/supervisor çöküşünde ağaç öldürülür |

**Not:** B4 ve B2 artık aynı mekanizmayı kullanır (AppContainer, `engine/sandbox.run_check` → `worker_policy` → `appcontainer.spawn`);
kısıtlı belirteç yolu kaldırıldı. Fark yalnızca politikadadır: verify yalnızca çalışma ağacına yazar, ağ kapalıdır.

## 4. Yetki matrisi

| Eylem | Operatör | MAF Master | Worker | Reviewer | Kabul/verify kodu | MCP istemcisi | Hub |
|---|---|---|---|---|---|---|---|
| Proje çalışma ağacını değiştirme | Evet | Hayır | Evet (yalnızca kendi lane'i) | Hayır | Hayır | Görev başlatma ile | Görev başlatma ile |
| Gerçek proje ağacına `apply` | Evet | Hayır | Hayır | Hayır | Hayır | Koşullu: doğrulanmış `patch_sha256` ve yetki | Bugün düğme yok |
| `.engine-key` okuma/yazma | Hayır (motor yapar) | Hayır | Hayır | Hayır | **Hayır (Windows)** | Hayır | Hayır |
| Kanıt yazma/değiştirme | Hayır (motor yapar) | Hayır | Hayır | Hayır | **Hayır (Windows)** | Hayır | Hayır |
| `maf-approval.json` üretme | **Yalnızca etkileşimli TTY** | Hayır | Hayır | Hayır | Hayır | Hayır | Hayır |
| Workspace dışına yazma | İşletim sistemi izinleri | Sağlayıcıya bağlı | **Engellenir (AppContainer, Windows)** | Sağlayıcıya bağlı | Windows'ta veri kökü dışında serbest | — | — |
| Ağ erişimi | İşletim sistemi | Sağlayıcıya bağlı | **Varsayılan kapalı (AppContainer)**; yalnızca OpenCode/Cursor için operatör anahtarıyla açılır | Sağlayıcıya bağlı | **Serbest** | Motorun kendi çağrıları | Hub kendi çağrıları |
| Alt süreç başlatma | Evet | Sağlayıcıya bağlı | Evet | Sağlayıcıya bağlı | Evet (job object içinde) | Hayır | Hayır |
| Görevi iptal/süre sınırı | Evet | Kendi run'ı | Hayır | Hayır | Hayır | Evet (araç varsa) | Evet (araç varsa) |
| Ayrıcalıklı MCP anahtarı (`custom`, `apply_root`, `engine_source`) | `--allow-privileged` ile | Hayır | Hayır | Hayır | Hayır | Varsayılan red | — |

Not: "MAF Master" kod teslim edemez; `workflows/project.py` içinde master yalnızca nihai değerlendirme yapar.
## 5. Saldırı senaryoları

Durum kodları: **Engellenir (test)** = sınır var ve testle kanıtlı; **Engellenir (kod)** = kodda açık ret, testi
ilgili dosyada; **Kısmi** = bazı koşullarda korur; **Yok** = bugün motor engellemez.

| ID | Saldırı | Sahip | Engel katmanı | Beklenen sonuç | Bugünkü durum | Kanıt |
|---|---|---|---|---|---|---|
| S-01 | Worker `..\` ile proje/workspace dışına dosya yazar | Worker / sağlayıcı | B2 AppContainer | İşlem öncesi red | **Engellenir (test, Windows)**; `write_outside_file` ve `junction_write_outside` vakaları | `tests/engine/test_worker_security.py` (`security_cases.py`); SEC-03/04 |
| S-02 | Worker profil altındaki kimlik bilgilerini okur | Worker / sağlayıcı | B2 AppContainer | Okuma reddi | **Engellenir (test, Windows)**; `read_outside_file` ve `.engine-key` okuma vakaları. İstisna: OpenCode/Cursor için kasıtlı kopyalanan `auth.json` | `test_worker_security.py`; SEC-03/04; B2a |
| S-03 | Worker proje içindeki `.env` dosyasını okur | Worker / operatör | Proje hijyeni | Sır yoksa sorun yok; varsa okuma reddi | **Yok**; dosya worktree'deyse okunabilir (worktree worker'a bilerek açılır), `forbidden` yolları yalnızca yamayı denetler | SEC-03; operatör kontrol listesi |
| S-04 | Worker onaysız adrese HTTP/TCP çıkar | Worker / sağlayıcı | B2 AppContainer ağ politikası | Varsayılan kapalı | **Engellenir (test, Windows)**; `network_egress` vakası. Operatör anahtarıyla açılan OpenCode/Cursor için ağ açıktır (B2a) | `test_worker_security.py`; SEC-03/04 |
| S-05 | Kabul kodu `.engine-key` okur (düz, `\\?\`, junction, hardlink) | Kabul kodu | B4 AppContainer | Erişim reddi | **Engellenir (test)** | `tests/engine/test_sandbox.py` |
| S-06 | Kabul kodu `settings.json` veya imzalı kanıtı okur/değiştirir/siler | Kabul kodu | B4 | Erişim ve yazma reddi | **Engellenir (test)** | `tests/engine/test_sandbox.py` |
| S-07 | Kabul kodu sahte `maf-approval.json` yazar | Kabul kodu | B4 + B5 | Yazma reddi; onay yok sayılır | **Engellenir (test)** | `test_sandbox.py`; `test_maf_coding.py` |
| S-08 | Kabul kodu DENY ACE'yi kaldırır veya anahtara kendini yetkilendirir | Kabul kodu | B4 ACL | Red; OWNER RIGHTS ile WRITE_DAC sınırlı | **Engellenir (test)** | `test_sandbox.py` (negatif kontrolle) |
| S-09 | Kabul kodu veri kökünde yeni dosya/klasör üretir | Kabul kodu | B4 | Red | **Engellenir (test)** | `test_sandbox.py` |
| S-10 | Worker imzalı sonucu/kanıtı kurcalar veya uydurur | Worker | B3 HMAC doğrulama | `check`/`apply` reddi | **Engellenir (test)** | `test_runner.py::test_result_and_request_envelopes_refuse_tampering` |
| S-11 | Worker kendi yamasını `apply` etmeye çalışır | Worker | B5 çocuk süreç reddi | Red | **Engellenir (test)** | `test_runner.py` (`RESPECTED_ORCH_CHILD`) |
| S-12 | Doğrulamadan sonra proje değişir; eski yama uygulanır | Motor | B5 tazelik + `git apply --check` | Red | **Engellenir (test)** | `test_runner.py::test_stale_or_tampered_results_are_rejected` |
| S-13 | Worker izinli kapsam dışına dosya ekler/değiştirir | Worker | B3 kapsam | Red | **Engellenir (test)** | `test_runner.py::test_scope_violation_and_acceptance_mutation_are_rejected` |
| S-14 | Worker/alt süreç insan onayı üretir | Worker | B5 + B6 | Red | **Engellenir (test)** | `test_maf_coding.py::test_approval_is_bound_to_patch_immutable_and_operator_only`; MCP'de onay aracı yok |
| S-15 | Onay başka yamaya/başka run'a kopyalanır | Saldırgan / hata | B5 `patch_sha256` + `root_run_id` | Red | **Engellenir (test)** | `test_maf_coding.py::test_cross_run_approval_is_rejected`, `test_approval_without_patch_binding...` |
| S-16 | Otomasyon/pipe TTY olmadan onay verir | Otomasyon | B5 TTY | Red | **Engellenir (test)** | `test_maf_coding.py::test_approval_refuses_non_interactive_callers` |
| S-17 | Timeout/iptal sonrası alt süreç yaşar | Worker | B8 job object | Ağaç tamamen ölür | **Engellenir (test, Windows)** | `test_windows_processes.py::test_timeout_kills_the_whole_tree`, `test_cancel...`, `test_an_orphan...` |
| S-18 | Sır gibi görünen ortam değişkeni worker'a geçer | Motor | B2 ortam temizliği | Adı sır olan değişken çıkarılır | **Kısmi**; ad tabanlı, `RESPECTED_WORKER_ENV_ALLOW` istisnası | `test_runner.py::test_worker_environment_drops_secrets_unless_allowed` |
| S-19 | Motor yükseltilmiş yönetici olarak çalışır | Operatör | B2/B4 işletim sistemi | Desteklenmez; worker başlamaz | **Engellenir (test)**; AppContainer yükseltilmiş veya doğrulanamayan oturumda `unsupported_elevated` ile reddeder | Bölüm 6; `test_worker_policy.py::test_elevated_session_never_starts_the_container`, `::test_unverifiable_session_never_starts_the_container` |
| S-20 | Worker kum havuzundan kaçmak için özyinelemeli alt süreç açar | Worker | B8 + B2 | Süreç ağacı ölür; AppContainer politikası alt süreçlere miras kalır | **Engellenir (test, Windows)**; `child_process_read_key` vakası ve öldürme testleri | `test_worker_security.py`; `test_windows_processes.py` |
| S-21 | MCP istemcisi `custom` worker, `apply_root` veya `engine_source` ister | MCP istemcisi | B1 MCP izin listesi | Varsayılan red | **Engellenir (test)** | `tests/interfaces/test_mcp_server.py` |
| S-22 | MCP istemcisi yanlış/eski `patch_sha256` ile `apply` çağırır | MCP istemcisi | B5 + B6 | Red | **Engellenir (test)** | `tests/interfaces/test_mcp_server.py` |
| S-23 | Worker, worktree dışına işaret eden symlink içeren yama üretir | Worker | B3/B5 yama güvenliği | Red | **Engellenir (test)**; `120000`/`160000` indeks modu güvensiz sayılır, kapsam ve export reddeder, apply çakışma döner | `test_worker_security.py::test_symlink_mode_patch_is_rejected_before_export_or_apply`; `test_frozen_security.py::test_frozen_engine_rejects_a_symlink_mode_patch_staged_without_symlink_privilege`; `engine/lanes.py` |
| S-24 | Kabul kodu ağ üzerinden dışarı veri sızdırır | Kabul kodu | B4 ağ | Varsayılan kapalı | **Engellenir (test, Windows)**; verify AppContainer'da ağ kapalı: IP, DNS, loopback ve alt süreç çıkışı reddedilir. Ağ istisnası yalnızca operatörün `RESPECTED_VERIFY_NETWORK_TASKS` ile adını verdiği görevde, hep-ya-hiç, kanıtta `network: allow`. AppContainer kurulamazsa verify çalışmaz | `tests/engine/test_sandbox.py` (ADR-018, FIX-04) |
| S-25 | Hub/MCP üzerinden insan onayı sahte bir düğmeyle verilir | Hub/MCP | B5/B6 | Yalnızca gerçek TTY oturumu | **Engellenir (test)** | `test_maf_coding.py`; MCP araç listesinde `maf-approve` yok |
## 6. Windows kullanıcı ve yönetici kararı

| Çalışma bağlamı | Karar | Gerekçe | Bugünkü uygulama |
|---|---|---|---|
| Windows normal kullanıcı (yükseltilmemiş) | **Desteklenir** | AppContainer yalnızca çalışma ağacı, araç dizinleri ve geçici alanı görür; kanıt/onay/sır erişilemez, ağ kapalı | `sandbox.run_check`; testli |
| Windows yönetici (yükseltilmiş) | **Desteklenmez** | Yönetici belirteci ve ayrıcalıkları bu modelin dışında; kısıtlı belirteç yine de yönetici gruplarını taşır | **Aktif ret:** AppContainer başlatıcısı yükseltilmiş belirteci görürse hiçbir worker başlatmaz; `unsupported_elevated` (`tests/engine/test_worker_policy.py`) |
| Windows admin olmayan ama UAC ile yükseltilmiş | Desteklenmez | Aynı gerekçe | **Aktif ret:** oturum doğrulanamıyor veya yükseltilmişse başlangıç fail-closed durur; sessiz sandbox'sız geri dönüş yok |
| macOS/Linux | **Desteklenmez (beta dışı)** | POSIX'te anahtar için işletim sistemi kum havuzu yok; `RESPECTED_ORCH_SANDBOX=off` tek yol | ARCHITECTURE §10; platform doğrulaması yok |

Karar, "yönetici olarak çalıştırırsan daha iyi olur" demek değildir. Tersi: yükseltilmiş bağlam bu ürünün tehdit
modelinin dışındadır. Motor bu bağlamı algıladığında fail-closed davranır ve worker başlatmaz.

## 7. Açıklanmamış güvenlik vaadi denetimi

Aşağıdaki tablo, ürünün güvenlik iddialarını tek yerde toplar. "Yok" satırları pazarlama metninde iddia edilmemelidir.

| İddia | Durum | Kanıt / sınır |
|---|---|---|
| `apply` doğrulanmamış, bayat veya kurcalanmış sonucu uygulamaz | **Var** | HMAC, `patch_sha256`, tazelik, `git apply --check`; `test_runner.py` |
| İnsan onayı ajan tarafından üretilemez | **Var (kimlik doğrulama değil)** | `RESPECTED_ORCH_CHILD`, TTY, patch bağı; `test_maf_coding.py` |
| Doğrulama kodu motorun sırlarını okuyamaz ve ağa çıkamaz | **Var (Windows)** | AppContainer, ağ kapalı; `test_sandbox.py` |
| Doğrulama kodu ağa çıkamaz | **Yok** | Kısıtlı belirteç ağı kapatmaz; SEC-03 |
| Worker işletim sistemi düzeyinde kapatılmıştır | **Var (Windows)** | AppContainer; `test_worker_security.py`, `test_worker_policy.py`; Windows dışında worker başlamaz |
| Worker ağı varsayılan olarak kapalıdır | **Var (Windows, worker)** | AppContainer `internetClient` vermez; operatör anahtarıyla açılan OpenCode/Cursor hariç. Doğrulama (kabul) kodu için **Yok** |
| Sırlar her yoldan temizlenir | **Kısmi** | Ad tabanlı ortam temizliği; dosya sistemi ve profil kapsanmaz |
| Aynı veri kökünde tek görev çalışır | **Var** | Kilit; ARCHITECTURE §2 |
| Yükseltilmiş yönetici desteklenir | **Yok** | Bölüm 6; aktif başlangıç reddi `test_worker_policy.py` ile testli |
| Hub/MCP insan onayı üretemez | **Var** | MCP araçlarında `maf-approve` yok; `orchestrator_apply` digest ister |

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

**Yorum:** Bu, SEC-01 anındaki (30 Ekim 2026) **tarihsel** ölçümdür; o gün motor worker süreci için OS düzeyinde dosya veya ağ
sınırı koymuyordu. Bu boşluklar SEC-03/SEC-04 ile AppContainer üzerinden kapatıldı (S-01, S-02, S-04, S-20; bölüm 5 ve 9);
P-04 (worktree içindeki `.env`) bilinçli olarak açık kalan sınırdır (S-03). Betik bugünkü motoru ölçmez.

## 9. Kanıt haritası

| Kanıt | Kapsadığı senaryolar |
|---|---|
| `tests/engine/test_sandbox.py` | S-24 ve verify sınırı: ağ çıkışı, anahtar/veri kökü erişimi, fail-closed; negatif kontrol aynı betiğin sınırsız bağlandığını gösterir. S-05..S-09 worker matrisiyle (`test_worker_security.py`) aynı AppContainer yolunda ölçülür |
| `tests/engine/security_cases.py` + `test_worker_security.py` | 21 negatif (19 worker içi + 2 dış) ve 9 izinli vaka; gerçek AppContainer, sandbox'sız kırmızı-takım kontrolü, özyinelemeli MCP ve symlink yaması |
| `tests/packaging/test_frozen_security.py` | Aynı worker matrisi, symlink yaması ve özyinelemeli MCP reddi paketlenmiş exe üzerinde |
| `tests/engine/test_security_gate.py` | Kayıt küçülemez; 13 zorunlu kategori ve ayrı worker/verify/frozen CI adımları zorunlu; `continue-on-error` yok |
| `tests/engine/test_runner.py` | S-10, S-11, S-12, S-13, S-18; kapsam, tazelik, imza, `apply` |
| `tests/engine/test_windows_processes.py` | S-17, S-20 (öldürme kısmı) |
| `tests/workflows/test_maf_coding.py` | S-07, S-14, S-15, S-16, S-25 |
| `tests/interfaces/test_mcp_server.py` | S-21, S-22 |
| `tests/packaging/test_frozen_build.py` | Paketlenmiş exe'de doğrulama ve kum havuzu yolu |

Doğrulama komutu: `python -m unittest discover -s tests -t .` (paketleme değişikliği yoksa build gerekmez).
Kanıt, test adı + çalışma tarihiyle birlikte sunulur; test adı belge cümlesine bağlanmaz.

## 10. Açık riskler ve sonraki görevler

| Risk | Etki | Kapatacak görev |
|---|---|---|
| Worker'ın ağaç dışı yazması ve ağ erişimi | Kullanıcı dosyaları ve dış sistemler | **Kapandı (SEC-03/SEC-04, test, Windows):** AppContainer; açık kalan: operatör anahtarıyla açılan Cursor/OpenCode ağı (B2a) |
| Kabul kodunun ağ erişimi | Dışarı sızma | SEC-03 |
| Yükseltilmiş yönetici bağlamı | Sınırın dışında çalışma | **Kapandı (SEC-03, test):** yükseltilmiş veya doğrulanamayan oturumda AppContainer başlatılmaz. |
| Symlink/gitlink yama varyantları | Workspace dışına yazım | **Kapandı (SEC-04, test):** `120000`/`160000` kapsam, export ve apply öncesi reddedilir. UNC/uzun yol worker okuma denemeleri AppContainer'da reddedilir. |
| Sağlayıcı kum havuzlarının sürüm farkı | Sessiz güven kaybı | SEC-02; sürüm ve CLI smoke testi |
| Onayın kimlik doğrulaması olmaması | Aynı kullanıcı hesabındaki başka süreç | Bilinen sınır; kimlik modeli ayrı ürün kararı |
| Tek veri kökünde tek görev | Paralellik kısıtı | EVAL/orkestrasyon görevleri |

## 11. Bakım kuralı

- Her yeni güvenlik iddiası bu belgeye bir satır ekler; testi yoksa "Kısmi" veya "Yok" yazılır.
- `sandbox.py`, `runner.py` (`apply`, `approve_maf_task`), `processes.py` veya MCP izin listesi değişirse bu belge
  aynı değişiklikte güncellenir.
- SEC-02/SEC-03 tamamlandığında B2 satırı ve S-01..S-04 yeniden sınıflandırıldı (4 Kasım 2026); S-03 (worktree içindeki `.env`) hâlâ "Yok"tur ve öyle kalmalıdır. S-24 (kabul kodunun ağı)
  FIX-04 testleri geçtiğinde "Engellenir" olarak yeniden sınıflandırıldı (ADR-018, 5 Kasım 2026).
- **CI sınırı (FIX-01):** hosted runner yükseltilmiş olduğundan güvenlik kümesi iş içinde oluşturulan geçici standart kullanıcıyla koşar
  (`tests/tools/run_security_as_user.ps1`), sıfır skip ister ve commit SHA'lı manifest üretir (`run_security_ci.py`). Kapı mantığı birim
  testlidir; **hosted koşunun kendisi bu depoda henüz bir GitHub koşusuyla kanıtlanmadı** (ROADMAP FIX-01 açık madde).

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
| D-13 | Terminal oturumu AppContainer dışında korumasız süreç açar | Renderer/ajan | B2, B9 | Oturum yalnızca sandbox yolundan açılır; kurulamazsa açılmaz | **Kısmen.** Chat: `opencode run` AppContainer içinde çalışmıyor (7 Kasım 2026 probu: varsayılan modda yerel servis portu çakışır, `--standalone` modunda çıktısız zaman aşımı), bu yüzden IPC yolu **varsayılan kapalıdır** ve yalnız operatör `RESPECTED_CHAT_UNSANDBOXED=allow` verirse açılır. Açıkken süreç sandbox dışındadır; dosya değiştiren, komut çalıştıran ve ağ araçları reddedilir (canlı kanıt: reddetme listesiyle `shell` isteği çalışmadı, kontrolde çalıştı), proje yapılandırması yok sayılır, süreç `RESPECTED_ORCH_CHILD` ile işaretlenir. PTY oturumu yok (ADR-024 koşullu GO). | B3-03.02; `test_session_control.py::SandboxGateTests`, `test_session_live.py` (isteğe bağlı) |

### 12.3 Yetkili eylem tablosu (sahip, kayıt, ret durumu)

| Eylem | Sahip | Kayıt | Reddedilme durumu |
|---|---|---|---|
| Okuma/durum | Renderer (salt okunur sınıf) | Denetim olayı | Belirteç yok → ret |
| Görev başlat/iptal | İnsan oturumu | Olay günlüğü | Yetki sınıfı yok → ret |
| Ayar değiştir | İnsan oturumu | Olay günlüğü | Sınıf uyuşmazlığı → ret |
| Onay/apply | Yalnızca human-presence authority | `maf-approval.json` + olay | Renderer/MCP/worker → ret, dosya oluşmaz |

Bu tablonun tamamlayıcısı B3-00.03'teki komut/yetki matrisidir.
