# Breakerspace SOP, short version (Sat Oct 31)

Full details and the fixed analysis rules: PROTOCOL.pdf. Part shapes and plate maps: PART_ID.html.

## Every test
1. Read the ID on the raft and write it on the part before snapping it off.
2. Calipers first (3 readings, mean) into `dims.csv`.
3. 5 kN load cell, 50 Hz. Zero load before gripping, never after.
4. Dots: round, 0.5 to 1 mm, facing the camera; check the extensometer locks on before Start.
5. Export one raw CSV per specimen: `<ID>_<test>.csv`.
6. Problem? One code in `exclude_reason` (slipped, damaged_before_test, wrong_speed, wrong_setup, id_uncertain, aborted_early, machine_fault). Test it anyway.

## Order and priority

**SIM** = needed to validate the simulator against the real world. **CONTEST** = needed to score the prediction contest.

Print key: **P1** = today's Form 4 plate, Rigid 10K (17 parts). **P2** = today's Form Studio 1 plate, Tough 1500 V2 (3 parts). **print1** = Alan's Form 4 print from this morning, Tough 1500 V2.

| # | Test | From print | Setup in one line | SIM | CONTEST |
|---|---|---|---|---|---|
| 1 | Lattice cubes CUBE-REF-1..3, x then y then z on each | P1 | Platens, 1 mm/min, stop at 0.10 mm, unload between axes; z = thicker struts | **Critical**: the only direct check of the 3-D lattice model | yes |
| 2 | Rigid 10K dog-bones DB-R-F4-FLAT-1..3 | P1 | 5 kN wedge grips, gap 25.4 mm, dots 7.6 mm apart, 5 mm/min to break | **Critical**: solid stiffness Es | yes |
| 3 | DSX ladders LAD-V-1 (0.4, 0.7, 1.0) and LAD-H-1 (0.7, top and bottom) | P1 | 3-D capture, line profile across each feature, export CSV | **Critical**: printed vs drawn strut width; designs use 0.8 to 2.5 mm struts | yes |
| 4 | Prisms PR-R-F4-UP-1..3, then PR-R-F4-FLAT-1..3 | P1 | Platens, 1 mm/min, stop at 0.5% strain, dots 6 mm apart | **Important**: stiffness across vs along layers | yes |
| 5 | AUX-1 | print1 | Platens, 1 mm/min to 1.5 mm, 4 dots + transverse strain, film on phone | **Important**: only physical test of inclined struts, where the fast and solid models disagree | no (extra check) |
| 6 | Notched bars SENB-R-1..3 | P1 | Razor-tap notch to ~5 mm, 3-point bend, span 40, notch down, 10 mm/min | Useful: strut stress allowable (defaults exist) | yes |
| 7 | Tough 1500 dog-bones DB-T-S1-FLAT-1..3, then D1..D3 | P2, then print1 | As #2; D1..D3 gap 65 mm, dots 25 mm | Not used by tonight's Rigid 10K designs | yes |

If time runs short, cut from the bottom. Rows 1 to 3 are the minimum for a calibrated simulator; rows 1 to 4, 6 and 7 complete the contest.

## Hand-off
Copy every CSV, `dims.csv`, photos and the AUX-1 video into one folder on the USB stick, then tell Claude.
