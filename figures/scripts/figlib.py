"""Shared style and output for the pitch figure set. Inputs are read only; everything is written to figures/.

Palette checked with the dataviz validator on #F6F3EC (orange/blue: deutan delta-E 22, contrast >= 3:1). In greyscale
orange is L* ~45 and blue is L* ~58, and every colour use also carries a shape, line style or direct label.
"""
import ctypes
import datetime as dt
import os
import sys
from ctypes import wintypes
from pathlib import Path

sys.dont_write_bytecode = True
FIG = Path(__file__).resolve().parents[1]
B = FIG.parent
AP = B / "analysis_process"
HO = B / "harness_open"
os.environ.setdefault("MPLCONFIGDIR", str(FIG / "scripts" / ".mplcache"))

try:  # below-normal priority: the laptop is shared with running jobs
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
except Exception:
    pass

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

BG, INK, MUTED, GRID = "#F6F3EC", "#14181F", "#565B63", "#DDD8CC"
ORANGE, BLUE, GREY = "#B5471A", "#4F8FC6", "#8A8D92"
SIZES = {"letter": (11.0, 8.5), "slide": (4000 / 300, 7.5)}
TITLE, LABEL, ANNOT, FOOT = 24, 17, 15, 12.5
MARGIN = 0.42  # inches

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "pdf.fonttype": 42, "ps.fonttype": 42, "font.size": ANNOT,
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 1.0,
    "xtick.labelsize": ANNOT, "ytick.labelsize": ANNOT, "axes.labelsize": ANNOT, "legend.frameon": False, "legend.fontsize": ANNOT,
})
EST = dt.timezone(dt.timedelta(hours=-5))


def minutes(iso):
    """Minutes after 00:00 local EST for an ISO timestamp; every time on these figures is after the fall-back."""
    d = dt.datetime.fromisoformat(iso).astimezone(EST)
    return d.hour * 60 + d.minute + d.second / 60


def hms(h, m, s=0):
    return h * 60 + m + s / 60


def clock(x, secs=False):
    t = int(round(x * 60))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}" + (f":{t % 60:02d}" if secs else "")


def _width_in(fig, s, fs, weight="normal"):
    r = fig.canvas.get_renderer()
    w, _, _ = r.get_text_width_height_descent(s, FontProperties(size=fs, weight=weight), False)
    return w / fig.dpi


def wrap(fig, s, fs, width_in):
    lines, cur = [], ""
    for word in s.split():
        trial = (cur + " " + word).strip()
        if _width_in(fig, trial, fs) <= width_in or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def new(fmt):
    w, h = SIZES[fmt]
    return plt.figure(figsize=(w, h), dpi=100)


def frame(fig, title, foot=None, subtitle=None):
    """Draw the title and footnote; return (left, bottom, right, top) in inches of the free plot region."""
    w, h = fig.get_size_inches()
    top = h - MARGIN
    tlines = wrap(fig, title, TITLE, w - 2 * MARGIN)
    for ln in tlines:
        fig.text(MARGIN / w, top / h, ln, fontsize=TITLE, fontweight="bold", va="top", ha="left", color=INK)
        top -= TITLE * 1.2 / 72
    if subtitle:
        for ln in wrap(fig, subtitle, ANNOT + 1, w - 2 * MARGIN):
            fig.text(MARGIN / w, (top - 0.03) / h, ln, fontsize=ANNOT + 1, va="top", ha="left", color=MUTED)
            top -= (ANNOT + 1) * 1.25 / 72
    bottom = 0.30
    if foot:
        lines = wrap(fig, foot, FOOT, w - 2 * MARGIN)
        fig.text(MARGIN / w, bottom / h, "\n".join(lines), fontsize=FOOT, va="bottom", ha="left", color=MUTED, linespacing=1.22)
        bottom += len(lines) * FOOT * 1.22 * 1.15 / 72 + 0.1
    return MARGIN, bottom, w - MARGIN, top - 0.12


def axes_in(fig, l, b, r, t, **kw):
    w, h = fig.get_size_inches()
    return fig.add_axes([l / w, b / h, (r - l) / w, (t - b) / h], **kw)


def save(fig, name, fmt, outdir=None):
    out = Path(outdir) if outdir else FIG
    out.mkdir(parents=True, exist_ok=True)
    stem = out / f"{name}_{fmt}"
    fig.savefig(str(stem) + ".png", dpi=300)
    fig.savefig(str(stem) + ".pdf")
    plt.close(fig)
    print("wrote", stem)
