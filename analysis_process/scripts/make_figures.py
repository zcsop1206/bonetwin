"""Figures for the process analysis. Reads analysis_process/metrics.json, data/curves.json and read-only logs."""
import datetime as dt
import os
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.dont_write_bytecode = True
B = Path(os.environ.get("BONETWIN_ROOT") or Path(__file__).resolve().parents[2])
OUT = B / "analysis_process"
G = OUT / "graphs"
G.mkdir(exist_ok=True)
M = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
CUR = json.loads((OUT / "data" / "curves.json").read_text(encoding="utf-8"))
H = B / "harness_open"
UTC = dt.timezone.utc
EST = dt.timezone(dt.timedelta(hours=-5))
EDT = dt.timezone(dt.timedelta(hours=-4))
FALLBACK = dt.datetime(2026, 11, 1, 6, tzinfo=UTC)
# Okabe-Ito order, checked with the dataviz validator: secondary encoding (line style + marker + labels) is always on.
AG = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#56B4E9", "#E69F00"]
LS = ["-", "--", "-.", ":", (0, (5, 1)), (0, (3, 1, 1, 1))]
MK = ["o", "s", "^", "D", "v", "P"]
INK, MUTED, GRID = "#1F2933", "#5B6B7A", "#E3E7EB"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left", "figure.facecolor": "white"})
END_MARK = {"capped": "X", "finished": "o", "window": "s"}
ARM_NAME = {"single": "single", "best_of_n": "best of N", "collective": "collective", "planner": "planner"}


def rj(p):
    out = []
    for ln in Path(p).read_text(encoding="utf-8-sig", errors="replace").splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def t(s):
    return dt.datetime.fromisoformat(s).astimezone(UTC)


def est(h, m, s=0):
    return dt.datetime(2026, 11, 1, h, m, s, tzinfo=EST).astimezone(UTC)


def clock_fmt(zone_label=False):
    def f(x, pos=None):
        d = mdates.num2date(x, tz=UTC)
        z = EDT if d < FALLBACK else EST
        return d.astimezone(z).strftime("%H:%M")
    return f


# ---------------------------------------------------------------- communication graphs
E_STYLE = {"reply": ("#0072B2", "-", 0.10), "mention": ("#D55E00", (0, (4, 2)), 0.24), "transfer": ("#009E73", "-.", 0.38),
           "review": ("#CC79A7", ":", 0.48), "cites": ("#56B4E9", "-", 0.5), "contradicts": ("#E69F00", "-", 0.52), "extends": ("#E69F00", "--", 0.54), "replicates": ("#56B4E9", "--", 0.56), "derived": (MUTED, ":", 0.58)}


def e_width(c):
    return 0.7 + 0.75 * math.sqrt(c)


def draw_graph(ax, key, compact=False):
    r = M["runs"][key]["board"]
    nodes = sorted({*(a.split("/")[2] for a in M["agents"] if a.startswith(key + "/"))})
    n = len(nodes)
    pos = {v: (math.cos(2 * math.pi * i / n + math.pi / 2), math.sin(2 * math.pi * i / n + math.pi / 2)) for i, v in enumerate(nodes)}
    size = {v: 170 + 60 * r["posts_by_agent"].get(v, 0) for v in nodes}
    for e in sorted(r["edges"], key=lambda e: -e["count"]):
        col, ls, rad = E_STYLE.get(e["type"], (MUTED, "-", 0.3))
        s, d = pos[e["source"]], pos[e["target"]]
        ax.annotate("", xy=d, xytext=s, zorder=2,
                    arrowprops=dict(arrowstyle="-|>,head_length=0.45,head_width=0.22", color=col, lw=e_width(e["count"]), linestyle=ls, alpha=0.85,
                                    connectionstyle=f"arc3,rad={rad}", shrinkA=math.sqrt(size[e["source"]]) / 2 + 1, shrinkB=math.sqrt(size[e["target"]]) / 2 + 1))
    for v in nodes:
        p = r["posts_by_agent"].get(v, 0)
        lead = key.endswith("planner") and v == "p1"
        ax.scatter(*pos[v], s=size[v], color="#2F3E4E" if p else "white", edgecolor="#2F3E4E", lw=2.4 if lead else 1.2, zorder=3)
        ax.text(*pos[v], v, ha="center", va="center", color="white" if p else INK, fontsize=9.5, fontweight="bold", zorder=4)
        x, y = pos[v]
        rp = math.sqrt(size[v]) / 2
        ax.annotate(f"{p} post{'s' if p != 1 else ''}", xy=pos[v], xytext=(x * (rp + 26), y * (rp + 11)), textcoords="offset points", ha="center", va="center", fontsize=8.5, color=MUTED, zorder=4)
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.45, 1.45)
    ax.set_aspect("equal")
    ax.axis("off")
    run, arm = key.split("/")
    ax.set_title(f"{run} {ARM_NAME[arm]}\n", loc="left", fontsize=12)
    ax.text(0, 1.015, f"degree centralization {r['degree_centralization']:.2f}, betweenness max {r['betweenness_max']:.2f} ({r['betweenness_argmax']}), "
                      f"top poster {r['top_poster']} {100 * r['top_agent_post_share']:.0f}%, {r['n_agent_posts']} posts",
            transform=ax.transAxes, fontsize=8.5, color=MUTED, va="bottom")


