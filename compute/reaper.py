"""reaper: deletes Brev instances that are wasting the night's credit.

Every reaper_interval_s (120 s) it deletes, logging each to compute_ledger.jsonl:
  - idle:    GPU util < idle_util_pct (5 %) and no exec/copy for idle_minutes (15)
             (an exec still inside its timeout counts as activity)
  - cap:     the instance's run has accrued >= its cap
  - orphan:  carries one of our run prefixes (bt-<run_id>-) but has no ledger start,
             or the ledger says deleted and it is still listed
  - stuck:   never became reachable within boot_grace_minutes (25) of its start
  - curfew:  everything of ours at hard_stop_local (07:15)
Instances whose names do not start with one of our run prefixes are never touched.

All state lives in the ledger, so a restart loses nothing.
  python reaper.py            # loop forever (wrap in run_reaper.cmd to auto-restart)
  python reaper.py --once     # one pass
  python reaper.py --dry-run  # one pass, report only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

import bt_compute as bt

HEARTBEAT = os.path.join(bt.HERE, "reaper_heartbeat.json")


def probe_util(name: str) -> float | None:
    r = bt.remote(name, "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits",
                  timeout=90)
    if r.returncode != 0:
        return None
    vals = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.replace(".", "", 1).isdigit():
            vals.append(float(line))
    return max(vals) if vals else None


def idle_since(i: dict, util_pct: float) -> float:
    """Start of the current idle stretch: the later of the last exec/copy activity
    and the last probe that saw the GPU busy."""
    since = i["last_exec"]
    for t, u in i["probes"]:
        if u is not None and u >= util_pct:
            since = max(since, t)
    return since


def one_pass(dry: bool = False) -> list[str]:
    c = bt.caps()
    now = time.time()
    acts = []
    inst = bt.state()
    try:
        listed = bt.brev_ls()
    except Exception as e:
        bt.append({"action": "reaper_error", "why": f"brev ls: {e}"[:300]})
        return [f"brev ls failed: {e}"]
    curfew = now >= bt.hard_stop_epoch()

    def kill(name, rid, why):
        acts.append(f"{why}: {name}")
        if not dry:
            bt.terminate(name, rid, "reap", why)

    for w in listed:
        name = w.get("name", "")
        rid = bt.ours(name)
        if rid is None:
            continue  # not ours: never touch
        if str(w.get("status", "")).upper() in ("DELETING", "DELETED", "STOPPING", "STOPPED"):
            continue
        i = inst.get(name)
        if curfew:
            kill(name, rid, "curfew 07:15")
            continue
        if i is None or not i["live"]:
            kill(name, rid, "orphan (no live ledger entry)")
            continue
        spent, cap, _ = bt.cap_status(rid, inst)
        # kill one pass early so the cap is not overrun by up to a whole interval
        if spent + i["rate"] * c["reaper_interval_s"] / 3600.0 >= cap:
            kill(name, rid, f"run {rid} hit cap ${cap:.2f}")
            continue
        ready = (w.get("shell_status") == "READY") or (w.get("status") == "RUNNING")
        if not ready:
            if now - i["t_start"] > c["boot_grace_minutes"] * 60:
                kill(name, rid, f"not ready {c['boot_grace_minutes']} min after start")
            continue
        open_exec = any(deadline > now for deadline in i["open_execs"].values())
        util = probe_util(name)
        if not dry:
            bt.append({"action": "probe", "run": rid, "name": name, "type": i["type"],
                       "rate": i["rate"], "accrued": bt.run_spend(rid, inst), "util": util,
                       "open_exec": open_exec})
            i["probes"].append((time.time(), util))
        if open_exec:
            continue
        quiet = now - idle_since(i, c["idle_util_pct"])
        if (util is None or util < c["idle_util_pct"]) and quiet >= c["idle_minutes"] * 60:
            kill(name, rid, f"idle {quiet/60:.0f} min (util {util})")

    # ledger says live but brev no longer lists it: close the ledger record so cost stops accruing
    names = {w.get("name") for w in listed}
    for n, i in inst.items():
        if i["live"] and n not in names and now - i["t_start"] > 120:
            acts.append(f"vanished: {n}")
            if not dry:
                bt.append({"action": "reap", "run": i["run"], "name": n, "type": i["type"],
                           "rate": i["rate"], "accrued": bt.run_spend(i["run"], inst),
                           "why": "no longer listed by brev", "rc": 0})
    return acts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    if a.once or a.dry_run:
        print("\n".join(one_pass(dry=a.dry_run)) or "nothing to do")
        return
    bt.append({"action": "reaper_start", "pid": os.getpid()})
    while True:
        t0 = time.time()
        try:
            acts = one_pass()
            for x in acts:
                print(time.strftime("%H:%M:%S"), x, flush=True)
        except Exception as e:
            try:
                bt.append({"action": "reaper_error", "why": repr(e)[:300]})
            except Exception:
                pass
            traceback.print_exc()
        with open(HEARTBEAT, "w", encoding="utf-8") as f:
            json.dump({"t": bt.now_iso(), "pid": os.getpid(), "pass_s": round(time.time() - t0, 1)}, f)
        interval = bt.caps()["reaper_interval_s"]
        time.sleep(max(5, interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
