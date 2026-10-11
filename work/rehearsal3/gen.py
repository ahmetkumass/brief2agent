import json, pathlib
BASE = "https://freya-bank-rehearsal2.ahmetkumas-freya.workers.dev/api/v1"
OUT = pathlib.Path(__file__).resolve().parents[2] / "out" / "rehearsal3.workflow.json"
H = {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}}

CAL_COMMON = r'''
HOLIDAYS = dict()
HOLIDAYS['2026-10-29'] = 'Cumhuriyet Bayramı'
HOLIDAYS['2027-01-01'] = 'Yılbaşı'
NAMES = ['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']
def is_bd(d):
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS
def nth_bd_after(d, n):
    c, k = d, 0
    while k < n:
        c = c + datetime.timedelta(days=1)
        if is_bd(c): k += 1
    return c
now = str(vars.get('now') or '')
today = datetime.date.fromisoformat(now[:10])
'''

SETUP = "import datetime\ntry:\n" + "\n".join("    " + l for l in CAL_COMMON.strip("\n").split("\n")) + r'''
    rows = []
    for i in range(0, 46):
        d = today + datetime.timedelta(days=i)
        if is_bd(d): tag = 'iş günü'
        elif d.isoformat() in HOLIDAYS: tag = 'RESMİ TATİL (' + HOLIDAYS[d.isoformat()] + ') - iş günü değil'
        else: tag = 'hafta sonu - iş günü değil'
        rows.append(d.isoformat() + ' ' + NAMES[d.weekday()] + ' - ' + tag)
    t = now[11:16]
    nb = nth_bd_after(today, 1)
    cb = []
    if is_bd(today) and t < '18:30':
        cb.append('BUGÜN ' + today.isoformat() + ': ' + (t if t > '09:30' else '09:30') + ' sonrası ile 18:30 arası (18:30 dahil)')
    else:
        cb.append('Bugün geri arama yapılamaz (saat ' + t + ' veya iş günü değil).')
    cb.append('SONRAKİ İŞ GÜNÜ ' + nb.isoformat() + ' ' + NAMES[nb.weekday()] + ': 09:30 ile 18:30 arası (ikisi de dahil)')
    cb.append('Bunların dışındaki her gün/saat PENCERE DIŞI.')
    vars['today'] = today.isoformat()
    vars['now_time'] = t
    vars['cb_text'] = '\n'.join(cb)
    vars['cal_text'] = 'Bugün ' + today.isoformat() + ' ' + NAMES[today.weekday()] + ', saat ' + t + '.\nTakvim:\n' + '\n'.join(rows)
    vars['setup_state'] = 'ok'
except Exception as e:
    vars['cal_text'] = 'Takvim yok'
    vars['cb_text'] = 'Bilinmiyor'
    vars['setup_state'] = 'error'
'''

