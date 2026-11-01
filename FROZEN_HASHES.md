# Frozen files and hashes

These files are byte-identical to the hackathon originals. Do not edit them: each SHA-256 below is what the run recorded or what the spec's addenda rely on. `.gitattributes` turns off line-ending conversion to keep it that way.

`sim/judge/JUDGE_MANIFEST.sha256` (paths relative to `sim/`) and `sim/goal_metric/GOAL_MANIFEST.sha256` verify with `sha256sum -c` from those folders.

| file | sha256 | frozen by |
|---|---|---|
| `sim/judge/judge.py` | `7bab7c9aac992477ae06f51d16bd0447848b15414794388174fc6216fb6cd13b` | JUDGE_MANIFEST.sha256 |
| `sim/judge/judge_batch.py` | `8c6598762f04553134a1f6bd3d66579c93460fbf3797768e0ca8a6d903eb383c` | JUDGE_MANIFEST.sha256 |
| `sim/judge/judge_fe.py` | `d04801d1a3f2964a82fb2830e980df8dba48475654a2278575f558ad8ea73ac3` | JUDGE_MANIFEST.sha256 |
| `sim/judge/judge_geom.py` | `92c35e16d8f5c37d8cbc540df8e25a4b735722d02849a13b9556f6edd5372d60` | JUDGE_MANIFEST.sha256 |
| `sim/judge/judge_intake.py` | `17af2577ecf6ff458b661fa5636311fdfe276af9a05a36be841c4d479bd35025` | JUDGE_MANIFEST.sha256 |
| `sim/judge/judge_rank.py` | `1010cca4d38b6abe3f7179e8cf2366220496084a0150d07f564fff23b71cd42c` | JUDGE_MANIFEST.sha256 |
| `sim/judge/judge_submission.py` | `8f8ef78a9b76f7e393457cfe80cc200512f414048b0cabf457fc8fb2fbce3788` | JUDGE_MANIFEST.sha256 |
| `sim/judge/panel_prepare.py` | `8888644fc22c288d5427a52736c6b2f3bc5bc722151942c19245eea459853ceb` | JUDGE_MANIFEST.sha256 |
| `sim/judge/precheck.py` | `0b978bcb8bdfa1490f0bfe1c718af57b3022aed47660a65c72fb1659c1666bc7` | JUDGE_MANIFEST.sha256 |
| `sim/judge/reference_materials.json` | `998163be05c188c3e515ceb417e6fa38aae44fc8ffd733134c86e36a163e4dce` | JUDGE_MANIFEST.sha256 |
| `sim/judge/BREV_BATCH.md` | `693655b7e642692bf0e0b77eb505d1ad89d7d639b9b89412edd7f7a8489836ad` | JUDGE_MANIFEST.sha256 |
| `sim/judge/JUDGE_MANIFEST.sha256` | `8d1cc6b9a6a84f3f8596f8f2c436bfc128f57900266f392410c858131035efac` | JUDGE_MANIFEST.sha256 |
| `sim/goal_metric/goal_metric.py` | `dd8212605e142ddd2581487812aceb3fb14320f4feaadf84339770c6e72714f5` | GOAL_MANIFEST.sha256 |
| `sim/goal_metric/make_kat.py` | `e9c5dbbf7715202182250ce611273ab679084467e8d4b98d872147a490325eed` | GOAL_MANIFEST.sha256 |
| `sim/goal_metric/run_kat.py` | `3445ad3257025712002da6ea63f15dffb27a1dc03511abfa4e44a4d134bf4339` | GOAL_MANIFEST.sha256 |
| `sim/goal_metric/check_exact.py` | `73f19eb3b6cdb2c6bd0dcffa82bfd13d47bfac268d9f8b0a680a52ac968eccf9` | GOAL_MANIFEST.sha256 |
| `sim/goal_metric/README.md` | `ba71e729a2d8bad0a6d1d4acfcb580456998685f804eca6a7d817ad61382ec09` | GOAL_MANIFEST.sha256 |
| `sim/goal_metric/GOAL_MANIFEST.sha256` | `b718e7e13a04ffd4768f81f22c5abd2022239287adfbeb774f8afd0236a3453d` | GOAL_MANIFEST.sha256 |
| `sim/EVAL_SPEC_v1.md` | `3f4c44f720d4551616ad57a67ee360eaa1794b1d6ef4da79fcdb54975a3e3c62` | hashed spec |
| `sim/EVAL_SPEC_v1_addendum.md` | `e332a7e3c07d8bf2bf59e9f4cfd703fcfd0a53f72327e777c05cb7298e9f1da8` | hashed spec |
| `sim/EVAL_SPEC_v1_addendum2.md` | `224dc1245934302b8abd2605c6a04bc2a2b0a3a92b280fa09cb04faa2ac273a4` | hashed spec |
| `sim/EVAL_SPEC_v1_addendum3.md` | `624bfe690cdf979271de279245c59f00bad5c36a54d9716557b05361a7fb2cc5` | hashed spec |
| `sim/EVAL_SPEC_v1_addendum4_goalmetric.md` | `cec0693c202c084e4e0584455218577a5154bafd4fdc44c673eceaa4be5fb4c1` | hashed spec |
| `targets/SOURCES.md` | `42be364f35e83df2e4ded63887e4c3c5a58acede2ca4a9dbd8b71cf6129d0584` | treated as frozen by the guard's R5 |

