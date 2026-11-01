"""bt_compute: the only door agents have to Brev GPUs tonight.

Windows-side CLI. Drives the brev CLI inside WSL, enforces per-run dollar
caps from caps.json, and appends every action to compute_ledger.jsonl.

  python bt_compute.py quote
  python bt_compute.py start --arm single --run 1 --type A6000 --name sim [--hours 1.0]
  python bt_compute.py exec  --arm single --run 1 --name sim [--timeout 1800] -- nvidia-smi
  python bt_compute.py copy-to   --arm single --run 1 --name sim LOCAL REMOTE
  python bt_compute.py copy-from --arm single --run 1 --name sim REMOTE LOCAL
  python bt_compute.py stop  --arm single --run 1 --name sim
  python bt_compute.py ls    [--arm single] [--run 1]

Instance names are always bt-<run_id>-<name>, run_id = <arm>-r<run>
(best_of_n is spelled bestofn). If the environment variable BT_RUN is set
(the harness sets it per agent), every command is locked to that run id.

Brev's A6000/A100/L40S rentals here are not stoppable, so `stop` deletes
the instance. Copy results off first. Cost = rate x wall time from the
ledger's start record to its stop record.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CAPS_PATH = os.path.join(HERE, "caps.json")
LEDGER = os.path.join(HERE, "compute_ledger.jsonl")
LOCK = LEDGER + ".lock"
QUOTE_CACHE = os.path.join(HERE, ".quote_cache.json")
PREFIX = "bt-"
ARMS = {"single": "single", "best_of_n": "bestofn", "bestofn": "bestofn",
        "collective": "collective", "planner": "planner", "control": "control"}


def caps() -> dict:
    with open(CAPS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- brev

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SSH_DOWN = ("not available after", "banner exchange", "Connection refused", "Connection timed out",
            "No route to host", "kex_exchange_identification")


_KEY_CACHE: list = []


def ngc_key() -> str | None:
    """The NGC API key, read only into memory; never printed, logged or written locally.
    Path from env BT_NGC_KEY_FILE, else caps.json "ngc_key_file"."""
    if not _KEY_CACHE:
        k = None
        path = os.environ.get("BT_NGC_KEY_FILE") or caps().get("ngc_key_file") or ""
        try:
            with open(path, encoding="utf-8") as f:
                k = f.read().strip() or None
        except OSError:
            pass
        _KEY_CACHE.append(k)
    return _KEY_CACHE[0]


def redact(text: str) -> str:
    k = ngc_key()
    if text and k:
        text = text.replace(k, "[REDACTED]")
    return re.sub(r"nvapi-[A-Za-z0-9_\-]{20,}", "[REDACTED]", text or "")


def _wsl_home() -> str:
    return caps()["brev"].split("/.local/")[0]


_SSH_INFO: dict = {}


def ssh_info(name: str, refresh: bool = True) -> dict | None:
    """{ip, port, user} for an instance, from the -host block of Brev's ssh config."""
    if name in _SSH_INFO:
        return _SSH_INFO[name]
    c = caps()
    for attempt in range(2 if refresh else 1):
        r = subprocess.run(["wsl", "-d", c["wsl_distro"], "--exec", "cat", _wsl_home() + "/.brev/ssh_config"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=60, input="", creationflags=NO_WINDOW)
        info, cur = {}, None
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            k = parts[0].lower()
            if k == "host":
                cur = parts[1]
            elif cur == name + "-host" and k in ("hostname", "port", "user"):
                info[k] = parts[1]
        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", info.get("hostname", "")):
            _SSH_INFO[name] = {"ip": info["hostname"], "port": info.get("port", "22"),
                               "user": info.get("user", "ubuntu")}
            return _SSH_INFO[name]
        if attempt == 0 and refresh:
            _brev(["refresh"], timeout=120)
    return None


def ssh_direct(info: dict, port: str, command: str, timeout: int, stdin: bytes = b"") -> subprocess.CompletedProcess:
    c = caps()
    cmd = ["wsl", "-d", c["wsl_distro"], "--exec", "ssh", "-T", "-F", "/dev/null",
           "-i", _wsl_home() + "/.brev/brev.pem", "-p", str(port),
           "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
           "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30",
           "-o", "ServerAliveCountMax=6", f"{info['user']}@{info['ip']}", command]
    try:
        r = subprocess.run(cmd, capture_output=True, input=stdin, timeout=timeout, creationflags=NO_WINDOW)
        return subprocess.CompletedProcess(cmd, r.returncode, redact(r.stdout.decode("utf-8", "replace")),
                                           redact(r.stderr.decode("utf-8", "replace")))
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, redact((e.stdout or b"").decode("utf-8", "replace")),
                                           f"timeout after {timeout}s")


