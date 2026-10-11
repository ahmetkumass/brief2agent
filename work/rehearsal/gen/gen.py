import json, sys

BASE = 'https://freya-bank-rehearsal.ahmetkumas-freya.workers.dev/api/v1'
OUT = sys.argv[1]

COMMON = '''import datetime
HOLIDAYS = dict([('2026-10-29', 'Cumhuriyet Bayramı'), ('2027-01-01', 'Yılbaşı')])
NAMES = ['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']
MONTHS = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık']
def is_bd(d):
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS
def nth_bd_after(d, n):
    c, k = d, 0
    while k < n:
        c = c + datetime.timedelta(days=1)
        if is_bd(c):
            k += 1
    return c
def spoken(d):
    return str(d.day) + ' ' + MONTHS[d.month - 1] + ' ' + NAMES[d.weekday()]
def money(x):
    x = float(x)
    if abs(x - round(x)) < 0.005:
        s = format(int(round(x)), ',').replace(',', '.')
    else:
        s = format(x, ',.2f').replace(',', 'X').replace('.', ',').replace('X', '.')
    return s + ' TL'
def num(x):
    x = float(x)
    return str(int(round(x))) if abs(x - round(x)) < 0.005 else ('%.2f' % x)
'''

SETUP = COMMON + '''try:
    now = str(vars.get('now') or '')
    today = datetime.date.fromisoformat(now[:10])
    tnow = now[11:16] if len(now) >= 16 else '00:00'
    rows = []
    for i in range(0, 46):
        d = today + datetime.timedelta(days=i)
        tag = 'iş günü' if is_bd(d) else ('RESMİ TATİL (' + HOLIDAYS[d.isoformat()] + ') - iş günü değil' if d.isoformat() in HOLIDAYS else 'hafta sonu - iş günü değil')
        rows.append(d.isoformat() + ' ' + spoken(d) + ' - ' + tag)
    nb = nth_bd_after(today, 1)
    tm = today + datetime.timedelta(days=1)
    cb = []
    if is_bd(today) and tnow < '18:30':
        start = tnow if tnow > '09:30' else '09:30'
        cb.append('BUGÜN ' + today.isoformat() + ' (' + spoken(today) + '): saat ' + start + ' sonrası ile 18:30 arası (dahil)')
    else:
        cb.append('BUGÜN ' + today.isoformat() + ': UYGUN DEĞİL (saat geçti veya iş günü değil)')
    cb.append('SONRAKİ İŞ GÜNÜ ' + nb.isoformat() + ' (' + spoken(nb) + '): 09:30 ile 18:30 arası (dahil)')
    if tm != nb:
        cb.append('Not: yarın ' + tm.isoformat() + ' (' + spoken(tm) + ') iş günü DEĞİL; "yarın" derlerse uygun değil, ' + nb.isoformat() + ' önerin.')
    else:
        cb.append('"Yarın" = ' + tm.isoformat() + '.')
    cb.append('Bunların dışındaki her gün/saat PENCERE DIŞIDIR.')
    vars['today'] = today.isoformat()
    vars['cb_text'] = 'GERİ ARAMA PENCERESİ (şu an ' + today.isoformat() + ' ' + tnow + '):\\n' + '\\n'.join(cb)
    vars['cal_text'] = 'Bugün ' + today.isoformat() + ' ' + spoken(today) + ', saat ' + tnow + '.\\nTakvim:\\n' + '\\n'.join(rows)
    vars['setup_state'] = 'ok'
except Exception as e:
    vars['cal_text'] = 'Takvim yok'
    vars['cb_text'] = 'Geri arama: sonraki iş günü 09:30-18:30'
    vars['setup_state'] = 'error'
'''

