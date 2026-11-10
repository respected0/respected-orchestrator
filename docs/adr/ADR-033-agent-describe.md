# ADR-033: `agent.describe` ortak şeması

## Durum

Kabul edildi ve uygulandı (10 Kasım 2026, kullanıcı onayı). Kod: `engine/agent_describe.py`; test: `tests/engine/test_agent_describe.py`.

## Sorun

Masaüstü, bir ajanın neyi desteklediğini (sohbet, terminal, kipler, modeller, komutlar, bağlam) elle biliyor. Motorda iki ayrı yoklama var (`agents.discover`, `capabilities.matrix`); ikisini de ekran kullanmıyor. Yeni ajan eklemek ekranı değiştirmeyi gerektiriyor.

## Orchestrator.inc nasıl yapmış

Kaynak: AO deposu `main`, 10 Kasım 2026'da okundu (`docs/STATUS.md`, `backend/internal/domain/agent_readiness.go`, `ports/chat.go`, `ports/agent.go`, `domain/agentconfig.go`). Ürün çalıştırılmadı.

AO bu bilgiyi tek cevapta değil, dört ayrı parçada tutar:

1. **Hazırlık anlık görüntüsü** (ajan seçici bunu okur): ajan başına `installation` ve `authentication` gözlemi (durum, tazelik, denetim zamanı, neden kodu ve metni) ve bunlardan türeyen `effectiveReadiness` (`ready` / `not_ready` / `unknown`).
2. **Yetenek bayrakları**: sohbet sürücüsü `Probe` ile, hiçbir şey başlatmadan, adlandırılmış bayraklar kümesi döndürür (`streaming`, `tools`, `approvals`, `interrupt`, `steer`, `resume`, `history`, `usage`, `plan_mode`, `models`, `config_options`, `compaction`, `rollback`, `fork`, `rename`, `skills`, `rate_limits`, `images`, …). Sohbet ancak taban bayraklar (`streaming`, `approvals`, `interrupt`, `resume`) varsa açılır.
3. **Model kataloğu** ayrı ve önbellekli: seçim biçimi (`catalog` / `text` / `mode`), modeller (ad, etiket, çaba düzeyleri, bağlam penceresi, varsayılan), kaynak, alınma zamanı, bayatlık.
4. **İzin kipleri** dört ortak addır (`default`, `accept-edits`, `auto`, `bypass-permissions`); adaptör ajanın kendi adına çevirir. Arayüz iki tanedir (`chat`, `tui`); aralarında geçiş ayrı bir yetenektir ve sohbet kaydından çıkarsanmaz.

## Karar

Tek motor komutu: **`agent.describe {agent?}`**. `agent` verilmezse bütün ajanlar döner (`{agents: [...]}`). Cevap AO'nun dört parçasını tek zarfta toplar; alan adları AO'nunkilerle aynıdır.

```json
{
  "agent": "claude",
  "checked_at": "2026-11-10T12:00:00+00:00",
  "version": "2.1.319",
  "readiness": {
    "installation":   {"state": "installed"},
    "authentication": {"state": "unauthorized"},
    "effective": "not_ready",
    "reason": "auth_required: not logged in"
  },
  "interfaces": {
    "chat":     {"status": "unverified", "source": "doc",  "note": "-p --output-format stream-json"},
    "terminal": {"status": "unsupported", "source": "none", "note": "the interactive terminal (PTY) is not wired yet"},
    "handoff":  {"status": "unsupported", "source": "none", "note": "needs both interfaces"}
  },
  "capabilities": {
    "resume":    {"status": "native", "source": "probe", "note": "--resume <id>, --continue"},
    "approvals": {"status": "native", "source": "probe", "note": "--permission-prompts host"}
  },
  "modes":    {"status": "native", "source": "probe", "note": "`--help`", "items": [{"id": "default", "native": ""}, {"id": "accept-edits", "native": "acceptEdits"}, {"id": "plan", "native": "plan"}]},
  "models":   {"status": "native", "source": "probe", "note": "--model in `--help`", "selection": "text", "items": []},
  "commands": {"status": "unverified", "source": "doc", "items": []},
  "context":  {"status": "unverified", "source": "doc"},
  "extra": []
}
```

Kurallar:

