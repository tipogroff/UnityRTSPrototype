# Gridnet Recipe Redesign Sweep Results

- sweep_id: gridnet_recipe_redesign_20260428T163823Z
- generated_utc: 2026-04-28T16:38:23.820076+00:00
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T163823Z

## Scope
- Entropy/reward/curriculum redesign only for Branch B Gridnet teacher.
- No Unity runtime modifications.
- No BC-ready dataset generation.
- No student retraining.
- No teacher-ready claim.
- D_activity_shaping_mild is diagnostics-only unless shaping_applied=true in run_manifest.

## Config Status
| config | status | map | num_bot_envs | curriculum_mode | staged_curriculum | ent_schedule | activity_shaping |
|---|---|---|---:|---|---|---|---|
| A_low_entropy | skipped | maps/24x24/basesWorkers24x24.xml | 24 | none | False | none | False |
| B_entropy_decay | skipped | maps/24x24/basesWorkers24x24.xml | 24 | none | False | linear | False |
| C_passive_warmup_entropy_decay | skipped | maps/24x24/basesWorkers24x24.xml | 24 | passive_warmup | True | linear | False |
| D_activity_shaping_mild | skipped | maps/24x24/basesWorkers24x24.xml | 24 | none | False | linear | True |

## Metrics Summary
| config | det_noop_share | det_return_mean | det_return_std | det_actor_move_mean | det_pass_count | stoch_return_mean | stoch_return_std | stoch_entropy_norm | stoch_top_action_share | stoch_actor_move_mean | adapter_clean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A_low_entropy | 1.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | det=False, stoch=False |
| B_entropy_decay | 1.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | det=False, stoch=False |
| C_passive_warmup_entropy_decay | 1.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | det=False, stoch=False |
| D_activity_shaping_mild | 1.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | det=False, stoch=False |

## Success Criteria Check
| config | det_behavior | det_return_gt_2 | stoch_entropy_lt_0_95 | visual_consistent | adapter_clean | promising |
|---|---|---|---|---|---|---|
| A_low_entropy | False | False | False | False | False | False |
| B_entropy_decay | False | False | False | False | False | False |
| C_passive_warmup_entropy_decay | False | False | False | False | False | False |
| D_activity_shaping_mild | False | False | False | False | False | False |

## Activity Shaping Diagnostics
- D_activity_shaping_mild is diagnostics-only unless shaping_applied=true in run_manifest.

## Ranking
- No completed configs to rank.

## Decision
- CONTINUE_SWEEP
- Do not promote based only on stochastic return when entropy remains near 1.0.

## Non-Goals Reinforced
- No BC-ready package created in this sweep.
- No student retraining performed.
- No Unity modifications.
- No teacher-ready claim made.