FACTS = COMMON + '''import json, ast
try:
    def load(v):
        if isinstance(v, list):
            return v
        if isinstance(v, str) and v.strip():
            for f in (json.loads, ast.literal_eval):
                try:
                    x = f(v)
                    if isinstance(x, list):
                        return x
                except Exception:
                    pass
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
                    if kk in vars:
                        p[k] = vars[kk]
                prods.append(p)
                i += 1
            if prods:
                break
    today = datetime.date.fromisoformat(str(vars.get('now'))[:10])
    debt = []
    plans = []
    for idx, p in enumerate(prods):
        pid = str(p.get('product_id'))
        l4 = str(p.get('card_last4'))
        pdue = float(p.get('past_due') or 0)
        mn = float(p.get('minimum_payment') or 0)
        dlate = int(float(p.get('days_late') or 0))
        nbd = 5 if dlate <= 30 else 2
        dl = nth_bd_after(today, nbd)
        debt.append('KART ' + str(idx + 1) + ': sonu ' + l4 + ' ile biten kart, gecikmiş borç ' + money(pdue) + ' (product_id=' + pid + ').')
        lines = []
        for i in range(0, 46):
            d = today + datetime.timedelta(days=i)
            if d > dl:
                ans = 'SON TARİHTEN SONRA -> kabul etme; en geç ' + spoken(dl) + ' (' + dl.isoformat() + ') olduğunu söyle ve onu öner'
            elif d == today and not is_bd(d):
                ans = 'iş günü değil -> ' + nth_bd_after(d, 1).isoformat() + ' öner'
            elif is_bd(d):
                ans = 'KABUL ' + d.isoformat()
            else:
                why = ('resmi tatil (' + HOLIDAYS[d.isoformat()] + ')') if d.isoformat() in HOLIDAYS else 'hafta sonu'
                opts = []
                c = d
                while len(opts) < 2:
                    c = c + datetime.timedelta(days=1)
                    if c > dl:
                        break
                    if is_bd(c):
                        opts.append(c)
                prev = d - datetime.timedelta(days=1)
                while prev >= today and not is_bd(prev):
                    prev = prev - datetime.timedelta(days=1)
                if not opts and prev >= today:
                    opts = [prev]
                ans = why + ', iş günü değil -> söyle ve ' + ' veya '.join([spoken(o) + ' (' + o.isoformat() + ')' for o in opts]) + ' öner'
            lines.append('  ' + d.isoformat() + ' ' + spoken(d) + ': ' + ans)
        plans.append('KART ' + str(idx + 1) + ' (sonu ' + l4 + ', product_id=' + pid + '):\\n'
            + '  Gecikme ' + str(dlate) + ' gün -> en geç söz tarihi ' + str(nbd) + ' iş günü: SON TARİH ' + spoken(dl) + ' (' + dl.isoformat() + ').\\n'
            + '  TUTAR KURALI: tam borç ' + money(pdue) + ', asgari ödeme (TABAN) ' + money(mn) + '. ' + num(mn) + ' ile ' + num(pdue) + ' arasındaki (dahil) her tutar KABUL (aynen o tutar). ' + num(mn) + ' altı KABUL EDİLMEZ: asgari ödemenin ' + money(mn) + ' olduğunu söyle. ' + num(pdue) + ' üstü kabul edilmez.\\n'
            + '  İLK SORU: "Sonu ' + l4 + ' ile biten kartınızda ' + money(pdue) + ' gecikmiş borç var. En geç ' + spoken(dl) + ' tarihine kadar ödeyebilir misiniz?"\\n'
            + '  İKNA 1 (bir kez): gecikme faizi işlediğini ve gecikmenin kayıtlara geçtiğini kısaca söyle, en geç ' + spoken(dl) + ' tarihini öner.\\n'
            + '  İKNA 2 (bir kez): kısmi ödeme öner: asgari ' + money(mn) + ', en geç ' + spoken(dl) + ' tarihine kadar.\\n'
            + '  Hâlâ hayır -> bu kart için söz yok (refused).\\n'
            + '  TARİH TABLOSU:\\n' + '\\n'.join(lines))
    vars['debt_text'] = '\\n'.join(debt) if debt else 'Hesap bilgisi alınamadı.'
    vars['plan_text'] = '\\n\\n'.join(plans)
    vars['n_products'] = str(len(prods))
    vars['facts_state'] = 'ok' if prods else 'empty'
except Exception as e:
    vars['debt_text'] = 'Hesap bilgisi alınamadı.'
    vars['plan_text'] = ''
    vars['facts_state'] = 'error'
'''

