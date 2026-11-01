"""Manipulation checks: every arm carries proof of what it claims (enforcement + automated check + stated falsifier).

    python manipulation.py --root R

Writes run/<arm>/<run_id>/manipulation_check.json for every sealed arm run (and control/<target>), plus
run/manipulation_summary.json and run/manipulation_summary.md (one table row per arm run). Each check file holds
the arm's claim, the enforcement in place, the automated checks (each {ok, detail}), the falsifier, and the
all-arms checks. Informational metrics carry ok = null.
"""
import argparse
import hashlib
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import centralization  # noqa: E402
import gateway as gw  # noqa: E402
from common import HERE, base_arm, load_json, read_jsonl, run_dir, sealed_dir, utc_now, write_json  # noqa: E402

CLAIMS = {
    "control": ("no agent judgement: the control design is a deterministic program output",
                "control_design.py runs with no model keys or tokens in its environment, twice",
                "the two runs' design hashes differ, or any model transcript or session exists for the control"),
    "single": ("one mind with the full budget",
               "Task/Agent denied in claude settings and --disallowedTools; one runner; resumes reuse the session",
               "two model processes overlap in time, any Task/Agent tool use, more than one session id, or another "
               "arm's run id / design hash / agent folder appears in its transcript"),
    "best_of_n": ("independent agents, no communication",
                  "separate folders, no board; other agents' folders, gateway ledgers and board files blocked by "
                  "the meter; web allowed but every URL logged",
                  "another member's run id / design hash / folder / distinctive text appears in a member's "
                  "transcript, a URL written by one member is fetched by another, or members' designs are "
                  "near-identical without a shared public source"),
    "collective": ("peers, nobody imposed",
                   "byte-identical brief bodies (hashes logged); fixed selection rule (reviewed by another agent); "
                   "no lead, no vote",
                   "brief bodies differ, the arm design was not reviewed by another agent, or a leader was "
                   "imposed by the harness (an emergent leader is a finding, not a violation)"),
    "planner": ("CENTRALIZED CONTROL GROUP: a star communication graph by construction",
                "board.py routing: workers read only the lead's posts and their own; worker designs must cite "
                "the lead's assignment post; the lead picks the arm design",
                "degree centralization well below 1, or worker designs not traceable to an assignment"),
}
SCHOLARLY = ("doi.org", ".edu", ".ac.", "sciencedirect", "springer", "wiley", "nature.com", "ncbi.nlm.nih.gov",
             "pubmed", "arxiv.org", "researchgate", "semanticscholar", "scholar.google", "formlabs.com",
             "wikipedia.org", "iso.org", "astm.org", "mdpi.com", "frontiersin", "tandfonline", "sagepub",
             "iopscience", "acs.org", "rsc.org", "ieee.org", "matweb", "engineeringtoolbox", "plos.org",
             "biorxiv", "jstor", "osti.gov", "nist.gov", "asme.org", "elsevier", "cell.com", "science.org",
             "biomedcentral", "jbiomech", "oup.com", "cambridge.org", "acm.org", "nvidia.com", "github.com",
             "readthedocs", "python.org", "lean-lang.org", "freecad.org", "build123d", "trimesh")
URL = re.compile(r"https?://[^\s\"'<>)\\]+")
WRITE_HINT = re.compile(r"(curl[^|;&]*\s-(d|F|X\s*(POST|PUT))|--data|requests\.(post|put)|-Method\s+(Post|Put)|"
                        r"Invoke-RestMethod[^|;]*-Body)", re.I)


def ck(ok, detail):
    return {"ok": ok, "detail": detail}


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def arm_runs(root):
    for rd in sorted(p for p in run_dir(root).iterdir() if p.is_dir()):
        for ad in sorted(p for p in rd.iterdir() if p.is_dir() and (p / "arm.json").exists()):
            yield rd.name, ad.name, ad


def identifiers(ad):
    """run ids, design hashes and agent folders an arm produced (from its harness-written ledger)."""
    out = {}
    for r in read_jsonl(ad / "gateway_ledger.jsonl"):
        rec = r["record"]
        ids = out.setdefault(r["author"], set())
        ids.add(rec.get("run_id"))
        if rec.get("design_sha256"):
            ids.add(rec["design_sha256"])
    return out


