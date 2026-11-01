"""Figure 1: log-scale modulus ladder.

    python stiffness_ladder.py [--designs designs.json] [--ti path] [--outdir dir]

Titanium: figures/ti_modulus.json = {"value_gpa": <number>, "cite": "<citation>"}. Until that file exists and is valid the
figure shows a marked placeholder with no number and no position. Re-run this script to pick it up.

--designs (optional, default none): JSON list of final designs to place on the ladder, each
    {"label": "r1 best-of-N", "value_mpa": 123.0, "note": "optional short text"}

Sources:
  measured   harness/measured.json E_rigid10k_flat_form4, E_tough1500_flat_studio1 (GPa); analysis/results_all.csv strain_source
  datasheet  sim/EVAL_SPEC_v1.md section 5a ([S9] Rigid 10K page, [S2] Tough 1500 V2 page)
  bone       targets/SOURCES.md "Results" table (E1, E2, E3 apparent moduli) and "Sources opened" row Morgan2018
"""
import argparse
import csv
import json
from pathlib import Path

from figlib import ANNOT, B, BLUE, FIG, FOOT, GRID, INK, LABEL, MUTED, ORANGE, axes_in, frame, new, save
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, NullFormatter

BONE = "#3C424C"


def load_inputs(ti_path):
    m = json.loads((B / "harness" / "measured.json").read_text(encoding="utf-8"))
    rigid, tough = m["E_rigid10k_flat_form4"] * 1000, m["E_tough1500_flat_studio1"] * 1000
    assert round(rigid) == 8018 and round(tough) == 1136, (rigid, tough)
    rows = list(csv.DictReader((B / "analysis" / "results_all.csv").open(encoding="utf-8-sig")))
    for g in ("E_rigid10k_flat_form4", "E_tough1500_flat_studio1"):
        spec = [r for r in rows if r["row_type"] == "specimen" and r["group"] == g]
        assert len(spec) == 1 and spec[0]["strain_source"] == "crosshead", g
    src = (B / "targets" / "SOURCES.md").read_text(encoding="utf-8")
    assert "| Femoral head (MPa) | 1143 | 1589 | 2209 |" in src and "| Lumbar vertebra (MPa) | 204 | 236 | 714 |" in src
    assert "E longitudinal 17.9 ± 3.9 GPa" in src and "Trabecular tissue modulus 10–20 GPa" in src
    ti = None
    p = Path(ti_path)
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        if isinstance(d.get("value_gpa"), (int, float)) and d["value_gpa"] > 0 and str(d.get("cite", "")).strip():
            ti = {"value": float(d["value_gpa"]) * 1000, "gpa": d["value_gpa"], "cite": str(d["cite"]).strip()}
        else:
            print("ti_modulus.json present but incomplete; keeping the placeholder")
    return rigid, tough, ti


