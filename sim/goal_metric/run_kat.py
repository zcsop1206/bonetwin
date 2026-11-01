"""Known-answer tests of the goal metric: synthetic shapes only, h2 = 0.4, h1 = 0.8, Tough 1500 (Ti for one block).

    python run_kat.py <out_dir> [--threads 2]

Passes when the gated top group contains lattice_matched and only uniform bone-like lattices: no block, sliver, frame,
locally stiff or too-weak shape. (An earlier criterion required lattice_matched alone at the top; see the addendum, A4.7.)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
threads = sys.argv[sys.argv.index("--threads") + 1] if "--threads" in sys.argv else "2"
os.environ["JUDGE_THREADS"] = threads
import goal_metric as G  # noqa: E402
import make_kat as K  # noqa: E402

CASES = [("solid_block", "solid_block", "tough1500"), ("solid_block_ti", "solid_block", "ti6al4v"), ("thin_frame", "thin_frame", "tough1500"),
         ("tilted_sliver", "tilted_sliver", "tough1500"), ("lattice_matched", "lattice_matched", "tough1500"),
         ("lattice_alone_match", "lattice_alone_match", "tough1500"),
         ("lattice_local_stiff", "lattice_local_stiff", "tough1500"), ("lattice_too_weak", "lattice_too_weak", "tough1500")]
BONE_LIKE = {"lattice_matched", "lattice_alone_match"}
shapes = K.shapes()
res = []
for name, shape, mat in CASES:
    o = out / f"{name}.json"
    if not o.exists():
        p = out / f"{shape}.stl"
        if not p.exists():
            K.save(shapes[shape], p)
        r = G.score_mesh(str(p), G.matargs(mat), h2=0.4, max_dof=20e6, early=True)
        o.write_text(json.dumps(r, indent=1, default=float))
    res.append(G.combine({"name": name, **json.loads(o.read_text())}))   # M_R recomputed from the stored Q per level
table = G.rank(res)
uncond = G.rank_unconditional(res)
print("unconditional (gates ignored): " + "; ".join(f"{t['rank']} {t['name']} {t['M_R']:.3f}" for t in uncond))
for row, r in ((t, next(x for x in res if x["name"] == t["name"])) for t in table):
    s = r["levels"]["h2"]["states"]; g = r["gates"]
    print(f"{row['rank']} {row['name']:22s} M_R {row['M_R']:.3f} [{row['band'][0]:.3f},{row['band'][1]:.3f}] "
          f"Qa {s['alone']['Q']:.3f} Qe {s['early']['Q']:.3f} Qf {s['fused']['Q']:.3f} "
          f"Da {s['alone']['D_eff']:.3f} Df {s['fused']['D_eff']:.3f} "
          f"IA {g['IA_alone_strength'].get('worst_p995_MPa_2x')}/{g['IA_alone_strength']['allow_MPa']} "
          f"fill {g['hull_fill']:.2f} G2 {g['G2_one_component']} G4 {g['G4_size']} pass {g['pass']} wall {r['wall_s']}s", flush=True)
(out / "kat_summary.json").write_text(json.dumps({"gated": table, "unconditional": uncond}, indent=1))
top = {t["name"] for t in table if t["rank"] == 1}
ok = "lattice_matched" in top and top <= BONE_LIKE
print("top group:", sorted(top))
print("KAT PASS" if ok else "KAT FAIL")
sys.exit(0 if ok else 1)
