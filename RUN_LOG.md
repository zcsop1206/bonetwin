# Run log, Sun Nov 1 2026 (EST), pending upload to the doc ("Bone-twin DoE plan" tab)

| Time | Event | Effect on the experiment |
| --- | --- | --- |
| 00:52 | First open-ended launch: 38 sessions at once, each with a visible console window; laptop froze; user force-closed and rebooted | Aborted; archived as *_aborted_0052; nothing scored |
| 03:32 | Relaunch with admission control (max 14, RAM/CPU gated, hidden, low priority), 90-min equal caps, 3 waves, 08:30 hard deadline; 14 sessions started (both r1 groups, both singles, r1 b1); all on API credits (subscription exhausted), ~$8 in the first 9 min | Billing source recorded per turn |
| 03:41 | Memory commit 33 of 34.9 GB; Brave browser held 5.7 GB; closed by the user | None on arms |
| 03:44-04:04 | Commit 94-98.6% from agents' own Python jobs (up to 5.3 GB each). User chose to ride it out and document failures; no agent process was stopped for memory | Shared condition for all arms; system-level log compute/memlog.jsonl every 30 s (memory, process counts, large Python jobs that disappeared, Windows low-memory events) |
| 03:50 | Evaluator lowered admission (max 14 -> 12 sessions, min free RAM 3.0 -> 3.5 GB) and restarted only the scheduler in recovery mode; a bug made it start duplicate runners for all 14 live agents for 1-2 min. Duplicates killed (108 processes), faulty scheduler stopped | INCIDENT. 14 agents flagged (metrics/incident_0350.json): r1 c2-c6, p1-p6, b1, both singles. r1 planner lead p1 later out of quota, possibly from its duplicate |
| ~04:00 | Recovery bug fixed (alive check by pid + creation time + command line; respawn at most once, only after a mid-turn crash); tested 9/9; scheduler restarted: 12 alive left alone, 3 finished, 0 respawns | New admission limits active |
| before 04:00 | r1 collective c1 out of quota; r1 planner p2 finished | From process records, numbers only |

| 04:50 | Two identical creativity notices sent at the user's request: 11 delivered, 7 pending, 20 missed | Human intervention, logged; notice confounded with replicate |
| 05:35 | Live leader intervention evaluated on r2 collective: no agent met the rule; no action | No takeover data |
| 06:27 | All sessions finished; r1 collective handed in nothing; r1 planner and r2 collective lack a report; both best-of-N picks used the random fallback | Diagnosis under way |
| ~06:50 | User moved the guard's read unlock from 07:15 to 06:45 (no agent was running); judge code verified against its manifest first (11 files, 0 problems) | Writes to arms and frozen files stay blocked |

| ~07:00 | Brev curfew moved from 07:15 to 12:00 for judging (user approved); judge cap to be lowered uniformly (addendum 3) | Deviation from the spec's 25M cap, logged |
| ~07:05 | Diagnosis: r1 collective agreed on the board that c1 was sole writer; c1 ran out of quota 10 s after posting "PIPELINE READY" (15 min in); nobody took over; all capped by 04:16. r2 collective and r1 planner lost their reports the same way | Emergent single point of failure; rule says r1 collective ranks last |
| ~07:05 | Diagnosis: every agent in the six-agent arms capped (except 3 of 6 in r2 planner), both singles finished with quota left; 54-78% of credits went on cache reads | "Equal credits" handicaps six-agent arms; must be stated with the results |
| ~07:05 | Correction: r1 planner lead p1's quota loss came from its original runner, not its duplicate. The 03:50 duplicates made only read-only probes; no duplicate writes or posts found | Corrects the 03:50 row above |
| ~07:05 | Harness bug: best-of-N pre-check timed out (900 s), used a wrong key, and excluded agents without a report. User approved applying the rule now on every agent with a .form; as-collected picks (r1 b2, r2 b3) also scored and shown | Deviation, logged in addendum 3 |

