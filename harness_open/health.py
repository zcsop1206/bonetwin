"""Launch health check (fail fast): one tiny call to the agent endpoint and one call per tool.

    python health.py --root R [--skip-claude]      (the launcher calls check() after the gateway preflight)

Agent endpoint: `claude -p` with the pinned --model, asked to reply OK; the model id reported back must match.
Tools: each wrapped tool runs once through tools/bt_tool.py from a throwaway health agent folder (run/health/agent)
with a cheap command. A tool that registry-checks as available but then fails aborts the launch; a tool that says
'unavailable' is recorded as such (the brief lists it, agents get the same answer).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import load_config, utc_now, write_json  # noqa: E402

TOOL_CALLS = [
    ("preform_api", ["list_settings"], None),
    ("compute", ["--", "--help"], None),
    ("cad_python", ["h_cad.py"], "import build123d, manifold3d, trimesh, gmsh\nprint('ok')\n"),
    ("warp_gpu", ["h_warp.py"], "import warp as wp\nwp.config.quiet = True\nwp.init()\nprint('ok', wp.get_preferred_device())\n"),
    ("freecad", ["h_fc.py"], "import FreeCAD\nprint('ok', FreeCAD.Version()[:2])\n"),
    ("train_widths", ["--", "--help"], None),
    ("lean_gate", ["--", "--help"], None),
    ("openresearch", ["--", "--query", "trabecular bone stiffness", "--max-papers", "1", "--sources", "embedding"], None),
]


def check_claude(cfg):
    exe = shutil.which("claude") or "claude"
    model = cfg.get("claude_model")
    try:
        r = subprocess.run([exe, "-p", "Reply with the single word OK.", "--output-format", "json", "--model", model,
                            "--max-turns", "1"], capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {"ok": False, "detail": f"claude -p failed: {exc}"}
    models = sorted((res.get("modelUsage") or {}).keys())
    ok = (not res.get("is_error")) and "OK" in str(res.get("result", "")).upper() and \
        all(m.startswith(model) for m in models)
    return {"ok": ok, "models": models, "result": str(res.get("result"))[:40],
            "cost_usd": res.get("total_cost_usd"), "usage": res.get("usage", {}).get("output_tokens")}


def check_api_key(root, cfg):
    """One tiny call billed to the overflow key (child env only); reports ok/fail only."""
    import billing
    if not billing.available(cfg):
        return {"ok": None, "detail": "overflow key not configured"}
    env, ok = billing.child_env({k: v for k, v in os.environ.items()}, cfg)
    if not ok:
        return {"ok": False}
    try:
        r = subprocess.run([shutil.which("claude") or "claude", "-p", "Reply with the single word OK.",
                            "--output-format", "json", "--model", cfg.get("claude_model"), "--max-turns", "1"],
                           capture_output=True, text=True, timeout=180, env=env, encoding="utf-8", errors="replace")
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"ok": False}
    if res.get("total_cost_usd"):
        billing.record_closed(root, {"ts": utc_now(), "agent": "health", "usd": res["total_cost_usd"],
                                     "source": "launch health check"})
    return {"ok": bool(not res.get("is_error") and "OK" in str(res.get("result", "")).upper())}


def check_tools(root, genome_src):
    d = Path(root) / "run" / "health" / "agent"
    d.mkdir(parents=True, exist_ok=True)
    g = dict(json.loads(Path(genome_src).read_text(encoding="utf-8")), id="health", quota=10 ** 9,
             board_shared=False, peers=[], arm_dir=str(d.parent), dir=str(d), kb_dir=str(d / "kb"),
             deliverables_dir=str(d / "deliverables"), role=None)
    (d / "kb").mkdir(exist_ok=True)
    (d / "deliverables").mkdir(exist_ok=True)
    write_json(d / "genome.json", g)
    env = {k: v for k, v in os.environ.items() if not k.startswith("BT_") or k == "BT_MOCK_TOOLS"}
    env.update(BT_AGENT="health", BT_AGENT_DIR=str(d))
    out = {}
    for tool, args, script in TOOL_CALLS:
        if script:
            (d / args[0]).write_text(script, encoding="utf-8")
        r = subprocess.run([sys.executable, str(HERE / "tools" / "bt_tool.py"), tool, *args], cwd=str(d), env=env,
                           capture_output=True, text=True, timeout=600)
        text = (r.stdout + r.stderr).strip()
        status = "unavailable" if r.returncode == 3 else ("ok" if r.returncode == 0 else f"FAILED exit {r.returncode}")
        out[tool] = {"status": status, "tail": text.splitlines()[-1][:120] if text else ""}
    return out


def check(root, genome_src, skip_claude=False):
    cfg = load_config()
    res = {"utc": utc_now(), "claude": None if skip_claude else check_claude(cfg),
           "api_key": None if skip_claude else check_api_key(root, cfg),
           "tools": check_tools(root, genome_src)}
    failed = [t for t, v in res["tools"].items() if v["status"].startswith("FAILED")]
    if res["claude"] is not None and not res["claude"]["ok"]:
        failed.append("claude endpoint")
    if res["api_key"] is not None and res["api_key"].get("ok") is False:
        failed.append("overflow API key")
    res["ok"] = not failed
    res["failed"] = failed
    write_json(Path(root) / "run" / "health.json", res)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--genome", required=True)
    ap.add_argument("--skip-claude", action="store_true")
    a = ap.parse_args()
    print(json.dumps(check(a.root, a.genome, a.skip_claude), indent=2))
