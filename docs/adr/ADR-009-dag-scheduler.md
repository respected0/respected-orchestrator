# ADR-009 — DAG planı ve bağımlılık tabanlı scheduler

## Durum

Kabul edildi.

## Bağlam

Çok hatlı projelerde hatların sırası ve paralelliği modelden ya da elle yazılmış sıradan geliyordu; döngülü bağımlılık ve aynı dosyaya yazan paralel hatlar ancak çalışırken fark ediliyordu.

## Karar

1. Plan taslağı düğüm/kenar DAG'ına çevrilir ve kaydedilmeden önce motor tarafından doğrulanır: bilinmeyen kenar, döngü (tam yolla), geçersiz kapsam/komut/zaman aşımı ve ata-torun ilişkisi olmayan paralel `ownership` çakışması reddedilir.
2. `plan` yalnızca taslak üretir; worker, proje ya da kampanya başlatmaz. Başlatma ayrı `project-start` çağrısıdır.
3. Scheduler deterministik hazır kuyruğu kullanır; `max_parallel` 1–8, varsayılan `min(4, hat sayısı)`. Bağımlı hat ancak bütün öncülleri `MASTER_APPROVED` olunca başlar; başarısız, zaman aşımına uğramış ya da iptal edilmiş öncül bağımlı zinciri `SKIPPED` yapar.
4. Aynı `project_root` altında `ownership` kapsamı çakışan iki hat asla eşzamanlı çalışmaz; bağımsız hatlar boş kapasiteyi kullanır.
5. Her hat geçişi (`QUEUED → RUNNING → terminal`) zaman damgası ve nedenle imzalı `result.json` içine yazılır.

## Sonuçlar

- Geçersiz plan hiçbir worker başlatmaz.
- Çakışma çalışırken değil planlama aşamasında yakalanır.
- Çakışan kapsamlar paralelliği düşürür; bu bilinçli bir tercihtir.
- Kabul ölçümleri `KANIT_LOG.md` içindedir.

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §4 ve §5 (erişim: 2026-11-04).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §SCH-01, §SCH-02 (erişim: 2026-11-04).
