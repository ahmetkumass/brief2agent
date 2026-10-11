import json
BASE = "https://freya-bank-mock.freyavoice.workers.dev/v1"
HOL = "['2026-10-26','2026-11-11','2026-11-26','2026-12-25','2027-01-01']"

CAL_HELPERS = """import datetime, json, ast
HOLIDAYS = set(""" + HOL + """)
NAMES = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
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
    return NAMES[d.weekday()] + ' ' + d.strftime('%B') + ' ' + str(d.day)
"""

SETUP = CAL_HELPERS + """try:
    now = str(vars.get('now') or '')
    today = datetime.date.fromisoformat(now[:10])
    rows = []
    for i in range(0, 46):
        d = today + datetime.timedelta(days=i)
        tag = 'business day' if is_bd(d) else ('HOLIDAY - not a business day' if d.isoformat() in HOLIDAYS else 'weekend - not a business day')
        wk = 'this week' if d.isocalendar()[1] == today.isocalendar()[1] else ('next week' if (d - datetime.timedelta(days=d.weekday())) == (today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=7)) else '')
        rows.append(d.isoformat() + ' ' + NAMES[d.weekday()] + ' - ' + tag + ((' (' + wk + ')') if wk else ''))
    nb = today if is_bd(today) else nth_bd_after(today, 1)
    nxt = nth_bd_after(today, 1)
    cb = []
    t = now[11:16]
    if is_bd(today):
        cb.append('today ' + today.isoformat() + ' (' + NAMES[today.weekday()] + ') from 10:00 to 19:00 but strictly later than ' + t)
    cb.append('next business day ' + nxt.isoformat() + ' (' + NAMES[nxt.weekday()] + ') from 10:00 to 19:00')
    vars['today'] = today.isoformat()
    vars['cb_text'] = 'Allowed callback slots (both ends included): ' + ' ; '.join(cb) + '. Anything else is outside the window.'
    vars['cal_text'] = 'Today is ' + today.isoformat() + ' (' + NAMES[today.weekday()] + '), time ' + t + '.\\nCalendar (weeks start Monday):\\n' + '\\n'.join(rows)
    vars['setup_state'] = 'ok'
except Exception as e:
    vars['cal_text'] = 'Calendar unavailable'
    vars['cb_text'] = ''
    vars['setup_state'] = 'error'
"""

