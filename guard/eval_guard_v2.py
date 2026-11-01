"""Evaluator guard v2 = v1 (eval_guard.py, unchanged) + R7 and wider tamper protection.

R7 The compute ledger records the commands agents run on their GPUs, so it is arm-internal content. Until UNLOCK
   (07:15) any tool call that names compute_ledger.jsonl is DENIED, except running compute\\ledger_costs.py, which
   prints cost fields only. After UNLOCK reads are allowed; writes never.
R6+ The evaluator may not write eval_guard_v2.py or ledger_costs.py (in addition to v1's protected files).
Everything else is decided by v1's rules. Same log, same fail-closed registration.
"""
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("eval_guard_v1", HERE / "eval_guard.py")
g1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g1)

LEDGER = re.compile(r"compute_ledger\.jsonl", re.I)
COST_READER = re.compile(r"ledger_costs\.py", re.I)
TAMPER2 = [r"guard[\\/]+eval_guard_v2\.py", r"compute[\\/]+ledger_costs\.py"]


def decide(tool, ti, now):
    if tool in g1.WRITE_TOOLS:
        target = g1.norm(ti.get("file_path") or ti.get("notebook_path") or "")
        if g1.any_match(TAMPER2, target):
            return "deny", "R6 tamper protection (v2)"
        if LEDGER.search(target):
            return "deny", "R7 the compute ledger is never written by the evaluator"
    elif tool in g1.READ_TOOLS:
        target = " ".join(str(ti.get(k, "")) for k in ("file_path", "path", "pattern", "glob"))
        if LEDGER.search(target) and now < g1.UNLOCK:
            return "deny", "R7 compute ledger holds agents' commands; use ledger_costs.py until 07:15"
    elif tool in g1.SHELL_TOOLS:
        cmd = g1.norm(ti.get("command", ""))
        writes = bool(g1.WRITE_VERBS.search(cmd))
        if writes and g1.any_match(TAMPER2, cmd):
            return "deny", "R6 tamper protection (v2)"
        if LEDGER.search(cmd):
            if writes:
                return "deny", "R7 the compute ledger is never written by the evaluator"
            if now < g1.UNLOCK:
                return "deny", "R7 compute ledger holds agents' commands; use ledger_costs.py until 07:15"
    return g1.decide(tool, ti, now)


def main():
    data = json.loads(sys.stdin.read() or "{}")
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    now = datetime.now()
    decision, rule = decide(tool, ti, now)
    with g1.LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now.isoformat(timespec="seconds"), "v": 2, "session": data.get("session_id"),
                            "agent": data.get("agent_id") or data.get("subagent_type"), "tool": tool,
                            "decision": decision, "rule": rule,
                            "target": str(ti.get("file_path") or ti.get("path") or ti.get("command") or "")[:300]})
                + "\n")
    if decision == "deny":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": f"Evaluator guard: {rule}"}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
