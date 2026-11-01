"""Briefs, blocked paths and agent folders for the OPEN run (harness_open; adapted from harness_design).

The brief is MINIMAL: the goal (verbatim), the deliverables, how it will be judged (one paragraph + link to
EVAL_SPEC.md), the resources (tool registry with honest status), the budget and the clock. Nothing about how to
solve it. Every brief is one shared body plus marked per-agent blocks:
    <!-- genome --> ... <!-- /genome -->   id, run, arm, folders, leanings (four lines), budget, the arm's rule
    <!-- role --> ... <!-- /role -->       planner arm only (lead / member)
    <!-- pack --><!-- /pack -->            empty (no knowledge packs in the open run)
check_identical() strips those blocks and requires one SHA-256 over all briefs; the launcher logs every hash.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, PLANNER_LABEL, SHARED_BOARD_ARMS, base_arm, write_json  # noqa: E402

# The PreForm server's local port is blocked for agents. Set BT_PREFORM_PORT to your adapter's port.
PREFORM_PORT = os.environ.get("BT_PREFORM_PORT", "PREFORM_PORT")

PY = Path(sys.executable).as_posix()
BLOCK = re.compile(r"<!-- (genome|role|pack) -->.*?<!-- /\1 -->", re.S)

ARM_RULE = {
    "single": "You work alone. Your deliverables are this run's submission.",
    "best_of_n": ("You are one of six agents working independently in this run; you cannot contact the others. "
                  "Each of you delivers its own files. When all six have stopped, the harness runs the judge's pre-check (visible "
                  "load cases only, coarse) on each agent's deliverables; the run's submission is the one with the "
                  "lowest H among those that pass the gates; if the pre-check is unavailable or all fail, a randomly "
                  "chosen agent's (seeded)."),
    "collective": ("You are one of six peers ({peers}) with a shared board and a shared knowledge base. Nobody "
                   "leads and nobody was assigned a role. The run's submission is whatever is in the shared "
                   "deliverables folder when your group's window closes."),
    "planner": ("This run has a lead (p1) and five members ({peers}); communication is routed through p1. The "
                "run's submission is what p1 puts in the deliverables folder."),
}
ROLE = {
    "lead": ("You are the LEAD (a deliberately centralized arm). Assign tasks to p2..p6 with "
             "`post --kind assign \"@p3 ...\"`, read their results, and write the deliverables yourself; only you "
             "can write the deliverables folder."),
    "member": ("You are a member. Follow p1's assignments (assign posts that name you); you can read only p1's "
               "posts and your own, and address only p1. Only p1 writes the deliverables."),
}

# Files the agents must never read or write (budget, identity, ledgers, secrets, judge internals, the other runs).
PROTECTED = ["genome.json", "meter_tokens", "meter_tools", "status.json", "board.jsonl", "board.lock",
             "claude_settings.json", "agent_log.jsonl", "run_manifest.json", "harness_sha256", "gateway_ledger",
             "candidates.jsonl", "finals.jsonl", "arm_designs", "schedule.json", "scheduler",
             ".gateway_key", "gateway_key", "hmac", "sealed_case", "bonetwin/targets", "bonetwin/sim/", "sim_mock",
             "score_design", "export_stl.py", "control_design", "preflight", "control_work", "/sealed",
             "hashes.log", "analysis/centralization", "harness/run", "harness/sealed", "bonetwin/harness/",
             "harness_design/run", "harness_design/sealed", "/submissions",
             "sealed_private", "tool_calls.jsonl", "tool_log", "sessions.jsonl", "manipulation_check",
             "lean_gate.py", "train_widths.py", "preform_tool.py", "freecadcmd", "human_posts", "voxel_queue",
             "voxel.lock", "models.jsonl", "rate_limit.jsonl", "usage_events", "touch.log", "rules_manifest",
             "anthropic_api_key", "api_spend", "billing.jsonl", "sim/probe", "bt_compute.py", "compute_ledger",
             PREFORM_PORT, "seen_notices", "notices_due", "kb_growth", "precheck_log"]


def blocked_for(root, run_id, arm, aid, judge_blocked=()):
    """Substring markers plus regexes: any path through run/ other than this agent's own folder and its arm's
    shared kb/ and deliverables/ folders; judge internals; direct Brev / WSL calls."""
    own = re.escape(f"{run_id}/{arm}/agents/{aid}".lower())
    shared = re.escape(f"{run_id}/{arm}/".lower())
    return sorted(set(PROTECTED) | set(judge_blocked)) + [
        rf"re:/run/(?!({own}|{shared}kb|{shared}deliverables)(?![\w-]))", r"re:(^|[\s\"'=])run/",
        r"re:\.sha256\b", r"re:(^|[\s;&|(\"'])(brev|wsl)(\.exe)?(\s|$|[\"'])"]


def genome_block(g, cfg):
    peers = ", ".join(g["peers"]) if g.get("peers") else ""
    rule = ARM_RULE[base_arm(g["arm"])].format(peers=peers)
    lean = g.get("leanings") or {}
    bud = cfg["budget"]
    return "\n".join([
        "<!-- genome -->", "## You",
        f"- id: {g['id']} (run {g['run_id']}, arm {g['arm']})",
        f"- your folder: {Path(g['dir']).as_posix()}",
        f"- knowledge base folder: {Path(g['kb_dir']).as_posix()}" + (" (shared with your arm)" if g.get("kb_shared") else ""),
        f"- deliverables folder: {Path(g['deliverables_dir']).as_posix()}",
        f"- leaning, knowledge: {lean.get('knowledge', 'generalist')}",
        f"- leaning, tools: {lean.get('tools', 'generalist')}",
        f"- leaning, communication: {lean.get('communication', 'generalist')}",
        f"- leaning, working style: {lean.get('working_style', 'generalist')}",
        f"- budget: {g['quota']:,} credits (tokens and priced tools); compute: the run shares a "
        f"${bud['compute_usd_per_run']:.0f} GPU cap through bt_compute",
        f"- your run's rule: {rule}",
        "<!-- /genome -->"])


def role_block(g):
    if base_arm(g["arm"]) != "planner":
        return "<!-- role --><!-- /role -->\n\n"
    return f"<!-- role -->\n## Your role\n{ROLE[g['role']]}\n<!-- /role -->\n\n"


def common_body(cfg, public_dir, data_files, judging, deadline_txt):
    bt = f'"{PY}" "{(HERE / "board.py").as_posix()}"'
    tool = f'"{PY}" "{(HERE / "tools" / "bt_tool.py").as_posix()}"'
    reg = json.loads((HERE / "tools.json").read_text(encoding="utf-8"))
    st = cfg.get("_tool_status") or {}
    tools = "\n".join(f"- {k} [{st.get(k, 'available')}]: {v['resource']}. Use: {v['how']}"
                      for k, v in reg["provided"].items())
    not_provided = "\n".join(f"- {k}: {v}" for k, v in reg["not_provided"].items())
    pub = Path(public_dir).as_posix()
    files = ", ".join(cfg["deliverables"]["files"]) + ", and implant.stl or implant.3mf"
    data = ("\n".join(f"  - {pub}/data/{n}" for n in data_files[:40]) +
            (f"\n  - ... {len(data_files) - 40} more under {pub}/data/" if len(data_files) > 40 else "")) \
        if data_files else "  - (none present at launch)"
    return f"""# Brief

