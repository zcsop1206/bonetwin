# Compute fair share, for the harness

(Hackathon record. `images.md`, `imgtest/` and `run_reaper.cmd` named below are not in this repo. Dollar figures are that night's.)

Agents reach GPUs only through `bt_compute.py`. The harness blocks direct
`brev` and `wsl brev` calls, and should also block `wsl` with `--exec`/`-e`
pointing at brev, and any edit to `caps.json` or `compute_ledger.jsonl`.

## What every run gets

| Run id | Arm | Replicate | Cap ($) | Max live instances |
|---|---|---|---|---|
| control-r1, control-r2 | control | 1, 2 | 0 (no compute) | 0 |
| single-r1, single-r2 | single | 1, 2 | 17.50 each | 1 |
| bestofn-r1, bestofn-r2 | best_of_n | 1, 2 | 17.50 each | 1 |
| collective-r1, collective-r2 | collective | 1, 2 | 17.50 each | 1 |
| planner-r1, planner-r2 | planner | 1, 2 | 17.50 each | 1 |
| imgtest | (setup test, not an arm) | | 1.00 | 1 |
| judge_<word> (e.g. judge_final, judge_bon1) | judge | any | **10.00 shared by all judge_* runs**, outside the arms' caps | 1 per judge run |

$150 credit − $10 reserve = $140 = 8 × $17.50. The judge pool ($10) is
separate from the arms, so arms + judge can reach the full $150: the reserve
is now only what the pool leaves unused (and the ~$0.39 setup test).
Pool caveat: each judge start is checked against the pool's spend so far, not
against other judge runs' planned hours; the reaper deletes every judge
instance once the pool reaches $10. Same types for every arm:
A6000, A100, L40S (no H100). What $17.50 buys at the live prices:
A6000 $0.68/h (massedcompute, now tried first) → 25 h, more than the 7.4 h night; L40S $1.06/h → 16.6 h;
A100 $1.66/h → 10.6 h. In practice no run can exhaust its cap on an A6000
before the 07:15 curfew, so the cap only binds on A100/L40S.

## Fairness rules the code enforces

- Each agent process gets `BT_RUN=<run id>` in its environment. With it set,
  every command is locked to that run: names from other runs are refused, and
  `--arm/--run` that disagree with `BT_RUN` are refused. Without it, the agent
  must pass `--arm` and `--run`. **Set `BT_RUN` per agent**; that is the
  isolation boundary.
- Cost is rate × wall time from the ledger start record to the delete. `start`
  refuses when spent + (worst rate in the type's fallback chain × `--hours`,
  clipped to the hours left before 07:15) exceeds the cap.
- The reaper deletes an instance one pass before its run reaches the cap, after
  15 idle minutes (GPU < 5 % and no exec/copy), 25 min after start if it never
  booted, and everything at 07:15. It never touches names without a
  `bt-<run id>-` prefix.
- `stop` **deletes** (these rentals are not stoppable). Copy results off first.
- Boot is billed. Tonight Crusoe L40S was shell-ready in 72 s; two Shadeform A6000s never gave SSH (20 and 11 min). Prefer L40S. See images.md.

## Tool registry strings

Working directory `<repo>\compute`,
environment `PYTHONIOENCODING=utf-8` and `BT_RUN=<run id>`. `{...}` are agent arguments.

```
gpu_quote:     python bt_compute.py quote
gpu_start:     python bt_compute.py start --type {L40S|A100|A6000} --name {name} --hours {planned_hours} --wait
gpu_wait:      python bt_compute.py wait --name {name} --max-min 20
gpu_exec:      python bt_compute.py exec --name {name} --timeout {seconds} -- {shell command}
gpu_exec_file: python bt_compute.py exec --name {name} --timeout {seconds} -- @{C:\local\script.sh}
gpu_copy_to:   python bt_compute.py copy-to --name {name} {C:\local\path} {/remote/path}
gpu_copy_from: python bt_compute.py copy-from --name {name} {/remote/path} {C:\local\path}
gpu_stop:      python bt_compute.py stop --name {name}
gpu_ls:        python bt_compute.py ls
```

Set `MSYS_NO_PATHCONV=1` when these run from Git Bash, or `/remote/path` gets rewritten.

## ALCHEMI for agents

Run the BGR NIM on the instance with `imgtest/nim_bgr.sh`: image
`nvcr.io/nim/nvidia/alchemi-bgr:1.0.0` (not 1.1.0, which fails on the driver these
instances ship), port 8000, ready check `curl localhost:8000/v1/health/ready` (200 after about
3 min), inference `POST localhost:8000/v1/infer` called from an `exec` on the instance.
Allow about 3 min to pull plus 3 min to load, billed. Request shape and limits are at the top
of images.md: a full relaxation has not been run yet, and `cell` and `pbc` are required. No
key is needed for this image. `NGC_API_KEY` is set for `exec` once a key path is configured;
`@script` commands get it too.

For judges set `BT_RUN=judge_<word>` (letters/digits, e.g. `judge_final`); the
instance becomes `bt-judge-<word>-<name>`.
With `BT_RUN` unset, add `--arm {single|best_of_n|collective|planner|judge} --run {1|2|<word>}`
after the subcommand. `{name}` is a short name (`sim`) or the full
`bt-<run id>-sim`. `exec` returns the remote exit code and prints its
stdout/stderr; a long job should be launched with `nohup ... &` and polled,
since an exec counts as activity only until its `--timeout`.

## Running the reaper

```
python reaper.py
```

Wrap `reaper.py` in a restart loop if it must survive crashes; the reaper rebuilds its
state from the ledger, so a restart or a laptop reboot loses nothing (start it
again after a reboot). Heartbeat: `reaper_heartbeat.json`; log: `reaper.log`.
`python reaper.py --dry-run` shows what it would delete now.