def remote(name: str, command: str, timeout: int = 300, stdin: bytes = b"") -> subprocess.CompletedProcess:
    """Run a command on an instance. Direct SSH first: Brev's forwarded port (and the tunnel in
    front of it) was seen dying minutes after boot while sshd on port 22 stayed healthy.
    Falls back to `brev exec` only when no connection was made, so a command never runs twice."""
    info = ssh_info(name)
    if info:
        for port in dict.fromkeys(["22", info["port"]]):
            r = ssh_direct(info, port, command, timeout, stdin)
            connect_failed = r.returncode == 255 and (r.stderr.startswith("ssh:")
                                                      or any(k in r.stderr for k in SSH_DOWN))
            if not connect_failed:
                return r
    if stdin:
        return subprocess.CompletedProcess([], 255, "", "ssh: no route for a command with stdin")
    return brev(["exec", name, command], timeout=timeout)


def brev(args: list[str], timeout: int = 300, inp: str | None = None) -> subprocess.CompletedProcess:
    r = _brev(args, timeout, inp)
    r.stdout, r.stderr = redact(r.stdout), redact(r.stderr)
    return r


def _brev(args: list[str], timeout: int = 300, inp: str | None = None) -> subprocess.CompletedProcess:
    c = caps()
    cmd = ["wsl", "-d", c["wsl_distro"], "--exec", c["brev"], "--no-check-latest"] + args
    try:
        # stdin is always fed (empty by default): brev reads instance names from a piped
        # stdin and prompts on some commands, so an open stdin hangs it. No console window.
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, input=inp if inp is not None else "",
                              creationflags=NO_WINDOW)
    except subprocess.TimeoutExpired as e:
        out = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        return subprocess.CompletedProcess(cmd, 124, out, f"timeout after {timeout}s")


def win_to_wsl(p: str) -> str:
    p = os.path.abspath(p)
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", p)
    if not m:
        return p
    return f"/mnt/{m.group(1).lower()}/" + m.group(2).replace("\\", "/")


def brev_ls() -> list[dict]:
    r = brev(["ls", "--json"], timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"brev ls failed: {r.stderr.strip()[:300]}")
    try:
        return json.loads(r.stdout).get("workspaces") or []
    except json.JSONDecodeError:
        if "No instances" in r.stdout:
            return []
        raise RuntimeError(f"brev ls: unparseable output: {r.stdout[:300]}")


def live_prices(max_age_s: int = 600) -> dict[str, float]:
    """brev type -> $/h, from `brev search gpu --json`, cached 10 min."""
    try:
        with open(QUOTE_CACHE, encoding="utf-8") as f:
            cached = json.load(f)
        if time.time() - cached["t"] < max_age_s:
            return cached["prices"]
    except Exception:
        pass
    r = brev(["search", "gpu", "--json"], timeout=120)
    prices = {}
    try:
        for row in json.loads(r.stdout):
            prices[row["type"]] = float(row["price_per_hour"])
    except Exception:
        return dict(caps()["fallback_rates"])
    with open(QUOTE_CACHE, "w", encoding="utf-8") as f:
        json.dump({"t": time.time(), "prices": prices}, f)
    return prices