## Goal
"{cfg['goal']}"

## Deliverables, within your session window
In your deliverables folder (see "You" below): {files}.
- implant.form: a PreForm .form file of the implant, and alongside it a matching implant.stl or implant.3mf of the
  same implant. As modelled, +Z is the cranial-caudal (superior-inferior) axis and X and Y map to bone axes 1
  and 2.
- material_spec.json: the material (any material; it need not be a Formlabs resin) and its properties, each with a
  cited source.
- report.md: your report; its claims link to evidence in your knowledge base folder.
You have a 90-minute session window from your start (in a board arm, from your group's start); deliverables are
collected when your session ends or the window closes. A missing deliverable then means no submission.
Automated notices arrive 30 and 10 minutes before your window closes.

## How it will be judged
{judging}
Full specification: {pub}/EVAL_SPEC_v1.md and its addenda in {pub}/ (EVAL_SPEC_v1_addendum*.md)

## Knowledge base
Your knowledge base folder is yours to fill in any form; keep the evidence your report links to there.

## Resources (status as of launch)
Board: `{bt} <command>` (read, post, wait, need, transfer, balance; board commands work only if your arm has a
board). Tools: `{tool} list` | `{tool} <tool> ...`.
{tools}
Not provided:
{not_provided}
Data (read-only): {cfg['published_data']['label']}
{data}
Bone targets (visible cases only): {pub}/targets/

## Rules
Work only in your folder, your knowledge base folder and your deliverables folder. Do not read other agents' or
runs' folders, the judge's internals or test designs, any sealed file, or the meter's files; the meter blocks them.
Do not start subagents. Call GPU compute only through bt_compute (not brev or wsl directly). Every tool call is
logged and priced against your budget. To wait for others, use `{bt} wait` (at most 100 s), not sleep loops.
"""


def render(g, body, cfg):
    return body + "\n" + genome_block(g, cfg) + "\n\n" + role_block(g) + "<!-- pack --><!-- /pack -->\n"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_identical(briefs):
    commons = {k: sha(BLOCK.sub("", v)) for k, v in briefs.items()}
    full = {k: sha(v) for k, v in briefs.items()}
    uniq = set(commons.values())
    return len(uniq) == 1, (uniq.pop() if len(uniq) == 1 else sorted(uniq)), full


def claude_settings(meter_cmd):
    return {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": meter_cmd}]}]},
            "permissions": {"deny": ["Task", "Agent"]}}


def write_agent(g, brief_text):
    d = Path(g["dir"])
    d.mkdir(parents=True, exist_ok=True)
    Path(g["kb_dir"]).mkdir(parents=True, exist_ok=True)
    Path(g["deliverables_dir"]).mkdir(parents=True, exist_ok=True)
    write_json(d / "genome.json", g)
    (d / "BRIEF.md").write_text(brief_text, encoding="utf-8")
    meter_cmd = f'"{PY}" "{(HERE / "meter.py").as_posix()}" hook'
    write_json(d / "claude_settings.json", claude_settings(meter_cmd))


def finish_genome(g, root, run_id, arm, target, public_dir, model, dim, stop_at, peers, cfg=None):
    from common import agent_dir, arm_dir, board_path
    cfg = cfg or {}
    g = dict(g)
    shared = base_arm(arm) in SHARED_BOARD_ARMS
    ad = arm_dir(root, run_id, arm)
    me = agent_dir(root, run_id, arm, g["id"])
    g.update(arm=arm, run_id=run_id, target=target, root=str(root), model=model, dim=dim, dir=str(me),
             arm_dir=str(ad), board=str(board_path(root, run_id, arm)), board_shared=shared,
             peers=peers if shared else [], public_dir=str(public_dir),
             target_file=(Path(public_dir) / "targets" / f"{target}.json").as_posix(),
             kb_dir=str(ad / "kb" if shared else me / "kb"), kb_shared=shared,
             deliverables_dir=str(ad / "deliverables" if shared else me / "deliverables"),
             stop_at=stop_at.isoformat(),
             blocked=blocked_for(root, run_id, arm, g["id"], (cfg.get("judge") or {}).get("blocked", [])))
    if base_arm(arm) == "planner":
        g["arm_label"] = PLANNER_LABEL
        g["lead"] = peers[0]
        if g.get("role") != "lead":  # routing: only the lead writes (or reads) the deliverables folder
            g["blocked"] = [f"{run_id}/{arm}/deliverables".lower()] + g["blocked"]
    return g
