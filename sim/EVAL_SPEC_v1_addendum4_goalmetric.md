# EVAL_SPEC v1 addendum A4: goal metric (supplementary; post-registered; exploratory)

Written 2026-11-01, frozen 08:07 EST.

**Status.** This is reported beside the official ranking and does not replace it. The official primary metric, gates and ranking (`EVAL_SPEC_v1.md`, A1, A2, A3) are unchanged. No frozen file was modified.

**Written blind.** The author did not read `sim\judge_final\`, `harness_open\`, `print_package\`, `analysis_process\` or `RUN_LOG.md`, and asked for no scores. A3 quotes pre-check values for best_of_n agents, and the author read that file for the cap, as instructed. Those values played no part in this design. The author knows which materials and pre-check figures A3 lists, so the blindness covers the final scores, not A3's content. Every test used synthetic geometry made by `make_kat.py`.

## A4.1 The metric in one sentence

**M is how many log-units the implant region is off from bone: in its worse life stage (empty voids or fused), taking the RMS over 5 mm regions of each region's worst-direction stiffness mismatch; lower is better, 0 is identical to bone, and e^M is the factor.**

Why this reading of the goal:

- "Mechanically homogeneous with bone" means the implant region has bone's stiffness in every direction and in every region. That is a property of the implant, so it is measured without surrounding bone.
- A thin frame in fused bone barely disturbs the bone, which is the concern raised about the official metric. Here it is scored with its voids empty as well, where it has almost no stiffness.
- A solid block is too stiff in both states.
- Empty voids and fused bone are the two ends of the implant's life. Filling voids can only stiffen the region, so a design too soft when empty and too stiff when fused is judged on the worse end. Early graft (30 MPa) lies between them, so it is not needed in M; §A4.6 reports how that held on the tests.

## A4.2 Formula

Region R is the implant's convex hull, as in `EVAL_SPEC_v1.md` §2. There is no surrounding bone.

For state s in {alone: voids empty; fused: voids = 1.0 × C_bone}:

1. **Solve.** Each of the 6 unit strains ε_i is applied as displacement u = ε_i·x on every node on the hull surface. Interior nodes are solved with the judge's hex8 elements, supersampled fill and AMG-CG (`judge_fe`, `judge_geom`, residual 1e-8).
2. **Split the energy into windows.** Cubes of about 5 mm tile the bounding box. With V_W the hull volume in window W:

   `C_W[i,j] = (1/V_W) Σ_(e in W) u_i^T K_e u_j`

   The volume-weighted mean of C_W is exactly the region's C_eff, so no energy is lost or counted twice.
3. **Worst direction in a window.** λ are the eigenvalues of C_W against C_bone (`C_W v = λ C_bone v`), floored at 1e-3.

   `D_W = max |ln λ|`

   D_W is therefore capped at ln 1000 = 6.91.
4. **State score.** `Q_s = sqrt( Σ V_W D_W² / Σ V_W )`, over windows whose hull volume is at least 25% of the nominal window.

`M = max(Q_alone, Q_fused)`

**Bone reference.** `lumbar_vertebra` `stiffness_voigt_MPa`, block axes, as in §2.

**Window size.** 5 mm is taken as the scale at which trabecular bone itself can be treated as a continuum (roughly 3 to 5 intertrabecular lengths, Harrigan et al. 1988). *That source was not opened tonight, so this value is an assumption.* A lattice whose cell is much larger than 5 mm is treated as heterogeneous, on purpose.

**Materials.** The same resolved material as the official primary run: the E, ν and strength from the same `judge_jobs.json` arguments.

## A4.3 Integrity rule (the implant carries its own load)

Each case is applied to the implant alone, voids empty, with no bone sharing the load. By superposition of the 6 solved strain fields, the apparent strain for case c is `ε* = C_eff⁻¹ σ_c`, so a soft implant must strain further to carry the same stress. No extra solve is needed.

| gate | condition |
|---|---|
| IA strength | at 2× load, p99.5 von Mises over voxels ≥ 50% filled ≤ strength/2, all 4 cases, at h2. Same statistic and factor as G1; only the load path differs. Fails outright if the smallest λ of C_eff is below 1e-3. |
| G2 | implant voxels form one face-connected component at h2, as in the official gate |
| G4 | the official size envelope |
| Hull fill | hull volume / bounding-box volume ≥ 0.5. Without this, a thin tilted plate passes G4 but is loaded only over its own tiny hull. This threshold is a judgement call. |

The official fused-state gates G1 and G3 are shown beside it, not used here. G3 is not recomputed for the alone state, so **damage tolerance is not assessed in the no-ingrowth state**. Fatigue is excluded: the reference table has no S-N data for these materials.

Known bias: fixing the whole hull surface over-stiffens slightly compared with uniform loading, so IA stresses are, if anything, slightly low.

## A4.4 Ranking and ties

- **Primary order of this metric:** designs passing all four gates first, by M_R, lower is better; then failing designs, by M_R, with the failed gates listed.
- **M_R:** `judge.richardson` on (M at h1, M at h2), p = 1, the same rule as §6, including the widened band when non-monotone.
- **Ties:** overlapping bands are a tie, chained in sorted order. Ties are not broken.
- **Unconditional order:** M_R alone, ignoring gates, is always reported beside it, with integrity results shown, so a ranking exists even if every design fails a gate.
- Q_alone, Q_fused, D_eff per state and the official H values are published beside M.

## A4.5 Resolution, cost, fallback

**Levels.** The same h2 and h1 as that submission's official run: the §6 / A3.1 rule on the 1.5× box at 20 M DOF, but solved only over the hull's bounding box.

**Why nothing is reused.** The official runs save no solved fields, and their solves are bone-box tractions, not these 6 hull strains. So no output of the runs in progress enters M.

**Extra solves per submission:** 2 states × 2 levels = 4 AMG setups and 24 CG solves (6 per setup).

**Measured on the largest synthetic** (30 × 20 × 12 mm, lattice, h = 0.33, Windows laptop, 2 threads, shared with other work):

| state | DOF | wall per state (6 solves + AMG setup + scoring) | CG iterations per strain |
|---|---|---|---|
| alone | 0.47 M and 0.52 M | 42 s and 48 s | 15-18 |
| fused | 0.65 M | 58 s and 61 s | 11-13 |

That is about 94 s per M DOF per state at most, and a peak of 4.1 GB at 0.65 M DOF, about 6.3 GB per M DOF.

**Projected to the contest sizes, not measured at them.** Grid DOF is the official box DOF / 3.375, since the 1.5× margin is gone. This is an upper bound, because the alone state keeps only the solid's nodes. From the A3.1 box sizes:

| | DOF at h2 (M) | state-level total, h1 + h2, 2 states (M) | one worker, 2 threads | peak memory |
|---|---|---|---|---|
| largest submission | 5.5 | 12.3 | about 19 min at the measured rate; allow 30 min for iteration growth | about 34 GB |
| all 8 | 25.2 | 56.8 | about 1.5 h at the measured rate; allow 2.2 h | at 4 workers, up to about 110 GB |

- **On one L40S with `--workers 4 --threads 2`:** about 35 minutes of wall time. Budget 1 h, **about $1.74 for the whole batch, about $0.22 per submission**, from the $16.8 uncommitted in the pool.
- **The same run at the task's quoted rate** (170 s per M per level on one core, scaled by 6/4 strains): 4.0 core-hours, about the same wall time on 8 vCPU.
- **Against a judge job:** the largest is about 12.3 M state-DOF and 34 GB, versus about 45 min and 60 GB for the largest judge job.
- **Sharing a box:** do not add this to a box already running the official batch unless memory is confirmed free. A separate box is the plan.

**Fallback, fixed now.** `--fallback` runs h2 = 0.4, h1 = 0.8 for all submissions, uniformly, never mixed. Use it if the normal run cannot be projected to finish by 11:30 at the time it is started. The trigger is starting after 10:30 EST, or having no box able to give 110 GB. Projected cost is one eighth of the DOF, about 5 min of wall time on one box. Under the fallback, thin walls are under-resolved at h1, which widens bands and produces more ties. Its results are labelled as fallback.

## A4.6 Known-answer tests

Synthetic only (`make_kat.py`), envelope 30 × 20 × 12 mm, h1/h2 = 0.8/0.4. Tough 1500 (E = 1136 from the reference table) unless stated. `check_exact.py` is the machinery check.

| shape | M at h1 / h2 | M_R [band] | Q_alone / Q_early / Q_fused at h2 | IA p99.5 at 2× / allowable (MPa) | hull fill | gates | rank (gated) | rank (unconditional) |
|---|---|---|---|---|---|---|---|---|
| lattice_alone_match: uniform, channels 0.6/0.6/1.7 mm, cell 2.5 mm | 1.240 / 1.117 | **0.994 [0.871, 1.117]** | 0.748 / 0.780 / 1.117 | 10.0 / 17 | 1.00 | pass | 1 (tie) | 1 (tie) |
| lattice_matched: uniform, channels 1.0/1.0/1.9 mm | 0.991 / 0.886 | **1.157 [0.886, 1.428]** | 0.886 / 0.617 / 0.869 | 15.9 / 17 | 1.00 | pass | 1 (tie) | 1 (tie) |
| solid block, Tough 1500 | 2.064 / 2.065 | 2.067 [2.065, 2.069] | 2.065 / 2.065 / 2.065 | 3.7 / 17 | 1.00 | pass | 3 | 5 |
| solid block, Ti-6Al-4V | 6.626 / 6.628 | 6.630 [6.628, 6.632] | 6.628 / 6.628 / 6.628 | 3.7 / 440 | 1.00 | pass | 4 | 8 |
| lattice_local_stiff: stiff core, softer shell | 1.147 / 1.265 | 1.497 [1.265, 1.730] | 1.265 / 0.954 / 1.044 | **20.4 / 17** | 1.00 | fails IA | 5 | 1 (tie) |
| tilted_sliver: 0.6 mm plate | 2.065 / 2.064 | 2.062 [2.061, 2.064] | 2.064 / 2.064 / 2.064 | 3.8 / 17 | **0.05** | fails hull fill | 6 | 4 |
| lattice_too_weak: channels 2.2/2.2/2.2 mm | 3.255 / 3.833 | 4.412 [3.833, 4.990] | 3.833 / 2.068 / 0.238 | **159 / 17** | 1.00 | fails IA | 7 | 6 |
| thin_frame: 1 mm bars | 5.011 / 5.152 | 5.293 [5.152, 5.434] | 5.152 / 2.357 / 0.185 | **248 / 17** | 1.00 | fails IA | 8 | 7 |

**What these show:**

- **The stated concern is answered.** The thin frame and the too-weak lattice look excellent when fused (Q_fused 0.185 and 0.238), the best of any shape, and rank last here, because M also scores them with empty voids and the implant carries the load.
- **The top group holds only uniform bone-like lattices.** Neither lattice beats the other at these levels. They are not separated by the bands, and this is reported as a tie, not resolved.
- **Heterogeneity is caught by the windows.** The stiff-core lattice has a whole-region mismatch close to the uniform one (D_eff alone 0.68 against 0.86), but its Q_alone is worse (1.27 against 0.89), because Q looks region by region.
- **Early graft never binds.** On all 8 shapes Q_early ≤ max(Q_alone, Q_fused), which supports leaving it out of M.

**Finer check, h = 0.33, one level:**

| lattice | Q_alone | Q_fused | M | IA (MPa) | inside its band above? |
|---|---|---|---|---|---|
| lattice_matched | 1.164 | 0.835 | 1.164 | 16.6 / 17 | yes (M_R 1.157) |
| lattice_alone_match | 0.725 | 1.096 | 1.096 | 10.7 / 17 | yes (M_R 0.994, band up to 1.117) |

So the extrapolation predicted both finer values, and the order of the two lattices at this level is alone_match, then matched. A bone-matching lattice in Tough 1500 can pass the integrity rule. A Rigid 10K lattice was not tested.

**Machinery (`check_exact.py`, block-aligned grid, h = 1.0):**

- A bone-equivalent solid gives Q = 9e-8 in both states.
- A Tough 1500 solid gives C_eff equal to its own isotropic tensor within 3e-7, and Q = 2.0654, which equals the analytic value 2.0654.
- A block off the grid carries a first-order boundary error (Q = 0.022 at h = 0.8), which is why two levels and bands are used.

**`goal_metric.py --folder`:** tested with `--fallback`, 2 workers, on both layouts at once (a prepared `judge_jobs.json` folder and a loose STL with `materials.json`) on synthetic geometry. It wrote `goal_ranking.json`, both return codes were 0, and each picked up its own material (M 2.06 in Tough 1500, 4.02 in Rigid 10K).

## A4.7 What changed during testing

Metric definition and integrity rule: **the integrity rule never changed after a test.** Nothing here was informed by any contest score.

1. **Band and extrapolation (changed after the first KAT run).** First version: Richardson on M itself. On lattice_matched the binding state switched between levels (fused at h1, alone at h2), so M_R came out 0.78, below every value at h2. Now: Richardson per state, M_R = max over states, band = [max of lows, max of highs]. This raised that lattice to 1.157, and the h = 0.33 check then gave 1.164.
2. **KAT pass criterion (loosened after the first run, recorded as such).** First version: lattice_matched alone at the top. Result: tied with lattice_alone_match, under both the first and the corrected band rule, and after the correction lattice_alone_match has the lower M_R. Now: the top group must contain lattice_matched and only uniform bone-like lattices. Both are uniform near-bone lattices, and the requirement that block, sliver, frame, heterogeneous and weak shapes do not win is unchanged. By the first criterion, this KAT **fails**.
3. **Shapes (tuned against this metric, so these KATs are not independent of it).**
   - The first four lattices swept had their z-channels the wrong way round, cutting the z stiffness that bone has most of. All four failed IA (24-46 / 17 MPa).
   - The bias was corrected in the shape, not by touching the rule. The next four all passed (7-16 / 17 MPa).
   - lattice_matched was chosen from that sweep as the point where Q_alone ≈ Q_fused at h = 0.4. It was not derived independently.
   - lattice_local_stiff was softened from 0.4/1.25 to 0.6/1.12 width scaling before its first run, to avoid 0.125 mm walls.
   - lattice_alone_match was added as a second bone-like shape.
4. **Energy split.** Uses exact fill fractions, not K's 1/24 levels. This made almost no difference: the 0.022 off-grid error above came from the boundary layer, as checked on the aligned grid.
5. **Unconditional ranking added** at the coordinator's request, so that a ranking exists even if integrity fails for everyone.
6. **Design-stage choices before any test.** Early graft was left out of M, and no official output is reused.

## A4.8 Limits

- **Not tested in the target environment.** Everything ran on Windows, Python 3.10. Docker and Python 3.11 are not on this laptop, so `python:3.11-slim` on Linux was not exercised. The code uses no 3.11 feature and the same pip list as the judge. Run it on one small synthetic first. No Brev box was started and no submission was run.
- **Cost is projected** from 0.65 M DOF to 5.5 M. Iteration growth and memory at contest scale are not measured. The laptop peak was 4.1 GB, slightly over the 4 GB limit, at h = 0.33.
- **M cannot reach 0 for a void-filled design.** Filling voids stiffens the region, so a design cannot match bone at both ends. The lowest M seen on these channel lattices is about 1.0-1.1 (e^M ≈ 3). Read M as a comparison, not a pass mark.
- **The sliver in the unconditional order.** A thin plate's hull is itself, so M returns its solid material's value (2.062) and it sits 0.005 ahead of the solid block (2.067), with the bands just separate. That is voxel noise, not merit. The sliver fails hull fill and ranks after every passing design in the gated order. It is not rewarded against the lattices, but the unconditional order alone does not reject it.
- **Unconditional tie.** At h = 0.8/0.4 the stiff-core lattice ties with the uniform ones in the unconditional order, and is separated only by IA (20.4 / 17). A contest run at h = 0.4/0.2 should narrow the bands, but this has not been shown.
- **Worst-direction scoring** strongly penalises bending-dominated lattices (low shear stiffness). That is deliberate: bone has that shear stiffness. A different reader might weight directions by the load cases instead.
- **Judgement values, not derived:** the 5 mm window (source not opened), the 1e-3 floor, the 25% window minimum and the 0.5 hull fill.
- **Boundary condition.** Hull-surface displacement over-stiffens compared with a uniform load, and is an idealisation of bonded bone.
- **Window phase.** A cell comparable to 5 mm can show window-to-window variation that depends on alignment with the tiling.
- **Inherited from the official spec:** crosshead-based resin moduli (the §5a datasheet moduli are not run here), perfect bonding, isotropic voxels, sub-voxel fill. A3.1 lists designs below 2 voxels across at h1, so expect wide bands there.
- **Not assessed:** fatigue (no data), damage tolerance with empty voids.
- **Blindness limit.** The blindness covers the final scores. The author read A3 as instructed, which lists pre-check values and materials.

## A4.9 Code and hashes

`sim\goal_metric\`: `goal_metric.py` (entry point), `make_kat.py`, `run_kat.py`, `check_exact.py`, `README.md`. It imports the frozen judge read-only.

`sim\goal_metric\GOAL_MANIFEST.sha256` holds the code hashes. The hash of this file is held outside it, because a file cannot contain its own hash.

Run in a `python:3.11-slim` container, from the same bundle:

```
pip install -q numpy scipy pyamg trimesh manifold3d pillow
cd sim/goal_metric && python goal_metric.py --folder /w/results --out /w/goal_results --workers 4 --threads 2
```

The folder may hold prepared `<run>/judge_jobs.json` folders (the primary job's mesh and material) or loose STL/3MF/OBJ files with a `materials.json`.
