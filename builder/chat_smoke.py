"""Talk to the saved workflow of a slot turn by turn (no simulation queue).

    python3 builder/chat_smoke.py <slot> [--script "turn1|turn2|..."] [--vars '{"customer_id": "..."}']

Uses the workflow's test_variables unless --vars is given. Prints each agent reply.
"""
import argparse, json, pathlib, sys
KIT = pathlib.Path(__file__).resolve().parent.parent; sys.path.insert(0, str(KIT))
import freya

ap = argparse.ArgumentParser(); ap.add_argument("slot"); ap.add_argument("--script", default="Hello?|Yes, speaking."); ap.add_argument("--vars")
a = ap.parse_args()
wf = json.loads((KIT / ".freya-agents.json").read_text())[a.slot]["workflow_id"]
w = freya.api("GET", f"/api/v2/workflow/{wf}", workspaceId=freya.workspace_id())["workflow"]["workflow"]
v = json.loads(a.vars) if a.vars else (w.get("test_variables") or {})
call = None
for turn in a.script.split("|"):
    body = {"workflowId": wf, "message": turn, "customerVariables": v}
    if call: body["callId"] = call
    try: r = freya.api("POST", "/api/v2/chat/message", body)
    except Exception as e: print("ERROR", str(e)[:500]); break
    call = r.get("callId") or call
    print("CUSTOMER:", turn); print("AGENT:   ", r.get("response"))
if call:
    try: freya.api("POST", "/api/v2/chat/end", {"callId": call})
    except Exception: pass
    print("call_id:", call)
