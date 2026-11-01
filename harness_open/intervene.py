"""The only sanctioned mid-run change: a logged human intervention post (frozen rules otherwise).

    python intervene.py --root R --run-id lumbar_vertebra_r1 --arm collective --as <name> "text of the intervention"

Posts kind "intervention" by human:<name> on that arm's board, appends to run/HUMAN_POSTS.log and run/touch.log.
manipulation.py reports every such post (the no_human_posts check fails for that arm, by design: it is disclosed).
Refuses to run inside an agent environment.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from board import Board  # noqa: E402
from common import board_path, run_dir, utc_now  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--as", dest="who", required=True)
    ap.add_argument("text")
    a = ap.parse_args()
    if os.environ.get("BT_AGENT_DIR") or os.environ.get("BT_BOARD"):
        sys.exit("refused: not available inside an agent environment")
    bp = board_path(a.root, a.run_id, a.arm)
    if not bp.exists():
        sys.exit(f"no board at {bp}")
    rec = Board(bp).post(f"human:{a.who}", "intervention", a.text, meta={"tag": "intervention"}, human=True)
    line = f"{utc_now()} INTERVENTION {a.run_id}/{a.arm} {rec['id']} by human:{a.who}: {a.text}"
    for name in ("HUMAN_POSTS.log", "touch.log"):
        with (run_dir(a.root) / name).open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    print(line)


if __name__ == "__main__":
    main()
