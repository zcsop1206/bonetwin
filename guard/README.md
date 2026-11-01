# Evaluator guard

A Claude Code PreToolUse hook that keeps an evaluating session (and its subagents) out of an experiment's arms. The rules are regexes with no model judgement. `eval_guard.py` holds rules R1 to R6, and `eval_guard_v2.py` adds R7 plus wider tamper protection, then falls through to v1. Register v2.

The path patterns are the hackathon's own (`harness_open/run`, `sim/EVAL_SPEC.md` and so on). Edit `ARM`, `FROZEN` and `TAMPER` for your layout.

## Register

In `.claude/settings.local.json` of the project the evaluator works in:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read|Grep|Glob|LS|Edit|Write|NotebookEdit|MultiEdit|Bash|PowerShell",
        "hooks": [
          {
            "type": "command",
            "command": "py -3 \"<repo>/guard/eval_guard_v2.py\"",
            "timeout": 20,
            "onFailure": "block",
            "statusMessage": "Evaluator guard"
          }
        ]
      }
    ]
  }
}
```

`onFailure: block` is what makes it fail closed: a crash in the script blocks the tool call.

## Configure

| Environment variable | Default | Meaning |
|---|---|---|
| `EVAL_GUARD_LOG` | `guard_log.jsonl` next to the script | Every call is logged here with its decision. It holds commands, so keep it out of version control. |
| `EVAL_GUARD_UNLOCK` | `2026-11-01T06:45` | Local time when reads of arm internals open. Writes stay denied. |

## Known limits

It matches text, not behaviour, so it has false positives and it can be bypassed. A shell command that names an arm path and contains any `>`, even `2>/dev/null`, counts as a write. A script that reads a protected path without naming it on the command line is not seen at all. Treat it as a guard against accidents, not as a security boundary.
