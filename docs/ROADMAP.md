# Respected Orchestrator — Ürün yol haritası (Beta.3 → v1.0)

> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`.
> Bu belge tek başına yeterli ana yol haritasıdır: Beta.3'ten v1.0'a kadar planlanan bütün geliştirmeleri, mimari kararları, test senaryolarını, rakip/araştırma gerekçelerini ve sürüm kabul kriterlerini içerir. Başka bir belgeye (geçici araştırma/plan dosyalarına) bağlı değildir; dış kaynaklar tam URL olarak §18'dedir.

**Belge durumu (5 Kasım 2026):** Plan / öneri. Bu belgedeki hiçbir yeni görev uygulanmış sayılmaz; hiçbiri `[x]` değildir. Kod yolları ve üçüncü taraf beyanları her göreve başlanırken güncel depoda ve kaynakta yeniden doğrulanır. Rakip özellikleri **üretici beyanıdır**; yerelde çalıştırılıp denenmemiştir (aksi belirtilmedikçe).

**Etiket sözleşmesi:** Kaynak planlardan gelen içerik görev kartlarında olduğu gibi korunmuştur. Bu belgeyi birleştirirken eklenen, kaynaklarda **bulunmayan** öneri ve yorumlar `[ÖNERİ]`, çözülmesi gereken teknik kararlar `[AÇIK KARAR]`, kaynaklar arası çelişkiler `[ÇELİŞKİ]` etiketiyle işaretlidir. Etiketsiz içerik kaynak plan veya mevcut depo belgesi içeriğidir.

## İçindekiler

- [1. Belgenin amacı ve nasıl okunur](#1-belgenin-amacı-ve-nasıl-okunur)
- [2. Sürüm özeti](#2-sürüm-özeti)
- [3. Mevcut durum: tamamlanmış temel ve açık maddeler](#3-mevcut-durum-tamamlanmış-temel-ve-açık-maddeler)
  - [3.1 Bu belgeden önce ROADMAP'te bulunan madde (özgün içerik, değiştirilmemiştir)](#31-bu-belgeden-önce-roadmapte-bulunan-madde-özgün-içerik-değiştirilmemiştir)
  - [3.2 Tamamlanmış Beta.1/Beta.2 çalışmaları — yeniden planlanmaz](#32-tamamlanmış-beta1beta2-çalışmaları--yeniden-planlanmaz)
  - [3.3 Planlamayı doğrudan etkileyen açık gerçekler (depo belgelerinden)](#33-planlamayı-doğrudan-etkileyen-açık-gerçekler-depo-belgelerinden)
- [4. Değişmez ilkeler, güvenlik sabitleri ve tamamlanma tanımı](#4-değişmez-ilkeler-güvenlik-sabitleri-ve-tamamlanma-tanımı)
  - [4.1 Değişmez ilkeler ve güvenlik sabitleri](#41-değişmez-ilkeler-ve-güvenlik-sabitleri)
  - [4.2 Görev kartı standardı ve tamamlanma tanımı (Definition of Done)](#42-görev-kartı-standardı-ve-tamamlanma-tanımı-definition-of-done)
  - [4.3 Başlama koşulları (önkoşul kapıları)](#43-başlama-koşulları-önkoşul-kapıları)
- [5. Araştırma temeli: rakip analizi ve mimari kararlar](#5-araştırma-temeli-rakip-analizi-ve-mimari-kararlar)
  - [5.1 Yönetici özeti](#51-yönetici-özeti)
  - [5.2 Respected'ın belgelenmiş mevcut temeli (analiz raporuna göre)](#52-respectedın-belgelenmiş-mevcut-temeli-analiz-raporuna-göre)
  - [5.3 Rakip matrisi — 16 çoklu ajan / orkestrasyon](#53-rakip-matrisi--16-çoklu-ajan--orkestrasyon)
  - [5.4 OrchestratorInc ve AgentSpace'den ayrıntılı öğrenimler](#54-orchestratorinc-ve-agentspaceden-ayrıntılı-öğrenimler)
  - [5.5 Rakip yetenek envanteri ve kapsama ölçüsü (strateji)](#55-rakip-yetenek-envanteri-ve-kapsama-ölçüsü-strateji)
  - [5.6 Mimari sınırlar](#56-mimari-sınırlar)
  - [5.7 Yapılmayacaklar](#57-yapılmayacaklar)
  - [5.8 Ölçüm ve risk kararları (strateji)](#58-ölçüm-ve-risk-kararları-strateji)
  - [5.9 Analiz raporundaki sürüm kapısı önerileri (özgün hâli)](#59-analiz-raporundaki-sürüm-kapısı-önerileri-özgün-hâli)
- [6. Rakip yetenek kapsam matrisi (Beta.5 / Beta.6) `[ÖNERİ]`](#6-rakip-yetenek-kapsam-matrisi-beta5--beta6-öneri)
  - [6.1 Yetenek satırları](#61-yetenek-satırları)
  - [6.2 Kasıtlı istisnalar (`excluded` karar adayları)](#62-kasıtlı-istisnalar-excluded-karar-adayları)
  - [6.3 Tamamlayıcı araçlar ve kullanım ilkesi](#63-tamamlayıcı-araçlar-ve-kullanım-ilkesi)
- [7. Beta.3 — Standalone Agent Workbench](#7-beta3--standalone-agent-workbench)
  - [7.0 Sürüm hedefi ve kapsamı](#70-sürüm-hedefi-ve-kapsamı)
  - [7.1 Ayrıntılı görevler — Beta.3](#71-ayrıntılı-görevler--beta3)
  - [B3-00 — Ürün sınırları, GUI yetki modeli ve sözleşme [P0]](#b3-00--ürün-sınırları-gui-yetki-modeli-ve-sözleşme-p0)
  - [B3-01 — Bağımsız Tauri masaüstü uygulaması ve tipli IPC [P0]](#b3-01--bağımsız-tauri-masaüstü-uygulaması-ve-tipli-ipc-p0)
  - [B3-02 — Kalıcı supervisor, event store ve reconnect [P0]](#b3-02--kalıcı-supervisor-event-store-ve-reconnect-p0)
  - [B3-03 — Gerçek Chat/Terminal agent oturumları [P0]](#b3-03--gerçek-chatterminal-agent-oturumları-p0)
  - [B3-04 — Project Board ve görsel DAG planlama [P0]](#b3-04--project-board-ve-görsel-dag-planlama-p0)
  - [B3-05 — Review, diff ve insan onayı merkezi [P0]](#b3-05--review-diff-ve-insan-onayı-merkezi-p0)
  - [B3-06 — Canlı aktivite, dosya, terminal ve önizleme inspector [P1]](#b3-06--canlı-aktivite-dosya-terminal-ve-önizleme-inspector-p1)
  - [B3-07 — Ajan profilleri ve uyumluluk kontrolleri [P1]](#b3-07--ajan-profilleri-ve-uyumluluk-kontrolleri-p1)
  - [B3-08 — Yerel, salt-okunur MCP/Skill envanteri [P1]](#b3-08--yerel-salt-okunur-mcpskill-envanteri-p1)
  - [B3-09 — Kurulum, güncelleme, veri geçişi ve beta release [P0]](#b3-09--kurulum-güncelleme-veri-geçişi-ve-beta-release-p0)
- [8. Beta.4 — Intelligent Agent Workspace](#8-beta4--intelligent-agent-workspace)
  - [8.0 Sürüm hedefi ve kapsamı](#80-sürüm-hedefi-ve-kapsamı)
  - [8.1 Ayrıntılı görevler — Beta.4](#81-ayrıntılı-görevler--beta4)
  - [B4-01 — Smart Agent Routing 2.0 [P0]](#b4-01--smart-agent-routing-20-p0)
  - [B4-02 — Kalıcı ajan profilleri, ekipler ve kontrollü handoff [P0]](#b4-02--kalıcı-ajan-profilleri-ekipler-ve-kontrollü-handoff-p0)
  - [B4-03 — Hub’sız yerel MCP/Skill uyumluluk ve öneri motoru [P0]](#b4-03--hubsız-yerel-mcpskill-uyumluluk-ve-öneri-motoru-p0)
  - [B4-04 — Gerçek token, kota, maliyet ve kalite analitiği [P0]](#b4-04--gerçek-token-kota-maliyet-ve-kalite-analitiği-p0)
  - [B4-05 — Context Budget Manager ve seçici bağlam [P1]](#b4-05--context-budget-manager-ve-seçici-bağlam-p1)
  - [B4-06 — Yerel uygulama içi sesli görev taslağı [P1]](#b4-06--yerel-uygulama-içi-sesli-görev-taslağı-p1)
  - [B4-07 — Screenshot-to-task ve görsel bağlam [P1]](#b4-07--screenshot-to-task-ve-görsel-bağlam-p1)
  - [B4-08 — Adaptif recovery ve circuit breaker [P1]](#b4-08--adaptif-recovery-ve-circuit-breaker-p1)
  - [B4-09 — Remote/mobile kontrol — koşullu araştırma (stretch) [P2]](#b4-09--remotemobile-kontrol--koşullu-araştırma-stretch-p2)
- [9. Beta.5 — Competitive Parity I: Local Developer Experience](#9-beta5--competitive-parity-i-local-developer-experience)
  - [9.0 Sürüm hedefi ve kapsamı](#90-sürüm-hedefi-ve-kapsamı)
  - [9.1 Ayrıntılı görevler — Beta.5](#91-ayrıntılı-görevler--beta5)
  - [B5-00 — Rekabet yetenek matrisi ve scope freeze [P0]](#b5-00--rekabet-yetenek-matrisi-ve-scope-freeze-p0)
  - [B5-01 — Agent Chat/Terminal parity [P0]](#b5-01--agent-chatterminal-parity-p0)
  - [B5-02 — Workspace, Git ve arama deneyimi [P0]](#b5-02--workspace-git-ve-arama-deneyimi-p0)
  - [B5-03 — Gelişmiş Git/PR/CI/review döngüsü [P0]](#b5-03--gelişmiş-gitprcireview-döngüsü-p0)
  - [B5-04 — Browser preview ve tasarım geri bildirimi [P0]](#b5-04--browser-preview-ve-tasarım-geri-bildirimi-p0)
  - [B5-05 — Kaydedilmiş iş akışları ve otomasyon [P1]](#b5-05--kaydedilmiş-iş-akışları-ve-otomasyon-p1)
  - [B5-06 — Operatör inbox ve birleşik zaman çizgisi [P0]](#b5-06--operatör-inbox-ve-birleşik-zaman-çizgisi-p0)
  - [B5-07 — Ekip kimliği ve görev devri UX [P1]](#b5-07--ekip-kimliği-ve-görev-devri-ux-p1)
  - [B5-08 — Hesap, kota ve provider sağlık durumu [P1]](#b5-08--hesap-kota-ve-provider-sağlık-durumu-p1)
  - [B5-09 — Desktop polish, erişilebilirlik ve yerelleştirme [P1]](#b5-09--desktop-polish-erişilebilirlik-ve-yerelleştirme-p1)
  - [B5-10 — Yerel profil aktarımı ve audit [P1]](#b5-10--yerel-profil-aktarımı-ve-audit-p1)
  - [B5-11 — Beta.5 canlı kabul ve release gate [P0]](#b5-11--beta5-canlı-kabul-ve-release-gate-p0)
- [10. Beta.6 — Competitive Parity II: Advanced & Connected Workflows](#10-beta6--competitive-parity-ii-advanced--connected-workflows)
  - [10.0 Sürüm hedefi ve kapsamı](#100-sürüm-hedefi-ve-kapsamı)
  - [10.1 Ayrıntılı görevler — Beta.6](#101-ayrıntılı-görevler--beta6)
  - [B6-00 — Gelişmiş rakip farklarının yeniden denetimi [P0]](#b6-00--gelişmiş-rakip-farklarının-yeniden-denetimi-p0)
  - [B6-01 — Güvenli SSH / remote worker [P0]](#b6-01--güvenli-ssh--remote-worker-p0)
  - [B6-02 — Mobil companion temel deneyimi [P1]](#b6-02--mobil-companion-temel-deneyimi-p1)
  - [B6-03 — Çoklu host ve durum senkronizasyonu [P1]](#b6-03--çoklu-host-ve-durum-senkronizasyonu-p1)
  - [B6-04 — Opsiyonel cloud worker PoC ve karar [P2]](#b6-04--opsiyonel-cloud-worker-poc-ve-karar-p2)
  - [B6-05 — Ek issue/source-control adaptörleri [P1]](#b6-05--ek-issuesource-control-adaptörleri-p1)
  - [B6-06 — Gelişmiş design mode ve satır içi review [P1]](#b6-06--gelişmiş-design-mode-ve-satır-içi-review-p1)
  - [B6-07 — Operasyon API ve olay abonelikleri [P1]](#b6-07--operasyon-api-ve-olay-abonelikleri-p1)
  - [B6-08 — Workspace rol erişimi ve paylaşım kararı [P2]](#b6-08--workspace-rol-erişimi-ve-paylaşım-kararı-p2)
  - [B6-09 — Opsiyonel görsel takım/ofis görünümü [P2]](#b6-09--opsiyonel-görsel-takımofis-görünümü-p2)
  - [B6-10 — macOS/Linux ve platform güvenlik eşdeğerliği [P1]](#b6-10--macoslinux-ve-platform-güvenlik-eşdeğerliği-p1)
  - [B6-11 — Beta.6 saha pilotu ve release kapısı [P0]](#b6-11--beta6-saha-pilotu-ve-release-kapısı-p0)
- [11. Beta.7 — Respected-Exclusive Value (Respected Innovations)](#11-beta7--respected-exclusive-value-respected-innovations)
  - [11.0 Sürüm hedefi ve kapsamı](#110-sürüm-hedefi-ve-kapsamı)
  - [11.1 Ayrıntılı görevler — Beta.7](#111-ayrıntılı-görevler--beta7)
  - [B7-01 — Project Doctor [P0]](#b7-01--project-doctor-p0)
  - [B7-02 — Build & Prove [P0]](#b7-02--build--prove-p0)
  - [B7-03 — Verified Autopilot [P0]](#b7-03--verified-autopilot-p0)
  - [B7-04 — Proof Pack 2.0 [P0]](#b7-04--proof-pack-20-p0)
  - [B7-05 — Agent Tournament [P1]](#b7-05--agent-tournament-p1)
  - [B7-06 — Impact & Risk Intelligence [P1]](#b7-06--impact--risk-intelligence-p1)
  - [B7-07 — Recovery Time Machine [P1]](#b7-07--recovery-time-machine-p1)
  - [11.2 Beta.7 teknik çerçeve `[ÖNERİ]`](#112-beta7-teknik-çerçeve-öneri)
- [12. Beta.8 — Research, Competitor Benchmarks & Engineering Optimization](#12-beta8--research-competitor-benchmarks--engineering-optimization)
  - [12.0 Sürüm hedefi ve kapsamı](#120-sürüm-hedefi-ve-kapsamı)
  - [12.1 Ayrıntılı görevler — Beta.8](#121-ayrıntılı-görevler--beta8)
  - [B8-01 — Rakip sürüm ve özellik yeniden doğrulaması [P0]](#b8-01--rakip-sürüm-ve-özellik-yeniden-doğrulaması-p0)
  - [B8-02 — Araştırma literatür haritası [P0]](#b8-02--araştırma-literatür-haritası-p0)
  - [B8-03 — Adil ajan ve rakip benchmark koşuları [P0]](#b8-03--adil-ajan-ve-rakip-benchmark-koşuları-p0)
  - [B8-04 — Gizli ve bağımsız doğrulanmış görev seti [P0]](#b8-04--gizli-ve-bağımsız-doğrulanmış-görev-seti-p0)
  - [B8-05 — Gerçek kullanıcı ve kullanım araştırmaları [P0]](#b8-05--gerçek-kullanıcı-ve-kullanım-araştırmaları-p0)
  - [B8-06 — Bağımsız güvenlik saldırı denetimi [P0]](#b8-06--bağımsız-güvenlik-saldırı-denetimi-p0)
  - [B8-07 — Performans, maliyet, bellek ve a11y optimizasyonu [P1]](#b8-07--performans-maliyet-bellek-ve-a11y-optimizasyonu-p1)
  - [B8-08 — Araştırma sonucunu kalıcı kalite kapısına dönüştürme [P0]](#b8-08--araştırma-sonucunu-kalıcı-kalite-kapısına-dönüştürme-p0)
  - [12.2 Beta.8 araştırma ve deney protokolü `[ÖNERİ]`](#122-beta8-araştırma-ve-deney-protokolü-öneri)
- [13. Beta.9 — Stabilization & Bug Fix (Fix-Only)](#13-beta9--stabilization--bug-fix-fix-only)
  - [13.0 Sürüm hedefi ve kapsamı](#130-sürüm-hedefi-ve-kapsamı)
  - [13.1 Ayrıntılı görevler — Beta.9](#131-ayrıntılı-görevler--beta9)
  - [B9-01 — Feature freeze ve change control [P0]](#b9-01--feature-freeze-ve-change-control-p0)
  - [B9-02 — P0/P1 bug ve güvenlik kapatma [P0]](#b9-02--p0p1-bug-ve-güvenlik-kapatma-p0)
  - [B9-03 — Desteklenen platform/ajan regresyonu [P0]](#b9-03--desteklenen-platformajan-regresyonu-p0)
  - [B9-04 — Kurulum, update, migration ve rollback [P0]](#b9-04--kurulum-update-migration-ve-rollback-p0)
  - [B9-05 — UX bugları, a11y ve dokümantasyon [P1]](#b9-05--ux-bugları-a11y-ve-dokümantasyon-p1)
  - [B9-06 — SBOM, lisans, gizlilik ve imzalı dağıtım [P0]](#b9-06--sbom-lisans-gizlilik-ve-imzalı-dağıtım-p0)
  - [B9-07 — RC, pilot, hotfix ve destek disiplini [P0]](#b9-07--rc-pilot-hotfix-ve-destek-disiplini-p0)
  - [13.2 Beta.9 süreç tanımları `[ÖNERİ]`](#132-beta9-süreç-tanımları-öneri)
- [14. v1.0 — First Stable Release](#14-v10--first-stable-release)
  - [14.0 Sürüm hedefi](#140-sürüm-hedefi)
  - [14.1 Çıkış kapısı sözleşmesi (strateji planından, kaynak metin)](#141-çıkış-kapısı-sözleşmesi-strateji-planından-kaynak-metin)
  - [14.2 Ayrıntılı görevler — v1.0](#142-ayrıntılı-görevler--v10)
  - [V1-01 — Final readiness ve yetenek kapsam kararı [P0]](#v1-01--final-readiness-ve-yetenek-kapsam-kararı-p0)
  - [V1-02 — Kararlı sürüm artefaktı ve yükseltme yolu [P0]](#v1-02--kararlı-sürüm-artefaktı-ve-yükseltme-yolu-p0)
  - [V1-03 — İlk sürüm izleme ve destek başlangıcı [P1]](#v1-03--ilk-sürüm-izleme-ve-destek-başlangıcı-p1)
- [15. Sürüm kapıları (release gates)](#15-sürüm-kapıları-release-gates)
  - [15.1 Beta.3 yayın kapısı (zorunlu)](#151-beta3-yayın-kapısı-zorunlu)
  - [15.2 Beta.4 yayın kapısı (zorunlu/koşullu)](#152-beta4-yayın-kapısı-zorunlukoşullu)
  - [15.3 Beta.5 yayın kapısı (`B5-GATE`)](#153-beta5-yayın-kapısı-b5-gate)
  - [15.4 Beta.6 yayın kapısı (`B6-GATE`)](#154-beta6-yayın-kapısı-b6-gate)
  - [15.5 Beta.7 yayın kapısı (`B7-GATE`)](#155-beta7-yayın-kapısı-b7-gate)
  - [15.6 Beta.8 yayın kapısı (`B8-GATE`)](#156-beta8-yayın-kapısı-b8-gate)
  - [15.7 Beta.9 yayın kapısı (`B9-GATE`)](#157-beta9-yayın-kapısı-b9-gate)
  - [15.8 v1.0 yayın kapısı (`V1-GATE`)](#158-v10-yayın-kapısı-v1-gate)
  - [15.9 Kapı ilişkileri `[ÖNERİ]`](#159-kapı-ilişkileri-öneri)
- [16. Kritik yol, riskler ve rollback](#16-kritik-yol-riskler-ve-rollback)
  - [16.1 Kritik yol ve bağımlılık kontrolü](#161-kritik-yol-ve-bağımlılık-kontrolü)
  - [16.2 Risk kaydı, erteleme ve teknik kararlar](#162-risk-kaydı-erteleme-ve-teknik-kararlar)
  - [16.3 Rollback ve feature flag matrisi](#163-rollback-ve-feature-flag-matrisi)
- [17. Geliştirme süreci, durum sözlüğü ve belge bakımı](#17-geliştirme-süreci-durum-sözlüğü-ve-belge-bakımı)
  - [17.1 Geliştirme ajanına / ekibe verilecek issue işleyişi (Beta.3/Beta.4 planından)](#171-geliştirme-ajanına--ekibe-verilecek-issue-işleyişi-beta3beta4-planından)
  - [17.2 Durum sözlüğü ve belge bakımı (Beta.5→v1.0 planından, birleştirilmiş)](#172-durum-sözlüğü-ve-belge-bakımı-beta5v10-planından-birleştirilmiş)
  - [17.3 Önerilen çalışma sırası ve ilk 5 issue (strateji planından)](#173-önerilen-çalışma-sırası-ve-ilk-5-issue-strateji-planından)
  - [17.4 Kaynak planların kullanım notları ve ilkeleri (aktarıldı)](#174-kaynak-planların-kullanım-notları-ve-ilkeleri-aktarıldı)
- [18. Kaynaklar (dış referanslar)](#18-kaynaklar-dış-referanslar)
  - [Respected Orchestrator deposu (işe başlanırken `main` yeniden doğrulanmalı)](#respected-orchestrator-deposu-işe-başlanırken-main-yeniden-doğrulanmalı)
  - [Rakip ve komşu araçlar (üretici beyanı; laboratuvar doğrulaması değil)](#rakip-ve-komşu-araçlar-üretici-beyanı-laboratuvar-doğrulaması-değil)
  - [Doğrulama araçları](#doğrulama-araçları)
  - [Araştırma ve literatür](#araştırma-ve-literatür)
- [Ek A. Görev kimliği kaydı](#ek-a-görev-kimliği-kaydı)
  - [A.1 Ana işler (68)](#a1-ana-işler-68)
  - [A.2 Alt görevler (149)](#a2-alt-görevler-149)
- [Ek B. Eksiksizlik ve entegrasyon denetim raporu](#ek-b-eksiksizlik-ve-entegrasyon-denetim-raporu)
- [Ek C. Kaynaklar arası çelişkiler ve çözülmemiş teknik kararlar](#ek-c-kaynaklar-arası-çelişkiler-ve-çözülmemiş-teknik-kararlar)
  - [C.1 Birleştirme sırasında bulunan çelişkiler ve çözümleri `[ÇELİŞKİ]`](#c1-birleştirme-sırasında-bulunan-çelişkiler-ve-çözümleri-çelişki)
  - [C.2 Çözülmemiş teknik kararlar ve araştırma görevleri `[AÇIK KARAR]`](#c2-çözülmemiş-teknik-kararlar-ve-araştırma-görevleri-açik-karar)

---

## 1. Belgenin amacı ve nasıl okunur

**Hiyerarşi:** Sürüm → Ana özellik (`B3-00` gibi) → Alt görev (`B3-00.01` gibi) → Teknik detaylar (mimari, uygulama adımları) → Testler → Kabul kriterleri → Tamamlanma kanıtı.

**Kimlik şeması:** `B3-xx`/`B4-xx` (Beta.3/4 ana işleri), `B5-xx` … `B9-xx` (Beta.5–9), `V1-xx` (v1.0); alt görev `ANA.NN`. Sürüm kapıları `B3-GATE-01` … `B4-GATE-07`, `B5-GATE` … `V1-GATE`. Rakip yetenek kimlikleri `CAP-xxx` (§6, `[ÖNERİ]`). Görev kimlikleri kaynak planlardan **değiştirilmeden** alınmıştır.

**Görev kartı alanlarının yeri.** Aşağıdaki tablo, bir görev için istenen bilgilerin bu belgede nerede bulunduğunu gösterir:

| Bilgi | Nerede |
|---|---|
| Görev kimliği, açıklama, durum kutusu | Alt görev başlığı ve ilk `- [ ]` satırı |
| Öncelik ve boyut (S/M/L) | Alt görevin `Öncelik` satırı; ana işin başlığındaki `[P0/P1/P2]` |
| Geliştirme hedefi / kullanıcı faydası | Ana işin `Amaç` ve `Ana kabul koşulu` satırları; ana iş altındaki "Strateji / analiz kaynağı" bloğu |
| Rakip / araştırma referansı ve gerekçe | Ana işin `Rakip dayanağı` / `Referans` satırı; §5 ve §6 |
| Mevcut kodla ilişki, etkilenen / önerilen modüller | Ana işin `Mevcut / önerilen kod eşlemesi` satırı; alt görevin `Mimari / değişecek alan` (veya `Mimari / modül sınırı`) satırı; §3.2 |
| Teknik uygulama adımları | `Uygulama adımları` / `Uygulama` satırı |
| Ön koşullar ve bağımlılıklar | `Bağımlılıklar` satırı; §16 (kritik yol) ve Ek A |
| Pozitif / negatif testler | `Test senaryoları` satırı (negatif senaryolar ağırlıktadır) |
| Güvenlik ve regresyon kontrolleri | §4.1 değişmez güvenlik kuralları; her kartın `Test senaryoları` satırı; sürüm kapıları (§15) |
| Ölçülebilir kabul | `Ölçülebilir kabul` satırı |
| Tamamlanma kanıtı | `Tamamlanma kanıtı` satırı; DoD §4.2 |
| Rollback / feature flag / riskler | Kartta açıkça yazılıysa kartta; ayrıca §16.3 rollback ve feature flag matrisi; §16.2 risk kaydı |

**Önemli sınır:** Önerilen yeni klasör ve dosya adları (`desktop/`, `engine/sessions/`, `engine/local_api.py`, `docs/COMPETITOR_CAPABILITY_MATRIX.md` vb.) **öneridir**. Görev başlamadan önce `git ls-files`, mevcut sınıf/fonksiyonlar ve test dizini ile yeniden eşlenir; mevcut modülü yeniden yazmak için gerekçe değildir.

---

## 2. Sürüm özeti

**Ürün konumu:** "Çalışan ajan filosu" değil, **kontrol altında, kanıtla teslim eden coding agent ekibi.** Beta.3 = *ajanlarını güvenle yönet*. Beta.4 = *ajanlarını daha az uğraşarak, ölçülebilir biçimde yönet*. Güvenlik, kanıt, açık onay ve bağımsızlık her sürümde pazarlık konusu değildir.

| Sürüm | Adı | Tema | Ana işler / alt görev | Yayın kapısı |
|---|---|---|---:|---|
| **Beta.3** | Standalone Agent Workbench | Bağımsız masaüstü, IPC, supervisor, izinli Chat/Terminal, board/DAG, kanıt/onay, paketleme | 10 / 38 | `B3-GATE-01…07` |
| **Beta.4** | Intelligent Agent Workspace | Riskli routing, kalıcı takım/handoff, yerel skill/MCP zekâsı, ölçülebilir kalite; remote/mobile yalnız stretch | 9 / 31 | `B4-GATE-01…07` |
| **Beta.5** | Competitive Parity I | Yerel geliştirici deneyiminde rakip kapsama | 12 / 24 | `B5-GATE` |
| **Beta.6** | Competitive Parity II | Mobil, SSH/çoklu host, ileri entegrasyon, koşullu cloud/paylaşım/OS | 12 / 24 | `B6-GATE` |
| **Beta.7** | Respected Innovations | Project Doctor, Build & Prove, Verified Autopilot, Proof Pack 2.0, Tournament, Impact & Risk, Recovery Time Machine | 7 / 14 | `B7-GATE` |
| **Beta.8** | Research & Optimization | Literatür, adil benchmark, holdout, kullanıcı çalışmaları, red team, optimizasyon | 8 / 8 | `B8-GATE` |
| **Beta.9** | Stabilization & Bug Fix | Feature freeze, P0/P1 sıfırlama, regresyon, güncelleme, SBOM/imza, RC | 7 / 7 | `B9-GATE` |
| **v1.0** | First Stable Release | Final readiness, imzalı kararlı sürüm, ilk sürüm destek | 3 / 3 | `V1-GATE` |
| **Toplam** | | | **68 / 149** | |

Beta.3+Beta.4 = 19 ana iş / 69 alt görev; Beta.5→v1.0 = 49 ana paket / 80 alt görev. (Beta.3'ün 10 ana işi `B3-00…B3-09`, Beta.4'ün 9 ana işi `B4-01…B4-09`'dur.)

**Fazlar (Beta.3/Beta.4):**
1. **G0 — Önkoşullar:** Beta.2 release gate kanıtı; güvenlik ve ürün sözleşmesi envanteri (`B3-00`).
2. **G1 — Platform:** Desktop shell, yetki sınırı/IPC (`B3-01`), supervisor/event journal (`B3-02`).
3. **G2 — Ana ürün deneyimi:** Agent session (`B3-03`), board/DAG (`B3-04`), review/approval (`B3-05`).
4. **G3 — Tamamlama:** Live inspector (`B3-06`), agent profiles (`B3-07`), read-only local discovery (`B3-08`), migration/release (`B3-09`).
5. **G4 — Zekâ çekirdeği:** Routing (`B4-01`), teams (`B4-02`), MCP/skill intelligence (`B4-03`), instrumentation (`B4-04`).
6. **G5 — Optimizasyon ve doğal giriş:** Context (`B4-05`), voice (`B4-06`), screenshot (`B4-07`), recovery (`B4-08`); remote/mobile (`B4-09`) yalnız araştırma/opt-in.

Fazlar tek bir katı DAG değildir; her görevdeki `Bağımlılıklar` alanı gerçek sırayı belirler. UI/engine işleri uygun olduğunda paralel geliştirilir.

**Fazlar arası genel bağımlılık (Beta.5→v1.0):** `Beta.2/Beta.3/Beta.4 doğrulanmış release gate → B5-00 → Beta.5 local parity → B6-00 → Beta.6 advanced parity → Beta.7 yenilik pilotları → Beta.8 araştırma → Beta.9 freeze/RC → v1.0`. Fazlar içindeki bağımsız işler, kart bağımlılıklarına uyarak paralel ilerleyebilir.

---

## 3. Mevcut durum: tamamlanmış temel ve açık maddeler

### 3.1 Bu belgeden önce ROADMAP'te bulunan madde (özgün içerik, değiştirilmemiştir)

Özgün ROADMAP'in ilkesi: *"Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir."* Aşağıdaki iki açık madde olduğu gibi korunur; ilgili yeni görevlere bağlantıları sağdadır.

```text
# Orchestrator: gelecekte yapılacaklar

> Tamamlanan işlerin kanıtı: `evidence/KANIT_LOG.md`.

Ürün beklentisiyle bugünkü durum arasındaki açıklar. Yapılan madde silinir.

---

## İlk sabit sürümü öncesi kontrol edilecek (v.1.0 öncesi)

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme
  makinesi Windows.
```

| Özgün açık madde | Durum | Yeni planda karşılandığı görevler |
|---|---|---|
| Kurucuyu Authenticode ile imzalamak | Açık (`[ ]`); üretim sertifikası yok. `REL-01` hattı self-signed test sertifikasıyla kanıtlıdır, üretim imzalı yayın yoktur | `B3-09.04`, `B3-GATE-06`, `B9-06.01`, `V1-02.01` |
| macOS / Linux doğrulanmadı; POSIX'te anahtar için OS kum havuzu yok | Açık (`[ ]`); `ADR-008`: yalnız Windows GA, Linux 7 fixture `blocked` (no-go), macOS koşulmadı (no-go) | `B6-10.01`, `B6-10.02`, `B9-03.01` |

- [ ] Kurucuyu Authenticode ile imzalamak (SmartScreen uyarısı). Kod imzalama sertifikası gerekir; yok.
- [ ] macOS / Linux: kod yolları var, doğrulanmadı; POSIX'te anahtar için işletim sistemi kum havuzu yok. Bu geliştirme makinesi Windows.

### 3.2 Tamamlanmış Beta.1/Beta.2 çalışmaları — yeniden planlanmaz

`evidence/KANIT_LOG.md`, `ARCHITECTURE.md`, `THREAT_MODEL.md` ve `adr/` (depo `c0e9531` anlık görüntüsü, 5 Kasım 2026) şu işleri tamamlanmış gösterir. Bunlar yeni görev değildir; yeni görevler bunların **üzerine** kurulur ve yeniden yazmaz:

| Kanıt kaydı | Tamamlanan yetenek (belgelenmiş) | Yeni görevlerle ilişki |
|---|---|---|
| `SEC-01…SEC-04`, `ADR-007/015/017/018` | Tehdit modeli ve yetki matrisi; AppContainer worker, fail-closed başlatıcı, CI negatif izolasyon, verify ağ izolasyonu (S-24 "Engellenir") | `B3-00.02/03` desktop tehdit modeli bunu genişletir; `B3-03.02` ConPTY+AppContainer; her GUI/IPC görevi bu testleri bypass edemez |
| `QUA-01…QUA-04`, `ADR-005` | Tester, MAF verify/review/fix döngüsü, bağımsız review, apply değişmezleri | `B3-05` review/apply merkezi bu API'yi tüketir |
| `SCH-01…SCH-04`, `ADR-009/010`, `engine` DAG | Plan DAG/ownership doğrulaması, scheduler, güvenli entegrasyon, coordinator | `B3-04` board/DAG yalnız görselleştirir ve revalidate ister |
| `RES-01…RES-03`, `ADR-012` | İmzalı checkpoint/handoff, çökme sonrası kontrollü resume; Brain ile isteğe bağlı karar hafızası sözleşmesi (`RES-03`) | `B3-02.04` mevcut resume'a bağlanır |
| `ADP-01…ADP-03`, `COST-01…COST-03`, `ADR-011` | OpenCode/OpenRouter adaptörleri, fiyat kataloğu, risk/başarım tabanlı `auto_assign v2` | `B4-01`, `B4-04` bunun üstüne kurulur |
| `EXT-01`, `EXT-02`, `ADR-013` | Skill/MCP manifest + izin denetimi (trust+digest yürütme kapısı), salt-okunur MCP deneme adaptörleri | `B3-08`, `B4-03` yalnız yerel keşif/uyumluluk/öneri ekler; `EXT-01` güvenlik kararı ayrı katman kalır |
| `UX-01…UX-03`, `ADR-004` | İmzalı kanıt görünümü, salt-okunur evidence API, TTY'de `maf-approve` insan onayı | `B3-05` read model + ayrı native human-presence authority |
| `GH-01…GH-03`, `ADR-014/020` | GitHub issue içe aktarma, doğrulanmış patch'ten taslak PR, CI/review geri bildirimi (yoklama, dinleyici yok) | `B5-03` döngüyü UI'ya taşır; `B7-03.02` issue→PR akışı bunu yeniden kullanır |
| `EVAL-01…EVAL-03`, `ADR-002/019` | Tekrarlanabilir değerlendirme koşucusu; sentetik altın-yama kıyası; gerçek ajan benchmark protokolü | `B4-04`, `B8-03` |
| `REL-01…REL-04`, `ADR-016/008` | Authenticode doğrulama hattı (test sertifikası), migration test kapısı, `health` wizard, platform kapısı (yalnız Windows GA) | `B3-09`, `B6-10`, `B9-04/06`, `V1-02` |
| `FIX-01…FIX-04` | Hosted güvenlik matrisi 28/28 skip=0 (5 Kasım 2026, koşu 42006314204); canlı taslak PR ve check-run kanıtı (test deposu); gerçek ajan benchmark; verify ağ izolasyonu; beta.1→beta.2 güncelleme kanıtları | G0 önkoşulunun çoğu karşılanmıştır; kalan riskler aşağıda |
| `CUR-01` | Cursor worker'ı AppContainer kum havuzunda | `B3-03.01` yetenek matrisine girdi |

### 3.3 Planlamayı doğrudan etkileyen açık gerçekler (depo belgelerinden)

- **Gerçek ajan benchmark sonucu (FIX-02, 5 Kasım 2026):** OpenCode/`amd/DeepSeek-V4.1-Flash`, 10 görev × 3 tekrar × 2 kol: direct 29/30 (%96,7), orchestrated 21/30 (%70), orchestrated ~2,4 kat yavaş; orkestratör kolunda güvenlik ihlali 0, direct kolda güvenlik ölçümü `unknown`, token/maliyet `unknown`. Belge bunu "orkestratör daha iyi" iddiasını **desteklemeyen** bir ölçüm olarak kaydeder (tek model, tek ajan, küçük görevler; 9 başarısızlığın nedeni çözümlenmemiş). **Sonuç:** `B4-01`, `B4-GATE-01`, `B8-03`, `B8-08` ve v1.0 pazarlama iddiaları bu temelden başlar; "daha iyi/daha hızlı" iddiası kanıtlanana kadar yazılmaz.
- **Hosted CI kanıtı kısmi:** Hosted güvenlik matrisi yeşil (28/28, skipped 0), ancak imzalı çalıştırma fixture'dır; token en düşük yetkili değil; kanıt **yayın commit'i için yinelenmelidir** (KANIT_LOG, FIX-01/FIX-03A/B). Gerçek uzak PR/check-run yalnızca test deposunda denendi.
- **beta.1→beta.2 güncelleme:** Kurucu geri alma yolu gerçek kurucuyla kanıtlandı (`schema_version: 99` senaryosu, çıkış 8, beta.1 SHA-256 aynı kaldı). Kalan risk: güncelleme sırasında çalışan proje/kampanya durdurulur; beta.1'de başlayan proje beta.2'de elle `project-approve` ister. → `B3-09.03`, `B9-04.01` bunu kapsar.
- **POSIX:** Worker yalnız Windows'ta başlatılır; POSIX'te OS kum havuzu sınırı yok (`ARCHITECTURE.md` §10, `ADR-008`).
- **Claude ve Cursor worker'ları** kendi onay modellerini korur; incelemelerde `model: null` görünebilir (ARCHITECTURE §10).
- **Onayın kimlik doğrulaması yok:** Aynı kullanıcı hesabındaki başka süreç için bilinen sınır; "kimlik modeli ayrı ürün kararı" (THREAT_MODEL §10). → `B3-00.03`, `B3-05.02` human-presence authority.
- **Kod eşlemesi doğrulaması (5 Kasım 2026, `c0e9531`):** Kaynak planların "mevcut" olarak andığı modüller depoda vardır: `engine/worker_policy.py`, `engine/appcontainer.py`, `engine/winproc.py` (kaynak planlarda `engine/winproc` olarak geçer; tek modül dosyasıdır), `engine/integration.py`, `engine/pricing.py`, `engine/capability_manifest.py`, `engine/runner.py`, `workflows/checkpoint.py`, `workflows/coordinator.py`, `workflows/roles.py`, `interfaces/rpp.py`, `tests/evals/compare.py`, `packaging/build_dist.py`, `packaging/windows/orchestrator_setup.iss`. `desktop/`, `engine/sessions/`, `engine/local_api.py` gibi yollar henüz **yoktur** (öneridir).

---

## 4. Değişmez ilkeler, güvenlik sabitleri ve tamamlanma tanımı

### 4.1 Değişmez ilkeler ve güvenlik sabitleri

**Amaç düzeltmeleri (strateji):**

**Amaç:** Beta.3/Beta.4'ün bağımsız masaüstü ve akıllı orkestrasyon temelinden hareketle Beta.5/Beta.6'da önemli rakip yeteneklerini kapsamak; Beta.7'de Respected'a özgü, işe yararlığı ölçülen özellikleri geliştirmek; Beta.8'de bağımsız karşılaştırma, bilimsel araştırma ve gerçek kullanıcı testleriyle performansı artırmak; Beta.9/RC aşamasında sürümü kararlı hale getirip v1.0 yayımlamak.

**Düzeltme A — “Tüm rakip özellikleri” için yönetilebilir tanım:** Rakiplerin bütün düğmeleri, tasarım tercihleri, fiyat planları, kapalı servisleri veya lisansa tabi yan ürünleri birebir kopyalanmaz. Aynı kullanıcı ihtiyacını karşılayan fonksiyonel yeteneklere **kanıtlı kapsama** hedeflenir. Ürün dışı/birebir taklit gereksiz özellikler açıkça *karar verilmiş istisna* olarak tutulur. Böylelikle sınırsız özellik yarışı, v1.0 çıkışını sonsuza ertelemez.

**Düzeltme B — Ölçüm Beta.8'de başlamaz:** Her iş paketinin ilk günden ölçülebilir kabul kriteri, güvenlik regresyonu, performans bütçesi ve kanıt bağlantısı olmalıdır. Beta.8 bu ölçümlerin geniş ölçekli bağımsız değerlendirme ve düzeltme dönemidir.

**Beta.3/Beta.4 güvenlik ve ürün sabitleri:**

**Kırılmayacak güvenlik ve ürün kuralları:**
- Worker AppContainer/sandbox fail-closed; yeni PTY/Chat oturumu “interaktif” diye korumasız process açamaz.
- `check`, imzalı evidence, scope/forbidden, güncellik ve `git apply --check` akışı korunur; `apply` tekrar kontrol eder, varsayılan otomatik commit/merge yoktur.
- MCP, worker, renderer ve yetkisiz child process insan onayı veremez. GUI için ayrı human-presence authority gerekir.
- Başka uygulama kurulu değilken tam kullanım; yerel MCP/skill keşfi, uyumluluk ve öneri Orchestrator’ın kendi yeteneğidir.
- Skill/MCP **keşif** ≠ doğrulanmış kullanılabilirlik ≠ güven ≠ etkinleştirme. Otomatik kurulum/aktivasyon yoktur.
- Model/CLI desteği yetenek ve sürüme göre doğrulanır. Maliyet veya token bilinmiyorsa `unknown`; 0 gösterilemez.
- Her kullanıcı verisi şeması değişikliği sürümlü migration + gerçek eski sürüm fixture + rollback gerektirir.
- `PRODUCT_CONTRACT.md` kopyaları/conformance etkisi planlanır; bu plan başka ürünün kodunu değiştirme yetkisi vermez.

**Beta.5→v1.0 sabitleri:**

**Sabitler:** Orchestrator başka bir uygulamaya, kullanıcı hesabına, markete veya ücretli TestSprite'a bağımlı değildir; mevcut Python engine, Git worktree, MAF, DAG, imzalı evidence, AppContainer, checkpoint, check/apply korunur. Renderer, worker, MCP veya uzak API insanın yetkili onayını taklit edemez. Her dış MCP/skill, tarayıcı veya remote worker ayrı güven sınırıdır. Sıfırdan Playwright/VS Code/sandbox yazılmaz; test ve kod zekâsı için sürümlü dar adaptörler kullanılır. Bilinmeyen kullanım ve fiyat `unknown` kalır.

**Strateji ilkeleri:**

1. **Bağımsız çalışma:** Hub veya başka yerel uygulama/mağaza kurulumu zorunlu değildir. Yerel görev, keşif, öneri, onay ve doğrulama bağımsız yürür.
2. **Mevcut motoru koru:** Worktree, mevcut Python engine, DAG, MAF, AppContainer, checkpoint, kanıt ve onay kurallarını yeniden yazma; üzerinde sürümlenmiş adaptör ve deneyim oluştur.
3. **Sıfır güven varsayımı:** MCP/skill/tool keşfedildiği için güvenilir sayılmaz. Dış süreçler, cloud/remote işçiler ve Playwright/test süreçleri ayrı güven sınırlarıdır.
4. **İnsan onayı:** UI/Web/MCP/remote istemciler ajan adına yetkili uygulama onayı oluşturamaz. Kimlik, kaynak ve `run_id`/patch hash bağlamı korunur.
5. **Yerel-first + BYO tools:** TestSprite/cloud/telefon/SSH seçenekli; hiçbiri çekirdek özellikleri bloke etmez.
6. **Bilinmeyen metrik ≠ sıfır:** Token, kota, güvenlik testi, desteklenen agent yeteneği ve gerçek başarı kanıtları doğrulanmadıysa `unknown` veya `not_supported` yazılır.
7. **Paralellik varsayılan iyi değildir:** Çakışma, bütçe ve gerçek hız kazancı ölçülür.
8. **Dokümantasyon-kod-güvence tutarlılığı:** `docs/ROADMAP.md` durumları gerçek commit + testle desteklenir.

### 4.2 Görev kartı standardı ve tamamlanma tanımı (Definition of Done)

**Beta.3/Beta.4:**

Bir alt görev ancak şu şartlar sağlandığında **Done** olur: (1) kod ve kapsamı review edilmiş, (2) pozitif/negatif testler geçiyor, (3) mevcut güvenlik regresyonu yeşil, (4) kullanıcı verisi etkileniyorsa migration fixture var, (5) kanıt commit SHA + komut/ortam/sonuç ile kaydedilmiş, (6) ilgili ADR/README/ROADMAP güncel, (7) rollback veya feature flag kararı belirtilmiş.

**Test ortamı:** Güvenlik sınırına dokunan görevlerin zorunlu koşuları normal, yükseltilmemiş Windows kullanıcısında gerçek AppContainer ile yapılır; skip/xfail release kanıtı sayılmaz. Mock testler ek, gerçek entegrasyonun alternatifi değildir.

**Bağımlılık gösterimi:** `B3-01.02` gibi kimlikler bu belgedeki görevlere referans verir. Beta.2 dış önkoşullar `G0` üzerinden yönetilir.

**Beta.5→v1.0:**

Her story kartı: `kimlik, amaç, öncelik, bağımlılıklar, modül/mimari, yapılacak işler, testler, ölçülebilir kabul, kanıt` alanlarını taşır. Her görevde `status = proposed` varsayılır. Yalnızca şu koşullarda Done:

1. Güncel kod incelendi; yeniden yazma/duplicate iş engellendi, gerekiyorsa ADR çıkarıldı.
2. Pozitif, negatif, entegrasyon ve ilgili regresyon testleri geçti; güvenlik koşuları uygun normal kullanıcı/OS ortamında **skipped=0**.
3. Kod review edildi, gizli veri redaksiyonu ve yetki sınırı doğrulandı.
4. Veri şeması değiştiyse sürümlü migration, gerçek eski sürüm fixture ve rollback test edildi.
5. Commit SHA, ortam, araç/model sürümü, test komutları, exit code, kullanılan artefaktlar ve eksik kanıt kaydedildi.
6. ROADMAP/architecture/evidence güncellendi; kritik risk varsa çıkış kapısında blocker açık tutuldu.

**Öncelikler (Beta.5→v1.0):**

- **P0:** O sürümdeki temel işlev veya güvenlik için olmazsa olmaz.
- **P1:** Yüksek kullanıcı değeri; belirlenen kapsamdaysa kabul testi gerekir, gerektiğinde gerekçeli defer yapılabilir.
- **P2/koşullu:** Önce veri, tehdit modeli ve fizibilite; `go` kararı olmadan genel yayına sokulmaz. `no-go` da belgelenmiş bir sonuçtur.

**Kapsama ve release kararı:**

`docs/COMPETITOR_CAPABILITY_MATRIX.md` alanları: `CAP-ID | user problem | competitor | source/date/version | shipped/beta/planned/paid | OS | respected_status | priority | issue | acceptance_test | evidence_SHA | defer/exclude_reason`.

Aynı kullanıcı ihtiyacının farklı rakip uygulamaları tek CAP-ID olabilir. Rakiplerin dekoratif uygulama detaylarını birebir kopyalamak zorunda değiliz. **Önerilen hedef:** in-scope P0 = %100 doğrulanmış; P1 ≥%90 doğrulanmış veya açıkça gerekçeli/kararlı istisna. Bunlar mevcut ölçülmüş başarı değil, release policy taslağıdır. Yeni rakip feature'ı scope freeze sonrası otomatik v1.0 blocker olmaz.

### 4.3 Başlama koşulları (önkoşul kapıları)

**Beta.3/Beta.4 önkoşulları:**

**Kaynakta doğrulanmış mevcut mekanizmalar (yeniden yazma):** `engine/worker_policy.py`, `engine/appcontainer.py`, `engine/winproc`, `workflows/checkpoint.py`, `workflows/coordinator.py`, `workflows/roles.py`, `engine/integration.py`, `engine/pricing.py`, `engine/capability_manifest.py`, `tests/evals/compare.py`, `packaging/build_dist.py`, `packaging/windows/orchestrator_setup.iss`, `interfaces/rpp.py`; belgelenmiş Git worktree, MAF, DAG, imzalı kanıt ve apply kontrolü.

**Önemli doğrulama sınırı:** Yukarıdaki yolların varlığı mimari dokümanda anlatılıyor. Klasör önerileri (`desktop/`, `engine/sessions/`, `engine/capabilities/`, vb.) bu planda **önerilen yeni yollar**dır; görev başlamadan önce `git ls-files`, mevcut sınıf/fonksiyonlar ve test diziniyle yeniden eşleştirilmelidir. Anlık GitHub dokümantasyonu sonradan değişmiş olabilir.

**Beta.2 önkoşulu:** CI’da gerçek AppContainer testlerinin skip edilmediği, verify kodunun ağ sınırı, gerçek agent benchmark ve PR/CI/UI kanıtları açısından Beta.2 FIX işlerinin durumu kontrol edilmeli. Eksik bir P0 güvenlik kapısı varken Beta.3 GUI bunu bypass eden alternatif bir yürütme yolu yaratamaz. `tests/evals/compare.py` sentetik altın-patch testi gerçek ajan kıyası değildir.

**Beta.5→v1.0 başlama koşulu ve kaynak/gerçeklik ayrımı:**

**Kaynak / gerçeklik ayrımı**

| Tür | Kullanım |
|---|---|
| Belgelenmiş mevcut | Beta.3/Beta.4 uygulama planı ve depodaki güncel mimariden doğrulanır. |
| Rakip beyanı | Beta.3/Beta.4 rakip analizi, 135 araçlık rehber ve kaynak URL/sürümü; bağımsız test yapılmadıysa `unverified`. |
| Öneri | Bu plandaki yeni API/klasörler, kullanıcı eşikleri ve test kapsamları; geliştirme sırasında ADR/testle netleştirilir. |

**Başlama koşulu**

- Beta.3/Beta.4 görevleri **belgeden değil gerçek commit ve test raporlarından** kontrol edilir.
- Beta.2 zorunlu Windows AppContainer, verify ağ sınırı, gerçek agent benchmark ve insan onayı kapıları açık ise bu plan bunları bypass edemez.
- Beta.5 başlamadan `COMPETITOR_CAPABILITY_MATRIX.md` üretilir ve P0/P1/P2 kapsamı dondurulur.
- Beta.6 remote/mobile/cloud işleri için ayrı tehdit modeli ve açık go/no-go gerekir.

**Beta.5 öncesi Beta.3/Beta.4 DoD önkoşulu (strateji):**

B5 başlamadan önce önceki Beta.3/Beta.4 uygulama planı yayın kapıları için gerçek kanıt kontrolü gerekir. Plan tamamlandı varsayımı, gerçek programın tamamlandığına kanıt değildir.

- Hub'sız masaüstü kurulumu ve iş çalıştırma.
- Güvenli Chat/Terminal, yeniden bağlanma, proje panosu, DAG, review/onay ve temel yerel skill/MCP envanteri.
- Kalıcı ekip/ajan profilleri, bütçeli routing, yerel öneri ve analitik asgari seviyede kullanılır.
- Windows AppContainer testleri zorunlu gerçek ortamda skip olmadan geçer; verify sürecinde ağ sınırı belgeli/doğrulanır.
- Aktif kullanıcı verileri için migration ve rollback fixture'ları mevcuttur.

---

## 5. Araştırma temeli: rakip analizi ve mimari kararlar

> Bu bölüm, geçici araştırma belgelerinden aktarılan rakip analizini ve gerekçeleri içerir (5 Kasım 2026). **Sınır (kaynaktan):** Üçüncü taraf yazılımlar yerel makinede çalıştırılarak test edilmedi. "Belgelenmiş" ifadeleri ürün sahiplerinin beyanıdır. "Belgede doğrulanmadı" yokluk kanıtı değildir. Analiz yalnızca **Respected Orchestrator** ürününün geliştirmelerine odaklanır; başka ürünlere çalışma zamanı bağımlılığı önermez. Kaynak rehber: kullanıcının `ai_coding_135_kategorili_rehber.html` dosyası (135 kayıt; repo dışı), rakiplerin resmî site/README/mimari kaynakları ve Respected `docs/` ana dalı.

### 5.1 Yönetici özeti

**Beta.3 — Standalone Agent Workbench:** Bağımsız masaüstü uygulaması, arayüzden bağımsız uzun yaşayan denetleyici, yapılandırılmış konuşma/gerçek terminal, görev ve DAG ekranı, canlı olay zaman çizgisi, güvenli diff/kanıt/onay, GitHub PR/CI deneyimi, kurulu ajan ve capability keşfi. *Kritik risk:* Motorun CLI/MCP'deki insan-onayı güven sınırı GUI'ye taşınırken gevşetilmemeli.

**Beta.4 — Intelligent Agent Workspace:** Risk-bazlı akıllı routing ve iş planı önerileri, izinli görev içi steer/handoff, proje ajan profilleri, yerel MCP/skill uyumluluk ve öneri motoru, ölçülebilir maliyet/kalite, bağlam bütçesi, isteğe bağlı uygulama içi yerel ses girişi, ekran görüntüsü ekleme/önizleme; uzaktan cihaz ve bulut workeri ayrı güvenlik projesi olarak ancak çekirdek doğrulandıktan sonra.

Ürün konumu: **“Çalışan ajan filosu” değil, “kontrol altında, kanıtla teslim eden coding agent ekibi.”**

### 5.2 Respected'ın belgelenmiş mevcut temeli (analiz raporuna göre)

- İşçi başına Git worktree + kapsam/forbidden kontrolü + imzalı kanıt + güncellik denetimi + ayrı insan `apply` kararı.
- Windows AppContainer worker kısıtlaması, fail-closed launcher, varsayılan ağ yok; diğer platformlar için eşdeğer güvenlik henüz doğrulanmamış.
- `tester`, bağımsız reviewer, sınırlı fix ve tekrar eden hata durdurma döngüsü.
- `coordinator` doğrulanmış DAG planı; kampanya paralelliği ve bağımlılık denetimi.
- Sürümlü ve imzalı checkpoint, kontrollü resume.
- RPP / MCP / CLI yüzeyleri; MCP üzerinden insan güvenlik onayı devredilmez.
- `engine/capability_manifest.py` fail-closed trust/provenance kontrolü; bu **yerel keşif/uyumluluk/öneri** ile aynı şey değildir.
- `tests/evals/compare.py` sentetik altın-yama karşılaştırması; gerçek model ölçümü olarak sunulmamalıdır.
- Resmî bağımsız masaüstü Workbench, canlı native Chat/PTY session deneyimi ve uygulama içinde son kullanıcı onayı bu kaynaklarda doğrulanamadı.

Kaynaklar: 
- https://github.com/respected0/respected-orchestrator/blob/main/docs/ARCHITECTURE.md
- https://github.com/respected0/respected-orchestrator/blob/main/docs/ROADMAP.md
- https://github.com/respected0/respected-orchestrator/blob/main/docs/PRODUCT_CONTRACT.md
- https://github.com/respected0/respected-orchestrator/blob/main/docs/evidence/KANIT_LOG.md

### 5.3 Rakip matrisi — 16 çoklu ajan / orkestrasyon

| Rehber # | Rakip | Belgelenen güçlü yaklaşım | Çıkarılacak ürün/mimari dersi | Öncelik |
|---|---|---|---|---|
| 077 | OrchestratorInc | Go daemon + Electron, Chat/TUI, worktree, GitHub PR/CI, review feedback, mobil, cloud, session restoration, browser preview | Kalıcı oturumlar ve tek panelde PR/CI + eylem | En kritik |
| 106 | Muratify AgentSpace | Kalıcı kimlikli çalışan, pixel-art office, gerçek split terminal, canlı diff, mobil onay, yerel dikte/screenshot tamamlayıcıları, hesap/maliyet | Ekip hissi, anlık gözlemlenebilirlik, görünür kullanıcı kontrolü | En kritik |
| 119 | Orca | Paralel worktree, çok ajanlı IDE, terminal/diff/browser/CLI, mobil, GitHub/Linear | Tek çalışma alanında dosya, tarayıcı, terminal, görev | Yüksek |
| 125 | Vi3ecode | Lead/Analyst/Developer/QA/Designer, shared thread, auto-handoff cap, PTY/chat, live steering, budget | Kalıcı rol profili ve denetlenebilir handoff | Yüksek |
| 060 | Mission Control | Task/Aegis quality gates, cost, alerts, agent runtime, skills, REST/MCP/CLI/WS/SSE | İşletim/kalite panosu ve açık kontrol API'si | Yüksek |
| 064 | Munder Difflin | Gerçek CLI PTY, çalışanların mailbox/blackboard, circuit breaker, mem, Monaco, lokal dikte, Slack/webhooks | Koordinasyon mesajları ve arıza döngüsü freni | Yüksek |
| 115 | Herdr | Window'dan ayrı `herdr-core`, tekrar bağlanma, agent helper/rapor, SSH machines, agent-customizable layouts | UI ölse de oturum koruma; sınırlı kişiselleştirme | Yüksek |
| 131 | Open Space | Pixel-art çoklu Claude Code oturumu; izinler, anlık diff, bağlam, bildirim, session search | Düşük sürtünmeli izin/oturum arayüzü | Orta-yüksek |
| 071 | Oh My ClaudeCode | Team aşamaları, multi-provider reviewer, deep interview, rate-limit wait, HUD, eval/learning | İş modu seçimi, görev brifingi, limit müdahalesi | Orta-yüksek |
| 053 | Kitchen | tmux, MCP kanalları, named worktree, reviewer | Gerçek oturum + araçlardan bağımsız koordinasyon | Orta |
| 003 | Agency Orchestrator | YAML/DAG/acceptance, web studio, şablonlar ve çok dil | Paylaşılabilir fakat denetimli workflow şablonları | Orta |
| 128 | DeepSeek DSH Superagent | Yetkili olay kaynaklarından görev alma, session, thread ve PR; araştırma prototipi | Event-to-task/admission policy; proaktif işlemi kontrollü tut | Orta |
| 018 | Block/Buzz | İmzalı olaylar, shared team/agent channels, branch-as-room, audit | Denetlenebilir olay/yorum geçmişi | Orta |
| 040 | gstack | CEO/designer/manager/release/QA uzman komutları | Basit, anlaşılır hazır rol reçeteleri | Seçmeli |
| 002 | Agency Agents | Hazır uzman personelar ve deliverable tanımları | Rol şablonları; yeni LLM framework gereksiz | Seçmeli |
| 087 | a-sirketi | Ajan ekip rol örnekleri, insan yayın kararı | İnsan kontrolü ve küçük ekip onboarding örnekleri | Seçmeli |

Not: Rehberdeki *doğrudan/kısmi rakiplik*, hedef ürüne göre değerlendirmedir; her araç aynı işi yapmaz. Ticari ürünlerde söylenen “var” özelliği ayrıca regresyonla doğrulanmış sayılmadı.

#### 5.3.1 Ek/komşu araçlar: potansiyel benchmark ve ilham

- **118 MXterm**: çoklu terminal + SSH, token meter, uzaktan kontrol; Respected için metriklerin güvenilirliği ve çok makine bağlantısı örneği. https://mxterm.net/
- **129 EVOLV**: yerel, değiştirilebilir UI/skills/plugins; Orchestrator çekirdeğine öz-değişiklik izni verilmemeli; gelecekte sadece sandbox'lı tema/mod önerileri düşünülebilir. https://github.com/dxn111/EVOLV
- **051 Jcode**: Rust agent harness performans yaklaşımı; doğrudan taşınması gerekli değil. https://github.com/1jehuang/jcode
- **089 GitHub Spec Kit / 090 Superpowers**: plan/test sözleşmesi, uygulama öncesi netlik. https://github.com/github/spec-kit , https://github.com/obra/superpowers
- **092 Task Observer**: tekrarlanan görev desenlerinden *öneri* üretme; otomatik yetki genişletme olmamalı. https://github.com/jonbobo212/task-observer
- **076 Serena / 043 Graphify / 042 Graft / 061 Context Mode**: ihtiyaca göre kod zekâsı ve bağlam tasarrufu. Orchestrator bunları gömülü zorunlu motor değil, isteğe bağlı yetenek olarak tanıyabilir.
- **023 Cloudflare Security Audit Skill / 134 AI Design Check / 133 Unslop**: doğrulama profilleri ve tasarım kalite değerlendirme örnekleri; görev odaklı öneri ama otomatik kurulum yok.
- **019 Claudex Loop / 052 LLM Council**: kritik kararlarda karşılıklı model incelemesi, gereksiz her görevde çok model kullanımını önle.

Katalogdan yeni özellikle ilgili kayıtlar: **#128 (DeepSeek DSH)**, **#129 (EVOLV)**, **#131 (Open Space)**. #130/#132 disk bakım uygulamaları, #133/#134 kalite/tasarım yardımcıları, #135 avatar altyapısıdır; doğrudan orkestratör değiller.

### 5.4 OrchestratorInc ve AgentSpace'den ayrıntılı öğrenimler

#### 5.4.1 OrchestratorInc

- Go daemon, Electron/TS, SQLite+CDC, SSE/WebSocket, native Chat/TUI ayrı controller, session restore, host adoption, UI/daemon güncellemesi sırasında canlı workeri koruma.
- Board = waiting/working/review/merge; PR, branch, CI/reviewer bağları; tarayıcı önizleme.
- GitHub issue intake read-only; PR/CI geri bildirimleri; otomasyonlar ve cues.
- Masaüstü ile mobil/opsiyonel bulut ayırımı; mobilde kimlik, pairing ve cihaz yetkileri.
- Dikkat: `main` ile yayımlanan sürüm farkı var. Özellik katalogunda her ajanın worker/chat/reviewer kapsamı farklı. “35+ agent” = bütün rollerin aynı düzeyde çalışması değil.

Kaynaklar: https://github.com/OrchestratorInc/agent-orchestrator ; https://github.com/OrchestratorInc/agent-orchestrator/blob/main/docs/STATUS.md ; https://docs.orchestrator.inc/ ; https://docs.orchestrator.inc/dashboard/

#### 5.4.2 Muratify AgentSpace / AgentVoice / AgentShot

- Kalıcı isim/kimlik, ofis metaforu, PTY pane splitting, kanban, canlı diff, browser, kalıcı hafıza ve dev/prod ayrı izinli entegrasyon kartları.
- Desteklenen CLI motorları ile yalnız sağlayıcı model yönlendirmelerini ve roadmap'teki motorları ayrı listelemesi olumlu.
- Token kullanımında varsa gerçek transkript; bilinmeyen maliyette sahte $0 göstermekten kaçınma; kota yüzdelerinin bilinmeyebileceğini açık söyleme.
- AgentVoice başka uygulamalara da yazan sistem genelinde yerel STT ürünüdür; Orchestrator için daha küçük uygulama içi ses-to-text yeterli.
- AgentShot bağımsız bölge yakalama/işaretleme ürünüdür; Orchestrator'da yalnız göreve ekran görüntüsü iliştirme ve gizlilik önizlemesi yeterli.
- Mobil ve bulut senkron, hesap/cihaz yönetimi ve gizlilik yüzeyi çok büyük ayrı mühendislik projeleridir.

Kaynaklar: https://muratify.com/tr/products/agentspace ; https://muratify.com/tr/products/agentvoice ; https://muratify.com/tr/products/agentshot

### 5.5 Rakip yetenek envanteri ve kapsama ölçüsü (strateji)

Rehberdeki 135 kaydın tamamı doğrudan rakip değildir; **16 orkestrasyon** ve **6 AI coding terminal/ortamı** ana tarama havuzudur. Gstack, Spec Kit, Playwright CLI/MCP, TestSprite, Serena, Graft, Context Mode gibi ürünler tamamlayıcı yetenek/araç referansıdır.

| Rakip/küme | İzlenecek işlev aileleri | Öncelikli sürüm |
|---|---|---|
| OrchestratorInc | Çoklu agent, native Chat/PTTY, worktree, PR/CI/review/çatışma, otomasyonlar, Cues, yerel daemon, mobil, multi-host, cloud | B5 çekirdek; B6 uzak/bulut |
| AgentSpace + AgentVoice/AgentShot | Kalıcı ajan ekipleri, görsel ofis, görev dağıtımı, split terminal, ses/görsel görev, usage ve hesap, mobil deneyim | B5 deneyim; B6 mobil/opsiyonel ofis |
| Orca | Worktree IDE, browser/design mode, satır içi diff yorumu, SSH, hızlı arama, çoklu split, mobil | B5 yerel çalışma; B6 ileri kontrol |
| Mission Control | Quality gates, audit, event logs, rol/izin, API/MCP, schedules, maliyet | B5 yönetişim; B6 API ve workspace |
| Vi3ecode / Munder Difflin | Kalıcı ekip, lider/dev/QA, handoff, mailbox, circuit breaker, bağlam/hafıza | B5 deneyim; B6 gelişmiş koordinasyon |
| Open Space / Herdr / Kitchen | Etkileşimli oturum, çalışma devamlılığı, terminal-pane, bildirim, proje durumu | B5 oturum sağlamlığı |
| Oh My ClaudeCode / Agency Orchestrator | İş modu, plan/verify, YAML DAG, rol ve şablon, sınırlı otomasyon | B5 tekrar kullanılabilir workflow |
| DeepSeek DSH prototype / block-buzz | Olaydan kontrollü görev tetikleme, izinli iş alma, denetlenebilir olay iletişimi | B6 events/automation |

Rakiplerin üretici beyanı, aktif sürümdeki gerçek davranışı, planlanan özelliği ve ücretli plan özelliği aynı kabul edilmez. Her satır özgün kanıt linki ve tarih içerir.

**Zorunlu envanter dosyası (öneri, yeni):** `docs/COMPETITOR_CAPABILITY_MATRIX.md`

Her rakip yeteneği bir satır olarak kaydet:

`CAP-ID | User problem | Competitor | Source URL | Checked date | Shipped/Beta/Planned/Paid | Target platform | Respected status (verified/partial/absent/unknown) | Parity decision (P0/P1/P2/excluded) | B5/B6 issue | Acceptance test | Evidence commit | Owner`

- **Kapsama birimi** UI butonu değil, kullanıcının başarıyla tamamlayabildiği eylemdir.
- Aynı yeteneği sağlayan birden fazla rakip özelliği tek `CAP-ID` altında toplanabilir.
- `excluded` kararı yalnızca gerekçe, güvenlik/ekonomi etkisi ve kullanıcıya alternatifle verilebilir.
- Değişen rakip özellikleri haftalık sürüm takibiyle otomatik içeri alınmaz; sürüm kapsamı ayrıca triage edilir.
- P0 temel iş akışlarının tamamı, P1 yüksek değerli akışların çoğu yayın öncesinde **gerçek e2e** ile karşılanmalı; P2 açık kapsamlı erteleme listesi olabilir.
- Öneri niteliğinde kapsama göstergesi: `weighted_coverage = sum(priority_weight × verified_capability) / sum(priority_weight × in_scope_capability)`; kısmi duruma otomatik tam puan verilmez. P0 kapsam için hedef %100, P1 için hedef en az %90. Bu oranlar benchmark sonucu değil planlama eşiğidir.

(Matris alan listesi iki kaynakta farklıdır; birleşimi Ek C, C3'tedir. İlk taslak satırlar §6'dadır.)

### 5.6 Mimari sınırlar

```
Standalone Desktop UI (Tauri/React/TypeScript)
    |
    +-- typed, authenticated, least-privilege local IPC
    v
Long-running Orchestrator Supervisor / Engine (Python, existing)
    |-- task coordinator / DAG + MAF
    |-- agent adapter (native chat where supported, PTY via controlled broker)
    |-- event store, replay, checkpoint
    |-- evidence/check/apply + separate human-presence authority
    |-- capability discovery + compatibility + trust gate (local)
    |-- usage ledger + real benchmark
    v
Policy-bounded Workers (Windows AppContainer; explicit fail-closed)
```

Güvenlik: UI'daki `Approve` düğmesi doğrudan arbitrary CLI shell'e çevrilmemeli; ayrı native onay köprüsü kullanıcı etkileşimini doğrulamalı; işlemin hangi run/patch için ve hangi kapsamda yapıldığı imzalı olmalı. Renderer, ajanlar ve MCP hiçbiri ayrıcalıklı IPC yetkisine otomatik sahip olmamalı.

### 5.7 Yapılmayacaklar

**Rakip analizinden:**

- Sıfırdan farklı bir kod sandbox veya scheduler yazma.
- Motoru Rust'a yeniden yazma; güvenliği ve runtime adapter'larını koru.
- Müşteri hesabını veya bulut bağlantısını zorunlu yapma.
- 3B/pixel-art office'i kritik yolun önüne koyma; önce fonksiyonel etkileşim.
- 35+ CLI adını 'tam destek' olarak yayımlama; her modelin role/capability matrisini gerçekten doğrula.
- Voice-to-code'u doğrudan otomatik `apply` olarak bağlama.
- Üçüncü taraf MCP/skill'i yalnız keşfedildi diye güvenilir sayma veya çalıştırma.
- Üretim kullanıcısı ve veri geçişi olmadan API contract'ını kırma.

**Beta.3/Beta.4 uygulama planından:**

- Python motorunu sırf yeni UI için Rust/Go’ya taşımak.
- Var olan sandbox, DAG, MAF, evidence ve checkpoint mekanizmalarını yeniden sıfırdan yazmak.
- MCP/skill mağazası, zorunlu çevrimiçi katalog veya zorunlu kullanıcı hesabı geliştirmek.
- 3B ofis, sahte agent avatarları veya tam IDE’yi release critical path’e koymak.
- 35+ CLI’ı tam destekli ilan etmek; her mod ancak gerçek testle enabled olur.
- Kullanıcı onayı olmadan worker/run başlatmak, yeni MCP yetkisi vermek, patch uygulamak veya PR merge etmek.

### 5.8 Ölçüm ve risk kararları (strateji)

- **Rakip sayısına göre değil, kullanıcı görevine göre kapsam:** “Muratify'daki pixel-art ofisin aynısı” yerine “kalıcı ekip durumunu hızlı görme”; dekoratif ofis ancak kullanıcı faydası kanıtlanırsa.
- **Mobil/cloud ayrı risk:** Mobil kimlik doğrulama ve güvenli onay; remote worker'ın OS izolasyonu; cloud işletme maliyeti ayrı release gate.
- **Fiyatlı / kapalı TestSprite:** Genel iş akışına bağlanabilir ama kodunu kopyalama, ücretli hizmeti ücretsizmiş gibi vaat etme; gereken veri çıkışı ve maliyeti kullanıcıya göster.
- **Tool çoğaltma:** Playwright/TestSprite/Serena/Context Mode/pytest/Jest zaten mevcut yeteneklerin üzerine dar adaptör; Orchestrator sadece koşuyu, yetkiyi, kanıtı ve kararı yönetir.
- **Benchmark tuzağı:** Flaky tests, test verisinin eğitime karışması, ortam farklılığı, dar puanlama; gerektiğinde bağımsız insan incelemesi.
- **Sürüm kayması:** Kaynakları tarihle; B5/B6 scope freeze sonrası her yeni rakip özelliğini otomatik olarak 1.0 hedefine ekleme.

### 5.9 Analiz raporundaki sürüm kapısı önerileri (özgün hâli)

Bu liste, uygulama planlarındaki kapıların (§15) özgün öneri biçimidir ve karşılaştırma için korunmuştur.

Beta.3 release:
1. Hub veya başka uygulama kurulu olmayan normal Windows kullanıcısında tam uçtan uca görev.
2. UI kapanması/crash sonrası worker ve gerçek session durumu korunur.
3. Terminal/Chat modları kapasiteye göre doğru görünür; yapılandırılmış olaylarda sır sızıntısı yok.
4. GUI üzerinden geçersiz/stale kanıt uygulanamaz; insanlar dışındaki süreçlerin onay kapısı yoktur.
5. DAG invalid planla sıfır worker; eski veriler migration ile korunur.
6. CI P0 güvenlik doğrulaması ve Beta.2 yayın kapıları tamam.

Beta.4 release:
1. Agent seçimi kıyaslaması gerçek benchmark'ta raporlu; bilinmeyen maliyet uydurulmaz.
2. MCP/skill önerileri çevrimdışı, başka uygulama olmadan çalışır; izin olmadan aktivasyon olmaz.
3. Handoff/circuit breaker döngülerinin negatif ve retry testleri geçer.
4. Ses ve ekran görüntüsü varsa opt-in, revocable ve görev onayından ayrı.
5. Regresyon: kabul edilen görev başarısı düşmüyor, worker güvenlik ihlali artmıyor; ölçülmemiş iddia yok.

---

## 6. Rakip yetenek kapsam matrisi (Beta.5 / Beta.6) `[ÖNERİ]`

> **Statü:** Bu matris, kaynak planlardaki rakip yeteneklerinin ve görevlerin ilk **taslak** eşlemesidir (kontrol tarihi: 5 Kasım 2026). Rakip sütunları üretici beyanıdır; yerelde denenmemiştir ve `shipped/beta/planned/paid` ayrımı bilinmediği için bu tabloda yapılmamıştır — bu ayrım `B5-00.01` ile yapılır ve `docs/COMPETITOR_CAPABILITY_MATRIX.md` (yeni dosya, öneri) olarak kalıcılaşır. "Respected şu an" sütunu §3.2'deki belgelenmiş duruma dayanır ve görev başlangıcında kodda yeniden doğrulanır. Öncelik sütunu `[ÖNERİ]`dir: hedef görevin kaynak plandaki önceliğinden türetilmiştir ve `B5-00.02` kapsam dondurmasında kesinleşir.

**Kapsama birimi** UI butonu değil, kullanıcının başarıyla tamamlayabildiği eylemdir. Planlama eşiği (benchmark sonucu değildir): P0 kapsamı hedef %100, P1 hedef ≥%90 (§5.5 `weighted_coverage`).

**Kaynak anahtarları** (tam URL'ler §18'de de vardır): **OI** = OrchestratorInc (https://github.com/OrchestratorInc/agent-orchestrator ; https://docs.orchestrator.inc/) · **AS** = Muratify AgentSpace (https://muratify.com/tr/products/agentspace) · **AV** = AgentVoice (https://muratify.com/tr/products/agentvoice) · **ASH** = AgentShot (https://muratify.com/tr/products/agentshot) · **ORCA** = Orca (https://www.onorca.dev/ ; https://www.onorca.dev/docs/mobile) · **MC** = Mission Control (https://github.com/builderz-labs/mission-control) · **V3** = Vi3ecode (https://vi3ecode.com/) · **MD** = Munder Difflin (https://github.com/HarnessMD/munder-difflin) · **HERDR** = Herdr (https://herdr.dev/) · **OS** = Open Space (https://github.com/Fantomiald/open-space) · **OMC** = Oh My ClaudeCode (https://github.com/Yeachan-Heo/oh-my-claudecode) · **KIT** = Kitchen (https://github.com/plonkus/kitchen) · **AO** = Agency Orchestrator (https://github.com/jnMetaCode/agency-orchestrator) · **DSH** = DeepSeek DSH prototype (https://github.com/deepseek-ai/dsh-superagent-prototype) · **BUZZ** = Block/Buzz (https://github.com/block/buzz) · **MXT** = MXterm (https://mxterm.net/).

**Respected durum etiketleri:** `mevcut` (depo belgelerinde kanıtlı), `kısmi`, `yok`, `unknown` (doğrulanmadı). `yok` = bağımsız masaüstü/UI katmanı henüz yoktur; arkadaki motor yeteneği ayrıca belirtilmiştir.

### 6.1 Yetenek satırları

| CAP-ID | Kullanıcının tamamlayabildiği eylem | Rakip referansı (kaynak) | Respected şu an | Hedef sürüm / görev | Öncelik | Doğrulama yöntemi |
|---|---|---|---|---|---|---|
| CAP-001 | Tek bağımsız masaüstü uygulamasında proje, run ve review'u yönetmek | OI (daemon+Electron), AS, ORCA | yok (motor CLI/RPP/MCP; bağımsız GUI doğrulanmadı) | Beta.3 `B3-01`, `B3-GATE-01` | P0 | Temiz Windows normal kullanıcı, başka uygulama yok, kurulumdan apply'a e2e |
| CAP-002 | Pencere kapansa/çökse de işin sürmesi, geri açınca doğru durumu görmek | OI (session restore, host adoption), HERDR (`herdr-core`) | kısmi (checkpoint/resume var; UI'dan bağımsız supervisor yok) | Beta.3 `B3-02`; Beta.5 `B5-01.02` | P0 | UI öldür/aç testi, event cursor/state hash, iki kez apply yok |
| CAP-003 | Ajanla yapılandırılmış Chat oturumu (araç çağrısı, ask-user, usage) | OI (native Chat/TUI), V3 (PTY/chat) | yok | Beta.3 `B3-03.03`; Beta.5 `B5-01.01` | P0 | ≥1 (Beta.5'te ≥3) gerçek CLI ile canlı transcript fixture |
| CAP-004 | Gerçek terminal/PTY oturumu | OI, AS (split terminal), ORCA, MD (gerçek CLI PTY), KIT (tmux) | yok | Beta.3 `B3-03.02` (feasibility gate), `B3-03.05`; Beta.5 `B5-01.02` | P0 (gate'e bağlı) | ConPTY+AppContainer negatif testleri; geçmezse mod kapalı kalır |
| CAP-005 | 2–4 bölmeli terminal/oturum yerleşimi | AS, ORCA, HERDR (agent-customizable layouts) | yok | Beta.3 `B3-03.05` (P1); Beta.5 `B5-01.02` | P0 (Beta.5) | 10k satır scrollback, kapat-aç yerleşim geri gelir |
| CAP-006 | Oturum geçmişinde arama ve kaldığı yerden devam | OS (session search), OI | kısmi (checkpoint resume; arama yok) | Beta.5 `B5-01.01/.02` | P0 | Pagination + reconnect cursor testi |
| CAP-007 | Çalışan ajana izinli mesaj göndermek, durdurmak (steer/interrupt) | V3 (live steering) | yok | Beta.3 `B3-03.04` | P0 | Yetki sınıfı negatifleri; tool çıktısı onaya dönüşmez |
| CAP-008 | Hangi CLI'ın hangi modu (chat/pty/resume/usage/approval) desteklediğini doğrulanmış görmek | OI (35+ ajan; her biri farklı kapsam) | kısmi (opencode, codex, claude, cursor, agy worker'ları) | Beta.3 `B3-03.01`, `B3-07`; Beta.5 `B5-01.01` | P0 | Adapter matrisi + canlı doğrulama; desteklenmeyen mod "unsupported" kaydı |
| CAP-009 | Paralel, çakışmayan worktree'lerde birden çok ajan çalıştırmak | OI, ORCA | mevcut (işçi başına worktree, kapsam/forbidden kontrolü) | Beta.5 `B5-02` (UI) | P0 | ≥3 çakışmasız iş tek projede |
| CAP-010 | Waiting/working/review/merge panosunda görevleri izlemek | OI (board), AS (kanban) | yok (motorda proje/run durumu var) | Beta.3 `B3-04.01`; Beta.5 `B5-02` | P0 | CLI ile UI aynı run durumunu gösterir |
| CAP-011 | Görev DAG'ını görsel incelemek/düzenlemek ve başlatmak | V3 (flow), AO (workflow studio) | kısmi (DAG doğrulama/scheduler mevcut; görsel yok) | Beta.3 `B3-04.02/.03/.04` | P0 | Geçersiz planla worker=0; revalidate; cycle/ownership çatışması |
| CAP-012 | Canlı diff ve değişen dosyalar | AS, ORCA, OS | yok (UI); diff/patch motorda | Beta.3 `B3-05.01`, `B3-06`; Beta.5 `B5-02.01` | P0 | Evidence fixture + UI snapshot |
| CAP-013 | Hızlı proje/dosya arama ve dosya önizleme | ORCA | yok | Beta.5 `B5-02` | P1 | Arama e2e; renderer restart sonrası tutarlılık |
| CAP-014 | GitHub issue'yu salt-okunur içeri almak | OI, DSH | mevcut (CLI/RPP, `GH-01`) | Beta.5 `B5-03` (UI); Beta.6 `B6-05` | P0 | Gerçek test deposunda içe aktarma |
| CAP-015 | PR/CI/review döngüsü: CI fail → doğru ajan → düzelt → tekrar CI → inceleme | OI (PR/CI/review feedback) | kısmi (`GH-02/03` CLI; canlı yalnız test deposunda) | Beta.5 `B5-03`; Beta.7 `B7-03.02` | P0 | Kontrollü gerçek repoda baştan sona; yanlış commit CI sonucu reddedilir |
| CAP-016 | İki worktree sonucunu güvenle birleştirmek, çatışmayı görmek | OI (çatışma) | mevcut (`SCH-03`) | Beta.5 `B5-03` | P0 | İki worktree entegrasyon fixture |
| CAP-017 | Kalite kapıları (tester/reviewer/acceptance) ile teslim | MC (Aegis gates) | mevcut (tester, MAF, bağımsız review, apply değişmezleri) | Beta.3 `B3-05`; Beta.5 `B5-11` | P0 | Mevcut QUA testleri + GUI saldırı testi |
| CAP-018 | İmzalı, denetlenebilir olay/kanıt geçmişi | BUZZ (imzalı olaylar), MC (audit) | mevcut (imzalı evidence) | Beta.3 `B3-02.02`; Beta.7 `B7-04` | P0 | Tamper/replay testleri; ikinci makinede doğrulama |
| CAP-019 | Çalışan uygulamanın tarayıcı önizlemesi | OI, ORCA | yok | Beta.3 `B3-06.03`; Beta.5 `B5-04` | P0 (Beta.5) | Playwright ile gerçek tarayıcıda akış; izin dışı ağ reddedilir |
| CAP-020 | Tasarım modu: UI elemanını seçip ajana geri bildirim, satır içi diff yorumu | ORCA (design mode, inline diff comments) | yok | Beta.5 `B5-04`; Beta.6 `B6-06` | P1 | Seçili eleman hedefe aktarılır, ekran görüntüsü redakte; otomatik write yok |
| CAP-021 | Tarayıcı testinin trace/screenshot/video kanıtını run'a bağlı görmek | (Playwright trace/video; TestSprite opsiyonel) | yok | Beta.5 `B5-04`; Beta.7 `B7-02` | P0 | Artifact digest tested commit'e bağlı |
| CAP-022 | "Needs-you" gelen kutusu, bildirim, doğru run'a cevap | OI, OS (bildirim) | yok | Beta.5 `B5-06` | P0 | 5 farklı müdahale doğru görevde; yanlış run'a cevap gönderilemez |
| CAP-023 | Tek konuşma/olay zaman çizgisi, ajanlar arası mailbox | MD (mailbox/blackboard), BUZZ (kanal/oda) | yok | Beta.5 `B5-06`, `B5-07` | P0/P1 | 3 roller arası handoff tek timeline'da |
| CAP-024 | Kalıcı kimlikli ekip ve rol profilleri | AS (kalıcı çalışan), V3 (lead/analyst/dev/QA/designer), gstack/Agency Agents (rol reçeteleri) | kısmi (`workflows/roles.py` rol atama; kalıcı takım yok) | Beta.4 `B4-02`; Beta.5 `B5-07` | P0/P1 | Profil kalıcılığı, handoff sınırı testleri |
| CAP-025 | Handoff döngüsü ve arıza freni (circuit breaker) | V3 (auto-handoff cap), MD (circuit breaker) | kısmi (başarısızlık taksonomisi `QUA-02`) | Beta.4 `B4-02`, `B4-08` | P0/P1 | max-hop, 20+ fault fixture |
| CAP-026 | Tekrarlanabilir otomasyon: preset, kayıtlı iş akışı, cron/manual tetik | OI (otomasyonlar/Cues), MC (schedules), AO (şablonlar), OMC | yok | Beta.5 `B5-05`; Beta.6 `B6-07` | P1 | Otomasyon tekrarlanır; yazma/merge/izin yükseltme insan kontrolünü aşmaz |
| CAP-027 | Gerçek token/kota/maliyet görünürlüğü (bilinmeyen = unknown) | AS (usage/hesap), MC (cost), MXT (token meter) | kısmi (fiyat kataloğu `COST-02`; unknown sözleşmesi) | Beta.4 `B4-04`; Beta.5 `B5-08` | P0 | Fixture ile yeniden hesaplama; 0 gösterilmez |
| CAP-028 | Provider/hesap sağlığı ve izinli hesap değiştirme | AS (hesap) | yok | Beta.5 `B5-08` | P1 | Gerçek sağlayıcı verisi; izinsiz kimlik değişimi yok |
| CAP-029 | Risk/maliyet bilinçli otomatik ajan seçimi | OMC, Respected `auto_assign v2` | kısmi (`COST-03`) | Beta.4 `B4-01` | P0 | Gerçek benchmark; kullanıcının açık ataması korunur |
| CAP-030 | Yerel skill/MCP envanteri, uyumluluk ve öneri (otomatik kurulum yok) | MC (skills), OMC; EVOLV/Serena vb. yalnız ilham | kısmi (`EXT-01` trust gate, `EXT-02` salt-okunur deneme) | Beta.3 `B3-08`; Beta.4 `B4-03` | P1/P0 | Çevrimdışı, başka uygulama yok; keşif sırasında hiçbir MCP çalıştırılmaz |
| CAP-031 | Uygulama içi ses ile görev taslağı | AV (sistem geneli STT), MD (lokal dikte) | yok | Beta.4 `B4-06` | P1 | Ses ağa çıkmaz; taslak otomatik çalıştırma/onay tetiklemez |
| CAP-032 | Ekran görüntüsünü göreve eklemek (gizlilik önizlemeli) | ASH (bölge yakalama/işaretleme) | yok | Beta.4 `B4-07` | P1 | Kullanıcı açıkça yüklemeden görsel aktarılmaz |
| CAP-033 | Bağlam bütçesi / seçici bağlam | Context Mode, Graft, Serena, Graphify (tamamlayıcı araçlar) | yok | Beta.4 `B4-05` | P1 | Aynı görevlerde token tasarrufu başarı kaybı olmadan ölçülür |
| CAP-034 | Mobilde izleme, bildirim, izinli cevap | OI (mobil), AS (mobil onay), ORCA (mobile) | yok | Beta.4 `B4-09` (yalnız araştırma); Beta.6 `B6-02` | P1 (Beta.6) | Eşleşme/iptal/replay saldırı testleri; app yokken desktop çalışır |
| CAP-035 | SSH / uzak worker | ORCA (SSH), HERDR (SSH machines), MXT | yok | Beta.6 `B6-01` | P0 (Beta.6) | Host pinning, revoke, process kill; remote fail-closed |
| CAP-036 | Birden çok host / cihaz ve durum senkronizasyonu | OI (host adoption, multi-host) | yok | Beta.6 `B6-03` | P1 | İş yanlış hostta başlamaz; kesintide güvenli replay |
| CAP-037 | Bulut worker (opsiyonel) | OI (cloud) | yok | Beta.6 `B6-04` (PoC + go/no-go) | P2 | Cloud kapalıyken local çekirdek tam çalışır; no-go belgelenebilir |
| CAP-038 | Ek issue/kaynak kontrol adaptörleri (GitLab/Linear vb.) | ORCA (GitHub/Linear) | yok (yalnız GitHub) | Beta.6 `B6-05` | P1 | Ortak issue/PR sözleşmesi; yanlış repo/commit bağlama negatifleri |
| CAP-039 | Operasyon API (REST/MCP/CLI/WS/SSE), webhook ve olay abonelikleri | MC (REST/MCP/CLI/WS/SSE), DSH (olaydan görev) | kısmi (RPP/MCP/CLI var; WS/SSE/webhook abonelik yok) | Beta.6 `B6-07` | P1 | API yetki matrisi; webhook replay idempotency; insan onayı API'den spoof edilemez |
| CAP-040 | Workspace rol erişimi ve paylaşım | MC (rol/izin) | yok | Beta.6 `B6-08` | P2 | Önce threat model; tek kullanıcılı kullanım bozulmaz |
| CAP-041 | Görsel takım/ofis görünümü | AS (pixel-art office), OS | yok | Beta.6 `B6-09` (yalnız kullanıcı testinde değerliyse) | P2 | Görsel mod olmadan her işlev kullanılabilir; ekran okuyucu alternatifi |
| CAP-042 | macOS/Linux'ta çalışmak | (platform ifadeleri rakip başına doğrulanmadı) | kısmi/no-go (`ADR-008`: yalnız Windows GA) | Beta.6 `B6-10` | P1 | OS başına eşdeğer izolasyon + gerçek test; Windows güvenliği diğer OS'te varmış gibi sunulmaz |
| CAP-043 | Güvenli profil/görev şablonu içe-dışa aktarma | AO (şablonlar), gstack/Agency Agents (rol reçeteleri) | yok | Beta.5 `B5-10` | P1 | Sırlar dışa aktarılmaz; eski fixture kayıpsız açılır |
| CAP-044 | Klavye ile erişilebilir, TR/EN, açık/koyu tema, küçük ekran | (rakip kanıtı kaynak planlarda yok) | yok | Beta.5 `B5-09` | P1 | Focus/contrast/resize regresyon suite'i |
| CAP-045 | Yetkili olay kaynağından kontrollü görev alma (admission policy) | DSH (event-to-task), BUZZ | yok | Beta.6 `B6-07`; Beta.7 `B7-03.01` | P1 | Proaktif işlem politika sınırı içinde; otomatik apply/merge yok |
| CAP-046 | Hata anında araştırma/öneri: tekrarlanan görev desenlerinden *öneri* | Task Observer (ilham) | yok | Beta.4 `B4-03`, `B4-08` (yalnız öneri; otomatik yetki genişletme yok) | P2 `[ÖNERİ]` | Öneri üretir, yetki genişletmez |

### 6.2 Kasıtlı istisnalar (`excluded` karar adayları)

Aşağıdakiler kaynak planlarda açıkça yapılmayacak veya koşullu olarak işaretlenmiştir; kapsamdan düşmesi bir eksik değil karar kaydıdır. Gerekçe, alternatif ve etki `B5-00.02` scope freeze ADR'sinde kesinleşir.

| İstisna | Gerekçe (kaynak) | Alternatif / koşul |
|---|---|---|
| Pixel-art/3B ofisin birebir kopyası | Kritik yolu geciktirir; önce işlevsel etkileşim | "Kalıcı ekip durumunu hızlı görme" (CAP-023/024); ofis yalnız `B6-09` koşullu |
| 35+ CLI'yı "tam destek" ilan etmek | Her modelin rol/yetenek matrisi gerçekten doğrulanmalı | Doğrulanmış adapter matrisi (CAP-008) |
| Zorunlu hesap, zorunlu bulut, zorunlu çevrimiçi MCP/skill mağazası | Ürün bağımsız ve yerel-first | Yerel keşif/öneri; cloud opsiyonel (CAP-037) |
| Sistem geneli dikte (AgentVoice benzeri) | Uygulama içi bas-konuş yeterli; gizlilik yüzeyi küçük | `B4-06` |
| Bağımsız bölge yakalama ürünü (AgentShot benzeri) | Yalnız göreve ekran görüntüsü iliştirme gerekli | `B4-07` |
| Orchestrator çekirdeğine öz-değişiklik izni (EVOLV benzeri) | Güvenlik sınırını gevşetir | Gelecekte yalnız sandbox'lı tema/mod önerisi |
| Motoru Rust'a/Go'ya yeniden yazmak (Jcode benzeri) | Güvenliği ve runtime adapter'larını korumak | Python motoru yerinde kalır |
| Voice-to-code'u doğrudan otomatik `apply`'a bağlamak | İnsan onayı devredilemez | Ses yalnız taslak |
| Üçüncü taraf MCP/skill'i yalnız keşfedildi diye güvenilir saymak | Keşif ≠ güven | `EXT-01` trust gate |
| Her LLM çağrısında çok modelli konsey (LLM Council/Claudex Loop benzeri) | Gereksiz maliyet | Yalnız kritik kararlarda, açık seçenek |

### 6.3 Tamamlayıcı araçlar ve kullanım ilkesi

Orchestrator bir test koşucusu veya kod zekâsı motoru değil, **koşuyu, yetkiyi, kanıtı ve kararı yöneten** orkestratördür. Aşağıdaki araçlar zorunlu gömülü motor değil, isteğe bağlı/adaptörle bağlanan yeteneklerdir; hiçbiri çekirdek özellikleri bloke etmez.

| Araç | Kullanım | Görev |
|---|---|---|
| Playwright CLI/MCP/Test, Trace Viewer, video (https://github.com/microsoft/playwright-cli ; https://github.com/microsoft/playwright-mcp ; https://playwright.dev/docs/trace-viewer ; https://playwright.dev/docs/videos) | Varsayılan tarayıcı doğrulama sağlayıcısı | `B5-04`, `B7-02` |
| Chrome DevTools, pytest, Jest ve proje testleri | Mevcut test koşucuları; adaptörle normalize edilir | `B7-01`, `B7-02` |
| TestSprite (https://www.testsprite.com/solutions/mcp ; https://github.com/TestSprite/testsprite-cli) | Opsiyonel/ücretli dış adaptör; ücretsizmiş gibi vaat edilmez; sonucu commit'e bağlanmadan `verified` sayılmaz | `B7-02.01` |
| Serena, Graft, Graphify, Context Mode | İsteğe bağlı kod zekâsı/bağlam tasarrufu | `B4-05`, `B7-06` |
| GitHub Spec Kit, Superpowers | Plan/test sözleşmesi ilhamı | `B4-01`, `B7-01` |

---

## 7. Beta.3 — Standalone Agent Workbench

### 7.0 Sürüm hedefi ve kapsamı

**Beta.3 — Standalone Agent Workbench:** Bağımsız masaüstü uygulaması, arayüzden bağımsız uzun yaşayan denetleyici, yapılandırılmış konuşma/gerçek terminal, görev ve DAG ekranı, canlı olay zaman çizgisi, güvenli diff/kanıt/onay, GitHub PR/CI deneyimi, kurulu ajan ve capability keşfi. *Kritik risk:* Motorun CLI/MCP'deki insan-onayı güven sınırı GUI'ye taşınırken gevşetilmemeli.

| Sürüm | Teması | Mutlaka çıkacaklar | Koşullu / sonraya |
|---|---|---|---|
| **Beta.3** | Standalone Agent Workbench | Bağımsız GUI, IPC, supervisor, izinli Chat/Terminal, board/DAG, kanıt/onay, packaging | Local browser preview gibi P1 iyileştirmeler teknik risk varsa kapalı flag ile taşınabilir |

**Ana iş indeksi — Beta.3**

| Ana iş | Öncelik | Alt görev | Hedef |
|---|---|---:|---|
| `B3-00` | P0 | 4 | Ürün sınırları, GUI yetki modeli ve sözleşme |
| `B3-01` | P0 | 4 | Bağımsız Tauri masaüstü uygulaması ve tipli IPC |
| `B3-02` | P0 | 4 | Kalıcı supervisor, event store ve reconnect |
| `B3-03` | P0 | 5 | Gerçek Chat/Terminal agent oturumları |
| `B3-04` | P0 | 4 | Project Board ve görsel DAG planlama |
| `B3-05` | P0 | 4 | Review, diff ve insan onayı merkezi |
| `B3-06` | P1 | 3 | Canlı aktivite, dosya, terminal ve önizleme inspector |
| `B3-07` | P1 | 3 | Ajan profilleri ve uyumluluk kontrolleri |
| `B3-08` | P1 | 3 | Yerel, salt-okunur MCP/Skill envanteri |
| `B3-09` | P0 | 4 | Kurulum, güncelleme, veri geçişi ve beta release |

### 7.1 Ayrıntılı görevler — Beta.3

### B3-00 — Ürün sınırları, GUI yetki modeli ve sözleşme [P0]

**Amaç:** Motorun ve yeni masaüstü uygulamasının sahiplik, güven ve onay sınırlarını yazılı ve test edilebilir hale getirmek.
**Mevcut / önerilen kod eşlemesi:** Mevcut: docs/PRODUCT_CONTRACT.md, docs/ARCHITECTURE.md, docs/THREAT_MODEL.md, interfaces/rpp.py. Önerilen: docs/adr/ADR-desktop-boundary.md, desktop/contracts/.
**Rakip dayanağı:** OrchestratorInc daemon ayrımı; Herdr core ayrımı; Respected imzalı kanıt.
**Ana kabul koşulu:** Başka bir uygulama olmadan çalışma; renderer veya ajan aracılığıyla ayrıcalıklı eylem sıfır; mevcut CLI/MCP değişmezleri korunur.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-00 — Ürün sözleşmesi ve güven sınırları [P0]`):
>
> - Mimari: `PRODUCT_CONTRACT.md` ve uyum testleri; bağımsız GUI'nin sahiplik/onay/ağ yüzeyini tanımla.
> - Test: Hub kurulmadan end-to-end, eski CLI/MCP davranışı, GUI üzerinden ayrıcalık aşma denemesi.
> - Kabul: Tüm temel işlemler bağımsız yürür, hiçbir model/worker kendi onayını üretemez.

#### B3-00.01 — Mevcut sınırları ve sürüm bazını dondur

- [x] **Tamamlandı** — baz `ec9e599`; ADR-021 + `KANIT_LOG.md` §B3-00.01 (kanıt commit'i `git log` içinde).
- **Öncelik / boyut:** P0 / S
- **Bağımlılıklar:** Yok (G0 önkoşulları geçerli).
- **Mimari / değişecek alan:** Mevcut ARCHITECTURE/PRODUCT_CONTRACT/ROADMAP ve KANIT_LOG; kod eşlemesi raporlanır.
- **Uygulama adımları:** Beta.2 release kapılarını, halihazırda olan komutları, sahiplikleri ve insan onayı yolunu tabloya dök; olası sözleşme değişimini ADR olarak kaydet.
- **Test senaryoları:** Belgede listelenen her güvenlik değişmezi için mevcut test/kanıt bağlantısını bul; eksik testleri issue olarak işaretle.
- **Ölçülebilir kabul:** Tüm kritik invariantlar için bir test kaynağı veya açık boşluk kaydı; hiçbir Beta.2 işi Beta.3 tamamlandı diye sayılmaz.
- **Tamamlanma kanıtı:** Baseline commit SHA + invariant matrisi + ADR.

#### B3-00.02 — Desktop threat model ve trust boundary

- [x] **Tamamlandı** — THREAT_MODEL §12 + `tests/docs/test_desktop_threat_model.py`; `KANIT_LOG.md` §B3-00.02.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-00.01`.
- **Mimari / değişecek alan:** Yeni UI renderer / Tauri native shell / yerel servis / worker / MCP sınırlarını ayır.
- **Uygulama adımları:** IPC spoofing, localhost CSRF, deep-link injection, XSS, renderer compromise, replay, ayrıcalık yükseltme, symlink/patch drift tehditlerini modelle.
- **Test senaryoları:** En az 12 negatif tehdit senaryosu için test planı; renderer içinden onay komutu taklidi denemesi.
- **Ölçülebilir kabul:** Bütün yetkili eylemlerin sahibi, kaydı ve reddetme durumu belirli; varsayılan fail-closed.
- **Tamamlanma kanıtı:** THREAT_MODEL ek taslağı + saldırı matrisi.

#### B3-00.03 — Komut/yetki matrisi ve onay otoritesi sözleşmesi

- [x] **Tamamlandı** — ADR-022 + `engine/authority.py` + `tests/engine/test_authority.py`; `KANIT_LOG.md` §B3-00.03.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-00.02`.
- **Mimari / değişecek alan:** Mevcut check/apply ve maf-approve davranışını koruyan ayrı human-presence authority protokolü taslağı.
- **Uygulama adımları:** Read/status, task/start, cancel, settings ve privileged/approve yetkilerini ayrı politika sınıflarıyla tanımla; worker/MCP/renderer girdisini operatör eyleminden ayır.
- **Test senaryoları:** Role matrix unit testi; yetkisiz apply, yanlış patch, tekrar oynatma ve devredilmiş child-origin testleri.
- **Ölçülebilir kabul:** AI/MCP/renderer kontrolü ile insanın yerine geçilemez; scope + run_id + patch digest eşleşir.
- **Tamamlanma kanıtı:** Yetki matrisi ve protokol örnekleri.

#### B3-00.04 — Ürün sözleşmesi ve uyumluluk karar kaydı

- [x] **Tamamlandı** — ADR-023 + conformance raporu (`KANIT_LOG.md` §B3-00.04; üç kopya sürüklenmesi bulgusu kayıtlı).
- **Öncelik / boyut:** P0 / S
- **Bağımlılıklar:** `B3-00.03`.
- **Mimari / değişecek alan:** PRODUCT_CONTRACT üç-kopya ve conformance kuralıyla uyumlu değişiklik planı (bu iş başka ürün geliştirmesi değildir).
- **Uygulama adımları:** Görsel arayüz sahipliği Orchestrator’a geçecek; ancak hesap, çevrimiçi servis ve başka uygulama koşulu oluşturulmayacak; sözleşme değişimi gerekiyorsa sürümlü planı belgele.
- **Test senaryoları:** Mevcut conformance ve CLI/MCP regresyonu; başka ürün yok senaryosu.
- **Ölçülebilir kabul:** Sözleşme taslağı ve conformance etkisi belgelidir; başka repo üzerinde izinsiz değişiklik yapılmaz.
- **Tamamlanma kanıtı:** ADR + sözleşme diff taslağı + conformance raporu.

### B3-01 — Bağımsız Tauri masaüstü uygulaması ve tipli IPC [P0]

**Amaç:** Python motorunu yeniden yazmadan gerçek bağımsız Windows GUI sağlamak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: src/respected_orchestrator/interfaces/rpp.py ve engine giriş noktaları. Önerilen: desktop/ (Tauri 2 / React / TS), yerel IPC adapter.
**Rakip dayanağı:** Orca Workbench; OrchestratorInc Electron/daemon; Herdr core.
**Ana kabul koşulu:** Uygulama açılır, motor durumunu gösterir, yetkisiz generic shell yok, başka uygulama olmadan ilk okuma deneyimi çalışır.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-01 — Tauri 2 + React/TS masaüstü shell [P0]`):
>
> - Mimari: tek repo içinde `desktop/`; Python motoru yerinde kalır; tipli ve allowlist'li IPC adaptörü.
> - Test: temiz Windows, yükseltilmemiş kullanıcı, kurulum/upgrade/uninstall, izin ihlali.
> - Kabul: Kurulumdan ilk göreve geçiş kullanıcı rehberli, GUI motoru yeniden yazmaz.

#### B3-01.01 — Tauri/React build ve güvenli başlangıç PoC

- [x] **Tamamlandı** — `desktop/` + `tests/desktop/test_shell_policy.py` + cargo test + smoke; `KANIT_LOG.md` §B3-01.01 (kalan riskler orada).
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-00.02`.
- **Mimari / değişecek alan:** Önerilen desktop/ Tauri 2 shell; üretim derlemesinde sabit allowlist, dış URL ve dosya erişim politikası.
- **Uygulama adımları:** Tek pencere, local resources, CSP, navigation guard ve signed asset/integrity tasarımı; üretim/development ayrımı.
- **Test senaryoları:** Tauri build smoke, yasak web navigation, arbitrary invoke, local-file erişim ve CSP regresyonu.
- **Ölçülebilir kabul:** Temiz Windows normal kullanıcıda pencere açılır; renderer arbitrary command çalıştıramaz.
- **Tamamlanma kanıtı:** Installer dışı test build + smoke log + CSP test sonucu.

#### B3-01.02 — Tipli IPC şeması, istemci ve sunucu

- [x] **Tamamlandı** — `engine/local_api.py` + `tests/engine/test_local_api.py`; `KANIT_LOG.md` §B3-01.02.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-00.03`, `B3-01.01`.
- **Mimari / değişecek alan:** Proposed desktop/contracts/ ve engine/local_api.py; mevcut RPP davranışını sarmala, değiştirme.
- **Uygulama adımları:** Komut sürümü, correlation id, operation id, error enum, payload size limit, auth handshake ve idempotency tanımla.
- **Test senaryoları:** Şema fuzz, unknown message, oversized payload, malformed JSON, replay, bypass, sürüm uyumsuzluğu.
- **Ölçülebilir kabul:** Bilinmeyen komut reddedilir; her yanıt izlenebilir; istemci/sunucu sürüm uyumsuzsa yetkili eylem engellenir.
- **Tamamlanma kanıtı:** Schema/test fixtures + negatif IPC raporu.

#### B3-01.03 — Engine connector ve health/version handshake

- [x] **Tamamlandı** — `engine_connector.rs` + `_ipc` + testler; `KANIT_LOG.md` §B3-01.03 (olumlu paketli-motor E2E B3-09.01'e devredildi).
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-01.02`.
- **Mimari / değişecek alan:** Var olan packaged engine exe, context.engine_command; proposed engine_connector.
- **Uygulama adımları:** Bağımsız GUI motoru keşfeder, başlatır veya çalışan motorla güvenli bağ kurar; health, version, installation state verir; raw command dispatch yok.
- **Test senaryoları:** Engine yok, bozuk install, sürüm farkı, beklenmedik port/pipe owner, crash ve tekrar bağlanma.
- **Ölçülebilir kabul:** GUI wrong-owner servisine bağlanmaz; motor bozuksa onarım önerilir; başka ürün gerektirmez.
- **Tamamlanma kanıtı:** E2E connector log ve version matrix.

#### B3-01.04 — Temel navigation, erişilebilirlik ve hata durumları

- [x] **Tamamlandı** — `desktop/src/shell.ts` + `tests/shell.test.ts` + UIA e2e; `KANIT_LOG.md` §B3-01.04 (kalan riskler orada).
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-01.03`.
- **Mimari / değişecek alan:** Önerilen React shell ve tipli API read model.
- **Uygulama adımları:** Projects, Runs, Reviews, Agents, Settings rota/ekran iskeletleri; tema, keyboard, loading/error/empty durumları.
- **Test senaryoları:** UI component tests, klavye erişimi, yavaş motor ve boş kurulum.
- **Ölçülebilir kabul:** Temel her ekran data yokken anlaşılır; API kopunca yanıltıcı başarı göstermez.
- **Tamamlanma kanıtı:** UI smoke videosu/screenshot seti + e2e raporu.

### B3-02 — Kalıcı supervisor, event store ve reconnect [P0]

**Amaç:** Pencere/renderer yaşam döngüsünü worker ve kampanya yaşam döngüsünden ayırmak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: engine/winproc, workflows/checkpoint.py ve mevcut ayrık kampanya/proje denetleyicileri. Önerilen: supervisor service + event journal.
**Rakip dayanağı:** OrchestratorInc daemon/session host; Herdr core.
**Ana kabul koşulu:** Uygulama kapanıp açıldığında görev sonucu ve durum korunur, iki worker yanlışlıkla başlatılmaz.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-02 — UI'dan bağımsız supervisor ve event protocol [P0]`):
>
> - Mimari: çalışma yaşam döngüsü ve `session/run_id`, `event_id`, `operation_id`; dayanıklı olay günlüğü ve resume; abonelik için Unix/Windows platforma uygun yerel bağlantı.
> - Test: pencere kapatma, GUI crash, beklenmeyen yeniden başlatma, event replay, duplicate commands.
> - Kabul: kapanan/çöken GUI worker öldürmez; yeniden açıldığında gerçek durumu, art arda eksiksiz olayları görür; hiçbir işlem iki kez uygulanmaz.

#### B3-02.01 — Mevcut ayrık kontrolcüleri denetleyen supervisor

- [x] **Tamamlandı** — `engine/supervisor.py` + `tests/engine/test_supervisor.py`; `KANIT_LOG.md` §B3-02.01 (bağlama ve gerçek 2-GUI testi sonraki görevlerde).
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-01.03`.
- **Mimari / değişecek alan:** Yeni supervisor yalnız orchestration ownership; mevcut campaign-run/project-resume kodu tek gerçek kaynak kalır.
- **Uygulama adımları:** OS kullanıcı oturumu altında tek örnek, PID/lock doğrulama, crash recovery, process-tree ownership ve güvenli stop protokolü.
- **Test senaryoları:** İki GUI, supervisor crash, stale PID, orphan süreç, elevated session ve çakışan start.
- **Ölçülebilir kabul:** Tek sahiplik; iki pencereden aynı run iki kez başlamaz; UI kapatma active run’ı öldürmez.
- **Tamamlanma kanıtı:** Process tree test + lock/race raporu.

#### B3-02.02 — Sürümlü event journal ve outbox

- [x] **Tamamlandı** — `engine/journal.py` + `tests/engine/test_journal.py`; `KANIT_LOG.md` §B3-02.02 (kısmi saklama yok, riskler orada).
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-02.01`.
- **Mimari / değişecek alan:** Önerilen append-only local journal: seq, operation_id, run_id, event_type, payload version; mevcut imzalı evidence farklı kaynaktır.
- **Uygulama adımları:** Persist/replay, zaman damgası, retention, redaction, atomik yazım, crash-safety; veri migrasyonu tanımla.
- **Test senaryoları:** 10000 event, truncate/corrupt tail, disk full, sır maskeleme ve aynı event tekrarı.
- **Ölçülebilir kabul:** Sıralama monotonic; tekrar okuma idempotent; corrupt journal privileged state’i açmaz.
- **Tamamlanma kanıtı:** Journal fixture + replay test logu.

#### B3-02.03 — Olay akışı ve reconnect cursor

- [x] **Tamamlandı** — `events.snapshot/since` + `desktop/src/events.ts` + testler; `KANIT_LOG.md` §B3-02.03 (üretici bağlama ve video sonraki görevlerde).
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-02.02`, `B3-01.04`.
- **Mimari / değişecek alan:** Desktop IPC subscription, seq cursor/replay ve snapshot handshake.
- **Uygulama adımları:** Snapshot + missed events üzerinden UI canlandır; backpressure, bounded buffer ve stream gap tespiti uygula.
- **Test senaryoları:** GUI 3 kez crash/reopen, 10k burst, network-free IPC interruption, slow consumer, duplicate event.
- **Ölçülebilir kabul:** Reopen sonrası doğru final state; event gap ya tamamlanır ya açık uyarı gösterilir.
- **Tamamlanma kanıtı:** Disconnect/reconnect e2e videosu ve state hash.

#### B3-02.04 — Resume ve shutdown davranışı

- [x] **Tamamlandı** — kapatma ayrımı + `runs.active` + modal + fault-injection testleri; `KANIT_LOG.md` §B3-02.04 (modal uçtan uca B3-09.01'e devredildi).
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-02.03`.
- **Mimari / değişecek alan:** Mevcut RES-01/02 checkpoint / project-resume mekanizmasına bağlanır; yeni güvenliksiz resume yok.
- **Uygulama adımları:** Pencere kapatma, uygulamadan çıkış, motoru durdurma komutlarını ayır; running işte modal ve güvenli shutdown seçeneği.
- **Test senaryoları:** Kill supervisor mid-write, checkpoint tampering, stale patch, cleanup ve retry idempotency.
- **Ölçülebilir kabul:** Geçersiz checkpoint otomatik devam etmez; ikinci apply veya çift ücretlendirme oluşmaz.
- **Tamamlanma kanıtı:** Fault-injection ve recovery kanıtları.

### B3-03 — Gerçek Chat/Terminal agent oturumları [P0]

**Amaç:** Rakiplerdeki kadar etkileşimli ama sandbox kurallarını ihlal etmeyen agent oturumu sağlamak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: engine/worker_policy.py, engine/appcontainer.py, engine/winproc, CLI worker adapters. Önerilen: engine/sessions/*, PTY broker.
**Rakip dayanağı:** OrchestratorInc native Chat/TUI; AgentSpace split terminal; Kitchen tmux.
**Ana kabul koşulu:** Her CLI’nin gerçek yetenek matrisi görülür; desteklenmeyen mod yok; terminal/konuşma worker sınırını aşmaz.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-03 — Agent Session: native Chat / PTY ve capability matrix [P0]`):
>
> - Mimari: `AgentAdapter` arayüzü: supports_chat/pty/interrupt/approval/usage/resume; desteklenmeyen yeteneği gizle; Windows ConPTY veya kontrollü process broker; renderer'dan doğrudan shell açma yok.
> - Test: farklı CLI, unicode ve büyük stdout, yavaş terminal, kill/reconnect, interactive auth, prompt-injection güvenlik sınırı.
> - Kabul: Claude/Codex en az bir desteklenen modda gerçek canlı ses/çıktı değil **metin/terminal** aktarır; sahte Chat modları yok; motorun sandbox'ı atlatılmaz.

#### B3-03.01 — Destek/yetenek matrisi ve protokol tasarımı

- [x] **Tamamlandı** — `engine/agent_adapters.py`, `tests/engine/test_agent_adapters.py` (9 OK), `docs/AGENT_ADAPTER_MATRIX.md`; kanıt `docs/evidence/KANIT_LOG.md` B3-03.01.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-00.02`, `B3-01.02`.
- **Mimari / değişecek alan:** AgentAdapter interface: chat, pty, send_input, interrupt, resume, usage, auth, approval; her araca yetenek bayrakları.
- **Uygulama adımları:** Codex/Claude/Cursor/OpenCode/Antigravity/custom yetenekleri kaynaktan ve canlı testten ayır; unsupported durumları açık tut.
- **Test senaryoları:** Yanlış mode advertise, binary missing, sürüm düşürme, auth gerekiyor.
- **Ölçülebilir kabul:** Tüm desteklenen CLI için doğrulanmış en az bir I/O modu veya explicit unsupported kaydı.
- **Tamamlanma kanıtı:** Adapter matrix ve doğrulama koşuları.

#### B3-03.02 — ConPTY ve sandbox uyumluluğu feasibility gate

- [x] **Tamamlandı** — karar `docs/adr/ADR-024-conpty-appcontainer-go-no-go.md` (koşullu GO), kapı testleri `tests/engine/test_conpty_feasibility.py` (10 OK); kanıt `docs/evidence/KANIT_LOG.md` B3-03.02.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-03.01`, `B3-02.01`.
- **Mimari / değişecek alan:** Controlled PTY broker, existing AppContainer launcher; Windows API ve izin modeli test edilecek.
- **Uygulama adımları:** PTY/ConPTY + AppContainer altında gerçek interactive süreç mümkün mü? Gerekirse yalnızca supported headless transcript moduna daraltma kararı ver; asla unsandboxed fallback uygulama.
- **Test senaryoları:** Dış dosyaya erişim, ağ default deny, child process, terminal escape, resize, control-C, 1MB çıktı.
- **Ölçülebilir kabul:** Destek verilen modda AppContainer negatif testleri geçer; geçmiyorsa mod Beta.3 dışı ve kapalı.
- **Tamamlanma kanıtı:** Windows test run + ADR go/no-go kararı.

#### B3-03.03 — Yapılandırılmış Chat oturum adaptörü

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-03.01`, `B3-02.02`.
- **Mimari / değişecek alan:** İlgili CLI JSONL/events üzerinden normalize message stream; supported only.
- **Uygulama adımları:** Ajan mesajı, tool call, progress, ask-user, usage ve status olaylarını typed protocol’e map et; gizli alanları ayıkla.
- **Test senaryoları:** Tool call içi prompt injection, incomplete stream, JSONL error, 429, untrusted rich text.
- **Ölçülebilir kabul:** En az 1 doğrulanmış CLI ile gerçek oturum transcript; modelin desteklemediği ask-user olayı sahte üretilmez.
- **Tamamlanma kanıtı:** Gerçek live session fixture + adapter unit/e2e raporu.

#### B3-03.04 — Etkileşim ve müdahale komutları

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-03.02`, `B3-03.03`, `B3-00.03`.
- **Mimari / değişecek alan:** session controller yetki sınıfları: send input / interrupt / cancel / approve ayrı.
- **Uygulama adımları:** İzinli kullanıcı mesajı, durdur, sınırlı yeniden dene; oturum permission prompt’larının mevcut onay otoritesini bypass etmesini engelle.
- **Test senaryoları:** Model çıktısından terminal input injection, spoofed approval, stale session id, unauthorized resume.
- **Ölçülebilir kabul:** Komutların her biri açık izin kontrolünden geçer; hiçbir tool output privileged approval’a dönüşmez.
- **Tamamlanma kanıtı:** Intervention auth negatives ve açık UI durumları.

#### B3-03.05 — Terminal render, split pane ve oturum regresyonu

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-03.02`, `B3-03.04`.
- **Mimari / değişecek alan:** Proposed desktop/terminal; PTY broker supported only, renderer receives escaped/filtered stream.
- **Uygulama adımları:** Terminal scrollback, resize, paste safety, 2–4 pane opt-in; model/araç destek durumunu göster.
- **Test senaryoları:** Unicode/Türkçe, ANSI escape, 10MB log, paste multiline, Windows CRLF, yeniden bağlanma.
- **Ölçülebilir kabul:** 10k satırda UI etkileşimli; unsupported terminal pane başlatılmaz; süreç broker dışında shell açamaz.
- **Tamamlanma kanıtı:** Terminal e2e kayıtları ve perf ölçümü.

### B3-04 — Project Board ve görsel DAG planlama [P0]

**Amaç:** Var olan plan/coordinate/project-start motorunu görsel kullanıma açmak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: workflows/coordinator.py, workflows/roles.py, engine/runner.py, interfaces/rpp.py. Önerilen: desktop/projects, desktop/dag.
**Rakip dayanağı:** Vi3ecode flow; Agency Orchestrator workflow studio; Orca.
**Ana kabul koşulu:** Geçersiz planla sıfır worker; explicit start ve anlaşılır bağımlılık/çakışma incelemesi.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-04 — Project/Task board + DAG preview [P0]`):
>
> - Mimari: mevcut `plan/coordinate/project-start` verisini tüketen renderer; her DAG düzenlemesinde motor yeniden validasyon.
> - Test: cycle, ownership collision, invalid budget, cancel/resume, stale proposal.
> - Kabul: geçersiz planla sıfır worker, doğru conflict mesajları, explicit Start.

#### B3-04.01 — Project/Run read model + filtreler

- [x] **Tamamlandı** — `engine/read_model.py`, IPC `runs.list`/`projects.list`, `tests/engine/test_read_model.py` (9 OK); kanıt `docs/evidence/KANIT_LOG.md` B3-04.01.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-01.03`, `B3-02.02`.
- **Mimari / değişecek alan:** Motor veri şemasından read-only DTO: project, run, stage, agent, status, dependency, evidence reference.
- **Uygulama adımları:** Liste, arama, sorting, stale/failed/in-progress ayrımı, güvenilir sıralama.
- **Test senaryoları:** 10k run pagination, corrupt metadata, duplicate run, incorrect status.
- **Ölçülebilir kabul:** CLI ile UI aynı run status’u gösterir; durumu yalnız UI hafızasından türetmez.
- **Tamamlanma kanıtı:** DTO mapping tests ve API contract snapshot.

#### B3-04.02 — DAG görselleştirme ve kapsam çatışması

- [x] **Tamamlandı** — `workflows/dag_view.py`, IPC `plan.view`, `desktop/src/dag.ts`; `tests/workflows/test_dag_view.py` (10 OK) + `desktop/tests/dag.test.ts` (3 OK); kanıt `docs/evidence/KANIT_LOG.md` B3-04.02.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-04.01`.
- **Mimari / değişecek alan:** Existing normalized DAG result; proposed visual renderer graph library ancak engine canonical.
- **Uygulama adımları:** Node/edge, bağımlılık, ownership/forbidden, bütçe, bekleyen insan eylemi ve hata açıklaması.
- **Test senaryoları:** Cycle, bilinmeyen edge, ancestry collision, 100 node/200 edge, keyboard navigation.
- **Ölçülebilir kabul:** Plan okunabilir, hatanın düğüm ve kenarı vurgulanır; render farklı engine kararı üretmez.
- **Tamamlanma kanıtı:** Visual snapshot + DAG fixtures.

#### B3-04.03 — Taslak düzenleme ve sunucu tarafı revalidate

- [x] **Tamamlandı** — `workflows/plan_draft.py`, IPC `plan.create/edit/start`; `tests/workflows/test_plan_draft.py` (10 OK); kanıt `docs/evidence/KANIT_LOG.md` B3-04.03.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-04.02`, `B3-00.03`.
- **Mimari / değişecek alan:** Plan revision/hash ve mevcut coordinator validator; UI local yalnız preview.
- **Uygulama adımları:** Düğüm adı/atama/bağımlılık/kapsam düzenlemelerini değişiklik taslağı olarak gönder; motor tüm DAG’ı yeniden doğrulasın.
- **Test senaryoları:** Concurrent edit, stale revision, id collision, conflict, rol unavailable, speculative plan.
- **Ölçülebilir kabul:** Invalid edit kaydedilip worker başlatmaz; start yalnız validated revision ve ayrı operator action.
- **Tamamlanma kanıtı:** Plan mutation negative test + no-worker assertion.

#### B3-04.04 — Başlat, durdur, devam ettir ve durum açıklaması

- [x] **Tamamlandı** — `workflows/project_control.py`, IPC `project.status/cancel/resume`; `tests/workflows/test_project_control.py` (9 OK) + gerçek ayrık süpervizörle e2e günlüğü; kanıt `docs/evidence/KANIT_LOG.md` B3-04.04.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-04.03`, `B3-02.04`.
- **Mimari / değişecek alan:** Mevcut project-start/cancel/project-resume çağrılarını tipli IPC ile bağla.
- **Uygulama adımları:** Bu eylemler için net confirmation, scheduling queue, retryable/fatal reason ve audit event göster.
- **Test senaryoları:** Aynı start iki kez, cancel race, resumed stale checkpoint, role missing.
- **Ölçülebilir kabul:** Exactly-once state transition; geçersiz ve yetkisiz çalıştırma sıfır worker.
- **Tamamlanma kanıtı:** E2E create-plan-start-cancel-resume logu.

### B3-05 — Review, diff ve insan onayı merkezi [P0]

**Amaç:** Kanıtı anlaşılır gösterirken apply yetkisinin insan dışında devredilememesini korumak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: engine/integration.py, check/apply mekanizması, imzalı evidence; proposed desktop/review, human approval native service.
**Rakip dayanağı:** Orca diff; OrchestratorInc PR/CI; Respected signed evidence.
**Ana kabul koşulu:** Tamper/stale durumunda sıfır apply; operator-approved geçerli patch yalnız bir kez uygulanır.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-05 — Review, evidence & human approval UX [P0]`):
>
> - Mimari: tek doğruluk kaynağı `evidence.view`/`check`; GUI kimliği onay için ayrı yetkili native user-presence service, MCP'nin onay yetkisi yok. `apply` anında yeniden doğrula.
> - Test: stale/tampered evidence, replay onay, renderer script injection, yanlış run/patch, ikinci apply.
> - Kabul: hatalı kanıtta sıfır apply, gerçek kullanıcı tarafından yapılan tek yetkili apply, doğrulama zaman damgası görsel.

#### B3-05.01 — Evidence/Diff/PR-CI read model

- [x] **Tamamlandı** — `engine/review_model.py`, IPC `review.view`; `tests/engine/test_review_model.py` (13 OK) + tam paket 774 test; kanıt `docs/evidence/KANIT_LOG.md` B3-05.01.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-04.01`, `B3-01.02`.
- **Mimari / değişecek alan:** Mevcut evidence/check API tek kaynak, diff read-only ve path-scope sanitization.
- **Uygulama adımları:** Patch hash, repo fingerprint, tests, reviewer, changed files, policy, PR/CI durumu göster; false green yok.
- **Test senaryoları:** Tampered evidence, symlink, binary patch, large diff, missing CI, secret redaction.
- **Ölçülebilir kabul:** Kanıtsız veya invalid koşu “onaylanabilir” değil; bütün uyarılar doğru görüntülenir.
- **Tamamlanma kanıtı:** Evidence fixtures + UI snapshots.

#### B3-05.02 — Gerçek kullanıcı onayı için native authority

- [x] **Tamamlandı** — `engine/approval.py`, IPC `approval.*`, `_ipc --human`, Rust `approval.rs` + `request_apply`; `tests/engine/test_approval.py` (14 OK), `cargo test --lib` (15 OK); kanıt `docs/evidence/KANIT_LOG.md` B3-05.02.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-00.03`, `B3-01.02`.
- **Mimari / değişecek alan:** IPC’den ayrı native/user-presence path; renderer ve worker’ın kendi kendine tetikleyemeyeceği sınır.
- **Uygulama adımları:** İnsanın onayladığı run/patch/repo fingerprint için kısa ömürlü, tek kullanımlık karar tokenı ve onay diyalog süreci tasarla.
- **Test senaryoları:** MCP/worker onay taklidi, renderer injection, replay, wrong window, stale patch, race.
- **Ölçülebilir kabul:** Privileged apply yalnız doğrulanmış operatör eyleminde; denial path side effect=0.
- **Tamamlanma kanıtı:** Security red-team tests + approval trace.

#### B3-05.03 — TOCTOU-safe apply ve işlem sonucu

- [x] **Tamamlandı** — `runner.apply_task` sertleştirildi (O_EXCL talep, tam parmak izi yeniden kontrolü, kapsam/symlink taraması, apply-failed.json, geri alma açıklaması); `tests/engine/test_apply_hardening.py` (7 OK) + mutasyon 3/3; kanıt `docs/evidence/KANIT_LOG.md` B3-05.03.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-05.01`, `B3-05.02`.
- **Mimari / değişecek alan:** Existing apply_task check+git apply --check; native authorization check binding.
- **Uygulama adımları:** Apply sırasında yeniden check, tam repo/patch digest matching, duplicate apply guard, success/failure artifact ve undo açıklaması.
- **Test senaryoları:** Between-check/apply repo edit, second click, cancel race, stale/forbidden patch.
- **Ölçülebilir kabul:** Double apply sıfır; failed apply gerçek repo değiştirmez; commit/auto merge yok.
- **Tamamlanma kanıtı:** Mutation test + repo before/after hash.

#### B3-05.04 — Onay merkezi uçtan uca saldırı testi

- [x] **Tamamlandı** — `tests/engine/test_approval_attacks.py` (19 senaryo; kaynak ve paketli exe 19/19, commit 9bf5935), rapor `docs/evidence/b3-05-04-attack-run.md`, kanıt `docs/evidence/KANIT_LOG.md` B3-05.04. **Not:** bağımlılık B3-03.04 henüz yapılmadı; oturum-müdahale saldırıları o kartta kanıtlanacak.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-05.03`, `B3-03.04`.
- **Mimari / değişecek alan:** Desktop integration test harness, packaged executable ile normal kullanıcı güvenlik senaryoları.
- **Uygulama adımları:** 12+ attacker fixtures, verified path success, approval cancellation ve logta secret kontrolü.
- **Test senaryoları:** Yanlış run_id, patch sha, operation id, renderer compromise, symlink and illegal file.
- **Ölçülebilir kabul:** Tanımlı saldırı kümesinde 100% reject ve 1 geçerli happy path; crash bile onayı auto-yapmaz.
- **Tamamlanma kanıtı:** Commit SHA’ya bağlı güvenlik koşusu raporu.

### B3-06 — Canlı aktivite, dosya, terminal ve önizleme inspector [P1]

**Amaç:** Çalışma devam ederken ajanı, dosyaları ve testleri güvenilir biçimde izletebilmek.
**Mevcut / önerilen kod eşlemesi:** Mevcut: runner/MAF/campaign event izleri ve evidence; önerilen: desktop/inspector ve bounded event API.
**Rakip dayanağı:** Open Space live diff; AgentSpace inspector; Mission Control.
**Ana kabul koşulu:** Yük altında UI yanıt verir; kimlik bilgileri aktarılmaz; kopma bilinçli gösterilir.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-06 — Live activity + terminal/file/diff/browser inspector [P1]`):
>
> - Mimari: seçilen run'a ait typed events ve izinli artifacts; bounded pagination/scrollback, gizli veri redaksiyonu.
> - Test: 10k+ olay, yavaş ekran, event kopması, gizli bilgi sızması, yerel tarayıcı erişim politikası.
> - Kabul: UI takılmaz, loglar sınırlı; tekrar bağlanınca atlanan olay yok ya da açık eksik veri uyarısı.

#### B3-06.01 — Event timeline ve arama/filtre

- [x] **Tamamlandı** — `engine/activity.py`, `Journal.scan`, IPC `activity.list`; `tests/engine/test_activity.py` (10 OK, 10k olay); kanıt `docs/evidence/KANIT_LOG.md` B3-06.01.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-02.03`, `B3-04.01`.
- **Mimari / değişecek alan:** Sürümlü type event’lerden activity read model.
- **Uygulama adımları:** Queued/running/review/fail/approval timeline; göreve, ajana, olaya göre filtre; operation correlation.
- **Test senaryoları:** 10k+ olay, out-of-order event, unknown type, slow UI, retention.
- **Ölçülebilir kabul:** UI 10k olayı sayfalayabilir; bilinmeyen event verisi kaybolmadan güvenli gösterilir.
- **Tamamlanma kanıtı:** Timeline perf ve snapshot.

#### B3-06.02 — Dosya diff/çıktı/kanıt inspector

- [x] **Tamamlandı** — `engine/artifact_view.py`, IPC `artifact.list/read`; `tests/engine/test_artifact_view.py` (11 OK, 1 atlandı: symlink ayrıcalığı yok; junction denendi) + mutasyon; kanıt `docs/evidence/KANIT_LOG.md` B3-06.02.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-06.01`, `B3-05.01`.
- **Mimari / değişecek alan:** Artifacts whitelist & path sandbox; bounded stream; command output redaction.
- **Uygulama adımları:** Büyük logları parça parça yükle, changed file navigation, test summary, full evidence link.
- **Test senaryoları:** Huge binary, symlink, path traversal, ANSI injection, token leakage.
- **Ölçülebilir kabul:** UI dış path okuyamaz; büyük çıktıda takılmaz; audit, artifact digest saklanır.
- **Tamamlanma kanıtı:** Read-only file access security test.

#### B3-06.03 — Güvenli local preview (isteğe bağlı)

- [x] **Tamamlandı** — `preview.rs`, `preview_open`, `preview_enabled` (varsayılan kapalı) + `preview_ports`, AppManifest + ad ad izin; `cargo test` 23+1 (gerçek yetkilerle ACL testi), gerçek WebView2 + düşman sayfa koşusu `docs/evidence/b3-06-03-preview-e2e.md`, tam paket 909 OK; kanıt `docs/evidence/KANIT_LOG.md` B3-06.03. **Not:** sayfanın kendi ağ istekleri engellenmez (arayüzde yazılı).
- **Öncelik / boyut:** P1 / L
- **Bağımlılıklar:** `B3-06.02`.
- **Mimari / değişecek alan:** Localhost preview policy / isolated webview; varsayılan kapalı; test kodundan gelen HTML güvensiz kabul edilir.
- **Uygulama adımları:** Preview port allowlist, timeout ve origins; harici sitelere cookie/secret taşınmasın; Beta.3 gecikirse feature flag off.
- **Test senaryoları:** XSS/CSRF, localhost port hijack, port scanning, injected JS, network egress.
- **Ölçülebilir kabul:** Önizleme privileged IPC çağırmaz; izin verilen proje dışına erişemez; kapalıyken görev akışı etkilenmez.
- **Tamamlanma kanıtı:** Browser security test + demo.

### B3-07 — Ajan profilleri ve uyumluluk kontrolleri [P1]

**Amaç:** Kurulu coding CLI’ları doğru tanımak ve her aracın gerçek yeteneğini dürüst göstermek.
**Mevcut / önerilen kod eşlemesi:** Mevcut: workflows/roles.py, track_record.py, CLI adapters; önerilen: engine/agent_registry.py ve desktop/agents.
**Rakip dayanağı:** OrchestratorInc per-agent capabilities; AgentSpace direct engines vs providers.
**Ana kabul koşulu:** Unknown/unsupported asla supported olarak sunulmaz; open user assignment preserved.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-07 — Agent profiles & local prereq check [P1]`):
>
> - Mimari: `tool/profile/role` ayrı tutulur, sürüm/CLI/auth/capability statüsü: configured/installed/verified/unavailable.
> - Test: binary kayıp, auth yok, sürüm değişimi, capability yanlış bildirim.
> - Kabul: unsupported özellik yanlışlıkla aktif görünmez; değişiklik açık kullanıcı eylemiyle.

#### B3-07.01 — CLI binary/sürüm/auth keşfi

- [x] **Tamamlandı** — `engine/agent_discovery.py`, IPC `agents.discover`, gerçek defter `docs/evidence/agent-compat-ledger-2026-11-06.txt`; `tests/engine/test_agent_discovery.py` (18 OK) + mutasyon 5/5; kanıt `docs/evidence/KANIT_LOG.md` B3-07.01.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-01.03`.
- **Mimari / değişecek alan:** Salt-okunur CLI probe ve allowlisted executable discovery.
- **Uygulama adımları:** Codex/Claude/Cursor/OpenCode/Antigravity/custom için installed/configured/verified/unavailable durumlarını ayır.
- **Test senaryoları:** Binary moved, renamed executable, unexpected stdout, timeout, auth-required, enterprise policy.
- **Ölçülebilir kabul:** Probe kapalı ağda çalışabilir; gizli anahtar okunmaz; her status gerekçeli.
- **Tamamlanma kanıtı:** Probe fixtures / real CLI compatibility ledger.

#### B3-07.02 — Role, tool, profile ayrımı ve düzenleme

- [x] **Tamamlandı** — `workflows/role_editor.py`, IPC `roles.view/plan_edit` (yazmaz, fark + aday ayar); `tests/workflows/test_role_editor.py` (16 OK) + mutasyon 6/6; kanıt `docs/evidence/KANIT_LOG.md` B3-07.02.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-07.01`, `B3-00.03`.
- **Mimari / değişecek alan:** Existing role resolver; UI profile editor; transparent explicit/default/auto precedence.
- **Uygulama adımları:** Atama profili editörü, havuz tercihi, fallback görünürlüğü ve risk uyarısı.
- **Test senaryoları:** Role conflict, unavailable, stale version, invalid fallback, implicit override.
- **Ölçülebilir kabul:** Kullanıcı açık seçimini hiçbir öneri sessizce değiştirmez; her seçim kaynağı görünür.
- **Tamamlanma kanıtı:** Role config diff + unit tests.

#### B3-07.03 — Canlı yetenek/uyumluluk matrisi

- [x] **Tamamlandı** — `engine/capability_matrix.py`, IPC `capabilities.matrix`, artefakt `docs/evidence/capability-matrix-2026-11-06.md`; `tests/engine/test_capability_matrix.py` (9 OK) + mutasyon 4/4; kanıt `docs/evidence/KANIT_LOG.md` B3-07.03.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-07.02`, `B3-03.01`.
- **Mimari / değişecek alan:** Per-tool/agent per-version capability descriptors, verified timestamp.
- **Uygulama adımları:** Terminal/chat/interactive input/usage/model switch/resume için verified/unverified/unsupported göster.
- **Test senaryoları:** False capability, out-of-date tool, unavailable login, offline.
- **Ölçülebilir kabul:** Unsupported mode düğmesi etkin olmaz; doğrulanmamış özellik uyarılı.
- **Tamamlanma kanıtı:** Capability matrix release artifact.

### B3-08 — Yerel, salt-okunur MCP/Skill envanteri [P1]

**Amaç:** Başka bir uygulama, mağaza veya hesap olmadan mevcut yetenekleri keşfetmek.
**Mevcut / önerilen kod eşlemesi:** Mevcut: engine/capability_manifest.py yalnız trust gate; önerilen: engine/capabilities/discovery.py, desktop/capabilities.
**Rakip dayanağı:** AgentSpace skill visibility; Task Observer patterns.
**Ana kabul koşulu:** Keşif sırasında sıfır MCP yürütmesi; çevrimdışı keşif; configured ≠ verified.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-08 — Minimal native capability inventory [P1]`):
>
> - Mimari: read-only detector; desteklenen istemcilerin ayar dosyalarını izinli konumlarda okur, skill ve MCP manifestolarını normalize eder; `EXT-01` güvenlik kararından ayrı katman.
> - Test: bozuk JSON, simb. bağlantı, şüpheli path, kurulu ama çalışmayan MCP; internet yok.
> - Kabul: başka uygulama/hesap olmadan envanter; discovery sırasında hiçbir MCP çalıştırılmaz.

#### B3-08.01 — Desteklenen istemcilerin config yolu matrisi

- [x] **Tamamlandı** — `engine/capabilities/paths.py`, IPC `capabilities.scan`; `tests/engine/test_capability_paths.py` (14 OK; gerçek junction, yan etkisiz) + mutasyon 7/7; kanıt `docs/evidence/KANIT_LOG.md` B3-08.01.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-00.02`, `B3-07.01`.
- **Mimari / değişecek alan:** Read-only discovery policy ve güvenli canonical path.
- **Uygulama adımları:** Desteklenen agent config konumlarını, user/project scopes ve schema parser’larını listele; dosya dışına taşan linkleri reddet.
- **Test senaryoları:** Symlink/reparse point, malformed JSON/TOML/YAML, Unicode paths, read permission errors.
- **Ölçülebilir kabul:** Hiçbir tarama dosya değiştirmez veya MCP çalıştırmaz; açık hata sınıfı döner.
- **Tamamlanma kanıtı:** Scan coverage + no-side-effect fixture.

#### B3-08.02 — Manifest normalizasyonu ve durum ayrımı

- [x] **Tamamlandı** — `engine/capabilities/normalize.py`, IPC `capabilities.inventory`; `tests/engine/test_capability_normalize.py` (12 OK) + mutasyon 9/9; kanıt `docs/evidence/KANIT_LOG.md` B3-08.02.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-08.01`.
- **Mimari / değişecek alan:** Normalized capability DTO: kind=skill/mcp, id, origin, scope, agent, declared permissions, digest, status.
- **Uygulama adımları:** Configured/installed/available/verified/trusted durumlarını ayrı tut; hash güven kararı için capability_manifest’e bağla.
- **Test senaryoları:** Duplicate names, no binary, fake manifest, malicious tool description, secrets in config.
- **Ölçülebilir kabul:** Yanlış trust yükselmesi sıfır; metadata kaynak/yer belirtir; raw secrets outputa çıkmaz.
- **Tamamlanma kanıtı:** Normalizer unit test + sample configs.

#### B3-08.03 — Envanter ekranı ve offline e2e

- [x] **Tamamlandı** — `desktop/src/inventory.ts`, `Capabilities.tsx`, Tauri `capability_inventory`; `npm run check` 21 OK, `cargo test --lib` 16 OK, tarayıcıda gerçek veriyle ekran; `tests/engine/offline_inventory_proof.py` (kaynak: ağ/süreç kancası + negatif kontrol, paketli exe izleme); kanıt `docs/evidence/KANIT_LOG.md` B3-08.03.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-08.02`, `B3-01.04`.
- **Mimari / değişecek alan:** UI read-only inventory; installation, activation and execution bu sürümde yok.
- **Uygulama adımları:** Filtre, uyum durumu, izinler, proje/global ayrımı, yenileme ve false-positive feedback.
- **Test senaryoları:** Ağ yokken çalıştırma, Hub yok, malformed configs, MCP untrusted.
- **Ölçülebilir kabul:** Temiz ve fixture makinesinde envanter çevrimdışı çalışır; hiçbir yetenek otomatik aktifleşmez.
- **Tamamlanma kanıtı:** Offline capture + process monitor doğrulaması.

### B3-09 — Kurulum, güncelleme, veri geçişi ve beta release [P0]

**Amaç:** Bağımsız uygulamayı mevcut kurulum/veri sözleşmesine zarar vermeden dağıtmak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: packaging/build_dist.py, packaging/windows/orchestrator_setup.iss, release fixtures, conformance; önerilen desktop bundle.
**Rakip dayanağı:** Herdr/OrchestratorInc lifecycle; mevcut Respected update contract.
**Ana kabul koşulu:** Mevcut kullanıcı verisi korunur; aktif görev update sırasında bozulmaz; imzalı yayın politikası uygulanır.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B3-09 — Packaging/migration/release [P0]`):
>
> - Mimari: app + engine version handshake, atomik updater, kullanıcı verisini koruyan migration, Windows Authenticode yayın politikası.
> - Test: beta.1 ve beta.2 dataları; rollback, kurulum sırasında kilitli çalışma, sürüm uyumsuzluğu.
> - Kabul: eski çalışma kanıtları okunur, bozulmuş migrate atlanmaz, Hub yokken tam ürün çalışır.

#### B3-09.01 — Desktop+engine paket sözleşmesi

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-01.03`, `B3-00.04`.
- **Mimari / değişecek alan:** Mevcut PyInstaller engine distribution.json ve Inno installer, desktop bundle; strateji ADR ile seçilir.
- **Uygulama adımları:** İki exe’nin konumu, servis başlangıcı, hash doğrulama, dosya sahipliği ve repair davranışı belirlensin; iki ayrı uygulama yükleniyormuş gibi davranma.
- **Test senaryoları:** Clean user install, package tampering, missing runtime, repair.
- **Ölçülebilir kabul:** Hub olmadan tek kurulumdan GUI+engine çalışır; dağıtım hash zinciri tutarlı.
- **Tamamlanma kanıtı:** Packaging smoke + manifest audit.

#### B3-09.02 — Beta.1/2 veri fixture ve migration

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-09.01`, `B3-02.02`.
- **Mimari / değişecek alan:** settings schema STEPS ve gerçek releases fixture; append-only event store migrate.
- **Uygulama adımları:** Kullanıcı verisi ve eski evidence/approval/checkpoint tutulur; migration atomik ve backup/restore korumalı.
- **Test senaryoları:** beta.1 + beta.2 gerçek fixtures, kesilen migration, read-only dir, bozuk json.
- **Ölçülebilir kabul:** Yükseltme kayıpsız; migration başarısızsa önceki iyi sürüm geri yüklenir.
- **Tamamlanma kanıtı:** Migration report + before/after digests.

#### B3-09.03 — Aktif görev varken update/rollback tasarımı

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-09.02`, `B3-02.04`.
- **Mimari / değişecek alan:** Supervisor version handshake; packaging repair/update rollback; active work handles.
- **Uygulama adımları:** Update sırasında yeni görev kabulünü güvenli durdur, çalışanları bitir veya kontrollü devret, dosya replace yarışını engelle.
- **Test senaryoları:** Update mid-run, power loss, rollback, version mismatch, partial install.
- **Ölçülebilir kabul:** Veri bütünlüğü bozulmaz; çalışan görevin durumu belirsizse otomatik apply yok.
- **Tamamlanma kanıtı:** Fault-injected install/update artifact.

#### B3-09.04 — Beta.3 release gate ve imza politikası

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-05.04`, `B3-04.04`, `B3-03.04`, `B3-09.03`.
- **Mimari / değişecek alan:** Zorunlu Windows normal-user security runner; code signing; release trace.
- **Uygulama adımları:** CI tüm P0 doğrulamalarını ve mevcut Beta.2 FIX kapılarını toplasın, SHA ilişkilendirsin; Authenticode sertifikası yoksa “signed release” iddiası yapılamaz.
- **Test senaryoları:** Unprivileged AppContainer matrix, GUI apply negatives, installer/hash, offline no-other-app, telemetry opt-out.
- **Ölçülebilir kabul:** P0 gate fail veya güvenlik testi skip olursa sürüm release-ready değil; imza yoksa ayrı açık blocker.
- **Tamamlanma kanıtı:** Signed release manifest + commit SHA + CI artifact.

---

## 8. Beta.4 — Intelligent Agent Workspace

### 8.0 Sürüm hedefi ve kapsamı

**Beta.4 — Intelligent Agent Workspace:** Risk-bazlı akıllı routing ve iş planı önerileri, izinli görev içi steer/handoff, proje ajan profilleri, yerel MCP/skill uyumluluk ve öneri motoru, ölçülebilir maliyet/kalite, bağlam bütçesi, isteğe bağlı uygulama içi yerel ses girişi, ekran görüntüsü ekleme/önizleme; uzaktan cihaz ve bulut workeri ayrı güvenlik projesi olarak ancak çekirdek doğrulandıktan sonra.

| Sürüm | Teması | Mutlaka çıkacaklar | Koşullu / sonraya |
|---|---|---|---|
| **Beta.4** | Intelligent Agent Workspace | Riskli routing, kalıcı takım/handoff, yerel skill/MCP intelligence, ölçülebilir kalite | Ses, screenshot, context optimization P1; remote/mobile B4-09 P2 **release blocker değil** |

**Ana iş indeksi — Beta.4**

| Ana iş | Öncelik | Alt görev | Hedef |
|---|---|---:|---|
| `B4-01` | P0 | 4 | Smart Agent Routing 2.0 |
| `B4-02` | P0 | 4 | Kalıcı ajan profilleri, ekipler ve kontrollü handoff |
| `B4-03` | P0 | 5 | Hub’sız yerel MCP/Skill uyumluluk ve öneri motoru |
| `B4-04` | P0 | 3 | Gerçek token, kota, maliyet ve kalite analitiği |
| `B4-05` | P1 | 3 | Context Budget Manager ve seçici bağlam |
| `B4-06` | P1 | 3 | Yerel uygulama içi sesli görev taslağı |
| `B4-07` | P1 | 3 | Screenshot-to-task ve görsel bağlam |
| `B4-08` | P1 | 3 | Adaptif recovery ve circuit breaker |
| `B4-09` | P2 | 3 | Remote/mobile kontrol — koşullu araştırma (stretch) |

### 8.1 Ayrıntılı görevler — Beta.4

### B4-01 — Smart Agent Routing 2.0 [P0]

**Amaç:** Risk, zorluk, gerçek maliyet ve geçmiş başarı verisiyle gerekçeli ajan seçmek.
**Mevcut / önerilen kod eşlemesi:** Mevcut: workflows/roles.py, track_record.py, engine/pricing.py, tests/evals/; önerilen TaskClassifier ve RoutingPolicy.
**Rakip dayanağı:** Oh My ClaudeCode model roles; AgentSpace multi-CLI; Mission Control cost.
**Ana kabul koşulu:** Açık kullanıcı seçimi korunur; unknown maliyet uydurulmaz; shadow vs active deney ayrı.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-01 — Task intelligence & risk-based routing [P0]`):
>
> - Mimari: ayrı `TaskClassifier` ve `RoutingPolicy`: görev kapsamı/risk/zorluk, izinli adaylar, gerçek track record, model fiyatı, bütçe; `shadow` ardından opt-in active.
> - Test: düşük veri, yanlış fiyat, açık kullanıcı ataması, yüksek risk, offline, model sürümü değişmesi.
> - Kabul: gerekçeli öneri; `unknown` güven/ücret doğru; kullanıcı açık ataması değişmez; benchmark'ta maliyet/başarı kıyaslanır.

#### B4-01.01 — Görev sınıflandırma ve risk şeması

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-04.03`.
- **Mimari / değişecek alan:** Yeni TaskClassifier deterministic features: changed scope, verification risk, deps, expected file types.
- **Uygulama adımları:** Risk seviyeleri (low/med/high/unknown) ve açıklama nedenleri; prompttan izin türetmeme.
- **Test senaryoları:** Adversarial task text, secret-like input, stale repo inventory, missing metadata.
- **Ölçülebilir kabul:** Her risk skoru açıklanabilir; bilinmiyorsa unknown; risk yetki genişletmez.
- **Tamamlanma kanıtı:** Classifier fixtures + decision table.

#### B4-01.02 — Politika temelli aday seçimi ve bütçe

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-01.01`, `B3-07.03`.
- **Mimari / değişecek alan:** Mevcut role resolver üstünde RoutingPolicy; verified capabilities + track_record + pricing katalog.
- **Uygulama adımları:** Explicit/default/auto önceliğini koru; quota, tool availability, model version, price currency, usage unknown dikkate al.
- **Test senaryoları:** No candidates, 0/3 samples, inaccurate price, unsupported tool, manual lock.
- **Ölçülebilir kabul:** Kullanıcı explicit seçimi sıfır silent override; her dışlanan aday nedenli; unknown $0 olmaz.
- **Tamamlanma kanıtı:** Routing decision fixtures + audit examples.

#### B4-01.03 — Shadow mode ve geri alınabilir active routing

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-01.02`, `B4-04.01`.
- **Mimari / değişecek alan:** Routing suggestion, actual execution’dan ayrı yazılır; opt-in ve kill switch.
- **Uygulama adımları:** Önce öneri üret; benchmark eşdeğeri ve kullanıcı onayı sonrası active aç; öneri farklarını kaydet.
- **Test senaryoları:** A/B same fixture, fallback consent, toggled off during task, quota failures.
- **Ölçülebilir kabul:** Shadow varsayılan; active seçim policy ihlali yapmaz; rollback tek ayarla.
- **Tamamlanma kanıtı:** A/B run artifacts + config test.

#### B4-01.04 — Gerçek ajan benchmark ile routing güveni

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-01.03`, `B4-04.02`.
- **Mimari / değişecek alan:** Beta.2 gerçek agent benchmark’ından task/model/version/commit metadata; synthetic eval ayrı tutulur.
- **Uygulama adımları:** En az 10 görev x 3 tekrar x direct/orchestrated veri setiyle göreli başarı/maliyet aralığı hesapla; ölçüm çıkmazsa launch gate fail.
- **Test senaryoları:** Confounded run, insufficient sample, same-model version drift, safety regression.
- **Ölçülebilir kabul:** Gerçek benchmark metrikleri raporlu; belirsizlik açıklanmış; başarı/regression gate geçer.
- **Tamamlanma kanıtı:** Reproducible eval manifest and report.

### B4-02 — Kalıcı ajan profilleri, ekipler ve kontrollü handoff [P0]

**Amaç:** Rol kimliği ve gerçek session’ı ayırıp deterministik görev devri oluşturmak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: workflows/roles.py, coordinator DAG, MAF, checkpoints; önerilen team profiles + handoff event.
**Rakip dayanağı:** AgentSpace persistent workers; Vi3ecode shared team; Munder Difflin mailbox.
**Ana kabul koşulu:** Role/agent/session ayrı; max-hop ve scope kontrolleri; sonsuz devir yok.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-02 — Agent teams & deterministic handoffs [P0]`):
>
> - Mimari: kalıcı team profile (`lead`, `builder`, `reviewer`, `qa`, `designer`) üstünde mevcut role mapping; görev handoff event'leri ile kapasite/sahiplik/loop sınırları.
> - Test: 2 rol aynı dosya, handoff cycle, kaynak yok, interrupted worker, retry ceiling.
> - Kabul: bağımsız işler çakışmadan devredilir; onaysız execute/apply yok; max-hop aşılınca durur.

#### B4-02.01 — Agent/team/profile sürümlü veri sözleşmesi

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-07.02`, `B3-09.02`.
- **Mimari / değişecek alan:** Team profile schema: role, tool, profile, default budget, allowed capability, display identity; no raw secrets.
- **Uygulama adımları:** Kalıcı lead, implementer, reviewer, QA, designer profilleri ve adlandırma; mevcut rol motoruna map et.
- **Test senaryoları:** Schema v1 migration, invalid ID, privilege escalation in profile, deleted CLI.
- **Ölçülebilir kabul:** Profil ile session farklı ID; kullanıcı profili değiştirdiğinde eski run kanıtı değişmez.
- **Tamamlanma kanıtı:** Schema fixtures + migration tests.

#### B4-02.02 — Handoff message envelope ve mailbox

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-02.01`, `B3-02.02`.
- **Mimari / değişecek alan:** Handoff event: from/to, scope, evidence refs, retry budget, reason, next_action; source bounded/signed.
- **Uygulama adımları:** Ham transcript yerine doğrulanmış ve küçük task state aktar; mesaj event store’a ekle.
- **Test senaryoları:** Spoofed role, forged evidence, huge message, prompt injection, missing destinatary.
- **Ölçülebilir kabul:** Ajan mesajı yetki değil veri sayılır; konu dışı dosya/komut izinleri genişlemez.
- **Tamamlanma kanıtı:** Handoff security suite + sample timeline.

#### B4-02.03 — Loop-limited takım koordinasyonu

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-02.02`, `B4-08.01`.
- **Mimari / değişecek alan:** Mevcut DAG/MAF ve scheduler üzerinden hop/round budgets, ownership conflict check.
- **Uygulama adımları:** Devretme için max_hops, retry budget ve reviewer-implementer bağımsızlığı zorunlu; görev bekleme durumunu göster.
- **Test senaryoları:** A↔B cycle, duplicate handoff, conflicting files, reviewer same worker.
- **Ölçülebilir kabul:** Budget aşıldığında running workers durur/escalate; double apply olmaz.
- **Tamamlanma kanıtı:** Cycle negative suite and simulated jobs.

#### B4-02.04 — Takım görünümü ve görev geçmişi

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B4-02.03`, `B3-06.01`.
- **Mimari / değişecek alan:** Desktop team overview and shared thread as projection of events, not second DB.
- **Uygulama adımları:** Rol geçişleri, kimin neden devraldığı ve yeniden atama açıklamaları.
- **Test senaryoları:** Two team view, actor renamed, missing event, stale UI.
- **Ölçülebilir kabul:** Her handoff tek operation timeline’a bağlıdır; loglar sır içermeden anlaşılır.
- **Tamamlanma kanıtı:** UI screenshots + history consistency test.

### B4-03 — Hub’sız yerel MCP/Skill uyumluluk ve öneri motoru [P0]

**Amaç:** Yetenekleri göreve göre analiz etmek; keşif ve öneriyi çalıştırma yetkisinden ayırmak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: engine/capability_manifest.py, B3-08 inventory; önerilen engine/capabilities/{compatibility,recommendation,activation}.
**Rakip dayanağı:** Mission Control capability view; Task Observer; Serena/Context Mode optional.
**Ana kabul koşulu:** Offline temel işlev, otomatik kurulum/etkinleştirme sıfır, proje scope ve trust gate zorunlu.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-03 — MCP/skill compatibility + recommendation [P0]`):
>
> - Mimari: local `CapabilityDiscovery` / `CompatibilityResolver` / `Recommender` / `PermissionInspector` / `ActivationPlan`; analiz öncelikle deterministic, LLM opsiyonel. `EXT-01` trust + digest zaten yürütme kapısı.
> - Test: offline, sahte manifest, path traversal, prompt injection, projeler arası yetki sızıntısı, unsupported agent, missing executable.
> - Kabul: uygun ve uygun olmayan açıklanır; AI yalnız **önerir**, otomatik kurmaz/etkinleştirmez; kullanıcı onayı ve sandbox uygulanır.

#### B4-03.01 — CompatibilityResolver & agent support registry

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B3-08.02`, `B3-07.03`.
- **Mimari / değişecek alan:** Deterministic capability ontology + agent/version support matrix.
- **Uygulama adımları:** Skill biçimi, MCP transport, agent config, tool permission, project/global scope, binary/version kontrol et; unknown ayrımı.
- **Test senaryoları:** Unsupported client, wrong transport, missing binary, invalid version, duplicate.
- **Ölçülebilir kabul:** Önerilerde compatible/incompatible/unknown ayrımı ve her kararın nedeni bulunur.
- **Tamamlanma kanıtı:** Compatibility fixture matrix.

#### B4-03.02 — Görev bazlı öneri ve gerekçe

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-03.01`, `B4-01.01`.
- **Mimari / değişecek alan:** Rule-based recommender; LLM candidate ranking sadece opsiyonel ve asla auth kaynağı değil.
- **Uygulama adımları:** Task taxonomy, suggested skills, already installed/unavailable, risk/permissions, explainability; no external catalog.
- **Test senaryoları:** Prompt injection in skill desc, irrelevant suggestion, all unknown, offline, malicious metadata.
- **Ölçülebilir kabul:** Yerel offline fixture setinde açıklanabilir öneri; öneri hiçbir dosyayı değiştirmez.
- **Tamamlanma kanıtı:** Golden recommendation fixtures; 0 side effects audit.

#### B4-03.03 — PermissionInspector ve risk kartları

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-03.01`, `B3-00.02`.
- **Mimari / değişecek alan:** Önerilen/kurulu yeteneklerin declared permissions ile gerçek policy gate bağları.
- **Uygulama adımları:** File/network/secrets/command/roots risklerini raporla; trusted digest ile environment availability ayrı tut.
- **Test senaryoları:** False trusted flag, malicious manifest, path traversal, external URL, too broad permissions.
- **Ölçülebilir kabul:** Eksik manifest = çalıştırma red; görüntüde trust unknown, uyumluluk başka ölçüdür.
- **Tamamlanma kanıtı:** Manifest adversarial tests + risk fixtures.

#### B4-03.04 — Onaylı ActivationPlan ve execution gate

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-03.02`, `B4-03.03`, `B3-05.02`.
- **Mimari / değişecek alan:** Plan = desired changes diff + scopes + hashes; current capability_manifest fail-closed gate remains final.
- **Uygulama adımları:** Kullanıcı onayını yerel app’te al; proje bazlı ayrı aktivasyon; external MCP sadece policy sınırında çalışır; güvenli uninstall/rollback planı.
- **Test senaryoları:** Cross-project bleed, stale manifest, tamper hash, repeated activation, workspace outside.
- **Ölçülebilir kabul:** Onaysız yazma/yürütme=0; yanlış project capabilities aktive olmaz; sandbox bypass yok.
- **Tamamlanma kanıtı:** Activation audit + side-effect tests.

#### B4-03.05 — Capability recommender UI + user feedback

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B4-03.04`, `B3-08.03`.
- **Mimari / değişecek alan:** Desktop capability recommendations read from engine; no mandatory cloud/marketplace.
- **Uygulama adımları:** Yetenek önerisi, neden, bulunabilirlik, izin ve reddetme; öneriyi görmezden gel seçeneği.
- **Test senaryoları:** Offline UI, untrusted skill, missing MCP runtime, hidden secrets.
- **Ölçülebilir kabul:** Başka uygulama yokken tam akış; UI click olmadan herhangi aktivasyon yok.
- **Tamamlanma kanıtı:** UI e2e recordings and offline inventory trace.

### B4-04 — Gerçek token, kota, maliyet ve kalite analitiği [P0]

**Amaç:** Her sağlayıcıya özgü ölçümü, unknown belirsizliğini ve kalite KPI’larını aynı rapora almak.
**Mevcut / önerilen kod eşlemesi:** Mevcut: engine/pricing.py, track_record.py, tests/evals/report.py; önerilen usage ledger.
**Rakip dayanağı:** Mission Control usage; AgentSpace quota; MXterm.
**Ana kabul koşulu:** Unknown 0 değildir; fiyat ve usage kaynağı açıktır; kabul edilen görev başına maliyet hesaplanır.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-04 — Real usage, quota, cost & quality analytics [P1]`):
>
> - Mimari: `UsageEvent` input/output/cache/unknown; provider-specific adapter, accepted-task cost, model version, benchmark confidence, ledger; abonelik = API masrafı gibi gösterilmez.
> - Test: kullanım raporlamayan agent, kısmi usage, sürüm değişimi, currency, token double count, privacy.
> - Kabul: bilinmeyen değer 0'a dönüşmez, basit veri setiyle maliyet yeniden hesaplanır; ağ gerektirmez.
>
> `[ÇELİŞKİ C1]` Analiz raporu bu işi **P1** yazar; uygulama planı **P0** yazar. Uygulama planı esas alınmıştır (Ek C, C1).

#### B4-04.01 — UsageEvent şeması ve provider adapters

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-02.02`, `B3-07.03`.
- **Mimari / değişecek alan:** Usage event input/output/cache read/write, usage status, CLI/session source, model version, timestamp.
- **Uygulama adımları:** Gözlemlenebilen kullanım alanlarını kaydet, token çakışmalarını normalize et, abonelik sabit ücreti API maliyeti sanma.
- **Test senaryoları:** Missing usage, duplicate event, different cache semantics, model upgrade, mock usage.
- **Ölçülebilir kabul:** Unknown null korunur; her değer provenance taşır; double-count=0 fixtures.
- **Tamamlanma kanıtı:** Typed schema + provider fixtures.

#### B4-04.02 — Cost/quality ledger ve benchmark korelasyonu

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / L
- **Bağımlılıklar:** `B4-04.01`.
- **Mimari / değişecek alan:** Price catalog snapshot + accepted task KPI + actual eval provenance.
- **Uygulama adımları:** Per run cost/elapsed/fix rounds/accepted/worker violations; versioned compare; same task class filters.
- **Test senaryoları:** Currency mismatch, stale price, missing sample, negative token, usage correction.
- **Ölçülebilir kabul:** Rapor eksik veri varsa hesaplanamadı der; aynı fixture ile deterministik tekrar hesaplanır.
- **Tamamlanma kanıtı:** Ledger golden fixtures + diff report.

#### B4-04.03 — Bütçe/başarı dashboard ve uyarılar

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B4-04.02`, `B3-06.01`.
- **Mimari / değişecek alan:** Privacy-first local read models; optional quota event & warning.
- **Uygulama adımları:** Kullanıcıya run, ajan, proje bazında bütçe/başarı grafikleri; actual vs estimate vs unknown ayrı.
- **Test senaryoları:** Large dataset, zero sample, 429 burst, disabled data collection.
- **Ölçülebilir kabul:** Görünen % yalnız anlamlı payda ile hesaplanır; unknown false green yok.
- **Tamamlanma kanıtı:** UI/e2e reports and sample analytical dataset.

### B4-05 — Context Budget Manager ve seçici bağlam [P1]

**Amaç:** Daha az gereksiz token ve dosya okuma; başarı ve güvenliği düşürmeden ölçmek.
**Mevcut / önerilen kod eşlemesi:** Mevcut: worker prompts, MAF feedback, checkpoints; önerilen selective context/manifest ve bounded tool outputs.
**Rakip dayanağı:** Graft, Serena, Context Mode ve Headroom yaklaşımı.
**Ana kabul koşulu:** Token düşüşü gerçek ve görev bazlı ölçülür; ayrıştırıcı kritik kanıtı atamaz.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-05 — Context budget / adaptive task preparation [P1]`):
>
> - Mimari: repo-context manifest, selective symbol/search summary, bounded log evidence, LLM prompt sınırı; yüksek riskli bağlamı yanlış özetleme yerine kaynak referansı koru.
> - Test: aynı benchmark görevlerinde token ve başarı, stale context invalidation, büyük repo.
> - Kabul: token tasarrufu başarı/güvenlik gerilemesi olmadan ölçülür; ölçülmemiş tasarruf iddiası yok.

#### B4-05.01 — Repo context map ve içerik invalidation

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-04.01`.
- **Mimari / değişecek alan:** Read-only project symbol/file inventory via local tools, scoped to allowed paths.
- **Uygulama adımları:** Önemli fonksiyonlar, kod sahipliği, repo commit ve cache key; symlink ve yasak dizinleri filtrele.
- **Test senaryoları:** Large repo, symlink loop, stale HEAD, generated dirs, non-UTF8.
- **Ölçülebilir kabul:** Cache Git drift olunca yenilenir; gizli veya yasak dosyalar indekse girmez.
- **Tamamlanma kanıtı:** Corpus fixtures + invalidation tests.

#### B4-05.02 — Bounded context preparation ve evidence refs

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / L
- **Bağımlılıklar:** `B4-05.01`, `B4-02.02`.
- **Mimari / değişecek alan:** Prompt builder summarizes/ranks only allowlisted excerpts; original evidence digest refs kept.
- **Uygulama adımları:** İlgisiz log ve dosyaları buda, ilgili test hatasını ve security warnings’i tam koru, hint source span ver.
- **Test senaryoları:** Malicious repo instructions, truncated critical error, faulty summary, overbudget input.
- **Ölçülebilir kabul:** Kritik güvenlik/ret sinyalleri asla budanmaz; her özet kaynak hash’e bağlıdır.
- **Tamamlanma kanıtı:** Prompt golden fixtures + source trace.

#### B4-05.03 — A/B token/başarı deneyleri

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / L
- **Bağımlılıklar:** `B4-05.02`, `B4-04.02`, `B4-01.04`.
- **Mimari / değişecek alan:** Direct baseline, new context prep via same agent/version/fixture/environment.
- **Uygulama adımları:** Önce gölge mod; ölçülebilen token, accepted task, security violations ve latency farklarını raporla.
- **Test senaryoları:** Insufficient samples, token unavailable, drift, benchmark contamination.
- **Ölçülebilir kabul:** Kazanım iddiası yalnız metriklerle; güvenlik regresyonunda devre dışı.
- **Tamamlanma kanıtı:** A/B benchmark manifest and report.

### B4-06 — Yerel uygulama içi sesli görev taslağı [P1]

**Amaç:** AgentVoice’tan ilhamla yalnız Orchestrator alanında, rızaya dayalı STT.
**Mevcut / önerilen kod eşlemesi:** Önerilen desktop/voice ve yerel STT adapter; execution IPC tamamen ayrı.
**Rakip dayanağı:** AgentVoice, AgentSpace voice.
**Ana kabul koşulu:** Offline, kullanıcı kontrolü, kayıt varsayılan yok; ses yürütme/onay emri değildir.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-06 — Local in-app voice task drafting [P1]`):
>
> - Mimari: uygulamaya özel opt-in bas-konuş, yerel STT, silinebilir metin, mikrofon erişim izni, proje sözlüğü; ses sadece taslak.
> - Test: mikrofon yok, offline, Türkçe teknik terimler, izin iptali, sesin ağ dışına çıkmaması.
> - Kabul: sesli taslak çalıştırmayı/onayı otomatik tetiklemez; kayıt varsayılan saklanmaz.

#### B4-06.01 — Mikrofon izinleri ve offline STT spike

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-01.04`.
- **Mimari / değişecek alan:** OS mic permission, opt-in push-to-talk, local model adapter choice via feasibility test.
- **Uygulama adımları:** Turkish/English technical vocabulary, resource consumption, download provenance; cloud fallback default kapalı.
- **Test senaryoları:** Offline disconnected, no device, mic denied, revoked permission, CPU/memory pressure.
- **Ölçülebilir kabul:** İzin yoksa kayıt yok; ses internete gönderilmez; STT performansı ölçülür.
- **Tamamlanma kanıtı:** Local capture privacy trace + go/no-go ADR.

#### B4-06.02 — Editable task draft, vocabulary ve safety

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B4-06.01`, `B3-04.03`.
- **Mimari / değişecek alan:** Voice-to-text only into task draft; UI edit/review step mandatory.
- **Uygulama adımları:** Proje sözlüğüyle CLI/library names, task parser confidence, yanlış kelime vurgusu.
- **Test senaryoları:** Adversarial voice phrasing, high-stakes approve phrase, speech-to-text hallucination.
- **Ölçülebilir kabul:** Metin onaylanmadan plan/start/apply yok; mikrofon kapalıyken ses işlenmez.
- **Tamamlanma kanıtı:** Voice-to-draft e2e with Turkish examples.

#### B4-06.03 — Ses gizlilik/performans release kapısı

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B4-06.02`.
- **Mimari / değişecek alan:** Mic indicators, ephemeral buffers, deletion controls, no audio in evidence/checkpoint.
- **Uygulama adımları:** Verbose logging disabled; opt-out, process termination, accessibility alternative, fallback typed entry.
- **Test senaryoları:** Audio residue, network capture, event leak, crash while recording.
- **Ölçülebilir kabul:** Raw audio varsayılan diske yazılmaz; test setinde ağ çıkışı=0; kapatma anlık.
- **Tamamlanma kanıtı:** Privacy negative suite + resource benchmark.

### B4-07 — Screenshot-to-task ve görsel bağlam [P1]

**Amaç:** AgentShot’ın tümünü kopyalamadan, görev öncesi kullanıcı seçimiyle görsel bağlam sağlamak.
**Mevcut / önerilen kod eşlemesi:** Önerilen desktop/capture + bounded task attachment service; existing task schema extension migration.
**Rakip dayanağı:** AgentShot, Open Space, Orca browser preview.
**Ana kabul koşulu:** Kullanıcı istemedikçe ekran yakalama ve modelle paylaşım yok; dosya açıkça incelenir.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-07 — Screenshot-to-task [P1]`):
>
> - Mimari: kullanıcı seçimi + izin kontrollü capture, PII/secret önizleme, seçilen görselin izinli görev payload'ına eklenmesi; mevcut screenshot uygulaması olmak şart değil.
> - Test: çoklu ekran, devasa görsel, gizli pencere, silme/iptal, medya redaksiyonu.
> - Kabul: kullanıcı açıkça yüklemeden kanıt/LLM'e görsel aktarılmaz.

#### B4-07.01 — Kullanıcı denetimli ekran yakalama

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B3-01.04`, `B3-00.02`.
- **Mimari / değişecek alan:** OS screenshot chooser, window/region selection, opt-in only, local temp storage.
- **Uygulama adımları:** Kırpma, işlem iptali, çoklu ekran DPI ve permission checks.
- **Test senaryoları:** Screen capture denied, multi-monitor, protected windows, mid-capture cancel.
- **Ölçülebilir kabul:** Background capture=0; izin yoksa görüntü oluşturulmaz; geçici dosya temizlenir.
- **Tamamlanma kanıtı:** Capture e2e and OS permission log.

#### B4-07.02 — Görsel önizleme, redaksiyon ve task attachment

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / L
- **Bağımlılıklar:** `B4-07.01`, `B3-04.03`.
- **Mimari / değişecek alan:** Attachment envelope MIME, digest, byte limit, allowed visibility; task payload opt-in.
- **Uygulama adımları:** Kullanıcının işaretleme/redaction/preview yapması ve seçilen görüntünün yalnız o göreve eklenmesi.
- **Test senaryoları:** Hidden secrets, huge image, EXIF, malicious formats, wrong task ID, path traversal.
- **Ölçülebilir kabul:** Eklemeden önce preview zorunlu; görüntü yanlış run veya üçüncü tarafta görünmez.
- **Tamamlanma kanıtı:** Attachment policy tests + sample masked image.

#### B4-07.03 — Model transfer ve retention onayı

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B4-07.02`, `B4-03.04`.
- **Mimari / değişecek alan:** Trusted provider/worker permission and network boundaries; separate data-sharing decision.
- **Uygulama adımları:** External model için provider disclosure; temp artifact TTL; evidence/loglarda opt-in; purge path.
- **Test senaryoları:** User deny, offline, revoke mid-transfer, screenshot in log, stale task.
- **Ölçülebilir kabul:** Açık paylaşım onayı olmadan dışarı görsel=0; silme/iptal testlerinden geçer.
- **Tamamlanma kanıtı:** Network audit + retention test.

### B4-08 — Adaptif recovery ve circuit breaker [P1]

**Amaç:** Mevcut sabit retry/MAF durdurma kurallarını daha iyi sınıflandırılmış ve sınırlı otomasyonla genişletmek.
**Mevcut / önerilen kod eşlemesi:** Mevcut: failure_class, retry_policy, MAF finite state, RES-02, AppContainer; önerilen decision policy ve operator escalation.
**Rakip dayanağı:** Munder Difflin circuit breaker; Oh My ClaudeCode rate-limit wait.
**Ana kabul koşulu:** Sınırsız döngü yok; güvenlik reddi otomatik retry edilmez; kaynak/bütçe sınırları korunur.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-08 — Adaptive recovery / unattended bounded work [P1]`):
>
> - Mimari: belirli retry/failure sınıfları, circuit breaker (steer → pause → stop), budget ve max-hop, operator escalation.
> - Test: tekrarlanan hata, 429, auth expiry, bad network, idempotency, recursive task attempts.
> - Kabul: sınırsız loop/sınırsız maliyet yok, politika aşımı fail-closed.

#### B4-08.01 — Recovery decision table ve maksimum kaynak sınırı

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P0 / M
- **Bağımlılıklar:** `B3-02.04`, `B4-04.01`.
- **Mimari / değişecek alan:** Existing failure_class enum with deterministic recovery policy: retry/pause/stop/operator.
- **Uygulama adımları:** Quota/auth/security/test/stale/infra/timeout için ayrı eylemler, max retry/handoff/time/cost.
- **Test senaryoları:** Infinite loop simulated, 429, auth, unsafe cmd, repeated tests.
- **Ölçülebilir kabul:** Policy_denied/auth/user approval auto-resume=0; tüm döngüler bounded.
- **Tamamlanma kanıtı:** Policy fixtures + max-limit simulations.

#### B4-08.02 — Operator escalation ve explainable recovery

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / M
- **Bağımlılıklar:** `B4-08.01`, `B3-05.01`.
- **Mimari / değişecek alan:** Event timeline and explicit operator action; recovery never automatic apply.
- **Uygulama adımları:** Problem nedeni, önerilen adım, kalan bütçe, controlled action buttons, resume checkpoint revalidation.
- **Test senaryoları:** Stale approval, quota resumed without auth, crash loop, wrong run escalation.
- **Ölçülebilir kabul:** Operator’a gerekçe gösterilir; onay gerektiren değişiklik yetki olmadan çalışmaz.
- **Tamamlanma kanıtı:** Recovery UX + attack tests.

#### B4-08.03 — Fault-injection ve regresyon release suite

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P1 / L
- **Bağımlılıklar:** `B4-08.02`, `B4-02.03`.
- **Mimari / değişecek alan:** Kill/failure injection harness, commit linked release evidence.
- **Uygulama adımları:** Network unavailable, half-written state, process tree residue, duplicate action, circuit breaker open/close.
- **Test senaryoları:** 20+ fault fixtures; reset after repair; worker sandbox check.
- **Ölçülebilir kabul:** Sınırsız retry=0; double apply=0; worker cleanup; no bypass.
- **Tamamlanma kanıtı:** CI fault matrix + event timeline.

### B4-09 — Remote/mobile kontrol — koşullu araştırma (stretch) [P2]

**Amaç:** Ancak yerel masaüstü ve güvenlik kanıtları sağlamlaşınca uzaktan salt-okunur deneyimi değerlendirmek.
**Mevcut / önerilen kod eşlemesi:** Şimdilik önerilen: docs/adr/remote-architecture.md; varsayılan remote socket yok.
**Rakip dayanağı:** OrchestratorInc mobile/cloud; AgentSpace mobile; Herdr SSH.
**Ana kabul koşulu:** Beta.4 yayın engeli değil; uzaktan kontrol kapalı ve opt-in.

> **Rakip analizi raporundaki görev önerisi** (kaynaktan aktarıldı; özgün başlık: `B4-09 — Remote/mobile — ayrı karara bağlı stretch [P2]`):
>
> - Yalnız güvenli yerel ürün doğrulandıktan sonra; ayrı tehdit modeli, pairing, kimlik, iptal edilebilir cihaz erişimi, read-only başlangıç.
> - Test: LAN/WAN erişim, replay, cihaz çalınması, host offline, background engine, yetki ayrımı.
> - Kabul: varsayılan kapalı; dış ağda doğrulanmış kimlik ve taşıma şifrelemesi olmadan işlem yok.

#### B4-09.01 — Tehdit modeli, kullanıcı araştırması ve Go/No-Go

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P2 / M
- **Bağımlılıklar:** `B3-09.04`, `B4-04.03`.
- **Mimari / değişecek alan:** Bambaşka kimlik/cihaz/pairing ve transport sınırı; local IPC dışına privilege taşıma.
- **Uygulama adımları:** Read-only remote MVP için kullanım senaryosu, saldırı yüzeyi, alternatif SSH üzerinden read-only gateway.
- **Test senaryoları:** Network spoof, stolen phone, replay, offline host, revocation.
- **Ölçülebilir kabul:** Threat model + maliyet/yarar raporu olmadan remote kod geliştirme başlamaz.
- **Tamamlanma kanıtı:** Research decision ADR.

#### B4-09.02 — Opt-in read-only remote observer prototipi

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P2 / L
- **Bağımlılıklar:** `B4-09.01`.
- **Mimari / değişecek alan:** Izole gateway, authenticated pairing, TLS, short-lived tokens; default no network listener.
- **Uygulama adımları:** Status/events/evidence summary dışında mutation yok; cihaz iptali ve session timeout.
- **Test senaryoları:** Unauthorized mutation attempts, reconnect, LAN/WAN, revoked device.
- **Ölçülebilir kabul:** Remote disabled by default; read-only endpoint ile hiçbir privileged mutation yapılmaz.
- **Tamamlanma kanıtı:** Remote pen-test report + prototype.

#### B4-09.03 — Genişleme karar kapısı: kontrol ve mobil

- [ ] **Tamamlandı** — testler ve commit kanıtı eklenince işaretlenecek.
- **Öncelik / boyut:** P2 / M
- **Bağımlılıklar:** `B4-09.02`.
- **Mimari / değişecek alan:** Ayrı sürüm önerisi; input/approval uzaktan aktarılması için farklı authority/consent tasarımı gerekir.
- **Uygulama adımları:** Uygulama içi mobile approvals ve task start ancak yeni modelin kanıtı sonra; performans/kullanıcı talebi.
- **Test senaryoları:** Stolen/replayed approval, source drift, old device, WAN outage.
- **Ölçülebilir kabul:** Beta.4 release için zorunlu değil; risk kabulü/pen-test olmadan uzaktan apply yok.
- **Tamamlanma kanıtı:** Go/no-go ADR + backlog.

---

## 9. Beta.5 — Competitive Parity I: Local Developer Experience

### 9.0 Sürüm hedefi ve kapsamı

**Sürüm vaadi:** Respected'ın yerel masaüstü kullanımında OrchestratorInc / AgentSpace / Orca / Mission Control'ün en çok kullanılan günlük iş akışlarını kapsaması. Beta.3/Beta.4'te zaten yapılmış parçalar yeniden yazılmaz; eksik kullanıcı akışları ve entegrasyonlar tamamlanır.

- **Beta.5:** Yerel geliştirici deneyiminde rakiplerle doğrulanabilir işlevsel kapsama.

**Ana iş indeksi — Beta.5**

| Ana iş | Başlık | Öncelik | Alt görev |
|---|---|---|---:|
| `B5-00` | Rekabet yetenek matrisi ve scope freeze | P0 | 2 |
| `B5-01` | Agent Chat/Terminal parity | P0 | 2 |
| `B5-02` | Workspace, Git ve arama deneyimi | P0 | 2 |
| `B5-03` | Gelişmiş Git/PR/CI/review döngüsü | P0 | 2 |
| `B5-04` | Browser preview ve tasarım geri bildirimi | P0 | 2 |
| `B5-05` | Kaydedilmiş iş akışları ve otomasyon | P1 | 2 |
| `B5-06` | Operatör inbox ve birleşik zaman çizgisi | P0 | 2 |
| `B5-07` | Ekip kimliği ve görev devri UX | P1 | 2 |
| `B5-08` | Hesap, kota ve provider sağlık durumu | P1 | 2 |
| `B5-09` | Desktop polish, erişilebilirlik ve yerelleştirme | P1 | 2 |
| `B5-10` | Yerel profil aktarımı ve audit | P1 | 2 |
| `B5-11` | Beta.5 canlı kabul ve release gate | P0 | 2 |

**Mimari bağlantı:** B3-01/02/03/04/05/06/07/09, B4-02/04/07/08 üzerinden UI, event store, session controller ve evidence şemasını genişlet. Browser özellikleri **VerificationProvider** arayüzünden gelir, Playwright yeniden yazılmaz.

**Beta.5 genel senaryoları:** (1) iki agent paralel ayrı worktree, (2) biri clarification ister → masaüstü inbox → aynı session, (3) PR CI fail → hatayı doğru agent düzeltir, (4) GUI kapanır/açılır ve iş sürer, (5) browser test video/trace ile review ekranına bağlanır.

### 9.1 Ayrıntılı görevler — Beta.5

### B5-00 — Rekabet yetenek matrisi ve scope freeze [P0]

**Referans:** OrchestratorInc, AgentSpace, Orca, diğerleri.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Rakip yetenek matrisi, kaynak sürümü, 5 temel kullanıcı yolculuğu ve P0/P1/P2 kapsam dondurma
> - **En az kabul kriteri (strateji):** Her P0 satır kaynakla ve testle eşleşir; açık durumlar saklanmaz

#### B5-00.01 — Kaynak destekli capability envanteri

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B4-GATE-01`, `B4-GATE-03`.
- **Mimari / modül sınırı:** docs/COMPETITOR_CAPABILITY_MATRIX.md (yeni); kaynak ve sürüm kayıtları.
- **Uygulama:** 135 araçlık rehberden ilgili 16 orkestrasyon ve 6 IDE/terminal adayını incele; tekil kullanıcı ihtiyacına karşılık gelen CAP-ID üret; shipped/beta/planned/paid ayrımı yap.
- **Test senaryoları:** Aynı yeteneğin farklı rakiplerde tekrarını ve kaynak tarihi olmayan satırı tespit eden matris linter; kaynağı belirsiz satıra unknown.
- **Ölçülebilir kabul:** Kapsama alınan her P0/P1 CAP-ID için kaynak URL, kontrol tarihi, kabul testi ve durum vardır; belirsiz hiçbir satır verified değildir.
- **Tamamlanma kanıtı:** Tarihli matrix diff + kaynak listesi + linter sonucu.

#### B5-00.02 — Kullanıcı yolculuğu ve ölçümlü kapsam dondurma

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-00.01`.
- **Mimari / modül sınırı:** docs/COMPETITOR_CAPABILITY_MATRIX.md; tests/e2e/ (mevcut konumu doğrula).
- **Uygulama:** Agent chat, paralel iş, CI onarım, browser review, insan onayı olmak üzere 5 ana journey tanımla; P0/P1/P2/excluded kararı, teknik maliyet ve gerekçeleri bağla.
- **Test senaryoları:** Her yolculukta clean-install başlangıç verisi; planlanan/gerçek sürüm eşleştirme ve açık P0 tespiti.
- **Ölçülebilir kabul:** 5 journey için yürütülebilir test tanımı; P0 kapsamı dondurulur, sonradan yeni rakip özelliği otomatik blocker olmaz.
- **Tamamlanma kanıtı:** Scope freeze ADR + journey fixtures + baseline raporu.

### B5-01 — Agent Chat/Terminal parity [P0]

**Referans:** OrchestratorInc, Orca, Kitchen, Open Space.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Agent session parity: native chat/terminal, resume, interactive questions, attachment, model switch (desteklenirse), search, split panes
> - **En az kabul kriteri (strateji):** En az 3 ana CLI için gerçek session-matrix; unsupported özellik açık gösterilir; reconnect veri kaybetmez

#### B5-01.01 — Gelişmiş oturum etkileşimi ve agent yetenek matrisi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B3-03.04`, `B3-07.03`.
- **Mimari / modül sınırı:** Mevcut session adapter/controller; önerilen desktop/session UX.
- **Uygulama:** İnteraktif soru/yanıt, çok satırlı giriş, cancel/interrupt, dosya ekleme ve yalnız desteklenen ajanlarda model değiştirme eylemlerini tipli sözleşmeyle ekle; bilinmeyen CLI özelliklerini kapalı tut.
- **Test senaryoları:** Gerçek Claude/Codex/OpenCode CLI sürümleriyle farklı yetenekleri dene; prompt injection, geçmiş arama, yanlış run-id ve 1 MB çıktı negatifleri.
- **Ölçülebilir kabul:** En az 3 doğrulanmış CLI sürümüyle capability matrix; unsupported eylem düğmesi yok; yanlış oturuma giriş sıfır.
- **Tamamlanma kanıtı:** Gerçek session kayıtları, version matrix ve auth saldırı raporu.

#### B5-01.02 — Split pane, geçmiş arama ve kesintisiz yeniden bağlanma

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-01.01`, `B3-02.03`.
- **Mimari / modül sınırı:** Desktop terminal panes + supervisor event journal.
- **Uygulama:** 2–4 bölmeli terminal, search, pagination ve reconnect cursor; her pane aynı worker/run kimliğini doğru gösterir; GUI yeniden açıldığında düzen geri gelir.
- **Test senaryoları:** 10k satır scrollback, Unicode/ANSI escape, slow renderer, kapat-aç ve forced GUI crash.
- **Ölçülebilir kabul:** 3 kez kapanıp açılmada mesaj kaybı/çifte komut sıfır; uzun çıktıda UI bloklanmaz; AppContainer bypass yok.
- **Tamamlanma kanıtı:** Reconnection videosu, event hash karşılaştırması ve performans ölçümü.

### B5-02 — Workspace, Git ve arama deneyimi [P0]

**Referans:** Orca, OrchestratorInc, AgentSpace.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Yerel çalışma alanı: worktree/branch/diff, çoklu sekme/split, hızlı proje ve dosya arama, dosya önizleme
> - **En az kabul kriteri (strateji):** Bir projede ≥3 çakışmasız iş; diffe gidiş en fazla 2 temel etkileşim; renderer restart sonrası state tutarlı

#### B5-02.01 — Çok sekmeli worktree ve dosya/diff gezinmesi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B3-04.01`, `B3-05.01`.
- **Mimari / modül sınırı:** Mevcut Git/worktree/read model, desktop/workspace.
- **Uygulama:** Worktree/branch/run için sekmeler; yalnız izinli dosyaların diff, binary durumu ve patch kaynağı gösterilir; kod yazdırma ve apply ayrı kalır.
- **Test senaryoları:** Üç çakışmasız görev; conflicting roots, symlink ve büyük binary diff; closing tab while running.
- **Ölçülebilir kabul:** En az 3 çalışmanın durumu karışmadan görünür; kapsam dışı dosya arayüzden okunamaz; yanlış branch ile apply olmaz.
- **Tamamlanma kanıtı:** E2E 3-run video + path scope audit.

#### B5-02.02 — Hızlı proje/dosya arama ve oturum layout kalıcılığı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-02.01`.
- **Mimari / modül sınırı:** Read-only scoped index + settings migration.
- **Uygulama:** Klavye paleti, proje ve izinli dosya araması; branch/sekme/ayrık görünüm yerleşimini sürümlü kullanıcı tercihinde sakla.
- **Test senaryoları:** Büyük repoda 100k dosya simülasyonu, stale index, symlink loop, config migration.
- **Ölçülebilir kabul:** Arama erişim kapsamından taşmaz; yeniden açılışta layout korunur; yanlış indeks sonucu açıkça yeniden taranır.
- **Tamamlanma kanıtı:** Index fixtures + UI perf trace + migration test.

### B5-03 — Gelişmiş Git/PR/CI/review döngüsü [P0]

**Referans:** OrchestratorInc, Mission Control, Orca.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Git/PR/CI/review uygulama akışı: fail → ilgili agent → düzelt → tekrar CI → inceleme
> - **En az kabul kriteri (strateji):** Kontrollü gerçek test reposunda baştan sona koşu; yanlış PR/commit CI sonucu kabul edilmez

#### B5-03.01 — CI/review başarısızlığını doğru worker’a yönlendir

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B3-05.01`, `B4-08.01`.
- **Mimari / modül sınırı:** GitHub adapter, PR/commit run mapping, MAF retry policy.
- **Uygulama:** PR/commit/branch için correlation key sakla; check-run ve reviewer yorumlarını doğrulanmış ilgili görev sahibine hata kanıtı olarak aktar.
- **Test senaryoları:** Stale PR, duplicate webhook, yanlış SHA, idempotent replay, yetkisiz yorum ve yarış durumu.
- **Ölçülebilir kabul:** Yanlış commit’e CI durumu uygulanması sıfır; tekrar olayda tek retry; secrets runner logunda görünmez.
- **Tamamlanma kanıtı:** Kontrollü uzak test reposu PR/CI logları + SHA eşleşme raporu.

#### B5-03.02 — Diff review yorumundan düzeltme ve tekrar kontrol

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-03.01`, `B3-05.03`.
- **Mimari / modül sınırı:** Review UI, typed comment events, existing check/apply gate.
- **Uygulama:** Satır/dosya yorumu; reviewer düzeltme isteğini tek görev zaman çizgisine iliştir; CI tekrar geçmeden final ready gösterme.
- **Test senaryoları:** Yorumun dosya sürümü değişmesi, binary diff, removed line, 429, failed fix, unauthorized merge.
- **Ölçülebilir kabul:** En az 1 canlı fail→comment→fix→rerun→review akışı; kendi kendine merge/apply sıfır.
- **Tamamlanma kanıtı:** E2E PR linki + check run ID + reviewer karar artefaktı.

### B5-04 — Browser preview ve tasarım geri bildirimi [P0]

**Referans:** Orca, AgentSpace, Open Space.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Browser/preview/design-review: var olan Playwright CLI/MCP/Chrome DevTools bağlantıları, screenshot, trace ve uygun durumda video
> - **En az kabul kriteri (strateji):** Basit UI akışı gerçek tarayıcıda doğrulanır, kanıt `run_id`/commit ile bağlıdır, izin dışı ağ reddedilir

#### B5-04.01 — VerificationProvider tasarımı ve Playwright adaptörü

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B3-06.03`, `B5-00.02`.
- **Mimari / modül sınırı:** Yeni versioned VerificationProvider + evidence artifact DTO; Playwright kullan, motor yazma.
- **Uygulama:** prepare/run/cancel/collect_artifacts/cleanup/capabilities/provenance sözleşmesi; Playwright CLI/Test veya MCP seçimi ADR; dış servis entegrasyonu isteğe bağlı.
- **Test senaryoları:** Başarılı/başarısız tarayıcı görevi; izinsiz ağ, gizli çerez, timeout, process leak, yanlış run SHA.
- **Ölçülebilir kabul:** Gerçek bir UI yolculuğundan screenshot+trace (mümkünse video) provenance ile çıkar; bir test sonucu doğrulanmamışsa verified denmez.
- **Tamamlanma kanıtı:** Provider fixtures + Playwright e2e + kayıt/video hash bilgisi.

#### B5-04.02 — Browser/design feedback ve güvenli preview UI

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-04.01`, `B3-05.01`.
- **Mimari / modül sınırı:** Desktop browser preview isolation; screenshot/reference mapping.
- **Uygulama:** Kullanıcı görselden eleman seçip lokatör/ekran görüntüsünü görev ekine aktarabilir; HTML içeriği ayrı güven sınırında; yetki onayı gereklidir.
- **Test senaryoları:** CSP/XSS/localhost hijack, sahte HTML aracılığıyla IPC invoke, hassas görsel paylaşımı ve click targeting.
- **Ölçülebilir kabul:** Preview kendi başına shell/approval tetiklemez; eklenen görsel kullanıcı önizlemesi olmadan dışarı gitmez.
- **Tamamlanma kanıtı:** Browser security test + kullanıcı akışı videosu.

### B5-05 — Kaydedilmiş iş akışları ve otomasyon [P1]

**Referans:** OrchestratorInc, OMC, Agency Orchestrator.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Otomasyonlar, task presets, repeatable workflows, kayıtlı komutlar ve cron/manual triggers
> - **En az kabul kriteri (strateji):** Bir otomasyon tekrarlanabilir; yazma/merge/izin yükseltme insan kontrolünü aşmaz

#### B5-05.01 — Sürüm kontrollü workflow presetleri

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B3-04.03`, `B4-02.03`.
- **Mimari / modül sınırı:** Existing DAG coordinator + versioned workflow templates.
- **Uygulama:** Yinelenen iş akışları için YAML/JSON şablon; rol, budget, path scope ve verification adımlarını parametreleştir; template import önizlemesi.
- **Test senaryoları:** Bozuk şema, tehlikeli shell alanı, cycle, stale template, cross-project permission.
- **Ölçülebilir kabul:** Örnek 3 şablon aynı test fixture üzerinde deterministik plan üretir; şablon import hiçbir görevi otomatik başlatmaz.
- **Tamamlanma kanıtı:** Template schema + 3 valid/invalid fixtures.

#### B5-05.02 — Zamanlayıcı ve olay tetikleyici için görev kabul kapısı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B5-05.01`, `B3-00.03`.
- **Mimari / modül sınırı:** Supervisor scheduling module; typed admission policy; existing approval.
- **Uygulama:** Manual/cron tetikleyici; kullanıcı önceden yetkilendirdiği read/plan işlemleri çalışır; write/merge/yetki genişletme ayrı açık onay gerektirir.
- **Test senaryoları:** Duplicate cron, DST/timezone, missed schedule, replay, disabled trigger, resource ceiling.
- **Ölçülebilir kabul:** Aynı tetikleme için tek task; kapatılmış otomasyon görev başlatmaz; insan onayı otomasyondan türetilemez.
- **Tamamlanma kanıtı:** Scheduler fixtures + e2e start/no-start logs.

### B5-06 — Operatör inbox ve birleşik zaman çizgisi [P0]

**Referans:** AgentSpace, Vi3ecode, Mission Control, Open Space.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Operatör deneyimi: Needs-you inbox, bildirimler, onay ve hata açıklaması, tek conversation timeline
> - **En az kabul kriteri (strateji):** Bekleyen 5 farklı müdahale doğru görevde görünür, yanlış run'a cevap gönderilemez

#### B5-06.01 — Needs-you inbox ve eylem ayrımı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B3-06.01`, `B3-05.02`.
- **Mimari / modül sınırı:** Event projections + read-only notifications + privileged native actions.
- **Uygulama:** Agent clarification, permission request, review-needed, expired auth, budget gibi nedenleri ayrı sınıflandır; her kaydı run/session/patch kimliğine bağla.
- **Test senaryoları:** 5 eşzamanlı bekleyen istek; yanlış run hedefleme, stale evidence, yinelenen bildirim, notification race.
- **Ölçülebilir kabul:** 5 farklı bekleyen isteğin tamamı doğru eylemle eşlenir; yanlış run yanıtı/approval sıfır.
- **Tamamlanma kanıtı:** Inbox e2e + wrong-target negatives.

#### B5-06.02 — Birleşik konuşma ve karar timeline

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-06.01`, `B4-02.04`.
- **Mimari / modül sınırı:** Append-only event journal projections, bounded search.
- **Uygulama:** Ajan mesajları, handoff, Git diff, PR/CI ve operator kararlarını tek kronolojik görünümde göster; AI mesajına asla yetkili komut statüsü verme.
- **Test senaryoları:** 10k event, bozuk sırayla olaylar, secret redaction, missing event, resume.
- **Ölçülebilir kabul:** Bir run’ın önemli eylemleri kaynak ID ve zamanla izlenebilir; belirsiz olay eksikliği açıkça işaretlenir.
- **Tamamlanma kanıtı:** Transcript/event hash test + timeline ekran kaydı.

### B5-07 — Ekip kimliği ve görev devri UX [P1]

**Referans:** AgentSpace, Vi3ecode, Munder Difflin.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Kalıcı ekip profilleri, rol şablonları, denetlenebilir ajan mailbox ve görsel sahiplik
> - **En az kabul kriteri (strateji):** 3 roller arası handoff tek görev timeline'ında; handoff döngüsü sınırlı

#### B5-07.01 — Kalıcı ekip ve rol şablonlarını görünür kıl

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B4-02.04`, `B4-01.02`.
- **Mimari / modül sınırı:** Agent profile read model + team UI; roles ayrı sessions ayrı.
- **Uygulama:** Kullanıcı takım ve rol presetleri oluşturup göreve atayabilir; worktree sahipliği ve aktif CLI ayrı görünür; basit ekip şablonları ekle.
- **Test senaryoları:** Aynı rolü iki profil, rol silinmesi, inactive CLI, yanlış reviewer assignment.
- **Ölçülebilir kabul:** Profil değişikliği mevcut imzalı run kanıtını değiştirmez; reviewer bağımsızlığı görselden bypass edilemez.
- **Tamamlanma kanıtı:** Team fixture migration + role routing test.

#### B5-07.02 — Mailbox, yorum ve handoff sınırı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B5-07.01`, `B4-02.03`.
- **Mimari / modül sınırı:** Typed handoff envelope, event journal, loop budget.
- **Uygulama:** Ajanlar arası mesajlar görev devri olayları olarak listelenir; cap, scope ve retry budget her devre yazılır; kullanıcı engelle/devir iste aksiyonları.
- **Test senaryoları:** Spoofed sender, A-B cycle, 3 rol devri, forbidden file ekleme, max_hops.
- **Ölçülebilir kabul:** Handoff sınırını aşan iş durur/escalate; en az 3 gerçek role geçişi aynı timeline’da görünür.
- **Tamamlanma kanıtı:** Mailbox trace + loop breaker negatif testleri.

### B5-08 — Hesap, kota ve provider sağlık durumu [P1]

**Referans:** AgentSpace, MXterm, Orca.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Kullanım/kota/hesap ve provider sağlık görünürlüğü, **izinli** hesap değiştirme
> - **En az kabul kriteri (strateji):** Gerçek sağlayıcı verisi ile unknown ayrılır; izinsiz hesap/kimlik değiştirme yok

#### B5-08.01 — Provider usage ve kota güvenilirlik etiketleri

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B4-04.03`, `B3-07.03`.
- **Mimari / modül sınırı:** Usage ledger + provider health adapter; secretless probes.
- **Uygulama:** Token, kullanılabilir kota, yetki, provider durumu için observed/estimated/unknown ayrımı; API ve abonelik masrafını ayır.
- **Test senaryoları:** Usage raporlamayan sağlayıcı, 429 burst, iptal edilen auth, stale quota, offline.
- **Ölçülebilir kabul:** Kota değeri bilinmiyorsa 0/%100 gösterilmez; her bilinen değer tarih/kaynak taşır.
- **Tamamlanma kanıtı:** Provider fixture ve redaction testi.

#### B5-08.02 — Kullanıcı onaylı profil değiştirme

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B5-08.01`, `B3-07.02`.
- **Mimari / modül sınırı:** Explicit profile selection; credential store isolation.
- **Uygulama:** İzinli alternatif hesap/profil seçiminde görünür önizleme; rate limit nedeniyle otomatik devredilecekse ayrı kullanıcı opt-in’i; gizli kimlik bilgileri loglara yazılmaz.
- **Test senaryoları:** Cross-account task leakage, expired credentials, disabled auto-switch, manual selection override.
- **Ölçülebilir kabul:** Uygun olmayan hesapta görev başlatılmaz; kullanıcı seçimini sessiz değiştirme sıfır.
- **Tamamlanma kanıtı:** Account boundary test + UI onay kayıtları.

### B5-09 — Desktop polish, erişilebilirlik ve yerelleştirme [P1]

**Referans:** AgentSpace, Orca, Open Space.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Desktop kalite: kısayollar, klavye/erişilebilirlik, TR/EN metinler, light/dark, küçük ekran, kısmi offline
> - **En az kabul kriteri (strateji):** Kritik akış klavyeyle yürür; UI focus/contrast/resize regresyon suite'i geçer

#### B5-09.01 — Klavye odaklı Command Palette ve erişilebilirlik

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B3-01.04`, `B5-06.01`.
- **Mimari / modül sınırı:** Desktop shared shortcuts, focus and ARIA contracts.
- **Uygulama:** Run/task open, global search, review, panes ve kritik işlemler için klavye navigasyonu; odak/kontrast/aria etiketleri.
- **Test senaryoları:** Keyboard-only run review, screen reader smoke, 125–200% scaling, modal focus trap, alt-tab.
- **Ölçülebilir kabul:** Beş ana journey klavyeyle tamamlanır; kritik modal altında odak kaçmaz.
- **Tamamlanma kanıtı:** A11y smoke report + keyboard journey video.

#### B5-09.02 — TR/EN, light/dark, responsive ve hata durumları

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B5-09.01`.
- **Mimari / modül sınırı:** UI localization, theming and regression snapshots.
- **Uygulama:** TR/EN mesaj sözlüğü; uzun Türkçe metin, erişilebilir tema, dar pencere, offline/partial-connect durumlarını tamamla.
- **Test senaryoları:** Pseudo localization, long error, dark mode contrast, 1024px window, engine disconnected.
- **Ölçülebilir kabul:** Kritik navigasyonda kesilen metin/bozuk layout yok; kopuk motor yeşil başarılı gösterilmiyor.
- **Tamamlanma kanıtı:** Locale/visual snapshot ve usability kayıtları.

### B5-10 — Yerel profil aktarımı ve audit [P1]

**Referans:** Mission Control, Agency Orchestrator.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Taşınabilirlik: güvenli profil/task şablonu import/export, local audit, migration
> - **En az kabul kriteri (strateji):** Sırlar dışa aktarılmaz; eski sürüm fixture'ı kayıpsız açılır

#### B5-10.01 — Güvenli import/export, şablon taşınabilirliği

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B5-05.01`, `B3-09.02`.
- **Mimari / modül sınırı:** Versioned export bundle, source validation, migration.
- **Uygulama:** Task/workflow/team tercihleri için seçmeli dışa aktarım; sırları, oturum tokenlarını, özel proje dosyalarını dışlama; import dry-run ve conflict resolution.
- **Test senaryoları:** Arşiv path traversal, zip bomb, unknown schema, private key leak, duplicate identifiers.
- **Ölçülebilir kabul:** Export paketi sıfır secret taşır; yanlış sürüm import fail-closed veya önizleme ile reddedilir.
- **Tamamlanma kanıtı:** Bundle format fixtures + secrets scanner output.

#### B5-10.02 — Yerel audit ve veri saklama politikası

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B5-10.01`, `B3-02.02`.
- **Mimari / modül sınırı:** Audit read model, event retention, signed evidence unchanged.
- **Uygulama:** Onay, görev, sağlayıcı profil değiştirme, dışa aktarım ve komutlar için denetlenebilir olay kayıtları; kullanıcıya güvenli temizleme seçenekleri.
- **Test senaryoları:** Disk dolması, retention, audit truncation, evidence deletion conflict, personal data leakage.
- **Ölçülebilir kabul:** İmzalı run kanıtı manipüle edilemez; saklama politikası açık; denetim zincirinde eksik olay gösterilir.
- **Tamamlanma kanıtı:** Audit tamper suite + retention fixtures.

### B5-11 — Beta.5 canlı kabul ve release gate [P0]

**Referans:** Hepsi.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Parity I bağımsız kabul koşusu
> - **En az kabul kriteri (strateji):** Beş ana akış temiz kurulumda çalışır; P0 feature kapsamı %100; kritik güvenlik testi skip=0

#### B5-11.01 — Beş gerçek kullanıcı yolculuğunun doğrulanması

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-01.02`, `B5-02.01`, `B5-03.02`, `B5-04.02`, `B5-06.02`.
- **Mimari / modül sınırı:** Packaged desktop + real supported CLIs + controlled test repositories.
- **Uygulama:** Clean Windows üzerinde gerçek paralel görev, interactive clarification, CI repair, browser trace, local approve/apply akışını tamamla.
- **Test senaryoları:** UI crash, quota exhaustion, wrong SHA, missing test artifact, AppContainer skip, network deny.
- **Ölçülebilir kabul:** 5 journey gerçek altyapıda geçer; P0 security gate skip=0; başarısız koşular done sayılmaz.
- **Tamamlanma kanıtı:** Release SHA + e2e videoları + CI/security kanıt dosyası.

#### B5-11.02 — Rakip parity gate ve release notları

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-11.01`, `B5-00.02`, `B5-09.02`.
- **Mimari / modül sınırı:** Capability matrix + versioned release manifest.
- **Uygulama:** P0 kayıtlarını evidence/test ile verified yap; P1 açıkları triage et; deferred/excluded gerekçeleriyle sürüm notuna aktar.
- **Test senaryoları:** Linter: CAP-ID kanıtsız verified, outdated source, circular task, missing release artifact.
- **Ölçülebilir kabul:** Scope içi P0 yeteneklerin %100’ü testli; bilinçli P1 ertelemeleri görünür; signed binary iddiası yalnız imza varsa.
- **Tamamlanma kanıtı:** Matrix coverage raporu + changelog + release gate imzası.

---

## 10. Beta.6 — Competitive Parity II: Advanced & Connected Workflows

### 10.0 Sürüm hedefi ve kapsamı

**Sürüm vaadi:** Beta.5'in yerel kaliteyi bozmadan gelişmiş rakip yeteneklerine (mobil, SSH, çoklu makine, uzak workspaces, gelişmiş review/entegrasyon) yaklaşmak. Kullanıcı hesabı/bulut **zorunlu değil**.

- **Beta.6:** Mobil, SSH/çoklu host, ileri entegrasyon ve **kanıtlanırsa** cloud/paylaşım/çoklu OS.

**Ana iş indeksi — Beta.6**

| Ana iş | Başlık | Öncelik | Alt görev |
|---|---|---|---:|
| `B6-00` | Gelişmiş rakip farklarının yeniden denetimi | P0 | 2 |
| `B6-01` | Güvenli SSH / remote worker | P0 | 2 |
| `B6-02` | Mobil companion temel deneyimi | P1 | 2 |
| `B6-03` | Çoklu host ve durum senkronizasyonu | P1 | 2 |
| `B6-04` | Opsiyonel cloud worker PoC ve karar | P2 | 2 |
| `B6-05` | Ek issue/source-control adaptörleri | P1 | 2 |
| `B6-06` | Gelişmiş design mode ve satır içi review | P1 | 2 |
| `B6-07` | Operasyon API ve olay abonelikleri | P1 | 2 |
| `B6-08` | Workspace rol erişimi ve paylaşım kararı | P2 | 2 |
| `B6-09` | Opsiyonel görsel takım/ofis görünümü | P2 | 2 |
| `B6-10` | macOS/Linux ve platform güvenlik eşdeğerliği | P1 | 2 |
| `B6-11` | Beta.6 saha pilotu ve release kapısı | P0 | 2 |

**Yüksek riskli kararlar:** Mobil + uzak kontrollere kimlik, ağ saldırı yüzeyi ve revocation; cloud'a ödeme/altyapı/veri gizliliği; çapraz platforma OS sandbox eşdeğerliği gerekir. Bunların hiçbirini sadece UI tamamlandı diye `done` sayma.

**B6-04 Cloud kararı:** Kullanıcı için anlamlı ve taşınabilir bir bulut çözümü koşulları sağlanmazsa `deferred with documented exception` olabilir. Böyle bir istisna, ticari iddiada “tüm rakiplerle yüzde yüz aynı özellikler” dememeyi gerektirir.

### 10.1 Ayrıntılı görevler — Beta.6

### B6-00 — Gelişmiş rakip farklarının yeniden denetimi [P0]

**Referans:** OrchestratorInc, AgentSpace, Orca, Herdr, Mission Control.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Gap re-audit: B5 sonrası P1/P2 açık özellikler, platform/release ve altyapı bütçesi
> - **En az kabul kriteri (strateji):** Her gap için build/integrate/defer kararı; risk ve maliyet açıklaması

#### B6-00.01 — Beta.5 sonrası P1/P2 gap yeniden sayımı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-11.02`.
- **Mimari / modül sınırı:** docs/COMPETITOR_CAPABILITY_MATRIX.md; source snapshots.
- **Uygulama:** Rakiplerin release planı, desteklenen OS, paid/preview ayrımı ve gerçek kullanıcı yolculuklarını yeniden incele; B5 tamamlananları düş; B6 kapsamını dondur.
- **Test senaryoları:** Eski kaynak, shipped olmayan özellik, aynı özellikte iki CAP-ID, doğrulanmamış P0 raporlama negatifleri.
- **Ölçülebilir kabul:** Her B6 yeteneği için build/integrate/defer/exclude kararı ve gerekçe vardır; kaynak tarihi ve sürüm açık.
- **Tamamlanma kanıtı:** Gap freeze + source snapshot + decision ADR.

#### B6-00.02 — Uzak yetki ve işletim maliyeti kararı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B6-00.01`, `B3-00.02`.
- **Mimari / modül sınırı:** docs/THREAT_MODEL.md ek karar; remote/mobile/cloud ayrı alt sınırlar.
- **Uygulama:** Cihaz/host trust boundary, anahtar yönetimi, firewall, kullanıcı hesabı gerekip gerekmediği, bandwidth ve işletim bütçesi; canary aşamasını belirle.
- **Test senaryoları:** Stolen device, revoked host, MITM, replay, offline fail, cross-project leakage tehdit tabloları.
- **Ölçülebilir kabul:** Remote/mobil/cloud için ayrı go/no-go ve ağ kapalı varsayılan; tehdit modeli yoksa uygulama başlamaz.
- **Tamamlanma kanıtı:** Threat model, kaynak maliyet tablosu ve ADR.

### B6-01 — Güvenli SSH / remote worker [P0]

**Referans:** Orca, Herdr.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Güvenli remote worker / SSH workspaces (opt-in)
> - **En az kabul kriteri (strateji):** Karşılıklı kimlik doğrulama, host pinning, revoke, process kill, reconnect, dosya sahipliği; remote fail-closed

#### B6-01.01 — Remote worker protokolü ve host kaydı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B6-00.02`, `B3-02.04`.
- **Mimari / modül sınırı:** Opt-in remote runner + host registry; engine worker policy version handshake.
- **Uygulama:** SSH/host key pinning, host ownership, remote worker identity, OS sandbox gereksinimleri ve sır dağıtım politikasını tanımla; default listener kapalı.
- **Test senaryoları:** Host spoof, MITM, wrong OS sandbox, invalid key, version mismatch, unauthorized command.
- **Ölçülebilir kabul:** Bilinmeyen host çalıştırılmaz; unsafe OS equivalence yoksa worker fail-closed; revoke sonrası yeni görev reddedilir.
- **Tamamlanma kanıtı:** Host pinning fixture + threat negative suite.

#### B6-01.02 — Çalıştırma, reconnect ve güvenli temizleme

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B6-01.01`, `B3-02.03`.
- **Mimari / modül sınırı:** Run location tags; remote process ownership + checkpoint translation.
- **Uygulama:** Remote görev başlatma/durdurma, sınırlandırılmış dosya aktarımı, reconnect cursor, network outage sonrası reconciliation ve process-tree cleanup.
- **Test senaryoları:** Connection drop mid-patch, two-host race, remote reboot, artifact digest mismatch, orphan worker.
- **Ölçülebilir kabul:** Yanlış hostta iş başlatma=0; kesinti sonrası duplicate apply=0; artifact provenance host/commit içerir.
- **Tamamlanma kanıtı:** 2 makineli SSH end-to-end + disconnect logları.

### B6-02 — Mobil companion temel deneyimi [P1]

**Referans:** OrchestratorInc, AgentSpace, Orca.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Mobil companion'ın asgari kullanım akışları (uygunsa PWA veya native)
> - **En az kabul kriteri (strateji):** Eşleşme, session gözlem, izinli cevap ve bildirim; app yokken desktop core çalışır

#### B6-02.01 — Cihaz eşleştirme ve salt-okunur izleme

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B6-00.02`, `B6-01.01`.
- **Mimari / modül sınırı:** Separate mobile/PWA client; authenticated minimal gateway, no core dependency.
- **Uygulama:** Kısa ömürlü QR/pairing, token rotation/revocation, task status ve read-only kanıt; pairing varsayılan kapalı; uygulama türü PoC ile seç.
- **Test senaryoları:** Stolen phone, replayed pairing, expired token, local-only engine, host offline.
- **Ölçülebilir kabul:** Eşleşmemiş cihaz hiçbir veriyi okuyamaz; revoke etkili; masaüstü uzaktan client olmadan tam çalışır.
- **Tamamlanma kanıtı:** Device pairing pen-test + offline e2e.

#### B6-02.02 — Mobil bildirim ve izinli cevap yönetimi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B6-02.01`, `B5-06.01`.
- **Mimari / modül sınırı:** Notification transport + input-only scope, native authority still separate.
- **Uygulama:** Needs-you bildirimleri, görev mesajı ve açıkça izin verilen durdur/cevap; uzak apply/merge onayını ayrı güvenlik projesi olarak kapalı tut veya kanıtlanmış farklı authority tasarla.
- **Test senaryoları:** Wrong run notification, replayed reply, revoked device, deep link injection, offline queue.
- **Ölçülebilir kabul:** Mobil cevap yanlış run’a yazılmaz; notification yanlışlıkla privileged approval olmaz; stop idempotent.
- **Tamamlanma kanıtı:** Mobil 3-senaryo video + replay testleri.

### B6-03 — Çoklu host ve durum senkronizasyonu [P1]

**Referans:** OrchestratorInc, Herdr.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Çoklu host / cihaz eşleştirme ve durum senkronizasyonu
> - **En az kabul kriteri (strateji):** Farklı host'un işi yanlış hostta başlatılmaz; bağlantı kesilince güvenli replay/recovery

#### B6-03.01 — Multi-host registry ve run ownership

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B6-01.01`.
- **Mimari / modül sınırı:** Remote host registry + durable run location + scheduler admission.
- **Uygulama:** Birden fazla hostu özellik, OS izolasyon ve sürüme göre göster; görev sahibi host ve veri kökü bir kez atanır; kullanıcıya taşınma etkisi açıklanır.
- **Test senaryoları:** Duplicate host UUID, lost credentials, host unavailable, incompatible CLI, placement collision.
- **Ölçülebilir kabul:** Her run tek kesin host owner’a sahiptir; kayıp host otomatik yetkisiz yedek hostta çalıştırılmaz.
- **Tamamlanma kanıtı:** 3-host simulation + ownership assertions.

#### B6-03.02 — Durum eşitleme, event replay ve çatışma çözümü

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B6-03.01`, `B6-01.02`.
- **Mimari / modül sınırı:** Event cursors per host, idempotent command IDs, reconciliation.
- **Uygulama:** Event stream uzaktan geldiğinde seq/cursor ve source host kontrolü; mesajların geriden gelmesi durumunda read model doğru gösterir.
- **Test senaryoları:** Partition + reconnect, duplicate/late events, clock skew, wrong-host approval.
- **Ölçülebilir kabul:** Remote olayın host kaynağı doğrulanır; parçalanma sonrası double run/apply sıfır; eksik olay açık bildirildi.
- **Tamamlanma kanıtı:** Network fault matrix + state hash consistency raporu.

### B6-04 — Opsiyonel cloud worker PoC ve karar [P2]

**Referans:** OrchestratorInc cloud worker.  **Öncelik:** P2 / koşullu.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Cloud worker **opsiyonel** PoC (self-host / BYO VM); genel ürünün parçası olmasına gate kararı
> - **En az kabul kriteri (strateji):** Cloud off durumunda tüm local çekirdek çalışır; izolasyon, maliyet, secrets, data locality doğrulanmadan genel erişim yok

#### B6-04.01 — BYO VM cloud threat, data & cost PoC

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P2 / koşullu.
- **Bağımlılıklar:** `B6-00.02`, `B6-01.01`.
- **Mimari / modül sınırı:** Optional VM/container host adapter; same signed run provenance.
- **Uygulama:** Kullanıcı kendi VM’sini bağlayabilsin; secret lifecycle, outbound network, sandbox eşdeğerliği, veri yerleşimi ve maliyet sınırlarını deneyle doğrula.
- **Test senaryoları:** Cloud network egress, leaked secrets, billing retry loop, revoked host, VM shutdown, container escape assumptions.
- **Ölçülebilir kabul:** Cloud kapalıyken local tüm senaryolar geçer; risk/fiyat doğrulanmadıysa `no-go/defer` yazılır.
- **Tamamlanma kanıtı:** Cloud ADR + PoC artefaktı + güvenlik raporu.

#### B6-04.02 — Cloud’u ürün kapsamına alma veya açık erteleme

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P2 / koşullu.
- **Bağımlılıklar:** `B6-04.01`.
- **Mimari / modül sınırı:** Feature flag, paid-provider disclosure, release scope matrix.
- **Uygulama:** PoC sonuçlarına göre GA/beta/deferred; kullanıcının dış sağlayıcı anahtarı ve faturası varsa açık anlat; veri sızıntısı/izin/incident prosedürünü planla.
- **Test senaryoları:** Feature flag off, cost limit, incorrect cloud status, VM quota/timeout, provider outage.
- **Ölçülebilir kabul:** Go kararı verildiyse ayrı canary, sandbox ve maliyet kriterleri tam; no-go kararı da tam ve gerekçeli teslimat sayılır.
- **Tamamlanma kanıtı:** Go/no-go ADR + canary veya deferred release notes.

### B6-05 — Ek issue/source-control adaptörleri [P1]

**Referans:** Orca, OrchestratorInc.  **Öncelik:** P1 / talep doğrulamalı.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Ek kaynak kontrol/issue adaptörleri (GitLab/Linear gibi, talep varsa)
> - **En az kabul kriteri (strateji):** Ortak issue/PR sözleşmesi; yanlış repo/commit bağlama testleri

#### B6-05.01 — Git sağlayıcı soyutlaması ve ikinci adaptör seçimi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1 / talep doğrulamalı.
- **Bağımlılıklar:** `B5-03.02`, `B6-00.01`.
- **Mimari / modül sınırı:** Versioned Issue/PR Provider; GitHub existing adapter unchanged.
- **Uygulama:** Kullanıcı ihtiyacıyla GitLab veya Linear seç; ortak issue/intake/review/status sözleşmesi; provider-specific izin ve rate-limit.
- **Test senaryoları:** Yanlış repo ID, token scope, paginated stale issue, duplicated webhook, branch collision.
- **Ölçülebilir kabul:** Eşit görev için provider farkları açıkça görünür; yanlış repo/issue/commit eşleşmesi sıfır.
- **Tamamlanma kanıtı:** Contract suite + sağlayıcı seçimi ADR.

#### B6-05.02 — Gerçek iki-sağlayıcı teslimat ve hata geri beslemesi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1 / talep doğrulamalı.
- **Bağımlılıklar:** `B6-05.01`.
- **Mimari / modül sınırı:** Issue source mapping + worker PR/CI evidence.
- **Uygulama:** İkinci sağlayıcıyla issue → görev → doğrulanmış PR/review ve hata geri besleme; tek scheduler/evidence otoritesi.
- **Test senaryoları:** Unauthorized issue, closed issue, webhook replay, failed checks, stale branch, missing permissions.
- **Ölçülebilir kabul:** Test reposunda iki ayrı sağlayıcı için e2e; mercek seçimi yanlış olduğunda güvenli reddetme.
- **Tamamlanma kanıtı:** İki sağlayıcı koşu linki + auth/commit test raporu.

### B6-06 — Gelişmiş design mode ve satır içi review [P1]

**Referans:** Orca, AgentSpace.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Gelişmiş design mode, diff satırı anotasyonu, tarayıcıdan ajan geri bildirimi
> - **En az kabul kriteri (strateji):** Kullanıcı seçtiği UI elemanını hedefe aktarır, kaynak ekran görüntüsü redakte edilir; otomatik write yok

#### B6-06.01 — Satır içi diff işaretleme ve kaynak sürüm izleme

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B5-03.02`, `B5-04.02`.
- **Mimari / modül sınırı:** Typed annotations for diff/source revision, native UI.
- **Uygulama:** Kullanıcı dosyada satır aralığını seçip yorum yazsın; comment commit/file hash’e bağlansın; eski diff durumunda uyarı.
- **Test senaryoları:** Moved lines, binary diff, split worktree, stale line, malicious comment payload.
- **Ölçülebilir kabul:** Yorum yanlış revizyona taşınmaz; agent’a yalnız açıkça izin verilen yorum görev bilgisi olarak gider.
- **Tamamlanma kanıtı:** Annotation fixtures + UI e2e.

#### B6-06.02 — DOM/element kaynaklı görev geri bildirimi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B6-06.01`, `B5-04.02`.
- **Mimari / modül sınırı:** Browser element locator envelope, safety preview.
- **Uygulama:** Kullanıcı seçtiği DOM öğesini screenshot, URL origin ve locator ile hata görevi bağlamına aktar; browser origin policy ile sınırla.
- **Test senaryoları:** DOM injection, 3rd-party cookies, file://, opaque iframe, XSS-to-IPC.
- **Ölçülebilir kabul:** Seçilen öğe doğrulanmış yerel uygulamayla ilişkilendirilir; browser hiçbir privileged eylemi tetikleyemez.
- **Tamamlanma kanıtı:** Element-to-task e2e + browser security negatives.

### B6-07 — Operasyon API ve olay abonelikleri [P1]

**Referans:** Mission Control, DeepSeek DSH, Block/Buzz.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Operasyon API/CLI/MCP, webhook event subscriptions, scheduled checks
> - **En az kabul kriteri (strateji):** API yetki matrisi; webhook doğrulama/replay idempotency; insan approval API üzerinden spoof edilemez

#### B6-07.01 — API/MCP/CLI komut ve yetki sözleşmesi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B6-00.02`, `B3-00.03`.
- **Mimari / modül sınırı:** External automation API with narrow scopes, separate approvals.
- **Uygulama:** Read/run/start/cancel/event subscribe yetkilerini ayır; MCP veya uzaktan istemciye native human-approval otoritesini vermeden OAuth/token/localhost modelini tasarla.
- **Test senaryoları:** CSRF, replay, privilege escalation, generic shell injection, unrestricted localhost, oversized payload.
- **Ölçülebilir kabul:** Bilinmeyen veya yetkisiz API komutu reddedilir; agent kendi patch’ini API ile approve/apply edemez.
- **Tamamlanma kanıtı:** API permissions matrix + authenticated e2e + fuzz.

#### B6-07.02 — Webhook güvenliği, scheduling ve event-to-task policy

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B6-07.01`, `B5-05.02`.
- **Mimari / modül sınırı:** Signed event subscriptions + admission policy + durable inbox.
- **Uygulama:** İsteğe bağlı webhook kaynağı, HMAC/signature, allowlist, replay window, event→task taslağı; dış olaylar otomatik yetki vermesin.
- **Test senaryoları:** Forged event, replay, burst, wrong branch/issue, timezone skew, poison event.
- **Ölçülebilir kabul:** Sahte event sıfır iş başlatır; gerçek event bir kez işlenir; yazma yetkili görev için insan kuralları uygulanır.
- **Tamamlanma kanıtı:** Webhook attack suite + queued event log.

### B6-08 — Workspace rol erişimi ve paylaşım kararı [P2]

**Referans:** Mission Control, Block/Buzz.  **Öncelik:** P2 / koşullu.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Workspace/rol erişimi, paylaşımlı senaryo gereksinimleri; önce threat model
> - **En az kabul kriteri (strateji):** Tek kullanıcılı kullanım bozulmaz; tenant isolation gerekirse ayrı release gate

#### B6-08.01 — Tek kullanıcı ile çok kullanıcı trust boundary ayrımı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P2 / koşullu.
- **Bağımlılıklar:** `B6-00.02`.
- **Mimari / modül sınırı:** Workspace authz threat model, principal roles, separate tenant resources.
- **Uygulama:** Gerçek ekip kullanımı ihtiyacını ölç; yalnız yerel tek kullanıcı ise çok kullanıcı sistemi zorlamadan role matrix/ADR çıkar.
- **Test senaryoları:** Cross-user run read/write, approval delegation, leaked evidence, shared secret, concurrency.
- **Ölçülebilir kabul:** Paylaşımlı kullanım için açık kimlik/tenant model olmadan çok kullanıcı yetkileri yayınlanmaz; yerel ürün etkilenmez.
- **Tamamlanma kanıtı:** Threat model + user-study go/no-go.

#### B6-08.02 — Koşullu paylaşımlı çalışma pilotu

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P2 / koşullu.
- **Bağımlılıklar:** `B6-08.01`, `B6-07.01`.
- **Mimari / modül sınırı:** Separate per-user workspace ACL with durable audit; optional.
- **Uygulama:** Go verilirse 2 kullanıcı/rol ile read, assignment, review ve izinli workflow; kullanıcılar arası erişim denetimi.
- **Test senaryoları:** Role downgrade, revoked user, cross-tenant artifact, concurrent approval, stolen token.
- **Ölçülebilir kabul:** İzinsiz cross-tenant veri/komut sıfır; no-go durumunda kapsam dışı açıkça belgelidir.
- **Tamamlanma kanıtı:** 2-principal security pilot veya deferred ADR.

### B6-09 — Opsiyonel görsel takım/ofis görünümü [P2]

**Referans:** AgentSpace, Open Space.  **Öncelik:** P2 / koşullu.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Opsiyonel görsel ekip/ofis modu (yalnız kullanıcı testlerinde değerliyse)
> - **En az kabul kriteri (strateji):** Görsel mod olmadan bütün işlevler kullanılabilir; ekran okuyucu ve performans alternatifi vardır

#### B6-09.01 — Kullanıcı değerini doğrulama ve tasarım kararı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P2 / koşullu.
- **Bağımlılıklar:** `B5-07.02`, `B5-09.02`.
- **Mimari / modül sınırı:** Desktop optional view, event read model.
- **Uygulama:** Kullanıcılara Kanban/liste vs basit görsel ofis prototiplerini kıyaslat; dikkat, hız ve erişilebilirlik etkilerini ölç.
- **Test senaryoları:** 5–10 görevli kullanılabilirlik deneyi; değişik ekran ölçeklerinde kontrast; temel UI klavye.
- **Ölçülebilir kabul:** Net kullanım faydası kanıtlanmıyorsa native ofis modu ertelenir; fonksiyonlar listede eksiksiz kalır.
- **Tamamlanma kanıtı:** Usability notes + design go/no-go.

#### B6-09.02 — Değerliyse düşük maliyetli, salt-okunur ofis görünümü

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P2 / koşullu.
- **Bağımlılıklar:** `B6-09.01`.
- **Mimari / modül sınırı:** Existing agent/team events projection; no second scheduler.
- **Uygulama:** Ajan rol, durum, handoff ve blokajı gösteren hafif görsel tema; bütün kontroller erişilebilir alternatifte aynen var.
- **Test senaryoları:** 100 agent simulation, GPU low-end, screen reader, stale status, 60Hz redraw pressure.
- **Ölçülebilir kabul:** Ekranı kapatma görev motorunu etkilemez; perf bütçesi aşılırsa flag off; alternatif görünüm aynı işlevlerde.
- **Tamamlanma kanıtı:** Optional UX test + perf/a11y raporu veya deferred ADR.

### B6-10 — macOS/Linux ve platform güvenlik eşdeğerliği [P1]

**Referans:** OrchestratorInc, Orca.  **Öncelik:** P1 / yüksek risk.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Desteklenen Windows/macOS/Linux kapsamını ayrı OS kanıtıyla genişlet
> - **En az kabul kriteri (strateji):** Windows AppContainer güvenliğini diğer OS'te varmış gibi iddia etme; her OS için eşdeğer izolasyon ve gerçek test

#### B6-10.01 — Platform port gereksinimleri ve güvenlik matrisi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1 / yüksek risk.
- **Bağımlılıklar:** `B6-00.02`, `B3-09.04`.
- **Mimari / modül sınırı:** OS-specific sandbox launcher adapters; engine policy canonical.
- **Uygulama:** Windows AppContainer’a eşdeğer yetki sınırlarını macOS/Linux için ayrı modelle; PTY, network sandbox, filesystem, signing ve installer gereksinimleri.
- **Test senaryoları:** Read/write path escape, unauthorized network, child process, symlinks, credentials, elevated account.
- **Ölçülebilir kabul:** Platform güvenlik testi koşmadan "supported" yayımlanmaz; fail-open fallback sıfır.
- **Tamamlanma kanıtı:** macOS/Linux negative-test suite ve platform go/no-go ADR.

#### B6-10.02 — Platform E2E, installer ve veri taşınabilirliği

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1 / yüksek risk.
- **Bağımlılıklar:** `B6-10.01`, `B3-09.03`.
- **Mimari / modül sınırı:** Platform release pipelines, migration and signed artifacts.
- **Uygulama:** Destek kararı verilen OS için temiz kurulumdan PR inceleme/onaya kadar gerçek görev; yollar, encoding, güncelleme/rollback ve sandbox kanıtını topla.
- **Test senaryoları:** Mac permission prompt, Linux user namespaces unavailable, updater crash, Windows↔Linux profile import.
- **Ölçülebilir kabul:** Her resmi OS’te güvenlik + user journey ayrı geçer; geçmeyen OS beta dışı ve açıkça belgeli.
- **Tamamlanma kanıtı:** Per-platform SHA + installer + App/Sandbox kanıt raporu.

### B6-11 — Beta.6 saha pilotu ve release kapısı [P0]

**Referans:** OrchestratorInc, AgentSpace, Orca, Mission Control.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş paketi ve kapsam (strateji):** Parity II saha pilotu ve sürüm kapısı
> - **En az kabul kriteri (strateji):** Mobil/SSH/remote için en az bir gerçek uçtan uca pilot; güvenlik tehdit modeli; kapsamlı P1 özellik doğrulaması

#### B6-11.01 — Mobil/SSH/çoklu host gerçek saha pilotu

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B6-01.02`, `B6-02.02`, `B6-03.02`.
- **Mimari / modül sınırı:** Actual machines and devices in controlled pilot.
- **Uygulama:** En az bir gerçek SSH host ve mobil cihazla uçtan uca görev gözlem/yanıt/reconnect; lokal bağımsız deneyimde değişiklik olmadığını doğrula.
- **Test senaryoları:** Stolen/revoked device, host outage, token expiration, network partition, audit mismatch.
- **Ölçülebilir kabul:** Pilot sonunda yetkisiz remote eylem sıfır; 0 kritik security skip; remote kapatınca local görev çalışır.
- **Tamamlanma kanıtı:** Pilot SHA, cihaz/host matrisi, olay ve pentest raporu.

#### B6-11.02 — Koşullu özellik kararları ve parity II release

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B6-11.01`, `B6-00.01`.
- **Mimari / modül sınırı:** Updated capability matrix, signed release manifest.
- **Uygulama:** Cloud, paylaşım, ofis, ek OS için go/no-go kararlarını kullanıcı verisi ve güvenlikle kapat; P0/P1 kapsama raporu; release notes.
- **Test senaryoları:** Deferred P0 gerekçe kontrolü; riskli özellik yanlışlıkla enabled; release artifact provenance.
- **Ölçülebilir kabul:** Kapsam içi P0 %100 testli, hedef P1 ≥%90 veya kabul edilmiş gerekçeli boşluk; hiçbir no-go özelliği aktifmiş gibi duyurulmaz.
- **Tamamlanma kanıtı:** Parity II report + signed/unsigned açık release status + changelog.

---

## 11. Beta.7 — Respected-Exclusive Value (Respected Innovations)

### 11.0 Sürüm hedefi ve kapsamı

**Kural:** B5/B6 parity sonuçları, saha verisi ve teknik fizibiliteye göre özelliği geliştirme/erteleme kararı ver. Önceki önerilerin otomatik olarak hepsini aynı sürüme sıkıştırma.

- **Beta.7:** Project Doctor, Build & Prove, Verified Autopilot, Proof Pack ve destekleyici yenilikler.

**Ana iş indeksi — Beta.7**

| Ana iş | Başlık | Öncelik | Alt görev |
|---|---|---|---:|
| `B7-01` | Project Doctor | P0 | 2 |
| `B7-02` | Build & Prove | P0 | 2 |
| `B7-03` | Verified Autopilot | P0 | 2 |
| `B7-04` | Proof Pack 2.0 | P0 | 2 |
| `B7-05` | Agent Tournament | P1 | 2 |
| `B7-06` | Impact & Risk Intelligence | P1 | 2 |
| `B7-07` | Recovery Time Machine | P1 | 2 |

**Araç kullanımı ilkesi:** Orchestrator test koşucusu değil, doğrulama **orkestratörü**. `VerificationProvider` sürümlü arabirimi: `capabilities`, `prepare`, `run`, `cancel`, `collect_artifacts`, `provenance`, `cleanup`; yerel Playwright varsayılan, TestSprite gibi ücretli dış servisler opt-in ve adapter. Dış servis sonucunun nereden geldiği ve hangi commit'e karşı koştuğu bağlanmadıkça "verified" sayılmaz.

**Minimum pilot kapsamı:** İlk önce B7-01 ve B7-02 dikey uçtan uca demo; gerçek kullanıcı tercihine göre B7-03/04/05/06/07 sırasını güncelle.

### 11.1 Ayrıntılı görevler — Beta.7

### B7-01 — Project Doctor [P0]

**Referans:** Respected özgün iş akışı; mevcut tester/MAF reuse.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Yeni kullanıcı değeri (strateji):** Yarım/bozuk projeyi kanıtla teşhis etme ve kurtarma planı
> - **Yeniden kullanılacak bileşen/araç (strateji):** Mevcut tester, MAF, DAG, repo indeksleme; TS/Python tools
> - **DoD örneği (strateji):** Tanılama salt okunur; rapor doğrulanabilir; düzeltme açık izinli

#### B7-01.01 — Salt-okunur proje teşhis sağlayıcıları ve bulgu şeması

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-04.01`, `B4-05.01`.
- **Mimari / modül sınırı:** DiagnosticProvider interface, existing test runner, repo metadata.
- **Uygulama:** Build/test/lint/package yönetici tanıma; proje izninde salt-okunur testlerin yan etki riskini ayrıca sandbox içinde; finding = command, affected component, severity, confidence, evidence.
- **Test senaryoları:** Bozuk proje fixture, gizli .env, network-dependent build, false error, dependency install side effect.
- **Ölçülebilir kabul:** Kullanıcı izni olmadan kaynak dosya mutasyonu=0; bulgular komut+log+commit’e bağlı; unknown kesin hata denmez.
- **Tamamlanma kanıtı:** 5 stack fixture (örn. JS/Python) + side-effect diff audit.

#### B7-01.02 — Teşhisten kontrollü kurtarma planına e2e

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B7-01.01`, `B3-04.03`.
- **Mimari / modül sınırı:** Diagnostic-to-DAG plan proposal; risk and owner preview.
- **Uygulama:** Bulgu → onaylı düzeltme aşamaları; bağımlılık/dosya sahipliği; her düzeltmede başlangıç kanıtı ve hangi testin tekrar koşacağı.
- **Test senaryoları:** 3 ilişkili hata, yanlış root-cause, cycle, forbidden files, no-worktree scenario.
- **Ölçülebilir kabul:** En az 5 bozuk örnek proje için anlaşılır plan; açık Start olmadan worker=0; teşhis kullanıcı değişikliklerini silmez.
- **Tamamlanma kanıtı:** Before/after diagnostic report + staged DAG + UI video.

### B7-02 — Build & Prove [P0]

**Referans:** Playwright, Chrome DevTools, opsiyonel TestSprite.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Yeni kullanıcı değeri (strateji):** Gerçek çalışan UI/API akışının gösterimi
> - **Yeniden kullanılacak bileşen/araç (strateji):** Playwright CLI/Test, MCP, Chrome DevTools; opsiyonel TestSprite
> - **DoD örneği (strateji):** Çalışan uygulama testi, trace/video ve test commit bağlantısı; ağ ve secret sınırları

#### B7-02.01 — Birleşik verification provider ve artefakt provenance

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B5-04.01`, `B7-01.01`.
- **Mimari / modül sınırı:** Versioned VerificationProvider; artifact store, signed evidence extension.
- **Uygulama:** Tarayıcı/UI, API ve proje testlerinden pass/fail/unknown, screenshot, video, trace, tested commit, browser version ve ortam bilgilerini normalize et; TestSprite yalnız opsiyonel adaptör.
- **Test senaryoları:** Wrong commit, stale browser session, media secret, provider unavailable, invalid video hash, network permission.
- **Ölçülebilir kabul:** Gerçek Playwright UI testinde ekran görüntüsü+trace/video kaydı run/commit’e bağlı; dış provider sonucu yerel verified sayılmadan provenance kontrolü.
- **Tamamlanma kanıtı:** Provider contract suite + artifact digest + Playwright E2E.

#### B7-02.02 — Önce/sonra gösterimi ve kullanıcı senaryosu kanıtı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B7-02.01`, `B3-05.01`.
- **Mimari / modül sınırı:** Review screen before/after snapshots, timeline, result classification.
- **Uygulama:** Sepet/auth/login gibi senaryo ekranları; önce/sonra farkları, test adımları, başarısız koşular ve kullanıcıya açıklama.
- **Test senaryoları:** Flaky UI test, missing before screenshot, inconsistent viewport, sensitive screenshot, broken preview.
- **Ölçülebilir kabul:** En az 3 gerçek UI user journey güvenli şekilde izlenebilir; test edilmeyen akış için “kanıtlandı” ifadesi kullanılmaz.
- **Tamamlanma kanıtı:** Review video + trace viewer + redaction testleri.

### B7-03 — Verified Autopilot [P0]

**Referans:** Respected DAG/MAF/CI; rakip issue-to-PR.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Yeni kullanıcı değeri (strateji):** Kullanıcının açık bütçe/izin sınırı içinde issue → doğrulanmış PR
> - **Yeniden kullanılacak bileşen/araç (strateji):** DAG, recovery, review, PR/CI; policy engine
> - **DoD örneği (strateji):** Bütçe / deneme / süre / yetki sınırı asla aşılmaz, merge ve apply ayrı açık karar

#### B7-03.01 — Sınırlı otonomi politika profilleri

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B4-08.03`, `B6-07.01`, `B3-00.03`.
- **Mimari / modül sınırı:** AutopilotPolicy versioned, scheduler admission, budgets, human authority.
- **Uygulama:** Guided/Supervised/Bounded modları; scope, network, token, elapsed, retry, allowed tools, merge/apply restrictions; politika önizleme ve kullanıcı rızası.
- **Test senaryoları:** Model output injection, infinite retries, budget exhaustion, unsafe tool, unauthorized privilege switch.
- **Ölçülebilir kabul:** Sınır aşılınca durdur/escalate; hiçbir mod insan apply/merge yetkisini üretmez; policy snapshot run ile tutulur.
- **Tamamlanma kanıtı:** Policy negative matrix + bounded-run simulations.

#### B7-03.02 — Issue→PR kanıtlı tam iş akışı ve bailout

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B7-03.01`, `B5-03.02`, `B7-02.01`.
- **Mimari / modül sınırı:** Existing GitHub workflow + plan/test/review/PR + exit criteria.
- **Uygulama:** Issue kabulü → plan → worker → tester/reviewer → izinli fix → gerçek PR → operator inbox; beklenmeyen sorunlarda kontrollü pause.
- **Test senaryoları:** CI unavailable, forged review, quota exhausted, stale patch, disk full, user cancel mid-run.
- **Ölçülebilir kabul:** Örnek 3 issue için PR ready ve kanıt; bütçe/izin ihlali sıfır; atlanan adım release kanıtında gösterilir.
- **Tamamlanma kanıtı:** 3 real-run manifests + budget ledger + approval trace.

### B7-04 — Proof Pack 2.0 [P0]

**Referans:** SLSA provenance, existing signed evidence.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Yeni kullanıcı değeri (strateji):** Bağımsız denetlenebilir ve paylaşılabilir teslimat
> - **Yeniden kullanılacak bileşen/araç (strateji):** İmzalı kanıt, trace, diff, provenance, yerel doğrulayıcı
> - **DoD örneği (strateji):** `not-tested`, `failed`, `verified` ayrılır; gizli veri redaksiyonu; bağımsız verification

#### B7-04.01 — Dışa aktarılabilir kanıt paketi şeması

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B7-02.01`, `B3-05.03`.
- **Mimari / modül sınırı:** ProofBundle versioned artifact manifest + signatures; existing evidence immutable.
- **Uygulama:** Kaynak SHA, task/run, tool/model version, policy, diff, check, logs, browser trace, review, unknown/fail ve açık kullanıcı kararı; secret redaction ve expiry.
- **Test senaryoları:** Tampered bundle, wrong run/patch, missing artifact, self-signed untrusted cert, hidden secret.
- **Ölçülebilir kabul:** Tek dosyada bütün referanslar digest’e bağlı; kanıt olmayan test failed veya verified diye etiketlenmez; sırlar sızmaz.
- **Tamamlanma kanıtı:** JSON schema + sample bundle + tamper test suite.

#### B7-04.02 — Çevrimdışı bağımsız proof doğrulayıcı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B7-04.01`.
- **Mimari / modül sınırı:** Read-only offline verifier; no code execution by default.
- **Uygulama:** Bundle signature/digest, izin verilen test kapsamı, kaynak commit ve kanıt tutarlılığı; verifier sonuçları valid/invalid/incomplete ayrımı.
- **Test senaryoları:** Farklı makinede verify, missing key, corrupt ZIP, replay artifact, untrusted provider attestation.
- **Ölçülebilir kabul:** Güvenilir anahtar verildiğinde 2. makinede doğrulama yapılır; bozuk kanıt reddedilir; test çalıştırıldığına dair iddia yalnız kanıtı ölçüsünde.
- **Tamamlanma kanıtı:** Cross-device verify log + tamper/unknown fixtures.

### B7-05 — Agent Tournament [P1]

**Referans:** Cross-model council yaklaşımı; mevcut worktree/eval.  **Öncelik:** P1 / opt-in.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Yeni kullanıcı değeri (strateji):** İki aday çözümü gerçek testlerle karşılaştırma (opt-in)
> - **Yeniden kullanılacak bileşen/araç (strateji):** Mevcut paralel worktree + eval harness
> - **DoD örneği (strateji):** Aynı koşullar, kontrollü bütçe; başarısız çözüme kazanan etiketi verilmez

#### B7-05.01 — Eşit koşullu çoklu aday yürütme

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1 / opt-in.
- **Bağımlılıklar:** `B4-01.04`, `B7-03.01`.
- **Mimari / modül sınırı:** Tournament scheduler, separate worktrees, budget ceiling.
- **Uygulama:** İki ajana aynı görev/commit/test seti; no shared state; ayrı policy, sınırlandırılmış maliyet ve açık opt-in.
- **Test senaryoları:** A/B dosya çakışması, leakage, unequal environment, provider version drift, budget blowup.
- **Ölçülebilir kabul:** İki aday eş koşul meta verisiyle yürür; user opt-in olmadan çift çağrı yok; toplam bütçe aşılmaz.
- **Tamamlanma kanıtı:** Paired-run manifest + cost and environment equivalence report.

#### B7-05.02 — Kör test, risk ve güvenilirlik temelli tercih

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1 / opt-in.
- **Bağımlılıklar:** `B7-05.01`, `B7-04.01`.
- **Mimari / modül sınırı:** Comparison rubric with functional/security/perf/cost, human final choice.
- **Uygulama:** Test sonuçları, regresyon, risk ve maliyet rubriği; aynı başarısızlıkta kazanan yok; hız tek başına belirleyici olamaz.
- **Test senaryoları:** Both fail, flaky tests, false performance winner, untrusted test changes, statistical noise.
- **Ölçülebilir kabul:** Yanlış/yetersiz karşılaştırmada winner=none; kullanıcı seçmeden kaynak projeye aday uygulanmaz.
- **Tamamlanma kanıtı:** Scored sample tournament + fairness/rubric audit.

### B7-06 — Impact & Risk Intelligence [P1]

**Referans:** Serena / code graph research; existing repo scope.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Yeni kullanıcı değeri (strateji):** Değişiklik etki alanına göre hedefli test planı
> - **Yeniden kullanılacak bileşen/araç (strateji):** Semantik kod/bağımlılık analizi (Serena gibi araçlara isteğe bağlı adaptör)
> - **DoD örneği (strateji):** Risk gerekçesi, coverage açıklığı, kritik regresyon testlerini atlamama

#### B7-06.01 — Değişiklik etki grafı ve test ilişkisi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B4-05.01`, `B7-01.01`.
- **Mimari / modül sınırı:** Read-only code index, symbol/dependency/test maps; optional external semantic tools.
- **Uygulama:** Değişen sembol/import/API, test coverage ve ilişkili modülleri analiz edip impact set ve confidence üret; büyük projede cache invalidation.
- **Test senaryoları:** Wrong dependency graph, stale HEAD, circular imports, symlink, untracked source, cross-language modules.
- **Ölçülebilir kabul:** Her risk önerisi kaynak referansı taşır; unresolved/unknown açık gösterilir; forbidden path indeksi yok.
- **Tamamlanma kanıtı:** Repo fixture graph + false positive/negative samples.

#### B7-06.02 — Risk bazlı test seçimi ve güvenlik kritik override

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B7-06.01`, `B7-02.01`.
- **Mimari / modül sınırı:** TestPlan proposal, mandatory suites independent from risk model.
- **Uygulama:** Değişikliğin etkilediği testleri öne çıkar, kritik auth/payment/security geniş regresyonu asla atlama; nedenini UI’da açıkla.
- **Test senaryoları:** Uncovered critical path, false low risk, cost budget vs security override, flaky test.
- **Ölçülebilir kabul:** Kritik regresyon atlama=0; seçilen testler gerekçeli ve canary karşılaştırmalı başarı raporlu.
- **Tamamlanma kanıtı:** Impact test plan + holdout regression report.

### B7-07 — Recovery Time Machine [P1]

**Referans:** Git/checkpoint/evidence reused.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Yeni kullanıcı değeri (strateji):** Güvenli geri dönüş adayını sunma
> - **Yeniden kullanılacak bileşen/araç (strateji):** Git, snapshot, checkpoint, migration, diff
> - **DoD örneği (strateji):** Kullanıcının ilgisiz değişiklikleri ezilmez; rollback öncesi preview + onay

#### B7-07.01 — Güvenli geri alma adayları ve salt-okunur önizleme

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B3-02.04`, `B7-04.01`.
- **Mimari / modül sınırı:** Git snapshots + signed checkpoint history + local restore planner.
- **Uygulama:** Görevler arası kırılma tespiti için commit/tarih/test evrimi; geri dönüş adayı, kaybolacak değişiklikler ve bağımlılıkları listele.
- **Test senaryoları:** Uncommitted user edit, shared branch, stale checkpoint, binary files, missing git object.
- **Ölçülebilir kabul:** Kullanıcının çalışma dosyaları otomatik ezilmez; her rollback adayı diff/riski önceden gösterir.
- **Tamamlanma kanıtı:** 5 recovery fixture + before/after hash.

#### B7-07.02 — Onaylı kurtarma transaction ve tekrar doğrulama

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B7-07.01`, `B3-05.03`.
- **Mimari / modül sınırı:** Restore authority with explicit user action; transaction log.
- **Uygulama:** İstisnasız açık kullanıcı onayı, safe snapshot ve geri dönüş; restore sonrası build/test/evidence; uyumsuzlukta dur ve kurtarmaya izin ver.
- **Test senaryoları:** Mid-restore crash, wrong branch, reapply, concurrent edit, partial rollback, unauthorized API call.
- **Ölçülebilir kabul:** İzin dışı restore=0; ilgisiz user edits kaybolmaz; başarısız restore geri alınabilir.
- **Tamamlanma kanıtı:** Fault-injection restore tests + user-presence audit.

### 11.2 Beta.7 teknik çerçeve `[ÖNERİ]`

Bu çerçeve, yukarıdaki görev kartlarını birbirine bağlayan veri akışını ve **yeniden kullanılacak mevcut araçları** özetler. Kartlarda olmayan yeni gereksinim eklemez; yalnız bileşenlerin sırasını ve sahipliğini gösterir.

```text
Project Doctor (B7-01)           Build & Prove (B7-02)             Proof Pack 2.0 (B7-04)
 salt-okunur teşhis               VerificationProvider              ProofBundle + çevrimdışı doğrulayıcı
 DiagnosticProvider  ──bulgu──►   Playwright/DevTools/pytest ──►    kaynak SHA, task/run, tool/model sürümü,
 (mevcut tester, MAF, DAG)        artefakt: screenshot/trace/video  policy, diff, check, log, trace, review,
        │                         tested commit + tarayıcı sürümü   unknown/fail ve kullanıcı kararı
        ▼ (açık Start şart)               ▲                                  ▲
 kurtarma planı (DAG önerisi) ────────────┘                                  │
        │                                                                    │
        ▼                                                                    │
 Verified Autopilot (B7-03): AutopilotPolicy (bütçe/deneme/süre/yetki) ──────┘
        │  issue → plan → worker → tester/reviewer → PR → operator inbox
        ├── Agent Tournament (B7-05): iki aday, aynı koşul, gerçek test
        ├── Impact & Risk Intelligence (B7-06): etki alanına göre hedefli test
        └── Recovery Time Machine (B7-07): önizlemeli, onaylı geri dönüş
```

**Mevcut araçlardan yararlanma ilkesi (temel prensip):** Playwright (CLI/Test/MCP, Trace Viewer, video), Chrome DevTools, pytest/Jest ve proje testleri, Git/worktree, mevcut `tester`/MAF/DAG, imzalı evidence ve checkpoint **yeniden yazılmaz**; dar, sürümlü adaptörlerle bağlanır. Orchestrator doğrulama **orkestratörüdür**: koşuyu, yetkiyi, kanıtı ve kararı yönetir.

| Beta.7 işi | Yeniden kullanılan bileşen | Yeni olan (dar katman) | Kritik güvenlik kuralı |
|---|---|---|---|
| `B7-01` Project Doctor | Mevcut tester, MAF, DAG, repo indeksleme, TS/Python araçları | `DiagnosticProvider` arabirimi, bulgu şeması (command, component, severity, confidence, evidence) | Kullanıcı izni olmadan kaynak mutasyonu = 0; unknown kesin hata denmez |
| `B7-02` Build & Prove | Playwright CLI/Test/MCP, Chrome DevTools, opsiyonel TestSprite | Sürümlü `VerificationProvider` (`capabilities`, `prepare`, `run`, `cancel`, `collect_artifacts`, `provenance`, `cleanup`), artefakt provenance | Dış servis sonucu commit'e bağlanmadan `verified` sayılmaz; ağ ve secret sınırları |
| `B7-03` Verified Autopilot | DAG, recovery, review, PR/CI (`GH-*`, `B5-03`), policy engine | `AutopilotPolicy` (Guided/Supervised/Bounded) | Merge/apply ayrı açık insan eylemi; bütçe/deneme/süre/yetki aşılamaz |
| `B7-04` Proof Pack 2.0 | İmzalı evidence, trace, diff, provenance | `ProofBundle` manifest + çevrimdışı doğrulayıcı | `not-tested` / `failed` / `verified` ayrı; secret redaksiyonu |
| `B7-05` Agent Tournament | Paralel worktree + eval harness | Aday karşılaştırma raporu (opt-in) | Başarısız çözüme kazanan etiketi verilmez; bütçe sınırı |
| `B7-06` Impact & Risk | Semantik kod/bağımlılık analizi (Serena gibi araçlara isteğe bağlı adaptör) | Etki→test planı, coverage açıklığı | Kritik regresyon testleri atlanmaz |
| `B7-07` Recovery Time Machine | Git, snapshot, checkpoint, migration, diff | Geri dönüş adayı + önizleme | Kullanıcının ilgisiz değişiklikleri ezilmez; önizleme + onay |

**Pilot sırası (kaynak):** İlk önce `B7-01` + `B7-02` dikey uçtan uca demo; gerçek kullanıcı tercihine göre `B7-03/04/05/06/07` sırası güncellenir. **Beta.7 kuralı:** B5/B6 parity sonuçları, saha verisi ve teknik fizibiliteye göre özelliği geliştirme/erteleme kararı verilir; önceki önerilerin hepsi otomatik olarak aynı sürüme sıkıştırılmaz.

**Önerilen test altyapısı sınırları `[ÖNERİ]`:** (1) Proje teşhis komutları (`build/test/lint/package`) yan etki riski taşıdığı için yalnız kullanıcı izniyle ve sandbox içinde; bağımlılık kurulumu yan etkisi `B7-01.01` "side-effect diff audit" ile kanıtlanır. (2) Tarayıcı artefaktları (screenshot/video/trace) hassas veri içerebilir; redaksiyon testi (`B7-02.02`) kanıt paketine girmeden önce zorunlu. (3) Dış provider (TestSprite) kullanıldığında veri çıkışı ve maliyet kullanıcıya gösterilir; ücretsiz sayılmaz.

---

## 12. Beta.8 — Research, Competitor Benchmarks & Engineering Optimization

### 12.0 Sürüm hedefi ve kapsamı

**Başlamadan önce** gerçek kullanıcılardan yeterli senaryo ve hata/performans kanıtı topla. Bu faz ürünün bütün özelliklerini *ölçülü şekilde* iyileştirir.

- **Beta.8:** Bağımsız literatür incelemesi, adil benchmark, kullanıcı testleri ve ölçümlü optimizasyon.

**Ana iş indeksi — Beta.8**

| Ana iş | Başlık | Öncelik | Alt görev |
|---|---|---|---:|
| `B8-01` | Rakip sürüm ve özellik yeniden doğrulaması | P0 | 1 |
| `B8-02` | Araştırma literatür haritası | P0 | 1 |
| `B8-03` | Adil ajan ve rakip benchmark koşuları | P0 | 1 |
| `B8-04` | Gizli ve bağımsız doğrulanmış görev seti | P0 | 1 |
| `B8-05` | Gerçek kullanıcı ve kullanım araştırmaları | P0 | 1 |
| `B8-06` | Bağımsız güvenlik saldırı denetimi | P0 | 1 |
| `B8-07` | Performans, maliyet, bellek ve a11y optimizasyonu | P1 | 1 |
| `B8-08` | Araştırma sonucunu kalıcı kalite kapısına dönüştürme | P0 | 1 |

**Literatür örnekleri (strateji planından):**

- Anthropic, *Building Effective Agents*: karmaşıklığı ancak ölçülebilir faydayla artır; şeffaflık ve basit araç sınırları.
- Google DORA 2025: AI katkısı, gelişim sisteminin güçlü/zayıf yönlerini büyütebilir; süreç/güvenlik/geri bildirim birlikte ölçülmeli.
- Anthropic, *Quantifying infrastructure noise in agentic coding evals* (5 Şubat 2026): farklı test kaynakları benchmark farkını tek başına etkileyebilir.
- OpenAI, *Why we no longer evaluate SWE-bench Verified* (23 Şubat 2026) ve *Separating signal from noise in coding evaluations* (8 Temmuz 2026): veri kontaminasyonu ve hatalı testler karşılaştırmayı bozabilir.
- Playwright Trace Viewer ve video dokümantasyonu; TestSprite CLI/MCP dokümanları: mevcut doğrulama ve raporlama araçlarından yararlan.

**Raporlama:** Başarı oranı, test/kanıt boşluğu, güvenlik ihlali, görev başına maliyet, end-to-end süre, insan müdahalesi, retry, kullanım oranı; baseline ve hedef birlikte gösterilmeli. “Daha güvenli/daha hızlı” pazarlama iddiası yalnızca kapsam ve karşılaştırma yöntemi açık deneyle kurulabilir.

### 12.1 Ayrıntılı görevler — Beta.8

### B8-01 — Rakip sürüm ve özellik yeniden doğrulaması [P0]

**Referans:** 16+6 ana havuz.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Araştırma/test işi (strateji):** Güncel rakip sürüm/plan/özellik envanteri yeniden doğrulama
> - **Somut çıktı (strateji):** Tarihli ve kanıtlı matrix; status = shipped/beta/paid/unknown

#### B8-01.01 — Kaynak tarihlendirmeli dış rekabet audit’i

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B6-11.02`, `B7-04.02`.
- **Mimari / modül sınırı:** docs/COMPETITOR_CAPABILITY_MATRIX.md; version snapshot audit.
- **Uygulama:** B5/B6 sonrası rakiplerin dağıtılan sürümlerini kaynak, plan, platform, ücret ve release date ile tekrar gözden geçir; Respected testlerini CAP-ID’ye bağla; belgesel özellik için bağımsız deney yoksa unverified yaz.
- **Test senaryoları:** Stale broken source, feature-only-on-paid, roadmap mistaken shipped, untested Respected claim.
- **Ölçülebilir kabul:** P0 satırlarının %100’ünde tarihli referans/test var; eski kaynak uyarılır; açık istisnalar listelenir.
- **Tamamlanma kanıtı:** Dated audit PDF/Markdown + CAP-ID diff + reproducibility links.

### B8-02 — Araştırma literatür haritası [P0]

**Referans:** Anthropic, OpenAI, DORA, veri güvenilirliği makaleleri.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Araştırma/test işi (strateji):** Literatür haritası: agent harness, evaluation, context, güvenlik, yazılım kalite ve UX
> - **Somut çıktı (strateji):** Her makale için hipotez, tehdit, uygulanabilir deney, karar kaydı

#### B8-02.01 — Hipotez, deney ve karar kayıtları

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B8-01.01`.
- **Mimari / modül sınırı:** docs/research/ (öneri); ADR/evidence linkleri.
- **Uygulama:** Harness, agent routing, context, sandbox, eval contamination, human approval, DORA ve UX kaynaklarını sistematik etiketle; her makale için bulgu→ölçülebilir hipotez→gerekli deney→reddetme koşulu oluştur.
- **Test senaryoları:** Kaynak tarihi/versiyonu eksikliği, korelasyonun nedensellik sayılması, iddia için uygun olmayan ölçüm.
- **Ölçülebilir kabul:** En az 12 yüksek ilgili kaynak için citation+hipotez+deney planı; kanıtsız performans iddiası yok.
- **Tamamlanma kanıtı:** Literature ledger + ADR list + citations.

### B8-03 — Adil ajan ve rakip benchmark koşuları [P0]

**Referans:** OrchestratorInc, AgentSpace, Orca, direct CLIs.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Araştırma/test işi (strateji):** Eşit şartlarda doğrudan agent / Respected / seçili rakip kıyasları
> - **Somut çıktı (strateji):** Aynı model, görev, commit, donanım, bütçe; güven aralıkları ve ham koşular

#### B8-03.01 — Çok tekrarlı eş koşullu performans deneyi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B8-02.01`, `B5-11.01`, `B7-03.02`.
- **Mimari / modül sınırı:** Real agent eval harness, environment manifest, statistical report.
- **Uygulama:** Aynı görev/commit/CLI model sürümü/CPU RAM/bütçe/test; randomize execution order ve yeterli tekrar, p50/p95 süre, başarı, maliyet, fail mode ve müdahale ölç.
- **Test senaryoları:** Resource skew, test flake, benchmark leakage, unavailable competitor config, incompatible pricing.
- **Ölçülebilir kabul:** Deney protokolü ön kayıtlı; en az 10 görev × 3 tekrar × karşılaştırılan kol (uygulanabilirse); sonuçlar güven aralığı ve kısıt içerir.
- **Tamamlanma kanıtı:** Raw run manifest + env snapshot + analysis report.

### B8-04 — Gizli ve bağımsız doğrulanmış görev seti [P0]

**Referans:** SWE-bench değerlendirme sorunları.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Araştırma/test işi (strateji):** Gizli ve insan onaylı görev setleri
> - **Somut çıktı (strateji):** Kontaminasyon riski azaltılmış, puanlama rubric'i denetlenmiş görevler

#### B8-04.01 — Holdout task dataset ve test hakemliği

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B8-02.01`.
- **Mimari / modül sınırı:** Private eval fixtures + independent scorer + contamination policy.
- **Uygulama:** Yeni gerçek bug/senaryo setlerini sabit commitlerle derle; çözümleri ve gizli testleri ajan promptuna sızdırma; test rubric’i insan hakemine doğrulat.
- **Test senaryoları:** Leakage, false negative, flaky test, hidden preinstalled fix, inconsistent seed.
- **Ölçülebilir kabul:** Gizli görevlerin tümünde test kararlılığı ön koşul; en az 2 bağımsız reviewer/uzlaşı prosedürü raporlu.
- **Tamamlanma kanıtı:** Holdout manifest + scorer validation + audit notes.

### B8-05 — Gerçek kullanıcı ve kullanım araştırmaları [P0]

**Referans:** Vibe coder, profesyonel geliştirici, küçük ekip.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Araştırma/test işi (strateji):** Gerçek kullanıcı çalışmaları (solo vibe coder, profesyonel dev, küçük ekip)
> - **Somut çıktı (strateji):** Task success, time-to-first-result, müdahale, SUS/UX, geri dönüş/tercih nedenleri

#### B8-05.01 — Kullanıcı görev başarısı ve tercih çalışması

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B8-01.01`, `B7-02.02`.
- **Mimari / modül sınırı:** UX research scripts, consent/privacy, product event anonymization opt-in.
- **Uygulama:** En az 3 persona için onboarding, hata düzeltme, PR teslimi ve kanıt inceleme deneyleri; blind/order-balanced rakip kıyası mümkünse uygula.
- **Test senaryoları:** Observer bias, priming, mismatched expertise, wrong baseline, consent withdrawal.
- **Ölçülebilir kabul:** Önceden seçilen en az 12 kullanıcı/temsilî oturum hedefi; tercih nedenleri ve başarısızlıklar açık, anket skoru tek ölçüt değil.
- **Tamamlanma kanıtı:** Consent-safe task recordings + outcomes table + bias limitations.

### B8-06 — Bağımsız güvenlik saldırı denetimi [P0]

**Referans:** Sandbox, prompt injection, MCP, remote/mobile.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Araştırma/test işi (strateji):** Güvenlik red team / sandbox / prompt injection / MCP riskleri
> - **Somut çıktı (strateji):** Saldırı matrisi, sıfır kritik açık, yeniden çalıştırılabilir repro

#### B8-06.01 — Threat-driven red-team ve güvenlik regresyonu

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B8-04.01`, `B6-11.01`, `B7-07.02`.
- **Mimari / modül sınırı:** Red-team harness + pen-test artifacts + sandbox gates.
- **Uygulama:** AppContainer/remote OS isolation, GUI approve spoof, MCP injection, malicious tool output, webhook replay, secrets exfiltration, path traversal; bulgu önceliklendirme.
- **Test senaryoları:** OS/network bypass attempts, compromised renderer, command injection, trust escalation, tamper evidence.
- **Ölçülebilir kabul:** Kritik exploit için açığın kapatıldığı yeniden gösterilir; release mandatory suite skip=0; hiçbir bilinen kritik açık açık kalmaz.
- **Tamamlanma kanıtı:** Attack matrix + repro scripts + independent re-test signoff.

### B8-07 — Performans, maliyet, bellek ve a11y optimizasyonu [P1]

**Referans:** DORA/harness/UX performans literatürü.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Araştırma/test işi (strateji):** Performans, token/maliyet, crash, memory leak, network ve UI a11y
> - **Somut çıktı (strateji):** Önce/sonra metrikleri; A/B/rollback; regressions list

#### B8-07.01 — Önce/sonra ölçümlü optimizasyon ve geri alma

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B8-03.01`, `B8-05.01`.
- **Mimari / modül sınırı:** Profiling dashboards, benchmarks, feature flag/rollback.
- **Uygulama:** İlk açılış, UI response, event journal, session memory, API latency, token/accepted-task cost, crash-free sessions ve a11y; değişiklik başına A/B ölç.
- **Test senaryoları:** Large event bursts, memory leaks, warm/cold startup, model drift, placebo gains, flaky UI tests.
- **Ölçülebilir kabul:** Her kabul edilen optimizasyonda baseline→delta→regresyon ölçüsü; kötüleşen/yetersiz hipotez geri alınır.
- **Tamamlanma kanıtı:** Before-after metrics + benchmark provenance + rollback ADR.

### B8-08 — Araştırma sonucunu kalıcı kalite kapısına dönüştürme [P0]

**Referans:** Tüm araştırmalar.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **Araştırma/test işi (strateji):** İyileştirme backlog ve yeniden test
> - **Somut çıktı (strateji):** Her optimizasyon için delta, baseline ve etkisizse geri alma kararı

#### B8-08.01 — Karar, düzeltme backlog’u ve yeniden deney

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B8-01.01`, `B8-03.01`, `B8-05.01`, `B8-06.01`, `B8-07.01`.
- **Mimari / modül sınırı:** Docs/research conclusions, roadmap issue links, permanent CI/evals.
- **Uygulama:** Her negatif/pozitif ölçümü öncelikli issue’ya bağla, değişiklik sonrası aynı veya holdout testte yeniden değerlendir; yarış performansını değil kullanıcı doğruluğunu optimize et.
- **Test senaryoları:** Fix regresses unrelated test, changed hardware invalidates baseline, missing raw data.
- **Ölçülebilir kabul:** Yüksek etkili bulguların %100’ünün karar/issue/karşı deney kaydı var; Beta.9 kritik backlog’u açık.
- **Tamamlanma kanıtı:** Research gate report + improvement backlog + rerun evidence.

### 12.2 Beta.8 araştırma ve deney protokolü `[ÖNERİ]`

Bu protokol, `B8-01…B8-08` kartlarının (ve Beta.8 yayın kapısının) nasıl uygulanacağını ayrıntılandırır. **Kaynak planlarda bulunmayan** sayısal eşikler, istatistiksel yöntemler ve örneklem büyüklükleri burada `[ÖNERİ]` veya `[AÇIK KARAR]` olarak işaretlidir; kaynaklardaki sayılar (≥10 görev × ≥3 tekrar, ≥12 kaynak, ≥12 kullanıcı/oturum, ≥2 hakem) olduğu gibi korunmuştur.

**Başlama koşulu (kaynak):** Gerçek kullanıcılardan yeterli senaryo ve hata/performans kanıtı toplandıktan sonra başlanır. Bu faz ürünün bütün özelliklerini *ölçülü şekilde* iyileştirir; ilk günden ölçülebilir kabul kriteri, güvenlik regresyonu, performans bütçesi ve kanıt bağlantısı her paketin kendisinde bulunur (ölçüm Beta.8'de **başlamaz**, geniş ölçekli bağımsız değerlendirme ve düzeltme dönemi olur).

#### A. Akademik / mühendislik literatür incelemesi (`B8-02.01`)

**Kayıt şablonu (her kaynak için bir satır):** `Kaynak (başlık, yazar/kurum, tarih/sürüm, URL) → Bulgu → Respected'ta ölçülebilir hipotez (H) → Gerekli deney → Reddetme koşulu → Karar kaydı (ADR bağlantısı) → Tehdit/geçerlilik sınırı`. Korelasyonun nedensellik sayılması, kaynak tarihi/sürüm eksikliği ve iddia için uygun olmayan ölçüm kabul edilmez (kart test senaryoları).

**Kaynak planlarda adı geçen kaynaklar ve Respected'a aktarımı:**

| # | Kaynak (URL) | Kaynakta belirtilen çıkarım | Hipotez taslağı `[ÖNERİ]` | Deney / ölçüm | Reddetme koşulu `[ÖNERİ]` |
|---|---|---|---|---|---|
| L1 | Anthropic, *Building Effective Agents* (https://www.anthropic.com/engineering/building-effective-agents) | Karmaşıklığı ancak ölçülebilir faydayla artır; şeffaflık ve basit araç sınırları | H1: Orkestrasyon katmanları (DAG, MAF, team handoff) basit tek-ajan koşuya göre kabul edilen görev başarısını artırır | `B8-03.01` direct vs orchestrated, aynı model/görev | Orchestrated kol başarıda direct'i anlamlı biçimde geçmiyorsa karmaşıklık gerekçesiz sayılır (FIX-02 başlangıç verisi: orchestrated %70 < direct %96,7) |
| L2 | Google DORA 2025 (https://dora.dev/research/2025/dora-report/) | AI katkısı gelişim sisteminin güçlü/zayıf yönlerini büyütebilir; süreç/güvenlik/geri bildirim birlikte ölçülmeli | H2: Kanıt+onay disiplini teslim kalitesini (yeniden iş, geri alma) iyileştirir | `B8-05.01` kullanıcı çalışması: yeniden iş / geri alma / müdahale sayısı | Süreç yükü (insan müdahalesi) kazancı aşıyorsa kapı sadeleştirilir |
| L3 | Anthropic, *Quantifying infrastructure noise in agentic coding evals* (5 Şubat 2026) (https://www.anthropic.com/research/infrastructure-noise) | Farklı test altyapısı benchmark farkını tek başına etkileyebilir | H3: Gözlenen kol farkı, ortam gürültüsünden (CPU/RAM/zaman aşımı) büyüktür | `B8-03.01` ortam manifesti, aynı donanım, kaynak limitleri sabit; tekrarlar arası varyans raporu | Fark, tekrarlar arası varyansın içinde kalıyorsa "fark yok" olarak raporlanır |
| L4 | OpenAI, *Why we no longer evaluate SWE-bench Verified* (23 Şubat 2026) (https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/) | Veri kontaminasyonu ve hatalı testler karşılaştırmayı bozabilir | H4: Holdout görev başarısı, kamuya açık görev başarısından belirgin düşük değildir | `B8-04.01` holdout seti, sızıntı denetimi | Holdout başarısı kamuya açık setten belirgin düşükse kamuya açık sonuçlar tek başına kullanılamaz |
| L5 | OpenAI, *Separating signal from noise in coding evaluations* (8 Temmuz 2026) (https://openai.com/index/separating-signal-from-noise-coding-evaluations/) | Hatalı/flaky testler ve gürültü karşılaştırmayı bozabilir | H5: Flaky test oranı kabul edilebilir eşiğin altındadır ve puanlama rubric'i hakemler arası tutarlıdır | `B8-04.01` test kararlılığı ön koşulu, ≥2 bağımsız reviewer uzlaşısı | Kararsız testli görev sete alınmaz |
| L6 | Playwright Trace Viewer / video dokümantasyonu (https://playwright.dev/docs/trace-viewer ; https://playwright.dev/docs/videos) ve TestSprite dokümanları (https://www.testsprite.com/solutions/mcp ; https://github.com/TestSprite/testsprite-cli) | Mevcut doğrulama/raporlama araçlarından yararlan | H6: Trace/video kanıtı, kullanıcının kanıt incelemesini hızlandırır/güveni artırır | `B8-05.01` kanıt inceleme görevi, kanıtlı vs kanıtsız | Süre veya doğruluk iyileşmiyorsa varsayılan görünümden çıkarılır |

**[AÇIK KARAR] — kaynak sayısı:** `B8-02.01` kabul kriteri en az 12 yüksek ilgili kaynak ister; kaynak planlar yalnız yukarıdaki 6 kaynak grubunu (5 makale/rapor + araç dokümantasyonu) adlandırır. Kalan kaynaklar aşağıdaki konu başlıklarından seçilmelidir (kart metni): **harness, agent routing, context, sandbox, eval contamination, human approval, DORA ve UX.** Kaynak adlarını tahmin ederek doldurma; B8-02.01 başında sistematik arama yapılıp literatür defterine (ledger) tarihli eklenir.

#### B. Karşılaştırma deneyi tasarımı (`B8-03.01`)

- **Kollar:** (1) doğrudan ajan CLI (aynı model/sürüm), (2) Respected (orchestrated; gerekirse routing/context/team varyantları ayrı kollar), (3) seçili rakipler — yalnızca **ulaşılabilir**, lisans/koşulları izin veren ve aynı model/bütçe ile yapılandırılabilenler (Gate: "ulaşılabilir rakiplerde"). Yapılandırılamayan rakip için tahmin yapılmaz; "karşılaştırılamaz" ve nedeni raporlanır.
- **Sabit tutulanlar (kaynak):** aynı görev, aynı commit, aynı CLI model sürümü, aynı CPU/RAM, aynı bütçe, aynı test. **Rastgeleleştirme:** yürütme sırası randomize.
- **Örneklem (kaynak):** en az 10 görev × 3 tekrar × karşılaştırılan kol (uygulanabilirse); sonuçlar güven aralığı ve kısıtlarla.
- **Ölçümler (kaynak):** başarı, p50/p95 süre, maliyet, fail mode, insan müdahalesi; ayrıca güvenlik ihlali, test/kanıt boşluğu, retry, kullanım oranı. Bilinmeyen maliyet/token `unknown` kalır (0 yazılmaz).
- **İstatistik `[ÖNERİ]`:** Başarı oranı için görev başına eşleştirilmiş analiz ve güven aralığı (ör. Wilson aralığı / eşleştirilmiş bootstrap); süre için medyan ve p95 bootstrap aralığı; kol farkı için görev düzeyinde eşleştirilmiş test. `[AÇIK KARAR]`: yöntem seçimi ve anlamlılık eşiği ön kayıtta sabitlenir; sonuç görüldükten sonra değiştirilmez.
- **Ön kayıt (kaynak: "deney protokolü ön kayıtlı") içeriği `[ÖNERİ]`:** hipotezler, kol tanımları, görev listesi ve commit SHA'ları, model/CLI sürümleri, donanım ve kaynak limitleri, zaman aşımı, tekrar sayısı, geçersiz koşu kuralları, analiz planı, durdurma/dışlama kuralları.
- **Geçersiz koşu kuralları (depodaki FIX-02 deneyiminden):** Sağlayıcı kota/limit mesajı, ortam hatası veya sızıntı tespit edilen koşu `INVALID` olarak ayrı kaydedilir ve istatistikten çıkarılır; parti ilk kota işaretinde durur; `bench.validate` benzeri doğrulayıcı (durum complete, kind real, sızıntı yok, geçersiz koşu yok, ölçülmeyen değer 0 yazılmadı) rapor yayınlanmadan koşar. Kapsam dışı: test sırasında kullanıcı kotasını ve maliyetini onaysız harcamak — ücretli/LLM-yoğun her parti için önceden kullanıcı onayı alınır.
- **Raw veri:** Ham koşu manifesti, ortam anlık görüntüsü, analiz betiği ve rapor birlikte saklanır (kart kanıtı: raw run manifest + env snapshot + analysis report).

#### C. Gizli / bağımsız görev seti (`B8-04.01`)

1. **Derleme:** Yeni gerçek bug/senaryo setleri **sabit commit**lerle derlenir; çözümler ve gizli testler ajan prompt'una sızdırılmaz.
2. **Kontaminasyon politikası:** Görev kaynağı, tarih ve çözümün kamuya açıklık durumu kayıt altına alınır; önceden kurulu çözüm (hidden preinstalled fix) kontrolü; tutarsız seed kontrolü.
3. **Hakemlik:** Test rubric'i insan hakemine doğrulatılır; en az 2 bağımsız reviewer/uzlaşı prosedürü raporlanır; flaky testler seti dışlar.
4. **Doğrulama:** Başlangıç durumunda test başarısız, altın çözümde geçmeli (depo `ARCHITECTURE.md` §9 değerlendirme koşucusu kuralıyla aynı: iki koşul doğrulanmadan görev `passed` sayılmaz).

#### D. Gerçek kullanıcı çalışmaları (`B8-05.01`)

- **Persona'lar (kaynak):** solo vibe coder, profesyonel geliştirici, küçük ekip.
- **Görevler (kaynak):** onboarding, hata düzeltme, PR teslimi, kanıt inceleme; mümkünse kör / sıra dengeli rakip kıyası.
- **Hedef (kaynak):** önceden seçilen en az 12 kullanıcı/temsilî oturum; anket skoru tek ölçüt değil.
- **Ölçümler (kaynak):** task success, time-to-first-result, müdahale sayısı, SUS/UX, geri dönüş/tercih nedenleri.
- **Etik ve gizlilik (kaynak: consent/privacy, opt-in anonim ürün olayı):** Onam, geri çekme hakkı, kayıtların anonimleştirilmesi; opt-in dışında proje verisi dışarı çıkmaz.
- **Önyargı kontrolleri (kaynak test senaryoları):** gözlemci yanlılığı, priming, uyumsuz uzmanlık, yanlış baseline, onam geri çekme. `[AÇIK KARAR]`: katılımcı edinimi, ücretlendirme, kıyas (rakip) uygulamalarının kurulumu.

#### E. Güvenlik saldırı denetimi (`B8-06.01`)

Saldırı yüzeyi (kart + depo `THREAT_MODEL.md`): AppContainer/remote OS izolasyonu, GUI approve spoof, MCP injection, kötü amaçlı tool çıktısı, webhook replay, secret exfiltration, path traversal; ayrıca ele geçirilmiş renderer, komut enjeksiyonu, güven yükseltme, tamper kanıtı, OS/ağ bypass denemeleri. Çıktı: saldırı matrisi + yeniden çalıştırılabilir repro betikleri + bağımsız yeniden test onayı; kritik exploit için "kapatıldı" yeniden gösterilir; zorunlu suite `skip=0`; bilinen kritik açık kalmaz. `[AÇIK KARAR]`: denetimin bağımsızlık derecesi (iç ekip dışı gözden geçiren / harici firma) ve kapsamı.

#### F. Performans, maliyet, bellek, a11y optimizasyonu (`B8-07.01`)

Ölçülen metrikler (kart): ilk açılış, UI yanıt, event journal, oturum belleği, API gecikmesi, token/accepted-task maliyeti, crash-free session, a11y. Kural: **her optimizasyon için baseline → delta → regresyon**; değişiklik başına A/B; plasebo kazanç, ısınma/soğuk başlangıç, model drift ve flaky UI testi kontrolü; kötüleşen veya yetersiz hipotez geri alınır. `[AÇIK KARAR]`: sayısal performans bütçeleri (açılış süresi, UI yanıt süresi, crash-free oranı vb.) kaynak planda yoktur; Beta.8'in ilk ölçümlerinden sonra, optimizasyondan **önce** sabitlenir ve V1-GATE'e girer (§15.8).

#### G. Karar kaydı ve kalıcı kapıya dönüşüm (`B8-08.01`)

Her ölçüm (pozitif/negatif) → önceliklendirilmiş issue → değişiklik → aynı veya holdout testte yeniden deney. Kullanıcı doğruluğu optimize edilir, "yarış performansı" değil. Yüksek etkili bulguların %100'ü için karar/issue/karşı deney kaydı vardır; Beta.9 kritik backlog'u açıktır. Kalıcı CI/eval kapılarına dönüşen testler `docs/research/` ve ADR bağlantılarıyla izlenir.

**Raporlama (kaynak):** Başarı oranı, test/kanıt boşluğu, güvenlik ihlali, görev başına maliyet, end-to-end süre, insan müdahalesi, retry, kullanım oranı; baseline ve hedef birlikte gösterilir. "Daha güvenli/daha hızlı" pazarlama iddiası yalnızca kapsam ve karşılaştırma yöntemi açık deneyle kurulabilir.

---

## 13. Beta.9 — Stabilization & Bug Fix (Fix-Only)

### 13.0 Sürüm hedefi ve kapsamı

**Önkoşul:** Yeni özellik geliştirmenin dondurulması; Beta.8 araştırmasından gelen bütün kritik ürün değişikliklerinin birleşmiş ve tekrar ölçülmüş olması.

- **Beta.9:** Feature freeze, güvenlik/hata/donanım/platform regresyonu ve RC.

**Ana iş indeksi — Beta.9**

| Ana iş | Başlık | Öncelik | Alt görev |
|---|---|---|---:|
| `B9-01` | Feature freeze ve change control | P0 | 1 |
| `B9-02` | P0/P1 bug ve güvenlik kapatma | P0 | 1 |
| `B9-03` | Desteklenen platform/ajan regresyonu | P0 | 1 |
| `B9-04` | Kurulum, update, migration ve rollback | P0 | 1 |
| `B9-05` | UX bugları, a11y ve dokümantasyon | P1 | 1 |
| `B9-06` | SBOM, lisans, gizlilik ve imzalı dağıtım | P0 | 1 |
| `B9-07` | RC, pilot, hotfix ve destek disiplini | P0 | 1 |

**Hata sürümleri ve resmî sürüm (strateji planından):**

- Beta.9'dan sonra gerekirse `beta.9.1`, `beta.9.2` gibi hata düzeltme sürümleri yayımla.
- Ardından `v1.0.0-rc.1`, `rc.2` vb. release candidate aşaması.
- **“Sıfır bug” kelimenin tam anlamıyla doğrulanamaz.** Yayın kapısı: sıfır açık P0/P1, kritik negatif güvenlik testleri %100 geçiş, veri kaybı sıfır, bilinen P2/P3 hataların gerekçeli ve görünür kayıtları, gerçek kullanıcı kabulü.
- RC'nin yalnızca adlandırma değil, stabil kod dondurma ve tekrar üretilebilir dağıtım testi olduğunu doğrula.

### 13.1 Ayrıntılı görevler — Beta.9

### B9-01 — Feature freeze ve change control [P0]

**Referans:** Release engineering.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş (strateji):** Feature freeze / sadece bug, güvenlik, a11y, veri kaybı ve uyumluluk fix
> - **Yayın şartı (strateji):** Yeni özellik yok; istisna yalnız kritik güvenlik ve yazılı karar

#### B9-01.01 — Sürüm dondurma ve exception kayıtları

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B8-08.01`.
- **Mimari / modül sınırı:** Branch protection + release issue policy.
- **Uygulama:** Yeni özellik PR’larını dondur, yalnız bug/security/data/a11y/compatibility fix al; istisna için explicit ADR ve risk/release gate.
- **Test senaryoları:** Yeni feature PR, önemli refactor etiketi, emergency fix, unreviewed dependency update.
- **Ölçülebilir kabul:** Freeze sonrası onaysız yeni özellik birleşimi sıfır; istisnalar karar ve test kaydı taşıyor.
- **Tamamlanma kanıtı:** Protected branch configuration + change log.

### B9-02 — P0/P1 bug ve güvenlik kapatma [P0]

**Referans:** All runtime/GUI/providers.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş (strateji):** P0/P1 hata ve güvenlik açıklarını sıfırlama
> - **Yayın şartı (strateji):** Açık P0/P1 = 0; fail-closed süreç ve veri koruma testleri geçiyor

#### B9-02.01 — Kritik sorunları kök neden ve regresyonla kapatma

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B9-01.01`, `B8-06.01`.
- **Mimari / modül sınırı:** Issue tracker and fault injection suite.
- **Uygulama:** Her P0/P1 hata için root cause, minimal repro, negatif/pozitif otomatik test, güvenlik/yetki analizini yap; workaround belgelemek close değildir.
- **Test senaryoları:** Reopened bug, sandbox denial, stale evidence, chain-of-errors, duplicate apply.
- **Ölçülebilir kabul:** Açık P0/P1 = 0; regresyon testleri gerçek ortamda geçiyor; kritik test skip=0.
- **Tamamlanma kanıtı:** Issue close audit + SHA-linked regression run.

### B9-03 — Desteklenen platform/ajan regresyonu [P0]

**Referans:** Windows/macOS/Linux ve CLI matrix.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş (strateji):** Regression matrix: Windows ve resmi desteklenen diğer OS'ler, bütün agent adaptörleri
> - **Yayın şartı (strateji):** Desteklenen kombinasyonlarda zorunlu CI e2e; skip=0 kritik kapılar

#### B9-03.01 — E2E support matrix ve release doğrulama

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B9-02.01`, `B6-10.02`.
- **Mimari / modül sınırı:** CI matrix real OS + real CLI adapters; no misleading support claims.
- **Uygulama:** Desteklenen OS×CLI×core journey için smoke/E2E ve negatif sandbox; unsupported durumları ürün sayfasında açıklanır.
- **Test senaryoları:** OS version changes, missing sandbox, unauthenticated CLI, model update, event replay.
- **Ölçülebilir kabul:** Resmi desteklenen her kombinasyonun gerekli testleri yeşil; kritik matriste skipped=0; unsupported etiketleri doğru.
- **Tamamlanma kanıtı:** OS/CLI compatibility ledger + CI artifacts.

### B9-04 — Kurulum, update, migration ve rollback [P0]

**Referans:** Packaging/runtime lifecycle.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş (strateji):** Installer/update/migration/rollback, bozuk oturum kurtarma
> - **Yayın şartı (strateji):** Gerçek eski kullanıcı verisi fixture, kesintili güncelleme, sıfır veri kaybı

#### B9-04.01 — Bozuk güncelleme ve eski veri senaryoları

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B9-02.01`, `B3-09.03`.
- **Mimari / modül sınırı:** Installer + schema migration + supervisor quiesce.
- **Uygulama:** Beta.1’den en son betaya gerçek fixture, kesilen migration, disk full, aktif görev sırasında upgrade, uninstaller ve rollback.
- **Test senaryoları:** Power loss, corrupted artifact, half-written settings, engine/desktop mismatch, active work.
- **Ölçülebilir kabul:** P0 veri kaybı=0; restore testleri yeşil; güvensiz sürüm uyumsuzluğu fail-closed.
- **Tamamlanma kanıtı:** Upgrade/downgrade report + before-after hashes.

### B9-05 — UX bugları, a11y ve dokümantasyon [P1]

**Referans:** Onboarding and standalone desktop.  **Öncelik:** P1.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş (strateji):** Kullanıcı deneyimi tamamlama: hata mesajları, erişilebilirlik, onboarding, dokümantasyon
> - **Yayın şartı (strateji):** Temsilî kullanıcılar çekirdek akışı bağımsız tamamlar

#### B9-05.01 — Kullanıcı başarı senaryosu düzeltmeleri

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `B8-05.01`, `B9-01.01`.
- **Mimari / modül sınırı:** UI polish, error taxonomy, docs/help, internationalization.
- **Uygulama:** İlk çalıştırma, program kapanıp açılma, failure explain, help, keyboard/a11y, TR/EN mesaj ve privacy kaynaklı bugları düzelt.
- **Test senaryoları:** Low DPI, narrow window, screen reader, offline and revoked permissions, human task failure.
- **Ölçülebilir kabul:** Gerçek test katılımcıları çekirdek ilk görev akışını rehbersiz tamamlayabilir (hedef ve örneklem raporlanır); kritik a11y blocker sıfır.
- **Tamamlanma kanıtı:** Usability retest + a11y audit + help doc diff.

### B9-06 — SBOM, lisans, gizlilik ve imzalı dağıtım [P0]

**Referans:** Supply chain.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş (strateji):** Güvenlik/bağımlılık/lisans envanteri, SBOM, imzalı dağıtım
> - **Yayın şartı (strateji):** Tüm zorunlu artefaktlar imzalı; lisans yükümlülükleri karşılanır

#### B9-06.01 — Yayın artefaktı ve lisans bütünlüğü

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B9-04.01`.
- **Mimari / modül sınırı:** SBOM/provenance, Authenticode, dependency license audit.
- **Uygulama:** Üçüncü taraf bileşen, Playwright browser binaries, native STT, MCP adaptör lisansı; SBOM, güvenlik bildirimleri, güvenilir imza ve dağıtım hash.
- **Test senaryoları:** Unsigned installer, tampered package, revoked cert, mismatched SBOM, disallowed license.
- **Ölçülebilir kabul:** Yayın için gerekli artefaktlar üretildi/doğrulandı; bilinmeyen lisans blocker olarak kalır.
- **Tamamlanma kanıtı:** SBOM + verify output + signing audit.

### B9-07 — RC, pilot, hotfix ve destek disiplini [P0]

**Referans:** Release candidates.  **Öncelik:** P0.

> **Strateji planındaki kayıt** (kaynaktan aktarıldı):
>
> - **İş (strateji):** Sürüm adayı, pilot ve hotfix disiplini
> - **Yayın şartı (strateji):** Kanıtlı RC raporu, geri alınabilir dağıtım, destek/incident süreci

#### B9-07.01 — Sürüm adayı ve geri dönüş tatbikatı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B9-02.01`, `B9-03.01`, `B9-04.01`, `B9-05.01`, `B9-06.01`.
- **Mimari / modül sınırı:** RC manifest + canary deployment + incident response docs.
- **Uygulama:** v1.0.0-rc.1 pilot, crash/bug feedback, rollback, support triage, freeze; başarısız RC sonrası rc.2 ve yeniden test.
- **Test senaryoları:** Signed release mismatch, bad update, late P0 bug, rollback after active worker.
- **Ölçülebilir kabul:** Pilot kabul ve release sign-off olmadan v1.0 tag yok; açık P0/P1 sıfır.
- **Tamamlanma kanıtı:** RC report + pilot sample + rollback drill evidence.

### 13.2 Beta.9 süreç tanımları `[ÖNERİ]`

**Özellik dondurma (`B9-01`):** Başlangıç noktası `B8-08.01` çıktısıdır. Dondurma sonrası yalnız bug, güvenlik, veri kaybı, a11y ve uyumluluk düzeltmesi birleşir; yeni özellik PR'ı reddedilir. İstisna: kritik güvenlik; **yazılı karar (ADR) + risk + yayın kapısı etkisi** şart. Dal korumasıyla (protected branch) uygulanır ve onaysız yeni özellik birleşimi sıfır olmalıdır.

**Hata önem sınıfları `[ÖNERİ]` (kaynak yalnız "P0/P1/P2/P3" der, tanım vermez):**

| Sınıf | Tanım `[ÖNERİ]` | Yayın kuralı (kaynak) |
|---|---|---|
| P0 | Veri kaybı/bozulması, güvenlik sınırı aşımı (sandbox, onay, imza), yanlış apply/PR, çekirdek akışı tamamen engelleyen hata | Açık P0 = 0 |
| P1 | Çekirdek kullanıcı yolculuğunu önemli ölçüde bozan, geçici çözümü olmayan hata | Açık P1 = 0 |
| P2 | Çekirdek akışı engellemeyen, geçici çözümü olan hata | Gerekçeli ve görünür kayıt |
| P3 | Kozmetik/küçük sorun | Gerekçeli ve görünür kayıt |

`[AÇIK KARAR]`: sınıf tanımlarının ve triage SLA'sının resmî onayı (`V1-03.01` destek politikasıyla birlikte).

**Regresyon süreci (`B9-02/B9-03`):** Her P0/P1 için kök neden, minimal repro, pozitif+negatif otomatik test, güvenlik/yetki analizi; geçici çözüm belgelemek kapatma değildir. Resmî desteklenen OS×CLI×çekirdek yolculuk matrisi gerçek CI'da koşar; kritik matriste `skipped = 0`; desteklenmeyen kombinasyonlar ürün sayfasında doğru etiketlenir.

**Güvenlik testleri:** Zorunlu negatif sandbox/verify matrisi (hosted'da standart kullanıcıyla, skip=0), IPC/webhook/MCP replay, onay taklidi, renderer compromise ve Beta.8 red-team bulgularının regresyonları release kapısına dahildir.

**Hata düzeltme sürümleri ve RC (kaynak):** Gerekirse `beta.9.1`, `beta.9.2`…; ardından `v1.0.0-rc.1`, `rc.2`…. RC yalnızca adlandırma değil, stabil kod dondurma ve tekrar üretilebilir dağıtım testidir. Başarısız RC → `rc.2` ve yeniden test.

---

## 14. v1.0 — First Stable Release

### 14.0 Sürüm hedefi

- **v1.0:** Release gate kanıtları doğrulanmış ilk kararlı sürüm.

**Ana iş indeksi — v1.0**

| Ana iş | Başlık | Öncelik | Alt görev |
|---|---|---|---:|
| `V1-01` | Final readiness ve yetenek kapsam kararı | P0 | 1 |
| `V1-02` | Kararlı sürüm artefaktı ve yükseltme yolu | P0 | 1 |
| `V1-03` | İlk sürüm izleme ve destek başlangıcı | P1 | 1 |

### 14.1 Çıkış kapısı sözleşmesi (strateji planından, kaynak metin)

**Fonksiyonel kapsam:** `COMPETITOR_CAPABILITY_MATRIX` içinde in-scope P0 %100, P1 ≥%90; tüm bilinçli istisnalar release note'ta açık. P0/P1 kullanıcı yolculukları gerçek ortamda tamamlandı. Bu hedefler politika önerisi; henüz sonuç değildir.

**Güvenlik:** Gerçek OS üzerinde zorunlu sandbox/verify negatif matrisinde `skipped = 0`, başarılı yetkisiz erişim = 0, izin dışı apply/approval = 0; replay/IPC/webhook/MCP testleri geçer.

**Kalite:** Açık P0/P1 bug = 0; veri kaybı/corruption için yüksek öncelikli senaryo = 0; örnekleme dayalı gerçek kullanıcı görevlerinde önceden tanımlanmış başarı eşiği. Crash-free session ve performans bütçesi testlerden önce kararlaştırılır.

**Deneyim:** Temiz kurulumdan testli PR'a, gerektiğinde lokal kanıt ve UI doğrulamasına kadar kullanıcı akışı tamam. Uygulama penceresi kapandığında işlerin durumu doğru kalır. Hub/ücretli servis kurulu değilken çekirdek özellikler çalışır.

**Yayın:** Versioned upgrade, restore, changelog, ilk kullanım rehberi, privacy/security dokümantasyonu, lisanslar, SBOM, installer imzası, izlenebilir release SHA ve rollback planı.

#### v1.0 çıkış kriterlerinin kategori eşlemesi

Kaynak çıkış sözleşmesi (§14.1) aşağıdaki sekiz başlıkta toplanmıştır. Sağ sütun, kaynakta sayısal/nesnel değeri bulunmayan ve **karar verilmesi gereken** noktaları belirtir. Hiçbir kriter bugün sağlanmış değildir.

| Kategori | Ölçülebilir kriter (kaynaktan) | Kanıtlayan görevler / kapılar | Açık karar |
|---|---|---|---|
| **Kapsam** | `COMPETITOR_CAPABILITY_MATRIX` içinde in-scope P0 %100, P1 ≥%90; bilinçli istisnalar release note'ta; P0/P1 kullanıcı yolculukları gerçek ortamda tamamlanmış | `B5-00`, `B5-11`, `B6-11.02`, `B8-01`, `V1-01.01`, `V1-GATE` | Yeni rakip özelliği scope freeze sonrası otomatik blocker olmaz (§5.5) |
| **Güvenlik** | Gerçek OS'te zorunlu sandbox/verify negatif matrisinde `skipped = 0`; başarılı yetkisiz erişim = 0; izin dışı apply/approval = 0; replay/IPC/webhook/MCP testleri geçer | `B3-GATE-02`, `B5-GATE`, `B8-06`, `B9-02`, `V1-GATE` | Bağımsız denetimin derecesi (`B8-06`) |
| **Kalite** | Açık P0/P1 = 0; veri kaybı/corruption senaryosu = 0; gerçek kullanıcı görevlerinde önceden tanımlı başarı eşiği | `B8-05`, `B9-02`, `B9-05`, `B9-GATE` | **Başarı eşiği değeri**, crash-free session hedefi (kaynak: "testlerden önce kararlaştırılır") |
| **Performans** | Performans bütçesi testlerden önce kararlaştırılır; ölçüm baseline→delta | `B8-07`, `B8-08` | **Sayısal bütçeler** (açılış, UI yanıt, bellek, event journal) — kaynakta yok |
| **Veri bütünlüğü** | Veri kaybı = 0; update/rollback ve eski veri fixture'ları geçer; checkpoint/migration bozulursa fail-closed | `B3-02`, `B3-09.02`, `B9-04`, `B9-GATE` | Desteklenen minimum eski sürüm aralığı (beta.1'den itibaren?) |
| **Kurulum / güncelleme** | Versioned upgrade, restore, changelog, ilk kullanım rehberi; imzalı installer, SBOM, izlenebilir release SHA, rollback planı; tekrarlanabilir v1.0.0 artefaktı | `B3-09`, `B9-04`, `B9-06`, `V1-02.01`, `V1-GATE` | Üretim Authenticode sertifikası temini (operasyonel bağımlılık; §3.1) |
| **Kullanıcı kabulü** | Temiz kurulumdan testli PR'a kadar akış; temsilî kullanıcılar çekirdek akışı bağımsız tamamlar; pencere kapanınca iş durumu doğru; Hub/ücretli servis olmadan çekirdek çalışır | `B8-05`, `B9-05.01`, `B9-07`, `V1-GATE` | Örneklem büyüklüğü ve hedef oranı (`B9-05.01`: "hedef ve örneklem raporlanır") |
| **Dokümantasyon / hukuk** | Gizlilik/güvenlik dokümantasyonu, lisanslar, notlar; "daha üstün/daha güvenli/daha ucuz" iddiası yalnız kanıt ölçüsünde | `B9-06`, `V1-02`, `V1-03` | Pazarlama iddia listesinin onayı |

### 14.2 Ayrıntılı görevler — v1.0

### V1-01 — Final readiness ve yetenek kapsam kararı [P0]

**Referans:** Bütün rakip matrisi ve ürün.  **Öncelik:** P0.

#### V1-01.01 — Son yetenek ve kabul kanıtı denetimi

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `B9-07.01`.
- **Mimari / modül sınırı:** Release readiness report; CAP-ID matrix.
- **Uygulama:** Tüm in-scope CAP-ID için test, platform, versiyon, açıklık ve gerekçeli istisna; kritik kullanıcı yolculuklarını final build üzerinde denetle.
- **Test senaryoları:** False verified, old commit test, unsupported platform in store copy, missing evidence.
- **Ölçülebilir kabul:** P0 kapsam %100 verified; P1 hedef ≥%90 veya gerekçeli kabul edilmiş fark; kritik security/approval test skipped=0.
- **Tamamlanma kanıtı:** Final matrix coverage + signed SHA-linked verification report.

### V1-02 — Kararlı sürüm artefaktı ve yükseltme yolu [P0]

**Referans:** Release engineering.  **Öncelik:** P0.

#### V1-02.01 — Tekrarlanabilir v1.0.0 imzalı yayın

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P0.
- **Bağımlılıklar:** `V1-01.01`, `B9-06.01`.
- **Mimari / modül sınırı:** Release manifest, build provenance, installers and rollback assets.
- **Uygulama:** Onaylanmış RC commit’ini immutable build ile paketle, imza/hashes, notes, migration docs, rollback ve ilk kullanım rehberiyle yayımla.
- **Test senaryoları:** Mismatch binary/commit, unsigned asset, download corruption, failed restore.
- **Ölçülebilir kabul:** v1.0.0 artifact + kaynak SHA + SBOM + imza + güncelleme e2e aynı setle doğrulandı.
- **Tamamlanma kanıtı:** Release manifest + offline installer smoke + verification script output.

### V1-03 — İlk sürüm izleme ve destek başlangıcı [P1]

**Referans:** User support, privacy.  **Öncelik:** P1.

#### V1-03.01 — Gizlilik dostu destek/incident akışı

- [ ] **Durum:** Öneri; kod/test kanıtı bekleniyor.
- **Öncelik:** P1.
- **Bağımlılıklar:** `V1-02.01`.
- **Mimari / modül sınırı:** Issue triage SLA policy, optional telemetry opt-in, update notes.
- **Uygulama:** Crash raporunu kullanıcı izinli/anonim; acil güvenlik bildirimi, bilinen P2/P3 sorunlar ve düzeltme yayımlama prosedürünü duyur.
- **Test senaryoları:** Disabled telemetry, offline install, leaked log secrets, urgent security patch, broken update feed.
- **Ölçülebilir kabul:** Hesapsız/local kullanımda support fallback var; P2/P3 kayıtlı; kullanıcı izni yokken proje verisi dışarı çıkmaz.
- **Tamamlanma kanıtı:** Support runbook + post-release smoke + privacy tests.

---

## 15. Sürüm kapıları (release gates)

Her beta sürümünün ayrı bir kapısı vardır. Kapı maddeleri `[ ]` olarak başlar ve **yalnızca gerçek commit SHA, ortam, komut, çıkış kodu ve atlanan test sayısı kaydedilince** işaretlenir; belge veya mock test kanıt sayılmaz. Güvenlik kapıları normal (yükseltilmemiş) Windows kullanıcısında ve gerçek AppContainer ile koşar; `skip`/`xfail` release kanıtı değildir.

### 15.1 Beta.3 yayın kapısı (zorunlu)

- [ ] **B3-GATE-01 — Bağımsız ürün:** Yalnız Orchestrator kurulmuş normal Windows kullanıcısı; kurulum → proje → plan → worker → check → onay → apply; başka uygulama/hesap yok.
- [ ] **B3-GATE-02 — Güvenlik:** Worker ve doğrulama sandbox güvenlik koşuları normal kullanıcıda skip=0; renderer/MCP/worker üzerinden insan onayı taklidi = 0 başarılı saldırı.
- [ ] **B3-GATE-03 — Kalıcılık:** UI öldür / aç; aktif run kaybolmaz; event cursor doğru; sonradan yanlış veya ikinci apply olmaz.
- [ ] **B3-GATE-04 — Interaktif ajan:** En az bir gerçek CLI üzerinde desteklenen mod kanıtlı; unsupported modlar kapalı; hiçbir PTY sandbox fallback yapmaz.
- [ ] **B3-GATE-05 — DAG:** Geçersiz/kapsam çakışmalı planla worker=0; geçerli plan kullanıcı eylemi olmadan başlamaz.
- [ ] **B3-GATE-06 — Paket ve veri:** beta.1 ve beta.2 gerçek fixture migration/rollback; install integrity; yanlış sürümde fail-closed; Authenticode yayın politikası belgeli.
- [ ] **B3-GATE-07 — Kanıt:** Her release artefaktı test ortamı, SHA, koşu zamanı, atlanan test sayısı, geçerli paket digest ile ilişkilendirilmiş.

### 15.2 Beta.4 yayın kapısı (zorunlu/koşullu)

- [ ] **B4-GATE-01:** Smart routing için aynı model/sürüm/fixture/ortamda gerçek ajan benchmark raporu; unknown cost=unknown, kullanıcı explicit ataması korunuyor.
- [ ] **B4-GATE-02:** Team handoff döngüleri, ownership ve limit saldırıları; max-hop exceeded → durdur/escalate, otomatik apply yok.
- [ ] **B4-GATE-03:** Yerel skill/MCP uyumluluk + öneri, başka uygulama veya internet olmadan; keşif ve öneriden kaynaklanan otomatik dosya değişikliği/aktivasyon=0.
- [ ] **B4-GATE-04:** Token/maliyet hesapları fixture tabanlı yeniden hesaplanabilir; bilinmeyen ölçüm 0 değil; kalite regression gate geçer.
- [ ] **B4-GATE-05:** Yerel ses/görsel P1 özelliği etkinleştirildiyse kayıt/share için açık kullanıcı eylemi ve negatif gizlilik testleri geçer; etkin değilse UI bunu destekleniyor demez.
- [ ] **B4-GATE-06:** Circuit breaker ve kurtarma: sınırsız retry=0, double apply=0, güvenlik fail-closed.
- [ ] **B4-GATE-07:** B4-09 remote/mobile varsayılan kapalıdır; araştırma prototipi prod yetkilerine bağlanmaz; Beta.4 için bloke edici değildir.

### 15.3 Beta.5 yayın kapısı (`B5-GATE`)

- [ ] Yerel 5 E2E kullanıcı yolculuğu gerçek CLI/gerçek Windows uygulamasında ve doğru SHA ile tamamlandı.
- [ ] P0 yerel rakip yetenekleri %100 test ve kanıta bağlı; bilinmeyenler hiçbir yerde `verified` değil.
- [ ] Native onay, worker AppContainer, verify network, MCP/IPC negatifleri atlanmadan geçti; yanlış apply ve yanlış PR eşleşmesi sıfır.
- [ ] Tarayıcı testlerinde Playwright adaptörüyle gerçek trace/screenshot provenance, isteğe bağlı ücretli entegrasyon zorunlu değil.
- [ ] Paket yükseltme ve UI crash/reconnect testleri geçti.

### 15.4 Beta.6 yayın kapısı (`B6-GATE`)

- [ ] SSH/remote ve varsa mobil kontrol gerçek cihaz/host pilotunda izin iptalini, yeniden bağlanmayı ve yanlış host korumasını geçti.
- [ ] Cloud, çok kullanıcı, ofis ve ek OS seçenekleri için açık go/no-go; no-go olduğunda özellik kullanıcıya varmış gibi sunulmuyor.
- [ ] Yerel kullanım ağ/hesap/remote olmadan Beta.5 kalitesini koruyor.
- [ ] Rakip matrisindeki in-scope P0 %100; P1 hedef ≥%90 veya gerekçeli açık istisna.
- [ ] Yeni dış sınırların tehdit modeli, gerçek güvenlik testi ve imzalı release kanıtı tamamlandı.

### 15.5 Beta.7 yayın kapısı (`B7-GATE`)

- [ ] Project Doctor, salt-okunur teşhis ve kontrollü düzeltme ile gerçek bozuk proje fixture’larında doğrulandı.
- [ ] Build & Prove gerçek UI/API akışlarını çalıştırdı; görüntü/trace/video gerçekten test edilen commit’e bağlı.
- [ ] Verified Autopilot policy/bütçe/izin sınırını aşamıyor; apply/merge için ayrı açık insan eylemi.
- [ ] Proof Pack başka makinede doğrulanıyor; unknown/fail/not-tested ile verified karışmıyor.
- [ ] Tournament, risk ve recovery yalnız gerçek test, user opt-in ve sınırlandırılmış maliyetle sunuluyor; P1 eksikler açık raporlu.

### 15.6 Beta.8 yayın kapısı (`B8-GATE`)

- [ ] Tarihli rakip matrisi ve araştırma literatür haritası yayımlandı.
- [ ] En az 10 görevlilik, ≥3 tekrarlı eş koşul benchmark (ulaşılabilir rakiplerde) ham sonuçları ve kısıtlarıyla raporlu.
- [ ] Bağımsız/holdout testlerden kontaminasyon, flaky test ve yanlış puanlama etkileri denetlendi.
- [ ] Gerçek kullanıcı çalışmaları ve güvenlik saldırı matrisi tamam; kritik bulgular otomatik issue/yeniden test bağlantılı.
- [ ] Her optimizasyonda baseline, ölçülen delta, regresyon ve gerektiğinde rollback kararı mevcut.

### 15.7 Beta.9 yayın kapısı (`B9-GATE`)

- [ ] Feature freeze aktif; açık P0/P1 bug = **0**; kritik negatif güvenlik testlerinde skipped=0.
- [ ] Gerçekte desteklenen OS/CLI kombinasyonlarının kapsam matrisi ve kullanıcı yolculukları geçti.
- [ ] Veri kaybı/corruption blocker = 0; update/rollback ve eski veri fixture’ları geçti.
- [ ] İmzalı installer, lisans/SBOM, gizlilik, yardım ve destek yolu hazır.
- [ ] RC pilotu ve güvenli geri dönüş tatbikatı geçti; kalan P2/P3 kayıtlı ve kabul edilmiş.

### 15.8 v1.0 yayın kapısı (`V1-GATE`)

- [ ] Son SHA üzerinde P0/P1 kullanıcı yolculukları ve release security evidence tekrar doğrulandı.
- [ ] v1.0.0 artifact/provenance/SBOM/signature/installer ve rollback doğrulandı.
- [ ] Sürüm notları, istisnalar, desteklenen platform ve sağlayıcılar belgeli; daha üstün/daha güvenli/daha ucuz iddiası yalnız kanıt ölçüsünde.
- [ ] Kullanıcı hesabı/başka uygulama/ücretli üçüncü taraf servis gerektirmeden yerel çekirdek çalışıyor.

Kategori bazlı kapsam/güvenlik/kalite/performans/veri bütünlüğü/kurulum/kullanıcı kabulü eşlemesi için bkz. §14.1.

### 15.9 Kapı ilişkileri `[ÖNERİ]`

Her kapı bir öncekinin kapanmış olmasını gerektirir (`B3-GATE` → `B4-GATE` → `B5-GATE` → … → `V1-GATE`). Kart bağımlılıkları kapılara referans verir: `B5-00.01` ← `B4-GATE-01`, `B4-GATE-03`; `V1-01.01` ← `B9-07.01`. Gate maddesi, ilişkili kartların `Tamamlanma kanıtı` kayıtları olmadan işaretlenmez.

---

## 16. Kritik yol, riskler ve rollback

### 16.1 Kritik yol ve bağımlılık kontrolü

**Beta.3 kritik yol:** `B3-00.01 → B3-00.02 → B3-00.03 → B3-01.02 → B3-01.03 → B3-02.01 → B3-02.02 → B3-02.03 → B3-03.03 / B3-04.03 → B3-05.02 → B3-05.03 → B3-05.04 → B3-09.04`. (Bu bir temsili kritik yoldur; ayrıntılı dependency listesi authoritative.)

**Beta.4 kritik yol:** `B3-07.03 + B3-08.02 → B4-03.01 → B4-03.02 + B4-03.03 → B4-03.04`; `B4-04.01 → B4-04.02 → B4-01.03/04`. `B4-09` bu yolun dışında kalır.

**Beta.5→v1.0 en uzun bağımlılık zinciri (kart `Bağımlılıklar` alanlarından hesaplandı) `[ÖNERİ]`:** Aşağıdaki zincirler yalnızca listelenmiş kart bağımlılıklarını izler; kapı ve dış koşullar (kullanıcı çalışması süresi, sertifika temini) dahil değildir.

- v1.0 görevlerinde biten en uzun zincir (35 adım: `B3-00.01` → `B3-00.02` → `B3-00.03` → `B3-01.02` → `B3-01.03` → `B3-02.01` → `B3-02.02` → `B3-02.03` → `B3-06.01` → `B3-06.02` → `B3-06.03` → `B5-04.01` → `B5-04.02` → `B5-11.01` → `B5-11.02` → `B6-00.01` → `B6-00.02` → `B6-01.01` → `B6-02.01` → `B6-02.02` → `B6-11.01` → `B6-11.02` → `B8-01.01` → `B8-02.01` → `B8-04.01` → `B8-06.01` → `B8-08.01` → `B9-01.01` → `B9-02.01` → `B9-04.01` → `B9-06.01` → `B9-07.01` → `V1-01.01` → `V1-02.01` → `V1-03.01`)
- Beta.5 görevlerinde biten en uzun zincir (15 adım: `B3-00.01` → `B3-00.02` → `B3-00.03` → `B3-01.02` → `B3-01.03` → `B3-02.01` → `B3-02.02` → `B3-02.03` → `B3-06.01` → `B3-06.02` → `B3-06.03` → `B5-04.01` → `B5-04.02` → `B5-11.01` → `B5-11.02`)
- Beta.6 görevlerinde biten en uzun zincir (22 adım: `B3-00.01` → `B3-00.02` → `B3-00.03` → `B3-01.02` → `B3-01.03` → `B3-02.01` → `B3-02.02` → `B3-02.03` → `B3-06.01` → `B3-06.02` → `B3-06.03` → `B5-04.01` → `B5-04.02` → `B5-11.01` → `B5-11.02` → `B6-00.01` → `B6-00.02` → `B6-01.01` → `B6-02.01` → `B6-02.02` → `B6-11.01` → `B6-11.02`)
- Beta.7 görevlerinde biten en uzun zincir (21 adım: `B3-00.01` → `B3-00.02` → `B3-00.03` → `B3-01.02` → `B3-01.03` → `B3-02.01` → `B3-02.02` → `B3-02.03` → `B3-06.01` → `B3-06.02` → `B3-06.03` → `B5-04.01` → `B5-04.02` → `B5-11.01` → `B5-11.02` → `B6-00.01` → `B6-00.02` → `B6-07.01` → `B7-03.01` → `B7-05.01` → `B7-05.02`)
- Beta.8 görevlerinde biten en uzun zincir (27 adım: `B3-00.01` → `B3-00.02` → `B3-00.03` → `B3-01.02` → `B3-01.03` → `B3-02.01` → `B3-02.02` → `B3-02.03` → `B3-06.01` → `B3-06.02` → `B3-06.03` → `B5-04.01` → `B5-04.02` → `B5-11.01` → `B5-11.02` → `B6-00.01` → `B6-00.02` → `B6-01.01` → `B6-02.01` → `B6-02.02` → `B6-11.01` → `B6-11.02` → `B8-01.01` → `B8-02.01` → `B8-04.01` → `B8-06.01` → `B8-08.01`)
- Beta.9 görevlerinde biten en uzun zincir (32 adım: `B3-00.01` → `B3-00.02` → `B3-00.03` → `B3-01.02` → `B3-01.03` → `B3-02.01` → `B3-02.02` → `B3-02.03` → `B3-06.01` → `B3-06.02` → `B3-06.03` → `B5-04.01` → `B5-04.02` → `B5-11.01` → `B5-11.02` → `B6-00.01` → `B6-00.02` → `B6-01.01` → `B6-02.01` → `B6-02.02` → `B6-11.01` → `B6-11.02` → `B8-01.01` → `B8-02.01` → `B8-04.01` → `B8-06.01` → `B8-08.01` → `B9-01.01` → `B9-02.01` → `B9-04.01` → `B9-06.01` → `B9-07.01`)

**Bağımlılık denetimi:** Bütün alt görev bağımlılıkları geçerli görev kimliklerine işaret eder; sürümler arası geri (ileri sürüme) bağımlılık yoktur; döngü yoktur (Ek B.6). Beta.4 içinde `B4-01.03/.04` ve `B4-02.03`, daha yüksek numaralı ana işlere (`B4-04`, `B4-08`) bağlıdır; numara sırası yürütme sırası değildir (Ek C, C7).

#### Minimal milestone kontrol listesi

- [ ] **M1:** GUI yetki modeli, Tauri shell, typed IPC ve ilk status ekranı.
- [ ] **M2:** Supervisor + journal + reconnect; UI crash sonrası aktif görev kaybolmaz.
- [ ] **M3:** Gerçek CLI adapter matrix; desteklenen Chat/PTY güvenli; unsupported modlar kapalı.
- [ ] **M4:** Project Board/DAG + evidence + ayrı insan onayı; gerçek run end-to-end.
- [ ] **M5:** Paket/migration/release: temiz Windows, önceki veriler, imza/gate.
- [ ] **M6:** Routing/team/capability recommendation güvenli ve açıklanabilir.
- [ ] **M7:** Usage benchmark + context / ses / görsel / recovery varsa gerçek regresyon verisi.

### 16.2 Risk kaydı, erteleme ve teknik kararlar

**Beta.3/Beta.4 risk kaydı (uygulama planından):**

| Risk | Tetikleyici | Önlem / geri dönüş |
|---|---|---|
| ConPTY + AppContainer uyumsuzluğu | Gerçek interactive worker sandbox testleri geçmiyor | Native Terminal’i disable, sadece doğrulanmış yapılandırılmış event/transcript; korumasız fallback yasak |
| Onay kapısı renderer’dan aşılabilir | Generic invoke/localhost endpoint ulaşılabiliyor | Ayrı native authority, negatif test, disabled apply |
| UI crash iş kaybettiriyor | Renderer process worker’a sahip | Supervisor sahibi değiştir, process tree testleri |
| Güncelleme aktif worker’ı öldürüyor | Installer process/lock clash | Transactional update, quiesce/resume, eski sürüme rollback |
| Skill keşfi kötü amaçlı çalıştırıyor | Probe olarak binary/MCP başlatılması | Read-only parse; verification ayrı izinli, manifest trust gate son söz |
| Routing gereksiz pahalı | Cost=0 veya yanlış model sürümü | Unknown state, shadow mode ve kill switch |
| Çok fazla kapsam | Voice/mobile/pixel-art çok erken | Release gate P0 öncelikli; B4-09 stretch, preview flag-off |
| Log/transkript sır sızdırıyor | Raw stdout/IPC event | Whitelist, bounded store, redaction ve network audit |

**Beta.5→v1.0 yüksek riskli kararlar (strateji planından):**

**Yüksek riskli kararlar:** Mobil + uzak kontrollere kimlik, ağ saldırı yüzeyi ve revocation; cloud'a ödeme/altyapı/veri gizliliği; çapraz platforma OS sandbox eşdeğerliği gerekir. Bunların hiçbirini sadece UI tamamlandı diye `done` sayma.

**B6-04 Cloud kararı:** Kullanıcı için anlamlı ve taşınabilir bir bulut çözümü koşulları sağlanmazsa `deferred with documented exception` olabilir. Böyle bir istisna, ticari iddiada “tüm rakiplerle yüzde yüz aynı özellikler” dememeyi gerektirir.

**Ölçüm ve risk kararları (strateji planından):** bkz. §5.8.

### 16.3 Rollback ve feature flag matrisi

DoD gereği her görev bir rollback veya feature flag kararı taşır. Aşağıdaki tablo, kaynak görev metinlerinde bu konuda **geçen ifadeyi** otomatik olarak gösterir; ifade yoksa karar açıktır. Veri şeması değişen her görevde ayrıca sürümlü migration + gerçek eski sürüm fixture + rollback testi zorunludur (§4.2). Güvenlik için genel kural: kapalı/opt-in varsayılan, fail-closed ve tek ayarla geri alınabilirlik; belirsizlikte özellik **kapalı** kalır.

| Ana iş | Kaynakta rollback / feature flag / güvenli varsayılan ifadesi | Karar durumu |
|---|---|---|
| `B3-00` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B3-01` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B3-02` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B3-03` | "Uygulama adımları: Terminal scrollback, resize, paste safety, 2–4 pane opt-in; model/araç destek durumunu göster." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B3-04` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B3-05` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B3-06` | "Mimari / değişecek alan: Localhost preview policy / isolated webview; varsayılan kapalı; test kodundan gelen HTML güvensiz kabul edilir." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B3-07` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B3-08` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B3-09` | "…değişecek alan: Supervisor version handshake; packaging repair/update rollback; active work handles." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B4-01` | "…değişecek alan: Routing suggestion, actual execution’dan ayrı yazılır; opt-in ve kill switch." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B4-02` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B4-03` | "…aktivasyon; external MCP sadece policy sınırında çalışır; güvenli uninstall/rollback planı." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B4-04` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B4-05` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B4-06` | "Mimari / değişecek alan: OS mic permission, opt-in push-to-talk, local model adapter choice via feasibility test." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B4-07` | "Mimari / değişecek alan: OS screenshot chooser, window/region selection, opt-in only, local temp storage." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B4-08` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B4-09` | "Ana kabul koşulu: Beta.4 yayın engeli değil; uzaktan kontrol kapalı ve opt-in." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B5-00` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-01` | "…değiştirme eylemlerini tipli sözleşmeyle ekle; bilinmeyen CLI özelliklerini kapalı tut." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B5-02` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-03` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-04` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-05` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-06` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-07` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-08` | "…önizleme; rate limit nedeniyle otomatik devredilecekse ayrı kullanıcı opt-in’i; gizli kimlik bilgileri loglara yazılmaz." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B5-09` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-10` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B5-11` | "…P0 kayıtlarını evidence/test ile verified yap; P1 açıkları triage et; deferred/excluded gerekçeleriyle sürüm notuna aktar." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B6-00` | "Ölçülebilir kabul: Her B6 yeteneği için build/integrate/defer/exclude kararı ve gerekçe vardır; kaynak tarihi ve sürüm açık." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B6-01` | "Mimari / modül sınırı: Opt-in remote runner + host registry; engine worker policy version handshake." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B6-02` | "…QR/pairing, token rotation/revocation, task status ve read-only kanıt; pairing varsayılan kapalı; uygulama türü PoC ile seç." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B6-03` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B6-04` | "…Cloud kapalıyken local tüm senaryolar geçer; risk/fiyat doğrulanmadıysa `no-go/defer` yazılır." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B6-05` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B6-06` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B6-07` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B6-08` | "Ölçülebilir kabul: İzinsiz cross-tenant veri/komut sıfır; no-go durumunda kapsam dışı açıkça belgelidir." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B6-09` | "Tamamlanma kanıtı: Usability notes + design go/no-go." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B6-10` | "…kurulumdan PR inceleme/onaya kadar gerçek görev; yollar, encoding, güncelleme/rollback ve sandbox kanıtını topla." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B6-11` | "Uygulama: Cloud, paylaşım, ofis, ek OS için go/no-go kararlarını kullanıcı verisi ve güvenlikle kapat; P0/P1 kapsama raporu; release notes." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B7-01` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B7-02` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B7-03` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B7-04` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B7-05` | "…görev/commit/test seti; no shared state; ayrı policy, sınırlandırılmış maliyet ve açık opt-in." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B7-06` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B7-07` | "Ölçülebilir kabul: Kullanıcının çalışma dosyaları otomatik ezilmez; her rollback adayı diff/riski önceden gösterir." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B8-01` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B8-02` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B8-03` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B8-04` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B8-05` | "…sınırı: UX research scripts, consent/privacy, product event anonymization opt-in." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B8-06` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B8-07` | "Mimari / modül sınırı: Profiling dashboards, benchmarks, feature flag/rollback." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B8-08` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B9-01` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B9-02` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B9-03` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B9-04` | "…kesilen migration, disk full, aktif görev sırasında upgrade, uninstaller ve rollback." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `B9-05` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B9-06` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `B9-07` | "Uygulama: v1.0.0-rc.1 pilot, crash/bug feedback, rollback, support triage, freeze; başarısız RC sonrası rc.2 ve yeniden test." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `V1-01` | Kaynakta ayrıca belirtilmedi | `[AÇIK KARAR]` — DoD madde 7: rollback veya feature flag kararı görev tamamlanmadan yazılır |
| `V1-02` | "Mimari / modül sınırı: Release manifest, build provenance, installers and rollback assets." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |
| `V1-03` | "Mimari / modül sınırı: Issue triage SLA policy, optional telemetry opt-in, update notes." | Kaynakta ima edilen; kesin mekanizma görev başında ADR ile `[AÇIK KARAR]` |

---

## 17. Geliştirme süreci, durum sözlüğü ve belge bakımı

### 17.1 Geliştirme ajanına / ekibe verilecek issue işleyişi (Beta.3/Beta.4 planından)

1. Yalnız **bir** `B3-xx.yy` veya `B4-xx.yy` issue seç; önce depoda kodun şimdiki durumunu ve dokümanın güncelliğini doğrula.
2. Kendi görevinde listelenen mevcut modülleri incele; **önerilen yol** adlarını kaynakta var sanma. Daha küçük ve mevcut mimariyle uyumlu çözüm varsa ADR’ye yaz.
3. Güvenlik sınırını ya da veri şemasını değiştiriyorsan önce negatif test ve migration fixture yaz; mevcut fail-closed korunur.
4. İlgili görev testleri + regression gate çalıştır. Windows AppContainer gerektiren testi uygun koşulda çalıştıramıyorsan “pass” deme; `blocked: environment` olarak yaz.
5. Kanıt kaydını commit SHA, platform, araç/model sürümü, komutlar, exit status, atlananlar, çıktının konumu, riskler ile oluştur; `docs/evidence/KANIT_LOG.md` düzeniyle tutarlı ol.
6. Issue tamamlanınca ilgili parent, DAG dependency ve release gate durumunu güncelle; başka bir issueyu otomatik done yapma.

### 17.2 Durum sözlüğü ve belge bakımı (Beta.5→v1.0 planından, birleştirilmiş)

- **İşlerin asıl kaynağı:** Bu dosya (Beta.5→v1.0) ve Beta.3/Beta.4 uygulama planı (Beta.3–4).
- **Ürün gerekçeleri:** Beta.3/Beta.4 rakip analizi ve Beta.5→v1.0 strateji planı.
- **Mevcut `docs/ROADMAP.md`:** Kısa sürüm bazlı indeks, açık iş sayacı, P0 release gate, story bağlantıları; tüm story metnini ikinci kez kopyalayıp belgeyi şişirme.
- **Kanıt:** `docs/evidence/KANIT_LOG.md` düzenine göre commit/test/provenance. Gerçekte koşturulmayan test `passed` yazılmaz.
- **Envanter:** `docs/COMPETITOR_CAPABILITY_MATRIX.md` (ilk `B5-00.01` işi olarak oluşturulacak); rakip/versiyon değiştikçe revizyon kaydı.
- **Yeni ADR:** Remote/cloud/paylaşım/OS güvenliği, VerificationProvider, native approval authority, autotask risk kuralı değişirse.
- **Status:** `proposed / in_progress / blocked / completed / deferred / excluded`; tamamlanma ancak commit + gerçek test kanıtıyla.

**Birleşik kural:** Her görevin kutusu `[ ]` ile başlar. Kutu yalnızca durum `completed` olduğunda ve commit SHA + gerçekten koşturulmuş test/kanıt kaydı (`docs/evidence/KANIT_LOG.md` düzeninde) bulunduğunda `[x]` olur. Kapı ve ana iş kutuları ilişkili alt görev kanıtları olmadan işaretlenmez. Gerçekte koşturulmayan test `passed` yazılmaz. Windows AppContainer gerektiren test uygun ortamda çalıştırılamadıysa "pass" denmez, `blocked: environment` yazılır.

**Belge bakımı kuralı:** Bu belge tek ana yol haritasıdır. Eski görevler ve açıklamalar silinmez; tamamlanan görevler yerinde kalır ve kanıta bağlanır (özgün ROADMAP'in "yapılan madde silinir" ilkesi, tamamlanan işin kaydının `KANIT_LOG.md`'de tutulması koşuluyla, tamamlanmış görev kutusunun işaretlenmesiyle karşılanır; silme yerine `[x]` + kanıt bağlantısı kullanılır — `[AÇIK KARAR]`: ekip özgün "sil" ilkesine dönmek isterse bu belgenin boyutu nedeniyle sürüm sonlarında tamamlananlar özetlenebilir).

**Koddaki değişiklikle belge tutarlılığı:** `docs/ARCHITECTURE.md` koda bağlayıcıdır ve aynı değişiklikte doğru tutulur. Yeni ADR gerekenler: remote/cloud/paylaşım/OS güvenliği, `VerificationProvider`, native approval authority, autotask risk kuralı.

**Kaynak planın düzenleme talimatı hakkında:** Kaynak plan, ROADMAP'in kısa indeks kalmasını isteyen bir talimat içerir; bu birleştirme onu geçersiz kılar (Ek C, C2).

### 17.3 Önerilen çalışma sırası ve ilk 5 issue (strateji planından)

1. `PARITY-01` — `docs/COMPETITOR_CAPABILITY_MATRIX.md` oluştur; mevcut Beta.3/Beta.4 özellikleriyle test kanıtlı eşleştir; 16+6 tarama havuzunu tam kapsa.
2. `PARITY-02` — 5 gerçek kullanıcı yolculuğunu seç ve baz ölçüm yap: local agent session, parallel workflow, PR/CI, browser preview, user approval.
3. `ARCH-01` — VerificationProvider + Artifact/Evidence şeması için *yalnız arayüz tasarımı ve spike*; Playwright/TestSprite/pytest çıkışlarının nasıl normalize edileceğini belirle.
4. `UX-01` — Beta.5 Needs-you/interactive session/PR review dikey prototipi; kaynak kod ve UI mimarisini doğrula.
5. `SEC-01` — B5/B6 mobil-remote-cloud güvenlik tehdit modeli, platform izolasyon ve izin matrisini oluştur.

### 17.4 Kaynak planların kullanım notları ve ilkeleri (aktarıldı)

**Beta.3/Beta.4 planı — kullanım:** > **Kullanım:** Bu dosya Github Issues ve yapay zekâ coding agentlarına tek tek verilecek, ölçülebilir iş paketleri içerir. `B3-*` / `B4-*` ana işleri; `.01`, `.02` biçimli kayıtlar bağımsız issue/story taslaklarıdır. Her iş tamamlandı diye işaretlenmeden önce kaynak commit ve test kanıtları yazılmalıdır.

**Beta.3/Beta.4 planı — kapsam notu:**

**Durum:** Plan / öneri; hiçbir görev bu belgeyle uygulanmış sayılmaz.  
**Ürün kapsamı:** Yalnızca Respected Orchestrator; başka uygulama, mağaza, hesap veya bulut hizmeti runtime bağımlılığı değildir.  
**Temel araştırma:** Beta.3/Beta.4 rakip analizi, `ai_coding_135_kategorili_rehber.html` ve Respected repo `docs/` (main, incelenen anlık görüntü).

**Beta.5→v1.0 planı — belgenin rolü:**

> **Belgenin rolü:** Beta.5→v1.0 strateji planı ürün stratejisini, bu dosya **uygulanabilir issue/story görevlerini** tanımlar. Beta.3/Beta.4 uygulama planı ile birlikte kullanılır. Hiçbir görev yalnız dokümana yazıldığı için tamamlanmış sayılmaz.
>
> **Önemli:** Bu plan kullanıcının 5 Kasım 2026 tarihli üç kaynak dosyasını esas alır. Kod yolları ve entegrasyon sınırları uygulanmadan **güncel depoda yeniden doğrulanmalıdır**. Her yeni dosya yolu öneridir; mevcut modülü tekrar yazmak için gerekçe değildir.

**Yol haritası ilkesi (Beta.3/Beta.4 planı):** **Yol haritası ilkesi:** Beta.3 = *ajanlarını güvenle yönet*. Beta.4 = *ajanlarını daha az uğraşarak, ölçülebilir biçimde yönet*. Güvenlik, kanıt, açık onay ve bağımsızlık iki sürümde de pazarlık konusu değildir.

**Kaynak planların sorumluluk notları:**

**Not:** Buradaki görevler teklif edilen kapsamdır; gerçek dosya yolları, mevcut kod durumu, performans ve test sonuçları her issue başlangıcında depodan yeniden doğrulanmalıdır. Beta.3/Beta.4 tamamlanmış sayılarak yazılmış sürüm varsayımı gerçek iş bitiş kanıtı değildir. Ne rakiplere karşı üstünlük ne de sıfır hata iddiası önceden doğrulanmıştır.

**Belge statüsü:** Taslak plan. Kod/CI/live benchmark testlerinin burada yapılmış olduğunu iddia etmez. Teknik doğruluk için implementasyondan hemen önce güncel repo kontrolü gerekir.

---

## 18. Kaynaklar (dış referanslar)

Bu bölüm, birleştirilen araştırma belgelerindeki ve bu belgedeki bütün dış URL'leri içerir. Kaynak klasörü silindiğinde araştırma gerekçeleri buradan ve §5–§6'dan izlenir. **Not:** Rakip/araştırma beyanları görev başında yeniden doğrulanır; erişim ve sürüm tarihi 5 Kasım 2026 itibarıyladır.

### Respected Orchestrator deposu (işe başlanırken `main` yeniden doğrulanmalı)

- https://github.com/respected0/respected-orchestrator
- https://github.com/respected0/respected-orchestrator/blob/main/docs/ARCHITECTURE.md
- https://github.com/respected0/respected-orchestrator/blob/main/docs/PRODUCT_CONTRACT.md
- https://github.com/respected0/respected-orchestrator/blob/main/docs/ROADMAP.md
- https://github.com/respected0/respected-orchestrator/blob/main/docs/THREAT_MODEL.md
- https://github.com/respected0/respected-orchestrator/blob/main/docs/evidence/KANIT_LOG.md

### Rakip ve komşu araçlar (üretici beyanı; laboratuvar doğrulaması değil)

- https://docs.orchestrator.inc/
- https://docs.orchestrator.inc/dashboard/
- https://github.com/1jehuang/jcode
- https://github.com/Fantomiald/open-space
- https://github.com/HarnessMD/munder-difflin
- https://github.com/OrchestratorInc/agent-orchestrator
- https://github.com/OrchestratorInc/agent-orchestrator/blob/main/docs/STATUS.md
- https://github.com/Yeachan-Heo/oh-my-claudecode
- https://github.com/block/buzz
- https://github.com/builderz-labs/mission-control
- https://github.com/deepseek-ai/dsh-superagent-prototype
- https://github.com/dxn111/EVOLV
- https://github.com/garrytan/gstack
- https://github.com/github/spec-kit
- https://github.com/jnMetaCode/agency-orchestrator
- https://github.com/jonbobo212/task-observer
- https://github.com/msitarzewski/agency-agents
- https://github.com/obra/superpowers
- https://github.com/plonkus/kitchen
- https://github.com/selmakcby/a-sirketi
- https://herdr.dev/
- https://muratify.com/products/agentspace
- https://muratify.com/tr/products/agentshot
- https://muratify.com/tr/products/agentspace
- https://muratify.com/tr/products/agentvoice
- https://mxterm.net/
- https://vi3ecode.com/
- https://www.onorca.dev/
- https://www.onorca.dev/docs/mobile

### Doğrulama araçları

- https://github.com/TestSprite/testsprite-cli
- https://github.com/microsoft/playwright-cli
- https://github.com/microsoft/playwright-mcp
- https://playwright.dev/docs/trace-viewer
- https://playwright.dev/docs/videos
- https://www.testsprite.com/solutions/mcp

### Araştırma ve literatür

- https://dora.dev/research/2025/dora-report/
- https://openai.com/index/separating-signal-from-noise-coding-evaluations/
- https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/
- https://www.anthropic.com/engineering/building-effective-agents
- https://www.anthropic.com/research/infrastructure-noise

Ek olarak kaynak rehber: kullanıcının `ai_coding_135_kategorili_rehber.html` dosyası (135 kayıt; 16 orkestrasyon ve 6 AI coding terminal/ortamı ana tarama havuzu; repo dışı).

---

## Ek A. Görev kimliği kaydı

Kaynak: Kaynak A = Beta.3/Beta.4 uygulama planı, Kaynak D = Beta.5→v1.0 uygulama planı (ikisi de bu belgeye aktarıldı; adları tarihsel izlenebilirlik içindir ve bu belge onlara bağlı değildir).

### A.1 Ana işler (68)

| Kimlik | Başlık | Öncelik | Alt görev | Kaynak |
|---|---|---|---:|---|
| `B3-00` | Ürün sınırları, GUI yetki modeli ve sözleşme | P0 | 4 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-01` | Bağımsız Tauri masaüstü uygulaması ve tipli IPC | P0 | 4 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-02` | Kalıcı supervisor, event store ve reconnect | P0 | 4 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-03` | Gerçek Chat/Terminal agent oturumları | P0 | 5 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-04` | Project Board ve görsel DAG planlama | P0 | 4 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-05` | Review, diff ve insan onayı merkezi | P0 | 4 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-06` | Canlı aktivite, dosya, terminal ve önizleme inspector | P1 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-07` | Ajan profilleri ve uyumluluk kontrolleri | P1 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-08` | Yerel, salt-okunur MCP/Skill envanteri | P1 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B3-09` | Kurulum, güncelleme, veri geçişi ve beta release | P0 | 4 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-01` | Smart Agent Routing 2.0 | P0 | 4 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-02` | Kalıcı ajan profilleri, ekipler ve kontrollü handoff | P0 | 4 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-03` | Hub’sız yerel MCP/Skill uyumluluk ve öneri motoru | P0 | 5 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-04` | Gerçek token, kota, maliyet ve kalite analitiği | P0 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-05` | Context Budget Manager ve seçici bağlam | P1 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-06` | Yerel uygulama içi sesli görev taslağı | P1 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-07` | Screenshot-to-task ve görsel bağlam | P1 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-08` | Adaptif recovery ve circuit breaker | P1 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B4-09` | Remote/mobile kontrol — koşullu araştırma (stretch) | P2 | 3 | Kaynak A (Beta.3/4 uygulama planı) |
| `B5-00` | Rekabet yetenek matrisi ve scope freeze | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-01` | Agent Chat/Terminal parity | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-02` | Workspace, Git ve arama deneyimi | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-03` | Gelişmiş Git/PR/CI/review döngüsü | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-04` | Browser preview ve tasarım geri bildirimi | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-05` | Kaydedilmiş iş akışları ve otomasyon | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-06` | Operatör inbox ve birleşik zaman çizgisi | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-07` | Ekip kimliği ve görev devri UX | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-08` | Hesap, kota ve provider sağlık durumu | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-09` | Desktop polish, erişilebilirlik ve yerelleştirme | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-10` | Yerel profil aktarımı ve audit | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B5-11` | Beta.5 canlı kabul ve release gate | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-00` | Gelişmiş rakip farklarının yeniden denetimi | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-01` | Güvenli SSH / remote worker | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-02` | Mobil companion temel deneyimi | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-03` | Çoklu host ve durum senkronizasyonu | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-04` | Opsiyonel cloud worker PoC ve karar | P2 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-05` | Ek issue/source-control adaptörleri | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-06` | Gelişmiş design mode ve satır içi review | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-07` | Operasyon API ve olay abonelikleri | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-08` | Workspace rol erişimi ve paylaşım kararı | P2 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-09` | Opsiyonel görsel takım/ofis görünümü | P2 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-10` | macOS/Linux ve platform güvenlik eşdeğerliği | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B6-11` | Beta.6 saha pilotu ve release kapısı | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B7-01` | Project Doctor | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B7-02` | Build & Prove | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B7-03` | Verified Autopilot | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B7-04` | Proof Pack 2.0 | P0 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B7-05` | Agent Tournament | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B7-06` | Impact & Risk Intelligence | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B7-07` | Recovery Time Machine | P1 | 2 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B8-01` | Rakip sürüm ve özellik yeniden doğrulaması | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B8-02` | Araştırma literatür haritası | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B8-03` | Adil ajan ve rakip benchmark koşuları | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B8-04` | Gizli ve bağımsız doğrulanmış görev seti | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B8-05` | Gerçek kullanıcı ve kullanım araştırmaları | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B8-06` | Bağımsız güvenlik saldırı denetimi | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B8-07` | Performans, maliyet, bellek ve a11y optimizasyonu | P1 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B8-08` | Araştırma sonucunu kalıcı kalite kapısına dönüştürme | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B9-01` | Feature freeze ve change control | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B9-02` | P0/P1 bug ve güvenlik kapatma | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B9-03` | Desteklenen platform/ajan regresyonu | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B9-04` | Kurulum, update, migration ve rollback | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B9-05` | UX bugları, a11y ve dokümantasyon | P1 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B9-06` | SBOM, lisans, gizlilik ve imzalı dağıtım | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `B9-07` | RC, pilot, hotfix ve destek disiplini | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `V1-01` | Final readiness ve yetenek kapsam kararı | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `V1-02` | Kararlı sürüm artefaktı ve yükseltme yolu | P0 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |
| `V1-03` | İlk sürüm izleme ve destek başlangıcı | P1 | 1 | Kaynak D (Beta.5→v1.0 uygulama planı) |

### A.2 Alt görevler (149)

| Alt görev | Başlık | Öncelik | Bağımlılıklar |
|---|---|---|---|
| `B3-00.01` | Mevcut sınırları ve sürüm bazını dondur | P0 / S | — |
| `B3-00.02` | Desktop threat model ve trust boundary | P0 / M | `B3-00.01` |
| `B3-00.03` | Komut/yetki matrisi ve onay otoritesi sözleşmesi | P0 / L | `B3-00.02` |
| `B3-00.04` | Ürün sözleşmesi ve uyumluluk karar kaydı | P0 / S | `B3-00.03` |
| `B3-01.01` | Tauri/React build ve güvenli başlangıç PoC | P0 / L | `B3-00.02` |
| `B3-01.02` | Tipli IPC şeması, istemci ve sunucu | P0 / L | `B3-00.03`, `B3-01.01` |
| `B3-01.03` | Engine connector ve health/version handshake | P0 / M | `B3-01.02` |
| `B3-01.04` | Temel navigation, erişilebilirlik ve hata durumları | P0 / M | `B3-01.03` |
| `B3-02.01` | Mevcut ayrık kontrolcüleri denetleyen supervisor | P0 / L | `B3-01.03` |
| `B3-02.02` | Sürümlü event journal ve outbox | P0 / L | `B3-02.01` |
| `B3-02.03` | Olay akışı ve reconnect cursor | P0 / L | `B3-02.02`, `B3-01.04` |
| `B3-02.04` | Resume ve shutdown davranışı | P0 / L | `B3-02.03` |
| `B3-03.01` | Destek/yetenek matrisi ve protokol tasarımı | P0 / M | `B3-00.02`, `B3-01.02` |
| `B3-03.02` | ConPTY ve sandbox uyumluluğu feasibility gate | P0 / L | `B3-03.01`, `B3-02.01` |
| `B3-03.03` | Yapılandırılmış Chat oturum adaptörü | P0 / L | `B3-03.01`, `B3-02.02` |
| `B3-03.04` | Etkileşim ve müdahale komutları | P0 / L | `B3-03.02`, `B3-03.03`, `B3-00.03` |
| `B3-03.05` | Terminal render, split pane ve oturum regresyonu | P1 / M | `B3-03.02`, `B3-03.04` |
| `B3-04.01` | Project/Run read model + filtreler | P0 / M | `B3-01.03`, `B3-02.02` |
| `B3-04.02` | DAG görselleştirme ve kapsam çatışması | P0 / M | `B3-04.01` |
| `B3-04.03` | Taslak düzenleme ve sunucu tarafı revalidate | P0 / L | `B3-04.02`, `B3-00.03` |
| `B3-04.04` | Başlat, durdur, devam ettir ve durum açıklaması | P0 / L | `B3-04.03`, `B3-02.04` |
| `B3-05.01` | Evidence/Diff/PR-CI read model | P0 / M | `B3-04.01`, `B3-01.02` |
| `B3-05.02` | Gerçek kullanıcı onayı için native authority | P0 / L | `B3-00.03`, `B3-01.02` |
| `B3-05.03` | TOCTOU-safe apply ve işlem sonucu | P0 / L | `B3-05.01`, `B3-05.02` |
| `B3-05.04` | Onay merkezi uçtan uca saldırı testi | P0 / L | `B3-05.03`, `B3-03.04` |
| `B3-06.01` | Event timeline ve arama/filtre | P1 / M | `B3-02.03`, `B3-04.01` |
| `B3-06.02` | Dosya diff/çıktı/kanıt inspector | P1 / M | `B3-06.01`, `B3-05.01` |
| `B3-06.03` | Güvenli local preview (isteğe bağlı) | P1 / L | `B3-06.02` |
| `B3-07.01` | CLI binary/sürüm/auth keşfi | P1 / M | `B3-01.03` |
| `B3-07.02` | Role, tool, profile ayrımı ve düzenleme | P1 / M | `B3-07.01`, `B3-00.03` |
| `B3-07.03` | Canlı yetenek/uyumluluk matrisi | P1 / M | `B3-07.02`, `B3-03.01` |
| `B3-08.01` | Desteklenen istemcilerin config yolu matrisi | P1 / M | `B3-00.02`, `B3-07.01` |
| `B3-08.02` | Manifest normalizasyonu ve durum ayrımı | P1 / M | `B3-08.01` |
| `B3-08.03` | Envanter ekranı ve offline e2e | P1 / M | `B3-08.02`, `B3-01.04` |
| `B3-09.01` | Desktop+engine paket sözleşmesi | P0 / L | `B3-01.03`, `B3-00.04` |
| `B3-09.02` | Beta.1/2 veri fixture ve migration | P0 / L | `B3-09.01`, `B3-02.02` |
| `B3-09.03` | Aktif görev varken update/rollback tasarımı | P0 / L | `B3-09.02`, `B3-02.04` |
| `B3-09.04` | Beta.3 release gate ve imza politikası | P0 / L | `B3-05.04`, `B3-04.04`, `B3-03.04`, `B3-09.03` |
| `B4-01.01` | Görev sınıflandırma ve risk şeması | P0 / M | `B3-04.03` |
| `B4-01.02` | Politika temelli aday seçimi ve bütçe | P0 / L | `B4-01.01`, `B3-07.03` |
| `B4-01.03` | Shadow mode ve geri alınabilir active routing | P0 / L | `B4-01.02`, `B4-04.01` |
| `B4-01.04` | Gerçek ajan benchmark ile routing güveni | P0 / L | `B4-01.03`, `B4-04.02` |
| `B4-02.01` | Agent/team/profile sürümlü veri sözleşmesi | P0 / M | `B3-07.02`, `B3-09.02` |
| `B4-02.02` | Handoff message envelope ve mailbox | P0 / L | `B4-02.01`, `B3-02.02` |
| `B4-02.03` | Loop-limited takım koordinasyonu | P0 / L | `B4-02.02`, `B4-08.01` |
| `B4-02.04` | Takım görünümü ve görev geçmişi | P1 / M | `B4-02.03`, `B3-06.01` |
| `B4-03.01` | CompatibilityResolver & agent support registry | P0 / L | `B3-08.02`, `B3-07.03` |
| `B4-03.02` | Görev bazlı öneri ve gerekçe | P0 / L | `B4-03.01`, `B4-01.01` |
| `B4-03.03` | PermissionInspector ve risk kartları | P0 / L | `B4-03.01`, `B3-00.02` |
| `B4-03.04` | Onaylı ActivationPlan ve execution gate | P0 / L | `B4-03.02`, `B4-03.03`, `B3-05.02` |
| `B4-03.05` | Capability recommender UI + user feedback | P1 / M | `B4-03.04`, `B3-08.03` |
| `B4-04.01` | UsageEvent şeması ve provider adapters | P0 / M | `B3-02.02`, `B3-07.03` |
| `B4-04.02` | Cost/quality ledger ve benchmark korelasyonu | P0 / L | `B4-04.01` |
| `B4-04.03` | Bütçe/başarı dashboard ve uyarılar | P1 / M | `B4-04.02`, `B3-06.01` |
| `B4-05.01` | Repo context map ve içerik invalidation | P1 / M | `B3-04.01` |
| `B4-05.02` | Bounded context preparation ve evidence refs | P1 / L | `B4-05.01`, `B4-02.02` |
| `B4-05.03` | A/B token/başarı deneyleri | P1 / L | `B4-05.02`, `B4-04.02`, `B4-01.04` |
| `B4-06.01` | Mikrofon izinleri ve offline STT spike | P1 / M | `B3-01.04` |
| `B4-06.02` | Editable task draft, vocabulary ve safety | P1 / M | `B4-06.01`, `B3-04.03` |
| `B4-06.03` | Ses gizlilik/performans release kapısı | P1 / M | `B4-06.02` |
| `B4-07.01` | Kullanıcı denetimli ekran yakalama | P1 / M | `B3-01.04`, `B3-00.02` |
| `B4-07.02` | Görsel önizleme, redaksiyon ve task attachment | P1 / L | `B4-07.01`, `B3-04.03` |
| `B4-07.03` | Model transfer ve retention onayı | P1 / M | `B4-07.02`, `B4-03.04` |
| `B4-08.01` | Recovery decision table ve maksimum kaynak sınırı | P0 / M | `B3-02.04`, `B4-04.01` |
| `B4-08.02` | Operator escalation ve explainable recovery | P1 / M | `B4-08.01`, `B3-05.01` |
| `B4-08.03` | Fault-injection ve regresyon release suite | P1 / L | `B4-08.02`, `B4-02.03` |
| `B4-09.01` | Tehdit modeli, kullanıcı araştırması ve Go/No-Go | P2 / M | `B3-09.04`, `B4-04.03` |
| `B4-09.02` | Opt-in read-only remote observer prototipi | P2 / L | `B4-09.01` |
| `B4-09.03` | Genişleme karar kapısı: kontrol ve mobil | P2 / M | `B4-09.02` |
| `B5-00.01` | Kaynak destekli capability envanteri | P0 | — |
| `B5-00.02` | Kullanıcı yolculuğu ve ölçümlü kapsam dondurma | P0 | `B5-00.01` |
| `B5-01.01` | Gelişmiş oturum etkileşimi ve agent yetenek matrisi | P0 | `B3-03.04`, `B3-07.03` |
| `B5-01.02` | Split pane, geçmiş arama ve kesintisiz yeniden bağlanma | P0 | `B5-01.01`, `B3-02.03` |
| `B5-02.01` | Çok sekmeli worktree ve dosya/diff gezinmesi | P0 | `B3-04.01`, `B3-05.01` |
| `B5-02.02` | Hızlı proje/dosya arama ve oturum layout kalıcılığı | P0 | `B5-02.01` |
| `B5-03.01` | CI/review başarısızlığını doğru worker’a yönlendir | P0 | `B3-05.01`, `B4-08.01` |
| `B5-03.02` | Diff review yorumundan düzeltme ve tekrar kontrol | P0 | `B5-03.01`, `B3-05.03` |
| `B5-04.01` | VerificationProvider tasarımı ve Playwright adaptörü | P0 | `B3-06.03`, `B5-00.02` |
| `B5-04.02` | Browser/design feedback ve güvenli preview UI | P0 | `B5-04.01`, `B3-05.01` |
| `B5-05.01` | Sürüm kontrollü workflow presetleri | P1 | `B3-04.03`, `B4-02.03` |
| `B5-05.02` | Zamanlayıcı ve olay tetikleyici için görev kabul kapısı | P1 | `B5-05.01`, `B3-00.03` |
| `B5-06.01` | Needs-you inbox ve eylem ayrımı | P0 | `B3-06.01`, `B3-05.02` |
| `B5-06.02` | Birleşik konuşma ve karar timeline | P0 | `B5-06.01`, `B4-02.04` |
| `B5-07.01` | Kalıcı ekip ve rol şablonlarını görünür kıl | P1 | `B4-02.04`, `B4-01.02` |
| `B5-07.02` | Mailbox, yorum ve handoff sınırı | P1 | `B5-07.01`, `B4-02.03` |
| `B5-08.01` | Provider usage ve kota güvenilirlik etiketleri | P1 | `B4-04.03`, `B3-07.03` |
| `B5-08.02` | Kullanıcı onaylı profil değiştirme | P1 | `B5-08.01`, `B3-07.02` |
| `B5-09.01` | Klavye odaklı Command Palette ve erişilebilirlik | P1 | `B3-01.04`, `B5-06.01` |
| `B5-09.02` | TR/EN, light/dark, responsive ve hata durumları | P1 | `B5-09.01` |
| `B5-10.01` | Güvenli import/export, şablon taşınabilirliği | P1 | `B5-05.01`, `B3-09.02` |
| `B5-10.02` | Yerel audit ve veri saklama politikası | P1 | `B5-10.01`, `B3-02.02` |
| `B5-11.01` | Beş gerçek kullanıcı yolculuğunun doğrulanması | P0 | `B5-01.02`, `B5-02.01`, `B5-03.02`, `B5-04.02`, `B5-06.02` |
| `B5-11.02` | Rakip parity gate ve release notları | P0 | `B5-11.01`, `B5-00.02`, `B5-09.02` |
| `B6-00.01` | Beta.5 sonrası P1/P2 gap yeniden sayımı | P0 | `B5-11.02` |
| `B6-00.02` | Uzak yetki ve işletim maliyeti kararı | P0 | `B6-00.01`, `B3-00.02` |
| `B6-01.01` | Remote worker protokolü ve host kaydı | P0 | `B6-00.02`, `B3-02.04` |
| `B6-01.02` | Çalıştırma, reconnect ve güvenli temizleme | P0 | `B6-01.01`, `B3-02.03` |
| `B6-02.01` | Cihaz eşleştirme ve salt-okunur izleme | P1 | `B6-00.02`, `B6-01.01` |
| `B6-02.02` | Mobil bildirim ve izinli cevap yönetimi | P1 | `B6-02.01`, `B5-06.01` |
| `B6-03.01` | Multi-host registry ve run ownership | P1 | `B6-01.01` |
| `B6-03.02` | Durum eşitleme, event replay ve çatışma çözümü | P1 | `B6-03.01`, `B6-01.02` |
| `B6-04.01` | BYO VM cloud threat, data & cost PoC | P2 / k | `B6-00.02`, `B6-01.01` |
| `B6-04.02` | Cloud’u ürün kapsamına alma veya açık erteleme | P2 / k | `B6-04.01` |
| `B6-05.01` | Git sağlayıcı soyutlaması ve ikinci adaptör seçimi | P1 / t | `B5-03.02`, `B6-00.01` |
| `B6-05.02` | Gerçek iki-sağlayıcı teslimat ve hata geri beslemesi | P1 / t | `B6-05.01` |
| `B6-06.01` | Satır içi diff işaretleme ve kaynak sürüm izleme | P1 | `B5-03.02`, `B5-04.02` |
| `B6-06.02` | DOM/element kaynaklı görev geri bildirimi | P1 | `B6-06.01`, `B5-04.02` |
| `B6-07.01` | API/MCP/CLI komut ve yetki sözleşmesi | P1 | `B6-00.02`, `B3-00.03` |
| `B6-07.02` | Webhook güvenliği, scheduling ve event-to-task policy | P1 | `B6-07.01`, `B5-05.02` |
| `B6-08.01` | Tek kullanıcı ile çok kullanıcı trust boundary ayrımı | P2 / k | `B6-00.02` |
| `B6-08.02` | Koşullu paylaşımlı çalışma pilotu | P2 / k | `B6-08.01`, `B6-07.01` |
| `B6-09.01` | Kullanıcı değerini doğrulama ve tasarım kararı | P2 / k | `B5-07.02`, `B5-09.02` |
| `B6-09.02` | Değerliyse düşük maliyetli, salt-okunur ofis görünümü | P2 / k | `B6-09.01` |
| `B6-10.01` | Platform port gereksinimleri ve güvenlik matrisi | P1 / y | `B6-00.02`, `B3-09.04` |
| `B6-10.02` | Platform E2E, installer ve veri taşınabilirliği | P1 / y | `B6-10.01`, `B3-09.03` |
| `B6-11.01` | Mobil/SSH/çoklu host gerçek saha pilotu | P0 | `B6-01.02`, `B6-02.02`, `B6-03.02` |
| `B6-11.02` | Koşullu özellik kararları ve parity II release | P0 | `B6-11.01`, `B6-00.01` |
| `B7-01.01` | Salt-okunur proje teşhis sağlayıcıları ve bulgu şeması | P0 | `B5-04.01`, `B4-05.01` |
| `B7-01.02` | Teşhisten kontrollü kurtarma planına e2e | P0 | `B7-01.01`, `B3-04.03` |
| `B7-02.01` | Birleşik verification provider ve artefakt provenance | P0 | `B5-04.01`, `B7-01.01` |
| `B7-02.02` | Önce/sonra gösterimi ve kullanıcı senaryosu kanıtı | P0 | `B7-02.01`, `B3-05.01` |
| `B7-03.01` | Sınırlı otonomi politika profilleri | P0 | `B4-08.03`, `B6-07.01`, `B3-00.03` |
| `B7-03.02` | Issue→PR kanıtlı tam iş akışı ve bailout | P0 | `B7-03.01`, `B5-03.02`, `B7-02.01` |
| `B7-04.01` | Dışa aktarılabilir kanıt paketi şeması | P0 | `B7-02.01`, `B3-05.03` |
| `B7-04.02` | Çevrimdışı bağımsız proof doğrulayıcı | P0 | `B7-04.01` |
| `B7-05.01` | Eşit koşullu çoklu aday yürütme | P1 / o | `B4-01.04`, `B7-03.01` |
| `B7-05.02` | Kör test, risk ve güvenilirlik temelli tercih | P1 / o | `B7-05.01`, `B7-04.01` |
| `B7-06.01` | Değişiklik etki grafı ve test ilişkisi | P1 | `B4-05.01`, `B7-01.01` |
| `B7-06.02` | Risk bazlı test seçimi ve güvenlik kritik override | P1 | `B7-06.01`, `B7-02.01` |
| `B7-07.01` | Güvenli geri alma adayları ve salt-okunur önizleme | P1 | `B3-02.04`, `B7-04.01` |
| `B7-07.02` | Onaylı kurtarma transaction ve tekrar doğrulama | P1 | `B7-07.01`, `B3-05.03` |
| `B8-01.01` | Kaynak tarihlendirmeli dış rekabet audit’i | P0 | `B6-11.02`, `B7-04.02` |
| `B8-02.01` | Hipotez, deney ve karar kayıtları | P0 | `B8-01.01` |
| `B8-03.01` | Çok tekrarlı eş koşullu performans deneyi | P0 | `B8-02.01`, `B5-11.01`, `B7-03.02` |
| `B8-04.01` | Holdout task dataset ve test hakemliği | P0 | `B8-02.01` |
| `B8-05.01` | Kullanıcı görev başarısı ve tercih çalışması | P0 | `B8-01.01`, `B7-02.02` |
| `B8-06.01` | Threat-driven red-team ve güvenlik regresyonu | P0 | `B8-04.01`, `B6-11.01`, `B7-07.02` |
| `B8-07.01` | Önce/sonra ölçümlü optimizasyon ve geri alma | P1 | `B8-03.01`, `B8-05.01` |
| `B8-08.01` | Karar, düzeltme backlog’u ve yeniden deney | P0 | `B8-01.01`, `B8-03.01`, `B8-05.01`, `B8-06.01`, `B8-07.01` |
| `B9-01.01` | Sürüm dondurma ve exception kayıtları | P0 | `B8-08.01` |
| `B9-02.01` | Kritik sorunları kök neden ve regresyonla kapatma | P0 | `B9-01.01`, `B8-06.01` |
| `B9-03.01` | E2E support matrix ve release doğrulama | P0 | `B9-02.01`, `B6-10.02` |
| `B9-04.01` | Bozuk güncelleme ve eski veri senaryoları | P0 | `B9-02.01`, `B3-09.03` |
| `B9-05.01` | Kullanıcı başarı senaryosu düzeltmeleri | P1 | `B8-05.01`, `B9-01.01` |
| `B9-06.01` | Yayın artefaktı ve lisans bütünlüğü | P0 | `B9-04.01` |
| `B9-07.01` | Sürüm adayı ve geri dönüş tatbikatı | P0 | `B9-02.01`, `B9-03.01`, `B9-04.01`, `B9-05.01`, `B9-06.01` |
| `V1-01.01` | Son yetenek ve kabul kanıtı denetimi | P0 | `B9-07.01` |
| `V1-02.01` | Tekrarlanabilir v1.0.0 imzalı yayın | P0 | `V1-01.01`, `B9-06.01` |
| `V1-03.01` | Gizlilik dostu destek/incident akışı | P1 | `V1-02.01` |

---

## Ek B. Eksiksizlik ve entegrasyon denetim raporu

> Bu rapor, birleştirme sonrası **bağımsız bir denetim betiğiyle** üretilmiştir: betik, bitmiş ROADMAP'i ve dört kaynak belgeyi yeniden okuyup karşılaştırır (derleme betiğinden bağımsız ayrıştırıcı). Kaynak belgeler: **Kaynak A** = Beta.3/Beta.4 uygulama planı, **Kaynak B** = Beta.3/Beta.4 rakip analizi raporu, **Kaynak C** = Beta.5→v1.0 strateji planı, **Kaynak D** = Beta.5→v1.0 uygulama planı. Bu belge onlara bağlı değildir; adlar yalnızca izlenebilirlik içindir. Denetim tarihi: 5 Kasım 2026. Kod çalıştırılmamış, yalnızca belge değişmiştir; tüm görevler açık (`[ ]`) kalmıştır.

### B.1 Görev sayıları

| Ölçü | Kaynak | ROADMAP | Sonuç |
|---|---:|---:|---|
| Ana iş — Beta.3/Beta.4 (Kaynak A) | 19 | 19 | GEÇTİ |
| Ana paket — Beta.5→v1.0 (Kaynak D) | 49 | 49 | GEÇTİ |
| Alt görev — Beta.3/Beta.4 | 69 | 69 | GEÇTİ |
| Alt görev — Beta.5→v1.0 | 80 | 80 | GEÇTİ |
| **Toplam alt görev** | **149** | **149** | GEÇTİ |
| Eksik ana iş / alt görev kimliği | — | 0 / 0 | GEÇTİ |
| Kaynakta olmayan fazladan kimlik | — | 0 / 0 | GEÇTİ |
| Yinelenen kimlik başlığı | — | 0 | GEÇTİ |

Beta bazında dağılım: Beta.3 = 10 ana / 38 alt, Beta.4 = 9 / 31, Beta.5 = 12 / 24, Beta.6 = 12 / 24, Beta.7 = 7 / 14, Beta.8 = 8 / 8, Beta.9 = 7 / 7, v1.0 = 3 / 3.

### B.2 İçerik karşılaştırması (yalnız sayı değil, teknik içerik)

- **Alt görev kartları:** 149 kartın her biri kaynakla alan alan karşılaştırıldı; toplam **1192** alan satırı (durum kutusu, öncelik/boyut, bağımlılıklar, mimari, uygulama adımları, test senaryoları, ölçülebilir kabul, tamamlanma kanıtı) karşılaştırıldı; fark sayısı: **0** — GEÇTİ. Tek düzenleme: Kaynak D kartlarında satır sonundaki yazım hatası `..` → `.` düzeltildi (içerik kaybı yok).
- **Zorunlu alanların varlığı:** her kartta öncelik, bağımlılıklar, mimari, uygulama, test, ölçülebilir kabul, tamamlanma kanıtı ve durum kutusu bulunuyor; eksik alan: **0** — GEÇTİ.
- **Ana iş başlık satırları** (Amaç, Mevcut/önerilen kod eşlemesi, Rakip dayanağı/Referans, Ana kabul koşulu): eksik satır **0** — GEÇTİ.
- **Rakip analizi (Kaynak B) görev önerileri:** 19/19 görev önerisi ilgili ana işin altına aktarıldı; eksik satır 0 — GEÇTİ.
- **Strateji (Kaynak C) tablo satırları:** Beta.5–Beta.9 için 46 satırın hücreleri ilgili ana işin altına aktarıldı (12+12+7+8+7); eksik hücre 0 — GEÇTİ.
- **Sürüm kapıları:** Kaynak A'dan 14 ve Kaynak D'den 29 kapı maddesi; eksik: 0 — GEÇTİ.

### B.3 Kaynak gerekçelerinin kapsanması

| Kaynak bölümü | ROADMAP'te yeri | Durum |
|---|---|---|
| B §1 Yönetici özeti, §2 mevcut temel, §3 rakip matrisi (16 rakip) ve §3.1 ek araçlar, §4 OrchestratorInc/AgentSpace öğrenimleri | §5.1–§5.4 | Eksiksiz aktarıldı (16/16 rakip adı bulundu) |
| B §5–§6 Beta.3/4 görev önerileri | İlgili ana işlerin altında (§7, §8) | 19/19 |
| B §7 mimari sınırlar, §8 kapılar, §9 yapılmayacaklar, §10 dış kaynaklar | §5.6, §5.9, §5.7, §18 | Eksiksiz |
| C §0–§2 amaç, ilkeler, önkoşul | §4.1, §4.3 | Eksiksiz |
| C §3 rakip envanteri + CAP formatı + kapsama formülü | §5.5, §6 | Eksiksiz; CAP matrisi 46 satır `[ÖNERİ]` |
| C §4–§8 Beta.5–Beta.9 tabloları ve notları | §9–§13 (ana iş altlarında ve sürüm girişlerinde) | 46/46 satır |
| C §9 v1.0 çıkış sözleşmesi, §10 ölçüm/risk, §11 ilk 5 issue, referanslar | §14.1, §5.8, §17.3, §18 | Eksiksiz |
| A §0 mevcut mekanizmalar/güvenlik sabitleri, §1 kapsam, §2 DoD | §4.1–§4.3, §2 | Eksiksiz |
| A §5 kritik yol, §6–§7 kapılar, §8 risk, §9 işleyiş, §10 kaynaklar | §16.1, §15.1–§15.2, §16.2, §17.1, §18 | Eksiksiz |
| D §0–§2 hedefler, standart, paket sayıları | §2, §4 | Eksiksiz |
| D §3 sürüm kapıları, §4 belge stratejisi, §5 kaynaklar | §15.3–§15.8, §17.2 (Ek C, C2 ile uzlaştırıldı), §18 | Eksiksiz |
| Dış URL'ler | §18 | Kaynaklarda 46 benzersiz URL; ROADMAP'te 46 (eksik: 0) — GEÇTİ |

Mevcut ROADMAP'in özgün içeriği (başlık, kanıt notu, ilke cümlesi ve iki açık madde): eksik satır **0** — GEÇTİ. Özgün iki madde `[ ]` olarak korunmuştur; yeni görevlerle ilişkileri §3.1'dedir.

### B.4 Kaybolan, birleştirilen veya yinelenen görevler

- **Kaybolan görev: 0. Birleştirilen görev: 0.** Hiçbir görev kimliği değiştirilmedi, silinmedi veya başka bir görevin içine katılmadı.
- **Örtüşen ama birleştirilmeyen konular** (aşamalı kapsam; kaynaklar bunları ayrı sürümlerde ayrı kabul kriteriyle ister, bu yüzden korundu):

| Konu | Önceki görev | Sonraki görev | İlişki |
|---|---|---|---|
| Terminal split pane / geçmiş arama | `B3-03.05` | `B5-01.02` | Beta.3 temel render, Beta.5 geçmiş arama + kesintisiz yeniden bağlanma + yerleşim kalıcılığı |
| Ajan yetenek matrisi | `B3-03.01`, `B3-07.03` | `B5-01.01` | ≥1 doğrulanmış CLI → ≥3 doğrulanmış CLI sürümü |
| Yerel preview | `B3-06.03` | `B5-04.02`, `B6-06` | Beta.3 isteğe bağlı güvenli önizleme → Beta.5 tarayıcı/tasarım geri bildirimi → Beta.6 gelişmiş design mode |
| Kalıcı takım / handoff | `B4-02` | `B5-07` | Beta.4 veri sözleşmesi ve sınırlar → Beta.5 görünür UX ve mailbox |
| Yerel skill/MCP envanteri | `B3-08` | `B4-03` | Salt-okunur envanter → uyumluluk/öneri motoru |
| Kullanım / maliyet | `B4-04` | `B5-08` | Ledger → provider sağlık/kota görünürlüğü |
| Operatör müdahalesi | `B3-05`, `B3-03.04` | `B5-06` | Onay merkezi → birleşik Needs-you inbox ve zaman çizgisi |
| Uzaktan / mobil | `B4-09` (araştırma, P2) | `B6-01`, `B6-02`, `B6-03` | Go/no-go sonucu Beta.6 uygulamasını koşullar |
| Sınırlı otonomi / kurtarma | `B4-08` | `B7-03`, `B7-07` | Circuit breaker → Verified Autopilot politikası ve Recovery Time Machine |
| GitHub issue/PR/CI | Beta.2 `GH-01…03` (mevcut) | `B5-03`, `B6-05`, `B7-03.02` | Mevcut CLI/RPP yeniden yazılmaz; UI, ikinci adaptör ve issue→PR akışı üstüne kurulur |

### B.5 Kırık bağlantı ve kaynak bağımlılığı denetimi

- Yerel (göreli) Markdown bağlantısı: **0**. İç sayfa bağlantıları (içindekiler): kırık bağlantı **0**. Kaynak dosya adı veya kaynak klasörü yolu referansı: **0** — GEÇTİ.
- Belgede geçen diğer dosya adları (`docs/COMPETITOR_CAPABILITY_MATRIX.md`, `docs/research/`, `docs/adr/remote-architecture.md`, `desktop/` …) **önerilen yeni yollardır**, bağlantı değildir.
- Geçici kaynak klasörü silindiğinde ROADMAP'ten hiçbir içerik veya bağlantı eksilmez.

### B.6 Markdown yapısı, kimlikler ve bağımlılıklar

- Tek `#` başlığı: 1; başlık seviyesi atlaması: 0; yinelenen başlık: 0; kod bloğu dengeli: True; tablo hücre sayısı uyumsuz satır: 0.
- `[x]` ile işaretlenmiş madde: **0** (hiçbir görev tamamlanmış sayılmadı).
- Bağımlılık grafı: 280 kenar; bilinmeyen kimliğe giden bağımlılık 0; **döngü 0**; ileri sürüme (geri yönlü) bağımlılık 0; tanımsız kapı referansı 0; belgede anılan ama tanımlı olmayan kimlik 0.
- Kart içi bağımlılık sırası, ana iş numarası sırasından farklı olan üç kenar vardır: `B4-01.03→B4-04.01`, `B4-01.04→B4-04.02`, `B4-02.03→B4-08.01` (Ek C, C7); döngü değildir.

### B.7 Çelişkili bağımlılıklar ve çözülmemiş teknik kararlar

- Çelişkiler (9 madde) ve çözümleri: **Ek C.1**. En önemlileri: `B4-04` önceliği (P1↔P0), ROADMAP'in rolü (kısa indeks↔tam metin), CAP alan listesi, ve gerçek ajan benchmark verisinin planın varsayımıyla uyumsuzluğu (orchestrated %70 < direct %96,7).
- Çözülmemiş teknik karar ve araştırma görevleri (24 madde, tahmin edilerek doldurulmadı): **Ek C.2**.
- Bağımlılık düzeyinde çelişki bulunmadı: döngü yok, geri yönlü sürüm bağımlılığı yok.

### B.8 Bu entegrasyonun sınırları (dürüst kayıt)

- Denetim betiği; ID kümesi, alan metni eşitliği, URL, rakip adı, kapı maddesi, bağlantı, başlık ve bağımlılık yapısını makinece doğrular. **Anlam doğruluğunu** doğrulamaz: rakip beyanlarının doğruluğu, CAP matrisi `Respected şu an` sütunu ve ek `[ÖNERİ]` bölümlerinin (Beta.7 çerçevesi, Beta.8 protokolü, Beta.9 tanımları, v1.0 kategori eşlemesi) teknik isabeti bir insan tarafından gözden geçirilmelidir.
- Rakip özellikleri yerelde denenmemiştir (kaynakların kendi sınırı). `shipped/beta/planned/paid` ayrımı `B5-00.01` işidir.
- Kod yolları yalnız §3.3'te belirtilen modül düzeyinde depoda doğrulandı; önerilen yeni dosya/klasörler depoda yoktur.
- Yalnızca `docs/ROADMAP.md` değiştirildi; kaynak kod, test ve geçici kaynak klasöründeki dosyalara dokunulmadı.

---

## Ek C. Kaynaklar arası çelişkiler ve çözülmemiş teknik kararlar

### C.1 Birleştirme sırasında bulunan çelişkiler ve çözümleri `[ÇELİŞKİ]`

| # | Çelişki | Çözüm (bu belgede uygulanan) |
|---|---|---|
| C1 | **B4-04 önceliği:** rakip analizi raporu `B4-04`'ü **P1**, Beta.3/4 uygulama planı **P0** yazar | Uygulama planı esas alındı (**P0**): `B4-GATE-04` bunu zorunlu kapı yapar ve `B4-01.03/.04` doğrudan `B4-04.01/.02`'ye bağlıdır. Analiz raporundaki P1 notu `B4-04` kartında korunmuştur |
| C2 | **ROADMAP'in rolü:** Beta.5→v1.0 uygulama planı §4, `ROADMAP.md`'nin "kısa indeks" kalmasını ve story metninin kopyalanmamasını önerir; bu birleştirme görevi ise ROADMAP'in kaynak dosyalar silinse de tek başına yeterli olmasını ister | Görev talimatı esas alındı: ROADMAP tam metni içerir. Kaynak planın "ikinci kez kopyalama" kaygısı, kaynak klasörünün silinecek olması nedeniyle geçersizdir; tek kaynak bu belgedir |
| C3 | **CAP matrisi alan listesi:** strateji belgesi 13 alan (Owner dahil, kaçınma gerekçesi yok), uygulama planı 12 alan (`defer/exclude_reason` dahil, Owner yok) tanımlar | Birleşim kullanılır: `CAP-ID \| user problem \| competitor \| source URL/date/version \| shipped/beta/planned/paid \| target platform/OS \| respected_status \| parity decision/priority \| B5/B6 issue \| acceptance_test \| evidence commit \| owner \| defer/exclude_reason` |
| C4 | **Durum sözcükleri:** Beta.3/4 kartları `- [ ] Tamamlandı` kutusu; Beta.5+ kartları `- [ ] Durum: Öneri` kutusu ve ayrıca `proposed/in_progress/blocked/completed/deferred/excluded` değerleri kullanır | Tüm kartlarda kutu `[ ]` = tamamlanmadı. Durum değerleri §17'deki sözlükle birleştirildi; kutu yalnızca `completed` + commit + gerçek test kanıtıyla işaretlenir |
| C5 | **`ARCHITECTURE` yol adı:** kaynak planlar `engine/winproc` yazar; depoda `engine/winproc.py` tek modül dosyasıdır | Modül adı olarak korundu (`winproc`); yol doğrulaması §3.3'te kayıtlı |
| C6 | **Rakip analizi B3-03 kabul ifadesi** "Claude/Codex en az bir desteklenen modda" (adı geçen iki CLI) ile uygulama planı `B3-03.03` "en az 1 doğrulanmış CLI" | Uygulama planı kabulü geçerli (herhangi doğrulanmış 1 CLI); Claude/Codex hedefi analiz bloğunda korunur. Beta.5 `B5-01.01` en az 3 CLI ister (aşamalı artış, çelişki değil) |
| C7 | **Beta.4 kart sırası ≠ yürütme sırası:** `B4-01.03` → `B4-04.01`, `B4-01.04` → `B4-04.02`, `B4-02.03` → `B4-08.01` sonraki numaralı ana işlere bağlıdır | Döngü yok (denetlendi); yürütme sırası kritik yolda (§16.1) gösterilir |
| C8 | **AgentSpace URL'si:** analiz raporu `muratify.com/tr/products/agentspace`, strateji `muratify.com/products/agentspace` verir | İkisi de §18'de korundu (TR ve genel sayfa) |
| C9 | **Gerçek ajan kıyas verisi vs plan varsayımı:** planlar "orkestratör değer katar" varsayımıyla ilerler; depo kanıtı (FIX-02) orchestrated kolunun direct'ten düşük başarı ve daha yavaş olduğunu gösterir | Varsayım doğrulanmış sayılmaz; `B4-GATE-01`, `B8-03` ve pazarlama iddiaları bu veriyi baseline alır (§3.3) |

### C.2 Çözülmemiş teknik kararlar ve araştırma görevleri `[AÇIK KARAR]`

Kaynak belgelerde açıklanmayan veya "ADR/PoC/spike ile karar verilecek" denen konular tahmin edilerek doldurulmamıştır.

| # | Karar / araştırma | Nerede | Karar zamanı ve çıktı |
|---|---|---|---|
| D1 | Windows ConPTY + AppContainer altında gerçek interaktif süreç mümkün mü? Değilse yalnız headless transcript | `B3-03.02` | Go/no-go ADR (Beta.3); no-go ise terminal modu Beta.3 dışı ve kapalı |
| D2 | Desktop+engine paketleme stratejisi (mevcut PyInstaller `distribution.json` + Inno ile desktop bundle) | `B3-09.01` | Paket sözleşmesi ADR'si |
| D3 | GUI↔motor yerel IPC taşıma/kimlik doğrulama (kaynak yalnız "platforma uygun yerel bağlantı", "auth handshake" der) | `B3-01.02`, `B3-01.03` | Şema + tehdit modeli (`B3-00.02/03`) sonrası |
| D4 | Event journal depolama biçimi, retention ve redaction (append-only; format belirtilmemiş) | `B3-02.02` | Migration fixture ile birlikte karar |
| D5 | İnsan varlığı (human-presence) yetkisinin teknik mekanizması (native diyalog, tek kullanımlık token) | `B3-00.03`, `B3-05.02` | Protokol örnekleri + kırmızı takım testi |
| D6 | Yerel STT motoru ve model seçimi (offline) | `B4-06.01` | Spike + go/no-go ADR |
| D7 | Remote/mobil kontrolün hiç yapılıp yapılmayacağı (SSH üzerinden salt-okunur gateway alternatifi) | `B4-09.01`, `B4-09.03` | Araştırma kararı ADR; Beta.4 blocker değil |
| D8 | Mobil companion türü (PWA / native) | `B6-02` ("uygulama türü PoC ile seç") | PoC sonucu |
| D9 | Cloud worker ürün kapsamına alınsın mı (BYO VM, self-host) | `B6-04.02` | Go/no-go; no-go "deferred with documented exception" |
| D10 | İkinci Git/issue sağlayıcısı (GitLab? Linear?) | `B6-05.01` | Talep verisine göre seçim |
| D11 | Çok kullanıcılı/paylaşımlı workspace ve görsel ofis yapılsın mı | `B6-08`, `B6-09` | Tehdit modeli / kullanıcı değeri kanıtı |
| D12 | Desteklenecek OS listesi ve her OS için eşdeğer izolasyon mekanizması | `B6-10.01` | Güvenlik matrisi + ADR (`ADR-008` ile uyumlu) |
| D13 | Project Doctor'ın desteklediği ilk teknoloji yığınları ("örn. JS/Python") | `B7-01.01` | 5 stack fixture seçimi |
| D14 | Karşılaştırmaya dahil edilecek rakipler (ulaşılabilir + lisans/ToS izin veren) ve yapılandırma biçimi | `B8-03.01` | Ön kayıt öncesi |
| D15 | Literatür defterinde eksik ≥6 kaynak (kaynak planlar yalnızca 6 kaynak grubunu adlandırır; kabul ≥12 ister) | `B8-02.01` | Sistematik aramayla |
| D16 | İstatistiksel yöntem ve anlamlılık eşiği, ön kayıt biçimi | `B8-03.01` | Ön kayıtta sabitlenir |
| D17 | Kullanıcı çalışması katılımcı edinimi, ücretlendirme, hedef oranlar (SUS vb.) | `B8-05.01`, `B9-05.01` | Çalışma protokolü |
| D18 | Sayısal performans bütçeleri ve crash-free hedefi | `B8-07`, V1 kalite | Optimizasyondan önce sabitlenir |
| D19 | Hata önem sınıfları ve triage SLA resmî tanımı | `B9-02`, `V1-03.01` | Politika belgesi |
| D20 | Opsiyonel telemetri/crash raporu tasarımı (kullanıcı izinli, anonim) | `V1-03.01` | Gizlilik testleriyle |
| D21 | Üretim Authenticode sertifikası ve zaman damgası (operasyonel bağımlılık; "sertifika yok") | `B3-09.04`, `B9-06.01`, `V1-02.01` | Sertifika temini; olmadan "üretim imzalı" iddia edilmez |
| D22 | Veri geçişinde desteklenecek en eski sürüm aralığı | `B3-09.02`, `B9-04.01` | Fixture seti |
| D23 | Skill/MCP önerisinde yerel arama/skor yöntemi (deterministik kurallar; LLM opsiyonel) ve test veri kümesi | `B4-03.01/.02` | Kural/ölçüt belgesi |
| D24 | B5-00.01'de rakip yeteneklerinin shipped/beta/planned/paid ayrımı (bu belge yapmaz) | `B5-00.01` | Tarihli matris |
