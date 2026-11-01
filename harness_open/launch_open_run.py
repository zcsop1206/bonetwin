"""Launch the bone-twin OPEN run: every arm pursues one goal, verbatim, and delivers files by 07:00.

    python launch_open_run.py --dry-run     # plan, leanings, budgets, est. tokens, tool status, brief check
    python launch_open_run.py               # real: health, control, agent folders, spawn the scheduler, exit
    python launch_open_run.py --mock --mock-tools --root <dir> --batches 1 --wall-cap-min 3   (smoke)
    python launch_open_run.py --archive-aborted     # first renames the aborted 00:52 run folders (*_aborted_0052)

Arms (2 replicates each): control (no agent: the gateway's Gibson-Ashby two-step control as STL + PreForm .form in
Rigid 10K, built at launch), single (1 agent, 2.5M credits), best_of_n (6 isolated agents, 0.42M each; submission =
best harness-logged judge pre-check estimate, else a seeded random agent's), collective (6 peers, shared board and
KB), planner (6 agents, p1 leads, routing enforced). Same model, tools, data and prices for every agent; leanings
(four drawn lines) are the only affinity. Admission-controlled scheduler (scheduler.py): at most 14 sessions, free
RAM and CPU checks, groups of 6 for board arms, a 2-hour wall cap per session (group: from the group's start),
notices at cap-60 and cap-15, last start 06:30, hard deadline 08:30; collection and metrics are code. Leader interventions: config switch, OFF.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import briefs  # noqa: E402
import gateway as gw  # noqa: E402
from common import spawn_hidden  # noqa: E402
from common import (AGENT_ARMS, BONETWIN, HERE, arm_dir, board_path, bt_path, build_schedule, clock_next,  # noqa: E402
                    draw_genomes, load_config, load_targets, public_target, run_dir, sealed_dir, utc_now,
                    write_json)

RULE_SOURCES = {
    "config.json": "user decisions (open goal, arms, budgets, deadline, notices, deliverables, affinities, switches)",
    "briefs.py": "minimal brief template: goal, deliverables, judging summary, resources, budget, arm rule",
    "board.py": "board rules: evidence-backed claims, planner routing, needs, typed links, done",
    "meter.py": "quota, access rules, notices, model pin, redaction",
    "collect.py": "pre-registered deadline collection and per-arm submission rules",
    "control_build.py": "control arm: deterministic Gibson-Ashby design -> STL -> .form (Rigid 10K)",
    "tools.json": "tool registry, same for every agent",
    "tools/bt_tool.py": "tool wrappers: PreForm API proxy (no print), compute, precheck log, OpenAlex cap",
    "scheduler.py": "start, notices, KB snapshots, collection",
    "directives.py": "directive classifier",
    "gateway.py": "signature contract, FIFO queue",
    "../sim/EVAL_SPEC_v1.md": "the judge's evaluation spec v1 (written by the judge agent); addenda hashed too",
}


def estimate(agents, cfg):
    te = cfg["token_estimate"]
    out = {}
    for label, frac in (("likely", te["likely_fraction_of_quota"]), ("full_quota", 1.0)):
        tot = {"tokens": 0, "usd": 0.0, "turns": 0, "cache_read": 0, "output": 0}
        for g in agents:
            w = g["credit_weights"]
            ctx, credits, turns = te["first_context"], 0.0, 0
            raw = {"input": 0, "cache_creation": 0, "cache_read": 0, "output": 0}
            while credits < g["quota"] * frac and turns < 5000:
                cc = te["new_context_per_turn"] if turns else te["first_context"]
                cr = ctx if turns else 0
                o = te["output_per_turn"]
                ex = (w["cache_read"] * min(cr, te["first_context"])) if turns else w["cache_creation"] * cc
                credits += w["cache_creation"] * cc + w["cache_read"] * cr + w["output"] * o + 150 - ex
                raw["cache_creation"] += cc; raw["cache_read"] += cr; raw["output"] += o; raw["input"] += 20
                ctx += te["new_context_per_turn"] + o
                if ctx > te.get("context_cap", 400000):
                    ctx = te["first_context"] + 40000
                turns += 1
            tot["tokens"] += sum(raw.values()); tot["turns"] += turns
            tot["usd"] += sum(raw[k] * te["usd_per_mtok"][k] for k in raw) / 1e6
            tot["cache_read"] += raw["cache_read"]; tot["output"] += raw["output"]
        out[label] = tot
    return out


def harness_hashes(out):
    lines = []
    for f in sorted(HERE.rglob("*")):
        rel = f.relative_to(HERE)
        if f.is_file() and "__pycache__" not in f.parts and "aborted" not in rel.parts[0] and rel.parts[0] not in (
                "run", "sealed", "public", "analysis", "metrics", "submissions", "control", "smoke") \
                and f.name != ".gateway_key" and not f.name.endswith((".tmp", ".jsonl", ".log", ".lock")):
            lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {rel.as_posix()}")
    spec_files = [cfg_spec := load_config()["judge"]["eval_spec"]] + [
        str(Path(cfg_spec).parent / x.name).replace("\\", "/") for x in sorted(
            bt_path(cfg_spec).parent.glob(load_config()["judge"].get("eval_addenda_glob", "x")))]
    for extra in (*spec_files, "../sim/run_spec.json", "../sim/desirability.json"):
        p = (HERE / extra).resolve()
        if p.exists():
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {extra}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def touch(root, what):
    with (run_dir(root) / "touch.log").open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {what}\n")


def rules_manifest(root):
    rows = [{"file": f, "sha256": hashlib.sha256((HERE / f).read_bytes()).hexdigest(), "source": src}
            for f, src in RULE_SOURCES.items() if (HERE / f).exists()]
    write_json(run_dir(root) / "rules_manifest.json", {"utc": utc_now(), "rules": rows,
                                                       "change_policy": "mid-run changes only via intervene.py"})
    return {"n_files": len(rows), "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}


def data_files(cfg, public_dir, write):
    """Snapshot the data dirs read-only into public/data (no scripts); returns relative names and hashes."""
    names, hashes = [], {}
    excl = tuple(cfg["published_data"].get("exclude_ext", []))
    for rel in cfg["published_data"]["dirs"]:
        src = bt_path(rel)
        if not src.exists():
            continue
        for f in sorted(src.rglob("*")):
            if not f.is_file() or "__pycache__" in f.parts or f.name.endswith(excl) or f.stat().st_size > 50_000_000:
                continue
            name = f"{src.name}/{f.relative_to(src).as_posix()}"
            names.append(name)
            if write:
                dest = Path(public_dir) / "data" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest)
                hashes[name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return names, hashes


def judging_summary(cfg):
    spec = bt_path(cfg["judge"]["eval_spec"])
    if cfg["judge"].get("summary"):
        return cfg["judge"]["summary"], spec.exists()
    if spec.exists():
        txt = spec.read_text(encoding="utf-8")
        paras = [p.strip() for p in txt.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        return (paras[0] if paras else "See EVAL_SPEC.md."), True
    return "(EVAL_SPEC.md not yet published by the judge.)", False


def tool_status(cfg, mock_tools):
    sys.path.insert(0, str(HERE / "tools"))
    import bt_tool
    st = {}
    for t in bt_tool.REGISTRY["provided"]:
        if t in bt_tool.WRAPPED:
            ok, why = bt_tool.availability(t, cfg)
            if mock_tools and t in ("compute", "precheck", "preform_api"):
                ok, why = True, "MOCK"
            st[t] = "available" if ok else f"unavailable: {why}"
        else:
            st[t] = "available"
    return st


def ensure_preform(cfg):
    sys.path.insert(0, str(HERE / "tools"))
    import bt_tool
    if bt_tool.preform_up():
        return "up"
    exe = bt_path(cfg["preform"]["exe"])
    if not exe.exists():
        return "down (no exe)"
    sys.path.insert(0, str(HERE.parent))
    import preform_tool as pt  # the adapter starts the server (public copy: mock, nothing to start)
    pt.start_server(exe)
    for _ in range(60):
        time.sleep(2)
        if bt_tool.preform_up():
            return "started"
    return "down (start timed out)"


def build_units(items, draws):
    """Pre-registered start order: groups collective_r1, planner_r1, collective_r2, planner_r2 (whole groups of 6;
    the scheduler tries groups first); fills one by one, single and best_of_n agents, r1/r2 alternating."""
    by = {(it["run_id"], it["arm"]): it for it in items}
    units = []
    for run_id in ("r1", "r2"):
        for arm in ("collective", "planner"):
            it = by.get((run_id, arm))
            if it:
                units.append({"key": f"{run_id}/{arm}", "item": f"{run_id}/{arm}", "kind": "group",
                              "run_id": run_id, "arm": arm, "agents": it["agents"]})
    fills = []
    for run_id in ("r1", "r2"):
        it = by.get((run_id, "single"))
        if it:
            fills.append((0, run_id, "single", it["agents"][0]))
    for k in range(6):
        for run_id in ("r1", "r2"):
            it = by.get((run_id, "best_of_n"))
            if it and k < len(it["agents"]):
                fills.append((k + 0.5, run_id, "best_of_n", it["agents"][k]))
    fills.sort(key=lambda f: (f[0], f[1]))
    for _, run_id, arm, aid in fills:
        units.append({"key": f"{run_id}/{arm}/{aid}", "item": f"{run_id}/{arm}", "kind": "fill", "run_id": run_id,
                      "arm": arm, "agents": [aid]})
    return units


def project(units, max_sessions, cap_min, now, last_start, hard):
    """Event simulation of the scheduler (groups first, fills fill), every session lasting its full cap."""
    t, running, rows, pending = now, [], [], list(units)
    while pending and t < last_start:
        running = [r for r in running if r["stop"] > t]
        busy = sum(r["n"] for r in running)
        for u in [u for u in pending if u["kind"] == "group"] + [u for u in pending if u["kind"] != "group"]:
            n = len(u["agents"])
            if busy + n > max_sessions:
                if u["kind"] == "group":
                    continue
                break
            stop = min(t + dt.timedelta(minutes=cap_min), hard)
            rows.append({"key": u["key"], "n": n, "start": t, "stop": stop})
            running.append({"n": n, "stop": stop})
            pending.remove(u)
            busy += n
        if not pending:
            break
        nxt = min((r["stop"] for r in running), default=t + dt.timedelta(minutes=1))
        t = max(nxt, t + dt.timedelta(seconds=30))
    finish = max((r["stop"] for r in rows), default=now)
    return {"rows": rows, "not_started": [u["key"] for u in pending], "finish": finish}


def archive_aborted(root, tag="aborted_0052"):
    """Rename the aborted run's folders (the evaluator guard keeps people from naming them; the launcher may)."""
    done = []
    for name in ("run", "kb", "boards", "submissions", "transcripts", "agents", "sealed", "public", "control",
                 "metrics"):
        src = Path(root) / name
        if src.exists():
            dst = Path(root) / f"{name}_{tag}"
            k = 2
            while dst.exists():
                dst = Path(root) / f"{name}_{tag}_{k}"
                k += 1
            src.rename(dst)
            done.append({"from": name, "to": dst.name})
    return done


