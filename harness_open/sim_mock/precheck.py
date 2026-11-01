"""MOCK of the judge's public pre-check tool: prints a primary-score estimate for a deliverables folder."""
import argparse
import hashlib
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--deliverables", default="deliverables")
ap.add_argument("--submission")
ap.add_argument("--folder")
a, _ = ap.parse_known_args()
d = Path(a.folder or a.submission or a.deliverables)
h = hashlib.sha256(b"".join(f.read_bytes() for f in sorted(d.glob("*")) if f.is_file())).hexdigest()
v = round(int(h[:6], 16) / 0xFFFFFF, 4)
print(json.dumps({"mock": True, "H": v, "gates_pass": v < 0.9, "primary_estimate": v}))
