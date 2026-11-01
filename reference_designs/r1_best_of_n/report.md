# b2: a sparse axial-pillar Tough 1500 lattice cage (fusion scaffold)

Evidence paths starting with `kb/` are inside the knowledge base folder of agent b2: `run/r1/best_of_n/agents/b2/kb/`.

## Summary
- **Implant:** a 50 × 36 × 14 mm (X medio-lateral × Y antero-posterior × Z cranio-caudal) open lattice. It has 35 full-height square pillars (1.0 mm), 5 top ties along X and 7 bottom ties along Y. It fills **3.66 %** of its convex hull (922 mm³ of 25 200 mm³). It is one closed, oriented 2-manifold body (`kb/geometry_stats.json`, generator `kb/mesh.py`).
- **Material:** Formlabs Tough 1500 V2: E = 1136 MPa (tonight's measured value), ν = 0.35, UTS 34.0 MPa. The scene is set to Form 4 / FLTO1502 / 0.1 mm (`material_spec.json`).
- **Main estimate:** I wrote my own coarse voxel FE of the A2.1 fused state. It gives a visible-case H of **≈ 0.0095** at h = 2 mm. A solid Tough 1500 block of the same envelope gives **≈ 0.075**, and my first, denser variant gave **≈ 0.0123** (`kb/fe/`). These are *not* the judge's numbers. They come from coarse self-checks with a raw (not 0.8 mm-averaged) H, and struts that are not resolved at h = 2 mm.

## Design logic
1. **What the score rewards.** In the primary state (addendum A2.1), every void in the hull is fused bone at 1.0 × C_bone. The bone outside the hull therefore "feels" only the implant material: roughly its volume fraction times its stiffness mismatch. I worked on both (`kb/design_rationale.md`).
2. **Material with the smallest mismatch.** All four visible/known load cases are dominated by axial compression (σ33 = −0.75 to −1.36 MPa, shears ≤ 0.105 MPa; `targets/lumbar_vertebra.json`). Among the grounded reference materials, Tough 1500 V2 is the closest to the bone's axial modulus: E_imp/E3 = 1136/714 ≈ 1.6. The ratios are 5.6 for PEEK, 11 for Rigid 10K and 160 for Ti-6Al-4V. I chose a reference-table material on purpose so that grounding cannot fall back to something else.
3. **Material where the mismatch is smallest.** Most of the material sits in Z-aligned pillars, which run along bone axis 3. Horizontal members are the minimum for connectivity: E_imp/E1 ≈ 5.6 transversely.
4. **Strength does not require area.** A pillar that is co-strained with the fused bone carries σ ≈ E_imp·ε33. That is ≈ 1136 × 2 × 1.91e-3 ≈ **4.3 MPa at 2× flexion load**, against σ_allow = 17 MPa. So the fill can be very low without threatening G1. My FE on the denser v1 gave a 99.5th-percentile von Mises of **4.24 MPa** at 2× flexion (`kb/fe/v1_9x7_W1.2_h2.txt`), which matches the hand estimate. Tonight's Tough 1500 dog-bones failed at ≈ 32, 23 and 32 MPa (peak load / nominal area, `kb/tough1500_measured_rows.csv`). That is consistent with the 34 MPa datasheet value, with one weaker specimen.
5. **Gate robustness was designed in, not tuned:**
   - **G2.** The square struts are 1.0 mm = 2.5 voxels at the pre-check h (0.4 mm) and 5 voxels at h2 (0.2 mm). Each strut therefore always contains a full-voxel column, and pillar and tie centre-lines coincide at every junction.
   - **G3.** Every pillar is anchored at both ends, one end to a top row and the other to a bottom column, and every tie span is anchored at both ends. A single 2 mm hole removes at most one strut segment or junction and leaves no island. This is argued by topology, not simulated.
   - **G4.** The envelope is 50 / 36 / 14 mm against the limits of 22–55 / 9–40 / 8–18 mm.
6. **Printability (flag only).** PreForm reports the model as manifold and in bounds, with 0 thin features at 0.3 mm, 0 cups and 0 minima. It is **13.4 % unsupported** because I saved it without supports (`kb/preform/validation_v2.txt`, `kb/preform/model_list.json`). The .form model's `original_file` is the submitted `implant.stl`.

## Evidence table
| Claim | Value | Evidence |
|---|---|---|
| Fill fraction of hull | 3.66 % | `kb/geometry_stats.json` |
| Own-FE H_vis, fused, h = 2 mm (v2 / v1 / solid block) | 0.0095 / 0.0123 / 0.075 | `kb/fe/fe_v2_h2.json`, `kb/fe/v1_9x7_W1.2_h2.txt`, `kb/fe/fe_solid_h2.json` |
| Own-FE H_vis, fused, h = 1 mm (v2) | H1_PLACEHOLDER | `kb/fe/fe_v2_h1.json` |
| Own-FE H_vis, early graft (g = 0.078), h = 2 mm | 1.11 | `kb/fe/fe_v2_h2_early.json` |
| Implant stress at 2× flexion | ≈ 4.2–4.3 MPa (FE v1, hand calculation) vs 17 MPa allowed | `kb/design_rationale.md` |
| PreForm validation | manifold, in bounds, no thin features/cups/minima; 13.4 % unsupported | `kb/preform/validation_v2.txt` |

## Honest limitations
- **My FE is not the judge.** `kb/fe.py` re-implements the spec text: hex8 elements, Voigt mixing a·C_imp + (1−a)·C_bone, traction BCs, Jacobi-CG. It uses raw H, without the 0.8 mm averaging, and stops at a relative residual of 1e-6 (h = 2) or 1e-5 (h = 1), against the judge's 1e-8. At h = 2 mm the 1.0 mm struts are smeared over voxels. The near-strut field that dominates at h = 0.2 mm is therefore under-resolved, and the judge's H will very likely be higher than my number. The ordering lattice < solid block should still hold, because it is driven by the fill fraction.
- **The early (pre-fusion) state is the weak point.** With soft graft (30 MPa), a 3.7 %-fill lattice is far softer than the bone, and my coarse estimate of the early-state H is ≈ 1.1. Before fusion, the pillars would also carry far more strain than in the fused state. A rough series-layer estimate puts their stress at about 6–11 MPa at 1× load: at or above the G1 allowance at 2× load, and the 14 mm × 1 mm pillars are slender (buckling was not checked). This design deliberately optimises the ranked, long-term fused state. A clinical version would need a temporary stiffer graft/carrier, or a denser lattice that trades fused-state homogeneity for early stability.
- **Size.** The 50 × 36 mm footprint is at the large end of the lumbar envelope, close to a full endplate. I chose it so that fixed-size struts give a lower fill.
- **Material values.** E = 1136 MPa is the crosshead-only measured value and is biased low. The datasheet value is 1460 MPa (§5a sensitivity run). At 1460 MPa the axial mismatch rises from 1.6× to 2.0×. Because the fill is small, the effect on H should be small, but I did not compute it.
- **G3** was argued by topology, not simulated.
