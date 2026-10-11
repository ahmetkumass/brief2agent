---
name: build-phone-agent
description: Build a Freya phone agent from a bank's brief (clean spec or raw bank material), test it and fix what fails. Use when asked to build or improve a phone agent from a brief.
---

# Build a phone agent from a brief

You work in the kit folder. Everything about the bank comes from the brief documents you are given. Never copy a rule, number, name, holiday or outcome from another brief, from the examples or from this skill. This skill gives you the *engineering patterns* that make a Freya agent reliable; the brief gives you the *content*.

The agent is scored per customer: bank ledger exactly right AND conversation inside the brief AND honest. A customer counts only if it passes 3 out of 3 runs. So: **put every rule you can into code, routes and tool hooks. Prompts are the last resort.**

## Step 0. Clock
Run `date`. You have the time budget stated in your task. Plan: rules (≤6 min) → workflow (≤10 min) → save + smoke (≤2 min) → one test round + fixes. Never start a test that cannot finish inside the budget.

## Step 1. Read everything, then write `work/<slot>/rules.md`
Read `work/<slot>/corpus.md` fully (all files: brief, mails, memos, policy extracts, code lists, Excel tables, example conversations, service contract / openapi). Raw material may contradict itself: a later memo or mail that changes a policy WINS over the older text; note each such override explicitly. Example conversations show tone and phrasing but the written rules win.

Write `rules.md` with these sections (fill from the brief; "none" if absent):
1. Language of the calls (the language of the brief / example conversations; if the brief is Turkish, the agent speaks Turkish and all fixed lines are Turkish). Mandatory sentences, quoted exactly.
2. Call variables (names, formats, what `now` means).
3. Opening + who-is-on-the-line rules, words forbidden before verification.
4. Third party / callback window / wrong number / deceased.
5. Identity: which fields, in which order, how to normalise each answer for the tool, max wrong answers, retries that do not count, decline handling.
6. Products and how to name them; what to state after verification.
7. Calendar: business days, holidays (exact list), deadline per band, band table, persuasion attempts per band, relative date rules ("next Friday"...).
8. Amounts: full amount, floor per product type, partial amounts allowed?, what may never be asked/offered.
9. Promise flow: first question, attempt 1/2 offers, refusal definition, hardship, disputes, already paid, restructuring, human request, scam question, unknown questions, do-not-want-to-talk.
10. Confirmation + recording + failure/retry + mandatory sentence after recording.
11. Multi-product rules (order, notes per product, combined read-back, closing reason precedence).
12. Outcome table: every (outcome, reason) and when. Note which tools are never used.
13. Tools: from the openapi file of THIS brief: url base, every path, every body field, enums, response fields, error semantics, whether a key/header is needed. (For a final case the base URL is the mock_url you were given.)

## Step 2. Design the workflow (pattern)
Read `reference/patterns.md` in this skill folder now (copy-ready JSON snippets for every node type below) and `docs/workflow-format.md`, `docs/tools-and-code.md` only for details you need. Read `examples/base-agent.json` for the JSON shape only.

Recommended graph (adapt names/steps to the brief, drop steps the brief does not have):

```
setup (code, passthrough)          computes calendar facts from `now` → {{cal_text}}, today, deadlines per band
  → opening (conversation)          fixed tts opening; confirm the right person; third-party handling with schedule_callback; close_call tool
  → identity (conversation)         verify_identity tool with post-hook what_to_do_next; close_call tool
       route on verify result (string flag) → load_account
  → load_account (api_request, passthrough)  get_account; post-hook writes facts per product
  → facts (code, passthrough)       per product: band, deadline, floor, spoken product name, allowed dates text → {{debt_text}}, {{plan_text}}
  → negotiate (conversation)        states the debt, runs the promise flow; tools: create_promise, add_note, transfer_to_agent, close_call
       route on close_call ok → goodbye (end_call, message_mode none)
global nodes: none needed for most briefs (keep scam/AI/human questions in system_prompt: they are answer-and-continue rules);
```

