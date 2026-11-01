"""Smoke test of live_intervention.py on copies of a mocked smoke root (never the real run).

    python test_live_intervention.py --src smoke/s5

Case A (leader): copies src to smoke/lv_a, adds directive posts by c1 (>= 5, share > 2x mean), gives c1 a live dummy
runner process, runs the intervention on r1 immediately: c1's process must die, its status must be final with the
intervention reason, the decision logged, leadership.jsonl written with numbers only.
Case B (no leader): copies src to smoke/lv_b unchanged (c1 has 3 directive posts): no intervention, logged.
Case C: --run r1 on a non-smoke root is refused.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from board import Board  # noqa: E402
from common import load_json, read_jsonl, run_dir, write_json  # noqa: E402

OK = []


def check(name, ok, detail=""):
    OK.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(detail)[:160]})" if detail else ""))


def alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
    return str(pid) in out.stdout


def run(root, extra=()):
    return subprocess.run([sys.executable, str(HERE / "live_intervention.py"), "--root", str(root), "--run", "r1",
                           "--at", "now", "--until", "+0.15", "--interval-min", "0.05", *extra],
                          capture_output=True, text=True, timeout=300)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    a = ap.parse_args()
    src = (HERE / a.src).resolve()
    ra, rb = HERE / "smoke" / "lv_a", HERE / "smoke" / "lv_b"
    for r in (ra, rb):  # minimal copy: the collective arm's arm.json, board and status files only
        if r.exists():
            shutil.rmtree(r)
        sa, da = run_dir(src) / "r1" / "collective", run_dir(r) / "r1" / "collective"
        da.mkdir(parents=True)
        for name in ("arm.json", "board.jsonl"):
            shutil.copyfile(sa / name, da / name)
        for st in (sa / "agents").glob("*/status.json"):
            (da / "agents" / st.parent.name).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(st, da / "agents" / st.parent.name / "status.json")
    # case A: make c1 a leader by the rule, with a live dummy runner
    b = Board(run_dir(ra) / "r1" / "collective" / "board.jsonl")
    for k in range(4):
        b.post("c1", "chat", f"@c{2 + k % 5} run another sweep of the cage literature, part {k}")
    dummy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    sf = run_dir(ra) / "r1" / "collective" / "agents" / "c1" / "status.json"
    write_json(sf, dict(load_json(sf) or {}, state="running", runner_pid=dummy.pid))
    r = run(ra)
    time.sleep(1)
    dec = load_json(ra / "metrics" / "live_intervention.json") or {}
    st = load_json(sf) or {}
    check("A: leader found by the rule", dec.get("leader") == "c1", {k: dec.get(k) for k in ("directive_counts", "leader")})
    check("A: leader process terminated", not alive(dummy.pid), dummy.pid)
    check("A: leader status final, reason recorded (no restart path)", st.get("state") == "failed" and
          st.get("reason") == "removed_by_live_intervention", st.get("state"))
    lj = read_jsonl(ra / "metrics" / "leadership.jsonl")
    check("A: leadership.jsonl written repeatedly, numbers and ids only", len(lj) >= 2 and all(
        "removed_agent" in x and "directive_share" in x for x in lj), len(lj))
    blob = (ra / "metrics" / "leadership.jsonl").read_text(encoding="utf-8") + json.dumps(dec)
    check("A: no post text in metrics", "sweep" not in blob and "literature" not in blob)
    n_before = len(read_jsonl(run_dir(ra) / "r1" / "collective" / "board.jsonl"))
    check("A: nothing posted to the board", n_before == len(read_jsonl(run_dir(ra) / "r1" / "collective" /
                                                                          "board.jsonl")) and "launcher" not in
          {p["author"] for p in read_jsonl(run_dir(ra) / "r1" / "collective" / "board.jsonl")[-3:]})
    # case B: no leader
    r = run(rb)
    dec_b = load_json(rb / "metrics" / "live_intervention.json") or {}
    check("B: no leader -> no intervention, logged", dec_b.get("leader") is None and "no intervention" in
          dec_b.get("action", ""), dec_b.get("directive_counts"))
    # case D: the pre-registered trigger (group start + 60 min, until both collective windows close)
    import datetime as dt
    rd = HERE / "smoke" / "lv_d"
    if rd.exists():
        shutil.rmtree(rd)
    shutil.copytree(ra, rd)
    (rd / "metrics" / "live_intervention.json").unlink(missing_ok=True)
    (rd / "metrics" / "leadership.jsonl").unlink(missing_ok=True)
    now = dt.datetime.now().astimezone()
    write_json(rd / "metrics" / "groups.json", {"r1/collective": {"start": (now - dt.timedelta(minutes=61)).isoformat(),
                                                                  "stop": (now + dt.timedelta(seconds=20)).isoformat()}})
    t0 = time.time()
    r = subprocess.run([sys.executable, str(HERE / "live_intervention.py"), "--root", str(rd), "--run", "r1",
                        "--interval-min", "0.1"], capture_output=True, text=True, timeout=300)
    dd = load_json(rd / "metrics" / "live_intervention.json") or {}
    check("D: group+60 trigger acts at once when due, measures until the windows close", dd.get("utc") and
          read_jsonl(rd / "metrics" / "leadership.jsonl") and time.time() - t0 < 120, f"{time.time() - t0:.0f}s")
    # case C: r1 on a non-smoke root refused
    r = subprocess.run([sys.executable, str(HERE / "live_intervention.py"), "--root", str(HERE), "--run", "r1",
                        "--at", "now"], capture_output=True, text=True, timeout=60)
    check("C: collective replicate 1 is never touched on the real root", r.returncode != 0 and "refused" in r.stderr,
          r.stderr.strip()[-80:])
    dummy.kill() if dummy.poll() is None else None
    print(f"{sum(OK)}/{len(OK)} passed")
    return 0 if all(OK) else 1


if __name__ == "__main__":
    sys.exit(main())
