# EVAL_SPEC v1 addendum A2 (2026-11-01, pre-launch; user-approved)

This addendum amends `EVAL_SPEC_v1.md` and addendum A1 without editing them. Where they differ, A2 governs.

## A2.1 Primary metric: the fused state, coarse-grained H (replaces §3's primary and §2's void rule for scoring)

**State.** Every void inside the implant's convex hull R is filled with graft/fusion mass at **g = 1.0 × C_bone**, the native lumbar trabecular stiffness of targets.json `lumbar_vertebra`. This is the long-term fused state, and the question it asks is stress shielding. Voxels that are only partly filled are mixed by supersampled fractions: stiffness = a·C_implant + (1 − a)·C_bone, where a is the implant's fill fraction.

**Metric.** In every bone voxel outside R, ψ_c (the strain-energy density under case c) is averaged over cubes of 0.8 mm (k = round(0.8/h) voxels per side, bone voxels only). Writing ψ̄ for that average and n for the number of bone voxels in each cube:

H_avg = sqrt( Σ_c Σ_cubes n·(ψ̄_c − ψ⁰_c)² / Σ_c Σ_cubes n·(ψ⁰_c)² )

The cases c are the 3 visible plus the sealed one.

**Ranking.** The primary score is H_avg_R, the Richardson estimate over h1/h2 with p = 1, together with the §6 band. Ranking (§8) uses H_avg_R and its band. Overlapping bands are a tie.

**Gates.** G1-G4 are evaluated in this fused state, at h2.

## A2.2 Secondary metric: the early state (reported, not ranked)

**State.** The same as A2.1, but the hull voids get soft graft: E_graft ≈ 30 MPa, implemented as g_early = 30 / (mean axial modulus of the bone) ≈ 0.078 × C_bone.

**Source** (opened 2026-11-01): Pankaj, Phillips, Howie, McLean, Simpson, "Quantifying the Behaviour of Morselised Cortico-Cancellous Bone", *Orthopaedic Proceedings* 90-B SUPP_II:381 (2008). The source states that E increases linearly with pressure, "achieving a value of around 30 MPa at a pressure of around 1 MPa". The context is impaction grafting, not spine, and the visible cases run at about 0.75-1.4 MPa.

**Reported:**
- H_avg (raw H too) at h1 and h2
- the Richardson estimate and band
- G1 stresses (for information)
- a `not_converged` flag, set when |H2 − H1| > 15% of H_R

## A2.3 Also reported

- **Raw H**, meaning §3's formula without coarse-graining, with its Richardson estimate, for both states.
- **Spec v1 void state.** It is not computed by default, because of its cost and because it does not converge: H at h = 0.8/0.4/0.2 grows 0.33 / 0.77 / 1.20 on a windowed cage (`judge_validation/VALIDATION.md`). It can be requested with `--graft 0 --no-early`.

## A2.4 Deadline (replaces §8.3's 07:00 EDT)

All times are local wall clock, which is EST after the DST change at 02:00 EDT on Nov 1. **Arm deliverables are due by 08:30 EST, a hard deadline: 2026-11-01T08:30:00-05:00.** The deadline applies to `implant.form` by file time or receipt.

## A2.5 Convergence check (g = 1.0, H_avg; non-arm shapes 12 x 6 x 5 mm; Rigid 10K; h = 0.8 / 0.4 / 0.2 mm)

| shape | H_avg | change from h 0.4 to 0.2 | raw H |
|---|---|---|---|
| windowed cage (2 mm walls) | 0.326 / 0.307 / 0.312 | +1.8% | 0.326 / 0.318 / 0.330 |
| simple-cubic lattice (rods 1.2 mm) | 0.262 / 0.236 / 0.236 | −0.1% | 0.262 / 0.248 / 0.257 |

At h = 0.8 the cube is a single voxel, so H_avg equals raw H there. In both cases H_avg converges to within 2%. This contrasts with the spec-v1 void state on the same cage: 0.33 / 0.77 / 1.20. At the 24 mm scale with g = 0.5 the bands were already narrow (`VALIDATION.md`).

## A2.6 Implementation

`sim/judge/judge.py` has `GRAFT_DEFAULT = 1.0`, `EARLY_E_MPA = 30.0`, and writes the output blocks `primary` (A2.1) and `secondary_early` (A2.2). `judge_rank.py` ranks on `primary`. `precheck.py` reports the fused-state H_avg. `judge_submission.py` uses an 08:30 EST deadline by default. Code hashes are in `sim/judge/JUDGE_MANIFEST.sha256`.
