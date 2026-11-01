# EVAL_SPEC v1: judging the bone-homogeneous implant arms (final, 2026-11-01 ~00:25 EDT)

**This file supersedes `EVAL_SPEC.md`.** That draft (~00:15) stays as the record, and a guard hook blocks edits to it. Relative to the draft, v1:

- grounds the material reference table (§5) in sources that were opened;
- grounds the G4 size envelope (§4) in published cage dimensions;
- adopts the coordinator's decisions: arms are told to include a matching STL/3MF as a backup mesh (§1.3) and the frame convention (§1.4);
- keeps a local CPU fallback when `bonetwin\computet_compute.py` is unavailable (§6).

It also adds the datasheet-stiffness sensitivity analysis (§5a). Everything else is unchanged from the draft.

**Task given to every arm:** "Make implants as mechanically homogeneous with bone as possible without losing integrity."

**Due 07:00 EDT.** Each arm submits one folder containing:
- `<arm>.form`: a PreForm project holding exactly one implant model
- `material_spec.json`: the material, its properties, and a source for each property
- `report.md`

The judge never helps arms. This spec, the judge code and the reference table are hashed (`EVAL_HASH.sha256`) before any submission is opened. The judge is validated only on non-arm geometries: the controls, a solid block and a bone-equivalent block (§9).

## 1. Intake (per submission, fully automatic)

1. **Open the file.** The `.form` is opened through PreFormServer ([REDACTED: local address]). If the server is down, restart it ([REDACTED: start command]). Each model in the scene is recorded: name, `canonical_model_hash`, bounding box, `original_file`, position, orientation, units (mm).
2. **Run PreForm validation.** The judge runs the validation checks `manifoldness`, `in-bounds`, `cups`, `minima`, `supportedness` and `thin-features`, with a threshold of 0.3 mm.
   - This is the **printability gate**. A failure is FLAGGED and published, but the submission is still scored.
   - If the file has more than one model, or a model with more than one body ([REDACTED: PreForm body-count call]), the bodies are united into one implant and this is flagged.
3. **Extract the mesh.** PreForm API v1 has no mesh export. The judge tries, in this order:
   - (a) a `.form` mesh reader. It counts only if it is validated before the hash on our own `.form` files: the volume and bounding box it reads must agree with PreForm's within 0.1%.
   - (b) the file at `original_file`, if it is readable.
   - (c) an STL/OBJ/3MF file in the submission folder.

   A mesh from (b) or (c) is accepted only if re-importing it into a scratch scene gives the same `canonical_model_hash` as the `.form` model. If the hash is not comparable, the volume and bounding box must match within 0.1%. If no mesh passes, the submission is **not evaluable** and is treated as no submission (§8). *The coordinator should tell arms that a matching mesh file in the folder is accepted as a backup.*
4. **Frame.** The implant is analysed in its own as-modelled frame. PreForm's print orientation and position are undone using the recorded orientation and position.
   - **+Z of that frame is cranial (superior-inferior).** X maps to bone axis 1 and Y to bone axis 2. In targets.json, axis 3 is the principal trabecular axis.
   - Units are mm. The size is kept exactly as submitted, with no rescaling.
5. **Record** the bounding box (Lx, Ly, Lz), the volume, the number of connected components (shells), and the print material and printer from the scene settings.

## 2. Scenario: an interbody implant embedded in vertebral cancellous bone

- **Bone.** `targets.json → sites.lumbar_vertebra.material.stiffness_voigt_MPa`: 3-D orthotropic trabecular bone, E1 204 / E2 236 / E3 714 MPa, in block axes. It is homogeneous and linear elastic.
- **Domain.** A box of size 1.5 Lx × 1.5 Ly × 1.5 Lz, centred on the implant's bounding-box centre, so there is a 25% margin on every side. The domain therefore scales with the submitted size.
- **Implant region R.** R is the voxelised convex hull of the implant.
  - Voxels in R that the implant solid occupies get the implant material (§5).
  - Voxels in R that the solid does not occupy are void. This represents the empty graft space at implantation, with E = 0, and those voxels are removed.
  - Bone fills everything outside R.
  - Bone and implant are perfectly bonded (an idealisation of fusion; the same for every arm).
- **Intact reference.** The same box, entirely bone.
- **Load cases.** The 3 visible cases of `lumbar_vertebra` (`relaxed_standing`, `upper_body_flexion`, `axial_rotation_standing`) plus the sealed case (`targets/sealed_case.json`, `lifting_weight_from_ground`). Each is a homogeneous stress state σ applied as tractions t = σ·n on the six outer faces of the box. Rigid modes are removed with 6 pinned DOFs. These are the same stresses for every arm, at physiological magnitude (MPa).

