# Bone targets: sources and assumptions (Oct 31 2026)

Files: `targets.json` (agents), `sealed_case.json` + `sealed_case.sha256` (gateway only; agents must not read). Every number in `targets.json` has a `src` tag: `S:` sourced (key below plus table or section), `A:` assumed, `D:` derived.

I read every source in full text from PMC or Europe PMC XML. I cite by table or section number. I did not open the typeset PDFs, so in-article page numbers are not verified. The journal page range is given instead.

## Sources opened

| Key | Reference | Used for |
|---|---|---|
| Simon2025 | Simon M, Uppuganti S, Nyman JS, Zysset P. Fabric–elasticity relationships of femoral head trabecular bone are similar in Type 2 diabetes and non-diabetic individuals. *Bone Reports* 27 (2025) 101884. doi:10.1016/j.bonr.2025.101884, PMC12615757 | Femoral head: BV/TV 0.36 and DA 1.66 (Table 1, control medians). Zysset–Curnier fit λ0 = 3959, λ0′ = 3253, μ0 = 3413 MPa, k = 1.70, l = 0.65 (Results 3.2). Tissue E = 10 GPa, ν = 0.3 (Methods 2.4). 56 cores from 56 donors aged 51–97. |
| Oefner2021 | Oefner C, et al. Determination of anisotropic elastic parameters from morphological parameters of cancellous bone for osteoporotic lumbar spine. *Med Biol Eng Comput* 60 (2022) 263–278. doi:10.1007/s11517-021-02465-0, PMC8724118 | Lumbar vertebra: orthotropic constants normalised by Et = 15 GPa (Table 4 means). BV/TV 0.133 and DA 0.554 (Table 2). Trabecular angle to the craniocaudal axis 5.6–9.9° (Table 3). 60 cubes from L1–L5 of 3 male donors aged 73–85. |
| Bergmann2016 | Bergmann G, et al. Standardized loads acting in hip implants. *PLoS ONE* 11 (2016) e0155612. doi:10.1371/journal.pone.0155612, PMC4873223 | Hip contact force: peak resultant force F_res (AVER75 average) and the frontal and sagittal force angles per activity (Table 5). Component signs (Table 6). Femur coordinate frame (Fig 1). |
| Rohlmann2014 | Rohlmann A, et al. Activities of everyday life with high spinal loads. *PLoS ONE* 9 (2014) e98510. doi:10.1371/journal.pone.0098510, PMC4035320 | Telemeterised vertebral body replacement (VBR) loads: resultant force (Table 2), bending moment (Table 3), torsion (Table 4), anterior and posterior shear (Tables 5 and 6). The Introduction cites Wilke's intradiscal pressure: about 0.5 MPa standing, 1.3 MPa forward bending, 2.3 MPa lifting 19.8 kg. |
| Morgan2018 | Morgan EF, Unnikrisnan GU, Hussein AI. Bone mechanical properties in healthy and diseased states. *Annu Rev Biomed Eng* 20 (2018) 119–143. doi:10.1146/annurev-bioeng-062117-121139, PMC6053074 | Femoral cortical bone (Table 1): E longitudinal 17.9 ± 3.9 GPa and 18.16 ± 1.88 GPa, E transverse 10.1 GPa, G 3.3 GPa. Trabecular tissue modulus 10–20 GPa (Section 2.2). |

I did not open the suggested reviews (Helgason 2008, Keaveny 2001, Morgan 2003, Öhman) or Gross 2013, because they are paywalled or the repository was down. No number here comes from them.

## Results (from the generator)

| | E1 | E2 | E3 | G12 | G13 | G23 | ν12 | ν13 | ν23 | E3/E1 | E3/Et |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Femoral head (MPa) | 1143 | 1589 | 2209 | 496 | 585 | 689 | 0.197 | 0.167 | 0.197 | 1.93 | 0.221 |
| Lumbar vertebra (MPa) | 204 | 236 | 714 | 82 | 131 | 147 | 0.300 | 0.098 | 0.109 | 3.50 | 0.048 |

The femur is denser and moderately anisotropic. Its load direction rotates with the activity: the force line is 1–8° off axis 3, so the shears τ23 and τ13 are up to 0.6 MPa.

The vertebra is sparse and strongly axial. It carries compression with flexion shear (τ23) and torsional shear (τ13).

The intact strains come out at 0.08–0.25 %, which is in the physiological range. That is a sanity check only, not a sourced value.

## Assumptions (all tagged A in the JSON)

1. **Femur fabric eigenvalues.** Not reported, so I took trace = 3 and m2 = √(m1·m3).
2. **Femur block axis 3.** Taken as parallel to the stance force line (Bergmann Table 5 stance: 16° frontal, 4° sagittal). This is a Wolff alignment.
3. **Femur stress.** Uniaxial compression p = F_res / A_eff along each activity's force line, with A_eff = 900 mm² (about a 30 mm load path in the head and neck). This is the largest single assumption: stress scales as 1/A_eff. The dimensionless compliance does not depend on it.
4. **Vertebra axes.** Mapping Oefner's x′/y′ to medio-lateral (1) and antero-posterior (2) is assumed. Axis 3 = cranial is sourced.
5. **Vertebral section.** Elliptical centrum with semi-axes 22.5 mm (lateral) and 17.5 mm (AP), block centroid 7.5 mm anterior. Then σ33 = −F/A − M·y_c/I, τ23 = V/A and τ13 = T·y_c/J.
6. **Vertebral standing stress.** σ33 = −0.75 MPa, from 1.5 × the 0.5 MPa intradiscal pressure (Nachemson's factor; I did not open that source).
7. **VBR forces are a lower bound.** The internal fixator shares the load, so the measured forces understate the full spinal load.
8. **Apparent density.** BV/TV × 2.0 g/cm³ (tissue density assumed).
9. **Resin moduli.** Rigid 10K 11 GPa and Tough 1500 V2 1.46 GPa are your figures; I did not check them.

## Scaling to resin

Compare the dimensionless compliance c = u·E_ref / (t_ref·L) face by face, with L = 20 mm and t_ref = the case's largest |stress component|.

- **E_ref for bone** is the tissue modulus that produced the constants: 10 GPa for the femur, 15 GPa for the vertebra. Apparent constants are linear in Et, so c_bone depends only on architecture.
- **E_ref for the lattice** is the solid modulus of the printed resin. Use tonight's coupon value if there is one, otherwise the nominal figure.

A match therefore means E_app/E_solid is equal in every direction. In absolute terms, Rigid 10K displacements come out ×0.91 (femur) or ×1.36 (vertebra) of bone, and Tough 1500 ×6.8 or ×10.3.

## Sealed case

One extra physiological case per site, from the same tables. Its definition and derivation are inside `sealed_case.json`. The SHA-256 of the file bytes is in `sealed_case.sha256` (1c82b10f…). The generator script is outside the agent-visible tree: `[REDACTED: local path]\build_targets.py`. It contains the sealed case, so do not copy it into `bonetwin/`.
