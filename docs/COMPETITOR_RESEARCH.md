# Rakip ve çerçeve araştırması

- Durum: Tamamlandı (DOC-01)
- Erişim tarihi: 30 Ekim 2026
- Yöntem: Yalnızca ürünün kendi deposu, resmî dokümanı veya resmî ürün sayfası "birincil" sayılır. İkincil kaynak ayrıca işaretlenir. Hiçbir kaynakla doğrulanamayan iddia "doğrulanmadı" olarak kaydedilir ve pazarlama/karar gerekçesi olarak kullanılmaz.
- Kapsam sınırı: Bu belge ürün kararlarının kaynağını tutar; çalışma sözleşmesi veya benchmark sonucu değildir. Ölçüm iddiaları [`evidence/KANIT_LOG.md`](evidence/KANIT_LOG.md) ve [`evidence/poc/eval01_results.json`](evidence/poc/eval01_results.json) dosyalarına bağlanır.

## Kaynak tablosu

| Kimlik | Kaynak | URL | Erişim | Düzey |
| --- | --- | --- | --- | --- |
| S1 | CrewAI README | https://raw.githubusercontent.com/crewAIInc/crewAI/main/README.md | 2026-10-30 | birincil |
| S2 | AutoGen README | https://raw.githubusercontent.com/microsoft/autogen/main/README.md | 2026-10-30 | birincil |
| S3 | LangGraph README | https://raw.githubusercontent.com/langchain-ai/langgraph/main/README.md | 2026-10-30 | birincil |
| S4 | OpenHands README | https://raw.githubusercontent.com/All-Hands-AI/OpenHands/main/README.md | 2026-10-30 | birincil |
| S5 | OpenAI Codex CLI dokümanı | https://developers.openai.com/codex/cli/ | 2026-10-30 | birincil |
| S6 | OpenAI Codex sandboxing dokümanı | https://developers.openai.com/codex/sandboxing/ | 2026-10-30 | birincil |
| S7 | OpenAI Codex Git worktrees dokümanı | https://developers.openai.com/codex/local-environments/git-worktrees/ | 2026-10-30 | birincil |
| S8 | Anthropic — Claude Code auto mode | https://www.anthropic.com/research/claude-code-auto-mode | 2026-10-30 | birincil |
| S9 | Claude Help — Claude Code sandboxing | https://support.claude.com/en/articles/14554000-claude-code-power-user-tips | 2026-10-30 | birincil |
| S10 | Cursor — background agents | https://prod.cursor.com/help/ai-features/background-agents | 2026-10-30 | birincil |
| S11 | Cursor — worktrees | https://cursor.com/docs/configuration/worktrees | 2026-10-30 | birincil |
| S12 | Gemini CLI README | https://github.com/google-gemini/gemini-cli | 2026-10-30 | birincil |
| S13 | OpenCode resmî ürün sayfası | https://opencode.ai/ | 2026-10-30 | birincil |
| S14 | Orchestrator.inc resmî ürün sayfası | https://orchestrator.inc/ | 2026-10-30 | birincil |
| S15 | OrchestratorInc/agent-orchestrator deposu | https://github.com/OrchestratorInc/agent-orchestrator | 2026-10-30 | birincil |
| S16 | OpenAI — Symphony duyurusu | https://openai.com/index/open-source-codex-orchestration-symphony/ | 2026-10-30 | birincil |
| S17 | Symphony SPEC deposu | https://raw.githubusercontent.com/openai/symphony/main/SPEC.md | 2026-10-30 | birincil |
| S18 | ryfranklin/Mission-Control README | https://github.com/ryfranklin/Mission-Control | 2026-10-30 | birincil |
| S19 | thomas-scrace/mission-control README | https://github.com/thomas-scrace/mission-control | 2026-10-30 | birincil |
| S20 | sugi64/orca-ai-orchestrator README | https://github.com/sugi64/orca-ai-orchestrator | 2026-10-30 | birincil |
| S21 | araa47/orca README | https://github.com/araa47/orca | 2026-10-30 | birincil |

## Çerçeve profilleri

### Çerçeve: CrewAI

