"""One identical mid-run notice to every agent of every arm (human intervention; requested by the user, relayed by
the coordinator). Uses the channel the meter hook already reads on every tool call: <root>/public/notices.json.

    python broadcast_notice.py --send [--notice N] [--root R]   publish notice N once (refuses a second send)
    python broadcast_notice.py --status [--root R]   append delivered / pending / missed per agent to the log

Nothing is restarted and no brief, quota or cap changes. The hook runs fresh on each tool call, so a live session gets
the notice at its next tool call (held once, like the cap-30 and cap-10 notices), and a session that has not started
gets it at its first tool call. Sessions in a final state make no more tool calls, so they never receive it.
The hook appends its usual line saying the call was held; the notice text itself is byte-identical for everyone.
Log: metrics/interventions.jsonl (time, text sha256, agent ids and states only). Also HUMAN_POSTS.log and touch.log.
States: delivered = the id is in the agent's seen_notices.json; pending_live / pending_not_started; missed = final
state without having seen it, or not started by the last start time.
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import FINAL_STATES, append_jsonl, load_json, local_now, run_dir, utc_now, write_json  # noqa: E402

TEXT_1 = ("Notice to all agents, identical for everyone: be as creative as you can with the tools and skills available "
          "to you, especially the sponsors': the PreForm API and NVIDIA software (Warp, PhysicsNeMo, BioNeMo, ALCHEMI, "
          "NGC containers on Brev; see compute_images.md). How you use them is up to you.")
TEXT_2 = ("Notice to all agents, identical for everyone: be as creative as you can with the tools and skills available "
          "to you, especially the sponsors': the PreForm API and NVIDIA software (Warp, PhysicsNeMo, BioNeMo, ALCHEMI, "
          "NGC containers on Brev; see compute_images.md). Also consider how impressive your creative uses would be in "
          "a demo, and whether they can be made even more impressive while making sure each creative use fits the "
          "needs of the problem. How you use them is up to you.")
NOTICES = {1: ("broadcast_sponsor_tools", TEXT_1), 2: ("broadcast_sponsor_tools_2", TEXT_2)}


def sha(n):
    return hashlib.sha256(NOTICES[n][1].encode("utf-8")).hexdigest()


def agent_rows(root, n=1):
    notice_id = NOTICES[n][0]
    sched = load_json(run_dir(root) / "schedule.json") or {}
    last = sched.get("last_start")
    too_late = bool(last) and local_now() >= dt.datetime.fromisoformat(last)
    rows = []
    for f in sorted(run_dir(root).glob("*/*/arm.json")):
        m = load_json(f) or {}
        for g in m.get("agents", []):
            d = f.parent / "agents" / g["id"]
            seen = load_json(d / "seen_notices.json", []) or []
            st = load_json(d / "status.json")
            state = (st or {}).get("state")
            if notice_id in seen:
                res = "delivered"
            elif state in FINAL_STATES:
                res = "missed"
            elif st is None:
                res = "missed" if too_late else "pending_not_started"
            else:
                res = "pending_live"
            rows.append({"run": f.parent.parent.name, "arm": f.parent.name, "agent": g["id"], "result": res,
                         "state": state})
    return rows


def summary(rows):
    out = {}
    for r in rows:
        out.setdefault(f"{r['run']}/{r['arm']}", Counter())[r["result"]] += 1
    return {k: dict(v) for k, v in out.items()}


def public_file(root):
    pub = (load_json(run_dir(root) / "schedule.json", {}) or {}).get("public_dir")
    return Path(pub) / "notices.json" if pub else Path(root) / "public" / "notices.json"


def log_status(root, event, notices=(1, 2)):
    md = Path(root) / "metrics"
    md.mkdir(parents=True, exist_ok=True)
    sent = {x.get("id") for x in (load_json(public_file(root), []) or [])}
    rec = None
    for n in notices:
        if NOTICES[n][0] not in sent:
            continue
        rows = agent_rows(root, n)
        rec = {"utc": utc_now(), "event": event, "kind": "human intervention (user request, relayed by the coordinator)",
               "notice": n, "notice_id": NOTICES[n][0], "text_sha256": sha(n),
               "totals": dict(Counter(r["result"] for r in rows)), "by_arm": summary(rows), "agents": rows}
        append_jsonl(md / "interventions.jsonl", rec)
        print(json.dumps({k: rec[k] for k in ("utc", "event", "notice", "text_sha256", "totals", "by_arm")}, indent=1))
    return rec


def send(root, n):
    path = public_file(root)
    notes = load_json(path, []) or []
    notice_id, text = NOTICES[n]
    if any(x.get("id") == notice_id for x in notes):
        sys.exit("refused: this notice was already sent")
    write_json(path, notes + [{"id": notice_id, "text": text, "utc": utc_now()}])
    line = f"{utc_now()} HUMAN INTERVENTION {notice_id} sha256 {sha(n)}: {text}"
    for name in ("HUMAN_POSTS.log", "touch.log"):
        with (run_dir(root) / name).open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    return log_status(root, "sent", (n,))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--notice", type=int, default=2, choices=[1, 2])
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if a.send:
        send(root, a.notice)
    else:
        log_status(root, "status")


if __name__ == "__main__":
    main()
