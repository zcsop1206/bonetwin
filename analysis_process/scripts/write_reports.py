"""metrics.md and timeline.md from metrics.json + read-only logs. Deterministic."""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
B = Path(os.environ.get("BONETWIN_ROOT") or Path(__file__).resolve().parents[2])
OUT = B / "analysis_process"
H = B / "harness_open"
M = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
R, AG, GL = M["runs"], M["agents"], M["global"]
ORDER = [f"{r}/{a}" for r in ("r1", "r2") for a in ("single", "best_of_n", "collective", "planner")]
BOARD = [k for k in ORDER if "board" in R[k]]
UTC = dt.timezone.utc


def t(s):
    return dt.datetime.fromisoformat(s).astimezone(UTC)


def loc(d):
    z, n = (dt.timezone(dt.timedelta(hours=-4)), "EDT") if d < dt.datetime(2026, 11, 1, 6, tzinfo=UTC) else (dt.timezone(dt.timedelta(hours=-5)), "EST")
    return d.astimezone(z).strftime("%H:%M:%S ") + n


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def k(n):
    return f"{n:,}"


def rate(d):
    return f"{d['agree']}/{d['n']} ({d['rate']:.2f})" if d["n"] else "n/a"


md = ["# Process metrics, bone-twin open run", "",
      "Deterministic measurement, no ranking of arms and no scores. Machine-readable: `metrics.json` (per agent, per run, KB series, edges). "
      "Regenerate: `scripts/compute_metrics.py`, `scripts/write_reports.py`, `scripts/make_figures.py`. All times are local; every session ran after the 02:00 fall-back, so EST.", "",
      "Harness code reused directly: `centralization.analyse`, `directives`, `process_metrics.kb_stats`, `billing.list_price`, `compute/ledger_costs.py`. "
      f"Tool counts match the harness's own `metrics/process_metrics.json` for all 38 agents (mismatches: {len(GL['harness_process_metrics_tool_counts_mismatch_agents'])}).", "",
      "## 1. Key numbers per run", ""]
rows = []
for key in ORDER:
    r = R[key]
    b = r.get("board")
    rows.append([key, r["n_agents"], r["model_process_starts"], r["duplicate_runner_starts"], r["wall_min_sum"], k(r["credits_used"]), k(r["quota_total"]),
                 f"{r['list_usd_from_tokens']:.2f}", ", ".join(f"{v} {s}" for s, v in r["end_states"].items()),
                 b["n_agent_posts"] if b else "-", f"{b['degree_centralization']:.2f}" if b else "-", r["preform"]["calls"], r["preform"]["distinct_ok"], r["brev_ledger"]["starts"], f"{r['brev_ledger']['usd']:.2f}",
                 r["kb"]["final"]["n_files"], "yes" if r["submission"]["submission"] else "no"])
md.append(table(["run", "agents", "model processes", "of which duplicate-runner", "agent wall min (sum)", "credits used", "quota", "list $ (tokens)", "end states", "posts", "deg. central.", "PreForm calls", "PreForm endpoints ok", "Brev starts", "Brev $", "KB files", "all deliverables at collection"], rows))
md += ["", "Control (`control/gibson_ashby_rigid10k`): no agent sessions, so these metrics do not apply. Brev $0; manipulation check passes (`deterministic_rerun`, `no_model_calls`). "
       "'All deliverables' is `metrics/submissions.json`, a completeness flag and not a score.", "",
       "End states: capped = balance reached zero; finished = the agent ran `done`/final; window = the 90-minute wall cap closed first (`safety_cap`).", "",
       "## 2. Credits and raw tokens by type", ""]
rows = []
for key in ORDER:
    r = R[key]
    x = r["tokens"]
    rows.append([key, k(x.get("input", 0)), k(x.get("cache_creation", 0)), k(x.get("cache_read", 0)), k(x.get("output", 0)), k(x.get("exempt", 0)), k(r["token_credits"]), k(r["tool_credits"]), k(r["credits_used"])])