def rate_of(brev_type: str, prices: dict | None = None) -> float:
    prices = prices or {}
    if brev_type in prices:
        return prices[brev_type]
    return float(caps()["fallback_rates"].get(brev_type, 0.0)) or 99.0


# ---------------------------------------------------------------- ledger

class _Lock:
    def __enter__(self):
        self.f = open(LOCK, "a+")
        if os.name == "nt":
            import msvcrt
            for _ in range(200):
                try:
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                    return self
                except OSError:
                    time.sleep(0.05)
        return self

    def __exit__(self, *a):
        if os.name == "nt":
            import msvcrt
            try:
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        self.f.close()


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def ts(rec: dict) -> float:
    if "epoch" in rec:
        return float(rec["epoch"])
    return dt.datetime.fromisoformat(rec["t"]).timestamp()


def read_ledger() -> list[dict]:
    out = []
    if not os.path.exists(LEDGER):
        return out
    with open(LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def append(rec: dict) -> dict:
    rec = {"t": now_iso(), "epoch": round(time.time(), 1), **rec}
    with _Lock():
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def state(ledger: list[dict] | None = None, at: float | None = None) -> dict:
    """name -> instance record rebuilt from the ledger (restart-safe)."""
    ledger = read_ledger() if ledger is None else ledger
    at = time.time() if at is None else at
    inst: dict[str, dict] = {}
    for r in ledger:
        n = r.get("name")
        a = r.get("action")
        if not n:
            continue
        if a == "start" and r.get("rc", 0) == 0:
            inst[n] = {"name": n, "run": r["run"], "type": r.get("type"),
                       "brev_type": r.get("brev_type"), "rate": float(r["rate"]),
                       "t_start": ts(r), "t_end": None, "last_exec": ts(r),
                       "open_execs": {}, "probes": []}
        elif n in inst:
            i = inst[n]
            if a in ("stop", "reap") and r.get("rc", 0) == 0:
                i["t_end"] = ts(r)
            elif a == "exec_start":
                i["last_exec"] = ts(r)
                i["open_execs"][r.get("exec_id")] = ts(r) + float(r.get("timeout", 3600))
            elif a == "exec_end":
                i["last_exec"] = ts(r)
                i["open_execs"].pop(r.get("exec_id"), None)
            elif a in ("copy_to", "copy_from"):
                i["last_exec"] = ts(r)
            elif a == "probe":
                i["probes"].append((ts(r), r.get("util")))
    for i in inst.values():
        end = i["t_end"] if i["t_end"] else at
        i["accrued"] = round(i["rate"] * max(0.0, end - i["t_start"]) / 3600.0, 4)
        i["live"] = i["t_end"] is None
    return inst


def run_spend(run_id: str, inst: dict | None = None) -> float:
    inst = state() if inst is None else inst
    return round(sum(i["accrued"] for i in inst.values() if i["run"] == run_id), 4)


def total_spend(inst: dict | None = None) -> float:
    inst = state() if inst is None else inst
    return round(sum(i["accrued"] for i in inst.values()), 4)


# ---------------------------------------------------------------- naming

def run_id_of(arm: str | None, run: str | None) -> str:
    env = os.environ.get("BT_RUN")
    rid = None
    if arm is not None and arm.lower() == "judge":
        if run is None:
            sys.exit("--run is required with --arm judge (a word, e.g. final)")
        rid = f"judge-{str(run).lower()}"
    elif arm is not None:
        a = ARMS.get(arm.lower().replace("-", "_"))
        if a is None:
            sys.exit(f"unknown arm {arm!r}; one of single, best_of_n, collective, planner, control")
        if run is None:
            sys.exit("--run is required with --arm (1 or 2)")
        r = str(run).lower().lstrip("r")
        rid = f"{a}-r{r}"
    if env:
        env = env.lower()
        if env.startswith("judge_"):
            env = "judge-" + env[6:]
        if rid and rid != env:
            sys.exit(f"refused: this agent is locked to run {env}, not {rid}")
        rid = env
    if rid is None:
        sys.exit("give --arm and --run")
    if rid not in caps()["runs"] and pool_of(rid) is None:
        sys.exit(f"refused: run {rid} has no entry in caps.json (judge runs: judge_<word>, letters/digits)")
    return rid


def pool_of(rid: str) -> str | None:
    """Pool name if rid is a pooled run (judge-<word>), else None."""
    for p in caps().get("pools", {}):
        if re.fullmatch(rf"{p}-[a-z0-9]{{1,20}}", rid):
            return p
    return None


def cap_status(rid: str, inst: dict | None = None) -> tuple[float, float, int]:
    """(spend counted against this run's cap, the cap, max concurrent) - pooled runs share one cap."""
    c = caps()
    inst = state() if inst is None else inst
    p = pool_of(rid)
    if p:
        spent = sum(i["accrued"] for i in inst.values() if pool_of(i["run"]) == p)
        pc = c["pools"][p]
        return round(spent, 4), float(pc["cap"]), int(pc.get("max_concurrent_per_run", 1))
    return run_spend(rid, inst), float(c["runs"].get(rid, 0.0)), int(c["max_concurrent_per_run"])


def full_name(run_id: str, name: str) -> str:
    name = name.strip().lower()
    want = f"{PREFIX}{run_id}-"
    if name.startswith(PREFIX):
        if not name.startswith(want):
            sys.exit(f"refused: {name} does not belong to run {run_id}")
        return name
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,30}", name):
        sys.exit("name: lowercase letters, digits and hyphens, 1-31 chars")
    return want + name