def hook_head(extra=''):
    return '''try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        sc = 500
        try:
            sc = int(result.get('status_code', 200) or 200)
        except Exception:
            sc = 200
        failed = d.get('ok') is False or sc >= 500 or (result.get('status') not in (None, 'success'))
''' + extra + '''except Exception:
    pass
'''

VERIFY_PRE = '''import re
try:
    b = config.get('body')
    if isinstance(b, dict):
        a = str(b.get('answer') or '').strip()
        dg = re.sub('[^0-9]', '', a)
        b['answer'] = dg if dg else a
except Exception:
    pass
'''

VERIFY_POST = hook_head('''        fld = ''
        try:
            fld = str(config.get('body', dict()).get('field') or '')
        except Exception:
            fld = ''
        if d.get('identity_complete') is True or str(d.get('identity_complete')) in ('true', 'True'):
            vars['id_state'] = 'verified'
            d['what_to_do_next'] = 'Kimlik doğrulandı. Sadece "Teşekkürler." de; hesap bilgisi sonra yüklenecek.'
        elif sc >= 500 or (d.get('ok') is not True and d.get('ok') is not False and not d):
            d['what_to_do_next'] = 'Sistem hatası, cevap kontrol edilemedi (yanlış sayılmaz). Aynı cevapla verify_identity aracını bir kez daha çağır.'
        elif d.get('ok') is False:
            d['what_to_do_next'] = 'Cevap anlaşılamadı (yanlış sayılmaz). Müşteriden aynı bilgiyi rakamlarla tekrar söylemesini iste (doğum yılı 4 hane, posta kodu 5 hane).'
        elif d.get('verified') is True:
            if fld:
                vars['ok_' + fld] = 'yes'
            nxt = 'posta kodunuzu' if not vars.get('ok_postcode') else 'doğum yılınızı'
            d['what_to_do_next'] = 'Bu cevap doğru. Şimdi sor: "Teşekkürler. ' + nxt + ' söyler misiniz?"'
        else:
            left = d.get('attempts_remaining')
            try:
                left = int(left)
            except Exception:
                left = 1
            if left <= 0:
                vars['id_state'] = 'failed'
                d['what_to_do_next'] = 'Kimlik doğrulanamadı (3 yanlış). Hesap hakkında HİÇBİR bilgi verme. Aynı turda: "Bilgiler eşleşmediği için görüşmeye devam edemiyorum. İyi günler dilerim." de ve close_call çağır: outcome=not_verified, reason=failed_identity.'
            else:
                other = 'postcode' if fld == 'birth_year' else 'birth_year'
                ask = other if not vars.get('ok_' + other) else fld
                q = 'posta kodunuzu' if ask == 'postcode' else 'doğum yılınızı'
                d['what_to_do_next'] = 'Bu cevap eşleşmedi (kalan hak ' + str(left) + '). Hesap bilgisi verme. Şimdi sor: "Bilgi eşleşmedi. ' + q + ' söyler misiniz?"'
''')

PROMISE_POST = hook_head('''        pid = ''
        try:
            pid = str(config.get('body', dict()).get('product_id') or '')
        except Exception:
            pid = ''
        if failed:
            err = str(d.get('error') or '')
            if err in ('invalid_date', 'below_minimum', 'above_past_due'):
                d['what_to_do_next'] = 'KAYDEDİLMEDİ (' + err + '). Değerleri kart planına göre düzelt: TARİH TABLOSU ve TUTAR KURALI. Müşteriye geçerli tarih/tutarı söyle, onay al, sonra tekrar çağır. SMS cümlesini SÖYLEME.'
            else:
                k = 'pfail_' + pid
                n = int(vars.get(k) or 0) + 1
                vars[k] = str(n)
                if n < 2:
                    d['what_to_do_next'] = 'KAYDEDİLMEDİ (sistem hatası). Müşteriye bir şey söylemeden create_promise aracını AYNI değerlerle hemen bir kez daha çağır. Kaydedildi deme, SMS cümlesini söyleme.'
                else:
                    d['what_to_do_next'] = 'İKİNCİ KEZ KAYDEDİLEMEDİ. Müşteriye dürüstçe söyle: "Teknik bir sorun nedeniyle ödeme sözünüzü sisteme işleyemedim." SMS cümlesini SÖYLEME. add_note ile not yaz (ör. "Söz kaydı sistem hatası nedeniyle yapılamadı: <tutar> TL, <tarih>"). Başka kartta söz kaydedilmediyse close_call: outcome=no_promise, reason=system_error.'
        else:
            vars['promise_ok'] = 'yes'
            vars['n_promises'] = str(int(vars.get('n_promises') or 0) + 1)
            d['what_to_do_next'] = 'Söz BAŞARIYLA kaydedildi. Şimdi AYNEN söyle: "Ödeme sözünüzü onaylayan bir SMS alacaksınız." Başka kart varsa onunla devam et; yoksa teşekkür edip vedalaş ve close_call çağır: outcome=promise.'
''')

