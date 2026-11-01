# Why the results are what they are

**Status: PROVISIONAL, 2026-11-01 about 09:05 EST.** Official scores exist for 7 of 7 submissions except r2 planner; early-graft scores for 3; datasheet runs for 2; goal metric not yet run. Numbers marked *h 0.8* or *h 0.4* are illustrative counterfactuals from the frozen judge functions at coarse resolution (`data/cf_results.jsonl`, `data/cf2_results.json`), not judge results. Fact = has a file path; Inference = labelled. Written against `PLAN.md` (fixed 08:22, before final scores were opened).

## The answer in one paragraph

Every arm read the disclosed metric within minutes and designed to it, so the official ranking mostly measures **which loophole an arm found**, not which organization designs better implants. The fused-state score fills every void with bone, so it is driven by two things: how far the strut material is from bone (material contrast) and how much material touches the scored bone (volume, especially on the hull surface). Arms split into two strategies: **minimize material in a stiff-ish resin** (both best-of-N picks, r2 collective, r2 single) or **match bone's modulus with UHMWPE** (r1 single, both planners), which is not printable on site. The minimal-material strategy wins the fused score and collapses in the early-graft state, where the graft is soft and the struts must carry the load: there a *solid block* of Tough 1000 or 1500 beats every agent design (h 0.8). The best official design, r2 best-of-N's 1 mm wire loop, was found by one isolated agent in about 9 minutes using 19% of its credits, and its report says it "targets the metric, not a clinical device". Differences between replicates of the same arm are as large as differences between arms, so at n = 2 **no arm-level difference survives**. What the experiment does show is mechanism: how groups explored, where their work was lost, and how a disclosed proxy shaped every design.

## What I'd say on stage (three sentences)

1. "All 38 agents found the scoring rule within minutes and optimized it; the top official design is a 1 mm wire loop whose own agent told us it games the metric."
2. "The collective did the most genuine science on the board (material physics, scaling laws, an integrity warning), but every agent ran out of credit 19 to 29 minutes in, so only its first draft shipped."
3. "With two runs per arm we can't crown an organization; we can show exactly why each design scored as it did, and we've changed the metric and the budget rules in round 2 because of it."

## Results so far (official, lower is better)

| Design | Material (E, MPa) | Solid vol. fraction of hull | Official fused H_R [band] | Early-graft H_R | Early G1 at 2x / allowable (MPa) |
|---|---|---|---|---|---|
| r2 best-of-N (b3 loop) | Tough 1500 (1136, measured) | 0.8% | 0.0053 [0.0040, 0.0066] | pending | pending |
| r2 collective | Tough 1000 (932, datasheet) | 5.6% | 0.0104 [0.0095, 0.0112] | 1.73 | 45.0 / 13.2 FAIL |
| r1 single | UHMWPE (720) | 41% | 0.0189 [0.0178, 0.0201] | **0.42** | 13.3 / 8.5 FAIL |
| r1 best-of-N (b2) | Tough 1500 (1136) | 3.7% | 0.0193 [0.0168, 0.0219] | pending | pending |
| r2 single | Tough 1500 (1136) | 8.2% | 0.0227 [0.0219, 0.0234] | 1.26 | 39.6 / 17.0 FAIL |
| r1 planner | UHMWPE (800) | 51% | 0.0325 [0.0315, 0.0335] | pending | pending |
| control | Rigid 10K (8018) | 48% | 0.2057 [0.2011, 0.2103] | pending | pending |
| r2 planner | UHMWPE (700) | — | pending (rerun after OOM) | pending | pending |
| r1 collective | — | — | no submission | — | — |

Sources: `sim/judge_final/waves/w*/<run>/judge_{primary,early}.json`, tabulated by `scripts/collect.py` into `data/results_table.json`; geometry `data/geometry.json`. All official primary runs pass gates G1–G4. In the early state G1 fails for all three scored so far; per the frozen spec that is information only.

## Evidence by explanation

