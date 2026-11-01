"""Robust liveness for runners: pid + process creation time + command line (used by scheduler --recover).

A runner counts as alive only if a process with the recorded pid exists, its command line contains
"agent_runner.py" and the agent's own folder, and it was created no later than the agent's last status write
(so a recycled pid cannot pass). An agent also counts as alive if a claude.exe process is a child of that runner.
"""
import datetime as dt
import json
import os
import subprocess
from pathlib import Path


def snapshot():
    """pid -> {ppid, name, cmd, created (aware datetime)} for every process (one CIM query)."""
    if os.name != "nt":
        return {}
    ps = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine,"
          "@{n='Created';e={if ($_.CreationDate) { $_.CreationDate.ToString('yyyy-MM-ddTHH:mm:ss.ffffffzzz') } else { '' }}} | ConvertTo-Json -Compress")
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + ps],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=120)
    rows = json.loads(r.stdout, strict=False) if r.stdout.strip() else []
    if isinstance(rows, dict):
        rows = [rows]
    out = {}
    for x in rows:
        try:
            created = dt.datetime.fromisoformat(x["Created"]) if x.get("Created") else None
        except ValueError:
            created = None
        if created is not None and created.tzinfo is None:
            created = created.astimezone()
        out[int(x["ProcessId"])] = {"ppid": int(x.get("ParentProcessId") or 0), "name": (x.get("Name") or "").lower(),
                                    "cmd": x.get("CommandLine") or "", "created": created}
    return out


def _norm(s):
    return s.replace("\\", "/").lower()


def runner_alive(snap, pid, agent_dir, status_ts=None):
    """(alive, why). Alive = pid present, command line is this agent's runner, created before its last status."""
    if not pid or int(pid) not in snap:
        return False, "no such pid"
    p = snap[int(pid)]
    if "agent_runner.py" not in p["cmd"] or _norm(str(agent_dir)) not in _norm(p["cmd"]):
        return False, "pid belongs to another process"
    if status_ts and p["created"]:
        try:
            st = dt.datetime.fromisoformat(status_ts)
            if p["created"] > st + dt.timedelta(seconds=5):
                return False, "pid recycled (process newer than the agent's last status)"
        except ValueError:
            pass
    return True, "runner alive"


def runners_for(snap, agent_dir):
    """Every live agent_runner.py process whose command line names this agent folder."""
    a = _norm(str(agent_dir))
    return [pid for pid, p in snap.items() if "agent_runner.py" in p["cmd"] and a in _norm(p["cmd"])]


def claude_children(snap, runner_pid):
    return [pid for pid, p in snap.items() if p["ppid"] == int(runner_pid) and p["name"].startswith("claude")]


def agent_alive(snap, agent_dir, status):
    """(alive, why, pids). Uses the recorded runner pid first, then any runner naming the folder, then claude."""
    ok, why = runner_alive(snap, status.get("runner_pid"), agent_dir, status.get("ts"))
    if ok:
        return True, why, [int(status["runner_pid"])]
    others = runners_for(snap, agent_dir)
    if others:
        return True, "a runner for this folder is alive (pid differs from status)", others
    if status.get("runner_pid") and claude_children(snap, status["runner_pid"]):
        return True, "claude child of the recorded runner is alive", claude_children(snap, status["runner_pid"])
    return False, why, []


def crashed_mid_turn(agent_dir):
    """True if the agent's ORIGINAL runner (the runner pid of its first logged model start) started a model process
    and never logged its end. Events written by other runner pids (e.g. the 03:50 duplicates) are ignored."""
    f = Path(agent_dir) / "sessions.jsonl"
    if not f.exists():
        return False
    events = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    starts = [e for e in events if e.get("event") == "start" and e.get("runner_pid")]
    if not starts:
        return False
    orig = starts[0]["runner_pid"]
    last = None
    for e in events:
        if e.get("event") in ("start", "end") and e.get("runner_pid", orig) == orig:
            last = e["event"]
    return last == "start"