def ours(name: str) -> str | None:
    """run id if the instance name carries one of our run prefixes, else None."""
    for rid in sorted(caps()["runs"], key=len, reverse=True):
        if name.startswith(f"{PREFIX}{rid}-"):
            return rid
    for p in caps().get("pools", {}):
        m = re.match(rf"^{PREFIX}({p}-[a-z0-9]{{1,20}})-", name)
        if m:
            return m.group(1)
    return None


def hard_stop_epoch() -> float:
    # naive local wall time -> epoch with that date's own UTC offset
    # (tonight crosses the DST fall-back at 02:00, so wall-clock subtraction is off by 1 h)
    return dt.datetime.fromisoformat(caps()["hard_stop_local"]).astimezone().timestamp()


def hours_left_tonight() -> float:
    return max(0.0, (hard_stop_epoch() - time.time()) / 3600.0)


# ---------------------------------------------------------------- commands

def cmd_quote(a):
    c = caps()
    prices = live_prices()
    print("allowed types ($/h, live from brev search; first = tried first):")
    for cls, types in c["allowed_types"].items():
        row = ", ".join(f"{t} {rate_of(t, prices):.3f}" for t in types)
        print(f"  {cls:6s} {row}")
    inst = state()
    print(f"\nrun caps (spent / cap, $); total credit {c['total_credit']}, reserve {c['reserve']}, "
          f"spent {total_spend(inst):.2f}")
    for rid, cap in c["runs"].items():
        print(f"  {rid:14s} {run_spend(rid, inst):7.3f} / {cap:.2f}")
    for p, pc in c.get("pools", {}).items():
        spent = sum(i["accrued"] for i in inst.values() if pool_of(i["run"]) == p)
        print(f"  {p + '_*':14s} {spent:7.3f} / {float(pc['cap']):.2f}  (shared pool)")
    print(f"\nmax concurrent per run: {c['max_concurrent_per_run']}; hard stop {c['hard_stop_local']} "
          f"({hours_left_tonight():.2f} h left); stop = delete (instances are not stoppable)")