FACTS = "import json, ast, datetime\ntry:\n" + "\n".join("    " + l for l in CAL_COMMON.strip("\n").split("\n")) + r'''
    def load(v):
        if isinstance(v, list): return v
        if isinstance(v, str) and v.strip():
            for f in (json.loads, ast.literal_eval):
                try:
                    x = f(v)
                    if isinstance(x, list): return x
                except Exception: pass
        return None
    prods = load(vars.get('products'))
    if prods is None:
        prods = []
        for prefix in ('load_account_response.data.products.', 'get_account_response.data.products.'):
            i = 0
            while (prefix + str(i) + '.product_id') in vars:
                p = dict()
                for k in ('product_id','card_last4','past_due','days_late','minimum_payment'):
                    kk = prefix + str(i) + '.' + k
                    if kk in vars: p[k] = vars[kk]
                prods.append(p); i += 1
            if prods: break
    def money(x):
        x = float(x)
        if x == int(x):
            return format(int(x), ',').replace(',', '.') + ' TL'
        return format(x, ',.2f').replace(',', 'X').replace('.', ',').replace('X', '.') + ' TL'
    def num(x):
        x = float(x)
        return str(int(x)) if x == int(x) else str(round(x, 2))
    debt = []
    plan = []
    n = 0
    for p in prods:
        n += 1
        pid = str(p.get('product_id'))
        l4 = str(p.get('card_last4'))
        full = float(p.get('past_due') or 0)
        mn = float(p.get('minimum_payment') or 0)
        dl_days = int(float(p.get('days_late') or 0))
        bdn = 5 if dl_days <= 30 else 2
        dl = nth_bd_after(today, bdn)
        debt.append('KART ' + str(n) + ': sonu ' + l4 + ' ile biten kart, gecikmiş borç ' + money(full) + ' (asgari ödeme ' + money(mn) + '), product_id=' + pid)
        lines = []
        for i in range(0, 46):
            d = today + datetime.timedelta(days=i)
            if i == 0: ans = ('KABUL ' + d.isoformat() + ' (bugün)') if is_bd(d) else ('iş günü değil -> ' + nth_bd_after(d, 1).isoformat() + ' öner')
            elif d > dl: ans = 'SINIRDAN SONRA -> en geç ' + dl.isoformat() + ' olabileceğini söyle ve onu öner'
            elif is_bd(d): ans = 'KABUL ' + d.isoformat()
            else:
                nbd = nth_bd_after(d, 1)
                why = HOLIDAYS.get(d.isoformat(), 'hafta sonu')
                ans = ('İŞ GÜNÜ DEĞİL (' + why + ') -> ' + nbd.isoformat() + ' öner') if nbd <= dl else ('İŞ GÜNÜ DEĞİL (' + why + ') -> ' + dl.isoformat() + ' öner')
            lines.append('  ' + d.isoformat() + ' ' + NAMES[d.weekday()] + ': ' + ans)
        plan.append('=== KART ' + str(n) + ' (sonu ' + l4 + ', product_id=' + pid + ') ===\n'
            + 'Gecikme ' + str(dl_days) + ' gün -> en geç söz tarihi ' + str(bdn) + ' iş günü: ' + dl.isoformat() + ' ' + NAMES[dl.weekday()] + '.\n'
            + 'TUTAR KURALI: tam borç ' + money(full) + ' (araca ' + num(full) + '). Taban (asgari) ' + money(mn) + ' (araca ' + num(mn) + '). Müşterinin söylediği tutar ' + num(mn) + ' ile ' + num(full) + ' arasındaysa (dahil) AYNEN o tutarı kabul et. ' + num(mn) + ' altındaysa kabul etme: asgarinin ' + money(mn) + ' olduğunu söyle. ' + num(full) + ' üstündeyse en fazla ' + money(full) + ' olabileceğini söyle.\n'
            + 'İKNA BASAMAKLARI (her biri bir kez):\n'
            + '  ADIM 0: Borcu söyle ve sor: "' + money(full) + ' tutarı en geç ' + dl.isoformat() + ' tarihine kadar ödeyebilir misiniz?"\n'
            + '  ADIM 1 (ilk ret/isteksizlik): gecikme faizi işleyeceğini ve gecikmenin kayıtlara geçeceğini kısaca söyle; ' + money(full) + ' için en geç ' + dl.isoformat() + ' tarihini öner.\n'
            + '  ADIM 2 (ikinci ret): asgari ödeme ' + money(mn) + ' tutarını en geç ' + dl.isoformat() + ' tarihine kadar öner.\n'
            + '  ADIM 2 sonrası yine hayır: bu kart için söz yok (refused).\n'
            + 'TARİH TABLOSU (müşterinin tarihini bul, satırın dediğini yap):\n' + '\n'.join(lines))
    vars['debt_text'] = '\n'.join(debt)
    vars['plan_text'] = '\n\n'.join(plan)
    vars['n_products'] = str(len(prods))
    vars['facts_state'] = 'ok' if prods else 'empty'
except Exception as e:
    vars['debt_text'] = 'Hesap bilgisi alınamadı: ' + str(e)[:100]
    vars['plan_text'] = ''
    vars['facts_state'] = 'error'
'''

