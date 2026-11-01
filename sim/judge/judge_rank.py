"""judge_rank.py: rank scored submissions (EVAL_SPEC_v1 §5a, §8).

    python judge_rank.py results/ [--panel panel_scores.json] [--out ranking.json]

results/<arm>/submission.json (+ judge_primary.json, judge_sensitivity_datasheet.json) from judge_submission.py.
Order: gate-passing submissions first, by H_R (Richardson); then gate-failing ones by H_R; then "no submission".
Ties: overlapping uncertainty bands. For a single order, ties are broken by the secondary panel median total, then by
the G1 stress margin. Kendall tau-b between the primary and the datasheet-sensitivity orders.
"""
import argparse
import json
from pathlib import Path


def load(arm_dir, tag):
    p = arm_dir / f"judge_{tag}.json"
    if not p.exists():
        return None
    r = json.loads(p.read_text())
    # addendum A2: primary = fused-state H_avg Richardson
    R = r.get("primary") or r.get("richardson_avg") or {"H_R": r["levels"]["h2"]["H_avg"], "band": [r["levels"]["h2"]["H_avg"]] * 2}
    margin = r["G1"]["sigma_allow_MPa"] - max(r["G1"]["p995_MPa_2x"].values())
    early = r.get("secondary_early") or {}
    return {"H_R": R["H_R"], "band": R["band"], "gates_pass": r["gates_pass"], "G1_margin_MPa": margin,
            "early_H_avg_R": (early.get("richardson_avg") or {}).get("H_R"), "early_not_converged": early.get("not_converged"),
            "raw_H_R": (r.get("richardson") or {}).get("H_R"),
            "gates": {g: r[g].get("pass") for g in ("G1", "G2", "G3", "G4")}}


def order(entries, panel):
    def key(arm):
        e = entries[arm]
        if e is None:
            return (2, 0, 0, 0)
        return (0 if e["gates_pass"] else 1, e["H_R"], -(panel.get(arm, 0)), -e["G1_margin_MPa"])
    arms = sorted(entries, key=key)
    # tie groups: consecutive arms (same gate class) whose bands overlap
    groups, cur = [], []
    for a in arms:
        e = entries[a]
        if cur and e is not None and entries[cur[-1]] is not None and \
                entries[cur[-1]]["gates_pass"] == e["gates_pass"] and e["band"][0] <= max(entries[c]["band"][1] for c in cur):
            cur.append(a)
        else:
            if cur:
                groups.append(cur)
            cur = [a]
    if cur:
        groups.append(cur)
    return arms, groups


def kendall_tau_b(r1, r2):
    """r1, r2: dict arm -> rank position (ties share a value)."""
    arms = [a for a in r1 if a in r2]
    nc = nd = t1 = t2 = 0
    for i in range(len(arms)):
        for j in range(i + 1, len(arms)):
            a, b = arms[i], arms[j]
            d1 = r1[a] - r1[b]; d2 = r2[a] - r2[b]
            if d1 == 0 and d2 == 0:
                continue
            if d1 == 0:
                t1 += 1
            elif d2 == 0:
                t2 += 1
            elif d1 * d2 > 0:
                nc += 1
            else:
                nd += 1
    den = ((nc + nd + t1) * (nc + nd + t2)) ** 0.5
    return (nc - nd) / den if den else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results"); ap.add_argument("--panel"); ap.add_argument("--out")
    a = ap.parse_args()
    panel = json.loads(Path(a.panel).read_text()) if a.panel else {}
    arms = sorted(p.name for p in Path(a.results).iterdir() if p.is_dir())
    out = {}
    pos = {}
    for tag in ("primary", "sensitivity_datasheet"):
        ent = {arm: load(Path(a.results) / arm, tag) for arm in arms}
        o, groups = order(ent, panel)
        pos[tag] = {arm: gi for gi, g in enumerate(groups) for arm in g}
        out[tag] = {"order": o, "tie_groups": groups, "entries": ent}
    out["kendall_tau_b_primary_vs_datasheet"] = kendall_tau_b(pos["primary"], pos["sensitivity_datasheet"])
    out["ranking_changes"] = out["primary"]["tie_groups"] != out["sensitivity_datasheet"]["tie_groups"]
    out["primary_is_official"] = True
    txt = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
