# The challenge: a bone-like spinal implant

This is the self-contained brief for any agent system, ours or yours, attempting the problem we ran at the ScienceClaw hackathon (Nov 2026). Give your system this file and the files it links. Round 2 of our run used the same goal and scoring; its exact brief is in [`round2/BRIEF_c1.md`](round2/BRIEF_c1.md). How to plug your system in and score it is in [`docs/BRING_YOUR_OWN_SYSTEM.md`](docs/BRING_YOUR_OWN_SYSTEM.md).

## Goal (verbatim)

"Make implants as mechanically homogeneous with bone as possible without losing integrity."

The bone is human lumbar vertebral body trabecular bone. The implant sits in it as an interbody block.

## Deliverables

One folder holding exactly these four files. A missing file means no submission.

| file | what it is |
|---|---|
| `implant.form` | A PreForm `.form` file of the implant, set up and validated for an on-site printer and resin (below): a **Form 4** or a **Form Studio 1**. |
| `implant.stl` | The same implant as a mesh (`implant.3mf` is also accepted), as modelled: **+Z is the cranial-caudal axis** (bone axis 3), X and Y are bone axes 1 (medio-lateral) and 2 (antero-posterior). Units mm. |
| `material_spec.json` | The material and its properties, each with a cited source. Any material is allowed; the printed demo will be one of the on-site resins. |
| `report.md` | Your report. Claims should link to evidence (files your system kept). |

### `material_spec.json` schema

Required: `material` (string) and `properties` with `E_MPa`, `nu` and `strength_MPa`, each an object with `value` (number) and `source` (string, a citation or a file path plus row). Optional per property: `tolerance`, `caveat`, `kind`. Optional top level: `material_family`, `printer_in_scene`, `graded` (bool), `regions` (list of `{body, material}`), `anisotropy`.

```json
{
  "material": "Tough 1500 V2 (printed, Form Studio 1)",
  "printer_in_scene": "Form Studio 1, 0.1 mm layers",
  "graded": false,
  "regions": [{"body": "implant", "material": "Tough 1500 V2 (printed, Form Studio 1)"}],
  "properties": {
    "E_MPa": {"value": 1136, "source": "data/analysis/results_all.csv, specimen DB-T-S1-FLAT-1, 1.1361 GPa, crosshead strain",
              "caveat": "crosshead-only strain reads low; datasheet 1460 MPa"},
    "nu": {"value": 0.35, "source": "sim/judge/reference_materials.json (assumed)"},
    "strength_MPa": {"value": 34.0, "kind": "ultimate tensile strength", "source": "Formlabs Tough 1500 V2 technical data sheet"}
  },
  "anisotropy": "none declared (isotropic voxels)"
}
```

The evaluator maps your material to the reference table by name (Rigid 10K, Tough 1500, PEEK, Ti-6Al-4V, cortical bone); otherwise by the nearest modulus to your declared `E`. Declared values replace the table's only when they are grounded in a cited source. Real examples: [`reference_designs/`](reference_designs/).

## Scoring (as in round 2)

1. **Primary score M**, from [`sim/EVAL_SPEC_v1_addendum4_goalmetric.md`](sim/EVAL_SPEC_v1_addendum4_goalmetric.md). The implant's convex hull is strained along 6 unit strains through its hull surface, with no surrounding bone, in two states: voids empty, and voids filled with bone (fused). The strain energy is split over about 5 mm windows; in each window D_W is the worst-direction |ln(stiffness / bone stiffness)|. Each state's score is the volume-weighted RMS of D_W, and **M is the worse of the two states**. Lower is better; 0 is identical to bone and e^M is the factor. M is extrapolated from two resolutions (Richardson); designs whose uncertainty bands overlap are **tied**, and ties are not broken.
2. **Integrity: the implant alone carries the load.** Voids empty, no bone sharing the load, every load case: the 99.5th-percentile von Mises stress at 2x load must be at or below strength / 2. Plus connectivity (G2: one face-connected body), size (G4: Z extent 8 to 18 mm, the larger in-plane extent 22 to 55 mm, the smaller 9 to 40 mm) and hull fill (hull volume / bounding-box volume at least 0.5). A design that fails integrity ranks below every design that passes.
3. **One further check, in another loading state, is applied at judging and is not described here.**
4. **For comparison only:** the frozen official fused-state score H from round 1 ([`sim/EVAL_SPEC_v1.md`](sim/EVAL_SPEC_v1.md), addenda 1 to 3) is also reported. It does not rank round 2 designs. See "What we learned" for why.