md.append(table(["run", "input", "cache creation", "cache read", "output", "exempt credits", "token credits", "tool credits", "credits used"], rows))
md += ["", "Credits = input + cache creation + 0.1 x cache read + output - exempt + tool charges (`meter.py`). Exempt = Claude Code first-turn overhead. r2 single's exemption is 0 against 236,499 for r1 single (already disclosed in RUN_LOG).", "",
       "Balance reconciliation: quota + transfers in - transfers out - credits used equals `status.json` balance for every agent (see section 11).", "",
       "## 3. Dollars and billing split", ""]
rows = [[key, R[key]["billing"]["subscription"]["turns"], f"{R[key]['billing']['subscription']['usd']:.2f}", R[key]["billing"]["api"]["turns"], f"{R[key]['billing']['api']['usd']:.2f}", f"{R[key]['list_usd_from_tokens']:.2f}"] for key in ORDER]
md.append(table(["run", "subscription-labelled turns", "subscription-labelled $", "API-labelled turns", "API-labelled $", "$ from token totals"], rows))
al = GL["api_ledger"]
pt = GL["per_turn_billing_sum"]
pre = {k_: a["subscription_label_before_0440_reset"] for k_, a in AG.items() if a["subscription_label_before_0440_reset"]["turns"] and a["arm"] == "best_of_n"}
md += ["", f"Per-turn sums: subscription ${pt['subscription']['usd']:.2f} ({pt['subscription']['turns']} turns), API ${pt['api']['usd']:.2f} ({pt['api']['turns']} turns). "
       f"Harness API ledger (`run/api_spend.jsonl` + `run/api_live/`): closed ${al['closed_usd']:.2f} + live ${al['live_usd']:.2f} = ${al['total_usd']:.2f}, cap ${al['cap_usd']:.0f}.", "",
       "Dollars are the harness's list-price estimate with per-Mtok prices fitted in `config.json` (`token_estimate.usd_per_mtok`), not an invoice. The gap between per-turn rows and the token-total column comes from the runner's output estimate (characters / 4 when larger than the logged count).", "",
       "Inference: the closed ledger overcounts. For resumed sessions `total_cost_usd` appears cumulative (r2 s1 rows 1.79, 2.97, 3.72, 3.72, 4.45; r1 s1 4.69, 4.82), and summing them counts earlier turns again. The per-turn API figure is the safer one.", "",
       f"Unclear label: {len(pre)} best-of-N agents have subscription-labelled turns before the 04:40 reset ({sum(v['turns'] for v in pre.values())} turns, ${sum(v['usd'] for v in pre.values()):.2f}). `apiKeySource` is `none` for those sampled (r1 b1, b2, r2 b1), and r2 b1 logged `allowed` rate-limit events with a new reset time, so the subscription seems to have accepted calls early. r1 b1 and b2 logged no rate-limit events, so that cannot be confirmed for them.", "",
       "## 4. Boards", ""]
rows = []
for key in BOARD:
    b = R[key]["board"]
    rows.append([key, b["n_agent_posts"], ", ".join(f"{a} {n}" for a, n in sorted(b["post_kinds"].items())), f"{b['degree_centralization']:.2f}", f"{b['degree_centralization_reply_only']:.2f}", f"{b['degree_centralization_with_plain_id_mentions']:.2f}",
                 f"{b['betweenness_max']:.2f} ({b['betweenness_argmax']})", f"{b['top_agent_post_share']:.2f} ({b['top_poster']})"])
md.append(table(["run", "posts", "kinds", "deg. central. (harness, all edge types)", "reply edges only", "harness + plain id mentions", "betweenness max", "top post share"], rows))
md += ["", "The harness counts `@c3` mentions, not bare `c3` or `c1 -> c2`, which is how the collective boards usually address each other. The two extra columns show how much that matters: adding bare ids makes the graphs denser, so centralization falls. Bare ids can also be references rather than addresses.", ""]
rows = []
for key in BOARD:
    b = R[key]["board"]
    ds = ", ".join(f"{a} {b['directive_counts'].get(a, 0)} ({b['directive_share'][a]:.2f})" for a in sorted(b["directive_share"]))
    e = b["edges_by_type"]
    rows.append([key, b["n_directive_posts"], ds, b["emergent_leader"], e["reply"], e["mention"], e["transfer"], e["review"], sum(b["typed_links"].values()), b["needs_harness"]["n"], b["needs_harness"]["answered"], b["needs_harness"]["expired"], len(b["transfers"])])