FACTS = CAL_HELPERS + """def money(x):
    x = float(x)
    return ('%.2f' % x).replace('.00', '')
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
                for k in ('product_id','type','card_last4','past_due','days_late','minimum_payment','instalment_amount'):
                    kk = prefix + str(i) + '.' + k
                    if kk in vars:
                        p[k] = vars[kk]
                prods.append(p)
                i += 1
            if prods:
                break
    today = datetime.date.fromisoformat(str(vars.get('now'))[:10])
    debt = []
    plan = []
    for p in prods:
        typ = str(p.get('type'))
        if typ == 'credit_card':
            name = 'credit card ending ' + str(p.get('card_last4'))
            floor = p.get('minimum_payment')
        elif typ == 'car_loan':
            name = 'car loan'
            floor = p.get('instalment_amount')
        else:
            name = 'personal loan'
            floor = p.get('instalment_amount')
        dl = int(p.get('days_late'))
        if dl <= 7:
            band, n, att = 'early', 12, 1
        else:
            band, n, att = 'late', 7, 2
        deadline = nth_bd_after(today, n)
        mon = today - datetime.timedelta(days=today.weekday())
        lw = None
        for k in range(6, -1, -1):
            d = mon + datetime.timedelta(days=k)
            if is_bd(d):
                lw = d
                break
        if lw is None or lw <= today:
            mon2 = mon + datetime.timedelta(days=7)
            for k in range(6, -1, -1):
                d = mon2 + datetime.timedelta(days=k)
                if is_bd(d):
                    lw = d
                    break
        if lw > deadline:
            lw = deadline
        valid = []
        d = today
        while d <= deadline:
            if is_bd(d):
                valid.append(d.isoformat() + ' (' + NAMES[d.weekday()] + ')')
            d = d + datetime.timedelta(days=1)
        vars['product_id'] = str(p.get('product_id'))
        vars['past_due'] = money(p.get('past_due'))
        vars['floor'] = money(floor)
        vars['deadline'] = deadline.isoformat()
        vars['attempt1_date'] = lw.isoformat()
        vars['band'] = band
        vars['attempts'] = str(att)
        debt.append('product_id=' + str(p.get('product_id')) + ' ; spoken name: ' + name + ' ; past-due amount ' + money(p.get('past_due')) + ' ; ' + str(dl) + ' days late.')
        s = ('Product ' + str(p.get('product_id')) + ' (' + name + '): band ' + band + ', persuasion attempts allowed: ' + str(att) + '.\\n'
             + 'FULL amount = ' + money(p.get('past_due')) + '. FLOOR (lowest amount you may record) = ' + money(floor) + '.\\n'
             + 'DEADLINE (latest date you may record) = ' + deadline.isoformat() + ' (' + spoken(deadline) + ').\\n'
             + 'Attempt 1 offer date = ' + lw.isoformat() + ' (' + spoken(lw) + ').\\n')
        if att == 2:
            s += 'Attempt 2 offer = the floor ' + money(floor) + ' on the deadline ' + deadline.isoformat() + ' (' + spoken(deadline) + ').\\n'
        else:
            s += 'There is NO attempt 2 for this product (early band). After attempt 1 is refused, close no_promise/refused.\\n'
        s += 'VALID PROMISE DATES (only these): ' + ', '.join(valid) + '.'
        plan.append(s)
    vars['debt_text'] = '\\n'.join(debt)
    vars['plan_text'] = '\\n'.join(plan)
    vars['facts_state'] = 'ok' if prods else 'empty'
except Exception as e:
    vars['debt_text'] = 'Account details unavailable'
    vars['plan_text'] = ''
    vars['facts_state'] = 'error'
"""

