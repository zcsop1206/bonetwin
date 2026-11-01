"""Process metrics for the open run (aggregate numbers only, never board or KB text) -> <root>/metrics/.

    python process_metrics.py --root R --snapshot     KB snapshot: metrics/kb_growth.jsonl (scheduler, every N min)
    python process_metrics.py --root R                full: metrics/process_metrics.json

KB growth: per knowledge base (shared per arm in collective/planner, per agent in single/best_of_n): file count,
bytes, cross-references (references in one KB file to another KB file's name).
Tool-usage entropy per agent: Shannon entropy (bits) of the agent's allowed tool calls over tool names.
Affinity vs actual use: share of an agent's calls in the tool family its 'tools' leaning names (config
affinity_tool_map), against that family's share across all agents (lift > 1 = leaning followed).
Idea lineage: design-artifact DAG (depth, syntheses, cross-agent derivations), typed board links, KB
cross-references, and report.md links into the KB that resolve.
"""
import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import append_jsonl, base_arm, load_config, load_json, read_jsonl, run_dir, utc_now, write_json  # noqa: E402

TEXT_EXT = {".md", ".txt", ".json", ".csv", ".py", ".yaml", ".yml", ".html", ".tex", ".bib"}
LINK = re.compile(r"\]\(([^)]+)\)")


def kb_stats(kb):
    kb = Path(kb)
    files = [f for f in kb.rglob("*") if f.is_file()] if kb.exists() else []
    names = {f.name for f in files}
    xrefs = 0
    for f in files:
        if f.suffix.lower() in TEXT_EXT and f.stat().st_size < 2_000_000:
            try:
                t = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            xrefs += sum(1 for n in names if n != f.name and n in t)
    return {"n_files": len(files), "bytes": sum(f.stat().st_size for f in files), "xrefs": xrefs}


def kbs_of(ad, manifest):
    if base_arm(manifest["arm"]) in ("collective", "planner"):
        return {"shared": Path(ad) / "kb"}
    return {g["id"]: Path(ad) / "agents" / g["id"] / "kb" for g in manifest["agents"]}


def arm_items(root):
    for f in sorted(run_dir(root).glob("*/*/arm.json")):
        yield f.parent.parent.name, f.parent.name, f.parent, load_json(f)


def snapshot(root, mdir):
    ts = utc_now()
    for run_id, arm, ad, m in arm_items(root):
        for who, kb in kbs_of(ad, m).items():
            append_jsonl(mdir / "kb_growth.jsonl", {"ts": ts, "run_id": run_id, "arm": arm, "kb": who, **kb_stats(kb)})


def entropy(counter):
    n = sum(counter.values())
    return -sum(c / n * math.log2(c / n) for c in counter.values() if c) if n else 0.0


def full(root, mdir, cfg):
    import centralization
    fam_of = {t: fam for fam, tools in cfg["affinity_tool_map"].items() for t in tools}
    agents, fam_totals = {}, Counter()
    for run_id, arm, ad, m in arm_items(root):
        for g in m["agents"]:
            calls = [r for r in read_jsonl(Path(ad) / "agents" / g["id"] / "tool_calls.jsonl")
                     if r.get("verdict") not in ("refused", "held_for_notice") and r.get("result") != "unavailable"]
            names = Counter((r.get("priced_as") or r.get("tool") or "?") for r in calls)
            fams = Counter(fam_of.get(n, "other") for n in names.elements())
            fam_totals.update(fams)
            agents[f"{run_id}/{arm}/{g['id']}"] = {"leaning": (g.get("leanings") or {}).get("tools"),
                                                   "n_calls": sum(names.values()), "tools": dict(names),
                                                   "families": dict(fams), "entropy_bits": round(entropy(names), 3)}
    tot = sum(fam_totals.values()) or 1
    for a in agents.values():
        lean = a["leaning"]
        if lean in cfg["affinity_tool_map"] and a["n_calls"]:
            share = a["families"].get(lean, 0) / a["n_calls"]
            base = fam_totals.get(lean, 0) / tot
            a["leaning_share"] = round(share, 3)
            a["leaning_lift"] = round(share / base, 3) if base else None
    arms = {}
    for run_id, arm, ad, m in arm_items(root):
        lin = centralization.lineage(read_jsonl(Path(ad) / "artifacts.jsonl"))
        lin.pop("derived_edges", None)
        kb = {who: kb_stats(p) for who, p in kbs_of(ad, m).items()}
        rep = None
        sub = Path(root) / "submissions" / run_id / arm / "report.md"
        if sub.exists():
            links = LINK.findall(sub.read_text(encoding="utf-8", errors="ignore"))
            rep = {"links": len(links), "kb_links": sum(1 for x in links if "kb" in x.lower())}
        row = {"kb": kb, "lineage": lin, "report_links": rep}
        if base_arm(arm) in ("collective", "planner"):
            res = centralization.arm_result(root, run_id, arm)
            row["graph"] = {k: res.get(k) for k in ("degree_centralization", "betweenness_max", "top_agent_post_share",
                                                    "n_directive_posts", "directive_share", "emergent_leader",
                                                    "edges_by_type", "needs", "replications")}
        arms[f"{run_id}/{arm}"] = row
    write_json(mdir / "process_metrics.json", {"utc": utc_now(), "agents": agents, "arms": arms,
                                               "family_totals": dict(fam_totals)})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--snapshot", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    cfg = load_config()
    mdir = root / cfg.get("metrics_dir", "metrics")
    mdir.mkdir(parents=True, exist_ok=True)
    if a.snapshot:
        snapshot(root, mdir)
    else:
        snapshot(root, mdir)
        full(root, mdir, cfg)
    print("ok")


if __name__ == "__main__":
    main()
