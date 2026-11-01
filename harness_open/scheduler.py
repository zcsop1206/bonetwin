"""Admission-controlled scheduler for the OPEN run (spawned hidden by launch_open_run.py, which then exits).

    python scheduler.py --root R [--recover]

Units, in the pre-registered order (schedule.json "units"): groups (collective_r1, planner_r1, ..., collective_r2,
planner_r2) start as whole groups of 6; fill units (best_of_n and single agents, r1/r2 alternating) start one by
one. Every check (30 s) the scheduler starts the next startable units while ALL of these hold:
    running sessions + unit size <= max_sessions (14)
    free RAM >= min_free_ram_gb (3.0) + session_ram_gb x (unit size - 1)
    1-minute CPU < max_cpu_pct (85)
    now < last_start (05:00)
Groups take priority over fills; a waiting group never blocks fills that fit. Every session gets the same wall cap
(90 min) from its own start; a group's six share the group's start. Notices fire per session at cap-30 and cap-10 min
(written to the agent's notices_due.json, shown once by the meter hook). A run's arm is collected (collect.py --item) as
soon as all its units have started and stopped; at the hard deadline (08:30) anything still running is stopped and
collected; units not started by the last start time (06:30) are recorded as no submission. Every child runs hidden (CREATE_NO_WINDOW) at below-normal priority.
metrics/scheduler.jsonl: counts, RAM, CPU only; metrics/groups.json: group start/stop times (for the live
intervention). --recover restores state; live agents are never respawned (procs.py liveness); see recover_agents.
"""
import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (FINAL_STATES, HERE, CpuMeter, agent_dir, append_jsonl, free_ram_gb, load_config,  # noqa: E402
                    load_json, local_now, read_jsonl, run_dir, spawn_hidden, utc_now, write_json)

NOTICE = ("NOTICE (automated, identical for every agent): {m} minutes left in your 90-minute session window. "
          "Deliverables not in place when the window closes mean no submission.")


def admit(busy, n, free_ram, cpu, ad):
    """Admission rule: slots, free RAM (min + per extra session of the unit; groups use group_extra_session_ram_gb),
    1-minute CPU."""
    extra = ad.get("group_extra_session_ram_gb", ad["session_ram_gb"]) if n > 1 else ad["session_ram_gb"]
    return (busy + n <= ad["max_sessions"] and free_ram >= ad["min_free_ram_gb"] + extra * (n - 1)
            and cpu < ad["max_cpu_pct"])


def ukey(u):
    return u["key"]


def status(root, run_id, arm, aid):
    return (load_json(agent_dir(root, run_id, arm, aid) / "status.json") or {}).get("state")


def unit_done(root, u):
    return all(status(root, u["run_id"], u["arm"], a) in FINAL_STATES for a in u["agents"])


def running(root, started):
    return sum(1 for u in started.values() for a in u["agents"]
               if status(root, u["run_id"], u["arm"], a) not in FINAL_STATES)


def start_unit(root, u, cap_min, log, recover=False, hard=None):
    t0 = local_now()
    stop = t0 + dt.timedelta(minutes=cap_min) if not recover else dt.datetime.fromisoformat(u["stop_at"])
    if hard is not None:
        stop = min(stop, hard)  # nothing runs past the hard deadline
    logs = run_dir(root) / "logs"
    logs.mkdir(exist_ok=True)
    for aid in u["agents"]:
        d = agent_dir(root, u["run_id"], u["arm"], aid)
        if not recover:
            write_json(d / "notices_due.json", [
                {"id": f"n{i + 1}", "due": (stop - dt.timedelta(minutes=m)).isoformat(), "text": NOTICE.format(m=m)}
                for i, m in enumerate((30, 10))])
        argv = [sys.executable, str(HERE / "agent_runner.py"), "--agent-dir", str(d), "--stop-at", stop.isoformat()]
        if recover:
            argv.append("--recover")
        spawn_hidden(argv, logs / f"runner_{u['run_id']}_{u['arm']}_{aid}.log", HERE)
    u = dict(u, started=t0.isoformat(), stop_at=stop.isoformat())
    log(f"started {u['key']} ({len(u['agents'])} sessions, stop {stop:%H:%M})")
    return u


