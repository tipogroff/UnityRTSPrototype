# Gridnet Recipe Redesign Sweep Results

- sweep_id: gridnet_recipe_redesign_20260428T164010Z
- generated_utc: 2026-04-28T16:51:43.285234+00:00
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T164010Z

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
| A_low_entropy | completed | maps/24x24/basesWorkers24x24.xml | 24 | none | False | none | False |
| B_entropy_decay | failed | maps/24x24/basesWorkers24x24.xml | 24 | none | False | linear | False |
| C_passive_warmup_entropy_decay | failed | maps/24x24/basesWorkers24x24.xml | 24 | passive_warmup | True | linear | False |
| D_activity_shaping_mild | failed | maps/24x24/basesWorkers24x24.xml | 24 | none | False | linear | True |

## Metrics Summary
| config | det_noop_share | det_return_mean | det_return_std | det_actor_move_mean | det_pass_count | stoch_return_mean | stoch_return_std | stoch_entropy_norm | stoch_top_action_share | stoch_actor_move_mean | adapter_clean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A_low_entropy | 0.9998881022135416 | 1.0 | 0.0 | 0.001303780964797914 | 0 | 11.5 | 6.576473218982953 | 0.999997352485009 | 0.16766272650824654 | 0.15468277459827173 | det=True, stoch=True |
| B_entropy_decay | 1.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | det=False, stoch=False |
| C_passive_warmup_entropy_decay | 1.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | det=False, stoch=False |
| D_activity_shaping_mild | 1.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | det=False, stoch=False |

## Success Criteria Check
| config | det_behavior | det_return_gt_2 | stoch_entropy_lt_0_95 | visual_consistent | adapter_clean | promising |
|---|---|---|---|---|---|---|
| A_low_entropy | False | False | False | False | True | False |
| B_entropy_decay | False | False | False | False | False | False |
| C_passive_warmup_entropy_decay | False | False | False | False | False | False |
| D_activity_shaping_mild | False | False | False | False | False | False |

## Activity Shaping Diagnostics
- D_activity_shaping_mild is diagnostics-only unless shaping_applied=true in run_manifest.
- A_low_entropy: {"status": "ok", "enabled": false, "shape_move_reward": 0.005, "shape_produce_reward": 0.003, "shape_noop_penalty": 0.0005, "shape_no_effect_penalty": 0.001, "shaping_applied": false, "attribution_reliable": false, "diagnostics_only_reason": "reliable per-step causal attribution is unavailable in current training env interface", "move_reward_events": 0, "produce_reward_events": 0, "repeated_noop_penalty_events": 0, "no_effect_penalty_events": 0, "shaping_total_reward_delta": 0.0}

## Ranking
- 1. A_low_entropy

## Decision
- REJECT_CURRENT_GRIDNET_RECIPE
- Do not promote based only on stochastic return when entropy remains near 1.0.

## Non-Goals Reinforced
- No BC-ready package created in this sweep.
- No student retraining performed.
- No Unity modifications.
- No teacher-ready claim made.

