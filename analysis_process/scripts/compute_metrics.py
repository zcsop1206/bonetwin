"""Process metrics for the finished bone-twin open run. Read-only on the experiment; writes only to analysis_process/.

Run with -B (no bytecode) so importing the harness modules leaves no __pycache__ change in harness_open.
Reuses harness code: centralization.analyse (graph, directives, needs), directives.RULE, process_metrics.kb_stats,
billing.list_price, compute/ledger_costs.py (as a subprocess, cost fields only). manipulation.py is NOT re-executed
because its check_arm writes into run/ and metrics/; the scheduler already ran it at 11:27:15Z, results are read.
"""
import datetime as dt
import os
import json
import math
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
B = Path(os.environ.get("BONETWIN_ROOT") or Path(__file__).resolve().parents[2])
H = B / "harness_open"
RUN = H / "run"
MET = H / "metrics"
OUT = B / "analysis_process"
(OUT / "data").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(H))
import billing  # noqa: E402
import centralization  # noqa: E402
import directives  # noqa: E402
import process_metrics  # noqa: E402

RUNS = ("r1", "r2")
ARMS = ("single", "best_of_n", "collective", "planner")
BOARD_ARMS = ("collective", "planner")
NOTICE_1 = "2026-11-01T09:46:41+00:00"
CFG = json.loads((H / "config.json").read_text(encoding="utf-8"))
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NV = {"warp_code": r"import warp|warp-lang|\bwp\.(kernel|launch|init|array|zeros)\b",
      "warp_word": r"\bwarp\b",
      "warp_fem": r"warp\.fem|wp\.fem|warp import fem",
      "physicsnemo": r"physics_?nemo",
      "bionemo": r"bionemo",
      "alchemi": r"alchemi",
      "ngc": r"nvcr\.io|\bngc\b",
      "compute_images_md": r"compute_images"}
KNOWLEDGE_MAP = {"bone biology": "literature", "solid mechanics / FEA": "NVIDIA simulation",
                 "materials chemistry": "literature", "additive manufacturing": "PreForm API",
                 "ML / surrogates": "NVIDIA simulation", "clinical / regulatory": "literature"}


def rj(p):
    out = []
    p = Path(p)
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out


