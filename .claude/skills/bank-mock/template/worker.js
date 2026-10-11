// Bank tool API mock. Adapt every path, field and response to the brief's service contract.
import DATA from "./customers.json";

const BASE = "/v1";                       // contract base path
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json" } });

function customer(id) { return (DATA.customers || []).find(c => c.customer_id === id || c.id === id); }

async function load(env, id) {
  const raw = await env.LEDGER.get("l:" + id);
  return raw ? JSON.parse(raw) : { verified: {}, wrong: 0, hinted: false, promises: [], notes: [], callbacks: [], transfers: [], outcome: null, reason: null, failures: {}, calls: [] };
}
async function save(env, id, l) { await env.LEDGER.put("l:" + id, JSON.stringify(l)); }

function normDate(s) {
  const m = String(s || "").trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return null;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return d.getUTCMonth() === +m[2] - 1 ? m[0] : null;
}

const TOOLS = {
  async verify_identity(c, b, l) {
    const fields = Object.keys(c.identity || {});
    if (!fields.includes(b.field)) return { ok: false, error: "unknown field" };
    if (l.wrong >= 3) return { ok: false, error: "identity check closed", verified: false, wrong_answers_left: 0, all_verified: false };
    let ans = String(b.answer || "").trim(), exp = String(c.identity[b.field]);
    if (b.field.includes("date")) {
      const d = normDate(ans);
      if (!d) return { ok: false, error: "unreadable date" };
      if (d !== exp) {
        const [y, m, dd] = d.split("-");
        if (`${y}-${dd}-${m}` === exp && !l.hinted) { l.hinted = true; return { ok: true, verified: false, wrong_answers_left: 3 - l.wrong, all_verified: false, hint: "day_month_swapped" }; }
      }
      ans = d;
    } else ans = ans.replace(/\D/g, "") || ans;
    const okAns = ans === exp;
    if (okAns) l.verified[b.field] = true; else l.wrong += 1;
    const all = fields.every(f => l.verified[f]);
    return { ok: true, verified: okAns, wrong_answers_left: Math.max(0, 3 - l.wrong), all_verified: all };
  },
  async get_account(c, b, l) {
    if (!Object.keys(c.identity || {}).every(f => l.verified[f])) return { ok: false, error: "identity not verified" };
    return { ok: true, products: c.products.map((p, i) => ({ product_id: p.product_id || "p" + (i + 1), ...p })) };
  },
  async create_promise(c, b, l) {
    if (!Object.keys(c.identity || {}).every(f => l.verified[f])) return { ok: false, error: "identity not verified" };
    const fail = (c.fail || {}).create_promise || 0;            // scripted failures from the test customer
    l.failures.create_promise = (l.failures.create_promise || 0) + 1;
    if (l.failures.create_promise <= fail) return [500, { ok: false, error: "service unavailable" }];
    const ids = c.products.map((p, i) => p.product_id || "p" + (i + 1));
    if (!ids.includes(b.product_id)) return { ok: false, error: "unknown product_id" };
    if (l.promises.some(p => p.product_id === b.product_id)) return { ok: false, error: "promise already recorded for this product" };
    if (!normDate(b.date) || !(Number(b.amount) > 0)) return { ok: false, error: "invalid amount or date" };
    const pr = { promise_id: "pr_" + (l.promises.length + 1), product_id: b.product_id, amount: Number(b.amount), date: b.date };
    l.promises.push(pr); return { ok: true, promise_id: pr.promise_id };
  },
  async add_note(c, b, l) { l.notes.push({ product_id: b.product_id, reason: b.reason, text: b.text || "" }); return { ok: true }; },
  async schedule_callback(c, b, l) { if (!normDate(b.date) || !/^\d{2}:\d{2}$/.test(b.time || "")) return { ok: false, error: "invalid date or time" }; l.callbacks.push({ date: b.date, time: b.time }); return { ok: true }; },
  async transfer_to_agent(c, b, l) { l.transfers.push({ queue: b.queue }); return { ok: true }; },
  async close_call(c, b, l) { l.outcome = b.outcome; l.reason = b.reason || null; return { ok: true }; },
};

// All requests go through ONE Durable Object, so ledger writes are serialised (a KV read-modify-write lost
// writes when the agent called two tools at once). The handler below sees env.LEDGER with get/put/delete.
export class Bank {
  constructor(state) { this.s = state.storage; }
  async fetch(req) {
    const s = this.s;
    return handle(req, { LEDGER: { get: k => s.get(k), put: (k, v) => s.put(k, v), delete: k => s.delete(k) } });
  }
}

export default {
  async fetch(req, env) { return env.BANK.get(env.BANK.idFromName("bank")).fetch(req); },
};

async function handle(req, env) {
    try {
      const url = new URL(req.url); const path = url.pathname.replace(/\/+$/, "");
      if (path === "" || path === "/" || path === BASE + "/health") return json({ ok: true, service: "bank mock" });
      // practice-style helpers: ledger read for self-tests
      if (req.method === "GET" && (path.startsWith(BASE + "/practice/ledger/") || path.startsWith("/v1/practice/ledger/"))) { const id = path.split("/").pop(); return json({ ok: true, ...(await load(env, id)) }); }
      if (req.method === "POST" && (path === BASE + "/practice/sessions" || path === "/v1/practice/sessions")) {
        const b = await req.json().catch(() => ({})); const c = customer(b.case) || (DATA.customers || []).find(x => x.case === b.case);
        if (!c) return json({ ok: false, error: "unknown case" }, 404);
        await env.LEDGER.delete("l:" + (c.customer_id || c.id));
        return json({ ok: true, variables: { customer_id: c.customer_id || c.id, ...(c.variables || {}) } });
      }
      const tool = path.startsWith(BASE + "/") ? path.slice(BASE.length + 1) : "";
      if (req.method !== "POST" || !TOOLS[tool]) return json({ ok: false, error: "not found" }, 404);
      const b = await req.json().catch(() => null);
      if (!b || typeof b !== "object") return json({ ok: false, error: "invalid json" }, 400);
      const c = customer(b.customer_id);
      if (!c) return json({ ok: false, error: "unknown customer_id" });
      const l = await load(env, b.customer_id);
      let out = await TOOLS[tool](c, b, l), status = 200;
      if (Array.isArray(out)) [status, out] = out;
      const { customer_id, ...args } = b;
      l.calls.push({ n: l.calls.length + 1, tool, args, status, result: out });
      await save(env, b.customer_id, l);
      return json(out, status);
    } catch (e) { return json({ ok: false, error: "internal error" }, 500); }
}
