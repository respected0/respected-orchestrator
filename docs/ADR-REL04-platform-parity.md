# ADR-REL04 — macOS/Linux güvenlik eşdeğerliği ve platform kararı

- **Durum:** Kabul edildi (3 Kasım 2026)
- **Bağlam:** Windows worker izolasyonu `SEC-03`/`SEC-04` ile ölçüldü. POSIX'te anahtar saklama, süreç izolasyonu,
  symlink/junction eşdeğeri ve kurucu geri alma davranışı henüz ölçülmedi.
- **Karar:** Windows GA'dır; ancak yayın yalnızca aşağıdaki 10 güvenlik fixture'ı `pass` olduğunda `go` olur.
  macOS ve Linux, aynı 10 fixture ve kurucu geri alma kanıtı tamamlanana kadar GA değildir. Kanıtsız platformda
  sessiz daraltma (sandbox-off) yapılmaz; destek yoksa çalıştırma reddedilir.
- **Gerekli fixture'lar (her OS):** `permission`, `symlink`, `network`, `child_tree`, `key_read`, `migration`,
  `installer_rollback`, `janitor`, `secret_env`, `mcp_recursion`.
- **Kapı:** `release_platform.decide()` kırmızı veya eksik fixture'da `no-go` döndürür; POSIX için sonuç her durumda
  `no-go`dur. Karar kodu `src/respected_orchestrator/release_platform.py`, testleri
  `tests/packaging/test_release_platform.py`.
- **Sonuçlar:** Bu makinede POSIX fixture koşusu yapılmadı; uydurma başarı yok. Windows fixture matrisi kaynak
  testlerine dayanır; gerçek kurucu ve imza kanıtı `REL-01` kapsamındadır.