| # | Claim | Evidence | Strength | Type |
|---|---|---|---|---|
| E3, E4 | **Arms optimized the disclosed metric.** The brief linked EVAL_SPEC and its addenda (`harness_open/briefs.py` l.128). r2 collective's first post, 2 min after its 04:35:49 start: "minimise solid volume fraction with the lowest-E grounded reference material" (`data/board_r2_collective.txt` p0001). Every report justifies its design from addendum A2's fused state (e.g. r1 single "Core idea", r1 b2 "What the score rewards"). r2 b3: "This design targets the metric, not a clinical device." | strong | fact |
| E1+E2 | **Score = material contrast x material near scored bone.** Across 13 designs (7 finals + 6 best-of-N pre-checks), material contrast alone explains R² 0.64 (leave-one-out 0.55) of log H; adding volume fraction gives 0.81 (LOO 0.66) (`data/fit.json`). Same geometry, material swapped (h 0.8): r1 single's lattice goes 0.060 (Tough 1500) to 0.023 (UHMWPE) to 0.006 (ideal bone-matched). Same material, geometry swapped (Tough 1500, h 0.8): solid block 0.100, r1 single 0.060, r2 collective 0.023, r2 single 0.020, loop 0.0064, a 15x range. | strong for direction; mixed fidelity, n = 13 | fact (fits), inference (mechanism) |
| E5 | **The fused and early states reward opposite things.** Fused favours less material; early (graft at 7.8% of bone) favours more. Early order is the reverse of material volume: r1 single (41%) 0.42 < r2 single (8%) 1.26 < r2 collective (6%) 1.73. A solid Tough 1500 block is unchanged at 0.100 in both states (h 0.8), better than every agent design in the early state; a solid Tough 1000 block is 0.063. Kendall tau fused vs early, 3 designs: −0.33. | strong mechanism; n = 3 for official early | fact |
| E4 | **Integrity in the early state was known and not acted on.** r2 collective's c4 computed about 96 MPa strut stress at 1x for a sparse frame against UTS 34 and suggested Z-bar area ≥ 8–10% of footprint "or state it as a limitation" (p0012). r2 single reported "early soft-graft state is much worse (H ≈ 1.3)", close to the judge's 1.26 (`subs/r2_single/report.md`). Nobody changed a design for it. | strong | fact |
| E6 | **The collective's work mostly didn't reach its deliverable.** r2 collective's final geometry is c1's baseline frame posted at 04:43, 8 min in (p0013; volume 185.5 mm³ matches `data/geometry.json`). Only the material switch to Tough 1000 (c3's analysis, c4's decision, p0011–p0015) changed it afterwards. Later findings (surface-dominance p0021, envelope scaling p0009, integrity p0012) never shipped; all six capped 04:55–05:05. 13 FE runs from three separate FE replicas (c2, c6, c3) plus c5's proxy: partly duplicated despite explicit dedup posts (p0003, p0005). | strong | fact; "would have improved" is inference |
| E7 | **Credit decided completeness, not the official score.** Six-agent arms capped (33 of 36 team agents); both singles stopped on their own with 56–57% of 2.5M unspent (`analysis_process/metrics.md`). r1 collective, r1 planner (report) and r2 collective (report) lost deliverables to capping. But the best official design used 79,614 credits, 19% of one agent's budget (`data/credits.json` at_final). | strong | fact |
| E8 | **Single points of failure appeared in every group form.** r1 collective: c1 sole writer, capped 10 s after "PIPELINE READY", no submission. r1 planner: only p1 could write the report; capped 03:50. Action also concentrated in collectives: c1 made all 30 of r1 collective's PreForm calls; r2 planner's p4 made all 189 of its arm's (`data/process.json`). | strong | fact |
| E9 | **Replicate noise is as large as arm differences.** Same arm, r1 vs r2: single 0.0189 vs 0.0227 (1.2x); best-of-N 0.0193 vs 0.0053 (3.6x); collective none vs 0.0104. Within one best-of-N arm, agents' pre-checks span 0.007–0.23 (33x). With 2 replicates the smallest possible two-sided permutation p for any arm comparison is 0.33. | strong | fact |
| E9 | **Best-of-N's lead is mostly selection.** Pre-check medians: r1 ≈ 0.026, r2 ≈ 0.034 (4 entries each); picks 0.016 and 0.007, i.e. 1.6x and 5x better than the median agent. The median best-of-N agent is no better than a single agent or planner. | moderate (pre-check fidelity) | fact |
| E9 | **The pre-check ignored declared materials.** Its intake read no modulus from four best-of-N specs (all UHMWPE: r1 b1, b3, b4; r2 b5) and scored them in Tough 1500 (`sim/judge_final/precheck/*.json`, `"E": null`). Rescored with their declared values (h 0.4, illustrative), r1 b3 drops from 0.018 to 0.0027 and r2 b5 from 0.054 to 0.0053 (`data/cf2_results.json`), which would likely have changed r1's pick. Caveat: those runs used each agent's declared ν = 0.33, while UHMWPE's ν is about 0.46, and ν alone moves a solid block 3.8x (h 0.8). | moderate | fact (pre-check behaviour), inference (pick change) |
| E9 | **Material values are not on equal footing.** Tough 1500 designs use our one Form Studio 1 specimen (1136 MPa); Form 4 specimens gave 1.28 and 1.44 GPa, the datasheet 1460. With 1460, r2 single goes 0.0227 to 0.0358 (`waves/w1/r2_single/judge_sensitivity_datasheet.json`). r2 collective's Tough 1000 uses a datasheet value. If r2 single's ratio (1.58) applied to the loop, it would still lead (≈ 0.008), but the mid-table ties may reorder. | moderate | fact; reordering inference |
| E9 | **Three of seven scored designs declare a material that can't be printed on site** (UHMWPE: r1 single, r1 planner, r2 planner). r2 planner says so ("the .form is a geometry carrier only"). Printed demo parts for these are Tough 1500 stand-ins, not the scored material. | strong | fact |
| E10 | **No arm-level effect survives** the replicate spread and confounds (03:50 duplicates r1 only; 04:50 notices by replicate; mesh cap only on best-of-N; selection advantage). Mechanisms (above) are what the data support. | strong | inference from the above |

