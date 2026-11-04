# ADR-014 — GitHub entegrasyon sınırı

## Durum

Kabul edildi.

## Bağlam

Issue metni dışarıdan gelir ve güvenilmezdir; PR ve CI düzeltmeleri geri alması zor, dışarı dönük eylemlerdir.

## Karar

1. Issue salt-okunur ve güvenilmeyen plan girdisi olarak alınır.
2. Taslak PR planı sonucu yeniden doğrular (`check_result`) ve sır içeren patch'i yayımlamayı reddeder. PR yalnızca açık `operation_id` ve RPP üzerinden `confirm: true` ile açılır; operatörün verdiği dal itilir ve taslak (`--draft`) PR oluşturulur. Aynı `operation_id` farklı kanıtla yeniden kullanılamaz; aynı kanıtla tekrar çağrı ağ çağrısı yapmaz, imzalı makbuzu döndürür.
3. CI düzeltmesi tek seferde en çok bir sınırlı tur planlar: geri bildirimin SHA'sı güncel HEAD ile eşleşmeli, yorumcu yetkili olmalı, onay geri alınmamış olmalı ve tur bütçesi dolmamış olmalıdır.
4. Merge komutu üretilmez.
5. Adaptör RPP `github.issue_import|pr_plan|pr_create|ci_plan` ve CLI `github-import-issue|pr-plan|pr-create|ci-plan` yüzeyine bağlıdır.

## Sonuçlar

- Orchestrator hiçbir koşulda GitHub'da birleştirme yapmaz.
- Issue içeriği tek başına worker başlatamaz; etiketler izin listesi dışındaysa atılır.
- Kimlik bilgisi yönetimi bu kararın dışındadır (ADR-007).
- Gerçek uzak PR ve canlı CI bağlantısı henüz kanıtlanmadı; CI geri bildirimi yoklama ile alınacak, webhook dinleyicisi eklenmeyecek (ADR-020, FIX-03A/B).

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §11 (GH-01/02/03) (erişim: 2026-11-04).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §GH-01, §GH-02, §GH-03 (erişim: 2026-11-04).
