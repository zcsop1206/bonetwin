"""Communication-graph centralization per shared-board arm (fixed per the audit of ../harness/centralization.py).

    python centralization.py --root R                       (every shared-board arm of every run under R/run)
    python centralization.py --root R --run-id site_A_r1 --arm collective
    python centralization.py --board path/board.jsonl [--out-dir D]

Audit fixes: the old script drew edges only from reply parents. Edges now come from
    reply      author -> author of each parent post (--re)
    transfer   author -> meta.to
    mention    author -> @c3-style agent mentions in the text, and author -> author of p0012-style post mentions
    review     author -> author of the reviewed candidate (meta.review_of)
    cites / contradicts / extends / replicates   typed links (meta.links, ScienceClaw-style)
    derived    author of a design artifact -> author of each parent artifact from another agent (lineage DAG)
Lineage (all arms): DAG depth, syntheses (artifacts with >= 2 parents from >= 2 different agents) and
cross-agent derivations (parent edges whose parent has another author).
Self-edges are dropped; the sealer and humans are not nodes. Nodes are the arm's agents (from arm.json when given),
so silent agents count.

Outputs per arm: degree_centralization (Freeman, undirected simple graph: sum(max-deg_i)/((n-1)(n-2)), 1 = star,
0 = regular), in_degree_centralization, betweenness (undirected, Brandes, normalized by (n-1)(n-2)/2) with its max
and argmax, top_agent_post_share (share of agent posts written by the most active poster), top_receiver_share,
most_connected (largest weighted undirected degree; ties by betweenness, then id), edge counts by type,
each agent's share of posts and of DIRECTIVE posts (directives.py, rule logged), emergent_leader = the agent with
the highest directive share if it exceeds 2x the mean share (1/n),
and <run_id>_<arm>.graphml / .png / .json in the output folder.
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import directives  # noqa: E402
from common import SHARED_BOARD_ARMS, base_arm, load_json, read_jsonl, run_dir  # noqa: E402

AGENT_MENTION = re.compile(r"@([a-z]\d{1,2})\b")
POST_MENTION = re.compile(r"\b(p\d{4})\b")


def edges_of(posts, nodes):
    nodeset = set(nodes)
    author_of = {p["id"]: p["author"] for p in posts}
    out = Counter()  # (src, dst, type) -> count
    for p in posts:
        a = p["author"]
        if a not in nodeset:
            continue
        meta = p.get("meta") or {}
        targets = [(author_of.get(par), "reply") for par in p.get("parents", [])]
        if p["kind"] == "transfer" and meta.get("to"):
            targets.append((meta["to"], "transfer"))
        if meta.get("review_of"):
            targets.append((author_of.get(meta["review_of"]), "review"))
        text = p.get("text") or ""
        targets += [(m, "mention") for m in AGENT_MENTION.findall(text)]
        targets += [(author_of.get(m), "mention") for m in POST_MENTION.findall(text) if m != p["id"]]
        targets += [(author_of.get(lk.get("post")), lk.get("type")) for lk in meta.get("links") or []]
        for t, kind in targets:
            if t and t != a and t in nodeset:
                out[(a, t, kind)] += 1
    return out


def brandes(nodes, adj):
    """Betweenness of an unweighted undirected graph (Brandes 2001), normalized to [0, 1]."""
    bc = dict.fromkeys(nodes, 0.0)
    for s in nodes:
        stack, pred = [], defaultdict(list)
        sigma = dict.fromkeys(nodes, 0.0); sigma[s] = 1.0
        dist = dict.fromkeys(nodes, -1); dist[s] = 0
        queue = [s]
        while queue:
            v = queue.pop(0)
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    n = len(nodes)
    norm = (n - 1) * (n - 2) if n > 2 else 1  # undirected: each pair counted twice above, so /2 cancels
    return {v: bc[v] / norm for v in nodes}


def attribution(index_rows, artifact):
    """Who decided: the final design's ancestry in the lineage DAG, counted per author (the design itself included)."""
    author, parents = {}, {}
    for r in index_rows:
        author.setdefault(r["id"], r["author"])
        parents.setdefault(r["id"], set()).update(r.get("parents") or [])
    seen, stack = set(), [artifact] if artifact in author else []
    while stack:
        a = stack.pop()
        if a in seen:
            continue
        seen.add(a)
        stack += [q for q in parents.get(a, ()) if q in author]
    per = Counter(author[a] for a in seen)
    tot = sum(per.values())
    return {"artifact": artifact, "n_ancestors": max(0, tot - 1), "by_author": dict(per),
            "share": {k: round(v / tot, 3) for k, v in per.items()} if tot else {}}