def api_tool(name, desc, props, required, pre=None, post=None, mapping=None):
    body = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    body.update(props)
    t = {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": 0},
         "function": {"name": name, "handler": "__function__:api_call", "description": desc,
                      "parameters": {"type": "object", "properties": {
                          "url": {"type": "string", "default": BASE + "/" + name},
                          "method": {"type": "string", "default": "POST"},
                          "headers": H,
                          "body": {"type": "object", "properties": body, "required": required}}}}}
    if pre: t["pre_process_code"] = pre
    if post: t["post_process_code"] = post
    if mapping: t["response_mapping"] = mapping
    return t

POST_HEAD = r'''try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        failed = d.get('ok') is False or int(result.get('status_code', 200) or 200) >= 500 or result.get('status') not in (None, 'success')
'''
POST_TAIL = r'''
except Exception:
    pass
'''
def post(body):
    return POST_HEAD + "\n".join("        " + l for l in body.strip("\n").split("\n")) + POST_TAIL

VERIFY_PRE = r'''try:
    import re
    b = config.get('body')
    if isinstance(b, dict):
        a = re.sub('[^0-9]', '', str(b.get('answer') or ''))
        f = str(b.get('field') or '')
        if f == 'birth_year' and len(a) == 2:
            a = ('19' + a) if int(a) > 26 else ('20' + a)
        if f == 'postcode' and len(a) == 4:
            a = '0' + a
        b['answer'] = a if a else str(b.get('answer') or '')
except Exception:
    pass
'''
VERIFY_POST = post(r'''
if failed and str(d.get('error') or '') == 'call_closed':
    d['what_to_do_next'] = 'Arama sistemde kapalı. Vedalaş ve close_call çağır.'
elif failed:
    d['what_to_do_next'] = 'Cevap işlenemedi (yanlış sayılmadı). Aynı soruyu müşteriye nazikçe bir kez daha sor, net 4 haneli yıl / 5 haneli posta kodu iste.'
else:
    left = d.get('attempts_remaining')
    if str(d.get('identity_complete')) in ('True', 'true'):
        vars['id_state'] = 'verified'
        d['what_to_do_next'] = 'Kimlik doğrulandı. Kısaca teşekkür et.'
    elif str(d.get('verified')) in ('True', 'true'):
        d['what_to_do_next'] = 'Bu cevap doğru. Şimdi diğer soruyu sor (doğum yılı doğrulandıysa posta kodunu sor).'
    elif left is not None and int(left) <= 0:
        vars['id_state'] = 'failed'
        d['what_to_do_next'] = 'Kimlik doğrulanamadı, 3 yanlış. Hesap hakkında hiçbir şey söyleme. Aynı turda: kimliğinizi doğrulayamadığımızı, bu nedenle devam edemediğimizi söyle, teşekkür edip vedalaş VE close_call(outcome=not_verified, reason=failed_identity) çağır.'
    else:
        d['what_to_do_next'] = 'Bu cevap doğru değil. Kalan hak: ' + str(left) + '. Müşteriye bilginin eşleşmediğini söyle ve AYNI soruyu tekrar sor.'
''')

