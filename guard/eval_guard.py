"""Evaluator guard: a PreToolUse hook that limits the orchestrating Claude session (and every subagent it
spawns) to evaluation, infrastructure and compute during the open-ended run.

Deterministic rules, no model judgement. Fail-closed: the hook is registered with onFailure=block, so a crash
here blocks the tool call.

R1 Arm internals are a black box: any tool call that names an arm path (run dirs, knowledge bases, boards,
   transcripts, submissions) is DENIED until UNLOCK (after the 07:00 deadline and sealing). Aggregate metrics
   under harness_open/metrics are always readable.
R2 Arm internals are never written by us: after UNLOCK, reads are allowed but any write-like call that names an
   arm path stays DENIED.
R3 No messages into arms: board posting commands are always DENIED.
R4 Compute: bt_compute actions that touch a running arm instance (exec, copy-to, copy-from, start for an arm,
   stop) are DENIED for us; the reaper and the harness manage arm instances. quote and ls are allowed.
   Judge instances (names starting 'judge') are allowed.
R5 Frozen evidence is never written: raw data, frozen scripts and specs, targets, sealed folders, hash manifests.
R6 Tamper protection: this script, the settings file that registers it, and the guard log are never written.
Every call is logged to guard_log.jsonl with the decision and the rule.
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

LOG = Path(os.environ.get("EVAL_GUARD_LOG") or Path(__file__).resolve().parent / "guard_log.jsonl")
UNLOCK = datetime.fromisoformat(os.environ.get("EVAL_GUARD_UNLOCK", "2026-11-01T06:45"))  # local time

ARM = [  # R1/R2: arm internals
    r"harness_open[\\/]+run\b", r"harness_open[\\/]+kb\b", r"harness_open[\\/]+boards?\b",
    r"harness_open[\\/]+submissions\b", r"harness_open[\\/]+transcripts?\b", r"harness_open[\\/]+agents?\b",
]
ALWAYS_READ_OK = [r"harness_open[\\/]+metrics\b"]
FROZEN = [  # R5
    r"breakerspace data", r"analysis[\\/]+ingest\.py", r"analysis[\\/]+PROTOCOL\.md", r"analysis[\\/]+track_dots\.py",
    r"analysis[\\/]+raw_data_sha256\.txt", r"sim[\\/]+EVAL_SPEC\.md", r"sim[\\/]+fit_calibration\.py",
    r"sim[\\/]+calibration_defaults\.json", r"sim[\\/]+run_spec\.json", r"sim[\\/]+desirability\.json",
    r"bonetwin[\\/]+targets[\\/]", r"harness[\\/]+sealed\b", r"harness[\\/]+run\b", r"sealed_private",
    r"FREEZE_MANIFEST", r"harness_sha256",
]
TAMPER = [  # R6
    r"guard[\\/]+eval_guard\.py", r"guard[\\/]+guard_log\.jsonl",
    r"\.claude[\\/]+settings\.local\.json",
]
WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
READ_TOOLS = {"Read", "Grep", "Glob", "LS"}
SHELL_TOOLS = {"Bash", "PowerShell"}
WRITE_VERBS = re.compile(
    r"(>|\btee\b|\brm\b|\bmv\b|\bcp\b|\bdel\b|\bcopy\b|\bmove\b|\brmdir\b|\bmkdir\b|\btouch\b|\bsed\s+-i|"
    r"Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item|Rename-Item|Clear-Content|"
    r"\bicacls\b|\battrib\b|\.write|open\([^)]*['\"][wa]|shutil\.|os\.remove|unlink)", re.I)
BOARD_POST = re.compile(r"board\.py\b[^\n]*\bpost\b|--as\s+\S+", re.I)
BT_ARM_ACTION = re.compile(r"bt_compute\.py\b[^\n]*\b(exec|copy-to|copy-from|start|stop)\b", re.I)
JUDGE_NAME = re.compile(r"--name\s+[\"']?judge", re.I)
ARM_START = re.compile(r"--arm\s+(?!judge)", re.I)


def norm(s):
    return (s or "").replace("/", "\\")


def any_match(patterns, text):
    return next((p for p in patterns if re.search(p, text, re.I)), None)


def decide(tool, ti, now):
    if tool in WRITE_TOOLS:
        target = norm(ti.get("file_path") or ti.get("notebook_path") or "")
        if any_match(TAMPER, target):
            return "deny", "R6 tamper protection"
        if any_match(FROZEN, target):
            return "deny", "R5 frozen evidence"
        if any_match(ARM, target):
            return "deny", "R2 never write arm internals" if now >= UNLOCK else "R1 arm internals are a black box"
        return "allow", ""
    if tool in READ_TOOLS:
        target = norm(" ".join(str(ti.get(k, "")) for k in ("file_path", "path", "pattern", "glob")))
        if any_match(ALWAYS_READ_OK, target) and not any_match(ARM, target.replace("metrics", "")):
            return "allow", ""
        if any_match(ARM, target) and now < UNLOCK:
            return "deny", "R1 arm internals are a black box until 07:15"
        return "allow", ""
    if tool in SHELL_TOOLS:
        cmd = norm(ti.get("command", ""))
        if BOARD_POST.search(cmd):
            return "deny", "R3 no messages into arms"
        if BT_ARM_ACTION.search(cmd) and not JUDGE_NAME.search(cmd) and (
                ARM_START.search(cmd) or not re.search(r"\bstart\b", cmd, re.I)):
            return "deny", "R4 arm compute is managed by the harness and reaper, not by the evaluator"
        writes = bool(WRITE_VERBS.search(cmd))
        if writes and any_match(TAMPER, cmd):
            return "deny", "R6 tamper protection"
        if writes and any_match(FROZEN, cmd):
            return "deny", "R5 frozen evidence"
        if any_match(ARM, cmd):
            if now < UNLOCK:
                return "deny", "R1 arm internals are a black box until 07:15"
            if writes:
                return "deny", "R2 never write arm internals"
        return "allow", ""
    return "allow", ""


def main():
    data = json.loads(sys.stdin.read() or "{}")
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    now = datetime.now()
    decision, rule = decide(tool, ti, now)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now.isoformat(timespec="seconds"), "session": data.get("session_id"),
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
