"""Append-only JSONL board plus every agent-side command of the DESIGN run (adapted from ../harness/board.py).

Post kinds: need, claim, review, chat, evidence, assign (planner lead only), candidate, final, transfer, seal.
Every post: {id, ts, author, human, kind, text, parents, meta}. Lineage via parents (post ids). No vote kind.

Agent usage (environment set by the runner: BT_AGENT, BT_AGENT_DIR, BT_BOARD):
    python board.py score --design d.json [--fidelity frame|planestress]   (run the gateway; priced; signed result)
    python board.py stl --design d.json --out d.stl                         (export an STL; priced)
    python board.py submit --run-id gw_x "one line"     (propose the design behind your gateway run for the arm)
    python board.py final --run-id gw_x --justification why.md            (your final design; ends your work)
    python board.py final --pick pNNNN --justification why.md             (planner lead only: pick the arm design)
    python board.py read [--since p0012] [--kind candidate] [--last 20]     (shared-board arms only)
    python board.py post --kind claim --run-id gw_x [--re p0003] "text"     (claims must cite signed gateway runs)
    python board.py post --kind review --re pNNNN [--run-id gw_y] "text"    (review a peer's candidate post)
    python board.py transfer --to c3 --amount 5000 "reason"                 (public quota transfer)
    python board.py balance
Identity comes from the agent's genome.json (via BT_AGENT_DIR), never from a claimed name. Scores come only from
the gateway: every claim, candidate and final must cite run ids whose signature verifies and that are in the
arm's gateway ledger; the board rejects the post otherwise and attaches the verified numbers to accepted posts.
Other agents' final posts are shown with the design withheld (candidates stay visible so they can be reviewed).
No human channel: the --as path of the prediction run is removed.
Planner arm (CENTRALIZED CONTROL GROUP), routing enforced here: a worker reads only the lead's posts and its own;
a worker's submit/final must cite --assignment pNNNN, an assign post by the lead that mentions the worker.
Leader-cap rerun: an agent whose genome has directive_cap N may post at most N directive posts (directives.py).

Mechanisms adopted from ScienceClaw (arXiv 2603.14312), identical for every board arm:
  artifacts   every scored design is stored immutably, content-addressed by SHA-256 (arm artifacts/<sha>.json) with
              `score --parents A1,A2` naming the artifact ids it was derived from -> a lineage DAG per arm
  needs       `post --kind need --inputs "..." "text"` broadcasts an unmet sub-problem; anyone may pick it up with
              `post --kind claim --re <need id> "text"` (a pickup needs no run id); no ranking or assignment by code
  typed links `post ... --link cites:p0003 --link contradicts:p0007` (cites, contradicts, extends, replicates)
Not adopted (deliberately): an orchestrator that writes agent specs or populates tasks, a shared task list with
atomic claiming, and novelty/centrality-weighted demand scoring.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import directives  # noqa: E402
import gateway as gw  # noqa: E402
from common import append_jsonl, load_config, load_json, read_jsonl, utc_now, write_json  # noqa: E402

KINDS = ["need", "claim", "review", "chat", "evidence", "assign", "candidate", "final", "transfer", "seal", "expire",
         "intervention"]
SYSTEM_AUTHORS = {"sealer", "sweeper", "launcher"}  # never nodes of the communication graph
HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
DONE_WORDS = re.compile(r"\b(done|finished|completed?|sha-?256)\b", re.I)
AGENT_KINDS = ["need", "claim", "review", "chat", "evidence", "assign"]
RUN_ID = re.compile(r"^[A-Za-z0-9_.:-]{4,80}$")
LINK_TYPES = ("cites", "contradicts", "extends", "replicates")


class Board:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = self.path.with_suffix(".lock")

    def _acquire(self, timeout=30):
        t0 = time.time()
        while True:
            try:
                fd = os.open(str(self.lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return
            except FileExistsError:
                if time.time() - t0 > timeout:  # stale lock
                    try:
                        os.remove(self.lock)
                    except OSError:
                        pass
                time.sleep(0.05)

    def read_for(self, viewer, since=None, kind=None, last=None, only_from=None):
        """Board as an agent sees it: designs inside other agents' final posts are withheld; planner workers see
        only the lead's posts, their own and the sealer's (only_from)."""
        out = []
        for p in self.read(since, kind, None):
            if only_from and p["author"] not in only_from:
                continue
            if p["kind"] == "final" and p["author"] != viewer:
                p = dict(p, meta={k: ("withheld" if k == "design" else v) for k, v in p["meta"].items()})
            out.append(p)
        return out[-last:] if last else out

    def read(self, since=None, kind=None, last=None):
        posts = read_jsonl(self.path)
        if since:
            posts = [p for p in posts if p["id"] > since]
        if kind:
            posts = [p for p in posts if p["kind"] == kind]
        if last:
            posts = posts[-last:]
        return posts

    def post(self, author, kind, text, parents=(), meta=None, human=False):
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        self._acquire()
        try:
            posts = self.read()
            ids = {p["id"] for p in posts}
            for par in parents:
                if par not in ids:
                    raise ValueError(f"parent {par} not on the board")
            pid = f"p{len(posts) + 1:04d}"
            rec = {"id": pid, "gid": f"{self.path.parent.parent.name}/{self.path.parent.name}/{pid}", "ts": utc_now(),
                   "author": author, "human": bool(human), "kind": kind, "text": text, "parents": list(parents),
                   "meta": meta or {}}
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            return rec
        finally:
            try:
                os.remove(self.lock)
            except OSError:
                pass


# ---------------------------------------------------------------- arm-level files (harness-written)

class Arm:
    """The arm's harness-owned records, located from the agent's genome. Agents are blocked from these paths."""

    def __init__(self, genome):
        self.g = genome
        self.dir = Path(genome["arm_dir"])
        self.ledger = self.dir / "gateway_ledger.jsonl"
        self.designs = self.dir / "arm_designs"
        self.candidates = self.dir / "candidates.jsonl"
        self.finals = self.dir / "finals.jsonl"
        self.artifacts = self.dir / "artifacts"
        self.artifact_index = self.dir / "artifacts.jsonl"
        self.info = gw.frozen(genome["root"])

    def resolve_artifact(self, ref, own_only_author=None):
        """Full artifact id from an id or a unique prefix (>= 8 hex chars)."""
        ref = (ref or "").strip().lower()
        if len(ref) < 8:
            return None, f"artifact id {ref!r} too short (use at least 8 hex characters)"
        idx = read_jsonl(self.artifact_index)
        hits = {a["id"] for a in idx if a["id"].startswith(ref) and
                (own_only_author is None or a["author"] == own_only_author)}
        if len(hits) != 1:
            return None, f"artifact {ref}: {'unknown' if not hits else 'ambiguous'} in this arm"
        return hits.pop(), None

    def store_artifact(self, design_path, author, parents, run_id):
        """Immutable, content-addressed design store; one index line per (artifact, run)."""
        import hashlib
        obj = json.loads(Path(design_path).read_text(encoding="utf-8"))
        aid = hashlib.sha256(gw.canonical(obj).encode()).hexdigest()
        self.artifacts.mkdir(parents=True, exist_ok=True)
        f = self.artifacts / f"{aid}.json"
        if not f.exists():
            f.write_text(gw.canonical(obj), encoding="utf-8")
        known = {a["id"] for a in read_jsonl(self.artifact_index)}
        append_jsonl(self.artifact_index, {"id": aid, "author": author, "parents": parents, "run_id": run_id,
                                           "ts": utc_now(), "first": aid not in known})
        return aid

    def ledger_rec(self, run_id):
        for r in read_jsonl(self.ledger):
            if r["record"].get("run_id") == run_id:
                return r
        return None

    def check_run(self, run_id, own_dir=None, need_author=None):
        """Verify a cited run: signature on the record the agent holds (own runs) or the ledger copy, and that the
        ledger knows it. Returns (ledger entry, None) or (None, reason)."""
        if not RUN_ID.match(run_id or ""):
            return None, f"{run_id}: not a run id"
        entry = self.ledger_rec(run_id)
        if not entry:
            return None, f"{run_id}: not in this arm's gateway ledger (only runs made with board.py score count)"
        rec = entry["record"]
        ok, why = gw.verify(self.info, rec)  # the harness-held signed record
        if not ok:
            return None, f"{run_id}: signature check failed ({why})"
        if own_dir and entry["author"] == self.g["id"]:
            held = load_json(Path(own_dir) / "gateway" / f"{run_id}.json")
            if held is not None and held != gw.visible(rec, load_config()):
                # the agent's copy was edited: it no longer matches the signed record
                return None, f"{run_id}: signature check failed (your copy differs from the signed record)"
        if need_author and entry["author"] != need_author:
            return None, f"{run_id}: run belongs to {entry['author']}, not {need_author}"
        return entry, None


def summary(rec, artifact=None):
    out = {"run_id": rec["run_id"], "score": rec.get("score"), "all_pass": gw.passes(rec),
           "fidelity": rec.get("fidelity"), "target": rec.get("target")}
    if artifact:
        out["artifact"] = artifact  # provenance: the design artifact behind this number
    return out


def _env(name):
    v = os.environ.get(name, "")
    return v or None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read"); r.add_argument("--since"); r.add_argument("--kind"); r.add_argument("--last", type=int)
    p = sub.add_parser("post"); p.add_argument("--kind", required=True); p.add_argument("--re", action="append", default=[])
    p.add_argument("--run-id", action="append", default=[]); p.add_argument("--link", action="append", default=[])
    p.add_argument("--inputs", help="need posts: the inputs the sub-problem would require")
    p.add_argument("--to", help="need posts: optional addressee (agent id)")
    p.add_argument("--deadline-min", type=float, help="need posts: optional deadline in minutes; a code sweep "
                                                      "marks unanswered needs expired")
    p.add_argument("--artifact", action="append", default=[], help="artifact id(s) (SHA-256) this post relies on")
    p.add_argument("--kb", action="append", default=[], help="knowledge-base file(s) this post relies on")
    p.add_argument("text")
    w = sub.add_parser("wait"); w.add_argument("--since", help="wait for a post newer than this id")
    w.add_argument("--timeout", type=float, default=90, help="seconds, at most 100 (keep tool calls short)")
    t = sub.add_parser("transfer"); t.add_argument("--to", required=True); t.add_argument("--amount", type=int, required=True)
    t.add_argument("--re", action="append", default=[]); t.add_argument("text", nargs="?", default="")
    s = sub.add_parser("score"); s.add_argument("--design", required=True)
    s.add_argument("--fidelity", default="frame", choices=["frame", "voxel", "planestress"])  # gated below
    s.add_argument("--parents", default="", help="comma-separated artifact ids this design was derived from")
    x = sub.add_parser("stl"); x.add_argument("--design", required=True); x.add_argument("--out", required=True)
    u = sub.add_parser("submit"); u.add_argument("--run-id", required=True); u.add_argument("--assignment")
    u.add_argument("text", nargs="?", default="")
    f = sub.add_parser("final"); f.add_argument("--run-id"); f.add_argument("--pick"); f.add_argument("--assignment")
    f.add_argument("--justification", required=True)
    sub.add_parser("balance")
    dn = sub.add_parser("done"); dn.add_argument("text", nargs="?", default="")
    args = ap.parse_args(argv)

    adir = _env("BT_AGENT_DIR")
    if not adir:
        sys.exit("No agent identity (BT_AGENT_DIR). board.py is run by agents inside their sessions.")
    from meter import Meter
    m = Meter(adir)
    genome = m.genome
    agent = genome["id"]  # identity from the genome, not from a claim
    claimed = _env("BT_AGENT")
    if claimed and claimed != agent:
        sys.exit(f"refused: claimed identity {claimed} does not match this agent's genome ({agent})")
    shared = bool(genome.get("board_shared"))
    board = Board(genome["board"]) if shared else None
    arm = Arm(genome)
    me = Path(adir)

    def need_board():
        if not board:
            sys.exit("This arm has no shared board: you work alone.")

    planner = genome.get("arm", "").startswith("planner")
    lead = genome.get("lead") if planner else None
    worker = planner and genome.get("role") != "lead"

    def check_assignment(pid):
        """Planner workers: the cited post must be the lead's assign post naming this worker."""
        posts = {q["id"]: q for q in board.read()}
        q = posts.get(pid or "")
        if not q or q["kind"] != "assign" or q["author"] != lead or f"@{agent}" not in (q["text"] or "").lower():
            sys.exit(f"refused: cite --assignment pNNNN, an assign post by {lead} that mentions @{agent}")
        return pid

    def charge(tool):
        ok, msg = m.charge_tool(tool)
        if not ok:
            sys.exit(msg)

    if args.cmd == "read":
        need_board()
        only = {agent, lead, "sealer"} if worker else None
        for post in board.read_for(agent, args.since, args.kind, args.last, only_from=only):
            print(json.dumps(post))

    elif args.cmd == "score":
        design = Path(args.design)
        if not design.is_absolute():
            design = (Path.cwd() / design)
        design = design.resolve()
        if not str(design).lower().startswith(str(me.resolve()).lower()):
            sys.exit("refused: score designs saved inside your own folder")
        try:
            json.loads(design.read_text(encoding="utf-8"))
        except Exception as exc:
            sys.exit(f"design is not valid JSON: {exc}")
        if args.fidelity not in arm.info.get("agent_fidelities", ["frame"]):
            sys.exit(f"refused: agents score at {arm.info.get('agent_fidelities', ['frame'])} fidelity only tonight "
                     "(expensive checks run one at a time through the shared queue)")
        parents = []
        for ref in [x for x in args.parents.split(",") if x.strip()]:
            full, why = arm.resolve_artifact(ref, None if shared else agent)
            if why:
                sys.exit(f"refused: {why}")
            parents.append(full)
        charge(f"gateway_{args.fidelity}")
        extra = arm.info.get("agent_check_args", []) if args.fidelity != "frame" else []
        try:
            rec = gw.score(arm.info, design, genome["target"], args.fidelity, extra=extra,
                           who=f"{genome['run_id']}/{genome['arm']}/{agent}",
                           wait_s=arm.info.get("agent_check_wait_s", 90))  # slots and RAM floor from gateway.json
        except RuntimeError as exc:
            if "slot busy" in str(exc):  # not granted within the wait: refund, the agent may retry later
                m.refund(f"gateway_{args.fidelity}")
                sys.exit(f"heavy-job queue busy or free RAM below the floor (FIFO, one local job at a time); not charged. "
                         f"Try again later, or run the heavy job on Brev through bt_compute. ({exc})")
            sys.exit(f"gateway error (credits already charged): {exc}")
        except Exception as exc:
            sys.exit(f"gateway error (credits already charged): {exc}")
        rid = rec.get("run_id")
        if not rid:
            sys.exit("gateway returned no run_id")
        arm.designs.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(design, arm.designs / f"{rid}.json")
        (me / "gateway").mkdir(exist_ok=True)
        (me / "designs").mkdir(exist_ok=True)
        view = gw.visible(rec, load_config())
        write_json(me / "gateway" / f"{rid}.json", view)
        shutil.copyfile(design, me / "designs" / f"{rid}.json")
        artifact = arm.store_artifact(design, agent, parents, rid)
        rec_model = rec.get("model")  # noqa: F841 (gateway is code, no model)
        append_jsonl(arm.ledger, {"ts": utc_now(), "author": agent, "design_file": f"arm_designs/{rid}.json",
                                  "artifact": artifact, "parents": parents, "record": rec})
        print(json.dumps(view))
        print(f"saved: gateway/{rid}.json and designs/{rid}.json; artifact {artifact} (parents {parents or 'none'}); "
              f"cite run id {rid} in claims", file=sys.stderr)

    elif args.cmd == "stl":
        charge("export_stl")
        code, out = gw.export_stl(arm.info, Path(args.design).resolve(), (me / Path(args.out).name).resolve())
        print(out)
        if code:
            sys.exit(code)

    elif args.cmd == "post":
        need_board()
        if args.kind not in AGENT_KINDS:
            sys.exit(f"agents post kinds {AGENT_KINDS}; use submit/final/transfer for the others")
        if args.kind == "assign" and genome.get("role") != "lead":
            sys.exit("refused: only the planner arm's lead posts assignments")
        if args.kind != "assign" and genome.get("directive_cap") is not None:
            ids = set(genome.get("peers", []))
            is_dir, _, _ = directives.classify({"kind": args.kind, "text": args.text, "author": agent}, ids)
            if is_dir:
                n = sum(1 for q in board.read() if q["author"] == agent and directives.classify(q, ids)[0])
                if n >= genome["directive_cap"]:
                    sys.exit(f"refused: you may post at most {genome['directive_cap']} directive posts (posts that "
                             "assign work to a named agent) in this run; you have used them")
        links = []
        posts_now = {q["id"]: q for q in board.read()}
        for spec in args.link:
            typ, _, pid = spec.partition(":")
            if typ not in LINK_TYPES or pid not in posts_now:
                sys.exit(f"refused: --link TYPE:pNNNN with TYPE in {LINK_TYPES} and an existing post")
            links.append({"type": typ, "post": pid})
        if worker:
            others = {m for m in directives.MENTION.findall(args.text.lower()) if m not in (agent, lead)}
            posts_by = {q["id"]: q["author"] for q in board.read()}
            if others or any(posts_by.get(r) not in (agent, lead) for r in args.re + [x["post"] for x in links]):
                sys.exit(f"refused: in this arm you address only the lead ({lead}); no other workers")
        pickup = [r for r in args.re if posts_now.get(r, {}).get("kind") == "need"]
        expired = [r for r in pickup if any(q["kind"] == "expire" and r in q["parents"] for q in posts_now.values())]
        if expired:
            sys.exit(f"refused: need {expired} has expired")
        if args.kind == "claim" and not args.run_id and not pickup and not args.artifact and not args.kb:
            sys.exit("refused: a claim must cite evidence: a gateway run id (--run-id), an artifact (--artifact) or a "
                     "knowledge-base file (--kb)")
        verified = []
        for rid in args.run_id:
            entry, why = arm.check_run(rid, own_dir=me)
            if why:
                sys.exit(f"refused: {why}")
            verified.append(summary(entry["record"], entry.get("artifact")) | {"by": entry["author"]})
        arts = []
        for ref in args.artifact:
            full, why = arm.resolve_artifact(ref)
            if why:
                sys.exit(f"refused: {why}")
            arts.append(full)
        # results must be signed: claims and "done"/hash-bearing posts need a verified run id or artifact
        known = {a["id"] for a in read_jsonl(arm.artifact_index)} | {
            r["record"].get("design_sha256") for r in read_jsonl(arm.ledger)}
        bad_hex = [h for h in HEX64.findall(args.text.lower()) if h not in known]
        if bad_hex:
            sys.exit(f"refused: the post names hash(es) {[h[:12] for h in bad_hex]} that are not artifacts or "
                     "gateway design hashes of this arm")
        kbs = []
        for ref in args.kb:
            kp = (Path(genome["kb_dir"]) / ref).resolve() if not Path(ref).is_absolute() else Path(ref).resolve()
            if not str(kp).lower().startswith(str(Path(genome["kb_dir"]).resolve()).lower()) or not kp.exists():
                sys.exit(f"refused: --kb {ref} is not a file in your knowledge base")
            kbs.append(kp.relative_to(Path(genome["kb_dir"]).resolve()).as_posix())
        if args.kind != "need" and DONE_WORDS.search(args.text) and not (verified or arts or pickup or kbs):
            sys.exit("refused: a post reporting a result ('done', a hash) must cite evidence: a gateway run id "
                     "(--run-id), an artifact (--artifact) or a knowledge-base file (--kb)")
        meta = {"verified_runs": verified} if verified else {}
        if kbs:
            meta["kb"] = kbs
        if arts:
            meta["artifacts"] = arts
        if links:
            meta["links"] = links
        if args.kind == "need":
            meta["inputs"] = args.inputs or ""
            if args.to:
                if args.to not in genome.get("peers", []):
                    sys.exit(f"unknown addressee {args.to}")
                meta["to"] = args.to
            if args.deadline_min:
                import datetime as _dt
                meta["deadline_utc"] = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(
                    minutes=float(args.deadline_min))).isoformat(timespec="seconds")
        if args.kind == "claim" and pickup:
            meta["pickup_of"] = pickup
        if args.kind == "review":
            posts = {q["id"]: q for q in board.read()}
            targets = [pid for pid in args.re if posts.get(pid, {}).get("kind") == "candidate"]
            if len(targets) != 1:
                sys.exit("refused: a review must --re exactly one candidate post")
            if posts[targets[0]]["author"] == agent:
                sys.exit("refused: you cannot review your own candidate")
            meta["review_of"] = targets[0]
            meta["review_of_run"] = posts[targets[0]]["meta"].get("run_id")
        charge("board_post")
        print(json.dumps(board.post(agent, args.kind, args.text, args.re, meta=meta)))

    elif args.cmd == "transfer":
        need_board()
        if args.amount <= 0:
            sys.exit("amount must be positive")
        if worker and args.to != lead:
            sys.exit(f"refused: in this arm workers transfer only to the lead ({lead})")
        if args.to not in genome.get("peers", []) or args.to == agent:
            sys.exit(f"unknown recipient {args.to}; peers are {genome.get('peers', [])}")
        bal = m.balance()
        if args.amount > bal:
            sys.exit(f"refused: balance {bal:.0f} < {args.amount}")
        rec = board.post(agent, "transfer", args.text or f"transfer {args.amount} to {args.to}", args.re,
                         meta={"to": args.to, "amount": args.amount})
        print(json.dumps(rec))

    elif args.cmd in ("submit", "final"):
        pick_post = None
        if args.cmd == "final" and args.pick:
            if genome.get("role") != "lead":
                sys.exit("refused: only the planner arm's lead picks with --pick; use --run-id")
            need_board()
            posts = {q["id"]: q for q in board.read()}
            if args.pick in posts and posts[args.pick]["kind"] == "candidate":
                pick_post = args.pick
                run_id = posts[args.pick]["meta"]["run_id"]
            elif any(q["kind"] == "candidate" and q["meta"].get("run_id") == args.pick for q in posts.values()):
                run_id = args.pick
                pick_post = next(q["id"] for q in posts.values()
                                 if q["kind"] == "candidate" and q["meta"].get("run_id") == args.pick)
            else:
                sys.exit("refused: --pick must name a candidate post (pNNNN) or a candidate's run id")
            entry, why = arm.check_run(run_id)
        else:
            run_id = args.run_id
            if not run_id:
                sys.exit("--run-id is required")
            entry, why = arm.check_run(run_id, own_dir=me, need_author=agent)
        assignment = check_assignment(args.assignment) if worker else None
        if why:
            sys.exit(f"refused: {why}")
        rec = entry["record"]
        artifact = entry.get("artifact")
        dpath = arm.dir / entry["design_file"]
        if not gw.design_matches(rec, dpath):
            sys.exit("refused: stored design does not match the signed design hash")
        design = json.loads(dpath.read_text(encoding="utf-8"))
        cand = {"ts": utc_now(), "author": agent, "run_id": run_id, "by": entry["author"], **summary(rec, artifact),
                "assignment": assignment}
        already = any(c["run_id"] == run_id and c["author"] == entry["author"] for c in read_jsonl(arm.candidates))
        cand_post = None
        if not pick_post and not already:
            if board:
                cand_post = board.post(agent, "candidate", args.text if args.cmd == "submit" else
                                       f"final design of {agent}", [assignment] if assignment else [],
                                       meta={**summary(rec), "design": design, "assignment": assignment,
                                             "artifact": artifact, "parents": entry.get("parents", [])})["id"]
            append_jsonl(arm.candidates, dict(cand, post=cand_post))
        if args.cmd == "submit":
            if already:
                print(f"{run_id} is already a candidate")
            else:
                print(json.dumps({"candidate": run_id, "post": cand_post, **summary(rec)}))
            return
        jpath = Path(args.justification)
        jpath = jpath if jpath.is_absolute() else Path.cwd() / jpath
        if not jpath.exists():
            sys.exit("justification file not found")
        just = jpath.read_text(encoding="utf-8")
        if len(just.strip()) < 200:
            sys.exit("refused: the justification must explain why you are confident (at least a short paragraph, "
                     "citing your gateway run ids)")
        fin = {"ts": utc_now(), "agent": agent, "run_id": run_id, "pick_post": pick_post, **summary(rec),
               "justification": just}
        write_json(me / "final.json", fin)
        append_jsonl(arm.finals, {k: v for k, v in fin.items() if k != "justification"})
        if board:
            board.post(agent, "final", f"final from {agent}" + (f" (picks {pick_post})" if pick_post else ""),
                       [pick_post] if pick_post else [], meta={**summary(rec), "design": design,
                                                               "pick_post": pick_post})
        print(json.dumps({"final": run_id, **summary(rec)}))
        print("Final recorded. Your work is done; end your session now.", file=sys.stderr)

    elif args.cmd == "wait":
        # event wait: block (briefly) until the board changes; use this instead of sleep loops
        need_board()
        import time as _t
        t0, limit = _t.time(), min(max(args.timeout, 1), 100)
        only = {agent, lead, "sealer"} if worker else None
        since = args.since or (board.read_for(agent, only_from=only) or [{"id": "p0000"}])[-1]["id"]
        mtime = board.path.stat().st_mtime if board.path.exists() else 0
        while _t.time() - t0 < limit:
            if board.path.exists() and board.path.stat().st_mtime != mtime:
                mtime = board.path.stat().st_mtime
                new = board.read_for(agent, since=since, only_from=only)
                if new:
                    for post in new:
                        print(json.dumps(post))
                    return
            _t.sleep(1.0)
        print(json.dumps({"timeout": True, "since": since, "waited_s": round(_t.time() - t0)}))

    elif args.cmd == "done":
        write_json(me / "final.json", {"ts": utc_now(), "agent": agent, "done": True, "note": args.text[:500]})
        print("Recorded: you are done. End your session now.")

    elif args.cmd == "balance":
        print(json.dumps(m.status()))


if __name__ == "__main__":
    main()
