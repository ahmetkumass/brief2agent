import DATA from "./customers.json";
const ERR = {
  "cards.list": [404, "FB_IVR_CHANNEL_102", "WARNING", "Müşteriye ait geçerli kart bilgisi bulunamadı."],
  "cards.balance": [404, "FB_IVR_CHANNEL_120", "WARNING", "Kart bakiye servisi hatası: kart bulunamadı"],
  "statement.week.get": [404, "FB_IVR_CHANNEL_121", "WARNING", "Kart bulunamadı"],
  "statement.pdf.send": [404, "FB_IVR_CHANNEL_107", "WARNING", "Pdf dokümanı bulunamadı"],
};
function errBody(http, code, type, msg, cause) {
  const g = crypto.randomUUID().replace(/-/g, "");
  return [http, { result: { guid: g, returnCode: code, messageText: msg, code, message: msg, type, details: { guid: g, rootCause: cause, errorOrigin: "ivr-gateway-test:ivr-channel-v0" } } }];
}
function notFound(svc) {
  const e = ERR[svc];
  if (e) return errBody(e[0], e[1], e[2], e[3], "NotFoundException");
  return errBody(400, "INVALID_ARGUMENTS_ERROR", "ERROR", "invalid arguments", "ValidationException");
}
const json = (s, b) => new Response(JSON.stringify(b), { status: s, headers: { "content-type": "application/json; charset=utf-8" } });
const S = (v) => (v === undefined || v === null ? "" : String(v).trim());
export default {
  async fetch(req) {
    try {
      const url = new URL(req.url);
      if (url.pathname === "/health") return json(200, { ok: true });
      const m = url.pathname.match(/^\/voice\/v1\/([a-z.]+)$/i);
      if (!m || req.method !== "POST") return json(404, { error: "not found" });
      const svc = m[1];
      const known = ["cards.list","cards.balance","statement.week.get","statement.week.decide","statement.week.change","contact.email.get","statement.pdf.send"];
      if (!known.includes(svc)) return json(404, { error: "not found" });
      let body = {};
      try { body = await req.json(); } catch (e) { const [s,b] = errBody(400,"INVALID_ARGUMENTS_ERROR","ERROR","invalid body","ValidationException"); return json(s,b); }
      const d = (body && body.data) || {};
      const cust = S(d.customerNo), card = S(d.cardNumber), week = S(d.newStatementWeek);
      let entry = null;
      if (["cards.list","contact.email.get","statement.pdf.send"].includes(svc)) {
        if (!cust) { const [s,b]=errBody(400,"INVALID_ARGUMENTS_ERROR","ERROR","customer number cannot be empty","ValidationException"); return json(s,b); }
        if (svc === "contact.email.get" && !S(d.intAddressInfoType)) { const [s,b]=errBody(400,"INVALID_ARGUMENTS_ERROR","ERROR","intAddressInfoType cannot be empty","ValidationException"); return json(s,b); }
        const c = DATA.customers.find(x => S(x.customerNo) === cust);
        entry = c && c.services[svc];
      } else {
        if (!card) { const [s,b]=errBody(400,"INVALID_ARGUMENTS_ERROR","ERROR","card number cannot be empty","ValidationException"); return json(s,b); }
        for (const c of DATA.customers) {
          const t = c.services[svc];
          if (t && t[card]) { entry = t[card]; break; }
        }
        if (entry && (svc === "statement.week.decide" || svc === "statement.week.change")) {
          if (!week) { const [s,b]=errBody(400,"INVALID_ARGUMENTS_ERROR","ERROR","newStatementWeek cannot be empty","ValidationException"); return json(s,b); }
          entry = entry[week] || null;
        }
      }
      if (!entry || entry.http === undefined) { const [s,b] = notFound(svc); return json(s,b); }
      if (entry.delaySeconds) await new Promise(r => setTimeout(r, entry.delaySeconds * 1000));
      return json(entry.http, entry.response);
    } catch (e) {
      const [s,b] = errBody(500,"FBE00099","ERROR","Teknik hata: ABORTED: ","TechnicalError"); return json(s,b);
    }
  }
};
