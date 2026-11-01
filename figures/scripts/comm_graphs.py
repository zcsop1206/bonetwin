"""Figure 3: communication graphs, layout reused from analysis_process/scripts/make_figures.py (draw_graph), redrawn for this format.
Source: analysis_process/metrics.json runs.<key>.board (edges, posts_by_agent, degree_centralization, n_directive_posts,
degree_centralization_with_plain_id_mentions), same numbers as metrics.md section 4."""
import json
import math

from figlib import ANNOT, AP, BG, BLUE, FOOT, INK, LABEL, MUTED, ORANGE, axes_in, frame, new, save
from matplotlib.lines import Line2D

KEYS = ["r1/collective", "r2/collective", "r1/planner", "r2/planner"]
BRIEF = {"r1/collective": (0.30, 3), "r2/collective": (0.40, 1), "r1/planner": (1.00, 15), "r2/planner": (1.00, 16)}
E_STYLE = {"reply": ("-", 0.10), "mention": ((0, (4, 2.5)), 0.26), "transfer": ((0, (1, 1.5)), 0.42)}
NAME = {"r1/collective": "Collective r1", "r2/collective": "Collective r2", "r1/planner": "Planner r1", "r2/planner": "Planner r2"}


def e_width(c):
    return 0.8 + 0.55 * math.sqrt(c)


def draw_graph(ax, key, M, node_k):
    r = M["runs"][key]["board"]
    nodes = sorted({a.split("/")[2] for a in M["agents"] if a.startswith(key + "/")})
    n = len(nodes)
    pos = {v: (math.cos(2 * math.pi * i / n + math.pi / 2), math.sin(2 * math.pi * i / n + math.pi / 2)) for i, v in enumerate(nodes)}
    size = {v: node_k * (360 + 30 * r["posts_by_agent"].get(v, 0)) for v in nodes}
    fill = ORANGE if "collective" in key else BLUE
    for e in sorted(r["edges"], key=lambda e: -e["count"]):
        ls, rad = E_STYLE[e["type"]]
        ax.annotate("", xy=pos[e["target"]], xytext=pos[e["source"]], zorder=2,
                    arrowprops=dict(arrowstyle="-|>,head_length=0.38,head_width=0.2", color=INK, lw=e_width(e["count"]), linestyle=ls, alpha=0.9,
                                    connectionstyle=f"arc3,rad={rad}", shrinkA=math.sqrt(size[e["source"]]) / 2 + 1, shrinkB=math.sqrt(size[e["target"]]) / 2 + 1))
    for v in nodes:
        ax.scatter(*pos[v], s=size[v], color=fill, edgecolor=BG, lw=1.5, zorder=3)
        ax.text(*pos[v], v, ha="center", va="center", color="white" if fill == ORANGE else INK, fontsize=ANNOT - 1, fontweight="bold", zorder=4)
    ax.set_xlim(-1.22, 1.22)
    ax.set_ylim(-1.22, 1.22)
    ax.set_aspect("equal")
    ax.axis("off")


def draw(fmt):
    M = json.loads((AP / "metrics.json").read_text(encoding="utf-8"))
    for k, (dc, dr) in BRIEF.items():
        b = M["runs"][k]["board"]
        assert round(b["degree_centralization"], 2) == dc and b["n_directive_posts"] == dr, k
    plain = [M["runs"][k]["board"]["degree_centralization_with_plain_id_mentions"] for k in KEYS]
    assert [round(p, 2) for p in plain] == [0.10, 0.10, 0.60, 0.50], plain
    fig = new(fmt)
    fig.canvas.draw()
    foot = ("Degree centralization is the harness measure: Freeman, undirected, 1.00 is a star, counting @mentions and replies (and the 2 credit transfers on planner r2). "
            f"It does not count bare ids such as c3 or c1 -> c2, which is how the collective boards usually address each other. Counting bare ids changes the values, in panel order, to "
            f"{plain[0]:.2f}, {plain[1]:.2f}, {plain[2]:.2f}, {plain[3]:.2f} (metrics.md section 4). Bare ids can also be references, not addresses. "
            "Directive posts: harness rule, kind 'assign' or an imperative @mention. Planner arms had an assigned lead, p1.")
    l, b, r, t = frame(fig, "Who addressed whom: collective vs planner, replicates r1 and r2", foot)
    leg_h = 0.42
    b += leg_h
    if fmt == "slide":
        n_cols, n_rows = 4, 1
        node_k = 0.9
    else:
        n_cols, n_rows = 2, 2
        node_k = 0.95
    cw = (r - l) / n_cols
    ch = (t - b) / n_rows
    for i, key in enumerate(KEYS):
        ci, ri = i % n_cols, i // n_cols
        x0, y1 = l + ci * cw, t - ri * ch
        y0 = y1 - ch
        bd = M["runs"][key]["board"]
        if fmt == "slide":  # graph over stats
            ax = axes_in(fig, x0, y0 + 1.0, x0 + cw, y1 - 0.4)
            tx, ty, va, ha = x0 + 0.1, y0 + 0.95, "top", "left"
            hx = x0 + 0.1
        else:  # graph beside stats
            ax = axes_in(fig, x0 + 1.75, y0 + 0.02, x0 + cw, y1 - 0.02)
            tx, ty, va, ha = x0, y1 - 1.0, "top", "left"
            hx = x0
        draw_graph(ax, key, M, node_k)
        W, H = fig.get_size_inches()
        fig.text(hx / W, (y1 - 0.02 if fmt == "slide" else y1 - 0.25) / H, NAME[key], fontsize=LABEL + 1, fontweight="bold", va="top", ha="left")
        fig.text(tx / W, ty / H, f"{bd['degree_centralization']:.2f}", fontsize=30, fontweight="bold", va="top", ha=ha)
        fig.text(tx / W, (ty - 0.47) / H, "degree centralization", fontsize=ANNOT - 1, va="top", ha=ha, color=INK) if fmt == "letter" else None
        if fmt == "slide":
            fig.text((tx + 1.32) / W, ty / H, f"{bd['n_directive_posts']}", fontsize=30, fontweight="bold", va="top", ha=ha)
            fig.text(tx / W, (ty - 0.47) / H, "centralization", fontsize=ANNOT - 2, va="top", ha=ha)
            fig.text((tx + 1.32) / W, (ty - 0.47) / H, "directive posts", fontsize=ANNOT - 2, va="top", ha=ha)
        else:
            fig.text(tx / W, (ty - 0.78) / H, f"{bd['n_directive_posts']}", fontsize=30, fontweight="bold", va="top", ha=ha)
            fig.text(tx / W, (ty - 1.25) / H, "directive posts", fontsize=ANNOT - 1, va="top", ha=ha)
    h = [Line2D([], [], color=INK, lw=2.4, ls=E_STYLE[k][0], label=k) for k in ("reply", "mention", "transfer")]
    h += [Line2D([], [], color=INK, lw=e_width(c), label=f"{c} link" + ("s" if c > 1 else "")) for c in (1, 12)]
    h += [Line2D([], [], marker="o", ls="", color=MUTED, ms=12, label="node area = posts; arrow = author to target")]
    fig.legend(handles=h, loc="lower left", bbox_to_anchor=(l / W - 0.008, (b - leg_h) / H), ncol=6, fontsize=ANNOT - 2, columnspacing=1.0, handlelength=1.8, handletextpad=0.4)
    save(fig, "comm_graphs", fmt)


if __name__ == "__main__":
    for f in ("letter", "slide"):
        draw(f)
