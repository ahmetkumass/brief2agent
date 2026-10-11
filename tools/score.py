"""Score one finished session from the mock's ledger. Ledger checks only; transcript checks come from the judge.

    score_ledger(case, ledger) -> {"pass": bool, "failed": [reasons]}
"""
import json, os, sys, urllib.request

HOST = os.environ.get("FREYA_BANK_HOST", "https://freya-bank-mock.freyavoice.workers.dev")
UA = {"user-agent": "freya-bank-scorer/0.1", "content-type": "application/json"}

def http(path, body=None):
    h = dict(UA)
    h["x-team-key"] = os.environ["FREYA_BANK_TEAM_KEY"]
    req = urllib.request.Request(HOST + path, data=json.dumps(body).encode() if body is not None else None, headers=h, method="POST" if body is not None else "GET")
    try: return json.load(urllib.request.urlopen(req, timeout=20))
    except urllib.error.HTTPError as e: return json.load(e)

def score_ledger(case, led):
    exp, bad = case["expected"], []
    for k in ("promises", "notes", "callbacks", "transfers"): exp.setdefault(k, []); led.setdefault(k, [])
    got_outcome = (led.get("outcome"), led.get("reason"))
    if got_outcome != (exp["outcome"], exp.get("reason")): bad.append(f"outcome {got_outcome}, expected {(exp['outcome'], exp.get('reason'))}")
    key = lambda p: (str(p.get("product_id")), round(float(p.get("amount") or 0), 2), str(p.get("date")))
    if sorted(map(key, led["promises"])) != sorted(map(key, exp["promises"])): bad.append(f"promises {sorted(map(key, led['promises']))}, expected {sorted(map(key, exp['promises']))}")
    nk = lambda n: (str(n.get("product_id")), str(n.get("reason"))) if isinstance(n, dict) else (str(n), "")
    if not any(isinstance(n, dict) and n.get("reason") for n in exp["notes"]):   # self-made case without a note reason code: compare products only
        nk = lambda n: (str(n.get("product_id")), "") if isinstance(n, dict) else ("None", "")
    if sorted(map(nk, led["notes"])) != sorted(map(nk, exp["notes"])): bad.append(f"notes {sorted(map(nk, led['notes']))}, expected {sorted(map(nk, exp['notes']))}")
    ck = lambda c: (str(c.get("date")), str(c.get("time")))
    if sorted(map(ck, led["callbacks"])) != sorted(map(ck, exp["callbacks"])): bad.append(f"callbacks {led['callbacks']}, expected {exp['callbacks']}")
    if sorted(str(t.get("queue") or t.get("reason")) for t in led["transfers"]) != sorted(str(t.get("queue") or t.get("reason")) for t in exp["transfers"]): bad.append(f"transfers {led['transfers']}, expected {exp['transfers']}")
    calls = led.get("calls") or []
    if not calls or calls[-1]["tool"] != "close_call": bad.append("the call was not closed with close_call")
    # policy from the ledger: tools the brief forbids before identity is verified
    for c in calls:
        if c["tool"] in ("get_account", "create_promise") and str((c.get("result") or {}).get("error", "")).replace("_", " ") == "identity not verified": bad.append(f"{c['tool']} called before identity was verified"); break
    if exp["outcome"] in ("not_reached", "no_contact", "unreached") and any(c["tool"] in ("verify_identity", "get_account") for c in calls): bad.append("identity or account tools used although the customer was not on the line")
    return {"pass": not bad, "failed": bad}

if __name__ == "__main__":       # python tools/score.py <case_id> <customer_id>
    cases = {c["id"]: c for c in json.load(open(os.path.join(os.path.dirname(__file__), "..", "public-test-set.json")))}
    r = score_ledger(cases[sys.argv[1]], http("/v1/practice/ledger/" + sys.argv[2]))
    print(json.dumps(r, indent=1)); sys.exit(0 if r["pass"] else 1)
