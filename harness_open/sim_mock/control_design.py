"""MOCK of bonetwin/sim/control_design.py: the no-agent control design (a regular cubic / square strut grid).

    python control_design.py --target <site> --out control.json [--dim 3|2]
"""
import itertools
import argparse
import json
from pathlib import Path


def grid(dim=3, n=5, box=20.0, w=0.8):
    h = box / (n - 1)
    idx = list(itertools.product(range(n), repeat=dim))
    pos = {p: k for k, p in enumerate(idx)}
    nodes = [[c * h for c in p] for p in idx]
    struts = []
    for p, k in pos.items():
        for ax in range(dim):
            q = tuple(c + (1 if a == ax else 0) for a, c in enumerate(p))
            if q in pos:
                struts.append([k, pos[q], w])
    d = {"schema": "bonetwin-design-v1", "units": "mm", "dim": dim, "material": "rigid10k",
         "box": [box] * dim, "nodes": nodes, "struts": struts}
    if dim == 2:
        d["thickness"] = 8.0
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dim", type=int, default=3, choices=[2, 3])
    a = ap.parse_args()
    Path(a.out).write_text(json.dumps(grid(a.dim), indent=1), encoding="utf-8")
    print(a.out)


if __name__ == "__main__":
    main()
