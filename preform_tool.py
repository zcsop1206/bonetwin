"""PreForm adapter: the one place the code touches Formlabs PreForm.

This public copy ships only a MOCK. It contains no PreForm endpoint names, request bodies or API documentation.
Real use needs your own authorized PreForm access: write a module with the same functions (same names, same
return shapes as the mock below) and point BT_PREFORM_ADAPTER at its file path. Nothing in this repo was written
from, or should be filled in from, material you are not entitled to share.

Contract (all arguments and results are plain JSON-able Python values):
    server_up() -> version string or "" ; start_server(exe_path) -> None
    call(op, body=None) -> dict          # generic, used by the agents' tool proxy
    create_scene(settings), import_model(scene, file), get_scene(scene), delete_scene(scene), open_form(file),
    body_count(scene), validate(scene, check, **opts), auto_support(scene), auto_layout(scene, seed=0),
    save_form(file, scenes, name), list_settings(), estimate_time(scene)
    get_catalog(folder) -> dict ; resolve_setting(catalog, printer, resin, layer_mm) -> dict with
        scene_settings, setting_label, printer_label, material_label
    safe(fn, *a, **k) -> fn's result, or {"error": str}

Scene records returned by get_scene/open_form use this repo's own schema: {"scene_id", "scene_settings",
"models": [{"id", "name", "bounding_box": {"min_corner", "max_corner"}, "canonical_model_hash", "raw_mesh_hash",
"original_file", "position", "orientation", "scale", "units", "has_supports"}]}. A real adapter translates into it.

CLI (used by tools/bt_tool.py's "preform" wrapper):  python preform_tool.py [--manifest M --out D] spec|materials|layout
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

OPS = ["create_scene", "import_model", "get_scene", "delete_scene", "open_form", "body_count", "validate",
       "auto_support", "auto_layout", "save_form", "list_settings", "estimate_time"]


def _load_real():
    p = os.environ.get("BT_PREFORM_ADAPTER", "")
    if not p:
        return None
    spec = importlib.util.spec_from_file_location("preform_adapter_private", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_REAL = _load_real()


def safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:  # pragma: no cover
        return {"error": str(e)}


# ------------------------------------------------------------------ mock
_SCENES = {}


def _mesh_record(file, name="implant"):
    f = Path(file)
    data = f.read_bytes() if f.exists() else b""
    lo, hi = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    try:
        import trimesh
        m = trimesh.load(str(f), force="mesh")
        lo, hi = [float(x) for x in m.bounds[0]], [float(x) for x in m.bounds[1]]
    except Exception:
        pass
    h = hashlib.sha256(data).hexdigest()
    return {"id": h[:12], "name": name, "bounding_box": {"min_corner": dict(zip("xyz", lo)),
                                                         "max_corner": dict(zip("xyz", hi))},
            "canonical_model_hash": h, "raw_mesh_hash": h, "original_file": str(f.resolve()),
            "position": {"x": 0, "y": 0, "z": 0}, "orientation": {"x": 0, "y": 0, "z": 1}, "scale": 1.0,
            "units": "mm", "has_supports": False}


def _new_scene(settings=None):
    sid = f"mock{len(_SCENES) + 1}"
    _SCENES[sid] = {"scene_id": sid, "scene_settings": dict(settings or {}), "models": []}
    return sid


def _mock_call(op, body=None):
    b = body or {}
    if op == "create_scene":
        return {"scene_id": _new_scene(b.get("settings"))}
    if op == "import_model":
        rec = _mesh_record(b["file"], b.get("name", "implant"))
        _SCENES[b["scene"]]["models"].append(rec)
        return {"new_models": [{"model_id": rec["id"]}]}
    if op == "get_scene":
        return _SCENES[b["scene"]]
    if op == "delete_scene":
        _SCENES.pop(b.get("scene"), None)
        return {"deleted": True}
    if op == "save_form":
        models = [m for s in b.get("scenes", []) for m in _SCENES.get(s, {}).get("models", [])]
        Path(b["file"]).write_text(json.dumps({"mock_form": 1, "models": [m["original_file"] for m in models]}))
        return {"saved": b["file"]}
    if op == "open_form":
        try:
            d = json.loads(Path(b["file"]).read_text())
        except Exception:
            d = {"models": []}
        sid = _new_scene({"note": "mock"})
        for mf in d.get("models", []):
            _SCENES[sid]["models"].append(_mesh_record(mf))
        return {"scenes": [{"scene_id": sid}]}
    if op == "body_count":
        return {"mock": True, "bodies": 1}
    if op in ("validate", "auto_support", "auto_layout", "estimate_time"):
        return {"mock": True, "op": op, "ok": True}
    if op == "list_settings":
        return {"mock": True, "settings": [{"printer": "MockPrinter", "material": "MockResin", "layer_mm": 0.1}]}
    raise ValueError(f"unknown op {op!r}; ops: {', '.join(OPS)}")


# ------------------------------------------------------------------ contract
def server_up():
    return _REAL.server_up() if _REAL else "mock"


def start_server(exe):
    if _REAL:
        return _REAL.start_server(exe)
    return None


def call(op, body=None):
    if op not in OPS:
        raise ValueError(f"unknown op {op!r}; ops: {', '.join(OPS)}")
    return _REAL.call(op, body) if _REAL else _mock_call(op, body)


def create_scene(settings):
    return call("create_scene", {"settings": settings})["scene_id"]


def import_model(scene, file, name="implant"):
    return call("import_model", {"scene": scene, "file": str(file), "name": name})


def get_scene(scene):
    return call("get_scene", {"scene": scene})


def delete_scene(scene):
    return call("delete_scene", {"scene": scene})


def open_form(file):
    return call("open_form", {"file": str(file)})


def body_count(scene):
    return call("body_count", {"scene": scene})


def validate(scene, check, **opts):
    return call("validate", {"scene": scene, "check": check, **opts})


def auto_support(scene):
    return call("auto_support", {"scene": scene})


def auto_layout(scene, seed=0):
    return call("auto_layout", {"scene": scene, "seed": seed})


def save_form(file, scenes, name="implant"):
    return call("save_form", {"file": str(file), "scenes": list(scenes), "name": name})


def list_settings():
    return call("list_settings")


def estimate_time(scene):
    return call("estimate_time", {"scene": scene})


def get_catalog(folder):
    return _REAL.get_catalog(folder) if _REAL else {"mock": True}


def resolve_setting(catalog, printer, resin, layer_mm):
    if _REAL:
        return _REAL.resolve_setting(catalog, printer, resin, layer_mm)
    return {"scene_settings": {"printer": printer, "material": resin, "layer_mm": layer_mm},
            "setting_label": f"{resin} {layer_mm} mm (mock)", "printer_label": printer, "material_label": resin}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest")
    ap.add_argument("--out")
    ap.add_argument("cmd", choices=["spec", "materials", "layout"])
    ap.add_argument("rest", nargs="*")
    a, _ = ap.parse_known_args()
    if _REAL and hasattr(_REAL, "cli"):
        return _REAL.cli(sys.argv[1:])
    print(json.dumps({"mock": True, "cmd": a.cmd, "manifest": a.manifest, "out": a.out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
