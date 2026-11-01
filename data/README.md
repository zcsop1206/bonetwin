# Breakerspace test data (Oct 31 to Nov 1 2026)

Mechanical tests of printed resin specimens on a universal test machine at Breakerspace, the evidence behind the measured moduli in [`../sim/calibration.json`](../sim/calibration.json). Strain is **crosshead-only** (no extensometer), so moduli read low; see `analysis/CHANGES.md`.

| file | what it is |
|---|---|
| `analysis/results_all.csv` | One row per specimen: modulus, strength and flags from the frozen ingest rules. |
| `analysis/specimen_map.csv` | Raw export name to specimen ID, with the source of each mapping. |
| `analysis/extra_measured_manual.json` | Values entered by hand (for example the auxetic Poisson's ratio), with sources. |
| `analysis/ingest_input/` | The machine CSV exports (`Time, Displacement, Force` in s, mm, kN), byte-identical copies renamed to specimen IDs, plus `dims.csv` (specimen dimensions) and `aux_steps/`. |
| `analysis/SOP_SHORT.md` | The short operator procedure used at the machine. |
| `analysis/CHANGES.md` | Change log of the analysis after its rules were frozen, including the ingest mapping. |

Calibration fit: Rigid 10K 8018 MPa (Form 4), Tough 1500 V2 1136 MPa (Form Studio 1).

## Not in this copy yet

The evaluator guard on the source machine protects these as frozen evidence and refused to let them be copied by this tool. They are unchanged in the private originals and can be added by hand after review:

- `analysis/ingest.py` (the frozen analysis code), `analysis/PROTOCOL.md` (full test protocol), `analysis/raw_data_sha256.txt` (raw-file manifest)
- `breakerspace data/` (raw instrument files: Bluehill `.is_tens`, `.is_comp`, `.id_*`, `.im_*`, PDFs and CSV exports; 47 files, 15 MB). The CSV exports are already here as `analysis/ingest_input/`.
- `sim/run_spec.json`, `sim/desirability.json` (round 1 run and desirability settings)
- `targets/targets.json` (bone targets: needed by `sim/judge/judge.py` and `tools/score_local.py`; its lumbar values are reproduced in [`../CHALLENGE.md`](../CHALLENGE.md))

Never shipped: `targets/sealed_case.json`, `harness/sealed`, `sealed_private`.