md.append(table(["run", "directive posts", "per agent: count (share)", "harness emergent leader", "reply", "mention", "transfer", "review", "typed links", "needs", "answered", "expired", "credit transfers"], rows))
md += ["", f"Directive rule: {GL['directive_rule']}.", "",
       "`emergent_leader` is the harness rule (share > 2 x mean, no minimum count), so r1 collective's c4 qualifies on 2 of 3 directive posts and r2 collective's c4 on 1 of 1. The live-intervention rule also requires at least 5 directive posts, and nobody met it.", "",
       "Needs: 'answered' means a claim post with `pickup_of`, which no agent used, so the harness count is 0. No `expire` posts were written either. Informal follow-up:", ""]
for key in BOARD:
    for n in R[key]["board"]["needs_detail"]:
        md.append(f"- {key} {n['id']} ({n['author']} to {n['to'] or 'anyone'}): next post by another agent addressing {n['author']} is {n['first_later_post_addressing_author'] or 'none'}" + (f" by {n['first_later_post_author']}" if n["first_later_post_author"] else "") + ".")
md += ["- r2/collective p0016 was addressed to c5; c5 did not reply on the board. c1 picked up the job in p0019 (read from the board).", "",
       "Credit transfers: " + "; ".join(f"{key} {x['id']} {x['from']} to {x['to']} {k(x['amount'])}" for key in BOARD for x in R[key]["board"]["transfers"]) + ".", "",
       "## 5. Knowledge bases", ""]
rows = []
for key in ORDER:
    r = R[key]
    s = r["kb"]["series"]
    f = r["kb"]["final"]
    b = r.get("board")
    rows.append([key, "shared" if b else "per agent", f["n_files"], k(f["bytes"]), f["xrefs"], len(s), b["kb_files_named_by_multiple_agents"]["n_named_by_2plus_agents"] if b else "-"])
md.append(table(["run", "KB", "files (final)", "bytes (final)", "cross-references (harness)", "snapshots", "files named in 2+ agents' tool calls"], rows))
md += ["", "Growth over time, snapshot sums (files / MB) from `metrics/kb_growth.jsonl`, nearest snapshot at or before each clock time. Full series in `metrics.json`.", ""]
clocks = ["03:45", "04:00", "04:15", "04:30", "04:45", "05:00", "05:15", "05:30", "05:45", "06:00", "06:27"]
rows = []
EST = dt.timezone(dt.timedelta(hours=-5))
for key in ORDER:
    row = [key]
    ser = R[key]["kb"]["series"]
    for c in clocks:
        h, m = map(int, c.split(":"))
        tt = dt.datetime(2026, 11, 1, h, m, 59, tzinfo=EST).astimezone(UTC)
        pts = [x for x in ser if t(x["utc"]) <= tt]
        row.append(f"{pts[-1]['files']} / {pts[-1]['bytes'] / 1e6:.2f}" if pts else "-")
    rows.append(row)
