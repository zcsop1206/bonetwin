# Process metrics, bone-twin open run

Deterministic measurement, no ranking of arms and no scores. Machine-readable: `metrics.json` (per agent, per run, KB series, edges). Regenerate: `scripts/compute_metrics.py`, `scripts/write_reports.py`, `scripts/make_figures.py`. All times are local; every session ran after the 02:00 fall-back, so EST.

Harness code reused directly: `centralization.analyse`, `directives`, `process_metrics.kb_stats`, `billing.list_price`, `compute/ledger_costs.py`. Tool counts match the harness's own `metrics/process_metrics.json` for all 38 agents (mismatches: 0).

## 1. Key numbers per run

| run | agents | model processes | of which duplicate-runner | agent wall min (sum) | credits used | quota | list $ (tokens) | end states | posts | deg. central. | PreForm calls | PreForm endpoints ok | Brev starts | Brev $ | KB files | all deliverables at collection |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r1/single | 1 | 4 | 1 | 66.7 | 1,095,417 | 2,500,000 | 6.68 | 1 finished | - | - | 23 | 7 | 2 | 2.40 | 8 | yes |
| r1/best_of_n | 6 | 7 | 1 | 157.4 | 2,630,044 | 2,520,000 | 15.64 | 6 capped | - | - | 103 | 12 | 0 | 0.00 | 46 | yes |
| r1/collective | 6 | 17 | 5 | 194.3 | 2,545,559 | 2,520,000 | 15.47 | 6 capped | 31 | 0.30 | 30 | 14 | 0 | 0.00 | 67 | no |
| r1/planner | 6 | 19 | 6 | 224.9 | 2,599,699 | 2,520,000 | 16.71 | 6 capped | 36 | 1.00 | 89 | 14 | 0 | 0.00 | 27 | no |
| r2/single | 1 | 4 | 1 | 57.6 | 1,076,910 | 2,500,000 | 6.17 | 1 finished | - | - | 31 | 12 | 0 | 0.00 | 9 | yes |
| r2/best_of_n | 6 | 6 | 0 | 170.1 | 2,557,262 | 2,520,000 | 15.87 | 6 capped | - | - | 102 | 14 | 0 | 0.00 | 25 | yes |
| r2/collective | 6 | 6 | 0 | 137.8 | 2,554,394 | 2,520,000 | 15.82 | 6 capped | 22 | 0.40 | 34 | 12 | 1 | 0.64 | 24 | no |
| r2/planner | 6 | 9 | 0 | 334.6 | 2,328,338 | 2,520,000 | 17.93 | 1 window, 3 capped, 2 finished | 28 | 1.00 | 189 | 17 | 1 | 1.20 | 47 | yes |

Control (`control/gibson_ashby_rigid10k`): no agent sessions, so these metrics do not apply. Brev $0; manipulation check passes (`deterministic_rerun`, `no_model_calls`). 'All deliverables' is `metrics/submissions.json`, a completeness flag and not a score.

End states: capped = balance reached zero; finished = the agent ran `done`/final; window = the 90-minute wall cap closed first (`safety_cap`).

## 2. Credits and raw tokens by type

| run | input | cache creation | cache read | output | exempt credits | token credits | tool credits | credits used |
|---|---|---|---|---|---|---|---|---|
| r1/single | 194 | 272,866 | 9,805,860 | 68,870 | 236,499 | 1,086,017 | 9,400 | 1,095,417 |
| r1/best_of_n | 624 | 881,863 | 22,801,261 | 67,150 | 632,519 | 2,597,244 | 32,800 | 2,630,044 |
| r1/collective | 678 | 674,201 | 26,364,921 | 69,556 | 850,769 | 2,530,159 | 15,400 | 2,545,559 |
| r1/planner | 598 | 1,057,843 | 21,695,473 | 78,866 | 749,855 | 2,556,999 | 42,700 | 2,599,699 |
| r2/single | 144 | 438,833 | 5,782,434 | 54,690 | 0 | 1,071,910 | 5,000 | 1,076,910 |
| r2/best_of_n | 552 | 1,087,097 | 19,646,235 | 61,144 | 588,355 | 2,525,062 | 32,200 | 2,557,262 |
| r2/collective | 568 | 1,107,348 | 19,596,545 | 51,560 | 578,938 | 2,540,194 | 14,200 | 2,554,394 |
| r2/planner | 482 | 743,902 | 19,018,092 | 326,095 | 700,000 | 2,272,288 | 56,050 | 2,328,338 |

Credits = input + cache creation + 0.1 x cache read + output - exempt + tool charges (`meter.py`). Exempt = Claude Code first-turn overhead. r2 single's exemption is 0 against 236,499 for r1 single (already disclosed in RUN_LOG).

