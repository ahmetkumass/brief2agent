"""The builder: reads a bank's brief (a folder of documents or brief files) and creates a Freya phone agent from it.

    python3 builder/build.py <case_folder | brief files...> [mock_url] [--slot NAME] [--practice A|B]

1. builder/ingest.py turns every document (md, docx, xlsx, pdf, json...) into text: work/<slot>/corpus.md
2. Claude (Claude Agent SDK, skills in .claude/skills) extracts the rules, writes the workflow, saves it on Freya,
   builds and deploys the bank mock when the folder asks for one, tests the agent and fixes what fails.
3. The workflow is exported to submissions/<slot>.workflow.json.

Every run writes a plain-text trace to traces/<slot>-<start>.log (start/end, each model call with model and purpose,
what was created on Freya, self-test results) and the raw message stream to traces/<slot>-<start>.jsonl.
Needs FREYA_API_KEY, FREYA_BANK_TEAM_KEY and ANTHROPIC_API_KEY (or a Claude login).
"""
import argparse, asyncio, dataclasses, json, os, pathlib, re, sys, time

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "builder"))
from ingest import ingest
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolUseBlock, ToolResultBlock, UserMessage, query

BUDGET_MIN = 28          # the rules allow 30 minutes per build, tests included
SECRETS = [os.environ.get(k, "") for k in ("FREYA_API_KEY", "FREYA_BANK_TEAM_KEY", "ANTHROPIC_API_KEY", "CLOUDFLARE_API_TOKEN")]


def redact(s):
    s = str(s)
    for k in SECRETS:
        if k and len(k) > 8: s = s.replace(k, "<redacted>")
    return re.sub(r"(fak_|sk-ant-)[A-Za-z0-9_\-]{8,}", r"\1<redacted>", s)


class Trace:
    def __init__(self, slot):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        (KIT / "traces").mkdir(exist_ok=True)
        self.log = open(KIT / "traces" / f"{slot}-{stamp}.log", "w")
        self.raw = open(KIT / "traces" / f"{slot}-{stamp}.jsonl", "w")
        self.path = self.log.name

    def line(self, msg):
        t = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        s = redact(f"[{t}] {msg}")
        print(s, flush=True); self.log.write(s + "\n"); self.log.flush()

    def raw_msg(self, m):
        self.raw.write(redact(json.dumps({"at": time.time(), "type": type(m).__name__, **dataclasses.asdict(m)}, default=str)) + "\n"); self.raw.flush()


def purpose(block_text, tools):
    if tools: return "tool use: " + "; ".join(tools)[:200]
    return ("reasoning/answer: " + " ".join(block_text.split()))[:200]