## 3. Primary metric: inhomogeneity H (lower is better)

For load case c, let ψ_c(x) = ½ σ:ε be the strain-energy density in the bone with the implant, and ψ⁰_c the intact value. ψ⁰_c is uniform, because the intact field is homogeneous. B is the set of bone voxels, meaning outside R.

```
H = sqrt( Σ_c ∫_B (ψ_c − ψ⁰_c)² dV  /  Σ_c ∫_B (ψ⁰_c)² dV )      c over the 3 visible + 1 sealed cases
```

- H = 0 means the bone does not feel the implant: no stress shielding (ψ < ψ⁰) and no concentration (ψ > ψ⁰).
- **Reported alongside:**
  - H for each case
  - H_vis, over the visible cases only
  - the shielded volume fraction (ψ < 0.5 ψ⁰) and the overloaded volume fraction (ψ > 2 ψ⁰)
  - the apparent stiffness of the implant region, using the same static-BC definition as the gateway
  - a displacement-based variant: the RMS relative error of face-averaged boundary displacements, as in the gateway

## 4. Integrity gates (pass/fail; a failed gate is published)

| Gate | Condition |
|---|---|
| G1 strength | At 2× each case's load, the 99.5th percentile of element von Mises stress in the implant is at most σ_allow = strength/2, so the 2× load with a further factor of 2 is a total safety factor of 4 on the case loads. Strength is the grounded tensile (or yield) strength (§5). The percentile is used because voxel corners are singular. The maximum is also reported. |
| G2 connectivity | The implant voxels at h2 form one face-connected component. The volume of any islands that would fall out is reported. |
| G3 damage tolerance | Take the 8 implant voxels with the highest von Mises stress under the governing case (at least 2 mm apart). One at a time, delete the implant material inside a sphere of diameter 2 mm around each, re-solve the governing case, and check: (a) the implant is still one component; (b) the 99.5th-percentile stress is ≤ strength (factor 1 at 2× load); (c) H changes by at most 0.10. All 8 must pass. |
| G4 size realism | The bounding box must fit a lumbar interbody envelope. **Longer horizontal side 22-55 mm** (sourced: shortest recommended PLIF length, 22 mm, women at L5-S1 [S7]; longest LLIF cage, 55 mm [S8]). **Z height 8-18 mm** (*assumed*: brackets the sourced 11-13 mm LLIF heights [S8]). **Shorter horizontal side 9-40 mm** (*assumed*: brackets the sourced 22 mm LLIF width [S8]; TLIF/PLIF widths and ALIF widths were not sourced). |
| P printability | PreForm validation (§1.2). Flag only. |

## 5. Materials

**Grounding check.** Every property the judge uses (E, ν, strength; optional anisotropy) must cite a source in `material_spec.json`: a URL, DOI or datasheet name, with the page or table. An independent checker opens each source and confirms the value, within the stated tolerance, or ±10% if none is stated. The checker is an LLM agent with web access and no access to the arms; its transcript is published.

**Use of declared values.** A property that passes is used as declared. A property that fails is replaced by the value from the nearest grounded reference material:

- If the declared material name matches a reference entry, that entry is used.
- Otherwise the entry nearest in log-E to the declared E is used.
- If E itself is ungrounded, the printer-resin entry for the scene's print material is used.

**Reference table** (grounded 2026-11-01 ~00:20 EDT; sources opened unless marked *assumed*):

| Material | E (MPa) | ν | Strength used in G1 (MPa) | Sources |
|---|---|---|---|---|
| Rigid 10K (printed, Form 4) | **8018**: tonight's flat dog-bones, crosshead-only. FLAGGED: crosshead strain includes machine compliance, so this underestimates E. | 0.35 *assumed* | **65**: ultimate tensile strength, UV post-cured, ASTM D638-14 | `calibration.json` (fit 00:11, `measured.json` E_rigid10k_flat_form4); [S1] |
| Tough 1500 V2 (printed, Form Studio 1) | **1136**: tonight's flat dog-bones, crosshead-only, FLAGGED as above | 0.35 *assumed* | **34.0**: ultimate tensile strength, post-cured (Form Cure V2, 12 min, 70 °C) | `calibration.json` (`measured.json` E_tough1500_flat_studio1); [S2] |
| PEEK (Victrex 450G) | **4000** (ISO 527-1, 23 °C) | **0.40** (distributor listing; Victrex lists none) | **98.0**: tensile stress at yield (ISO 527-2) | [S3]; ν from [S4] |
| Ti-6Al-4V (Grade 5, annealed) | **113800** | **0.342** | **880**: tensile yield (ultimate 950) | [S5] |
| Cortical bone (femoral) | **17900** longitudinal, **10100** transverse | 0.3 *assumed* | 130 *assumed* (the source was not opened tonight) | targets.json `cortical_reference` (Morgan et al. 2018, Table 1) |
| Trabecular bone (lumbar vertebra) | the targets.json `lumbar_vertebra` constants (E1/E2/E3 204/236/714) | from targets | 2 *assumed* (Bevill et al. 2007 [S6], opened, gives only side-artifact correction factors, 1.32 ± 0.17 for the vertebral body, not an absolute value) | targets.json, SOURCES.md |

