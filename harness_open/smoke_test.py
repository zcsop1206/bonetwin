"""Mocked end-to-end smoke test of the OPEN run (fake agents, mock tools, no API calls, no PreForm, no Brev).

    python smoke_test.py --root <harness_open/smoke/<name>> [--timeout 600]

Use a root under harness_open/smoke/ (the evaluator guard denies tool calls naming the real run folders). Launches
replicate 1 (19 fake sessions) + the mock control, lets the real scheduler run and collect, then checks:
briefs identical and minimal (goal verbatim, EVAL_SPEC linked), every arm's submission collected with hashes under
the pre-registered rules (best_of_n by the harness-logged pre-check), the meter (notices shown once, planner members
cannot write the deliverables, brev/wsl and PreForm print refused, other runs blocked), the usage-window pause,
metrics (KB growth, entropy, leaning lift, centralization) with no board or KB text, manipulation checks.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import load_json, read_jsonl, run_dir  # noqa: E402
import briefs  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), str(detail)[:300]))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(detail)[:200]})" if detail else ""))


def py(args, env=None, cwd=None, inp=None, timeout=600):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, env=env, cwd=cwd or str(HERE),
                          input=inp, timeout=timeout)


def agent_env(adir):
    g = load_json(Path(adir) / "genome.json")
    env = {k: v for k, v in os.environ.items() if not k.startswith("BT_") or k == "BT_MOCK_TOOLS"}
    env.update(BT_AGENT=g["id"], BT_AGENT_DIR=str(adir), BT_BOARD=g["board"] if g.get("board_shared") else "")
    return env


def hook(adir, tool, tin):
    r = py([str(HERE / "meter.py"), "hook"], env=agent_env(adir), inp=json.dumps({"tool_name": tool, "tool_input": tin}))
    return r.returncode, r.stderr.strip()[:1500]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if "smoke" not in root.parts:
        sys.exit("use a root under harness_open/smoke/")
    env = dict(os.environ, BT_MOCK_TOOLS="1", BT_MOCK_LIMIT_ONCE="1")
    t0 = time.time()
    r = py([str(HERE / "launch_open_run.py"), "--mock", "--mock-tools", "--root", str(root), "--batches", "1",
            "--wall-cap-min", "10", "--min-free-ram", "0.5"], env=env, timeout=900)
    check("launcher (mock agents, mock tools, replicate 1) exits cleanly", r.returncode == 0, r.stdout[-300:] + r.stderr[-400:])
    if r.returncode:
        return finish(root)
    plan = load_json(run_dir(root) / "run_manifest.json")
    check("brief bodies identical, hashes logged", plan["brief_check"]["ok"], plan["brief_check"]["common_sha256"][:12])
    check("launch health check passed (one call per tool)", plan.get("health"), plan.get("tools_at_launch"))
    log = run_dir(root) / "scheduler.log"
    while time.time() - t0 < a.timeout:
        if log.exists() and "scheduler exits" in log.read_text(encoding="utf-8"):
            break
        time.sleep(3)
    txt = log.read_text(encoding="utf-8") if log.exists() else ""
    check("scheduler collected and exited", "scheduler exits" in txt, f"{time.time() - t0:.0f}s")
    sj = read_jsonl(root / "metrics" / "scheduler.jsonl")
    gj = load_json(root / "metrics" / "groups.json") or {}
    check("scheduler.jsonl logs counts, RAM and CPU only", sj and all(set(x) <= {"utc", "running", "pending_units",
          "started_units", "collected_units", "free_ram_gb", "cpu_pct_1min", "started_now"} for x in sj), len(sj))
    check("groups started whole (groups.json)", {"r1/collective", "r1/planner"} <= set(gj), list(gj))
    nd = load_json(run_dir(root) / "r1" / "single" / "agents" / "s1" / "notices_due.json") or []
    check("per-session notices at cap-30 and cap-10", len(nd) == 2 and "30 minutes" in nd[0]["text"], len(nd))

    g0 = next(iter(run_dir(root).glob("r1/collective/agents/c1/BRIEF.md")))
    brief = g0.read_text(encoding="utf-8")
    cfg = load_json(HERE / "config.json")
    check("brief: goal verbatim, deliverables, judging paragraph, EVAL_SPEC link, STL/axes line, 2-hour window",
          f'"{cfg["goal"]}"' in brief and "implant.form" in brief and "EVAL_SPEC_v1.md" in brief and
          "cranial-caudal" in brief and "implant.stl or implant.3mf" in brief and "90-minute session window" in brief)
    check("brief: four leaning lines, arm rule", brief.count("- leaning, ") == 4 and "your run's rule:" in brief)
    subs = load_json(root / "metrics" / "submissions.json") or {}
    rows = {f"{x['run_id']}/{x['arm']}": x for x in subs.get("rows", [])}
    for k in ("r1/single", "r1/best_of_n", "r1/collective", "r1/planner", "control/control/gibson_ashby_rigid10k"):
        check(f"submission collected: {k}", rows.get(k, {}).get("submission"), rows.get(k))
    check("best_of_n picked by the judge pre-check run at collection", "pre-check H" in str(rows.get("r1/best_of_n", {}).get("why")),
          rows.get("r1/best_of_n"))
    r = py([str(HERE / "collect.py"), "--root", str(root)])
    check("collection runs once (second run refused)", r.returncode != 0, (r.stderr + r.stdout).strip()[-60:])
    s1 = load_json(run_dir(root) / "r1" / "single" / "agents" / "s1" / "status.json") or {}
    check("usage-window block logged, paused, resumed, finished", s1.get("state") == "done" and
          read_jsonl(run_dir(root) / "usage_events.jsonl"), s1.get("state"))

    # meter: notices, planner deliverables, brev/wsl, other runs
    pub = root / "public"
    (pub / "notices.json").write_text(json.dumps([{"id": "t1", "text": "NOTICE test: 60 minutes to the deadline."}]))
    c2 = run_dir(root) / "r1" / "collective" / "agents" / "c2"
    own = {"file_path": str(c2 / "x.md")}
    code1, err1 = hook(c2, "Read", own)
    code2, _ = hook(c2, "Read", own)
    check("notice shown once (held call), then calls proceed", code1 == 2 and "NOTICE test" in err1 and code2 == 0,
          err1[:80])
    p3 = run_dir(root) / "r1" / "planner" / "agents" / "p3"
    p1 = run_dir(root) / "r1" / "planner" / "agents" / "p1"
    dl = run_dir(root) / "r1" / "planner" / "deliverables" / "report.md"
    for adir in (p3, p1):  # consume the test notice first
        hook(adir, "Read", {"file_path": str(adir / "x")})
    c_m, _ = hook(p3, "Write", {"file_path": str(dl), "content": "x"})
    c_l, _ = hook(p1, "Write", {"file_path": str(dl), "content": "x"})
    check("planner: member cannot write the deliverables, lead can", c_m == 2 and c_l == 0, (c_m, c_l))
    c_c, _ = hook(c2, "Write", {"file_path": str(run_dir(root) / "r1" / "collective" / "deliverables" / "r.md"),
                                "content": "x"})
    c_k, _ = hook(c2, "Write", {"file_path": str(run_dir(root) / "r1" / "collective" / "kb" / "n.md"), "content": "x"})
    check("collective peer can write the shared deliverables and KB", c_c == 0 and c_k == 0, (c_c, c_k))
    for label, tool, tin in [("brev direct", "Bash", {"command": "brev ls"}),
                             ("wsl direct", "Bash", {"command": "wsl -e nvidia-smi"}),
                             ("another arm", "Read", {"file_path": str(run_dir(root) / "r1" / "best_of_n" / "agents"
                                                                   / "b1" / "kb" / "x.md")}),
                             ("sealed_private", "Read", {"file_path": r"C:\Users\someone\sealed_private\k.txt"}),
                             ("judge internals", "Read", {"file_path": str(HERE.parent / "sim" / "tests" / "x.json")}),
                             ("PreForm port direct", "Bash", {"command": f"curl http://127.0.0.1:{briefs.PREFORM_PORT}/"})]:
        code, err = hook(c2, tool, tin)
        check(f"meter blocks {label}", code == 2, err[:80])
    r = py([str(HERE / "tools" / "bt_tool.py"), "preform_api", "print_job"], env=agent_env(c2), cwd=str(c2))
    check("PreForm print endpoint refused", r.returncode != 0 and "refused" in r.stderr, r.stderr.strip()[-80:])

    # metrics (aggregate only)
    md = root / "metrics"
    pm = load_json(md / "process_metrics.json") or {}
    kbg = read_jsonl(md / "kb_growth.jsonl")
    check("KB growth snapshots", kbg and any(x["n_files"] > 0 for x in kbg), len(kbg))
    ag = pm.get("agents", {})
    check("tool-usage entropy and leaning lift per agent", ag and all("entropy_bits" in v for v in ag.values()) and
          any("leaning_lift" in v for v in ag.values()), len(ag))
    arms = pm.get("arms", {})
    gr = (arms.get("r1/collective") or {}).get("graph") or {}
    check("centralization in metrics (mentions, typed links, directives)",
          gr.get("edges_by_type", {}).get("mention", 0) > 0 and gr.get("edges_by_type", {}).get("extends", 0) > 0
          and gr.get("n_directive_posts", 0) >= 3, gr.get("edges_by_type"))
    blob = " ".join(f.read_text(encoding="utf-8", errors="ignore") for f in md.rglob("*") if f.is_file()
                    and f.suffix in (".json", ".jsonl", ".graphml"))
    check("metrics hold no board or KB text", "literature sweep" not in blob and "note 0" not in blob)
    summ = load_json(md / "manipulation_summary.json") or {}
    for row in summ.get("rows", []):
        check(f"manipulation: {row['arm']} {row['run_id']} passes", row["pass"], row["failed"])
    return finish(root)


def finish(root):
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / "smoke_result.json").write_text(json.dumps({"n": len(RESULTS), "failed": n_fail, "results": [
        {"check": n, "ok": ok, "detail": d} for n, ok, d in RESULTS]}, indent=2), encoding="utf-8")
    print(f"\n{len(RESULTS) - n_fail}/{len(RESULTS)} checks passed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
