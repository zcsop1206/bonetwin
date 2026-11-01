"""Control arm: no agent judgement. The gateway's deterministic Gibson-Ashby two-step control design, turned into an
STL and a PreForm .form in Rigid 10K, plus a material_spec.json and a report.md. Run once at launch.

    python control_build.py --root R

Steps (code only, no model; run with no model keys or tokens in the environment):
  1. sim/control_design.py --target lumbar_vertebra --dim 3 --material rigid10k  (twice: hashes must match): the
     textbook two-step rule (Gibson-Ashby relative density, then strength sizing) on the gateway's 20 mm block
  2. the same rule at the standard lumbar cage size (config control.envelope_mm, 40 x 22 x 12 mm): the same unit
     cell (cubic edges + body diagonals) with whole cells per axis (pitch 40/8, 22/4, 12/2 mm), each strut's width
     taken from its direction class in the step-1 design; capsules united and clipped to the envelope with
     manifold3d -> implant.stl as modelled (+Z cranial-caudal; X anterior-posterior = bone axis 1, Y lateral = 2);
     built twice, STL hashes must match
  3. PreForm, through the adapter in preform_tool.py: create a scene (Form 4, Rigid 10K, 0.1 mm), import, support, lay out, save implant.form
  4. material_spec.json (calibrated modulus from sim/calibration.json + datasheet values) and report.md
Output: <root>/control/gibson_ashby_rigid10k/ (+ kb/ with the design JSON and the gateway's frame score record).
A step that fails is recorded in control_build.json; the collector then records 'no submission' for the control.
"""
import argparse
import hashlib
import json
import subprocess

import numpy as np
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gateway as gw  # noqa: E402
from common import BONETWIN, load_config, utc_now, write_json  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, cwd):
    r = subprocess.run([sys.executable, *cmd], capture_output=True, text=True, cwd=str(cwd), env=gw.no_model_env(),
                       timeout=1200)
    return r.returncode, (r.stdout + r.stderr)[-1500:]


def direction_class(a, b):
    v = np.array(b, float) - np.array(a, float)
    s = np.sign(np.round(v, 9))
    if np.count_nonzero(s) == 1:
        return ("edge", int(np.argmax(np.abs(s))))
    if s[0] < 0 or (s[0] == 0 and s[1] < 0):
        s = -s
    return ("diag", tuple(int(x) for x in s))


def sized_design(cube, env, pitch):
    """The rule's unit cell over the envelope with whole cells per axis; widths by direction class."""
    X = cube["nodes"]
    widths = {}
    for i, j, w in cube["struts"]:
        widths.setdefault(direction_class(X[int(i)], X[int(j)]), []).append(float(w))
    wmap = {k: float(np.median(v)) for k, v in widths.items()}
    n = [max(1, int(round(e / pitch))) for e in env]
    h = [e / k for e, k in zip(env, n)]
    nodes, idx, struts = [], {}, []

    def node(p):
        k = tuple(round(float(v), 6) for v in p)
        if k not in idx:
            idx[k] = len(nodes)
            nodes.append(list(k))
        return idx[k]
    for i in range(n[0] + 1):
        for j in range(n[1] + 1):
            for k in range(n[2] + 1):
                a = node((i * h[0], j * h[1], k * h[2]))
                for d in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                    q = (i + d[0], j + d[1], k + d[2])
                    if q[0] <= n[0] and q[1] <= n[1] and q[2] <= n[2]:
                        struts.append([a, node((q[0] * h[0], q[1] * h[1], q[2] * h[2]))])
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                c = node(((i + .5) * h[0], (j + .5) * h[1], (k + .5) * h[2]))
                for a_ in (0, 1):
                    for b_ in (0, 1):
                        for e_ in (0, 1):
                            struts.append([node(((i + a_) * h[0], (j + b_) * h[1], (k + e_) * h[2])), c])
    out = []
    for a, b in struts:
        cls = direction_class(nodes[a], nodes[b])
        out.append([a, b, wmap.get(cls, float(np.median([w for v in widths.values() for w in v])))])
    return {"schema": "bonetwin-design/1", "name": "control_lumbar_cage_40x22x12_rigid10k", "dim": 3,
            "envelope_mm": list(env), "material": cube.get("material", "rigid10k"), "build": {"axis": [0, 0, 1]},
            "nodes": nodes, "struts": out,
            "meta": {"rule": "two-step textbook rule from the 20 mm control (control_design.py), same unit cell",
                     "cells_per_axis": n, "pitch_per_axis_mm": h,
                     "width_by_direction_class_mm": {str(k): v for k, v in wmap.items()}}}


def lattice_stl(design, env, out, seg=16):
    import manifold3d as m3
    import trimesh
    X = np.array(design["nodes"], float)
    parts = []
    for i, j, w in design["struts"]:
        r = float(w) / 2
        sa = m3.Manifold.sphere(r, seg).translate(tuple(X[int(i)]))
        sb = m3.Manifold.sphere(r, seg).translate(tuple(X[int(j)]))
        parts.append(m3.Manifold.batch_hull([sa, sb]))
    body = m3.Manifold.batch_boolean(parts, m3.OpType.Add)
    body = body ^ m3.Manifold.cube(tuple(env))  # clip to the envelope (origin corner, +Z cranial-caudal)
    mesh = body.to_mesh()
    tm = trimesh.Trimesh(vertices=np.array(mesh.vert_properties)[:, :3], faces=np.array(mesh.tri_verts),
                         process=False)
    tm.export(str(out))
    return {"volume_mm3": round(float(body.volume()), 3), "watertight": bool(tm.is_watertight),
            "extent_mm": [round(float(x), 3) for x in tm.extents], "triangles": int(len(tm.faces)),
            "components": len(body.decompose())}


