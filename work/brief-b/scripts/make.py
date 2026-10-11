import json, copy
w = json.load(open('out/brief-a.workflow.json'))
w['system_prompt'] = w['system_prompt'].replace(' Never use add_note.', ' Use add_note only as the negotiate stage instructions say.')
neg = w['nodes']['negotiate']
facts = w['nodes']['facts']
code = facts['pre_actions'][0]['function']['parameters']['properties']['code']['default']
# per-product numbering + order list
code = code.replace("    debt = []\n    plan = []\n    for p in prods:\n",
 "    debt = []\n    plan = []\n    order = []\n    for idx, p in enumerate(prods):\n")
code = code.replace("        debt.append('product_id=' + str(p.get('product_id'))",
 "        order.append(str(p.get('product_id')))\n        debt.append('PRODUCT ' + str(idx + 1) + ': product_id=' + str(p.get('product_id'))")
code = code.replace("        s = ('Product ' + str(p.get('product_id'))", "        s = ('=== PRODUCT ' + str(idx + 1) + ' product_id=' + str(p.get('product_id'))")
code = code.replace("close no_promise/refused.", "this product ends without a promise: add_note reason refused, move to the next product.")
code = code.replace("    vars['debt_text'] = '\\n'.join(debt)\n",
 "    vars['debt_text'] = '\\n'.join(debt)\n    vars['pid_order'] = json.dumps(order)\n    vars['n_products'] = str(len(order))\n")
assert "pid_order" in code and "PRODUCT ' + str(idx" in code
facts['pre_actions'][0]['function']['parameters']['properties']['code']['default'] = code

STATUS = r'''
def _status(vars):
    import json as _j
    try:
        order = _j.loads(vars.get('pid_order') or '[]')
    except Exception:
        order = []
    try:
        st = _j.loads(vars.get('pstate') or '{}')
    except Exception:
        st = dict()
    left = [p for p in order if p not in st]
    if left:
        return 'Products still open (no promise and no note yet): ' + ', '.join(left) + '. Continue with the next one in order.'
    if vars.get('transferred') == 'yes':
        return ''
    if any(v == 'promise' for v in st.values()):
        return 'All products are handled. Close with outcome=promise (no reason).'
    rs = [st[p] for p in order if p in st]
    if rs and all(r == 'paid' for r in rs):
        return 'All products are handled. Close with outcome=paid (no reason).'
    first = [r for r in rs if r != 'paid']
    return 'All products are handled. Close with outcome=no_promise reason=' + (first[0] if first else 'refused') + '.'
def _mark(vars, pid, val):
    import json as _j
    try:
        st = _j.loads(vars.get('pstate') or '{}')
    except Exception:
        st = dict()
    if not (st.get(pid) == 'promise'):
        st[pid] = val
    vars['pstate'] = _j.dumps(st)
'''

def find(name):
    return [t for t in neg['tools'] if t['function']['name'] == name][0]

cp = find('create_promise')
cp['function']['description'] = 'CALL this only after the customer clearly said yes to your combined read-back and "Do you confirm?". Call it ONCE PER PRODUCT (one product per call). product_id from FACTS, amount as a plain number, date YYYY-MM-DD from that product\'s VALID PROMISE DATES.'
cp['pre_process_code'] = "try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        vars['last_pid'] = str(b.get('product_id'))\nexcept Exception:\n    pass\n"
cp['post_process_code'] = STATUS + r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        pid = str(vars.get('last_pid') or '')
        failed = d.get('ok') is False or (result.get('status') not in (None, 'success')) or int(result.get('status_code', 200) or 200) >= 500
        if failed or d.get('ok') is not True:
            k = 'pfail_' + pid
            n = int(vars.get(k) or 0) + 1
            vars[k] = n
            if n < 2:
                d['what_to_do_next'] = 'NOT RECORDED for product ' + pid + '. Call create_promise again right now, once, with exactly the same values. Do not say it is recorded.'
            else:
                d['what_to_do_next'] = 'NOT RECORDED for product ' + pid + ', failed twice. Do not try again. Call add_note for product ' + pid + ' with reason service_error, tell the customer you could not record the promise for that product, then go on with any other agreed promises (call create_promise for them).'
        else:
            _mark(vars, pid, 'promise')
            vars['promise_done'] = 'yes'
            d['what_to_do_next'] = 'Promise for product ' + pid + ' is recorded. If other agreed promises are still to be recorded, call create_promise for them now. When all agreed promises are written: say they are recorded and say exactly: "You will receive a text message confirming this promise." ' + _status(vars)