**Sources:**
- [S1] Formlabs, Rigid 10K Resin technical data sheet, Rev 01, 06.09.2020 (https://core-electronics.com.au/attachments/rigid10k-TDS-ENUS-0.pdf). UTS is 55 / 65 / 53 MPa for green / UV / UV+thermal; tensile modulus is 7.5 / 10 / 10 GPa. G1 uses the UV value, 65 MPa: tonight's parts were post-cured per the Formlabs defaults.
- [S2] Formlabs, Tough 1500 Resin V2 product page tech specs (https://formlabs.com/products/tough-1500-resin/): UTS 34.0 MPa, tensile modulus 1460 MPa, elongation 155%.
- [S3] Victrex, VICTREX PEEK 450G datasheet (https://www.victrex.com/en/downloads/datasheets/victrex-peek-450g): tensile modulus 4000 MPa (ISO 527-1), tensile stress at yield 98.0 MPa (ISO 527-2), at 23 °C. It gives no Poisson's ratio.
- [S4] Goodfellow, Victrex PEEK 450G listing (https://www.goodfellow.com/uk/victrex-peek-450g-peek-granules-1000075491): Poisson's ratio 0.4, tensile modulus 3.7-4 GPa.
- [S5] ASM Aerospace Specification Metals, Titanium Ti-6Al-4V (Grade 5), Annealed (https://www.aerospacemetals.com/wp-content/uploads/2023/07/Titanium-Ti-6Al-4V-Grade-5-Annealed.pdf): E 113.8 GPa, ν 0.342, yield 880 MPa, ultimate 950 MPa.
- [S6] Bevill, Easley, Keaveny, J Biomech 2007, "Side-artifact errors in yield strength and elastic modulus for human trabecular bone..." (PMC2099450).
- [S7] "Length of Lumbar Interbody Cage Using Radiological Measurements of Chinese Endplates and the Apophyseal Ring", World Neurosurg 2018;116:e1204-e1213 (PubMed 29886299). Recommended lengths: TLIF >30 (men) and 26 (women) mm; PLIF 28-30 / 24-26 mm, and 26 / 22 mm at L5-S1; OLIF/XLIF/DLIF 35-43 mm; ALIF 23-29 mm.
- [S8] Wu et al., "Effects of the cage height and positioning on clinical and radiographic outcome of lateral lumbar interbody fusion", BMC Musculoskelet Disord 2022 (PMC9733007). Cages 50 or 55 mm long, 22 mm wide, 11 or 13 mm high.

**Strength rule.** G1 uses the grounded tensile strength: ultimate strength for the resins, yield stress for PEEK and Ti. It applies the factor of 2 at 2× load from §4.

**Modulus caveat.** The resin moduli are crosshead-based and therefore low; the PEEK, Ti and bone moduli are not. This is applied identically to every arm.

**How the implant material is modelled.**
- Voxels are isotropic with the grounded E and ν.
- For Formlabs resins, the width law and layer factor from `calibration.json` are **not** applied. The as-submitted mesh is taken to be the as-printed geometry, so the same rule holds for every material.
- Declared anisotropy is used only if it is grounded.
- If a material is graded (for example, multi-material), each region's material must be identified in `material_spec.json` by the mesh or body name. Otherwise the stiffest declared material is used everywhere.

## 5a. Sensitivity analysis: datasheet stiffness (pre-registered 2026-11-01 ~00:45 EDT)

Every submission is scored a second time. Everything is identical (mesh, bone, cases, h1/h2, Richardson, gates) except the resin moduli, which come from the Formlabs datasheets:

| Resin | Primary E (measured tonight) | Sensitivity E (datasheet) | Datasheet source |
|---|---|---|---|
| Rigid 10K | 8018 MPa | **11000 MPa** | [S9] Formlabs Rigid 10K Resin page, tech specs: tensile modulus 11,000 MPa (UTS 88 MPa). Footnote: Form 3, 100 µm, Form Cure 60 min at 70 °C. |
| Tough 1500 V2 | 1136 MPa | **1460 MPa** | [S2] Formlabs Tough 1500 Resin V2 page, tech specs: tensile modulus 1460.0 MPa. Post-cured with Form Cure V2, 12 min at 70 °C. |

Non-resin materials (PEEK, Ti-6Al-4V, bone) and every strength used in G1 are unchanged.

**What is reported:**
- H_R with its band under both moduli
- both rankings
- the Kendall τ between the two rankings (τ-b, ties as in §8)
- the gate outcomes under both, with any gate that flips listed

**The primary ranking is the measured-modulus one.** The sensitivity ranking is reported only; it is never used to rank.

**Why both are reported:**
- The measured moduli are crosshead-only. Machine compliance adds to the measured displacement, which biases E low.
- For Tough 1500, the measured value also disagrees about 2× with the video-tracked strain on Alan's print1 dog-bone D2.
- The datasheet values assume cure and print conditions we cannot confirm for tonight's parts (the Rigid 10K datasheet uses a Form 3 and a 60-minute cure; tonight's parts were printed on a Form 4).
- Neither value is known to be right for the submitted parts, so both are shown and the sensitivity of the ranking to this choice is measured.

[S9] Formlabs, Rigid 10K Resin product page (https://formlabs.com/store/materials/rigid-10k-resin/), tech specs, opened 2026-11-01.

## 6. Numerics

- **Solver.** Voxel FE (trilinear hex8) on the box. Implant voxels use supersampled volume-fraction moduli, as in `sim/voxel_check.py` v2 (E × filled fraction, about 0.07 mm sub-grid). The solver is CG with pyamg smoothed-aggregation preconditioning on CPU, or Warp CG on GPU, with a relative residual of at most 1e-8.
- **Resolutions.** h2 = 0.2 mm and h1 = 2 h2 = 0.4 mm.
  - If the box at h2 would exceed 25 M DOF, h2 becomes the smallest h giving at most 25 M DOF, and h1 = 2 h2.
  - h1 and h2 are recorded per submission.
- **Richardson estimate.** With p = 1 (voxel boundaries converge at first order): H_R = H2 + (H2 − H1)/(2^p − 1). The uncertainty band is H_R ± |H2 − H1|, and the reported value is H_R [band].
  - **Overlapping bands are a tie.**
  - If H1, H2 and H_R are non-monotone in h, the band is widened to [min, max] of {H1, H2, H_R} ± |H2 − H1|.
- **Where it runs.** Runs that do not fit the laptop go to a Brev GPU through `bonetwin\compute\bt_compute.py`. That script is being built. If it is unavailable at judging time, runs stay local on CPU with AMG: same numerics, longer wall time. This compute comes from the judge's own budget, not the arms'.
- **Gate resolution.** G1-G3 are evaluated at h2.

## 7. Secondary panel (does not change the primary rank)

- **Blinding.** Each `report.md` and `material_spec.json` is shown with the arm name and model identity removed. The order is randomised with a seed: the SHA-256 of the concatenated submission hashes.
- **Panellists.** Three independent calls score each criterion from 1 to 5, and the median is reported:
  - ambition/novelty
  - evidence quality
  - honesty: each quantitative claim in the report is re-checked against the judge's own results, which the panel sees, and claim versus judge is tabulated
- **Models.** The panel uses Claude models available to the harness. The NVIDIA Nemotron endpoint configured in `harness/config.json` is used only if its API key is present at judging time. No other providers are available. Which models were actually used will be stated.

## 8. Ranking, ties, no submission

1. Submissions that pass G1-G4 are ranked first, by H_R, lower being better. Failing submissions are ranked after them, also by H_R, with the failed gates listed.
2. **Ties:** overlapping uncertainty bands are a tie. If one order is required, ties are broken by the secondary panel's median total, then by the G1 stress margin.
3. **No submission:** a folder that is missing, a `.form` that is late (after 07:00 EDT by file time, or received after 07:00), unreadable or not evaluable (§1.3) is listed as "no submission" and ranked last. It is not imputed.
4. Everything is published: the per-case fields, the gates, h1/h2/H_R/bands, solver logs and wall times, the material-grounding transcripts, and the panel transcripts.

## 9. Judge validation (before the hash; non-arm geometries only)

- **Bone-equivalent block:** the implant material is set to the bone constants. Expected H ≈ 0, up to discretisation (the void fraction is 0 in a solid block).
- **Solid block (worst shielding):** the solid cuboid of the bounding box in Rigid 10K and in Ti-6Al-4V. Expected: large H, with the shielded fraction near 1 above and below the implant.
- **Controls:** the gateway's 2-D and 3-D control lattices, extruded or as they are, at cage size.
- **Convergence:** H1, H2 and H_R for each, plus one h3 = h2/2 check on a small case, to confirm the order assumption.
- **Determinism:** two runs give identical outputs (fixed seeds, fixed solver tolerances).
