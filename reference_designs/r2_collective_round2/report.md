# Bone-homogeneous interbody implant: run r3, collective arm

> Status: skeleton by c1. Sections 3-5 were filled in by c4. **Design B-pad15 (B with 0.45 mm perimeter walls, c3) is in `implant.stl` / `implant.form` (09:39).** The design and results sections are filled in by whoever's design is in `implant.stl` / `implant.form`. Evidence paths are given relative to the arm folder `run/r3/collective/`, so `kb/...` is the shared knowledge base.

## 1. Goal and how we read it
"Make implants as mechanically homogeneous with bone as possible without losing integrity." We optimise the addendum-4 metric M (EVAL_SPEC_v1_addendum4_goalmetric.md). M is the worse of the empty-void state and the fused state, each taken as the RMS over ~5 mm windows of the worst-direction |ln(C_window / C_bone)|. The integrity rule is that the implant alone carries 2x each load case at p99.5 von Mises ≤ strength/2, together with G2 connectivity, the G4 size envelope and hull fill ≥ 0.5. The bone reference is the lumbar vertebra, E1/E2/E3 = 204/236/714 MPa, with +Z cranio-caudal.

## 2. Material: Tough 1500 Resin V2
- Declared: E = 1136 MPa (measured tonight, crosshead), ν = 0.35 (assumed: no vendor value exists), UTS = 34.0 MPa, which gives an allowable of 17 MPa. Every value and its source is in `material_spec.json` (this folder), and the evidence table is in `kb/materials/EVIDENCE.md`.
- Why Tough 1500: the judge maps any non-reference material to the nearest reference entry in log-E. Tough 1500 is the softest grounded entry and the closest to bone, which gives the highest solid fraction for a bone-like lattice. That means thicker struts, a better strength margin and a smaller fused-state overshoot. Rigid 10K would need roughly 3 % solid (`kb/materials/EVIDENCE.md`).
- Modulus uncertainty: the datasheet E is 1460 MPa, 1.29x higher. Because empty-lattice stiffness scales linearly with E, we bias the design slightly toward the soft side when empty.
- Not an implant material. Tough 1500 has ISO 10993-1 skin-contact evaluation only. This part is a mechanical demonstrator.

## 3. Design
**Shipped: design B-pad15 (c3), in `implant.stl` / `implant.form`.** It is c4's design B with the box padded so the outer skins are printable.
- A solid **30.3 x 20.3 x 12.5 mm** block (X x Y x Z) is cut by three orthogonal families of square through-channels on a 2.5 mm cubic grid (12 x 8 x 5 cells, centred on the box). The channels are 0.6 mm along X, 0.6 mm along Y and **1.9 mm along Z**. The solid fraction is 0.41 (volume 3138 mm3). The convex hull is the full box, so hull fill is 1.0.
- **Why it is padded.** In design B (30 x 20 x 12.5), the outermost walls on the X and Y faces were only (2.5 − 1.9)/2 = 0.3 mm thick. PreForm `validate/thin-features` at the judge's 0.3 mm threshold flagged B's `implant.form`: has_thin_walls true, 22 regions, 235 mm3 (`kb/c3/preform_validation_bpad.md`). Padding each X/Y face by 0.15 mm makes those skins 0.45 mm thick. Thin-features then reports 0 regions, and the metric stays tied with B (section 4). A full half-wall pad, giving 0.6 mm skins (B-pad, 30.6 x 20.6), was over-stiff when fused: M_R 0.888 (`kb/c3/gm_Bpad.json`).
- Generator: `kb/c3/slot.py out.stl 30.3 20.3 12.5 2.5 1.9 0.6 0.6` (manifold3d boolean). The mesh is `kb/c3/Bp15.stl`, watertight with one body.
- Design B (c4) was the same channel grid in a 30 x 20 x 12.5 box (solid 0.39). Design A was that box with 1.7 mm Z channels (solid 0.50).
- Frame: +Z is cranio-caudal (bone axis 3), X is bone axis 1 and Y is bone axis 2. The bounding box is centred on the origin.
- The wide Z channels leave continuous vertical walls, so Z is the stiffest direction, as it is in bone (E3/E1 = 3.5). The narrow X and Y channels keep the walls connected laterally.
- Basis: B is derived from the addendum-4 known-answer shape `lattice_alone_match` (EVAL_SPEC_v1_addendum4_goalmetric.md §A4.6; channels 0.6/0.6/1.7, which is our design A). Its Z channels are widened to 1.9 mm to remove the fused-state overshoot.
- Generator: `kb/c4/lattice.py` (manifold3d boolean). The STL is watertight with one body.

## 4. Results (goal_metric, local fallback h2 = 0.4 / h1 = 0.8)
**Design B-pad15** (shipped), local `goal_metric --fallback`, h1/h2 = 0.88/0.44 mm. Raw output: `kb/c3/gm_Bp15.json`.

| quantity | h1 | h2 | Richardson |
|---|---|---|---|
| Q_alone | 0.662 | 0.709 | 0.756 |
| Q_fused | 1.108 | 0.972 | 0.836 |
| **M_R** | | | **0.836, band [0.709, 0.972]** |

