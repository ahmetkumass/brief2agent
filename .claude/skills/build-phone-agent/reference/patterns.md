# Copy-ready patterns for Freya workflows

All values in CAPITALS or <angle brackets> come from the brief. Nothing here is a rule of any bank.

## 1. Calendar code node (initial node)

```json
"setup": {
  "name": "setup", "node_type": "code", "passthrough": true, "passthrough_default_transition": "opening",
  "on_enter": {"type": "silent"}, "disable_inactivity_monitor": true,
  "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
    "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": "<PYTHON BELOW AS ONE JSON STRING>"}, "timeout_ms": {"type": "number", "default": 10000}}}}}],
  "transitions": [{"target_node": "opening", "description": "always", "condition": {"operator": "always"}}]
}
```

Python (fill HOLIDAYS, WEEKEND, BANDS from the brief; keep the structure; never write two braces in a row):

```python
import datetime
try:
    HOLIDAYS = set(['YYYY-MM-DD'])            # from the brief
    WEEKEND = set([5, 6])                     # Monday=0; from the brief
    NAMES = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']  # translate if the call language differs
    now = str(vars.get('now') or '')
    today = datetime.date.fromisoformat(now[:10])
    def is_bd(d):
        return d.weekday() not in WEEKEND and d.isoformat() not in HOLIDAYS
    def nth_bd_after(d, n):
        c, k = d, 0
        while k < n:
            c = c + datetime.timedelta(days=1)
            if is_bd(c): k += 1
        return c
    rows = []
    for i in range(0, 46):
        d = today + datetime.timedelta(days=i)
        tag = 'business day' if is_bd(d) else ('HOLIDAY - not a business day' if d.isoformat() in HOLIDAYS else 'weekend - not a business day')
        rows.append(d.isoformat() + ' ' + NAMES[d.weekday()] + ' - ' + tag)
    # last business day of this calendar week / next week
    monday = today - datetime.timedelta(days=today.weekday())
    def last_bd_of_week(mon):
        for k in range(6, -1, -1):
            d = mon + datetime.timedelta(days=k)
            if is_bd(d): return d
        return None
    lw = last_bd_of_week(monday); lnw = last_bd_of_week(monday + datetime.timedelta(days=7))
    vars['today'] = today.isoformat()
    vars['today_name'] = NAMES[today.weekday()]
    vars['now_time'] = now[11:16]
    vars['next_bd'] = nth_bd_after(today, 1).isoformat()
    vars['last_bd_this_week'] = lw.isoformat() if lw else ''
    vars['last_bd_next_week'] = lnw.isoformat() if lnw else ''
    vars['cal_text'] = 'Today is ' + today.isoformat() + ' (' + NAMES[today.weekday()] + '), time ' + now[11:16] + '.\nCalendar:\n' + '\n'.join(rows)
    vars['setup_state'] = 'ok'
except Exception as e:
    vars['cal_text'] = 'Calendar unavailable'
    vars['setup_state'] = 'error'
```

Band deadlines are computed per product in the facts step (section 4), because they depend on `days_late`.

## 2. api_call tool with hooks (model-called)

```json
{
  "type": "function",
  "config": {"timeoutMs": 10000, "maxRetries": 0},
  "function": {
    "name": "verify_identity",
    "handler": "__function__:api_call",
    "description": "CALL this every time the customer answers a security question, with that one answer. ...",
    "parameters": {"type": "object", "properties": {
      "url": {"type": "string", "default": "<BASE>/verify_identity"},
      "method": {"type": "string", "default": "POST"},
      "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
      "body": {"type": "object", "properties": {
        "customer_id": {"type": "string", "default": "{{customer_id}}"},
        "field": {"type": "string", "enum": ["<from openapi>"], "description": "Which question was answered. One of: ...", "default": "{{field}}"},
        "answer": {"type": "string", "description": "The answer, normalised: ...", "default": "{{answer}}"}
      }, "required": ["field", "answer"]}
    }}
  },
  "pre_process_code": "<python: normalise vars/config body>",
  "post_process_code": "<python: see below>",
  "response_mapping": [{"path": "data.all_verified", "variable": "id_all_verified"}]
}
```

Notes:
- A model-filled body field must NOT share its name with a variable that is already set (it would be baked). Use names like `{{field}}`, `{{answer}}`, `{{promise_amount}}` only if no node sets them.
- Header with a team key or auth: add it under `headers.properties` with a `default`, only if the contract requires it.

### Post-hook template (adapt the messages to the brief; keep try/except)

```python
try:
    if isinstance(result, dict):
        result.pop('header', None)
        d = result.get('data')
        if not isinstance(d, dict):
            d = dict()
            result['data'] = d
        ok = d.get('ok')
        if ok is False or result.get('status_code', 200) >= 500 or result.get('status') not in (None, 'success'):
            n = int(vars.get('promise_fail_n') or 0) + 1
            vars['promise_fail_n'] = n
            d['what_to_do_next'] = 'NOT RECORDED. ' + ('Call the same tool again once with exactly the same values. Do not tell the customer it is recorded.' if n < 2 else 'It failed twice. Tell the customer you could not record it. Then <brief rule>.')
        else:
            d['what_to_do_next'] = 'Recorded. Now say exactly: <mandatory sentence>. Then <next step>.'
except Exception:
    pass
```

