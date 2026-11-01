"""Per-agent quota meter for the DESIGN run (adapted from ../harness/meter.py): counts credits, refuses tools
when the balance cannot pay. Gateway calls (frame, planestress) and STL export are priced inside board.py.
Blocked entries are substrings, or regexes when prefixed "re:".

Credits spent = sum over token kinds of credit_weight[kind] * tokens[kind]  +  tool charges.
Balance = quota + transfers received - transfers sent - credits spent. Transfers are public board posts.

Ledgers live in the agent's directory:
    genome.json          quota, tool prices, credit weights, board path, blocked paths (written by the launcher)
    meter_tokens.json    token totals, written only by the runner
    meter_tools.jsonl    one line per charged tool call, appended by the hook / Nemotron loop / board.py

CLI:
    python meter.py hook      Claude Code PreToolUse hook (reads hook JSON on stdin, env BT_AGENT_DIR);
                              exit 2 blocks the tool call with a reason
    python meter.py status --agent-dir DIR
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_json, utc_now, write_json  # noqa: E402

TOKEN_KINDS = ["input", "cache_creation", "cache_read", "output"]


class Meter:
    def __init__(self, agent_dir):
        if not agent_dir:
            raise SystemExit("meter: no agent directory")
        self.dir = Path(agent_dir)
        self.genome = load_json(self.dir / "genome.json")
        self.tokens_file = self.dir / "meter_tokens.json"
        self.tools_file = self.dir / "meter_tools.jsonl"

    # -- ledgers
    def tokens(self):
        return load_json(self.tokens_file, {k: 0 for k in TOKEN_KINDS})

    def record_tokens(self, totals):
        write_json(self.tokens_file, {k: int(totals.get(k, 0)) for k in TOKEN_KINDS} | {"exempt": int(totals.get("exempt", 0))})

    def tool_spend(self):
        if not self.tools_file.exists():
            return 0.0
        total = 0.0
        for line in self.tools_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                total += json.loads(line)["price"]
        return total

    def token_spend(self):
        t = self.tokens()
        w = self.genome["credit_weights"]
        return sum(w.get(k, 1.0) * t.get(k, 0) for k in TOKEN_KINDS) - t.get("exempt", 0)

    def transfers(self):
        bp = self.genome.get("board")
        if not bp or not self.genome.get("board_shared"):
            return 0, 0
        from board import Board
        me = self.genome["id"]
        got = sent = 0
        for p in Board(bp).read(kind="transfer"):
            amt = int(p["meta"].get("amount", 0))
            if p["author"] == me:
                sent += amt
            if p["meta"].get("to") == me:
                got += amt
        return got, sent

    def balance(self):
        got, sent = self.transfers()
        return self.genome["quota"] + got - sent - self.token_spend() - self.tool_spend()

    def status(self):
        got, sent = self.transfers()
        return {"agent": self.genome["id"], "quota": self.genome["quota"], "received": got, "sent": sent,
                "token_credits": round(self.token_spend()), "tool_credits": round(self.tool_spend()),
                "balance": round(self.balance()), "tool_prices": self.genome["tool_prices"],
                "credit_weights": self.genome["credit_weights"]}

    def charge_tool(self, tool):
        price = float(self.genome["tool_prices"].get(tool, 0))
        bal = self.balance()
        if bal <= 0:
            return False, f"refused by meter: quota exhausted (balance {bal:.0f}). Run board.py final now."
        if price > bal:
            return False, f"refused by meter: {tool} costs {price:.0f}, balance {bal:.0f}"
        if price:
            with self.tools_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": utc_now(), "tool": tool, "price": price}) + "\n")
        return True, ""

    def refund(self, tool):
        price = float(self.genome["tool_prices"].get(tool, 0))
        if price:
            with self.tools_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": utc_now(), "tool": tool, "price": -price, "refund": True}) + "\n")

    # -- access rule (arms must not read each other's files or the sealed folder)
    def blocked(self, text):
        # escaped quotes first (json.dumps turns " into \" and a quote must not become a slash: idiom test 19:15)
        norm = text.replace('\\"', '"').replace("\\\\", "/").replace("\\", "/").lower()
        for b in self.genome.get("blocked", []):
            if b.startswith("re:"):
                if re.search(b[3:], norm):
                    return b
            elif b.lower() in norm:
                return b
        if "../" in norm or "..\\" in text:
            return "relative parent paths (..)"
        return None


def classify_claude_tool(name, tool_input):
    """Map a Claude Code tool call onto a priced tool, or None if free, or 'deny'."""
    if name in ("Task", "Agent"):
        return "deny"
    if name == "WebSearch":
        return "web_search"
    if name == "WebFetch":
        return "web_fetch"
    if name == "Bash" or name == "PowerShell":
        cmd = str(tool_input.get("command", ""))
        if "board.py" in cmd or "bt_tool.py" in cmd:
            return None  # board.py charges for itself (posts, gateway runs, STL export)
        low = cmd.lower()
        if "python" in low or "py -3" in low or low.startswith("py "):
            return "python"
        return "bash"
    return None


def log_call(m, name, tin, tool, verdict):
    """Every tool call, allowed or refused, for the affinity and audit analysis (URLs and queries in full)."""
    rec = {"ts": utc_now(), "agent": m.genome.get("id"), "tool": name, "priced_as": tool, "verdict": verdict,
           "session": os.environ.get("CLAUDE_SESSION_ID") or None}
    for k in ("url", "query", "file_path", "pattern", "path"):
        if tin.get(k):
            rec[k] = str(tin[k])[:500]
    if tin.get("command"):
        rec["command"] = str(tin["command"])[:600]
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:  # redact: the key may be in this process's env (overflow billing), never in a log
        rec = json.loads(json.dumps(rec).replace(k, "[REDACTED]"))
    try:
        with (m.dir / "tool_calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def notice_check(m):
    """Per-session notices (cap-60, cap-15 min) written by the scheduler at start; plus any public notices."""
    import datetime as _dt
    now = _dt.datetime.now().astimezone()
    notes = [n for n in (load_json(m.dir / "notices_due.json", []) or [])
             if _dt.datetime.fromisoformat(n["due"]) <= now]
    pub = Path(m.genome.get("public_dir", "")) / "notices.json"
    if m.genome.get("public_dir") and pub.exists():
        notes += load_json(pub, []) or []
    if not notes:
        return None
    seen_f = m.dir / "seen_notices.json"
    seen = load_json(seen_f, []) or []
    new = [n for n in notes if n["id"] not in seen]
    if not new:
        return None
    write_json(seen_f, seen + [n["id"] for n in new])
    return "\n".join(n["text"] for n in new)


def hook():
    data = json.loads(sys.stdin.read() or "{}")
    m = Meter(os.environ.get("BT_AGENT_DIR"))
    name = data.get("tool_name", "")
    tin = data.get("tool_input") or {}
    if data.get("session_id"):
        os.environ["CLAUDE_SESSION_ID"] = str(data["session_id"])
    note = notice_check(m)
    if note:  # identical automated notices: shown once to every agent as the reason its next call was held
        log_call(m, name, tin, None, "held_for_notice")
        print(note + "\n(This tool call was held only to show you this notice; repeat it if you still need it.)",
              file=sys.stderr)
        sys.exit(2)
    try:
        _hook(m, name, tin)
    except SystemExit as e:
        log_call(m, name, tin, classify_claude_tool(name, tin), "allowed" if not e.code else "refused")
        raise


def _hook(m, name, tin):
    hit = m.blocked(json.dumps(tin))  # checked first, so protected files stay blocked even when broke
    if not hit and name in ("Bash", "PowerShell"):
        cmd = str(tin.get("command", ""))
        if "BT_AGENT" in cmd or "BT_BOARD" in cmd or " --as " in f" {cmd} " or "--board" in cmd:
            hit = "identity or board environment"
        elif "BT_ROOT" in cmd or "BT_RUN" in cmd or "BT_GATEWAY" in cmd.upper():
            hit = "run or gateway environment"
        elif "ANTHROPIC" in cmd.upper() or re.search(r"(^|[\s;&|(])(env|printenv|set)(\s*$|\s*[;&|)])", cmd) \
                or "os.environ" in cmd or "env:" in cmd.lower() or "getenv" in cmd.lower():
            hit = "environment dump"
    if not hit and name in ("Write", "Edit", "NotebookEdit"):
        body = json.dumps(tin)
        if "os.environ" in body or "getenv" in body.lower() or "ANTHROPIC" in body.upper():
            hit = "environment access in a script"
    if hit:
        print(f"refused: this path is outside your arm ({hit}). Work only in your own folder and the shared "
              "read-only files named in BRIEF.md.", file=sys.stderr)
        sys.exit(2)
    tool = classify_claude_tool(name, tin)
    if tool == "deny":
        print("refused: subagents are not allowed; do the work yourself.", file=sys.stderr)
        sys.exit(2)
    ok, msg = m.charge_tool(tool) if tool else (m.balance() > 0, "refused by meter: quota exhausted. "
                                                 "Write your justification and run board.py final now.")
    if not ok:
        # still allow submitting the answer when broke
        c = str(tin.get("command", ""))
        if name in ("Bash", "PowerShell") and "board.py" in c and (" final" in c or " submit" in c or " balance" in c):
            sys.exit(0)
        if name in ("Write", "Read") and m.dir.as_posix().lower() in json.dumps(tin).replace("\\\\", "/").lower():
            sys.exit(0)  # writing/reading the answer file in its own folder
        print(msg, file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["hook", "status"])
    ap.add_argument("--agent-dir", default=os.environ.get("BT_AGENT_DIR"))
    a = ap.parse_args()
    if a.cmd == "hook":
        hook()
    else:
        print(json.dumps(Meter(a.agent_dir).status(), indent=2))


if __name__ == "__main__":
    main()
