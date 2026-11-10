# ADR-032: Tek işlem kataloğu (kalıcı motor dilim 6)

## Durum

**Kabul edildi ve uygulandı (10 Kasım 2026).** Kullanıcı iki açık soruyu ("masaüstü listeleri nasıl beslensin", "kapsam ne olsun") ürün hedefine ve rakiplere bakarak karara bağlamayı bana bıraktı; gerekçe aşağıda. Kaynak karar: `RAKIP_ESKIKLERI.md` §6 madde 3 ("CLI, MCP ve masaüstü motordaki tek katalogdan beslenir; yeni özellik üçünde birden görünür") ve ADR-030 dilim 6.

## Bağlam

Aynı motor komutu beş yerde elle yazılıydı; biri unutulursa özellik o yüzde görünmüyor ya da izin listesi sessizce ayrışıyordu:

| Yer | İçerik |
|---|---|
| `engine/local_api.py` `COMMANDS` | 67 komut: ad → (RPP işlemi, yetki sınıfı) |
| `__main__.py` `SESSION_COMMANDS`, `SESSION_ARGUMENT` | `rorch session <fiil>` → motor komutu |
| `interfaces/mcp_server.py` `SESSION_TOOLS` | `orchestrator_session_*` → motor komutu + açıklama + şema |
| `desktop/src-tauri/src/engine_connector.rs` | `SESSION_COMMANDS`, `VOICE_COMMANDS`, `ATTACH_COMMANDS`, `READ_COMMANDS` |
| `desktop/src/contracts/ipc.ts`, `sessionlog.ts` | Aynı listelerin TypeScript kopyaları |

## Rakipler nasıl yapıyor

Codex, Orchestrator.inc ve Herdr satırları 10 Kasım 2026'da resmî belgeden okundu (ayrıntı: `RAKIP_ESKIKLERI.md` §1c); OpenCode ve ACP satırları genel bilgidir, yeniden doğrulanmadı.

| Ürün | Tek kaynak | Ön yüzler nasıl beslenir | MCP yüzü |
|---|---|---|---|
| Codex | `codex app-server` protokolü (JSON-RPC) | TypeScript tipleri `codex app-server generate-ts` ile **üretilir**; yetenekler bağlantı başında `initialize` ile bildirilir; model listesi çalışırken `model/list` ile sorulur | `codex mcp-server` kaldırıldı; bütünleşme app-server üzerinden |
| Orchestrator.inc | Go arka plan sürecinin veri tipleri | OpenAPI tanımı tiplerden, TypeScript tipleri ondan **üretilir**; CI ayrışmayı denetler | Ayrı |
| Herdr | `herdr-core` API'si | `hc schema` API'yi OpenRPC olarak verir; uygulama istemcilerden yalnız biridir | Yok |
| OpenCode | Sunucunun OpenAPI tanımı | SDK tanımdan **üretilir**; terminal, masaüstü ve web aynı sunucunun istemcisidir | Ayrı, dar |
| Claude Code | Agent SDK denetim protokolü | Türler sabittir; kullanıcıya dönük komut listesi (`slash_commands`) çalışırken `init` mesajıyla gelir | Ayrı |
| ACP (Zed) | Şema dosyası | Türler şemadan üretilir; hangi yeteneğin açık olduğu bağlantı başında (`initialize`) pazarlık edilir | Yok |

Ortak desen iki katmanlıdır: **biçim ve izin derleme zamanında tek kaynaktan üretilir, neyin kullanılabilir olduğu çalışırken sorulur.** Hiçbiri izin listesini çalışırken sunucudan alıp güvenlik sınırı olarak kullanmaz; hiçbiri MCP'ye tüm kataloğu otomatik açmaz. Hepsinde iş komutları (görev başlat, oturum, durum) tek sunucudan geçer.

## Karar

