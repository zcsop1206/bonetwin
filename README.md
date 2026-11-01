# bonetwin

Reusable tools from one overnight experiment at the ScienceClaw hackathon (Nov 2026). Groups of Claude Code agents, arranged in different ways, tried to design a spinal implant that is mechanically like bone, and a frozen simulation judged what they handed in. This repo holds the tools, the challenge brief, the Breakerspace test data behind the material calibration, round 1's submitted designs as references, and a provisional analysis. It holds no run boards, knowledge bases or transcripts.

This is unpolished hackathon code. It is not production ready and is not a medical or clinical tool. Licence: MIT, copyright 2026 Adit Bhargava and Alan Chen (see `LICENSE`).

**Run your own system on the same problem:** [`CHALLENGE.md`](CHALLENGE.md) is the self-contained brief and scoring; [`docs/BRING_YOUR_OWN_SYSTEM.md`](docs/BRING_YOUR_OWN_SYSTEM.md) shows how to score your deliverables and measure your system's centralization the same way as ours.

Built by Adit with teammate Alan. The shared board (`harness_open/board.py`) descends from Alan's earlier agent harness, and the spec cites his print and video tracking.

## What is here

| Folder | What it does |
|---|---|
| `harness_open/` | **Arena.** Launches agents in arms (single, best of N, collective, planner), with identical briefs, a credit meter, a shared board, an admission-controlled scheduler, deadline collection, and checks that each arm did what it claims. Also the metrics code (`process_metrics.py`, `centralization.py`, `directives.py`). |
| `compute/` | **Compute management.** `bt_compute.py` is the only door agents get to Brev GPUs, with per-run dollar caps and a ledger. `reaper.py` deletes idle, over-cap or orphaned instances. |
| `guard/` | **Evaluator guard.** A Claude Code PreToolUse hook that stops the evaluating session from reading arm internals before an unlock time, writing them at all, or touching frozen files. Deterministic regex rules, fail-closed. See `guard/README.md`. |
| `sim/judge/` | **Judge.** Voxel finite elements of an implant embedded in orthotropic bone: a strain-energy mismatch score at two resolutions, a Richardson band where overlapping bands tie, strength and connectivity gates, and ranking. Specs are `sim/EVAL_SPEC_v1.md` and addenda 1 to 4. |
| `sim/goal_metric/` | A second, exploratory metric: the implant region's stiffness against bone's, empty and fused. |
| `CHALLENGE.md`, `docs/BRING_YOUR_OWN_SYSTEM.md`, `tools/score_local.py` | The brief for any agent system, the integration guide, and a wrapper that runs the frozen goal metric without the sealed load case. |
| `data/` | Breakerspace test results, specimen map and machine CSV exports (`data/README.md` lists what is still held back). |
| `reference_designs/` | Round 1 deliverables (.form, material spec, report). They target the old metric. |
| `round2/` | The round 2 brief (redacted) and its change log. |
| `analysis_why/WHY.md`, `analysis_process/*.md`, `citations/` | Provisional analysis of round 1, process findings, and the citation list. |
| `figures/scripts/`, `analysis_process/scripts/` | Plotting and process-analysis scripts. They expect this run's data, which is not here, and hard-code some of its labels and checks. Read them as examples. |

`FROZEN_HASHES.md` lists the frozen files and their original hashes. Three were edited for this public copy, to remove a personal path and PreForm API detail: `docs/FROZEN_CHANGES.md` gives each one's original and new hash, and `ISSUES/fix-hashes.md` describes the consequence.

**PreForm.** All PreForm use goes through `preform_tool.py`, which ships as a mock. This copy contains no PreForm endpoint names, request bodies or API documentation. To use real PreForm you need your own authorized access: write an adapter with the same functions and set `BT_PREFORM_ADAPTER` to its file path.

## How to run

Python 3.10+. Most of the code was only run on Windows.

```
pip install -r requirements.txt
```

**Arena in mock mode** (fake agents, mock PreForm and compute; no API key, PreForm or GPU):

```
cd harness_open
copy config.template.json config.json      (cp on macOS or Linux)
python launch_open_run.py --mock --mock-tools --root smoke/try1 --batches 1 --wall-cap-min 2 --min-free-ram 0.5 --dry-run
python smoke_test.py --root smoke/try2 --timeout 600
```

