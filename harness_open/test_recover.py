"""Test scheduler --recover on a smoke copy with live dummy runners (never the real run).

    python test_recover.py --src smoke/s12

Agents in r1/collective are set up as: c1 live dummy runner (recorded pid, matching command line) -> left alone;
c2 recorded pid dead but another dummy runner names its folder -> left alone; c3 recorded pid = an unrelated live
process (recycled) and no runner -> stopped; c4 runner gone, last model process ended -> marked stopped;
c5 runner gone, crashed mid-turn -> respawned once; second recover -> c5 not respawned again.
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
from common import FINAL_STATES, load_json, read_jsonl, run_dir, write_json  # noqa: E402

OK = []


def check(name, ok, detail=""):
    OK.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(detail)[:200]})" if detail != "" else ""))


def dummy(agent_dir):
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)", "agent_runner.py", "--agent-dir",
                             str(agent_dir)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    a = ap.parse_args()
    root = HERE / "smoke" / "rec1"
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(HERE / a.src, root)
    rd = run_dir(root)
    st = load_json(rd / "scheduler_state.json")
    import datetime as dt
    now = dt.datetime.now().astimezone()
    for k, u in st["started"].items():  # make every started unit still inside its window
        u["stop_at"] = (now + dt.timedelta(minutes=30)).isoformat()
    write_json(rd / "scheduler_state.json", st)
    ag = {c: rd / "r1" / "collective" / "agents" / c for c in ("c1", "c2", "c3", "c4", "c5", "c6")}
    procs = {}
    procs["c1"] = dummy(ag["c1"])
    procs["c2"] = dummy(ag["c2"])
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    time.sleep(2)
    ts = now.isoformat()
    write_json(ag["c1"] / "status.json", {"agent": "c1", "state": "running", "runner_pid": procs["c1"].pid, "ts": ts})
    write_json(ag["c2"] / "status.json", {"agent": "c2", "state": "running", "runner_pid": 999999, "ts": ts})
    write_json(ag["c3"] / "status.json", {"agent": "c3", "state": "running", "runner_pid": unrelated.pid,
                                           "ts": (now - dt.timedelta(minutes=10)).isoformat()})
    write_json(ag["c4"] / "status.json", {"agent": "c4", "state": "running", "runner_pid": 999998, "ts": ts})
    write_json(ag["c5"] / "status.json", {"agent": "c5", "state": "running", "runner_pid": 999997, "ts": ts})
    with (ag["c4"] / "sessions.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "start"}) + "\n" + json.dumps({"event": "end"}) + "\n")
    with (ag["c5"] / "sessions.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "start"}) + "\n")
    before = set(p for p in procs_named(root))

    def recover(extra=()):
        r = subprocess.run([sys.executable, str(HERE / "scheduler.py"), "--root", str(root), "--recover",
                            "--dry-recover", *extra], capture_output=True, text=True, timeout=300,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        rows = read_jsonl(root / "metrics" / "recover_decisions.jsonl")
        return {d["agent"]: d for d in rows[-1]["decisions"]} if rows else {}

    dd = recover()
    act = {k.split("/")[-1]: v["action"] for k, v in dd.items() if k.startswith("r1/collective/")}
    check("dry recover: c1 live runner left alone", act.get("c1", "").startswith("alive"), act.get("c1"))
    check("dry recover: c2 another runner names its folder -> left alone", act.get("c2", "").startswith("alive"),
          act.get("c2"))
    check("dry recover: c3 recycled pid -> not alive", not act.get("c3", "").startswith("alive"), act.get("c3"))
    check("dry recover: c4 runner gone, ended cleanly -> marked stopped", "stopped" in act.get("c4", ""), act.get("c4"))
    check("dry recover: c5 crashed mid-turn -> respawn once", "respawn once" in act.get("c5", ""), act.get("c5"))
    check("dry recover changed nothing", (load_json(ag["c4"] / "status.json") or {}).get("state") == "running")
    # real recover (spawns the mock runner for c5 only), then a second recover must not respawn c5 again
    import importlib
    import scheduler as S
    importlib.reload(S)
    from common import load_config
    sched = load_json(rd / "schedule.json")
    started = load_json(rd / "scheduler_state.json")["started"]
    logs = []
    S.recover_agents(root, started, float(sched["wall_cap_min"]), logs.append, dry=False)
    time.sleep(3)
    after = procs_named(root)
    new = [p for p in after if p not in before and p not in (procs["c1"].pid, procs["c2"].pid)]
    check("real recover: exactly one runner spawned (c5), live agents untouched", len(new) == 1 and
          procs["c1"].poll() is None and procs["c2"].poll() is None, f"new runners {len(new)}")
    check("real recover: c4 marked stopped (final)", (load_json(ag["c4"] / "status.json") or {}).get("state")
          in FINAL_STATES)
    time.sleep(20)  # let the respawned mock runner finish
    dec2 = S.recover_agents(root, started, float(sched["wall_cap_min"]), logs.append, dry=True)
    c5 = next(d for d in dec2 if d["agent"].endswith("/c5"))
    check("second recover: c5 is never respawned twice", "respawn" not in c5["action"], c5["action"])
    for p in (*procs.values(), unrelated):
        p.kill()
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(new[0])], capture_output=True) if new else None
    print(f"{sum(OK)}/{len(OK)} passed")
    return 0 if all(OK) else 1


def procs_named(root):
    import procs as P
    snap = P.snapshot()
    a = str(root).replace("\\", "/").lower()
    mine = {pid for pid, p in snap.items() if "agent_runner.py" in p["cmd"] and a in p["cmd"].replace("\\", "/").lower()}
    return [pid for pid in mine if snap[pid]["ppid"] not in mine]  # a venv launcher + its python count once


if __name__ == "__main__":
    sys.exit(main())