def graph_legend(fig, y=0.02, ncol=7):
    h = [Line2D([0], [0], color=E_STYLE[k][0], lw=2.2, ls=E_STYLE[k][1], label=f"edge: {k}") for k in ("reply", "mention", "transfer")]
    h += [Line2D([0], [0], color=MUTED, lw=e_width(c), label=f"{c} link{'s' if c > 1 else ''}") for c in (1, 5, 12)]
    h += [Line2D([0], [0], marker="o", color="none", markerfacecolor="#2F3E4E", markeredgecolor="#2F3E4E", markersize=9, label="node area = posts; arrow = author to target")]
    fig.legend(handles=h, loc="lower center", ncol=ncol, frameon=False, bbox_to_anchor=(0.5, y), fontsize=8.5)


def graphs():
    for key in ("r1/collective", "r2/collective", "r1/planner", "r2/planner"):
        fig, ax = plt.subplots(figsize=(7.2, 7.4), dpi=160)
        draw_graph(ax, key)
        graph_legend(fig, y=0.005, ncol=3)
        fig.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.11)
        fig.savefig(G / f"comm_graph_{key.replace('/', '_')}.png")
        plt.close(fig)
    fig, axs = plt.subplots(2, 2, figsize=(13.2, 13.2), dpi=150)
    for ax, key in zip(axs.ravel(), ("r1/collective", "r1/planner", "r2/collective", "r2/planner")):
        draw_graph(ax, key, compact=True)
    fig.suptitle("Communication graphs: collective vs planner, replicates r1 and r2", x=0.02, ha="left", fontsize=14, fontweight="bold")
    graph_legend(fig, y=0.012)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.05, hspace=0.14, wspace=0.03)
    fig.savefig(G / "comm_graphs_collective_vs_planner.png")
    plt.close(fig)


# ---------------------------------------------------------------- credits over time
NOTICE = [t("2026-11-01T09:46:41+00:00"), t("2026-11-01T09:50:39+00:00")]