def spawn_detached(args, log, env=None):
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    out = open(log, "a", encoding="utf-8")
    return subprocess.Popen([sys.executable, *args], stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True, cwd=str(HERE), env=env)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true", help="fake agents (smoke test)")
    ap.add_argument("--mock-tools", action="store_true", help="mock gateway, precheck, compute, PreForm (smoke)")
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--batches", type=int)
    ap.add_argument("--wall-cap-min", type=float, help="per-session wall cap override (smoke)")
    ap.add_argument("--min-free-ram", type=float, help="admission override (smoke tests only)")
    ap.add_argument("--archive-aborted", action="store_true",
                    help="rename the aborted 00:52 run's folders (run, kb, boards, submissions, ...) to *_aborted_0052")
    ap.add_argument("--skip-health", action="store_true")
    ap.add_argument("--no-scheduler", action="store_true")
    ap.add_argument("--allow-missing-eval", action="store_true")
    a = ap.parse_args()

    cfg = load_config()
    if a.mock_tools:
        os.environ["BT_MOCK_TOOLS"] = "1"  # health check and tools use the mocks too
    root = Path(a.root).resolve()
    hard = clock_next(cfg["hard_deadline"])
    last_start = clock_next(cfg["last_start"])
    if last_start > hard:
        last_start -= dt.timedelta(days=1)
    cap_min = a.wall_cap_min or cfg["wall_cap_min"]
    if a.min_free_ram is not None:
        cfg["admission"]["min_free_ram_gb"] = a.min_free_ram
        cfg["admission"]["session_ram_gb"] = 0.01
    deadline = hard  # genome stop_at = the hard deadline; each runner gets its own wall-cap stop at start
    notices = [{"rule": "per session, cap-60 and cap-15 minutes"}]
    targets, tsource = load_targets(cfg)
    info = gw.resolve(cfg, force_mock=a.mock_tools)
    batches = build_schedule(cfg)[: a.batches or None]
    reps = sorted({b["rep"] for b in batches})
    draws = {r: draw_genomes(cfg, r) for r in reps}
    model = "mock" if a.mock else (cfg.get("force_model") or "claude")
    public_dir = root / "public"
    dfiles, _ = data_files(cfg, public_dir, write=False)
    judging, have_eval = judging_summary(cfg)
    cfg["_tool_status"] = tool_status(cfg, a.mock_tools)
    items = []
    for b in batches:
        for arm in b["arms"]:
            items.append({"run_id": b["run_id"], "arm": arm, "batch": b["batch"], "target": b["target"],
                          "rep": b["rep"], "agents": [g["id"] for g in draws[b["rep"]][arm]]})
    body = briefs.common_body(cfg, public_dir, dfiles, judging, "")
    texts, genomes = {}, {}
    for it in items:
        for g in draws[it["rep"]][it["arm"]]:
            ng = briefs.finish_genome(g, root, it["run_id"], it["arm"], it["target"], public_dir, model,
                                      info.get("dim", 3), deadline, it["agents"], cfg)
            ng["model_override"] = "deliberate (force_model in config.json), not a fallback"
            k = f"{it['run_id']}/{it['arm']}/{g['id']}"
            texts[k], genomes[k] = briefs.render(ng, body, cfg), ng
    ok, common, full = briefs.check_identical(texts)
    agents_all = list(genomes.values())
    est = estimate(agents_all, cfg)
    total_q = sum(g["quota"] for g in agents_all)

    units = build_units(items, draws)
    ad_cfg = cfg["admission"]
    from common import CpuMeter, free_ram_gb
    ram_now, cpu_now = free_ram_gb(), CpuMeter(60).sample()
    fit_now = max(0, int((ram_now - ad_cfg["min_free_ram_gb"]) / ad_cfg["session_ram_gb"]) + 1) \
        if ram_now >= ad_cfg["min_free_ram_gb"] else 0
    group_need = ad_cfg["min_free_ram_gb"] + ad_cfg.get("group_extra_session_ram_gb", ad_cfg["session_ram_gb"]) * 5
    proj = project(units, ad_cfg["max_sessions"], cap_min, dt.datetime.now().astimezone(), last_start, hard)
    print(f"Bone-twin OPEN run. now {dt.datetime.now():%a %H:%M}; wall cap {cap_min:g} min per session; last start "
          f"{last_start:%a %H:%M}; hard deadline {hard:%a %H:%M}")
    print(f"machine now: free RAM {ram_now:.1f} GB, CPU {cpu_now:.0f}% -> RAM admits about {fit_now} session(s) now "
          f"(rule: >= {ad_cfg['min_free_ram_gb']} GB free + {ad_cfg['session_ram_gb']} GB per extra session; "
          f"max {ad_cfg['max_sessions']}; CPU < {ad_cfg['max_cpu_pct']}%); a group of 6 needs {group_need:.2f} GB free "
          f"({'OK now' if ram_now >= group_need else 'NOT now'})")
    print(f'goal (verbatim, every brief): "{cfg["goal"]}"')
    print(f"root {root}; agents {model} ({cfg['claude_model']}); seed {cfg['seed']}; admission: max "
          f"{ad_cfg['max_sessions']} sessions, groups of 6 for collective/planner, fills one by one; every child "
          f"hidden at below-normal priority; heavy local tools: {cfg.get('heavy_slots', 2)} FIFO slots")
    print(f"deliverables: {', '.join(cfg['deliverables']['files'])} + implant.stl|3mf ({cfg['deliverables']['axes']})")
    print(f"EVAL_SPEC.md: {'present' if have_eval else 'NOT PRESENT YET'}; judging paragraph: {judging[:120]}")
    print(f"gateway (optional sim tools): {info['mode']} at {info['dir']}")
    print("tools: " + "; ".join(f"{k} {v}" for k, v in cfg["_tool_status"].items()))
    print(f"data: {len(dfiles)} files from {', '.join(cfg['published_data']['dirs'])} ({cfg['published_data']['label']})")
    print(f"targets (visible cases only): {', '.join(t['name'] for t in targets)}")
    print("live leader intervention: ON, separate hidden job (collective r2 only, at its group start + 60 min; "
          "LIVE_INTERVENTION_RULE.md); rerun-style interventions: OFF")
    print(f"\nProjected schedule if RAM/CPU admit max {ad_cfg['max_sessions']} sessions (each runs its full cap):")
    for r_ in proj["rows"]:
        print(f"  {r_['start']:%H:%M}-{r_['stop']:%H:%M}  {r_['key']} ({r_['n']})")
    for k in proj["not_started"]:
        print(f"  NOT STARTED before {last_start:%H:%M} (no submission): {k}")
    print(f"  projected finish {proj['finish']:%a %H:%M} (hard deadline {hard:%H:%M}); control built at launch")
    if fit_now < ad_cfg["max_sessions"]:
        p2 = project(units, max(fit_now, 1), cap_min, dt.datetime.now().astimezone(), last_start, hard)
        print(f"  at today's free RAM (admits ~{fit_now}): projected finish {p2['finish']:%a %H:%M}; not started by "
              f"{last_start:%H:%M}: {p2['not_started'] or 'none'}")
    for r in reps:
        print(f"\nLeanings, replicate {r} (shared by best_of_n b*, collective c*, planner p*; single = generalist):")
        for g in draws[r]["collective"]:
            ln = g["leanings"]
            print(f"  g{g['id'][1:]}: knowledge {ln['knowledge']}; tools {ln['tools']}; communication "
                  f"{ln['communication']}; style {ln['working_style']}")
    print(f"\nBudget: {len(agents_all)} sessions; per run {cfg['budget']['run_credits']:,} credits (single "
          f"{cfg['budget']['single_quota']:,}; six x {cfg['budget']['agent_quota']:,}) + ${cfg['budget']['compute_usd_per_run']:.0f} "
          f"Brev per run; total {total_q:,} credits, hard cap {cfg['total_credit_cap']:,} "
          f"({'OK' if total_q <= cfg['total_credit_cap'] else 'EXCEEDED'}); API overflow cap "
          f"${cfg['overflow_api']['spend_cap_usd']:.0f}")
    for label, e in est.items():
        print(f"Est. tokens ({label}): {e['tokens'] / 1e6:,.0f} M raw ({e['cache_read'] / 1e6:,.0f} M cache reads, "
              f"{e['output'] / 1e6:,.1f} M output), ~{e['turns']:,} turns, ~${e['usd']:,.0f} at list price")
    print(f"Brief check: {len(texts)} briefs identical apart from per-agent blocks: {'OK' if ok else 'FAILED'}; "
          f"common sha256 {common}")
    if not ok:
        raise SystemExit("brief bodies differ; refusing")
    if total_q > cfg["total_credit_cap"]:
        raise SystemExit("planned quotas exceed total_credit_cap; refusing")
    if a.dry_run:
        print("\nDry run: nothing written, nothing launched.")
        return
    if not have_eval and not a.allow_missing_eval:
        raise SystemExit("EVAL_SPEC.md is not published yet; refusing to launch (or pass --allow-missing-eval)")

    archived = archive_aborted(root) if a.archive_aborted else []
    if run_dir(root).exists() and any(run_dir(root).iterdir()):
        raise SystemExit(f"{run_dir(root)} already exists; use a fresh --root or move the old run away")
    run_dir(root).mkdir(parents=True, exist_ok=True)
    sealed_dir(root).mkdir(parents=True, exist_ok=True)
    touch(root, f"launcher pid {os.getpid()} start (mock={a.mock}, mock_tools={a.mock_tools})")
    gw.ensure_key(info)
    pre = run_dir(root) / "preflight"
    pre.mkdir(exist_ok=True)
    try:
        used_dim, prerec = gw.preflight(info, pre, cfg["control"]["target"])
        info["dim"] = used_dim
    except SystemExit as exc:  # the sim tools are optional in the open run: record, do not block
        prerec = {"error": str(exc)}
    gw.freeze(root, info)
    public_dir.mkdir(parents=True, exist_ok=True)
    gw.public_copy(info, public_dir)
    (public_dir / "targets").mkdir(exist_ok=True)
    for t in targets:
        write_json(public_dir / "targets" / f"{t['name']}.json", public_target(t, cfg))
    spec = bt_path(cfg["judge"]["eval_spec"])
    (public_dir / "EVAL_SPEC_v1.md").write_text(spec.read_text(encoding="utf-8") if spec.exists() else
                                                "EVAL_SPEC_v1.md was not published at launch.\n", encoding="utf-8")
    for add in sorted(spec.parent.glob(cfg["judge"].get("eval_addenda_glob", "EVAL_SPEC_v1_addendum*.md"))):
        shutil.copyfile(add, public_dir / add.name)
    imgs = bt_path(cfg["compute"]["images"])
    if imgs.exists():
        shutil.copyfile(imgs, public_dir / "compute_images.md")
    write_json(public_dir / "notices.json", [])  # per-session notices are written by the scheduler
    _, dhash = data_files(cfg, public_dir, write=True)
    n_hashed = harness_hashes(run_dir(root) / "harness_sha256.txt")
    for it in items:
        ad = arm_dir(root, it["run_id"], it["arm"])
        (ad / "agents").mkdir(parents=True, exist_ok=True)
        board_path(root, it["run_id"], it["arm"]).touch()
        ags = [genomes[f"{it['run_id']}/{it['arm']}/{aid}"] for aid in it["agents"]]
        write_json(ad / "arm.json", {"arm": it["arm"], "run_id": it["run_id"], "target": it["target"],
                                     "rep": it["rep"], "batch": it["batch"], "board_shared": ags[0]["board_shared"],
                                     "agents": ags})
        for ng in ags:
            briefs.write_agent(ng, texts[f"{it['run_id']}/{it['arm']}/{ng['id']}"])
    touch(root, f"wrote {len(texts)} agent folders")
    rules = rules_manifest(root)
    pf = "skipped (mock tools)" if a.mock_tools else ensure_preform(cfg)
    touch(root, f"PreFormServer: {pf}")
    hres = None
    if not a.skip_health:
        import health
        first = next(iter(genomes.values()))
        hres = health.check(root, Path(first["dir"]) / "genome.json", skip_claude=a.mock)
        print(f"health: {'OK' if hres['ok'] else 'FAILED ' + str(hres['failed'])}")
        touch(root, f"health {'ok' if hres['ok'] else 'FAILED'}")
        if not hres["ok"]:
            raise SystemExit("health check failed; nothing spawned (see the run's health.json)")
    if a.mock_tools:
        cb = subprocess.run([sys.executable, str(HERE / "sim_mock" / "control_build_mock.py"), "--root", str(root)],
                            capture_output=True, text=True)
    else:
        cb = subprocess.run([sys.executable, str(HERE / "control_build.py"), "--root", str(root)],
                            capture_output=True, text=True, timeout=1800)
    touch(root, f"control build exit {cb.returncode}")
    sched = {"created_utc": utc_now(), "units": units, "admission": cfg["admission"], "wall_cap_min": cap_min,
             "last_start": last_start.isoformat(), "hard_deadline": hard.isoformat(),
             "public_dir": str(public_dir), "brief_common_sha256": common,
             "kb_snapshot_minutes": cfg.get("kb_snapshot_minutes", 10)}
    write_json(run_dir(root) / "schedule.json", sched)
    plan = {"created_utc": utc_now(), "root": str(root), "goal": cfg["goal"], "seed": cfg["seed"], "model": model,
            "claude_model": cfg["claude_model"], "deadline": deadline.isoformat(), "notices": notices,
            "gateway": info, "preflight_record": prerec, "targets": [t["name"] for t in targets],
            "published_data": {"n_files": len(dhash), "sha256_of_list": hashlib.sha256(
                json.dumps(dhash, sort_keys=True).encode()).hexdigest()},
            "batches": batches, "interventions": cfg["interventions"].get("enabled", False),
            "tools_at_launch": cfg["_tool_status"], "preform_server": pf, "eval_spec_present": have_eval,
            "brief_check": {"ok": ok, "common_sha256": common, "per_brief_sha256": full},
            "rules_manifest": rules, "harness_files_hashed": n_hashed, "token_estimate": est,
            "total_quota": total_q, "health": hres and hres.get("ok")}
    if not a.no_scheduler:
        logs = run_dir(root) / "logs"
        logs.mkdir(exist_ok=True)
        plan["scheduler_pid"] = spawn_hidden([sys.executable, str(HERE / "scheduler.py"), "--root", str(root)],
                                             logs / "scheduler.out", HERE).pid
        if cfg.get("live_intervention", {}).get("enabled", True):
            plan["live_intervention_pid"] = spawn_hidden(
                [sys.executable, str(HERE / "live_intervention.py"), "--root", str(root)],
                logs / "live_intervention.out", HERE).pid
    touch(root, "launcher spawned the scheduler and exits" if not a.no_scheduler else "launcher exits (no scheduler)")
    plan["launcher_pid"] = os.getpid()
    plan["launcher_exit_local"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(run_dir(root) / "run_manifest.json", plan)
    mdir = root / cfg.get("metrics_dir", "metrics")
    mdir.mkdir(parents=True, exist_ok=True)
    write_json(mdir / "launch.json", {"utc": utc_now(), "last_start": last_start.isoformat(),
                                      "hard_deadline": hard.isoformat(), "wall_cap_min": cap_min,
                                      "archived": archived, "projected_finish": proj["finish"].isoformat(),
                                      "sessions": len(texts),
                                      "total_quota": total_q, "tools": cfg["_tool_status"], "health": plan["health"],
                                      "preform_server": pf, "eval_spec_present": have_eval})
    print(f"\n{n_hashed} files hashed; control build exit {cb.returncode}; scheduler "
          f"{'spawned' if not a.no_scheduler else 'not spawned'}. Launcher exits now.")


if __name__ == "__main__":
    main()