def draw(fmt, designs, ti_path, outdir):
    rigid, tough, ti = load_inputs(ti_path)
    fig = new(fmt)
    fig.canvas.draw()
    foot = ("Measured: crosshead-only strain, one flat Type V dog-bone each (Rigid 10K on Form 4, Tough 1500 V2 on Form Studio 1). Machine compliance biases "
            "crosshead E low; Tough 1500 also disagrees about 2x with video-tracked strain on another dog-bone (EVAL_SPEC_v1, 5a). Datasheet: Formlabs product pages, with cure and print conditions not confirmed for these parts. "
            "Trabecular E1, E2, E3: apparent moduli of the porous block along its three orthotropic axes, computed from published fits, not measured here "
            "(femoral head, Simon 2025, tissue E 10 GPa; lumbar, Oefner 2021, tissue E 15 GPa). Tissue: the solid trabecular material (Morgan 2018, Section 2.2). "
            "Cortical: femoral, longitudinal (Morgan 2018, Table 1).")
    if ti:
        foot += f" Titanium: {ti['cite']}."
    l, b, r, t = frame(fig, "Stiffness ladder: printed resins and bone", foot)
    lab_w = 3.05 if fmt == "slide" else 2.75
    ax = axes_in(fig, l + lab_w, b + 1.12, r, t)
    ax.set_xscale("log")
    ax.set_xlim(100, 400000)

    rows = ["Titanium", "Femoral cortical bone", "Trabecular tissue", "Rigid 10K resin", "Femoral head trabecular,\napparent", "Tough 1500 V2 resin", "Lumbar trabecular,\napparent"]
    rows += [d["label"] for d in designs]
    y = {name: i for i, name in enumerate(rows)}
    ax.set_ylim(len(rows) - 0.45, -0.55)
    ax.set_yticks(list(y.values()))
    ax.set_yticklabels(rows, fontsize=LABEL - 1, color=INK, linespacing=1.05)
    ax.tick_params(axis="y", length=0, pad=8)
    ax.spines["left"].set_visible(False)
    ax.xaxis.set_major_locator(FixedLocator([100, 1000, 10000, 100000]))
    ax.xaxis.set_minor_locator(FixedLocator([v * k for v in (100, 1000, 10000, 100000) for k in range(2, 10) if v * k <= 400000]))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xticklabels(["100 MPa", "1 GPa", "10 GPa", "100 GPa"], fontsize=LABEL - 1)
    ax.grid(axis="x", which="major", color=GRID, lw=1.2)
    ax.set_axisbelow(True)
    ax.set_xlabel("Elastic modulus (log scale)", fontsize=ANNOT)

    def note(row, x, s, right=False):
        ax.annotate(s, (x, y[row]), xytext=(-12 if right else 12, 0), textcoords="offset points", ha="right" if right else "left", va="center", fontsize=ANNOT, color=INK, zorder=6, bbox=dict(fc="#F6F3EC", ec="none", pad=1.5))

    def meas(row, v):
        ax.scatter([v], [y[row]], s=190, marker="o", color=ORANGE, edgecolor=BG_RING, lw=1.4, zorder=5)

    def sheet(row, v):
        ax.scatter([v], [y[row]], s=190, marker="D", color=BLUE, edgecolor=BG_RING, lw=1.4, zorder=5)

    def bone(row, vals):
        ax.plot([min(vals), max(vals)], [y[row]] * 2, color=BONE, lw=2.5, zorder=3, solid_capstyle="butt")
        ax.scatter(vals, [y[row]] * len(vals), s=120, marker="s", color=BONE, edgecolor=BG_RING, lw=1.2, zorder=5)

    # titanium
    if ti:
        ax.scatter([ti["value"]], [y["Titanium"]], s=210, marker="^", color=INK, edgecolor=BG_RING, lw=1.2, zorder=5)
        note("Titanium", ti["value"], f"{ti['gpa']:g} GPa", right=True)
    else:
        yy = y["Titanium"]
        ax.axhspan(yy - 0.3, yy + 0.3, facecolor="none", edgecolor=INK, lw=1.4, ls=(0, (5, 4)), zorder=2)
        ax.text(0.5, yy, "PLACEHOLDER: value pending citation, position not plotted", transform=ax.get_yaxis_transform(), ha="center", va="center", fontsize=ANNOT, fontweight="bold", color=INK)

    # cortical with the source's spread
    c = y["Femoral cortical bone"]
    ax.plot([14000, 21800], [c, c], color=BONE, lw=2.5, zorder=3)
    for e in (14000, 21800):
        ax.plot([e, e], [c - 0.14, c + 0.14], color=BONE, lw=2.5, zorder=3)
    ax.scatter([17900], [c], s=120, marker="s", color=BONE, edgecolor=BG_RING, lw=1.2, zorder=5)
    ax.annotate("17.9 ± 3.9 GPa", (14000, c), xytext=(-12, 0), textcoords="offset points", ha="right", va="center", fontsize=ANNOT, bbox=dict(fc="#F6F3EC", ec="none", pad=1.5))

    # trabecular tissue range
    ty = y["Trabecular tissue"]
    ax.plot([10000, 20000], [ty, ty], color=BONE, lw=9, zorder=3, solid_capstyle="butt")
    note("Trabecular tissue", 10000, "10–20 GPa, literature range", right=True)

    # resins
    meas("Rigid 10K resin", rigid)
    sheet("Rigid 10K resin", 11000)
    note("Rigid 10K resin", rigid, "measured 8018, datasheet 11000 MPa", right=True)
    meas("Tough 1500 V2 resin", tough)
    sheet("Tough 1500 V2 resin", 1460)
    note("Tough 1500 V2 resin", 1460, "measured 1136, datasheet 1460 MPa")

    # trabecular apparent
    fh = "Femoral head trabecular,\napparent"
    bone(fh, [1143, 1589, 2209])
    note(fh, 2209, "E1 1143, E2 1589, E3 2209 MPa")
    lv = "Lumbar trabecular,\napparent"
    bone(lv, [204, 236, 714])
    note(lv, 714, "E1 204, E2 236, E3 714 MPa")

    for d in designs:
        ax.scatter([d["value_mpa"]], [y[d["label"]]], s=210, marker="*", color=INK, edgecolor=BG_RING, lw=0.8, zorder=5)
        note(d["label"], d["value_mpa"], f"{d['value_mpa']:g} MPa" + (f", {d['note']}" if d.get("note") else ""))

    h = [Line2D([], [], marker="o", ls="", color=ORANGE, ms=13, label="measured, crosshead only"),
         Line2D([], [], marker="D", ls="", color=BLUE, ms=11, label="datasheet"),
         Line2D([], [], marker="s", ls="", color=BONE, ms=11, label="bone, from sources")]
    fig.legend(handles=h, loc="lower left", bbox_to_anchor=((l + lab_w - 0.1) / fig.get_size_inches()[0], (b - 0.04) / fig.get_size_inches()[1]), ncol=3, fontsize=ANNOT, handletextpad=0.2, columnspacing=1.2)
    save(fig, "stiffness_ladder", fmt, outdir)


BG_RING = "#F6F3EC"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--designs", help="optional JSON list of final designs; default none")
    ap.add_argument("--ti", default=str(FIG / "ti_modulus.json"))
    ap.add_argument("--outdir")
    a = ap.parse_args()
    ds = json.loads(Path(a.designs).read_text(encoding="utf-8")) if a.designs else []
    for f in ("letter", "slide"):
        draw(f, ds, a.ti, a.outdir)
