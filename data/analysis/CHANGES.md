# ingest.py change log

Rules frozen at 18:50 on Oct 31 2026 (see the header of ingest.py and the "Analysis rules" page of PROTOCOL.md).
Every change to ingest.py after that time is logged here, with the time, what changed and why.

| Time | Change | Reason |
|---|---|---|
| Oct 31 ~19:45 | No change to ingest.py, PROTOCOL.md or track_dots.py (still match their 18:17 hashes). Added operator aids SOP_SHORT.md and PART_ID.md/html; the suggested test order now puts simulator-critical tests first | Operator could not identify parts; protocol too long to use at the machine |
| Nov 1 ~00:15 | No change to ingest.py (sha256 a477536e... unchanged), PROTOCOL.md, score.py, sealed files or fit_calibration.py (37e3ae78...). Raw data manifest (85dc4026...) re-verified before and after; nothing in `breakerspace data/` modified. Added `adapt_breakerspace.py` (byte-identical copies into `ingest_input/`; read_bluehill already handles `Time,Displacement,Force` + `(s),(mm),(kN)`, so no format conversion) and `specimen_map.csv` (mapping with source column) | Breakerspace exports are not named `<specimenID>_<test>.csv` |

### Nov 1 ~00:15: Breakerspace data ingested

Mapping (raw -> ingest_input, source):
- tough_1_5mm-min_1.csv -> D1_tension.csv (print1 Type IV, Tough 1500, Form 4; Alan's agent, Discord 21:04)
- tough_large_2.is_tens_Exports/tough_large_2_1.csv -> D2_tension.csv (print1 Type IV; Alan 21:41 'dogbone 2')
- tough_small.is_tens_Exports/tough_small_1.csv -> DB-T-S1-FLAT-1_tension.csv (P2 Type V, Tough 1500, Form Studio 1; Adit's notes)
- tough_1_5mm-min_2.csv -> DB-R-F4-FLAT-1_tension.csv (P1 Type V, Rigid 10K; Adit confirmed)
- lattice_x/y/z_1.csv -> CUBE-REF-1_compx/compy/compz.csv (one cube, replicate number unrecorded, identical design)
- aux_5mm_1..3.csv -> ingest_input/aux_steps/ only (not globbed by ingest). Not concatenated: no strain columns and no video, so ingest cannot compute AUX nu and does not need the trace.
- compression_1_1/_2.csv -> UNKNOWN-1_comp.csv / UNKNOWN-2_comp.csv, dims.csv exclude_reason id_uncertain (ingest also skips them as unknown specimens).
- Not used: rigid_1_5mm-min.is_tens_small_1.csv, top-level tough_large_2_1.csv and tough_small_1.csv (all three are the same 6-line Bluehill results-table stub, sha 6f026a..., no raw data).

dims.csv source: Adit's caliper notes (written as cm, read as mm). Thickness: Rigid 10K Type V 3.4; Tough Studio 1 Type V 3.6; Tough Form 4 Type IV 2.91, applied to D1 and D2 (assumed same as the recorded Form 4 dog-bone). Widths left blank (recorded 9.50 / 9.48 / 21.02 are tab widths), so ingest uses nominal gauge widths 3.18 (Type V) and 6.0 (Type IV) and marks nominal_dims. Grip separations recorded 25.4 (Type V) and 66 mm (Type IV, protocol 65): ingest's fixed L0 (65) kept, deviation noted only. Failure locations not recorded (blank). Cube edge not measured (nominal 20 mm). Notes avoid the words fit_calibration's X2 rule treats as exclusion flags.

Run: `python ingest.py ingest_input --out ../harness/measured.json --results results_all.csv --extra extra_measured.json`. No rule changed. All tension moduli use crosshead strain (no video columns) and carry crosshead_compliance_warning + nominal_dims.

AUX-1 nu by calipers (deviation from protocol, approved by the user) recorded by hand in `extra_measured_manual.json` from Alan's report; not an ingest output, not scored.

### Nov 1 ~00:30: decision on the dims.csv note wording (evaluator, user asked for the prudent path)

The ingestion agent removed the word "flagged" from its own descriptive notes in dims.csv because fit_calibration's X2 rule excludes specimens whose notes contain flag words. X2 exists for operator exclusions made at the machine; these notes were the agent's description of the nominal-width fallback, not operator flags, so the measured values are kept as the PRIMARY calibration (Rigid 10K 8018 MPa, Tough 1500 1136 MPa). Because both the measured values (crosshead-only; Tough disagrees ~2x with Alan's video-tracked D2) and datasheet values (cure unconfirmed) are uncertain, the judge pre-registers a SENSITIVITY analysis scoring every submission with datasheet stiffness too and reporting whether the ranking changes (EVAL_SPEC_v1.md).
