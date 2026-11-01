"""Run one DESIGN agent until it writes its final design + justification, runs out of quota, or hits the safety
cap. Spawned (detached) by scheduler.py. Adapted from ../harness/agent_runner.py.

Modes, from genome.json "model": claude (headless `claude -p`, stream-json, PreToolUse hook = meter) and mock
(no API; fake agents that drive the real board.py CLI, for smoke tests). The Nemotron loop of the prediction run
is not ported (force_model is claude for tonight).

Stop rule (user decision): no time budget to burn. The agent stops when it has run `board.py final` (final.json),
or its balance reaches zero, or the safety cap (05:00) arrives. A session that ends without a final is resumed up
to max_resumes times.

Token metering fix (audit of the Oct 31 prediction logs): stream-json `assistant` events carry the output_tokens
of the first streamed chunk only (meters saw ~100 output tokens where the session's `result` reported ~9,000).
Mid-session the runner now estimates output as max(reported, content chars / 4) per message, and replaces each
session's totals with the exact `result` usage when the session ends.
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HERE, load_config, load_json, utc_now, write_json  # noqa: E402
from meter import Meter  # noqa: E402
import billing  # noqa: E402

FIRST_PROMPT = "Read BRIEF.md in this folder and do the task it describes."
RESUME_PROMPT = ("Continue. Your session stopped before you ran `board.py done`. Re-read BRIEF.md, check `balance` "
                 "and your folders, and carry on toward the deliverables; run `board.py done` when you are finished.")
CRASH_PROMPT = ("Continue. Your session was interrupted by a harness restart. Re-read BRIEF.md, check `balance` and "
                "your folders, and carry on toward the deliverables; run `board.py done` when you are finished.")
TOKEN_KINDS = ["input", "cache_creation", "cache_read", "output"]


def detect_limit(line):
    """A usage-window / rate-limit signal in one stream-json line (patterns from run_tracks.py). Returns a dict or None."""
    try:
        msg = json.loads(line)
    except Exception:
        low = line.lower()
        if "usage limit" in low or "limit reached" in low or "hit your limit" in low or "rate limit" in low:
            return {"kind": "text", "detail": line.strip()[:200]}
        return None
    if msg.get("type") == "rate_limit_event":
        info = msg.get("rate_limit_info") or {}
        if info.get("status") not in (None, "allowed", "allowed_warning"):
            fh = (info.get("unifiedWindows") or {}).get("five_hour") or {}
            return {"kind": "rate_limit_event", "status": info.get("status"), "resets_at": fh.get("resetsAt"),
                    "utilization": fh.get("utilization")}
    if msg.get("type") == "result" and msg.get("is_error"):
        res = str(msg.get("result", "")).lower()
        if "limit" in res or "429" in res or "overloaded" in res:
            return {"kind": "result_error", "detail": res[:200]}
    return None


class Runner:
    def __init__(self, agent_dir):
        self.dir = Path(agent_dir).resolve()
        self.genome = load_json(self.dir / "genome.json")
        self.cfg = load_config()
        self.meter = Meter(self.dir)
        self.stop_at = dt.datetime.fromisoformat(self.genome["stop_at"])
        self.hard = self.stop_at  # the genome's stop_at is the hard deadline; --stop-at sets the session cap
        self.tokens = {k: 0 for k in TOKEN_KINDS} | {"exempt": 0}
        self.closed = {k: 0 for k in TOKEN_KINDS}  # exact totals of finished sessions (from `result`)
        self.msg_usage = {}  # current session: message id -> (usage, est_output)
        self.exempt = 0.0
        self.overhead = None
        self.seen_msgs = set()
        self.log = self.dir / "agent_log.jsonl"
        env = {k: v for k, v in os.environ.items()
               if k not in ("BT_GATEWAY_KEY", "BT_GATEWAY_ADMIN", billing.ENV)}  # subscription by default
        self.env = dict(env, BT_AGENT=self.genome["id"], BT_AGENT_DIR=str(self.dir),
                        BT_BOARD=self.genome["board"] if self.genome.get("board_shared") else "")
        self.sessions = self.dir / "sessions.jsonl"  # one line per model process: pid, session id, start, end
        self.recover = False
        self.last_model = None
        self.billing = "subscription"  # or "api" (overflow, child env only)
        self.api_until = None
        self.api_session_usd = 0.0
        self.live_name = f"{self.genome.get('run_id')}_{self.genome.get('arm')}_{self.genome['id']}"

    def log_session(self, **rec):
        with self.sessions.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dict(rec, ts=utc_now(), runner_pid=os.getpid())) + "\n")

    def status(self, state, **extra):
        write_json(self.dir / "status.json", {"agent": self.genome["id"], "model": self.genome["model"],
                                              "state": state, "ts": utc_now(), "tokens": self.tokens,
                                              "runner_pid": os.getpid(),
                                              "balance": round(self.meter.balance()), **extra})

    def now(self):
        return dt.datetime.now().astimezone()

    def has_final(self):
        f = load_json(self.dir / "final.json")
        return bool(f and (f.get("run_id") or f.get("done")))

    # ------------------------------------------------------------ token accounting
    def _push_tokens(self):
        t = {k: self.closed[k] for k in TOKEN_KINDS}
        for u, est in self.msg_usage.values():
            t["input"] += u.get("input_tokens", 0)
            t["cache_creation"] += u.get("cache_creation_input_tokens", 0)
            t["cache_read"] += u.get("cache_read_input_tokens", 0)
            t["output"] += max(u.get("output_tokens", 0), est)
        t["exempt"] = int(self.exempt)
        self.tokens = t
        self.meter.record_tokens(t)

    def on_assistant(self, msg):
        m = msg.get("message") or {}
        model = m.get("model")
        if model:
            want = self.cfg.get("claude_model")
            if model != self.last_model:
                with (self.dir / "models.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": utc_now(), "model": model, "expected": want,
                                        "switch": self.last_model is not None, "mismatch": bool(want) and
                                        not str(model).startswith(want)}) + "\n")
                self.last_model = model
        u = m.get("usage") or {}
        mid = m.get("id") or f"anon{len(self.msg_usage)}"
        chars = 0
        for block in m.get("content") or []:
            if isinstance(block, dict):
                chars += len(block.get("text") or "") + len(block.get("thinking") or "")
                if block.get("type") == "tool_use":
                    chars += len(json.dumps(block.get("input") or {}))
        prev = self.msg_usage.get(mid, ({}, 0))[1]
        if mid not in self.seen_msgs:
            usd = billing.list_price(self.cfg, u)
            with (self.dir / "billing.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": utc_now(), "msg": mid, "billing": self.billing, "model": m.get("model"),
                                    "usd_list_price_est": round(usd, 5)}) + "\n")
            if self.billing == "api":
                self.api_session_usd += usd
                billing.set_live(self.genome["root"], self.live_name, round(self.api_session_usd, 4))
        self.msg_usage[mid] = (u, prev + chars // 4)
        if mid not in self.seen_msgs:
            self.seen_msgs.add(mid)
            w = self.genome["credit_weights"]
            inp, cc, cr = (u.get("input_tokens", 0), u.get("cache_creation_input_tokens", 0),
                           u.get("cache_read_input_tokens", 0))
            if self.cfg.get("first_turn_overhead_exempt"):
                # Claude Code's own system prompt and tool definitions are not the agent's work
                if self.overhead is None:
                    self.overhead = inp + cc + cr
                    self.exempt += w.get("cache_creation", 1.0) * cc + w.get("input", 1.0) * inp
                self.exempt += w.get("cache_read", 0.0) * min(cr, self.overhead)
        self._push_tokens()

    def on_result(self, msg):
        if self.billing == "api":
            billing.record_closed(self.genome["root"], {"ts": utc_now(), "agent": self.live_name,
                                                        "usd": msg.get("total_cost_usd") or self.api_session_usd,
                                                        "source": "result" if msg.get("total_cost_usd") else "estimate"})
            billing.set_live(self.genome["root"], self.live_name, None)
            self.api_session_usd = 0.0
        u = msg.get("usage") or {}
        if not u:
            return
        self.closed["input"] += u.get("input_tokens", 0)
        self.closed["cache_creation"] += u.get("cache_creation_input_tokens", 0)
        self.closed["cache_read"] += u.get("cache_read_input_tokens", 0)
        self.closed["output"] += u.get("output_tokens", 0)
        self.msg_usage = {}
        self._push_tokens()

    # ------------------------------------------------------------ claude
    def claude_cmd(self, resume_id=None):
        exe = shutil.which("claude") or "claude"
        cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "auto",
               "--settings", str(self.dir / "claude_settings.json"),
               "--disallowedTools", "Task", "Agent",
               "--add-dir", str(HERE), "--add-dir", self.genome["public_dir"]]
        if self.cfg.get("claude_model"):
            cmd += ["--model", self.cfg["claude_model"]]
        if resume_id:
            cmd += ["--resume", resume_id]
        return cmd

    def run_claude(self, recover=False):
        """Resumes count against max_resumes; usage-window pauses do not (subscription pacing, as in
        run_tracks.py): on a usage-limit signal the runner logs it, waits for the window to reset (resetsAt + 2 min,
        else limit_retry_minutes), and resumes the same session. Never past the safety cap or the quota."""
        session = self.last_session() if recover else None
        attempt, pauses = (1 if session else 0), 0
        while attempt <= self.cfg.get("max_resumes", 3) and pauses <= self.cfg.get("max_limit_pauses", 30):
            if self.now() >= self.stop_at or self.meter.balance() <= 0 or self.has_final():
                break
            prompt = CRASH_PROMPT if (recover and attempt == 1 and not pauses) else (RESUME_PROMPT if attempt else FIRST_PROMPT)
            if self.billing == "api" and self.api_until and time.time() >= self.api_until:
                self.set_billing("subscription", "usage window reset")
            env = self.env
            if self.billing == "api":
                env, ok = billing.child_env(self.env, self.cfg)  # the key lives only in this child's env
                if not ok:
                    self.set_billing("subscription", "key unavailable")
                    env = self.env
            proc = subprocess.Popen(self.claude_cmd(session if session else None), cwd=self.dir, env=env,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace",
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
            proc.stdin.write(prompt)
            proc.stdin.close()
            self.log_session(event="start", attempt=attempt, pid=proc.pid, resume=session, billing=self.billing)
            key = env.get(billing.ENV)
            holder = {"session": session, "limit": None, "api_cap": False, "safe": False, "switch_back": False}

            def reader():
                with self.log.open("a", encoding="utf-8") as out:
                    for line in proc.stdout:
                        if key and key in line:
                            line = line.replace(key, "[REDACTED]")
                        out.write(line)
                        out.flush()
                        hit = detect_limit(line)
                        if hit:
                            holder["limit"] = hit
                            self.log_limit(hit)
                        try:
                            msg = json.loads(line)
                        except Exception:
                            continue
                        if msg.get("session_id") and msg["session_id"] != holder["session"]:
                            holder["session"] = msg["session_id"]
                            self.log_session(event="session", session_id=msg["session_id"], attempt=attempt)
                        if msg.get("type") == "assistant":
                            self.on_assistant(msg)
                            holder["safe"] = False
                        elif msg.get("type") == "user":
                            holder["safe"] = True  # a tool result is in: a turn boundary (safe point)
                        elif msg.get("type") == "result":
                            self.on_result(msg)

            th = threading.Thread(target=reader, daemon=True)
            th.start()
            reason = None
            while proc.poll() is None:
                if self.meter.balance() <= 0:
                    reason = "capped"
                elif self.now() >= self.stop_at:
                    reason = "safety_cap"
                elif self.billing == "api" and self.api_until and time.time() >= self.api_until and holder.get("safe"):
                    kill_tree(proc)  # subscription window reset: switch back at this turn boundary
                    holder["switch_back"] = True
                    break
                elif self.billing == "api" and not billing.under_cap(self.genome["root"], self.cfg):
                    kill_tree(proc)  # API spend cap: stop using the key, pause instead
                    holder["limit"] = holder["limit"] or {"kind": "api_spend_cap"}
                    holder["api_cap"] = True
                    break
                if reason:
                    kill_tree(proc)
                    break
                self.status("running", attempt=attempt, final=self.has_final(), billing=self.billing)
                time.sleep(2)
            th.join(timeout=10)
            session = holder["session"]
            self.log_session(event="end", attempt=attempt, pid=proc.pid, session_id=session, reason=reason,
                             returncode=proc.returncode, limit=bool(holder["limit"]))
            if reason:
                return reason
            if self.has_final():
                return "done"
            if self.billing == "api" and self.api_session_usd:
                billing.record_closed(self.genome["root"], {"ts": utc_now(), "agent": self.live_name,
                                                            "usd": self.api_session_usd, "source": "estimate (killed)"})
                billing.set_live(self.genome["root"], self.live_name, None)
                self.api_session_usd = 0.0
            if holder.get("switch_back"):
                self.set_billing("subscription", "subscription window reset (switch at a turn boundary)")
                self.api_until = None
                continue  # resume the same session id, same model, without the key; not a resume attempt
            if holder["limit"]:
                pauses += 1
                hit = holder["limit"]
                if not holder.get("api_cap") and self.billing == "subscription" and billing.available(self.cfg) \
                        and billing.under_cap(self.genome["root"], self.cfg, margin=5.0):
                    # overflow: resume the same session on the same model, billed to the API key
                    self.api_until = self.switch_back_time(hit)
                    self.set_billing("api", f"usage window block ({hit.get('kind')})")
                    continue
                if self.billing == "api":
                    self.set_billing("subscription", "API spend cap reached" if holder.get("api_cap") else "API blocked")
                self.wait_window(hit)
                continue  # resume the same session; not a resume attempt
            attempt += 1
        if self.has_final():
            return "done"
        if self.meter.balance() <= 0:
            return "capped"
        return "safety_cap" if self.now() >= self.stop_at else "no_final"

    def switch_back_time(self, hit):
        """When an API session should try the subscription again: the configured reset (04:40 local) if it is
        ahead within 12 h, else the event's own reset time, else limit_retry_minutes from now."""
        cfg_reset = (self.cfg.get("overflow_api") or {}).get("subscription_resets_at")
        if cfg_reset:
            from common import clock_next
            t = clock_next(cfg_reset)
            if (t - self.now()).total_seconds() < 12 * 3600:
                return t.timestamp()
        if hit.get("resets_at"):
            return float(hit["resets_at"]) + 120
        return time.time() + self.cfg.get("limit_retry_minutes", 15) * 60

    def set_billing(self, source, why):
        self.billing = source
        with (self.dir / "billing.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": utc_now(), "event": "billing_switch", "billing": source, "why": why}) + "\n")

    def last_session(self):
        sid = None
        if self.sessions.exists():
            for line in self.sessions.read_text(encoding="utf-8").splitlines():
                try:
                    sid = json.loads(line).get("session_id") or sid
                except json.JSONDecodeError:
                    pass
        return sid

    def log_limit(self, hit):
        rec = dict(hit, ts=utc_now(), agent=self.genome["id"])
        with (self.dir / "rate_limit.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        try:
            with (Path(self.genome["root"]) / "run" / "usage_events.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(dict(rec, arm=self.genome["arm"], run_id=self.genome["run_id"])) + "\n")
        except OSError:
            pass

    def wait_window(self, hit):
        """Pause (non-final status, so the sealer keeps waiting) until the usage window resets."""
        retry = self.cfg.get("limit_retry_minutes", 15) * 60
        if os.environ.get("BT_MOCK_LIMIT_ONCE"):
            retry = 3
        until = time.time() + retry
        if hit.get("resets_at"):
            until = max(time.time() + 10, float(hit["resets_at"]) + 120)
        until = min(until, self.hard.timestamp())
        self.status("waiting_usage_window", resume_at=dt.datetime.fromtimestamp(until).astimezone().isoformat(
            timespec="seconds"), limit=hit)
        t0 = time.time()
        while time.time() < until:
            time.sleep(min(15, max(0.5, until - time.time())))
        self.extend_cap(time.time() - t0)

    def extend_cap(self, paused_s):
        """Pause time is excluded from the session's wall cap (never past the hard deadline); notices move with it."""
        if paused_s <= 0:
            return
        new = min(self.stop_at + dt.timedelta(seconds=paused_s), self.hard)
        shift = new - self.stop_at
        self.stop_at = new
        nd = self.dir / "notices_due.json"
        notes = load_json(nd, []) or []
        if notes:
            write_json(nd, [dict(n, due=(dt.datetime.fromisoformat(n["due"]) + shift).isoformat()) for n in notes])
        with self.sessions.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "cap_extended", "paused_s": round(paused_s), "stop_at": new.isoformat(),
                                "ts": utc_now()}) + "\n")

    # ------------------------------------------------------------ mock (smoke tests, no API)
    def bt(self, *args):
        r = subprocess.run([sys.executable, str(HERE / "board.py"), *args], cwd=self.dir, env=self.env,
                           capture_output=True, text=True, timeout=300)
        with self.log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": utc_now(), "cmd": list(args)[:3], "rc": r.returncode,
                                "out": r.stdout[-400:], "err": r.stderr[-400:]}) + "\n")
        return r

    def mock_spend(self, n=1):
        self.tokens["input"] += 2000 * n
        self.tokens["output"] += 600 * n
        self.meter.record_tokens(self.tokens)

    def mock_design(self, rng):
        schema_dim = self.genome.get("dim", 3)
        n, box = 4, (20.0 if schema_dim == 3 else 40.0)  # the gateway's blocks: 20 mm cube (3-D), 40 mm square (2-D)
        h = box / (n - 1)
        import itertools
        idx = list(itertools.product(range(n), repeat=schema_dim))
        pos = {p: k for k, p in enumerate(idx)}
        nodes = [[c * h for c in p] for p in idx]
        struts = []
        for p, k in pos.items():
            for ax in range(schema_dim):
                q = tuple(c + (1 if a == ax else 0) for a, c in enumerate(p))
                if q in pos:
                    struts.append([k, pos[q], round(rng.uniform(0.6, 2.2 if schema_dim == 3 else 1.6), 3)])
        d = {"schema": "bonetwin-design-v1", "units": "mm", "dim": schema_dim, "material": "rigid10k",
             "box": [box] * schema_dim, "nodes": nodes, "struts": struts}
        if schema_dim == 2:
            d["thickness"] = 8.0
        return d

    def tool(self, *args):
        r = subprocess.run([sys.executable, str(HERE / "tools" / "bt_tool.py"), *args], cwd=self.dir, env=self.env,
                           capture_output=True, text=True, timeout=600)
        with self.log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": utc_now(), "tool": list(args)[:3], "rc": r.returncode,
                                "out": r.stdout[-300:], "err": r.stderr[-300:]}) + "\n")
        return r

    def run_mock(self):
        """Fake agent for the open run: fills its KB, uses a few tools, talks on the board (board arms), writes the
        deliverables if its arm's rule lets it, runs the pre-check (best_of_n), then `done`."""
        g = self.genome
        rng = random.Random(g["id"] + g["arm_dir"])
        shared = g.get("board_shared")
        peers = [x for x in g.get("peers", []) if x != g["id"]]
        kb, dl = Path(g["kb_dir"]), Path(g["deliverables_dir"])
        if os.environ.get("BT_MOCK_LIMIT_ONCE") and g["id"] == "s1":
            hit = detect_limit(json.dumps({"type": "rate_limit_event", "rate_limit_info": {
                "status": "rejected", "unifiedWindows": {"five_hour": {"utilization": 1.0}}}}))
            self.log_limit(hit)
            self.log_session(event="end", attempt=0, pid=os.getpid(), session_id=f"mock-{g['id']}", limit=True)
            self.wait_window(hit)
            self.log_session(event="start", attempt=0, pid=os.getpid(), resume=f"mock-{g['id']}")
        kb.mkdir(parents=True, exist_ok=True)
        for k in range(2):
            (kb / f"{g['id']}_note{k}.md").write_text(f"# {g['id']} note {k}\nsee {g['id']}_note0.md\n",
                                                      encoding="utf-8")
        self.mock_spend()
        self.tool("list")
        self.tool("compute", "--", "--image", "warp", "--dry-run")
        d = self.dir / "d0.json"
        d.write_text(json.dumps(self.mock_design(rng)), encoding="utf-8")
        self.bt("score", "--design", d.name)
        self.mock_spend()
        if shared:
            talk_to = [g["lead"]] if g.get("role") == "member" else peers
            self.bt("post", "--kind", "claim", "--kb", f"{g['id']}_note0.md",
                    f"evidence in my note; see @{rng.choice(talk_to)}" + ("" if g.get("role") == "member" else " and p0001"))
            if g["arm"].startswith("collective") and g["id"].endswith("1"):
                for k in range(3):
                    self.bt("post", "--kind", "chat", f"@{peers[k % len(peers)]} run a literature sweep on cages")
            if g["arm"].startswith("collective") and g["id"].endswith("2"):
                self.bt("post", "--kind", "need", "--inputs", "a stiffness estimate", "need: bone modulus range?")
            if g["arm"].startswith("collective") and g["id"].endswith("3"):
                needs, t1 = [], time.time()
                while not needs and time.time() - t1 < 15:
                    needs = [json.loads(x) for x in self.bt("read", "--kind", "need").stdout.splitlines() if x.strip()]
                    time.sleep(0.5)
                if needs:
                    self.bt("post", "--kind", "claim", "--re", needs[0]["id"], "picking this up")
            if g.get("role") == "lead":
                for x in peers:
                    self.bt("post", "--kind", "assign", f"@{x} survey one material family")
            posts = [json.loads(x) for x in self.bt("read", "--last", "3").stdout.splitlines() if x.strip()]
            mine = [q for q in posts if q.get("author") != g["id"] and q.get("id")]
            if mine and g.get("role") != "member":
                self.bt("post", "--kind", "evidence", "--kb", f"{g['id']}_note1.md", "--link",
                        f"extends:{mine[0]['id']}", "building on this")
        writer = (not shared) or (g["arm"].startswith("collective") and g["id"].endswith("1")) or \
            g.get("role") == "lead"
        if writer:
            time.sleep(2 if shared else 0)
            dl.mkdir(parents=True, exist_ok=True)
            (dl / "implant.stl").write_text("solid mock\nendsolid mock\n", encoding="utf-8")
            (dl / "material_spec.json").write_text(json.dumps({"material": "mock", "properties": {
                "E_MPa": {"value": 1000 + rng.randint(0, 9000), "source": "mock datasheet"}}}), encoding="utf-8")
            (dl / "report.md").write_text(f"# mock report {g['id']}\nEvidence: [note]({kb.as_posix()}/{g['id']}_note0.md)\n",
                                          encoding="utf-8")
            body = self.dir / "save.json"
            body.write_text(json.dumps({"file": str(dl / "implant.form"), "scenes": ["mock"]}), encoding="utf-8")
            self.tool("preform_api", "save_form", "--body", body.name)
        self.bt("done", "mock finished")
        return "done" if self.has_final() else "no_final"

    def run(self):
        self.status("running", started=utc_now())
        try:
            mock = self.genome["model"] == "mock"
            if mock:
                self.log_session(event="start", attempt=0, pid=os.getpid(), mock=True)
            if self.genome["model"] == "claude":
                final = self.run_claude(recover=self.recover)
            else:
                final = self.run_mock()
            if mock:
                self.log_session(event="end", attempt=0, pid=os.getpid(), session_id=f"mock-{self.genome['id']}")
        except Exception as exc:
            for _ in range(5):  # the sealer must see a final state
                try:
                    self.status("failed", error=str(exc)[:500])
                    break
                except Exception:
                    time.sleep(1)
            return
        if final == "done" and not self.has_final():
            final = "no_final"
        self.status(final, ended=utc_now(), has_final=self.has_final())


def kill_tree(proc):
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            proc.kill()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-dir", required=True)
    ap.add_argument("--recover", action="store_true", help="resume the agent's last session after a crash")
    ap.add_argument("--stop-at", help="this session's wall-cap stop time (ISO), set by the scheduler at start")
    a = ap.parse_args()
    r = Runner(a.agent_dir)
    r.recover = a.recover
    if a.stop_at:
        r.stop_at = dt.datetime.fromisoformat(a.stop_at)
    r.run()
