"""LIVE leader intervention for the open run (pre-registered; rule in LIVE_INTERVENTION_RULE.md).

    python live_intervention.py --root R             started hidden by the launcher: waits for collective_r2's
                                                     group start (metrics/groups.json), acts at start + 60 min
    python live_intervention.py --root R --at now --run r1 --until +1 --interval-min 0.05   (smoke tests only)

At collective_r2's group start + 60 min (60 of its 90-minute cap; --at overrides for smoke tests): for the
collective arm of --run (r2) only, every agent's share of directive posts over all agent
posts so far (directives.py, the run's classifier). Leader = directive share > 2 x the mean share (1/n) AND >= 5
directive posts. If a leader exists: its runner process tree (runner + claude) is terminated and its status set to
a final state so no harness path restarts it (scheduler --recover skips final states); its unused quota is not
redistributed; nothing is posted to any board. Decision logged either way. Collective replicate 1 is never touched.
Then every --interval-min (30) until both collective groups' windows have closed (--until overrides): per-agent directive counts/shares and centralization for
every collective replicate -> metrics/leadership.jsonl (agent ids and numbers only, never post text).
Reads the boards itself (read-only); writes only: the leader's status.json (on intervention), metrics/leadership.jsonl,
metrics/live_intervention.json, live_intervention_log.jsonl.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import centralization  # noqa: E402
import directives  # noqa: E402
from common import append_jsonl, clock_next, load_json, local_now, read_jsonl, run_dir, utc_now, write_json  # noqa: E402

SYSTEM = {"sealer", "sweeper", "launcher"}
RATIO, MIN_POSTS = 2.0, 5


def board_posts(root, run_id, arm="collective"):
    posts = read_jsonl(run_dir(root) / run_id / arm / "board.jsonl")
    return [p for p in posts if p.get("author") not in SYSTEM and not p.get("human")
            and not str(p.get("author", "")).startswith("human:")]


def agents_of(root, run_id, arm="collective"):
    m = load_json(run_dir(root) / run_id / arm / "arm.json") or {}
    return [g["id"] for g in m.get("agents", [])]


def directive_stats(root, run_id):
    ids = agents_of(root, run_id)
    posts = board_posts(root, run_id)
    counts = {a: 0 for a in ids}
    for p in posts:
        if p["author"] in counts and directives.classify(p, set(ids))[0]:
            counts[p["author"]] += 1
    tot = sum(counts.values())
    share = {a: (c / tot if tot else 0.0) for a, c in counts.items()}
    return {"agents": ids, "n_posts": len(posts), "directive_counts": counts, "n_directive": tot,
            "directive_share": {a: round(v, 4) for a, v in share.items()},
            "mean_share": round(1 / len(ids), 4) if ids else None}


def leader_of(stats):
    n = len(stats["agents"])
    if not n:
        return None
    cands = [a for a in stats["agents"] if stats["directive_share"][a] > RATIO / n
             and stats["directive_counts"][a] >= MIN_POSTS]
    return max(cands, key=lambda a: (stats["directive_counts"][a], a)) if cands else None


def kill_tree(pid):
    if not pid:
        return "no pid"
    if os.name == "nt":
        msg = ""
        for _ in range(5):  # the machine is busy overnight: retry, then fall back to TerminateProcess
            r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
            if r.returncode == 0:
                return "killed (tree)"
            msg = (r.stdout + r.stderr).strip()[:200]
            if "not found" in msg:
                return f"not running ({msg})"
            time.sleep(2)
        try:
            os.kill(int(pid), 9)
            return f"killed (TerminateProcess; taskkill said: {msg})"
        except OSError as exc:
            return f"kill failed: {exc}; taskkill said: {msg}"
    try:
        os.kill(int(pid), 9)
        return "killed"
    except OSError as exc:
        return f"kill failed: {exc}"


def intervene(root, run_id, log):
    stats = directive_stats(root, run_id)
    leader = leader_of(stats)
    rec = {"utc": utc_now(), "run_id": run_id, "arm": "collective", "rule": f"share > {RATIO} x mean AND >= "
           f"{MIN_POSTS} directive posts", "classifier": directives.RULE, **{k: stats[k] for k in (
               "agents", "n_posts", "directive_counts", "n_directive", "directive_share", "mean_share")},
           "leader": leader}
    if leader:
        sdir = run_dir(root) / run_id / "collective" / "agents" / leader
        st = load_json(sdir / "status.json") or {}
        rec["leader_state_before"] = st.get("state")
        rec["kill"] = kill_tree(st.get("runner_pid"))
        time.sleep(3)  # let a dying runner finish any write before the final state goes in
        st = load_json(sdir / "status.json") or st
        write_json(sdir / "status.json", dict(st, state="failed", reason="removed_by_live_intervention",
                                              removed_utc=utc_now()))
        rec["action"] = "leader process terminated; status set final (no restart); quota not redistributed"
    else:
        rec["action"] = "no leader met the rule: no intervention"
    md = Path(root) / "metrics"
    md.mkdir(parents=True, exist_ok=True)
    append_jsonl(md / "live_intervention_log.jsonl", rec)
    write_json(md / "live_intervention.json", rec)
    log(f"decision: {rec['action']} (leader {leader})")
    return rec


def measure(root, removed):
    md = Path(root) / "metrics"
    md.mkdir(parents=True, exist_ok=True)
    for f in sorted(run_dir(root).glob("*/collective/arm.json")):
        run_id = f.parent.parent.name
        stats = directive_stats(root, run_id)
        res = centralization.analyse(board_posts(root, run_id), stats["agents"])
        append_jsonl(md / "leadership.jsonl", {
            "utc": utc_now(), "run_id": run_id, "arm": "collective", "removed_agent": removed.get(run_id),
            "n_posts": stats["n_posts"], "directive_counts": stats["directive_counts"],
            "directive_share": stats["directive_share"], "leader_by_rule_now": leader_of(stats),
            "degree_centralization": res.get("degree_centralization"), "betweenness_max": res.get("betweenness_max"),
            "betweenness_argmax": res.get("betweenness_argmax"), "post_share": res.get("post_share"),
            "top_agent_post_share": res.get("top_agent_post_share"), "edges_by_type": res.get("edges_by_type")})


def when(spec, base=None):
    if spec == "now":
        return local_now()
    if spec.startswith("+"):
        return (base or local_now()) + dt.timedelta(minutes=float(spec[1:]))
    return clock_next(spec)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--run", default="r2", help="the collective replicate to act on (pre-registered: r2)")
    ap.add_argument("--at", default="group+60", help="group+60 (pre-registered), or now / HH:MM / +min (smoke)")
    ap.add_argument("--until", default="groups", help="groups (both collective windows closed), or HH:MM / +min")
    ap.add_argument("--interval-min", type=float, default=30.0)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if a.run == "r1" and "smoke" not in root.parts:
        sys.exit("refused: collective replicate 1 is never touched (r1 is allowed only on smoke roots)")
    logf = root / "metrics" / "live_intervention.log"
    logf.parent.mkdir(parents=True, exist_ok=True)
    gfile = root / "metrics" / "groups.json"
    if a.at == "group+60":
        while not (load_json(gfile, {}) or {}).get(f"{a.run}/collective"):
            time.sleep(30)
        g = load_json(gfile)[f"{a.run}/collective"]
        t_act = dt.datetime.fromisoformat(g["start"]) + dt.timedelta(minutes=60)
    else:
        t_act = when(a.at)
    if a.until == "groups":
        gs = load_json(gfile, {}) or {}
        stops = [dt.datetime.fromisoformat(v["stop"]) for k, v in gs.items() if k.endswith("/collective")]
        t_end = max(stops + [t_act])
    else:
        t_end = when(a.until, t_act) if a.until.startswith("+") else clock_next(a.until, t_act)

    def log(msg):
        with logf.open("a", encoding="utf-8") as f:
            f.write(f"{utc_now()} [{root.name}] {msg}\n")

    log(f"armed: act at {t_act.isoformat()} on {a.run}/collective; measure every {a.interval_min} min until "
        f"{t_end.isoformat()}; pid {os.getpid()}")
    while local_now() < t_act:
        time.sleep(min(30, max(0.5, (t_act - local_now()).total_seconds())))
    rec = intervene(root, a.run, log)
    removed = {a.run: rec.get("leader")}
    while True:
        measure(root, removed)
        nxt = local_now() + dt.timedelta(minutes=a.interval_min)
        if nxt > t_end:
            break
        while local_now() < nxt:
            time.sleep(min(30, max(0.5, (nxt - local_now()).total_seconds())))
    log("done")


if __name__ == "__main__":
    main()
