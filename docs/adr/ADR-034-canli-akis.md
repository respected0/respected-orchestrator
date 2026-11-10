# ADR-034: Canlı akış ve sayfalı konuşma geçmişi

## Durum

Kabul edildi ve uygulandı (10 Kasım 2026; tasarım kararı yön kararı gereği ajana bırakıldı). Kod: `engine/session_control.py`, `engine/daemon.py` (`Subscriber`, `_stream`), `engine/daemon_client.py` (`subscribe`), masaüstünde `engine_connector.rs` (`subscribe`, `next_note`), `lib.rs` (`engine_subscribe`), `Sessions.tsx`. Test: `tests/engine/test_live_stream.py`, `desktop/tests/sessionlog.test.ts`, `desktop/tests/chatmodel.test.ts`, `engine_connector.rs` ve `tests/acl.rs` içindeki testler.

## Sorun

Sohbet ekranı çalışan oturum varken motoru saniyede bir yokluyordu. Bir turun çıktısı ancak tur bitince okunabiliyordu (ajan süreci bitene kadar bekleniyordu) ve `session.transcript` konuşmanın tamamını tek yanıtta veriyordu. 1.7 (onay isteğinin istemciye yollanması) için motorun istemciye kendiliğinden veri yollayabilmesi gerekiyor.

## Rakipler nasıl yapıyor

Kaynak: `KALAN_ISLER.md` 4.4 ve `RAKIP_ESKIKLERI.md` §1c (10 Kasım 2026'da resmî belge ve depolardan okundu; bu iş için yeniden okunmadı, hiçbir ürün çalıştırılmadı).

- **AO (birincil örnek):** değişiklikleri sunucudan istemciye tek yönlü bir akışla (SSE) yollar; komutlar ayrı isteklerle gider. Sohbet sayfalıdır ve yalnız değişen kısım yenilenir.
- **Codex:** `app-server` çift yönlü JSON-RPC'dir; `item/agentMessage/delta` gibi bildirimler aynı bağlantıdan akar.
- **Claude Code:** `stream-json` çıktısı.

## Karar

1. **Tur satır satır okunur.** `run_killable` ajanın çıktısını geldikçe `on_line`'a verir; `SessionController` her satırı `chat_session.normalize` ile olaya çevirir, turun `live` listesine ekler ve dinleyicilere bildirir. Olay numarası (`seq`) bitmiş turun numarasıyla aynıdır; bitmiş turun sonucu yine bütün çıktıdan hesaplanır ve tek doğru kaynaktır.
2. **Akış ayrı, tek yönlü bir bağlantıdır (AO'nun yolu).** İstemci boruya yeni bir bağlantı açar ve `events.subscribe {project_id}` yollar. Yanıttan sonra o bağlantıdan yalnız motor yazar; istemci bir şey yollamaz, aboneliği bitirmek için bağlantıyı kapatır. Komutlar eskisi gibi kendi bağlantılarından gider. Böylece istek-yanıt yolu değişmedi ve bir bağlantıya iki iş parçacığı aynı anda yazmıyor.
3. **Bildirim biçimi:** `{"ipc": "1", "event": AD, "data": {...}}`; `id` taşımaz. İki ad var:
   - `session.event`: `{session_id, turn, event}`; çalışan turun bir olayı (`event.seq` sırayı verir).
   - `session.state`: `{session}`; oturumun yeni görünümü (tur başladı, bitti, durduruldu, oturum bitti ya da sürdürüldü).
4. **Abone yalnız kendi `project_id`'sinin oturumlarını duyar** (oturumlar zaten `(session_id, project_id)` ile adreslenir). Komut `READ` sınıfıdır; işçi soyundan gelen bağlantı (`CHILD`) abone olamaz.
5. **Yavaş okuyan kesilir.** Abone başına en çok 2000 bildirim bekler; taşarsa motor bağlantıyı kapatır. İstemci yeniden abone olur ve durumu baştan okur. Kapanan istemci en geç iki saniyede fark edilir, böylece ölü abone motoru uyanık tutmaz.
6. **Kaçırılan olay tahmin edilmez.** Abonelik, yanıt yazılmadan önce kurulur; istemci "abone ol, sonra durumu oku" sırasını izler. Ekran sıradaki `seq`'i bekler; boşluk görürse `session.transcript`'i yeniden okur (yanıttaki `live` çalışan turun o ana kadarki olaylarıdır).
7. **Geçmiş sayfalıdır.** `session.transcript {session_id, before?, limit?}` en yeni sayfayı verir (varsayılan 50 tur, en çok 200). Yanıttaki `first`, dönen ilk turun sırasıdır; bir üst sayfa için `before` olarak geri yollanır, `0` ise daha eskisi yoktur. `total` tur sayısı, `usage` bütün konuşmanın toplamıdır.
8. **Yoklama kalktı.** Sohbet ekranındaki bir saniyelik zamanlayıcı silindi; liste yalnız `session.state` gelince, akış yeniden kurulunca ve kişinin kendi işleminden sonra okunur.

## Yüzler (dikey dilim)

| Yüz | Ne var |
|---|---|
| Motor | `events.subscribe` (katalogda bir satır), `session.events` yanıtında `live`, `session.transcript`'te sayfalama ve `live` |
| CLI | `rorch session watch PROJE`: her bildirimi bir JSON satırı olarak yazar, Ctrl+C ile biter |
| MCP | Araç çağrısı bildirim alamaz; `orchestrator_session_events` çalışan turun olaylarını `live` içinde verir, `orchestrator_session_transcript` `before` ve `limit` alır |
| Masaüstü | Kabuk akışı kendi bağlantısında açar (`engine_subscribe`) ve her bildirimi yalnız `main` penceresine `engine-event` olarak iletir; ekran çalışan turu geldikçe çizer, "Daha eski turları göster" bir üst sayfayı okur |

## Yapılmayanlar

- **Görev panosu hâlâ yokluyor** (4 saniyede bir). Görev koşuları motordan ayrı süreçlerde dosyaya yazar; onları akışa bağlamak dosya değişikliklerini izlemeyi gerektirir (AO'daki CDC'nin karşılığı).
- **Harf harf akış yok.** `opencode run --format json` metni parça tamamlanınca verir; ekran parça parça ilerler. Daha ince akış ajan adaptörünün işidir (3.2).
- **Kayıtlı konuşmanın silinmesi bildirilmez** (kayıtlar `project_id` taşımıyor); silen ekran listeyi kendisi yeniler.
- **Sayfa imleci konum numarasıdır.** Kayıt 200 turu aşınca en eski tur düşer ve numaralar kayar; o an okunan üst sayfa bir tur kayabilir.
- Unix soketi yok (1.4); akış bugün yalnız Windows adlandırılmış borusunda.
