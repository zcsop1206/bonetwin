# Round 2 changes (exploratory; not part of the frozen round 1 comparison)

Launched 08:48:27 EST Nov 1 2026 at the user's "go" (08:37). Root: `bonetwin/harness_round2/`, code copied from `harness_open/` at 08:38 (code only; no round 1 run data). Run id r3, arm collective, six agents c1-c6, leanings drawn from seed + 3. Group stop 10:03 (75-min cap); forced collection 10:15.

Brief common sha256: `6c9fc74609da1a41252d83801b0fd47550b6e964cacba89b0d6f95790d0e5d7b` (all six identical apart from per-agent blocks; per-brief hashes in `run/run_manifest.json`).

| Change | Where |
|---|---|
| One collective, 1,000,000 credits per agent (total 6M); no roles; shared board, KB and deliverables | config.json, common.build_schedule (only_arms, rep_offset) |
| 75-min wall cap; notices at 30 and 15 min before close (45 and 60 min elapsed) | config.json, scheduler.py |
| Harness posts on the board when an agent reaches 10% of credits and when it runs out; on running out, its work files are copied to kb/handoff_<id>/ | agent_runner.py (system_post, handoff) |
| Brief: objective is addendum 4's M with the implant-alone integrity rule; materials; one undescribed further check; agents may run the metric | briefs.py |
| `goal_metric` tool: runs sim/goal_metric/goal_metric.py for agents, forced to the frozen coarse fallback, max 1M unknowns, one heavy slot; `--with-early` is stripped (the hidden check is never computed for agents). 2000 credits per call | tools/bt_tool.py, tools.json, config |
| Context paragraph: early complete deliverable with a PreForm-validated .form for an on-site printer, Breakerspace data, Formlabs/NVIDIA open to any use | briefs.py |
| Data published read-only: analysis, breakerspace data, analysis_process, figures, citations, round 1 designs (sim/judge_final/subs); addenda 1, 2, 4 only (addendum 3 holds round 1 pre-check scores) | config.json |
| Brev: pool `round2` $60 shared, runs round2-c1..c6, 2 live instances each; NGC key file enabled in compute/caps.json (path only) | compute/caps.json, bt_tool (BT_RUN) |
| Billing: every session starts on the API key (subscription exhausted, user instruction); API cap $125.35 = $180 minus $54.65 from round 1. The whole of round 2 runs on the API | config.json, agent_runner.py |
| max_resumes 3 -> 8, so brief network drops resume the same session id (no new runner, no duplicate) | config.json |
| No control arm, no live leader intervention | launch_open_run.py, config.json |

Smoke test: mock mode, 1-min cap, `smoke/m1`: scheduler started r3/collective, collected, metrics and manipulation ran, exit 0 (mock PreForm wrote no .form, as expected in mock).

First check 08:50: six agents running, every logged message billed to the API, 0 usage-limit events, board active, Brev quote shows the round2 pool at $0 / $60.

Not covered: the evaluator guard's patterns name `harness_open` only, so it does not block the evaluator from `harness_round2/run`; black-box discipline here is by instruction. Python: the harness runs on the venv at the session scratchpad path (`access/Scripts/python.exe`), as in round 1.
