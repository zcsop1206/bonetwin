"""Figure 6: rubric weights with an evidence pointer per row. Weights and pointers are as given in the figure brief.
No self-scoring and no claim about results."""
from figlib import ANNOT, BG, BLUE, FOOT, GRID, INK, LABEL, MUTED, axes_in, frame, new, save

ROWS = [("Impact", 25, "Stiffness ladder and printed parts"),
        ("Collective capability", 25, "Arm results and contest"),
        ("Significance", 20, "Sole-writer failure"),
        ("Decentralized agency", 20, "Communication graphs"),
        ("Working system and validation", 10, "Session timeline")]
assert sum(w for _, w, _ in ROWS) == 100


def draw(fmt):
    fig = new(fmt)
    fig.canvas.draw()
    l, b, r, t = frame(fig, "Rubric weights and where the evidence is", "Bar length is the hackathon rubric weight, total 100. Pointers name where to look; they are not scores.")
    lab = 3.35 if fmt == "slide" else 2.75
    pw = 3.6 if fmt == "slide" else 2.6
    ev = 4.2 if fmt == "slide" else 3.45
    ax = axes_in(fig, l + lab, b + 0.2, r - ev, t - 0.5)
    ax.set_xlim(0, 25)
    ax.set_ylim(4.55, -0.55)
    n = len(ROWS)
    for i, (name, w_, ptr) in enumerate(ROWS):
        ax.barh(i, w_, height=0.56, color=BLUE, edgecolor="none", zorder=2)
        ax.text(w_ - 0.6, i, f"{w_}", ha="right", va="center", fontsize=LABEL + 5, fontweight="bold", color=INK, zorder=3)
    ax.set_yticks(range(n))
    ax.set_yticklabels(["\n".join(_two(nm)) for nm, _, _ in ROWS], fontsize=LABEL + 1, linespacing=1.05)
    ax.tick_params(axis="y", length=0, pad=10)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_color(INK)
    for i, (_, _, ptr) in enumerate(ROWS):
        ax.annotate("\n".join(_wrap_ptr(ptr, fmt)), xy=(1, i), xycoords=ax.get_yaxis_transform(), xytext=(26, 0), textcoords="offset points", va="center", ha="left", fontsize=LABEL + 1, linespacing=1.08, annotation_clip=False)
    ax.text(0, 1.03, "Weight", transform=ax.transAxes, fontsize=ANNOT, color=MUTED, va="bottom", ha="left")
    ax.annotate("Evidence", xy=(1, 1.03), xycoords=ax.transAxes, xytext=(26, 0), textcoords="offset points", fontsize=ANNOT, color=MUTED, va="bottom", ha="left", annotation_clip=False)
    save(fig, "rubric_map", fmt)


def _two(nm):
    return {"Working system and validation": ["Working system", "and validation"], "Collective capability": ["Collective", "capability"], "Decentralized agency": ["Decentralized", "agency"]}.get(nm, [nm])


def _wrap_ptr(p, fmt):
    if p.startswith("Stiffness"):
        return ["Stiffness ladder", "and printed parts"]
    return [p]


if __name__ == "__main__":
    for f in ("letter", "slide"):
        draw(f)