def api_tool(name, desc, body_props, required, pre=None, post=None, retries=0):
    props = {"customer_id": {"type": "string", "default": "{{customer_id}}"}}
    props.update(body_props)
    t = {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": retries},
         "function": {"name": name, "handler": "__function__:api_call", "description": desc,
                      "parameters": {"type": "object", "properties": {
                          "url": {"type": "string", "default": BASE + "/" + name},
                          "method": {"type": "string", "default": "POST"},
                          "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                          "body": {"type": "object", "properties": props, "required": required}}}}}
    if pre: t["pre_process_code"] = pre
    if post: t["post_process_code"] = post
    return t

HOOK_HEAD = """try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        failed = d.get('ok') is False or (result.get('status') not in (None, 'success')) or int(result.get('status_code', 200) or 200) >= 500
"""
HOOK_TAIL = """except Exception:
    pass
"""

VERIFY_PRE = """import re
try:
    b = config.get('body')
    if isinstance(b, dict):
        a = str(b.get('answer') or '').strip()
        if b.get('field') == 'phone_last4':
            dg = re.sub('[^0-9]', '', a)
            if len(dg) >= 4:
                dg = dg[-4:]
            b['answer'] = dg
        else:
            m = re.match('^([0-9]{1,2})[./ -]([0-9]{1,2})[./ -]([0-9]{4})$', a)
            if m:
                b['answer'] = m.group(3) + '-' + m.group(2).zfill(2) + '-' + m.group(1).zfill(2)
            else:
                b['answer'] = a
except Exception:
    pass
"""
VERIFY_POST = HOOK_HEAD + """        if d.get('all_verified') is True or str(d.get('all_verified')) in ('true', 'True'):
            vars['id_state'] = 'verified'
            d['what_to_do_next'] = 'Identity verified. Say nothing more, the account is loaded next.'
        elif d.get('hint') == 'day_month_swapped':
            d['what_to_do_next'] = 'The day and month look swapped. This does NOT count as a wrong answer. Ask the customer to say their date of birth again with the month as a word.'
        elif d.get('ok') is False or failed:
            d['what_to_do_next'] = 'The answer could not be read (not counted as wrong). Ask the customer to repeat it clearly, e.g. the date of birth with day, month name and year.'
        elif d.get('verified') is True:
            d['what_to_do_next'] = 'That answer is correct. Now ask the next security question: the last four digits of the phone number on file.'
        else:
            left = d.get('wrong_answers_left')
            try:
                left = int(left)
            except Exception:
                left = 1
            if left <= 0:
                vars['id_state'] = 'failed'
                d['what_to_do_next'] = 'Identity check FAILED. Do not mention any debt or account details. In ONE turn say: for your security, please use the Freya Bank mobile app or visit a branch; thank you and goodbye. And call close_call with outcome=not_verified reason=failed.'
            else:
                d['what_to_do_next'] = 'That answer is not correct. Ask the SAME question again (wrong answers left: ' + str(left) + '). Do not reveal which part was wrong.'
""" + HOOK_TAIL

PROMISE_POST = HOOK_HEAD + """        if failed or d.get('ok') is not True:
            n = int(vars.get('promise_fail_n') or 0) + 1
            vars['promise_fail_n'] = n
            if n < 2:
                d['what_to_do_next'] = 'NOT RECORDED. Call create_promise again right now, once, with exactly the same values. Do not tell the customer it is recorded.'
            else:
                d['what_to_do_next'] = 'NOT RECORDED, failed twice. In ONE turn tell the customer you could not record the promise, thank them, say goodbye, and call close_call with outcome=no_promise reason=service_error.'
        else:
            vars['promise_done'] = 'yes'
            d['what_to_do_next'] = 'Recorded. Tell the customer the promise is recorded and say exactly: "You will receive a text message confirming this promise." Then thank them, say goodbye and call close_call with outcome=promise (no reason) in the same turn, unless they ask for something else.'
""" + HOOK_TAIL

CB_POST = HOOK_HEAD + """        if failed or d.get('ok') is not True:
            d['what_to_do_next'] = 'Callback NOT scheduled (' + str(d.get('error') or 'error') + '). If the time is outside the allowed window, ask once for another time; otherwise try again once. Never say it is scheduled.'
        else:
            d['what_to_do_next'] = 'Callback scheduled. In ONE turn confirm we will call back then, thank them, say goodbye, and call close_call with outcome=not_reached reason=callback.'
""" + HOOK_TAIL

TR_POST = HOOK_HEAD + """        if failed or d.get('ok') is not True:
            d['what_to_do_next'] = 'Transfer failed. Try transfer_to_agent once more with the same queue. Never say you transferred unless ok=true.'
        else:
            d['what_to_do_next'] = 'Transfer accepted. In ONE turn tell the customer you are connecting them now, thank them, say goodbye, and call close_call with outcome=transferred and the reason matching the queue (support->support, restructuring->restructuring, general->human).'
""" + HOOK_TAIL

CLOSE_PRE = """try:
    b = config.get('body')
    if isinstance(b, dict):
        if b.get('outcome') in ('promise', 'paid'):
            b.pop('reason', None)
except Exception:
    pass
"""
CLOSE_POST = HOOK_HEAD + """        if failed or d.get('ok') is not True:
            d['what_to_do_next'] = 'close_call failed. Call close_call again with the same values. Say nothing.'
        else:
            vars['closed'] = 'yes'
            d['ok'] = True
""" + HOOK_TAIL

CLOSE_TABLE = ("Record how the call ended. CALL it exactly once, as the last action, in the same turn as your goodbye. Table: "
  "promise (no reason) = a promise was recorded with ok=true. paid (no reason) = customer says they already paid this past-due amount. "
  "transferred + restructuring/human/support = after transfer_to_agent ok (queue restructuring/general/support); also when the transfer follows a recorded promise. "
  "no_promise + refused = persuasion attempts used up, or customer said twice they do not want to talk (after verification); "
  "no_promise + hardship = hardship and the customer declined the support transfer; no_promise + dispute = debt/product not theirs or claims it was closed/paid off in the past; "
  "no_promise + service_error = create_promise failed twice. not_verified + failed = three wrong security answers; not_verified + declined = refused the security questions (or asked what the call is about instead) twice, or said twice before verification they do not want to talk. "
  "not_reached + callback = schedule_callback ok; no_callback = callback time outside window twice; wrong_number; deceased; unclear = right person not confirmed after two asks.")
CLOSE = api_tool("close_call", CLOSE_TABLE, {
    "outcome": {"type": "string", "enum": ["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"], "default": "{{outcome}}", "description": "See table."},
    "reason": {"type": "string", "enum": ["restructuring", "human", "support", "refused", "hardship", "dispute", "service_error", "failed", "declined", "callback", "no_callback", "wrong_number", "deceased", "unclear"], "default": "{{reason}}", "description": "Required except for promise and paid."}},
    ["outcome"], pre=CLOSE_PRE, post=CLOSE_POST)
VERIFY = api_tool("verify_identity", "CALL this every time the customer answers a security question, with that one answer. Date of birth as YYYY-MM-DD (a date said only in numbers is day, then month, then year). Phone as the four digits.", {
    "field": {"type": "string", "enum": ["date_of_birth", "phone_last4"], "default": "{{field}}", "description": "date_of_birth or phone_last4"},
    "answer": {"type": "string", "default": "{{answer}}", "description": "date_of_birth: YYYY-MM-DD. phone_last4: four digits."}},
    ["field", "answer"], pre=VERIFY_PRE, post=VERIFY_POST)
CALLBACK = api_tool("schedule_callback", "CALL this when the person who answered (not the customer) gives a callback day and time that is inside the allowed callback slots. date YYYY-MM-DD, time HH:MM 24h.", {
    "date": {"type": "string", "default": "{{cb_date}}", "description": "YYYY-MM-DD"},
    "time": {"type": "string", "default": "{{cb_time}}", "description": "HH:MM 24h"}},
    ["date", "time"], post=CB_POST)
TRANSFER = api_tool("transfer_to_agent", "CALL this to transfer: queue support (hardship, customer accepted the offer to connect to support), restructuring (customer asks for a new payment plan or lower instalments), general (customer insists on a human after you asked once if you can help).", {
    "queue": {"type": "string", "enum": ["restructuring", "general", "support"], "default": "{{queue}}"}},
    ["queue"], post=TR_POST)
PROMISE = api_tool("create_promise", "CALL this only after the customer clearly said yes to your read-back (product, amount, date) and \"Do you confirm?\". product_id from FACTS, amount as a plain number, date YYYY-MM-DD from VALID PROMISE DATES.", {
    "product_id": {"type": "string", "default": "{{p_id}}", "description": "product_id from FACTS"},
    "amount": {"type": "number", "default": "{{p_amount}}", "description": "plain number, between the floor and the full amount"},
    "date": {"type": "string", "default": "{{p_date}}", "description": "YYYY-MM-DD"}},
    ["product_id", "amount", "date"], post=PROMISE_POST)

def code_node(name, code, nxt):
    return {"name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": nxt,
            "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True,
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": code}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
            "transitions": [{"target_node": nxt, "description": "always", "condition": {"operator": "always"}}]}

CLOSED_TR = {"target_node": "goodbye", "description": "The call was closed", "condition": {"logic": "or", "conditions": [
    {"variable": "closed", "operator": "equals", "operand": "yes"},
    {"variable": "close_call_success_count", "operator": "greater_than", "operand": 0}]}}

SYSTEM = """You are the digital assistant of Freya Bank, on a recorded outbound phone call. Speak English only. One or two short sentences per turn, one question at a time. Address the customer as {{title}} {{last_name}}.
After every tool result: follow its what_to_do_next, then speak to the customer or call the next tool. Never end a turn with nothing.
Never say something is recorded, scheduled or transferred unless the tool returned ok=true. Never invent figures, dates or reasons; if you cannot answer from the tools say you do not have that information.
If asked whether you are a robot or an AI: say you are Freya Bank's digital assistant, then continue.
If asked "is this a scam?": say they can verify the call by phoning Freya Bank's customer service number, then continue.
If the customer asks for a human: first ask once whether you can help them. If they insist, call transfer_to_agent with queue general, then close transferred/human. (This applies before and after verification.)
Ending a call: in ONE turn thank the customer and say goodbye, and call close_call (exactly once, it is the last tool call). Never use add_note."""

INTRO_TASK = """STAGE: opening and identity check. You do NOT know anything about the account. Before verification never say "collections", "debt", "payment", "late", "overdue", any amount or any product, to anyone, including relatives. If asked what the call is about, say you can explain only after the security check.

The opening was already said: "Hello, this is Freya Bank's digital assistant. This call is recorded. Am I speaking with {{title}} {{last_name}}?"

A. Who is on the line.
- Confirmation counts ONLY if they say yes / that's me / speaking / their own name ({{first_name}} or {{last_name}}). "Hello", "go ahead", "who is this" do not count. If not confirmed, answer any question they asked first, then ask once more "Am I speaking with {{title}} {{last_name}}?". If still unclear after that second ask: close not_reached / unclear.
- Someone else answered (e.g. a relative, colleague, "he's not here"): say nothing about why you call. Ask when {{title}} {{last_name}} can be reached. Never ask them security questions and tell them nothing, even if they offer to pay.
  {{cb_text}}
  If they give a day+time inside the allowed slots: call schedule_callback (date YYYY-MM-DD, time HH:MM), then close not_reached / callback. If they give only a day or only a vague time, ask for the exact time within 10:00-19:00. If the offered time is outside the slots: ask ONCE for another time within those slots; if that is also outside, do not schedule, close not_reached / no_callback.
- "This number does not belong to that person" / wrong number: close not_reached / wrong_number.
- The customer has died: say exactly "I am sorry for your loss." and nothing else besides goodbye, close not_reached / deceased.

B. Identity (only after the customer confirmed who they are). Ask the questions one at a time:
 1. "For security, could you please tell me your date of birth?" Call verify_identity field=date_of_birth with YYYY-MM-DD. Dates said only in numbers (e.g. 05/03/1985) are DAY/MONTH/YEAR -> 1985-03-05. Convert words ("March fifth nineteen eighty-five") yourself.
 2. After the date of birth is verified: "And the last four digits of the phone number we have on file?" Call verify_identity field=phone_last4.
 Follow what_to_do_next after every verify_identity result (wrong answer -> ask the same question again; day_month_swapped -> ask for the month as a word, not counted; three wrong -> mobile app or branch, close not_verified / failed).
- If the customer does not want to answer (or asks what the call is about instead of answering): explain once that the questions protect their account and ask again. A second refusal or second such question: close not_verified / declined. Saying twice they do not want to talk before verification: not_verified / declined.

CALENDAR:
{{cal_text}}"""

NEG_TASK = """STAGE: the customer {{title}} {{last_name}} is VERIFIED. Now handle the debt.

FACTS (computed by code, trust them, never compute dates yourself):
{{debt_text}}
{{plan_text}}

CALENDAR:
{{cal_text}}

STEP 1 (your first turn here): say you are calling from the collections team about a late payment on the product (use its spoken name exactly, e.g. "credit card ending 4821" / "personal loan" / "car loan"), state the past-due amount and how many days late it is, then ask exactly: "Can you make this payment today?"

INTERRUPTS (check these first, at any moment):
H. Illness, a death in the family, or job loss: say one short sentence of sympathy, make NO persuasion attempt, offer to connect them with the customer support team. Accept -> transfer_to_agent queue support, then close transferred / support. Decline -> close no_promise / hardship. (If they themselves still name a date or amount, handle it with the date and amount rules and record the promise.)
P. "I already paid" (this past-due amount): say payments can take one business day to appear, take no promise, close paid (no reason).
D. "Not my debt", "I never had this product", "it was closed / paid off in the past": do not argue, no promise, close no_promise / dispute.
R. Asks for a new payment plan, lower instalments, restructuring: do not describe any plan. transfer_to_agent queue restructuring, then close transferred / restructuring.
X. Says they do not want to talk: the second time -> close no_promise / refused.
Never offer a discount, waiver, instalment plan or any other term. Never ask "how much can you pay?" - you propose every amount.

DATE RULES (for any date the customer names):
- Date in VALID PROMISE DATES -> accept.
- "Next <weekday>" = that weekday in the following calendar week (see the "(next week)" tags in CALENDAR). "This <weekday>" = in the current week. "Today", "tomorrow" relative to today.
- Weekend or holiday not after the deadline -> offer the next business day after it.
- After the deadline -> say the latest date you can record is the deadline (say it) and offer it. If they refuse the deadline, that is a flat refusal (uses an attempt).
- Vague ("next week", "end of month", "when my salary comes") -> ask once for the exact day; if still none, propose the deadline.
AMOUNT RULES:
- Default amount is the FULL past-due amount.
- If they say the full amount is too much: offer the FLOOR once, saying the rest stays overdue. If they refuse the floor -> flat refusal (uses an attempt).
- Customer proposes an amount from the floor up to the full amount (inclusive) -> accept. Below the floor -> say it cannot be recorded and offer the floor once; if not accepted -> flat refusal.
- A date or amount the customer proposes is never a refusal.

PERSUASION (a "no" to paying today with no date and no amount, or a non-answer, is a flat refusal and uses one attempt):
- Attempt 1: propose the attempt 1 offer date from FACTS for the full amount (or for the floor if they already said the full amount is too much).
- Attempt 2 (only if the product allows 2 attempts): propose the floor amount on the deadline.
- When the allowed attempts are used up and they still refuse: stop, do not repeat refused offers, close no_promise / refused.

CONFIRM AND RECORD:
- Read back the product (spoken name), the amount and the date (say it naturally with weekday) and ask exactly "Do you confirm?". Only after a clear yes call create_promise (product_id from FACTS, amount as a number, date YYYY-MM-DD).
- If at this step they change the date or amount, check it with the rules and read back again.
- Only one promise. A recorded promise cannot be changed or cancelled in this call; if asked, say they can change it in the mobile app.
- After ok=true: say the promise is recorded and say exactly "You will receive a text message confirming this promise." Then thank them, say goodbye and close promise. If create_promise fails: call it once more; if it fails again say you could not record it and close no_promise / service_error.
- If a transfer happens after a recorded promise, close transferred with that transfer's reason."""

nodes = {
  "setup": code_node("setup", SETUP, "intro"),
  "intro": {"name": "intro", "node_type": "conversation",
    "on_enter": {"type": "tts", "text": "Hello, this is Freya Bank's digital assistant. This call is recorded. Am I speaking with {{title}} {{last_name}}?"},
    "task_message": INTRO_TASK, "role_message": "", "interruptible": True, "max_node_turns": 80,
    "tools": [VERIFY, CALLBACK, TRANSFER, CLOSE],
    "transitions": [CLOSED_TR,
      {"target_node": "load_account", "description": "Both questions passed", "condition": {"logic": "or", "conditions": [
        {"variable": "id_state", "operator": "equals", "operand": "verified"},
        {"variable": "verify_identity_response.data.all_verified", "operator": "equals", "operand": "true"},
        {"variable": "verify_identity_response.data.all_verified", "operator": "equals", "operand": "True"}]}}]},
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
    "task_message": NEG_TASK, "role_message": "", "interruptible": True, "max_node_turns": 80,
    "tools": [PROMISE, TRANSFER, CLOSE],
    "transitions": [CLOSED_TR]},
  "goodbye": {"name": "goodbye", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
    "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
      "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}}},
}
wf = {"nodes": nodes, "global_nodes": {}, "initial_node": "setup", "system_prompt": SYSTEM, "tools": [],
      "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}}
json.dump(wf, open("out/brief-a.workflow.json", "w"), indent=1)
print("ok")