PROMISE_PRE = r'''try:
    b = config.get('body')
    if isinstance(b, dict):
        vars['last_pid'] = str(b.get('product_id') or '')
        s = str(b.get('amount') or '').replace('TL', '').strip()
        if s.count('.') and s.count(','):
            s = s.replace('.', '').replace(',', '.')
        elif s.count(',') == 1 and len(s.split(',')[1]) == 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '').replace('.', '') if (s.count('.') and len(s.split('.')[-1]) == 3) else s
        try:
            b['amount'] = float(s)
        except Exception:
            pass
except Exception:
    pass
'''
PROMISE_POST = post(r'''
pid = str(vars.get('last_pid') or '')
err = str(d.get('error') or '')
if failed and err in ('invalid_date', 'below_minimum', 'above_past_due'):
    d['what_to_do_next'] = 'KAYDEDİLMEDİ (' + err + '). Kayıt olmadığını söyleme; tarih/tutar kurala uymuyor. TARİH TABLOSU ve TUTAR KURALI ile geçerli bir değer öner, müşteri onaylarsa yeniden çağır.'
elif failed:
    k = 'pfail_' + pid
    n = int(vars.get(k) or 0) + 1
    vars[k] = n
    if n < 2:
        d['what_to_do_next'] = 'KAYDEDİLMEDİ (sistem hatası). Müşteriye bir şey söylemeden, hemen create_promise aracını AYNI değerlerle bir kez daha çağır.'
    else:
        d['what_to_do_next'] = 'İkinci deneme de başarısız, söz KAYDEDİLEMEDİ. SMS cümlesini SÖYLEME. Müşteriye dürüstçe teknik bir sorun nedeniyle sözü sisteme işleyemediğini söyle, add_note ile not yaz (sistem hatası, söz kaydedilemedi, tutar ve tarih), sonra vedalaşıp close_call çağır (bu aramada başka kayıtlı söz yoksa outcome=no_promise reason=system_error; varsa outcome=promise).'
else:
    vars['promises_ok'] = int(vars.get('promises_ok') or 0) + 1
    vars['ok_' + pid] = 'yes'
    d['what_to_do_next'] = 'Söz başarıyla kaydedildi. Şimdi AYNEN söyle: "Ödeme sözünüzü onaylayan bir SMS alacaksınız." Başka söz bekleyen kart varsa ona geç; yoksa teşekkür edip vedalaş ve close_call(outcome=promise) çağır.'
''')

SIMPLE_POST = lambda okmsg: post(r'''
if failed:
    d['what_to_do_next'] = 'İşlem BAŞARISIZ, yapılmadı. Bir kez aynı değerlerle tekrar dene. Yapıldı deme.'
else:
    d['what_to_do_next'] = '%s'
''' % okmsg)

CB_POST = post(r'''
err = str(d.get('error') or '')
if failed and err == 'outside_window':
    n = int(vars.get('cb_out') or 0) + 1
    vars['cb_out'] = n
    d['what_to_do_next'] = 'Geri arama PLANLANMADI: saat pencere dışında. ' + ('Pencereyi söyleyip (bugün/sonraki iş günü 09:30-18:30) bir kez başka bir saat iste.' if n < 2 else 'Planlama yapma. Teşekkür edip vedalaş ve close_call(outcome=not_reached, reason=no_callback) çağır.')
elif failed:
    d['what_to_do_next'] = 'Geri arama PLANLANMADI (sistem hatası). Aynı değerlerle bir kez tekrar çağır.'
else:
    d['what_to_do_next'] = 'Geri arama planlandı. Saati teyit edip teşekkür et, vedalaş ve close_call(outcome=not_reached, reason=callback) çağır.'
''')

CLOSE_PRE = r'''try:
    b = config.get('body')
    if isinstance(b, dict) and b.get('outcome') in ('promise', 'paid'):
        b.pop('reason', None)
except Exception:
    pass
'''
CLOSE_POST = post(r'''
if not failed or str(d.get('error') or '') == 'call_closed':
    vars['closed'] = 'yes'
    d['what_to_do_next'] = 'Arama kapandı. Başka bir şey söyleme.'
else:
    d['what_to_do_next'] = 'Kapatma başarısız. close_call aracını bir kez daha çağır.'
''')