md.append(table(["run"] + clocks, rows))
md += ["", "Cross-agent lineage: `artifacts.jsonl` does not exist in this run (agents did not use the gateway's design-artifact path), so the harness lineage measures (DAG depth, syntheses, cross-agent derivations) are all zero by absence, not by measurement. Proxy from board citations (parents, `pNNNN` mentions):", ""]
md.append(table(["run", "longest citation chain", "cross-agent citation edges", "posts citing 2+ other agents"], [[key, R[key]["board"]["board_lineage_proxy"]["max_chain_depth"], R[key]["board"]["board_lineage_proxy"]["cross_agent_citation_edges"], R[key]["board"]["board_lineage_proxy"]["posts_citing_two_or_more_other_agents"]] for key in BOARD]))
md += ["", "## 6. Tool calls", "", "Claude-level = calls the meter hook allowed (allowed does not mean succeeded). Proxied = calls logged by `bt_tool.py`, usually launched from a Bash call, so the two levels overlap and must not be added. Per-agent breakdown is in section 11 and `metrics.json` under `agents.<id>.tool_calls`.", ""]
rows = []
for key in ORDER:
    c = R[key]["tool_calls"]
    rows.append([key, ", ".join(f"{a} {n}" for a, n in sorted(c["allowed_claude_level"].items(), key=lambda x: -x[1])), ", ".join(f"{a} {n}" for a, n in sorted(c["proxied"].items(), key=lambda x: -x[1])), c["refused"], c["held_for_notice"]])
md.append(table(["run", "Claude-level allowed", "proxied", "refused", "held for notice"], rows))
md += ["", "## 7. PreForm API", "", "`preform_api` rows; ids and query strings normalized out of endpoints.", ""]
rows = [[key, R[key]["preform"]["calls"], R[key]["preform"]["ok"], R[key]["preform"]["calls"] - R[key]["preform"]["ok"], R[key]["preform"]["distinct_attempted"], R[key]["preform"]["distinct_ok"]] for key in ORDER]
md.append(table(["run", "calls", "ok", "errors", "distinct endpoints attempted", "distinct endpoints ok"], rows))
top = sorted(AG.items(), key=lambda x: -x[1]["preform"]["distinct_ok"])[:6]
md += ["", "Widest use by agent: " + "; ".join(f"{a} {v['preform']['distinct_ok']} endpoints ok of {v['preform']['calls']} calls" for a, v in top) + ".", "",
       "## 8. Brev (cost fields from `compute/ledger_costs.py` only)", ""]
rows = [[x.get("run"), x.get("usd"), x.get("instances"), x.get("starts"), ", ".join(x.get("types") or [])] for x in GL["brev_ledger_output"] if x.get("run") not in ("?", None)]
md.append(table(["ledger run", "$", "instances", "starts", "types"], rows))
tot = [x for x in GL["brev_ledger_output"] if "total_usd" in x]
arm_tot = sum(R[k_]["brev_ledger"]["usd"] for k_ in ORDER)
md += ["", f"Ledger total ${tot[0]['total_usd']:.2f}, of which arms ${arm_tot:.2f}; the rest is image tests and judge setup. Arms absent from the ledger made no starts. The ledger reports by run; which agent started what comes from tool logs:", ""]
for a, v in AG.items():
    if v["brev_starts_from_tool_log"]:
        md.append(f"- {a}: " + ", ".join(f"{t(s['utc']).astimezone(EST).strftime('%H:%M')} {s['result']}" for s in v["brev_starts_from_tool_log"]))
md += ["", "## 9. NVIDIA tool use by agent", "", "'ran' = a `warp_gpu` call returned ok, or Warp code was executed on Brev. Only agents with some signal are listed.", ""]
rows = []
for a, v in AG.items():
    n = v["nvidia"]
    if n["warp_status"] != "none":
        w = n["warp_gpu_tool"]
        rows.append([a, n["warp_status"], w.get("ok", 0), w.get("unavailable", 0), n["brev_exec_warp_ok"]])
md.append(table(["agent", "Warp", "warp_gpu ok", "warp_gpu unavailable (heavy queue / RAM)", "Brev exec with Warp ok"], rows))
oth = {x: sum(v["nvidia"][x] for v in AG.values()) for x in ("warp_fem_hits", "physicsnemo_hits", "bionemo_hits", "alchemi_hits", "ngc_hits")}
md += ["", f"Across all 38 agents' tool inputs, assistant text and own scripts: warp.fem {oth['warp_fem_hits']}, PhysicsNeMo {oth['physicsnemo_hits']}, BioNeMo {oth['bionemo_hits']}, ALCHEMI {oth['alchemi_hits']}, NGC {oth['ngc_hits']} hits. "
       f"`compute_images.md` was named in {sum(v['nvidia']['compute_images_md_refs'] for v in AG.values())} tool inputs. The Warp solvers are the agents' own matrix-free hex8 kernels, not `warp.fem`, even where a board post uses that label.", "",
       "Sponsor-tool calls before and after the first notice (04:46:41), per run:", ""]
