"""judge_intake.py: open a submitted .form through PreFormServer, record models + validation, find a verified mesh
(EVAL_SPEC_v1 §1).

    python judge_intake.py --form arm/x.form [--folder arm/] --out intake.json [--work DIR]

Mesh acceptance: a candidate mesh (the model's original_file, or any STL/OBJ/3MF in the submission folder) is
imported into a scratch scene; it is accepted only if its canonical_model_hash equals the .form model's hash, or
(if hashes are not comparable) its volume and bounding-box extents match within 0.1%. The accepted mesh is then
re-expressed in the as-modelled frame (the candidate files are already in that frame: PreForm's pose lives in the
scene, not in the file).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
import preform_tool as pt  # noqa: E402

SERVER = ROOT / "PreFormServer" / "PreFormServer" / "PreFormServer.exe"
VALIDATORS = ["manifoldness", "in-bounds", "cups", "minima", "supportedness"]


def ensure_server(timeout=120):
    if pt.server_up():
        return pt.server_up()
    pt.start_server(SERVER)  # public copy: the adapter starts the server (see preform_tool.py)
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(2)
        v = pt.server_up()
        if v:
            return v
    raise RuntimeError("PreFormServer did not start")


def models(sid):
    return pt.get_scene(sid)["models"]


def safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:  # pragma: no cover
        return {"error": str(e)}


def ext(m):
    bb = m["bounding_box"]
    return [bb["max_corner"][c] - bb["min_corner"][c] for c in "xyz"]


def candidate_matches(form_model, cand, scene_settings):
    """Import cand into a scratch scene; compare hash, else extents (rotation-free comparison of sorted extents)."""
    sid = pt.create_scene(scene_settings)
    try:
        r = pt.import_model(sid, cand)
        mid = r["new_models"][0]["model_id"]
        m = [x for x in models(sid) if x["id"] == mid][0]
        h_ok = bool(m.get("canonical_model_hash")) and m.get("canonical_model_hash") == form_model.get("canonical_model_hash")
        e1, e2 = sorted(ext(m)), sorted(ext(form_model))
        ext_ok = all(abs(a - b) <= 1e-3 * max(b, 1e-9) for a, b in zip(e1, e2))
        return {"file": str(cand), "hash": m.get("canonical_model_hash"), "hash_match": h_ok, "extent_match": ext_ok,
                "accepted": bool(h_ok or (not form_model.get("canonical_model_hash") and ext_ok))}
    finally:
        safe(pt.delete_scene, sid)


def intake(form, folder=None):
    ver = ensure_server()
    rec = {"form": str(Path(form).resolve()), "server_version": ver}
    op = pt.open_form(Path(form).resolve())
    sc = op["scenes"][0]; sid = sc["scene_id"]
    rec["scenes_in_file"] = len(op["scenes"])
    scene = pt.get_scene(sid)
    rec["scene_settings"] = scene.get("scene_settings")
    ms = scene["models"]
    rec["models"] = [{k: m.get(k) for k in ("id", "name", "position", "orientation", "scale", "units", "bounding_box",
                                             "original_file", "raw_mesh_hash", "canonical_model_hash", "has_supports")} for m in ms]
    bc = safe(pt.body_count, sid)
    rec["body_count"] = bc
    v = {name: safe(pt.validate, sid, name) for name in VALIDATORS}
    v["thin-features"] = safe(pt.validate, sid, "thin-features", threshold_mm=0.3)
    rec["validation"] = v
    flags = []
    if len(ms) != 1:
        flags.append(f"{len(ms)} models in the scene (expected 1): bodies united")
    rec["flags"] = flags
    # mesh: (b) original_file, (c) files in the submission folder
    cands = []
    for m in ms:
        if m.get("original_file") and Path(m["original_file"]).exists():
            cands.append(Path(m["original_file"]))
    if folder:                      # addendum A1.1 order: implant.stl, implant.3mf, then any other mesh file
        F = Path(folder)
        for nm in ("implant.stl", "implant.3mf"):
            if (F / nm).exists():
                cands.append(F / nm)
        for pat in ("*.stl", "*.STL", "*.obj", "*.3mf"):
            cands += [c for c in sorted(F.glob(pat)) if c not in cands]
    ss = {k: v_ for k, v_ in (rec["scene_settings"] or {}).items() if k in ("machine_type", "material_code", "print_setting", "layer_thickness_mm")}
    checks = []
    for m in ms:
        acc = None
        for c in cands:
            r = safe(candidate_matches, m, c, ss)
            checks.append(r)
            if r.get("accepted"):
                acc = r["file"]; break
        m["accepted_mesh"] = acc
    rec["mesh_checks"] = checks
    rec["meshes"] = [m.get("accepted_mesh") for m in ms]
    rec["evaluable"] = all(rec["meshes"]) and len(ms) >= 1
    safe(pt.delete_scene, sid)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--form", required=True); ap.add_argument("--folder"); ap.add_argument("--out")
    a = ap.parse_args()
    rec = intake(a.form, a.folder)
    txt = json.dumps(rec, indent=1, default=str)
    if a.out:
        Path(a.out).write_text(txt)
    print(json.dumps({k: rec[k] for k in ("evaluable", "meshes", "flags", "scenes_in_file")}, indent=1, default=str))


if __name__ == "__main__":
    main()
