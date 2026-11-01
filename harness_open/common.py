"""Shared paths, config, targets, genome draws and the batch schedule for the bone-twin overnight DESIGN run.

Adapted from ../harness/common.py (the sealed prediction run, left untouched). Layout under a root:
    run/<run_id>/<arm>/arm.json, board.jsonl, gateway_ledger.jsonl, agents/<id>/...
    sealed/<run_id>/<arm>.json, sealed/hashes.log
run_id = <target>_r<replicate>; the remove-one rerun is arm "collective_minus_<id>" inside the same run_id.
"""
import datetime as dt
import json
import os
import random
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BONETWIN = HERE.parent
CONFIG_FILE = HERE / "config.json"
FACTS_FILE = HERE / "facts_design.md"
PACKS_DIR = HERE / "packs"

AGENT_ARMS = ["single", "best_of_n", "collective", "planner"]
ARMS = ["control"] + AGENT_ARMS
FINAL_STATES = {"done", "capped", "safety_cap", "failed", "no_final"}  # waiting_usage_window is not final
PREFIX = {"single": "s", "best_of_n": "b", "collective": "c", "planner": "p"}
SHARED_BOARD_ARMS = {"collective", "planner"}
PLANNER_LABEL = ("CENTRALIZED CONTROL GROUP (star graph by construction): p1 is told it is the lead, assigns tasks "
                 "and picks the arm's design. Exists only to show what a star communication graph looks like; "
                 "it is not a decentralized arm.")