def cmd_start(a):
    c = caps()
    rid = run_id_of(a.arm, a.run)
    spent, cap, maxc = cap_status(rid)
    cls = a.type.upper().replace("L40S", "L40S")
    if cls not in c["allowed_types"]:
        sys.exit(f"refused: type {a.type} not allowed; allowed {list(c['allowed_types'])}")
    name = full_name(rid, a.name)
    inst = state()
    live = [i for i in inst.values() if i["run"] == rid and i["live"]]
    if name in inst and inst[name]["live"]:
        sys.exit(f"refused: {name} is already running")
    if len(live) >= maxc:
        sys.exit(f"refused: run {rid} already has {len(live)} live instance(s): "
                 f"{[i['name'] for i in live]} (max {maxc})")
    prices = live_prices()
    chain = c["allowed_types"][cls]
    worst = max(rate_of(t, prices) for t in chain)
    if hours_left_tonight() < 0.1:
        sys.exit(f"refused: past or within 6 min of the {c['hard_stop_local']} hard stop")
    if float(a.hours) <= 0:
        sys.exit("--hours must be positive")
    hours = min(float(a.hours), hours_left_tonight())
    projected = spent + worst * hours
    if cap <= 0 or projected > cap + 1e-9:
        append({"action": "start_refused", "run": rid, "name": name, "type": cls,
                "rate": worst, "accrued": spent, "cap": cap, "hours": hours,
                "why": "cap" if cap > 0 else "run has no compute"})
        sys.exit(f"refused: run {rid} spent ${spent:.2f}; {hours:.2f} h of {cls} at up to "
                 f"${worst:.3f}/h would reach ${projected:.2f} > cap ${cap:.2f}. "
                 f"Use --hours smaller or a cheaper type.")
    arms_total = sum(i["accrued"] for i in inst.values() if pool_of(i["run"]) is None)
    if pool_of(rid) is None and arms_total + worst * hours > c["total_credit"] - c["reserve"]:
        sys.exit("refused: would eat into the global reserve")
    r = brev(["create", name, "--type", ",".join(chain), "--detached"], timeout=600)
    out = r.stdout + r.stderr
    m = re.search(r"\]\s+(\S+)\s+Success!", out)
    got = m.group(1) if m else None
    ok = r.returncode == 0 and got is not None
    rate = rate_of(got, prices) if got else worst
    rec = append({"action": "start", "run": rid, "name": name, "type": cls, "brev_type": got,
                  "rate": rate, "accrued": spent, "cap": cap, "hours_planned": hours,
                  "rc": 0 if ok else (r.returncode or 1), "out": out.strip()[-400:]})
    if not ok:
        # a half-made instance would be billed; the reaper deletes orphans
        sys.exit(f"start failed: {out.strip()[-600:]}")
    print(f"started {name} ({got}, ${rate:.3f}/h). Run {rid} spent ${spent:.2f} of ${cap:.2f}. "
          f"The reaper deletes it after 15 idle min, at the cap, at {c['hard_stop_local']}, "
          f"or if not ready {c['boot_grace_minutes']} min after start.", flush=True)
    if a.wait:
        if not wait_ready(name, rid, float(c["boot_grace_minutes"]) - 1):
            sys.exit(f"{name} did not give a shell in time; run `stop` and retry another type")
    else:
        print("Not waiting: run `wait --name ...` before `exec`.")


def wait_ready(name: str, rid: str, max_min: float) -> bool:
    """Poll until `brev exec name true` works. Logs a `ready` record with boot seconds."""
    inst = state()
    i = inst[name]
    deadline = time.time() + max_min * 60
    last = ""
    while time.time() < deadline:
        try:
            w = next((x for x in brev_ls() if x.get("name") == name), None)
        except Exception as e:
            w, last = {}, str(e)
        if w is None:
            print(f"{name} is no longer listed by brev")
            return False
        st = f"{w.get('status')}/{w.get('build_status')}/{w.get('shell_status')}/{w.get('health_status')}"
        if st != last:
            print(f"{time.strftime('%H:%M:%S')} {st}", flush=True)
            last = st
        if w.get("status") in ("FAILURE", "ERROR", "DELETING"):
            return False
        if w.get("status") == "RUNNING" or w.get("shell_status") == "READY" or w.get("health_status") == "HEALTHY":
            r = remote(name, "true", timeout=120)
            if r.returncode == 0:
                boot = round(time.time() - i["t_start"])
                append({"action": "ready", "run": rid, "name": name, "type": i["type"],
                        "brev_type": i["brev_type"], "rate": i["rate"], "accrued": run_spend(rid),
                        "boot_s": boot})
                print(f"{name} ready: shell works {boot // 60} min {boot % 60} s after start")
                setup_ngc(name, rid)
                return True
        time.sleep(20)
    return False