rows = [[key, *(R[key]["notice_tool_calls_before_after_first_notice"].get(f"{x}_{y}", 0) for x in ("preform_api", "warp_gpu", "compute") for y in ("before", "after"))] for key in ORDER]
md.append(table(["run", "PreForm before", "PreForm after", "warp_gpu before", "warp_gpu after", "compute before", "compute after"], rows))
it = GL["interventions"]["final_status"]
md += ["", f"Notice delivery: {it['totals']['delivered']} delivered, {it['totals']['pending_not_started']} shown at start (not yet started), {it['totals']['missed']} missed. So who saw it is confounded with replicate and start time, and before/after is not a clean comparison.", "",
       "## 10. Leanings against actual use", "",
       "Only the `tools` axis has a pre-registered mapping (`config.json` `affinity_tool_map`). Other axes are analyst-defined proxies, not pre-registered, included because the rate was requested. Singles are 'generalist' and excluded.", "",
       "- tools, top family: the leaning is the agent's most-used family, excluding 'other'.",
       "- tools, lift > 1: the family's share of the agent's calls exceeds its share across all agents (harness definition).",
       "- knowledge proxy: leaning mapped to a family (FEA, ML to NVIDIA simulation; additive manufacturing to PreForm; biology, chemistry, clinical to literature), lift > 1.",
       "- working style proxy: explorer or exploiter = tool entropy above or below the median; builder = CAD/PreForm/Write share at or above the median; verifier = PreForm validation share at or above the median. Base rate about 0.5.",
       "- communication proxy (board arms): broadcaster = posts above arm mean; listener = below; connector = betweenness above arm mean. 'challenger' is not measured (it would need text classification).", ""]
rows = []
for key in ORDER + ["ALL"]:
    la = GL["leanings_agreement_all"] if key == "ALL" else R[key]["leanings_agreement"]
    rows.append([key, rate(la["tools_top_family_match"]), rate(la["tools_lift_gt_1"]), rate(la["knowledge_proxy"]), rate(la["working_style_proxy"]), rate(la["communication_proxy"])])
md.append(table(["run", "tools, top family", "tools, lift > 1", "knowledge proxy", "working style proxy", "communication proxy"], rows))
md += ["", "## 11. Per agent", ""]
rows = []
for a, v in AG.items():
    tc = v["tool_calls"]
    bal_in = sum(x["amount"] for key in BOARD for x in R[key]["board"]["transfers"] if key == f"{v['run']}/{v['arm']}" and x["to"] == v["agent"])
    bal_out = sum(x["amount"] for key in BOARD for x in R[key]["board"]["transfers"] if key == f"{v['run']}/{v['arm']}" and x["from"] == v["agent"])
    rec = v["quota"] + bal_in - bal_out - v["credits_used"] - v["balance_status"]
    v["_rec"] = rec
    prox = sum(sum(x.values()) for x in tc["proxied_by_result"].values())
    lean = v["leanings"] or {}
    rows.append([a, v["start_local"][:5], v["end_local"][:5], v["wall_min"], v["end_state"], k(v["credits_used"]), k(v["balance_status"]), f"{v['cache_read_credit_share']:.2f}", f"{v['billing']['subscription']['usd'] + v['billing']['api']['usd']:.2f}",
                 sum(tc["allowed_claude_level"].values()), prox, tc["refused"], v["preform"]["calls"], v["preform"]["distinct_ok"], lean.get("tools", "-")])
