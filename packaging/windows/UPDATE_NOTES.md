Respected Orchestrator, kodlama ajanlarını projenizde değil, yalıtılmış bir Git çalışma ağacında çalıştırır; sonucu denetler ve siz onaylamadan projenize hiçbir şey uygulamaz.

beta.4'te neler değişti:

- Akıllı yönlendirme: görev türü sınıflandırılır; hangi aracın hangi göreve uygun olduğu açık gerekçeyle önerilir. Sizin açıkça yaptığınız atama her zaman korunur, hiçbir şey sessizce değiştirilmez.
- Takım profilleri ve devirler: roller, araçlar ve yetkiler tek yerde tanımlanır; ajanlar arası devirler sınırlıdır ve insana yükseltme kaydedilir. Yeni "Takım" ekranı yalnızca okunur.
- Kullanım ve maliyet kaydı: ajanın bildirdiği kullanım ile tahmin ayrı tutulur; bilinmeyen değer sıfır sayılmaz. "Bütçe ve başarı" ekranı salt okunurdur.
- Yetenek önerileri: göreve uygun, kurulu MCP sunucusu ve becerileri nedenleriyle önerir. Hiçbir şey kurmaz, açmaz veya çalıştırmaz.
- Bağlam hazırlığı ve kurtarma: görev öncesi sınırlı bağlam özeti; yarıda kalan işler için sınıflandırılmış kurtarma vakaları ve operatör eylemleri.
- Sesli görev taslağı (isteğe bağlı, varsayılan kapalı): bas-konuş ile konuşursunuz, ses yalnızca bellekte tutulur, diske yazılmaz ve sizin seçtiğiniz yerel bir konuşma tanıma programıyla metne çevrilir. Çıkan metin yalnızca bir taslaktır; okuyup onaylamadan hiçbir yere gitmez ve ses hiçbir zaman çalıştırma, onay veya uygulama komutu olmaz. Orchestrator konuşma modeli indirmez veya kurmaz.
- Ekran görüntüsü ekleme (isteğe bağlı, varsayılan kapalı): seçtiğiniz veya yapıştırdığınız PNG/JPEG üstveriden arındırılır, gizlemek istediğiniz yerleri karartırsınız, önizlersiniz ve yalnızca henüz başlamamış bir çalıştırmaya, ayrı bir onay penceresiyle eklenir. Bir modelle paylaşmak ayrı, süreli bir onaydır; şu an hiçbir ajan görüntüyü dışarı göndermez.
- Bilinen sınırlar: kurucu henüz Authenticode ile imzalı değildir, Windows SmartScreen uyarı gösterebilir. Ses ve ekran görüntüsü özellikleri gerçek mikrofon ve işletim sistemi onay penceresiyle elle denenmedi; Türkçe konuşma doğruluğu ölçülmedi. Akıllı yönlendirmenin kazanç iddiası için gerçek ajan karşılaştırması sonraki sürümlere kaldı. Sohbet oturumları deneyseldir ve varsayılan olarak kapalıdır.

beta.3'te neler değişti:

- Yeni masaüstü uygulaması: kurucuyla birlikte gelir, motoru kendi başlatır; çalışmaları, kanıtları, projeleri ve ayarları tek pencerede gösterir. Komut satırı aynen çalışmaya devam eder.
- Orchestrator bağımsız bir üründür: kurucudan Hub yolu kalktı. Güncellemek için yeni sürümün kurucusunu GitHub sürüm sayfasından indirip çalıştırın; kurucu önce yedek alır, ayarlarınızı ve görevlerinizi korur, bir şey ters giderse önceki sürümü geri yükler. beta.1 ve beta.2 verileri okunur ve taşınır.
- Güncelleme penceresi: çalışan iş varsa kurucu bunu görür ve işi güvenle durdurur; çalışıp çalışmadığı gerçek süreç denetimiyle bulunur.
- Daha sağlam çalışma kaydı: tek sahipli denetleyici, çökmeye dayanıklı olay günlüğü ve etkinlik zaman çizgisi.
- Daha güvenli yama uygulama: uygulamadan önce durum yeniden doğrulanır, çakışma ve yarış durumlarına karşı korunur, uygulanan yama geri alınabilir. Hiçbir sonuç siz onaylamadan uygulanmaz.
- İnceleme ve kanıt görünümü; sınırlı ve maskelenmiş kanıt dosyası okuyucu.
- Ajan araçları dürüst durumla bulunur (`agy` bulunamıyordu, düzeltildi); rol, araç ve model atamaları açık farkla düzenlenir, sessizce değiştirilmez.
- Salt-okunur MCP/skill envanteri: hangi AI aracında neyin kayıtlı olduğunu gösterir, hiçbir şeyi değiştirmez.
- Projeler için plan görünümü, plan düzenleme, tekrar denemeye dayanıklı iptal ve sürdürme.
- Brain hafızası isteğe bağlıdır: `memory connect` ile bağlanır, varsayılan kapalıdır. Hata iletileri artık yalnızca çalıştırabileceğiniz komutu söyler.
- Bilinen sınırlar: kurucu henüz Authenticode ile imzalı değildir, Windows SmartScreen uyarı gösterebilir. Sohbet oturumları deneyseldir ve varsayılan olarak kapalıdır.

beta.2'de neler değişti:

- Güncelleme sırasında çalışan proje veya kampanya durdurulur.
- Güncelleme verinizi yerinde taşır; beta.1'de oluşturduğunuz görevler, kampanyalar ve projeler okunur ve doğrulanır. beta.1'de yarıda kalmış bir proje varsa güncellemeden sonra kendiliğinden sürmez; `project-approve` ile onaylayıp sürdürürsünüz. Güncelleme yedeklidir: bir şey ters giderse önceki sürüm ve ayarlar kendiliğinden geri yüklenir.
- Gemini CLI kaldırıldı, yerine Antigravity (agy) kullanılır; güncelleme Gemini ayarlarınızı agy'ye taşır, eski Gemini MCP girdisi `integrations set gemini=off` ile temizlenir.
- Doğrulama ve kabul komutları artık ağsız, yalıtılmış bir kapta (AppContainer) çalışır; kap kurulamazsa doğrulama çalışmaz.
- Kanıt paneli: imzalı sonucu, eski/bozuk kanıtı ayırarak salt-okunur gösterir.
- GitHub: doğrulanmış sonuçtan taslak PR açma ve CI sonuçlarını yoklama (otomatik birleştirme yok).
- Projeler ve kampanyalar için doğrulanmış sürdürme noktaları.
- Gerçek ajanlarla karşılaştırmalı ölçüm altyapısı.
- Hesap yok, telemetri yok.
