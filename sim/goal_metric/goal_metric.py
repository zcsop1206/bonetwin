"""goal_metric.py: supplementary, post-registered, exploratory metric of EVAL_SPEC_v1_addendum4_goalmetric.md.

The implant region (its convex hull R, no surrounding bone) is strained through its hull surface along all 6 strain
directions, once with empty voids (no ingrowth) and once with voids = 1.0 x C_bone (fused). Strain energy is split over
~5 mm windows, giving each window a stiffness tensor C_W that averages exactly to the region's C_eff. For each window,
D_W = worst-direction |ln(stiffness / bone stiffness)|. Q_state = hull-volume-weighted RMS of D_W. M = max(Q_alone, Q_fused).

One mesh:  python goal_metric.py --mesh implant.stl --material tough1500 --out result.json
A folder:  python goal_metric.py --folder <dir> --out <dir_out> --workers 4 --threads 2
Imports the frozen judge read-only. Never writes to sim/judge.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "judge"))
import judge as J  # noqa: E402  (sets below-normal priority on Windows and caps BLAS threads via JUDGE_THREADS)
import numpy as np  # noqa: E402
import scipy.linalg as sl  # noqa: E402
import scipy.sparse as sp  # noqa: E402
from scipy import ndimage  # noqa: E402

fe, jg = J.fe, J.jg
WINDOW_MM = 5.0         # bone's continuum scale, assumed (see the addendum)
MIN_WINDOW_HULL = 0.25  # a window with less hull than this fraction of its nominal volume is not scored
LAMBDA_FLOOR = 1e-3     # stiffness ratios below this are read as this: D_W is capped at ln(1000) = 6.9
MIN_HULL_FILL = 0.5     # gate: hull volume / bounding-box volume
LEVELS = 24             # same stiffness quantisation as judge_fe.assemble


def unit_strains():
    """Voigt [e11 e22 e33 g23 g13 g12] unit vectors as symmetric strain tensors."""
    out = []
    for i, j in fe.VOIGT:
        e = np.zeros((3, 3))
        if i == j:
            e[i, i] = 1.0
        else:
            e[i, j] = e[j, i] = 0.5      # engineering shear = 1
        out.append(e)
    return out


def geometry(tm, man, h):
    n, origin = jg.make_box(tm, h, factor=1.0)
    sub = int(np.ceil(h / J.SUB_H - 1e-9))
    frac = jg.occupancy(man, n, origin, h, sub)
    hull = np.maximum(jg.occupancy(man.hull(), n, origin, h, sub), frac)
    return n, origin, frac, hull, sub


def solve_state(n, origin, frac, hull, h, C_bone, C_imp, g):
    """Hull-surface displacement BC, epsilon_i . x, for the 6 unit strains. Returns U (nd x 6) plus the element data."""
    box = fe.Box(n, h, origin)
    L = LEVELS
    fa = frac.ravel(); fc = hull.ravel()
    ia = np.rint(fa * L).astype(int); ia[(fa > 1e-6) & (ia == 0)] = 1
    bf = g * (fc - fa)
    ib = np.rint(bf * L).astype(int); ib[(bf > 1e-6) & (ib == 0)] = 1
    keep = (ia > 0) | (ib > 0)
    # surface nodes: touch a voxel with hull fill < 0.5, or the outside of the grid
    inside = np.pad(hull >= 0.5, 1, constant_values=False)
    interior = (inside[:-1, :-1, :-1] & inside[1:, :-1, :-1] & inside[:-1, 1:, :-1] & inside[:-1, :-1, 1:]
                & inside[1:, 1:, :-1] & inside[1:, :-1, 1:] & inside[:-1, 1:, 1:] & inside[1:, 1:, 1:])
    surf_node = ~interior.ravel()
    # face-connected pieces with no surface node cannot carry anything: dropped (they carry zero energy anyway)
    lab, nc = ndimage.label(keep.reshape(frac.shape))
    lab = lab.ravel()
    e0 = np.nonzero(keep)[0]
    if len(e0) == 0:
        return None
    cn0 = box.conn(e0)
    has = np.zeros(nc + 1, bool)
    has[lab[e0][surf_node[cn0].any(axis=1)]] = True
    ok = has[lab[e0]]
    dropped = float(fa[e0[~ok]].sum() * h ** 3)
    elems = e0[ok]; cn = cn0[ok]
    if len(elems) == 0:
        return None
    ia = ia[elems]; ib = ib[elems]
    used, inv = np.unique(cn, return_inverse=True)
    cl = inv.reshape(cn.shape)
    dofs = ((3 * cl[:, :, None] + np.arange(3)).reshape(len(cn), 24)).astype(np.int32)
    nd = 3 * len(used)
    Ke_i = fe.ke(h, C_imp); Ke_b = fe.ke(h, C_bone)
    q = ia * (L + 1) + ib
    Ke_stack = np.stack([Ke_i * (i / L) + Ke_b * (j / L) for i in range(L + 1) for j in range(L + 1)])
    K = fe.assemble_K(Ke_stack, q, dofs, nd)
    xyz = box.node_ijk(used) * h + box.origin
    x0 = xyz - (np.asarray(origin) + np.asarray(n) * h / 2)
    surf = surf_node[used]
    pdof = np.nonzero(np.repeat(surf, 3))[0]; fdof = np.nonzero(np.repeat(~surf, 3))[0]
    Ubc = np.zeros((nd, 6))
    for c, e in enumerate(unit_strains()):
        Ubc[:, c] = (x0 @ e).ravel()
    U = Ubc.copy()
    slog = []
    if len(fdof):
        Kf = K[fdof]
        Kff = Kf[:, fdof].tocsr()
        rhs = -np.asarray(Kf[:, pdof] @ Ubc[pdof])
        # hinge-only attachments leave rigid modes: a 1e-9 relative shift keeps K_ff positive definite
        Kff = (Kff + sp.diags(np.full(Kff.shape[0], 1e-9 * Kff.diagonal().mean()))).tocsr()
        Xf, _ = fe.solve(Kff, rhs, np.zeros(0, int), log=slog, xyz=xyz[~surf])
        U[fdof] = Xf
    return {"box": box, "elems": elems, "dofs": dofs, "a": fa[elems].astype(float), "b": bf[elems].astype(float), "U": U, "Ke_i": Ke_i, "Ke_b": Ke_b, "nd": nd,
            "free_dofs": int(len(fdof)), "solver_log": slog, "dropped_mm3": dropped}


def windows(n, h):
    k = max(1, int(round(WINDOW_MM / h)))
    nw = [max(1, int(round(int(m) / k))) for m in n]
    return k, nw


def window_index(elems, box, k, nw):
    nx, ny = box.nx, box.ny
    i = np.minimum((elems % nx) // k, nw[0] - 1)
    j = np.minimum(((elems // nx) % ny) // k, nw[1] - 1)
    l = np.minimum((elems // (nx * ny)) // k, nw[2] - 1)
    return i + nw[0] * (j + nw[1] * l)


def stiffness_ratio(C, C_bone):
    return sl.eigh(0.5 * (C + C.T), C_bone, eigvals_only=True)


def worst_log(C, C_bone):
    lam = np.maximum(stiffness_ratio(C, C_bone), LAMBDA_FLOOR)
    return float(np.abs(np.log(lam)).max()), lam


def score_state(st, hull, h, C_bone):
    """Energy partition: C_W = sum_e u_i^T Ke u_j / V_W. It sums to C_eff exactly."""
    box = st["box"]
    n = (box.nx, box.ny, box.nz)
    k, nw = windows(n, h)
    NW = int(np.prod(nw))
    allc = np.arange(hull.size)
    vw = np.bincount(window_index(allc, box, k, nw), hull.ravel().astype(float) * h ** 3, minlength=NW)
    W = np.zeros((NW, 6, 6))
    win = window_index(st["elems"], box, k, nw)
    U = st["U"]
    for a in range(0, len(st["elems"]), 50000):
        b = min(a + 50000, len(st["elems"]))
        ue = U[st["dofs"][a:b]]                                    # e x 24 x 6
        wi = np.einsum("eak,eal->ekl", ue, st["Ke_i"] @ ue)
        wb = np.einsum("eak,eal->ekl", ue, st["Ke_b"] @ ue)
        we = st["a"][a:b, None, None] * wi + st["b"][a:b, None, None] * wb   # exact fractions, not K's 1/24 quantisation
        np.add.at(W, win[a:b], we)
    V = vw.sum()
    C_eff = W.sum(axis=0) / V
    D_eff, lam_eff = worst_log(C_eff, C_bone)
    nominal = (k * h) ** 3
    scored = vw >= MIN_WINDOW_HULL * nominal
    if not scored.any():
        scored = vw > 0
    D = np.array([worst_log(W[m] / vw[m], C_bone)[0] for m in np.nonzero(scored)[0]])
    wgt = vw[scored]
    Q = float(np.sqrt((wgt * D ** 2).sum() / wgt.sum()))
    return {"Q": Q, "D_eff": D_eff, "lambda_eff": [float(x) for x in lam_eff], "windows_scored": int(scored.sum()),
            "windows_total": NW, "D_window_max": float(D.max()), "D_window_min": float(D.min()),
            "windows_at_floor": int((D >= -np.log(LAMBDA_FLOOR) - 1e-9).sum()),
            "hull_volume_mm3": float(V), "C_eff_MPa": C_eff.round(3).tolist(), "dofs": st["nd"], "free_dofs": st["free_dofs"],
            "dropped_islands_mm3": st["dropped_mm3"], "cg_iters": [s["cg_iters"] for s in st["solver_log"]],
            "cg_info": [s["info"] for s in st["solver_log"]]}, C_eff


def integrity(st, C_eff, frac, C_imp, C_bone, cases, strength):
    """The implant alone carries each whole case: apparent strain = C_eff^-1 sigma, fields by superposition.
    Same statistic and factor as G1: p99.5 von Mises at 2x load <= strength / 2."""
    lam = stiffness_ratio(C_eff, C_bone)
    if lam.min() < LAMBDA_FLOOR:
        return {"pass": False, "reason": f"implant alone has almost no stiffness in some direction (lambda_min {lam.min():.2e})",
                "worst_p995_MPa_2x": None, "allow_MPa": strength / 2}
    a = frac.ravel()[st["elems"]]
    solid = a >= 0.5
    if not solid.any():
        return {"pass": False, "reason": "no voxel at least half filled", "worst_p995_MPa_2x": None, "allow_MPa": strength / 2}
    B0 = fe.bmat(st["box"].h, 0, 0, 0)
    Si = np.linalg.inv(C_eff)
    res = []
    for _, sig, _ in cases:
        sv = np.array([sig[i, j] for i, j in fe.VOIGT])
        u = st["U"] @ (Si @ sv)
        eps = u[st["dofs"][solid]] @ B0.T
        vm = fe.von_mises(eps @ C_imp.T)
        res.append(2 * float(np.percentile(vm, 99.5)))
    worst = max(res)
    return {"pass": bool(worst <= strength / 2), "p995_MPa_2x_by_case": res, "worst_p995_MPa_2x": worst,
            "allow_MPa": strength / 2, "reason": None}


def peak_rss_gb():
    """Peak memory of this process, measured, for the cost table. None if the platform will not say."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                            ("d", ctypes.c_size_t), ("e", ctypes.c_size_t), ("f", ctypes.c_size_t)]
            pm = PMC(); pm.cb = ctypes.sizeof(PMC)
            k = ctypes.windll.kernel32; k.GetCurrentProcess.restype = wintypes.HANDLE
            ps = ctypes.windll.psapi
            ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            ps.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(pm), pm.cb)
            return pm.PeakWorkingSetSize / 1e9
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 / 1e9
    except Exception:
        return None