CLOSE_DESC = ("Aramayı bitirir; HER ZAMAN son araç. Önce aynı turda vedalaşma cümlesini söyle, sonra çağır. Tablo: "
  "promise (reason yok) = en az bir söz başarıyla kaydedildi; paid (reason yok) = müşteri zaten ödediğini söyledi ve add_note yazıldı; "
  "transferred+hardship / transferred+dispute = temsilciye aktarıldı; no_promise+refused = doğrulanmış, 2 ikna sonrası hâlâ hayır; "
  "no_promise+customer_hangup = doğrulanmış, söz yok, müşteri kapatmak istedi; no_promise+system_error = söz 2 kez kaydedilemedi; "
  "not_verified+failed_identity = 3 yanlış kimlik cevabı; not_reached+callback = üçüncü kişi, geri arama planlandı; "
  "not_reached+no_callback = pencere dışı saat iki kez / saat verilmedi; not_reached+wrong_number = yanlış numara; "
  "not_reached+deceased = müşteri vefat etmiş; not_reached+unclear = iki soruda da kişi teyit edilemedi.")

def close_tool():
    return api_tool("close_call", CLOSE_DESC, {
        "outcome": {"type": "string", "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"], "default": "{{outcome}}", "description": "Sonuç."},
        "reason": {"type": "string", "enum": ["hardship", "dispute", "refused", "customer_hangup", "system_error", "failed_identity", "callback", "no_callback", "wrong_number", "deceased", "unclear"], "default": "{{reason}}", "description": "promise ve paid için boş bırak; diğerlerinde zorunlu."}},
        ["outcome"], pre=CLOSE_PRE, post=CLOSE_POST)

verify = api_tool("verify_identity", "Müşteri bir güvenlik sorusunu her cevapladığında, o tek cevapla çağır.", {
    "field": {"type": "string", "enum": ["birth_year", "postcode"], "default": "{{field}}", "description": "birth_year = doğum yılı, postcode = posta kodu."},
    "answer": {"type": "string", "default": "{{answer}}", "description": "Rakamlarla: doğum yılı 4 hane (bin dokuz yüz seksen beş -> 1985), posta kodu 5 hane (otuz dört yedi yüz on -> 34710)."}},
    ["field", "answer"], pre=VERIFY_PRE, post=VERIFY_POST)
callback = api_tool("schedule_callback", "Üçüncü kişinin söylediği gün/saatte geri arama planlar. Yalnızca saat tekrarlanıp onaylandıktan sonra çağır.", {
    "callback_date": {"type": "string", "default": "{{callback_date}}", "description": "YYYY-MM-DD, takvimden."},
    "callback_time": {"type": "string", "default": "{{callback_time}}", "description": "HH:MM 24 saat (öğlen 12 -> 12:00, akşam 5 -> 17:00)."}},
    ["callback_date", "callback_time"], post=CB_POST)
promise = api_tool("create_promise", "Bir kart için ödeme sözü kaydeder. Yalnızca tutar ve tarihi okuyup müşteri açıkça 'evet' dedikten sonra çağır. Kart başına bir söz.", {
    "product_id": {"type": "string", "default": "{{product_id}}", "description": "KART satırındaki product_id, aynen kopyala."},
    "amount": {"type": "number", "default": "{{amount}}", "description": "TL tutarı düz sayı (iki bin -> 2000)."},
    "payment_date": {"type": "string", "default": "{{payment_date}}", "description": "YYYY-MM-DD, TARİH TABLOSU'nda KABUL olan bir tarih."}},
    ["product_id", "amount", "payment_date"], pre=PROMISE_PRE, post=PROMISE_POST)
note = api_tool("add_note", "Arama notu ekler (zorluk, itiraz, zaten ödedim, sistem hatası).", {
    "text": {"type": "string", "default": "{{note_text}}", "description": "Kısa Türkçe not, ilgili kartın son 4 hanesi ile."}},
    ["text"], post=SIMPLE_POST("Not eklendi. Sıradaki adıma geç (aktarım veya kapanış)."))
