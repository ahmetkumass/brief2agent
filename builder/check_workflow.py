"""Static checks on a workflow JSON before saving it. Prints problems; exit 1 if any.

    python3 builder/check_workflow.py out/<slot>.workflow.json
"""
import json, sys

def walk(x, path=""):
    if x is None: yield path
    elif isinstance(x, dict):
        for k, v in x.items(): yield from walk(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from walk(v, f"{path}[{i}]")

def main(p):
    w = json.load(open(p)); w = w.get("workflow", w); bad = []
    nodes = dict(w.get("nodes", {})); nodes.update(w.get("global_nodes") or {})
    if "agent_config" in w: bad.append("remove agent_config")
    if w.get("initial_node") not in w.get("nodes", {}): bad.append("initial_node missing")
    warn = [f"null value at {n} (the API may reject it; use \"\" or omit)" for n in walk(w)]
    for k, n in nodes.items():
        t = n.get("node_type")
        targets = [tr.get("target_node") for tr in n.get("transitions", [])]
        for tg in targets + [n.get("passthrough_default_transition"), n.get("max_turn_transition")]:
            if tg and tg != "__previous__" and tg not in nodes: bad.append(f"{k}: target {tg} does not exist")
        if n.get("passthrough") and not any((tr.get("condition") or {}).get("operator") == "always" for tr in n.get("transitions", [])):
            bad.append(f"{k}: passthrough node without an always transition")
        if t == "conversation" and n.get("pre_actions"): bad.append(f"{k}: pre_actions on a conversation node are dropped")
        if t in ("api_request", "code") and n.get("tools"): bad.append(f"{k}: tools on a {t} node are dropped")
        if t == "end_call" and not n.get("terminal"): bad.append(f"{k}: end_call without terminal")
        for a in n.get("pre_actions", []) or []:
            if "response_mapping" in a: bad.append(f"{k}: response_mapping inside a pre_action is ignored; put it on the node")
            code = ((a.get("function") or {}).get("parameters") or {}).get("properties", {}).get("code", {}).get("default", "")
            if "{{" in code or "}}" in code: bad.append(f"{k}: '{{{{' or '}}}}' inside python code")
            if code:
                try: compile(code, k, "exec")
                except SyntaxError as e: bad.append(f"{k}: python syntax error: {e}")
        for tool in n.get("tools", []) or []:
            f = tool.get("function", {}); name = f.get("name")
            for hk in ("pre_process_code", "post_process_code"):
                c = tool.get(hk) or ""
                if c:
                    try: compile(c, f"{k}.{name}.{hk}", "exec")
                    except SyntaxError as e: bad.append(f"{k}.{name}: {hk} syntax error: {e}")
            props = (f.get("parameters") or {}).get("properties", {})
            if f.get("handler") == "__function__:api_call":
                if "default" not in props.get("url", {}): bad.append(f"{k}.{name}: url has no default")
                if any("const" in v for v in walk_props(props)): bad.append(f"{k}.{name}: uses const (never sent)")
        for e in n.get("extraction_schema", []) or []:
            if "min_confidence" not in e: bad.append(f"{k}: extraction {e.get('name')} has no min_confidence")
    reach = {w.get("initial_node")}; todo = list(reach)
    while todo:
        n = nodes.get(todo.pop(), {})
        for tr in n.get("transitions", []):
            tg = tr.get("target_node")
            if tg in nodes and tg not in reach: reach.add(tg); todo.append(tg)
    for k in w.get("nodes", {}):
        if k not in reach: bad.append(f"{k}: not reachable from initial_node")
    if not any(n.get("node_type") == "end_call" for n in nodes.values()): warn.append("no end_call node")
    tools = sorted({t["function"]["name"] for n in nodes.values() for t in n.get("tools", []) or []} | {a["function"]["name"] for n in nodes.values() for a in n.get("pre_actions", []) or []})
    print("tools used:", ", ".join(tools)); print("nodes:", len(nodes))
    for b in warn: print("WARNING:", b)
    for b in bad: print("PROBLEM:", b)
    print("OK" if not bad else f"{len(bad)} problem(s)"); return 1 if bad else 0

def walk_props(props):
    for v in props.values():
        if isinstance(v, dict):
            yield v
            yield from walk_props(v.get("properties", {}))

if __name__ == "__main__": sys.exit(main(sys.argv[1]))
