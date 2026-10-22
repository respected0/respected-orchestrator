# Orchestrator mimarisi

Motorun nasıl paketlendiği, bir görevin nasıl doğrulandığı, hangi güvenlik sınırlarının uygulandığı ve hangi kuralların
bağlayıcı olduğu. Giriş ve komutlar: [README.md](../README.md). Üç ürünün ortak kuralları (kurucu, komutlar, ayarlar,
protokol) ekosistem kökündeki `docs/PRODUCT_CONTRACT.md` dosyasındadır; burada tekrarlanmaz.

## 1. Paketlenmiş motor

- `packaging/build_dist.py` motoru PyInstaller ile (onedir, içerik `app/` altında) `dist/RespectedOrchestrator/` klasörüne
  dondurur: `respected-orchestrator.exe` ve her dosyanın SHA-256'sını taşıyan `distribution.json`. Agent Framework'ün tembel
  alt modülleri toplanır; bildirilen bağımlılıkların dışındaki kurulu paketler dışarıda bırakılır, böylece yerel derleme
  temiz bir CI derlemesiyle aynı içeriği taşır. `_selfcheck` her modülü içe aktarır ve eksik olanda başarısız olur.
- Kurucu (`packaging/windows/orchestrator_setup.iss`) programı `app\` altına yazar ve `setup` çalıştırır; `setup` dosyaları
  `distribution.json` ile doğrulayıp kurulumu `app\.respected\install.json` olarak kaydeder. `manifest`'in `install_state`
  değeri bu kayıttan ve dosyaların şimdiki hash'inden gelir; Hub ve ürün "kurulu" ile "onarım gerekli" konusunda aynı şeyi
  söyler.
- Motor kendini her zaman `context.engine_command` ile yeniden başlatır: donmuşsa exe, kaynaktan
  `python -m respected_orchestrator`. Ayrık görev, proje ve kampanya denetleyicileri ve kısıtlı belirteçli doğrulama
  başlatıcısı (`_sandbox-exec`) bu yoldan geçer. Her alt süreç `engine/winproc` üzerinden açılır.
- `--data-root` yalnızca motorun kendi alt süreçleri içindir (her kampanya hattının kendi kökü vardır); yardımda görünmez.
  Kişiler ve testler `RESPECTED_DATA_DIR` kullanır.

## 2. Görev ve sonuç denetimi

- Her görev projenin yalıtılmış bir Git çalışma ağacında çalışır. Sonuç bir iddiadır: kapsam (`ownership` / `forbidden`),
  doğrulama komutları, yamanın projeye hâlâ uyması, imzalı kanıt ve projenin güncelliği ayrı ayrı geçmelidir. Hiçbir şey
  kendiliğinden uygulanmaz; `apply` `check`'i yeniden çalıştırır, `git apply --check` yapar, commit atmaz ve çalışan
  süreçlerin içinden reddedilir. Yeniden denemeler açık ve sınırlıdır; süre sınırları ve süreç ağacı temizliği korunur.
- Kanıt, veri kökündeki `.engine-key` ile HMAC imzalanır. Anahtar Windows'ta yalnızca kullanıcıya açık bir ACL ile korunur.
- **Codex sonucu:** yerleşik Codex uyarlayıcısı `exec --json` ile çalışır ve tam görev metnini tek argüman olarak verir
  (`--json` ile çağrılan `codex` adlı özel komutlar da aynı sözleşmeye tabidir). Çıktı yalnızca JSON nesnelerinden oluşan,
  `turn.completed` ile biten, `turn.failed` ya da `error` olayı içermeyen JSONL olmalıdır; son ajan mesajında açıkça başarılı
  bir `status` taşıyan bir JSON nesnesi bulunmalıdır. Yorum, engellenmiş yanıt, bozuk çıktı ya da eksik son olay, araç 0 ile
  çıksa bile doğrulamaya ilerlemez. Açık başarısızlık `WORKER_FAILED`; kota ve kimlik hataları kendi sınıflarını korur; zaman
  aşımı önceliklidir. Windows'ta projede `.runtime/codex-0.162.0-alpha.20/bin/codex.exe` varsa o tercih edilir, yoksa PATH.
  Motor ortak bir Codex kum havuzu kurmaz ya da onarmaz.
- Codex çalışanları `--sandbox workspace-write` ve `approval_policy="never"` ile başlar; kişinin `danger-full-access`
  ayarı devralınmaz. Çalışan, denetim ve gözden geçirme ortamlarından sır gibi görünen değişkenler çıkarılır
  (`RESPECTED_WORKER_ENV_ALLOW` ad başına açık istisnadır). İzin atlayan bayraklar (`--dangerously*`, `--yolo`,
  `bypassPermissions`, `danger-full-access`, `-y`, `--approval-mode yolo`, `sandbox_mode` geçersiz kılma) her yerde
  reddedilir.

## 3. Doğrulama kum havuzu

Doğrulama komutları (ve proje `verify` komutları) bir çalışanın yazdığı kod üzerinde çalışır. Bu kodun motorun yetkisini
taşımaması için komutlar `sandbox_exec` ile **kısıtlı bir belirteçle** (`CreateRestrictedToken` + `CreateProcessAsUser`)
çalışır:

- Belirteç kullanıcının bütün SID'lerini kısıtlayıcı SID olarak tutar (araçlar ve önbellekler aynı çalışır) ve bu veri
  köküne ait bir SID daha ekler (`sandbox.json`; hiçbir gerçek hesabın sahip olmadığı biçimli bir SID). Windows erişimi iki
  kez denetlediği için bu SID'e verilen **ret** kum havuzunu engeller, o SID'i taşımayan motoru etkilemez.
- `DISABLE_MAX_PRIVILEGE` yedekleme/geri yükleme/sahiplik alma ayrıcalıklarını kaldırır.
- Veri kökü bu SID'i bütün alt öğelerde (kalıtımlı), kökün kendisinde oluşturma/değiştirme/silme/ACL değiştirmede ve
  anahtar dosyasında reddeder. `workspaces/` (çalışanın alanı) kalıtımı keser ve kullanılabilir kalır.
- Bir **OWNER RIGHTS** girdisi sahibin örtük haklarını READ_CONTROL ile sınırlar; yoksa aynı kullanıcı WRITE_DAC'i korur ve
  kum havuzu erişimini geri verebilirdi (saldırı testiyle bulundu).
- Kurulamazsa çalışma `sandbox_unavailable` ile başarısız olur; sessiz geri dönüş yoktur. `RESPECTED_ORCH_SANDBOX=off`
  açık bir geliştirici anahtarıdır (Windows dışındaki tek yol).
- Kanıt (`tests/engine/test_sandbox.py`, negatif kontrolle): kum havuzundaki kod anahtarı okuyamaz (düz yol, `\\?\`,
  bağlantı noktası, sabit bağ), ayarları ve kanıtı okuyamaz, veri kökünde hiçbir şey oluşturamaz/değiştiremez/silemez,
  `maf-approval.json` sahteleyemez, ACL'yi ya da ret girdisini değiştiremez, sahiplik alamaz. Kum havuzu olmadan aynı
  denemelerin hepsi başarılı olur.
- Sınırlar: yalnızca motorun sırları ve kanıtı korunur; kod kişinin diğer dosyalarını okuyabilir ve ağa çıkabilir. Çalışan
  araçların (claude/codex/agy) kendisi bu belirteçle çalışmaz; kendi izin modları vardır. Yükseltilmiş yönetici olarak
  çalışan bir motor bu modelin dışındadır. Veri kökü başına ilk kullanımda bir PowerShell ACL kurulumu (yaklaşık bir
  saniye) yapılır.

## 4. Rol atama

Her uyumlu model, sağlayıcı ya da araç her role atanabilir; kod hiçbir zaman "X modeli yalnızca Y rolünü yapar"
demez. Kavramlar ayrıdır: **rol** (iş akışındaki görev, `^[a-z][a-z0-9_]{0,39}$`, açık küme: `implementer`, `reviewer`,
`deep_reviewer`, `planner`, `debugger`, `tester`, `coordinator`, `master`…), **profil** (motor için opak bir model
yapılandırması), **araç** (`codex`, `claude`, `gemini`, `agy`, `cursor`, `custom`) ve **atama** (`{tool, profile}` + kaynağı).

Her rol için öncelik:

1. **Açık atama** görev isteğinde: `roles: {rol: profil | {tool, profile, fallbacks}}` ya da `worker`, `worker_profile`,
   `workflow.reviewer_profile|reviewer_tool|deep_review_profile|deep_review_tool`. Aynı role iki farklı değer `ROLE_CONFLICT`.
2. **Ayarlardaki varsayılan:** `default_worker`, `default_worker_profile`, `default_reviewer_tool`,
   `default_reviewer_profile`, `default_roles`.
3. **Otomatik öneri**, yalnızca `auto_assign` açıksa, `auto_pool` adaylarından: yazma rolleri başsız düzenleyebilen bir
   araç ister; okuma rolleri `custom` kullanamaz; kullanılamayanlar gerekçesiyle `excluded`'da listelenir. Sıralama bu
   kurulumun kendi imzalı geçmişinden gelir (`track_record.py`): yumuşatılmış tamamlanma oranı, başka rolün kullanmadığı
   profil, daha düşük ortalama belirteç, havuz sırası. Her aday için 3'ten az kayıt varsa bu bir ölçüm değildir: ilk uygun
   aday alınır ve `basis: pool_order` olarak kaydedilir. Görev zorluğu ve fiyat modellenmez.

Belirtilmeyen `deep_reviewer` `reviewer`'dır. Çözülen atamalar ve kaynakları (`explicit` / `hub_default` / `auto`) imzalı
istekte `role_assignments` olarak saklanır.

- Açık seçim asla sessizce değiştirilmez: kullanılamayan atama `ROLE_UNAVAILABLE`'dır; yalnızca atamanın kendi
  `fallbacks` listesi devreye girer. Hiçbir kaynaktan atanmayan gerekli rol `ROLE_UNASSIGNED`; gözden geçirici, MAF
  akışının ücretli ilk adımından önce denetlenir.
- `require_independent_review` açıksa çalışanla aynı profili kullanan gözden geçirici `ROLE_INDEPENDENCE`'tır; kapalıysa
  izin verilir ve `role_notes`'a yazılır. `escalate_profile` sonraki düzeltmeleri başka profile verir, ilk çalışan gözden
  geçirici olur. `blocked_profiles` (varsayılan `mimo`) profilleri her rolde reddeder.
- Gözden geçirmeler atanan araçla yapılır: `codex` salt okunur kum havuzu yolunu kullanır; diğer araçlar boş bir kanıt
  klasöründe başsız çalışır. Bunların komut satırları belirteç kullanımı bildirmez; kullanım "bilinmiyor" kaydedilir
  (sıfır değil) ve hat bütçesinden varsayılan miktar düşülür.
- Tüketilen roller: `implementer`, `reviewer`, `deep_reviewer` (her görev), `debugger` (atandıysa düzeltme turları),
  `master` (kampanya/proje son incelemesi; açık `final.command` önceliklidir, ikisi birden `ROLE_CONFLICT`), `planner`
  (`plan` komutu: atanan araçla bir proje taslağı çıkarır, motorla doğrular, `drafts/`'a kaydeder, başlatmaz). `tester` ve
  `coordinator` henüz hiçbir aşamada kullanılmaz.

Kod: `workflows/roles.py`, `engine/runner.create_task`, `workflows/maf_workflow._review_assignment`, `interfaces/rpp.py`;
testler `tests/workflows/test_roles.py`.

## 5. Kampanyalar ve projeler

- `campaign-start` imzalı bir tanım saklar, motorun anlık görüntüsünü alır ve ayrık bir denetleyici (`campaign-run`)
  başlatır; çağıran çıkar, kimse sorgulamaz. `campaign-list` ve `campaign-status` durumu motordan okur.
- Her iş akışı hattı ayrı bir veri köküdür (kendi kilidi, anahtarı, durumu, çalışma ağaçları); hatlar gerçek paralel
  süreçlerdir, `after` bağımlılığı ifade eder. Bağımlılığı onaylanmamış hat `SKIPPED` olur. Hat veri kökleri ayar ya da
  hafıza anahtarı tutmaz; ana köke `RESPECTED_ORCH_MAIN_ROOT` ile bakar.
- Bütün hatlar bitince denetleyici imzalı `result.json` yazar ve son incelemeyi bir kez başlatır (`final.claim`).
  `final.allow_apply` isteğe bağlıdır ve yalnızca motorun kendi komut satırına izin verir.
- Git olmayan kaynaklar kampanya klasöründeki geçici bir Git aynasında geliştirilir (sırlar ve ağır klasörler hariç).
- Kaynaktan çalışırken denetleyici motorun anlık görüntüsünden çalışır (motor kendini geliştirebilir); paketlenmiş exe
  zaten değişmez bir kopyadır.
- `maf-approve` etkileşimli bir terminal ister; insan onayı hiçbir zaman MCP'den sunulmaz.

## 6. MCP sunucusu ve izinler

`respected-orchestrator mcp [--allow-auto-apply] [--allow-privileged]`, Hub'ın kullandığı motor işlevleri üzerinde
standart kütüphaneyle yazılmış bir stdio MCP sunucusudur; Hub gerekmez, başlattığı çalışmalar Hub'da görünür. Araçlar:
`orchestrator_status`, `_plan`, `_task_start`, `_project_start`, `_list`, `_progress`, `_evidence`, `_resume`, `_cancel`,
`_apply`, `_memory_note`. `integrations set İSTEMCİ=on` (ya da Hub'ın paneli) AI aracının ayarına kurulu programı
gösteren bir girdi ekler: `respected-orchestrator.exe mcp`. Başka girdiler korunur; kapatınca yalnızca kendi girdisi kalkar.

Sunucu, istem enjeksiyonuna uğramış olabilecek bir modelin isteğini alır. Bu yüzden MCP üzerinden
`orchestrator_task_start` ve `orchestrator_project_start` şunları reddeder:

- `worker: "custom"`, herhangi bir `command`, `apply_root`, `engine_source` — sunucu `--allow-privileged` ile
  kaydedilmedikçe. `--allow-auto-apply` yalnızca `auto_apply` reddini kaldırır. Hub ikisini de hiç vermez.
- Kişinin önceden onaylamadığı doğrulama ve `verify` komutları: `mcp_acceptance_allow` ayarındaki öneklerden biriyle
  kelimesi kelimesine başlamayan komut geçmez. Varsayılan liste boştur. Onaylı komutlar da doğrulama kum havuzunda çalışır.
- İzin atlayan bayraklar (bölüm 2).

Özyineleme yoktur: `RESPECTED_ORCH_CHILD` ya da `RESPECTED_ORCH_DELEGATED` tanımlıyken bütün araçlar gizlenir ve reddedilir;
sunucunun başlattığı her şey `RESPECTED_ORCH_DELEGATED=1` taşır. Çalışanlar yalıtılmış çalışma alanlarını düzenler; gerçek
ağaç yalnızca doğrulanmış `patch_sha256` ile `orchestrator_apply` üzerinden değişir.

Sınırlar: listelenen bir önek her argümana izin verir (`pytest -p eklenti` projeden kod çalıştırır); dar önekler yazın.
Aracı çağırıp çağırmamaya yine istemcinin kendi izin sorusu karar verir. `verify` girdisinin `cwd`'si kısıtlanmaz.

## 7. SecondBrain hafızası

Orchestrator SecondBrain'e hiçbir zaman bağımlı değildir; bağlantı yoksa aşağıdakilerin hiçbiri çalışmaz.

- **Bağlanma:** `memory connect [--write]` kurulu SecondBrain'in `rpp` sunucusundan `memory.grant` ile izin alır ve
  `memory_enabled`, `memory_write`, `memory_grant_id`, `memory_command` (`{"argv": [<respectedbrain.exe>, "rpp"], "env": {}}`)
  ve yalnızca yazılabilen `memory_token` ayarlarını `config set` ile aynı kodla yazar. Ayar yazılamazsa izin hemen iptal
  edilir; yarım bağlantı kalmaz. `memory disconnect` izni iptal eder ve alanları temizler.
- **Kullanım bir izindir, varsayılan değil:** `memory: {use: true, query?}` demeyen görev hafızayı okumaz. Bağlantı yokken
  `use: true` görev oluşturulurken hatadır. Çalışma anında yapılandırma yeniden denetlenir (kopan bağlantı kuyruktaki
  görevleri hemen etkiler), SecondBrain'e `memory.recall` sorulur (alt süreç, stdin'de bir istek, stdout'ta bir yanıt) ve en
  fazla yaklaşık 3000 karakterlik parça, güvenilmeyen veri olduğunu belirten bir başlık altında görev metnine eklenir.
  Sorgu `memory.query` ya da görevin ayırt edici kelimeleri (en fazla 12). Her hata yalnızca "hafıza yok" demektir.
- **Anahtar:** yalnızca `<veri kökü>/memory-token` dosyasındadır (`.engine-key` gibi ACL'li; Codex kum havuzu kullanıcıları
  okuyamaz). `settings.json`'da, makbuzlarda, istekte, durumda, kanıtta, günlükte, hata metninde ve görev metninde yer
  almaz; okumada `***set***` görünür. Alt sürece yalnızca stdin'den, en az ortamla verilir. `memory-context.json` yalnızca
  durum, sayı, göreli yollar, puanlar ve dizin durumunu kaydeder.
- **Yazma:** `orchestrator_memory_note` MCP aracı, her iki izin varsa (bağlantı `--write` ile ve SecondBrain tarafında yazma
  izni) yeniden kullanılabilir bilgiyi `memory.write` ile SecondBrain'in gelen kutusuna yeni not olarak yazar. Görev
  geçmişi yazılmaz.
- Kalan risk: parçalar o çalışmanın `brief.md` dosyasındadır (çalışan model görmek zorunda) ve çalışan, kişinin dosya
  erişimine sahip bir modeldir. Hafızayı yalnızca not parçalarının o modele gitmesini kabul ettiğiniz projelerde açın.

## 8. Ayarların saklanması

Ayarlar veri kökündeki `settings.json`'dadır (geçici dosya + atomik değiştirme). `settings.apply` birleştirir: verilmeyen
anahtarlar saklı değerini korur. Gizli anahtarda `***set***` ya da yokluk korur, `""` temizler. Geçerli her uygulama
`receipts/<operation_id>.json` makbuzu yazar (yalnızca işlem kimliği, zaman ve ayarların özeti, değerler değil); aynı
işlem kimliği aynı ayarlarla tekrarlanırsa saklı makbuz döner, farklı ayarlarla `OPERATION_ID_CONFLICT`. Bilinmeyen
anahtar hatadır.

## 9. Testler

| Klasör | Kapsam |
|---|---|
| `tests/engine/` | çalıştırıcı, çalışma ağaçları, Codex sonuçları, süre sınırları, kum havuzu, Windows süreçleri, bütçe, geçmiş |
| `tests/workflows/` | MAF iş akışı, kampanyalar, rol atama |
| `tests/interfaces/` | RPP, kurulum ve hafıza bağlantısı, MCP sunucusu ve izinleri, SecondBrain hafızası, AI aracı kayıtları |
| `tests/packaging/` | derlenmiş exe, PATH'te Python yokken: RPP, MCP, ayrık denetleyiciyle gerçek bir yazma görevi, kum havuzlu doğrulama |
| `tests/test_main.py` | komut satırı, ortak komutlar, hata biçimi |

Testler geçici depolarda ve sahte çalışanlarla çalışır; HOME yalıtılır. Paketleme testleri önce `packaging/build_dist.py`
ister; SecondBrain takımıyla aynı anda çalıştırmayın. CI derlenmiş exe'yi üretir ve iki takımı da zorunlu tutar.

## 10. Açık sınırlar

- Beta yalnızca Windows'u destekler; macOS/Linux kod yolları var ama doğrulanmadı. POSIX'te anahtar için işletim sistemi
  kum havuzu sınırı yoktur.
- Claude, Gemini ve Cursor çalışanları kendi onay modellerini korur. Sağlayıcının `turn.completed` olayı modeli
  bildirmediği için incelemelerde `model: null` görünür.
- Kapsam denetimi çalışmadan sonra yapılır; çalışanın kendisi kişinin izinleriyle çalışır.
- Kurucu Authenticode ile imzalı değildir.