def preform_form(stl, form, cfg, log):
    sys.path.insert(0, str(BONETWIN))
    import preform_tool as pt
    if not pt.server_up():
        log["preform"] = "PreFormServer not running: no .form"
        return False
    p = cfg["preform"]
    cat = pt.get_catalog(form.parent)
    res = pt.resolve_setting(cat, p["control_printer"], p["control_resin"], p["layer_mm"])
    sid = pt.create_scene(dict(res["scene_settings"]))
    pt.import_model(sid, stl, name="implant")
    pt.auto_support(sid)
    pt.auto_layout(sid, seed=0)
    pt.save_form(form, [sid], name="control")
    pt.safe(pt.delete_scene, sid)
    log["preform"] = {"settings": res["setting_label"], "printer": res["printer_label"],
                      "material": res["material_label"]}
    return form.exists()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    a = ap.parse_args()
    cfg = load_config()
    c = cfg["control"]
    out = Path(a.root).resolve() / "control" / f"gibson_ashby_{c['material']}"
    if out.exists():  # regenerate deterministically
        import shutil
        shutil.rmtree(out)
    kb = out / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    sim = BONETWIN / "sim"
    log = {"utc": utc_now(), "steps": {}}
    d1, d2 = kb / "control_design.json", kb / "control_design_rerun.json"
    for d in (d1, d2):
        rc, txt = run(["control_design.py", "--target", c["target"], "--dim", str(c["dim"]), "--material",
                       c["material"], "--out", str(d)], sim)
        log["steps"][d.name] = {"rc": rc, "tail": txt[-300:]}
    log["determinism"] = {"sha256": sha(d1) if d1.exists() else None, "rerun": sha(d2) if d2.exists() else None}
    log["determinism"]["identical"] = bool(d1.exists() and d2.exists() and sha(d1) == sha(d2))
    stl = out / "implant.stl"
    if d1.exists():
        env = c["envelope_mm"]
        sized = sized_design(json.loads(d1.read_text(encoding="utf-8")), env, c["rule_pitch_mm"])
        write_json(kb / "control_design_sized.json", sized)
        info1 = lattice_stl(sized, env, stl)
        stl2 = kb / "implant_rebuild_check.stl"
        lattice_stl(sized, env, stl2)
        log["stl"] = dict(info1, sha256=sha(stl), rebuild_identical=sha(stl) == sha(stl2))
        stl2.unlink()
        log["size"] = {"envelope_mm": env, "source": c["size_source"]}
        try:  # the gateway's frame record of the 20 mm rule design, as KB evidence
            info = gw.resolve(cfg)
            gw.ensure_key(info)
            rec = gw.score(info, d1, c["target"], "frame", dim=c["dim"])
            write_json(kb / "gateway_frame_record.json", rec)
            log["frame_score"] = rec.get("score")
        except Exception as exc:
            log["frame_score_error"] = str(exc)[:300]
    form = out / "implant.form"
    if stl.exists():
        try:
            preform_form(stl, form, cfg, log)
        except BaseException as exc:  # preform_tool exits on errors
            log["preform_error"] = str(exc)[:300]
    calib = json.loads((sim / "calibration.json").read_text(encoding="utf-8"))["materials"][c["material"]]
    write_json(out / "material_spec.json", {
        "material": "Formlabs Rigid 10K (glass-filled photopolymer), printed on a Form 4 at 0.1 mm, post-cured",
        "properties": {
            "tensile_modulus_MPa": {"value": 10000, "source": "Formlabs Rigid 10K technical data sheet (post-cured)"},
            "ultimate_tensile_strength_MPa": {"value": 65, "source": "Formlabs Rigid 10K technical data sheet (post-cured)"},
            "calibrated_strut_modulus_MPa": {"value": round(calib["Es_MPa"], 1),
                                             "source": "bonetwin/sim/calibration.json (the gateway's calibration)"},
            "poisson_ratio": {"value": calib.get("nu"), "source": "bonetwin/sim/calibration.json"}}})
    (out / "report.md").write_text(
        "# Control: textbook Gibson-Ashby two-step lattice (no agent)\n\n"
        "Deterministic output of the gateway's control_design.py (Gibson-Ashby relative density for the bone's "
        "stiffness, then strength sizing), applied at a standard lumbar cage size, exported to STL and laid out in "
        "PreForm in Rigid 10K.\n\n"
        f"- Size: {c['envelope_mm'][0]:g} mm anterior-posterior (X) x {c['envelope_mm'][1]:g} mm lateral (Y) x "
        f"{c['envelope_mm'][2]:g} mm cranial-caudal (+Z). Source: {c['size_source']}.\n"
        "- Rule design on the gateway's 20 mm block: [kb/control_design.json](kb/control_design.json) (rerun "
        f"identical: {log['determinism']['identical']})\n"
        "- The same rule over the cage envelope: [kb/control_design_sized.json](kb/control_design_sized.json) "
        f"(STL rebuild identical: {(log.get('stl') or {}).get('rebuild_identical')})\n"
        "- Gateway frame record of the rule design: [kb/gateway_frame_record.json](kb/gateway_frame_record.json)\n"
        "- Material: [material_spec.json](material_spec.json)\n", encoding="utf-8")
    log["deliverables"] = {f: (out / f).exists() for f in ("implant.form", "implant.stl", "material_spec.json",
                                                            "report.md")}
    write_json(out / "control_build.json", log)
    print(json.dumps({"control": str(out), "deliverables": log["deliverables"],
                      "deterministic": log["determinism"]["identical"]}, indent=1))


if __name__ == "__main__":
    main()
