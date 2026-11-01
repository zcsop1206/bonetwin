"""Harness side of the design gateway: locate it (real bonetwin/sim or the mock), run it, verify signatures.

The launcher freezes the choice in run/gateway.json; every later process (board.py inside agent sessions,
seal.py, scheduler.py) reads that file, so one run never mixes the mock and the real gateway.

Signature contract (from bonetwin/sim/bt_common.py; the mock implements the same): the gateway signs with the key in
env BT_GATEWAY_KEY: record["signature"] = {"alg": "HMAC-SHA256", "value": HMAC(key, canonical JSON of the record
without "signature")}, canonical = json.dumps(sort_keys=True, separators=(",", ":"), default=float).
The key lives in a harness-only file (config gateway.key_file, default harness_design/.gateway_key, created at
launch) and is put into the environment of the gateway subprocess only, never into an agent's environment.
The sealed 4th load case is scored only by the sealer, which also sets BT_GATEWAY_ADMIN for its gateway calls.
If the real gateway signs differently, set gateway.verify_cmd (reads the record on stdin, exit 0 = verified); the
launcher's preflight refuses to launch when a fresh gateway record does not verify.
"""
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BONETWIN, HERE, bt_path, load_json, write_json  # noqa: E402,F401


KEY_ENV = "BT_GATEWAY_KEY"
ADMIN_ENV = "BT_GATEWAY_ADMIN"
STRIP_ENV = (KEY_ENV, ADMIN_ENV, "ANTHROPIC_API_KEY")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=float)


def resolve(cfg, force_mock=False):
    g = cfg["gateway"]
    real = bt_path(g["real_dir"])
    mock = bt_path(g["mock_dir"])
    use_real = (real / g["score_script"]).exists() and not force_mock
    d = real if use_real else mock
    key = HERE / ".gateway_key"
    if g.get("key_file"):
        key = Path(g["key_file"]) if Path(g["key_file"]).is_absolute() else (BONETWIN / g["key_file"]).resolve()
    info = {"mode": "real" if use_real else "MOCK", "dir": str(d), "score": str(d / g["score_script"]),
            "control": str(d / g["control_script"]), "export": str(d / g["export_script"]),
            "schema": str(real / g["schema_file"]) if (real / g["schema_file"]).exists() else str(mock / g["schema_file"]),
            "key_file": str(key), "verify_cmd": g.get("verify_cmd") or "", "timeout_s": g.get("timeout_s", 600),
            "seal_fidelity": g.get("seal_fidelity", "frame"),
            "agent_fidelities": g.get("agent_fidelities", ["frame"]),
            "postscore": g.get("postscore", {}), "heavy_slots": cfg.get("heavy_slots", 1),
            "heavy_min_free_ram_gb": cfg.get("heavy_min_free_ram_gb", 0), "agent_check_args": g.get("agent_check_args", []),
            "agent_check_wait_s": g.get("agent_check_wait_s", 90), "voxel_lock": str(HERE / g.get("voxel_lock", "voxel.lock")), "seal_extra_args": g.get("seal_extra_args", []),
            "dim": g.get("dim", 3), "dim_fallback": g.get("dim_fallback", 2),
            "score_better": g.get("score_better", "lower")}
    for k in ("control", "export"):
        if not Path(info[k]).exists():
            info[k] = str(mock / Path(info[k]).name)
            info[k + "_mock_fallback"] = True
    return info


def frozen(root):
    """The gateway chosen at launch for this root."""
    info = load_json(Path(root) / "run" / "gateway.json")
    if not info:
        raise SystemExit("no run/gateway.json under this root (launch first)")
    return info


def freeze(root, info):
    write_json(Path(root) / "run" / "gateway.json", info)


def _last_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    i = text.find("\n{")
    if text.startswith("{") or i >= 0:
        try:
            return json.loads(text[0 if text.startswith("{") else i + 1:])
        except json.JSONDecodeError:
            pass
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def ensure_key(info):
    kf = Path(info["key_file"])
    if not kf.exists():
        import secrets
        kf.write_text(secrets.token_hex(32), encoding="utf-8")
    return kf


