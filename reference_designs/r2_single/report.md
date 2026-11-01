# Bone-homogeneous lumbar interbody implant: a sparse Tough 1500 strut lattice

**Submission:** `implant.form` (with matching `implant.stl`) and `material_spec.json`. The implant is a single-body, axis-aligned strut lattice with a 27 × 12 × 10 mm bounding box (X × Y × Z, +Z cranial-caudal). The material is Formlabs Tough 1500 Resin V2.

**Headline (my own FE estimate, not a judge result):** in the fused state, H_avg over the visible cases is **0.020** at h = 0.4 mm (0.022 with the datasheet modulus). No fused-state Tough 1500 run shows shielded or overloaded bone volume. The estimated implant stress is 3.2 MPa at 1× of an assumed lifting case, against an allowable of 17 MPa at 2×. The early soft-graft state is much worse (H ≈ 1.3; see §5).

The knowledge base (evidence) is at `<bonetwin>/harness_open/run/r2/single/agents/s1/kb/`, written `KB/` below:
- [KB/design_rationale.md](<<bonetwin>/harness_open/run/r2/single/agents/s1/kb/design_rationale.md>)
- [KB/material_tough1500.md](<<bonetwin>/harness_open/run/r2/single/agents/s1/kb/material_tough1500.md>)
- [KB/preform_validation.md](<<bonetwin>/harness_open/run/r2/single/agents/s1/kb/preform_validation.md>)
- [KB/fe_h.py](<<bonetwin>/harness_open/run/r2/single/agents/s1/kb/fe_h.py>), [KB/make_lattice.py](<<bonetwin>/harness_open/run/r2/single/agents/s1/kb/make_lattice.py>)
- [KB/fe_sweep_v1_h0.8.txt](<<bonetwin>/harness_open/run/r2/single/agents/s1/kb/fe_sweep_v1_h0.8.txt>), [KB/fe_sweep_v2.txt](<<bonetwin>/harness_open/run/r2/single/agents/s1/kb/fe_sweep_v2.txt>), [KB/fe_final_v3.txt](<<bonetwin>/harness_open/run/r2/single/agents/s1/kb/fe_final_v3.txt>)

## 1. Idea

How the judge scores fused-state inhomogeneity determines the design. In the judge's primary state (EVAL_SPEC addendum A2.1), every void inside the implant's convex hull is filled with graft at 1.0 × C_bone. A voxel with implant fill fraction *a* gets *a*·C_implant + (1 − *a*)·C_bone. So the bone outside the hull feels the implant only through *a*·(C_implant − C_bone). To make the implant "mechanically homogeneous with bone" there are two levers (KB/design_rationale.md):

1. **Modulus contrast.** The loads are dominated by axial compression (σ33 = −0.75 to −1.36 MPa in the visible cases; shears ≤ 0.11 MPa). The bone's axial stiffness is E3 = 714 MPa (C33 = 796 MPa). Among the judge's grounded reference materials, Tough 1500 V2 (E = 1136 MPa as measured tonight) is the closest. Its contrast against C33 is about +340 MPa. For comparison, PEEK is +3200 MPa, Rigid 10K +7200 MPa and Ti-6Al-4V about +113 000 MPa (KB/material_tough1500.md).
2. **Volume fraction.** The implant only needs enough material to stay one connected piece and stay strong. With E_implant ≈ E_bone, strut stress roughly follows the iso-strain value E_implant·ε_bone, whatever the strut diameter. Thin struts therefore don't raise stress.

The design is the sparsest robust lattice I could justify. It has 28 vertical struts (0.8 mm diameter) along the load axis (Z), tied by horizontal X and Y struts (0.6 mm) in three layers (bottom, middle, top), with node spheres at the joints. The cells are about 4.4 × 3.7 × 4.6 mm, and the solid volume fraction is 8.2% of the bounding box (KB/preform_validation.md).

## 2. Evidence: my own voxel FE estimate of the judge's metric

I wrote a matrix-free hex8 voxel FE solver (KB/fe_h.py; the lattice generator is KB/make_lattice.py) that follows A2.1:
- a 1.5× box with homogeneous-stress traction BCs on all six faces
- orthotropic lumbar bone from targets.json
- the implant region (the bounding box, ≈ the hull here) mixed by 4³-subsampled fill fractions, with graft = 1.0 × C_bone
- ψ coarse-grained over 0.8 mm cubes of bone voxels.

It is **not the judge**. Its limits:
- the sealed case is unknown, so I used an assumed proxy (σ33 = −2.0, τ23 = 0.2, τ13 = 0.1 MPa), reported separately and left out of H_vis;
- strain is evaluated at element centres;
- the solve tolerance is 1e-7;
- there is no Richardson extrapolation and no G3 simulation.

Raw outputs are in KB/fe_sweep_v1_h0.8.txt, KB/fe_sweep_v2.txt and KB/fe_final_v3.txt.