def transcript(agent_dir):
    parts = []
    for name in ("agent_log.jsonl", "tool_calls.jsonl"):
        f = Path(agent_dir) / name
        if f.exists():
            parts.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def scan(text, foreign):
    """foreign: {label: set(strings)} -> hits."""
    hits = []
    for label, strings in foreign.items():
        for s in strings:
            if s and len(s) >= 8 and s in text:
                hits.append(f"{label}:{s[:24]}")
    return hits


def _t(s):
    """Parse an ISO timestamp (never compare timestamp strings)."""
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat(str(s)).timestamp()
    except (TypeError, ValueError):
        return float("-inf")


def breach_scan(root, run_id, arm, agents, members=()):
    """Post-run filesystem isolation scan (no per-agent OS accounts, so no ACL deny): every tool call the meter
    ALLOWED whose path or command touches another run/arm/agent folder, a sealed file or the gateway secrets."""
    own = {a: f"/run/{run_id}/{arm}/agents/{a}".lower() for a in agents}
    foreign = re.compile(r"/run/([^/\s\"']+)/([^/\s\"']+)(/agents/([^/\s\"']+))?")
    secrets = ("sealed_case", "sealed_private", ".gateway_key", "/sealed/", "voxel_queue")
    out = {}
    for a in agents:
        hits = []
        d = run_dir(root) / run_id / arm / "agents" / a
        for r in read_jsonl(d / "tool_calls.jsonl"):
            if r.get("verdict") == "refused":
                continue
            text = " ".join(str(r.get(k, "")) for k in ("file_path", "path", "command", "url", "pattern"))
            norm = text.replace("\\", "/").lower()
            ok_pref = [own[a], f"/run/{run_id}/{arm}/kb", f"/run/{run_id}/{arm}/deliverables"]
            if a in members:
                ok_pref = ok_pref[:2]
            for m in foreign.finditer(norm):
                if not any(norm[m.start():].startswith(x.lower()) for x in ok_pref):
                    hits.append(m.group(0)[:80])
            hits += [x for x in secrets if x in norm]
        if hits:
            out[a] = hits[:10]
    return out


def web_audit(agents_dirs):
    """URLs per agent with times; flags non-scholarly domains, writes, and cross-agent URL reuse after a write."""
    events = []
    for aid, d in agents_dirs.items():
        for r in read_jsonl(Path(d) / "tool_calls.jsonl"):
            urls = []
            if r.get("url"):
                urls.append(r["url"])
            if r.get("command"):
                urls += URL.findall(r["command"])
            for u in urls:
                events.append({"agent": aid, "ts": r.get("ts"), "url": u, "tool": r.get("tool"),
                               "write": bool(r.get("command") and WRITE_HINT.search(r["command"]))})
            if r.get("query"):
                events.append({"agent": aid, "ts": r.get("ts"), "query": r["query"], "tool": r.get("tool")})
    flags = []
    for e in events:
        if "url" in e:
            host = urlparse(e["url"]).netloc.lower()
            if not any(k in host for k in SCHOLARLY):
                flags.append({"type": "non_reference_domain", **e})
            if e["write"]:
                flags.append({"type": "write_to_url", **e})
    writes = [e for e in events if e.get("write")]
    for w in writes:
        key = urlparse(w["url"]).netloc + urlparse(w["url"]).path
        for e in events:
            if "url" in e and e["agent"] != w["agent"] and _t(e["ts"]) > _t(w["ts"]) and \
                    urlparse(e["url"]).netloc + urlparse(e["url"]).path == key:
                flags.append({"type": "fetched_after_other_agents_write", "writer": w["agent"], **e})
    by_url = {}
    for e in events:
        if "url" in e:
            by_url.setdefault(e["url"], set()).add(e["agent"])
    shared = {u: sorted(a) for u, a in by_url.items() if len(a) > 1}
    return {"n_events": len(events), "urls": sorted(by_url), "flags": flags, "shared_urls": shared}


def design_set(design):
    nodes = design.get("nodes") or []
    out = set()
    for s in design.get("struts") or []:
        try:
            a = tuple(round(c * 2) / 2 for c in nodes[int(s[0])])
            b = tuple(round(c * 2) / 2 for c in nodes[int(s[1])])
            out.add((min(a, b), max(a, b), round(float(s[2]), 1)))
        except (IndexError, TypeError, ValueError):
            pass
    return out


