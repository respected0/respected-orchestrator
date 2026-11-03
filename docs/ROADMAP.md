# Orchestrator: gelecekte yapılacaklar

> Yürütme sırası, kapılar ve görev durumu: `ROADMAP_EXECUTION_PLAN.md`.
> Tamamlanan işlerin kanıtı: `ilerleme/KANIT_LOG.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

## Her AI ile çalışma

- [x] **OpenCode** çalışanı ve MCP kaydı: gerçek ACP oturumu, güvenli fenced final JSON sözleşmesi, izole
  `APPDATA`/`LOCALAPPDATA`, credential bridge ve `opencode` MCP istemcisi. Tamamlandı — kanıt: `KANIT_LOG.md` §ADP-01.
- [ ] **OpenRouter / API tabanlı modeller**: bugün çalışanlar yalnızca komut satırı araçları (codex, claude, gemini, agy,
  cursor, custom). Çin modelleri (GLM, DeepSeek, Qwen, Kimi) yalnızca bir aracın profili üzerinden çalışıyor; kendi
  desteği yok. Anahtarın saklanması ve sağlayıcı/fiyat seçimi karar bekliyor.

## Master–worker rolleri

- [x] `coordinator` rolü `coordinate` komutuyla plan/rol ataması üretir; shell/apply/worker yetkisi yoktur, geçersiz planda 0 worker (`ARCHITECTURE.md` §4). `tester` imzalı doğrulama aşamasıyla yürütülebilir.
- [ ] Otomatik atama görev zorluğunu ve fiyatı modellemiyor.
- [x] Bağımsız review/apply değişmezleri (QUA-04): 12/12 saldırgan ret, otomatik apply 0, meşru check→apply 1/1;
  kanıt `ilerleme/KANIT_LOG.md` §QUA-04.

## Planlama ve paralellik

- [x] Plan taslağı DAG/ownership doğrulaması (SCH-01): 5/5 input sınıfı doğru tanılandı, döngü kabulü 0, bilinen
  paralel ownership çakışmaları %100 işaretlendi ve `plan` 0 worker başlattı; kanıt `ilerleme/KANIT_LOG.md` §SCH-01.
- [x] Bağımlılık ve risk tabanlı scheduler (SCH-02): 10/10 odaklı scheduler testi geçti; `max_parallel=2` zirvesi 2,
  bağımlı hat öncülü `MASTER_APPROVED` olmadan başlamadı, çakışan ownership eşzamanlılığı 1'e indirildi ve iptalde son
  master 0 kez başladı; kanıt `ilerleme/KANIT_LOG.md` §SCH-02.
- [x] İki worktree sonucunu güvenli entegre et (SCH-03): 5/5 deterministik senaryo geçti, hatalarda gerçek repo SHA
  değişimi ve kısmi apply 0 kaldı, bağımsız iki patch 1/1 combined verification sonrasında karar için hazırlandı;
  kanıt `ilerleme/KANIT_LOG.md` §SCH-03.

## Kalıcı görev devri

- [x] Checkpoint ve handoff veri modeli (RES-01): run/kampanya/proje için imzalı, atomik v2 snapshot; eksik/bozuk/eski
  HEAD veya sır içeren kayıt `NEEDS_REVIEW` olur, v1 bir kez göç eder ve yazma öncesi reddedilen veri dosya bırakmaz;
  kanıt `ilerleme/KANIT_LOG.md` §RES-01.
- [x] Gerçek kill/restart sonrası kontrollü resume, kilit temizleme ve tekrar çalıştırılabilir adım whitelist'i (RES-02):
  13/13 senaryo geçti; 5/5 kill/restart noktası, onaysız apply 0, yinelenen ücret 0, canlı kilit reddi ve terminal-only
  onay doğrulandı; kanıt `ilerleme/KANIT_LOG.md` §RES-02.
- [x] Brain ile isteğe bağlı karar hafızası sözleşmesi (RES-03): bağlantısız campaign/apply/verify resume 3/3 ve Brain
  çağrısı 0; opt-out ve yazma izni yokken 0 çağrı; grant matrisi 5/5; prompt-injection notu yalnızca güvenilmeyen veri
  bloğunda; operasyonel checkpoint local ve ADR-006 kod importu yasağı korunuyor; kanıt `ilerleme/KANIT_LOG.md` §RES-03.

## Token tasarrufu

- [ ] Gemini ve Cursor token kullanımı doğrulanamadı: Claude ve agy kullanımı gerçek çalıştırmayla doğrulandı
  (Claude modeli de bildiriyor, agy modeli bildirmiyor, o yüzden agy incelemelerinde `model: null` doğru).
  Gemini çalışanı Windows'ta npm'in `.cmd` kabuğu olarak kurulduğunda kullanılamıyor (cmd.exe komut enjeksiyonu
  kuralı); Cursor geliştirme makinesinde kurulu değil. İkisi için ölçüm yolu gerçek araçla denenmeli.

## Araştırmaya dayalı tasarım

- [ ] Rakip analizi ve araştırma belgesi: CrewAI, AutoGen, LangGraph, OpenHands gibi orkestrasyon ürünleriyle karşılaştırma
  ve kararların dayandığı makaleler/ölçümler yazılı değil.

## Yayın

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.

## Güncelleme

- [ ] Biçimi değiştiren ilk sürümde `interfaces/migrate.py` içindeki `STEPS` tablosuna eski sürüm için taşıma adımı
  eklenmeli (mekanizma ve test hazır; bugün gönderilmiş tüm biçimler güncel olduğu için adım yok).
  Her yayında o sürümün gerçek veri dosyaları `tests/fixtures/releases/<sürüm>/` altına da kopyalanır (sözleşme §4).