def lineage(index_rows):
    """Lineage DAG of an arm's design artifacts (artifacts.jsonl rows)."""
    author, parents = {}, {}
    for r in index_rows:
        author.setdefault(r["id"], r["author"])
        parents.setdefault(r["id"], set()).update(r.get("parents") or [])
    depth = {}

    def d(a, seen=()):
        if a in depth:
            return depth[a]
        ps = [q for q in parents.get(a, ()) if q in author and q not in seen]
        depth[a] = 0 if not ps else 1 + max(d(q, seen + (a,)) for q in ps)
        return depth[a]

    for a in author:
        d(a)
    cross = [(a, q) for a, ps in parents.items() for q in ps if q in author and author[q] != author[a]]
    synth = [a for a, ps in parents.items() if len(ps) >= 2 and len({author.get(q) for q in ps if q in author}) >= 2]
    return {"n_artifacts": len(author), "n_parent_edges": sum(len(p) for p in parents.values()),
            "dag_depth": max(depth.values()) if depth else 0, "n_syntheses": len(synth),
            "n_cross_agent_derivations": len(cross), "syntheses": synth[:20],
            "derived_edges": [(author[a], author[q]) for a, q in cross]}


def analyse(posts, nodes=None, leader_ratio=2.0, artifacts=None):
    # launcher, sealer, sweeper and human posts are removed before any graph measure
    agent_posts = [p for p in posts if p["author"] not in ("sealer", "sweeper", "launcher") and not p.get("human")
                   and not str(p["author"]).startswith("human:")]
    nodes = sorted(set(nodes or []) | {p["author"] for p in agent_posts})
    typed = edges_of(agent_posts, nodes)
    lin = lineage(artifacts or [])
    lin.pop("ancestors_by_author", None)
    for s_, t_ in lin.pop("derived_edges"):
        if s_ in nodes and t_ in nodes:
            typed[(s_, t_, "derived")] += 1
    multi = Counter()
    for (s, t, _), k in typed.items():
        multi[(s, t)] += k
    und = defaultdict(int)
    for (s, t), k in multi.items():
        und[frozenset((s, t))] += k
    adj = {v: set() for v in nodes}
    for e in und:
        s, t = tuple(e)
        adj[s].add(t); adj[t].add(s)
    n = len(nodes)
    deg = {v: len(adj[v]) for v in nodes}
    wdeg = {v: sum(k for e, k in und.items() if v in e) for v in nodes}
    indeg = {v: len({s for (s, t) in multi if t == v}) for v in nodes}
    posts_by = Counter(p["author"] for p in agent_posts)
    recv = Counter()
    for (s, t), k in multi.items():
        recv[t] += k
    bc = brandes(nodes, adj) if n else {}
    res = {"n_nodes": n, "n_posts": len(agent_posts), "n_edges_total": sum(multi.values()),
           "edges_by_type": _by_type(typed),
           "degree": deg, "weighted_degree": wdeg, "in_degree": indeg, "posts_by_agent": dict(posts_by),
           "received": dict(recv), "betweenness": {v: round(b, 4) for v, b in bc.items()}}
    if n >= 3:
        md, mi = max(deg.values()), max(indeg.values())
        res["degree_centralization"] = round(sum(md - d for d in deg.values()) / ((n - 1) * (n - 2)), 4)
        res["in_degree_centralization"] = round(sum(mi - d for d in indeg.values()) / ((n - 1) ** 2), 4)
    if bc:
        top = max(bc, key=lambda v: (bc[v], v))
        res["betweenness_max"] = round(bc[top], 4)
        res["betweenness_argmax"] = top
    if posts_by:
        top, k = posts_by.most_common(1)[0]
        res["top_agent_post_share"] = round(k / sum(posts_by.values()), 4)
        res["top_poster"] = top
    if recv:
        top, k = recv.most_common(1)[0]
        res["top_receiver"] = top
        res["top_receiver_share"] = round(k / sum(recv.values()), 4)
    if nodes:
        res["most_connected"] = max(nodes, key=lambda v: (wdeg[v], bc.get(v, 0), -nodes.index(v)))
    # directive posts (directives.py): who assigns work to named agents
    ids = set(nodes)
    dir_posts = []
    for p in agent_posts:
        is_dir, tg, why = directives.classify(p, ids)
        if is_dir:
            dir_posts.append({"id": p["id"], "author": p["author"], "targets": tg, "why": why[:120]})
    dcount = Counter(d["author"] for d in dir_posts)
    ndir = sum(dcount.values())
    res["directive_rule"] = directives.RULE
    res["n_directive_posts"] = ndir
    res["post_share"] = {v: round(posts_by.get(v, 0) / max(1, len(agent_posts)), 4) for v in nodes}
    res["directive_share"] = {v: round(dcount.get(v, 0) / ndir, 4) if ndir else 0.0 for v in nodes}
    res["directive_posts"] = dir_posts
    res["emergent_leader"] = None
    if ndir and nodes:
        top = max(nodes, key=lambda v: (res["directive_share"][v], v))
        mean = 1.0 / len(nodes)
        res["directive_share_max"] = res["directive_share"][top]
        res["directive_share_top"] = top
        if res["directive_share"][top] > leader_ratio * mean:
            res["emergent_leader"] = top
    res["lineage"] = lin
    # needs: answered (a claim cites it) / expired (sweep) / open
    needs = [p for p in posts if p["kind"] == "need"]
    answered = {r for p in posts if p["kind"] == "claim" for r in (p.get("meta") or {}).get("pickup_of", [])}
    expired = {r for p in posts if p["kind"] == "expire" for r in p.get("parents", [])}
    res["needs"] = {"n": len(needs), "answered": sum(1 for n in needs if n["id"] in answered),
                    "expired": sum(1 for n in needs if n["id"] in expired and n["id"] not in answered),
                    "addressed": sum(1 for n in needs if (n.get("meta") or {}).get("to"))}
    # replications: independent (the replicating post cites a different artifact) vs re-scoring the same artifact
    by_id = {p["id"]: p for p in posts}

    def arts(p):
        m = p.get("meta") or {}
        return set(m.get("artifacts") or []) | {v.get("artifact") for v in m.get("verified_runs") or [] if v.get("artifact")} \
            | ({m["artifact"]} if m.get("artifact") else set())
    rep = [(p, by_id.get(lk["post"])) for p in posts for lk in (p.get("meta") or {}).get("links") or []
           if lk.get("type") == "replicates"]
    res["replications"] = {"n": len(rep), "independent": sum(1 for a, b in rep if b and arts(a) and arts(a) - arts(b)),
                           "same_artifact_or_uncited": sum(1 for a, b in rep if not (b and arts(a) and arts(a) - arts(b)))}
    res["_edges"] = [{"source": s, "target": t, "type": k_, "count": c} for (s, t, k_), c in sorted(typed.items())]
    return res


