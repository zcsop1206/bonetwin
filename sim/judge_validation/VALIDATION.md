# Judge validation on non-arm geometry (EVAL_SPEC_v1 s9)

Box = 1.5x the implant bbox in lumbar trabecular bone; 3 visible + sealed cases; H = pooled bone SED mismatch.

| shape | material | E (MPa) | h1/h2 | DOF h2 | H1 | H2 | H_R [band] | H_avg R [band] | max shielded / overloaded frac | G1 p99.5@2x / allow | G2 | G3 | G4 | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| block_24x12x10 | bone_equivalent | 385 | 0.80/0.40 | 489,762 | 0.001 | 0.000 | -0.001 [-0.003, 0.000] | -  | 0.00 / 0.00 | 3.7 / 1.0 FAIL | True | False | True | 250 |
| block_24x12x10 | bone_equivalent [A2 graft 0.5] | 385 | 0.80/0.40 | 489,762 | 0.001 | 0.000 | -0.001 [-0.003, 0.000] | -0.001 [-0.003, 0.000] | 0.00 / 0.00 | 3.7 / 1.0 FAIL | True | skipped (--no-g3) | True | 61 |
| block_24x12x10 | peek450g | 4000 | 0.80/0.40 | 489,762 | 0.260 | 0.273 | 0.286 [0.273, 0.299] | 0.280 [0.270, 0.291] | 0.10 / 0.00 | 10.6 / 49.0 ok | True | skipped (--no-g3) | True | 72 |
| block_24x12x10 | rigid10k | 8018 | 0.80/0.40 | 489,762 | 0.306 | 0.319 | 0.331 [0.319, 0.344] | -  | 0.14 / 0.00 | 14.3 / 32.5 ok | True | skipped (--no-g3) | True | 73 |
| block_24x12x10 | ti6al4v | 113800 | 0.80/0.40 | 489,762 | 0.384 | 0.399 | 0.414 [0.399, 0.429] | -  | 0.19 / 0.01 | 22.6 / 440.0 ok | True | True | True | 1293 |
| block_24x12x10 | ti6al4v [A2 graft 0.5] | 113800 | 0.80/0.40 | 489,762 | 0.384 | 0.399 | 0.414 [0.399, 0.429] | 0.390 [0.387, 0.393] | 0.19 / 0.01 | 22.6 / 440.0 ok | True | skipped (--no-g3) | True | 81 |
| block_24x12x10 | tough1500 | 1136 | 0.80/0.40 | 489,762 | 0.100 | 0.108 | 0.116 [0.108, 0.125] | 0.114 [0.107, 0.121] | 0.00 / 0.00 | 5.1 / 17.0 ok | True | skipped (--no-g3) | True | 63 |
| cage_window_24x12x10 | rigid10k | 8018 | 0.80/0.40 | 428,904 | 1.820 | 2.779 | 3.738 [2.779, 4.697] | -  | 0.21 / 0.16 | 33.8 / 32.5 FAIL | True | True | True | 447 |
| cage_window_24x12x10 | rigid10k [A2 graft 0.5] | 8018 | 0.80/0.40 | 489,762 | 0.351 | 0.377 | 0.404 [0.377, 0.430] | 0.385 [0.368, 0.401] | 0.16 / 0.01 | 16.8 / 32.5 ok | True | skipped (--no-g3) | True | 90 |
| control_femur_3d | rigid10k | 8018 | 0.80/0.40 | 1,292,787 | 0.332 | 0.334 | 0.336 [0.334, 0.338] | 0.326 [0.324, 0.329] | 0.13 / 0.00 | 26.7 / 32.5 ok | True | skipped (--no-g3) | False | 210 |
| control_femur_3d | rigid10k [A2 graft 0.5] | 8018 | 0.80/0.40 | 1,316,928 | 0.339 | 0.333 | 0.326 [0.320, 0.333] | 0.321 [0.312, 0.330] | 0.15 / 0.00 | 24.1 / 32.5 ok | True | skipped (--no-g3) | False | 208 |
| lattice_sc_24x12x10 | rigid10k | 8018 | 0.80/0.40 | 452,694 | 0.202 | 0.214 | 0.226 [0.214, 0.238] | 0.197 [0.195, 0.200] | 0.03 / 0.00 | 35.3 / 32.5 FAIL | True | skipped (--no-g3) | True | 70 |
| lattice_sc_24x12x10 | rigid10k [A2 graft 0.5] | 8018 | 0.80/0.40 | 489,762 | 0.217 | 0.223 | 0.228 [0.223, 0.234] | 0.213 [0.212, 0.215] | 0.06 / 0.00 | 28.2 / 32.5 ok | True | skipped (--no-g3) | True | 84 |
| lattice_sc_24x12x10 | rigid10k (datasheet E) | 11000 | 0.80/0.40 | 452,694 | 0.239 | 0.246 | 0.254 [0.246, 0.262] | 0.231 [0.227, 0.235] | 0.06 / 0.00 | 39.1 / 32.5 FAIL | True | skipped (--no-g3) | True | 76 |
| lattice_sc_24x12x10 | tough1500 | 1136 | 0.80/0.40 | 452,694 | 0.395 | 0.646 | 0.897 [0.646, 1.149] | 0.846 [0.620, 1.072] | 0.02 / 0.10 | 28.0 / 17.0 FAIL | True | skipped (--no-g3) | True | 69 |
| lattice_sc_24x12x10 | tough1500 [A2 graft 0.5] | 1136 | 0.80/0.40 | 489,762 | 0.065 | 0.090 | 0.114 [0.090, 0.139] | 0.103 [0.084, 0.122] | 0.00 / 0.00 | 8.6 / 17.0 ok | True | skipped (--no-g3) | True | 69 |

## The 24 mm shapes under the proposed A2 (graft 0.5, h1/h2 = 0.8/0.4; see `VALIDATION_table.md`)

| shape | material | H_R [band], spec H | H_avg R [band] |
|---|---|---|---|
| bone-equivalent block | bone | −0.001 [−0.003, 0.000] | −0.001 [−0.003, 0.000] |
| solid block | Ti-6Al-4V | 0.414 [0.399, 0.429] | 0.390 [0.387, 0.393] |
| windowed cage | Rigid 10K | 0.404 [0.377, 0.430] (v1 void rule: 3.74 [2.78, 4.70]) | 0.385 [0.368, 0.401] |
| SC lattice | Rigid 10K | 0.228 [0.223, 0.234] | 0.213 [0.212, 0.215] |
| SC lattice | Tough 1500 | 0.114 [0.090, 0.139] (v1: 0.90 [0.65, 1.15]) | 0.103 [0.084, 0.122] |
| femur control lattice (20 mm cube) | Rigid 10K | 0.326 [0.320, 0.333] (v1: 0.336 [0.334, 0.338]) | 0.321 [0.312, 0.330] |

Under A2 every band is narrow enough to rank, and the order is physically sensible: compliant lattice < stiff lattice < windowed stiff cage ≈ solid Ti.