SIMPLE_POST = lambda okmsg, failmsg: hook_head('''        if failed:
            d['what_to_do_next'] = ''' + json.dumps(failmsg, ensure_ascii=False) + '''
        else:
            d['what_to_do_next'] = ''' + json.dumps(okmsg, ensure_ascii=False) + '''
''')

CLOSE_PRE = '''try:
    b = config.get('body')
    if isinstance(b, dict):
        if str(b.get('outcome')) in ('promise', 'paid'):
            b.pop('reason', None)
        elif not b.get('reason') or '{' in str(b.get('reason')):
            b.pop('reason', None)
except Exception:
    pass
'''

CLOSE_POST = hook_head('''        if failed and str(d.get('error') or '') != 'call_closed':
            d['what_to_do_next'] = 'Kapatma işlenmedi. close_call aracını aynı değerlerle bir kez daha çağır.'
        else:
            vars['closed'] = 'yes'
            d['what_to_do_next'] = 'Arama kapandı. Başka hiçbir şey söyleme veya çağırma.'
''')

def api_tool(name, desc, body_props, required, pre=None, post=None):
    props = dict(customer_id={"type": "string", "default": "{{customer_id}}"})
    props.update(body_props)
    t = {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": 0},
         "function": {"name": name, "handler": "__function__:api_call", "description": desc,
                      "parameters": {"type": "object", "properties": {
                          "url": {"type": "string", "default": BASE + "/" + name},
                          "method": {"type": "string", "default": "POST"},
                          "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                          "body": {"type": "object", "properties": props, "required": required}}}}}
    if pre:
        t["pre_process_code"] = pre
    if post:
        t["post_process_code"] = post
    return t

verify_tool = api_tool('verify_identity',
    'Müşteri bir güvenlik sorusunu cevapladığında HER SEFERİNDE, o tek cevapla çağır. field: birth_year (doğum yılı, 4 hane) veya postcode (posta kodu, 5 hane). answer: sadece rakamlar ("bin dokuz yüz seksen beş" -> 1985; "otuz dört yedi yüz on" -> 34710; baştaki 0 korunur: "sıfır altı beş yüz yirmi" -> 06520).',
    {"field": {"type": "string", "enum": ["birth_year", "postcode"], "default": "{{field}}", "description": "birth_year veya postcode"},
     "answer": {"type": "string", "default": "{{answer}}", "description": "Sadece rakamlar."}},
    ["field", "answer"], VERIFY_PRE, VERIFY_POST)

callback_tool = api_tool('schedule_callback',
    'Üçüncü kişi müşterinin ulaşılabileceği bir gün+saat verdiğinde ve bu GERİ ARAMA PENCERESİ içindeyse çağır. callback_date YYYY-MM-DD, callback_time HH:MM (24 saat).',
    {"callback_date": {"type": "string", "default": "{{callback_date}}", "description": "YYYY-MM-DD"},
     "callback_time": {"type": "string", "default": "{{callback_time}}", "description": "HH:MM"}},
    ["callback_date", "callback_time"], None,
    SIMPLE_POST('Geri arama planlandı. Teşekkür edip vedalaş ("Teşekkür ederim, iyi günler.") ve aynı turda close_call çağır: outcome=not_reached, reason=callback.',
                'Geri arama PLANLANAMADI (saat pencere dışı olabilir). Planlandı deme. Pencere dışıysa bir kez 09:30-18:30 arası başka saat iste (GERİ ARAMA PENCERESİ). İkinci kez de olmazsa vedalaş ve close_call: outcome=not_reached, reason=no_callback.'))

promise_tool = api_tool('create_promise',
    'Bir kart için ödeme sözünü kaydet. SADECE müşteriye tutar+tarihi okuyup açık "evet" onayı aldıktan sonra. Her kart için ayrı çağrı. product_id FACTS içinden aynen kopyala. amount: düz sayı (ör. 2000). payment_date: YYYY-MM-DD, TARİH TABLOSU\'nda KABUL olan bir tarih.',
    {"product_id": {"type": "string", "default": "{{product_id}}", "description": "FACTS içindeki product_id"},
     "amount": {"type": "number", "default": "{{amount}}", "description": "TL, düz sayı"},
     "payment_date": {"type": "string", "default": "{{payment_date}}", "description": "YYYY-MM-DD"}},
    ["product_id", "amount", "payment_date"], None, PROMISE_POST)

note_tool = api_tool('add_note',
    'Arama notu ekle (kısa, Türkçe). Zorluk, itiraz, zaten ödedim ve iki kez başarısız söz kaydında kullan.',
    {"text": {"type": "string", "default": "{{note_text}}", "description": "Kısa not"}},
    ["text"], None,
    SIMPLE_POST('Not kaydedildi (müşteriye not hakkında bir şey söyleme). Kurala göre sıradaki adıma geç (aktarım veya kapanış).',
                'Not kaydedilemedi. add_note aracını bir kez daha aynı metinle çağır.'))

transfer_tool = api_tool('transfer_to_agent',
    'Canlı temsilciye aktar. reason: hardship (işsizlik, hastalık vb. ödeme güçlüğü) veya dispute (borca/harcamaya itiraz). Önce add_note çağır.',
    {"reason": {"type": "string", "enum": ["hardship", "dispute"], "default": "{{transfer_reason}}", "description": "hardship veya dispute"}},
    ["reason"], None,
    SIMPLE_POST('Aktarım başarılı. Müşteriye kısa bir cümleyle temsilciye aktarıldığını söyle, vedalaş ve aynı turda close_call çağır: outcome=transferred, reason=aktarımdaki reason (hardship veya dispute).',
                'Aktarım YAPILAMADI. transfer_to_agent aracını bir kez daha aynı değerle çağır. Aktarıldı deme.'))

close_tool = api_tool('close_call',
    'Aramanın sonucunu kaydet. HER ZAMAN son araç çağrısı, tam bir kez, vedalaşma cümlesiyle aynı turda. TABLO: '
    'promise (reason yok) = en az bir söz create_promise ok=true ile kaydedildi. '
    'paid (reason yok) = müşteri zaten ödediğini söyledi ve add_note yazıldı. '
    'transferred + hardship / dispute = transfer_to_agent başarılı oldu. '
    'no_promise + refused = doğrulanmış, 2 ikna denemesinden sonra hâlâ söz yok; no_promise + customer_hangup = doğrulanmış müşteri söz vermeden kapatmak istedi; no_promise + system_error = create_promise iki kez başarısız (add_note sonrası). '
    'not_verified + failed_identity = 3 yanlış güvenlik cevabı. '
    'not_reached + callback = schedule_callback başarılı; no_callback = pencere dışı saat iki kez / saat verilmedi; wrong_number = yanlış numara; deceased = müşteri vefat etmiş; unclear = iki soruda da doğru kişi teyit edilemedi.',
    {"outcome": {"type": "string", "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"], "default": "{{outcome}}", "description": "Tabloya göre"},
     "reason": {"type": "string", "enum": ["hardship", "dispute", "refused", "customer_hangup", "system_error", "failed_identity", "callback", "no_callback", "wrong_number", "deceased", "unclear"], "default": "{{reason}}", "description": "promise ve paid dışında zorunlu"}},
    ["outcome"], CLOSE_PRE, CLOSE_POST)

def code_node(name, code, nxt):
    return {"name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": nxt,
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
            "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}]}

CLOSED_T = {"target_node": "goodbye", "description": "The call was closed", "condition": {"logic": "or", "conditions": [
    {"variable": "closed", "operator": "equals", "operand": "yes"},
    {"variable": "close_call_success_count", "operator": "greater_than", "operand": 0}]}}

OPENING_LINE = "Anadolu Kart Bank'tan arayan dijital asistanım, görüşme kayıt altına alınmaktadır. {{unvan}} {{soyad}} ile mi görüşüyorum?"

INTRO_TASK = '''AŞAMA: açılış ve kimlik doğrulama. Hesap hakkında HİÇBİR ŞEY bilmiyorsun.
YASAK SÖZCÜKLER (doğrulamadan önce, herkese, üçüncü kişiler dahil): "borç", "ekstre", "gecikme", "tahsilat", "kart", "ödeme" (banka adı "Anadolu Kart Bank" hariç). Tutar, ürün, arama nedeni söyleme. Ne için aradığını sorarlarsa: "Kendisiyle özel bir konuda görüşmem gerekiyor." (müşteriye ise: "Güvenlik doğrulamasından sonra bilgi verebilirim.").

Açılış zaten söylendi: "''' + OPENING_LINE + '''"

A. HATTAKİ KİŞİ
- ONAY sadece: "evet", "benim", "buyurun benim" ya da kendi adını ({{ad}} / {{soyad}}) söylemesi. "Alo", "buyurun", "kimsiniz", "efendim" ONAY DEĞİL: varsa sorusunu kısaca cevapla ve bir kez daha sor: "{{unvan}} {{soyad}} ile mi görüşüyorum?". İkinci soruda da net onay yoksa: vedalaş ve close_call(not_reached, unclear).
- Robot/yapay zeka mısın sorusu: "Evet, Anadolu Kart Bank'ın dijital asistanıyım." de ve devam et.
- YANLIŞ NUMARA ("burada öyle biri yok", "yanlış numara"): özür dile, vedalaş, close_call(not_reached, wrong_number).
- VEFAT (müşteri vefat etti): AYNEN "Başınız sağolsun." de, başka hiçbir şey sorma, aynı turda close_call(not_reached, deceased).
- BAŞKASI AÇTI (eşi, yakını, "o burada değil"): arama nedenini SÖYLEME, güvenlik sorusu sorma, bilgi verme. Sor: "{{unvan}} {{soyad}}'a ne zaman ulaşabiliriz?"
  {{cb_text}}
  Verilen gün+saat pencere İÇİNDEYSE: schedule_callback(callback_date YYYY-MM-DD, callback_time HH:MM) çağır ("yarın saat 12" -> 12:00; "öğleden sonra 3" -> 15:00). ok=true sonrası teşekkür, vedalaş, close_call(not_reached, callback).
  Pencere DIŞIYSA (çağırmadan önce kendin kontrol et): bir kez "O saatte arayamıyoruz; 09:30 ile 18:30 arasında, bugün veya bir sonraki iş günü uygun bir saat söyleyebilir misiniz?" diye sor. İkinci cevap da dışarıdaysa veya saat veremezlerse: planlama, vedalaş, close_call(not_reached, no_callback).
  Kişi sonra "aslında benim" derse kimlik doğrulamaya geç.

B. KİMLİK DOĞRULAMA (onaydan sonra)
1. Sor: "Güvenliğiniz için doğum yılınızı söyler misiniz?"
2. Her cevapta verify_identity çağır (field=birth_year veya postcode, answer=sadece rakamlar). Sonra what_to_do_next ne diyorsa onu yap.
3. Doğum yılı doğruysa: "Posta kodunuzu söyler misiniz?" Tek seferde tek soru.
4. Cevabı kendin değerlendirme, doğru/yanlış deme; araç sonucuna uy. Müşterinin söylediği bilgiyi asla tekrar etme veya ipucu verme.
5. 3 yanlışta (araç söyler): hesap bilgisi verme, vedalaş, close_call(not_verified, failed_identity).
6. Müşteri güvenlik sorusuna cevap vermek istemezse: bir kez nedenini açıkla (güvenliği için); yine istemezse vedalaş, close_call(not_reached, unclear).
'''

NEG_TASK = '''AŞAMA: müşteri {{unvan}} {{soyad}} KİMLİĞİ DOĞRULANDI. Şimdi kartları konuş.

FACTS (kod hesapladı, aynen güven, tarih/tutar HESAPLAMA, tablodan bak):
{{debt_text}}

{{plan_text}}

TAKVİM:
{{cal_text}}

AKIŞ:
1. İlk turunda: KART 1'in İLK SORU cümlesini aynen söyle (birden çok kart varsa önce "Gecikmiş iki kartınız var." gibi kısaca belirt, sonra KART 1 ile başla). Kartları FACTS sırasıyla TEK TEK işle; bir kart bitince (söz kaydedildi veya söz yok) diğerine geç ve onun İLK SORU cümlesini söyle.
2. Müşteri tarih söylerse: o tarihi ilgili kartın TARİH TABLOSU'nda bul ve satırın dediğini aynen yap. ("20 Ekim" -> o yılın 2026-10-20 satırı; "cuma", "yarın", "haftaya" -> TAKVİM'den bul.) Tatil/hafta sonu ise nedenini (ör. "29 Ekim Cumhuriyet Bayramı, iş günü değil") ve en geç son tarihi söyleyip satırdaki seçenekleri öner.
3. Müşteri tutar söylerse: TUTAR KURALI'na uy. Tutar söylemeden "öderim" derse tam borcu mu ödeyeceğini sor. Asgari altı tutara asgari tutarı söyle.
4. Son tarihten sonrası isterse: bir kez son tarihi tekrar öner. Kabul etmezse İKNA 1, sonra İKNA 2. Her adım bir kez; bir teklifi asla tekrarlama. Hangi adımda olduğunu takip et. Toplam en fazla 2 ikna denemesi. Hâlâ hayırsa o kart için söz yok.
5. ONAY: kaydetmeden önce oku: "Sonu XXXX ile biten kartınız için <tarih> tarihinde <tutar> ödeme sözü alıyorum, onaylıyor musunuz?" Açık "evet" gelince create_promise çağır (product_id FACTS'ten aynen, amount düz sayı, payment_date YYYY-MM-DD). Kaydedilen söz değiştirilmez; her kart için tek söz.
6. create_promise sonrası what_to_do_next'e AYNEN uy. "Ödeme sözünüzü onaylayan bir SMS alacaksınız." cümlesi SADECE ok=true sonrası söylenir. Hata olursa müşteriye bir şey demeden bir kez tekrar dene; ikinci hata: dürüstçe kaydedilemediğini söyle, add_note, close_call(no_promise, system_error). "kaydedildi/kaydettim/alındı" sözcüklerini sadece ok=true sonrası kullan.

ÖZEL DURUMLAR (hemen, ikna etmeden):
- ZORLUK (işsizlik, işini kaybetme, hastalık, gelir yok vb.): empati kur ("Anlıyorum, geçmiş olsun."), ikna ETME, add_note (ör. "Müşteri işini kaybetti, ödeme güçlüğü"), sonra transfer_to_agent(reason=hardship), sonra "Size yardımcı olabilecek bir temsilciye aktarıyorum." + close_call(transferred, hardship).
- İTİRAZ ("bu harcamayı ben yapmadım", "borcum yok"): tartışma, add_note (itirazı yaz), transfer_to_agent(reason=dispute), close_call(transferred, dispute).
- ZATEN ÖDEDİM: inanmaya/ikna etmeye çalışma, doğrulayamazsın. add_note (ör. "Müşteri ödediğini beyan etti"), sonra teşekkür, vedalaş, close_call(paid) (reason yok).
- Müşteri kapatmak/konuşmak istemezse ve hiç söz yoksa: vedalaş, close_call(no_promise, customer_hangup). Söz varsa close_call(promise).
- Robot musun: dijital asistan olduğunu söyle, devam et. Bilmediğin soru: o bilgiye sahip olmadığını söyle.

KAPANIŞ: tüm kartlar bitince: en az bir söz ok=true ise (SMS cümlesi söylendiyse) teşekkür et, vedalaş ve aynı turda close_call(promise). Hiç söz yoksa ve ikna bittiyse close_call(no_promise, refused). close_call her zaman son araç çağrısıdır.
'''

SYSTEM = '''Sen Anadolu Kart Bank'ın dijital asistanısın; kayıtlı bir giden telefon aramasındasın. SADECE Türkçe konuş. Her turda bir-iki kısa cümle, tek seferde tek soru. Müşteriye "{{unvan}} {{soyad}}" diye hitap et (ör. "Bay Yılmaz").
Tarihleri doğal Türkçe söyle (ör. "20 Ekim Salı"), tutarları "4.800 TL" gibi.
Her araç sonucundan sonra what_to_do_next talimatına uy; sonra müşteriyle konuş veya sıradaki aracı çağır. Asla boş tur bırakma.
Bir işlem araç ok=true dönmeden "kaydedildi / planlandı / aktarıldı" deme. Rakam, tarih, neden uydurma.
Robot/yapay zeka sorulursa: Anadolu Kart Bank'ın dijital asistanı olduğunu söyle ve devam et.
Arama bittiğinde: TEK turda teşekkür edip vedalaş VE close_call çağır (tam bir kez, her zaman son araç çağrısı).
'''

wf = {
    "initial_node": "setup",
    "system_prompt": SYSTEM,
    "tools": [],
    "global_nodes": {},
    "test_variables": {"customer_id": "AK-1001", "ad": "Mehmet", "soyad": "Yılmaz", "unvan": "Bay", "now": "2026-10-14T11:00"},
    "nodes": {
        "setup": code_node("setup", SETUP, "intro"),
        "intro": {"name": "intro", "node_type": "conversation",
                  "on_enter": {"type": "tts", "text": OPENING_LINE},
                  "task_message": INTRO_TASK, "role_message": SYSTEM, "interruptible": True, "max_node_turns": 80,
                  "tools": [verify_tool, callback_tool, close_tool],
                  "transitions": [CLOSED_T,
                      {"target_node": "load_account", "description": "Both questions passed", "condition": {"logic": "or", "conditions": [
                          {"variable": "id_state", "operator": "equals", "operand": "verified"},
                          {"variable": "verify_identity_response.data.identity_complete", "operator": "equals", "operand": "true"},
                          {"variable": "verify_identity_response.data.identity_complete", "operator": "equals", "operand": "True"}]}}]},
        "load_account": {"name": "load_account", "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "facts",
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "suppress_tool_results": False,
            "pre_actions": [{"type": "function", "config": {"timeoutMs": 10000, "maxRetries": 2}, "function": {"name": "get_account", "handler": "__function__:api_call", "description": "Get the account.",
                "parameters": {"type": "object", "properties": {"url": {"type": "string", "default": BASE + "/get_account"}, "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                    "body": {"type": "object", "properties": {"customer_id": {"type": "string", "default": "{{customer_id}}"}}, "required": []}}}}}],
            "response_mapping": [{"path": "data.products", "variable": "products"}],
            "transitions": [{"target_node": "facts", "description": "always", "condition": {"operator": "always"}}]},
        "facts": code_node("facts", FACTS, "negotiate"),
        "negotiate": {"name": "negotiate", "node_type": "conversation", "on_enter": {"type": "llm"},
                      "task_message": NEG_TASK, "role_message": SYSTEM, "interruptible": True, "max_node_turns": 80,
                      "tools": [promise_tool, note_tool, transfer_tool, close_tool],
                      "transitions": [CLOSED_T]},
        "goodbye": {"name": "goodbye", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
                    "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                        "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}}},
    },
}
json.dump(wf, open(OUT, 'w'), ensure_ascii=False, indent=1)
print('ok')