def billing_metrics(root, started, mdir):
    """Every 5 min: running API spend (closed + live, list price) and turn counts by billing source (numbers only)."""
    import billing
    closed, live = billing.spend(root)
    turns = {"subscription": 0, "api": 0}
    for u in started.values():
        for aid in u["agents"]:
            for r in read_jsonl(agent_dir(root, u["run_id"], u["arm"], aid) / "billing.jsonl"):
                if r.get("billing") in turns and "msg" in r:
                    turns[r["billing"]] += 1
    sources, switches = {}, []
    for u in started.values():
        for aid in u["agents"]:
            rows = read_jsonl(agent_dir(root, u["run_id"], u["arm"], aid) / "billing.jsonl")
            key = f"{u['run_id']}/{u['arm']}/{aid}"
            src = "subscription"
            for r in rows:
                if r.get("event") == "billing_switch":
                    src = r.get("billing", src)
                    switches.append({"session": key, "to": r.get("billing"), "utc": r.get("ts")})
            if status(root, u["run_id"], u["arm"], aid) not in FINAL_STATES:
                sources[key] = src
    append_jsonl(mdir / "billing.jsonl", {"utc": utc_now(), "api_spend_usd_closed": round(closed, 4),
                                          "api_spend_usd_live": round(live, 4), "turns": turns,
                                          "api_cap_usd": load_config().get("overflow_api", {}).get("spend_cap_usd"),
                                          "running_by_source": dict(__import__("collections").Counter(sources.values())),
                                          "session_source": sources, "switches": switches})


def collect_item(root, item, log):
    r = subprocess.run([sys.executable, str(HERE / "collect.py"), "--root", str(root), "--item", item],
                       capture_output=True, text=True, cwd=str(HERE),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    log(f"collected {item}: exit {r.returncode}")


def force_stop(root, u, log):
    """Hard deadline: stop a still-running session tree and mark it final, so its unit can be collected."""
    for aid in u["agents"]:
        d = agent_dir(root, u["run_id"], u["arm"], aid)
        st = load_json(d / "status.json") or {}
        if st.get("state") in FINAL_STATES:
            continue
        if st.get("runner_pid") and os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(st["runner_pid"]), "/T", "/F"], capture_output=True)
        time.sleep(1)
        st = load_json(d / "status.json") or st
        write_json(d / "status.json", dict(st, state="safety_cap", reason="hard deadline", ended=utc_now()))
        log(f"hard deadline: stopped {u['key']}/{aid}")