md.append(table(["agent", "start", "end", "wall min", "state", "credits", "balance", "cache-read credit share", "list $", "Claude-level calls", "proxied calls", "refused", "PreForm calls", "PreForm endpoints ok", "tools leaning"], rows))
bad = [a for a, v in AG.items() if abs(v["_rec"]) > 2]
md += ["", f"Balance reconciliation failures (more than 2 credits): {bad or 'none'}. Largest quota overshoots: " + ", ".join(f"{a} {k(-v['balance_status'])}" for a, v in sorted(AG.items(), key=lambda x: x[1]['balance_status'])[:3]) + ".", "",
       "## 12. Manipulation checks", "",
       f"From the scheduler's own run of `manipulation.py` at {GL['manipulation_checked_utc']} (06:27 EST), after all sessions ended. Not re-executed here: `check_arm` writes into `run/` and `metrics/`. These are the harness's stored results.", ""]
WHY = {"all_arms.no_human_posts": "by design: `run/HUMAN_POSTS.log` holds the two 04:47 and 04:51 notices. No human post appears on any board.",
       "all_arms.model_pinned": "`<synthetic>` rows only, logged at the 03:32 to 03:33 usage-limit block. The real model was claude-opus-5-5 throughout. Inference: a Claude Code limit message, not a model switch.",
       "one_model_session": "4 processes, one session id, overlap true. The overlap is the 03:50 duplicate runner (metrics/incident_0350.json).",
       "all_arms.fs_breaches": "1 hit, the agent's own folder path cut off by the meter's 600-character command limit (row length 600). Inference: false positive."}
rows = []
for key in ["control/gibson_ashby_rigid10k"] + [f"{a}/{r}" for r in ("r1", "r2") for a in ("single", "best_of_n", "collective", "planner")]:
    m = R[f"{key.split('/')[1]}/{key.split('/')[0]}"]["manipulation"] if not key.startswith("control") else M["control"]["manipulation"]
    rows.append([key, "PASS" if m["pass"] else "FAIL", "yes" if m["pass_excluding_no_human_posts"] else "no", ", ".join(x.replace("all_arms.", "") for x in m["failed"]) or "-", ", ".join(x.replace("all_arms.", "") for x in m["ok_true"])])
md.append(table(["arm/run", "harness verdict", "pass apart from no_human_posts", "failed", "passed"], rows))
md += ["", "Reasons:", ""] + [f"- `{a.replace('all_arms.', '')}`: {b}" for a, b in WHY.items()]
fb = GL["fs_breach_rows"]
md += ["", "fs_breaches rows checked: " + "; ".join(f"{x['agent']} {x['utc'][11:19]}Z, command length {x['command_len']}, tail `{x['flagged_tail']}`" for x in fb) + ".", "",
       "Global checks: " + "; ".join(f"{a} = {b['ok']}" for a, b in GL["manipulation_global"].items()) + ". `harness_unchanged_since_launch` is false because `config.json`, `manipulation.py` and `scheduler.py` were changed after launch; `rules_frozen` is false because `config.json` and `scheduler.py` no longer match their launch hashes in `run/rules_manifest.json`; the other 10 rule files match.", "",
       "## 13. Not measured or only partly measured", "",
       "- Lineage (DAG depth, syntheses, derivations): no `artifacts.jsonl` in this run. Board citation proxy only.",
       "- Typed links (cites, contradicts, extends, replicates): 0 on every board. The field exists and no agent used it, so these are true zeros, not a gap.",
       "- Needs answered: 0 by rule because no claim used `pickup_of`. Informal answers are listed individually, not counted.",
       "- Memory before 04:06: `memlog.jsonl` starts at 04:06, so the 03:44 to 04:04 commit peak exists only as RUN_LOG text. `scheduler.jsonl` free RAM covers that period.",
       f"- Memory-governor kills: `metrics/memgov.jsonl` does not exist. 73 Python processes of 1 GB or more disappeared per `memlog.jsonl`; why they ended is unknown, and 0 Windows low-memory events are in the file because that step runs at 08:35 and the log I read ends at 07:14.",
       "- True billing source for best-of-N turns before 04:40: only the label is known for r1 b1 and b2 (section 3). API ledger total is an estimate and probably overcounts.",
       "- Tool success for Claude-level calls: the hook logs before execution, so success is only known for proxied tools.",
       "- Duplicate-runner share of tokens: original and duplicate runners write the same transcript and status, so usage cannot be split per runner in the 03:50 window.",
       "- Credit curves are reconstructed from per-message usage and tool charges, then scaled to the runner's total. Scale is within 5% of 1 for most agents and 1.12 to 1.19 for r2 planner; inference: the runner's character-based output estimate exceeded logged output there. Totals are exact as logged; curve shape is approximate.",
       "- Leaning agreement on knowledge, working style and communication: analyst proxies only. 'challenger' not measured.",
       "- Control: not applicable. Final scores: excluded by instruction.",
       "- Live files: `compute/memlog.jsonl` and `compute/compute_ledger.jsonl` were still being appended during this analysis (judge jobs), so judge-related Brev lines can grow on a rerun. Arm lines are final.",
       ""]
