"""Deadline collection (pre-registered): deliverables -> submissions/<run_id>/<arm>/ with SHA-256.

    python collect.py --root R          (run by the scheduler at 07:00; refuses to run twice)

Units are collected one by one as their sessions stop (--item), the rest and the controls at the end (--final).
A submission needs implant.form, implant.stl or implant.3mf, material_spec.json and report.md; anything missing =
no submission for that run (recorded, not repaired). Per arm:
    control     the deterministic control deliverables built at launch (control_build.py)
    single      the agent's deliverables folder
    best_of_n   the harness runs the judge's pre-check (visible cases, coarse) on each agent's deliverables at the
                deadline and takes the lowest H among those passing the gates; if the pre-check is unavailable or
                all fail, a seeded random agent's (complete agents first)
    collective  the shared deliverables folder as it is at the deadline
    planner     the shared deliverables folder (only p1 can write it)
Writes submissions/<run_id>/<arm>/{files, SUBMISSION.json} and submissions/hashes.log; a summary of counts goes to
metrics/submissions.json (no content).
"""
import argparse
import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import append_jsonl, base_arm, load_config, load_json, read_jsonl, run_dir, utc_now, write_json  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def complete(d, cfg):
    d = Path(d)
    need = list(cfg["deliverables"]["files"])
    missing = [f for f in need if not (d / f).is_file()]
    for group in cfg["deliverables"].get("one_of", []):
        if not any((d / f).is_file() for f in group):
            missing.append(" or ".join(group))
    return missing


def files_of(d, cfg):
    names = list(cfg["deliverables"]["files"]) + [f for g in cfg["deliverables"].get("one_of", []) for f in g]
    return [Path(d) / n for n in names if (Path(d) / n).is_file()]


def run_precheck(d, cfg):
    """The judge's pre-check on one deliverables folder (visible cases, coarse). Returns (H, passes, raw) or None."""
    import os
    import subprocess
    script = Path(cfg["judge"]["precheck"])
    script = script if script.is_absolute() else (Path(__file__).resolve().parent / script).resolve()
    if os.environ.get("BT_MOCK_TOOLS"):
        script = Path(__file__).resolve().parent / "sim_mock" / "precheck.py"
    if not script.exists():
        return None
    args = [x.replace("{dir}", str(d)) for x in cfg["judge"].get("precheck_args", ["--submission", "{dir}"])]
    env = {k: v for k, v in os.environ.items() if "API_KEY" not in k.upper() and "TOKEN" not in k.upper()}
    try:
        r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, env=env,
                           cwd=str(script.parent), timeout=cfg["judge"].get("precheck_timeout_s", 900))
        out = r.stdout.strip()
        res = json.loads(out[out.index("{"):]) if "{" in out else {}  # one (indented) JSON object
    except Exception as exc:
        return {"error": str(exc)[:300]}
    if not isinstance(res, dict):
        return {"error": "pre-check output is not a JSON object"}
    return {"H": res.get(cfg["judge"].get("estimate_key", "H")), "pass": res.get(cfg["judge"].get("pass_key", "gates_pass")),
            "rc": r.returncode}


def pick_best_of_n(ad, agents, cfg, run_id, layout="agents"):
    """Fixed before launch: the judge's pre-check on each agent's deliverables at the deadline; lowest H among those
    passing the gates; if the pre-check is unavailable or all fail, a seeded random agent's (complete ones first)."""
    lower = cfg["judge"].get("better", "lower") == "lower"
    results, cands = {}, []
    for a in sorted(agents):
        d = Path(ad) / a if layout == "flat" else Path(ad) / "agents" / a / "deliverables"
        if complete(d, cfg):
            results[a] = {"skipped": "incomplete deliverables"}
            continue
        res = run_precheck(d, cfg)
        results[a] = res if res is not None else {"unavailable": True}
        if res and res.get("pass") and res.get("H") is not None:
            cands.append((float(res["H"]) if lower else -float(res["H"]), a))
    if cands:
        cands.sort()
        return cands[0][1], "lowest pre-check H among agents passing the gates", results
    full = [a for a in agents if not complete(Path(ad) / a if layout == "flat" else
                                              Path(ad) / "agents" / a / "deliverables", cfg)]
    pool = sorted(full) or sorted(agents)
    why = "pre-check unavailable or every agent failed: seeded random " + ("complete agent" if full else "agent")
    return random.Random(run_id).choice(pool), why, results