| before 07:13 | All 8 best-of-N pre-checks back (r1 b1, b3, b4 on the laptop, the other 5 on Brev, same code). Rule picks equal the as-collected picks, r1 b2 and r2 b3. L40S has 8 vCPU, 144 GB; uniform cap set to 20M unknowns, per the judge agent | Best-of-N entries unchanged; estimated finish 10:40, about $8.2 of the $10 pool |

| 07:13 | Addendum 3 written (sha256 04994437...), then final scoring started on the L40S. Cap changes only r1 and r2 best-of-N (h2 = 0.242, 0.293). precheck.py crashes without material_spec.json; r2 b2 got an empty spec to select the fallback, no code change. r2 single's thinnest walls are 1.5 voxels at h2 = 0.2 | Logged in addendum 3 |
| 07:13 | Judge agent's observation: void filling in the primary state makes all H_avg tiny and rewards less material; early state may show designs under load more honestly. Scoring as specified | Metric validity caveat to report with the results |

| ~07:15 | Addendum 3 reworded after scoring began: one added sentence (3 pre-checks on the laptop, 5 on Brev, same code); no number or rule changed. Hash moved from 04994437... (written before scoring) to 624bfe69... (final); the file records this | Both hashes must be disclosed |

| ~07:25 | Judge pool raised from $10 to $25 at the user's request, for margin. Second judge box allowed only if it saves at least about 30 min | Infrastructure only; no change to scoring |

| ~07:30 | Judge agent's estimate, from pre-check rates: one box 11:00, two boxes 09:35. Meets the user's 30-minute rule, so second L40S (judge_final2) added for queued best-of-N primary and datasheet jobs only | Infrastructure only; about $9 total either way |
| ~07:30 | User asked for an evaluation closer to the original goal. Separate agent designing a supplementary metric blind to results (addendum 4) | Official ranking stays frozen; supplementary metric is exploratory |

| ~07:35 | User ran flatten_for_panel.ps1 by hand, since the guard blocks the evaluator from copying out of submissions: sim\judge_final\subs holds nine runs, with r1 collective empty and two without a report | Matches the collection record |

| ~07:50 | Panel packets: 6 of 9 leak arm or replicate through the arms' own text, past the frozen redaction. User approved a second redaction pass on the packets only; P01 (no submission) excluded from the panel | Deviation, logged in panel\BLINDING_NOTE.md; blinding remains imperfect |

| 08:07 | Goal-matching metric frozen by an agent blind to results: addendum 4 (cec0693c...), code manifest b718e7e1.... Criterion loosened after the first known-answer run (under the original, a tie fails); test lattices tuned against the metric; band and extrapolation rule changed; integrity rule unchanged; without gates a sliver edges a solid block by 0.005 | Exploratory, reported beside the official ranking; does not replace it |

| ~08:30 | r2 best-of-N (b3), leading the official score so far, is a closed loop of 1 mm struts; its own report says "This design targets the metric, not a clinical device." Metric was disclosed to arms | Official ranking stays frozen; must be stated with the result |

| ~08:35 | Judge box 1: r2 planner primary killed by out-of-memory at 384 s (3 jobs, 40.6M unknowns at once), producing no result. r1 planner early stopped pre-emptively. Both requeued with identical arguments; remaining waves at or below 34M | No numbers or code changed; box 1 finish moves to about 10:20; total about $11-12 |

Other disclosures from the diagnosis: 0 memory errors in logged results but 70 large jobs vanished for unknown reasons, and silent kills can't be ruled out; memlog starts 04:06, missing the 03:44-04:06 peak; r2 single's overhead exemption was 0 vs 236,499 for r1 single (no outcome effect); quota overshoots up to 80,925 credits (r1 b2); r1 b1's billing label is unclear; the diagnosis agent ran read-only scripts from its scratchpad after two guard false positives.

Pending: judging; panel.