| Design (Tough 1500 unless noted) | h (mm) | H_avg, visible cases | 99.5% von Mises in implant, 1× load (max over cases, incl. proxy) |
|---|---|---|---|
| Lattice 8×4×3, struts 1.0/0.8 mm (first candidate) | 0.8 | 0.031 | 3.2 MPa |
| Same lattice in **Rigid 10K** (E 8018) | 0.8 | 0.202 | 15.6 MPa |
| Same lattice, Tough at datasheet E 1460 | 0.8 | 0.050 | 4.0 MPa |
| **Solid** Tough 1500 block, 27×12×10 | 0.8 | 0.113 | 2.7 MPa |
| Lattice 8×4×3, struts 0.8/0.6 | 0.8 / 0.4 | 0.019 / 0.026 | 3.2 MPa |
| Lattice 8×4×3, struts 0.7/0.5 | 0.8 | 0.014 | 3.2 MPa |
| **Final: lattice 6×3×2, struts 0.8/0.6** | 0.8 | **0.0135** | 3.2 MPa |
| Final, h = 0.4 | 0.4 | **0.020** (cases 0.020 / 0.020 / 0.022; proxy 0.021) | 3.2 MPa (visible ≤ 2.2) |
| Final, datasheet E 1460 (judge's §5a sensitivity) | 0.8 | 0.022 | 4.1 MPa (visible ≤ 2.7) |
| Final, early state (graft 0.078 × C_bone, A2.2) | 0.8 | 1.29 (shielded 0.1-2.5%, overloaded about 18% of bone) | 14.7 MPa visible (flexion), 21.8 MPa proxy |

How to read the table:
- H falls roughly in proportion to the implant's volume fraction. The h = 0.8 sampling under-resolves thin struts (it gave a volume fraction of 0.10 where h = 0.4 gave 0.13 for the 0.8/0.6 lattice), so the h = 0.4 values are the more trustworthy, and higher.
- Material choice matters more than geometry: the identical lattice in Rigid 10K is about 6× worse.
- For context, the spec's own validation (A2.5) reports H_avg ≈ 0.31 for a 2 mm-wall windowed Rigid 10K cage (12 × 6 × 5 mm) and 0.24 for a 1.2 mm simple-cubic Rigid 10K lattice.
- In every fused-state Tough 1500 run (lattices and the solid block), the shielded fraction (ψ < 0.5 ψ⁰) and the overloaded fraction (ψ > 2 ψ⁰) of bone are both 0.000. The Rigid 10K control lattice shielded 4.5% of bone.

## 3. Integrity gates (my estimates; the judge decides)

- **G1 strength:** the allowable is 34.0 MPa / 2 = 17 MPa at 2× load. My estimated 99.5th-percentile implant stress is about 3.2 MPa at 1× of the assumed lifting proxy, so about 6.4 MPa at 2×, a margin of about 2.6×. In the visible cases it is ≤ 2.2 MPa at 1× (≤ 4.3 MPa at 2×). If the sealed lifting case were about 2.6× more severe than my proxy, G1 would be at risk. That is the main unquantified risk.
- **G2 connectivity:** the mesh is one watertight body (PreForm body-count 1). Every strut is at least 0.6 mm (≥ 3 voxels at h2 = 0.2 mm) and axis-aligned, so it voxelises continuously.
- **G3 damage tolerance:** not simulated. Argument: each strut is attached at both ends to a 3-D node network. Removing a 2 mm sphere at any node or strut leaves every remaining piece attached through another path, including at corners, where each node has three struts. With implant E close to bone, removing 2 mm of material changes H very little: the whole implant only contributes H ≈ 0.01-0.03.
- **G4 size:** longer horizontal side 27 mm (22-55), shorter 12 mm (9-40), height 10 mm (8-18). Pass.
- **P printability:** MANIFOLD, 0 cups, 0 minima, no thin features at 0.3 mm, in bounds. Supportedness is 27.5% unsupported because the saved file has no supports. Auto-support fixes this, but I didn't keep it because it changes the model's reported bounding box (KB/preform_validation.md).

## 4. Material

The material is Tough 1500 V2, declared under the judge's reference-entry name with E = 1136 MPa (tonight's measured value, crosshead strain), ν = 0.35 (assumed, as in the judge's table; Formlabs lists none) and UTS = 34.0 MPa (Formlabs tech specs, https://formlabs.com/products/tough-1500-resin/). See material_spec.json and KB/material_tough1500.md.

The measured E is biased low by machine compliance. The datasheet E of 1460 MPa raises my H estimate from 0.0135 to 0.022 (h = 0.8). The design's ranking logic doesn't depend on which value is right: both are much closer to bone than any other grounded material. Tough 1500's 155% elongation at break also suits damage tolerance.

## 5. Honest limitations

- All numbers here are my own FE estimates, not judge outputs. Its resolution, its centre-point strains and its lack of Richardson extrapolation all differ from the judge. The sealed case is a guess.
- **The early state is this design's weak point.** With soft graft at 30 MPa (A2.2), the sparse lattice makes the hull region much softer than bone. My estimate is H ≈ 1.29, with about 18% of nearby bone overloaded (ψ > 2ψ⁰). The implant then carries the load: its 99.5th-percentile stress is 14.7 MPa at 1× in upper-body flexion, so it would exceed the 17 MPa allowable at 2×. This state is reported, not ranked or gated (A2.2 'for information'). Clinically it means the lattice relies on graft consolidation, or on a stiffer early fixation. That is the price of optimising for the long-term fused state the brief asks about.
- **Clinical integrity is beyond these gates.** A 0.6-0.8 mm resin lattice would not survive impaction or endplate point loads the way a PEEK or titanium cage does. The judge's gates are about physiological stress in a bonded, fused state. A real device would need a solid rim or endplate faces, which would cost homogeneity. Tough 1500 is not an implant-grade material.
- Bone is orthotropic (E1/E2 ≈ 204/236 MPa, E3 = 714 MPa). An isotropic material cannot match it in every direction. Tough 1500 is stiffer than bone laterally, but the lateral stresses here are near zero.
