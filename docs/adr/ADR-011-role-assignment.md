# ADR-011 — Rol atama, coordinator ve tester sınırları

## Durum

Kabul edildi.

## Bağlam

Her model her role atanabilmeli, ama planlayıcı bir model prompt enjeksiyonuyla yetki kazanmamalı ve doğrulama modele bırakılmamalı.

## Karar

1. Kod hiçbir zaman "X modeli yalnızca Y rolünü yapar" demez. Kavramlar ayrıdır: rol, profil, araç, atama.
2. Öncelik: açık atama, ayarlardaki varsayılan, ancak `auto_assign` açıksa `auto_pool` içinden otomatik öneri. Açık seçim sessizce değiştirilmez; yalnızca atamanın kendi `fallbacks` listesi devreye girer.
   Otomatik öneri bu kurulumun kendi imzalı geçmişinden gelir (`track_record.py`): yumuşatılmış tamamlanma oranı, başka rolün kullanmadığı profil, daha düşük ortalama belirteç, havuz sırası. Aday elemez, yalnızca sıralar. Görev zorluğu ve fiyat sıralamaya girmez.
3. `coordinator` yalnızca doğrulanmış DAG ve rol ataması döndürür. Shell, worker başlatma, kampanya/proje başlatma ve apply yetkisi yoktur; bu yöndeki öneriler plan doğrulamasından önce reddedilir. Tek görevde coordinator `ROLE_NOT_EXECUTABLE` döner.
4. `tester` motorun sahip olduğu doğrulama aşamasıdır: yalnızca görevin kabul komutlarını bir kez AppContainer içinde çalıştırır, serbest komut kabul etmez ve imzalı `tester-report.json` üretir. MAF gözden geçirici bu kanıtı doğrulamadan çalışmaz.
5. `require_independent_review` açıksa çalışanla aynı profili kullanan gözden geçirici `ROLE_INDEPENDENCE`'tır.

## Sonuçlar

- Geçersiz coordinator planında 0 worker başlar.
- Yeni model eklemek rol koduna dokunmayı gerektirmez.
- Hiçbir adayın 3 ya da daha fazla kaydı yoksa öneri ölçüm sayılmaz ve `basis: pool_order` olarak işaretlenir.
- `engine/pricing.py` sürüm kontrollü bir fiyat kataloğu sağlar (bilinmeyen fiyat `unknown` kalır, sıfıra çevrilmez) ama rol ataması bu kataloğu kullanmaz; yalnızca testlerde çağrılır.

## Kaynaklar

- [Mimari](../ARCHITECTURE.md) §4 (erişim: 2026-11-04).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §QUA-01, §SCH-04 (erişim: 2026-11-04).