- Gates all pass. IA p99.5 at 2x load, by case: 4.8 / 9.0 / 5.2 / **12.1** MPa against an allowable of 17 MPa, slightly lower than B's 12.6 because the edge walls are thicker. G2 (one component), G4 (30.3 x 20.3 x 12.5 is inside the envelope) and hull fill 1.0 pass.
- B-pad15 ties with B: the bands overlap, and its point value is 0.03 higher. It was shipped because B fails the PreForm thin-features check and its 0.3 mm skins are a real risk on the printed part.

**Design B** (c4, shipped until 09:39), local `goal_metric`, same settings. Raw output: `kb/c4/gm_b.json`.

| quantity | h1 | h2 | Richardson |
|---|---|---|---|
| Q_alone | 0.659 | 0.722 | 0.786 |
| Q_fused | 1.094 | 0.950 | 0.806 |
| **M_R** | | | **0.806, band [0.722, 0.950]** |

- Gates all pass. IA p99.5 at 2x load, by case: 5.0 / 9.3 / 5.4 / 12.6 MPa against an allowable of 17 MPa. The fourth case is the sealed lifting case; the local tool applies all four (it reports sealed_sha256 and four values). G2, G4 and hull fill 1.0 pass.
- The two states are now balanced (alone 0.786 against fused 0.806). B's band upper limit (0.95) lies below design A's point value (1.009).

Design A, earlier baseline, local `goal_metric`, Tough 1500 (E 1136, ν 0.35, strength 34), h1/h2 = 0.88/0.44 mm. Raw output: `kb/c4/gm_baseline_a.json`.

| quantity | h1 | h2 | Richardson |
|---|---|---|---|
| Q_alone | 0.946 | 0.766 | 0.587 |
| Q_fused | 1.279 | 1.144 | 1.009 |
| **M_R** | | | **1.009, band [0.875, 1.144]** |

- Gates all pass. IA p99.5 von Mises at 2x load, by case: 3.9 / 7.1 / 4.1 / 9.7 MPa against an allowable of 17 MPa. G2 (one component), G4 size and hull fill 1.0 all pass.
- The fused state binds. Its generalized eigenvalues against bone are 1.28-3.13, all above 1. When empty they are 0.76-2.14. Removing solid should therefore lower M, and the 9.7/17 MPa IA margin leaves room for that. 

Sweep (cell 2.5 mm, channels x/y/z in mm, M_R from local goal_metric):

| design | channels | solid | M_R [band] | binding state | IA worst / 17 | evidence |
|---|---|---|---|---|---|---|
| A | 0.6/0.6/1.7 | 0.50 | 1.009 [0.875, 1.144] | fused | 9.7 | `kb/c4/gm_baseline_a.json` |
| B | 0.6/0.6/1.9 | 0.39 | 0.806 [0.722, 0.950] | balanced | 12.6 | `kb/c4/gm_b.json` (fails thin-features) |
| **B-pad15 (c3, shipped)**: B in a 30.3x20.3 box | 0.6/0.6/1.9 | 0.41 | **0.836 [0.709, 0.972]** | fused (slightly) | 12.1 | `kb/c3/gm_Bp15.json` |
| B-pad (c3): B in a 30.6x20.6 box | 0.6/0.6/1.9 | 0.42 | 0.888 [0.759, 1.018] (h 0.97/0.48) | fused | 11.0 | `kb/c3/gm_Bpad.json` |
| D | 0.8/0.8/1.9 | 0.37 | 0.978 [0.803, 1.153] | alone | 13.7 | `kb/c4/gm_d.json` |
| a1 (c1; box 30x20x**10**) | 0.8/0.8/1.8 | 0.42 | 0.828 [0.660, 0.997] | fused (h2: alone 0.56, fused 1.00) | 12.4 | `kb/c1/gm_a1.json` |
| slot-B (c3) | x/y 0.6 wide x 1.5 tall slots, z 1.7 | 0.445 | 0.925 [0.78, 1.07] | fused | 10.3 | `kb/c3/gm_slotB.json` |
| tri-A (c6): triangular Z-prism walls, s 4, t 0.45, 0.45 perimeter wall, 30x20x12 | n/a | 0.39 | 0.835 [0.727, 0.943] | fused | 14.3 | `kb/c6/gm_tri_s4.json` |
| tri-NB (c6): same, no perimeter wall | n/a | 0.34 | **0.740 [0.711, 0.855]** | balanced (alone 0.71, fused 0.74) | **16.0** | `kb/c6/gm_tri_nb.json` |
| tri-T05 (c6): s 4, t 0.50, no perimeter | n/a | 0.37 | 0.789 [0.666, 0.912] | fused | 14.6 | `kb/c6/gm_tri_t05.json` |
| tri5n (c2): triangular honeycomb s 5, t 0.56, no perimeter | n/a | 0.34 | 0.719 [0.643, 0.850] | fused | **15.4** | `kb/c2/gm_tri5n.json`, `kb/c2/RESULTS.md` |
| tri5t62 / tc2 / tc1 (c2): t 0.62; t 0.5 + 2.2 mm node columns; t 0.45 + 1.5 mm columns | n/a | – | 0.814 / 0.770 / 0.819 | fused (X normal, C11 ≈ 2.3x bone) | 13.9 / 14.6 / **17.9 fails** | `kb/c2/RESULTS.md` |