NGC_REMOTE = (
    "umask 077; mkdir -p ~/.ngc && cat > ~/.ngc/api_key && "
    "printf '%s\\n' 'export NGC_API_KEY=\"$(cat ~/.ngc/api_key)\"' > ~/.ngc/env && "
    "(grep -q ngc/env ~/.bashrc 2>/dev/null || "
    "{ echo '[ -f ~/.ngc/env ] && . ~/.ngc/env'; cat ~/.bashrc 2>/dev/null; } > ~/.bashrc.ngc && "
    "mv ~/.bashrc.ngc ~/.bashrc); "
    "if docker info >/dev/null 2>&1; then D=docker; else D='sudo -n docker'; fi; "
    "$D login nvcr.io -u '$oauthtoken' --password-stdin < ~/.ngc/api_key 2>&1 | tail -1"
)


def setup_ngc(name: str, rid: str) -> bool:
    """Put the NGC key on the instance (stdin over ssh, never argv) and docker-login to nvcr.io.
    Afterwards ~/.ngc/env exports NGC_API_KEY; `exec` sources it before every command."""
    k = ngc_key()
    if not k:
        print("NGC: no key configured (BT_NGC_KEY_FILE / caps.json ngc_key_file); skipped")
        return False
    rc, out, ok = 1, "", False
    for attempt in range(4):  # the remote script is idempotent; SSH to a busy box can time out
        r = remote(name, NGC_REMOTE, timeout=180, stdin=k.encode("utf-8"))
        rc, out = r.returncode, (r.stdout + r.stderr).strip()
        ok = rc == 0 and "Login Succeeded" in out
        if ok or not any(x in out for x in SSH_DOWN + ("timeout", "timed out")):
            break
        time.sleep(15)
    i = state().get(name, {})
    append({"action": "ngc_setup", "run": rid, "name": name, "type": i.get("type"),
            "rate": i.get("rate"), "accrued": run_spend(rid), "rc": 0 if ok else (rc or 1),
            "out": out[-200:]})
    print("NGC: " + ("docker logged in to nvcr.io; NGC_API_KEY set for exec" if ok
                     else "setup failed: " + out[-200:]))
    return ok


def cmd_ngc(a):
    rid = run_id_of(a.arm, a.run)
    name = full_name(rid, a.name)
    _require_live(rid, name)
    sys.exit(0 if setup_ngc(name, rid) else 1)


def cmd_wait(a):
    rid = run_id_of(a.arm, a.run)
    name = full_name(rid, a.name)
    _require_live(rid, name)
    if not wait_ready(name, rid, a.max_min):
        sys.exit(f"{name} not ready after {a.max_min} min. The reaper deletes it "
                 f"{caps()['boot_grace_minutes']} min after start; `stop` it now to save money.")


def _require_live(rid: str, name: str) -> dict:
    inst = state()
    i = inst.get(name)
    if not i or not i["live"]:
        sys.exit(f"refused: {name} is not a live instance of run {rid} in the ledger")
    return i


