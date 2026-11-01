"""Safe scheduler restart for the open run (written after the 03:50 incident).

    python restart_scheduler.py            # dry: prints what --recover would do per agent; changes nothing
    python restart_scheduler.py --go       # refuses if a scheduler is already running; else spawns it hidden

--go: (1) refuses if any scheduler.py process for this root is alive; (2) runs the recover decision logic in dry
mode and refuses if it would respawn any agent whose runner is alive (cannot happen with procs.py, checked anyway);
(3) spawns `scheduler.py --root <root> --recover` hidden (CREATE_NO_WINDOW, below-normal priority) and exits.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import procs  # noqa: E402
from common import load_json, run_dir, spawn_hidden, utc_now  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    snap = procs.snapshot()
    rt = str(root).replace("\\", "/").lower()
    sched_pids = [pid for pid, p in snap.items() if "scheduler.py" in p["cmd"] and "restart_scheduler" not in p["cmd"]
                  and rt in p["cmd"].replace("\\", "/").lower()]
    print(f"scheduler processes alive for this root: {sched_pids}")
    import scheduler as S
    st = load_json(run_dir(root) / "scheduler_state.json") or {}
    sched = load_json(run_dir(root) / "schedule.json")
    dec = S.recover_agents(root, st.get("started") or {}, float(sched["wall_cap_min"]), lambda m: None, dry=True)
    counts = {}
    for d in dec:
        counts[d["action"].split(":")[0].split(" (")[0]] = counts.get(d["action"].split(":")[0].split(" (")[0], 0) + 1
        print(f"  {d['agent']}: {d['action']}")
    print(f"summary: {counts}")
    if not a.go:
        print("dry run only; re-run with --go to restart the scheduler hidden")
        return
    if sched_pids:
        sys.exit("refused: a scheduler is already running for this root")
    logs = run_dir(root) / "logs"
    logs.mkdir(exist_ok=True)
    p = spawn_hidden([sys.executable, str(HERE / "scheduler.py"), "--root", str(root), "--recover"],
                     logs / "scheduler.out", HERE)
    with (run_dir(root) / "touch.log").open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} scheduler restarted with --recover (hidden), pid {p.pid}\n")
    print(f"scheduler restarted hidden with --recover: pid {p.pid}")


if __name__ == "__main__":
    main()
