# Orchestrator: ne yaparsan nerede ne oluşur

Bu belge, Orchestrator'ı kurduğunda, AI araçlarına bağladığında, görev çalıştırdığında ve kaldırdığında **bilgisayarında hangi
dosyanın nerede, hangi şartla ve neden oluştuğunu** anlatır. Kod okunarak ve boş bir kullanıcı klasöründe doğrulandı
(2026-10-24, `0.1.0-beta.1`). Kullanım için [USAGE.md](USAGE.md), güvenlik sınırları için [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Tek bakışta

| Ne | Nerede | Kim oluşturur | Ne zaman |
|---|---|---|---|
| Program (`respected-orchestrator.exe`, kaldırıcı) | `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app` | Kurucu | Her kurulumda |
| Windows "Yüklü uygulamalar" kaydı | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{8E2B4D7A-61C3-4F09-A5D8-3B9E17C2F640}_is1` | Kurucu | Her kurulumda |
| Veri klasörü (ayarlar, kayıtlar, kanıtlar) | `%LOCALAPPDATA%\Respected\RespectedOrchestrator\data` | Orchestrator | Kurulumda klasör; içindekiler ilk kullanımda |
| MCP kaydı | AI aracının ayar dosyası (bölüm 3) | Orchestrator | **Yalnızca sen bağlarsan** ve araç kuruluysa |
| Görev çalışma ağacı ve dalı | Veri klasöründe `workspaces\<görev>` ve **projenin Git deposunda** `orchestrator/<görev>` dalı | Orchestrator | Görev çalışırken var; **görev bitince silinir** |
| Başlat menüsü, masaüstü kısayolu, zamanlanmış görev | yok | | Orchestrator arka planda çalışan bir servis ya da uygulama değildir |

Orchestrator **AI araçlarına hook, kural metni ya da beceri yazmaz**. Tek bağlantı biçimi bir MCP kaydıdır. Beceri metni
(`kod-orkestrasyon`) dosya olarak kopyalanmaz; MCP sunucusu aracı çağırınca iletir.

## 2. Kurulum

Kurucu sayfaları ve varsayılanları:

- **Kurulum yolu:** "Respected Hub ile devam et" (önerilen) ya da "Yalnızca Orchestrator".
- **Varsayılan çalışan:** Codex, Claude, Gemini, Antigravity, Cursor gibi hangi AI aracının görev yapacağı; ilki seçili gelir.
  Araç bilgisayarında kurulu olmalıdır; kurucu aracı **kurmaz**.
- **Brain hafızası:** "Brain hafızasını oku" ve "Gelen kutusuna not yazabilsin"; ikisi de **varsayılan kapalı**. Brain kurulu olmalıdır.

Kurucu **MCP sayfası sormaz**; AI araçlarına bağlantı kurulumdan sonra Hub'dan (Orchestrator → Ayarlar) ya da komutla yapılır.

Kurulum sırasında:

1. Kurucu programı `app` klasörüne açar, "Yüklü uygulamalar" kaydını yazar. Yönetici izni istemez. `%TEMP%` içinde kısa
   süreli `is-XXXX.tmp` klasörü açıp siler.
2. `respected-orchestrator setup` programı doğrular, kurulum kaydını (`distribution.json` ile eşleşen) yazar ve `data`
   klasörünü hazırlar. Seçtiğin varsayılan çalışan ve hafıza ayarları `settings.json` dosyasına yazılır.
3. Bir adım hata verirse ürün kendi değişikliklerini geri alır, kurucu program klasörünü ve "Yüklü uygulamalar" kaydını da
   siler (geriye hiçbir şey kalmaz) ve son sayfada "Kurulum tamamlanamadı" der. Kurucuyu yeniden çalıştırabilirsin. Sessiz
   kurulumda bu durumda **çıkış kodu 0 kalır** (Inno Setup kurulum sonrası adımda kod veremiyor); Hub sonucu ayrıca doğrular.

## 3. AI araçlarına bağlama (MCP)

Hub'da **Orchestrator → Ayarlar** ya da `respected-orchestrator integrations set <araç>=on`. Kayıt, aracın ayar dosyasında
`respected-orchestrator` adlı bir sunucudur ve `respected-orchestrator.exe mcp` komutunu çalıştırır. Sunucuyu araç gerektiğinde
kendi başlatır (stdio); arka planda sürekli çalışan bir şey yoktur.

| Araç | Dosya | Biçim |
|---|---|---|
| Claude Code | `~\.claude.json` | `mcpServers.respected-orchestrator` (`type: stdio`) |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | `mcpServers.respected-orchestrator` |
| Codex | `~\.codex\config.toml` | `[mcp_servers.respected-orchestrator]` tablosu |
| Cursor | `~\.cursor\mcp.json` | `mcpServers.respected-orchestrator` |
| Gemini CLI | `~\.gemini\settings.json` | `mcpServers.respected-orchestrator` |
| Windsurf | `~\.codeium\windsurf\mcp_config.json` | `mcpServers.respected-orchestrator` |

**Şart:** aracın ayar klasörü bilgisayarında var olmalı (`~\.claude`, `~\.codex`, `~\.cursor`, `~\.gemini`,
`~\.codeium\windsurf`, `%APPDATA%\Claude`). Kurulu olmayan bir aracı bağlamaya çalışırsan Orchestrator **reddeder**
("Client not detected on this computer") ve klasörünü **oluşturmaz**. Birden çok aracı birlikte istersen, biri reddedilirse
hiçbiri yazılmaz.

**Sahiplik:** yazdığı girdinin özetini `data\integrations.json` dosyasında tutar. Aracı kapatınca ya da kaldırınca yalnızca
**değişmemiş** kendi girdisini siler; sen girdiyi elle düzenlediysen "senin" sayılır, silinmez ve çakışma olarak bildirilir.
İşlem makbuzları `data\receipts\<işlem kimliği>.json` dosyalarına yazılır.

Bağlantıdan sonra AI aracını **yeniden başlat**; araç sunucuyu yalnızca açılırken görür. Claude'da eklentiler bölümünde
Orchestrator görünür, ona izin vermen gerekir.

## 4. Brain hafızasına bağlanma

Varsayılan **kapalı**. "Brain hafızasını oku" ya da `memory connect` açarsan:

- Orchestrator veri klasöründe `memory-token` dosyası oluşur (kullanıcıya özel erişim izniyle).
- Brain tarafında bu ürüne verilen izin kaydedilir (Brain'in kendi veri klasöründe).
- Görev başlayınca göreve uygun Brain notlarından en çok yaklaşık 3000 karakter, "güvenilmeyen veri" başlığıyla görev metnine
  eklenir. **Bu metin görevi yapan AI aracının sağlayıcısına gider.**
- "Gelen kutusuna not yazabilsin" ayrıca açıksa Brain'de `🔮 850-Companion\Inbox\Orchestrator` içine geri alınabilir not yazılır.

Kapatınca (`memory disconnect`) token ve izin kaydı kaldırılır.

## 5. Görev çalıştırınca ne oluşur

Bir görevi başlattığında (Hub, komut ya da AI aracı üzerinden):

| Ne | Nerede | Not |
|---|---|---|
| **Yalıtılmış çalışma ağacı** | `data\workspaces\<görev-adı>` | Projenin bir kopyası; çalışan AI aracı **burada** çalışır |
| **Git dalı** | Projenin deposunda `orchestrator/<görev-adı>` | `git worktree add -b ... HEAD` ile açılır |
| Çalışma ağacı kaydı | Projenin `.git\worktrees\<görev-adı>` klasörü | Git'in kendi kaydı |
| Görev durumu, günlükler | `data\` altında her çalışma için `process.json`, `stdout.log`, `stderr.log`, `events.jsonl`, `lane.json`, `baseline.json` | Hub ve komutlar buradan okur |
| Kanıt ve imza | `data\.engine-key` (ilk görevde), kanıt dosyaları | Kanıt bu anahtarla imzalanır; anahtar kullanıcıya özel ACL ile korunur |
| Çok görevli iş (kampanya) | `data\campaigns\<kimlik>\` | Her hat kendi veri köküne sahiptir |
| Kum havuzu | Veri klasörüne **reddetme ACL'i** | İlk kullanımda bir PowerShell ACL kurulumu (yaklaşık 1 sn); doğrulama komutları kısıtlı belirteçle çalışır |

**Projenin kendi dosyalarına** dokunulmaz: sonuç bir **yama** olarak hazırlanır ve siz `apply` demeden projeye uygulanmaz.
Ama görev çalışırken projenin **Git deposuna** iki şey eklenir: `orchestrator/<görev-adı>` dalı ve çalışma ağacı kaydı.
**Görev bitince** (tamamlansın, başarısız olsun, iptal edilsin ya da zaman aşımına uğrasın) Orchestrator ikisini de ve
çalışma ağacı klasörünü **siler**; sonuç `worker.patch` dosyasında ve imzalı kayıtta durur, `apply` yamadan çalışır. Bu yüzden
görev geçmişi çoğalsa da deponda `orchestrator/*` dalı birikmez. Yalnızca görev **zorla öldürülürse** (bilgisayar kapanır,
süreç sonlandırılır) bir dal ve klasör kalabilir; `git worktree prune` ve `git branch -D orchestrator/<görev>` temizler.

Çalışan AI aracı (Codex, Claude, Gemini, Antigravity, Cursor) **kendi** komut satırıyla çalıştırılır; o aracın kendi oturum
geçmişi ve günlükleri **kendi klasörlerine** (`~\.codex`, `~\.claude` vb.) yazılır. Bunlar Orchestrator'ın değil, aracın dosyalarıdır.

## 6. Güncelleme ve onarım

- **Onar / Güncelle:** programı yenisiyle değiştirir; çalışan süreçler durdurulur; ürün kendini onarır (dosyaları doğrular,
  AI araçlarındaki MCP kaydını yeni sürüme göre yeniler).
- Kurucu güncellemeden önce eski programı ve veri dosyalarını `%LOCALAPPDATA%\Respected\RespectedOrchestrator\update-backup`
  klasörüne yedekler; ters giderse geri yükler, tamamlanınca yedeği siler.

## 7. Kaldırma

| Ne | Sonuç |
|---|---|
| Program klasörü, "Yüklü uygulamalar" kaydı, kurulum kaydı | **Silinir** |
| AI araçlarındaki MCP girdileri | Değişmemiş olanlar **silinir** (bölüm 3) |
| Brain'e verdiğin hafıza izni | Kaldırma bunu **iptal etmez**; Brain'de iz kalmaması için kaldırmadan önce `memory disconnect` (ya da Hub'da Ayarlar'dan kapat) |
| Ayarlar, görev geçmişi, kanıtlar, çalışma ağaçları (`data`) | **Kalır**; "çalışma verileri de silinsin" ya da `uninstall --purge` ile silinir |
| **Projelerin ve Git depoların** | **Dokunulmaz.** Biten görevlerin dalı ve çalışma ağacı zaten silindi; yalnızca zorla öldürülen bir görevin kalıntısı varsa `git worktree prune` temizler |

## 8. Sık sorulanlar

**`.claude.json`, `.claude`, `.codex` bizden mi?** Yalnızca o araç kuruluysa ve onu sen bağladıysan **içine** bir `mcpServers`
girdisi yazarız. Kurulu olmayan aracın klasörünü **oluşturmayız**.

**Hiçbir şey bağlamadım, yine de bir şey oluştu mu?** Evet, ama yalnızca bölüm 1'in ilk üç satırı ve boş bir `data` klasörü.
AI araçlarının dosyalarına dokunulmaz.

**Ne gönderiliyor?** Bkz. [PRIVACY.md](../PRIVACY.md): görev metni ve çalışanın okuduğu dosyalar yalnızca senin seçtiğin AI aracının sağlayıcısına gider.
