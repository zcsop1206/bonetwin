"""Overflow API billing (subscription by default; the API key only on a usage-window block).

The key is read from config overflow_api.key_file only here, only when a child process needs it, and is placed
only in that child's environment. It is never logged, printed, or written to a config, brief or transcript:
redact() scrubs it from every transcript line and meter log line. Spend is tracked at list price:
    run/api_spend.jsonl     exact total_cost_usd of each finished API session (and the launch health call)
    run/api_live/<agent>    running estimate of an API session in progress
Total = closed + live; at overflow_api.spend_cap_usd the runner stops using the key and pauses instead.
"""
import json
import os
from pathlib import Path

ENV = "ANTHROPIC_API_KEY"


def cfg_api(cfg):
    return cfg.get("overflow_api") or {}


def available(cfg):
    c = cfg_api(cfg)
    return bool(c.get("enabled")) and Path(c.get("key_file", "")).exists()


def _key(cfg):
    try:
        return Path(cfg_api(cfg)["key_file"]).read_text(encoding="utf-8").strip() or None
    except (OSError, KeyError):
        return None


def child_env(base_env, cfg):
    """A copy of base_env with the key added (child process only). Returns (env, ok)."""
    k = _key(cfg)
    if not k:
        return dict(base_env), False
    env = dict(base_env)
    env[ENV] = k
    return env, True


def strip(env):
    return {k: v for k, v in env.items() if k != ENV}


def redact(text, cfg=None, key=None):
    k = key or (os.environ.get(ENV)) or (_key(cfg) if cfg else None)
    if k and k in text:
        text = text.replace(k, "[REDACTED]")
    return text


def spend(root):
    run = Path(root) / "run"
    closed = 0.0
    f = run / "api_spend.jsonl"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                closed += float(json.loads(line).get("usd") or 0)
            except (ValueError, json.JSONDecodeError):
                pass
    live = 0.0
    for p in (run / "api_live").glob("*.json") if (run / "api_live").exists() else []:
        try:
            live += float(json.loads(p.read_text(encoding="utf-8")).get("usd") or 0)
        except (ValueError, json.JSONDecodeError, OSError):
            pass
    return closed, live


def under_cap(root, cfg, margin=1.0):
    closed, live = spend(root)
    return closed + live + margin < float(cfg_api(cfg).get("spend_cap_usd", 0))


def record_closed(root, rec):
    run = Path(root) / "run"
    with (run / "api_spend.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def set_live(root, name, usd):
    d = Path(root) / "run" / "api_live"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    if usd is None:
        try:
            p.unlink()
        except OSError:
            pass
    else:
        p.write_text(json.dumps({"usd": usd}), encoding="utf-8")


def list_price(cfg, usage):
    """USD at list price for one usage dict (fitted per-Mtok prices in config token_estimate)."""
    pr = cfg["token_estimate"]["usd_per_mtok"]
    return (usage.get("input_tokens", 0) * pr["input"] + usage.get("cache_creation_input_tokens", 0) *
            pr["cache_creation"] + usage.get("cache_read_input_tokens", 0) * pr["cache_read"] +
            usage.get("output_tokens", 0) * pr["output"]) / 1e6
