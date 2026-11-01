# goal_metric: supplementary, exploratory, post-registered

Spec: `../EVAL_SPEC_v1_addendum4_goalmetric.md`. This does not replace the official ranking.

| file | role |
|---|---|
| `goal_metric.py` | Entry point. Takes one mesh or a folder and imports the frozen `sim/judge` read-only. |
| `make_kat.py` | Builds the synthetic known-answer shapes. Nothing from the contest. |
| `run_kat.py` | Runs the known-answer tests. |
| `check_exact.py` | Exact checks: a solid block returns its own material, bone-equivalent returns lambda = 1. |

```
# a folder of prepared judge folders (<run>/judge_jobs.json), or loose meshes with materials.json
python goal_metric.py --folder <dir> --out <dir_out> --workers 4 --threads 2
# the frozen coarse fallback, uniform for all submissions
python goal_metric.py --folder <dir> --out <dir_out> --workers 4 --threads 2 --fallback
```

`materials.json`: `{"<stem>": {"material": "tough1500"}, "_default": {"material": "rigid10k"}}`. Optional keys are `E`, `nu` and `strength`. A mesh with no entry and no `_default` is skipped and named in the output.

It finishes by writing `<dir_out>/goal_ranking.json`: the gated ranking, the unconditional ranking and the gates. A result already in `<dir_out>` is not recomputed, so a stopped run can resume.
