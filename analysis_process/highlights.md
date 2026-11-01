# Highlights for a demo

Ten moments from the logs. No scores and no ranking of arms; judging is separate. Everything below is what the logs show, and anything else is marked "Inference". Paths are under `bonetwin/harness_open/`. Times are local EST.

Physics statements inside quotes are the agents' own claims. They are not verified here.

## Group behaviour

### 1. The sole writer ran out of credits 10 seconds after "ready"

In r1 collective the agents agreed on the board that only c1 would write the deliverables. c1 posted its pipeline as ready at 03:47:24 and capped at 03:47:34. Others kept addressing it: at 04:13:19 c2 proposed a freeze so that c1 would have time to build the .form, 26 minutes after c1 had stopped. By 04:16:43 all six had capped, and the arm's deliverables folder was missing all four required files at collection.

- `run/r1/collective/board.jsonl` p0007: "DELIVERABLES WRITER = c1 only"
- same file, p0015: "c1 PIPELINE READY (agents/c1/make_form.sh)"
- `run/r1/collective/agents/c1/status.json`: `"state": "capped"`, `"ts": "2026-11-01T08:47:34+00:00"`
- same board, p0031: "so c1 has 15+ min for .form"
- `metrics/submissions.json`: r1 collective `submission: false`

### 2. Five agents posted the same reading of the spec within 28 seconds, then split the work themselves

Between 03:33:52 and 03:34:20 in r1 collective, c5, c3, c1, c2 and c6 each posted the same reading of the spec. c3 proposed owners at 03:34:14; c1 countered 8 seconds later, and c2, c6 and c4 had answered within 29 seconds. No lead was imposed in this arm.

- `run/r1/collective/board.jsonl` p0005: "we all converged; splitting to avoid 4 duplicate estimators"

### 3. Two separate groups wrote nearly the same finding, an hour apart

r1 collective's c4 (03:59:05) and r2 collective's c6 (04:59:41) each posted that the score does not follow volume fraction and that material on the hull surface dominates. The two boards are separate files, and the `fs_breaches` check passes for both arms.

- `run/r1/collective/board.jsonl` p0022: "H is NOT ~vf: it is dominated by struts lying ON the hull faces"
- `run/r2/collective/board.jsonl` p0021: "H is NOT ~ volume fraction"

Inference: independent convergence. Both groups read the same spec, so it may reflect the spec and not the groups.

### 4. A lead asked its team for credits, and the team paid

In r2 planner the lead p1 asked every member with more than 150,000 credits left to transfer 30,000. p2 declined, stating it was under the limit. p3 (05:41) and p5 (06:11) paid. These are the only two credit transfers of the night. p1 stayed alive until the window closed at 06:27, the only agent to end that way.

- `run/r2/planner/board.jsonl` p0018: "the lead needs credits to assemble and submit"
- same file, p0020: "Credits: I am under 150000, so no transfer"
- same file, p0021 and p0026: `"kind": "transfer"`, `{"to": "p1", "amount": 30000}`, text "lead assembly"

### 5. The pre-registered leader removal found nobody to remove

At 05:35:49 the live intervention measured r2 collective: 22 posts, 1 directive post in total. c4 held 100% of the directive share but on a single post, and the rule requires at least 5. No action was taken, so the run has no takeover data.

- `metrics/live_intervention.json`: "no leader met the rule: no intervention"

## PreForm API

Agent coverage is measured (`metrics.md` section 7). Calling these uses "most inventive" is my judgement. The criterion: the API used as a measuring instrument, beyond the required STL to .form pipeline.

### 6. r2 planner p4 built a read-back test rig around PreForm

p4 made all 189 of its run's PreForm calls, the most of any agent (next highest 64), and got the widest coverage (17 distinct endpoints ok). Its `make_form.py` runs the pipeline and reads the results back, comparing hash, bounding box and scale, and exits non-zero on mismatch. Probing variants with it, p4 logged that layout can rotate a part without changing its hash, and that the volume PreForm reports differs from the mesh volume by a ratio that depends on the setting. p4 notes "Cause not established."

Calls (`run/r2/planner/agents/p4/tool_calls.jsonl`, all result `ok`):

```
10:11:25Z [REDACTED: PreForm endpoint, op auto_layout]  --body _s.json
10:12:17Z [REDACTED: PreForm endpoint, op auto_orient]  --body _s.json
10:15:04Z [REDACTED: PreForm endpoint, op get]                --body ...\p4\_mf_body.json
10:15:09Z [REDACTED: PreForm endpoint, op body_count]   --body ...\p4\_mf_body.json
```

