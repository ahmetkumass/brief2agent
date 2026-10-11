---
name: bank-mock
description: Write and deploy the bank's tool API as a mock on Cloudflare Workers from the brief's service contract and test customers. Use when the brief folder asks for a mock of the bank's services or when a mock_url must be served by us.
---

# Bank mock on Cloudflare Workers

Use this only when the brief documents ask you to provide the bank's services (a service contract + test customers), or the task says the mock must be deployed. The phone agent calls this mock during evaluation: an unreachable or wrong mock fails every conversation. Correctness and uptime matter more than features.

## Steps
1. From `work/<slot>/corpus.md` collect: the service contract (paths, request fields, response fields, error semantics, auth headers, status codes, any ledger/admin/session endpoints the evaluators will call), and the test customers (ids, names, identity answers, products and balances, any scripted failures such as "the first create_promise fails").
2. Copy `template/` from this skill folder to `mock/<slot>/`. Fill `customers.json` with the test customers in the contract's own shape (keep their ids exactly). Edit `worker.js` so every path, field name, enum, response shape and status code matches the contract exactly. The template mirrors the practice mock's behaviour (identity attempts, swapped day/month hint, one-promise-per-product, scripted failures, ledger, practice session endpoints) — keep what the contract agrees with, change what it does not, add what it adds. If the contract says the service does not enforce the brief, do not enforce it.
3. Deploy: in `mock/<slot>/` set `name` in `wrangler.toml` to the worker name you were given (or `freya-bank-<slot>`, lowercase, dashes). State lives in a Durable Object (`BANK`, already declared in wrangler.toml, no KV to create). Then `npx -y wrangler@4 deploy`. The URL printed (`https://<name>.<account>.workers.dev`) + the contract's base path is the mock_url. The first request after a new deploy may fail for a few seconds (DNS): retry curl up to 10 times, 3 s apart.
4. Smoke test with curl every endpoint against a test customer: print `SMOKE <path> <status> <body>` lines. Fix until all pass. Then print `DEPLOYED <mock_url>`.
5. Use that mock_url as the tool base URL in the workflow (unless the task gave a mock_url, then make sure it is this deployment).

## Rules
- No secrets in the code. If the contract requires an auth header, accept the value the contract defines.
- Keep state through `env.LEDGER` (get/put/delete, backed by the single Durable Object so concurrent tool calls never lose a write), keyed by customer id (plus a session id if the contract has sessions). Do not switch to KV or in-memory state.
- Answer every unknown path with 404 JSON, every bad body with 400 JSON `{ok:false,error}`; never throw (wrap the handler in try/catch, return 500 JSON).
- CORS is not needed.
- Self-test compatibility (keep this even if the contract renames fields): `POST /v1/practice/sessions {"case": "<case id>"}` resets that customer's ledger and returns `{variables: {customer_id, ...call variables}}`; `GET /v1/practice/ledger/<customer_id>` returns the ledger with these normalised keys: `outcome`, `reason`, `promises[{product_id, amount (number), date YYYY-MM-DD}]`, `notes[{product_id, reason}]`, `callbacks[{date, time}]`, `transfers[{queue}]`, `calls[{tool, args, status, result}]` where `tool` is the contract's tool name. Every customer in `customers.json` gets a `case` field (the case id used in `work/<slot>/cases.json`) and `variables` (first_name, last_name, now, and every other call variable the brief lists). If the contract uses other field names (e.g. `tutar` instead of `amount`), map them into these keys when writing the ledger.