- **Doğrulama:** birincil
- **Kaynak:** S1 (erişim: 2026-10-30)
- **Gözlem:** Python çok-ajan framework'ü. İki ayrı yaklaşım sunuyor: rol tabanlı otonom "Crews" ve olay güdümlü, daha sıkı kontrollü "Flows". Ticari AMP/Control Plane gözlem, yönetişim ve dağıtım katmanı ekliyor.
- **Respected için çıkarım:** CrewAI bir iş akışı çalıştırma çerçevesi; teslim edilen yamanın kapsam, tazelik, imza ve insan onayı sözleşmesini çözmez. Respected'ın farkı ajanı değil, sonucu doğrulaması olmalı.

### Çerçeve: AutoGen

- **Doğrulama:** birincil
- **Kaynak:** S2 (erişim: 2026-10-30)
- **Gözlem:** Microsoft projesi **arşivlenmiş** ve artık bakımlı değil; README yeni projeler için Microsoft Agent Framework'e yönlendiriyor. Katmanlar Core (mesajlaşma/olay), AgentChat (hızlı prototip) ve Extensions.
- **Respected için çıkarım:** AutoGen doğrudan rakip değil, komşu/emekli bir referans. Yeni bağımlılık olarak seçilmemeli; yalnızca desen karşılaştırmasında kullanılmalı.

### Çerçeve: LangGraph

- **Doğrulama:** birincil
- **Kaynak:** S3 (erişim: 2026-10-30)
- **Gözlem:** Uzun süreli, durumlu ajan iş akışları için altyapı. Dayanıklı yürütme (hatadan sonra kaldığı yerden devam), insan-döngüde kesme, kısa/uzun vadeli hafıza ve LangSmith ile izleme öne çıkarılıyor.
- **Respected için çıkarım:** Kalıcı durum ve resume ihtiyacı (`RES-01..03`) burada kanıtlanmış bir desen. Ancak LangGraph'ı bağımlılık yapmak yerine mevcut görev verisine küçük, makine-okunur handoff kaydı eklemek yeterli.

### Çerçeve: OpenHands

- **Doğrulama:** birincil
- **Kaynak:** S4 (erişim: 2026-10-30)
- **Gözlem:** "Agent Canvas" kendiliğinden barındırılan bir geliştirici kontrol merkezi. OpenHands, Claude Code, Codex, Gemini, Pi, OpenCode ve ACP uyumlu ajanları yerel, uzak ve bulut arka uçlarında çalıştırıyor.
- **Respected için çıkarım:** Çoklu ajan adaptörü ve tek kontrol yüzeyi artık farklılaştırıcı değil. Respected'ın savunulabilir alanı, bu ajanların sonuçlarını doğrulayan teslim sözleşmesi.

## Doğrudan rakip profilleri

### Rakip: Claude Code

- **Doğrulama:** birincil
- **Kaynak:** S8, S9 (erişim: 2026-10-30)
- **Gözlem:** Varsayılan olarak dosya yazımı ve komutlar için onay istiyor. Auto mode, her araç çağrısını bir sınıflandırıcıdan geçirip riskli eylemleri engelliyor; bunun riski tamamen kaldırmadığı ve izole ortam önerildiği açıkça yazıyor. `/sandbox` ile dosya ve ağ yalıtımı sunuluyor.
- **Respected için çıkarım:** Onay yorgunluğu gerçek bir sorun; sadece "daha çok onay" güvenlik değildir. Respected'ın `check/apply` kapısı ve bağımsız kanıtı, ajanın kendi izin modelinin üstüne eklenmeli.

### Rakip: Codex

- **Doğrulama:** birincil
- **Kaynak:** S5, S6, S7 (erişim: 2026-10-30)
- **Gözlem:** CLI ve bulut ortamları var. Sandbox teknik sınırları, onay politikası ise bu sınırları aşarken ne zaman durulacağını tanımlıyor; ikisi ayrı kontrol olarak konumlanıyor. Bulut ortamları paralel görev ve Git worktree kullanımına izin veriyor.
- **Respected için çıkarım:** Sandbox ile onayı aynı şey sanmamak gerekiyor. Respected'ın worker başlatıcısı (`SEC-02/03`) bu iki kontrolü ayrı ayrı uygulamalı.

