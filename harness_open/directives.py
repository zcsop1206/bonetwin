"""Directive-post classifier (kept simple on purpose; the rule is logged with every analysis).

A post is DIRECTIVE when it assigns work to a named agent:
    kind == "assign"                                                    (planner lead), or
    it @-mentions another agent of the arm AND the sentence holding the mention contains an imperative cue:
    a sentence-initial verb from VERBS, or one of PHRASES.
Self-mentions do not count. Used by board.py (the leader cap) and by centralization.py / manipulation.py.
"""
import re

VERBS = {"do", "run", "try", "check", "explore", "take", "test", "compute", "review", "sweep", "score", "focus",
         "handle", "design", "look", "verify", "use", "build", "write", "post", "submit", "rerun", "evaluate",
         "optimize", "optimise", "train", "export", "measure", "fix", "send", "drop", "stop", "start", "own",
         "cover", "work", "investigate", "compare", "report", "prepare", "go", "keep", "make", "pick", "repeat"}
PHRASES = ("can you", "could you", "please", "you should", "your task", "you take", "you handle", "i need you",
           "assign", "you're on", "you are on", "you own", "would you")
RULE = ("directive = kind 'assign', or an @mention of another arm agent in a sentence that starts with an "
        f"imperative verb ({len(VERBS)} verbs) or contains one of {list(PHRASES)}")
MENTION = re.compile(r"@([a-z]\d{1,2})\b")
SPLIT = re.compile(r"(?<=[.!?;\n])\s+")


def classify(post, agent_ids=None):
    """(is_directive, targets, reason)."""
    if post.get("kind") == "assign":
        tg = sorted(set(MENTION.findall((post.get("text") or "").lower())) - {post.get("author")})
        return True, tg, "kind assign"
    text = (post.get("text") or "").lower()
    targets, reasons = set(), []
    for sent in SPLIT.split(text):
        ments = [m for m in MENTION.findall(sent) if m != post.get("author")
                 and (agent_ids is None or m in agent_ids)]
        if not ments:
            continue
        words = re.findall(r"[a-z']+", MENTION.sub(" ", sent))
        cue = (words[:1] and words[0] in VERBS) or any(p in sent for p in PHRASES) or \
            any(w in VERBS for w in words[:2])
        if cue:
            targets.update(ments)
            reasons.append(sent[:80])
    return bool(targets), sorted(targets), "; ".join(reasons)