def load_json(path, default=None):
    """Read JSON, retrying briefly: on Windows another process may be mid-replace."""
    path = Path(path)
    for i in range(50):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (PermissionError, json.JSONDecodeError):
            time.sleep(0.05 * (i + 1))
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, obj):
    """Atomic replace, retried: Windows refuses os.replace while a reader holds the target open."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    for i in range(50):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05 * (i + 1))
    os.replace(tmp, path)


def append_jsonl(path, rec):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:  # a line being appended right now
                pass
    return out


def load_config():
    return load_json(CONFIG_FILE)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def local_now():
    return dt.datetime.now().astimezone()


def clock_next(hhmm, now=None):
    """Next occurrence of HH:MM local time (today if still ahead, else tomorrow): 05:00 at 18:05 is tomorrow."""
    now = now or local_now()
    h, m = map(int, hhmm.split(":"))
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return t if t > now else t + dt.timedelta(days=1)


def bt_path(rel):
    """Resolve a config path relative to the design harness folder."""
    p = Path(rel)
    return p if p.is_absolute() else (HERE / p).resolve()


# ---------------------------------------------------------------- layout

def run_dir(root):
    return Path(root) / "run"


def sealed_dir(root):
    return Path(root) / "sealed"


def arm_dir(root, run_id, arm):
    return run_dir(root) / run_id / arm


def agent_dir(root, run_id, arm, aid):
    return arm_dir(root, run_id, arm) / "agents" / aid


def board_path(root, run_id, arm):
    """Every agent arm has a board file. Only collective and planner agents read or post to theirs;
    for single and best_of_n it only receives the seal record."""
    return arm_dir(root, run_id, arm) / "board.jsonl"


def ledger_path(root, run_id, arm):
    """Harness-written record of every gateway call in the arm (agents are blocked from it)."""
    return arm_dir(root, run_id, arm) / "gateway_ledger.jsonl"


def base_arm(arm):
    """Leader-intervention reruns (collective_minus_<id>, collective_cap_<id>) are collective arms."""
    return "collective" if arm.startswith(("collective_minus_", "collective_cap_")) else arm


# ---------------------------------------------------------------- targets

def load_targets(cfg):
    """Site names and visible load cases. Falls back to placeholders until targets.json lands."""
    t = cfg["targets"]
    f = bt_path(t["file"])
    data = load_json(f) if f.exists() else None
    if data:
        sites = data.get("sites") or data.get("targets") or data
        if isinstance(sites, dict):
            items = [dict(v, name=k) if isinstance(v, dict) else {"name": k, "value": v} for k, v in sites.items()]
        else:
            items = [s if isinstance(s, dict) else {"name": str(s)} for s in sites]
        items = [dict(s, name=s.get("name") or s.get("site") or s.get("id")) for s in items]
        if t.get("only"):
            items = [s for s in items if s["name"] in t["only"]]
        return items[: t["n_targets"]], f"targets.json ({f})"
    return [{"name": n, "placeholder": True} for n in t["placeholders"]], "placeholders (targets.json not found)"


def public_target(site, cfg=None):
    """Visible load cases only: drop anything that looks sealed or hidden. For a 2-D run the site's '2d' reduction
    (targets.json["2d"][site]) and the 2-D description are added."""
    bad = ("sealed", "hidden", "secret", "holdout")

    def clean(d):
        return {k: (clean(v) if isinstance(v, dict) else v) for k, v in d.items()
                if not any(b in str(k).lower() for b in bad)}
    out = clean(site)
    cfg = cfg or {}
    if cfg.get("gateway", {}).get("dim") == 2 and cfg.get("targets", {}).get("use_2d_key"):
        data = load_json(bt_path(cfg["targets"]["file"])) or {}
        two = data.get("2d") or {}
        out = {"dim": 2, "2d": clean(two.get(site["name"]) or {}),
               "2d_description": two.get("description"), "square_edge_mm": two.get("square_edge_mm"),
               "conventions": data.get("conventions"), "scaling_to_resin": data.get("scaling_to_resin"),
               "site_3d_visible": out}
    return out


# ---------------------------------------------------------------- genomes

def _genome(rng, cfg, aid):
    """Open run: tool prices and token weights are fixed (equal for everyone); the affinity is four drawn lines
    (knowledge, tools, communication, working style), shown in the brief as leanings, not roles."""
    g = cfg["genome"]
    model = "nemotron" if rng.random() < g["p_nemotron"] else "claude"
    lean = {axis: rng.choice(opts) for axis, opts in sorted(cfg["affinity_axes"].items())}
    return {"id": aid, "model_drawn": model, "pack": "none", "tool_prices": dict(cfg["fixed_tool_prices"]),
            "credit_weights": dict(cfg["credit_weights_fixed"]), "leanings": lean}


def draw_genomes(cfg, rep):
    """Replicate rep draws six leaning sets from seed+rep; best_of_n, collective and planner reuse them (same
    distribution and seeds); single is a 'generalist' with no leaning. Quotas: six agents x agent_quota, single
    single_quota (the run's whole budget)."""
    n = cfg["n_agents"]
    rng = random.Random(cfg["seed"] + rep)
    six = [_genome(rng, cfg, f"g{i + 1}") for i in range(n)]
    q = cfg["budget"]["agent_quota"]
    out = {}
    for arm in ("best_of_n", "collective", "planner"):
        out[arm] = [dict(g, id=PREFIX[arm] + g["id"][1:], genome_source=f"r{rep}.{g['id']}", quota=q) for g in six]
    out["planner"][0]["role"] = "lead"
    for g in out["planner"][1:]:
        g["role"] = "member"
    single = _genome(random.Random(cfg["seed"] + rep + 1000), cfg, "s1")
    single["leanings"] = {axis: "generalist" for axis in cfg["affinity_axes"]}
    single["quota"] = cfg["budget"]["single_quota"]
    single["genome_source"] = f"r{rep}.single"
    out["single"] = [single]
    return out


def sessions(arm_or_genomes):
    if isinstance(arm_or_genomes, list):
        return len(arm_or_genomes)
    return 1 if arm_or_genomes == "single" else 6


# ---------------------------------------------------------------- schedule

def build_schedule(cfg, targets=None):
    """Open run: one batch per replicate (run_id r1, r2), all four agent arms each; arm start order rotates per
    batch. Every run works until the same 07:00 deadline, so both batches start at launch (max_sessions 40)."""
    batches = []
    for k, rep in enumerate(range(1, cfg["replicates"] + 1)):
        order = AGENT_ARMS[k % 4:] + AGENT_ARMS[:k % 4]
        batches.append({"batch": k + 1, "target": cfg.get("control", {}).get("target", "lumbar_vertebra"),
                        "rep": rep, "run_id": f"r{rep}", "arms": order})
    return batches


# ---------------------------------------------------------------- processes and machine load (open run, 01:20)

HEAVY_ENV = {"OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4"}


def hidden_flags():
    """No visible console window, below-normal priority, own process group (survives its parent's exit)."""
    if os.name != "nt":
        return 0
    import subprocess as _sp
    return _sp.CREATE_NO_WINDOW | _sp.BELOW_NORMAL_PRIORITY_CLASS | _sp.CREATE_NEW_PROCESS_GROUP


def spawn_hidden(argv, log_path, cwd, env=None):
    import subprocess as _sp
    out = open(log_path, "a", encoding="utf-8")
    return _sp.Popen(argv, stdout=out, stderr=_sp.STDOUT, stdin=_sp.DEVNULL, creationflags=hidden_flags(),
                     close_fds=True, cwd=str(cwd), env=env)


def free_ram_gb():
    if os.name != "nt":
        return float("inf")
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2 ** 30


class CpuMeter:
    """System CPU busy % over the last `window` seconds, from GetSystemTimes samples."""

    def __init__(self, window=60.0):
        self.window, self.samples = window, []

    @staticmethod
    def _times():
        import ctypes
        idle, kern, user = (ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong())
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
        return idle.value, kern.value + user.value  # kernel time includes idle

    def sample(self):
        if os.name != "nt":
            return 0.0
        now = time.time()
        idle, total = self._times()
        self.samples.append((now, idle, total))
        self.samples = [s for s in self.samples if now - s[0] <= self.window + 31] or self.samples[-1:]
        old = next((s for s in self.samples if now - s[0] <= self.window + 1), self.samples[0])
        if old is self.samples[-1]:
            time.sleep(1.0)
            idle2, total2 = self._times()
            d_idle, d_tot = idle2 - idle, total2 - total
        else:
            d_idle, d_tot = idle - old[1], total - old[2]
        return round(100.0 * (1 - d_idle / d_tot), 1) if d_tot > 0 else 0.0