A 500 from the server may arrive as `status` != success with no `data`; the hook covers that. `vars` is readable/writable in hooks.

## 3. api_request node (engine-called, e.g. get_account after verification)

```json
"load_account": {
  "name": "load_account", "node_type": "api_request", "passthrough": true, "passthrough_default_transition": "facts",
  "on_enter": {"type": "silent"}, "disable_inactivity_monitor": true, "suppress_tool_results": false,
  "pre_actions": [{"type": "function", "config": {"timeoutMs": 10000, "maxRetries": 2}, "function": {"name": "get_account", "handler": "__function__:api_call", "description": "Get the account.",
    "parameters": {"type": "object", "properties": {"url": {"type": "string", "default": "<BASE>/get_account"}, "method": {"type": "string", "default": "POST"},
      "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
      "body": {"type": "object", "properties": {"customer_id": {"type": "string", "default": "{{customer_id}}"}}, "required": []}}}}}],
  "response_mapping": [{"path": "data.products", "variable": "products"}],
  "transitions": [{"target_node": "facts", "description": "always", "condition": {"operator": "always"}}]
}
```

## 4. Facts code node (after get_account)

Read products defensively: mapped variable may be a list, a JSON string or a Python-repr string; fall back to flattened keys `get_account_response.data.products.0.past_due` etc. (Note: for a pre_actions node the auto keys are named after the node: `load_account_response...`; check both.)

```python
import json, ast, datetime
try:
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
                for k in ('product_id','type','card_last4','past_due','days_late','minimum_payment','instalment_amount'):
                    kk = prefix + str(i) + '.' + k
                    if kk in vars: p[k] = vars[kk]
                prods.append(p); i += 1
            if prods: break
    # per product: band, deadline (reuse calendar helpers: copy is_bd / nth_bd_after here), floor, spoken name, valid dates
    ...
    vars['debt_text'] = '...'      # one line per product, in get_account order, with product_id
    vars['plan_text'] = '...'      # per product: band, attempts, deadline, floor, attempt-1 date, attempt-2 offer, valid dates list
    vars['n_products'] = str(len(prods))
    vars['facts_state'] = 'ok' if prods else 'empty'
except Exception as e:
    vars['debt_text'] = 'Account details unavailable'
    vars['plan_text'] = ''
    vars['facts_state'] = 'error'
```

Amounts: format money as the brief does (2 decimals if needed), and give the amount the tool needs as a plain number.

## 5. Closing via tool + end node

Conversation nodes carry the `close_call` tool (enum outcome + reason from the brief's table; description = the table). Transition (first in the list):

```json
{"target_node": "goodbye", "description": "The call was closed", "condition": {"logic": "or", "conditions": [
  {"variable": "close_call_success_count", "operator": "greater_than", "operand": 0}]}}
```

```json
"goodbye": {"name": "goodbye", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": true, "transitions": [],
  "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
    "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "none"}}}}}}
```

The farewell (thank + goodbye) is spoken by the conversation node in the same turn, BEFORE it calls close_call. Prompt: "When the call must end: in ONE turn say the closing words (thank the customer, goodbye), and call close_call."

## 6. Routing on a tool result (identity → account)

Use a string flag written by the post-hook (`vars['id_state'] = 'verified' | 'failed' | 'pending'`) or test both spellings:

```json
{"target_node": "load_account", "description": "Both questions passed", "condition": {"logic": "or", "conditions": [
  {"variable": "id_state", "operator": "equals", "operand": "verified"},
  {"variable": "verify_identity_response.data.all_verified", "operator": "equals", "operand": "true"},
  {"variable": "verify_identity_response.data.all_verified", "operator": "equals", "operand": "True"}]}}
```

## 7. Prompt skeleton for the main conversation node

```
<role line>. Speak <LANGUAGE> only. One or two short sentences per turn. One question at a time.
After every tool result: follow its what_to_do_next, then speak to the customer or call the next tool. Never end a turn with nothing.
Never say something is recorded/scheduled/transferred unless the tool returned ok=true.

FACTS (computed, trust them, never compute dates yourself):
{{debt_text}}
{{plan_text}}
{{cal_text}}

RULES, in priority order:
1. (interrupts that come first: hardship, dispute, already paid, restructuring, human, scam, AI question, unknown question)
2. ... the promise flow step by step with the exact attempt offers ...
3. read-back + "<confirm question>" + create_promise only after a clear yes
4. closing table
```

Number the rules, keep the brief's wording for anything quoted, and state explicit decision tables ("if the customer names a date: if it is in VALID DATES → accept; if weekend/holiday ≤ deadline → offer the next business day after it; if > deadline → say the latest date is <deadline> and offer it").