def h_levels(tm, h2, max_dof):
    """The rule of EVAL_SPEC_v1 s6 and A3.1, on the same 1.5x box as the official run, so h matches the official level."""
    while True:
        n, _ = jg.make_box(tm, h2)
        if 3 * np.prod(n + 1) <= max_dof:
            return h2, 2 * h2
        h2 *= 1.1


def combine(out):
    """Richardson per state, then the maximum: M_R = max(Q_R), band = [max(lo), max(hi)]. Extrapolating the maximum itself
    is wrong when the binding state changes between levels. One level only: M_R = M at that level, zero band."""
    lv = out["levels"]
    if "h1" not in lv:
        M2 = lv["h2"]["M"]
        out["richardson"] = {}; out["M_R"] = M2; out["band"] = [M2, M2]
        return out
    R = {s: J.richardson(lv["h1"]["states"][s]["Q"], lv["h2"]["states"][s]["Q"]) for s in ("alone", "fused")}
    out["richardson"] = R
    out["M_R"] = max(r["H_R"] for r in R.values())
    out["band"] = [max(r["band"][0] for r in R.values()), max(r["band"][1] for r in R.values())]
    return out


def score_mesh(path, mat_ns, h2=0.2, max_dof=20e6, levels=2, early=False, log=print):
    T0 = time.time()
    C_bone, cases, hashes = J.load_cases()
    mat = J.material(mat_ns)
    C_imp = C_bone if mat.get("bone_equivalent") else fe.iso_C(mat["E"], mat["nu"])
    tm = jg.load_mesh(path); man = jg.to_manifold(tm)
    info = jg.mesh_info(tm, man)
    ext = sorted(info["extent"][:2])
    g4 = bool(8 <= info["extent"][2] <= 18 and 22 <= ext[1] <= 55 and 9 <= ext[0] <= 40)
    hull_fill = float(man.hull().volume() / np.prod(info["extent"]))
    H2, H1 = h_levels(tm, h2, max_dof)
    Sm = np.linalg.inv(C_bone)
    g_e = J.EARLY_E_MPA / float(np.mean([1 / Sm[i, i] for i in range(3)]))
    states = {"alone": 0.0, "fused": 1.0}
    if early:
        states["early"] = g_e
    out = {"metric": "goal_metric/1 (EVAL_SPEC_v1_addendum4_goalmetric.md) exploratory, post-registered",
           "mesh": str(Path(path).name), "mesh_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
           "material": {k: mat.get(k) for k in ("name", "E", "nu", "strength")}, **hashes, "mesh_info": info,
           "hull_fill": hull_fill, "h": {"h2": H2, "h1": H1}, "levels": {}}
    lv = ((H1, "h1"), (H2, "h2")) if levels == 2 else ((H2, "h2"),)
    integ = g2 = None
    for h, tag in lv:
        t0 = time.time()
        n, origin, frac, hull, sub = geometry(tm, man, h)
        rec = {"h": h, "n": [int(x) for x in n], "states": {}, "geom_s": round(time.time() - t0, 1)}
        for s, g in states.items():
            t1 = time.time()
            st = solve_state(n, origin, frac, hull, h, C_bone, C_imp, g)
            if st is None:
                rec["states"][s] = {"Q": float(-np.log(LAMBDA_FLOOR)), "D_eff": float(-np.log(LAMBDA_FLOOR)), "note": "no elements"}
                continue
            r, C_eff = score_state(st, hull, h, C_bone)
            r["wall_s"] = round(time.time() - t1, 1)
            rec["states"][s] = r
            if s == "alone" and tag == "h2":
                integ = integrity(st, C_eff, frac, C_imp, C_bone, cases, mat["strength"])
            del st
            log(f"  {Path(path).stem} {tag} h={h:.3f} {s}: Q={r['Q']:.3f} D_eff={r['D_eff']:.3f} dof={r['dofs']} "
                f"iters={r['cg_iters']} {r['wall_s']}s")
        rec["M"] = max(rec["states"][s]["Q"] for s in ("alone", "fused"))
        if tag == "h2":
            g2 = bool(ndimage.label(frac > 0)[1] == 1)
        out["levels"][tag] = rec
    M2 = out["levels"]["h2"]["M"]
    combine(out)
    out["factor_off_from_bone_h2"] = float(np.exp(M2))
    gates = {"IA_alone_strength": integ or {"pass": False, "reason": "no solve"}, "G2_one_component": g2, "G4_size": g4,
             "hull_fill": hull_fill, "hull_fill_pass": bool(hull_fill >= MIN_HULL_FILL)}
    gates["pass"] = bool(gates["IA_alone_strength"]["pass"] and g2 and g4 and gates["hull_fill_pass"])
    out["gates"] = gates
    out["wall_s"] = round(time.time() - T0, 1)
    out["peak_rss_GB"] = peak_rss_gb()
    return J._round(out)


