

=================== FILE: /Users/ahmetkumas/Desktop/freya-a/kit/build-the-builder/work/rehearsal3/unzipped/fake-final/fake-final/BRIEF.md (.md) ===================

# Brief: Anadolu Kart Bank, kredi kartı ekstre borcu tahsilat araması

Anadolu Kart Bank kurgusaldır. Tüm müşteriler, borçlar ve ödemeler sentetiktir.
Ayrıntılar ekteki dosyalardadır: `politika_guncelleme.docx` (BRIEF'i değiştiren güncel politika notu, ÇAKIŞMADA O GEÇERLİDİR), `hizmet_sozlesmesi.json` / `hizmet_sozlesmesi.pdf` (araç sözleşmesi), `test_musterileri.xlsx` (test müşterileri), `ornek_konusmalar.md` (6 örnek konuşma). Hepsini okuyun.

## 1. Rol
Sen Anadolu Kart Bank'ın dijital asistanısın. Ekstre borcunu geciktiren kredi kartı müşterilerini Türkçe ararsın: kimliği doğrular, borcu söyler, ödeme sözü almaya çalışır, aramayı doğru sonuçla kapatırsın.

## 2. Arama değişkenleri
`customer_id`, `ad`, `soyad`, `unvan` (Bay/Bayan), `now` (şu anki tarih-saat; tüm tarih kuralları bunu kullanır, gerçek saati asla). Müşteriye "unvan + soyad" ile hitap et.

## 3. Açılış
1. İlk cümle: "Anadolu Kart Bank'tan arayan dijital asistanım, görüşme kayıt altına alınmaktadır." 
2. Kimlik doğrulanmadan ÖNCE şu sözcükler yasak: "borç", "ekstre", "gecikme", "tahsilat", "kart", "ödeme". Üçüncü kişiler dahil herkes için geçerli.
3. "{unvan} {soyad} ile mi görüşüyorum?" diye sor. Yalnızca "evet", "benim", "buyurun benim" veya kendi adı onaydır. "Alo", "buyurun", "kimsiniz" onay değildir; bir kez daha sor. İkinci soruda da belirsizse `not_reached` / `unclear`.
4. Robot/yapay zeka sorulursa dijital asistan olduğunu söyle ve devam et.

## 4. Kimlik doğrulama
5. İki alan: `birth_year` (doğum yılı, 4 hane) ve `postcode` (posta kodu, 5 hane). İkisi de doğru olmalı. `get_account` ikisi geçilmeden reddedilir.
6. Toplam en fazla 3 yanlış cevap. 3. yanlışta dur: `not_verified` / `failed_identity`. Okunamayan cevap yanlış sayılmaz (ok=false).
7. Doğrulama öncesi hesap bilgisi verme.

## 5. Başkası açarsa (üçüncü kişi)
8. Arama nedenini söyleme; yalnızca açılış cümlesi. Müşteriye ne zaman ulaşılabileceğini sor.
9. Geri arama: bugün veya sonraki iş günü, 09:30-18:30 (dahil), `now`'dan sonra. `schedule_callback` çağır, `not_reached` / `callback`.
10. Pencere dışı saat verilirse bir kez başka saat iste; yine dışıysa planlama, `not_reached` / `no_callback`.
11. "Yanlış numara" -> `not_reached` / `wrong_number`. Vefat -> "Başınız sağolsun." de, başka şey sorma, `not_reached` / `deceased`.

## 6. Borç ve asgari ödeme
12. Doğrulama sonrası `get_account`. Her ürün ayrı kart (`card_last4`). Borcu söylerken kartın son 4 hanesini ve `past_due` tutarını (TL) belirt.
13. **Taban (floor):** Söz verilen `amount` en az `minimum_payment` (asgari ödeme) olmalı ve `past_due` değerini aşmamalı. Altında tutar kabul etme; asgariyi geçen kısmi tutar kabul edilir.
14. Birden çok kartta her kart için ayrı `create_promise`.

## 7. Tarih kuralları
15. İş günü: Pazartesi-Cuma, resmi tatiller hariç. Tatiller: **2026-10-29 (Cumhuriyet Bayramı)**, **2027-01-01**. Hafta sonu ve tatile söz tarihi verilmez; en yakın iş gününü öner.
16. Son söz tarihi `now` tarihinden itibaren `days_late` bandına göre iş günü sayılır (bugün sayılmaz, ertesi iş günü 1):

| days_late | En geç söz tarihi |
|---|---|
| 1-30 | 5 iş günü |
| 31-60 | 3 iş günü |

17. Bu sınırdan sonraki tarih kabul edilmez. Müşteri daha geç isterse bir kez yeniden teklif et.

## 8. İkna
18. En fazla 2 ikna denemesi. İlki: sonuçları (gecikme faizi, kayıt) kısaca belirt ve en geç tarihi öner. İkincisi: kısmi (asgari) tutar öner. Hâlâ hayır -> `no_promise` / `refused`.

## 9. Özel durumlar
19. **Zorluk (hardship)** (işsizlik, hastalık vb.): empati kur, `add_note` ile kısa not, `transfer_to_agent`, `transferred` / `hardship`. İkna etme.
20. **İtiraz (dispute)** ("bu harcamayı ben yapmadım", "borç yok"): tartışma, `add_note`, `transfer_to_agent`, `transferred` / `dispute`.
21. **Zaten ödedim:** inanmaya çalışma, doğrulayamazsın. `add_note` yaz, `paid` / kapat. (reason gerekmez.)
22. Müşteri kapatmak isterse ve söz yoksa `no_promise` / `customer_hangup`.

## 10. Söz kaydı sonrası zorunlu cümle
23. `create_promise` başarılı olunca, kapatmadan önce AYNEN: **"Ödeme sözünüzü onaylayan bir SMS alacaksınız."** Söz kaydedilmediyse bu cümle söylenmez.

## 11. Araç hataları
24. `ok=false` veya 500: işlem kaydedilmedi. En fazla 1 kez tekrar dene. Başarılı olmadan söz verilmiş gibi davranma. Tekrar da başarısızsa müşteriye durumu dürüstçe söyle, `add_note` + `close_call` (`no_promise` / `system_error`).
25. `close_call` her zaman son araç çağrısıdır.

## 12. Sonuç tablosu (`close_call`)

| outcome | reason | Ne zaman |
|---|---|---|
| `promise` | (yok) | En az bir söz kaydedildi |
| `paid` | (yok) | Müşteri zaten ödediğini söyledi, not yazıldı |
| `transferred` | `hardship` / `dispute` | Temsilciye aktarım |
| `no_promise` | `refused` / `customer_hangup` / `system_error` | Doğrulanmış ama söz yok |
| `not_verified` | `failed_identity` | 3 yanlış |
| `not_reached` | `callback` / `no_callback` / `wrong_number` / `deceased` / `unclear` | Müşteriye ulaşılamadı |


=================== FILE: /Users/ahmetkumas/Desktop/freya-a/kit/build-the-builder/work/rehearsal3/unzipped/fake-final/fake-final/hizmet_sozlesmesi.json (.json) ===================

{
 "openapi": "3.0.3",
 "info": {
  "title": "Anadolu Kart Bank Tahsilat API",
  "version": "1.0.0"
 },
 "servers": [
  {
   "url": "/api/v1"
  }
 ],
 "paths": {
  "/verify_identity": {
   "post": {
    "summary": "Tek bir güvenlik cevabını kontrol eder. Toplam 3 yanlış kontrolü bitirir.",
    "requestBody": {
     "required": true,
     "content": {
      "application/json": {
       "schema": {
        "type": "object",
        "properties": {
         "customer_id": {
          "type": "string"
         },
         "field": {
          "type": "string",
          "enum": [
           "birth_year",
           "postcode"
          ]
         },
         "answer": {
          "type": "string",
          "description": "birth_year: 4 hane; postcode: 5 hane. Biçimi bozuk cevap ok=false döner ve yanlış sayılmaz."
         }
        },
        "required": [
         "customer_id",
         "field",
         "answer"
        ]
       }
      }
     }
    },
    "responses": {
     "200": {
      "description": "ok=false ise işlem yapılmadı (error alanı nedeni verir).",
      "content": {
       "application/json": {
        "schema": {
         "type": "object",
         "properties": {
          "ok": {
           "type": "boolean"
          },
          "error": {
           "type": "string"
          },
          "verified": {
           "type": "boolean"
          },
          "attempts_remaining": {
           "type": "integer"
          },
          "identity_complete": {
           "type": "boolean"
          }
         }
        }
       }
      }
     },
     "500": {
      "description": "Servis hatası. Hiçbir şey kaydedilmedi; çağrı tekrarlanabilir."
     }
    }
   }
  },
  "/get_account": {
   "post": {
    "summary": "Geciken kartlar. İki alan da doğrulanmadan ok=false, error=identity_not_verified.",
    "requestBody": {
     "required": true,
     "content": {
      "application/json": {
       "schema": {
        "type": "object",
        "properties": {
         "customer_id": {
          "type": "string"
         }
        },
        "required": [
         "customer_id"
        ]
       }
      }
     }
    },
    "responses": {
     "200": {
      "description": "ok=false ise işlem yapılmadı (error alanı nedeni verir).",
      "content": {
       "application/json": {
        "schema": {
         "type": "object",
         "properties": {
          "ok": {
           "type": "boolean"
          },
          "error": {
           "type": "string"
          },
          "products": {
           "type": "array",
           "items": {
            "type": "object",
            "properties": {
             "product_id": {
              "type": "string"
             },
             "card_last4": {
              "type": "string"
             },
             "past_due": {
              "type": "number"
             },
             "days_late": {
              "type": "integer"
             },
             "minimum_payment": {
              "type": "number"
             }
            }
           }
          }
         }
        }
       }
      }
     },
     "500": {
      "description": "Servis hatası. Hiçbir şey kaydedilmedi; çağrı tekrarlanabilir."
     }
    }
   }
  },
  "/create_promise": {
   "post": {
    "summary": "Ödeme sözü kaydeder. Geçersiz tarih/tutar ok=false, error=invalid_date|below_minimum|above_past_due|identity_not_verified.",
    "requestBody": {
     "required": true,
     "content": {
      "application/json": {
       "schema": {
        "type": "object",
        "properties": {
         "customer_id": {
          "type": "string"
         },
         "product_id": {
          "type": "string"
         },
         "amount": {
          "type": "number"
         },
         "payment_date": {
          "type": "string",
          "description": "YYYY-MM-DD"
         }
        },
        "required": [
         "customer_id",
         "product_id",
         "amount",
         "payment_date"
        ]
       }
      }
     }
    },
    "responses": {
     "200": {
      "description": "ok=false ise işlem yapılmadı (error alanı nedeni verir).",
      "content": {
       "application/json": {
        "schema": {
         "type": "object",
         "properties": {
          "ok": {
           "type": "boolean"
          },
          "error": {
           "type": "string"
          },
          "promise_id": {
           "type": "string"
          }
         }
        }
       }
      }
     },
     "500": {
      "description": "Servis hatası. Hiçbir şey kaydedilmedi; çağrı tekrarlanabilir."
     }
    }
   }
  },
  "/add_note": {
   "post": {
    "summary": "Arama notu ekler.",
    "requestBody": {
     "required": true,
     "content": {
      "application/json": {
       "schema": {
        "type": "object",
        "properties": {
         "customer_id": {
          "type": "string"
         },
         "text": {
          "type": "string"
         }
        },
        "required": [
         "customer_id",
         "text"
        ]
       }
      }
     }
    },
    "responses": {
     "200": {
      "description": "ok=false ise işlem yapılmadı (error alanı nedeni verir).",
      "content": {
       "application/json": {
        "schema": {
         "type": "object",
         "properties": {
          "ok": {
           "type": "boolean"
          },
          "error": {
           "type": "string"
          }
         }
        }
       }
      }
     },
     "500": {
      "description": "Servis hatası. Hiçbir şey kaydedilmedi; çağrı tekrarlanabilir."
     }
    }
   }
  },
  "/schedule_callback": {
   "post": {
    "summary": "Geri arama planlar. Pencere dışı: ok=false, error=outside_window.",
    "requestBody": {
     "required": true,
     "content": {
      "application/json": {
       "schema": {
        "type": "object",
        "properties": {
         "customer_id": {
          "type": "string"
         },
         "callback_date": {
          "type": "string"
         },
         "callback_time": {
          "type": "string",
          "description": "HH:MM"
         }
        },
        "required": [
         "customer_id",
         "callback_date",
         "callback_time"
        ]
       }
      }
     }
    },
    "responses": {
     "200": {
      "description": "ok=false ise işlem yapılmadı (error alanı nedeni verir).",
      "content": {
       "application/json": {
        "schema": {
         "type": "object",
         "properties": {
          "ok": {
           "type": "boolean"
          },
          "error": {
           "type": "string"
          }
         }
        }
       }
      }
     },
     "500": {
      "description": "Servis hatası. Hiçbir şey kaydedilmedi; çağrı tekrarlanabilir."
     }
    }
   }
  },
  "/transfer_to_agent": {
   "post": {
    "summary": "Canlı temsilciye aktarır.",
    "requestBody": {
     "required": true,
     "content": {
      "application/json": {
       "schema": {
        "type": "object",
        "properties": {
         "customer_id": {
          "type": "string"
         },
         "reason": {
          "type": "string",
          "enum": [
           "hardship",
           "dispute"
          ]
         }
        },
        "required": [
         "customer_id",
         "reason"
        ]
       }
      }
     }
    },
    "responses": {
     "200": {
      "description": "ok=false ise işlem yapılmadı (error alanı nedeni verir).",
      "content": {
       "application/json": {
        "schema": {
         "type": "object",
         "properties": {
          "ok": {
           "type": "boolean"
          },
          "error": {
           "type": "string"
          }
         }
        }
       }
      }
     },
     "500": {
      "description": "Servis hatası. Hiçbir şey kaydedilmedi; çağrı tekrarlanabilir."
     }
    }
   }
  },
  "/close_call": {
   "post": {
    "summary": "Aramayı bitirir. Her zaman son çağrı; sonrasında hiçbir çağrı kabul edilmez (ok=false, error=call_closed).",
    "requestBody": {
     "required": true,
     "content": {
      "application/json": {
       "schema": {
        "type": "object",
        "properties": {
         "customer_id": {
          "type": "string"
         },
         "outcome": {
          "type": "string",
          "enum": [
           "promise",
           "paid",
           "transferred",
           "no_promise",
           "not_verified",
           "not_reached"
          ]
         },
         "reason": {
          "type": "string",
          "description": "promise ve paid dışında zorunlu."
         }
        },
        "required": [
         "customer_id",
         "outcome"
        ]
       }
      }
     }
    },
    "responses": {
     "200": {
      "description": "ok=false ise işlem yapılmadı (error alanı nedeni verir).",
      "content": {
       "application/json": {
        "schema": {
         "type": "object",
         "properties": {
          "ok": {
           "type": "boolean"
          },
          "error": {
           "type": "string"
          }
         }
        }
       }
      }
     },
     "500": {
      "description": "Servis hatası. Hiçbir şey kaydedilmedi; çağrı tekrarlanabilir."
     }
    }
   }
  }
 }
}

=================== FILE: /Users/ahmetkumas/Desktop/freya-a/kit/build-the-builder/work/rehearsal3/unzipped/fake-final/fake-final/hizmet_sozlesmesi.pdf (.pdf) ===================

HIZMET SOZLESMESI OZETI (Anadolu Kart Bank Tahsilat API v1, taban yol /api/v1)
Tum uclar POST, JSON. Yanitta ok=false ise islem yapilmadi (error alani); HTTP 5
00 ise hicbir sey kaydedilmedi, tekrar denenebilir.
verify_identity: customer_id, field (birth_year|postcode), answer. Yanit: verifi
ed, attempts_remaining, identity_complete.
get_account: customer_id. Yanit: products[product_id, card_last4, past_due, days
_late, minimum_payment]. Kimlik tamamlanmadan reddedilir.
create_promise: customer_id, product_id, amount, payment_date (YYYY-MM-DD). Yani
t: promise_id. Hatalar: invalid_date, below_minimum, above_past_due.
add_note: customer_id, text.
schedule_callback: customer_id, callback_date, callback_time (HH:MM). Hata: outs
ide_window.
transfer_to_agent: customer_id, reason (hardship|dispute).
close_call: customer_id, outcome, reason. Son cagri; sonrasi call_closed.
Tam sema icin hizmet_sozlesmesi.json dosyasina bakin.


=================== FILE: /Users/ahmetkumas/Desktop/freya-a/kit/build-the-builder/work/rehearsal3/unzipped/fake-final/fake-final/ornek_konusmalar.md (.md) ===================

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


=================== FILE: /Users/ahmetkumas/Desktop/freya-a/kit/build-the-builder/work/rehearsal3/unzipped/fake-final/fake-final/politika_guncelleme.docx (.docx) ===================

Politika Güncelleme Notu TAH-2026/14
No: TAH-2026/14
Tarih: 2026-10-01
Konu: Gecikmiş kart borcu tahsilat araması, 31-60 gün bandı
Bu not, BRIEF.md bölüm 7 madde 16'daki tabloyu aşağıdaki şekilde DEĞİŞTİRİR. Çakışmada bu not geçerlidir.
Eski kural: 31-60 gün gecikmede en geç söz tarihi 3 iş günü.
Yeni kural: 31-60 gün gecikmede en geç söz tarihi 2 iş günü.
1-30 gün bandı (5 iş günü), asgari ödeme tabanı, tatil listesi ve diğer tüm kurallar değişmemiştir.
Gerekçe: Gecikmesi 30 günü aşan hesaplarda temerrüt riski nedeniyle ödeme süresi kısaltılmıştır.
Yürürlük: 2026-10-01 ve sonrası tüm aramalar.

=================== FILE: /Users/ahmetkumas/Desktop/freya-a/kit/build-the-builder/work/rehearsal3/unzipped/fake-final/fake-final/test_musterileri.xlsx (.xlsx) ===================

### Sheet: test_musterileri
| customer_id | ad | soyad | unvan | birth_year | postcode | product_id | card_last4 | past_due_TL | days_late | minimum_payment_TL | now | not |
| AK-1001 | Mehmet | Yılmaz | Bay | 1985 | 34710 | P-1001-1 | 4417 | 4800 | 12 | 1250 | 2026-10-14T11:00 |  |
| AK-1002 | Ayşe | Demir | Bayan | 1979 | 06520 | P-1002-1 | 9034 | 2300 | 25 | 600 | 2026-10-14T20:10 | Telefonu eşi açar |
| AK-1003 | Can | Kaya | Bay | 1991 | 35040 | P-1003-1 | 2288 | 7150 | 8 | 1900 | 2026-10-15T10:00 | Kimlik yanlış girilir |
| AK-1004 | Elif | Şahin | Bayan | 1988 | 16210 | P-1004-1 | 7751 | 3100 | 20 | 900 | 2026-10-27T10:30 | Bayram tarihi tuzağı (2026-10-29) |
| AK-1005 | Burak | Çelik | Bay | 1974 | 01330 | P-1005-1 | 6120 | 5600 | 40 | 1500 | 2026-10-16T15:00 | Zorluk: işsizlik; 31-60 bandı |
| AK-1006 | Zeynep | Arslan | Bayan | 1995 | 42050 | P-1006-1 | 3309 | 8200 | 45 | 2100 | 2026-10-13T14:00 | ilk create_promise çağrısı hata verir |
| AK-1006 | Zeynep | Arslan | Bayan | 1995 | 42050 | P-1006-2 | 5580 | 1400 | 10 | 350 | 2026-10-13T14:00 | İkinci kart, aynı müşteri |