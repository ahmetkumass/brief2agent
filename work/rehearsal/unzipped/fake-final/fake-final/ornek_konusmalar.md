# 6 Örnek Konuşma (Anadolu Kart Bank)

## 1. Mutlu yol (AK-1001, now 2026-10-14T11:00, 12 gün gecikme, asgari 1.250 TL, borç 4.800 TL)
A: Anadolu Kart Bank'tan arayan dijital asistanım, görüşme kayıt altına alınmaktadır. Bay Yılmaz ile mi görüşüyorum?
M: Evet, benim.
A: Güvenliğiniz için doğum yılınızı söyler misiniz? M: 1985. A: Posta kodunuz? M: 34710.
A: Teşekkürler. Sonu 4417 ile biten kartınızda 4.800 TL gecikmiş borç var. En geç 2026-10-21'e kadar ödeyebilir misiniz?
M: 20 Ekim'de 2.000 TL öderim.
(Araçlar: verify_identity x2, get_account, create_promise{amount 2000, payment_date 2026-10-20}, close_call)
A: Ödeme sözünüzü onaylayan bir SMS alacaksınız.
Beklenen: `promise`.

## 2. Üçüncü kişi (AK-1002, now 2026-10-14T20:10)
A: (açılış cümlesi) Bayan Demir ile mi görüşüyorum? K: Hayır, eşi. A: Ne zaman ulaşabilirim? K: Yarın saat 12.
Not: now 20:10 ama yarın 12:00 pencere içi (09:30-18:30, sonraki iş günü). Borç/kart sözcüğü kullanılmaz.
(Araçlar: schedule_callback 2026-10-15 12:00, close_call)
Beklenen: `not_reached` / `callback`.

## 3. Yanlış kimlik (AK-1003)
M: Doğum yılım 1990 (yanlış). Posta kodu 06100 (yanlış). Tekrar: 1991 (yanlış).
Beklenen: 3. yanlışta dur, hesap bilgisi yok. `not_verified` / `failed_identity`.

## 4. Tatil tarihi (AK-1004, now 2026-10-27T10:30, 20 gün gecikme, asgari 900 TL)
M: 29 Ekim'de öderim. A: 29 Ekim Cumhuriyet Bayramı, iş günü değil. 5 iş günü sınırı 2026-11-04. 30 Ekim veya 2 Kasım uygun mu?
M: 30 Ekim, 900 TL.
Beklenen: create_promise payment_date 2026-10-30, amount 900; zorunlu SMS cümlesi; `promise`.

## 5. Zorluk (AK-1005)
M: İşimi kaybettim, ödeyemem. A: Anlıyorum, size yardımcı olabilecek bir temsilciye aktaracağım. (add_note "işsizlik", transfer_to_agent)
Beklenen: `transferred` / `hardship`. İkna denemesi yok.

## 6. Araç hatası (AK-1006, now 2026-10-13T14:00, 45 gün gecikme -> memo ile 2 iş günü)
M: 15 Ekim'de 1.600 TL. İlk create_promise -> 500/ok=false. A: tekrar dener, ikinci çağrı başarılı.
Beklenen: SMS cümlesi yalnızca başarılı çağrıdan sonra; `promise`. (İkinci de başarısız olsaydı: add_note + `no_promise` / `system_error`.)
