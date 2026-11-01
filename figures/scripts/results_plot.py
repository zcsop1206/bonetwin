"""Figure 7: arm-by-arm dot-and-band results plot, for per-design values in two states.

    python results_plot.py DATA.json [--name results] [--outdir DIR]

Writes <name>_letter.{png,pdf} and <name>_slide.{png,pdf} into figures/ unless --outdir is given.
Test data: scripts/results_template_data.json is entirely made up and renders as results_template_*, watermarked TEMPLATE.
This script reads only the file you give it. The watermark goes away only when the JSON has "template": false.

EXPECTED JSON

{
  "template": false,                    // optional. Anything but false draws the TEMPLATE watermark.
  "title": "Results by arm",            // optional, keep it descriptive
  "footnote": "Source and method.",     // optional
  "metric": {                           // required: what the two state panels plot
    "name": "H_R",                      // required
    "lower_is_better": true,            // optional, default true; only labels the axis
    "log": false                        // optional, default false
  },
  "goal_metric": {                      // optional: adds a third panel, same fields as "metric"
    "name": "goal metric", "lower_is_better": true, "log": false
  },
  "gates": ["G1", "G2", "G3", "G4"],    // optional: columns of the gate matrix; [] or absent hides it
  "arms": [                             // required: rows are drawn in this order; nothing is re-sorted or ranked
    {
      "arm": "Collective",              // required
      "designs": [                      // required, at least one
        {
          "id": "r1",                   // required: row label
          "submitted": true,            // optional, default true. false draws the no-submission marker; no values allowed
          "fused": {"value": 0.20, "lo": 0.18, "hi": 0.22},   // official fused state
          "graft": {"value": 0.15, "lo": 0.14, "hi": 0.16},   // early graft state
          "goal":  {"value": 1.10, "lo": 1.00, "hi": 1.20},   // optional, only with goal_metric
          "gates": {"G1": true, "G2": false}                  // pass (true), fail (false); a missing gate draws as not run
        }
      ]
    }
  ]
}

"lo" <= "value" <= "hi" is checked. On a submitted design a missing state draws "not run", which is different from no submission.

Drawing rules: dot = value, thick line = band. Within each panel, designs linked by overlapping bands form a tie group, drawn as a bracket
at the right of the panel with a letter and a tint over the group's span. A chain A-B-C is one group even if A and C do not overlap.
A hollow dot means at least one gate failed for that design. Rows are not ranked.
"""
import argparse
import json
import sys
from pathlib import Path

from figlib import ANNOT, BG, BLUE, FOOT, GRID, INK, LABEL, MUTED, ORANGE, axes_in, frame, new, save

STATES = [("fused", "Official fused", ORANGE, "o"), ("graft", "Early graft", BLUE, "D")]


def fail(msg):
    sys.exit(f"results_plot: bad input: {msg}")


def validate(d):
    if "metric" not in d or "name" not in d["metric"]:
        fail("metric.name is required")
    if not d.get("arms"):
        fail("arms is required")
    panels = ["fused", "graft"] + (["goal"] if d.get("goal_metric") else [])
    gates = d.get("gates") or []
    for a in d["arms"]:
        if "arm" not in a or not a.get("designs"):
            fail("each arm needs 'arm' and 'designs'")
        for x in a["designs"]:
            where = f"{a['arm']}/{x.get('id')}"
            if "id" not in x:
                fail(f"design without id in {a['arm']}")
            if x.get("submitted", True) is False:
                if any(k in x for k in ("fused", "graft", "goal")):
                    fail(f"{where}: submitted false but has values")
                continue
            for k in panels:
                if k in x:
                    v = x[k]
                    if not all(isinstance(v.get(f), (int, float)) for f in ("value", "lo", "hi")):
                        fail(f"{where}.{k}: needs numeric value, lo, hi")
                    if not v["lo"] <= v["value"] <= v["hi"]:
                        fail(f"{where}.{k}: needs lo <= value <= hi")
            for g in x.get("gates", {}):
                if g not in gates:
                    fail(f"{where}: gate {g} not in top-level gates")
    return panels