(OUT / "metrics.md").write_text("\n".join(md), encoding="utf-8")

# ---------------------------------------------------------------- timeline.md
sl = (H / "run" / "scheduler.log").read_text(encoding="utf-8").splitlines()
started = []
for ln in sl:
    m = re.match(r"(\S+) started (\S+) \((\d+) sessions", ln)
    if m and not m.group(1).startswith("2026-11-01T08:49:57"):
        started.append((t(m.group(1)), m.group(2), int(m.group(3))))
waves, cur = [], []
for row in started:
    if cur and (row[0] - cur[-1][0]).total_seconds() > 300:
        waves.append(cur)
        cur = []
    cur.append(row)
waves.append(cur)
guard = B / "guard"
g_m = dt.datetime.fromtimestamp(os.stat(guard).st_mtime, UTC)
groups = json.loads((H / "metrics" / "groups.json").read_text(encoding="utf-8"))
sw_sub = [(t(x["utc"]), a) for a, v in AG.items() for x in v["billing_switches"] if x["to"] == "subscription"]
events = [(t("2026-11-01T04:50:04+00:00"), "First launcher start", "run_aborted_0052/touch.log"),
          (t("2026-11-01T04:52:46+00:00"), "Aborted launch: scheduler up, 38 sessions started at once, each with a visible window; laptop froze", "run_aborted_0052/scheduler.log; RUN_LOG.md"),
          (t("2026-11-01T05:12:02+00:00"), "Last timestamp in any aborted-run agent log; force-close and reboot follows, time not logged", "run_aborted_0052/*/agents/*"),
          (dt.datetime(2026, 11, 1, 6, tzinfo=UTC), "Clocks fall back: 02:00 EDT becomes 01:00 EST. The stated 00:52 to 03:32 gap is 3 h 40 min of real time", "timestamps in run_aborted_0052 vs run"),
          (t("2026-11-01T08:31:15+00:00"), "Relaunch: launcher start", "run/touch.log"),
          (t("2026-11-01T08:32:25+00:00"), "Scheduler up, launcher exits (max 14 sessions, 90 min caps)", "run/scheduler.log"),
          (t("2026-11-01T08:32:38+00:00"), "Subscription 5-hour limit hit by all 14 running sessions within 22 s; each switches to the API key", "run/usage_events.jsonl; agents/*/billing.jsonl"),
          (t("2026-11-01T08:44:00+00:00"), "Memory commit 94%, 33 of 34.9 GB; duplicate-incident window opens (RUN_LOG text, no numeric log yet)", "RUN_LOG.md; compute/MEMORY_GOVERNOR_RULE.md; metrics/incident_0350.json"),
          (t("2026-11-01T08:47:24+00:00"), "r1 collective c1's last board post before capping", "run/r1/collective/board.jsonl p0015"),
          (t("2026-11-01T08:47:34+00:00"), "c1 capped, 10 s later", "run/r1/collective/agents/c1/status.json"),
          (t("2026-11-01T08:49:57+00:00"), "Incident: scheduler restarted with --recover respawned runners for the 14 live agents; 29 sessions at peak; 108 processes killed", "run/scheduler.log; metrics/incident_0350.json"),
          (t("2026-11-01T08:57:34+00:00"), "Incident recorded; window closes 03:58", "run/touch.log"),
          (t("2026-11-01T09:00:13+00:00"), "Scheduler restart with the fixed recover; admission 12 sessions, 3.5 GB", "run/touch.log; run/scheduler.log"),
          (t("2026-11-01T09:06:05+00:00"), "memlog.jsonl starts", "compute/memlog.jsonl"),
          (g_m, "Guard v2 in place. Time is the guard folder's modified time plus the brief; guard contents not read", "bonetwin/guard folder mtime"),
          (t("2026-11-01T09:40:00+00:00"), f"Subscription window reset (configured 04:40). API sessions switching back at this point: {len(sw_sub)}; every API session had already ended, last one r1 s1 at 04:39", "config.json overflow_api; agents/*/billing.jsonl"),
          (t("2026-11-01T09:46:41+00:00"), "Creativity notice 1 to all agents", "run/HUMAN_POSTS.log; metrics/interventions.jsonl"),
          (t("2026-11-01T09:50:39+00:00"), "Creativity notice 2. Final tally 11 delivered, 7 at start, 20 missed", "run/HUMAN_POSTS.log; metrics/interventions.jsonl"),
          (t("2026-11-01T10:35:49+00:00"), "Live intervention on r2 collective: no leader met the rule, no action", "metrics/live_intervention.json"),
          (t("2026-11-01T11:27:03+00:00"), "r2 planner window closes (p1 stopped by the wall cap)", "agents/p1/sessions.jsonl"),
          (t("2026-11-01T11:27:15+00:00"), "All units collected; scheduler exits", "run/scheduler.log"),
          (dt.datetime(2026, 11, 1, 11, 50, tzinfo=UTC), "~06:50 guard read unlock moved up from 07:15 to 06:45 (approximate)", "RUN_LOG.md"),
          ]