### Rakip: Cursor

- **Doğrulama:** birincil
- **Kaynak:** S10, S11 (erişim: 2026-10-30)
- **Gözlem:** Cloud/background agent'lar kendi sanal makinesinde çalışıyor; sır, ağ politikası ve kimlik yönetimi sağlanıyor. Sonuç video, ekran görüntüsü ve günlüklerle PR'a ekleniyor. Worktree'ler her göreve ayrı checkout veriyor.
- **Respected için çıkarım:** "Kanıt" bir video olabilir ama tek başına kabul ölçütü değildir. Respected kanıtı yeniden doğrulanabilir komut çıktısı ve imzayla sınırlamalı.

### Rakip: Gemini CLI

- **Doğrulama:** birincil
- **Kaynak:** S12 (erişim: 2026-10-30)
- **Gözlem:** Gemini'yi terminale getiren açık kaynak ajan; MCP istemci/sunucu konuları var. README, ücretsiz katman ve Google One kullanıcıları için 18 Haziran 2026'da Antigravity CLI'ya geçildiğini belirtiyor.
- **Respected için çıkarım:** Sağlayıcı CLI'ları hızla değişiyor. Respected adaptörü belirli bir CLI sürümüne değil, sürüm saptanabilir bir sözleşmeye bağlanmalı (`ADP-01`, `COST-01`).

### Rakip: OpenCode

- **Doğrulama:** birincil
- **Kaynak:** S13 (erişim: 2026-10-30)
- **Gözlem:** Açık kaynak terminal/IDE/masaüstü ajanı; aynı projede birden fazla oturum, 75+ sağlayıcı ve MCP/ACP desteği öne çıkarılıyor.
- **Respected için çıkarım:** OpenCode bir worker olarak değerli; Respected onu kendi başına bir ürün olarak taklit etmemeli, adaptör olarak desteklemeli.

### Rakip: Orchestrator.inc

- **Doğrulama:** birincil
- **Kaynak:** S14, S15 (erişim: 2026-10-30)
- **Gözlem:** Eski adı Agent Orchestrator (AO). Yerel ajanlar Git worktree'lerinde çalışıyor; yerleşik bir reviewer ajanı PR'ı inceleyip değişiklik isteklerini aynı worker'a gönderebiliyor. Yerel uygulama Apache-2.0 ve ücretsiz; bulut planları barındırılan sandbox ekliyor.
- **Respected için çıkarım:** En yakın doğrudan rakip. Fark, doğrulama/kanıt sözleşmesinin bağımsız ve insan kararına bağlı olması olmalı; yalnızca "reviewer ajanı" eklemek yeterli değil.

### Rakip: Mission Control

- **Doğrulama:** doğrulanmadı
- **Kaynak:** S18, S19 (erişim: 2026-10-30) — kimlik çakışması U-02
- **Gözlem:** En az iki farklı açık kaynak projesi aynı adı kullanıyor. `ryfranklin/Mission-Control` her görevi worktree'de yalıtıyor, adım başına maliyet ölçüyor, insan go/no-go kapısı ve çökme sonrası resume sunuyor; golden task + LLM judge tabanlı bir eval kapısı tanımlıyor. `thomas-scrace/mission-control` ise yalnızca oturum dosyalarını okuyan yerel bir pano.
- **Respected için çıkarım:** Bu isim altında tek bir ürün varmış gibi karşılaştırma yapılmamalı. Önce hangi proje kastedildiği kaynakla sabitlenmeli; "Aegis kalite kapısı" iddiası bu belgede doğrulanmış sayılmaz.

### Rakip: Orca