The hashes above are the originals recorded during the run. In this public copy, `sim/judge/judge_intake.py`, `sim/EVAL_SPEC_v1.md` and `targets/SOURCES.md` were edited, so they no longer match: see `docs/FROZEN_CHANGES.md` for their new hashes and `ISSUES/fix-hashes.md`.

## Names and paths left in frozen files

- `sim/judge/BREV_BATCH.md` line 11: `/home/ubuntu`, the generic cloud user
- `sim/EVAL_SPEC_v1.md` line 138: teammate first name "Alan", kept as attribution

## Files changed from the original (not frozen)

| file | original sha256 | this repo's sha256 |
|---|---|---|
| `harness_open/smoke_test.py` | `7bbc7d9827c38a3c07ea89927d0328c1dc02cb127a809f040d6fd7c87aa99ccb` | `8817879d0b30ecdefe84bf9786e7ff634de170362ad0b031b6c80c3888eda97c` |
| `harness_open/intervene.py` | `6b18e42e2d4a6a6b91b6cfc25a1a8f840b473563e28ad070d5769f2646b3289d` | `f17ba323207a0a8c2c7b5daf19df99aa3db2562ed2db3dfc6105019e7607e0a5` |
| `harness_open/tools.json` | `a888d96061849a7233ae0f72b00ea026b2412230cae88ee90006a3bcbbea0f31` | `bc1632d85fc6438cd19273b1dfe81c2008f1c93a12f51a5222ba9e79526f1935` |
| `guard/eval_guard.py` | `2ba817714df299747cca62f38e8d3265e8cab22e78cf41623234975a43132ab0` | `cca27e9c087bdb8ab6c73495308c961c1a9c2bc049af5f9deaab9aaf8646e68f` |
| `compute/FAIRSHARE.md` | `170d0f2a96f869b8438afd2cad4a1c2c6dc068b096d4f48fd2722a7da665a1ff` | `21324bc32a7decd7fb658c9437c59e7858b1fd8fb1562dae9b8e05c6dc7e5396` |
| `figures/scripts/build_all.py` | `f08bdf560875d23993bf6cc7a1fb1c7b7aa03ef6adb3d01d870a55be712ead51` | `ea4ea002cb4bebe9433c7ec19ad7972f9f5563d7af8285f92b48b9705e852d86` |
| `analysis_process/scripts/compute_metrics.py` | `156dbbc4878ec788711aeb7d54af5d20458ac894db7ec90b34f04ca91fee71fa` | `19f01458c58fb9946ae2384dfa610ce0aafbfe379ac897524bf8f64dd996cb3e` |
| `analysis_process/scripts/make_figures.py` | `4e7933b137eb0cc90476c06893f5c50d9c2823f49c4c69044fcd4626d985682e` | `4520a13aa900a5d1f8bba64d8422ee3205939f701d502c11af9f2458014510c9` |
| `analysis_process/scripts/write_reports.py` | `a75cfde8b3b326434ea49db0cdaecb9823ea256bf4fddb40d95192997c5101a8` | `45c5fefb40d7dfdc6a30d5f470638418184ddf193aa68491e6f68fd6c5c49617` |
| `analysis_process/scripts/run_all.py` | `5cd6a869ce2444a6adec0d48579975f9f87620cfdfec2a588d7ccb8a2caaf2e6` | `ef97ecb4f37aedb4f7b2ae4a380f415ac50c9aab15bb9cf1753b539875a238bc` |

`harness_open/config.template.json` and `compute/caps.template.json` are templates generated from the originals, with key paths removed.
