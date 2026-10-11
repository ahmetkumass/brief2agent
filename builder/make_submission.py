"""Write submission.json after a final build.

    python3 builder/make_submission.py <slot> <mock_url> --team NAME --members "Name <email>, Name <email>"

Fills repo and commit from git, the workflow export and the newest trace of that slot.
"""
import argparse, glob, json, os, pathlib, subprocess

KIT = pathlib.Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("slot"); ap.add_argument("mock_url")
ap.add_argument("--team", required=True); ap.add_argument("--members", required=True)
ap.add_argument("--case", default="{case_folder}")
a = ap.parse_args()

git = lambda *c: subprocess.run(["git", *c], cwd=KIT, capture_output=True, text=True).stdout.strip()
repo = git("remote", "get-url", "origin").removesuffix(".git")
traces = sorted(glob.glob(str(KIT / "traces" / f"{a.slot}-*.log")), key=os.path.getmtime)
final_log = KIT / "traces" / "final.log"
sub = {
    "team": a.team,
    "members": [{"name": m.split("<")[0].strip(), "email": m.split("<")[1].rstrip(">").strip() if "<" in m else ""}
                for m in a.members.split(",") if m.strip()],
    "repo": repo,
    "commit": git("rev-parse", "HEAD"),
    "run_command": "python3 builder/build.py {case_folder} {mock_url} --slot final --deploy-mock",
    "workflow": f"submissions/{a.slot}.workflow.json",
    "trace": "traces/final.log" if final_log.exists() else (os.path.relpath(traces[-1], KIT) if traces else ""),
    "mock_url": a.mock_url,
}
missing = [k for k in ("workflow", "trace") if not sub[k] or not (KIT / sub[k]).exists()]
(KIT / "submission.json").write_text(json.dumps(sub, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(sub, indent=2, ensure_ascii=False))
if missing: print("WARNING missing files:", missing)
if git("status", "--porcelain"): print("NOTE: uncommitted changes; commit and push, then run this again so 'commit' matches.")
