# EVAL_SPEC v1 addendum A3 (2026-11-01, ~07:15 EST; written before any final scoring started)

This addendum records deviations from `EVAL_SPEC_v1.md` and addenda A1 and A2 that the user decided on. Judge code is unchanged (`judge/JUDGE_MANIFEST.sha256`, verified at 06:44). Everything below uses existing command-line options and input files only.

## A3.1 Resolution cap (changes the number in §6)

§6 caps the box at **25 M DOF**. The cap for this scoring is **20 M DOF, applied uniformly to every submission** through `judge.py --max-dof 20e6`. §6's rule is otherwise unchanged: h2 = 0.2 mm, multiplied by 1.1 until the box fits; h1 = 2·h2.

**Why.** The machine is one Brev L40S with 8 vCPU and 144 GB RAM (the solver does not use the GPU), and the judge pool is $10, of which $2.05 was spent when this was written.
- **Memory:** 4.4 GB per M DOF measured on the laptop in a run that included full-re-solve G3. On this box, about 2.9 GB per M DOF during pre-checks (46 GB at 16.7 M DOF).
- **Time:** about 90 s per M DOF for a 3-case level, measured on this box with 3 parallel runs (r2_b3: 6.3 M DOF, 567 s).
- **Estimate:** at 20 M the batch ends at about 10:40 and costs about $8.2 in total. At 25 M the estimate ends past 11:00 and leaves little of the pool, with two jobs at about 135 GB together.

**Effect of the cap.** It changes h for the two largest designs only. Thin-wall figures are my estimate from z-slices at 0.05 mm (2 × distance-to-edge on the medial ridge; 5th percentile / median), not a judge output.

| run | DOF at h = 0.2 (M) | h2 / h1 (mm) | box DOF (M) | thin wall p5 / median (mm) | voxels across at h2 (p5 / median) |
|---|---|---|---|---|---|
| r1_single | 4.1 | 0.2 / 0.4 | 4.07 | 1.5 / 1.5 | 7.5 / 7.5 |
| r2_single | 4.2 | 0.2 / 0.4 | 4.23 | 0.3 / 0.5 | **1.5** / 2.5 |
| r2_collective | 4.3 | 0.2 / 0.4 | 4.34 | 0.6 / 0.6 | 3.0 / 3.0 |
| r1_planner | 11.2 | 0.2 / 0.4 | 11.18 | 3.1 / 3.5 | 15.5 / 17.5 |
| r2_planner | 13.4 | 0.2 / 0.4 | 13.39 | 2.7 / 2.7 | 13.5 / 13.5 |
| control | 13.6 | 0.2 / 0.4 | 13.64 | 0.4 / 0.8 | 2.0 / 4.0 |
| r1_best_of_n | 32.4 | **0.242 / 0.484** | 18.47 | 1.1 / 1.1 | 4.5 / 4.5 |
| r2_best_of_n | 49.2 | **0.293 / 0.586** | 15.82 | 1.1 / 1.1 | 3.8 / 3.8 |

**Below 2 voxels across at h2:** only r2_single at its thinnest walls (p5). This comes from the spec's h2 = 0.2, not the cap, and is not changed. At the coarse level h1, these are below 2 voxels at p5: r2_single (0.75), r2_collective (1.5), control (1.0), r2_best_of_n (1.9).

## A3.2 How the runs are split (same numerics, less memory)

`judge.py` keeps the primary state in memory while it computes the early state, which doubles peak memory. So each submission runs as separate processes using existing options:
- **Primary:** `--no-early`, with gates G1-G4.
- **Early state (A2.2):** `--graft 0.0779625386332731 --no-early --no-g3`. This is g_early = 30 MPa / mean axial bone modulus, the value `judge.py` computes itself. Its levels, H and H_avg are copied unchanged into the `secondary_early` block before ranking.
- **Datasheet sensitivity (§5a):** the primary state only, `--datasheet --no-early`, with gates. It is not run for the early state. It is run for the resin arms (control, r1_best_of_n, r2_best_of_n, r2_single). For arms whose moduli are grounded declarations (r1_single, r1_planner, r2_planner, r2_collective), the inputs are identical, so the primary output is reused and labelled as such.

