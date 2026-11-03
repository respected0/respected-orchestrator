# ADR-004 — İnsan onayı sınırı

## Durum

Kabul edildi.

## Bağlam

Bir ajanın kendi ürettiği sonucu yine kendisinin onaylayabilmesi, doğrulama zincirini anlamsız kılar. `apply` başarısız veya bayat sonucu uygulamamalı; onay sıradan bir MCP çağrısına dönüşmemeli.

## Karar

1. `apply` yalnızca yeniden çalıştırılan `check` başarılıysa, yama güncelse ve çağrı çalışan sürecin içinden gelmiyorsa uygular.
2. `maf-approve` ajan tarafından kendi kendine tetiklenebilen sıradan bir MCP aracı değildir; kimliği doğrulanmış, açık insan eylemine bağlıdır.
3. Otomatik PR merge yoktur. PR oluşturmak, onaylamak ve birleştirmek ayrı yetkilerdir.
4. Yüksek riskli değişiklik ve kapsam genişletme insan kararı gerektirir.

## Sonuçlar

- Insan onayı ekranı (`UX-03`) bu sınırı zayıflatamaz; yalnızca kanıtı görünür kılar.
- Bir ajan "onaylandı" diyerek uygulama adımını atlayamaz.
- Bu karar ürün sözleşmesinin parçasıdır; performans için gevşetilmez.

## Kaynaklar

- [Ürün sözleşmesi](../PRODUCT_CONTRACT.md) (erişim: 2026-10-30).
- [Mimari](../ARCHITECTURE.md) §2 (erişim: 2026-10-30).
- [KANIT_LOG](../ilerleme/KANIT_LOG.md) §SEC-01, "bilinen sınırlar" (erişim: 2026-10-30).