def lj(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8-sig"))


def t(s):
    return dt.datetime.fromisoformat(s)


def local(s):
    """UTC ISO -> local clock. 2026-11-01 02:00 EDT = 06:00Z, so before 06:00Z is EDT (-4), after is EST (-5)."""
    d = t(s).astimezone(dt.timezone.utc)
    off, z = (4, "EDT") if d < dt.datetime(2026, 11, 1, 6, tzinfo=dt.timezone.utc) else (5, "EST")
    return (d - dt.timedelta(hours=off)).strftime("%H:%M:%S ") + z


def norm_path(p):
    return UUID.sub("{id}", str(p).split("?")[0])


def entropy(c):
    n = sum(c.values())
    return -sum(v / n * math.log2(v / n) for v in c.values() if v) if n else 0.0


def agent_metrics(run, arm, g):
    aid = g["id"]
    d = RUN / run / arm / "agents" / aid
    st = lj(d / "status.json", {})
    ses = rj(d / "sessions.jsonl")
    starts = [s for s in ses if s.get("event") == "start"]
    runners = list(dict.fromkeys(s.get("runner_pid") for s in ses))
    tok = st.get("tokens") or {}
    w = g["credit_weights"]
    tc_ = sum(w.get(k, 1.0) * tok.get(k, 0) for k in ("input", "cache_creation", "cache_read", "output")) - tok.get("exempt", 0)
    tools_led = rj(d / "meter_tools.jsonl")
    tool_cr = sum(r.get("price", 0) for r in tools_led)
    state = st.get("state")
    end_state = {"capped": "capped", "done": "finished", "safety_cap": "window"}.get(state, state)
    first = starts[0]["ts"] if starts else None
    wall = (t(st["ts"]) - t(first)).total_seconds() / 60 if first and st.get("ts") else None
    # billing rows, per message, first occurrence
    bill = {"subscription": {"turns": 0, "usd": 0.0}, "api": {"turns": 0, "usd": 0.0}}
    seen, switches, msg_ts = set(), [], {}
    for r in rj(d / "billing.jsonl"):
        if r.get("event") == "billing_switch":
            switches.append({"utc": r["ts"], "to": r["billing"], "why": r.get("why")})
            continue
        m = r.get("msg")
        if m in seen or r.get("model") == "<synthetic>":
            continue
        seen.add(m)
        msg_ts[m] = r["ts"]
        bill[r["billing"]]["turns"] += 1
        bill[r["billing"]]["usd"] += r.get("usd_list_price_est", 0)
    prereset = [r for r in rj(d / "billing.jsonl") if r.get("billing") == "subscription" and r.get("msg") and r.get("model") != "<synthetic>"
                and t(r["ts"]) < t("2026-11-01T09:40:00+00:00") and t(r["ts"]) > t("2026-11-01T08:34:00+00:00")]
    # usage per message from the transcript (last row of each message id) + tool use text scan
    usage, nv_tool, nv_text = {}, Counter(), Counter()
    tool_inputs = []
    for m in rj(d / "agent_log.jsonl"):
        if m.get("type") != "assistant":
            continue
        msg = m.get("message") or {}
        if msg.get("id") and msg.get("usage"):
            usage[msg["id"]] = msg["usage"]
        for b in msg.get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                s = json.dumps(b.get("input") or {}, ensure_ascii=False)
                tool_inputs.append(s)
                for k, rx in NV.items():
                    if re.search(rx, s, re.I):
                        nv_tool[k] += 1
            elif b.get("type") == "text":
                for k, rx in NV.items():
                    if re.search(rx, b.get("text") or "", re.I):
                        nv_text[k] += 1
    # disk scan of the agent's own text files
    disk = Counter()
    skip = {"agent_log.jsonl", "tool_calls.jsonl", "BRIEF.md", "billing.jsonl", "genome.json", "meter_tools.jsonl", "sessions.jsonl",
            "models.jsonl", "claude_settings.json", "notices_due.json", "seen_notices.json", "status.json", "meter_tokens.json"}
    for f in d.rglob("*"):
        if f.is_file() and f.name not in skip and f.suffix.lower() in {".py", ".sh", ".md", ".txt", ".log", ".ps1"} and f.stat().st_size < 2_000_000:
            txt = f.read_text(encoding="utf-8", errors="ignore")
            for k, rx in NV.items():
                if re.search(rx, txt, re.I):
                    disk[k] += 1
    rows = rj(d / "tool_calls.jsonl")
    hook = [r for r in rows if r.get("verdict") is not None]
    prox = [r for r in rows if r.get("verdict") is None]
    claude_level = Counter(r["tool"] for r in hook if r["verdict"] == "allowed")
    refused = sum(1 for r in hook if r["verdict"] == "refused")
    held = sum(1 for r in hook if r["verdict"] == "held_for_notice")
    proxied = defaultdict(Counter)
    for r in prox:
        proxied[r["tool"]][str(r.get("result"))] += 1
    harness_view = Counter((r.get("priced_as") or r.get("tool") or "?") for r in rows
                           if r.get("verdict") not in ("refused", "held_for_notice") and r.get("result") != "unavailable")
    fam_of = {x: fam for fam, tools in CFG["affinity_tool_map"].items() for x in tools}
    fams = Counter(fam_of.get(n, "other") for n in harness_view.elements())
    pf = [r for r in prox if r["tool"] == "preform_api"]
    ep_all, ep_ok = Counter(), Counter()
    for r in pf:
        p = norm_path(r.get("path"))
        ep_all[p] += 1
        if r.get("result") == "ok":
            ep_ok[p] += 1
    warp = proxied.get("warp_gpu", Counter())
    brev_warp = [r for r in prox if r["tool"] == "compute" and "warp" in json.dumps(r.get("args")).lower()
                 or (r["tool"] == "compute" and any(x in json.dumps(r.get("args")) for x in ("validate.py", "validate2.py", "hmap.py", "sweep2.py", "nusweep.py", "final_score.py")))]
    brev_warp_ok = sum(1 for r in brev_warp if r.get("result") == "ok" and r["args"][0] == "exec")
    if warp.get("ok") or brev_warp_ok:
        wstatus = "ran"
    elif warp or nv_tool.get("warp_code"):
        wstatus = "attempted, did not run"
    elif nv_tool.get("warp_word") or nv_text.get("warp_word"):
        wstatus = "mention only"
    else:
        wstatus = "none"
    brev_starts = [r for r in prox if r["tool"] == "compute" and (r.get("args") or [""])[0] == "start" and "--help" not in r["args"] and "-h" not in r["args"]]
    syn = [r["ts"] for r in rj(d / "models.jsonl") if r.get("model") == "<synthetic>"]
    transfers_rows = []
    return {
        "run": run, "arm": arm, "agent": aid, "role": g.get("role"), "leanings": g.get("leanings"), "quota": g["quota"],
        "state_raw": state, "end_state": end_state, "first_start_utc": first, "end_utc": st.get("ts"), "end_local": local(st["ts"]) if st.get("ts") else None,
        "start_local": local(first) if first else None, "wall_min": round(wall, 1) if wall is not None else None,
        "model_process_starts": len(starts), "runner_pids": runners, "duplicate_runner_starts": sum(1 for s in starts if s.get("runner_pid") != runners[0]),
        "session_ids": sorted({s["session_id"] for s in ses if s.get("session_id")}), "has_final_json": (d / "final.json").exists(),
        "tokens": tok, "token_credits": round(tc_), "tool_credits": round(tool_cr), "credits_used": round(tc_ + tool_cr),
        "balance_status": st.get("balance"),
        "cache_read_credit_share": round(w.get("cache_read", 0.1) * tok.get("cache_read", 0) / (tc_ + tok.get("exempt", 0) + tool_cr), 3) if tc_ else None,
        "list_usd_from_tokens": round(billing.list_price(CFG, {"input_tokens": tok.get("input", 0), "cache_creation_input_tokens": tok.get("cache_creation", 0),
                                                               "cache_read_input_tokens": tok.get("cache_read", 0), "output_tokens": tok.get("output", 0)}), 3),
        "billing": {k: {"turns": v["turns"], "usd": round(v["usd"], 3)} for k, v in bill.items()}, "billing_switches": switches,
        "subscription_label_before_0440_reset": {"turns": len(prereset), "usd": round(sum(r.get("usd_list_price_est", 0) for r in prereset), 3)},
        "tool_calls": {"allowed_claude_level": dict(claude_level), "refused": refused, "held_for_notice": held,
                       "proxied_by_result": {k: dict(v) for k, v in proxied.items()},
                       "harness_view": dict(harness_view), "families": dict(fams), "entropy_bits": round(entropy(harness_view), 3),
                       "n_harness_view": sum(harness_view.values())},
        "preform": {"calls": len(pf), "ok": sum(1 for r in pf if r.get("result") == "ok"), "error": sum(1 for r in pf if r.get("result") == "error"),
                    "distinct_attempted": len(ep_all), "distinct_ok": len(ep_ok), "ok_endpoints": dict(ep_ok), "attempted_endpoints": dict(ep_all)},
        "nvidia": {"warp_status": wstatus, "warp_gpu_tool": dict(warp), "brev_exec_warp_ok": brev_warp_ok, "warp_fem_hits": nv_tool.get("warp_fem", 0) + disk.get("warp_fem", 0),
                   "physicsnemo_hits": nv_tool.get("physicsnemo", 0) + nv_text.get("physicsnemo", 0) + disk.get("physicsnemo", 0),
                   "bionemo_hits": nv_tool.get("bionemo", 0) + nv_text.get("bionemo", 0) + disk.get("bionemo", 0),
                   "alchemi_hits": nv_tool.get("alchemi", 0) + nv_text.get("alchemi", 0) + disk.get("alchemi", 0),
                   "ngc_hits": nv_tool.get("ngc", 0) + nv_text.get("ngc", 0) + disk.get("ngc", 0),
                   "compute_images_md_refs": nv_tool.get("compute_images_md", 0),
                   "tool_input_keyword_counts": dict(nv_tool), "assistant_text_keyword_counts": dict(nv_text), "own_file_keyword_counts": dict(disk)},
        "brev_starts_from_tool_log": [{"utc": r["ts"], "result": r.get("result")} for r in brev_starts],
        "synthetic_model_rows_utc": syn,
        "_usage": usage, "_msg_ts": msg_ts, "_tool_inputs": tool_inputs, "_tools_led": tools_led,
    }


def curve(a):
    """Credits-used curve: per-message token credits at the billing-row time + tool charges, scaled so the token part
    ends at the runner's own total (status.json). The scale is reported per agent."""
    w = {"input_tokens": 1.0, "cache_creation_input_tokens": 1.0, "cache_read_input_tokens": 0.1, "output_tokens": 1.0}
    ev = []
    recon = 0.0
    overhead = None
    use_exempt = a["tokens"].get("exempt", 0) > 0
    for mid, ts in a["_msg_ts"].items():
        u = a["_usage"].get(mid)
        if not u:
            continue
        v = sum(w[k] * u.get(k, 0) for k in w)
        if use_exempt:  # same first-turn overhead rule as agent_runner.on_assistant
            inp, cc, cr = u.get("input_tokens", 0), u.get("cache_creation_input_tokens", 0), u.get("cache_read_input_tokens", 0)
            if overhead is None:
                overhead = inp + cc + cr
                v -= cc + inp
            v -= 0.1 * min(cr, overhead)
        recon += v
        ev.append((ts, v, 0.0))
    scale = a["token_credits"] / recon if recon else 0.0
    ev += [(r["ts"], 0.0, r.get("price", 0)) for r in a["_tools_led"]]
    ev.sort(key=lambda x: t(x[0]))
    pts, cum = [], 0.0
    for ts, v, p in ev:
        cum += v * scale + p
        pts.append([ts, round(cum)])
    return pts, round(scale, 4)


def board_metrics(run, arm, nodes):
    posts = rj(RUN / run / arm / "board.jsonl")
    res = centralization.analyse(posts, nodes, 2.0, [])
    agent_posts = [p for p in posts if p["author"] in nodes]
    kinds = Counter(p["kind"] for p in posts)
    per = defaultdict(Counter)
    for p in posts:
        per[p["author"]][p["kind"]] += 1
    # reply-only and plain-id graph variants (supplementary)
    author = {p["id"]: p["author"] for p in posts}

    def freeman(edges):
        adj = {n: set() for n in nodes}
        for s, d in edges:
            if s != d and s in adj and d in adj:
                adj[s].add(d)
                adj[d].add(s)
        deg = [len(v) for v in adj.values()]
        n = len(nodes)
        return round(sum(max(deg) - x for x in deg) / ((n - 1) * (n - 2)), 4) if n >= 3 else None

    reply_edges = [(p["author"], author.get(q)) for p in agent_posts for q in p.get("parents", [])]
    idrx = re.compile(r"\b(" + "|".join(nodes) + r")\b")
    plain = []
    for p in agent_posts:
        for m in idrx.findall(p.get("text") or ""):
            if m != p["author"]:
                plain.append((p["author"], m))
    harness_edges = [(e["source"], e["target"]) for e in res["_edges"]]
    # board-post lineage proxy: parents + pNNNN mentions + typed links
    pars = {}
    for p in posts:
        ps = set(p.get("parents") or [])
        ps |= {m for m in re.findall(r"\b(p\d{4})\b", p.get("text") or "") if m != p["id"] and m in author}
        ps |= {lk.get("post") for lk in (p.get("meta") or {}).get("links") or [] if lk.get("post")}
        pars[p["id"]] = {q for q in ps if q in author and q < p["id"]}
    depth = {}
    for p in posts:
        depth[p["id"]] = 1 + max((depth[q] for q in pars[p["id"]]), default=-1)
    cross = sum(1 for k, v in pars.items() for q in v if author[q] != author[k])
    synth = [k for k, v in pars.items() if len({author[q] for q in v if author[q] != author[k]}) >= 2]
    # needs in detail
    needs = []
    by_ts = sorted(posts, key=lambda p: p["ts"])
    answered = {r for p in posts if p["kind"] == "claim" for r in (p.get("meta") or {}).get("pickup_of", [])}
    expired = {r for p in posts if p["kind"] == "expire" for r in p.get("parents", [])}
    for p in posts:
        if p["kind"] != "need":
            continue
        to = (p.get("meta") or {}).get("to")
        later = [q for q in by_ts if q["ts"] > p["ts"] and q["author"] != p["author"]
                 and (p["id"] in (q.get("parents") or []) or p["id"] in (q.get("text") or "")
                      or re.search(rf"->\s*{p['author']}\b|@{p['author']}\b", q.get("text") or ""))]
        needs.append({"id": p["id"], "author": p["author"], "to": to, "utc": p["ts"], "harness_answered": p["id"] in answered,
                      "harness_expired": p["id"] in expired, "first_later_post_addressing_author": later[0]["id"] if later else None,
                      "first_later_post_author": later[0]["author"] if later else None})
    transfers = [{"id": p["id"], "from": p["author"], "to": (p.get("meta") or {}).get("to"), "amount": (p.get("meta") or {}).get("amount"), "utc": p["ts"]}
                 for p in posts if p["kind"] == "transfer"]
    return {"res": {k: v for k, v in res.items() if not k.startswith("_")}, "edges": res["_edges"],
            "post_kinds": dict(kinds), "post_kinds_by_author": {k: dict(v) for k, v in per.items()},
            "degree_centralization_reply_only": freeman(reply_edges), "degree_centralization_with_plain_id_mentions": freeman(harness_edges + plain),
            "n_plain_id_mentions": len(plain),
            "directive_counts": dict(Counter(x["author"] for x in res["directive_posts"])),
            "typed_links": {k: res["edges_by_type"].get(k, 0) for k in ("cites", "contradicts", "extends", "replicates")},
            "needs_harness": res["needs"], "needs_detail": needs, "transfers": transfers,
            "board_lineage_proxy": {"max_chain_depth": max(depth.values(), default=0), "cross_agent_citation_edges": cross, "posts_citing_two_or_more_other_agents": len(synth)}}


def kb_cross(run, arm, agents):
    kb = RUN / run / arm / "kb"
    files = [f for f in kb.rglob("*") if f.is_file() and "__pycache__" not in f.parts] if kb.exists() else []
    keys = {}
    for f in files:
        rel = f.relative_to(kb).as_posix()
        key = rel if f.name.lower() in ("readme.md", "index.md", "notes.md", "report.md") or len(f.name) < 8 else f.name
        keys[rel] = key
    touch = defaultdict(set)
    for a in agents:
        blob = "\n".join(a["_tool_inputs"])
        blob = blob.replace("\\\\", "/")
        for rel, key in keys.items():
            if key in blob:
                touch[rel].add(a["agent"])
    multi = {k: sorted(v) for k, v in touch.items() if len(v) >= 2}
    return {"n_kb_files_excl_pycache": len(files), "n_named_by_2plus_agents": len(multi), "examples": dict(list(sorted(multi.items(), key=lambda x: -len(x[1])))[:8])}


def main():
    agents, curves = {}, {}
    arm_manifest = {}
    for run in RUNS:
        for arm in ARMS:
            m = lj(RUN / run / arm / "arm.json")
            arm_manifest[(run, arm)] = m
            for g in m["agents"]:
                a = agent_metrics(run, arm, g)
                agents[f"{run}/{arm}/{a['agent']}"] = a
    # leaning agreement
    fam_totals = Counter()
    for a in agents.values():
        fam_totals.update(a["tool_calls"]["families"])
    tot = sum(fam_totals.values())
    med_ent = statistics.median(a["tool_calls"]["entropy_bits"] for a in agents.values())

    def builder_share(a):
        v = a["tool_calls"]["harness_view"]
        n = a["tool_calls"]["n_harness_view"] or 1
        return sum(v.get(k, 0) for k in ("cad_python", "export_stl", "freecad", "preform_api", "Write", "Edit")) / n

    def verifier_share(a):
        n = a["tool_calls"]["n_harness_view"] or 1
        ok = a["preform"]["ok_endpoints"]
        return sum(c for p, c in ok.items() if "validate" in p or "body_count" in p) / n

    med_b, med_v = statistics.median(builder_share(a) for a in agents.values()), statistics.median(verifier_share(a) for a in agents.values())
    # board metrics first (communication axis needs them)
    boards = {}
    for run in RUNS:
        for arm in BOARD_ARMS:
            nodes = [g["id"] for g in arm_manifest[(run, arm)]["agents"]]
            boards[f"{run}/{arm}"] = board_metrics(run, arm, nodes)
    for key, a in agents.items():
        lean = a["leanings"] or {}
        fam = a["tool_calls"]["families"]
        n = a["tool_calls"]["n_harness_view"] or 1
        lt = lean.get("tools")
        res = {}
        if lt in CFG["affinity_tool_map"]:
            share = fam.get(lt, 0) / n
            base = fam_totals.get(lt, 0) / tot
            top = max((k for k in fam if k != "other"), key=lambda k: fam[k], default=None)
            res["tools"] = {"leaning": lt, "share": round(share, 3), "lift": round(share / base, 3) if base else None, "lift_gt_1": bool(base and share / base > 1),
                            "top_family": top, "top_family_match": top == lt}
        lk = lean.get("knowledge")
        if lk in KNOWLEDGE_MAP:
            f = KNOWLEDGE_MAP[lk]
            share = fam.get(f, 0) / n
            base = fam_totals.get(f, 0) / tot
            res["knowledge_proxy"] = {"leaning": lk, "mapped_family": f, "lift": round(share / base, 3) if base else None, "lift_gt_1": bool(base and share / base > 1)}
        ls = lean.get("working_style")
        if ls in ("explorer", "exploiter", "builder", "verifier"):
            e = a["tool_calls"]["entropy_bits"]
            ok = {"explorer": e >= med_ent, "exploiter": e < med_ent, "builder": builder_share(a) >= med_b, "verifier": verifier_share(a) >= med_v}.get(ls)
            res["working_style_proxy"] = {"leaning": ls, "agrees": bool(ok)}
        lc = lean.get("communication")
        if lc and a["arm"] in BOARD_ARMS:
            b = boards[f"{a['run']}/{a['arm']}"]["res"]
            posts = b["posts_by_agent"].get(a["agent"], 0)
            mean = b["n_posts"] / b["n_nodes"]
            bw = b["betweenness"].get(a["agent"], 0)
            mb = sum(b["betweenness"].values()) / b["n_nodes"]
            if lc == "broadcaster":
                res["communication_proxy"] = {"leaning": lc, "agrees": posts > mean}
            elif lc == "listener":
                res["communication_proxy"] = {"leaning": lc, "agrees": posts < mean}
            elif lc == "connector":
                res["communication_proxy"] = {"leaning": lc, "agrees": bw > mb}
            else:
                res["communication_proxy"] = {"leaning": lc, "agrees": None}
        a["leaning_vs_use"] = res

    def agree(rows, key, field):
        vals = [r["leaning_vs_use"][key][field] for r in rows if key in r["leaning_vs_use"] and r["leaning_vs_use"][key].get(field) is not None]
        return {"n": len(vals), "agree": sum(vals), "rate": round(sum(vals) / len(vals), 3) if vals else None}

    def agree_block(rows):
        return {"tools_top_family_match": agree(rows, "tools", "top_family_match"), "tools_lift_gt_1": agree(rows, "tools", "lift_gt_1"),
                "knowledge_proxy": agree(rows, "knowledge_proxy", "lift_gt_1"), "working_style_proxy": agree(rows, "working_style_proxy", "agrees"),
                "communication_proxy": agree(rows, "communication_proxy", "agrees")}

    # Brev: only ledger_costs.py
    out = subprocess.run([sys.executable, "-B", str(B / "compute" / "ledger_costs.py")], capture_output=True, text=True, check=True).stdout
    ledger = [json.loads(x) for x in out.splitlines() if x.strip()]
    led_by = {r.get("run"): r for r in ledger}
    harness_pm = lj(MET / "process_metrics.json", {})
    pm_mismatch = [k for k, a in agents.items() if harness_pm.get("agents", {}).get(k, {}).get("tools") != a["tool_calls"]["harness_view"]]
    submissions = {f"{r['run_id']}/{r['arm']}": r for r in lj(MET / "submissions.json")["rows"]}
    growth = rj(MET / "kb_growth.jsonl")
    # manipulation
    manip = {}
    for f in sorted(RUN.glob("*/*/manipulation_check.json")):
        d = lj(f)
        arm, rid = f.parent.parent.name, f.parent.name
        failed = {k: c["detail"] for k, c in d["checks"].items() if not k.startswith("_") and c.get("ok") is False}
        manip[f"{arm}/{rid}"] = {"claim": d["claim"], "falsifier": d["falsifier"], "pass": d["pass"], "checked_utc": d["checked_utc"],
                                 "failed": {k: (v if isinstance(v, str) else json.dumps(v))[:320] for k, v in failed.items()},
                                 "pass_excluding_no_human_posts": all(k == "all_arms.no_human_posts" for k in failed),
                                 "ok_true": [k for k, c in d["checks"].items() if not k.startswith("_") and c.get("ok") is True],
                                 "informational": [k for k, c in d["checks"].items() if not k.startswith("_") and c.get("ok") is None]}
    glob = lj(RUN / "manipulation_summary.json")["global"]
    # fs breach row check: the flagged paths are the agent's own folder cut by the meter's 600-char command limit
    breach = []
    for key, rx_own in (("r1/best_of_n/b4", "/run/r1/best"), ("r1/planner/p1", "/run/r1/planner")):
        r_, arm_, ag_ = key.split("/")
        for row in rj(RUN / r_ / arm_ / "agents" / ag_ / "tool_calls.jsonl"):
            c = (row.get("command") or "").replace("\\", "/").lower()
            if row.get("verdict") == "allowed" and rx_own in c:
                own = f"/run/{r_}/{arm_}/agents/{ag_}"
                rest = [c[m.start():] for m in re.finditer(r"/run/", c)]
                bad = [x for x in rest if not x.startswith(own) and not x.startswith(f"/run/{r_}/{arm_}/kb") and not x.startswith(f"/run/{r_}/{arm_}/deliverables")]
                if bad:
                    breach.append({"agent": key, "utc": row["ts"], "command_len": len(row.get("command") or ""), "flagged_tail": bad[0][:60]})
    # notice before/after
    notice = {}
    for k, a in agents.items():
        r_, arm_, ag_ = k.split("/")
        c = Counter()
        for row in rj(RUN / r_ / arm_ / "agents" / ag_ / "tool_calls.jsonl"):
            if row.get("tool") in ("preform_api", "warp_gpu", "compute"):
                c[(row["tool"], "after" if t(row["ts"]) >= t(NOTICE_1) else "before")] += 1
        notice[k] = {f"{x}_{y}": v for (x, y), v in c.items()}
    runs = {}
    for run in RUNS:
        for arm in ARMS:
            key = f"{run}/{arm}"
            rows = [a for k, a in agents.items() if k.startswith(key + "/")]
            for a in rows:
                pts, sc = curve(a)
                curves[f"{run}/{arm}/{a['agent']}"] = {"points": pts, "token_scale_to_status": sc, "quota": a["quota"], "end_state": a["end_state"], "end_utc": a["end_utc"], "start_utc": a["first_start_utc"]}
                a["credit_curve_token_scale"] = sc
            toks = Counter()
            for a in rows:
                toks.update({k: v for k, v in a["tokens"].items()})
            kbset = process_metrics.kbs_of(RUN / run / arm, arm_manifest[(run, arm)])
            kb_now = {w: process_metrics.kb_stats(p) for w, p in kbset.items()}
            ser = defaultdict(lambda: {"files": 0, "bytes": 0, "xrefs": 0})
            for g in growth:
                if g["run_id"] == run and g["arm"] == arm:
                    s = ser[g["ts"]]
                    s["files"] += g["n_files"]
                    s["bytes"] += g["bytes"]
                    s["xrefs"] += g["xrefs"]
            series = [{"utc": k, "local": local(k), **v} for k, v in sorted(ser.items())]
            pf_ok, pf_att = Counter(), Counter()
            for a in rows:
                pf_ok.update(a["preform"]["ok_endpoints"])
                pf_att.update(a["preform"]["attempted_endpoints"])
            bk = led_by.get(f"{'bestofn' if arm == 'best_of_n' else arm}-{run}", {"usd": 0, "instances": 0, "starts": 0, "types": []})
            tool_sum = Counter()
            prox_sum = Counter()
            for a in rows:
                tool_sum.update(a["tool_calls"]["allowed_claude_level"])
                for tn, rc in a["tool_calls"]["proxied_by_result"].items():
                    prox_sum[tn] += sum(rc.values())
            row = {"run": run, "arm": arm, "n_agents": len(rows), "model_process_starts": sum(a["model_process_starts"] for a in rows),
                   "duplicate_runner_starts": sum(a["duplicate_runner_starts"] for a in rows),
                   "wall_min_per_agent": {a["agent"]: a["wall_min"] for a in rows}, "wall_min_sum": round(sum(a["wall_min"] for a in rows), 1),
                   "quota_total": sum(a["quota"] for a in rows), "credits_used": sum(a["credits_used"] for a in rows),
                   "token_credits": sum(a["token_credits"] for a in rows), "tool_credits": sum(a["tool_credits"] for a in rows),
                   "tokens": dict(toks), "list_usd_from_tokens": round(sum(a["list_usd_from_tokens"] for a in rows), 2),
                   "billing": {s: {"turns": sum(a["billing"][s]["turns"] for a in rows), "usd": round(sum(a["billing"][s]["usd"] for a in rows), 2)} for s in ("subscription", "api")},
                   "end_states": dict(Counter(a["end_state"] for a in rows)), "end_state_by_agent": {a["agent"]: a["end_state"] for a in rows},
                   "cap_times_local": {a["agent"]: a["end_local"] for a in rows if a["end_state"] == "capped"},
                   "kb": {"final": {"n_files": sum(v["n_files"] for v in kb_now.values()), "bytes": sum(v["bytes"] for v in kb_now.values()), "xrefs": sum(v["xrefs"] for v in kb_now.values())},
                          "per_kb": kb_now, "series": series},
                   "tool_calls": {"allowed_claude_level": dict(tool_sum), "proxied": dict(prox_sum), "refused": sum(a["tool_calls"]["refused"] for a in rows),
                                  "held_for_notice": sum(a["tool_calls"]["held_for_notice"] for a in rows)},
                   "preform": {"calls": sum(pf_att.values()), "ok": sum(pf_ok.values()), "distinct_attempted": len(pf_att), "distinct_ok": len(pf_ok), "ok_endpoints": dict(pf_ok)},
                   "brev_ledger": {k: bk.get(k) for k in ("usd", "instances", "starts", "types")},
                   "nvidia": {a["agent"]: {"warp_status": a["nvidia"]["warp_status"], "warp_gpu_tool": a["nvidia"]["warp_gpu_tool"], "brev_exec_warp_ok": a["nvidia"]["brev_exec_warp_ok"]} for a in rows if a["nvidia"]["warp_status"] != "none"},
                   "nvidia_other_hits": {k: sum(a["nvidia"][k] for a in rows) for k in ("warp_fem_hits", "physicsnemo_hits", "bionemo_hits", "alchemi_hits", "ngc_hits", "compute_images_md_refs")},
                   "leanings_agreement": agree_block(rows), "submission": {k: submissions.get(key, {}).get(k) for k in ("submission", "missing", "picked", "why")},
                   "manipulation": manip.get(f"{arm}/{run}"), "notice_tool_calls_before_after_first_notice": {k: v for k, v in Counter(
                       sum((Counter(notice[f'{run}/{arm}/{a["agent"]}']) for a in rows), Counter())).items()}}
            if arm in BOARD_ARMS:
                b = boards[key]
                r = b["res"]
                row["board"] = {"n_agent_posts": r["n_posts"], "post_kinds": b["post_kinds"], "posts_by_agent": r["posts_by_agent"], "post_kinds_by_author": b["post_kinds_by_author"],
                                "degree_centralization": r["degree_centralization"], "degree_centralization_reply_only": b["degree_centralization_reply_only"],
                                "degree_centralization_with_plain_id_mentions": b["degree_centralization_with_plain_id_mentions"], "betweenness_max": r["betweenness_max"], "betweenness_argmax": r["betweenness_argmax"],
                                "top_agent_post_share": r["top_agent_post_share"], "top_poster": r["top_poster"], "directive_counts": b["directive_counts"], "n_directive_posts": r["n_directive_posts"],
                                "directive_share": r["directive_share"], "emergent_leader": r["emergent_leader"], "edges_by_type": r["edges_by_type"], "typed_links": b["typed_links"],
                                "needs_harness": b["needs_harness"], "needs_detail": b["needs_detail"], "transfers": b["transfers"], "harness_lineage": r["lineage"], "board_lineage_proxy": b["board_lineage_proxy"],
                                "kb_files_named_by_multiple_agents": kb_cross(run, arm, rows), "edges": b["edges"]}
            runs[key] = row
    ctrl = {"note": "deterministic program output, no agent sessions; process metrics are not applicable",
            "manipulation": manip.get("control/gibson_ashby_rigid10k"), "submission": submissions.get("control/control/gibson_ashby_rigid10k") or {k: v for k, v in submissions.items() if "control" in k},
            "brev_ledger": {"usd": 0, "starts": 0}}
    closed, live = billing.spend(H)
    spend_rows = rj(RUN / "api_spend.jsonl")
    per_agent_spend = defaultdict(list)
    for r in spend_rows:
        per_agent_spend[r["agent"]].append(round(r["usd"], 4))
    global_ = {
        "launch_local": "03:32:25 EST", "run_end_local": local("2026-11-01T11:27:15+00:00"),
        "brev_ledger_output": ledger,
        "api_ledger": {"closed_usd": round(closed, 2), "live_usd": round(live, 2), "total_usd": round(closed + live, 2), "cap_usd": CFG["overflow_api"]["spend_cap_usd"], "closed_rows_by_agent": dict(per_agent_spend),
                       "closed_note": "INFERENCE: for resumed sessions total_cost_usd looks cumulative (r2 s1 rows rise 1.79, 2.97, 3.72, 3.72, 4.45; r1 s1 4.69, 4.82), so summing closed rows overcounts single-arm API spend; api_live leftovers are estimates for sessions stopped at cap"},
        "per_turn_billing_sum": {s: {"turns": sum(a["billing"][s]["turns"] for a in agents.values()), "usd": round(sum(a["billing"][s]["usd"] for a in agents.values()), 2)} for s in ("subscription", "api")},
        "directive_rule": directives.RULE,
        "harness_process_metrics_tool_counts_mismatch_agents": pm_mismatch,
        "fs_breach_rows": breach, "manipulation_global": glob, "manipulation_checked_utc": lj(RUN / "manipulation_summary.json")["checked_utc"],
        "leanings_agreement_all": agree_block(list(agents.values())), "family_totals": dict(fam_totals),
        "interventions": {"first_notice_utc": NOTICE_1, "first_notice_local": local(NOTICE_1), "second_notice_local": local("2026-11-01T09:50:39+00:00"),
                          "final_status": {k: v for k, v in rj(MET / "interventions.jsonl")[-1].items() if k != "agents"}},
        "live_intervention": lj(MET / "live_intervention.json"), "memgov_log_exists": (MET / "memgov.jsonl").exists(),
        "incident_0350": {k: v for k, v in lj(MET / "incident_0350.json").items() if k in ("coordinator_counts", "cause", "n_agents_started", "affected_agents", "window_local")},
    }
    pub_agents = {k: {x: y for x, y in a.items() if not x.startswith("_")} for k, a in agents.items()}
    (OUT / "metrics.json").write_text(json.dumps({"generated_note": "deterministic; scripts/compute_metrics.py; read-only on harness_open", "global": global_, "control": ctrl, "runs": runs, "agents": pub_agents}, indent=1), encoding="utf-8")
    (OUT / "data" / "curves.json").write_text(json.dumps(curves), encoding="utf-8")
    print("ok", len(agents), "pm mismatch", pm_mismatch, "scales", [(k, c["token_scale_to_status"]) for k, c in curves.items() if abs(c["token_scale_to_status"] - 1) > 0.05])


if __name__ == "__main__":
    main()