transfer = api_tool("transfer_to_agent", "Canlı temsilciye aktarır (zorluk veya itiraz). Önce add_note çağır.", {
    "reason": {"type": "string", "enum": ["hardship", "dispute"], "default": "{{transfer_reason}}", "description": "hardship = maddi zorluk; dispute = borca/harcamaya itiraz."}},
    ["reason"], post=SIMPLE_POST("Aktarım yapıldı. Müşteriye temsilciye aktarıldığını söyle, vedalaş ve close_call(outcome=transferred, reason=aynı neden) çağır."))

CLOSED_T = {"target_node": "goodbye", "description": "Arama kapandı", "condition": {"logic": "or", "conditions": [
    {"variable": "closed", "operator": "equals", "operand": "yes"},
    {"variable": "close_call_success_count", "operator": "greater_than", "operand": 0}]}}

def code_node(name, code, nxt):
    return {"name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": nxt,
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
            "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}]}

SYSTEM = """Sen Anadolu Kart Bank'ın dijital asistanısın; telefonda konuşuyorsun. YALNIZCA TÜRKÇE konuş. Her turda bir-iki kısa cümle, tek soru. Müşteriye "{{unvan}} {{soyad}}" diye hitap et.
Her araç sonucundan sonra what_to_do_next talimatını uygula ve hemen konuş ya da sıradaki aracı çağır; asla boş tur bırakma.
Bir araç ok=true dönmeden "kaydedildi/planlandı/aktarıldı" deme. Başarısız yazımda "işleyemedim" de.
Robot / yapay zeka musun diye sorulursa: "Ben Anadolu Kart Bank'ın dijital asistanıyım." de ve kaldığın yerden devam et (bu bir ret sayılmaz).
Dolandırıcılık şüphesi olursa: bankanın resmi numarasından arandığını, şifre veya kart bilgisi istemediğini söyle ve devam et.
Tarihleri doğal söyle (ör. "21 Ekim Çarşamba"), tutarları "4.800 TL" gibi. Tarih hesaplama; yalnızca verilen takvim/tablolara bak.
Müşterinin son söylediği değer geçerlidir. Cevap yarım kaldıysa veya düzeltme içeriyorsa ("pardon", "yani", "hayır", "şey", "yok yok") araç çağırma, değeri tekrar sor.
close_call her zaman son araçtır: önce aynı turda vedalaş (teşekkür + iyi günler), sonra close_call çağır."""

OPEN_TASK = """GÖREV: Doğru kişiye ulaşmak ve kimliği doğrulamak. Aramanın nedenini BİLMİYORSUN.
YASAK SÖZCÜKLER (kimlik doğrulanana kadar, herkese): borç, ekstre, gecikme, tahsilat, kart, ödeme. Neden aradığın sorulursa: "Güvenlik doğrulamasından sonra yalnızca {{unvan}} {{soyad}} ile görüşebileceğim bir konu." de.
Açılış cümlesi ve "{{unvan}} {{soyad}} ile mi görüşüyorum?" sorusu zaten söylendi.

A) KİŞİ TEYİDİ: Yalnızca "evet", "benim", "buyurun benim" veya kendi adını ({{ad}} / {{soyad}}) söylemesi onaydır. "Alo", "buyurun", "kimsiniz", "efendim" onay DEĞİLDİR: soruyu bir kez daha sor ("{{unvan}} {{soyad}} ile mi görüşüyorum?"). İkinci soruda da belirsizse: vedalaş ve close_call(not_reached, unclear).
B) ÜÇÜNCÜ KİŞİ (eşi, annesi, iş arkadaşı vb. "hayır, ben ..."): aramanın nedenini söyleme. "{{unvan}} {{soyad}}'a ne zaman ulaşabilirim?" diye sor.
   GERİ ARAMA PENCERESİ (yalnızca bunlar):
{{cb_text}}
   Söylenen günü takvimden YYYY-MM-DD'ye çevir ("yarın" = bugünden sonraki gün). Gün ve saat pencere içindeyse: gün ve saati tekrar et ("Yarın 15 Ekim saat 12:00'de arayalım mı?"), onay gelince schedule_callback çağır. Pencere dışıysa planlama: pencereyi söyleyip bir kez başka saat iste; yine dışıysa vedalaş ve close_call(not_reached, no_callback). Saat vermezse de bir kez sor; yine yoksa no_callback.
   "Yanlış numara" / böyle biri yok: özür dile, vedalaş, close_call(not_reached, wrong_number).
   Vefat: yalnızca "Başınız sağolsun." de, başka şey sorma, close_call(not_reached, deceased).
C) KİMLİK (kişi teyit edildikten sonra): önce "Güvenliğiniz için doğum yılınızı söyler misiniz?" -> cevabı verify_identity(field=birth_year). Doğruysa "Posta kodunuzu söyler misiniz?" -> verify_identity(field=postcode). Tek seferde bir soru. Her cevap için aracı çağır, kendin doğru/yanlış karar verme. Yanlışta aynı soruyu tekrar sor. Kimlik tamamlanınca kısa "Teşekkür ederim." de. 3 yanlışta (araç söyler): hesap hakkında hiçbir şey söylemeden vedalaş ve close_call(not_verified, failed_identity).
   Müşteri cevap vermek istemezse bir kez nedenini açıkla (güvenliği için); yine istemezse vedalaş, close_call(not_reached, unclear).
Müşteri konuşmak istemez/kapatmak isterse (kimlik öncesi): vedalaş ve close_call(not_reached, unclear)."""

NEG_TASK = """GÖREV: Müşteri ({{unvan}} {{soyad}}) kimliğini doğruladı. Borcu söyle ve her kart için ödeme sözü al.

KARTLAR (get_account sırasıyla):
{{debt_text}}

{{plan_text}}

{{cal_text}}

KURALLAR (öncelik sırasıyla):
1. ÖZEL DURUMLAR (her an olabilir, ikna etme):
   a. ZORLUK (işsizlik, iş kaybı, hastalık, maaş alamama gibi ciddi durum): empati kur ("Anlıyorum, geçmiş olsun."), add_note (kısa: ör. "işsizlik"), sonra transfer_to_agent(reason=hardship), sonra "Size yardımcı olabilecek bir temsilciye aktarıyorum." deyip vedalaş, close_call(transferred, hardship). Ödeme sözü İSTEME.
   b. İTİRAZ ("bu harcamayı ben yapmadım", "borcum yok"): tartışma, add_note, transfer_to_agent(reason=dispute), bilgi ver, close_call(transferred, dispute).
   c. ZATEN ÖDEDİM: inandırmaya/sorgulamaya çalışma; "Bilgi için teşekkürler, not alıyorum." add_note (ör. "müşteri ödediğini belirtti"), vedalaş, close_call(paid) (reason yok).
   d. Söz vermeden kapatmak istiyor / konuşmak istemiyor: vedalaş, close_call(no_promise, customer_hangup).
2. AKIŞ: Her kart için sırayla: kartın son 4 hanesi ve gecikmiş tutarı söyle, kartın ADIM 0 sorusunu sor. (Birden çok kart varsa ilk turda kaç kart olduğunu söyleyip ilk kartla başla.)
3. TARİH: Müşteri bir tarih söylerse o kartın TARİH TABLOSU'ndaki satırı bul ve AYNEN uygula. Tatil/hafta sonu ise nedenini söyle (ör. "29 Ekim Cumhuriyet Bayramı, iş günü değil") ve tablodaki tarihi öner. Sınırdan sonraki tarih kabul edilmez: en geç tarihi bir kez yeniden öner (bu ADIM 1 sayılır). Tarih itirazında tutarı düşürme.
4. TUTAR: Müşteri tutar söylerse TUTAR KURALI'nı uygula. Asgari ile tam borç arasındaki her tutar kabul. Tutar söylemeden yalnızca tarih kabul ederse tutar = tam borç. Asla "ne kadar ödeyebilirsiniz?" diye açık soru sorma; basamaktaki tutarı öner.
5. İKNA: En fazla 2 deneme, her biri BİR KEZ, sırayla (ADIM 1 sonra ADIM 2). Ara soru (robot musun vb.) basamak ilerletmez. ADIM 2'ye de hayır derse: vedalaş, close_call(no_promise, refused) (başka kartta söz kaydedildiyse outcome=promise).
6. ONAY: Yazmadan önce oku: "Sonu XXXX ile biten kart için [tutar] TL, [tarih] tarihinde ödeme sözünüzü onaylıyor musunuz?" Açık "evet" gelince create_promise (product_id KART satırından aynen). Kart başına bir söz; kaydedilmiş sözü değiştirme.
7. KAYIT SONRASI: araç başarılıysa AYNEN "Ödeme sözünüzü onaylayan bir SMS alacaksınız." de (yalnızca başarılı kayıttan sonra). Sistem hatasında what_to_do_next'e uy: önce sessizce bir kez tekrar dene; ikinci hatada dürüstçe söyle, add_note, close_call(no_promise, system_error).
8. KAPANIŞ: Tüm kartlar bitince teşekkür et, vedalaş ve close_call çağır: en az bir söz kaydedildiyse outcome=promise."""

FIRST_NEG = "Teşekkür ederim, kimliğiniz doğrulandı."

wf = {
  "initial_node": "setup",
  "system_prompt": SYSTEM,
  "test_variables": {"customer_id": "AK-1001", "ad": "Mehmet", "soyad": "Yılmaz", "unvan": "Bay", "now": "2026-10-14T11:00"},
  "tools": [],
  "global_nodes": {},
  "nodes": {
    "setup": code_node("setup", SETUP, "opening"),
    "opening": {"name": "opening", "node_type": "conversation", "interruptible": False, "max_node_turns": 80,
        "on_enter": {"type": "tts", "text": "Anadolu Kart Bank'tan arayan dijital asistanım, görüşme kayıt altına alınmaktadır. {{unvan}} {{soyad}} ile mi görüşüyorum?"},
        "task_message": OPEN_TASK, "tools": [verify, callback, close_tool()],
        "transitions": [CLOSED_T,
            {"target_node": "load_account", "description": "Kimlik doğrulandı", "condition": {"logic": "or", "conditions": [
                {"variable": "id_state", "operator": "equals", "operand": "verified"},
                {"variable": "verify_identity_response.data.identity_complete", "operator": "equals", "operand": "true"},
                {"variable": "verify_identity_response.data.identity_complete", "operator": "equals", "operand": "True"}]}}]},
    "load_account": {"name": "load_account", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "facts",
        "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "suppress_tool_results": False,
        "pre_actions": [{"type": "function", "config": {"timeoutMs": 10000, "maxRetries": 2}, "function": {"name": "get_account", "handler": "__function__:api_call", "description": "Hesap.",
            "parameters": {"type": "object", "properties": {"url": {"type": "string", "default": BASE + "/get_account"}, "method": {"type": "string", "default": "POST"}, "headers": H,
                "body": {"type": "object", "properties": {"customer_id": {"type": "string", "default": "{{customer_id}}"}}, "required": []}}}}}],
        "response_mapping": [{"path": "data.products", "variable": "products"}],
        "transitions": [{"target_node": "facts", "description": "always", "condition": {"operator": "always"}}]},
    "facts": code_node("facts", FACTS, "negotiate"),
    "negotiate": {"name": "negotiate", "node_type": "conversation", "interruptible": True, "max_node_turns": 80,
        "on_enter": {"type": "llm"},
        "task_message": NEG_TASK, "tools": [promise, note, transfer, close_tool()],
        "transitions": [CLOSED_T]},
    "goodbye": {"name": "goodbye", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
        "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
            "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}}},
  }
}
OUT.write_text(json.dumps(wf, ensure_ascii=False, indent=1))
print("wrote", OUT)