except Exception:
    pass
'''

note = copy.deepcopy(cp)
note.pop('pre_process_code', None)
nf = note['function']
nf['name'] = 'add_note'
nf['description'] = ('CALL this once for each product that ends WITHOUT a promise, with that product_id and reason: refused (attempts used up / does not want to talk), hardship (hardship, declined support transfer), '
    'dispute (not theirs / closed or paid off in the past), paid (says already paid this past-due amount), service_error (create_promise failed twice). Also when no product gets a promise. NEVER call it when a transfer happens or happened in this call.')
props = nf['parameters']['properties']
props['url']['default'] = props['url']['default'].replace('create_promise', 'add_note')
props['body'] = {'type': 'object', 'properties': {
    'customer_id': {'type': 'string', 'default': '{{customer_id}}'},
    'product_id': {'type': 'string', 'default': '{{n_pid}}', 'description': 'product_id from FACTS'},
    'reason': {'type': 'string', 'enum': ['refused', 'hardship', 'dispute', 'paid', 'service_error'], 'default': '{{n_reason}}'},
    'text': {'type': 'string', 'default': '{{n_text}}', 'description': 'one short sentence'}},
    'required': ['product_id', 'reason']}
note['pre_process_code'] = "try:\n    b = config.get('body')\n    if isinstance(b, dict):\n        vars['last_note_pid'] = str(b.get('product_id'))\n        vars['last_note_reason'] = str(b.get('reason'))\nexcept Exception:\n    pass\n"
note['post_process_code'] = STATUS + r'''
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        pid = str(vars.get('last_note_pid') or '')
        failed = d.get('ok') is False or (result.get('status') not in (None, 'success')) or int(result.get('status_code', 200) or 200) >= 500
        if failed or d.get('ok') is not True:
            k = 'nfail_' + pid
            n = int(vars.get(k) or 0) + 1
            vars[k] = n
            if n < 2:
                d['what_to_do_next'] = 'Note not saved. Call add_note again once with the same values.'
            else:
                _mark(vars, pid, str(vars.get('last_note_reason') or 'refused'))
                d['what_to_do_next'] = 'Note could not be saved; continue. ' + _status(vars)
        else:
            _mark(vars, pid, str(vars.get('last_note_reason') or 'refused'))
            d['what_to_do_next'] = 'Note saved (internal, do not mention it). ' + _status(vars)
except Exception:
    pass
'''
neg['tools'].insert(1, note)

tr = find('transfer_to_agent')
tr['post_process_code'] = tr['post_process_code'].replace("result.pop('header', None)", "result.pop('header', None)\n        vars['transferred'] = 'yes'", 1)

cc = find('close_call')
cc['function']['description'] = cc['function']['description'].replace(
 'Table: promise (no reason) = a promise was recorded with ok=true.',
 'MULTI-PRODUCT: promise (no reason) = at least one promise recorded with ok=true (unless a transfer happened: then transferred/<that reason>). No promise recorded: every product noted paid -> paid; otherwise no_promise with the reason of the FIRST product (get_account order) whose note is not paid. Table:')

neg['task_message'] = r'''STAGE: the customer {{title}} {{last_name}} is VERIFIED. Now handle the late products. The customer may have 1 to 3 products; each has its OWN band, deadline, floor, attempts and valid dates (see FACTS). Never compute dates yourself; look them up in FACTS.

FACTS (computed by code, trust them):
{{debt_text}}
{{plan_text}}

CALENDAR:
{{cal_text}}

