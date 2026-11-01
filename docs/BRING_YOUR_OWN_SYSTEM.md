# Bring your own system

How to run your own (decentralized or not) agent system on [`CHALLENGE.md`](../CHALLENGE.md) and get numbers that compare directly with ours. Your system can be anything; it only has to produce the folder below and, if you want the process compared, a board log in our format.

## 1. What your system must produce

```
<your_root>/
  <run_id>/                       e.g. alan_r1, alan_r2 (one folder per replicate)
    deliverables/
      implant.form                PreForm file for a Form 4 or Form Studio 1 (see section 4)
      implant.stl                 or implant.3mf; +Z cranial-caudal, X/Y bone axes 1/2, mm
      material_spec.json          schema in CHALLENGE.md
      report.md
    board.jsonl                   optional: every message between your agents (section 5)
    arm.json                      optional: {"agents": ["a1", "a2", ...]} so silent agents count as nodes
    run.json                      your limits and usage: wall time per agent, credits or tokens, $ spent, model
```

Freeze `deliverables/` at your deadline (copy it and record SHA-256 of each file) before scoring. That is what our `harness_open/collect.py` does.

## 2. Score it

Python 3.10 (what we ran) or 3.11 (what the spec's container uses). On Windows, macOS or Linux:

```
python -m venv .venv
.venv\Scripts\activate            (source .venv/bin/activate on macOS or Linux)
pip install -r requirements.txt   (numpy scipy pyamg trimesh manifold3d pillow matplotlib)
```

**Goal metric M with the integrity rule** (the round 2 objective). From the repo root:

```
# quick, laptop-sized (about 6 GB): the frozen coarse fallback, capped at 1M unknowns, as round 2 agents ran it
python tools/score_local.py --mesh <your_root>/<run_id>/deliverables/implant.stl --material tough1500 --out results/<run_id>_gm_coarse.json --fallback --max-dof 1e6
# full resolution, as judged (30+ GB for large designs; use a rented CPU box, section 3)
python tools/score_local.py --mesh <your_root>/<run_id>/deliverables/implant.stl --material tough1500 --out results/<run_id>_gm_full.json
```

Use the material your `material_spec.json` names: a reference key (`rigid10k`, `tough1500`, `peek450g`, `ti6al4v`, `cortical_bone`) or `--E <MPa> --nu <ν> --strength <MPa>` for a grounded declared material. `tools/score_local.py` runs the frozen `sim/goal_metric/goal_metric.py` and checks integrity on the 3 visible load cases; the sealed 4th case and the undescribed further check run on our side.

**Frozen official judge** (round 1's fused-state score H, reported for comparison only):

```
cd sim/judge
python judge.py --mesh ../../<your_root>/<run_id>/deliverables/implant.stl --material tough1500 --out ../../results/<run_id>_official.json
```

`judge.py` needs `targets/targets.json` and `targets/sealed_case.json`; neither is in this copy (see [`data/README.md`](../data/README.md)). Send us the deliverables folder and we run the official judge and the full goal metric with the sealed case, the same way for your runs and ours.

**Identical scoring.** Same code (check `sim/judge/JUDGE_MANIFEST.sha256` and `sim/goal_metric/GOAL_MANIFEST.sha256`; the one known mismatch is described in [`ISSUES/fix-hashes.md`](../ISSUES/fix-hashes.md)), same material table, same resolution rule, same tie rule. Score every design at the same level: all coarse or all full, never mixed.

## 3. Compute on Brev, with your own account

`compute/bt_compute.py` is a thin, capped wrapper around the Brev CLI: per-run dollar caps, a ledger, and `compute/reaper.py` to delete idle or over-cap instances.

1. Make your own Brev account and add credit. Install the Brev CLI (we ran it inside WSL on Windows) and run `brev login` there. Credentials stay in Brev's own config in your home folder, never in this repo.
2. `copy compute\caps.template.json compute\caps.json` (gitignored). Set `brev` to the CLI path, `wsl_distro`, your total cap, and one entry per run under `runs`.
3. Optional NGC key for `nvcr.io` pulls: keep the key file outside the repo and set `BT_NGC_KEY_FILE=<path>`. Set `BT_RUN=<run name>` so every call is charged to that run.
4. Use:

```
python compute/bt_compute.py quote
python compute/bt_compute.py start --type L40S --run alan_r1 --name box1 --wait
python compute/bt_compute.py copy-to --run alan_r1 --name box1 <local_dir> /home/ubuntu/w
python compute/bt_compute.py exec --run alan_r1 --name box1 -- "cd /home/ubuntu/w && python tools/score_local.py ..."
python compute/bt_compute.py stop --run alan_r1 --name box1
python compute/reaper.py --dry-run
```

The judge and goal metric are CPU and RAM bound: for full-resolution scoring rent a high-memory CPU box (we used 8 vCPU, 144 GB; see [`sim/judge/BREV_BATCH.md`](../sim/judge/BREV_BATCH.md)). GPUs only help your agents' own tools (Warp etc.). Never commit `caps.json`, keys, or `compute_ledger.jsonl`.

## 4. PreForm

All PreForm use in this repo goes through [`preform_tool.py`](../preform_tool.py), which ships as a **mock**: it returns plausible shapes and writes no real `.form`. It is enough to test wiring (`python harness_open/smoke_test.py ...` uses it).

A real, valid `implant.form` needs **your own authorized PreForm Server** (or the PreForm desktop app, saving by hand). To connect it, write an adapter with the same functions as `preform_tool.py` (`create_scene`, `import_model`, `auto_support`, `auto_layout`, `validate`, `save_form`, `list_settings`, `estimate_time`, ...) using your own licensed access and documentation, and set `BT_PREFORM_ADAPTER=<path to your adapter.py>`. This repo contains no PreForm endpoint names or API documentation, and the adapter should not be committed here.

## 5. Make the decentralization measurable

To compare your organization with ours, log every inter-agent message as one JSON line in `board.jsonl`, in our board's format ([`harness_open/board.py`](../harness_open/board.py)):

```json
{"id": "p0007", "ts": "2026-11-01T08:47:24+00:00", "author": "a3", "human": false, "kind": "claim",
 "text": "@a1 please run the coarse metric on v2", "parents": ["p0005"],
 "meta": {"links": [{"type": "cites", "post": "p0004"}], "to": null, "review_of": null}}
```

- `id` unique and increasing (`p0001`, ...); `author` your agent id (short ids like `a1` make `@a1` mentions count); `parents` the post ids it replies to.
- `kind`: `need`, `claim`, `review`, `chat`, `evidence`, `assign`, `candidate`, `final`, `transfer`. Use `assign` only for explicit top-down task assignment; `transfer` with `meta.to` for any resource handover.
- `meta.links`: typed links `cites`, `contradicts`, `extends`, `replicates`. `meta.review_of`: the post a review targets.
- If your agents talk through another channel (shared files, direct calls), convert each message into one post; one post per message, not per token.

Then:

```
python harness_open/centralization.py --board <your_root>/<run_id>/board.jsonl --out-dir results/<run_id>_central
```

It reports Freeman degree centralization (1 = star, 0 = everyone equal), in-degree centralization, betweenness (max and who), the top poster's share of posts, the top receiver's share, edges by type, directive posts per agent and an emergent leader if one agent issues more than twice its share of directives, plus GraphML and PNG. The directive rule is [`harness_open/directives.py`](../harness_open/directives.py): an `assign` post, or an `@mention` of another agent in a sentence that starts with an imperative verb or says "please", "can you", and so on. Our round 1 and round 2 numbers come from the same two files, so yours are directly comparable. Also report the share of final-deliverable writes per agent and per-agent credit use, which we found decisive (see CHALLENGE.md, "What we learned").

[`harness_open/process_metrics.py`](../harness_open/process_metrics.py) adds tool-usage entropy and artifact lineage; it expects our run layout, so read it as the definition if your layout differs.

## 6. Reproduce our setup instead

To run our arena (mock first, no keys needed), follow the README's "How to run". To use it as a host for your agents, `harness_open/agent_runner.py` is the one place that starts an agent process.
