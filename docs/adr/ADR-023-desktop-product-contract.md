# ADR-023 — Masaüstü uygulaması ve ürün sözleşmesi (v1) uyumu

## Durum

Kabul edildi (6 Kasım 2026). Görev: B3-00.04. Sözleşme metni **değiştirilmedi**.

## Bağlam

`docs/PRODUCT_CONTRACT.md` üç depoda (Hub, Brain, Orchestrator) aynı kopya olmak zorundadır; Hub deposundaki
`common/conformance/` bunu ve ortak komutları ölçer. Beta.3 ile Orchestrator'ın görsel arayüzü ürüne taşınır.

## Karar

1. **Sözleşme değişikliği gerekmez.** Ortak komutlar (§5) aynen kalır; masaüstü uygulaması Orchestrator'a özgü bir giriştir ("Ürüne özel komutlar serbesttir"). Kurulum yerleşimi (§2–§4) aynı kalır, GUI program dosyaları `app\` altında kurucuyla gelir.
2. GUI hesap, çevrimiçi servis veya başka bir Respected uygulaması gerektirmez; Hub'sız tam kullanım korunur.
3. Gelecekte sözleşme metni değişirse: üç kopya **aynı değişiklikte** güncellenir, conformance koşulur, eski yol silinir (giriş bölümü: geçiş dönemi yok). Bu belge başka depoda değişiklik yapma yetkisi vermez; o depolardaki değişiklik ilgili depoda ayrı yapılır.
4. Orchestrator ayarları (`config`/RPP `settings.*`) tek kaynak kalır; GUI ayarları aynı kod yolunu kullanır.

## Sonuçlar

- **Mevcut bulgu (bu görevin kapsamı dışında, başka depoyu ilgilendirir):** 6 Kasım 2026'da
  `python -m unittest common.conformance.test_product_contract.ProductContract.test_every_repo_carries_the_same_contract`
  (Hub deposunda) **başarısız**: `AssertionError: 2 != 1 : docs/PRODUCT_CONTRACT.md differs between the repos`.
  Brain kopyası BR-028 ("migration sözleşmesi doğrulaması") ile 71–74. satırlarda ilerlemiş (`STEPS` yalnızca gerçek boşlukları
  taşır; CI yayın klasöründe tanınmayan veri dosyası olmadığını da doğrular); Hub ve Orchestrator kopyaları eski metinde.
  Düzeltme: Brain metnini diğer iki depoya aynı baytlarla taşımak. Orchestrator tarafı tek başına eşitlenirse Hub hâlâ farklı kalır,
  bu yüzden eşitleme sahibinin kararıdır ve burada yapılmadı.
- Conformance etkisi: bu ADR sözleşmeyi değiştirmediğinden Beta.3 başlangıcında yeni bir conformance kırılması yoktur; mevcut kırılma yukarıdaki sürüklenmedir.

## Kaynaklar

- `docs/PRODUCT_CONTRACT.md` giriş, §2–§5 (erişim: 2026-11-06).
- [ADR-021](ADR-021-desktop-boundary-baseline.md), [ADR-022](ADR-022-command-authority-matrix.md).
- [Kanıt kaydı](../evidence/KANIT_LOG.md) §B3-00.04 (erişim: 2026-11-06).

**Güncelleme (6 Kasım 2026):** Yukarıdaki sözleşme kopyası sürüklenmesi giderildi: Brain'deki güncel metin Hub ve Orchestrator'a kopyalandı, üç `md5` eşit, Hub `common.conformance.test_product_contract` 9 OK. Eski bulgu yukarıda tarihçe olarak kalır.
