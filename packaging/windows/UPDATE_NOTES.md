Respected Orchestrator, kodlama ajanlarını projenizde değil, yalıtılmış bir Git çalışma ağacında çalıştırır; sonucu denetler ve siz onaylamadan projenize hiçbir şey uygulamaz.

beta.2'de neler değişti:

- Gemini CLI kaldırıldı, yerine Antigravity (agy) kullanılır. Güncelleme ayarlarınızdaki Gemini seçimlerini kendiliğinden agy'ye taşır; AI araçlarındaki eski Gemini MCP girdisi `integrations set gemini=off` ile ya da kaldırırken temizlenir.
- Doğrulama ve kabul komutları artık ağsız, yalıtılmış bir kapta (AppContainer) çalışır; kap kurulamazsa doğrulama çalışmaz.
- Hub'da kanıt paneli: imzalı sonucu, eski/bozuk kanıtı ayırarak salt-okunur gösterir.
- GitHub: doğrulanmış sonuçtan taslak PR açma ve CI sonuçlarını yoklama (otomatik birleştirme yok).
- Projeler ve kampanyalar için doğrulanmış sürdürme noktaları.
- Gerçek ajanlarla karşılaştırmalı ölçüm altyapısı.
- Güncelleme verinizi yerinde taşır; beta.1'de oluşturduğunuz görevler, kampanyalar ve projeler okunur ve doğrulanır. Güncelleme yedeklidir: bir şey ters giderse önceki sürüm ve ayarlar kendiliğinden geri yüklenir.
- Hesap yok, telemetri yok.
