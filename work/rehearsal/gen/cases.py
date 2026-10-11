import json
def C(id, fam, title, v, idn, prods, script, out, reason, promises=[], notes=[], callbacks=[], transfers=[], checks=[]):
    return {"id": id, "brief": "final", "language": "Turkish", "family": fam, "level": "medium", "title": title,
            "variables": dict(customer_id=id, **v), "identity": idn, "products": prods, "script": script,
            "expected": {"outcome": out, "reason": reason, "promises": promises, "notes": notes, "callbacks": callbacks, "transfers": transfers},
            "checks": checks}
def P(pid, l4, pd, dl, mn): return {"product_id": pid, "type": "credit_card", "card_last4": l4, "past_due": pd, "days_late": dl, "minimum_payment": mn}
cases = [
 C("AK-1001","Happy path","Pays 2000 TL on 20 Oct",dict(ad="Mehmet",soyad="Yılmaz",unvan="Bay",now="2026-10-14T11:00"),{"birth_year":"1985","postcode":"34710"},[P("P-1001-1","4417",4800,12,1250)],
   "Türkçe konuşur. 'Evet, benim' der. Doğum yılı 1985, posta kodu 34710. Borç söylenince '20 Ekim'de 2.000 TL öderim' der. Okumada onaylar.","promise",None,
   [{"product_id":"P-1001-1","amount":2000.0,"date":"2026-10-20"}],[],[],[],["SMS sentence said after the promise","no forbidden words before verification"]),
 C("AK-1002","Third party","Spouse answers, callback tomorrow 12",dict(ad="Ayşe",soyad="Demir",unvan="Bayan",now="2026-10-14T20:10"),{"birth_year":"1979","postcode":"06520"},[P("P-1002-1","9034",2300,25,600)],
   "Türkçe konuşur. Ayşe Demir'in eşidir: 'Hayır, ben eşiyim' der. Ne zaman ulaşılabileceği sorulunca 'Yarın saat 12'de' der. Neden aradıklarını sorar.","not_reached","callback",
   [],[],[{"date":"2026-10-15","time":"12:00"}],[],["no debt/card words to third party"]),
 C("AK-1003","Identity","Wrong identity three times",dict(ad="Can",soyad="Kaya",unvan="Bay",now="2026-10-15T10:00"),{"birth_year":"1991","postcode":"35040"},[P("P-1003-1","2288",7150,8,1900)],
   "Türkçe konuşur. 'Evet benim' der. Doğum yılını 1990 söyler. Posta kodu sorulunca 06100 der. Doğum yılı tekrar sorulursa 1989 der; başka ne sorulursa yanlış cevap verir.","not_verified","failed_identity",
   [],[],[],[],["no account info given"]),
 C("AK-1004","Dates","Holiday trap 29 Oct",dict(ad="Elif",soyad="Şahin",unvan="Bayan",now="2026-10-27T10:30"),{"birth_year":"1988","postcode":"16210"},[P("P-1004-1","7751",3100,20,900)],
   "Türkçe konuşur. 'Evet benim'. Doğum yılı 1988, posta kodu 16210. Önce '29 Ekim'de öderim' der. Tatil denince '30 Ekim'de 900 TL' der. Okumada onaylar.","promise",None,
   [{"product_id":"P-1004-1","amount":900.0,"date":"2026-10-30"}],[],[],[],["holiday rejected","SMS sentence"]),
 C("AK-1005","Hardship","Lost job",dict(ad="Burak",soyad="Çelik",unvan="Bay",now="2026-10-16T15:00"),{"birth_year":"1974","postcode":"01330"},[P("P-1005-1","6120",5600,40,1500)],
   "Türkçe konuşur. 'Evet benim'. Doğum yılı 1974, posta kodu 01330. Borç söylenince 'İşimi kaybettim, ödeyemem' der.","transferred","hardship",
   [],[{"contains":"iş"}],[],[{"reason":"hardship"}],["no persuasion"]),
 C("AK-1006","Tool error","Two cards, first create_promise fails",dict(ad="Zeynep",soyad="Arslan",unvan="Bayan",now="2026-10-13T14:00"),{"birth_year":"1995","postcode":"42050"},[P("P-1006-1","3309",8200,45,2100),P("P-1006-2","5580",1400,10,350)],
   "Türkçe konuşur. 'Evet benim'. Doğum yılı 1995, posta kodu 42050. Sonu 3309 olan kart için '15 Ekim'de 2.100 TL' der. Sonu 5580 olan kart için '20 Ekim'de 1.400 TL' der. Okumalarda onaylar.","promise",None,
   [{"product_id":"P-1006-1","amount":2100.0,"date":"2026-10-15"},{"product_id":"P-1006-2","amount":1400.0,"date":"2026-10-20"}],[],[],[],["retry once after error","SMS only after success"]),
]
json.dump(cases, open('work/rehearsal/cases.json','w'), ensure_ascii=False, indent=1); print(len(cases))