Balance reconciliation: quota + transfers in - transfers out - credits used equals `status.json` balance for every agent (see section 11).

## 3. Dollars and billing split

| run | subscription-labelled turns | subscription-labelled $ | API-labelled turns | API-labelled $ | $ from token totals |
|---|---|---|---|---|---|
| r1/single | 4 | 0.19 | 94 | 5.41 | 6.68 |
| r1/best_of_n | 306 | 14.52 | 0 | 0.00 | 15.64 |
| r1/collective | 13 | 0.70 | 327 | 13.87 | 15.47 |
| r1/planner | 19 | 0.94 | 286 | 14.85 | 16.71 |
| r2/single | 1 | 0.04 | 68 | 5.22 | 6.17 |
| r2/best_of_n | 269 | 14.83 | 0 | 0.00 | 15.87 |
| r2/collective | 281 | 14.97 | 0 | 0.00 | 15.82 |
| r2/planner | 232 | 12.22 | 0 | 0.00 | 17.93 |

Per-turn sums: subscription $58.41 (1125 turns), API $39.34 (775 turns). Harness API ledger (`run/api_spend.jsonl` + `run/api_live/`): closed $27.82 + live $26.83 = $54.65, cap $180.

Dollars are the harness's list-price estimate with per-Mtok prices fitted in `config.json` (`token_estimate.usd_per_mtok`), not an invoice. The gap between per-turn rows and the token-total column comes from the runner's output estimate (characters / 4 when larger than the logged count).

Inference: the closed ledger overcounts. For resumed sessions `total_cost_usd` appears cumulative (r2 s1 rows 1.79, 2.97, 3.72, 3.72, 4.45; r1 s1 4.69, 4.82), and summing them counts earlier turns again. The per-turn API figure is the safer one.

Unclear label: 11 best-of-N agents have subscription-labelled turns before the 04:40 reset (348 turns, $16.38). `apiKeySource` is `none` for those sampled (r1 b1, b2, r2 b1), and r2 b1 logged `allowed` rate-limit events with a new reset time, so the subscription seems to have accepted calls early. r1 b1 and b2 logged no rate-limit events, so that cannot be confirmed for them.

## 4. Boards

| run | posts | kinds | deg. central. (harness, all edge types) | reply edges only | harness + plain id mentions | betweenness max | top post share |
|---|---|---|---|---|---|---|---|
| r1/collective | 31 | chat 16, claim 1, evidence 14 | 0.30 | 0.20 | 0.10 | 0.25 (c4) | 0.29 (c2) |
| r1/planner | 36 | assign 15, chat 6, evidence 15 | 1.00 | 1.00 | 0.60 | 1.00 (p1) | 0.47 (p1) |
| r2/collective | 22 | chat 11, evidence 9, need 2 | 0.40 | 0.40 | 0.10 | 0.40 (c4) | 0.27 (c4) |
| r2/planner | 28 | assign 15, chat 1, evidence 9, need 1, transfer 2 | 1.00 | 0.60 | 0.50 | 1.00 (p1) | 0.54 (p1) |

The harness counts `@c3` mentions, not bare `c3` or `c1 -> c2`, which is how the collective boards usually address each other. The two extra columns show how much that matters: adding bare ids makes the graphs denser, so centralization falls. Bare ids can also be references rather than addresses.

| run | directive posts | per agent: count (share) | harness emergent leader | reply | mention | transfer | review | typed links | needs | answered | expired | credit transfers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r1/collective | 3 | c1 0 (0.00), c2 1 (0.33), c3 0 (0.00), c4 2 (0.67), c5 0 (0.00), c6 0 (0.00) | c4 | 1 | 13 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1/planner | 15 | p1 15 (1.00), p2 0 (0.00), p3 0 (0.00), p4 0 (0.00), p5 0 (0.00), p6 0 (0.00) | p1 | 16 | 38 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2/collective | 1 | c1 0 (0.00), c2 0 (0.00), c3 0 (0.00), c4 1 (1.00), c5 0 (0.00), c6 0 (0.00) | c4 | 6 | 3 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| r2/planner | 16 | p1 15 (0.94), p2 0 (0.00), p3 0 (0.00), p4 0 (0.00), p5 1 (0.06), p6 0 (0.00) | p1 | 9 | 49 | 2 | 0 | 0 | 1 | 0 | 0 | 2 |

Directive rule: directive = kind 'assign', or an @mention of another arm agent in a sentence that starts with an imperative verb (45 verbs) or contains one of ['can you', 'could you', 'please', 'you should', 'your task', 'you take', 'you handle', 'i need you', 'assign', "you're on", 'you are on', 'you own', 'would you'].

