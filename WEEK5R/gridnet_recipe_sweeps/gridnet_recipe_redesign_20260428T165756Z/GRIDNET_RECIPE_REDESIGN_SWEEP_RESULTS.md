# Gridnet Recipe Redesign Sweep Results

- sweep_id: gridnet_recipe_redesign_20260428T165756Z
- generated_utc: 2026-04-28T17:33:15.123136+00:00
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z

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
| B_entropy_decay | completed | maps/24x24/basesWorkers24x24.xml | 24 | none | False | linear | False |
| C_passive_warmup_entropy_decay | completed | maps/24x24/basesWorkers24x24.xml | 24 | passive_warmup | True | linear | False |
| D_activity_shaping_mild | completed | maps/24x24/basesWorkers24x24.xml | 24 | none | False | linear | True |

## Metrics Summary
| config | det_noop_share | det_return_mean | det_return_std | det_actor_move_mean | det_pass_count | stoch_return_mean | stoch_return_std | stoch_entropy_norm | stoch_top_action_share | stoch_actor_move_mean | adapter_clean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| B_entropy_decay | 0.9999830457899306 | 1.0 | 0.0 | 0.0 | 0 | 7.0 | 4.847679857416329 | 0.9999954272523656 | 0.1680543687608507 | 0.2496896972000789 | det=True, stoch=True |
| C_passive_warmup_entropy_decay | 0.9998575846354166 | 2.0 | 0.0 | 0.013196480938416423 | 0 | 10.0 | 6.819090848492928 | 0.9999974532299533 | 0.16766357421875 | 0.21034437530655625 | det=True, stoch=False |
| D_activity_shaping_mild | 0.999755859375 | 2.0 | 0.0 | 0.013196480938416423 | 4 | 9.0 | 5.385164807134504 | 0.9999971498050108 | 0.1676847669813368 | 0.19368504780452406 | det=True, stoch=True |

## Success Criteria Check
| config | det_behavior | det_return_gt_2 | stoch_entropy_lt_0_95 | visual_consistent | adapter_clean | promising |
|---|---|---|---|---|---|---|
| B_entropy_decay | False | False | False | False | True | False |
| C_passive_warmup_entropy_decay | False | False | False | False | False | False |
| D_activity_shaping_mild | False | False | False | False | True | False |

## Activity Shaping Diagnostics
- D_activity_shaping_mild is diagnostics-only unless shaping_applied=true in run_manifest.
- B_entropy_decay: {"status": "ok", "enabled": false, "shape_move_reward": 0.005, "shape_produce_reward": 0.003, "shape_noop_penalty": 0.0005, "shape_no_effect_penalty": 0.001, "shaping_applied": false, "attribution_reliable": false, "diagnostics_only_reason": "reliable per-step causal attribution is unavailable in current training env interface", "move_reward_events": 0, "produce_reward_events": 0, "repeated_noop_penalty_events": 0, "no_effect_penalty_events": 0, "shaping_total_reward_delta": 0.0}
- C_passive_warmup_entropy_decay: {"status": "ok", "enabled": false, "shape_move_reward": 0.005, "shape_produce_reward": 0.003, "shape_noop_penalty": 0.0005, "shape_no_effect_penalty": 0.001, "shaping_applied": false, "attribution_reliable": false, "diagnostics_only_reason": "reliable per-step causal attribution is unavailable in current training env interface", "move_reward_events": 0, "produce_reward_events": 0, "repeated_noop_penalty_events": 0, "no_effect_penalty_events": 0, "shaping_total_reward_delta": 0.0}
- D_activity_shaping_mild: {"status": "ok", "enabled": true, "shape_move_reward": 0.005, "shape_produce_reward": 0.003, "shape_noop_penalty": 0.0005, "shape_no_effect_penalty": 0.001, "shaping_applied": false, "attribution_reliable": false, "diagnostics_only_reason": "reliable per-step causal attribution is unavailable in current training env interface", "move_reward_events": 0, "produce_reward_events": 0, "repeated_noop_penalty_events": 0, "no_effect_penalty_events": 0, "shaping_total_reward_delta": 0.0}

## Ranking
- 1. D_activity_shaping_mild
- 2. C_passive_warmup_entropy_decay
- 3. B_entropy_decay

## Decision
- CONTINUE_SWEEP
- Do not promote based only on stochastic return when entropy remains near 1.0.

## Non-Goals Reinforced
- No BC-ready package created in this sweep.
- No student retraining performed.
- No Unity modifications.
- No teacher-ready claim made.

