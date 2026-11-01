"""Build figures 1 to 6 and the results template, one process at a time to stay light on memory.

    python build_all.py

Titanium: write figures/ti_modulus.json, then re-run this or stiffness_ladder.py alone.
Results: python results_plot.py <data.json> --name results (schema in that script's docstring).
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NO_WINDOW = 0x08000000
BELOW_NORMAL = 0x00004000
JOBS = [["stiffness_ladder.py"], ["comm_graphs.py"], ["sessions.py"], ["rubric_map.py"],
        ["results_plot.py", str(HERE / "results_template_data.json"), "--name", "results_template"]]
for job in JOBS:
    args = [sys.executable, "-B", str(HERE / job[0])] + job[1:]
    if len(sys.argv) > 1 and job[0].split(".")[0] not in sys.argv[1:]:
        continue
    print(">>", job[0], flush=True)
    r = subprocess.run(args, cwd=str(HERE), creationflags=NO_WINDOW | BELOW_NORMAL)
    if r.returncode:
        sys.exit(r.returncode)
