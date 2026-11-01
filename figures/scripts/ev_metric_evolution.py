"""C. How success was operationalized, on a to-scale real-time axis. Times: analysis/CHANGES.md (18:50 freeze),
sim/README.md (3-D NO-GO about 20:35), file times of score_report.json and the spec addenda (UTC, read here)."""
import datetime as dt
import os

from matplotlib.patches import FancyBboxPatch

from figlib import *  # noqa

U = dt.timezone.utc
def mt(rel):
    return dt.datetime.fromtimestamp(os.path.getmtime(B / rel), U)

EDT = dt.timezone(dt.timedelta(hours=-4))
EV = [
    (dt.datetime(2026, 10, 31, 18, 50, tzinfo=EDT), "18:50", "Prediction contest", "Sealed predictions vs. coupon tests. Scored 00:10: 7 of 16 quantities measured.", "Why: test agents against real parts first."),
    (dt.datetime(2026, 10, 31, 20, 35, tzinfo=EDT), "20:35", "3-D judge NO-GO, 2-D interim", "Ranks swapped between 0.4 and 0.2 mm meshes: 0.196 vs 0.220 became 0.350 vs 0.174.", "Why: a score that flips with mesh can't rank."),
    (mt("sim/EVAL_SPEC_v1.md"), "00:22", "Implant goal, spec v1", "Arbitrary 3-D geometry, two mesh sizes, Richardson band, gates. Calibrated from the tests.", "Why: goal became matching bone without losing integrity."),
    (mt("sim/EVAL_SPEC_v1_addendum2.md"), "03:22", "Addendum 2: fused state", "Voids filled with bone, H averaged over 0.8 mm cubes. Early 30 MPa graft reported.", "Why: empty-void H kept growing, 0.33, 0.77, 1.20."),
    (mt("sim/EVAL_SPEC_v1_addendum3.md"), "07:15", "Addendum 3: 20M mesh cap", "One uniform cap, down from 25M unknowns. Only the two largest designs got coarser.", "Why: measured 4.4 GB per million unknowns."),
    (mt("sim/EVAL_SPEC_v1_addendum4_goalmetric.md"), "08:07", "Addendum 4: goal metric", "Stiffness mismatch, worse of empty and fused states; implant alone carries load. Exploratory.", "Why: fused score can favor less material."),
]
for e in EV:
    print(e[1], e[0].astimezone(U))
T0 = dt.datetime(2026, 10, 31, 22, 0, tzinfo=U)  # 18:00 EDT
hrs = lambda d: (d - T0).total_seconds() / 3600
END = 16.0


def local(h):
    d = T0 + dt.timedelta(hours=h)
    off = -4 if d < dt.datetime(2026, 11, 1, 6, 0, tzinfo=U) else -5
    return (d + dt.timedelta(hours=off)).strftime("%H:%M")


def build(fmt):
    fig = new(fmt)
    l, b, r, t = frame(fig, "How we defined success, and each time evidence forced a change",
                       foot="Axis is real elapsed time, to scale. Clocks fell back at 02:00, so local time repeats 01:00 to 02:00. The official ranking stayed frozen after addendum 2 except for the logged mesh cap. Sources: analysis/CHANGES.md, sim/validation_3d.md, sim addenda (file times).")
    ax = axes_in(fig, l, b, r, t)
    W, Ht = r - l, t - b
    ax.set_xlim(0, W)
    ax.set_ylim(0, Ht)
    ax.axis("off")
    ytop = Ht - 0.55
    sc = (W - 0.3) / END
    x = lambda h: 0.15 + h * sc
    ax.plot([x(0), x(END)], [ytop, ytop], color=MUTED, lw=2)
    for h in range(0, 17, 2):
        ax.plot([x(h)] * 2, [ytop - 0.07, ytop], color=MUTED, lw=1.2)
        ax.text(x(h), ytop - 0.2, local(h), ha="center", va="top", fontsize=FOOT, color=MUTED)
    for i, e in enumerate(EV):
        h = hrs(e[0])
        ax.plot(x(h), ytop, "o", ms=23, color=ORANGE, mec=BG, mew=2, zorder=3, clip_on=False)
        ax.text(x(h), ytop - 0.005, str(i + 1), color="#FFFDF8", fontsize=ANNOT - 1, fontweight="bold", ha="center", va="center", zorder=4)
    gap = 0.18
    cw = (W - 2 * gap) / 3
    area = ytop - 0.58
    ch = (area - gap) / 2
    for i, e in enumerate(EV):
        cx = (i % 3) * (cw + gap)
        cy = area - ch - (i // 3) * (ch + gap)
        ax.add_patch(FancyBboxPatch((cx, cy), cw, ch, boxstyle="round,pad=0,rounding_size=0.05", fc="#FFFDF8", ec=GRID, lw=1.3))
        y = cy + ch - 0.1
        fs = 15 if fmt == "slide" else 13
        for ln in wrap(fig, f"{i + 1}  {e[1]}  {e[2]}", fs + 1, cw - 0.55):
            ax.text(cx + 0.12, y, ln, fontsize=fs + 1, fontweight="bold", va="top")
            y -= (fs + 1) * 1.25 / 72
        y -= 0.05
        for ln in wrap(fig, e[3], fs, cw - 0.24):
            ax.text(cx + 0.12, y, ln, fontsize=fs, va="top")
            y -= fs * 1.22 / 72
        y -= 0.04
        for ln in wrap(fig, e[4], fs, cw - 0.24):
            ax.text(cx + 0.12, y, ln, fontsize=fs, va="top", color=ORANGE, fontweight="bold")
            y -= fs * 1.22 / 72
        if y < cy:
            print("OVERFLOW", fmt, i, y - cy)
    save(fig, "metric_evolution", fmt)


for f in ("slide", "letter"):
    build(f)