## A3.3 Materials (reading of §5 and §5a)

For Rigid 10K and Tough 1500 V2, E always comes from the reference table: measured in the primary run, datasheet in the sensitivity run. This holds even when a declared value passes grounding (the control declares 10000 MPa, grounded, and also its calibrated 8017.8). All other properties follow the independent checker's verdict (`judge_final/grounding_check/`).

## A3.4 best_of_n pick: bug and pre-registered rule applied

**The bug.** At collection, the harness's pick did not apply the pre-registered rule (lowest pre-check H among agents passing the gates):
- pre-check calls hit a 900 s timeout;
- the harness read `estimate_key` "H" where `precheck.py` prints `H_avg`;
- agents without `report.md` were excluded from pre-check.

Both arms fell back to the seeded random pick.

**The rule applied now** (user decision, logged deviation): the frozen `precheck.py` is run on every best_of_n agent with `deliverables/implant.form`, and the lowest H_avg passing the gates becomes the arm's entry.

**Values.** They were produced with no change to judge code. Two inputs were adjusted without touching code:
- The Brev runs used a mesh that passed the PreForm hash match, the PreForm intake record with its mesh path rewritten, and a spec holding the declared material name.
- `precheck.py` raises `KeyError: 'raw_contains'` when `material_spec.json` is absent, so r2_b2 (no spec) was given an empty `{}` spec, which selects the scene-resin fallback as A1.1 intends.

Of the 8 pre-checks, 3 (r1 b1, b3, b4) ran on the laptop and 5 (r1 b2, r2 b2, b3, b4, b5) on Brev, with the same code (the manifest's files, verified against `JUDGE_MANIFEST.sha256`). r2_b5, also run on the laptop as a cross-check, gives the same H_avg to 10 digits on both. This sentence was reworded at about 07:15, after scoring started at 07:13, at the coordinator's request; no number or rule changed. The pre-check runs at h = 0.4 on visible cases only, with gates G1, G2 and G4, and reference-table materials only.

| agent | H_avg | raw H | material used (E, MPa) | G1 p99.5 at 2× / allowable (MPa) | G2 | G4 | gates | DOF |
|---|---|---|---|---|---|---|---|---|
| r1 b1 | 0.03427 | 0.03632 | Tough 1500 (1136) | 4.25 / 17.0 | ok | ok | pass | 0.50 M |
| **r1 b2** | **0.01609** | 0.01728 | Tough 1500 (1136) | 4.33 / 17.0 | ok | ok | pass | 4.16 M |
| r1 b3 | 0.01836 | 0.01993 | Tough 1500 (1136) | 3.92 / 17.0 | ok | ok | pass | 0.47 M |
| r1 b4 | 0.03842 | 0.04043 | Tough 1500 (1136) | 4.22 / 17.0 | ok | ok | pass | 0.49 M |
| r2 b2 | 0.23072 | 0.23618 | Rigid 10K (8018), no spec: scene-resin fallback | 18.66 / 32.5 | ok | ok | pass | 0.50 M |
| **r2 b3** | **0.00703** | 0.00786 | Tough 1500 (1136) | 4.35 / 17.0 | ok | ok | pass | 6.30 M |
| r2 b4 | 0.01349 | 0.01482 | Tough 1500 (1136) | 4.33 / 17.0 | ok | ok | pass | 6.21 M |
| r2 b5 | 0.05442 | 0.05624 | Tough 1500 (1136) | 4.23 / 17.0 | ok | ok | pass | 0.42 M |

**Result: the rule picks r1 b2 and r2 b3, the same agents as the as-collected picks.** The arm entries therefore do not change, and no extra submissions are scored.

r1 b5 and b6 have only `work/test.form` and no `deliverables/implant.form`, so they are not entries. r2 b1 and r1 b6 have no implant.form in their collected deliverables.
