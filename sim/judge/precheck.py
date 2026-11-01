"""precheck.py: coarse pre-check of one submission folder (EVAL_SPEC_v1 addendum A1.2). NOT a score; harness-only.

    python precheck.py --folder submissions/<run>/ [--g3] [--h 0.4] [--skip-intake intake.json]

Same pipeline as the judge, reduced: visible load cases only (no sealed case), one resolution (h = 0.4 mm), no
Richardson (band reported as +-0, flagged coarse), gates G1, G2, G4 (G3 with --g3). Material: the declared material
name / E in material_spec.json mapped to the reference table (no grounding check at pre-check time).
Prints one JSON object.
"""
import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import judge as J  # noqa: E402
import judge_geom as jg  # noqa: E402
from judge_submission import NAME_MAP, REF, ref_E  # noqa: E402


def declared(folder):
    p = Path(folder) / "material_spec.json"
    if not p.exists():
        return {}, None
    try:
        d = json.loads(p.read_text(errors="replace"))
    except Exception:
        return {}, None
    flat = json.dumps(d).lower()
    name = None
    for k in ("material_name", "material", "name"):
        v = d.get(k) if isinstance(d, dict) else None
        if isinstance(v, str):
            name = v; break
        if isinstance(v, dict) and isinstance(v.get("name"), str):
            name = v["name"]; break
    E = None
    for k in ("E_MPa", "E", "youngs_modulus_MPa", "elastic_modulus_MPa", "modulus_MPa"):
        v = d.get(k) if isinstance(d, dict) else None
        if isinstance(v, dict):
            v = v.get("value")
        if isinstance(v, (int, float)):
            E = float(v); break
    return {"name": name, "E": E, "raw_contains": [k for k in NAME_MAP if k in flat]}, d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--folder", required=True); ap.add_argument("--g3", action="store_true")
    ap.add_argument("--h", type=float, default=0.4); ap.add_argument("--skip-intake")
    a = ap.parse_args()
    T0 = time.time()
    folder = Path(a.folder)
    out = {"precheck": "bonetwin-judge precheck (addendum A1.2) - NOT A SCORE", "folder": str(folder.resolve()), "coarse": True}
    form = folder / "implant.form"
    if not form.exists():
        out["status"] = "no implant.form"; print(json.dumps(out, indent=1)); return
    if a.skip_intake:
        intake = json.loads(Path(a.skip_intake).read_text())
    else:
        tmp = folder / ".precheck_intake.json"
        subprocess.run([sys.executable, str(HERE / "judge_intake.py"), "--form", str(form), "--folder", str(folder), "--out", str(tmp)],
                       capture_output=True, text=True)
        intake = json.loads(tmp.read_text()) if tmp.exists() else {"evaluable": False}
    out["intake"] = {k: intake.get(k) for k in ("evaluable", "meshes", "flags")}
    if not intake.get("evaluable"):
        out["status"] = "not evaluable (no verified mesh)"; print(json.dumps(out, indent=1)); return
    meshes = [m for m in intake["meshes"] if m]
    import trimesh
    tm = trimesh.util.concatenate([trimesh.load(m, force="mesh") for m in sorted(set(meshes))]) if len(set(meshes)) > 1 else jg.load_mesh(meshes[0])
    man = jg.to_manifold(tm)
    dec, _ = declared(folder)
    key = next((v for k, v in NAME_MAP.items() if dec.get("name") and k in dec["name"].lower()), None) or \
        (dec["raw_contains"] and NAME_MAP[dec["raw_contains"][0]]) or None
    if key is None and dec.get("E"):
        cands = [k for k in REF if k not in ("bone_equivalent", "trabecular_bone_iso")]
        key = min(cands, key=lambda k: abs(math.log(ref_E(k) / dec["E"])))
    if key is None:
        mc = str((intake.get("scene_settings") or {}).get("material_code", "")).lower()
        key = "tough1500" if ("tough" in mc or mc.startswith("flto")) else "rigid10k"

    class Args:
        material = key; E = nu = strength = None; material_source = None; datasheet = False
    mat = J.material(Args)
    out["material_used"] = {"reference": key, "E": mat["E"], "nu": mat["nu"], "strength": mat["strength"], "declared": dec}
    C, cases, _ = J.load_cases()
    vis = [c for c in cases if not c[2]]
    info = jg.mesh_info(tm, man)
    ext = sorted(info["extent"][:2])
    g4 = {"height_mm": info["extent"][2], "long_side_mm": ext[1], "short_side_mm": ext[0],
          "pass": bool(8 <= info["extent"][2] <= 18 and 22 <= ext[1] <= 55 and 9 <= ext[0] <= 40)}
    if a.g3:
        res, state = J.run_level(tm, man, a.h, C, vis, mat, want_fields=True)
    else:
        res = J.run_level(tm, man, a.h, C, vis, mat)
    g1p = {k: 2 * v["implant_vm_p995_MPa_1x"] for k, v in res["cases"].items()}
    g1 = {"sigma_allow_MPa": mat["strength"] / 2, "p995_MPa_2x": g1p, "pass": bool(max(g1p.values()) <= mat["strength"] / 2)}
    out.update({"status": "prechecked", "h": a.h, "H_avg": res["H_avg"], "H_raw": res["H"], "band": [res["H_avg"], res["H_avg"]],
                "state": f"A2 fused (graft {J.GRAFT_DEFAULT} x C_bone)", "H_per_case": {k: v["H_case"] for k, v in res["cases"].items()},
                "G1": g1, "G2": res["G2"], "G4": g4, "dofs": res["dofs"]})
    if a.g3:
        out["G3"] = J.gate_g3(state, res, C, vis, mat, mat["strength"], a.h)
        out["G3"] = {"pass": out["G3"]["pass"], "governing_case": out["G3"]["governing_case"],
                     "failed": [d for d in out["G3"]["deletions"] if not d["pass"]]}
    out["gates_pass"] = bool(g1["pass"] and res["G2"]["pass"] and g4["pass"] and (out.get("G3", {"pass": True})["pass"]))
    out["wall_s"] = round(time.time() - T0, 1)
    print(json.dumps(J._round(out), indent=1, default=float))


if __name__ == "__main__":
    main()
