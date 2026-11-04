# ADR-003 — Şema değişikliği göç kapısı

## Durum

Kabul edildi ve uygulandı (REL-02).

## Bağlam

Kullanıcı verisi dosyaları biçim sürümü taşıyor. Yeni bir sürüm yazıp göç adımını unutmak, eski kurulumlarda veri kaybı veya sessiz bozulma üretebilir.

## Karar

1. Her veri dosyası için `CURRENT` sürümü, `STEPS` içinde eski sürümden yeni sürüme adımlar ve `tests/fixtures/releases/<sürüm>/` altında o sürümün gerçek çıktısı bulunur.
2. Göç fail-closed çalışır: adım eksikse `MigrationError`; hiçbir dosya yazılmaz.
3. Yazma atomiktir; başarısız göç orijinal byte'ları korur.
4. İlk başarılı göç öncesi `.bak` oluşturulur; aynı göç ikinci kez çalıştırıldığında byte düzeyinde değişiklik olmaz.
5. `CURRENT` artırılıp adım/fixture eklenmezse test kapısı kırılır ve değişiklik birleştirilmez.

## Sonuçlar

- Göç sözleşmesi test edilir; yalnızca dokümana güvenilmez.
- Yeni yayın fixture'ı eklemek her yeni biçim sürümünde zorunludur.
- CI'da ayrı bir "diff'te CURRENT değişti mi" kontrolü yok; koruma test suite'inin kırılmasına dayanıyor (bilinen sınır).

## Kaynaklar

- [REL-02 kanıtı](../evidence/KANIT_LOG.md) §REL-02 (erişim: 2026-10-30).
- [rel02_gate_proof.txt](../evidence/poc/rel02_gate_proof.txt) — adımsız sürüm artırımının reddi (erişim: 2026-10-30).
- [Mimari](../ARCHITECTURE.md) §8 (erişim: 2026-10-30).