`emergent_leader` is the harness rule (share > 2 x mean, no minimum count), so r1 collective's c4 qualifies on 2 of 3 directive posts and r2 collective's c4 on 1 of 1. The live-intervention rule also requires at least 5 directive posts, and nobody met it.

Needs: 'answered' means a claim post with `pickup_of`, which no agent used, so the harness count is 0. No `expire` posts were written either. Informal follow-up:

- r2/collective p0016 (c2 to c5): next post by another agent addressing c2 is p0017 by c3.
- r2/collective p0017 (c3 to anyone): next post by another agent addressing c3 is none.
- r2/planner p0022 (p4 to p1): next post by another agent addressing p4 is none.
- r2/collective p0016 was addressed to c5; c5 did not reply on the board. c1 picked up the job in p0019 (read from the board).

Credit transfers: r2/planner p0021 p3 to p1 30,000; r2/planner p0026 p5 to p1 30,000.

## 5. Knowledge bases

| run | KB | files (final) | bytes (final) | cross-references (harness) | snapshots | files named in 2+ agents' tool calls |
|---|---|---|---|---|---|---|
| r1/single | per agent | 8 | 446,522 | 1 | 17 | - |
| r1/best_of_n | per agent | 46 | 3,263,080 | 21 | 17 | - |
| r1/collective | shared | 67 | 9,767,340 | 45 | 17 | 11 |
| r1/planner | shared | 27 | 659,613 | 36 | 17 | 13 |
| r2/single | per agent | 9 | 23,534 | 1 | 17 | - |
| r2/best_of_n | per agent | 25 | 1,277,322 | 2 | 17 | - |
| r2/collective | shared | 24 | 50,333 | 11 | 17 | 8 |
| r2/planner | shared | 47 | 1,260,634 | 41 | 17 | 16 |

Growth over time, snapshot sums (files / MB) from `metrics/kb_growth.jsonl`, nearest snapshot at or before each clock time. Full series in `metrics.json`.

| run | 03:45 | 04:00 | 04:15 | 04:30 | 04:45 | 05:00 | 05:15 | 05:30 | 05:45 | 06:00 | 06:27 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| r1/single | 1 / 0.43 | 1 / 0.43 | 1 / 0.43 | 2 / 0.43 | 8 / 0.45 | 8 / 0.45 | 8 / 0.45 | 8 / 0.45 | 8 / 0.45 | 8 / 0.45 | 8 / 0.45 |
| r1/best_of_n | 0 / 0.00 | 0 / 0.00 | 0 / 0.00 | 10 / 1.77 | 37 / 3.25 | 37 / 3.25 | 46 / 3.26 | 46 / 3.26 | 46 / 3.26 | 46 / 3.26 | 46 / 3.26 |
| r1/collective | 6 / 0.02 | 35 / 1.35 | 58 / 8.58 | 67 / 9.77 | 67 / 9.77 | 67 / 9.77 | 67 / 9.77 | 67 / 9.77 | 67 / 9.77 | 67 / 9.77 | 67 / 9.77 |
| r1/planner | 3 / 0.02 | 21 / 0.41 | 22 / 0.41 | 24 / 0.42 | 27 / 0.66 | 27 / 0.66 | 27 / 0.66 | 27 / 0.66 | 27 / 0.66 | 27 / 0.66 | 27 / 0.66 |
| r2/single | 0 / 0.00 | 6 / 0.02 | 7 / 0.02 | 8 / 0.02 | 9 / 0.02 | 9 / 0.02 | 9 / 0.02 | 9 / 0.02 | 9 / 0.02 | 9 / 0.02 | 9 / 0.02 |
| r2/best_of_n | 0 / 0.00 | 0 / 0.00 | 0 / 0.00 | 1 / 0.01 | 9 / 0.08 | 19 / 0.49 | 22 / 0.66 | 25 / 1.28 | 25 / 1.28 | 25 / 1.28 | 25 / 1.28 |
| r2/collective | 0 / 0.00 | 0 / 0.00 | 0 / 0.00 | 0 / 0.00 | 5 / 0.01 | 10 / 0.02 | 21 / 0.04 | 24 / 0.05 | 24 / 0.05 | 24 / 0.05 | 24 / 0.05 |
| r2/planner | 0 / 0.00 | 0 / 0.00 | 0 / 0.00 | 0 / 0.00 | 0 / 0.00 | 0 / 0.00 | 1 / 0.00 | 12 / 0.12 | 33 / 0.95 | 43 / 1.24 | 47 / 1.26 |

