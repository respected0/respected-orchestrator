---
name: kod-orkestrasyon
description: Respected Orchestrator ile çoklu AI model orkestrasyonu (izole çalışma alanı). "orkestrasyon", "modeli işçi olarak çalıştır", "worktree'de dene" için kullan.
---

# Kod Orkestrasyonu (Respected Orchestrator)

Bu talimatın sahibi Respected Orchestrator'dır; MCP bağlantısı kurulduğunda sunucu bunu bağlanan AI aracına `instructions` olarak verir. Hub'da Orchestrator → "AI araçlarından kullan (MCP)" bölümünden ya da `respected-orchestrator integrations set <araç>=on` komutuyla bağlandıysa bu araçta `orchestrator_*` MCP araçları görünür.

## Kurallar
1. Ağır kodlama/refactoring işini `orchestrator_task_start` ile başlat; işçi model izole bir çalışma alanında çalışır, gerçek ağaca dokunmaz.
2. İlerlemeyi `orchestrator_progress`, kanıtı `orchestrator_evidence` ile oku.
3. Yamayı yalnızca kullanıcı onayıyla `orchestrator_apply` ile uygula (evidence'taki `patch_sha256` gerekir).
4. Master/işçi rolleri sabit değildir: kullanıcı veya Hub varsayılanı hangi modeli seçtiyse o kullanılır.
5. Tekrar kullanılabilir bir karar veya bilgi çıkarsa (görev geçmişi değil) `orchestrator_memory_note` ile Brain gelen kutusuna not bırak; yalnızca Brain kuruluysa ve kullanıcı yazma iznini açtıysa (Hub'da ya da `respected-orchestrator memory connect --write`) çalışır.
6. Başarısız, bekleyen, eski veya değiştirilmiş sonuç kabul edilmez; yeniden deneme yalnızca kullanıcının açık isteğiyle yapılır.

Orchestrator MCP bağlı değilse kullanıcıdan Hub'da ya da `respected-orchestrator integrations set <araç>=on` ile bağlamasını iste.

## Claude Master döngüsü (kampanya)

Planla, tek JSON ile devret, kapan; bekleme ve polling yapma:

`respected-orchestrator.exe --data-root DATA campaign-start < spec.json` (kaynaktan çalışırken: `python -m respected_orchestrator ...`)

Spec: `goal`, `workstreams` (1..8; her biri `name`, `after`, `request` = create isteği;
`worker=codex`, `worker_profile=deepseek`, `workflow.reviewer_profile=glm`,
`workflow.escalate_profile=glm` ile GLM zor görevi devralır ve DeepSeek review eder),
`final` (`command` varsayılan `["claude","-p","{prompt}"]`, `allow_apply` opt-in).
Detached supervisor hatları paralel yürütür; hepsi bitince yeni bir master süreç
doğrulanmış sonuçlarla bir kez başlatılır. Durum: `campaign-status ID`. Non-Git
kaynaklar geçici Git mirror'da geliştirilir; `apply RUN_ID` yalnız doğrulanmış
sonucu çalışma ağacına uygular, commit etmez. İnsan onayı (`maf-approve`) yalnız
etkileşimli terminalden verilir. MiMo profilleri reddedilir.
