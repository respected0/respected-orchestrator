# Orchestrator kullanım rehberi

Kurulumdan kaldırmaya kadar kişinin yapacağı her şey. Komutların tam listesi ve istek biçimleri
[COMMANDS.md](COMMANDS.md), iç yapı ve güvenlik sınırları [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Gerekenler

- Windows 10/11 (beta yalnızca Windows'u destekler).
- **Git**: her görev projenin yalıtılmış bir Git çalışma ağacında çalışır; proje bir Git deposu olmalıdır.
- Görevleri yapacak en az bir AI aracının komut satırı, **oturumu açık** olarak: Codex, Claude Code, Gemini CLI,
  Antigravity ya da Cursor. Kota ve hesap o aracındır.
- Python gerekmez. Brain ve Hub isteğe bağlıdır.

## 2. Kurulum

`RespectedOrchestrator-Windows-Setup.exe` kullanıcı başına kurulur, yönetici izni istemez. İlk sayfada iki yol vardır:

- **Respected Hub ile devam et (önerilen):** kurucu Hub'ı indirip kurar ve Orchestrator'ı Hub'ın kurulum sayfasında açar.
- **Yalnızca Orchestrator:** kurucu sırayla sorar:
  - **Varsayılan çalışan:** görevleri hangi AI aracının yapacağı. Her görevde ayrıca seçilebilir.
  - **Brain hafızası:** görevler Brain kasandaki notlardan kısa parçalar okuyabilsin mi; isterseniz ayrıca
    yeniden kullanılabilir notları Brain'in gelen kutusuna yazabilsin mi. Brain kurulu olmalıdır.

Kurucu, kurmadan önce "bilgisayarınızda neler olur" sayfasını gösterir: kurulumda, kullanırken, güncellemede ve kaldırmada neler yazıldığı, değiştiği ve silindiği. Aynı bilgi Hub'ın Kütüphane sayfasındaki ürün kartında da vardır (`packaging/windows/orchestrator_info.txt`).

Kurucu programı `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app` altına yazar ve ürünün `setup` komutunu çalıştırır.
Ayarlar ve görev çalışmaları `...\RespectedOrchestrator\data` altındadır. Yüklü uygulamalar girdisini kurucu yazar.

Sessiz kurulum aynı ayarları anahtarlarla alır:

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

- **Onar / güncelle:** program dosyaları bu kurucudaki sürümle yenilenir, ardından `repair` kaydı doğrular. Ayarlar ve
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

Çalışan, projenizin ayrı bir kopyasında (çalışma ağacı) çalışır; asıl projeniz değişmez. Bittiğinde:

```powershell
& $exe check RUN_ID     # kapsam, doğrulama komutları, imzalı kanıt, yamanın projeye hâlâ uyması, projenin güncelliği
& $exe apply RUN_ID     # yalnızca check'ten geçen yamayı projenize uygular; commit atmaz
```

Yamayı uygulamadan önce `inspect` çıktısındaki değişikliklere bakın; uyguladıktan sonra her zamanki gibi `git diff` ile
inceleyip kendiniz commit edin. Başarısız bir görev `retry RUN_ID` ile yeniden denenir (toplam en fazla üç deneme);
`cancel RUN_ID` görevi ve bütün süreçlerini durdurur.

**Gözden geçirmeli iş akışı (MAF):** `maf RUN_ID` görevi uygulama, gözden geçirme ve en fazla iki düzeltme turuyla yürütür;
gözden geçiren aracı `default_reviewer_tool` ya da istekteki `workflow` belirler. Sonucu bir insan `maf-approve RUN_ID` ile
onaylar (etkileşimli terminal ister).

Daha büyük işler için: `plan` bir hedeften çok aşamalı bir proje taslağı çıkarır (başlatmaz), `project-start` onu
başlatır; `campaign-start` birden çok paralel hattı yürütüp sonunda bir son inceleme yaptırır. Biçimler: [COMMANDS.md](COMMANDS.md#projeler-ve-kampanyalar).

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

İstemciler: `claude-code`, `claude-desktop`, `codex`, `cursor`, `gemini`, `windsurf`. Aynı işi Hub'da Orchestrator →
Ayarlar → "AI araçlarından kullan (MCP)" yapar (önce ne ekleneceğini gösterir). Ürün yalnızca kendi girdisini ekler ve kaldırır;
aracın ve sizin diğer ayarlarınız korunur. Kayıttan sonra AI aracını yeniden başlatın.

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
| AI araçlarındaki kendi MCP girdileri | kaldırılır; diğer girdiler kalır |
| Kurulum kaydı | her zaman kalkar |
| Ayarlar, görev çalışmaları, kanıtlar | kalır; "Evet" / `--purge` / `/PURGE=1` ile silinir |
| Projeleriniz | hiçbir durumda dokunulmaz |

Brain hafıza bağlantısı varsa önce `memory disconnect` ile kapatmak izni Brain tarafında da iptal eder.

## 10. Sorun giderme

| Belirti | Bakılacak yer |
|---|---|
| `health` başarısız | Çıktıdaki kontrol: `git_available` (Git kurulu mu), `worker_cli` (en az bir AI aracı PATH'te mi), `data_root_writable`, `engine_key` |
| `ROLE_UNAVAILABLE` | Seçilen aracın komut satırı bulunamadı ya da profil `blocked_profiles`'ta; `status` hangi araçların bulunduğunu gösterir |
| `ROLE_UNASSIGNED` | Gözden geçirici gibi gerekli bir rol için atama yok; `default_reviewer_tool` ya da istekte `workflow` verin |
| `ROLE_CONFLICT` | Aynı role iki farklı değer verilmiş (ör. `worker` ve `roles.implementer`) |
| Görev `failed`, `WORKER_FAILED` | Çalışanın çıktısı başarılı bir sonuç bildirmedi; `inspect` ve Hub'daki loglar. Kota ya da oturum hatası ayrıca belirtilir |
| `timed_out` | `timeout_seconds` ya da `default_timeout_seconds` artırın |
| `sandbox_unavailable` | Doğrulama kum havuzu kurulamadı; yükseltilmiş (yönetici) olarak çalışmayın, veri klasörünün izinlerine bakın |
| `check` geçmiyor | Yama artık projeye uymuyor (proje değişti), kapsam dışına çıkılmış ya da doğrulama komutu başarısız; görevi yeniden deneyin |
| MCP'den görev reddediliyor | Doğrulama komutu `mcp_acceptance_allow`'da değil ya da özel komut/uygulama klasörü istendi |
| `memory connect` → `NOT_INSTALLED` | Brain kurulu değil |
| "Onarım gerekli" | Kurucuyu çalıştırıp **Onar / güncelle** seçin |

Hata bildirirken `--version` çıktısı, Windows sürümü, hata kodu ve kişisel bilgilerden arındırılmış komut yeterlidir.
Görev metninizi, projenizin kodunu ve kimlik bilgilerinizi herkese açık yere koymayın.
