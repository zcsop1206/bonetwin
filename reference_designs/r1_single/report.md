# Bone-matched UHMWPE lattice interbody cage (run r1, arm single, agent s1)

Evidence links point into my knowledge base folder, `kb/`, which sits next to `deliverables/` in the agent folder.

## Summary
- **Design.** A 26 × 12 × 10 mm (X × Y × Z) lumbar interbody cage. It is an orthogonal strut lattice: 9 × 4 = 36 vertical
  columns plus a horizontal strut grid at the top and bottom endplate levels. All struts are square, 1.5 mm, and the
  solid fills 41% of the bounding box (volume 1278 mm³). The other 59% of the hull is graft space, through-connected in
  every direction. +Z is cranial-caudal. The long side is X (bone axis 1). Files: `implant.stl` and `implant.form`
  (PreForm canonical_model_hash d68ffb15…, [kb/preform_model_list.json](kb/preform_model_list.json)).
- **Material.** UHMWPE, declared isotropic: E = 720 MPa, ν = 0.46, tensile yield = 17.0 MPa
  ([material_spec.json](material_spec.json); evidence in [kb/sources.md](kb/sources.md) M1 and M2).
- **Core idea.** In the judged fused state (addendum A2) the hull voids hold graft of bone stiffness, so the bone only
  "feels" the difference between the strut material and bone. Lumbar trabecular bone has E3 = 714 MPa along the
  cranial axis, and that axis carries almost all of the load ([kb/sources.md](kb/sources.md) B1). UHMWPE's datasheet
  modulus (720 MPa) is within 1% of E3. A load-bearing UHMWPE column therefore strains like the bone it replaces:
  neither shielding nor concentration.