async def run(args):
    t0 = time.time()
    if not os.environ.get("BUILDER_USE_API_KEY"):      # use the Claude login of this machine, not an API key
        os.environ.pop("ANTHROPIC_API_KEY", None)
    inputs = [pathlib.Path(p).resolve() for p in args.inputs]
    slot = args.slot or (inputs[0].name if inputs[0].is_dir() else "-".join(p.stem for p in inputs))
    slot = re.sub(r"[^\w-]+", "-", slot).strip("-").lower() or "brief"
    tr = Trace(slot)
    tr.line(f"BUILD START slot={slot} inputs={[str(p) for p in inputs]} mock_url={args.mock_url or '-'} practice={args.practice or '-'}")

    work = KIT / "work" / slot
    idx = ingest([str(p) for p in inputs], work)
    tr.line(f"INGEST {len(idx)} files -> {work / 'corpus.md'}")
    for r in idx: tr.line(f"  file {r['file']} ({r['chars']} chars)")

    model = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")
    deadline = time.strftime("%H:%M", time.localtime(t0 + BUDGET_MIN * 60))
    prompt = f"""Build a Freya phone agent for this bank brief. Use the build-phone-agent skill and follow it exactly.

slot: {slot}
brief documents (converted to text): {work / 'corpus.md'} (one file per section; originals listed in {work / 'index.json'})
original inputs: {', '.join(str(p) for p in inputs)}
mock_url: {args.mock_url or '(none given)'}
practice set: {args.practice or '(none: this is not a practice brief, use the self-test path of the skill)'}
time budget: you must be completely finished by {deadline} local time ({BUDGET_MIN} minutes from now). Check the clock with `date` before every test.

When finished, print one final line: RESULT workflow_id=<id> agent_id=<id> nodes=<n> tools=<n> selftest=<summary>"""
    tr.line(f"MODEL CALL model={model} purpose=builder agent session (reads brief, writes workflow, saves on Freya, tests, fixes)")

    options = ClaudeAgentOptions(
        cwd=KIT, model=model,
        skills=["build-phone-agent", "bank-mock"],
        setting_sources=["project"],
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Skill"],
        permission_mode="dontAsk", max_turns=250,
        env={"BASH_DEFAULT_TIMEOUT_MS": "900000", "BASH_MAX_TIMEOUT_MS": "1200000", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"},
    )
    result_line, turns = "", 0
    async for m in query(prompt=prompt, options=options):
        tr.raw_msg(m)
        if isinstance(m, AssistantMessage):
            turns += 1
            texts = [b.text for b in m.content if isinstance(b, TextBlock)]
            tools = [f"{b.name}({redact(json.dumps(b.input, ensure_ascii=False))[:140]})" for b in m.content if isinstance(b, ToolUseBlock)]
            tr.line(f"MODEL CALL #{turns} model={getattr(m, 'model', model)} purpose={purpose(' '.join(texts), tools)}")
            for t in texts:
                if "RESULT " in t: result_line = t[t.index("RESULT "):].splitlines()[0]
                if re.search(r"\d+\s*/\s*\d+ passed", t) or "selftest" in t.lower(): tr.line(f"  SELFTEST {' '.join(t.split())[:400]}")
        elif isinstance(m, UserMessage) and isinstance(m.content, list):
            for b in m.content:
                if isinstance(b, ToolResultBlock):
                    out = b.content if isinstance(b.content, str) else json.dumps(b.content, default=str)
                    for ln in str(out).splitlines():
                        if re.match(r"^(PASS|FAIL) |^\d+ / \d+ passed|workflow_id|agent_id|DEPLOYED|SMOKE", ln.strip()): tr.line(f"  TOOL OUTPUT {ln.strip()[:300]}")
        elif isinstance(m, ResultMessage):
            tr.line(f"BUILDER SESSION DONE turns={m.num_turns} duration={m.duration_ms / 1000:.0f}s cost=${m.total_cost_usd or 0:.2f}")

    # what was created on Freya
    import freya
    state = json.loads((KIT / ".freya-agents.json").read_text()) if (KIT / ".freya-agents.json").exists() else {}
    if slot in state:
        wf = state[slot]
        (KIT / "submissions").mkdir(exist_ok=True)
        out = freya.export_workflow(wf["workflow_id"], str(KIT / "submissions" / f"{slot}.workflow.json"))
        w = json.load(open(out))["workflow"]
        nodes = len(w.get("nodes", {})) + len(w.get("global_nodes", {}) or {})
        tools = sum(len(n.get("tools") or []) for n in w.get("nodes", {}).values())
        tr.line(f"CREATED ON FREYA workflow_id={wf['workflow_id']} agent_id={wf['agent_id']} version={wf.get('version', 1)} nodes={nodes} tools={tools} exported={out}")
    else:
        tr.line(f"WARNING no workflow saved for slot {slot}")
    if result_line: tr.line(result_line)
    tr.line(f"BUILD END elapsed={(time.time() - t0) / 60:.1f} min trace={tr.path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="a case folder, or brief files")
    ap.add_argument("--slot"); ap.add_argument("--practice", choices=["A", "B"])
    a = ap.parse_args()
    # a trailing http(s) argument is the mock url
    a.mock_url = next((x for x in a.inputs if x.startswith("http")), None)
    a.inputs = [x for x in a.inputs if not x.startswith("http")]
    asyncio.run(run(a))