STEP 1 (your first turn here): say you are calling from the collections team about late payments. State EVERY product, one sentence each, in FACTS order: spoken name exactly (e.g. "credit card ending 4821" / "personal loan" / "car loan"), past-due amount, days late. Then ask ONE question: if one product, exactly "Can you make this payment today?"; if several, "Can you pay all of them today?". Never ask about today again later.
STEP 2: if they pay all today (full amounts) -> go to CONFIRM. Otherwise go through the products ONE BY ONE in FACTS order (PRODUCT 1 first). Each product starts at its own attempt 1; attempts are counted per product. Finish one product (agreed promise, or no promise) before moving to the next. When a product ends without a promise (attempts used up, paid, dispute, hardship declined), call add_note for it right away (see NOTES), say nothing about notes, and continue with the next product. If the customer names ONE date for everything: use it for each product, but a product whose deadline is before that date gets its OWN deadline instead (say so in the read-back).

INTERRUPTS (any moment, per product):
H. Illness, a death in the family, or job loss: one short sentence of sympathy, make NO persuasion attempt, offer to connect them with the customer support team. Accept -> transfer_to_agent queue support, close transferred / support (no notes). Decline -> add_note reason hardship for every product without a promise, then close per the closing rule. (If they themselves still name a date or amount, record that promise under the date and amount rules.)
P. "I already paid" (this past-due amount of a product): say payments can take one business day to appear, no promise for that product, add_note reason paid for it, continue with the others.
D. "Not mine", "I never had this product", "it was closed / paid off in the past": do not argue, no promise for it, add_note reason dispute, continue with the others.
R. A new payment plan, lower instalments, restructuring: do not describe any plan. Promises not yet recorded are NOT recorded. transfer_to_agent queue restructuring, close transferred / restructuring. NO add_note.
X. Says twice they do not want to talk: add_note refused for each product without a promise, then close (no_promise / refused unless a promise was recorded).
Never offer a discount, waiver, instalment plan or any other term. Never ask "how much can you pay?" - you propose every amount.

DATE RULES (for the product being discussed):
- Date in that product's VALID PROMISE DATES -> accept.
- "Next <weekday>" = that weekday in the following calendar week (see "(next week)" tags). "This <weekday>" = current week.
- Weekend or holiday not after the deadline -> offer the next business day listed in NON-BUSINESS DAYS for that product.
- After the product's deadline -> say the latest date you can record is the deadline and offer it. Refusing the deadline = flat refusal (uses an attempt).
- Vague ("next week", "end of month", "when my salary comes") -> ask once for the exact day; if still none, propose the deadline.
AMOUNT RULES (per product):
- Default amount is the FULL past-due amount.
- Full too much -> offer the FLOOR once, saying the rest stays overdue. Refusing the floor = flat refusal (uses an attempt).
- Amount from the floor up to the full amount (inclusive) -> accept. Below the floor -> say it cannot be recorded and offer the floor once; not accepted -> flat refusal.
- A date or amount the customer proposes is never a refusal.

PERSUASION (per product; a "no" with no date and no amount, or a non-answer, is a flat refusal and uses one attempt):
- Attempt 1: the product's attempt 1 offer from FACTS (floor instead of full if they already said the full amount is too much for that product).
- Attempt 2 (only late-band products): the floor on that product's deadline.
- Attempts used up -> stop for that product, never repeat a refused offer; add_note refused; next product.

CONFIRM AND RECORD:
- When every product is either agreed or ended: read back ALL agreed promises together (each product's spoken name, amount, date with weekday; mention if a product was moved to its deadline) and ask exactly "Do you confirm?" once. If they change something, check it and read back again.
- After a clear yes: call create_promise once per agreed product (one call each). Follow what_to_do_next. A failure: retry once; second failure -> add_note service_error for that product and keep the others.
- One promise per product; a recorded one cannot be changed or cancelled (say they can change it in the mobile app).
- After the promises are recorded say they are recorded and say exactly "You will receive a text message confirming this promise."
NOTES: every product without a recorded promise gets exactly one add_note (refused, hardship, dispute, paid, service_error) - also when no product has a promise. NEVER add notes if a transfer happens in the call (support, restructuring, human).
CLOSING: thank them and say goodbye, and call close_call in the same turn. At least one promise recorded -> promise (but any transfer -> transferred / its reason). No promise: all products noted paid -> paid; otherwise no_promise with the reason of the first product (FACTS order) whose note is not paid. Follow the "Close with" hint in the latest what_to_do_next.'''
neg['max_node_turns'] = 80
json.dump(w, open('out/brief-b.workflow.json', 'w'), indent=1)
print('ok')
