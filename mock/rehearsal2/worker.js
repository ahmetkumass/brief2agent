import DATA from "./customers.json";
const BASE = "/api/v1";
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json" } });
const customer = id => DATA.customers.find(c => c.customer_id === id);
const fresh = () => ({ verified: {}, wrong: 0, promises: [], notes: [], callbacks: [], transfers: [], outcome: null, reason: null, closed: false, fails: 0, calls: [] });
async function load(env, id) { const r = await env.LEDGER.get("l:" + id); return r ? JSON.parse(r) : fresh(); }
function normDate(s) {
  const m = String(s || "").trim().match(/^(\d{4})-(\d{2})-(\d{2})$/); if (!m) return null;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])); return d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3] ? m[0] : null;
}
const HOL = ["2026-10-29", "2027-01-01"];
const bizday = s => { const d = new Date(s + "T00:00:00Z").getUTCDay(); return d !== 0 && d !== 6 && !HOL.includes(s); };
const idOk = (c, l) => Object.keys(c.identity).every(f => l.verified[f]);
const TOOLS = {
  async verify_identity(c, b, l) {
    const f = b.field; if (!(f in c.identity)) return { ok: false, error: "invalid_field" };
    const a = String(b.answer ?? "").trim();
    if (!(f === "birth_year" ? /^\d{4}$/ : /^\d{5}$/).test(a)) return { ok: false, error: "invalid_format" };
    if (l.wrong >= 3) return { ok: false, error: "identity_locked", verified: false, attempts_remaining: 0, identity_complete: false };
    const good = a === c.identity[f]; if (good) l.verified[f] = true; else l.wrong++;
    return { ok: true, verified: good, attempts_remaining: Math.max(0, 3 - l.wrong), identity_complete: idOk(c, l) };
  },
  async get_account(c, b, l) { if (!idOk(c, l)) return { ok: false, error: "identity_not_verified" }; return { ok: true, products: c.products }; },
  async create_promise(c, b, l) {
    if (!idOk(c, l)) return { ok: false, error: "identity_not_verified" };
    if (c.fail_create_promise && l.fails < c.fail_create_promise) { l.fails++; return [500, { ok: false, error: "service_unavailable" }]; }
    const p = c.products.find(x => x.product_id === b.product_id); if (!p) return { ok: false, error: "unknown_product" };
    const d = normDate(b.payment_date); if (!d || !bizday(d)) return { ok: false, error: "invalid_date" };
    const amt = Number(b.amount); if (!(amt > 0) || amt < p.minimum_payment) return { ok: false, error: "below_minimum" };
    if (amt > p.past_due) return { ok: false, error: "above_past_due" };
    const pr = { promise_id: "pr_" + (l.promises.length + 1), product_id: p.product_id, amount: amt, date: d };
    l.promises.push(pr); return { ok: true, promise_id: pr.promise_id };
  },
  async add_note(c, b, l) { if (!b.text) return { ok: false, error: "missing_text" }; l.notes.push({ product_id: b.product_id || null, reason: b.text }); return { ok: true }; },
  async schedule_callback(c, b, l) {
    const d = normDate(b.callback_date), t = String(b.callback_time || "");
    if (!d || !/^\d{2}:\d{2}$/.test(t)) return { ok: false, error: "invalid_format" };
    if (t < "09:30" || t > "18:30" || !bizday(d)) return { ok: false, error: "outside_window" };
    l.callbacks.push({ date: d, time: t }); return { ok: true };
  },
  async transfer_to_agent(c, b, l) { if (!["hardship", "dispute"].includes(b.reason)) return { ok: false, error: "invalid_reason" }; l.transfers.push({ queue: b.reason }); return { ok: true }; },
  async close_call(c, b, l) {
    if (!["promise", "paid", "transferred", "no_promise", "not_verified", "not_reached"].includes(b.outcome)) return { ok: false, error: "invalid_outcome" };
    if (!["promise", "paid"].includes(b.outcome) && !b.reason) return { ok: false, error: "reason_required" };
    l.outcome = b.outcome; l.reason = b.reason || null; l.closed = true; return { ok: true };
  },
};
export class Bank {
  constructor(state) { this.s = state.storage; }
  async fetch(req) { const s = this.s; return handle(req, { LEDGER: { get: k => s.get(k), put: (k, v) => s.put(k, v), delete: k => s.delete(k) } }); }
}
export default { async fetch(req, env) { return env.BANK.get(env.BANK.idFromName("bank")).fetch(req); } };
const _h = {
  async fetch(req, env) {
    try {
      let path = new URL(req.url).pathname.replace(/\/+$/, "");
      if (path === "" || path === BASE + "/health") return json({ ok: true });
      const pm = path.match(/^(?:\/api)?\/v1\/practice\/(.*)$/);
      if (pm) {
        if (req.method === "GET" && pm[1].startsWith("ledger/")) {
          const id = pm[1].slice(7); if (!customer(id)) return json({ ok: false, error: "unknown customer" }, 404);
          const l = await load(env, id); return json({ ok: true, outcome: l.outcome, reason: l.reason, promises: l.promises, notes: l.notes, callbacks: l.callbacks, transfers: l.transfers, calls: l.calls });
        }
        if (req.method === "POST" && pm[1] === "sessions") {
          const b = await req.json().catch(() => ({})); const c = DATA.customers.find(x => x.case === b.case || x.customer_id === b.case);
          if (!c) return json({ ok: false, error: "unknown case" }, 404);
          await env.LEDGER.delete("l:" + c.customer_id); return json({ ok: true, variables: c.variables });
        }
        return json({ ok: false, error: "not found" }, 404);
      }
      const tool = path.startsWith(BASE + "/") ? path.slice(BASE.length + 1) : "";
      if (req.method !== "POST" || !TOOLS[tool]) return json({ ok: false, error: "not found" }, 404);
      const b = await req.json().catch(() => null);
      if (!b || typeof b !== "object") return json({ ok: false, error: "invalid_json" }, 400);
      const c = customer(b.customer_id); if (!c) return json({ ok: false, error: "unknown_customer" });
      const l = await load(env, c.customer_id);
      let out, status = 200;
      if (l.closed) out = { ok: false, error: "call_closed" };
      else { out = await TOOLS[tool](c, b, l); if (Array.isArray(out)) [status, out] = out; }
      const { customer_id, ...args } = b;
      l.calls.push({ tool, args, status, result: out });
      await env.LEDGER.put("l:" + c.customer_id, JSON.stringify(l));
      return json(out, status);
    } catch (e) { return json({ ok: false, error: "internal_error" }, 500); }
  },
};

async function handle(req, env) { return _h.fetch(req, env); }
