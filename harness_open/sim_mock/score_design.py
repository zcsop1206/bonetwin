"""MOCK of the bone-twin design gateway (bonetwin/sim/score_design.py, built in parallel). Same interface:

    python score_design.py --design d.json --target <site> [--fidelity frame|planestress] [--dim 3|2]
        -> prints signed JSON: run_id, target, fidelity, design_sha256, score, constraints, all_pass, signature

The physics here is a placeholder (a stiffness proxy, not a frame solve). Only the interface and the signing
contract matter, copied from bonetwin/sim/bt_common.py: key from env BT_GATEWAY_KEY; signature =
{"alg": "HMAC-SHA256", "value": HMAC(key, canonical JSON without "signature")}; unsigned when the key is absent.
With BT_GATEWAY_ADMIN set the record also carries a (mock) sealed-case score.
"""
import argparse
import hashlib
import hmac
import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOCK_TARGETS = {"site_A": {"E_target_MPa": 300.0, "axis": "z"}, "site_B": {"E_target_MPa": 120.0, "axis": "x"}}
E_SOLID = {"tough1500": 1500.0, "rigid10k": 10000.0}


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=float)


def sign(rec):
    key = os.environ.get("BT_GATEWAY_KEY")
    body = {k: v for k, v in rec.items() if k != "signature"}
    if not key:
        return {"alg": "HMAC-SHA256", "value": None, "note": "unsigned: BT_GATEWAY_KEY not set in this process"}
    return {"alg": "HMAC-SHA256", "value": hmac.new(key.encode(), canonical(body).encode(), hashlib.sha256).hexdigest()}


def evaluate(d, target, fidelity, dim):
    nodes, struts = d.get("nodes") or [], d.get("struts") or []
    box = d.get("box") or [float(d.get("block_mm", 20.0 if dim == 3 else 40.0))] * dim
    if len(box) != dim or any(len(n) != dim for n in nodes):
        raise ValueError(f"design is not {dim}-D (box and every node need {dim} coordinates)")
    t = float(d.get("thickness", 8.0)) if dim == 2 else box[2]
    widths = [float(s[2]) for s in struts] or [0.0]
    inside = all(-1e-9 <= c <= b + 1e-9 for n in nodes for c, b in zip(n, box))
    tgt = MOCK_TARGETS.get(target, {"E_target_MPa": 200.0, "axis": "y"})
    ax = min("xyz".index(tgt["axis"]), dim - 1)
    vol = math.prod(box)
    area = 0.0
    eff = 0.0
    for i, j, w in struts:
        a, b = nodes[int(i)], nodes[int(j)]
        L = math.dist(a, b)
        c = abs(b[ax] - a[ax]) / L if L else 0.0
        sec = w if dim == 2 else math.pi * w * w / 4  # 2-D: in-plane width; 3-D: strut diameter
        area += L * sec
        eff += L * sec * c ** 3
    rho = area / vol if vol else 0
    E = E_SOLID.get(d.get("material", "tough1500"), 1500.0) * eff / vol
    if fidelity == "planestress":
        E *= 0.9  # nodes and finite size soften the frame estimate
    score = abs(math.log(max(E, 1e-6) / tgt["E_target_MPa"])) + 0.5 * max(0.0, rho - 0.5)  # error: lower is better
    cons = {
        "min_strut_width_mm": {"value": min(widths), "limit": 0.5, "op": ">=", "pass": min(widths) >= 0.5},
        "max_strut_width_mm": {"value": max(widths), "limit": 3.0, "op": "<=", "pass": max(widths) <= 3.0},
        "nodes_inside_box": {"value": inside, "limit": True, "op": "==", "pass": inside},
        "porosity": {"value": round(1 - rho, 4), "limit": 0.5, "op": ">=", "pass": 1 - rho >= 0.5},
        "has_struts": {"value": len(struts), "limit": 1, "op": ">=", "pass": len(struts) >= 1},
        "material_rigid10k": {"value": d.get("material"), "limit": "rigid10k", "op": "==",
                              "pass": d.get("material") == "rigid10k"},
        "thickness_mm": {"value": t, "limit": [2.0, 25.0], "op": "in", "pass": 2.0 <= t <= 25.0},
    }
    return round(score, 6), cons, {"E_app_MPa": round(E, 3), "relative_density": round(rho, 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--fidelity", default="frame", choices=["frame", "voxel", "planestress"])
    ap.add_argument("--sealed", action="store_true")
    ap.add_argument("--dim", type=int, default=3, choices=[2, 3])
    a, _unknown = ap.parse_known_args()  # mock: accept the real gateway's extra flags (--voxel-h, --solver, ...)
    raw = Path(a.design).read_bytes()
    try:
        d = json.loads(raw.decode("utf-8"))
        score, cons, extra = evaluate(d, a.target, a.fidelity, a.dim)
        dsha = hashlib.sha256(canonical(d).encode()).hexdigest()
    except Exception as exc:  # invalid design: signed failure record
        score, cons, extra, dsha = None, {"valid_json_and_schema": {"value": str(exc)[:200], "pass": False}}, {}, \
            hashlib.sha256(raw).hexdigest()
    rec = {"run_id": "gw_" + uuid.uuid4().hex[:16], "gateway": "MOCK", "target": a.target, "fidelity": a.fidelity, "dim": a.dim,
           "design_sha256": dsha, "score": score, "constraints": cons,
           "all_pass": all(c.get("pass") for c in cons.values()), "outputs": extra,
           "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if score is not None:  # MOCK desirability parts in [0, 1] (the real gateway computes them; spec sim/desirability.json)
        import random as _r
        rr = _r.Random(dsha)
        des = {"d1_bone_match": round(max(0.0, 1 - score), 4), "d4_stress_margin": round(rr.uniform(0.3, 1), 4),
               "d5_porosity": round(rr.uniform(0.4, 1), 4), "d3_model_agreement": round(rr.uniform(0.2, 1), 4)}
        if a.sealed:
            des["d2_sealed_case"] = round(rr.uniform(0.2, 1), 4)
        des["D"] = round(min(des.values()), 4)
        rec["desirability"] = des
    if a.sealed:
        if os.environ.get("BT_GATEWAY_ADMIN") != "1":
            print(json.dumps({"ok": False, "error": "--sealed refused: BT_GATEWAY_ADMIN=1 is not set"}))
            return 3
        if score is not None:
            rec["sealed"] = {"score": round(score * 1.05 + 0.01, 6), "note": "MOCK sealed 4th case"}
    rec["signature"] = sign(rec)
    print(json.dumps(rec))


if __name__ == "__main__":
    sys.exit(main())
