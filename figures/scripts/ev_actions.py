"""D. Who did what: per-agent shares of posts, directives, tool calls, PreForm calls, active time and credits.
Source: analysis_process/metrics.json. Per-agent KB files cannot be attributed from that file, so active minutes stand in."""
import json

import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

from figlib import *  # noqa

m = json.load(open(AP / "metrics.json", encoding="utf-8"))
RUNS = [("r1/collective", "r1 collective"), ("r2/collective", "r2 collective"), ("r1/planner", "r1 planner"), ("r2/planner", "r2 planner")]
COLS = ["Posts", "Directives", "Tool calls", "PreForm", "Minutes", "Credits (k)"]
CMAP = LinearSegmentedColormap.from_list("o", ["#FBF0E6", "#EDB48E", "#B5471A", "#5E2108"])


def table(run):
    R = m["runs"][run]
    ags = [k for k in m["agents"] if k.startswith(run + "/")]
    rows = {}
    bd = R["board"]
    for k in ags:
        a = m["agents"][k]
        n = a["agent"]
        rows[n] = [bd["posts_by_agent"].get(n, 0), bd["directive_counts"].get(n, 0), a["tool_calls"]["n_harness_view"], a["preform"]["calls"], a["wall_min"], a["credits_used"] / 1000]
    names = sorted(rows)
    M = np.array([rows[n] for n in names], float)
    tot = M.sum(0)
    S = np.divide(M, tot, out=np.zeros_like(M), where=tot > 0)
    order = np.argsort(-S.mean(1), kind="stable")
    return [names[i] for i in order], M[order], S[order], tot


def heat(fmt):
    fig = new(fmt)
    l, b, r, t = frame(fig, "Planner talk runs through one agent; PreForm use concentrates",
                       foot="Direct. = directive posts; Tools = tool calls; Min. = minutes; Cred. k = thousand credits. Cell shade = that agent's share of its run's column total; number = raw count (equal split would be 17% each). Agents sorted by mean share. Credits are capped by quota, so they differ little; minutes are per-agent wall time. "
                            "Knowledge-base files can't be attributed per agent from the logs. Source: analysis_process/metrics.json.")
    gapx, gapy = 0.45, 0.36
    w = (r - l - gapx) / 2
    h = (t - b - gapy) / 2
    for i, (run, lab) in enumerate(RUNS):
        c, rw = i % 2, i // 2
        x0 = l + c * (w + gapx)
        y0 = b + (1 - rw) * (h + gapy)
        ax = axes_in(fig, x0 + 0.42, y0, x0 + w, y0 + h - 0.62)
        names, M, S, tot = table(run)
        print(lab, {COLS[j]: f"{names[int(np.argmax(S[:, j]))]} {S[:, j].max():.2f} of {tot[j]:.0f}" for j in range(6)})
        ax.imshow(S, cmap=CMAP, vmin=0, vmax=1, aspect="auto")
        fs = 13 if fmt == "slide" else 12
        for a in range(M.shape[0]):
            for j in range(M.shape[1]):
                ax.text(j, a, f"{M[a, j]:.0f}", ha="center", va="center", fontsize=fs, color="#FFFDF8" if S[a, j] > 0.45 else INK)
        ax.set_xticks(range(6))
        ax.set_xticklabels(COLS if fmt == "slide" else ["Posts", "Direct.", "Tools", "PreForm", "Min.", "Cred. k"], fontsize=FOOT)
        ax.xaxis.tick_top()
        ax.set_yticks(range(6))
        ax.set_yticklabels(names, fontsize=FOOT + 1)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xticks(np.arange(-0.5, 6), minor=True)
        ax.set_yticks(np.arange(-0.5, 6), minor=True)
        ax.grid(which="minor", color=BG, lw=2)
        ax.tick_params(which="minor", length=0)
        fig.text((x0) / fig.get_size_inches()[0], (y0 + h - 0.05) / fig.get_size_inches()[1], lab, fontsize=LABEL - 1, fontweight="bold", va="top")
    save(fig, "action_heatmap", fmt)


def top(fmt):
    fig = new(fmt)
    l, b, r, t = frame(fig, "Share held by the top agent in each run",
                       foot="Dashed line: even split among six agents (17%). n = directive posts in the whole run; r2 collective's 100% is a single post. Source: analysis_process/metrics.json.")
    ax = axes_in(fig, l + 1.45, b + 1.05, r - 0.3, t)
    STY = {"r1 collective": ("o", ORANGE), "r2 collective": ("s", ORANGE), "r1 planner": ("D", BLUE), "r2 planner": ("^", BLUE)}
    cols = [0, 1, 2, 3, 4]
    off = {"r1 collective": 0.3, "r2 collective": 0.1, "r1 planner": -0.1, "r2 planner": -0.3}
    for run, lab in RUNS:
        names, M, S, tot = table(run)
        mk, col = STY[lab]
        for k, j in enumerate(cols):
            y = len(cols) - 1 - k + off[lab]
            ax.plot(100 * S[:, j].max(), y, mk, color=col, ms=13, mec=BG, mew=1.2, clip_on=False)
            who = names[int(np.argmax(S[:, j]))]
            ax.text(100 * S[:, j].max() + 2.1, y, who + (f" (n={tot[j]:.0f})" if j == 1 else ""), va="center", fontsize=FOOT, color=MUTED)
    ax.axvline(100 / 6, color=MUTED, ls="--", lw=1.2)
    ax.set_yticks([len(cols) - 1 - k for k in range(len(cols))])
    ax.set_yticklabels([COLS[j] for j in cols], fontsize=ANNOT)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 118)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("Top agent's share, %")
    ax.set_ylim(-0.5, len(cols) - 0.5)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    hs = [Line2D([], [], marker=STY[k][0], color=STY[k][1], ls="", ms=11, mec=BG, label=k) for _, k in RUNS]
    fig.legend(handles=hs, loc="lower center", ncol=4, bbox_to_anchor=(0.55, (b + 0.0) / fig.get_size_inches()[1]), fontsize=FOOT + 1, handletextpad=0.2, columnspacing=1.4)
    save(fig, "action_top_share", fmt)


for f in ("slide", "letter"):
    heat(f)
    top(f)