def similarity(ad, agents):
    designs = {}
    for aid in agents:
        f = load_json(ad / "agents" / aid / "final.json")
        if f and f.get("run_id") and (ad / "arm_designs" / f"{f['run_id']}.json").exists():
            designs[aid] = design_set(load_json(ad / "arm_designs" / f"{f['run_id']}.json"))
    out = {}
    for a, b in itertools.combinations(sorted(designs), 2):
        u = designs[a] | designs[b]
        out[f"{a}~{b}"] = round(len(designs[a] & designs[b]) / len(u), 3) if u else None
    return out


def common_checks(root, plan, run_id, arm, ad, manifest, sealed):
    info = gw.frozen(root)
    agents = manifest["agents"]
    out = {}
    out["same_model"] = ck(len({g["model"] for g in agents}) == 1 and agents[0]["model"] == plan.get("model"),
                           f"model {agents[0]['model']} ({plan.get('claude_model')}), plan {plan.get('model')}")
    keys = {tuple(sorted(g["tool_prices"])) for g in agents}
    out["same_tools"] = ck(len(keys) == 1, f"{len(next(iter(keys)))} priced tools for every agent; registry sha256 "
                                           f"{(plan.get('tools_registry_sha256') or '')[:12]}")
    pub = Path(agents[0]["public_dir"]) / "data"
    now = {f.relative_to(pub).as_posix(): sha_file(f) for f in sorted(pub.rglob("*")) if f.is_file()}         if pub.exists() else {}
    want = (plan.get("published_data") or {}).get("sha256_of_list")
    got = hashlib.sha256(json.dumps(now, sort_keys=True).encode()).hexdigest()
    out["same_data"] = ck(got == want, f"{len(now)} read-only data files, list hash {'matches' if got == want else 'DIFFERS'}")
    quota = sum(g["quota"] for g in agents)
    ex = {g["id"]: ((load_json(ad / "agents" / g["id"] / "status.json") or {}).get("tokens") or {}).get("exempt", 0)
          for g in agents}
    out["budget"] = ck(None, f"arm quota {quota:,}; Claude Code overhead exempted per agent (credits): {ex}")
    recs = read_jsonl(ad / "gateway_ledger.jsonl")
    bad = [r["record"].get("run_id") for r in recs if not gw.verify(info, r["record"])[0]]
    out["signed_scores"] = ck(not bad, f"{len(recs)} gateway records, {len(bad)} failed verification {bad[:5]}")
    ps = load_json(sealed_dir(root) / "postscore" / f"{run_id}__{arm}.json")
    leaked = [r["record"].get("run_id") for r in recs if any("sealed" in k for k in r["record"])]
    out["sealed_case_by_gateway_admin"] = ck(not leaked and (None if ps is None else ps.get("sealed_case_score") is not None),
                                             f"agent-time records with a sealed field: {leaked}; postscore "
                                             f"{'pending (runs once after all arms seal)' if ps is None else ps.get('sealed_case_score')}")
    board = read_jsonl(ad / "board.jsonl")
    humans = [p["id"] for p in board if p.get("human")]
    hp = [x for x in [run_dir(root) / "HUMAN_POSTS.log"] if x.exists()]  # this run only, not smoke or archives
    out["no_human_posts"] = ck(not humans and all(p.stat().st_size == 0 for p in hp),
                               f"human posts on board {humans}; HUMAN_POSTS.log files {[str(p) for p in hp]}")
    refused = sum(1 for g in agents for r in read_jsonl(ad / "agents" / g["id"] / "tool_calls.jsonl")
                  if r.get("verdict") == "refused")
    lin = centralization.lineage(read_jsonl(ad / "artifacts.jsonl"))
    lin.pop("derived_edges")
    out["lineage"] = ck(None, lin)
    br = breach_scan(root, run_id, arm, [g["id"] for g in agents],
                     [g["id"] for g in agents if g.get("role") == "member"])
    out["fs_breaches"] = ck(not br, {"n_breaches": sum(len(v) for v in br.values()), "by_agent": br,
                                     "method": "meter hook blocks; post-run scan of allowed calls (no per-agent "
                                               "OS accounts, so no ACL deny)"})
    sw = {}
    for g in agents:
        for r in read_jsonl(ad / "agents" / g["id"] / "models.jsonl"):
            if r.get("switch") or r.get("mismatch"):
                sw.setdefault(g["id"], []).append(r["model"])
    seen = sorted({r["model"] for g in agents for r in read_jsonl(ad / "agents" / g["id"] / "models.jsonl")})
    out["model_pinned"] = ck(not sw, f"models seen {seen or ['(none logged: mock)']}; switches/fallbacks {sw}")
    lim = sum(len(read_jsonl(ad / "agents" / g["id"] / "rate_limit.jsonl")) for g in agents)
    out["usage_window_pauses"] = ck(None, f"{lim} usage-window/rate-limit events (paused and resumed, same model)")
    iv = read_jsonl(Path(root) / "metrics" / "interventions.jsonl")
    if iv:  # human intervention: the identical broadcast notice (broadcast_notice.py)
        import broadcast_notice
        d_ = {}
        for r_ in [x for x in iv if x.get("event") == "sent"]:
            n_ = r_.get("notice") or 1
            now_rows = [r for r in broadcast_notice.agent_rows(root, n_) if r["run"] == run_id and r["arm"] == arm]
            d_[r_["notice_id"]] = {"kind": r_.get("kind"), "sent_utc": r_.get("utc"), "text_sha256": r_.get("text_sha256"),
                                   "agents": {r["agent"]: r["result"] for r in now_rows}}
        out["human_intervention_broadcast"] = ck(None, d_)
    inc = load_json(Path(root) / "metrics" / "incident_0350.json") or {}
    hit = [x for x in inc.get("agents", []) if x["agent"].startswith(f"{run_id}/{arm}/") and x.get("affected")]
    if inc:
        out["incident_0350_duplicates"] = ck(None, {"affected_agents": [x["agent"] for x in hit],
                                                    "duplicate_model_starts": sum(x["duplicate_model_starts"] for x in hit),
                                                    "board_posts_in_window": sum(x["board_posts_in_window"] for x in hit),
                                                    "note": "harness fault (scheduler --recover), disclosed; see metrics/incident_0350.json"})
    out["blocked_attempts"] = ck(None, f"{refused} tool calls refused by the meter (blocked path, price or quota)")
    return out


