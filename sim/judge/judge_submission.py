"""judge_submission.py: one submission folder -> intake -> material resolution -> primary + sensitivity judge runs.

    python judge_submission.py --folder subs/<arm>/ --grounding grounding/<arm>.json --out results/<arm>/ [--h2 0.2]
                               [--deadline 2026-11-01T08:30:00-05:00]

grounding/<arm>.json is written by the independent grounding checker (EVAL_SPEC_v1 §5):
  {"material_name": "...", "properties": {"E": {"value": 3600, "unit": "MPa", "grounded": true, "source": "...",
   "checker_note": "..."}, "nu": {...}, "strength": {...}}}
A property is used only if grounded; otherwise the nearest reference material supplies it (name match, else nearest
log-E to the declared E, else the printer resin from the .form scene settings).
"""
import argparse
import datetime as dt
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
FLAGS = (0x08000000 | 0x00004000) if sys.platform == "win32" else 0      # CREATE_NO_WINDOW | BELOW_NORMAL
REF = json.loads((HERE / "reference_materials.json").read_text())["materials"]
NAME_MAP = {"rigid 10k": "rigid10k", "rigid10k": "rigid10k", "tough 1500": "tough1500", "tough1500": "tough1500",
            "peek": "peek450g", "ti-6al-4v": "ti6al4v", "ti6al4v": "ti6al4v", "ti-6-4": "ti6al4v", "titanium": "ti6al4v",
            "cortical": "cortical_bone"}


def ref_E(key):
    if REF[key].get("E_from_calibration"):
        cal = json.loads((HERE.parent / "calibration.json").read_text())
        return cal["materials"][REF[key]["E_from_calibration"]]["Es_MPa"]
    return REF[key]["E"]


def resolve(grounding, scene_settings):
    name = (grounding.get("material_name") or "").lower()
    props = grounding.get("properties", {})
    key = next((v for k, v in NAME_MAP.items() if k in name), None)
    decl_E = (props.get("E") or {}).get("value")
    how = "name match" if key else None
    if key is None and decl_E:
        cands = [k for k in REF if k not in ("bone_equivalent", "trabecular_bone_iso")]
        key = min(cands, key=lambda k: abs(math.log(ref_E(k) / float(decl_E)))); how = "nearest log-E to declared E"
    if key is None:
        mc = str((scene_settings or {}).get("material_code", "")).lower()
        key = "tough1500" if ("tough" in mc or mc.startswith("flto")) else "rigid10k"; how = f"printer resin from scene ({mc})"
    used = {"fallback_reference": key, "fallback_rule": how}
    args = ["--material", key]
    for p in ("E", "nu", "strength"):
        g = props.get(p) or {}
        if g.get("grounded") and g.get("value") is not None:
            args += [f"--{p}", str(g["value"])]
            used[p] = {"value": g["value"], "from": "declared, grounded", "source": g.get("source")}
        else:
            used[p] = {"from": f"reference {key}", "declared": g.get("value"), "grounded": bool(g.get("grounded"))}
    args += ["--material-source", "grounded declaration (see grounding file)"]
    return args, used


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--folder", required=True); ap.add_argument("--grounding", help="grounding checker output; absent = no grounded properties (reference fallback)"); ap.add_argument("--out", required=True)
    ap.add_argument("--h2", default="0.2"); ap.add_argument("--deadline", default="2026-11-01T08:30:00-05:00", help="hard deadline, local wall clock EST (addendum A2)")
    ap.add_argument("--skip-intake", help="use this intake JSON instead of PreForm (tests)")
    ap.add_argument("--prepare-only", action="store_true",
                    help="stop after intake + material resolution; write judge_jobs.json for judge_batch.py (e.g. on Brev)")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    folder = Path(a.folder)
    allforms = sorted(folder.glob("*.form"))
    forms = [f for f in allforms if f.name.lower() == "implant.form"]          # addendum A1.1
    rec = {"folder": str(folder.resolve()), "forms": [str(f) for f in forms],
           "ignored_forms": [str(f) for f in allforms if f not in forms]}
    if len(forms) != 1:
        rec["status"] = "no submission (no implant.form)"
        (out / "submission.json").write_text(json.dumps(rec, indent=1)); print(rec["status"]); return
    mtime = dt.datetime.fromtimestamp(forms[0].stat().st_mtime).astimezone()
    rec["form_mtime"] = mtime.isoformat()
    if mtime > dt.datetime.fromisoformat(a.deadline):
        rec["status"] = "no submission (late)"
        (out / "submission.json").write_text(json.dumps(rec, indent=1)); print(rec["status"]); return
    if a.skip_intake:
        intake = json.loads(Path(a.skip_intake).read_text())
    else:
        r = subprocess.run([PY, str(HERE / "judge_intake.py"), "--form", str(forms[0]), "--folder", str(folder),
                            "--out", str(out / "intake.json")], capture_output=True, text=True, creationflags=FLAGS)
        intake = json.loads((out / "intake.json").read_text()) if (out / "intake.json").exists() else {"evaluable": False, "error": r.stderr[-2000:]}
    rec["intake"] = {k: intake.get(k) for k in ("evaluable", "meshes", "flags", "scenes_in_file")}
    if not intake.get("evaluable"):
        rec["status"] = "no submission (not evaluable: no verified mesh)"
        (out / "submission.json").write_text(json.dumps(rec, indent=1)); print(rec["status"]); return
    meshes = [m for m in intake["meshes"] if m]
    mesh = meshes[0]
    if len(set(meshes)) > 1:
        import trimesh
        u = trimesh.util.concatenate([trimesh.load(m, force="mesh") for m in meshes])
        mesh = str(out / "united.stl"); u.export(mesh); rec["united_bodies"] = len(meshes)
    grounding = json.loads(Path(a.grounding).read_text()) if a.grounding and Path(a.grounding).exists() else {}
    margs, used = resolve(grounding, intake.get("scene_settings"))
    rec["material_resolution"] = used
    if a.prepare_only:
        import shutil
        shutil.copy(mesh, out / "mesh.stl" if str(mesh).lower().endswith(".stl") else out / Path(mesh).name)
        mname = "mesh.stl" if str(mesh).lower().endswith(".stl") else Path(mesh).name
        jobs = [{"run": out.name, "tag": tag, "mesh": mname, "args": ["--h2", a.h2, *margs, *extra], "out": f"judge_{tag}.json"}
                for tag, extra in (("primary", []), ("sensitivity_datasheet", ["--datasheet"]))]
        (out / "judge_jobs.json").write_text(json.dumps(jobs, indent=1))
        rec["status"] = "prepared"
        (out / "submission.json").write_text(json.dumps(rec, indent=1, default=str)); print(rec["status"]); return
    for tag, extra in (("primary", []), ("sensitivity_datasheet", ["--datasheet"])):
        r = subprocess.run([PY, str(HERE / "judge.py"), "--mesh", mesh, "--h2", a.h2, *margs, *extra,
                            "--out", str(out / f"judge_{tag}.json")], capture_output=True, text=True, creationflags=FLAGS)
        rec[tag] = {"returncode": r.returncode, "stdout_tail": r.stdout[-3000:], "stderr_tail": r.stderr[-2000:]}
    rec["status"] = "scored"
    (out / "submission.json").write_text(json.dumps(rec, indent=1, default=str))
    print(rec["status"])


if __name__ == "__main__":
    main()