def snapshot_bon(out_root, run_id, arm, ad, cfg):
    """Freeze every best_of_n agent's deliverables (copies + hashes) before the slow pre-checks."""
    hashes = {}
    for g in load_json(ad / "arm.json")["agents"]:
        src = ad / "agents" / g["id"] / "deliverables"
        dst = out_root / run_id / arm / "_candidates" / g["id"]
        dst.mkdir(parents=True, exist_ok=True)
        for f in files_of(src, cfg):
            shutil.copyfile(f, dst / f.name)
        hashes[g["id"]] = {f.name: sha(f) for f in sorted(dst.glob("*")) if f.is_file()}
    write_json(out_root / run_id / arm / "candidates_frozen.json", {"utc": utc_now(), "hashes": hashes})


def collect_item(root, run_id, arm, cfg):
    out_root = root / "submissions"
    dest = out_root / run_id / arm
    if (dest / "SUBMISSION.json").exists():
        return None  # collected once
    ad = run_dir(root) / run_id / arm
    m = load_json(ad / "arm.json")
    agents = [g["id"] for g in m["agents"]]
    kind = base_arm(arm)
    extra = {}
    if kind == "single":
        src = ad / "agents" / agents[0] / "deliverables"
    elif kind == "best_of_n":
        snapshot_bon(out_root, run_id, arm, ad, cfg)
        cdir = out_root / run_id / arm / "_candidates"
        who, why, results = pick_best_of_n(cdir, agents, cfg, run_id, layout="flat")
        src = cdir / who
        extra = {"picked": who, "why": why,
                 "n_passing": sum(1 for r in results.values() if isinstance(r, dict) and r.get("pass"))}
        write_json(dest / "precheck_results.json", {"utc": utc_now(), "results": results,
                                                    "rule": cfg["judge"]["selection_rule"]})
    else:
        src = ad / "deliverables"
    missing = complete(src, cfg)
    dest.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for f in files_of(src, cfg):
        shutil.copyfile(f, dest / f.name)
        hashes[f.name] = sha(dest / f.name)
    states = {a: (load_json(ad / "agents" / a / "status.json") or {}).get("state") for a in agents}
    rec = {"run_id": run_id, "arm": arm, "collected_utc": utc_now(), "submission": not missing,
           "missing": missing, "files": hashes, "agent_states": states, **extra}
    write_json(dest / "SUBMISSION.json", rec)
    append_jsonl(out_root / "hashes.log", {"run_id": run_id, "arm": arm, "submission": not missing,
                                           "sha256": sha(dest / "SUBMISSION.json"), "utc": utc_now()})
    return {k: rec[k] for k in ("run_id", "arm", "submission", "missing")} | extra


def collect_controls(root, cfg):
    out_root = root / "submissions"
    rows = []
    ctl = root / "control"
    for t in sorted(ctl.glob("*/")) if ctl.exists() else []:
        dest = out_root / "control" / t.name
        if (dest / "SUBMISSION.json").exists():
            continue
        missing = complete(t, cfg)
        dest.mkdir(parents=True, exist_ok=True)
        hashes = {}
        for f in files_of(t, cfg):
            shutil.copyfile(f, dest / f.name)
            hashes[f.name] = sha(dest / f.name)
        write_json(dest / "SUBMISSION.json", {"run_id": "control", "arm": "control", "variant": t.name,
                                              "submission": not missing, "missing": missing, "files": hashes,
                                              "collected_utc": utc_now()})
        rows.append({"run_id": "control", "arm": f"control/{t.name}", "submission": not missing, "missing": missing})
    return rows


def summary(root, cfg):
    rows = []
    for f in sorted((root / "submissions").rglob("SUBMISSION.json")):
        r = load_json(f) or {}
        arm = r.get("arm") if r.get("arm") != "control" else f"control/{r.get('variant')}"
        rows.append({k: r.get(k) for k in ("run_id", "submission", "missing", "picked", "why")} | {"arm": arm})
    md = Path(root) / cfg.get("metrics_dir", "metrics")
    md.mkdir(parents=True, exist_ok=True)
    write_json(md / "submissions.json", {"utc": utc_now(), "rows": rows})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--item", help="run_id/arm: collect this unit now (its sessions have stopped)")
    ap.add_argument("--final", action="store_true", help="collect anything left (units never started = no "
                                                          "submission), the controls, and write the summary")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    cfg = load_config()
    out_root = root / "submissions"
    out_root.mkdir(parents=True, exist_ok=True)
    if a.item:
        run_id, arm = a.item.split("/", 1)
        res = collect_item(root, run_id, arm, cfg)
        if res is None:
            sys.exit("already collected")
        summary(root, cfg)
        print(json.dumps(res))
        return
    if (out_root / "COLLECTED.json").exists():
        sys.exit("already collected")
    for f in sorted(run_dir(root).glob("*/*/arm.json")):
        collect_item(root, f.parent.parent.name, f.parent.name, cfg)
    collect_controls(root, cfg)
    rows = summary(root, cfg)
    write_json(out_root / "COLLECTED.json", {"utc": utc_now(), "n": len(rows)})
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
