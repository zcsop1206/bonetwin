"""Agent-side wrapper for the project's resources (registry: ../tools.json). Same tools for every agent; each call
is charged at the caller's own genome price and logged to <agent>/tool_calls.jsonl and the arm's tool_log.jsonl.

    python bt_tool.py list                                   tools, your prices, availability
    python bt_tool.py train_widths -- <args>                 bonetwin/sim/train_widths.py (Warp width training)
    python bt_tool.py lean_gate -- <args>                    bonetwin/sim/lean_gate.py (Lean 4 admissibility proof)
    python bt_tool.py cad_python SCRIPT.py [args]            venv Python: build123d, manifold3d, trimesh, gmsh
    python bt_tool.py warp_gpu SCRIPT.py [args]              venv Python with NVIDIA Warp on the laptop GPU
    python bt_tool.py freecad SCRIPT.py                      FreeCAD 1.1 headless
    python bt_tool.py preform layout --manifest M.json [...] PreForm layout, always --dry-run (print is refused)
    python bt_tool.py preform spec|materials
    python bt_tool.py remote_gpu -- <args>                   remote GPU slot ('unavailable' unless configured)
    python bt_tool.py openresearch -- --query Q --max-papers N   OpenResearch literature search (if installed)
Scripts must be in your own folder; they run with your folder as working directory. The gateway's key is never in
your environment. Unavailable tools print 'unavailable: <reason>', exit 3, and are not charged.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HARNESS))
from common import BONETWIN, append_jsonl, load_config, load_json, read_jsonl, utc_now  # noqa: E402

REGISTRY = load_json(HARNESS / "tools.json")
WRAPPED = ["preform_api", "compute", "warp_gpu", "train_widths", "lean_gate", "cad_python", "freecad",
           "openresearch"]  # the judge's pre-check is harness-only (collect.py), not an agent tool
SIM = BONETWIN / "sim"
STRIP = ("BT_GATEWAY_KEY", "BT_GATEWAY_ADMIN", "ANTHROPIC_API_KEY")
HEAVY = ("train_widths", "lean_gate", "warp_gpu", "cad_python", "freecad")


def freecad_exe(cfg):
    p = (cfg.get("tools") or {}).get("freecadcmd") or ""
    if p and Path(p).exists():
        return p
    cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "FreeCAD 1.1" / "bin" / "freecadcmd.exe"
    return str(cand) if cand.exists() else (shutil.which("freecadcmd") or "")


def preform_up(timeout=1.0):
    """True when the PreForm adapter (preform_tool.py) reports a server; the public copy's mock always does."""
    try:
        sys.path.insert(0, str(BONETWIN))
        import preform_tool as pt
        return bool(pt.server_up())
    except Exception:
        return False


def _cfg_path(rel):
    p = Path(rel)
    return p if p.is_absolute() else (HARNESS / p).resolve()


def availability(tool, cfg):
    if os.environ.get("BT_MOCK_TOOLS") and tool in ("compute", "precheck", "preform_api"):
        return True, str(HARNESS / "sim_mock" / {"compute": "bt_compute.py", "precheck": "precheck.py",
                                                  "preform_api": "preform_api"}[tool])
    if tool == "preform_api":
        return (True, cfg["preform"]["server"]) if preform_up() else (False, "PreForm adapter reports no server")
    if tool == "compute":
        s = _cfg_path(cfg["compute"]["script"])
        return (True, str(s)) if s.exists() else (False, "bonetwin/compute/bt_compute.py not installed yet")
    if tool == "precheck":
        s = _cfg_path(cfg["judge"]["precheck"])
        return (True, str(s)) if s.exists() else (False, "the judge's pre-check tool is not published yet")
    if tool in ("train_widths", "lean_gate"):
        s = SIM / REGISTRY["provided"][tool]["script"]
        return (True, str(s)) if s.exists() else (False, f"{s.name} not in bonetwin/sim yet")
    if tool in ("cad_python", "warp_gpu"):
        mods = {"cad_python": "build123d, manifold3d, trimesh, gmsh", "warp_gpu": "warp"}[tool]
        r = subprocess.run([sys.executable, "-c", f"import {mods}"], capture_output=True, text=True)
        return (True, sys.executable) if r.returncode == 0 else (False, f"this Python lacks {mods}")
    if tool == "openresearch":
        s = HERE / "openresearch_tool.py"
        return (True, str(s)) if s.exists() else (False, "tools/openresearch_tool.py not installed")
    if tool == "freecad":
        exe = freecad_exe(cfg)
        return (True, exe) if exe else (False, "freecadcmd.exe not found")
    if tool == "preform":
        return (BONETWIN / "preform_tool.py").exists(), "preform_tool.py (layout dry-run works offline; "\
            f"server {'up' if preform_up() else 'down'})"
    if tool == "remote_gpu":
        cmd = ((cfg.get("tools") or {}).get("remote_gpu") or {}).get("cmd")
        return (True, cmd) if cmd else (False, "no remote GPU configured tonight (Brev A100 not set up)")
    return True, sys.executable