a1 and the triangle variants tie with B because the bands overlap. tri-NB has the lowest M_R measured, but its worst IA, 16.0/17 MPa, leaves about 6% margin. The finer judging mesh is expected to raise p99.5 by about 7%, so tri-NB risks failing integrity, and a failing design ranks below every passing one. The B family was kept because it is balanced and has the best IA margin. The padded B-pad15 replaced B for printability.

Widening the X and Y channels (D) costs empty-state stiffness, while widening only the Z channels (B) lowers fused stiffness and keeps the lateral load paths.

## 5. Printability
- PreForm local API scene: Form 4 (FRML-4-0), Tough 1500 V2 (FLTO1502), 0.100 mm layers, DEFAULT print setting. The workflow was import `Bp15.stl`, then auto-orient, auto-support, auto-layout and save (`implant.form`).
- **Validation of the shipped B-pad15 `implant.form` (c3):** manifoldness MANIFOLD, in-bounds true, cups 0, minima 0, supportedness 0 % unsupported, interferences none, and **thin-features (0.3 mm) 0 regions**. These are the same checks the judge runs in §1.2. The procedure and B-pad results are in `kb/c3/preform_validation_bpad.md`; B-pad15 gave identical results.
- Superseded design B (`kb/c4/preform_validation_b.md`) gave interferences none, cups 0 and minima 0, but thin-features flagged 22 regions (235 mm3) of 0.3 mm outer skin.
- The API does not support print-time estimation for this machine type (HTTP 422). For the Form Studio 1, re-slice with machine CLRK-1-2 and material FLST1502.

## 6. Limits
- Moduli are crosshead-based (low). ν is assumed.
- The local metric runs at the coarse fallback resolution. Final judging uses a finer one.
- Damage tolerance in the empty state and fatigue are not assessed.
- Sensitivity to the datasheet modulus (c1, from `kb/c4/gm_b.json`). With voids empty, stiffness scales linearly with E. Moving from 1136 to 1460 MPa multiplies every alone-state λ by 1.29. At h2, B's whole-region eigenvalues go from 0.51-1.61 to 0.65-2.07, so D_eff(alone) changes only from 0.67 to 0.73: B sits nearly symmetric in log space. The fused state would stiffen by less than 1.29x because the bone share does not change, but it would rise and bind more. Expect M about 0.05-0.2 higher under datasheet E. The A4 metric uses the measured 1136 MPa, so this is a sensitivity estimate only and was not solved.
- The shipped design's IA worst case, 12.1 MPa (B: 12.6), comes from the fallback mesh. The spec's known-answer tests showed p99.5 rising by about 7% from h = 0.4 to 0.33, so finer judging may push it toward about 14-15 MPa. That is still below 17 but not measured. c5 tried, and the local goal_metric does not refine below h2 ≈ 0.4 mm: `--h2 0.3` on B and `--h2 0.25` on a quarter-size sub-block both ran at 0.40-0.44 (`kb/c5/gm_b03.log`, `kb/c5/gm_bq.log`, `kb/c5/EVIDENCE_c5.md` §3). For that reason we did not ship lower-M candidates whose fallback IA was above about 14 MPa: c2's tri5n at 15.4 and c6's tri-NB at 16.0. A +10-20% rise at finer h would take them to or past 17, and a design that fails integrity ranks below every design that passes.
- Rotating the square channel grid about Z was tested on a periodic unit-cell homogenization surrogate (c5, `kb/c5/homog.py`, `kb/c5/sweep_results.txt`). Angles from 0 to 45° changed M by less than 0.03. The surrogate reproduces KAT `lattice_alone_match` (D_alone/D_fused 0.78/1.13 against 0.75/1.12).
- Square channel grids cannot match bone's in-plane shear isotropy. The remaining mismatch is mostly tensor shape, not stiffness level (see the c5 and c6 board posts).
- **Explored alternative: a triangular Z-prism lattice (c6, `kb/c6/TRIANGLE_PRISM.md`).** Bone is close to isotropic in XY ((C11-C12)/2 = 73 against C66 = 82 MPa). A square grid's two in-plane shear moduli differ about 4x (B-family alone: 178 against 47), and rotating the grid only swaps them. A 60-degree wall honeycomb extruded along Z is in-plane isotropic. A periodic-homogenization surrogate (`kb/c6/homog.py`) reproduces the addendum-4 KAT values to within 0.03. On that surrogate, alone-state eigenvalues tighten from 0.57-2.19 (square) to 0.76-1.24 (triangle). With goal_metric the best variant reached M_R 0.740, against B's 0.806, but the bands overlap and the IA margin is too thin to ship. Thicker walls placed only near the hull faces are the obvious next step. c2 independently swept the same family (`kb/c2/RESULTS.md`). tri5n reached M_R 0.719 with IA 15.4, and variants with node columns did not fix the binding fused X-normal mode. This confirms the M-against-IA trade-off and the decision to keep B.
