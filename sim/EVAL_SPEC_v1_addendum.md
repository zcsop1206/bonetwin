# EVAL_SPEC v1 addendum A1 (2026-11-01, pre-launch)

This addendum amends `EVAL_SPEC_v1.md` without editing it. That file is hashed. Where the two differ, the addendum governs.

## A1.1 Submission layout and file names (replaces the file names in the preamble and in §1)

Each run submits one folder, `submissions\<run>\`, containing:

| file | required | role |
|---|---|---|
| `implant.form` | yes | the PreForm project with the implant (§1.1-§1.2: models, validation, scene settings) |
| `implant.stl` or `implant.3mf` | strongly recommended | the backup mesh for §1.3(c); accepted only if it hash-matches the `.form` model |
| `material_spec.json` | yes | the material, its properties and the source for each (§5) |
| `report.md` | yes | the report the secondary panel reads (§7) |

**How the intake maps these names:**
- `implant.form` is the submission. Any other `.form` file in the folder is ignored and listed in the record.
- Mesh candidates for §1.3 are tried in this order:
  1. the `.form` model's `original_file`;
  2. `implant.stl`;
  3. `implant.3mf`;
  4. any other STL/OBJ/3MF in the folder.
- The `canonical_model_hash` rule of §1.3 applies unchanged.
- A folder without `implant.form` is "no submission" (§8.3).
- If `report.md` or `material_spec.json` is missing, the folder is still scored. Every material property then falls back to the reference rule of §5, and the panel scores the missing report as absent.
- The deadline rule of §8.3 applies to `implant.form` (file time, or received after 07:00 EDT).

## A1.2 Pre-check (not a judging step)

`sim\judge\precheck.py` runs the same pipeline at reduced settings:
- the visible load cases only, with no sealed case;
- one resolution, h = 0.4 mm;
- no Richardson extrapolation (the band is reported as ±0, flagged "coarse");
- gates G1, G2 and G4, with G3 optional.

The harness may use it at 07:00 only to choose which submission of each best_of_n run goes forward. Its output is never a score, and agents never get it.