Cross-agent lineage: `artifacts.jsonl` does not exist in this run (agents did not use the gateway's design-artifact path), so the harness lineage measures (DAG depth, syntheses, cross-agent derivations) are all zero by absence, not by measurement. Proxy from board citations (parents, `pNNNN` mentions):

| run | longest citation chain | cross-agent citation edges | posts citing 2+ other agents |
|---|---|---|---|
| r1/collective | 2 | 7 | 0 |
| r1/planner | 1 | 16 | 0 |
| r2/collective | 2 | 8 | 1 |
| r2/planner | 2 | 10 | 0 |

## 6. Tool calls

Claude-level = calls the meter hook allowed (allowed does not mean succeeded). Proxied = calls logged by `bt_tool.py`, usually launched from a Bash call, so the two levels overlap and must not be added. Per-agent breakdown is in section 11 and `metrics.json` under `agents.<id>.tool_calls`.

| run | Claude-level allowed | proxied | refused | held for notice |
|---|---|---|---|---|
| r1/single | Bash 73, WebFetch 8, WebSearch 5, ToolSearch 1, PowerShell 1, Grep 1, Read 1, Write 1, Edit 1 | compute 38, preform_api 23, cad_python 3 | 7 | 1 |
| r1/best_of_n | Bash 245, WebSearch 14, WebFetch 13, Write 10, ToolSearch 8, Read 4, PowerShell 3, TaskStop 3, Monitor 2, Edit 1 | preform_api 103, cad_python 5 | 16 | 4 |
| r1/collective | Bash 294, Write 13, WebSearch 8, ToolSearch 6, Edit 6, TaskStop 4, WebFetch 4, PowerShell 2 | preform_api 30, cad_python 18 | 23 | 0 |
| r1/planner | Bash 233, WebFetch 33, WebSearch 29, Write 11, ToolSearch 4, TaskStop 2, Read 1, PowerShell 1, Edit 1 | preform_api 89, cad_python 8 | 28 | 1 |
| r2/single | Bash 53, Monitor 3, ToolSearch 2, WebFetch 1, TaskStop 1, Write 1 | preform_api 31, cad_python 8 | 6 | 0 |
| r2/best_of_n | Bash 199, Write 15, WebSearch 14, WebFetch 14, ToolSearch 8, Read 6, TaskStop 5, PowerShell 3, Monitor 3, Grep 1 | preform_api 102, cad_python 12, warp_gpu 3, openresearch 2 | 26 | 7 |
| r2/collective | Bash 224, WebSearch 6, WebFetch 6, Write 4, ToolSearch 3, PowerShell 3, TaskStop 2, Edit 2, Read 1 | preform_api 34, compute 21, cad_python 6, openresearch 2, warp_gpu 1 | 29 | 12 |
| r2/planner | Bash 184, WebFetch 54, Write 18, WebSearch 16, Read 3, ToolSearch 3, Edit 2, TaskStop 1 | preform_api 189, compute 41, cad_python 19, warp_gpu 10 | 35 | 8 |

## 7. PreForm API

`preform_api` rows; ids and query strings normalized out of endpoints.

| run | calls | ok | errors | distinct endpoints attempted | distinct endpoints ok |
|---|---|---|---|---|---|
| r1/single | 23 | 14 | 9 | 8 | 7 |
| r1/best_of_n | 103 | 66 | 37 | 18 | 12 |
| r1/collective | 30 | 19 | 11 | 18 | 14 |
| r1/planner | 89 | 67 | 22 | 19 | 14 |
| r2/single | 31 | 25 | 6 | 14 | 12 |
| r2/best_of_n | 102 | 56 | 46 | 26 | 14 |
| r2/collective | 34 | 23 | 11 | 16 | 12 |
| r2/planner | 189 | 151 | 38 | 32 | 17 |

Widest use by agent: r2/planner/p4 17 endpoints ok of 189 calls; r1/collective/c1 14 endpoints ok of 30 calls; r1/planner/p5 14 endpoints ok of 64 calls; r2/best_of_n/b5 14 endpoints ok of 29 calls; r2/single/s1 12 endpoints ok of 31 calls; r2/best_of_n/b4 12 endpoints ok of 26 calls.

## 8. Brev (cost fields from `compute/ledger_costs.py` only)

| ledger run | $ | instances | starts | types |
|---|---|---|---|---|
| collective-r2 | 0.644 | 1 | 1 | L40S |
| imgtest | 0.649 | 2 | 2 | A6000 |
| judge-brevtest | 0.585 | 2 | 1 | L40S |
| judge-final | 1.524 | 1 | 1 | L40S |
| judge-final2 | 2.433 | 1 | 1 | L40S |
| judge-ngc | 0.935 | 1 | 1 | L40S |
| judge-stack | 0.094 | 1 | 1 | L40S |
| planner-r2 | 1.203 | 1 | 1 | L40S |
| single-r1 | 2.396 | 2 | 2 | L40S |

Ledger total $10.46, of which arms $4.24; the rest is image tests and judge setup. Arms absent from the ledger made no starts. The ledger reports by run; which agent started what comes from tool logs:

- r1/single/s1: 03:40 exit 1, 03:41 ok, 04:06 ok
- r2/collective/c2: 04:52 exit 1, 04:52 exit 1
- r2/collective/c5: 04:50 exit 1, 04:51 ok
- r2/planner/p2: 05:11 exit 1, 05:12 ok

## 9. NVIDIA tool use by agent

'ran' = a `warp_gpu` call returned ok, or Warp code was executed on Brev. Only agents with some signal are listed.

| agent | Warp | warp_gpu ok | warp_gpu unavailable (heavy queue / RAM) | Brev exec with Warp ok |
|---|---|---|---|---|
| r1/best_of_n/b5 | mention only | 0 | 0 | 0 |
| r1/best_of_n/b6 | mention only | 0 | 0 | 0 |
| r1/collective/c5 | mention only | 0 | 0 | 0 |
| r1/planner/p5 | mention only | 0 | 0 | 0 |
| r2/best_of_n/b5 | mention only | 0 | 0 | 0 |
| r2/best_of_n/b6 | ran | 2 | 1 | 0 |
| r2/collective/c2 | mention only | 0 | 0 | 0 |
| r2/collective/c5 | attempted, did not run | 0 | 1 | 0 |
| r2/planner/p1 | mention only | 0 | 0 | 0 |
| r2/planner/p2 | ran | 1 | 1 | 7 |
| r2/planner/p5 | ran | 2 | 6 | 0 |

Across all 38 agents' tool inputs, assistant text and own scripts: warp.fem 0, PhysicsNeMo 0, BioNeMo 0, ALCHEMI 0, NGC 0 hits. `compute_images.md` was named in 20 tool inputs. The Warp solvers are the agents' own matrix-free hex8 kernels, not `warp.fem`, even where a board post says 'Warp FEM'.

Sponsor-tool calls before and after the first notice (04:46:41), per run:

| run | PreForm before | PreForm after | warp_gpu before | warp_gpu after | compute before | compute after |
|---|---|---|---|---|---|---|
| r1/single | 23 | 0 | 0 | 0 | 38 | 0 |
| r1/best_of_n | 79 | 24 | 0 | 0 | 0 | 0 |
| r1/collective | 30 | 0 | 0 | 0 | 0 | 0 |
| r1/planner | 89 | 0 | 0 | 0 | 0 | 0 |
| r2/single | 31 | 0 | 0 | 0 | 0 | 0 |
| r2/best_of_n | 54 | 48 | 0 | 3 | 0 | 0 |
| r2/collective | 21 | 13 | 1 | 0 | 0 | 21 |
| r2/planner | 0 | 189 | 0 | 10 | 0 | 41 |

Notice delivery: 11 delivered, 7 shown at start (not yet started), 20 missed. So who saw it is confounded with replicate and start time, and before/after is not a clean comparison.

## 10. Leanings against actual use

Only the `tools` axis has a pre-registered mapping (`config.json` `affinity_tool_map`). Other axes are analyst-defined proxies, not pre-registered, included because the rate was requested. Singles are 'generalist' and excluded.

- tools, top family: the leaning is the agent's most-used family, excluding 'other'.
- tools, lift > 1: the family's share of the agent's calls exceeds its share across all agents (harness definition).
- knowledge proxy: leaning mapped to a family (FEA, ML to NVIDIA simulation; additive manufacturing to PreForm; biology, chemistry, clinical to literature), lift > 1.
- working style proxy: explorer or exploiter = tool entropy above or below the median; builder = CAD/PreForm/Write share at or above the median; verifier = PreForm validation share at or above the median. Base rate about 0.5.
- communication proxy (board arms): broadcaster = posts above arm mean; listener = below; connector = betweenness above arm mean. 'challenger' is not measured (it would need text classification).

| run | tools, top family | tools, lift > 1 | knowledge proxy | working style proxy | communication proxy |
|---|---|---|---|---|---|
| r1/single | n/a | n/a | n/a | n/a | n/a |
| r1/best_of_n | 3/6 (0.50) | 5/6 (0.83) | 3/6 (0.50) | 5/6 (0.83) | n/a |
| r1/collective | 4/6 (0.67) | 2/6 (0.33) | 1/6 (0.17) | 2/6 (0.33) | 2/6 (0.33) |
| r1/planner | 2/6 (0.33) | 2/6 (0.33) | 0/6 (0.00) | 2/6 (0.33) | 3/6 (0.50) |
| r2/single | n/a | n/a | n/a | n/a | n/a |
| r2/best_of_n | 1/6 (0.17) | 3/6 (0.50) | 0/6 (0.00) | 4/6 (0.67) | n/a |
| r2/collective | 4/6 (0.67) | 6/6 (1.00) | 4/6 (0.67) | 4/6 (0.67) | 3/5 (0.60) |
| r2/planner | 0/6 (0.00) | 2/6 (0.33) | 3/6 (0.50) | 2/6 (0.33) | 3/5 (0.60) |
| ALL | 14/36 (0.39) | 20/36 (0.56) | 11/36 (0.31) | 19/36 (0.53) | 11/22 (0.50) |

## 11. Per agent

| agent | start | end | wall min | state | credits | balance | cache-read credit share | list $ | Claude-level calls | proxied calls | refused | PreForm calls | PreForm endpoints ok | tools leaning |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r1/single/s1 | 03:32 | 04:39 | 66.7 | finished | 1,095,417 | 1,404,583 | 0.74 | 5.59 | 92 | 64 | 7 | 23 | 7 | generalist |
| r1/best_of_n/b1 | 03:47 | 04:15 | 27.1 | capped | 427,165 | -7,165 | 0.63 | 2.44 | 44 | 16 | 1 | 14 | 8 | PreForm API |
| r1/best_of_n/b2 | 04:11 | 04:44 | 33.6 | capped | 500,925 | -80,925 | 0.66 | 2.84 | 53 | 28 | 4 | 27 | 11 | data analysis |
| r1/best_of_n/b3 | 04:11 | 04:34 | 23.4 | capped | 430,652 | -10,652 | 0.78 | 2.25 | 56 | 15 | 3 | 15 | 8 | data analysis |
| r1/best_of_n/b4 | 04:12 | 04:36 | 24.4 | capped | 429,164 | -9,164 | 0.78 | 2.24 | 61 | 23 | 2 | 23 | 7 | literature |
| r1/best_of_n/b5 | 04:36 | 04:57 | 21.0 | capped | 421,773 | -1,773 | 0.66 | 2.39 | 46 | 13 | 2 | 12 | 5 | NVIDIA simulation |
| r1/best_of_n/b6 | 04:39 | 05:07 | 27.9 | capped | 420,365 | -365 | 0.69 | 2.36 | 43 | 13 | 4 | 12 | 5 | data analysis |
| r1/collective/c1 | 03:32 | 03:47 | 15.1 | capped | 425,956 | -5,956 | 0.78 | 2.39 | 52 | 31 | 4 | 30 | 14 | PreForm API |
| r1/collective/c2 | 03:32 | 04:16 | 44.3 | capped | 426,710 | -6,710 | 0.80 | 2.45 | 59 | 6 | 2 | 0 | 0 | data analysis |
| r1/collective/c3 | 03:32 | 04:00 | 27.8 | capped | 422,928 | -2,928 | 0.76 | 2.48 | 59 | 8 | 8 | 0 | 0 | data analysis |
| r1/collective/c4 | 03:32 | 04:11 | 38.8 | capped | 421,004 | -1,004 | 0.78 | 2.39 | 56 | 1 | 2 | 0 | 0 | literature |
| r1/collective/c5 | 03:32 | 04:01 | 28.9 | capped | 420,205 | -205 | 0.77 | 2.42 | 51 | 1 | 5 | 0 | 0 | NVIDIA simulation |
| r1/collective/c6 | 03:32 | 04:11 | 39.4 | capped | 428,756 | -8,756 | 0.78 | 2.44 | 60 | 1 | 2 | 0 | 0 | data analysis |
| r1/planner/p1 | 03:32 | 03:50 | 18.3 | capped | 423,441 | -3,441 | 0.75 | 2.47 | 48 | 26 | 4 | 25 | 8 | PreForm API |
| r1/planner/p2 | 03:32 | 03:58 | 26.1 | capped | 424,365 | -4,365 | 0.77 | 2.35 | 67 | 0 | 3 | 0 | 0 | data analysis |
| r1/planner/p3 | 03:32 | 04:28 | 55.9 | capped | 428,635 | -8,635 | 0.78 | 2.46 | 59 | 1 | 5 | 0 | 0 | data analysis |
| r1/planner/p4 | 03:32 | 04:35 | 62.6 | capped | 423,332 | -3,332 | 0.38 | 2.97 | 33 | 6 | 6 | 0 | 0 | literature |
| r1/planner/p5 | 03:32 | 04:06 | 33.9 | capped | 422,535 | -2,535 | 0.65 | 2.64 | 50 | 64 | 5 | 64 | 14 | NVIDIA simulation |
| r1/planner/p6 | 03:32 | 04:00 | 28.1 | capped | 477,391 | -57,391 | 0.53 | 2.91 | 58 | 0 | 5 | 0 | 0 | data analysis |
| r2/single/s1 | 03:32 | 04:30 | 57.6 | finished | 1,076,910 | 1,423,090 | 0.54 | 5.27 | 61 | 39 | 6 | 31 | 12 | generalist |
| r2/best_of_n/b1 | 04:11 | 04:51 | 40.5 | capped | 423,492 | -3,492 | 0.32 | 2.85 | 24 | 8 | 4 | 1 | 1 | PreForm API |
| r2/best_of_n/b2 | 04:11 | 04:35 | 24.3 | capped | 426,610 | -6,610 | 0.70 | 2.36 | 52 | 29 | 3 | 28 | 5 | data analysis |
| r2/best_of_n/b3 | 04:12 | 04:38 | 26.3 | capped | 422,090 | -2,090 | 0.65 | 2.44 | 47 | 19 | 4 | 18 | 7 | data analysis |
| r2/best_of_n/b4 | 04:35 | 04:52 | 17.0 | capped | 426,115 | -6,115 | 0.67 | 2.41 | 42 | 29 | 3 | 26 | 12 | literature |
| r2/best_of_n/b5 | 04:38 | 04:56 | 17.7 | capped | 430,965 | -10,965 | 0.69 | 2.40 | 46 | 30 | 5 | 29 | 14 | NVIDIA simulation |
| r2/best_of_n/b6 | 04:57 | 05:41 | 44.3 | capped | 427,990 | -7,990 | 0.69 | 2.37 | 57 | 4 | 7 | 0 | 0 | geometry / CAD |
| r2/collective/c1 | 04:35 | 04:55 | 19.2 | capped | 425,532 | -5,532 | 0.62 | 2.50 | 44 | 21 | 3 | 21 | 7 | PreForm API |
| r2/collective/c2 | 04:35 | 04:55 | 20.0 | capped | 425,557 | -5,557 | 0.64 | 2.48 | 41 | 8 | 7 | 0 | 0 | data analysis |
| r2/collective/c3 | 04:35 | 05:04 | 28.3 | capped | 425,713 | -5,713 | 0.65 | 2.44 | 45 | 1 | 5 | 0 | 0 | data analysis |
| r2/collective/c4 | 04:35 | 04:55 | 19.3 | capped | 428,634 | -8,634 | 0.59 | 2.54 | 40 | 15 | 6 | 13 | 9 | literature |
| r2/collective/c5 | 04:35 | 04:57 | 21.6 | capped | 423,742 | -3,742 | 0.61 | 2.51 | 37 | 17 | 4 | 0 | 0 | NVIDIA simulation |
| r2/collective/c6 | 04:35 | 05:05 | 29.4 | capped | 425,216 | -5,216 | 0.65 | 2.49 | 44 | 2 | 4 | 0 | 0 | geometry / CAD |
| r2/planner/p1 | 04:57 | 06:27 | 90.0 | window | 317,018 | 162,982 | 0.68 | 1.89 | 35 | 0 | 5 | 0 | 0 | PreForm API |
| r2/planner/p2 | 04:57 | 05:47 | 50.4 | capped | 421,100 | -1,100 | 0.62 | 2.13 | 35 | 43 | 8 | 0 | 0 | data analysis |
| r2/planner/p3 | 04:57 | 05:48 | 51.7 | capped | 400,882 | -10,882 | 0.61 | 2.04 | 66 | 10 | 4 | 0 | 0 | data analysis |
| r2/planner/p4 | 04:57 | 05:48 | 51.9 | capped | 469,598 | -49,598 | 0.62 | 2.41 | 48 | 197 | 6 | 189 | 17 | literature |
| r2/planner/p5 | 04:57 | 06:13 | 76.1 | finished | 389,774 | 226 | 0.63 | 1.98 | 32 | 8 | 8 | 0 | 0 | NVIDIA simulation |
| r2/planner/p6 | 04:57 | 05:11 | 14.5 | finished | 329,966 | 90,034 | 0.61 | 1.77 | 65 | 1 | 4 | 0 | 0 | geometry / CAD |

Balance reconciliation failures (more than 2 credits): none. Largest quota overshoots: r1/best_of_n/b2 80,925, r1/planner/p6 57,391, r2/planner/p4 49,598.

## 12. Manipulation checks

From the scheduler's own run of `manipulation.py` at 2026-11-01T11:27:15+00:00 (06:27 EST), after all sessions ended. Not re-executed here: `check_arm` writes into `run/` and `metrics/`. These are the harness's stored results.

| arm/run | harness verdict | pass apart from no_human_posts | failed | passed |
|---|---|---|---|---|
| control/gibson_ashby_rigid10k | PASS | yes | - | deterministic_rerun, no_model_calls |
| single/r1 | FAIL | no | one_model_session, no_human_posts, model_pinned | subagents_disabled, no_task_tool_use, no_cross_arm_reference, same_model, same_tools, same_data, signed_scores, fs_breaches |
| best_of_n/r1 | FAIL | no | no_human_posts, fs_breaches | no_cross_reference, no_board_traffic, web_no_cross_agent_channel, same_model, same_tools, same_data, signed_scores, model_pinned |
| collective/r1 | FAIL | no | no_human_posts, model_pinned | identical_briefs, same_model, same_tools, same_data, signed_scores, fs_breaches |
| planner/r1 | FAIL | no | no_human_posts, fs_breaches, model_pinned | star_graph, deliverables_written_by_lead_only, same_model, same_tools, same_data, signed_scores |
| single/r2 | FAIL | no | one_model_session, no_human_posts, model_pinned | subagents_disabled, no_task_tool_use, no_cross_arm_reference, same_model, same_tools, same_data, signed_scores, fs_breaches |
| best_of_n/r2 | FAIL | yes | no_human_posts | no_cross_reference, no_board_traffic, web_no_cross_agent_channel, same_model, same_tools, same_data, signed_scores, fs_breaches, model_pinned |
| collective/r2 | FAIL | yes | no_human_posts | identical_briefs, same_model, same_tools, same_data, signed_scores, fs_breaches, model_pinned |
| planner/r2 | FAIL | yes | no_human_posts | star_graph, deliverables_written_by_lead_only, same_model, same_tools, same_data, signed_scores, fs_breaches, model_pinned |

Reasons:

- `no_human_posts`: by design: `run/HUMAN_POSTS.log` holds the two 04:47 and 04:51 notices. No human post appears on any board.
- `model_pinned`: `<synthetic>` rows only, logged at the 03:32 to 03:33 usage-limit block. The real model was claude-opus-5-5 throughout. Inference: a Claude Code limit message, not a model switch.
- `one_model_session`: 4 processes, one session id, overlap true. The overlap is the 03:50 duplicate runner (metrics/incident_0350.json).
- `fs_breaches`: 1 hit, the agent's own folder path cut off by the meter's 600-character command limit (row length 600). Inference: false positive.

fs_breaches rows checked: r1/best_of_n/b4 09:20:46Z, command length 600, tail `/run/r1/best`; r1/planner/p1 08:44:08Z, command length 600, tail `/run/r1/planner/agent`.

Global checks: interleaved_order = True; harness_unchanged_since_launch = False; brief_hashes_logged = True; rules_frozen = False; health_check = True; launcher_exit_logged = True; tools_registry = True. `harness_unchanged_since_launch` is false because `config.json`, `manipulation.py` and `scheduler.py` were changed after launch; `rules_frozen` is false because `config.json` and `scheduler.py` no longer match their launch hashes in `run/rules_manifest.json`; the other 10 rule files match.

## 13. Not measured or only partly measured

- Lineage (DAG depth, syntheses, derivations): no `artifacts.jsonl` in this run. Board citation proxy only.
- Typed links (cites, contradicts, extends, replicates): 0 on every board. The field exists and no agent used it, so these are true zeros, not a gap.
- Needs answered: 0 by rule because no claim used `pickup_of`. Informal answers are listed individually, not counted.
- Memory before 04:06: `memlog.jsonl` starts at 04:06, so the 03:44 to 04:04 commit peak exists only as RUN_LOG text. `scheduler.jsonl` free RAM covers that period.
- Memory-governor kills: `metrics/memgov.jsonl` does not exist. 73 Python processes of 1 GB or more disappeared per `memlog.jsonl`; why they ended is unknown, and 0 Windows low-memory events are in the file because that step runs at 08:35 and the log I read ends at 07:14.
- True billing source for best-of-N turns before 04:40: only the label is known for r1 b1 and b2 (section 3). API ledger total is an estimate and probably overcounts.
- Tool success for Claude-level calls: the hook logs before execution, so success is only known for proxied tools.
- Duplicate-runner share of tokens: original and duplicate runners write the same transcript and status, so usage cannot be split per runner in the 03:50 window.
- Credit curves are reconstructed from per-message usage and tool charges, then scaled to the runner's total. Scale is within 5% of 1 for most agents and 1.12 to 1.19 for r2 planner; inference: the runner's character-based output estimate exceeded logged output there. Totals are exact as logged; curve shape is approximate.
- Leaning agreement on knowledge, working style and communication: analyst proxies only. 'challenger' not measured.
- Control: not applicable. Final scores: excluded by instruction.
- Live files: `compute/memlog.jsonl` and `compute/compute_ledger.jsonl` were still being appended during this analysis (judge jobs), so judge-related Brev lines can grow on a rerun. Arm lines are final.