## Novelty in the agents' research approaches

Judged against what the spec gave them and what's in their knowledge bases; "novel" here means derived during the run, not known to the field. Literature novelty was not checked.

| Approach | Who | Reached a design? | Goal or metric? | Evidence |
|---|---|---|---|---|
| First-order "polarization" proxy to rank materials before any FE, finding ν matters as much as E | r2 collective c5 (p0006); c3 grid | Yes: drove the switch to Tough 1000 (−42% H by c3's FE, p0022) | Metric, but physically general (dilute-inclusion reasoning) | `data/board_r2_collective.txt` |
| Under the uniaxial load, an isotropic solid with E ≈ 714, ν ≈ 0.34 is "nearly invisible": a solid bone-matched block | r2 collective c3 (p0007) | No: no groundable material with that E and ν | **Goal-aligned**: the most direct answer to "homogeneous with bone" | p0007, p0011 |
| Hull-surface dominance: H is set by struts on the hull, not volume fraction | r2 collective c2, c6 (p0004, p0021); independently r1 collective c4 | Partly (inset designs never shipped) | Metric structure | `analysis_process/highlights.md` 3 |
| Envelope scaling H² ~ V_implant / V_bbox: grow the box, keep struts sparse | r2 collective c5 (p0009) | Yes, in best-of-N picks (r1 b2 50×36×14; r2 b3 55×40×18) | Metric exploit; c4 noted the clinical LLIF footprint agrees | p0009, p0012 |
| Gate-aware topology: one closed loop survives any single 2 mm deletion (G3) | r2 b3 | Yes: the top design | Metric exploit, honestly labelled | `subs/r2_best_of_n/report.md` |
| Modulus matching with UHMWPE (720 within 1% of E3 714) | r1 single; both planners | Yes | Goal-aligned on E, ignores ν and printability | `subs/r1_single/report.md` |
| Warp adjoint gradient checked by finite differences (2.97e-4) | r2 planner p5 | No: lead redirected, GPU queue | Method | highlights 8 |
| PreForm read-back rig: found layout can rotate a part without changing its hash | r2 planner p4 | Indirectly (validation) | Tooling | highlights 6 |
| Early-state integrity estimate (≈ 96 MPa vs UTS 34) | r2 collective c4 | No | Goal-aligned (integrity) | p0012 |

Pattern: the most goal-aligned ideas (solid bone-matched block, early-state integrity) appeared in the collective and were dropped for lack of a groundable material or of credit; the ideas that shipped were the ones the metric rewarded.

## Ground truth: what is and isn't validated

- **Validated by physical test:** the material inputs (coupon moduli at the Breakerspace; one specimen per condition, crosshead only) and the agents' *predictions* in the prediction contest.
- **Not validated physically:** the judge itself. No printed lattice or implant was tested against the judge's FE prediction. "Triangulation" means tests, published bone data and simulation feed one score, not that the score was checked against a test.
- Agents' own FE agreed with the judge where comparable (r2 single: fused 0.020 at h 0.4 vs judge 0.0227; early ≈ 1.3 vs 1.26), so the simulation chain is at least reproducible across independent implementations.

## What the experiment can and can't conclude (n = 2)

- **Can:** describe mechanisms (metric shaping, loss of group work to credit caps, single points of failure, selection effects) with direct evidence; show the frozen metric is gameable and by how much.
- **Can't:** rank organizations. No arm difference exceeds replicate spread; the minimum attainable p is 0.33; confounds are unbalanced across arms.

## Tempting claims not supported

- "The collective (or any arm) designed the best implant."
- "The top design is a good implant." It is a 1 mm loop, labelled by its author as non-clinical, and very likely fails the early state.
- "Best-of-N is the best organization." Its lead is the best of up to six draws; median agents match singles.
- "The judge was validated against physical tests."
- "Agents discovered new physics." The proxy and scaling arguments are standard mechanics applied fast.
- "UHMWPE designs show printable bone-matched implants." UHMWPE isn't printable here; the printed parts are stand-ins.
- "Decentralization reduced failures." Every group form had a single point of failure.

## Still to add before final

r2 planner official; early-graft for best-of-N, planners and control; datasheet runs; goal metric (addendum 4) and its ranking vs official; Kendall tau across all states; figures.
