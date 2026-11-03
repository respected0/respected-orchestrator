# ADP-01 timeout senaryosu kararı

- İlk bütçe 20 saniyeydi; model `read` görevini 20 saniyeden önce yanıtladığı için senaryo `completed`
  döndü ve `timed_out` beklentisi karşılanmadı. Bu bir sahte başarı olarak kabul edilmedi.
- Kimlik köprüsü ölçümü: auth export/import tamamlanıyor, ardından gerçek model yanıtı geliyor.
  3 s, 5 s ve 8 s bütçelerinin üçünde de senaryo `timed_out` döndü; hiçbirinde `AUTH_REQUIRED` görülmedi.
- Bu nedenle harness bütçesi 8 saniyeye çekildi. Amaç kimlik köprüsünü tamamlayıp model yanıtından önce kesmek;
  8 s bunu yaparken modelin gerçek yanıt süresinin altında kalıyor.
- ACP kimlik köprüsünde değişiklik gerekmedi: `AUTH_REQUIRED` hatası yoktu, mevcut bridge doğru çalıştı.
- Nihai E2E: timeout = `timed_out`; diğer senaryolar beklendiği gibi.