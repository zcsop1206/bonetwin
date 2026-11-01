"""MOCK of bonetwin/sim/export_stl.py: extrude each strut as a box and write an ASCII STL.

    python export_stl.py --design d.json --out d.stl
"""
import argparse
import json
import math
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = json.loads(Path(a.design).read_text(encoding="utf-8"))
    t = float(d.get("thickness", 8.0))
    lines = ["solid mock"]
    for i, j, w in d["struts"]:  # 3-D designs are projected onto z = 0 (mock only)
        (x1, y1), (x2, y2) = d["nodes"][int(i)][:2], d["nodes"][int(j)][:2]
        L = math.hypot(x2 - x1, y2 - y1) or 1.0
        nx, ny = -(y2 - y1) / L * w / 2, (x2 - x1) / L * w / 2
        q = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
        for z0, z1 in ((0.0, 0.0), (t, t)):  # bottom and top faces only (mock)
            for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                lines.append("facet normal 0 0 1\n outer loop")
                lines += [f"  vertex {x:.4f} {y:.4f} {z0:.4f}" for x, y in tri]
                lines.append(" endloop\nendfacet")
    lines.append("endsolid mock")
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {a.out} ({len(d['struts'])} struts, MOCK)")


if __name__ == "__main__":
    main()