def cmd_exec(a):
    rid = run_id_of(a.arm, a.run)
    name = full_name(rid, a.name)
    i = _require_live(rid, name)
    command = " ".join(a.command).strip()
    if command.startswith("-- "):
        command = command[3:]
    if not command:
        sys.exit("give a command after --")
    if command.startswith("@"):
        # @C:\path\to\script.sh runs a local script on the instance
        local = command[1:].strip().strip('"')
        if not os.path.isfile(local):
            sys.exit(f"no such local script: {local}")
        with open(local, "rb") as f:
            script = f.read().replace(b"\r\n", b"\n")
        command = "[ -f ~/.ngc/env ] && . ~/.ngc/env; bash -s"
    else:
        script = b""
        command = "[ -f ~/.ngc/env ] && . ~/.ngc/env; " + command
    exec_id = f"{int(time.time()*1000)}-{os.getpid()}"
    append({"action": "exec_start", "run": rid, "name": name, "type": i["type"], "rate": i["rate"],
            "accrued": run_spend(rid), "exec_id": exec_id, "timeout": a.timeout,
            "cmd": command[:300]})
    t0 = time.time()
    for attempt in range(3):
        r = remote(name, command, timeout=a.timeout, stdin=script)
        if r.returncode == 0 or not any(k in (r.stdout + r.stderr) for k in SSH_DOWN):
            break
        time.sleep(20)  # SSH not up yet or a transient drop: retry, do not rerun on real failures
    append({"action": "exec_end", "run": rid, "name": name, "type": i["type"], "rate": i["rate"],
            "accrued": run_spend(rid), "exec_id": exec_id, "rc": r.returncode,
            "secs": round(time.time() - t0, 1)})
    sys.stdout.write(_clean(r.stdout))
    sys.stderr.write(_clean(r.stderr))
    sys.exit(r.returncode)


def _clean(s: str) -> str:
    """Drop brev's spinner frames and ANSI codes so agents see only the remote output."""
    s = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", s)
    keep = [l for l in s.splitlines() if "waiting for SSH connection" not in l]
    return "\n".join(keep) + ("\n" if keep else "")


