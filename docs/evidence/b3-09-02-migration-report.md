# B3-09.02 — Migrasyon raporu

Geçerli biçim: `{'settings.json': 2}`. Her senaryo geçici bir veri kökünde koşar; ikinci koşu hiçbir şey taşımamalıdır.

## beta.1 gerçek fixture (Gemini yok)

taşınan: ['settings.json'] · biçim sonrası: 2 · ikinci koşuda taşınan: yok · yedek özgünle aynı: True

| dosya | önce (sha256) | sonra (sha256) | durum |
|---|---|---|---|
| `settings.json` | `2d3ba90aca45b551…` | `59806d69d2dcce7b…` | REWRITTEN |
| `settings.json.v1.bak` | `-` | `2d3ba90aca45b551…` | new |
| `state/evidence.json` | `bc297c5ecfda6433…` | `bc297c5ecfda6433…` | unchanged |

## beta.1 + Gemini varsayılanları

taşınan: ['settings.json'] · biçim sonrası: 2 · ikinci koşuda taşınan: yok · yedek özgünle aynı: True

| dosya | önce (sha256) | sonra (sha256) | durum |
|---|---|---|---|
| `settings.json` | `7b00c1f78078cb8b…` | `9c53fde5cf96faca…` | REWRITTEN |
| `settings.json.v1.bak` | `-` | `7b00c1f78078cb8b…` | new |
| `state/evidence.json` | `bc297c5ecfda6433…` | `bc297c5ecfda6433…` | unchanged |

## beta.2 gerçek fixture

taşınan: yok (zaten güncel) · biçim sonrası: 2 · ikinci koşuda taşınan: yok · yedek özgünle aynı: None

| dosya | önce (sha256) | sonra (sha256) | durum |
|---|---|---|---|
| `settings.json` | `59806d69d2dcce7b…` | `59806d69d2dcce7b…` | unchanged |
| `state/evidence.json` | `bc297c5ecfda6433…` | `bc297c5ecfda6433…` | unchanged |

## Gerçek yükseltme kanıtı: v0.1.0-beta.1 (motor 0.1.0b1) → bu çalışma kopyası

sonuç: **OK** · adım: 29 · uygulanamaz: 0 · başarısız: 0

- OK  old release runs
- OK  old: Gemini defaults saved
- OK  old: Gemini MCP registered
- OK  old: task completed
- OK  old: unstarted task created
- OK  old: campaign reached a terminal state
- OK  old: project started and reached a stable state
- OK  old: project killed mid-run (second phase in flight)
- OK  new release runs and is a different version (or, with the same version string, different source)
- OK  new: setup migrates in place
- OK  new: Gemini defaults moved to agy, other keys kept
- OK  new: original settings kept as .bak
- OK  new: repair is idempotent
- OK  new: health
- OK  new: old finished task still verifies
- OK  new: old task inspectable
- OK  new: old task evidence readable
- OK  new: old tasks listed
- OK  new: old unstarted task starts
- OK  new: old unstarted task runs to a result
- OK  new: old campaign status readable
- OK  new: old project status readable and unchanged
- OK  new: interrupted old project is readable and not falsely finished
- OK  new: interrupted old project resumes, or is refused only for human approval
- OK  new: interrupted old project can be cancelled
- OK  new: Gemini MCP entry removed, user's own entries kept
- OK  new: a fresh task works end to end
- OK  new: uninstall leaves no Respected entry in AI tools
- OK  new: integrations listing has no gemini

## Gerçek yükseltme kanıtı: v0.1.0-beta.2 (motor 0.1.0b2) → bu çalışma kopyası

sonuç: **OK** · adım: 29 · uygulanamaz: 3 · başarısız: 0

- OK  old release runs
- N/A old: Gemini defaults saved
- N/A old: Gemini MCP registered
- OK  old: task completed
- OK  old: unstarted task created
- OK  old: campaign reached a terminal state
- OK  old: project started and reached a stable state
- OK  old: project killed mid-run (second phase in flight)
- OK  new release runs and is a different version (or, with the same version string, different source)
- OK  new: setup migrates in place
- OK  new: settings written by the old release are read as they are and keep their keys
- OK  new: nothing to back up when the file is already in the current format
- OK  new: repair is idempotent
- OK  new: health
- OK  new: old finished task still verifies
- OK  new: old task inspectable
- OK  new: old task evidence readable
- OK  new: old tasks listed
- OK  new: old unstarted task starts
- OK  new: old unstarted task runs to a result
- OK  new: old campaign status readable
- OK  new: old project status readable and unchanged
- OK  new: interrupted old project is readable and not falsely finished
- OK  new: interrupted old project resumes, or is refused only for human approval
- OK  new: interrupted old project can be cancelled
- N/A new: Gemini MCP entry removed, user's own entries kept
- OK  new: a fresh task works end to end
- OK  new: uninstall leaves no Respected entry in AI tools
- OK  new: integrations listing has no gemini

