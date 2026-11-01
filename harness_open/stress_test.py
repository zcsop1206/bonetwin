"""Stress test: 14 hidden dummy processes + the admission rule (no API, no agents).

    python stress_test.py

1. Spawns 14 dummy Python children exactly as the scheduler spawns runners (common.spawn_hidden: CREATE_NO_WINDOW,
   below-normal priority, own process group), each of which also starts a grandchild console process, then counts
   visible top-level windows owned by any of those processes (EnumWindows). Expect 0. Also checks the priority class.
2. Admission rule (scheduler.admit) on the live RAM/CPU readings and on edge cases (slots, RAM, CPU), and a
   3-check scheduler-style loop that logs counts/RAM/CPU only.
"""
import ctypes
import ctypes.wintypes as wt
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import CpuMeter, free_ram_gb, load_config, spawn_hidden  # noqa: E402
from scheduler import admit  # noqa: E402

OK = []


def check(name, ok, detail=""):
    OK.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail != "" else ""))


def visible_windows(pids):
    u32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        pid = wt.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and u32.IsWindowVisible(hwnd):
            found.append(pid.value)
        return True
    u32.EnumWindows(cb, 0)
    return found


def tree_pids(root_pids):
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId | ConvertTo-Json"],
                         capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    rows = json.loads(out.stdout)
    kids = {}
    for r in rows:
        kids.setdefault(r["ParentProcessId"], []).append(r["ProcessId"])
    seen, stack = set(), list(root_pids)
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack += kids.get(p, [])
    return seen


def main():
    logs = HERE / "smoke" / "stress"
    logs.mkdir(parents=True, exist_ok=True)
    child = ("import subprocess, time; subprocess.Popen(['cmd', '/c', 'ping -n 30 127.0.0.1 > nul']); "
             "time.sleep(30)")
    ram0 = free_ram_gb()
    procs = [spawn_hidden([sys.executable, "-c", child], logs / f"dummy{i}.log", HERE) for i in range(14)]
    time.sleep(6)
    pids = tree_pids([p.pid for p in procs])
    vis = visible_windows(pids)
    check("14 hidden dummies (+ console grandchildren): no visible windows", not vis and len(pids) >= 28,
          f"{len(pids)} processes in the trees, visible windows {len(vis)}")
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, procs[0].pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    pc = k32.GetPriorityClass(h)
    check("children run at below-normal priority", pc == 0x4000, hex(pc))
    ram1 = free_ram_gb()
    cpu = CpuMeter(60)
    ad = load_config()["admission"]
    rows = []
    for k in range(3):
        load = cpu.sample()
        rows.append({"running": 14, "free_ram_gb": round(free_ram_gb(), 2), "cpu_pct_1min": load,
                     "admit_one_more": admit(14, 1, free_ram_gb(), load, ad), "admit_group_at_8": admit(8, 6, free_ram_gb(), load, ad)})
        time.sleep(2)
    check("admission refuses a 15th session (max 14)", not any(r["admit_one_more"] for r in rows), rows[-1])
    check("admission rule edge cases", admit(0, 6, 10.0, 10, ad) and not admit(9, 6, 10.0, 10, ad) and
          not admit(0, 6, ad["min_free_ram_gb"] + 0.1, 10, ad) and not admit(0, 1, 10.0, ad["max_cpu_pct"], ad)
          and admit(0, 1, ad["min_free_ram_gb"], 10, ad))
    check("RAM / CPU readings sane", 0 < ram1 < 64 and 0 <= rows[-1]["cpu_pct_1min"] <= 100,
          f"free RAM {ram0:.2f} -> {ram1:.2f} GB with 14 dummies")
    for p in procs:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    print(f"{sum(OK)}/{len(OK)} passed")
    return 0 if all(OK) else 1


if __name__ == "__main__":
    sys.exit(main())
