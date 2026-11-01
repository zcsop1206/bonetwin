"""Figure 5: all 38 sessions to scale, simplified from analysis_process/timeline.png panel b, no billing colours.
Source: analysis_process/metrics.json agents.* (first_start_utc, end_utc, end_state); event times from analysis_process/timeline.md."""
import json

from figlib import ANNOT, AP, BG, FOOT, GREY, GRID, INK, LABEL, MUTED, ORANGE, BLUE, axes_in, clock, frame, hms, minutes, new, save
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ARMS = [("collective", "Collective", ORANGE), ("planner", "Planner", BLUE), ("best_of_n", "Best-of-N", GREY), ("single", "Single", GREY)]
END = {"capped": ("X", 13), "finished": ("o", 11), "window": ("s", 11)}
INCIDENT, N1, N2, INTERV = hms(3, 49, 57), hms(4, 46, 41), hms(4, 50, 39), hms(5, 35, 49)


def draw(fmt):
    M = json.loads((AP / "metrics.json").read_text(encoding="utf-8"))
    ag = M["agents"]
    assert len(ag) == 38
    tl = (AP / "timeline.md").read_text(encoding="utf-8")
    for s in ("03:49:57 EST", "04:46:41 EST", "04:50:39 EST", "05:35:49 EST"):
        assert s in tl, s
    counts = {k: sum(a["end_state"] == k for a in ag.values()) for k in END}
    assert sum(counts.values()) == 38
    fig = new(fmt)
    fig.canvas.draw()
    foot = ("Local time, EST, to scale. Bars run from each agent's first start to its end; the aborted 00:52 launch is not shown. "
            "Incident: scheduler restart spawned duplicate runners, shaded window 03:44 to 03:58. Notices: two creativity notices (tally: 11 delivered, 7 at start, 20 missed). "
            "Intervention: the pre-registered check on r2 collective found no leader and took no action. Source: analysis_process/metrics.json, timeline.md.")
    l, b, r, t = frame(fig, "All 38 sessions, one row per agent", foot)
    h = [Line2D([], [], marker="X", ls="", color=INK, ms=13, label=f"out of credit ({counts['capped']})"),
         Line2D([], [], marker="o", ls="", color=INK, ms=11, label=f"finished ({counts['finished']})"),
         Line2D([], [], marker="s", ls="", color=INK, ms=11, label=f"90-min window closed ({counts['window']})")]
    W, H = fig.get_size_inches()
    fig.legend(handles=h, loc="lower left", bbox_to_anchor=((l + 1.2) / W, b / H), ncol=3, fontsize=ANNOT, handletextpad=0.2, columnspacing=1.4)
    b2 = b + 0.78
    arm_w = 1.28
    id_w = 0.36
    gutter = 0.3
    pw = (r - l - arm_w - id_w * 2 - gutter) / 2
    head = 0.82
    xa = l + arm_w + id_w
    for pi, run in enumerate(("r1", "r2")):
        x0 = xa + pi * (pw + gutter + id_w)
        ax = axes_in(fig, x0, b2, x0 + pw, t - head)
        y, yt, yl = 0, [], []
        for arm, name, col in ARMS:
            keys = sorted(k for k in ag if k.startswith(f"{run}/{arm}/"))
            ys = []
            for k in keys:
                A = ag[k]
                st, en = minutes(A["first_start_utc"]), minutes(A["end_utc"])
                ax.plot([st, en], [y, y], color=col, lw=6.5, solid_capstyle="butt", zorder=2)
                mk, ms = END[A["end_state"]]
                ax.plot([en], [y], marker=mk, ms=ms * (0.82 if fmt == "slide" else 0.95), color=INK, mec=BG, mew=1, zorder=4)
                yt.append(y)
                yl.append(A["agent"])
                ys.append(y)
                y += 1
            if pi == 0:
                ax.text(-(id_w + 0.03) / pw, (ys[0] + ys[-1]) / 2, name, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=LABEL - 1 if fmt == "slide" else LABEL - 1, fontweight="bold")
            y += 0.7
        ax.set_ylim(y - 0.5, -0.8)
        ax.set_yticks(yt)
        ax.set_yticklabels(yl, fontsize=11)
        ax.tick_params(axis="y", length=0, pad=3)
        ax.spines["left"].set_visible(False)
        ax.set_xlim(hms(3, 25), hms(6, 35))
        tk = [hms(3, 30), hms(4, 30), hms(5, 30), hms(6, 30)]
        ax.set_xticks(tk)
        ax.set_xticklabels([clock(v) for v in tk], fontsize=ANNOT)
        ax.grid(axis="x", color=GRID, lw=1)
        ax.set_axisbelow(True)
        ax.axvspan(hms(3, 44), hms(3, 58), color="#E3DDCF", lw=0, zorder=0)
        ax.axvline(INCIDENT, color=INK, lw=1.4, ls=(0, (2, 2)), zorder=1)
        ax.axvline(N1, color=INK, lw=1.4, ls=(0, (1, 1.5)), zorder=1)
        ax.axvline(N2, color=INK, lw=1.4, ls=(0, (1, 1.5)), zorder=1)
        tr = ax.get_xaxis_transform()
        fs = ANNOT - 2
        ax.text(INCIDENT, 1.012, "incident\n03:49:57", transform=tr, ha="center", va="bottom", fontsize=fs, linespacing=1.05)
        ax.text((N1 + N2) / 2, 1.012, "notices\n04:46:41, 04:50:39", transform=tr, ha="center", va="bottom", fontsize=fs, linespacing=1.05)
        if run == "r2":
            ax.axvline(INTERV, color=INK, lw=1.4, ls=(0, (6, 2)), zorder=1)
            ax.text(INTERV + 3, 1.012, "intervention check\n05:35:49", transform=tr, ha="left", va="bottom", fontsize=fs, linespacing=1.05)
        fig.text(x0 / W, (t - 0.02) / H, f"Replicate {run}", fontsize=LABEL + 1, fontweight="bold", va="top", ha="left")
    save(fig, "sessions", fmt)


if __name__ == "__main__":
    for f in ("letter", "slide"):
        draw(f)