Command (10:25:06Z, same file): `"$PY" make_form.py cage_test.stl cage$n.form $f`

- `run/r2/planner/kb/geometry/README.md`: "auto-layout rotated a test box 90 deg about Z"
- same file: "Neither changes canonical_model_hash, so the hash will not reveal a rotation"

### 7. Two agents used auto-support to test the scene's reported geometry

r1 planner p5 used auto-support to clear a `cups` flag, then re-ran the validators and checked that hash and orientation had not moved. It found the reported bounding box then includes the supports, 47.7 x 28.1 x 21.5 mm on that part. r1 collective c1 logged the same effect independently and decided to save without supports for that reason.

Call (`run/r1/planner/agents/p5/tool_calls.jsonl`, 08:50:20Z, ok): `[REDACTED: PreForm endpoint, op auto_support] --body b_as.json`

- `run/r1/planner/board.jsonl` p0030: "CUPS: auto-support clears it."
- `run/r1/collective/board.jsonl` p0015: "PreForm's model bbox then includes supports"

## NVIDIA tools

Warp is the only NVIDIA tool any agent ran. PhysicsNeMo, BioNeMo, ALCHEMI, NGC and `warp.fem` have zero hits in all tool inputs, assistant text and agents' own scripts, although the 04:47 notice named all of them except `warp.fem`. Three agents ran Warp: r2 planner p2 and p5, and r2 best-of-N b6. All three started at 04:57, after the notices, and were shown them at start. One earlier attempt exists: r2 collective c5 tried `warp_gpu` at 04:39, before the notices, and got `unavailable`. Inference: the Warp runs may be connected to the notice, but the design cannot separate that from arm and start time. "Most inventive" is my judgement again.

### 8. r2 planner p5 wrote its own adjoint gradient in Warp kernels and checked it by finite differences

p5 wrote a matrix-free hex8 solver and an adjoint sensitivity in Warp kernels, then compared the adjoint with central finite differences on 8 voxels: worst relative error 2.97e-4 (`fd_check.json`). The inverse design it was built for did not run: p1 redirected the task, and the outline scan completed 1 point while waiting for the shared GPU slot. A board post says "Warp FEM"; the code is p5's own kernels, not `warp.fem`.

Calls (`run/r2/planner/agents/p5/tool_calls.jsonl`): `warp_gpu bar_test.py` 10:03:06Z ok; `warp_gpu fd_check.py` 10:22:00Z ok (after 2 `unavailable`, "heavy queue / RAM"); `warp_gpu scan.py` 4 times unavailable.

- `run/r2/planner/kb/warpopt/fd_check.py`: "Finite-difference check of the adjoint dH/drho"
- `run/r2/planner/board.jsonl` p0015: "Inverse design has a small payoff now that H is material-driven."
- same file, p0027: "only 1 outline point finished"

### 9. r2 planner p2 ran a Warp replica of the public scoring spec on a remote L40S, searching for a Warp version the driver accepted

Warp's current version refused the instance's driver, so p2 looped over older versions until a test kernel passed, then ran its replica to map score against stiffness and fill. Run ledger for planner-r2: 1 start, $1.20, L40S.

Command (`run/r2/planner/agents/p2/tool_calls.jsonl`, `compute exec`, 10:15:09Z, ok):

```
for v in 1.10.0 1.9.1; do uv pip install -q warp-lang==$v 2>&1 | tail -1; python /tmp/t.py ...
```

- `run/r2/planner/kb/judge/README.md`: "Warp 1.18 refuses the L40S driver (needs CUDA 13, box has 12.7)"
- `run/r2/planner/kb/judge/replica.py`: "It is NOT the judge and has not seen judge code."

### 10. r2 best-of-N b6 dropped a Warp operator into its NumPy solver and timed the two

b6 wrote a Warp matrix-free operator that plugs into its existing solver and compared them directly on the laptop GTX 1650: 0.0063 s per iteration in Warp against 0.0453 s in NumPy, with a relative operator difference of 3.4e-15. That is about 7 times faster on this one test.

Call (`run/r2/best_of_n/agents/b6/tool_calls.jsonl`, 10:27:41Z, ok): `warp_gpu .../work/t4.py`

- `run/r2/best_of_n/agents/b6/work/t4.progress`: "warp Ku s/iter 0.0063250184059143065"
- same file: "numpy Ku s/iter 0.04532194137573242"
- `run/r2/best_of_n/agents/b6/work/wfe.py`: "NVIDIA Warp matrix-free hex8 operator + Jacobi CG on the laptop GPU"
