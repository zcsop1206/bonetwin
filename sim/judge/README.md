# bone-twin judge (`sim/judge/`): implements `EVAL_SPEC_v1.md` and addendum A1

| file | role |
|---|---|
| `judge_intake.py` | Opens `implant.form` through PreFormServer, which it restarts if it is down. Records the models (hashes, pose, bounding box, `original_file`), body count and PreForm validation (printability gate P). Finds a mesh that hash-matches the `.form` model: `original_file`, then `implant.stl`, then `implant.3mf`, then any other mesh file. |
| `judge_geom.py` | Turns the mesh into a manifold, then into a supersampled voxel fill fraction (sub-grid about 0.07 mm) plus the convex-hull mask R. Uses manifold slicing with even-odd polygon rasterising. |
| `judge_fe.py` | Hex8 voxel finite elements on a rectangular box. Bone is orthotropic (`lumbar_vertebra`). The implant uses E × fill fraction. Hull voids are removed. Loads are face tractions; rigid modes are suppressed by 3-2-1 pins. The solver is CG preconditioned with pyamg smoothed aggregation using the 6 rigid modes. |
| `judge.py` | Runs one mesh and one material at h1 = 2·h2 and h2. Outputs: H (pooled strain-energy-density mismatch in bone, 3 visible + sealed cases) at each level, the Richardson H_R and its band, and gates G1 (p99.5 von Mises at 2× load ≤ strength/2), G2 (one component), G3 (8 deletions of 2 mm spheres) and G4 (lumbar size envelope). `--datasheet` gives the §5a sensitivity run. |
| `judge_submission.py` | Handles one `submissions/<run>/` folder: deadline and file checks, then intake, then material resolution (grounded declaration, else the reference fallback), then primary and sensitivity judge runs. |
| `judge_rank.py` | Ranks runs: gate-passing runs first, ordered by H_R; overlapping bands count as ties. Reports Kendall τ-b between the primary and sensitivity rankings. |
| `panel_prepare.py` | Builds blinded, seeded panel packets: redacted report, material spec, the judge's results and the rubric. Writes a sealed key file. |
| `precheck.py` | Harness-only, never a score (A1.2). Visible cases only, h = 0.4, gates G1/G2/G4. |
| `reference_materials.json` | The §5 reference table, including the datasheet moduli for §5a. Rigid 10K and Tough 1500 moduli come from `sim/calibration.json`. |

Validation runs on non-arm geometry only: `../judge_validation/` (`make_shapes.py`, `run_validation.sh`, `results/`).

## Implementation notes (choices made inside the spec)

- **Partly filled voxels.** In each voxel, a is the implant's fill fraction and c is the convex hull's, both from the same sub-grid (about 0.07 mm). The voxel stiffness is a·C_implant + (1 − c)·C_bone; the hull-but-unfilled part, c − a, is void. Voxels that are entirely void (a = 0, c = 1) are removed. This matches §2: void inside R, bone outside R. A bone-equivalent solid block gives H = 0.0014 at h = 0.8. Before this rule (the centre-sampled hull of 01:30) it gave 0.14.
- **The H region B.** H is computed over voxels with c = 0, that is, entirely outside the hull.
- **G3 deletions** use a global-local re-solve by default. A submodel spans 8 x 8 x 8 mm (R = 4 mm) around each deleted 2 mm sphere. Interface nodes keep the intact displacement, and the deleted voxels carry 1e-6 of their stiffness.
  - Against a full re-solve at h = 0.8 (`mode="full"`): on the Ti block, dH agrees within 3e-4 and p99.5 within 1%. On the windowed Rigid 10K cage, dH differs by up to 0.015 (with the sign flipped) and p99.5 agrees within 1%. Both are far inside the gate's 0.10 threshold.
  - It is 10-25x faster. The full mode needed about 300 CG iterations per deletion for Ti at h = 0.4, about 20 min per submission.
- **Resource limits.** Each judge process sets itself to below-normal priority and at most `JUDGE_THREADS` (default 4) BLAS/OpenMP threads. Assembly is chunked to bound memory.