1. **Durum sözlüğü üç değerdir:** `native` (ajan veriyor ve bu makinede görüldü), `unsupported` (sunulmuyor), `unverified` (belgede ya da adaptör tablosunda var, bu makinede görülmedi). `KALAN_ISLER.md`'deki "doğrulanmadı" tel üzerinde `unverified`'dır.
2. **Kaynak:** `probe` (yüklü CLI'ın kendi yardım metninde ya da giriş durumunda görüldü), `doc` (yalnız belge), `none`. `native` yalnız `probe` ile verilir. Sürüm, doğruladığımız tabandan eskiyse `native` verilmez.
3. **Hiçbir ajan çalıştırılmaz.** Yalnız bugünkü salt-okunur yoklamalar (`--version`, `--help`, giriş durumu) kullanılır; token harcanmaz. Bu yüzden komut `READ` sınıfındadır.
4. **Yetenek adları AO'nun bayrak adlarıdır.** Cevapta yalnız adaptör tablosunda karşılığı olan bayraklar bulunur; bulunmayan bayrak "yok" demektir ve ekran onu çizmez (karar 12: uydurma yok).
5. **Kipler:** AO'nun dört ortak adı `id`, ajanın kendi adı `native` alanındadır. Ajanın dört adın dışındaki kipi (ör. `plan`) kendi adıyla listelenir. `default` hiçbir bayrak geçirmez (ajanın kendi tabanı). Yalnız yardım metninde görülen kipler listelenir.
   Hazırlıkta kurulum ve giriş durumları ayrı, neden tek alandadır (`reason`, keşfin verdiği metin). Sohbet arayüzü yalnız akışı gerçekten doğrulanmış ajanda `native`'dir; bayrağın yardımda görünmesi yetmez.
6. **Model listesi bu cevaba girmez**, AO'daki gibi ayrı kalır: `models.status` model seçilebildiğini (`--model` bayrağı) söyler; `selection` `catalog` ise liste var olan `session.models` komutundan gelir (o komut CLI'ı çalıştırdığı için ayrı tutulur), `text` ise ad elle yazılır. `items` şimdilik hep boştur.
7. **`commands` ve `context`** canlı oturum ister (Claude Code'da `init.slash_commands`, `get_context_usage`). Gerçek koşu yapılana kadar (3.3, `[A]`) `unverified` ve boş kalır.
8. **`extra`:** şemada karşılığı olmayan her şey için etiket/değer listesi (karar 9); ekran olduğu gibi çizer.
9. **Tazelik:** `checked_at` ve bugünkü 30 saniyelik süreç içi önbellek. AO'nun `fresh` / `stale` / `checking` durumları ve eşgüdümcüsü şimdi alınmaz; yoklama yavaş kalırsa eklenir.

## Yüzler (dikey dilim)

| Yüz | Ne eklenir |
|---|---|
| Motor | `engine/agent_describe.py`: `agent_adapters.verify` ve `agent_discovery.discover` çıktısını şemaya çevirir. Adaptör tablosuna (`ADAPTERS`) kip eşlemesi eklenir |
| Katalog | `Entry("agent.describe", READ, cli=("describe", "agent"), mcp=(...), desktop="session")`; masaüstü dosyaları yeniden üretilir |
| CLI | `rorch session describe [ajan]` (`models` ile aynı kalıp) |
| MCP | `orchestrator_agent_describe`, salt okunur |
| Masaüstü | Yeni sohbet sayfası varsayılan ajanın durum satırını `agent.describe`'tan gösterir (hazır / hazır değil ve motorun verdiği neden). Ajan seçici yok: sohbet bugün tek ajanla çalışıyor |
| Test | Sözleşme testi (AO'nun kayıt sözleşmesi testinin karşılığı): her adaptör satırı şemaya uyar, durumlar sözlükten, `native` yalnız `probe` ile; sahte yoklamayla "CLI yok", "giriş yok", "sürüm eski", "bayrak kayboldu" durumları |
| Belge | `ARCHITECTURE.md`, `COMMANDS.md`, `KALAN_ISLER.md` |

## Verilen iki karar (10 Kasım 2026, kullanıcı)

1. `capabilities.matrix` komutu, `capability_matrix.py` ve testi silindi; `agent.describe` yerine geçti. `agents.discover` kaldı.
2. Kip adları: AO'nun dört ortak adı ve ajanın kendi adı birlikte verilir.

## Yapılmayanlar

- Ajan çalıştırarak doğrulama (3.3, 3.6; `[A]`).
- Terminal arayüzü ve geçiş (3.4): bayrakların yeri hazır, değerleri `unsupported`.
- Oturum içi canlı ayarlar (AO'nun `config_options`'ı): canlı oturum ve 4.4 ister.
