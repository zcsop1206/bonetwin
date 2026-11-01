"""Test broadcast_notice.py on a small fixture built under smoke/ (no copy of a real run, no agents, no API).

    python test_broadcast.py

Fixture: one single agent running, one collective agent running, one capped, one not started. Each hook call is the
real meter.py as a new process with the agent's environment, as Claude Code runs it.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import broadcast_notice as B  # noqa: E402
from common import load_json, read_jsonl, write_json  # noqa: E402

OK = []


def check(name, ok, detail=""):
    OK.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({str(detail)[:160]})" if detail != "" else ""))


def hook(d):
    env = {k: v for k, v in os.environ.items() if not k.startswith("BT_")}
    env.update(BT_AGENT_DIR=str(d))
    return subprocess.run([sys.executable, str(HERE / "meter.py"), "hook"], capture_output=True, text=True, env=env,
                          input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": str(d / "x.md")}}),
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def main():
    root = HERE / "smoke" / "bc1"
    if root.exists():
        shutil.rmtree(root)
    (root / "public").mkdir(parents=True)
    write_json(root / "public" / "notices.json", [])
    rd = root / "run"
    rd.mkdir()
    write_json(rd / "schedule.json", {"public_dir": str(root / "public")})
    dirs = {}
    for arm, ids in (("single", ["s1"]), ("collective", ["c1", "c2", "c3"])):
        ad = rd / "r1" / arm
        agents = []
        for aid in ids:
            d = ad / "agents" / aid
            d.mkdir(parents=True)
            g = {"id": aid, "quota": 1000, "tool_prices": {}, "credit_weights": {}, "blocked": [],
                 "public_dir": str(root / "public"), "board_shared": False}
            write_json(d / "genome.json", g)
            agents.append(g)
            dirs[aid] = d
        write_json(ad / "arm.json", {"arm": arm, "run_id": "r1", "agents": agents})
    write_json(dirs["s1"] / "status.json", {"state": "running"})
    write_json(dirs["c1"] / "status.json", {"state": "running"})
    write_json(dirs["c2"] / "status.json", {"state": "capped"})  # c3 has no status: not started

    rec = B.send(root, 1)
    check("after send: 2 live pending, 1 not started pending, 1 missed", rec["totals"] == {
        "pending_live": 2, "missed": 1, "pending_not_started": 1}, rec["totals"])
    want = B.TEXT_1 + "\n(This tool call was held"
    r1, r2 = hook(dirs["s1"]), hook(dirs["s1"])
    check("single (no board): next tool call held, exact text first", r1.returncode == 2 and r1.stderr.startswith(want),
          r1.stderr[:60])
    check("held only once, the repeated call runs", r2.returncode == 0, r2.stderr[:80])
    r3 = hook(dirs["c1"])
    check("byte-identical for another arm", r3.returncode == 2 and r3.stderr == r1.stderr)
    r4 = hook(dirs["c3"])
    check("a not-started session gets it at its first tool call", r4.returncode == 2 and r4.stderr == r1.stderr)
    check("the capped agent's folder is untouched (not revived)", not (dirs["c2"] / "seen_notices.json").exists()
          and load_json(dirs["c2"] / "status.json")["state"] == "capped")
    rec2 = B.log_status(root, "status", (1,))
    check("status: 3 delivered, 1 missed", rec2["totals"] == {"delivered": 3, "missed": 1}, rec2["by_arm"])
    r5 = subprocess.run([sys.executable, str(HERE / "broadcast_notice.py"), "--send", "--notice", "1", "--root", str(root)],
                        capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    check("second send refused", r5.returncode != 0 and "refused" in r5.stderr)
    log = read_jsonl(root / "metrics" / "interventions.jsonl")
    blob = json.dumps(log)
    check("log holds the sha256 and ids, not the text", B.sha(1) in blob and "creative" not in blob, len(log))
    check("HUMAN_POSTS.log and touch.log record it", "HUMAN INTERVENTION" in (rd / "HUMAN_POSTS.log").read_text(
        encoding="utf-8") and "HUMAN INTERVENTION" in (rd / "touch.log").read_text(encoding="utf-8"))
    # second notice: a session that saw the first gets only the second; a new session gets both, together, once
    d4 = rd / "r1" / "collective" / "agents" / "c4"
    d4.mkdir()
    g4 = dict(load_json(dirs["c1"] / "genome.json"), id="c4")
    write_json(d4 / "genome.json", g4)
    arm = load_json(rd / "r1" / "collective" / "arm.json")
    arm["agents"].append(g4)
    write_json(rd / "r1" / "collective" / "arm.json", arm)
    B.send(root, 2)
    want2 = B.TEXT_2 + "\n(This tool call was held"
    r6, r7 = hook(dirs["s1"]), hook(dirs["c1"])
    check("second notice: held once more, only the new text, byte-identical", r6.returncode == 2 and
          r6.stderr.startswith(want2) and B.TEXT_1 not in r6.stderr and r7.stderr == r6.stderr, r6.stderr[:40])
    r8, r9 = hook(d4), hook(d4)
    check("a session not started when both were sent gets both once, then runs", r8.returncode == 2 and
          r8.stderr.startswith(B.TEXT_1 + "\n" + B.TEXT_2) and r9.returncode == 0)
    check("capped agent still untouched", not (dirs["c2"] / "seen_notices.json").exists())
    print(f"{sum(OK)}/{len(OK)} passed")
    return 0 if all(OK) else 1


if __name__ == "__main__":
    sys.exit(main())
