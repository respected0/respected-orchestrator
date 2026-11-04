# Orchestrator kullanım rehberi

Kurulumdan kaldırmaya kadar kişinin yapacağı her şey. Komutların tam listesi ve istek biçimleri
[COMMANDS.md](COMMANDS.md), iç yapı ve güvenlik sınırları [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Gerekenler

- Windows 10/11 (beta yalnızca Windows'u destekler).
- **Git**: her görev projenin yalıtılmış bir Git çalışma ağacında çalışır; proje bir Git deposu olmalıdır.
- Görevleri yapacak en az bir AI aracının komut satırı, **oturumu açık** olarak: Codex, Claude Code,
  Antigravity, Cursor ya da OpenCode. Kota ve hesap o aracındır.
- İsteğe bağlı: **OpenRouter** (okuma ve yazma görevleri; API anahtarı gerekir, profil olarak model adı verilir; model tam dosya içerikleri döndürür, motor yolları kapsamla denetleyip yazar). Anahtarı bir kez `provider-key set` ile girin
  (anahtar stdin'den okunur, komut satırına yazılmaz), ağ erişimini
  `RESPECTED_PROVIDER_NETWORK=allow` ve `RESPECTED_PROVIDER_CODE_GATE=1` ile açın, rolün aracını `openrouter`, profilini model adı
  (`provider-models --free` ücretsiz modelleri listeler; 429 gelirse çalışan en çok iki kez bekleyip yeniden dener) yapın.
- Python gerekmez. Brain ve Hub isteğe bağlıdır.

## 2. Kurulum

`RespectedOrchestrator-Windows-Setup.exe` kullanıcı başına kurulur, yönetici izni istemez. İlk sayfada iki yol vardır:

- **Respected Hub ile devam et (önerilen):** kurucu Hub'ı indirip kurar ve Orchestrator'ı Hub'ın kurulum sayfasında açar.
- **Yalnızca Orchestrator:** kurucu sırayla sorar:
  - **Varsayılan çalışan:** görevleri hangi AI aracının yapacağı. Her görevde ayrıca seçilebilir.
  - **Brain hafızası:** görevler Brain kasanızdaki notlardan kısa parçalar okuyabilsin mi; isterseniz ayrıca
    yeniden kullanılabilir notları Brain'in gelen kutusuna yazabilsin mi. Brain kurulu olmalıdır.

Kurucu, kurmadan önce "bilgisayarınızda neler olur" sayfasını gösterir: kurulumda, kullanırken, güncellemede ve kaldırmada neler yazıldığı, değiştiği ve silindiği. Aynı bilgi Hub'ın Kütüphane sayfasındaki ürün kartında da vardır (`packaging/windows/orchestrator_info.txt`).

Kurucu programı `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app` altına yazar ve ürünün `setup` komutunu çalıştırır.
Ayarlar ve görev çalışmaları `...\RespectedOrchestrator\data` altındadır. Yüklü uygulamalar girdisini kurucu yazar.

Sessiz kurulum aynı ayarları anahtarlarla alır. Başarısız olursa kurucu sıfırdan farklı bir çıkış koduyla (8) biter ve geriye
hiçbir şey bırakmaz; yarıda kesilirse yeniden çalıştırmak yeterlidir:

```text
RespectedOrchestrator-Windows-Setup.exe /VERYSILENT /SET=default_worker=claude /SET=default_timeout_seconds=1200
```

Kurulumdan sonra kontrol (`$exe` = kurulu programın tam yolu, PATH'e eklenmez):

```powershell
$exe = "$env:LOCALAPPDATA\Respected\RespectedOrchestrator\app\respected-orchestrator.exe"
& $exe --version
& $exe health      # Git, en az bir çalışan aracı, veri klasörü, motor anahtarı
& $exe status      # hangi çalışan araçları bulundu
```

## 3. Kurucuyu yeniden çalıştırmak

Ürün kuruluyken kurucu tek bir sayfa gösterir:

- **Onar / Güncelle:** program dosyaları bu kurucudaki sürümle yenilenir, ardından `repair` kaydı doğrular. Ayarlar ve
  görev çalışmaları korunur. **Güncelleme budur:** yeni sürümün kurucusunu çalıştırmak (sessiz: `/VERYSILENT`). Hub
  güncellemeyi kendisi önerir ve aynı kurucuyu çalıştırır.
- **Ayarları değiştir:** varsayılan çalışan ve hafıza sayfaları mevcut değerlerle açılır; kaydetmek `config set` ve
  `memory connect` ile aynıdır.
- **Kaldır:** bölüm 9.

## 4. İlk görev

Önce dosya değiştirmeyen bir **okuma görevi** deneyin. `istek.json`:

```json
{
  "project_root": "C:/yol/git/projesi",
  "task": "src klasörünü incele ve genel giriş noktalarını açıkla. Dosya değiştirme.",
  "kind": "read",
  "ownership": ["src"],
  "forbidden": [".env", "credentials"],
  "acceptance": [],
  "timeout_seconds": 300
}
```

```powershell
Get-Content -Raw istek.json | & $exe create      # -> {"run_id": "..."}
& $exe start RUN_ID                               # ayrık denetleyici; terminali kapatsanız da sürer
& $exe inspect RUN_ID                             # durum: queued -> running -> completed / failed / timed_out
```

Sonra bir **yazma görevi**. Yazma görevi en az bir doğrulama komutu ve değişecek dosyaları kapsayan `ownership` ister:

```json
{
  "project_root": "C:/yol/git/projesi",
  "task": "parse_date fonksiyonu boş metinde ValueError atsın; testini ekle.",
  "kind": "write",
  "ownership": ["src/dates.py", "tests/test_dates.py"],
  "acceptance": [["python", "-m", "pytest", "tests/test_dates.py", "-q"]],
  "timeout_seconds": 900
}
```

Çalışan, projenizin ayrı bir kopyasında (çalışma ağacı) çalışır; asıl projeniz değişmez. Görev bitince kopya ve onun Git dalı
(`orchestrator/<görev>`) silinir; sonuç yama olarak kayıtlıdır. Bittiğinde:

```powershell
& $exe check RUN_ID     # kapsam, doğrulama komutları, imzalı kanıt, yamanın projeye hâlâ uyması, projenin güncelliği
& $exe apply RUN_ID     # yalnızca check'ten geçen yamayı projenize uygular; commit atmaz
```

Yamayı uygulamadan önce `inspect` çıktısındaki değişikliklere bakın; uyguladıktan sonra her zamanki gibi `git diff` ile
inceleyip kendiniz commit edin. Başarısız bir görev `retry RUN_ID` ile yeniden denenir (toplam en fazla üç deneme);
`cancel RUN_ID` görevi ve bütün süreçlerini durdurur.

**Gözden geçirmeli iş akışı (MAF):** `maf RUN_ID` görevi uygulama, doğrulama ve gözden geçirme adımlarıyla yürütür;
düzeltme turları `max_fix_rounds` ile sınırlıdır (varsayılan 2, üst sınır 5). Gözden geçiren aracı
`default_reviewer_tool` ya da istekteki `workflow` belirler. Sonucu bir insan `maf-approve RUN_ID` ile onaylar
(etkileşimli terminal ister).

Daha büyük işler için: `plan` bir hedeften çok aşamalı bir proje taslağı çıkarır (başlatmaz), DAG/ownership
doğrulamasından geçen taslağı `spec` ve `dag` alanlarıyla kaydeder; `project-start` onu başlatır. Döngü, bilinmeyen
bağımlılık veya paralel ownership çakışması taslağı reddeder ve hiçbir worker başlamaz. `coordinate` aynı doğrulamayı
yapıp rol atamalarını da üretir; `command`, `auto_apply`, `allow_apply` veya `shell` öneremez, worker/proje/kampanya
başlatamaz ve apply edemez. Açık atama kullanılamıyorsa sessizce başka profile geçmez; `ROLE_UNAVAILABLE` döner. `campaign-start` birden çok paralel
hattı sınırlı eşzamanlılıkla (`max_parallel`, varsayılan `min(4, hat sayısı)`) yürütür; aynı proje kökünde ownership
çakışan hatları sıraya alır ve sonunda bir son inceleme yaptırır. `campaign-cancel ID` bekleyen/çalışan hatları iptal eder
ve son master'ı başlatmaz. Durumu `campaign-status ID` / `project-status ID`, listeyi `campaign-list`, projeyi durdurmayı
`project-cancel ID` verir. Bir görevin kanıt paketindeki çıktıyı (örneğin yamayı) `artifact RUN_ID` okur. Hub'ın konuştuğu protokol
`rpp` komutudur; elle kullanılmaz. `campaign-run` ve `project-run` denetleyicilerin giriş noktalarıdır. Biçimler: [COMMANDS.md](COMMANDS.md#projeler-ve-kampanyalar).

İki ayrı doğrulanmış sonucu birlikte denemek için `integrate` kullanın. Komut gerçek projede değil, geçici bir detached
worktree'de sıralı `git apply` ve tek birleşik doğrulama çalıştırır. Başarıda yalnızca karar kanıtı ve `combined.patch`
üretir; gerçek projeye uygulamak ayrı bir `apply RUN_ID` kararıdır.

**Çökme sonrası resume:** `project-resume ID`, projeyi checkpoint'teki `campaign`, `apply`, `verify`, `review` veya
`complete` sınırından sürdürür. Aynı operation ve aynı tamamlanmış iş yeniden ücretlendirilmez; imzalı `applied.json`
ile açıklanabilen apply tekrarlanmaz. Canlı bir süreç kilidi varsa resume reddedilir, yalnızca ölü/bozuk kilit temizlenir.
Kaynak dosyaları veya Git HEAD checkpoint'ten sonra değiştiyse, checkpoint adımı bilinmiyorsa ya da checkpoint
doğrulanamıyorsa önce terminalde insan onayı gerekir:

```powershell
& $exe project-approve PROJECT_ID
& $exe project-resume PROJECT_ID
```

Onay; proje, operation, checkpoint SHA-256'sı, kaynak parmak izi, HEAD ve onaylayan kişiye bağlıdır; bunlardan biri
değişirse yeniden onay gerekir. Onay yalnızca etkileşimli terminalden alınır; worker/alt süreç ve MCP self-approval
reddedilir. Resume onayı `auto_apply=false` aşamasının apply yetkisini genişletmez. Kaynakla çakışan eski patch
`stale patch` olarak bloke edilir ve zorla uygulanmaz.

## 5. Hub'dan kullanım

Hub → Orchestrator çalışma alanı:

| Sekme | Ne var |
|---|---|
| Genel bakış | Motorun durumu, bulunan çalışan araçları |
| Ajanlar ve modeller | Çalışan araçları ve rol atamaları |
| Kanıtlar | Seçilen çalışmanın kanıtı, incelemeleri ve sonraki adım |
| Kampanyalar | Kampanyaların ve hatlarının durumu |
| Görevler | **Yeni görev** formu (proje, görev, çalışan, iş türü, izin verilen ve yasak yollar, doğrulama komutları, süre), görev listesi, loglar, sonuç/yama; Başlat, Durdur, Yeniden dene, Sonucu doğrula |
| Ayarlar | Ayarlar formu, "Brain hafıza erişimi", "AI araçlarından kullan (MCP)" |

Hub'da yama uygulama düğmesi yoktur; doğrulanan yamayı `apply RUN_ID` komutuyla ya da bir AI aracından
`orchestrator_apply` ile uygularsınız. Görevler Hub kapansa da sürer; Hub yeniden açılınca durumu motordan okur.

## 6. AI aracından MCP ile kullanım

Orchestrator kendini AI araçlarına bir MCP sunucusu olarak kaydedebilir; o zaman örneğin Claude Code'a "şu işi Codex'e
yaptır, sonucu doğrula" diyebilirsiniz.

```powershell
& $exe integrations                              # hangi araçta kayıt var, hangisine eklenebilir
& $exe integrations set claude-code=on codex=on   # kaydet
& $exe integrations set codex=off                 # kaydı kaldır
```

İstemciler: `claude-code`, `claude-desktop`, `codex`, `cursor`, `windsurf`, `opencode`. Aynı işi Hub'da Orchestrator →
Ayarlar → "AI araçlarından kullan (MCP)" yapar (önce ne ekleneceğini gösterir). Ürün yalnızca kendi girdisini ekler ve kaldırır;
aracın ve sizin diğer ayarlarınız korunur. Kayıttan sonra AI aracını yeniden başlatın.

OpenCode çalışanı gerçek ACP oturumu kullanır ve sonucu güvenli biçimde ayrıştırır: çıplak JSON ya da tek bir
fenced JSON bloğu kabul edilir; fence dışındaki açıklama metni sorun değildir, ancak serbest metinden JSON çıkarılmaz.
Birden fazla fence, yarım fence, bozuk JSON ve geçersiz `status` başarısız sayılır. OpenCode ağ erişimi varsayılan
kapalıdır; `RESPECTED_OPENCODE_NETWORK=allow` yalnızca gerektiğinde verilir.

Cursor çalışanı Cursor'un kendi `node.exe` ve `index.js` girişiyle (`--trust --output-format json`) kum havuzu içinde
çalışır; `.cmd` kabuğu hiç çalıştırılmaz. Cursor'da oturumunuz açık olmalıdır. Ağ erişimi varsayılan kapalıdır ve
Cursor ağsız çalışamayacağından `RESPECTED_CURSOR_NETWORK=allow` verilmedikçe görev hızlıca `AUTH_REQUIRED` ile başarısız
olur; ağ açıkken yalnızca `auth.json` dosyanız o görev için yalıtılmış bir geçici kullanıcı klasörüne kopyalanır ve görev
sonunda silinir.
Ücretsiz (Free) planda yalnızca `auto` ve Grok 4.7/4.6 modelleri kullanılabilir.

AI aracı şu araçları görür: `orchestrator_status`, `orchestrator_plan`, `orchestrator_task_start`,
`orchestrator_project_start`, `orchestrator_list`, `orchestrator_progress`, `orchestrator_evidence`,
`orchestrator_resume`, `orchestrator_cancel`, `orchestrator_apply` ve (hafıza yazma izni varsa) `orchestrator_memory_note`.

**MCP'den verilen işlerin sınırları:** AI aracındaki model istem enjeksiyonuna uğramış olabilir; bu yüzden MCP üzerinden
özel çalışan komutu, başka bir uygulama klasörü ve otomatik uygulama reddedilir. Doğrulama komutları da yalnızca sizin
önceden izin verdiğiniz öneklerle başlıyorsa kabul edilir. Örneğin pytest'e izin vermek için:

```powershell
& $exe config set 'mcp_acceptance_allow=[["python","-m","pytest"]]'
```

Önekleri dar tutun: listelenen bir önek her argümana izin verir. İnsan onayı (`maf-approve`) MCP'den hiç yapılamaz.

## 7. Brain hafızası

Brain kuruluysa görevler kasanızdaki ilgili notlardan kısa parçalar alabilir.

```powershell
& $exe memory connect           # okuma izni (Brain'den izin alınır, Orchestrator'a kaydedilir)
& $exe memory connect --write   # ayrıca Brain gelen kutusuna not yazma
& $exe memory status
& $exe memory disconnect        # izni iptal eder
```

Hub'da aynı iş Orchestrator → Ayarlar → "Brain hafıza erişimi"dir. Bağlantı bir **izindir**, varsayılan değil:
bir görev hafızayı ancak istekte `"memory": {"use": true}` derse kullanır; isteğe bağlı `"query"` arama metnini belirler,
yoksa görevin ayırt edici kelimeleri kullanılır. En fazla yaklaşık 3000 karakter, güvenilmeyen veri olarak işaretlenmiş
şekilde görev metnine eklenir. Hafıza erişilemezse görev hafızasız çalışır.

Not parçaları o görevin çalışan modeline gider. Hafızayı yalnızca bunu kabul ettiğiniz projelerde kullanın. Yazma izni
varsa `orchestrator_memory_note` yeniden kullanılabilir bilgiyi Brain'de `🔮 850-Companion/Inbox/Orchestrator/`
altına yeni bir not olarak yazar; görev geçmişi yazılmaz.

## 8. Ayarlar

```powershell
& $exe config
& $exe config get default_worker
& $exe config set default_worker=claude default_timeout_seconds=1200
```

| Anahtar | Ne | Varsayılan |
|---|---|---|
| `default_worker` | Görevleri yapan AI aracı | `codex` |
| `default_worker_profile` | Çalışan aracın profili; boş: aracın varsayılanı | boş |
| `default_reviewer_tool` | İşi gözden geçiren AI aracı | `codex` |
| `default_reviewer_profile` | Gözden geçiren aracın profili | boş |
| `default_timeout_seconds` | Bir görevin en uzun süresi (saniye) | `900` |
| `default_roles` | Varsayılan rol atamaları, JSON (ör. `{"planner": {"tool": "claude"}}`) | boş |
| `auto_assign` | Atama yoksa geçmiş başarıya göre araç önerilsin | `false` |
| `auto_pool` | Otomatik atama adayları, JSON liste | boş |
| `require_independent_review` | Gözden geçiren, işi yapandan farklı olmalı | `false` |
| `mcp_acceptance_allow` | MCP ile verilen görevlerde izin verilen doğrulama komutu önekleri, JSON | boş |
| `blocked_profiles` | Hiçbir rolde kullanılmayacak profiller, virgülle | `mimo` |

Mantıksal değerler `true`/`false` yazılır; geçersiz bir değer hiçbir şey yazmaz. Gizli hafıza alanları (`memory_*`)
yalnızca `memory connect` ile yazılır. Rollerin nasıl seçildiği: [ARCHITECTURE.md](ARCHITECTURE.md#4-rol-atama).

## 9. Kaldırma

Kaldırma yolları: Windows **Yüklü uygulamalar** → Respected Orchestrator → Kaldır; kurucu → Kaldır; Hub → Orchestrator →
Kaldır; sessiz `unins000.exe /VERYSILENT [/PURGE=1]`. Kaldırıcı "Ayarlar ve çalışma verileri de silinsin mi?" diye sorar
(varsayılan Hayır) ve ürünün `uninstall [--purge]` komutunu çalıştırır.

| Ne | Kaldırınca |
|---|---|
| Program (`app\`) | kaldırıcı siler |
| AI araçlarındaki kendi MCP girdileri | kaldırılır (elle değiştirmiş olsanız da); diğer girdiler kalır |
| Kurulum kaydı | her zaman kalkar |
| Ayarlar, görev çalışmaları, kanıtlar | kalır; "Evet" / `--purge` / `/PURGE=1` ile silinir |
| Projeleriniz | hiçbir durumda dokunulmaz |

Brain hafıza bağlantısı varsa önce `memory disconnect` ile kapatmak izni Brain tarafında da iptal eder.

## 10. Sorun giderme

| Belirti | Bakılacak yer |
|---|---|
| `health` başarısız | Çıktıdaki kontrol: `git_available` (Git kurulu mu), `worker_cli` (en az bir AI aracı PATH'te mi), `data_root_writable`, `engine_key` (anahtar ilk görevde oluşur; henüz yoksa sorun sayılmaz, var ama okunamıyorsa sorundur) |
| `ROLE_UNAVAILABLE` | Seçilen aracın komut satırı bulunamadı ya da profil `blocked_profiles`'ta; `status` hangi araçların bulunduğunu gösterir |
| `ROLE_UNASSIGNED` | Gözden geçirici gibi gerekli bir rol için atama yok; `default_reviewer_tool` ya da istekte `workflow` verin |
| `ROLE_CONFLICT` | Aynı role iki farklı değer verilmiş (ör. `worker` ve `roles.implementer`) |
| Görev `failed`, `WORKER_FAILED` | Çalışanın çıktısı başarılı bir sonuç bildirmedi; `inspect` ve Hub'daki loglar. Kota ya da oturum hatası ayrıca belirtilir |
| `timed_out` | `timeout_seconds` ya da `default_timeout_seconds` artırın |
| Başka bir görev çalışırken yeni görev bekliyor | Aynı veri kökünde aynı anda tek görev çalışır; sıradaki görev kendi süresi içinde sıraya girer (`cancel` ile vazgeçilir) |
| Codex görevi `failed`; çalışan "erişim engellendi" diyor | Codex'in kum havuzu kullanıcı profilinizdeki programları (örneğin `AppData\Local\Programs` altındaki Python) çalıştıramaz; doğrulama komutunda sistem ya da `Program Files` altındaki bir programı kullanın. Doğrulamayı motor ayrıca kendi belirteciyle yapar |
| `sandbox_unavailable` | Doğrulama kum havuzu kurulamadı; yükseltilmiş (yönetici) olarak çalışmayın, veri klasörünün izinlerine bakın |
| `check` geçmiyor | Yama artık projeye uymuyor (proje değişti), kapsam dışına çıkılmış ya da doğrulama komutu başarısız; görevi yeniden deneyin |
| MCP'den görev reddediliyor | Doğrulama komutu `mcp_acceptance_allow`'da değil ya da özel komut/uygulama klasörü istendi |
| `memory connect` → `NOT_INSTALLED` | Brain kurulu değil |
| "Onarım gerekli" | Kurucuyu çalıştırıp **Onar / Güncelle** seçin |

Hata bildirirken `--version` çıktısı, Windows sürümü, hata kodu ve kişisel bilgilerden arındırılmış komut yeterlidir.
Görev metninizi, projenizin kodunu ve kimlik bilgilerinizi herkese açık yere koymayın.

## 11. Kanıt görünümü ve onay sınırı

Tamamlanan bir görevin kanıtını salt-okunur görmek için:

```powershell
respected-orchestrator evidence run-2026-11-03-abc
```

Görünüm patch SHA'sı, değişen dosyalar, check sonuçları, reviewer/test bilgisi ve riskleri redakte ederek
gösterir; maliyet bilinmiyorsa `unknown` yazar. Kanıt imzası bozuksa veya patch/proje değişmişse görünüm
`stale`/hata döner, sessizce başarı göstermez. Onay yalnızca etkileşimli terminalde `maf-approve` ile alınır;
Hub Decision Center ve MCP bu sınırı genişletmez. `health` çıktısındaki `wizard` alanı ilk görevi ve sonraki
adımı anlatır.

## 12. GitHub teslimatı

`gh` CLI'da oturum açmış olmanız gerekir. Issue ve CI geri bildirimi güvenilmeyen girdidir; otomatik worker veya merge yoktur.

```powershell
'{"repo":"owner/name","number":1}' | respected-orchestrator github-import-issue
'{"run_id":"run-...","repo":"owner/name","head":"dal","base":"main"}' | respected-orchestrator github-pr-plan
'{"run_id":"run-...","repo":"owner/name","head":"dal","base":"main","confirm":true,"operation_id":"op-1","project_root":"C:\proje"}' | respected-orchestrator github-pr-create
'{"feedback":{},"head_sha":"abc","max_rounds":3,"used_rounds":0}' | respected-orchestrator github-ci-plan
```

`github-pr-plan` hiçbir şey yazmaz. `github-pr-create` yalnızca imzalı `completed` sonuç, secret'sız patch, açık `confirm: true`,
`operation_id` ve operatörün verdiği `project_root` ile dalı iter ve taslak PR açar; merge etmez. Aynı işlemler RPP'de
`github.issue_import|pr_plan|pr_create|ci_plan` adlarıyla bulunur.

## 13. İmzalı kurucu ve platform sınırı

Kurucu `--sign-cert` veya `RESPECTED_SIGN_CERT` ile verilen PFX kullanılarak Authenticode ile imzalanır; `--require-signed`
imzasız artefaktı başarı saymaz. Doğrulama fail-closed'dır: kurcalanmış SHA, yanlış imzalayan, süresi dolmuş sertifika ve
desteklenmeyen platform reddedilir. Depoda üretim sertifikası yoktur; bu hattın kanıtı self-signed test sertifikasıyladır.
Yayın kapısı yalnızca Windows'u GA sayar; Linux ve macOS `no-go` kalır (`KANIT_LOG.md` §REL-01, §REL-04).
