---
name: bank-mock
description: Write and deploy the bank's tool API as a mock on Cloudflare Workers from the brief's service contract and test customers. Use when the brief folder asks for a mock of the bank's services or when a mock_url must be served by us.
---

# Bank mock on Cloudflare Workers

Use this only when the brief documents ask you to provide the bank's services (a service contract + test customers), or the task says the mock must be deployed. The phone agent calls this mock during evaluation: an unreachable or wrong mock fails every conversation. Correctness and uptime matter more than features.

## Steps
1. From `work/<slot>/corpus.md` collect: the service contract (paths, request fields, response fields, error semantics, auth headers, status codes, any ledger/admin/session endpoints the evaluators will call), and the test customers (ids, names, identity answers, products and balances, any scripted failures such as "the first create_promise fails").
2. Copy `template/` from this skill folder to `mock/<slot>/`. Fill `customers.json` with the test customers in the contract's own shape (keep their ids exactly). Edit `worker.js` so every path, field name, enum, response shape and status code matches the contract exactly. The template mirrors the practice mock's behaviour (identity attempts, swapped day/month hint, one-promise-per-product, scripted failures, ledger, practice session endpoints) — keep what the contract agrees with, change what it does not, add what it adds. If the contract says the service does not enforce the brief, do not enforce it.
3. Deploy: in `mock/<slot>/` set `name` in `wrangler.toml` to `freya-bank-<slot>` (lowercase, dashes). Create the KV namespace once: `npx -y wrangler@4 kv namespace create LEDGER` and put its id into `wrangler.toml`. Then `npx -y wrangler@4 deploy`. The URL printed (`https://freya-bank-<slot>.<account>.workers.dev`) + the contract's base path is the mock_url.
4. Smoke test with curl every endpoint against a test customer: print `SMOKE <path> <status> <body>` lines. Fix until all pass. Then print `DEPLOYED <mock_url>`.
5. Use that mock_url as the tool base URL in the workflow (unless the task gave a mock_url, then make sure it is this deployment).

## Rules
- No secrets in the code. If the contract requires an auth header, accept the value the contract defines.
- Keep state in KV (`LEDGER`), keyed by customer id (plus a session id if the contract has sessions). In-memory state is lost between requests.
- Answer every unknown path with 404 JSON, every bad body with 400 JSON `{ok:false,error}`; never throw (wrap the handler in try/catch, return 500 JSON).
- CORS is not needed.
