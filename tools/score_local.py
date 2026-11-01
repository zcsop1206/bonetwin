"""score_local.py: run the frozen goal metric (addendum 4) on your own deliverables, without the sealed load case.

The frozen judge loads the 3 visible lumbar load cases from targets/targets.json plus a 4th sealed case from
targets/sealed_case.json, which is not in this repo. This wrapper does not modify any frozen file. If
sealed_case.json is absent, it replaces judge.load_cases at runtime with the visible-only version, so the integrity
rule (IA) is checked on 3 cases instead of 4. Everything else (M, windows, gates, ranking, ties) is the frozen code.
The official evaluation uses all 4 cases, the full resolution and one further check, so a local pass is necessary
but not sufficient.

  python tools/score_local.py --mesh my_run/implant.stl --material tough1500 --out gm.json --fallback
  python tools/score_local.py --mesh my_run/implant.stl --material rigid10k --out gm.json
  python tools/score_local.py --mesh x.stl --E 4000 --nu 0.4 --strength 98 --out gm.json   (declared material)

All goal_metric.py options pass through. --folder mode is not supported here (its workers are separate processes
that load the frozen judge directly); score one mesh per call.
"""
import hashlib
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GM = ROOT / "sim" / "goal_metric" / "goal_metric.py"
TARGETS = ROOT / "targets" / "targets.json"
SEALED = ROOT / "targets" / "sealed_case.json"


def main():
    if "--folder" in sys.argv:
        sys.exit("score_local.py scores one mesh per call (--mesh); see its docstring")
    if not TARGETS.exists():
        sys.exit(f"missing {TARGETS}: see CHALLENGE.md, 'Bone targets'")
    sys.path.insert(0, str(ROOT / "sim" / "judge"))
    import judge as J  # the frozen judge, imported read-only

    if not SEALED.exists():
        def load_cases_visible():
            t = json.loads(TARGETS.read_text())
            site = t["sites"]["lumbar_vertebra"]
            C = J.np.array(site["material"]["stiffness_voigt_MPa"], float)
            key = "stress_voigt_MPa_[11,22,33,23,13,12]"
            cases = [(c["name"], J.fe.sigma_tensor(c[key]), False) for c in site["load_cases_visible"]]
            return C, cases, {"targets_sha256": hashlib.sha256(TARGETS.read_bytes()).hexdigest(),
                              "sealed_sha256": None, "note": "visible cases only (score_local.py)"}
        J.load_cases = load_cases_visible
        print("score_local: sealed_case.json absent; integrity checked on the 3 visible cases", file=sys.stderr)
    sys.argv[0] = str(GM)
    runpy.run_path(str(GM), run_name="__main__")


if __name__ == "__main__":
    main()