- **Result (my own voxel FE, not the judge's).** In the fused state, H_avg ≈ **0.020** over the 3 visible cases plus my
  lifting proxy. Peak implant stress (p99.5 von Mises) at 2× load is about 5.3 MPa under the proxy and at most 2.8 MPa
  under the visible cases. The G1 allowable is 8.5 MPa.

## Method
I wrote an independent hex8 voxel FE that follows EVAL_SPEC v1 §2–3 and addendum A2
([kb/code/fe.py](kb/code/fe.py), [kb/code/sw3.py](kb/code/sw3.py), geometry [kb/code/gen.py](kb/code/gen.py)):
- **Domain and bone.** A box 1.5× the implant, filled with orthotropic bone (targets.json C matrix).
- **Implant.** Supersampled fill fractions mixed as a·C_impl + (1−a)·g·C_bone inside the hull, with g = 1.0 (fused)
  or 0.078 (early).
- **Loads and solver.** Traction BCs from each case's σ, 6 pinned DOFs, pyamg-preconditioned CG at rtol 1e-8.
- **Metrics.** ψ is coarse-grained over 0.8 mm cubes for H_avg.
- **Sealed case.** I did not read it. As a stand-in I used a "lift_proxy" of σ33 = −2.5 MPa with τ23 = 0.3 MPa. That is
  my assumption, not the sealed load.
- **Where it ran.** CPU on the bt_compute L40S node, because the laptop's heavy-job slot was unavailable (low RAM).
- **Resolution.** All comparisons used h = 0.5 mm, coarser than the judge's 0.4 / 0.2 mm. A finer-grid check (h = 0.25)
  did not finish within the session window, so **convergence of my numbers is not verified**.

The raw outputs are in [kb/fe_runs.log](kb/fe_runs.log).

**Comparisons (fused state g = 1; H_avg over visible cases plus proxy; 26×12×10 hull unless noted):**

| Variant | vol. frac. | H_avg | p99.5 vM at 1× (proxy), MPa |
|---|---|---|---|
| solid box, E = 400, ν 0.35 (24×10×10) | 1.00 | 0.202 | 2.66 |
| solid box UHMWPE (720, 0.46) | 1.00 | 0.034 | 2.59 |
| lattice UHMWPE, 1.0 mm struts, 7×3 columns | 0.14 | 0.012 | 2.67 |
| lattice UHMWPE, 1.2 mm, 7×3 | 0.22 | 0.017 | 2.65 |
| lattice UHMWPE, 1.4 mm, 7×3 | 0.26 | 0.018 | 2.66 |
| **lattice UHMWPE, 1.5 mm, 9×4 (submitted)** | **0.40** | **0.020** | **2.66** |
| same 1.5 mm 9×4 lattice in Tough 1500 (E 1136, ν 0.35) | 0.40 | 0.062 | 3.76 |

For context only, the spec's own validation cage (2 mm walls, Rigid 10K, A2.5) scored H_avg ≈ 0.31 in the judge.
That figure comes from different code and a different size, so it is not a like-for-like comparison.

## Integrity: why I did not submit the lowest-H design
The thinnest lattice (1.0 mm struts) had the best fused-state H (0.012). In the **early state**, though, the graft is
soft (g = 0.078, addendum A2.2) and the struts carry nearly all of the load:

| Lattice | early p99.5 vM at 1×, worst visible case (MPa) | early, lift proxy (MPa) |
|---|---|---|
| 1.0 mm, 7×3 | 11.3 | 20.8 (above the 17 MPa yield) |
| 1.2 mm, 7×3 | 9.5 | 17.5 |
| 1.4 mm, 7×3 | 8.2 | 15.1 |
| **1.5 mm, 9×4 (submitted)** | **5.3** | **10.0** |

I accepted a small fused-state cost (0.012 → 0.020) to keep the early-state stresses below yield in every case I
modelled. Under the visible cases the margin is at least 3.2× (17 / 5.3). The judge reports the early state but does
not rank or gate on it. It is my own reading of "without losing integrity": the cage has to survive the months before
fusion.

**Damage tolerance (G3).** This follows from the topology. Every column is tied to both endplate grids, and each grid is
a closed mesh of X- and Y-struts. Deleting any 2 mm sphere (one node or one strut segment) leaves the structure
connected through the other grid or the neighbouring columns. **I did not run G3 numerically.**

## Gates (self-assessed, not judge results)
- **G4 size.** Long side 26 mm (allowed 22–55), short side 12 mm (allowed 9–40), height 10 mm (allowed 8–18). Pass.
- **G2 connectivity.** One body. The STL has 0 unmatched directed edges and a signed volume of 1278 mm³
  ([kb/code/chkstl.py](kb/code/chkstl.py)). PreForm manifoldness: MANIFOLD.
- **G1 strength.** p99.5 vM at 2× load, fused state: visible cases ≤ 2.84 MPa and proxy 5.3 MPa, against an allowable
  of 8.5 MPa. This passes **only if** the sealed lifting case has a σ33 magnitude below roughly 4 MPa. I expect about
  2–3 MPa from the targets.json beam formula with typical lifting loads, but I have not verified that.
- **Printability (flag only).** PreForm reports the submitted model as MANIFOLD, and its thin-feature check at 0.3 mm
  found 0 thin regions. No supports were generated, so the supportedness check may
  be flagged.

## Caveats (honest limitations)
1. **Material grounding.** E and yield come from a Celanese GUR 4120 datasheet as listed on a distributor page
   ([kb/sources.md](kb/sources.md) M1). ν = 0.46 comes from Goodfellow (M2). GUR 4120 is an industrial grade. The
   implant grade (GUR 1020, ASTM F648) is the same polymer family, but I could not open a source giving its modulus. If
   the checker rejects E, the spec's nearest-log-E fallback could map the implant to trabecular bone, whose 2 MPa
   strength would fail G1. That is a real risk I chose to accept for the stiffness match.
2. **Manufacturing.** UHMWPE is not an SLA resin. The PreForm scene uses Tough 1500 V2 on a Form 4 as a printable
   prototype of the geometry. A clinical UHMWPE part would be moulded or machined, and 1.5 mm struts at about 3 mm
   pitch are at the edge of what is practical.
3. **UHMWPE behaviour.** UHMWPE creeps. Compression tests report a lower ν (~0.33) than the 0.46 datasheet value.
   Neither effect is modelled; the judge is linear elastic.
4. **Model gaps.** My FE resolution is coarse (h = 0.5 mm, convergence unverified), and the sealed case is a guess.
5. **Isotropy.** An isotropic material cannot match the softer transverse bone moduli (204 / 236 MPa). The remaining H
   comes mainly from the horizontal endplate grids and from the Poisson mismatch (0.46 against ~0.34). That is also why
   the solid UHMWPE block (0.034) scores worse than the lattices.
