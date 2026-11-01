"""MOCK control build (smoke tests): placeholder deliverables + determinism record, no PreForm, no gateway."""
import argparse
import hashlib
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True)
a = ap.parse_args()
out = Path(a.root) / "control" / "gibson_ashby_rigid10k"
(out / "kb").mkdir(parents=True, exist_ok=True)
d = json.dumps({"mock": True, "pitch": 5.0})
(out / "kb" / "control_design.json").write_text(d)
(out / "implant.stl").write_text("solid mock\nendsolid mock\n")
(out / "implant.form").write_bytes(b"MOCK FORM")
(out / "material_spec.json").write_text(json.dumps({"material": "Rigid 10K (mock)"}))
(out / "report.md").write_text("# mock control\n[design](kb/control_design.json)\n")
h = hashlib.sha256(d.encode()).hexdigest()
(out / "control_build.json").write_text(json.dumps({"determinism": {"sha256": h, "rerun": h, "identical": True}}))
print("mock control built")
