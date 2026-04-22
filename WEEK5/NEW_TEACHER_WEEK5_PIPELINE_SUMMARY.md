# NEW_TEACHER_WEEK5_PIPELINE_SUMMARY

Date (UTC): 2026-04-22
Status: canonical Day 3 -> Day 6 rerun completed for new teacher candidate

## 1. Candidate used

Checkpoint lineage:

- `python/week5_teacher/teacher_models/day5_teacher_hardened_serious_v2_20260420T173711Z/teacher_sb3_ppo.zip`

Canonical Python env:

- `python/week5_teacher/.venv_day2_py39/Scripts/python.exe`

Important Day 3 note:

- The rerun could not start on the first attempt because `run_teacher_rollout.py` only reloaded standard SB3 PPO checkpoints, while this checkpoint was produced by `sb3_contrib.MaskablePPO`.
- The local root fix was applied in Day 3 loader compatibility so the canonical pipeline could honestly rerun from raw rollout instead of skipping provenance.

## 2. New lineage artifacts created

Day 3 raw rollout:

- `python/week5_teacher/teacher_rollouts/teacher_raw_training_day5_hardened_v2_teacher_candidate_20260422T074106Z`
- `python/week5_teacher/teacher_logs/teacher_rollout_20260422T074106Z.summary.json`

Day 4 adapted batch:

- `python/week5_teacher/teacher_exports/teacher_adapted_day5_hardened_v2_teacher_candidate_20260422T074106Z`

Day 5 validation outputs:

- `strict_validation_day5.json`
- `quality_report_day5.json`
- `quality_report_day5.md`

Day 6 BC-ready outputs:

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_20260422T074106Z`
- `bc_train.npz`
- `bc_validation.npz`
- `bc_debug.npz`
- `bc_manifest.json`
- `bc_summary.json`
- `dry_run_bc_loader_report.json`

Comparison artifacts for this rerun:

- `python/week5_teacher/teacher_exports/COMPARE_TEACHER_BATCHES_DAY5_hardened_v2_vs_preferred.md`
- `python/week5_teacher/teacher_exports/COMPARE_TEACHER_BATCHES_DAY5_hardened_v2_vs_preferred.json`

## 3. Pipeline outcome

Day 3 raw rollout:

- status: success
- episodes: 6
- steps: 1536
- mean episode length: 256
- mean return: 0.0
- runtime backend: `gym_microrts.envs.vec_env.MicroRTSGridModeVecEnv`
- backend note: preferred backend failed with `NameNotFound`, so the run used the documented fallback path

Day 4 adaptation:

- status: success
- converted episode files: 6
- dropped samples at adapter stage: 0

Day 5 validation:

- status: pass
- hard failures: 0
- warnings: 19

Day 6 BC-ready packaging:

- status: success
- total samples: 1536
- splits: train=1392, validation=144, debug=256

Day 6 loader dry run:

- status: pass
- expected tensor shape contract verified for train, validation, and debug splits

## 4. Honest comparison vs current preferred batch

Current preferred adapted baseline:

- `python/week5_teacher/teacher_exports/teacher_adapted_day5_first_nonrandom_meaningful`

Current preferred BC-ready baseline:

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z`

Scripted Day 5 comparison result:

- `comparison_result`: `mixed`
- `preferred_bc_candidate_batch`: `mixed_decision`

Metrics improved in the new candidate:

- `remap_to_noop_share`: 19.97% -> 9.38%
- `class_imbalance_ratio`: 19.4545 -> 11.55
- `inactive_branch_anomaly_share`: 4.51% -> 2.60%
- `attack_action_share`: 1.91% -> 3.47%

Metrics worsened in the new candidate:

- `warnings_count`: 4 -> 19
- `usable_samples`: 2000 -> 1536
- `production_actions_survived_share`: 60.00% -> 58.49%
- `produce_action_share`: 10.42% -> 5.38%

BC-ready readiness comparison:

- old preferred Day 6 package: pass
- new candidate Day 6 package: pass
- old preferred loader dry run: pass
- new candidate loader dry run: pass
- neither side has an exclusive Day 6 readiness advantage

## 5. Recommendation

Recommendation: keep the old preferred batch as the canonical default for now.

Reasoning:

- The new candidate is not a clear upgrade; the scripted comparison result is `mixed`, not `better`.
- It improves several data-quality stress metrics, especially remap pressure and branch anomaly severity.
- It also loses meaningful coverage and action-survival signal, and it introduces substantially more Day 5 warnings.
- Because both old and new batches pass Day 6 packaging and loader validation, the decision comes down to data quality tradeoffs, and those tradeoffs are not strong enough yet to justify replacing the current preferred baseline.

## 6. Bottom line

The new hardened v2 teacher candidate now has a complete, non-overwritten canonical Week 5 lineage from Day 3 raw rollout through Day 6 BC-ready artifacts.

It is usable as a comparison candidate and as a secondary BC-ready source, but it should not replace the current preferred batch unless a follow-up run resolves the warning inflation and recovers stronger production-action coverage without reintroducing higher remap pressure.