- **Doğrulama:** birincil (kimlik sınırı U-01)
- **Kaynak:** S20, S21 (erişim: 2026-10-30)
- **Gözlem:** Aynı adı kullanan iki proje var. `sugi64/orca-ai-orchestrator` kendisini paralel ajan filosu için ADE olarak tanımlıyor; Codex, Claude Code, OpenCode ve Pi'yi ayrı worktree'lerde yan yana çalıştırıp tek yerden izlemeyi vaat ediyor. `araa47/orca` ise ajanların tmux pencerelerinde alt worker açmasını sağlayan deneysel bir CLI.
- **Respected için çıkarım:** Worktree başına ajan artık standart. Respected'ın farkı, worktree sonuçlarının birleştirilmesi ve kabul edilmesi sırasındaki doğrulama kapıları olmalı.

### Rakip: Symphony

- **Doğrulama:** birincil
- **Kaynak:** S16, S17 (erişim: 2026-10-30)
- **Gözlem:** Linear panosunu ajanlar için kontrol düzlemine çeviriyor. Her açık görev kendi çalışma alanında bir ajanla eşleşiyor; ajan çökerse yeniden başlatılıyor. Referans uygulama Elixir, ancak depo özünde dil-bağımsız bir SPEC.
- **Respected için çıkarım:** Issue durumunu durum makinesi yapmak güçlü bir desen. Ancak SPEC'i kopyalamak yerine, mevcut görev verisine bağımlılık ve sahiplik alanları eklemek (`SCH-01/02`) daha küçük ve doğrulanabilir.

### Rakip: OpenHands

- **Doğrulama:** birincil
- **Kaynak:** S4 (erişim: 2026-10-30)
- **Gözlem:** Çerçeve profilinde ayrıntılı. Agent Canvas, birden çok ajanı yerel/uzak/bulut arka uçlarında çalıştıran kendiliğinden barındırılan kontrol merkezi.
- **Respected için çıkarım:** Çoklu ajan çalıştırma ve kontrol paneli rekabeti yoğun; Respected burada değil, doğrulanmış teslim ve insan kabulünde farklılaşmalı.

## Doğrulanmamış iddialar

- **U-01:** Orca'nın diff yorumlarını doğrudan ajana geri gönderdiği iddiası. Kaynak sayfasında bu akış doğrulanmadı.
- **U-02:** "Mission Control" adlı tek bir ürün ve "Aegis kalite kapısı" iddiası. En az iki farklı proje aynı adı kullanıyor; iddiaya uyan birincil kaynak bulunamadı.
- **U-03:** Symphony'nin bazı ekiplerde ilk üç haftada birleştirilen PR sayısını %500 artırdığı iddiası. Duyuru sayfasının tam metni bu oturumda alınamadı; doğrulanmış sayılmaz.
- **U-04:** CrewAI Flows'un checkpointing, insan girdisi ve A2A gibi ayrıntılı yetenekleri. README'de yalnızca olay güdümlü kontrol doğrulandı; ayrıntılar doğrulanmadı.
- **U-05:** Rakiplerin fiyat, kota ve ekip planı ayrıntıları. Bu belge fiyat karşılaştırması yapmıyor.
- **U-06:** "Respected aynı görevde daha az hatalı uygulama üretir" iddiası. Henüz `EVAL-02` karşılaştırması yok; pazarlama iddiası olarak kullanılamaz.

## Benchmark'a bağlı kararlar

- **B-01:** Değerlendirme koşucusunun tekrarlanabilirliği ölçüldü: 20 fixture × 3 tekrar = 60 koşu, 60/60 sabit SHA ve beklenen hatalı/altın ayrımı. Kanıt: [`evidence/poc/eval01_results.json`](evidence/poc/eval01_results.json), özet [`evidence/KANIT_LOG.md`](evidence/KANIT_LOG.md) §EVAL-01. Bu sonuç **ajan başarısı değil**, harness tekrarlanabilirliğidir; karar ADR-002'de bu sınırla kayıtlı.
- **B-02:** Ajan karşılaştırması ve "daha az hata" iddiası **doğrulanmadı** (U-06). Güncelleme (4 Kasım 2026): `EVAL-02` tamamlandı, ama harness tutarlılığını ölçer, model kalitesi iddiası değildir; bu belgedeki diğer içerik 30 Ekim 2026 durumudur ve yeniden araştırılmadı. Bu nedenle DOC-01 kapsamında ürün başarısı iddiası üretilmedi.
