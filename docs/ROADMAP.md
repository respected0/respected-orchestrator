# Orchestrator: gelecekte yapılacaklar

> Yürütme sırası, kapılar ve görev durumu: `ROADMAP_EXECUTION_PLAN.md`.
> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Her AI ile çalışma

- [x] **OpenCode** çalışanı ve MCP kaydı: gerçek ACP oturumu, güvenli fenced final JSON sözleşmesi, izole
  `APPDATA`/`LOCALAPPDATA`, credential bridge ve `opencode` MCP istemcisi. Tamamlandı — kanıt: `KANIT_LOG.md` §ADP-01.
- [ ] **OpenRouter / API tabanlı modeller**: adaptör, DPAPI anahtar kasası ve ağ kapısı hazır (ADP-02/03, kanıt: `KANIT_LOG.md`), ancak
  henüz CLI'ye ve çalışan seçimine bağlı değil; bugün çalışanlar yalnızca komut satırı araçlarıdır (codex, claude, agy, cursor,
  opencode, custom). Çin modelleri (GLM, DeepSeek, Qwen, Kimi) yalnızca bir aracın profili üzerinden çalışıyor.

## Master–worker rolleri

- [x] `coordinator` rolü `coordinate` komutuyla plan/rol ataması üretir; shell/apply/worker yetkisi yoktur, geçersiz planda 0 worker (`ARCHITECTURE.md` §4). `tester` imzalı doğrulama aşamasıyla yürütülebilir.
- [x] Otomatik atama görev zorluğunu ve fiyatı modelliyor (COST-02 sürüm kontrollü fiyat kataloğu, COST-03 risk ve başarım tabanlı
  atama; bilinmeyen değer `unknown` kalır). Kanıt: `KANIT_LOG.md` §COST-02, §COST-03.
- [x] Bağımsız review/apply değişmezleri (QUA-04): 12/12 saldırgan ret, otomatik apply 0, meşru check→apply 1/1;
  kanıt `evidence/KANIT_LOG.md` §QUA-04.

## Planlama ve paralellik

- [x] Plan taslağı DAG/ownership doğrulaması (SCH-01): 5/5 input sınıfı doğru tanılandı, döngü kabulü 0, bilinen
  paralel ownership çakışmaları %100 işaretlendi ve `plan` 0 worker başlattı; kanıt `evidence/KANIT_LOG.md` §SCH-01.
- [x] Bağımlılık ve risk tabanlı scheduler (SCH-02): 10/10 odaklı scheduler testi geçti; `max_parallel=2` zirvesi 2,
  bağımlı hat öncülü `MASTER_APPROVED` olmadan başlamadı, çakışan ownership eşzamanlılığı 1'e indirildi ve iptalde son
  master 0 kez başladı; kanıt `evidence/KANIT_LOG.md` §SCH-02.
- [x] İki worktree sonucunu güvenli entegre et (SCH-03): 5/5 deterministik senaryo geçti, hatalarda gerçek repo SHA
  değişimi ve kısmi apply 0 kaldı, bağımsız iki patch 1/1 combined verification sonrasında karar için hazırlandı;
  kanıt `evidence/KANIT_LOG.md` §SCH-03.

## Kalıcı görev devri

- [x] Checkpoint ve handoff veri modeli (RES-01): run/kampanya/proje için imzalı, atomik v2 snapshot; eksik/bozuk/eski
  HEAD veya sır içeren kayıt `NEEDS_REVIEW` olur, v1 bir kez göç eder ve yazma öncesi reddedilen veri dosya bırakmaz;
  kanıt `evidence/KANIT_LOG.md` §RES-01.
- [x] Gerçek kill/restart sonrası kontrollü resume, kilit temizleme ve tekrar çalıştırılabilir adım whitelist'i (RES-02):
  13/13 senaryo geçti; 5/5 kill/restart noktası, onaysız apply 0, yinelenen ücret 0, canlı kilit reddi ve terminal-only
  onay doğrulandı; kanıt `evidence/KANIT_LOG.md` §RES-02.
- [x] Brain ile isteğe bağlı karar hafızası sözleşmesi (RES-03): bağlantısız campaign/apply/verify resume 3/3 ve Brain
  çağrısı 0; opt-out ve yazma izni yokken 0 çağrı; grant matrisi 5/5; prompt-injection notu yalnızca güvenilmeyen veri
  bloğunda; operasyonel checkpoint local ve ADR-006 kod importu yasağı korunuyor; kanıt `evidence/KANIT_LOG.md` §RES-03.

## Token tasarrufu

- [x] Cursor token kullanımı gerçek CLI ile doğrulandı (Free plan; `inputTokens` önbellek okumasını içermez,
  kanıt `evidence/poc/cursor_cache_probe.log`). Claude ve agy kullanımı da gerçek çalıştırmayla doğrulandı
  (Claude modeli de bildiriyor, agy modeli bildirmiyor, o yüzden agy incelemelerinde `model: null` doğru).
- [ ] Gemini kapsam dışı (kullanıcı kararı, 2026-11-04): kod yolu duruyor ama canlı doğrulanmadı ve desteklenmiyor;
  Windows'ta npm'in `.cmd` kabuğu olarak kurulursa cmd.exe komut enjeksiyonu kuralı gereği kullanılamaz.

## Araştırmaya dayalı tasarım

- [x] Rakip analizi ve araştırma belgesi: `COMPETITOR_RESEARCH.md` (kaynaklı karşılaştırma) ve `adr/` karar defteri. Kanıt: `KANIT_LOG.md` §DOC-01.

## Yayın

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.

## Güncelleme

- [ ] Biçimi değiştiren ilk sürümde `interfaces/migrate.py` içindeki `STEPS` tablosuna eski sürüm için taşıma adımı
  eklenmeli (mekanizma ve test hazır; bugün gönderilmiş tüm biçimler güncel olduğu için adım yok).
  Her yayında o sürümün gerçek veri dosyaları `tests/fixtures/releases/<sürüm>/` altına da kopyalanır (sözleşme §4).