def _by_type(typed):
    c = Counter()
    for (_, _, k), v in typed.items():
        c[k] += v
    return {k: c.get(k, 0) for k in ("reply", "transfer", "mention", "review", "cites", "contradicts", "extends",
                                     "replicates", "derived")}


def write_graphml(res, path):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
             '<key id="posts" for="node" attr.name="posts" attr.type="int"/>',
             '<key id="betweenness" for="node" attr.name="betweenness" attr.type="double"/>',
             '<key id="type" for="edge" attr.name="type" attr.type="string"/>',
             '<key id="weight" for="edge" attr.name="weight" attr.type="int"/>',
             '<graph id="G" edgedefault="directed">']
    for v in res["degree"]:
        lines.append(f'<node id="{escape(v)}"><data key="posts">{res["posts_by_agent"].get(v, 0)}</data>'
                     f'<data key="betweenness">{res["betweenness"].get(v, 0)}</data></node>')
    for i, e in enumerate(res["_edges"]):
        lines.append(f'<edge id="e{i}" source="{escape(e["source"])}" target="{escape(e["target"])}">'
                     f'<data key="type">{e["type"]}</data><data key="weight">{e["count"]}</data></edge>')
    lines += ["</graph>", "</graphml>"]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_png(res, path, title):
    import math
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    nodes = list(res["degree"])
    n = max(len(nodes), 1)
    pos = {v: (math.cos(2 * math.pi * i / n + math.pi / 2), math.sin(2 * math.pi * i / n + math.pi / 2))
           for i, v in enumerate(nodes)}
    w = Counter()
    for e in res["_edges"]:
        w[(e["source"], e["target"])] += e["count"]
    fig, ax = plt.subplots(figsize=(5, 5), dpi=120)
    mx = max(w.values()) if w else 1
    for (s, t), k in w.items():
        (x1, y1), (x2, y2) = pos[s], pos[t]
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", lw=0.6 + 3.0 * k / mx, color="#5b6b7a", alpha=0.75,
                                    shrinkA=14, shrinkB=14, connectionstyle="arc3,rad=0.12"))
    for v in nodes:
        size = 300 + 120 * res["posts_by_agent"].get(v, 0)
        ax.scatter(*pos[v], s=size, color="#2b6cb0", zorder=3)
        ax.text(*pos[v], v, ha="center", va="center", color="white", fontsize=9, zorder=4)
    dc = res.get("degree_centralization")
    ax.set_title(f"{title}\ndegree centralization {dc if dc is not None else 'n/a'}, "
                 f"betweenness max {res.get('betweenness_max', 'n/a')}", fontsize=9)
    ax.set_xlim(-1.4, 1.4); ax.set_ylim(-1.4, 1.4); ax.axis("off")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def run_one(board_file, out_dir, name, nodes=None, figures=True, leader_ratio=2.0):
    res = analyse(read_jsonl(board_file), nodes, leader_ratio,
                  read_jsonl(Path(board_file).parent / "artifacts.jsonl"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if figures:
        write_graphml(res, out_dir / f"{name}.graphml")
        write_png(res, out_dir / f"{name}.png", name)
    safe = dict(res, directive_posts=[{k: v for k, v in d.items() if k != "why"}
                                      for d in res.get("directive_posts", [])])  # metrics: ids and counts, no text
    (out_dir / f"{name}.json").write_text(json.dumps(safe, indent=2), encoding="utf-8")
    return res


def arm_result(root, run_id, arm, out_dir=None, figures=True, leader_ratio=2.0):
    ad = run_dir(root) / run_id / arm
    manifest = load_json(ad / "arm.json") or {}
    nodes = [g["id"] for g in manifest.get("agents", [])]
    return run_one(ad / "board.jsonl", out_dir or Path(root) / "metrics" / "centralization", f"{run_id}_{arm}",
                   nodes, figures, leader_ratio)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--run-id")
    ap.add_argument("--arm")
    ap.add_argument("--board")
    ap.add_argument("--out-dir")
    a = ap.parse_args()
    if a.board:
        res = run_one(a.board, a.out_dir or Path(a.board).parent, Path(a.board).parent.name)
        print(json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, indent=2))
        return
    summary = {}
    for rd in sorted(p for p in (run_dir(a.root)).iterdir() if p.is_dir() and any(p.glob("*/arm.json"))):
        if a.run_id and rd.name != a.run_id:
            continue
        for ad in sorted(p for p in rd.iterdir() if p.is_dir()):
            if (a.arm and ad.name != a.arm) or base_arm(ad.name) not in SHARED_BOARD_ARMS:
                continue
            res = arm_result(a.root, rd.name, ad.name, a.out_dir)
            summary[f"{rd.name}/{ad.name}"] = {k: res.get(k) for k in (
                "n_nodes", "n_posts", "n_edges_total", "edges_by_type", "degree_centralization",
                "in_degree_centralization", "betweenness_max", "betweenness_argmax", "top_agent_post_share",
                "top_receiver_share", "most_connected", "n_directive_posts", "directive_share_max",
                "directive_share_top", "emergent_leader", "lineage")}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