def check_arm(root, plan, sched, run_id, arm, ad, all_ids):
    manifest = load_json(ad / "arm.json")
    sealed = load_json(sealed_dir(root) / run_id / f"{arm}.json")
    agents = [g["id"] for g in manifest["agents"]]
    kind = base_arm(arm)
    claim, enforcement, falsifier = CLAIMS[kind]
    checks = {}
    foreign_other_arms = {f"{k}": v for k, v in all_ids.items() if not k.startswith(f"{run_id}/{arm}/")}
    if kind == "single":
        aid = agents[0]
        d = ad / "agents" / aid
        st = load_json(d / "claude_settings.json") or {}
        checks["subagents_disabled"] = ck("Task" in st.get("permissions", {}).get("deny", []) and
                                          "Agent" in st.get("permissions", {}).get("deny", []),
                                          f"deny list {st.get('permissions', {}).get('deny')}")
        ses = read_jsonl(d / "sessions.jsonl")
        starts = [s for s in ses if s["event"] == "start"]
        ends = [s for s in ses if s["event"] == "end"]
        sids = sorted({s.get("session_id") for s in ends if s.get("session_id")})
        overlap = any(starts[i + 1]["ts"] < ends[i]["ts"] for i in range(min(len(starts) - 1, len(ends))))
        checks["one_model_session"] = ck(len(sids) <= 1 and not overlap,
                                         f"{len(starts)} model process(es) (pids {[s['pid'] for s in starts]}), "
                                         f"session ids {sids}, overlapping {overlap}")
        text = transcript(d)
        task = len(re.findall(r'"name":\s*"(Task|Agent)"', text))
        checks["no_task_tool_use"] = ck(task == 0, f"{task} Task/Agent tool uses in the transcript")
        hits = scan(text, foreign_other_arms)
        checks["no_cross_arm_reference"] = ck(not hits, f"{len(hits)} hits {hits[:5]}")
    elif kind == "best_of_n":
        dirs = {a: ad / "agents" / a for a in agents}
        hits = {}
        for a in agents:
            text = transcript(dirs[a])
            own = f"{run_id}/{arm}/{a}"
            foreign = {k: v for k, v in all_ids.items() if k != own}
            foreign[f"folders/{a}"] = {f"agents/{b}" for b in agents if b != a}
            other_final = [load_json(dirs[b] / "final.json") or {} for b in agents if b != a]
            shingles = set()
            for f in other_final:
                w = (f.get("justification") or "").split()
                shingles |= {" ".join(w[i:i + 8]) for i in range(0, max(0, len(w) - 8), 8)}
            foreign["text"] = {s for s in shingles if len(s) > 40}
            h = scan(text, foreign)
            if h:
                hits[a] = h[:5]
        checks["no_cross_reference"] = ck(not hits, f"hits {hits}")
        board = [p for p in read_jsonl(ad / "board.jsonl") if p["author"] != "sealer"]
        checks["no_board_traffic"] = ck(not board, f"{len(board)} non-seal posts on the (unshared) board file")
        wa = web_audit(dirs)
        writes = [f for f in wa["flags"] if f["type"] in ("write_to_url", "fetched_after_other_agents_write")]
        checks["web_no_cross_agent_channel"] = ck(not writes, f"{len(writes)} write/reuse flags {writes[:3]}")
        checks["web_non_reference_domains"] = ck(None, f"{sum(1 for f in wa['flags'] if f['type'] == 'non_reference_domain')}"
                                                       f" of {wa['n_events']} web events flagged; shared URLs "
                                                       f"{list(wa['shared_urls'])[:5]}")
        sim = similarity(ad, agents)
        checks["pairwise_design_similarity"] = ck(None if not sim else max(v or 0 for v in sim.values()) < 0.95,
                                                  f"Jaccard of quantized strut sets {sim}")
        checks["_web_audit"] = wa
    elif kind == "collective":
        texts = {g["id"]: (ad / "agents" / g["id"] / "BRIEF.md").read_text(encoding="utf-8") for g in manifest["agents"]}
        import briefs
        ok, common, full = briefs.check_identical(texts)
        expected = sched.get("brief_common_sha256")
        checks["identical_briefs"] = ck(ok and common == expected, f"common sha256 {common} (launch {expected}); "
                                                                   f"per-brief {full}")
        sub = load_json(root / "submissions" / run_id / arm / "SUBMISSION.json") or {}
        checks["fixed_submission_rule"] = ck(None, {"rule": "the shared deliverables folder at the deadline",
                                                    "submission": sub.get("submission"), "missing": sub.get("missing")})
        res = centralization.arm_result(root, run_id, arm)
        checks["communication"] = ck(None, {k: res.get(k) for k in (
            "degree_centralization", "betweenness_max", "betweenness_argmax", "post_share", "directive_share",
            "n_directive_posts", "emergent_leader", "most_connected", "edges_by_type", "directive_rule", "needs",
            "replications", "lineage")})
        iv = manifest.get("intervention")
        if iv:
            src = load_json(sealed_dir(root) / run_id / f"{iv['source_arm']}.json") or {}
            s0 = (src.get("arm_design") or {}).get("seal_score")
            s1 = ((sealed or {}).get("arm_design") or {}).get("seal_score")
            new_leader = res.get("emergent_leader")
            takeover = bool(new_leader and new_leader != iv["leader"])
            d = {"kind": iv["kind"], "leader": iv["leader"], "leader_basis": iv["leader_basis"],
                 "source_directive_share": (iv["source_metrics"].get("directive_share") or {}),
                 "source_degree_centralization": iv["source_metrics"].get("degree_centralization"),
                 "rerun_emergent_leader": new_leader, "rerun_directive_share": res.get("directive_share"),
                 "rerun_degree_centralization": res.get("degree_centralization"),
                 "takeover": takeover, "score_source": s0, "score_rerun": s1,
                 "score_change": (s1 - s0) if (s0 is not None and s1 is not None) else None}
            if iv["kind"] == "cap":
                nd = sum(1 for p in res.get("directive_posts", []) if p["author"] == iv["leader"])
                d["leader_directive_posts"] = nd
                checks["cap_enforced"] = ck(nd <= (iv.get("directive_cap") or 0), f"{nd} directive posts by "
                                                                                    f"{iv['leader']}, cap {iv['directive_cap']}")
            checks["leader_intervention"] = ck(None, d)
    elif kind == "planner":
        res = centralization.arm_result(root, run_id, arm)
        dc = res.get("degree_centralization")
        checks["star_graph"] = ck(dc is not None and dc >= 0.8, f"degree centralization {dc} (star = 1); "
                                                               f"betweenness max {res.get('betweenness_max')}")
        lead = next(g["id"] for g in manifest["agents"] if g.get("role") == "lead")
        dl = f"/run/{run_id}/{arm}/deliverables".lower()
        leaks = []
        for g in manifest["agents"]:
            if g["id"] == lead:
                continue
            for r in read_jsonl(ad / "agents" / g["id"] / "tool_calls.jsonl"):
                t = json.dumps(r).replace("\\\\", "/").replace("\\", "/").lower()
                if r.get("verdict") != "refused" and dl in t:
                    leaks.append(g["id"])
        checks["deliverables_written_by_lead_only"] = ck(not leaks, f"member calls touching the deliverables: {leaks}")
        assigns = [p_ for p_ in read_jsonl(ad / "board.jsonl") if p_["kind"] == "assign"]
        checks["assignments_logged"] = ck(None, f"{len(assigns)} assign posts by the lead")
    chosen_art = None
    if sealed and sealed.get("arm_design"):
        led = {r["record"]["run_id"]: r for r in read_jsonl(ad / "gateway_ledger.jsonl")}
        chosen_art = (led.get(sealed["arm_design"]["run_id"]) or {}).get("artifact")
    checks["who_decided"] = ck(None, centralization.attribution(read_jsonl(ad / "artifacts.jsonl"), chosen_art)
                               if chosen_art else "no arm design")
    checks.update({f"all_arms.{k}": v for k, v in common_checks(root, plan, run_id, arm, ad, manifest, sealed).items()})
    verdict = all(c["ok"] is not False for k, c in checks.items() if not k.startswith("_"))
    return {"arm": arm, "run_id": run_id, "checked_utc": utc_now(), "claim": claim, "enforcement": enforcement,
            "falsifier": falsifier, "pass": verdict, "checks": checks,
            "seal_score": ((sealed or {}).get("arm_design") or {}).get("seal_score"), "sealed": sealed is not None}