The dry run prints the schedule, budgets and brief check. The smoke test runs 19 fake sessions plus the control under the real scheduler, then checks collection, the meter, refusals and metrics. Keep roots under `smoke/`. On a small machine, lower `admission.max_sessions` in `config.json`. Optional tools (`cad_python`, `warp_gpu`, FreeCAD) report themselves unavailable when their modules are missing. From a fresh clone it passes 35 of 36 checks; the one failure is the known best-of-N pre-check bug under "Honest limits", where the pick falls back to a seeded random choice.

Evaluate a mesh with the judge (CPU only). You must supply `targets/targets.json` and `targets/sealed_case.json`, which are not shipped (`sim/calibration.json` now is; `tools/score_local.py` runs the goal metric without the sealed case); `targets/SOURCES.md` and `sim/EVAL_SPEC_v1.md` describe them.

```
cd sim/judge
python judge.py --mesh implant.stl --material ti6al4v --out result.json
```

Goal metric, same inputs:

```
cd sim/goal_metric
python goal_metric.py --mesh implant.stl --material ti6al4v --out result.json
```

Guard: see `guard/README.md`.

Compute: copy `compute/caps.template.json` to `compute/caps.json`, install the Brev CLI in WSL, then `python bt_compute.py quote` and `python reaper.py --dry-run`.

**Real runs need more than this repo.** Real agents need the Claude Code CLI and an Anthropic account; real `.form` files need PreForm through your own adapter; Brev compute needs `compute/caps.json` and the Brev CLI. The judge's `.form` intake (`judge_intake.py`, `judge_submission.py`, `precheck.py`) goes through the adapter, so with the mock it only checks wiring; `judge.py` on a mesh needs no PreForm.

## Hardware

- The arena ran on one Windows laptop with about 35 GB of commit limit. It ran out of room at 12 to 14 sessions, so plan for more.
- The judge is CPU and RAM bound and does not use a GPU. Measured about 3 to 4.4 GB per million unknowns; the largest jobs ran on a rented 8 vCPU, 144 GB machine.
- GPU compute for agents was rented through Brev.

## Honest limits

- **The 00:52 freeze.** The first launch started all 38 sessions at once, each with a visible console window, and froze the laptop. It was aborted and nothing from it was scored. The current scheduler admits sessions by slot, free RAM and CPU, and runs them hidden. Later that night memory still reached 94 to 98.6% of commit, and large Python jobs vanished for unknown reasons, so silent kills cannot be ruled out.
- **The scheduler bug and its fix.** At 03:50 a scheduler restart with `--recover` started duplicate runners for all 14 live agents for 1 to 2 minutes. Recovery now checks liveness by pid, creation time and command line (`procs.py`), and respawns an agent at most once, only after a mid-turn crash.
- **The pre-check bugs.** The best-of-N pick did not apply its rule at collection: pre-check calls hit a 900 s timeout, the config read key `H` where `precheck.py` prints `H_avg`, and agents without a report were left out. `precheck.py` also raises `KeyError` when `material_spec.json` is absent. The template fixes the key name only; the timeout, the report exclusion and the `KeyError` remain. The rule was applied by hand afterwards, as addendum 3 records.
- **The frozen fused-state metric can be gamed.** It fills implant voids with bone before scoring, so a very low-material design barely disturbs the bone and scores well without being a usable implant. Agents could read the metric. Do not read a good score on it as a good implant.
- **The goal metric is exploratory.** It was added after the run and does not replace the official metric. Its known-answer shapes were tuned against it and its pass criterion was loosened after the first test; addendum 4 records both.
- **Other assumptions.** Resin moduli come from crosshead-only tests that read low. The bone is homogeneous and perfectly bonded. Fatigue is not assessed. The Linux and Docker paths were barely exercised. Many comments, dates and dollar figures still describe that one night.
- **Addendum 3 contains pre-check values** from the run, because it is a frozen record. They are coarse selection numbers, not scores.

## Left out on purpose

Run data, boards, knowledge bases, transcripts, submission STLs and selection files, sealed cases, keys, ledgers, logs, print packages and PreForm binaries. `targets/targets.json` is also left out, and so is the target generator, which holds the sealed case. `compute/MEMORY_GOVERNOR_RULE.md` is omitted because that rule was written but never enforced. These scripts were dropped because they embed agents' board or knowledge-base content or hard-coded results: `figures/scripts/` `sole_writer.py`, `ev_preform.py`, `ev_warp.py`, `contest.py`, `ev_specimens.py`, `ev_triangulation.py`; `analysis_process/scripts/` `apply_edits.py`, `verify_highlights.py`.
