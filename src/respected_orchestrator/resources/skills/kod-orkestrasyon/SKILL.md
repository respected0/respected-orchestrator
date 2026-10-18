---
name: kod-orkestrasyon
description: Bağımsız Respected Orchestrator ile bounded scope içinde AI worker görevi çalıştırma ve sonuç inceleme.
---

# Kod Orkestrasyonu

Respected Hub üzerinden Git projesini, worker'ı, read/write türünü ve explicit
dosya scope'unu seç. Write için doğrulama komutunu JSON argv listeleri olarak ver.
Kullanıcı veya herhangi bir AI planlayıcı task metnini hazırlayabilir; worker
Codex, Claude, Gemini, Antigravity veya uyumlu özel komut olabilir.

Engine DataRoot altında bağımsız teknik state ve workspaces kullanır. Brain
kurulumu veya kasa UUID'si gerekmez. Worker ayrı worktree'de çalışır. Ana proje
otomatik değiştirilmez. Görev deadline'ı bütün worker/test süresini sınırlar;
permission bypass varsayılan değildir ve engine tarafından reddedilir.

Hub'dan status, log, doğrulama sonucu ve binary patch'i incele; Cancel ile çalışan
görevi durdur. Hub kapanınca engine sürer. Başarısız/pending/stale/tampered sonuç
kabul edilmez. Retry yalnız açık kullanıcı eylemiyle yapılır ve iki retry ile
sınırlıdır. Ana projeye patch entegrasyonu bu geliştirme sürümünde dış inceleme
sonrası `apply` komutuyla yapılır.

Codex worker'ları açık `--sandbox workspace-write` ve onaysız modda çalışır;
ortamdaki secret benzeri değişkenler worker'a geçmez. Diğer CLI'ler için scope
denetimi tam OS sandbox değildir; onların approval/sandbox kontrollerini koru. Salt read işi repository diff
üretirse başarısız sayılır. Brain'e kalıcı kayıt isteğe bağlı ayrı bir işlemdir.

## Claude Master döngüsü (kampanya)

Planla, tek JSON ile devret, kapan; bekleme ve polling yapma:

`python -m respected_orchestrator --data-root DATA campaign-start < spec.json`

Spec: `goal`, `workstreams` (1..8; her biri `name`, `after`, `request` = create isteği;
`worker=codex`, `worker_profile=deepseek`, `workflow.reviewer_profile=glm`,
`workflow.escalate_profile=glm` ile GLM zor görevi devralır ve DeepSeek review eder),
`final` (`command` varsayılan `["claude","-p","{prompt}"]`, `allow_apply` opt-in).
Detached supervisor hatları paralel yürütür; hepsi bitince yeni bir master süreç
doğrulanmış sonuçlarla bir kez başlatılır. Durum: `campaign-status ID`. Non-Git
kaynaklar geçici Git mirror'da geliştirilir; `apply RUN_ID` yalnız doğrulanmış
sonucu çalışma ağacına uygular, commit etmez. İnsan onayı (`maf-approve`) yalnız
etkileşimli terminalden verilir. MiMo profilleri reddedilir.

Provenance: Brain `resources/skills/kod-orkestrasyon/SKILL.md` içindeki görev,
izolasyon ve yama sözleşmesinden çıkarıldı; eski vault/dashboard komutları
bağımsız ürün akışına uyarlandı. Diğer provider ayarlarına kurulum yapma.