def matargs(material=None, E=None, nu=None, strength=None, source=None, datasheet=False):
    return SimpleNamespace(material=material, E=E, nu=nu, strength=strength, material_source=source, datasheet=datasheet)


def _parse_job_args(args):
    d = {}
    for i, a in enumerate(args):
        if a.startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            d[a[2:].replace("-", "_")] = args[i + 1]
    return d


def discover(folder):
    """Two layouts: prepared judge folders (<run>/judge_jobs.json, primary job), or loose meshes + materials.json
    ({"<stem>": {"material": "tough1500", "E": .., "nu": .., "strength": ..}, "_default": {...}})."""
    folder = Path(folder); jobs = []
    for jf in sorted(folder.glob("*/judge_jobs.json")):
        for job in json.loads(jf.read_text()):
            if job.get("tag") == "primary":
                d = _parse_job_args(job["args"])
                jobs.append({"name": jf.parent.name, "mesh": str(jf.parent / job["mesh"]),
                             "mat": {k: d[k] for k in ("material", "E", "nu", "strength") if k in d}})
    done = {j["name"] for j in jobs}
    mm = json.loads((folder / "materials.json").read_text()) if (folder / "materials.json").exists() else {}
    for p in sorted(sum((list(folder.glob(e)) for e in ("*.stl", "*.3mf", "*.obj")), [])):
        if p.stem not in done:
            m = mm.get(p.stem, mm.get("_default"))
            if m is None:
                print(f"SKIP {p.name}: no entry in materials.json"); continue
            jobs.append({"name": p.stem, "mesh": str(p), "mat": m}); done.add(p.stem)
    return jobs


