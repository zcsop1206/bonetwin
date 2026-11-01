# Reference designs (reference only)

The deliverables each round 1 run handed in, as judged (`sim/judge_final/subs/<run>/`), plus the round 2 collective's (`r2_collective_round2/`, scored in [`../RESULTS.md`](../RESULTS.md)). Use them as starting material, baselines or negative examples.

**They target the old metric.** Round 1 ranked on the frozen fused-state score, which fills implant voids with bone, so several of these are minimal-material designs that do well there and badly on the round 2 objective (CHALLENGE.md). The best official design, `r2_best_of_n`, is a 1 mm wire loop whose own report says it targets the metric, not a clinical device. Scores and their context are in [`../analysis_why/WHY.md`](../analysis_why/WHY.md) (provisional); none are repeated here.

| folder | arm | PreForm machine / material in the .form | files |
|---|---|---|---|
| `control` | deterministic Gibson-Ashby lattice | Form 4 / Rigid 10K | form, spec, report |
| `r1_single` | one agent | Form 4L / Tough 1500 V2 | form, spec, report |
| `r2_single` | one agent | Form 4 / Tough 1500 V2 | form, spec, report |
| `r1_best_of_n` | six isolated agents, best pre-check picked | Form 4L / Tough 1500 V2 | form, spec, report |
| `r2_best_of_n` | six isolated agents, best pre-check picked | Form Studio 1 / Tough 1500 V2 | form, spec, report |
| `r1_planner` | six agents, one lead writes | Form 4L / Tough 1500 V2 | form, spec (no report; capped) |
| `r2_planner` | six agents, one lead writes | Form Studio 1 / Tough 1500 V2 | form, spec, report |
| `r2_collective` | six peers, shared board | Form 4L / Tough 1000 | form, spec (no report; capped) |
| `r2_collective_round2` | round 2: leaderless six-agent collective (see its README) | Form 4L (machine code FRML-4-0, which its report wrongly calls Form 4) / Tough 1500 V2; the evaluator re-sliced it for Form 4 and Form Studio 1 | stl, form, spec, report |

The machine and material are what each original `.form` targets. The declared `material_spec.json` material differs for some: UHMWPE for `r1_single`, `r1_planner` and `r2_planner`, Tough 1000 for `r2_collective`. Those were not printable on site, so the prints were stand-ins.

`r1_collective` submitted nothing. `r1` and `r2` here are replicates of round 1 (both run the same night), not round 2.

`.form` files open in PreForm. **Round 1 STL meshes are not included** (the round 2 folder ships its STL): they live only in the source tree's `harness_open/submissions/<r1|r2>/<arm>/implant.stl` and `harness_open/submissions/control/gibson_ashby_rigid10k/implant.stl`, which the evaluator guard protects from being copied by tooling. PreForm can export the mesh from each `.form`.
