# Results

Lower is better.

| Design | Goal metric M (A4, full res) | Implant-alone integrity | Early graft (withheld state) | Official fused (A2) |
|---|---|---|---|---|
| Round 2 collective | 1.748 [1.233, 2.264] | pass, 14.10/17 MPa | 0.283 [0.214, 0.351] | 0.0628 |
| Control (textbook, Rigid 10K) | 2.283 [2.151, 2.414] | pass | 0.301 [0.261, 0.340] | 0.2057 |
| r2 planner | 4.713 | pass, narrowly | 0.927 | 0.0183 |
| r1 single | 1.916 | fail | 0.424 | 0.0189 |
| r1 planner | 2.824 | fail, narrowly | 0.801 | 0.0325 |
| r2 single | 3.890 | fail | 1.263 | 0.0227 |
| r2 collective | 4.553 | fail | 1.734 | 0.0104 |
| r1 best-of-N | 6.018 | fail | 1.393 | 0.0193 |
| r2 best-of-N (1 mm loop) | 6.732 | fail, 1132/17 MPa | 1.018 | 0.0053 (official winner) |
| r1 collective | no submission | | | ranks last |

Notes: The official ranking (addendum 2) is frozen; the goal metric (addendum 4) is post-registered and exploratory. Official and goal rankings nearly invert (Spearman -0.62, n=8). Round 2 is one arm, one run, no control arm; it knew round 1's lessons and started from a lattice shape given in addendum 4; it ties the control under M's own band rule. Its own coarse-tool value 0.836 became 1.748 when re-scored at full resolution: the fused state agrees within 3%, the gap is the empty state, and 1.748 is a Richardson extrapolation (finest computed 1.233). The early-graft value was withheld from the agents' tool, but addenda 2 and 4 describe that state. Each arm had two replicates, so no arm ranking is claimed. Six-agent arms ran out of credit while singles finished. No check compares the judge against physical tests. Stiffness inputs are one specimen each, crosshead only. Printed parts are demonstrators, not implant-grade. Full incident log: RUN_LOG.md.