def openalex_budget(args, g, arm_log):
    """OpenAlex allows ~100 keyless searches a day shared by every agent: each arm run gets the same small cap
    (genome openalex_arm_cap, set at launch). Past the cap OpenAlex is dropped from --sources (other sources stay)."""
    args = list(args)
    if "--sources" in args:
        i = args.index("--sources")
        sources = args[i + 1].split(",") if i + 1 < len(args) else []
        del args[i:i + 2]
    else:
        sources = ["openalex", "embedding"]
    cap = int(g.get("openalex_arm_cap", 2))
    used = sum(1 for r in read_jsonl(arm_log) if r.get("tool") == "openresearch" and r.get("openalex")
               and r.get("result") == "ok")
    note = {"openalex": "openalex" in sources, "text": ""}
    if "openalex" in sources and used >= cap:
        sources = [s for s in sources if s != "openalex"] or ["embedding", "keyword"]
        note = {"openalex": False, "text": f"note: this arm's OpenAlex budget ({cap} searches, shared limit) is used; "
                                           f"searched {','.join(sources)} instead"}
    return args + ["--sources", ",".join(sources)], note


def rate_limited(stdout):
    try:
        out = stdout.strip()
        res = json.loads(out[out.index("{"):]) if "{" in out else {}
    except (json.JSONDecodeError, IndexError, ValueError):
        try:
            res = json.loads(stdout)
        except json.JSONDecodeError:
            return "429" in stdout
    errs = json.dumps(res.get("errors") or "")
    return not res.get("papers") and ("429" in errs or "rate" in errs.lower())


def allowed_dirs(g):
    dirs = [Path(g["dir"]).resolve(), Path(g["kb_dir"]).resolve()]
    if g.get("role") != "member":  # planner members cannot write the deliverables
        dirs.append(Path(g["deliverables_dir"]).resolve())
    return dirs


def record_precheck(stdout, g, cfg, args):
    """The harness (not the agent) records the pre-check's primary-score estimate, with a hash of the agent's
    deliverables at that moment; best_of_n selection reads only this log."""
    import hashlib
    try:
        res = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else {}
    except (json.JSONDecodeError, IndexError):
        try:
            res = json.loads(stdout)
        except json.JSONDecodeError:
            res = {}
    key = cfg["judge"].get("estimate_key", "primary_estimate")
    est = res.get(key) if isinstance(res, dict) else None
    d = Path(g["deliverables_dir"])
    h = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.glob("*")) if f.is_file()}
    append_jsonl(Path(g["arm_dir"]) / "precheck_log.jsonl",
                 {"ts": utc_now(), "agent": g["id"], "estimate": est, "args": args[:12], "deliverables": h})