def check_control(root, variant):
    b = load_json(Path(root) / "control" / variant / "control_build.json") or {}
    sealed = {}
    det = b.get("determinism") or {}
    nm = {"model_transcripts": sorted(x.name for x in (Path(root) / "control" / variant).rglob("*.jsonl"))}
    claim, enforcement, falsifier = CLAIMS["control"]
    checks = {"deterministic_rerun": ck(bool(det.get("identical")), det),
              "no_model_calls": ck(not nm.get("model_transcripts"), nm)}
    return {"arm": "control", "run_id": f"control_{variant}", "checked_utc": utc_now(), "claim": claim,
            "enforcement": enforcement, "falsifier": falsifier,
            "pass": all(c["ok"] for c in checks.values()), "checks": checks,
            "seal_score": (sealed.get("arm_design") or {}).get("seal_score"), "sealed": bool(sealed)}


def rules_unchanged(root):
    m = load_json(run_dir(root) / "rules_manifest.json") or {}
    return all(sha_file(HERE / r["file"]) == r["sha256"] for r in m.get("rules", [])) if m else None


def touches(root):
    f = run_dir(root) / "touch.log"
    return f"{len(f.read_text(encoding='utf-8').splitlines())} logged" if f.exists() else "none logged"


def global_checks(root, plan, sched):
    orders = [tuple(b["arms"]) for b in plan.get("batches", [])]
    cur = (HERE / "tools.json")
    rows = (run_dir(root) / "harness_sha256.txt").read_text(encoding="utf-8").splitlines() \
        if (run_dir(root) / "harness_sha256.txt").exists() else []
    changed = []
    for line in rows:
        h, rel = line.split("  ", 1)
        f = HERE / rel
        if not f.exists() or sha_file(f) != h:
            changed.append(rel)
    return {"interleaved_order": ck(len(set(orders)) == min(len(orders), 4), f"arm orders by batch {orders}"),
            "harness_unchanged_since_launch": ck(not changed, f"{len(rows)} files hashed at launch; changed {changed}"),
            "brief_hashes_logged": ck(bool((plan.get("brief_check") or {}).get("ok")),
                                      f"common sha256 {(plan.get('brief_check') or {}).get('common_sha256')}"),
            "rules_frozen": ck(rules_unchanged(root), "every rule file in run/rules_manifest.json still has its "
                                                       "launch hash; touches: " + touches(root)),
            "health_check": ck((load_json(run_dir(root) / "health.json") or {}).get("ok"),
                               (load_json(run_dir(root) / "health.json") or {}).get("failed")),
            "launcher_exit_logged": ck(bool(plan.get("launcher_exit_local")),
                                       f"launcher pid {plan.get('launcher_pid')} exited {plan.get('launcher_exit_local')}"),
            "tools_registry": ck(cur.exists(), f"tools.json sha256 {sha_file(cur)[:12]}")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    plan = load_json(run_dir(root) / "run_manifest.json") or {}
    sched = load_json(run_dir(root) / "schedule.json") or {}
    all_ids = {}
    for run_id, arm, ad in arm_runs(root):
        for author, ids in identifiers(ad).items():
            all_ids[f"{run_id}/{arm}/{author}"] = {i for i in ids if i}
    rows = []
    for t in sorted(x.name for x in (root / "control").glob("*/")) if (root / "control").exists() else []:
        res = check_control(root, t)
        write_json(run_dir(root) / "control" / t / "manipulation_check.json", res)
        rows.append(res)
    for run_id, arm, ad in list(arm_runs(root)):
        res = check_arm(root, plan, sched, run_id, arm, ad, all_ids)
        out = run_dir(root) / arm / run_id
        out.mkdir(parents=True, exist_ok=True)
        write_json(out / "manipulation_check.json", res)
        rows.append(res)
    glob = global_checks(root, plan, sched)
    # tool use per agent (affinity in practice vs prices in the genome), logged into the run plan
    usage, orx = {}, {}
    for run_id, arm, ad in arm_runs(root):
        for gg in load_json(ad / "arm.json")["agents"]:
            calls = read_jsonl(ad / "agents" / gg["id"] / "tool_calls.jsonl")
            c = Counter((r.get("priced_as") or r.get("tool")) for r in calls if r.get("verdict") != "refused"
                        and r.get("result") != "unavailable")
            key = f"{run_id}/{arm}/{gg['id']}"
            usage[key] = {"calls": dict(c), "prices": gg["tool_prices"]}
            orx[key] = sum(1 for r in calls if r.get("tool") == "openresearch" and r.get("result") == "ok")
    write_json(run_dir(root) / "tool_usage.json", usage)
    if plan:
        plan["post_run"] = {"checked_utc": utc_now(), "openresearch_calls_per_agent": orx,
                            "tool_usage_file": "run/tool_usage.json"}
        write_json(run_dir(root) / "run_manifest.json", plan)
    summary = {"checked_utc": utc_now(), "global": glob, "rows": [
        {k: r[k] for k in ("arm", "run_id", "pass", "seal_score", "sealed")} |
        {"failed": [k for k, c in r["checks"].items() if not k.startswith("_") and c["ok"] is False]} for r in rows]}
    write_json(run_dir(root) / "manipulation_summary.json", summary)
    md = ["| arm | run | pass | seal score | failed checks |", "|---|---|---|---|---|"]
    for r in summary["rows"]:
        md.append(f"| {r['arm']} | {r['run_id']} | {'yes' if r['pass'] else 'NO'} | {r['seal_score']} | "
                  f"{', '.join(r['failed']) or '-'} |")
    md += ["", "| global check | ok | detail |", "|---|---|---|"]
    for k, c in glob.items():
        md.append(f"| {k} | {c['ok']} | {str(c['detail'])[:160]} |")
    (run_dir(root) / "manipulation_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    mdir = root / (load_json(HERE / "config.json") or {}).get("metrics_dir", "metrics")
    mdir.mkdir(parents=True, exist_ok=True)  # counts only (no content) for the evaluator
    write_json(mdir / "manipulation_summary.json", {"checked_utc": summary["checked_utc"], "rows": [
        {k: r[k] for k in ("arm", "run_id", "pass", "failed")} for r in summary["rows"]],
        "global": {k: c["ok"] for k, c in glob.items()}})
    print("\n".join(md))


if __name__ == "__main__":
    main()
