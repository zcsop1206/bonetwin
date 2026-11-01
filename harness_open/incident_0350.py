"""Incident record for the 03:50 EST duplicate-runner event (counts, pids, times; never content).

    python incident_0350.py [--root R] [--from 03:44] [--to 03:58]

What happened (from the coordinator): the scheduler was stopped and restarted with --recover; the old recover code
respawned every non-final agent without checking liveness, so 14 duplicate runners (with --recover) ran for about
1-2 minutes beside the 14 live originals before they were killed. This script reads each agent's sessions.jsonl
(runner pids are logged on every event), the boards and tool logs, and the live process table, and writes
metrics/incident_0350.json: per agent, the original runner pid, other runner pids seen in the window, their
model-process starts and resumed session ids (ids only), board posts and tool calls in the window (counts),
and whether the original runner is alive now. manipulation.py reads the file and marks the affected agents.
"""
import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import procs  # noqa: E402
from common import append_jsonl, load_json, local_now, read_jsonl, run_dir, utc_now, write_json  # noqa: E402


def t(s):
    try:
        x = dt.datetime.fromisoformat(s)
        return x if x.tzinfo else x.astimezone()
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--from", dest="t0", default="03:44")
    ap.add_argument("--to", dest="t1", default="03:58")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    today = local_now()
    w0 = today.replace(hour=int(a.t0[:2]), minute=int(a.t0[3:]), second=0, microsecond=0)
    w1 = today.replace(hour=int(a.t1[:2]), minute=int(a.t1[3:]), second=0, microsecond=0)
    snap = procs.snapshot()
    agents, live_runner_procs = [], 0
    for f in sorted(run_dir(root).glob("*/*/arm.json")):
        m = load_json(f) or {}
        for g in m.get("agents", []):
            d = f.parent / "agents" / g["id"]
            if not d.exists():
                continue
            ev = read_jsonl(d / "sessions.jsonl")
            starts = [e for e in ev if e.get("event") == "start" and e.get("runner_pid")]
            if not starts:
                continue  # never started
            orig = starts[0]["runner_pid"]
            in_win = [e for e in ev if (t(e.get("ts")) or w0 - dt.timedelta(days=1)) >= w0
                      and (t(e.get("ts")) or w1) <= w1]
            dup_pids = sorted({e["runner_pid"] for e in in_win if e.get("runner_pid") and e["runner_pid"] != orig})
            dup_starts = [e for e in in_win if e.get("event") == "start" and e.get("runner_pid") in dup_pids]
            resumed = sorted({e.get("resume") for e in dup_starts if e.get("resume")})
            posts = [p for p in read_jsonl(f.parent / "board.jsonl")
                     if p.get("author") == g["id"] and w0 <= (t(p.get("ts")) or w0 - dt.timedelta(1)) <= w1]
            calls = [c for c in read_jsonl(d / "tool_calls.jsonl") if w0 <= (t(c.get("ts")) or w0 - dt.timedelta(1)) <= w1]
            st = load_json(d / "status.json") or {}
            alive, why, pids = procs.agent_alive(snap, d, dict(st, runner_pid=orig))
            live_runner_procs += len(pids)
            agents.append({
                "agent": f"{f.parent.parent.name}/{f.parent.name}/{g['id']}", "original_runner_pid": orig,
                "duplicate_runner_pids": dup_pids, "duplicate_model_starts": len(dup_starts),
                "duplicate_resumed_session_ids": resumed, "board_posts_in_window": len(posts),
                "tool_calls_in_window": len(calls), "tool_calls_in_window_by_tool": dict(Counter(
                    c.get("priced_as") or c.get("tool") for c in calls)),
                "status_state_now": st.get("state"), "status_runner_pid_now": st.get("runner_pid"),
                "original_alive_now": alive, "liveness": why, "affected": bool(dup_pids)})
    rec = {"incident": "0350 duplicate runners after scheduler --recover", "written_utc": utc_now(),
           "window_local": [w0.isoformat(), w1.isoformat()],
           "coordinator_counts": {"claude_sessions_before": 15, "claude_sessions_peak": 29, "duplicate_runner_trees_killed": 14,
                                  "processes_killed": 108, "stopped_scheduler_pids": [21700, 25296],
                                  "recovered_scheduler_pids_stopped": [26576, 12544],
                                  "after": {"agent_claude_sessions": 13, "original_runners": 13}},
           "cause": "scheduler.py --recover respawned every non-final agent without a liveness check (fixed: procs.py "
                    "liveness by pid + creation time + command line; runner-gone agents marked stopped unless their "
                    "original runner crashed mid-turn; at most one respawn per agent)",
           "n_agents_started": len(agents), "affected_agents": [x["agent"] for x in agents if x["affected"]],
           "agents_without_live_runner_now": [x["agent"] for x in agents if not x["original_alive_now"]
                                              and x["status_state_now"] not in ("done", "capped", "safety_cap",
                                                                                "failed", "no_final")],
           "agents": agents}
    md = root / "metrics"
    md.mkdir(parents=True, exist_ok=True)
    write_json(md / "incident_0350.json", rec)
    with (run_dir(root) / "touch.log").open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} incident 0350 recorded: {len(rec['affected_agents'])} agents had duplicate runners\n")
    print(json.dumps({k: rec[k] for k in ("n_agents_started", "affected_agents", "agents_without_live_runner_now")},
                     indent=1))


if __name__ == "__main__":
    main()