def credits():
    for arm in ("single", "best_of_n", "collective", "planner"):
        fig, axs = plt.subplots(1, 2, figsize=(13, 5.4), dpi=150, sharey=True)
        for ax, run in zip(axs, ("r1", "r2")):
            keys = sorted(k for k in CUR if k.startswith(f"{run}/{arm}/"))
            xmin, xmax = None, None
            for i, k in enumerate(keys):
                c = CUR[k]
                pts = c["points"]
                xs = [t(c["start_utc"])] + [t(p[0]) for p in pts] + [t(c["end_utc"])]
                ys = [0] + [p[1] / 1000 for p in pts] + [pts[-1][1] / 1000]
                ag = k.split("/")[2]
                es = c["end_state"]
                lab = f"{ag} {es} {t(c['end_utc']).astimezone(EST).strftime('%H:%M')}"
                ax.step(xs, ys, where="post", color=AG[i], ls=LS[i], lw=1.8, label=lab, zorder=3)
                ax.scatter([xs[-1]], [ys[-1]], marker=END_MARK[es], s=62, color=AG[i], edgecolor="white", lw=0.6, zorder=4)
                xmin = min(xmin or xs[0], xs[0])
                xmax = max(xmax or xs[-1], xs[-1])
            q = CUR[keys[0]]["quota"] / 1000
            ax.axhline(q, color=MUTED, lw=1, ls=(0, (2, 2)), zorder=1)
            ax.text(xmin, q, f" quota {q:,.0f}k per agent", va="bottom", ha="left", fontsize=8.5, color=MUTED)
            pad = dt.timedelta(minutes=3)
            ax.set_xlim(xmin - pad, xmax + pad)
            for n, lbl in zip(NOTICE, ("notice 1", "notice 2")):
                if xmin < n < xmax:
                    ax.axvline(n, color=MUTED, lw=0.8, ls=":", zorder=1)
                    ax.text(n, 0.015, lbl + " ", rotation=90, fontsize=7.5, color=MUTED, va="bottom", ha="right", transform=ax.get_xaxis_transform())
            ax.set_title(f"{run} {ARM_NAME[arm]}")
            if f"{run}/{arm}" == "r2/planner":
                ax.text(0.02, 0.975, "p3 and p5 each transferred 30k to p1, so their limits are 390k and p1's is 480k", transform=ax.transAxes, fontsize=8, color=MUTED, va="top")
            ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 10), tz=EST))
            ax.xaxis.set_major_formatter(plt.FuncFormatter(clock_fmt()))
            ax.set_xlabel("Local time, EST")
            ax.grid(axis="y", color=GRID, lw=0.8)
            ax.set_axisbelow(True)
            ax.legend(frameon=False, fontsize=8.5, loc="lower right", title="agent, end state, time", title_fontsize=8.5)
        axs[0].set_ylabel("Credits used (thousands)")
        axs[0].set_ylim(bottom=0)
        fig.suptitle(f"Credits used over time, {ARM_NAME[arm]} arm (X capped, circle finished, square window closed)", x=0.01, ha="left", fontsize=12.5, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(G / f"credits_over_time_{arm}.png")
        plt.close(fig)


# ---------------------------------------------------------------- memory
EVENTS_MEM = [(est(3, 49, 57), "03:50 duplicate runners"), (est(4, 0, 13), "04:00 scheduler restart"), (est(4, 35), "04:35 guard v2"), (est(4, 40), "04:40 subscription back"),
              (est(4, 46, 41), "04:47 notice 1"), (est(4, 50, 39), "04:51 notice 2"), (est(5, 35, 49), "05:35 live intervention"), (est(6, 27, 15), "06:27 end"), (est(6, 50), "~06:50 unlock")]


def memory():
    ml = rj(B / "compute" / "memlog.jsonl")
    for r in ml:
        r["_t"] = dt.datetime.fromisoformat(r["t"]).replace(tzinfo=EST).astimezone(UTC)
    sch = rj(H / "metrics" / "scheduler.jsonl")
    for r in sch:
        r["_t"] = t(r["utc"])
    fig, axs = plt.subplots(3, 1, figsize=(13, 9.2), dpi=150, sharex=True, gridspec_kw={"height_ratios": [1.1, 1, 1], "hspace": 0.12})
    a = axs[0]
    a.plot([r["_t"] for r in ml], [r["commit_pct"] for r in ml], color=AG[0], lw=1.6)
    a.axhline(100, color=MUTED, lw=0.8, ls=":")
    a.axvspan(est(3, 44), est(4, 4), color="#D9DEE3", alpha=0.6, lw=0)
    a.text(est(3, 54), 58, "RUN_LOG reports\n94 to 98.6% commit;\nmemlog starts 04:06", ha="center", fontsize=8.5, color=INK)
    gone = [r["_t"] for r in ml for _ in (r.get("python_gone_ge1gb") if isinstance(r.get("python_gone_ge1gb"), list) else [r.get("python_gone_ge1gb")] if r.get("python_gone_ge1gb") else [])]
    a.scatter(gone, [36] * len(gone), marker="|", s=70, color=AG[1], label=f"Python process of 1 GB or more disappeared ({len(gone)})", zorder=3)
    a.set_ylabel("Memory commit (%)")
    a.set_ylim(30, 104)
    a.legend(frameon=False, fontsize=8.5, loc="upper right")
    b = axs[1]
    b.plot([r["_t"] for r in sch], [r["free_ram_gb"] for r in sch], color=AG[2], lw=1.3, ls="--", label="scheduler.jsonl (from launch)")
    b.plot([r["_t"] for r in ml], [r["free_ram_gb"] for r in ml], color=AG[0], lw=1.3, label="memlog.jsonl (from 04:06)")
    b.axhline(3.5, color=MUTED, lw=0.8, ls=":")
    b.text(est(7, 17), 3.55, "admission floor 3.5 GB (from 04:00)", fontsize=8, color=MUTED, va="bottom", ha="right")
    b.set_ylabel("Free RAM (GB)")
    b.set_ylim(0, 13.5)
    b.legend(frameon=False, fontsize=8.5, loc="upper right")
    c = axs[2]
    c.plot([r["_t"] for r in ml], [r["python"] for r in ml], color=AG[1], lw=1.3, ls="-.", label="python processes (memlog)")
    c.plot([r["_t"] for r in ml], [r["claude"] for r in ml], color=AG[0], lw=1.5, label="claude processes (memlog)")
    c.step([r["_t"] for r in sch], [r["running"] for r in sch], where="post", color=AG[2], lw=1.3, ls="--", label="running sessions (scheduler)")
    c.set_ylabel("Count")
    c.set_ylim(bottom=0)
    c.legend(frameon=False, fontsize=8.5, loc="upper right")
    c.set_xlabel("Local time, EST")
    c.set_xlim(est(3, 25), est(7, 18))
    c.xaxis.set_major_locator(mdates.MinuteLocator(byminute=(0, 30), tz=EST))
    c.xaxis.set_major_formatter(plt.FuncFormatter(clock_fmt()))
    for ax in axs:
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for e, _ in EVENTS_MEM:
            ax.axvline(e, color=INK, lw=0.7, ls=(0, (1, 2)), zorder=1)
    for e, lbl in EVENTS_MEM:
        a.text(e, 1.015, lbl, rotation=38, transform=a.get_xaxis_transform(), fontsize=8, ha="left", va="bottom", color=INK)
    fig.suptitle("Laptop memory over the night, with incident markers", x=0.01, y=0.985, ha="left", fontsize=13, fontweight="bold")
    fig.subplots_adjust(left=0.07, right=0.98, top=0.86, bottom=0.07)
    fig.savefig(G / "memory_with_incidents.png")
    plt.close(fig)


# ---------------------------------------------------------------- timeline
NIGHT = [(t("2026-11-01T04:52:46+00:00"), "00:52 EDT first launch\n38 sessions"), (t("2026-11-01T05:12:02+00:00"), "01:12 EDT last aborted-run log row"),
         (FALLBACK, "02:00 EDT clocks fall back to 01:00 EST"), (est(3, 32, 25), "03:32 relaunch"), (est(3, 49, 57), "03:50 duplicate runners"),
         (est(4, 0, 13), "04:00 scheduler restart"), (est(4, 35), "04:35 guard v2"), (est(4, 40), "04:40 subscription back"), (est(4, 46, 41), "04:47 notice 1"), (est(4, 50, 39), "04:51 notice 2"),
         (est(5, 35, 49), "05:35 intervention check,\nno leader"), (est(6, 27, 15), "06:27 all finished"), (est(6, 50), "~06:50 early unlock")]


def timeline():
    fig = plt.figure(figsize=(17, 15.5), dpi=150)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 6.2], hspace=0.27, left=0.085, right=0.985, top=0.945, bottom=0.075)
    a = fig.add_subplot(gs[0])
    a.barh(0, (t("2026-11-01T05:12:02+00:00") - t("2026-11-01T04:52:46+00:00")).total_seconds() / 86400, left=mdates.date2num(t("2026-11-01T04:52:46+00:00")), height=0.5, color="#9AA5B1")
    a.barh(0, (est(6, 27, 15) - est(3, 32, 25)).total_seconds() / 86400, left=mdates.date2num(est(3, 32, 25)), height=0.5, color=AG[0])
    a.text(est(4, 58), 0, "open run", color="white", ha="center", va="center", fontsize=9.5, fontweight="bold")
    a.text(t("2026-11-01T05:15:00+00:00"), 0, "aborted", ha="left", va="center", fontsize=8.5, color=MUTED)
    lv = [1, 1, 1, 1, 3.05, 1, 3.05, 1, 3.05, 1, 1, 1, 1]
    for (e, lbl), h in zip(NIGHT, lv):
        a.plot([e, e], [-0.25, h * 0.9 - 0.1], color=INK, lw=0.7, ls=(0, (1, 2)))
        rot = 32
        a.text(e, h * 0.9, lbl, fontsize=8, rotation=rot, ha="left", va="bottom", color=INK)
    a.set_ylim(-0.8, 5.5)
    a.set_yticks([])
    a.spines["left"].set_visible(False)
    a.set_xlim(t("2026-11-01T04:30:00+00:00"), t("2026-11-01T12:30:00+00:00"))
    a.xaxis.set_major_locator(mdates.MinuteLocator(byminute=(0, 30), tz=UTC))
    a.xaxis.set_major_formatter(plt.FuncFormatter(clock_fmt()))
    a.set_xlabel("Whole night, linear in real elapsed time. Local clock: EDT before the 02:00 fall-back, EST after (the 01:00 to 02:00 hour appears twice).")
    a.set_title("(a) The whole night", pad=4)
    b = fig.add_subplot(gs[1])
    ag = M["agents"]
    order = [(r, arm) for r in ("r1", "r2") for arm in ("collective", "planner", "best_of_n", "single")]
    y, yt, yl = 0, [], []
    for r, arm in order:
        keys = sorted(k for k in ag if k.startswith(f"{r}/{arm}/"))
        for k in keys:
            A = ag[k]
            st, en = t(A["first_start_utc"]), t(A["end_utc"])
            b.barh(y, (st + dt.timedelta(minutes=90) - st).total_seconds() / 86400, left=mdates.date2num(st), height=0.82, color="#EDF0F3", zorder=1, lw=0)
            sw = [(st, "subscription")] + [(t(x["utc"]), x["to"]) for x in A["billing_switches"]]
            sw.sort(key=lambda x: x[0])
            for i, (s0, src) in enumerate(sw):
                s1 = sw[i + 1][0] if i + 1 < len(sw) else en
                if s1 <= s0:
                    continue
                b.barh(y, (s1 - s0).total_seconds() / 86400, left=mdates.date2num(s0), height=0.58, zorder=2, lw=0,
                       color=AG[1] if src == "api" else AG[0], hatch="////" if src == "api" else None, edgecolor="white" if src == "api" else None)
            b.scatter([en], [y], marker=END_MARK[A["end_state"]], s=58, color=INK, edgecolor="white", lw=0.7, zorder=4)
            b.text(en + dt.timedelta(minutes=1.1), y, t(A["end_utc"]).astimezone(EST).strftime("%H:%M"), va="center", fontsize=7.5, color=MUTED, zorder=4)
            yt.append(y)
            yl.append(f"{r} {ARM_NAME[arm]} {A['agent']}")
            y += 1
        y += 0.8
    b.set_yticks(yt)
    b.set_yticklabels(yl, fontsize=8.2, color=INK)
    b.set_ylim(y - 0.3, -1.0)
    b.set_xlim(est(3, 25), est(7, 0))
    b.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 15), tz=EST))
    b.xaxis.set_major_formatter(plt.FuncFormatter(clock_fmt()))
    b.set_xlabel("Local time, EST")
    b.axvspan(est(3, 44), est(3, 58), color="#F6E3D7", alpha=0.75, lw=0, zorder=0)
    ev = [(est(3, 32, 25), "03:32 relaunch"), (est(3, 49, 57), "03:50 duplicates"), (est(4, 0, 13), "04:00 restart"), (est(4, 35), "04:35 guard v2"), (est(4, 40), "04:40 subscription back"),
          (est(4, 46, 41), "04:47 notice 1"), (est(4, 50, 39), "04:51 notice 2"), (est(5, 35, 49), "05:35 no-leader check"), (est(6, 27, 15), "06:27 end"), (est(6, 50), "~06:50 unlock")]
    for e, lbl in ev:
        b.axvline(e, color=INK, lw=0.7, ls=(0, (1, 2)), zorder=3)
        b.text(e, 1.004, lbl, rotation=32, ha="left", va="bottom", fontsize=8, transform=b.get_xaxis_transform(), color=INK)
    b.set_title("(b) Sessions, to scale", pad=46)
    h = [Patch(color="#EDF0F3", label="90-minute wall cap from the agent's own start"), Patch(color=AG[0], label="billing label: subscription"),
         Patch(facecolor=AG[1], hatch="////", edgecolor="white", label="billing label: API key"), Patch(color="#F6E3D7", label="03:44 to 03:58 incident window (metrics/incident_0350.json)"),
         Line2D([0], [0], marker="X", color="none", markerfacecolor=INK, markeredgecolor="white", markersize=9, label="capped"),
         Line2D([0], [0], marker="o", color="none", markerfacecolor=INK, markeredgecolor="white", markersize=8, label="finished"),
         Line2D([0], [0], marker="s", color="none", markerfacecolor=INK, markeredgecolor="white", markersize=8, label="window closed")]
    fig.legend(handles=h, frameon=False, loc="lower center", ncol=4, fontsize=8.5, bbox_to_anchor=(0.53, 0.005))
    b.grid(axis="x", color=GRID, lw=0.7)
    b.set_axisbelow(True)
    b.spines["left"].set_visible(False)
    b.tick_params(axis="y", length=0)
    fig.suptitle("Bone-twin open run: night of Nov 1, 2026", x=0.01, y=0.985, ha="left", fontsize=14, fontweight="bold")
    fig.savefig(OUT / "timeline.png")
    plt.close(fig)


if __name__ == "__main__":
    graphs()
    credits()
    memory()
    timeline()
    print("ok")
