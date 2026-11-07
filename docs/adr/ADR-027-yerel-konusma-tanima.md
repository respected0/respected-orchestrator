# ADR-027 — Uygulama içi sesli görev taslağı: yerel konuşma tanıma Go/No-Go

## Durum

Kabul edildi (8 Kasım 2026). Görevler: B4-06.01, B4-06.02, B4-06.03. Özellik **kapalı gelir** (`voice_enabled=false`). Ortak komut listesi ve
`docs/PRODUCT_CONTRACT.md` değişmedi.

## Bağlam

Ses yalnızca görev **taslağı** için metin girdisidir; yürütme, onay ya da uygulama emri değildir. Gereksinimler: çevrimdışı, kullanıcı denetimi, kayıt
varsayılan yok, ses ağa çıkmaz, diske yazılmaz, kapatma anlık.

## Ölçülen durum (bu makine, 8 Kasım 2026)

| Ne | Sonuç |
|---|---|
| Windows `System.Speech` yüklü tanıyıcılar | **Yok** (`InstalledRecognizers()` boş; yalnız en-US sentez sesi var) |
| Python konuşma paketleri (`faster_whisper`, `whisper`, `vosk`, `speech_recognition`) | Başlangıçta yüklü değildi. Kullanıcı izniyle yalnız `%LOCALAPPDATA%\respected-orchestrator-stt\` altında yalıtık bir sanal ortama `faster-whisper 1.2.1` ve modele `Systran/faster-whisper-small` (MIT, ücretsiz; `model.bin` 483 546 902 bayt) indirildi; özetler `docs/evidence/b4-06-01-stt-measurement.json` |
| Mikrofon donanımı | Var (3 uç nokta; izin ve yakalama masaüstü arayüzünün işi) |
| Oturum (tampon) maliyeti, 60 sn 16 kHz/16 bit mono | **0,019 sn** besleme, **1,9 MB** tutulan, tepe bellek ~1,9 MB; durdurunca **0** bayt |
| Konuşma tanıma (İngilizce, 4 cümle, Windows sesiyle üretilmiş ses) | Kelime hata oranı **%8,6** (cümle başına %0–14,3); soğuk çağrı 4–7,5 sn (model yükleme dahil), ılık ~4–6,5 sn / ~4 sn ses; tepe bellek **692 MB**; ölçüm tam test paketi aynı makinede koşarken yapıldı (gecikme için üst sınır) |
| Türkçe doğruluk | **Ölçülemedi**: makinede Türkçe ses üretecek bir kaynak yok; ölçmek için `packaging/voice/measure_stt.py` kişinin kaydettiği 16 kHz mono WAV'larla çalışır |

## Karar

1. **Çerçeve: GO.** `engine/voice.py` her koşulda geçerli kalan güvenceleri taşır: ayar kapalı; izin yoksa kayıt başlamaz (`NO_PERMISSION`); kayıt yalnız bas-konuş
   (`arm` → `start`) ile; izin geri alınırsa, ayar kapatılırsa, süre (60 sn) ya da boyut aşılırsa anında kapanır ve ses atılır; ses yalnız bellekteki bir `bytearray`'de
   durur ve `stop`/`wipe`/silinme ile sıfırlanır; modülün diske yazan ya da ağ kullanan hiçbir kodu yoktur (kaynak taraması + soket engelli test).
2. **Paketlenmiş motor: NO-GO (şimdilik).** Orchestrator hiçbir tanıma modeli indirmez ya da dağıtmaz: makinede motor yoktur ve model indirmek kullanıcının açık
   izni, kaynağı ve boyutu belirtilmiş bir indirme gerektirir (bu karar için verilmedi). Motor **kişinin seçtiği yerel bir program** olabilir (`voice_engine_command`,
   JSON liste): ses yalnızca programın stdin'ine gider, dil ve sözlük argümandır. Bu program Orchestrator tarafından **sandbox'lanmaz**; çevrimdışı olması kişinin
   sorumluluğundadır ve rapor bunu `network_isolated: false` olarak söyler. Bulut yedeği yoktur.
3. **Taslak güvenliği:** metin yalnızca `Draft`'a girer (`needs_review=true`, `confirmed=false`); `confirm` kişinin düzenlenmiş metnini ve İNSAN kökenini ister;
   `require_confirmed` onaylanmamış sesli metni reddeder. "approve/apply/merge/delete/onayla/uygula/sil/birleştir" sözcükleri **işaretlenir** ama yalnızca metindir;
   taslakta eyleme dönüşebilecek alan yoktur. Proje sözlüğü (bağlam haritasındaki sembol adları + kişinin listesi) yanlış duyulan terimleri düzeltir ve her düzeltme
   listelenir (vurgu için). Türkçe `İ/ı` katlaması bilinir.
4. **Erişilebilirlik:** yazarak giriş her zaman vardır ve kapı dışıdır (`require_confirmed` düz metni geçirir).

## Sonuçlar ve sınırlar

- İngilizce başarım ölçüldü; **Türkçe teknik terim doğruluğu ölçülmedi** (Türkçe ses kaynağı yok). Ölçüm, 'rename' gibi sıradan bir sözcüğü 'readme'ye çevirme hatasını ortaya çıkardı; düzeltici artık yalnız tek harflik kaymaları uygular, iki harflik yakınlıkları öneri olarak bırakır (`applied: false`). Masaüstü arayüzünde mikrofon izni ve bas-konuş düğmesi bu depoda henüz bağlı değildir (motor tarafı hazırdır).
- `voice_engine_command` programının ağını doğrulamak mümkün değildir.
- OS mikrofon izni durumunu okuyan kod (`permission` çağrısı) arayüz tarafındadır; test çift ile doğrulandı.

## Kaynaklar

- `src/respected_orchestrator/engine/voice.py`, `engine/authority.py`, `workflows/roles.py` (ayarlar `voice_enabled`, `voice_engine_command`) (erişim: 2026-11-08).
- Kanıt: `tests/engine/test_voice.py` (21), `docs/evidence/KANIT_LOG.md` B4-06 (erişim: 2026-11-08). Ölçümler: bu makinede `System.Speech` tanıyıcı yoklaması ve 60 sn'lik oturum beslemesi (erişim: 2026-11-08).
