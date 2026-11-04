# Gizlilik: Respected Orchestrator

Bu metin Orchestrator `0.1.0-beta.1` için geçerlidir (2026-10-24, güncelleme 2026-11-04). Kod okunarak yazıldı; kod değişirse metin de değişir.

## Kısaca

- Orchestrator **hesap istemez, telemetri ya da kullanım istatistiği göndermez**, Respected'e hiçbir veri iletmez.
- Motorun kendisi ağa bağlanmaz. Dışarı giden her şey, görevi yapan **sizin kurduğunuz AI aracı** üzerinden ya da sizin açıkça verdiğiniz GitHub komutları (`gh` oturumunuzla) üzerinden gider.
- Projenize hiçbir şey siz onaylamadan yazılmaz.

## Bilgisayarınızda ne saklanır

| Ne | Nerede |
|---|---|
| Program | `%LOCALAPPDATA%\Respected\RespectedOrchestrator\app` |
| Ayarlar, görev ve kampanya kayıtları, kanıtlar, günlükler | `%LOCALAPPDATA%\Respected\RespectedOrchestrator\data` |
| Her görevin yalıtılmış çalışma kopyası (Git çalışma ağacı) | Veri klasöründe `workspaces/` altında |
| Kanıtları imzalayan anahtar | Veri klasöründe; yalnızca sizin kullanıcı hesabınıza açıktır |

## Bilgisayardan ne çıkar, kime gider

| Ne zaman | Ne gider | Nereye |
|---|---|---|
| Bir görev çalıştığında | Görev metni ve çalışanın çalışma kopyasında okuduğu dosyalar | Görevi yapan AI aracı (Codex, Claude, agy, Cursor, OpenCode) ve onun sağlayıcısı. Bu aktarım o aracın ve sağlayıcının kendi şartlarına tabidir |
| Brain hafıza erişimini **kendiniz açtıysanız** | Göreve uygun bulunan Brain notlarından en fazla yaklaşık 3000 karakterlik parça, görev metnine "güvenilmeyen veri" başlığıyla eklenir | Görev metniyle birlikte aynı AI aracı ve sağlayıcısı |
| GitHub işlemini **kendiniz** verdiyseniz (`github-pr-create`) | Dal ve taslak PR; yalnızca açık `confirm: true` ve `operation_id` ile | Sizin `gh` oturumunuzla GitHub |
| Cursor ya da OpenCode çalışanında ağı **kendiniz** açtıysanız (`RESPECTED_CURSOR_NETWORK` / `RESPECTED_OPENCODE_NETWORK`) | Aracın oturum dosyası (Cursor için `auth.json`) görev için yalıtılmış geçici bir klasöre kopyalanır, görev sonunda silinir; ağ açık olduğundan o süreç ağa çıkabilir | Aracın kendi sağlayıcısı |
| Doğrulama komutları çalıştığında | Görev isteğinde verdiğiniz komutlar (bir AI aracının MCP ile verdiği görevlerde yalnızca sizin önceden izin verdiğiniz önekli komutlar) kısıtlı bir Windows belirteciyle ve ortamdan sır gibi görünen değişkenler çıkarılarak çalışır | Bilgisayarınızda yerel |

Brain hafıza erişimi varsayılan olarak **kapalıdır**; Orchestrator › Ayarlar'dan ya da `memory connect` ile açılır, geri alınabilir.

## Dürüst sınırlar

- Görev metnini ve projenizin kodunu AI aracınızın sağlayıcısı görür. Kimlik bilgilerini ve çok hassas kodu görev metnine
  ya da çalışma kopyasına koymayın.
- Çalışan araç Windows'ta bir AppContainer içinde başlatılır: varsayılan olarak yalnızca görevin çalışma kopyasına yazabilir,
  ağa çıkamaz ve kullanıcı profilinizi okuyamaz. Kum havuzu kurulamazsa çalışan hiç başlamaz. Bu sınır yalnızca Windows'ta
  vardır; çalışma kopyasının **içindeki** dosyaları (örneğin `.env`) çalışan okuyabilir. Ağı kendiniz açtığınız Cursor/OpenCode
  çalışanında bu sınır ağ için geçerli değildir.
- Bu metin hukuki danışmanlık ya da sözleşme metni değildir; neyin nereye gittiğini anlatır.

## Silme

Kaldırmak programı ve AI araçlarınıza eklediği girdileri siler; projelerinize ve Git depolarınıza dokunmaz. Ayarlar, görev
geçmişi ve çalışma ağaçları varsayılan olarak kalır; "çalışma verileri de silinsin" seçeneğiyle silinir.

## Soru ve bildirim

[GitHub Issues](https://github.com/respected0/respected-orchestrator/issues)