## Running the metric yourself

Python 3.10 or 3.11, `pip install -r requirements.txt`. The frozen code is `sim/goal_metric/goal_metric.py`; [`tools/score_local.py`](tools/score_local.py) runs it unchanged, except that it checks integrity on the 3 visible load cases (the 4th, sealed case stays with the evaluator).

```
# coarse: the frozen fallback (h2 = 0.4 mm, h1 = 0.8 mm), what round 2 agents could run; cap the size for a laptop
python tools/score_local.py --mesh my_run/implant.stl --material tough1500 --out gm_coarse.json --fallback --max-dof 1e6
# full: the evaluator's resolution (h2 = 0.2 mm, coarsened until the box is at most 20 M unknowns)
python tools/score_local.py --mesh my_run/implant.stl --material tough1500 --out gm_full.json
```

`--material` takes a reference name (`rigid10k`, `tough1500`, `peek450g`, `ti6al4v`, `cortical_bone`), or give `--E --nu --strength` directly. Memory is about 6 GB per million unknowns: the coarse run with `--max-dof 1e6` needs about 6 GB; the full run can need 30+ GB (see addendum 4 §A4.5 and [`sim/judge/BREV_BATCH.md`](sim/judge/BREV_BATCH.md)). The output JSON has `M_R`, `band`, per-state `Q`, and `gates`. In round 2, agents had only the coarse run (at most 1M unknowns); final judging uses the full resolution.

## Materials

**Measured calibration** ([`sim/calibration.json`](sim/calibration.json), fitted 2026-11-01 00:11 EST, from the Breakerspace tests in [`data/`](data/README.md)):

| resin | printer | E used (MPa) | ν | strength / allowable (MPa) |
|---|---|---|---|---|
| Rigid 10K | Form 4 | 8018 | 0.35 | 65 |
| Tough 1500 V2 | Form Studio 1 | 1136 | 0.35 | 34 (judge table) / 33 (calibration) |

Both moduli come from **crosshead-only** strain, which includes machine compliance and reads low. Datasheet moduli: Rigid 10K about 10 to 11 GPa, Tough 1500 V2 1460 MPa; Form 4 Tough 1500 specimens gave 1.28 and 1.44 GPa.

**Reference table** ([`sim/judge/reference_materials.json`](sim/judge/reference_materials.json)), used for anything else:

| key | E (MPa) | ν | strength (MPa) | source |
|---|---|---|---|---|
| `peek450g` | 4000 | 0.40 | 98 | Victrex PEEK 450G datasheet, ISO 527-1 |
| `ti6al4v` | 113800 | 0.342 | 880 | ASM Aerospace Specification Metals, Grade 5 annealed |
| `cortical_bone` | 17900 | 0.30 | 130 | Morgan et al. 2018, Table 1 (longitudinal; isotropic approximation) |

## Bone targets and load cases

The target is the lumbar vertebra's orthotropic stiffness, block axes (1 medio-lateral, 2 antero-posterior, 3 cranial-caudal), Voigt order 11, 22, 33, 23, 13, 12, engineering shear, MPa:

```
[[244.69,  97.72, 116.10,   0,     0,     0   ],
 [ 97.72, 284.23, 127.09,   0,     0,     0   ],
 [116.10, 127.09, 795.66,   0,     0,     0   ],
 [  0,      0,      0,    147.0,   0,     0   ],
 [  0,      0,      0,      0,   130.5,   0   ],
 [  0,      0,      0,      0,     0,    81.9 ]]
```

E1 204, E2 236.4, E3 714 MPa; G12 81.9, G13 130.5, G23 147 MPa; ν12 0.30, ν13 0.098, ν23 0.109. Source: Oefner et al., *Med Biol Eng Comput* 60 (2022) 263-278, Table 4 means (micro-FE, tissue modulus 15 GPa, L1-L5 of 3 osteoporotic or osteopenic donors, BV/TV 0.133); the transposed Poisson's ratios are derived by symmetry.

Visible load cases (stress, Voigt order above, MPa), from Rohlmann et al., *PLoS ONE* 9 (2014) e98510, telemeterised vertebral body replacement loads, converted with a beam model of an elliptical centrum (A 1237 mm²):

| case | stress | source |
|---|---|---|
| relaxed_standing | σ33 = -0.75 | intradiscal pressure 0.5 MPa x 1.5 (assumed disc-area factor) |
| upper_body_flexion | σ33 = -1.3624, τ23 = 0.10509 | Table 2 peak force 1075 N, Table 5 shear 130 N, Table 3 bending 6.23 Nm |
| axial_rotation_standing | σ33 = -0.75, τ13 = 0.09402 | Table 4 torsion 3.15 Nm, axial stress as standing (assumed) |