def _key(info):
    kf = Path(info["key_file"])
    return kf.read_text(encoding="utf-8").strip() if kf.exists() else None


def gateway_env(info, admin=False):
    """Environment for a gateway subprocess: the key (and, for the sealer, the admin flag) only here."""
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    env.update({"OMP_NUM_THREADS": "4", "MKL_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4"})
    key = _key(info)
    if key:
        env[KEY_ENV] = key
    if admin:
        env[ADMIN_ENV] = info.get("admin_value") or "1"
    return env


class VoxelLock:
    """Neutral N-slot queue (open run: heavy_slots = 2) for voxel / plane-stress jobs across every harness process (the laptop GPU runs one
    at a time). Scheduled by code only: FIFO by the signed request time, tie-break by the requester label (run_id/arm);
    nobody can reorder it. Every enqueue, grant and dequeue is appended to voxel_queue.jsonl (the queue itself) and
    the slot is an O_EXCL lock file; tickets whose process has died are skipped."""

    def __init__(self, path, wait_s=3600, who=None, info=None, slots=None, min_ram=None):
        self.path, self.wait_s = Path(path), wait_s
        self.qfile = self.path.with_name("voxel_queue.jsonl")
        self.who = who or f"pid{os.getpid()}"
        self.info = info or {}
        self.ticket = None
        self.slots = int(slots or (info or {}).get("heavy_slots") or 1)
        self.min_ram = float(min_ram if min_ram is not None else (info or {}).get("heavy_min_free_ram_gb") or 0)
        self.slot = None

    @staticmethod
    def _alive(pid):
        try:
            if os.name == "nt":
                out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
                return str(pid) in out.stdout
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    def _log(self, event, **kw):
        import datetime as _dt
        rec = {"event": event, "ticket": self.ticket and self.ticket["id"], "who": self.who, "pid": os.getpid(),
               "utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds"), **kw}
        with self.qfile.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def _queue(self):
        recs = []
        if self.qfile.exists():
            for line in self.qfile.read_text(encoding="utf-8").splitlines():
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        done = {r["ticket"] for r in recs if r["event"] in ("dequeue", "abandon")}
        open_ = [r for r in recs if r["event"] == "enqueue" and r["ticket"] not in done]
        alive = [r for r in open_ if r["ticket"] == self.ticket["id"] or self._alive(r["pid"])]
        return sorted(alive, key=lambda r: (float(r["t"]), r["who"]))

    def __enter__(self):
        import time
        import uuid
        t = time.time()
        self.ticket = {"id": uuid.uuid4().hex[:12], "t": t, "who": self.who, "pid": os.getpid()}
        key = _key(self.info) if self.info else None
        sig = hmac.new(key.encode(), canonical(self.ticket).encode(), hashlib.sha256).hexdigest() if key else None
        self._log("enqueue", t=t, signature=sig)
        while True:
            q = self._queue()
            pos = next((k for k, r in enumerate(q) if r["ticket"] == self.ticket["id"]), None)
            ram_ok = True
            if self.min_ram:
                from common import free_ram_gb
                ram_ok = free_ram_gb() >= self.min_ram
                if not ram_ok and not getattr(self, "_ram_logged", False):
                    self._ram_logged = True
                    self._log("ram_wait", free_ram_gb=round(free_ram_gb(), 2), need_gb=self.min_ram)
            if ram_ok and pos is not None and pos < self.slots:  # FIFO: the first `slots` tickets may hold a slot
                for k in range(self.slots):
                    sp = self.path.with_name(f"{self.path.name}.{k}")
                    try:
                        fd = os.open(str(sp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        os.write(fd, str(os.getpid()).encode())
                        os.close(fd)
                        self.slot = sp
                        self._log("grant", slot=k, waited_s=round(time.time() - t, 1), queue_len=len(q))
                        return self
                    except FileExistsError:
                        try:
                            pid = int(sp.read_text().strip() or 0)
                        except (OSError, ValueError):
                            pid = 0
                        if pid and not self._alive(pid):
                            try:
                                sp.unlink()
                            except OSError:
                                pass
            if time.time() - t > self.wait_s:
                self._log("abandon", reason="wait limit")
                raise RuntimeError("voxel slot busy (queue ahead of you); try later")
            time.sleep(1)

    def __exit__(self, *exc):
        try:
            (self.slot or self.path).unlink()
        except OSError:
            pass
        self._log("dequeue")


def score(info, design_path, target, fidelity="frame", extra=(), dim=None, admin=False, who=None, wait_s=3600):
    if fidelity != "frame" or "--sealed" in extra:
        with VoxelLock(info.get("voxel_lock") or (HERE / "voxel.lock"), wait_s=wait_s, who=who, info=info):
            return _score(info, design_path, target, fidelity, extra, dim, admin)
    return _score(info, design_path, target, fidelity, extra, dim, admin)


def _score(info, design_path, target, fidelity="frame", extra=(), dim=None, admin=False):
    dim = dim or info.get("dim")
    cmd = [sys.executable, info["score"], "--design", str(design_path), "--target", target, "--fidelity", fidelity,
           *(["--dim", str(dim)] if dim else []), *extra]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=info.get("timeout_s", 600),
                       cwd=str(Path(info["score"]).parent), env=gateway_env(info, admin),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
    rec = _last_json(r.stdout)
    if rec and rec.get("ok") is False:
        raise RuntimeError(f"gateway refused the design: {rec.get('error')}")
    if r.returncode or not rec:
        raise RuntimeError(f"gateway failed (exit {r.returncode}): {(r.stderr or r.stdout)[-800:]}")
    return rec


def export_stl(info, design_path, out):
    r = subprocess.run([sys.executable, info["export"], "--design", str(design_path), "--out", str(out)],
                       capture_output=True, text=True, timeout=info.get("timeout_s", 600),
                       cwd=str(Path(info["export"]).parent), env=gateway_env(info))
    return r.returncode, (r.stdout + r.stderr)[-2000:]


NO_MODEL_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "NVIDIA_API_KEY",
                "OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN", "AZURE_OPENAI_API_KEY", "HF_TOKEN")


def no_model_env():
    return {k: v for k, v in os.environ.items()
            if k not in STRIP_ENV and k not in NO_MODEL_ENV and "API_KEY" not in k.upper() and "TOKEN" not in k.upper()}


def control_design(info, target, out, dim=None):
    """The control arm: no agent. Run with no model API keys or tokens in its environment."""
    dim = dim or info.get("dim")
    r = subprocess.run([sys.executable, info["control"], "--target", target, "--out", str(out),
                        *(["--dim", str(dim)] if dim else [])],
                       capture_output=True, text=True, timeout=info.get("timeout_s", 600),
                       cwd=str(Path(info["control"]).parent), env=no_model_env())
    if r.returncode or not Path(out).exists():
        raise RuntimeError(f"control_design failed: {(r.stderr or r.stdout)[-800:]}")
    return Path(out)


def verify(info, rec):
    """(ok, reason). Never prints or returns the key."""
    if not isinstance(rec, dict) or not rec.get("signature") or not rec.get("run_id"):
        return False, "no signature or run_id"
    if info.get("verify_cmd"):
        r = subprocess.run(info["verify_cmd"], input=json.dumps(rec), shell=True, capture_output=True, text=True,
                           timeout=60)
        return (r.returncode == 0), ("verify_cmd ok" if r.returncode == 0 else "verify_cmd rejected")
    key = _key(info)
    if not key:
        return False, "gateway key not available to the harness"
    sig = rec["signature"]
    sig = sig.get("value") if isinstance(sig, dict) else sig
    if not sig:
        return False, "record is unsigned"
    body = {k: v for k, v in rec.items() if k != "signature"}
    want = hmac.new(key.encode(), canonical(body).encode(), hashlib.sha256).hexdigest()
    good = hmac.compare_digest(want, str(sig))
    return good, ("hmac ok" if good else "signature mismatch")


def design_hashes(path_or_obj):
    """Hashes a gateway might have signed: canonical JSON and raw bytes."""
    if isinstance(path_or_obj, (str, Path)):
        raw = Path(path_or_obj).read_bytes()
        obj = json.loads(raw.decode("utf-8"))
        return {hashlib.sha256(canonical(obj).encode()).hexdigest(), hashlib.sha256(raw).hexdigest()}
    return {hashlib.sha256(canonical(path_or_obj).encode()).hexdigest()}


def design_matches(rec, design_path):
    h = rec.get("design_sha256")
    return True if not h else h in design_hashes(design_path)


def better(a, b, info=None):
    """True when score a beats score b (the real gateway's score is an error: lower is better)."""
    lower = (info or {}).get("score_better", "lower") == "lower"
    return a < b if lower else a > b


def best(items, key, info=None):
    lower = (info or {}).get("score_better", "lower") == "lower"
    return (min if lower else max)(items, key=key) if items else None


def _hidden(key, pats):
    k = str(key)
    return any(k == p or k.lower().startswith(p.lower() + "_") or (len(p) > 2 and p.lower() in k.lower())
               for p in pats)


def visible(rec, cfg):
    """What an agent may see of a gateway record: the desirability parts filtered (d2/sealed never; d3, model
    agreement and the composite D only in voxel checks). The signed record stays whole in the harness ledger."""
    dc = cfg.get("desirability") or {}
    field = dc.get("field", "desirability")
    out = {k: v for k, v in rec.items() if not _hidden(k, ["sealed"])}
    des = rec.get(field)
    if isinstance(des, dict):
        hide = list(dc.get("hide_always", [])) + ([] if rec.get("fidelity") not in (None, "frame") else
                                                  list(dc.get("hide_unless_voxel", [])))

        def scrub(d):
            return {k: (scrub(v) if isinstance(v, dict) else v) for k, v in d.items() if not _hidden(k, hide)}
        out[field] = scrub(des)
    out["_view"] = "agent view (signed full record kept by the harness)"
    return out


def desirability(rec, cfg):
    """(D, {part: value}) from a final record, whatever the gateway's exact layout."""
    dc = cfg.get("desirability") or {}
    des = rec.get(dc.get("field", "desirability")) or {}
    if not isinstance(des, dict):
        return None, {}
    flat = {}

    def walk(d, pre=""):
        for k, v in d.items():
            if isinstance(v, dict):
                walk(v, pre + k + ".")
            elif isinstance(v, (int, float)):
                flat[pre + k] = v
    walk(des)
    Dv = des.get("D", des.get("index"))
    return Dv, {k: v for k, v in flat.items() if k not in ("D", "index")}


def passes(rec):
    if rec.get("ok") is False:
        return False
    if "all_pass" in rec:
        return bool(rec["all_pass"])
    if isinstance(rec.get("constraints"), dict) and "all_pass" in rec["constraints"]:
        return bool(rec["constraints"]["all_pass"])
    cons = rec.get("constraints") or {}
    vals = cons.values() if isinstance(cons, dict) else cons
    return bool(vals) and all((c.get("pass") if isinstance(c, dict) else bool(c)) for c in vals)


def preflight(info, scratch, target):
    """Score the control design at the configured dim (falling back to dim_fallback) and verify the signature.
    Returns (dim used, record). Raises when no dim works or the signature does not verify."""
    errors = []
    for dim in (info["dim"], info["dim_fallback"]):
        try:
            d = control_design(info, target, Path(scratch) / f"preflight_control_dim{dim}.json", dim=dim)
            rec = score(info, d, target, "frame", dim=dim)
        except Exception as exc:
            errors.append(f"dim {dim}: {exc}")
            continue
        if rec.get("score") is None:
            errors.append(f"dim {dim}: gateway rejected the control design: {rec.get('constraints')}")
            continue
        ok, why = verify(info, rec)
        if not ok:
            raise SystemExit(f"preflight: gateway record does not verify ({why}); set gateway.key_file or verify_cmd")
        return dim, rec
    raise SystemExit("preflight: gateway unusable: " + " | ".join(errors))


def public_copy(info, dest_dir):
    """Copy only what agents may read: the design schema. (Not the gateway source, key, or control design.)"""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    src = Path(info["schema"])
    (dest_dir / "design_schema.json").write_bytes(src.read_bytes())
    return dest_dir / "design_schema.json"


if __name__ == "__main__":
    print(json.dumps(resolve(load_json(HERE / "config.json")), indent=2))