for i, w in enumerate(waves, 1):
    names = ", ".join(f"{u}" for _, u, _ in w)
    events.append((w[0][0], f"Start cluster {i} ({sum(x[2] for x in w)} sessions, through {loc(w[-1][0])[:8]}): {names}", "run/scheduler.log"))
for g, v in groups.items():
    events.append((t(v["start"]), f"Group start {g}, scheduled stop {t(v['stop']).astimezone(EST).strftime('%H:%M:%S')}", "metrics/groups.json"))
    events.append((t(v["stop"]), f"Group scheduled stop {g}", "metrics/groups.json"))
for a, v in AG.items():
    if v["end_state"] == "capped":
        events.append((t(v["end_utc"]), f"{a} capped", "agents status.json"))
    elif v["end_state"] == "finished":
        events.append((t(v["end_utc"]), f"{a} finished", "agents status.json"))
events.sort(key=lambda x: x[0])
tm = ["# Timeline of the night, Nov 1 2026", "", "![timeline](timeline.png)", "",
      "To scale in real elapsed time. The US fall-back happened at 02:00 EDT that night, so clock times before and after it are one hour apart from what they look like: 00:52 EDT to 03:32 EST is 3 h 40 min, not 2 h 40 min.", "",
      "'Start clusters' are my grouping of scheduler starts with gaps over 5 minutes. RUN_LOG speaks of 3 planned waves; the logs show 5 clusters. Scheduler rows at 03:49:57 are the duplicate incident and are excluded. Group stops are scheduled stops: both r1 groups and r2 collective had all capped well before theirs.", "",
      table(["local", "UTC", "event", "source"], [[loc(e[0]), e[0].strftime("%H:%M:%S"), e[1], e[2]] for e in events]), "",
      "Paths are relative to `bonetwin/harness_open/` unless they start with `bonetwin/`, `compute/` or `RUN_LOG.md` (those are under `bonetwin/`).", ""]
(OUT / "timeline.md").write_text("\n".join(tm), encoding="utf-8")
print("ok; recon bad:", bad, "switch to sub:", len(sw_sub), "guard mtime", loc(g_m), "clusters", len(waves))
