"""judge_batch.py: score many prepared submissions in parallel on one machine (e.g. a Brev instance).

    python judge_batch.py results_dir/ [--workers N] [--threads T] [--only primary]

results_dir/<run>/judge_jobs.json + the mesh file come from `judge_submission.py --prepare-only` (run on the laptop,
where PreFormServer does the intake). Each job runs `judge.py` as its own process with T BLAS/OpenMP threads; N jobs
run at once (default: N = min(12, jobs, cpu_count // T, free_RAM_GB // 6)). Results land next to each judge_jobs.json;
then rank on the laptop with judge_rank.py. The solver is CPU (pyamg-preconditioned CG); the GPU is not needed.
Memory: about 1 GB per million DOF per process (h2 = 0.2 on a 25 x 12 x 10 mm implant is ~3.7 M DOF -> ~4-5 GB).
"""
import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent


def free_gb():
    try:
        if os.name == "nt":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tot", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                            ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong), ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
            m = MS(); m.l = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); return m.avail / 2**30
        for line in open("/proc/meminfo"):
            if line.startswith("MemAvailable"):
                return int(line.split()[1]) / 2**20
    except Exception:
        return 16.0


def run_job(job, d, threads):
    env = dict(os.environ, JUDGE_THREADS=str(threads), OMP_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads),
               OPENBLAS_NUM_THREADS=str(threads))
    t = time.time()
    flags = (0x08000000 | 0x00004000) if os.name == "nt" else 0
    with open(d / (Path(job["out"]).stem + ".log"), "w") as lg:
        rc = subprocess.run([sys.executable, str(HERE / "judge.py"), "--mesh", str(d / job["mesh"]), *job["args"],
                             "--out", str(d / job["out"])], stdout=lg, stderr=subprocess.STDOUT, env=env, creationflags=flags).returncode
    return {"run": job["run"], "tag": job["tag"], "rc": rc, "seconds": round(time.time() - t, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results"); ap.add_argument("--workers", type=int); ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--only")
    a = ap.parse_args()
    jobs = []
    for jf in sorted(Path(a.results).glob("*/judge_jobs.json")):
        for j in json.loads(jf.read_text()):
            if a.only and j["tag"] != a.only:
                continue
            if not (jf.parent / j["out"]).exists():
                jobs.append((j, jf.parent))
    n = a.workers or max(1, min(12, len(jobs), (os.cpu_count() or 4) // a.threads, int(free_gb() // 6)))
    print(json.dumps({"jobs": len(jobs), "workers": n, "threads_each": a.threads, "free_gb": round(free_gb(), 1)}), flush=True)
    log = []
    with ThreadPoolExecutor(n) as ex:
        for r in ex.map(lambda jd: run_job(jd[0], jd[1], a.threads), jobs):
            print(json.dumps(r), flush=True); log.append(r)
    (Path(a.results) / "batch_log.json").write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