1. **Tek tablo: `engine/catalog.py`.** Her satır bir motor komutudur: `name`, `action` (yetki sınıfı), `op` (RPP işlemi) ve isteğe bağlı yüzler: `cli` (`rorch session` fiili ve girdi biçimi), `mcp` (araç adı, açıklama, girdi şeması, salt-okunur mu), `desktop` (iletim listesi: `session` / `voice` / `attach` / `read`). Yüzü boş olan komut o yüzde görünmez; bu bir karardır, unutma değildir (MCP yüzü rakiplerdeki gibi elle seçilir).
2. **`local_api.COMMANDS` tablodan türetilir** (biçimi aynı). Yetki denetimi (`authority.py`), `only=` izin listesi ve motorun `SERVED` kümeleri değişmedi: güvenlik sınırı taşınmadı, yalnız kaynağı tekleşti.
3. **`catalog.list`** (`READ`): çağıranın çalıştırabildiği satırları verir (`handle` ile aynı iki denetim: bağlantının izin listesi ve köken). Ortak uçta yetkili komut görünmez; işçi soyundan gelen bağlantı hiçbir şey göremez.
4. **CLI ve MCP tablodan kurulur:** `rorch session` fiilleri `catalog.CLI`, `orchestrator_session_*` araçları `catalog.MCP`. Dış davranış (adlar, şemalar) aynı.
5. **Masaüstü listeleri üretilir, çalışırken alınmaz** (rakiplerdeki iki katmanın ilki): `python -m respected_orchestrator.engine.catalog` `desktop/src/contracts/catalog.ts` ve `desktop/src-tauri/src/catalog.rs` dosyalarını yazar; `ipc.ts`, `sessionlog.ts` ve `engine_connector.rs` bunları kullanır. `tests/engine/test_local_api.py` depodaki dosyaların tabloyla aynı olduğunu ölçer. JSON yerine iki kaynak dosyası seçildi: TypeScript'te komut adlarının tür olarak kalması (`as const`) ve Rust'ta listelerin derleme zamanı sabiti olması için.
6. **Kapsam: yalnız motor komutları.** Süreç içi MCP araçları (görev, proje, kampanya, apply, not) ve ~45 eski CLI komutu motor komutu değildir; tanımlarını tabloya kopyalamak iki ayrı çalıştırma yolunu tek gibi gösterirdi. Doğru yön rakiplerdeki gibi bunları motora taşımaktır; ayrı iştir (`KALAN_ISLER.md` §1).

## Bilerek yapılmayanlar

- Genel bir `rorch call <komut>` yolu (istenmedi).
- Masaüstünün `catalog.list`'i çağırıp ekranları ona göre açıp kapatması: komut hazır ve `read_call` ile iletilebilir, ama bugün ona ihtiyaç duyan ekran yok.
- Ekrana özgü kullanım listeleri (`voicedraft.ts`, `attachdraft.ts`, `beta4.ts`) yerinde kaldı: izin listesi değiller, kendi testleri sözleşmede olduklarını ölçüyor.

## Sonuçlar

Yeni bir motor komutu tek satırla eklenir ve doldurulan yüzlerde görünür; beş elle yazılı liste bire indi. Yeni komutta unutulabilecek tek adım üretim komutunu çalıştırmaktır, onu da test yakalar.

## Doğrulama

- `tests/engine/test_local_api.py`: yüzlerin tablodan kurulduğu; MCP "salt-okunur" işaretinin motorun yetki sınıfıyla aynı olduğu; yetkili komutun hiçbir yüzü olmadığı; `catalog.list`'in köken ve bağlantıya göre süzdüğü; üretilmiş dosyaların ayrışmadığı.
- `tests/engine/test_daemon.py`, `tests/interfaces/test_mcp_server.py`, `test_mcp_client.py`, `test_product_contract.py`: yeşil. Masaüstü: `npm test` (92), `tsc --noEmit`, `cargo test --lib engine_connector` (11) yeşil.
- **Görülmedi:** tam Python süiti (işlerin sonunda çalıştırılacak), paketli sürüm, gerçek bir AI istemcisinden `orchestrator_session_*`.

## Kaynaklar

- `engine/catalog.py`, `tests/engine/test_generated_artifacts.py` (erişim: 2026-11-10).
- Rakip mekanizmaları: `docs/RAKIP_ESKIKLERI.md` §0 ve §1c (erişim: 2026-11-10).