def _copy(a, direction: str):
    rid = run_id_of(a.arm, a.run)
    name = full_name(rid, a.name)
    i = _require_live(rid, name)
    remote_path = a.dst if direction == "to" else a.src
    if re.match(r"^[A-Za-z]:[\\/]", remote_path):
        sys.exit(f"refused: remote path {remote_path!r} looks like a Windows path; "
                 "Git Bash rewrites /paths, so set MSYS_NO_PATHCONV=1")
    if direction == "to":
        src, dst = win_to_wsl(a.src), f"{name}:{a.dst}"
    else:
        src, dst = f"{name}:{a.src}", win_to_wsl(a.dst)
        os.makedirs(os.path.dirname(os.path.abspath(a.dst)) or ".", exist_ok=True)
    t0 = time.time()
    r = None
    info = ssh_info(name)
    if info:
        c = caps()
        here = lambda p: p.replace(f"{name}:", f"{info['user']}@{info['ip']}:", 1)
        r = subprocess.run(["wsl", "-d", c["wsl_distro"], "--exec", "scp", "-r", "-F", "/dev/null",
                            "-i", _wsl_home() + "/.brev/brev.pem", "-P", "22", "-o", "BatchMode=yes",
                            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
                            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10", here(src), here(dst)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=a.timeout, input="", creationflags=NO_WINDOW)
        r.stdout, r.stderr = redact(r.stdout), redact(r.stderr)
    if r is None or r.returncode != 0:
        r = brev(["copy", src, dst], timeout=a.timeout)
    append({"action": f"copy_{direction}", "run": rid, "name": name, "type": i["type"],
            "rate": i["rate"], "accrued": run_spend(rid), "rc": r.returncode,
            "src": a.src, "dst": a.dst, "secs": round(time.time() - t0, 1)})
    sys.stdout.write(_clean(r.stdout))
    sys.stderr.write(_clean(r.stderr))
    sys.exit(r.returncode)


def terminate(name: str, rid: str, action: str, why: str) -> dict:
    """Delete an instance and record it. Used by `stop` and by the reaper."""
    inst = state()
    i = inst.get(name, {})
    r = brev(["delete", name], timeout=300)
    out = (r.stdout + r.stderr).strip()
    gone = r.returncode == 0 or "not found" in out.lower() or "no workspace" in out.lower()
    return append({"action": action, "run": rid, "name": name, "type": i.get("type"),
                   "rate": i.get("rate"), "accrued": run_spend(rid), "inst_accrued": i.get("accrued"),
                   "why": why, "rc": 0 if gone else (r.returncode or 1), "out": out[-300:]})


def cmd_stop(a):
    rid = run_id_of(a.arm, a.run)
    name = full_name(rid, a.name)
    rec = terminate(name, rid, "stop", "requested")
    if rec["rc"] != 0:
        sys.exit(f"stop failed (the reaper will retry): {rec['out']}")
    print(f"deleted {name}; it accrued ${rec['inst_accrued'] or 0:.3f}; run {rid} total ${run_spend(rid):.3f}")


def cmd_ls(a):
    c = caps()
    env = os.environ.get("BT_RUN")
    rids = list(c["runs"])
    if a.arm or env:
        if a.arm and a.run is None and not env:
            arm = ARMS.get(a.arm.lower().replace("-", "_"))
            rids = [r for r in rids if r.startswith(f"{arm}-")]
        else:
            rids = [run_id_of(a.arm, a.run)]
    inst = state()
    try:
        live = {w["name"]: w for w in brev_ls()}
    except Exception as e:
        live = {}
        print(f"(brev ls failed: {e})")
    for rid in rids:
        sp, cp, _ = cap_status(rid, inst)
        print(f"{rid}: spent ${sp:.3f} of ${cp:.2f}" + (" (shared judge pool)" if pool_of(rid) else ""))
        for i in inst.values():
            if i["run"] != rid:
                continue
            w = live.get(i["name"], {})
            st = w.get("status", "-") if i["live"] else "deleted"
            shell = w.get("shell_status", "")
            print(f"  {i['name']:32s} {i['brev_type'] or i['type']:28s} ${i['rate']:.3f}/h "
                  f"accrued ${i['accrued']:.3f}  {st} {shell}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="bt_compute", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, name=True):
        sp.add_argument("--arm")
        sp.add_argument("--run")
        if name:
            sp.add_argument("--name", required=True)

    sub.add_parser("quote")
    s = sub.add_parser("start"); common(s)
    s.add_argument("--wait", action="store_true", help="block until the shell works (up to the boot grace)")
    s.add_argument("--type", required=True, help="A6000, A100 or L40S")
    s.add_argument("--hours", type=float, default=caps()["default_hours"],
                   help="planned hours, used for the cap check (default 1)")
    e = sub.add_parser("exec"); common(e)
    e.add_argument("--timeout", type=int, default=1800)
    e.add_argument("command", nargs=argparse.REMAINDER)
    for d in ("to", "from"):
        cp = sub.add_parser(f"copy-{d}"); common(cp)
        cp.add_argument("--timeout", type=int, default=1200)
        cp.add_argument("src"); cp.add_argument("dst")
    wt = sub.add_parser("wait"); common(wt)
    wt.add_argument("--max-min", type=float, default=20.0)
    ng = sub.add_parser("ngc-login"); common(ng)
    st = sub.add_parser("stop"); common(st)
    ls = sub.add_parser("ls"); common(ls, name=False)

    a = p.parse_args(argv)
    if a.cmd == "exec" and a.command and a.command[0] == "--":
        a.command = a.command[1:]
    {"quote": cmd_quote, "start": cmd_start, "exec": cmd_exec,
     "copy-to": lambda x: _copy(x, "to"), "copy-from": lambda x: _copy(x, "from"),
     "stop": cmd_stop, "ls": cmd_ls, "wait": cmd_wait, "ngc-login": cmd_ngc}[a.cmd](a)


if __name__ == "__main__":
    main()
