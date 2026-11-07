Respected Orchestrator, kodlama ajanlarını projenizde değil, yalıtılmış bir Git çalışma ağacında çalıştırır; sonucu denetler ve siz onaylamadan projenize hiçbir şey uygulamaz.

beta.3'te neler değişti:

- Orchestrator bağımsız bir üründür: kurucuda Hub yolu kalktı. Güncellemek için yeni sürümün kurucusunu GitHub sürüm sayfasından indirip çalıştırın; ayarlarınız ve görevleriniz korunur.
- Brain hafızası isteğe bağlı olarak durur: `memory connect` ile bağlanır, varsayılan kapalıdır.
- Hata iletileri artık yalnızca çalıştırabileceğiniz komutu söyler.

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