A 4th physiological case from the same tables is sealed and used only by the evaluator. Every source, derivation and assumption is in [`targets/SOURCES.md`](targets/SOURCES.md). The frozen judge reads these from `targets/targets.json`, which is held back from this copy for now (see [`data/README.md`](data/README.md)); until it is added, the numbers above are the reference.

## On-site printers and resins

Form 4 or Form Studio 1, in Tough 1500 V2, Rigid 10K, Alpha Clear or Alpha Fast. You may propose another material, but a printed demo will be one of these. The `.form` must be valid in PreForm for one of these printer and resin pairs. Printing itself was not available to agents.

## Time and budget we used (reference, not rules)

| | round 1 | round 2 |
|---|---|---|
| wall time | 2 h per session | **75 min per agent** (one shared group start), notices at 30 and 15 min before close |
| model credits | 2.5M for a single agent; 0.42M each in six-agent arms | 1.0M per agent, six agents, no roles |
| GPU (Brev) | $15 per run | $60 pool shared by the six agents, at most 2 live instances each |
| API spend | cap $180 for the night | cap $125.35 |

Credits = input + cache creation + 0.1 x cache read + output tokens, plus tool charges ([`harness_open/meter.py`](harness_open/meter.py)). Use whatever limits suit your system, but report them, so the comparison is fair.

## What we learned (round 1)

- **Agents optimized the disclosed metric, not the goal.** Round 1 scored the fused state only, and every arm read that metric within minutes and designed to it. The best official design was a 1 mm wire loop, found by one isolated agent in about 9 minutes with 19% of its credits. Its own report says: "**This design targets the metric, not a clinical device.** A 1 mm wire loop has no endplate bearing area, no graft containment and no insertion features." ([`reference_designs/r2_best_of_n/report.md`](reference_designs/r2_best_of_n/report.md)). This is why round 2 scores the worse of the empty and fused states, with the implant carrying the load alone.
- **The sole-writer failure.** In one collective, the agents agreed that only c1 would write the deliverables. c1 posted its pipeline as ready and ran out of credits 10 seconds later; the arm submitted nothing ([`analysis_process/highlights.md`](analysis_process/highlights.md) §1). Any single point of failure in who writes the final files is a risk.
- **Quota exhaustion in six-agent arms.** 33 of 36 agents in six-agent arms ran out of credits, most 19 to 29 minutes in, so collectives shipped first drafts or nothing, while both single agents stopped on their own with over half their 2.5M unspent ([`analysis_process/metrics.md`](analysis_process/metrics.md), [`analysis_why/WHY.md`](analysis_why/WHY.md) E7).
- **Pre-check bugs.** The best-of-N pick relied on a pre-check that timed out at 900 s, read the wrong key (`H` for `H_avg`), dropped agents without a report, and crashes without `material_spec.json`. The rule was applied by hand afterwards ([`sim/EVAL_SPEC_v1_addendum3.md`](sim/EVAL_SPEC_v1_addendum3.md); README "Honest limits"). Check your own selection code on real outputs before the run.
- **At n = 2, no arm-level difference survived:** replicates differed as much as arms ([`analysis_why/WHY.md`](analysis_why/WHY.md), provisional).

## Files

- Spec: [`sim/EVAL_SPEC_v1.md`](sim/EVAL_SPEC_v1.md), addenda [1](sim/EVAL_SPEC_v1_addendum.md), [2](sim/EVAL_SPEC_v1_addendum2.md), [3](sim/EVAL_SPEC_v1_addendum3.md), [4 (goal metric)](sim/EVAL_SPEC_v1_addendum4_goalmetric.md)
- Code: [`sim/goal_metric/`](sim/goal_metric/), [`sim/judge/`](sim/judge/), [`tools/score_local.py`](tools/score_local.py)
- Data: [`data/README.md`](data/README.md), [`sim/calibration.json`](sim/calibration.json), [`targets/SOURCES.md`](targets/SOURCES.md), [`citations/CITATIONS.md`](citations/CITATIONS.md)
- Round 1 designs: [`reference_designs/`](reference_designs/README.md); analysis: [`analysis_why/WHY.md`](analysis_why/WHY.md) (provisional), [`analysis_process/`](analysis_process/)
- Round 2 brief: [`round2/`](round2/README.md)
