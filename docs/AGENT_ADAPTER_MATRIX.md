# Ajan adaptörü destek matrisi

Durum: B3-03.01 (6 Kasım 2026). Kaynak: `src/respected_orchestrator/engine/agent_adapters.py`; yeniden üretmek için `agent_adapters.matrix()`.

## Durum anlamları

| Durum | Anlamı |
|---|---|
| `verified` | Yetenek bayrağı, kurulu CLI'nin **kendi `--help` çıktısında** bulundu ve sürüm doğrulanmış tabanın altında değil. Bu, bir modelle gerçek oturum yapıldığı anlamına **gelmez**; gerçek oturum kanıtı B3-03.03'tür. |
| `source` | Belgeden/yardım metninden biliniyor ama canlı yoklamayla doğrulanmadı veya sürüm tabanın altında. Başlatma için sayılmaz. |
| `advertised_missing` | Bildirilen yetenek bayrağı kurulu CLI'de yok veya yoklama başarısız. Kapalı. |
| `unsupported` | Açıkça desteklenmiyor (ikili yok, sözleşme yok, ya da PTY kapısı henüz karar vermedi). |

Bir mod yalnızca `verified` **ve** ikili mevcut **ve** giriş yapılmış ise başlatılabilir (`usable`). PTY hiçbir ajan için açık değildir; ConPTY+AppContainer kapısı (B3-03.02) karar verene kadar `unsupported`.

## Canlı doğrulama (6 Kasım 2026, bu makine, yalnız salt-okunur yoklama: `--version`, `--help`, giriş durumu)

| Ajan | Sürüm | Sürüm durumu | Giriş | chat | pty | send_input | interrupt | resume | usage | auth | approval |
|---|---|---|---|---|---|---|---|---|---|---|---|
| codex | codex-cli 0.160.1 | ok | ok | verified | unsupported | source | source | verified | source | verified | verified |
| claude | 2.1.318 | ok | ok | verified | unsupported | verified | source | verified | source | verified | verified |
| cursor | 2026.10.22-27dcf5f | unpinned | ok | verified | unsupported | source | source | verified | source | verified | verified |
| opencode | v2.2.3 | ok | ok | verified | unsupported | source | source | verified | source | verified | verified |
| antigravity | yok | - | - | unsupported | unsupported | unsupported | unsupported | unsupported | unsupported | unsupported | unsupported |
| custom | - | - | - | unsupported | unsupported | unsupported | unsupported | unsupported | unsupported | unsupported | unsupported |

## Her ajanın yapılandırılmış (chat) yolu

- codex: `exec --json` (JSONL), `exec resume`; onay/kum havuzu `-a`/`-s`.
- claude: `-p --output-format stream-json`, `--input-format stream-json` (gerçek zamanlı girdi), `--resume`, `--permission-prompts`.
- cursor: `-p --output-format stream-json`, `--resume`, `--sandbox`. Sürüm tarih biçiminde olduğundan taban henüz sabitlenmedi (`unpinned`).
- opencode: `run --format json`, `run --session`, `--auto`. `auth list` yalnızca kayıtlı kimlik bilgisi olduğunu gösterir, geçerliliğini kanıtlamaz.
- antigravity: bu makinede çalıştırılabilir ikili yok (yalnızca gömülü `rg`); `unsupported`.
- custom: kullanıcı komutları hakkında hiçbir yetenek varsayılmaz.

## Bilinen sınırlar

- `interrupt`, `usage` ve (claude hariç) `send_input` yalnızca `source`: işlem sonlandırmanın ötesinde yoklanmış bir mesaj protokolü yok. B3-03.03/04 gerçek oturumda ölçmeden `verified` olmaz.
- Yoklama ücretli model çağrısı yapmaz.
