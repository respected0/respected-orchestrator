Respected Orchestrator'a hoş geldiniz. Kodlama ajanlarını kendi projenizde değil, yalıtılmış bir Git çalışma ağacında çalıştırır; sonucu denetler ve siz onaylamadan projenize hiçbir şey uygulamaz. Ajanlar çalışır, karar sizde kalır.

Bu ilk beta sürümde her şey yenidir:

- Yalıtılmış çalışma: Her görev projenizin ayrı bir Git çalışma ağacında çalışır; asıl projeniz değişmez.
- Onay sizde: Sonuç yama olarak kaydedilir ve yalnızca denetimden geçerse, siz uygulayınca projenize girer. Orchestrator commit atmaz.
- Denetim: Kapsam, doğrulama komutları, imzalı kanıt ve yamanın projeye hâlâ uyması denetlenir; bekleyen, başarısız, bayat ya da kurcalanmış sonuç reddedilir.
- Kendi ajanınız: Codex, Claude, Gemini, Antigravity, Cursor ya da kendi komutunuz.
- Okuma ve yazma görevleri: Okuma görevi dosya değiştirmez. Yazma görevi en az bir doğrulama komutu ve değişecek dosyaları kapsayan izin listesi ister; yasak yollar ve süre sınırı verilebilir.
- Arka planda çalışır: Görevler terminali ya da Hub'ı kapatsanız da sürer; durdurma, iptal ve yeniden deneme (en çok üç deneme) vardır.
- Gözden geçirmeli iş akışı: Uygulama, gözden geçirme ve en çok iki düzeltme turu; sonucu bir insan onaylar.
- Büyük işler: Hedeften çok aşamalı proje planı çıkarır, projeleri yürütür, kampanyalarda paralel hatları sürdürüp sonunda son inceleme yaptırır. Roller (planlayıcı, uygulayıcı, gözden geçiren) istediğiniz araca atanır; isterseniz geçmiş başarıya göre otomatik önerilir ve gözden geçirenin işi yapandan farklı olması zorunlu tutulur.
- AI araçlarına MCP: Claude Code, Claude Desktop, Codex, Cursor, Gemini ve Windsurf'e MCP sunucusu olarak kaydedilir; örneğin Claude Code'a "şu işi Codex'e yaptır, sonucu doğrula" diyebilirsiniz. MCP'den verilen işlerde özel komut, otomatik uygulama ve insan onayı reddedilir; doğrulama komutları yalnızca önceden izin verdiğiniz öneklerle çalışır.
- Ortak hafıza (isteğe bağlı): Ortak hafıza ürünü kuruluysa ve izin verirseniz görevler ilgili notlardan kısa parçalar alır (güvenilmeyen veri olarak işaretlenir); yazma izni verirseniz kalıcı kararlar gelen kutusuna not olarak bırakılır.
- Hub'da çalışma alanı: Görevler, kampanyalar, kanıtlar, ajanlar ve ayarlar Hub'da görsel olarak durur; komut satırı bilmeden görev verip sonucu doğrulatabilirsiniz.
- Güvenli kurulum: Orchestrator AI araçlarının ayar dosyasına yalnızca kendi girdisini ekler ve kaldırır; projelerinize dokunmaz. Python ve yönetici izni gerekmez; Git ve görevleri yapacak bir AI aracının komut satırı gerekir.
- Güncelleme yedekli: Bir şey ters giderse önceki sürüm ve ayarlar kendiliğinden geri yüklenir.
- Hesap yok, telemetri yok.