def preform_api(args, g, me, cfg, m, log, arm_log):
    """Proxy to the PreForm adapter (preform_tool.call): print/device operations refused; file paths only in the
    agent's folders. Usage: preform_api OP [--body body.json], OP one of preform_tool.OPS."""
    if len(args) < 1:
        sys.exit("usage: preform_api OP [--body body.json]")
    path = args[0]
    method = "OP"
    low = path.lower()
    if any(x in low for x in cfg["preform"]["denied_path_parts"]):
        sys.exit("refused: printing and device operations are not available (printers are on an offline network)")
    body = None
    if "--body" in args:
        bf = me / args[args.index("--body") + 1]
        if not inside(bf, me):
            sys.exit("refused: the body file must be in your folder")
        body = json.loads(bf.read_text(encoding="utf-8"))

    def check_paths(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and (k in ("file", "path", "folder", "output", "out") or ":\\" in v
                                           or v.endswith((".stl", ".3mf", ".form", ".obj", ".png"))):
                    pv = Path(v) if Path(v).is_absolute() else me / v
                    if not any(inside(pv, a) for a in allowed_dirs(g)):
                        sys.exit(f"refused: {k}={v} is outside your folders")
                    obj[k] = str(pv.resolve())
                else:
                    check_paths(v)
        elif isinstance(obj, list):
            for x in obj:
                check_paths(x)
    check_paths(body)
    if os.environ.get("BT_MOCK_TOOLS"):  # smoke tests: no server; a save writes a placeholder .form
        if path == "save_form" and body and body.get("file"):
            Path(body["file"]).write_bytes(b"MOCK FORM " + path.encode())
        m.charge_tool("preform_api")
        append_jsonl(me / "tool_calls.jsonl", dict(log, result="ok", charged=0, path=path, mock=True))
        print(json.dumps({"mock": True, "path": path}))
        return 0
    if not preform_up():
        append_jsonl(me / "tool_calls.jsonl", dict(log, result="unavailable", charged=0))
        print("unavailable: PreFormServer is not running")
        return 3
    price = float(g["tool_prices"].get("preform_api", 0))
    if m.balance() <= 0 or price > m.balance():
        sys.exit("refused by meter: preform_api costs more than your balance")
    sys.path.insert(0, str(BONETWIN))
    import preform_tool as pt  # the adapter: mock in the public copy, or your own via BT_PREFORM_ADAPTER
    try:
        res, rc = pt.call(path, body), 0
        out = json.dumps(res)
    except Exception as exc:
        out, rc = f"error: {exc}", 1
    m.charge_tool("preform_api")
    append_jsonl(me / "tool_calls.jsonl", dict(log, result="ok" if rc == 0 else "error", charged=price, path=path))
    append_jsonl(arm_log, dict(log, result="ok" if rc == 0 else "error", charged=price, path=path))
    print(out[-20000:])
    return rc


def inside(path, folder):
    try:
        Path(path).resolve().relative_to(Path(folder).resolve())
        return True
    except ValueError:
        return False


def main(argv):
    adir = os.environ.get("BT_AGENT_DIR")
    if not adir:
        sys.exit("No agent identity (BT_AGENT_DIR).")
    from meter import Meter
    m = Meter(adir)
    g = m.genome
    if os.environ.get("BT_AGENT") and os.environ["BT_AGENT"] != g["id"]:
        sys.exit("refused: claimed identity does not match this agent's genome")
    cfg = load_config()
    me = Path(adir).resolve()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    tool, args = argv[0], argv[1:]
    if args[:1] == ["--"]:
        args = args[1:]
    if tool == "list":
        for t, spec in REGISTRY["provided"].items():
            price = g["tool_prices"].get(t, g["tool_prices"].get(t.replace("score_", "gateway_"), 0))
            ok, why = availability(t, cfg) if t in WRAPPED else (True, "")
            print(f"{t:18s} price {price:>6} credits  {'available' if ok else 'UNAVAILABLE'}  {spec['how']}")
        for t, why in REGISTRY["not_provided"].items():
            print(f"{t:18s} not provided: {why}")
        return 0
    if tool not in WRAPPED:
        sys.exit(f"unknown tool {tool}; run `bt_tool.py list`")
    ok, where = availability(tool, cfg)
    log = {"ts": utc_now(), "agent": g["id"], "tool": tool, "args": args[:12]}
    arm_log = Path(g["arm_dir"]) / "tool_log.jsonl"
    if not ok:
        append_jsonl(me / "tool_calls.jsonl", dict(log, result="unavailable", reason=where, charged=0))
        append_jsonl(arm_log, dict(log, result="unavailable", charged=0))
        print(f"unavailable: {where}")
        return 3
    env = {k: v for k, v in os.environ.items() if k not in STRIP}
    if tool in ("cad_python", "warp_gpu", "freecad"):
        if not args or not inside(me / args[0], me) or not (me / args[0]).exists():
            sys.exit("refused: give a script that exists in your own folder")
        script = str((me / args[0]).resolve())
        cmd = ([sys.executable, script, *args[1:]] if tool != "freecad" else [where, script])
    elif tool == "preform_api":
        return preform_api(args, g, me, cfg, m, log, arm_log)
    elif tool == "compute":
        env.update(BT_COMPUTE_RUN=f"{g['run_id']}/{g['arm']}", BT_COMPUTE_AGENT=g["id"],
                   BT_COMPUTE_CAP_USD=str(cfg["budget"]["compute_usd_per_run"]))
        cmd = [sys.executable, where, *args]
    elif tool == "precheck":
        cmd = [sys.executable, where, *args]
    elif tool == "openresearch":
        args, orx_note = openalex_budget(args, g, arm_log)
        log["openalex"] = orx_note["openalex"]
        env["OPENRESEARCH_TOOL_LOG"] = str(me / "openresearch_calls.jsonl")  # per agent, not in the harness folder
        cmd = [sys.executable, where, *args]  # OPENALEX_API_KEY / OPENALEX_MAILTO pass through if set
    elif tool in ("train_widths", "lean_gate"):
        import gateway as gw
        info = gw.frozen(g["root"])
        env = gw.gateway_env(info)  # these tools may sign their results like the gateway does
        cmd = [sys.executable, where, *args]
    elif tool == "preform":
        if any("print" in a.lower() for a in args):
            sys.exit("refused: the preform wrapper cannot print or list printers")
        sub = args[0] if args else ""
        if sub == "layout":
            rest = [a for a in args[1:] if a not in ("--dry-run", "--keep-scene")]
            if "--manifest" not in rest:
                sys.exit("refused: layout needs --manifest M.json from your own folder")
            mi = rest.index("--manifest") + 1
            if mi >= len(rest) or not inside(me / rest[mi], me):
                sys.exit("refused: the manifest must be in your own folder")
            rest[mi] = str((me / rest[mi]).resolve())
            out = me / "preform_out"
            out.mkdir(exist_ok=True)
            cmd = [sys.executable, str(BONETWIN / "preform_tool.py"), "--manifest", rest.pop(mi), "--out", str(out)]
            rest.pop(mi - 1)
            cmd += ["layout", "--dry-run", *rest]
        elif sub in ("spec", "materials"):
            if sub == "materials" and not preform_up():
                append_jsonl(me / "tool_calls.jsonl", dict(log, result="unavailable", reason="server down", charged=0))
                print("unavailable: the PreForm adapter reports no server")
                return 3
            cmd = [sys.executable, str(BONETWIN / "preform_tool.py"), sub]
        else:
            sys.exit("refused: preform allows layout (dry-run), spec, materials")
    else:  # remote_gpu
        cmd = [*where.split(), *args]
    price = float(g["tool_prices"].get(tool, 0))
    bal = m.balance()
    if bal <= 0 or price > bal:
        sys.exit(f"refused by meter: {tool} costs {price:.0f}, balance {bal:.0f}")
    env.update({"OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4",
                "NUMEXPR_NUM_THREADS": "4"})
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)

    def _run():
        try:
            r_ = subprocess.run(cmd, cwd=str(me), env=env, capture_output=True, text=True, creationflags=flags,
                                timeout=(cfg.get("tools") or {}).get("timeout_s", 1800))
            return r_, r_.returncode, (r_.stdout + ("\n" + r_.stderr if r_.stderr else ""))
        except subprocess.TimeoutExpired:
            return None, 124, "timeout"
    if tool in HEAVY:  # local solvers share a global FIFO semaphore (heavy_slots, 2); Brev (compute) is not counted
        import gateway as gw
        try:
            with gw.VoxelLock(HARNESS / "voxel.lock", who=f"{g.get('run_id')}/{g.get('arm')}/{g['id']}:{tool}",
                              slots=cfg.get("heavy_slots", 1), wait_s=300,
                              min_ram=cfg.get("heavy_min_free_ram_gb", 2.5)):
                r, rc, out = _run()
        except RuntimeError:
            append_jsonl(me / "tool_calls.jsonl", dict(log, result="unavailable", reason="heavy queue / RAM", charged=0))
            print("unavailable: the local heavy-job slot is busy or free RAM is below 2.5 GB (one local heavy job at a "
                  "time); not charged. Try again later, or run it on Brev through `bt_tool.py compute`.")
            return 3
    else:
        r, rc, out = _run()
    if tool == "openresearch" and rate_limited(r.stdout if r is not None else ""):
        # non-fatal for the agent: not charged, stated as unavailable
        append_jsonl(me / "tool_calls.jsonl", dict(log, result="unavailable", reason="rate limited (429)", charged=0))
        append_jsonl(arm_log, dict(log, result="unavailable", reason="rate limited (429)", charged=0))
        print("unavailable: literature sources rate-limited (HTTP 429); not charged. Try other sources "
              "(--sources embedding,keyword,pubmed) or later.")
        return 3
    m.charge_tool(tool)
    if tool == "precheck":
        record_precheck(r.stdout if r is not None else "", g, cfg, args)
    if tool == "openresearch":
        print(orx_note["text"], file=sys.stderr)
    append_jsonl(me / "tool_calls.jsonl", dict(log, result="ok" if rc == 0 else f"exit {rc}", charged=price))
    append_jsonl(arm_log, dict(log, result="ok" if rc == 0 else f"exit {rc}", charged=price))
    print(out[-20000:])
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
