# Frozen files changed for the public copy

Three frozen files differ from the hackathon originals in this copy. Each change removes either a personal path or PreForm API detail that may not be publishable. No number, rule or scoring logic changed. The originals are kept privately, unchanged, with their recorded hashes.

| file | original sha256 | public sha256 | what changed |
|---|---|---|---|
| `sim/judge/judge_intake.py` | `17af2577ecf6ff458b661fa5636311fdfe276af9a05a36be841c4d479bd35025` | `486445562548d6dea6d9a51fe9e842fbfd8a662d76d6f992eeaf282e0b7c422b` | PreForm calls go through `preform_tool.py`'s adapter functions instead of raw endpoint paths and request bodies; the server start command moved into the adapter. Same checks, same order, same acceptance rule. |
| `sim/EVAL_SPEC_v1.md` | `3f4c44f720d4551616ad57a67ee360eaa1794b1d6ef4da79fcdb54975a3e3c62` | `4d2c6b9fc17619a7f4efd48af90221dc76b01be5c316d191f2014648e83bdfe2` | §1: local address, server start command and two endpoint paths replaced by `[REDACTED: ...]`. |
| `targets/SOURCES.md` | `42be364f35e83df2e4ded63887e4c3c5a58acede2ca4a9dbd8b71cf6129d0584` | `26ac970be14a1f07a4772fe524c7f772a8627049b428aaf2f6145d0a6fa322f3` | Line 55: a personal local path replaced by `[REDACTED: local path]`. |

Consequence: `sim/judge/JUDGE_MANIFEST.sha256` still lists the original hash for `judge_intake.py`, so `sha256sum -c` reports that one file as FAILED in this copy. All other judge files verify. See `ISSUES/fix-hashes.md`.

## Not changed, flagged

- `sim/EVAL_SPEC_v1.md` line 138 names Alan, the teammate whose print and video tracking it cites. Kept as attribution.
- `sim/judge/BREV_BATCH.md` line 11 uses `/home/ubuntu`, the generic cloud user. Not personal.
- Frozen judge files and spec addenda still use scene and model field names (`canonical_model_hash`, `original_file`, `scene_settings`, `material_code`, `bounding_box`). In this copy these are the adapter contract's own schema (see `preform_tool.py`). Whether they match PreForm's own names was not checked against any PreForm document; the owner should confirm they are fine to publish.

## Non-frozen PreForm redactions

`preform_tool.py` is a new mock adapter with no PreForm endpoints. `harness_open/control_build.py`, `tools/bt_tool.py`, `launch_open_run.py`, `health.py`, `agent_runner.py` (mock path), `smoke_test.py`, `briefs.py`, `tools.json`, `config.template.json` and `analysis_process/scripts/compute_metrics.py` now use adapter operation names (`create_scene`, `import_model`, `save_form`, ...) in place of endpoint paths, request bodies and the server's port.
