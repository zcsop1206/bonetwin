"""Exact checks of the machinery on a grid aligned to the block (h = 1.0 fits 30 x 20 x 12 exactly): a solid block must
return its own material, bone-equivalent must return lambda = 1. Off-grid blocks carry a first-order boundary error (Q = 0.022 at h = 0.8)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import goal_metric as G
import make_kat as K

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
p = out / "solid.stl"; K.save(K.shapes()["solid_block"], p)
C_bone = G.J.load_cases()[0]
r = G.score_mesh(str(p), G.matargs("bone_equivalent"), h2=1.0, levels=1, log=lambda s: None)
s = r["levels"]["h2"]["states"]
print("bone_equivalent solid: Q_alone", s["alone"]["Q"], "Q_fused", s["fused"]["Q"], "M", r["M_R"])
assert s["alone"]["Q"] < 1e-3 and s["fused"]["Q"] < 1e-3
r = G.score_mesh(str(p), G.matargs("tough1500"), h2=1.0, levels=1, log=lambda s: None)
C = np.array(r["levels"]["h2"]["states"]["alone"]["C_eff_MPa"])
Ci = G.fe.iso_C(r["material"]["E"], r["material"]["nu"])
err = np.abs(C - Ci).max() / Ci.max()
print("tough solid: max |C_eff - C_iso| / C11 =", err, "Q", r["M_R"], "expected worst ln", np.log(G.stiffness_ratio(Ci, C_bone).max()))
assert err < 1e-3
print("OK")