Hard rules (each one comes from a failure seen in practice runs):
- **Every tool the brief needs must be present in the node where it can be needed.** close_call must be available in every conversation node (callers can end anywhere). schedule_callback in the opening/third-party node. transfer_to_agent wherever restructuring/hardship/human can come up.
- **Calendar in code.** setup computes: today's weekday, a table of the next ~45 days (date, weekday, business day yes/no, holiday name, business-day index), last business day of this week and of next week, and for every band the deadline (N-th business day after today, counting rules exactly as the brief says). Put this as text in prompts (`{{cal_text}}`). Never ask the LLM to count business days.
- **Product facts in code.** After get_account, a code node or post-hook writes per product: product_id, spoken name, past_due, days_late, band, deadline, floor, attempts allowed, and the exact list of valid promise dates. The model copies product_id from that text; never let it invent ids.
- **Decision tables, not decisions.** The facts code writes, per product, a DATE TABLE (every date from today to +45 days → ACCEPT / offer <date> / after deadline → offer <deadline>), AMOUNT RULES with the numbers filled in, and the persuasion ladder as numbered STEPS with exact offers (see patterns.md section 4). The prompt says: look the date up, never compute, never repeat a step.
- **Words the judge watches.** Words such as "recorded/registered/saved/kaydedildi" may appear only after a successful write, except inside a sentence the brief itself mandates (e.g. a call-recording notice: say exactly the brief's wording there and nowhere else). After a failed write say "could not complete it", not "not recorded yet".
- **Tool results carry the next step.** Every api_call tool gets a `post_process_code` that pops `header` and adds `result["data"]["what_to_do_next"]` = one plain sentence: what the result means and what to say/call next (e.g. verified=false + wrong_answers_left=0 → "Identity check failed. Tell the customer to use <channel from brief>, say goodbye, then call close_call with outcome=<x> reason=<y>." ; ok=false on a write → "NOT recorded. Call create_promise again once with the same values" / after the 2nd failure → "Say you could not record it. Then close with <reason>"). Keep counters in `vars` inside the hook (try/except).
- **Honesty.** Prompt + hook: only say "recorded/scheduled/transferred" after ok=true. After a tool result always speak or call the next tool, never an empty turn.
- **Exact closing.** close_call is a model tool with `enum` on outcome and reason (from the brief's table). Its tool description lists the full table "use outcome X reason Y when ...". The farewell sentence is said in the same turn BEFORE calling close_call; a transition on `close_call_response.data.ok` (true/True) or `close_call_success_count > 0` goes to an end_call node with `message_mode: none`.
- **Fixed lines as tts** where the brief quotes a sentence (opening, sympathy, mandatory confirmation sentence can be required in prompt "say exactly: ...").
- **Read-back + explicit confirmation before any write**, as the brief says; one promise per product; never change a recorded one.
- **Identity:** normalise answers in a `pre_process_code` hook (dates → YYYY-MM-DD with the brief's day/month order; digits only; trim). Ask one question at a time. Respect the hint semantics the openapi describes (e.g. a swapped day/month hint is a free retry).
- **Before verification** the model must not see debt details: do not put debt text into opening/identity prompts.
- **Language**: system_prompt states the language. All tts lines and spoken_message in that language. Dates spoken naturally in that language.
- No `agent_config`, no `null` anywhere, no `{{` or `}}` inside Python code, every passthrough ends with an `always` transition, `min_confidence` ≤ 0.7 on extraction, string flags for routing, `maxRetries: 0` on write tools (the model retries per the brief instead), `max_node_turns` 60 with a `max_turn_transition` to a safe close node is NOT needed — leave defaults except set `max_node_turns: 80` on the main conversation nodes.
- Tool URLs: practice → the url in `tools/openapi.json` servers; final → `<mock_url>` + paths from the final service contract. Body field names/enums from THAT contract.

## Step 3. Write, validate, save
- Write `out/<slot>.workflow.json`. Validate the JSON with python (`json.load`) and run `python3 builder/check_workflow.py out/<slot>.workflow.json` (static checks: tools present, passthrough always, no null, no braces in code). Fix everything it reports.
- Save: `python3 -c "import freya,json,sys; print(json.dumps(freya.save_workflow(sys.argv[1], json.load(open(sys.argv[2])))))" <slot> out/<slot>.workflow.json` (same slot updates in place; this publishes). If it fails, read the error, fix, save again.
- Smoke: `python3 builder/chat_smoke.py <slot>` sends 2 chat turns with the test variables and prints what the agent says. It must open correctly in the right language.

## Step 4. Test and fix
- **Practice brief** (task says practice A or B): `python3 tools/run_cases.py <agent_id> --brief <A|B> --out results/<slot>.json`. Foreground. Never background, never end your turn during a test.
- **Final brief**: build a cases file from the brief's test customers and example conversations in the same format as `public-test-set.json` (variables, identity, products, script, expected outcome/promises/notes/callbacks/transfers, checks), save as `work/<slot>/cases.json` (each case also gets `"brief": "final"`, `"language": "<call language, e.g. Turkish>"` so the simulated customer speaks it, `"family"` (use `"Third party"` when someone else answers), and a `script` written in the brief's language describing what the customer says; one case per test customer / example conversation, ids matching the mock's `case` fields), then run `FREYA_BANK_HOST=<mock_url without /v1> python3 tools/run_cases.py <agent_id> --cases work/<slot>/cases.json --out results/<slot>.json` — only if the mock implements the practice endpoints (bank-mock skill). Otherwise do 2–3 scripted chat conversations with `builder/chat_smoke.py <slot> --script "<turn1>|<turn2>|..."` covering the happy path and one failure path, and read the transcripts.
- For every FAIL: read the reason; if unclear `python3 -c "import freya,json;print(json.dumps(freya.get_call('<call_id>')['messages'],indent=1)[:20000])"`. Fix the root cause in the workflow file (prefer code/route/hook fixes), save, re-test. Max 2 fix rounds, inside the time budget.
- Print each test summary line (`N / M passed`) in your reply so the trace records it.

## Step 5. Finish
Final line exactly: `RESULT workflow_id=<id> agent_id=<id> nodes=<n> tools=<n> selftest=<e.g. 9/10 practice A>`.

## Never
- Never edit the agent on the platform by hand. Change the file, save again.
- Never put anything specific to a brief into files outside `out/`, `work/`, `results/`, `mock/`.
- Never change `AGENT_LLM` in freya.py.