def tie_groups(items):
    """items: list of (row, lo, hi). Returns groups of 2+ rows connected through overlapping bands."""
    items = sorted(items, key=lambda i: i[1])
    groups, cur, cur_hi = [], [], None
    for it in items:
        if cur and it[1] <= cur_hi:
            cur.append(it)
            cur_hi = max(cur_hi, it[2])
        else:
            if len(cur) > 1:
                groups.append(cur)
            cur, cur_hi = [it], it[2]
    if len(cur) > 1:
        groups.append(cur)
    return groups


def draw(d, panels, fmt, name, outdir):
    fig = new(fmt)
    fig.canvas.draw()
    foot = d.get("footnote", "")
    tail = "Dot = value, thick line = band. Brackets mark ties: designs linked by overlapping bands. Hollow dot = a gate failed. Rows are not ranked."
    l, b, r, t = frame(fig, d.get("title", "Results by arm"), (foot + " " + tail).strip())
    W, H = fig.get_size_inches()
    rows = []
    y = 0
    for a in d["arms"]:
        for x in a["designs"]:
            rows.append((y, a["arm"], x))
            y += 1
        y += 0.6
    ymax = y - 0.6
    arm_w, id_w = 1.3, 0.55
    gates = d.get("gates") or []
    gw = 0.32 * len(gates) + (0.2 if gates else 0)
    x_start = l + arm_w + id_w + gw
    gap = 0.2
    pw = (r - x_start - gap * (len(panels) - 1)) / len(panels)
    head = 0.5
    ax0 = None
    for pi, key in enumerate(panels):
        x0 = x_start + pi * (pw + gap)
        ax = axes_in(fig, x0, b + 0.72, x0 + pw, t - head)
        if pi == 0:
            ax0 = ax
        spec = d["goal_metric"] if key == "goal" else d["metric"]
        lab, col, mk = next(((s[1], s[2], s[3]) for s in STATES if s[0] == key), (spec["name"], INK, "s"))
        ax.set_ylim(ymax - 0.4 + 0.4, -0.7)
        if spec.get("log"):
            ax.set_xscale("log")
        vals = [v for _, _, x in rows if key in x for v in (x[key]["lo"], x[key]["hi"])]
        if d.get("goal_metric") is None or key != "goal":
            vals += [v for k in ("fused", "graft") for _, _, x in rows if k in x for v in (x[k]["lo"], x[k]["hi"])]
        lo, hi = min(vals), max(vals)
        if spec.get("log"):
            ax.set_xlim(lo / 1.3, hi * 2.2)
        else:
            span = hi - lo or 1
            ax.set_xlim(lo - 0.07 * span, hi + 0.30 * span)
        ax.grid(axis="x", color=GRID, lw=1)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(pi == 0)
        ax.set_yticks([])
        better = "lower is better" if spec.get("lower_is_better", True) else "higher is better"
        ax.set_xlabel(f"{spec['name']} ({better})", fontsize=ANNOT - 1)
        ax.tick_params(axis="x", labelsize=ANNOT - 2)
        fig.text(x0 / W, (t - 0.04) / H, lab, fontsize=LABEL, fontweight="bold", va="top", ha="left")
        items = []
        for yy, _, x in rows:
            if x.get("submitted", True) is False:
                ax.plot([0.04], [yy], marker="x", ms=11, mew=2.6, color=INK, ls="", transform=ax.get_yaxis_transform(), zorder=5)
                ax.text(0.095, yy, "no submission", transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=ANNOT - 2, color=INK)
                continue
            if key not in x:
                ax.text(0.03, yy, "not run", transform=ax.get_yaxis_transform(), va="center", ha="left", fontsize=ANNOT - 2, color=MUTED, style="italic")
                continue
            v = x[key]
            failed = any(g is False for g in x.get("gates", {}).values())
            ax.plot([v["lo"], v["hi"]], [yy, yy], color=col, lw=8, solid_capstyle="butt", zorder=3, alpha=0.8)
            ax.plot([v["value"]], [yy], marker=mk, ms=8, mfc=BG if failed else col, mec=INK, mew=1.4, ls="", zorder=4)
            items.append((yy, v["lo"], v["hi"]))
        for gi, grp in enumerate(tie_groups(items)):
            ys = [i[0] for i in grp]
            ax.axvspan(min(i[1] for i in grp), max(i[2] for i in grp), ymin=0, ymax=1, color="#E3DDCF", alpha=0.55, lw=0, zorder=0)
            bx = 0.86 + 0.07 * (gi % 2)
            tr = ax.get_yaxis_transform()
            ax.plot([bx, bx], [min(ys), max(ys)], color=INK, lw=2, transform=tr, zorder=6)
            for yy in ys:
                ax.plot([bx - 0.015, bx], [yy, yy], color=INK, lw=2, transform=tr, zorder=6)
            ax.text(bx + 0.012, (min(ys) + max(ys)) / 2, f"tie {chr(65 + gi)}", transform=tr, rotation=90, ha="left", va="center", fontsize=ANNOT - 3, color=INK)
    # labels and gate matrix on the first panel's axes
    tr = ax0.get_yaxis_transform()
    pw0 = pw
    def fx(inches):  # inches left of the first panel, in axes fraction
        return -inches / pw0
    seen = {}
    for yy, arm, x in rows:
        seen.setdefault(arm, []).append(yy)
        ax0.text(fx(gw + 0.08), yy, x["id"], transform=tr, ha="right", va="center", fontsize=ANNOT - 1, clip_on=False)
        for gi, g in enumerate(gates):
            gx = fx(gw - 0.1 - 0.32 * gi - 0.13)
            st = None if x.get("submitted", True) is False else x.get("gates", {}).get(g)
            if x.get("submitted", True) is False:
                continue
            if st is True:
                ax0.plot([gx], [yy], marker="s", ms=11, color=INK, ls="", transform=tr, clip_on=False, zorder=6)
            elif st is False:
                ax0.plot([gx], [yy], marker="s", ms=11, mfc=BG, mec=INK, mew=1.4, ls="", transform=tr, clip_on=False, zorder=6)
                ax0.plot([gx], [yy], marker="x", ms=8, mew=1.6, color=INK, ls="", transform=tr, clip_on=False, zorder=7)
            else:
                ax0.text(gx, yy, "–", transform=tr, ha="center", va="center", fontsize=ANNOT, color=MUTED, clip_on=False)
    for gi, g in enumerate(gates):
        ax0.text(fx(gw - 0.1 - 0.32 * gi - 0.13), -0.62, g, transform=tr, ha="center", va="bottom", fontsize=ANNOT - 3, clip_on=False, color=INK)
    for arm, ys in seen.items():
        ax0.text(fx(gw + id_w), (min(ys) + max(ys)) / 2, arm, transform=tr, ha="right", va="center", fontsize=LABEL - 1, fontweight="bold", clip_on=False)
    if gates:
        fig.text((x_start - gw + 0.02) / W, (t - 0.04) / H, "Gates", fontsize=ANNOT, va="top", ha="left", fontweight="bold")
    if d.get("template", True) is not False:
        fig.text(0.5, 0.52, "TEMPLATE", fontsize=96 if fmt == "slide" else 84, fontweight="bold", color=INK, alpha=0.13, rotation=24, ha="center", va="center", zorder=50)
        fig.text(0.985, 0.985, "TEMPLATE: MADE-UP DATA", fontsize=ANNOT, fontweight="bold", color=INK, ha="right", va="top", zorder=50)
    save(fig, name, fmt, outdir)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data")
    ap.add_argument("--name", default="results")
    ap.add_argument("--outdir")
    a = ap.parse_args()
    d = json.loads(Path(a.data).read_text(encoding="utf-8-sig"))
    panels = validate(d)
    for f in ("letter", "slide"):
        draw(d, panels, f, a.name, a.outdir)


if __name__ == "__main__":
    main()
