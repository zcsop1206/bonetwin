"""judge.py: the arm-agnostic judge of EVAL_SPEC_v1.md (primary metric H, gates G1-G4, two resolutions + Richardson).

    python judge.py --mesh implant.stl --material <ref name> [--E MPa --nu - --strength MPa --material-source ...]
                    [--h2 0.2] [--max-dof 25e6] [--no-g3] [--out result.json] [--levels 1|2]

The mesh must be in the as-modelled frame (+Z cranial; X -> bone axis 1, Y -> bone axis 2), units mm.
Intake from a .form (PreForm) is in judge_intake.py; material grounding results arrive as --E/--nu/--strength with
their provenance, or a reference-table name (reference_materials.json).
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# resource limits (coordinator, 01:20): <= 4 BLAS/OpenMP threads, below-normal priority on Windows
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, os.environ.get("JUDGE_THREADS", "4"))
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL
    except Exception:
        pass

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
SIM = HERE.parent
ROOT = SIM.parent
sys.path.insert(0, str(HERE))
import judge_fe as fe  # noqa: E402
import judge_geom as jg  # noqa: E402

SUB_H = 0.07          # supersampling sub-grid, mm (as voxel_check v2)
AVG_MM = 0.8          # coarse-graining cube for the reported H_avg variant (not the spec's primary H)
GRAFT_DEFAULT = 1.0   # addendum A2 (primary, fused state): hull voids filled with g x C_bone, g = 1.0
EARLY_E_MPA = 30.0    # addendum A2 (secondary, early state): morselised graft E ~ 30 MPa at ~1 MPa (Pankaj et al.,
                      # Orthop Proc 90-B SUPP_II:381, 2008); g_early = 30 / mean axial bone modulus
NOT_CONVERGED_REL = 0.15   # early-state flag: |H2 - H1| > 15% of H_R


def load_cases():
    t = json.loads((ROOT / "targets" / "targets.json").read_text())
    site = t["sites"]["lumbar_vertebra"]
    C = np.array(site["material"]["stiffness_voigt_MPa"], float)
    key = "stress_voigt_MPa_[11,22,33,23,13,12]"
    cases = [(c["name"], fe.sigma_tensor(c[key]), False) for c in site["load_cases_visible"]]
    sp = ROOT / "targets" / "sealed_case.json"
    sealed = json.loads(sp.read_text())["lumbar_vertebra"]
    cases.append((sealed["name"], fe.sigma_tensor(sealed[key]), True))
    return C, cases, {"targets_sha256": hashlib.sha256((ROOT / "targets" / "targets.json").read_bytes()).hexdigest(),
                      "sealed_sha256": hashlib.sha256(sp.read_bytes()).hexdigest()}


def material(args):
    ref = json.loads((HERE / "reference_materials.json").read_text())
    cal = json.loads((SIM / "calibration.json").read_text())
    if args.material and args.material in ref["materials"]:
        m = dict(ref["materials"][args.material])
        if m.get("E_from_calibration") and getattr(args, "datasheet", False):
            m["E"] = m["E_datasheet"]; m["E_source"] = m["E_datasheet_source"] + " (SENSITIVITY run, EVAL_SPEC_v1 s5a)"
        elif m.get("E_from_calibration"):
            m["E"] = float(cal["materials"][m["E_from_calibration"]]["Es_MPa"])
            m["E_source"] = f"calibration.json {m['E_from_calibration']} (fit {cal.get('fitted_at')}; crosshead-only, flagged)"
        m["name"] = args.material
    else:
        m = {"name": args.material or "declared", "E_source": args.material_source, "nu_source": args.material_source,
             "strength_source": args.material_source}
    for k in ("E", "nu", "strength"):
        v = getattr(args, k)
        if v is not None:
            m[k] = v; m[f"{k}_source"] = args.material_source or "declared (grounded by the checker)"
    return m


def run_level(tm, man, h, C_bone, cases, mat, want_fields=False, log=None, graft=None):
    graft = GRAFT_DEFAULT if graft is None else graft
    t0 = time.time()
    n, origin = jg.make_box(tm, h)
    sub = int(np.ceil(h / SUB_H - 1e-9))
    frac = jg.occupancy(man, n, origin, h, sub)
    hull = jg.occupancy(man.hull(), n, origin, h, sub)       # hull fill fraction (same supersampling)
    t_geo = time.time() - t0
    box = fe.Box(n, h, origin)
    C_imp = C_bone if mat.get("bone_equivalent") else fe.iso_C(mat["E"], mat["nu"])
    asm = fe.assemble(box, frac, hull, C_bone, C_imp, graft=graft)
    F = fe.face_loads(box, asm["used"], [s for _, s, _ in cases])
    pd = fe.pins(box, asm["used"])
    slog = []
    xyz = box.node_ijk(asm["used"]) * h + box.origin
    U, M = fe.solve(asm["K"], F, pd, log=slog, xyz=xyz)
    t_fe = time.time() - t0 - t_geo
    S_bone = np.linalg.inv(C_bone)
    Ciso = C_imp
    isb = asm["isb"]
    fr = frac.ravel()[asm["elems"]]
    solid_imp = (~isb) & (fr >= 0.5)
    res = {"h": h, "n": [int(x) for x in n], "subsample": sub, "dofs": int(asm["nd"]), "elements": int(len(asm["elems"])),
           "bone_elements": int(isb.sum()), "implant_elements": int((~isb).sum()),
           "implant_volume_voxel_mm3": float(fr[~isb].sum() * h ** 3), "geom_s": round(t_geo, 1), "fe_s": round(t_fe, 1),
           "solver_log": slog, "cases": {}}
    num = den = numv = denv = 0.0
    numa_, dena_ = [0.0], [0.0]
    fields = {}
    for c, (name, sig, sealed) in enumerate(cases):
        eps = fe.element_strain(box, asm, U[:, c])
        eb = eps[isb]
        psi = 0.5 * np.einsum("ei,ij,ej->e", eb, C_bone, eb)
        sv = np.array([sig[i, j] for i, j in fe.VOIGT])
        psi0 = 0.5 * sv @ S_bone @ sv
        d2 = float(((psi - psi0) ** 2).sum()); n2 = float(psi0 ** 2 * len(psi))
        num += d2; den += n2
        # coarse-grained variant: psi averaged over cubes of AVG_MM (a mechanosensory volume), bone voxels only
        kf = max(1, int(round(AVG_MM / h)))
        eb_idx = asm["elems"][isb]
        ci_, cj_, ck_ = eb_idx % box.nx // kf, (eb_idx // box.nx) % box.ny // kf, eb_idx // (box.nx * box.ny) // kf
        cell = ci_ + (box.nx // kf + 1) * (cj_ + (box.ny // kf + 1) * ck_)
        cnt = np.bincount(cell); sm = np.bincount(cell, psi)
        nz_ = cnt > 0
        pbar = sm[nz_] / cnt[nz_]
        d2a = float((cnt[nz_] * (pbar - psi0) ** 2).sum())
        numa_[0] += d2a; dena_[0] += n2
        if not sealed:
            numv += d2; denv += n2
        vm = fe.von_mises(eps[solid_imp] @ Ciso.T) if solid_imp.any() else np.zeros(1)
        res["cases"][name] = {"sealed": sealed, "H_case": float(np.sqrt(d2 / n2)), "H_case_avg": float(np.sqrt(d2a / n2)), "psi0": float(psi0),
                              "shielded_frac": float((psi < 0.5 * psi0).mean()), "overloaded_frac": float((psi > 2 * psi0).mean()),
                              "implant_vm_p995_MPa_1x": float(np.percentile(vm, 99.5)), "implant_vm_max_MPa_1x": float(vm.max())}
        if want_fields:
            fields[name] = {"vm": vm}
            fields.setdefault("_eps", []).append(eps)
    res["H"] = float(np.sqrt(num / den))
    res["H_visible"] = float(np.sqrt(numv / denv))
    res["H_avg"] = float(np.sqrt(numa_[0] / dena_[0])); res["avg_cell_mm"] = max(1, int(round(AVG_MM / h))) * h
    # G2 connectivity at this level (implant voxels with any fill)
    imp = frac > 0
    lab, ncomp = ndimage.label(imp)
    sizes = np.bincount(lab.ravel())[1:] if ncomp else np.array([0])
    res["G2"] = {"components": int(ncomp), "island_volume_mm3": float((sizes.sum() - sizes.max()) * h ** 3) if ncomp else 0.0,
                 "pass": ncomp == 1}
    if want_fields:
        return res, {"box": box, "asm": asm, "frac": frac, "hull": hull, "U": U, "M": M, "F": F, "pd": pd, "fields": fields,
                     "fields_eps": fields.pop("_eps"),
                     "solid_imp": solid_imp}
    return res


def local_resolve(state, ci, dele, p, R, h):
    """Global-local re-solve after a deletion: submodel = kept elements whose centres lie within R (inf-norm) of p;
    its interface nodes keep the intact displacement (Dirichlet), loads and pins inside it are kept. Returns the
    governing-case strain of every kept element (intact outside the submodel)."""
    import scipy.sparse.linalg as spla
    box, asm = state["box"], state["asm"]
    nx, ny = box.nx, box.ny; e = asm["elems"]
    cen = np.stack([e % nx, (e // nx) % ny, e // (nx * ny)], 1) * h + h / 2
    sub = np.max(np.abs(cen - p), axis=1) <= R
    D = asm["dofs"]
    outside = np.zeros(asm["nd"], bool); outside[D[~sub].ravel()] = True
    sdofs = np.unique(D[sub].ravel())
    loc = np.full(asm["nd"], -1); loc[sdofs] = np.arange(len(sdofs))
    scale = np.where(dele[sub], 1e-6, 1.0)
    Ks = fe.assemble_K(np.stack(asm["Ke"]), asm["q"][sub], loc[D[sub]].astype(np.int32), len(sdofs), scale=scale)
    U0 = state["U"][:, ci]
    bnd = outside[sdofs]
    pin = np.isin(sdofs, state["pd"])
    fix = bnd | pin
    us = U0[sdofs].copy()
    fr = np.nonzero(~fix)[0]; fx = np.nonzero(fix)[0]
    rhs = state["F"][sdofs, ci][fr] - Ks[fr][:, fx] @ us[fx]
    Kff = Ks[fr][:, fr].tocsc()
    if len(fr) <= 120000:
        us[fr] = spla.splu(Kff).solve(rhs)
        how = "splu"
    else:
        import pyamg
        ml = pyamg.smoothed_aggregation_solver(Kff.tocsr(), max_coarse=500)
        us[fr], _ = spla.cg(Kff, rhs, x0=U0[sdofs][fr], rtol=1e-8, maxiter=4000, M=ml.aspreconditioner())
        how = "amg"
    U = U0.copy(); U[sdofs] = us
    eps = state["fields_eps"][ci].copy()
    B0 = fe.bmat(h, 0, 0, 0)
    eps[sub] = U[D[sub]] @ B0.T
    return eps, {"submodel_elements": int(sub.sum()), "submodel_dofs": int(len(sdofs)), "free_dofs": int(len(fr)), "solver": how}


def gate_g3(state, res, C_bone, cases, mat, strength, h, log=None, mode="local", R=4.0):
    """8 sphere deletions (d = 2 mm) at the highest-stress implant voxels of the governing case.
    mode "local": global-local re-solve in a (2R)^3 mm submodel around each deletion (default, R = 4 mm);
    mode "full": full re-solve (validation of the local mode)."""
    box, asm, frac = state["box"], state["asm"], state["frac"]
    gov = max(res["cases"], key=lambda k: res["cases"][k]["implant_vm_p995_MPa_1x"])
    ci = [c[0] for c in cases].index(gov)
    vm = state["fields"][gov]["vm"]
    el = asm["elems"][state["solid_imp"]]
    order = np.argsort(-vm)
    nx, ny = box.nx, box.ny
    cen = np.stack([el % nx, (el // nx) % ny, el // (nx * ny)], 1) * h + h / 2
    picks = []
    for o in order:
        p = cen[o]
        if all(np.linalg.norm(p - q) >= 2.0 for q in picks):
            picks.append(p)
        if len(picks) == 8:
            break
    Ciso = C_bone if mat.get("bone_equivalent") else fe.iso_C(mat["E"], mat["nu"])
    S_bone = np.linalg.inv(C_bone)
    sig = cases[ci][1]; sv = np.array([sig[i, j] for i, j in fe.VOIGT]); psi0 = 0.5 * sv @ S_bone @ sv
    H0 = res["cases"][gov]["H_case"]
    allcen = np.stack([asm["elems"] % nx, (asm["elems"] // nx) % ny, asm["elems"] // (nx * ny)], 1) * h + h / 2
    out = []
    for p in picks:
        dele = (~asm["isb"]) & (np.linalg.norm(allcen - p, axis=1) <= 1.0)
        # deleted voxels keep their DOFs but get 1e-6 of the implant stiffness (same sparsity; preconditioner reused)
        # K minus (1 - 1e-6) x the deleted elements' contribution (only the deleted elements are re-assembled)
        glog = []
        if mode == "local":
            eps, info = local_resolve(state, ci, dele, p, R, h); glog.append(info)
        else:
            dK = fe.assemble_K(np.stack(asm["Ke"]), asm["q"][dele], asm["dofs"][dele], asm["nd"])
            Kd = (asm["K"] - (1 - 1e-6) * dK).tocsr()
            U, _ = fe.solve(Kd, state["F"][:, [ci]], state["pd"], M=state["M"], maxiter=8000, X0=state["U"][:, [ci]], log=glog)
            eps = fe.element_strain(box, asm, U[:, 0])
        eb = eps[asm["isb"]]
        psi = 0.5 * np.einsum("ei,ij,ej->e", eb, C_bone, eb)
        Hc = float(np.sqrt(((psi - psi0) ** 2).sum() / (psi0 ** 2 * len(psi))))
        keep_imp = state["solid_imp"] & ~dele
        vm2 = fe.von_mises(eps[keep_imp] @ Ciso.T)
        p995 = float(np.percentile(vm2, 99.5))
        fr2 = frac.copy().ravel(); fr2[asm["elems"][dele]] = 0
        ncomp = ndimage.label(fr2.reshape(frac.shape) > 0)[1]
        ok = (ncomp == 1) and (2 * p995 <= strength) and (abs(Hc - H0) <= 0.10)
        out.append({"centre_mm": (p + box.origin).round(3).tolist(), "deleted_voxels": int(dele.sum()), "components": int(ncomp),
                    "p995_MPa_2x": 2 * p995, "H_case": Hc, "dH": Hc - H0, "pass": bool(ok), "solver": glog})
    return {"governing_case": gov, "mode": mode, "R_mm": R if mode == "local" else None, "deletions": out,
            "pass": all(o["pass"] for o in out) and len(out) == 8}


def _round(o, sig=10):
    if isinstance(o, float):
        return float(f"{o:.{sig}g}")
    if isinstance(o, dict):
        return {k: _round(v, sig) for k, v in o.items()}
    if isinstance(o, list):
        return [_round(v, sig) for v in o]
    return o


def richardson(H1, H2, p=1.0):
    HR = H2 + (H2 - H1) / (2 ** p - 1)
    U = abs(H2 - H1)
    mono = (H1 - H2) * (H2 - HR) >= 0
    lo, hi = (HR - U, HR + U) if mono else (min(H1, H2, HR) - U, max(H1, H2, HR) + U)
    return {"H1": H1, "H2": H2, "H_R": HR, "band": [lo, hi], "monotone": bool(mono)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--material")
    ap.add_argument("--E", type=float); ap.add_argument("--nu", type=float); ap.add_argument("--strength", type=float)
    ap.add_argument("--material-source")
    ap.add_argument("--h2", type=float, default=0.2)
    ap.add_argument("--max-dof", type=float, default=25e6)
    ap.add_argument("--levels", type=int, default=2)
    ap.add_argument("--no-g3", action="store_true")
    ap.add_argument("--datasheet", action="store_true", help="sensitivity run: resin moduli from the Formlabs datasheets (s5a)")
    ap.add_argument("--no-early", action="store_true", help="skip the A2 secondary (early, soft-graft) state")
    ap.add_argument("--graft", type=float, default=GRAFT_DEFAULT,
                    help="hull-void fill as a fraction of C_bone (A2 primary 1.0; spec v1 = 0)")
    ap.add_argument("--out")
    a = ap.parse_args()
    T0 = time.time()
    C_bone, cases, hashes = load_cases()
    mat = material(a)
    tm = jg.load_mesh(a.mesh); man = jg.to_manifold(tm)
    info = jg.mesh_info(tm, man)
    ext = sorted(info["extent"][:2])
    g4 = {"height_mm": info["extent"][2], "long_side_mm": ext[1], "short_side_mm": ext[0],
          "pass": bool(8 <= info["extent"][2] <= 18 and 22 <= ext[1] <= 55 and 9 <= ext[0] <= 40)}
    # resolution: h2 = 0.2 unless the box would exceed max-dof
    h2 = a.h2
    while True:
        n, _ = jg.make_box(tm, h2)
        if 3 * np.prod(n + 1) <= a.max_dof:
            break
        h2 *= 1.1
    h1 = 2 * h2
    out = {"judge": "bonetwin-judge/1 (EVAL_SPEC_v1.md)", "mesh": str(Path(a.mesh).resolve()),
           "mesh_sha256": hashlib.sha256(Path(a.mesh).read_bytes()).hexdigest(), "mesh_info": info, "material": mat,
           **hashes, "G4": g4, "graft_factor": a.graft, "levels": {}}
    res1 = run_level(tm, man, h1, C_bone, cases, mat, graft=a.graft) if a.levels == 2 else None
    if res1:
        out["levels"]["h1"] = res1
    res2, state = run_level(tm, man, h2, C_bone, cases, mat, want_fields=True, graft=a.graft)
    out["levels"]["h2"] = res2
    strength = mat["strength"]
    g1 = {"sigma_allow_MPa": strength / 2, "p995_MPa_2x": {k: 2 * v["implant_vm_p995_MPa_1x"] for k, v in res2["cases"].items()}}
    g1["pass"] = bool(max(g1["p995_MPa_2x"].values()) <= strength / 2)
    out["G1"] = g1; out["G2"] = res2["G2"]
    out["G3"] = {"status": "skipped (--no-g3)"} if a.no_g3 else gate_g3(state, res2, C_bone, cases, mat, strength, h2)
    if res1:
        out["richardson"] = richardson(res1["H"], res2["H"])
        out["richardson_avg"] = richardson(res1["H_avg"], res2["H_avg"])
        out["primary"] = {"definition": f"A2 fused state: hull voids = {a.graft} x C_bone; metric H_avg (psi averaged over "
                                        f"{AVG_MM} mm bone cubes); Richardson p=1 over h1/h2", **out["richardson_avg"]}
    # A2 secondary: early state (soft graft), same levels, H_avg + band + not-converged flag; G1 reported for information
    if not a.no_early:
        Sm = np.linalg.inv(C_bone); g_e = EARLY_E_MPA / float(np.mean([1 / Sm[i, i] for i in range(3)]))
        e2 = run_level(tm, man, h2, C_bone, cases, mat, graft=g_e)
        early = {"graft_factor": g_e, "E_graft_MPa": EARLY_E_MPA, "source": "Pankaj et al. 2008, Orthop Proc 90-B SUPP_II:381 (impaction grafting, not spine)",
                 "H2": e2["H"], "H_avg2": e2["H_avg"],
                 "G1_p995_MPa_2x": {k: 2 * v["implant_vm_p995_MPa_1x"] for k, v in e2["cases"].items()}}
        if res1:
            e1 = run_level(tm, man, h1, C_bone, cases, mat, graft=g_e)
            R = richardson(e1["H_avg"], e2["H_avg"])
            early.update({"H1": e1["H"], "H_avg1": e1["H_avg"], "richardson_avg": R, "richardson_raw": richardson(e1["H"], e2["H"]),
                          "not_converged": bool(abs(R["H2"] - R["H1"]) > NOT_CONVERGED_REL * max(abs(R["H_R"]), 1e-9))})
        out["secondary_early"] = early
    out["gates_pass"] = bool(g1["pass"] and out["G2"]["pass"] and out["G3"].get("pass", False) and g4["pass"])
    out["wall_s"] = round(time.time() - T0, 1)
    out = _round(out)          # 10 significant digits: multithreaded BLAS sums differ at ~1e-12 between runs
    txt = json.dumps(out, indent=1, default=float)
    if a.out:
        Path(a.out).write_text(txt)
    summ = {k: out[k] for k in ("G1", "G4", "gates_pass", "wall_s")}
    summ["H"] = {lv: r["H"] for lv, r in out["levels"].items()}
    if "primary" in out:
        summ["primary_H_avg_R"] = {k: out["primary"][k] for k in ("H_R", "band", "monotone")}
    if "secondary_early" in out:
        summ["early"] = {k: out["secondary_early"].get(k) for k in ("H_avg2", "richardson_avg", "not_converged")}
    summ["G2"] = out["G2"]["pass"]; summ["G3"] = out["G3"].get("pass", out["G3"].get("status"))
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