def recover_agents(root, started, cap_min, log, dry=False):
    """Fixed after the 03:50 incident. Never respawn a live agent: liveness = recorded runner pid alive with this
    agent's command line and a creation time before its last status, or any runner naming its folder, or a claude
    child of its runner (procs.py). An agent whose runner is gone counts as stopped (final state no_final,
    reason recorded) unless its last model process started and never ended (crashed mid-turn); such an agent is
    respawned with --recover at most once per agent for the whole night (run/recover_log.json)."""
    import procs
    snap = procs.snapshot()
    rlog_f = run_dir(root) / "recover_log.json"
    rlog = load_json(rlog_f, {}) or {}
    decisions = []
    for u in started.values():
        for aid in u["agents"]:
            d = agent_dir(root, u["run_id"], u["arm"], aid)
            stt = load_json(d / "status.json") or {}
            key = f"{u['run_id']}/{u['arm']}/{aid}"
            if stt.get("state") in FINAL_STATES:
                decisions.append({"agent": key, "action": "final already", "state": stt.get("state")})
                continue
            alive, why, pids = procs.agent_alive(snap, d, stt)
            if alive:
                decisions.append({"agent": key, "action": "alive: left alone", "why": why, "pids": pids})
                continue
            if procs.crashed_mid_turn(d) and rlog.get(key, 0) < 1 and local_now() < dt.datetime.fromisoformat(u["stop_at"]):
                decisions.append({"agent": key, "action": "respawn once (crashed mid-turn)", "why": why})
                if not dry:
                    rlog[key] = rlog.get(key, 0) + 1
                    start_unit(root, dict(u, agents=[aid]), cap_min, log, recover=True)
                continue
            decisions.append({"agent": key, "action": "runner gone: marked stopped", "why": why,
                              "respawned_before": rlog.get(key, 0)})
            if not dry:
                write_json(d / "status.json", dict(stt, state="no_final", reason="runner gone at scheduler recover",
                                                   ended=utc_now()))
    if not dry:
        write_json(rlog_f, rlog)
    mdir = Path(root) / load_config().get("metrics_dir", "metrics")
    mdir.mkdir(parents=True, exist_ok=True)
    append_jsonl(mdir / "recover_decisions.jsonl", {"utc": utc_now(), "dry": dry, "decisions": decisions})
    for x in decisions:
        log(f"recover: {x['agent']}: {x['action']}")
    return decisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--poll", type=float)
    ap.add_argument("--recover", action="store_true")
    ap.add_argument("--dry-recover", action="store_true", help="print the recover decisions only; change nothing")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    sched = load_json(run_dir(root) / "schedule.json")
    cfg = load_config()
    # live admission values: config.json overrides the launch-time copy in schedule.json (so the evaluator's 03:55
    # change to max_sessions 12 / min_free_ram_gb 3.5 takes effect on a restart)
    ad = dict(sched["admission"], **{k: v for k, v in (cfg.get("admission") or {}).items()
                                     if k in ("max_sessions", "min_free_ram_gb", "session_ram_gb", "max_cpu_pct",
                                              "check_s", "group_extra_session_ram_gb")})
    cap_min = float(sched["wall_cap_min"])
    last_start = dt.datetime.fromisoformat(sched["last_start"])
    hard = dt.datetime.fromisoformat(sched["hard_deadline"])
    items = {}
    for u in sched["units"]:
        items.setdefault(u["item"], []).append(u["key"])
    poll = a.poll or float(ad.get("check_s", 30))
    pending = [dict(u) for u in sched["units"]]
    started, collected = {}, set()
    mdir = root / cfg.get("metrics_dir", "metrics")
    mdir.mkdir(parents=True, exist_ok=True)
    logf = run_dir(root) / "scheduler.log"

    def log(msg):
        with logf.open("a", encoding="utf-8") as f:
            f.write(f"{utc_now()} {msg}\n")

    if a.recover:
        st = load_json(run_dir(root) / "scheduler_state.json") or {}
        for k, u in (st.get("started") or {}).items():
            started[k] = u
        collected = set(st.get("collected", []))
        pending = [u for u in pending if u["key"] not in started]
        recover_agents(root, started, cap_min, log, dry=a.dry_recover)
        log(f"RECOVER: {len(started)} started units restored")
        if a.dry_recover:
            return
    cpu = CpuMeter(60)
    groups = load_json(mdir / "groups.json", {}) or {}
    snap_every, last_snap = 60 * float(sched.get("kb_snapshot_minutes", 10)), 0.0
    last_bill = 0.0
    log(f"admission in force: {ad}")
    log(f"scheduler up: {len(pending)} units, max {ad['max_sessions']} sessions, cap {cap_min:g} min, "
        f"last start {last_start:%H:%M}")
    while True:
        now = local_now()
        ram, load = free_ram_gb(), cpu.sample()
        busy = running(root, started)
        startable = now < last_start
        did = []
        order = [u for u in pending if u["kind"] == "group"] + [u for u in pending if u["kind"] != "group"]
        for u in order:  # groups first (in order), then fills (in order); one pass per check
            if not startable:
                break
            n = len(u["agents"])
            if u["kind"] != "group":
                g = next((x for x in pending if x["kind"] == "group"), None)
                if g is not None and busy + len(g["agents"]) <= ad["max_sessions"] and                         not admit(busy, len(g["agents"]), ram, load, ad):
                    break  # a group is waiting only for RAM/CPU: fills must not take that headroom
            if not admit(busy, n, ram, load, ad):
                if u["kind"] == "group":
                    continue  # a group waiting for slots does not block fills that fit
                break
            su = start_unit(root, u, cap_min, log, hard=hard)
            started[u["key"]] = su
            pending.remove(u)
            busy += n
            ram -= ad["session_ram_gb"] * n  # until the next measurement
            did.append(u["key"])
            if u["kind"] == "group":
                groups[u["key"]] = {"start": su["started"], "stop": su["stop_at"]}
                write_json(mdir / "groups.json", groups)
        if now >= hard + dt.timedelta(minutes=2):
            for u in started.values():
                if not unit_done(root, u):
                    force_stop(root, u, log)
        for item, keys in items.items():  # a run's arm is collected once all its units have started and stopped
            if item not in collected and all(k in started and unit_done(root, started[k]) for k in keys):
                collect_item(root, item, log)
                collected.add(item)
        append_jsonl(mdir / "scheduler.jsonl", {"utc": utc_now(), "running": busy, "pending_units": len(pending),
                                                "started_units": len(started), "collected_units": len(collected),
                                                "free_ram_gb": round(ram, 2), "cpu_pct_1min": load,
                                                "started_now": len(did)})
        write_json(run_dir(root) / "scheduler_state.json", {"utc": utc_now(), "started": started,
                                                             "collected": sorted(collected),
                                                             "pending": [u["key"] for u in pending], "pid": os.getpid()})
        if time.time() - last_bill >= 300:
            last_bill = time.time()
            billing_metrics(root, started, mdir)
        if time.time() - last_snap >= snap_every:
            last_snap = time.time()
            subprocess.run([sys.executable, str(HERE / "process_metrics.py"), "--root", str(root), "--snapshot"],
                           capture_output=True, cwd=str(HERE), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        no_more = not pending or not startable
        if no_more and all(unit_done(root, u) for u in started.values()):
            if pending:
                log(f"not started before {last_start:%H:%M}: {[u['key'] for u in pending]} (no submission)")
            for step in (["collect.py", "--final"], ["process_metrics.py"], ["manipulation.py"]):
                r = subprocess.run([sys.executable, str(HERE / step[0]), "--root", str(root), *step[1:]],
                                   capture_output=True, text=True, cwd=str(HERE),
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                log(f"{step[0]} exit {r.returncode}")
            log("all units done and collected; scheduler exits")
            break
        time.sleep(poll)


if __name__ == "__main__":
    main()
