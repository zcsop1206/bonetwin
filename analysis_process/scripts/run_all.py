"""Regenerate everything in analysis_process/ and check the experiment tree was not changed."""
import os
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
for s in ("compute_metrics.py", "write_reports.py", "make_figures.py"):
    r = subprocess.run([sys.executable, "-B", str(D / s)], capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(D))
    lines = r.stdout.splitlines()
    if s == "verify_highlights.py":
        lines = [x for x in lines if x.startswith(("BAD", "NOT IN", "bad"))]
    print(s, "exit", r.returncode, "|", " / ".join(x[:170] for x in lines[-4:]), r.stderr[-400:])
H = D.parent.parent / "harness_open"
latest = sorted(((f.stat().st_mtime, str(f)) for f in H.rglob("*") if f.is_file()), reverse=True)[:3]
import datetime as dt
print("newest files in harness_open:", [(dt.datetime.fromtimestamp(a).strftime("%H:%M:%S"), b[len(str(H)) + 1:]) for a, b in latest])
print("now", dt.datetime.now().strftime("%H:%M:%S"))
md = (D.parent / "metrics.md").read_text(encoding="utf-8")
print(md[md.index("## 12."):][:2600])
print((D.parent / "timeline.md").read_text(encoding="utf-8")[:1500])
for p in sorted(D.parent.rglob("*")):
    if p.is_file():
        print(p.relative_to(D.parent), p.stat().st_size)
