# Round 1 designs (reference only)

The deliverables each round 1 run handed in, as judged (`sim/judge_final/subs/<run>/`). Use them as starting material, baselines or negative examples.

**They target the old metric.** Round 1 ranked on the frozen fused-state score, which fills implant voids with bone, so several of these are minimal-material designs that do well there and badly on the round 2 objective (CHALLENGE.md). The best official design, `r2_best_of_n`, is a 1 mm wire loop whose own report says it targets the metric, not a clinical device. Scores and their context are in [`../analysis_why/WHY.md`](../analysis_why/WHY.md) (provisional); none are repeated here.

| folder | arm | files |
|---|---|---|
| `control` | deterministic Gibson-Ashby lattice, Rigid 10K | form, spec, report |
| `r1_single`, `r2_single` | one agent | form, spec, report |
| `r1_best_of_n`, `r2_best_of_n` | six isolated agents, best pre-check picked | form, spec, report |
| `r1_planner`, `r2_planner` | six agents, one lead writes | form, spec (r1 has no report; capped) |
| `r2_collective` | six peers, shared board | form, spec (no report; capped) |

`r1_collective` submitted nothing. `r1` and `r2` here are replicates of round 1 (both run the same night), not round 2.

`.form` files open in PreForm. **STL meshes are not included:** they live only in the source tree's `harness_open/submissions/<r1|r2>/<arm>/implant.stl` and `harness_open/submissions/control/gibson_ashby_rigid10k/implant.stl`, which the evaluator guard protects from being copied by tooling. PreForm can export the mesh from each `.form`.