def rank(results):
    """Gate-passers first, by M_R, lower is better; a band that overlaps the running tie group is a tie."""
    order = sorted(results, key=lambda r: (not r["gates"]["pass"], r["M_R"]))
    rows = []; pos = 0; hi_group = None; pass_group = None
    for i, r in enumerate(order):
        lo, hi = r["band"]
        same = hi_group is not None and pass_group == r["gates"]["pass"] and lo <= hi_group
        if same:
            hi_group = max(hi_group, hi)
        else:
            pos = i + 1; hi_group = hi; pass_group = r["gates"]["pass"]
        st = r["levels"]["h2"]["states"]
        rows.append({"rank": pos, "name": r["name"], "M_R": r["M_R"], "band": r["band"], "gates_pass": r["gates"]["pass"],
                     "Q_alone_h2": st["alone"]["Q"], "Q_fused_h2": st["fused"]["Q"]})
    return rows


def rank_unconditional(results):
    """M_R alone, gates ignored and shown beside it, same tie rule."""
    rows = rank([{**r, "gates": {**r["gates"], "pass": True}} for r in results])
    real = {r["name"]: r["gates"]["pass"] for r in results}
    return [{**row, "gates_pass": real[row["name"]]} for row in rows]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mesh"); ap.add_argument("--folder")
    ap.add_argument("--material"); ap.add_argument("--E", type=float); ap.add_argument("--nu", type=float); ap.add_argument("--strength", type=float)
    ap.add_argument("--h2", type=float, default=0.2); ap.add_argument("--max-dof", type=float, default=20e6)
    ap.add_argument("--fallback", action="store_true", help="the frozen coarse fallback, uniform for all: h2 = 0.4, h1 = 0.8")
    ap.add_argument("--with-early", action="store_true", help="also compute the 30 MPa state (reported, not in M)")
    ap.add_argument("--workers", type=int, default=1); ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    h2 = 0.4 if a.fallback else a.h2
    if a.mesh:
        r = score_mesh(a.mesh, matargs(a.material, a.E, a.nu, a.strength, "declared"), h2, a.max_dof, early=a.with_early)
        Path(a.out).write_text(json.dumps(r, indent=1, default=float))
        print(json.dumps({"M_R": r["M_R"], "band": r["band"], "wall_s": r["wall_s"], "gates_pass": r["gates"]["pass"]}, default=float))
        return
    jobs = discover(a.folder)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    flags = (0x08000000 | 0x00004000) if sys.platform == "win32" else 0

    def run(j):
        o = out / f"{j['name']}.json"
        if o.exists():
            return j["name"], 0
        cmd = [sys.executable, str(Path(__file__).resolve()), "--mesh", j["mesh"], "--h2", str(h2), "--max-dof", str(a.max_dof), "--out", str(o)]
        for k, v in j["mat"].items():
            cmd += [f"--{k}", str(v)]
        if a.with_early:
            cmd.append("--with-early")
        env = {**os.environ, "JUDGE_THREADS": str(a.threads)}
        with open(out / f"{j['name']}.log", "w") as lf:
            return j["name"], subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, creationflags=flags).returncode

    with ThreadPoolExecutor(a.workers) as ex:
        codes = dict(ex.map(run, jobs))
    res = []
    for j in jobs:
        o = out / f"{j['name']}.json"
        if o.exists():
            res.append({"name": j["name"], **json.loads(o.read_text())})
    table = rank(res)
    (out / "goal_ranking.json").write_text(json.dumps({"label": "post-registered, exploratory; does not replace the official ranking",
                                                        "ranking": table,
                                                        "ranking_unconditional_gates_ignored": rank_unconditional(res),
                                                        "gates": {r["name"]: r["gates"] for r in res},
                                                        "returncodes": codes}, indent=1))
    print(json.dumps(table, indent=1))


if __name__ == "__main__":
    main()
