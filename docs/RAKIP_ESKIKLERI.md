# Rakiplerde olup bizde olmayan özellikler

Tarih: 2026-11-08. Bu belge bir **yol haritası girdisidir**, bağlayıcı mimari kural değildir (bağlayıcı olan `ARCHITECTURE.md`).
Her madde bittiğinde `ARCHITECTURE.md` / `COMMANDS.md` güncellenir ve buradaki durum işaretlenir.

## 0. Kaynaklar ve güvenilirlik

| Ürün | Ne | Bilgi kaynağı (resmî) | Güven |
|---|---|---|---|
| Claude Code masaüstü (Claude uygulamasının Code sekmesi) | Anthropic | `code.claude.com/docs/en/desktop` (tam sayfa indirildi, başlıklar ve bölüm girişleri okundu) | Yüksek |
| Claude Code CLI | Terminal sürümü | Aynı sayfadaki "Coming from the CLI?" karşılaştırması + kendi bilgim | Orta-yüksek |
| Codex (ChatGPT masaüstü uygulamasındaki Codex kipi) | OpenAI | `learn.chatgpt.com/docs/` altında: `agent-approvals-security`, `automations`, `code-review`, `environments/git-worktrees`, `agent-configuration/subagents`, `windows/windows-app` (indirildi, başlıklar ve girişler okundu). Not: Codex uygulaması "ChatGPT desktop app" içine taşınmış | Yüksek (başlıklar), orta (ayrıntılar) |
| Codex CLI | Terminal sürümü | Aynı belge seti (`Codex CLI` bölümleri) | Orta |
| DeepSeek Harness (`dsh`) | Resmî DeepSeek harness'ı, MIT, TypeScript, "developer preview" | `github.com/deepseek-ai/deepseek-harness`: README, `docs/architecture.md`, `docs/user/guide/*` başlıkları, `packages/` klasör adları | Yüksek (yapı), orta (davranış) |
| Orchestrator.inc | Ajan filosu yöneticisi, Apache-2.0, TypeScript | `github.com/OrchestratorInc/agent-orchestrator` README (iddialar README'dedir, denenmedi) | Orta-yüksek |

Hiçbir ürünü çalıştırıp denemedim; "var" resmî belgede veya README'de yazıyor demektir.

Not: `dsh` paketlerinin içeriğini (alt dokümanları) okumadım; yalnız paket adlarından ve mimari belgeden çıkardım. Özellik
"var" demek, README'de iddia edildiği anlamına gelir; çalışıp çalışmadığı doğrulanmadı.

## 1. Bizde ne var, ne yok (kısa özet)

Motor (Python) güçlü: işçiler (Codex, Claude, Cursor, OpenRouter), worktree, kampanya, plan, inceleme, DAG, bütçe/başarı kaydı,
rol atama, Brain hafızası, MCP sunucusu, onay merkezi. **Masaüstü ise ağırlıklı olarak salt okunur bir izleyici**:
görev/proje başlatamıyor, pano yok, ayarlar boş. Sohbet yalnız `opencode` ile ve dosya değiştirmeden çalışıyor.

Bizim farkımız (korunacak): telemetri yok; yerel veri; ajanın veya MCP istemcisinin kendi kendine kip değiştirememesi (kipi yalnız kullanıcı seçer).

**Karar (2026-11-08, kullanıcı):** Önceki "onay yalnız yerel pencerede, hiçbir şey otomatik onaylanmaz" kuralı gerçek kullanım için gerçekçi değil. Kullanıcıya `Manuel`den `İzinleri atla`ya kadar tüm izin kipleri sunulur ve kullanıcı istediğini seçer (B3). Kuralın korunan kısmı: kipi **kullanıcı** seçer; ajan, model çıktısı veya MCP istemcisi kendi kipini yükseltemez.

---

## 1b. Karşılaştırma tablosu (güncel)

Sütunlar: **Biz** (masaüstü + motor), **CC-App** Claude Code masaüstü, **CC-CLI**, **Cx-App** Codex uygulaması, **Cx-CLI**, **dsh** DeepSeek Harness,
**AO** Orchestrator.inc. ✓ var, ◐ kısmen/belirsiz, ✗ yok, ? doğrulanamadı.

| Özellik | Biz | CC-App | CC-CLI | Cx-App | Cx-CLI | dsh | AO |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dosya düzenleme ve komut çalıştırma | ✗ (sohbette bilerek kapalı; işçi hattında ✓) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (ajanlar) |
| Onay kipleri (salt-okunur / onaylı / tam) | ✗ | ✓ (Manual, Accept edits, Plan, Auto, Bypass) | ✓ | ✓ (salt-okunur / workspace-write + on-request / never) | ✓ | ✓ | ◐ |
| İzin kuralları (izin / yasak listesi) | ✗ | ✓ | ✓ | ◐ | ◐ | ✓ | ✗ |
| Sandbox | ✗ (kaldırılacak, karar §6; ajanın kendi sandbox'ı kullanılır) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Canlı akış | ✗ (1 sn yoklama) | ✓ | ✓ | ✓ | ✓ | ✓ | ◐ |
| Geri alma / kontrol noktası | ✗ (motorda `checkpoint.py` var, ekranda yok) | ✓ | ✓ | ◐ | ◐ | ✗ (belgede yok) | ◐ |
| Proje talimat dosyası | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ◐ |
| Alt ajanlar / paralel çalışma | ✗ (sohbette) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (30'a kadar) |
| Her ajana ayrı git worktree | ◐ (motorda ✓, ekranda ✗) | ✓ | ◐ | ✓ | ✓ | ◐ (`worktrees`, deneysel, varsayılan kapalı) | ✓ |
| Hook'lar | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| MCP kullanma | ◐ (salt okunur liste) | ✓ | ✓ | ✓ | ✓ | ✓ | ◐ |
| Eklenti / beceri / eğik çizgi komutu | ✗ | ✓ | ✓ | ◐ | ◐ | ✓ | ✗ |
| Çoklu ajan / sağlayıcı desteği | ✗ (sohbette yalnız opencode; işçilerde ✓) | ✗ | ✗ | ✗ | ✗ | ✓ (LLM adaptörleri) | ✓ (35+) |
| Birden çok oturumu tek panelde izleme | ◐ | ✓ (kenar çubuğu) | ✗ | ✓ (iş parçacıkları) | ✗ | ◐ | ✓ (pano) |
| PR açma, CI izleme, otomatik düzeltme | ✗ | ✓ (Auto-fix, Merge when ready) | ◐ | ◐ (PR inceleme eklentisi; yorum/birleştirmeyi kendisi yapmaz) | ◐ | ◐ (`github-review`) | ✓ |
| Oturum devam ettirme | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Maliyet / token takibi | ✓ (motorda) | ✓ | ✓ | ◐ | ◐ | ✓ | ◐ |
| Uzun bağlam yönetimi ve sıkıştırma | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Başsız / CI kipi | ✗ (motor `rpp` komutları var, sohbet için yok) | ✗ | ✓ | ✗ | ✓ (`exec`) | ✓ | ✓ |
| Kendini MCP sunucusu yapma | ◐ (motorun MCP sunucusu var, sohbet için yok) | ✗ | ✓ | ✗ | ✗ (`codex mcp-server` kaldırıldı; yerine app server) | ? | ✗ |
| Bildirim | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ (+mobil) |
| Görsel diff incelemesi + satır yorumu | ◐ (diff paneli var, yorum ve kabul/geri alma yok) | ✓ | ✗ | ✓ (inceleme bölmesinde satır içi yorumlar) | ✗ | ? | ✓ |
| Gömülü tarayıcı / uygulama önizleme | ◐ (`preview.rs`) | ✓ | ✗ | ✓ (tarayıcı + bilgisayar kullanımı) | ✗ | ✓ (`browser-use`) | ✓ |
| Gömülü terminal ve dosya düzenleyici | ◐ (terminal ve dosya paneli var, düzenleyici yok) | ✓ | – | ✓ (entegre terminal) | – | ✓ | ✓ |
| Zamanlanmış görevler + inceleme kuyruğu | ✗ (motorda iz var) | ✓ (scheduled tasks) | ✗ | ✓ (Scheduled görünümü bir gelen kutusu; Gmail/Slack/GitHub olay tetikleyicileri) | ✗ | ✓ (`schedule`) | ◐ |
| Yan sohbet (ana bağlamı kullanır, geri yazmaz) | ✗ | ✓ | ✗ | ✓ (`/side`, Ctrl/⌘+Alt+S) | ✗ | ? | ✗ |
| SSH / uzak oturum | ✗ | ✓ | – | ✓ (SSH üzerinden uygulama) | – | ✓ | ✗ |
| CLI oturumunu uygulamaya taşıma | ✗ | ✓ (`/desktop`) | – | ? | – | ✗ | ✓ (ajanın kendi terminal arayüzü) |
| Mobil / bulut | ✗ | ◐ | ✗ | ◐ (bulut tetikleyici planlı) | ✗ | ✗ | ✓ |
| Sesle giriş | ✓ | ✗ (belgede yok) | ✗ | ✓ (uygulama içi dikte) | ✗ | ✓ (`voice-input`) | ✗ |
| Ekran görüntüsü ekleme (onaylı) | ✓ | ✓ (görsel/PDF ekleme, sürükle-bırak) | ✗ | ? | ✗ | ✓ (`attachment`) | ✗ |
| Oturum ayrıntı paneli (bağlam %, değişiklikler, çalışan işler, çalıştığı yer) | ◐ (token/model var, bağlam % yok) | ✓ (kartlar) | ✗ | ◐ (`/status`: bağlam, hız sınırı) | ✗ | ✓ (`token-meter`) | ◐ |
| Sürükle-bırak bölme düzeni (sohbet, diff, tarayıcı, terminal, dosya, plan, görev, alt ajan) | ◐ (sabit paneller) | ✓ | – | ? (belgede bulunamadı) | – | ◐ | ◐ |
| Arka plan işleri bölmesi (alt ajan, kabuk, iş akışı) | ✗ | ✓ | ✗ | ◐ | ✗ | ✓ (`jobs`) | ✗ |
| Oturumlar arası mesajlaşma ("hangi oturum auth'a dokundu?") | ✗ | ✓ | ✗ | ? (belgede bulunamadı) | ✗ | ◐ (`team`) | ✓ |
| Ajanın önerdiği görevler | ✗ | ✓ | ✗ | ✗ (belgede yok) | ✗ | ? | ✗ |
| Ağ proxy ve alan adı izin listesi | ✗ | ✓ (yönetilen ayarlar) | ✓ | ✓ (komut ağ proxy'si) | ✓ | ✓ (`network-proxy`) | ✗ |
| Kural dosyası: sandbox dışı çalışacak komutlar | ✗ | ✓ | ✓ | ✓ (Rules) | ✓ | ✓ (`guard`) | ✗ |
| Korunan yollar (`.git` salt okunur) | ? (işçilerde kapsam denetimi var) | ? | ? | ✓ | ✓ | ? | ✗ |
| Yerel ortam / kurulum betikleri (worktree başına) | ✗ | ✓ (saved environments) | ✗ | ✓ (local environments) | ✗ | ✗ | ◐ |
| Bilgisayar kullanımı (computer use) | ✗ | ✓ | ✓ (macOS) | ✓ | ? | ✓ (`computer-use`) | ✗ |
| Sağlayıcı / model ayar ekranı | ✗ (yalnız model seçici) | ◐ (ağ geçidi) | ✓ | ◐ | ✓ | ✓ (Settings → Models) | ✓ |
| Eklenti pazarı / yöneticisi | ✗ | ✓ (plugin manager) | ✓ | ✓ | ✓ | ✓ (`plugin-market`) | ✗ |
| Python SDK / herkese açık dağıtım | ✗ | ✓ (Agent SDK) | ✓ | ✓ (Codex SDK) | ✓ | ✓ | ✗ |
| Görünüm kipleri (döküm ayrıntı düzeyi) | ✗ | ✓ | ✗ | ? | ✗ | ? | ✗ |
| Oturuma klasör ekleme | ✗ | ✓ | ✓ | ✓ (ek yazılabilir kökler) | ✓ | ✓ | ✗ |
| Telemetri yok | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ (`product-telemetry`, `otel` alt sistemleri var) | ✗ |
| Ajan ekipleri (lider + ortak görev listesi) | ✗ | ✗ (yalnız CLI; masaüstünde "dynamic workflows") | ✓ | ◐ (alt ajanlar) | ◐ | ✓ (`agent-team`) | ✓ |
| Sohbet sabitleme, yeniden adlandırma, arama, arşiv | ✗ | ✓ (gruplama, sıralama, arama, arşiv) | – | ✓ (sabitle, adlandır, ara) | – | ◐ (`session-title`, `session-query`) | ? |

"?" belgede bulunamayan veya doğrulanamayan hücrelerdir; bu satırlara dayanarak karar verilmemeli.

Doğrulama notu (2026-11-08): önceki sürümdeki iki iddia yanlıştı. (1) Codex CLI'ın kendini MCP sunucusu yapması: `codex mcp-server` komutu kaldırılmış (resmî belge), eski üçüncü taraf yazılar bunu hâlâ anlatıyordu. (2) Claude Code masaüstünde ajan ekipleri: yalnız CLI'da var; masaüstünde "dynamic workflows" var. Claude Code masaüstünde olmayanlar (resmî "What's not available"): üçüncü taraf sağlayıcılar (ağ geçidi hariç), satır içi kod tamamlama, ajan ekipleri; Linux'ta computer use yok. dsh'nin kendi "auto-review" ve "permission-presets" bileşenleri var; Codex'te `approvals_reviewer = "auto_review"`.

## 2. Özellik listesi

Her maddede: **Rakipler** · **Bizde şimdi** · **Hedef** · **Motor işi** · **Masaüstü işi** · **Güvenlik sınırı** · **Testler** · **Boyut** (S/M/L/XL).

### A. Görev ve proje yönetimi (masaüstünden)

**A1. Görev / plan başlatma ekranı** · Boyut M · Öncelik 1
- Rakipler: Orchestrator.inc "ana ajana ne istediğini söyle, işi planlar, her parça için işçi başlatır". Claude Code/Codex: görevi doğrudan verirsin. dsh: `plan`, `goal`, `todo`, `workflow` paketleri.
- Bizde: motorda `plan.create|edit|start`, `project.cancel|resume` var; masaüstü izin listesinde yok (`READ_COMMANDS` yalnız okuma).
- Hedef: Görevler ekranında "Yeni görev": açıklama, proje klasörü, ajan/rol seçimi, plan taslağı düzenleme, başlat.
- Motor: yeni komut gerekmez; masaüstü için izin listesine eklenir (`plan.create|edit|view`, `project.cancel|resume`). `plan.start` ayrı eylemdir.
- Masaüstü: form + taslak düzenleyici; karar ve doğrulama motorda (`plan_draft`), ekran gerekçeyi çizer.
- Güvenlik: `plan.start` TASK sınıfı; onay gerektiren adım yine yerel onay penceresinde. Başlatma, onay yerine geçmez. Test: izin listesinde `approval.*` hâlâ yok.
- Testler: Rust izin listesi eşitlik testi, node ekran testi (motor kapalı = hata görünümü), Python IPC testi (renderer origin ile start izinli, MCP ile değil/duruma göre).

**A2. Pano (kanban / şeritler)** · Boyut M · Öncelik 2
- Rakipler: Orchestrator.inc: Çalışıyor / Sana ihtiyaç var / İncelemede / Birleştirmeye hazır; şeritler ajan, PR, CI ve incelemeden türer.
- Bizde: Görevler/Projeler düz liste; Gelen kutusu var.
- Hedef: Tek pano; "sana ihtiyaç var" en üstte.
- Motor: yeni `board.view` (READ): her çalışma/oturum için şerit hesabı **motorda** yapılır, ekran yalnız çizer.
- Masaüstü: şerit sütunları, kart, filtre. Şerit kuralı ekranda tutulmaz.
- Testler: Python (durum → şerit tablosu), node (bilinmeyen şerit = hata görünümü, boş pano değil).

**A3. Worktree / dal / değişiklik görünümü ve geri alma** · Boyut M · Öncelik 3
- Rakipler: Orchestrator.inc "her görev kendi ajan, dal ve worktree"; Claude Code kontrol noktası + `Esc Esc` geri sarma; dsh geri alma (paket adı belgelenmedi).
- Bizde: motor worktree ve `workflows/checkpoint.py` kullanıyor; ekranda hiçbir yüzey yok.
- Hedef: Kartta dal adı, değişen dosyalar, diff, "bu noktaya geri dön".
- Motor: `worktree.view`, `checkpoint.list|restore` (restore TASK; kullanıcı verisini değiştirdiği için onay kapısından geçer).
- Güvenlik: geri alma yalnız motorun kendi worktree'sinde; kullanıcının asıl çalışma ağacına dokunmaz.

**A4. PR / CI / inceleme akışı** · Boyut L · Öncelik 10
- Rakipler: Orchestrator.inc: başarısız CI, inceleme yorumu, birleştirme çatışması dalın sahibi işçiye geri gider; inceleyici ajan PR'ı insandan önce okur. Composio AO benzer.
- Bizde: `GitHub sınırı` (ARCHITECTURE §11), `review.view`; PR açma/CI izleme yok.
- Hedef: Görev → PR → CI durumu → hatayı işçiye geri yönlendir.
- Güvenlik: Ağ/GitHub erişimi ayrı izinle; token'lar `secret_vault`te; telemetri yok.

### B. Sohbet çekirdeği

**B1. Canlı akış** · Boyut M · Öncelik 4
- Rakipler: hepsi.
- Bizde: tur bitince tek sonuç; ekran 1 sn yoklar.
- Hedef: Metin ve araç çağrıları geldikçe görünsün.
- Motor: `session.events` artımlı (`since` imleci); tur iş parçacığı olayları ara belleğe yazar. Her olay güvenilmeyen veri olmayı sürdürür.
- Masaüstü: artımlı çizim; yoklama aralığı dışında mantık yok.
- Testler: artımlı okuma sırası, kaçan olay yok, kesintide tutarlılık.

**B2. Sohbette dosya düzenleme ve komut çalıştırma** · Boyut XL · Öncelik 8 (mimari karar bekliyor)
- Rakipler: Claude Code, Codex (`workspace-write` sandbox), dsh (`fs`, `shell`, `guard`, `sandbox`).
- Bizde: bilerek kapalı. Neden: `opencode run` AppContainer içinde çalışmıyordu; AppContainer kaldırılınca (karar §6) bu engel ortadan kalkar ve sohbet, ajanın kendi izin kipleriyle (B3) dosya düzenleyebilir/komut çalıştırabilir.
- **Karar değişti:** sandbox kaldırıldığı için seçenek (a) kendiliğinden gelir: sohbette yazma ve komut, ajanın izin kipine (B3) bağlı açılır. Ayrı bir görev hattı yönlendirmesi gerekmez.
- Güvenlik: koruma ajanın kendi sandbox'ı ve izin kipidir (B3). `RESPECTED_CHAT_UNSANDBOXED` anahtarı kalkar.

**B3. Onay kipleri ve izin kuralları** · Boyut L · Öncelik 5 (B2 ile birlikte)
- Rakipler: Claude Code (izin ver/yasakla kuralları, kipler), Codex (read-only / workspace-write / danger; `approval_policy`), dsh (`guard`). "YOLO" benzeri onaysız kip biz de eklemeyiz.
- Hedef: Oturum kipi: yalnız oku / plan / onayla-sor. Kural deposu motorda.
- **Karar (kullanıcı, 2026-11-08): tüm kipler sunulacak, seçim kullanıcının.** İki rakip uygulamanın seçicisi örnek alındı:
  Claude Code masaüstü: Otomatik · Manuel · Düzenlemeleri kabul et · Plan · İzinleri atla; Codex/ChatGPT: Ajanın izinlerini kullan · Düzenlemeleri kabul et ·
  Otomatik onay (rutin eylemleri onaylar, riskliyi sorar) · İzinleri atla (hiç sormaz); "Bu proje için hatırla" anahtarı.
- Önerilen kip kümesi: **Manuel** (her değişiklikte sor) · **Plan** (önce plan, onaydan sonra değişiklik) · **Düzenlemeleri kabul et** (dosya düzenlemeleri sormadan, komutlar sorulur) ·
  **Otomatik** (rutin eylem sormadan, riskli olan sorulur; karar kuralını motor verir) · **İzinleri atla** (hiç sormaz). Varsayılan: Manuel.
- Kip motorda saklanır (oturum başına, "bu proje için hatırla" ile proje başına) ve motor uygular; ekran yalnız seçici ve soru penceresini çizer.
- Kip değiştirme komutu (`session.mode.set`) ajan/MCP kaynağından reddedilir; yalnız kullanıcı eylemiyle (renderer/yerel) geçer.
- **Karar (kullanıcı): sandbox yok.** İzin kipi tek eksendir; sandbox kaldırılıyor (§6). `İzinleri atla` soruları kapatır, ajanın kendi sandbox'ı varsa o ayrıca geçerlidir (ajan CLI'ının işi). Ajan kullanıcı olarak, kısıtsız çalışır (Claude Code, Codex, Orchestrator.inc ile aynı).
- **Karar (kullanıcı): `İzinleri atla` ilk kez seçilirken uyarı penceresi çıkar** (açıklayıcı, onay düğmeli). Claude Code'da bu kip seçicide ancak Ayarlar'da açıldıktan sonra görünür; bizde Ayarlar'da böyle bir anahtar olmaz (karar): kip seçicide her zaman görünür, yalnız ilk seçimde uyarı penceresi çıkar.
- Eski kural belgeleri (`ARCHITECTURE.md` §6 ve sohbet bölümü, `tests/acl.rs`, `session.approve` yok testi) bu karar uygulanırken **kodla birlikte** güncellenecek; o zamana kadar mevcut koruma geçerli.

**B4. Çoklu ajan sohbeti** · Boyut L · Öncelik 7
- Rakipler: Orchestrator.inc 35+ ajan, görev başına ajan+model.
- Bizde: `SUPPORTED = ("opencode",)`; işçi tarafında Codex/Claude/Cursor var.
- Hedef: Sohbette ajan seçici; her ajan için doğrulanmış akış adaptörü.
- Motor: `chat_session` adaptör tablosu genişler; `session.defaults.agents` zaten motordan gelir.
- Testler: her adaptör için kayıtlı akış (fixture) + canlı doğrulama kanıtı.

**B5. Mesaj düzenleme / yeniden üretme / dallanma** · Boyut M · Öncelik 12
- Rakipler: Claude Code (geri sarma), sohbet uygulamaları.
- Bizde: yalnız `retry`.

**B6. Çalışan oturumda model değiştirme** · Boyut S · Öncelik 12
- CLI desteklemiyorsa yeni oturuma devretme ("bu modelle devam et"): `continue_conversation` + model parametresi.

**B7. Sınırların esnetilmesi** · Boyut S
- 20 oturum, 180 sn tur, 8000 karakter: bilinçli sınırlar; ihtiyaca göre ayar anahtarına bağlanır (`settings.*`).

### C. Bağlam ve hafıza

**C1. Bağlam doluluğu göstergesi** · Boyut S · Öncelik 6
- Rakipler: Claude Code, dsh.
- Bizde: ajan pencere boyutunu bildirmiyor, ekran uydurmuyor (doğru karar).
- Hedef: Modelin bağlam penceresi **motorda bilinen bir kaynaktan** (sağlayıcı kataloğu) gelir; yoksa "bilinmiyor".

**C2. Bağlam sıkıştırma** · Boyut L · Öncelik 9
- Rakipler: Claude Code `/compact`, dsh `compaction` + `spill`.
- Bizde: yok. CLI'dan geçirme mümkün mü, araştırılacak.

**C3. Proje talimat dosyası (AGENTS.md / CLAUDE.md)** · Boyut S · Öncelik 5
- Rakipler: Claude Code CLAUDE.md, Codex AGENTS.md (+ override), dsh.
- Hedef: Oturum başlarken proje kökündeki talimat dosyası **güvenilmeyen veri** olarak okunur, kullanıcıya gösterilir, isteğe bağlı bağlama eklenir; ekranda "Bu sohbet şu talimatları okuyor" şeridi.
- Güvenlik: Dosya içeriği talimat değil veridir; yetki vermez.

**C4. Brain hafızası görünürlüğü** · Boyut S
- Sohbetin hangi hafızayı gördüğü (`memory.status` var) ekranda görünsün.

### D. Genişletme

**D1. MCP yönetimi (ekle / aç-kapat)** · Boyut M · Öncelik 9
- Rakipler: hepsi.
- Bizde: `capabilities.inventory|scan|matrix|recommend` salt okunur; "AI araçları" ekranı yalnız listeliyor.
- Güvenlik: Açma/kapama, istemci yapılandırmasını değiştirir → ayar sınıfı + onay; gizli değerler ekrana çıkmaz (şimdiki kural).

**D2. Eklenti / beceri / eğik çizgi komutları** · Boyut L · Öncelik 11
- Rakipler: Claude Code (plugins, skills, slash commands), dsh ("everything is a plugin", `skill`, `extensions`).
- Önce karar: bunlar ajan CLI'ında mı yaşayacak (geçir), bizde mi?

**D3. Hook'lar** · Boyut L · Öncelik 11
- Rakipler: Claude Code hooks. dsh `guard`/olay sistemi.
- Güvenlik: Hook çıktısı onay veremez; yalnız yerel kurallar.

**D4. Alt ajanlar / ekipler** · Boyut XL · Öncelik 10
- Rakipler: Claude Code subagents, Codex subagents, dsh `subagent` + `team` + ortak görev panosu.
- Bizde: "Ajanlar ve ekipler" ekranı salt okunur; işçi paralelliği motorda (kampanya) var.

**D5. Zamanlama** · Boyut M · Öncelik 11
- Rakipler: dsh `schedule`, Claude Code scheduled tasks.
- Bizde: motorda 2 dosyada iz var, ekran yok.

**D6. Tarayıcı ile deneme** · Boyut L
- Rakipler: Orchestrator.inc işçi başına tarayıcı; dsh `browser-use`, `computer-use`.
- Bizde: önizleme paneli (`preview.rs`) var; işçiyle bağlı değil.

**D7. LSP / tanılama** · Boyut M · dsh `lsp`.

### E. Uygulama kabuğu

**E1. Ayarlar ekranı** · Boyut S · Öncelik 5
- Bizde: boş ("sonraki sürümde"); motorda `settings.schema|readback|validate|apply` hazır. Varsayılan model, tur süresi, sınırlar burada.
- Güvenlik: `settings.apply` yalnız doğrulamadan geçen anahtarlar.

**E2. Bildirimler** · Boyut S · Öncelik 6
- Rakipler: Orchestrator.inc (masaüstü + mobil push).
- Hedef: tur bitti / onay bekliyor / hata → işletim sistemi bildirimi. Metin motordan gelen olaydan türer; içerik (kod, istem) bildirime yazılmaz.

**E3. Klavye kısayolları ve komut paleti** · Boyut S · Öncelik 6

**E4. Geçmiş: arama, yeniden adlandırma, sabitleme, arşivleme, dışa aktarma, toplu silme** · Boyut M · Öncelik 7
- Motor: `session.search`, `session.rename`, `session.export` (kayıtlar zaten motorda, `chat/sessions.json`).

**E5. Taslakların kalıcılığı** · Boyut S. Gönderilmemiş mesaj yeniden açılınca kalsın (görünüm tercihi sayılır → yerel depolama olur).

**E6. Eski sohbetlerin taşınması** · Boyut S. Eski `orch.history.v1` kayıtlarını bir kez motora içe aktar (kullanıcı onayıyla), sonra sil.

**E7. Uzak erişim / web / mobil / bulut** · Boyut XL · Öncelik 13
- Rakipler: Orchestrator.inc iPhone/Android + bulut ajanları; dsh web arayüzü + ssh.
- Bizde: yok. Ürün kararı gerekir (yerel-öncelikli ilke ile çelişebilir).

**E8. Erişilebilirlik ve dil** · Boyut M. Arayüz yalnız Türkçe; klavye ve ekran okuyucu denetimi yapılmadı.

### G. Uygulama rakiplerinden (Claude Code ve Codex masaüstü) gelen ek maddeler

**G1. İnceleme kuyruğu ve satır yorumlu diff** · Boyut M · Öncelik 3
- Rakipler: Codex uygulaması: Automations sonuçları "review queue"ya düşer, diff yan yana, satır içi yorum. Claude Code masaüstü: görsel diff incelemesi.
- Bizde: diff paneli var; yorum, kabul, reddet, kuyruk yok. `review.view` motorda var.
- Hedef: Her işçi çıktısı inceleme kuyruğuna düşer; kullanıcı satıra yorum yazar, yorum işçiye geri gider.
- Güvenlik: Yorum metni işçiye **veri** olarak gider, onay yerine geçmez. Birleştirme/uygulama yine yerel onay penceresinde.

**G2. Yan sohbet** · Boyut S · Öncelik 8
- Rakip: Claude Code masaüstü (Ctrl+;): ana oturumun bağlamını okur, ana oturuma geri yazmaz.
- Motor: `session.side {session_id, text}` (salt okuma kopyası); sonuç ana döküme eklenmez.

**G3. Zamanlanmış görevler + sonuçların inceleme kuyruğuna düşmesi** · Boyut M · Öncelik 11
- Rakipler: Codex Automations, Claude Code scheduled tasks, dsh `schedule`.
- Bizde: motorda zamanlama izi var (2 dosya), komut ve ekran yok.
- Güvenlik: Zamanlanmış çalışma kullanıcıdan alınmış kalıcı bir izindir; kapsamı, süresi ve bütçesi görünür olmalı, onay gerektiren adımda durur.

**G4. Gömülü dosya düzenleyici** · Boyut M. Codex'te yok, Claude Code masaüstünde var. Dosya paneline "düzenle" eklemek `files.rs` izin sınırını (yalnız seçili klasörler) korumalı; yazma yeni bir izin gerektirir.

**G5. CLI oturumunu uygulamaya taşıma** · Boyut M. Kullanıcının terminaldeki ajan oturumu (`ses_…`) uygulamada açılabilsin. `resume_session` motorda var; ekranda "kimlikle aç" yok.

**G6. Başsız kip ve sohbetin MCP olarak sunulması** · Boyut M · Öncelik 11
- Rakipler: Claude Code CLI ve Codex CLI başsız çalışır; Codex CLI kendini MCP sunucusu yapabilir.
- Bizde: motorun MCP sunucusu (§6) var, `rpp` komutları var. Sohbet oturumu (`session.*`) bunlarda yok.
- Güvenlik: MCP kaynağı SETTINGS/PRIVILEGED yapamaz (şimdiki kural); sohbet başlatma TASK sınıfı.

**G7. Mobil / uzak erişim:** E7'ye bağlı.

**G8. Oturum ayrıntı paneli** · Boyut S · Öncelik 4
- Claude Code masaüstü: kartlar: oturumun çalıştığı yer, değişenler, çalışan işler, bağlam doluluğu %.
- Bizde: sağ "Oturum çubuğu" token, model ve dosyaları gösteriyor; bağlam %, çalışan işler, dal yok.
- Motor: `session.details` (dal, worktree yolu, değişen dosyalar, çalışan işler); bağlam % yalnız model penceresi bilinirse (C1).

**G9. Oturumlar arası mesajlaşma ve önerilen görevler** · Boyut M · Öncelik 12
- Claude Code: oturumlar birbirini listeler/okur/mesajlar; ajan dışı iş fark edince görev önerir.
- Güvenlik: oturumdan oturuma gelen metin **veri**dir, yetki vermez; öneri kullanıcı onayı olmadan başlamaz.

**G10. Ağ proxy ve alan adı izin listesi** · Boyut M · Öncelik 9
- Codex: komut ağı için proxy; "workspace-write" varsayılanı ağsız; proxy MCP/web aramasını süzmez (belgede açıkça yazıyor). Claude Code: yönetilen ağ gereksinimleri. dsh: `network-proxy`.
- Bizde: işçi sandbox'ı kalkınca ağ kısıtı da kalkar; ağ kuralını ajanın kendi ayarı belirler. Kullanıcıya görünen ve ayarlanabilir bir izin listesi yok.

**G11. Kural dosyası (sandbox dışı komutlar) ve korunan yollar** · Boyut M · Öncelik 5 (B3 ile)
- Codex Rules: hangi komutların sandbox dışında çalışabileceği. `.git` yazılabilir kökte bile salt okunur.
- Codex'in `auto_review` ayarı (onay sorusunu başka bir ajana yönlendirir) kullanıcı kararıyla tartışmaya açık: kullanıcı "tüm kipler sunulsun" dedi; ajana onay devretme ayrı bir kip olarak eklenecekse kullanıcı açıkça seçmeli ve varsayılan kapalı olmalı (açık soru 5).

**G12. Yerel ortam / kurulum betikleri** · Boyut S. Worktree açılınca çalışan kurulum komutları (bağımlılık kurma vb.); betik içeriği kullanıcıya gösterilir, onaysız çalışmaz.

**G13. Bilgisayar kullanımı (computer use)** · Boyut XL · Öncelik 14. Ekran/klavye denetimi; yetki ve gizlilik riski yüksek; ürün kararı olmadan başlanmaz.

**G14. Sağlayıcı / model ayar ekranı** · Boyut M · Öncelik 5. dsh: Settings → Models; anahtar girilince yeniden başlatmadan geçerli. Bizde `secret_vault` ve `provider_policy` motorda var; anahtar girişi ekranı yok (anahtarlar ekrana ve günlüğe yazılmaz).

**G15. Eklenti pazarı, Python SDK, herkese açık dağıtım** · D2/E7 ile: önce yerel kullanım; SDK ve dağıtım ürün kararı.

**G16. Görünüm kipleri, oturuma klasör ekleme, @dosya otomatik tamamlama** · Boyut S. Dökümde ayrıntı düzeyi (Claude: Ctrl+O), `@` ile dosya ekleme (sohbette yol ekleme yalnız dosya seçici).

### F. Bilerek yapmadıklarımız (eksik değil)

- Telemetri, hesap/oturum sistemi, otomatik güncelleme (kurucu yönetir).
- Ajanın veya MCP istemcisinin kendi kipini yükseltmesi.

---

## 3. Önerilen sıra

1. A1 görev başlatma → 2. A2 pano → 3. A3 worktree/geri alma → 4. B1 canlı akış → 5. E1 ayarlar + C3 AGENTS.md + B3 kipler
6. C1 bağlam göstergesi + E2 bildirim + E3 kısayollar → 7. B4 çoklu ajan + E4 geçmiş araçları → 8. B2 (karar sonrası)
9. D1 MCP yönetimi + C2 sıkıştırma → 10. A4 PR/CI + D4 alt ajanlar → 11. D2/D3/D5 → 12. B5/B6 → 13. E7.

## 4. Her madde için ortak kurallar

- Karar ve iş kuralı motorda; masaüstü yalnız çizer ve seçimi iletir (`desktop/tests/engine_owns.test.ts` bunu denetler).
- Masaüstü komut izin listeleri üç yerde aynı tutulur: `engine_connector.rs`, `sessionlog.ts`/`beta4.ts`, `contracts/ipc.ts`.
- Motor kapalı / komut hatası: hata görünümü; sahte veya yedek veri çizilmez.
- Yeni komut: yetki sınıfı (READ/TASK/SETTINGS/PRIVILEGED) belgelenir, `tests/engine` ve `cargo test` ACL testi güncellenir.
- Telemetri eklenmez; ağ erişimi yeni özellik için ayrıca gerekçelendirilir.

## 6. Alınan kararlar (2026-11-08, kullanıcı)

1. **Odak:** "Birden çok ajanı çalıştıran, işin gerçekten bittiğini kanıtlayan, tamamen yerel orchestrator." Özellik sayısı yarışına girilmez.
2. **Motor tek, kalıcı bir arka plan süreci olur.** CLI, MCP ve masaüstü aynı canlı oturumları görür. (Tasarım ayrı belge/ADR ister: başlatma, kurucu, yerel bağlantı güvenliği.)
3. **Tek işlem kataloğu:** CLI, MCP ve masaüstü motordaki tek katalogdan beslenir; yeni özellik üçünde birden görünür.
4. **İzin kipleri:** tüm kipler sunulur, seçimi kullanıcı yapar; `İzinleri atla` yalnız soruları kapatır, ilk seçimde uyarı penceresi çıkar (B3).
5. **Sandbox komple kaldırılır** (yedek olarak da kalmaz). İşçiler kullanıcı olarak, ajanın kendi sandbox ve izin kipiyle çalışır. Motorun doğrulama komutları dahil AppContainer yolu tamamen silinir: işçi kısıtsız çalıştığı için doğrulamayı kutuda koşmak yarım koruma olurdu. Kanıt ve onay bütünlüğü imza ve motor doğrulamasıyla sağlanır; anahtar gizliliği için ek garanti verilmez ve belgede açıkça yazılır. Getirisi: Windows bağımlılığı biter (macOS/Linux yolu açılır), `RESPECTED_CHAT_UNSANDBOXED` kalkar, araç uyumsuzlukları (`npm test`, Codex sandbox) biter.
   - **Silinecek:** `engine/appcontainer.py`, `engine/sandbox.py`, `engine/worker_policy.py` (sandbox olmayan kısımları, örneğin ortam süzme, önce okunup korunur), bunlara bağlı `runner.py`, `integration.py`, `processes.py`, `supervisor.py`, `workflows/project.py`, `workflows/maf_workflow.py` kısımları; testler `test_sandbox.py`, `test_worker_policy.py`, `test_worker_security.py`, `test_security_gate.py`, `test_conpty_feasibility.py`; kapı/CI betikleri `release_gate.py`, `run_security_ci.py` içindeki sandbox adımları; `ARCHITECTURE.md` §2/§3 ve ADR-015/018/021/024'ün ilgili kısımları.
   - **Silinmeyecek:** kapsam denetimi ve yama doğrulama (symlink/submodule reddi), süre sınırları ve süreç ağacı temizliği, `RESPECTED_ORCH_CHILD` işareti ve MCP özyineleme koruması, imzalı kanıt. Eski kanıt dosyaları (`docs/evidence/poc/*`) tarihçedir, silinmez; "artık geçerli değil" notu eklenir.
   - Kod ve `ARCHITECTURE.md` aynı değişiklikte güncellenir; `rorch` adına geçiş ayrı bir adımdır.
6. **CLI adı: `rorch`** (Respected Orchestrator; `ro` fazla kısa bulundu). Tek ad: yürütülebilir dosya `rorch.exe`, MCP girdisi `rorch mcp`; uzun ad ve takma ad yoktur (depo kuralı). Ürün adı "Respected Orchestrator" olarak kalır. Beta olduğu için geçiş şimdi ucuz: kayıtlı MCP girdileri (`respected-orchestrator.exe mcp`), kurucu, belgeler ve testler güncellenir. Ayrı adım olarak yapılır. Reddedilenler: `ro`, `rsp`, `orch`. İlk komut yapısı için Orchestrator.inc'in `ao` komutları örnek alındı (daemon/start/stop/status/doctor, spawn/send/session/project, pr/review, mcp, hooks).
7. **Çalışma şekli:** dikey dilimler; bir özellik motor + CLI + MCP + masaüstü + test + belge bitince biter.

8. **Ajanın kendi özellikleri ajandan gelir.** Bağlam doluluğu, sıkıştırma (`/compact`), temizleme (`/clear`), model listesi, izin kipleri, eğik çizgi komutları, beceriler, alt ajanlar, hook'lar ajanın işidir; biz yeniden üretmeyiz. Motor ajana sorar, ortak şemaya çevirir, ekran yalnız çizer (§7).
9. **Ortak şema + ajana özel uzantı alanı.** Her ajan için motor aynı biçimde cevap verir; şemada karşılığı olmayan şeyler "uzantı" alanında genel etiket/değer listesi olarak gelir ve ekran bunu olduğu gibi çizer. Yeni bir ajan özelliği masaüstünü değiştirmeyi gerektirmez.
10. **Önce Claude Code adaptörü** derinleştirilir (OpenCode'un ACP istemcisi zaten var; Codex sonra).
11. **Ajanın kendi terminal arayüzü ürünün resmî parçasıdır** (Orchestrator.inc gibi): normalleştirmediğimiz her şey için evrensel yedek. Sandbox kalktığı için ConPTY yolu açılır (ADR-024 engeli ortadan kalkar).
12. **Taklit yok:** ajan bir özelliği sunuyorsa vardır, sunmuyorsa yoktur. Biz onun yerine üretmeyiz (ör. sıkıştırma). Ekran "yok" olan yeteneği gizler ya da nedeniyle gri gösterir.

## 7. Ajan adaptörü (tasarım çerçevesi)

**Üç tür özellik:** (A) ajanın kendi özelliği: ajandan gelir; (B) ajandan bağımsız bizim değerimiz: geçmiş, maliyet kaydı, kanıt, pano, worktree, bildirim: hepsinde aynı, bizde; (C) taklit: yapılmaz (karar 12).

**Mevcut zemin:** `engine/agent_adapters.py` (yetenek yoklaması: yalnız salt-okunur `--version`/`--help`/giriş durumu; bir yetenek ancak CLI'ın kendi yardım metninde görünürse "doğrulandı"), `engine/capability_matrix.py` (ajan başına kip hücresi: doğrulandı / doğrulanmadı / desteklenmiyor; düğme yalnız doğrulanmışsa açık), `engine/opencode_acp.py` (OpenCode ACP istemcisi).

**Ajanla konuşma yolları (güvenilirlik sırasıyla):**
1. Protokol: ACP, Codex app server, Claude Agent SDK. İki yönlü, yapılandırılmış: kip değiştirme, komut listesi, bağlam, izin soruları.
2. Tur başına yapılandırılmış çıktı (bugünkü sohbet): basit; kip değiştirme/sıkıştırma gibi etkileşimli şeylerde zayıf.
3. Ajanın kendi terminal arayüzü paneli: evrensel yedek.

**Önerilen komut:** `agent.describe {agent}` → ortak şema:
`{agent, version, logged_in, context: {supported, percent, window, source}, compact: {...}, clear: {...}, modes: [...], models: [...], commands: [...], extra: [{label, value}]}`.
Her yetenek: `native` (ajan veriyor) ya da `unsupported`; kaynağı ve doğrulama zamanı yazılı (mevcut doğrulandı/doğrulanmadı kuralı).

**Ekran kuralı:** yalnız motorun verdiğini çizer; ajan bağlam yüzdesini vermiyorsa kart çıkmaz, "bilinmiyor" uydurulmaz.

**İlk iş (Claude Code):** gerçek çıktı alanlarını (bağlam bilgisinin nerede verildiği, mod/komut listesi, `/compact` ve `/clear`'ın yapılandırılmış kullanımı) yalnız salt-okunur yoklama ve resmî belgeyle doğrula; doğrulanmayan hiçbir alan şemaya "native" olarak girmez. **Henüz doğrulanmadı.**

**Risk:** ortak şema en küçük ortak paydaya inebilir; çözüm uzantı alanı ve terminal yedeği.

## 5. Açık sorular (karar bekleyen)

0. (Karara bağlandı) `İzinleri atla` yalnız soruları kapatır; sandbox kaldırılıyor; ilk seçimde uyarı penceresi çıkar. Ayarlar'da ayrı bir "izin ver" anahtarı yok (karar): kip seçicide her zaman görünür, yalnız ilk seçimde uyarı penceresi çıkar.
5. Ajana onay devretme (`auto_review`) eklensin mi, eklenirse varsayılan kapalı ve açıkça seçilir mi?

1. (Karara bağlandı) Sohbette yazma: sandbox kalktığı için ajanın izin kipiyle açılır (B2).
2. Eklenti/hook/alt ajan (D2–D4): ajan CLI'ından geçirmek mi, kendi katmanımızı yazmak mı?
3. Uzak/mobil (E7): yerel-öncelikli ilke ile uyumlu mu?
4. İsim: "Respected Orchestrator" ile "Orchestrator.inc" yakınlığı, yayın öncesi ticari marka kontrolü.
