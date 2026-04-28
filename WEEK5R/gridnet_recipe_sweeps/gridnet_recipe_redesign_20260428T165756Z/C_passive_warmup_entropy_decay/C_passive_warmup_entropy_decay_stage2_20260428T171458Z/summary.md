# Gridnet Teacher Run Summary

- run_id: C_passive_warmup_entropy_decay_stage2_20260428T171458Z
- created_utc: 2026-04-28T17:20:35.056211+00:00
- total_timesteps_target: 100000
- global_step_reached: 105296
- initial_global_step: 50000
- remaining_timesteps_planned: 50000
- overshoot_steps: 5296
- resume_from_checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\C_passive_warmup_entropy_decay\C_passive_warmup_entropy_decay_stage1_20260428T170933Z\agent_final.pt
- resume_model_metadata: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\C_passive_warmup_entropy_decay\C_passive_warmup_entropy_decay_stage1_20260428T170933Z\model_metadata.json
- map_path: maps/24x24/basesWorkers24x24.xml
- observation_shape: [24, 24, 27]
- action_nvec: [576, 6, 4, 4, 4, 4, 7, 49]
- checkpoints_saved: [100000]
- checkpoint_eval_reports: 1
- checkpoint_eval_pass_count: 0
- final_model_saved: True
- final_eval_status: SUSPICIOUS
- final_eval_effective_position_delta_count: 52
- final_eval_actor_level_move_share: 0.013196480938416423
- final_eval_no_effect_action_share: 1.0
- ent_schedule: linear
- ent_coef_base: 0.01
- ent_coef_start: 0.01
- ent_coef_end: 0.0005
- curriculum_mode: passive_warmup
- phase_boundaries: [{'phase': 'warmup', 'start_global_step': 50000, 'end_global_step': 50000}, {'phase': 'diverse', 'start_global_step': 50000, 'end_global_step': 100000}]
- opponent_pool_by_phase: {'warmup': ['passiveAI', 'randomBiasedAI'], 'diverse': ['randomBiasedAI', 'lightRushAI', 'workerRushAI', 'coacAI']}
- activity_shaping_enabled: False
- activity_shaping_applied: False
- shaping_counters: {'enabled': False, 'shaping_applied': False, 'attribution_reliable': False, 'diagnostics_only_reason': 'reliable per-step causal attribution is unavailable in current training env interface', 'move_reward_events': 0, 'produce_reward_events': 0, 'repeated_noop_penalty_events': 0, 'no_effect_penalty_events': 0, 'shaping_total_reward_delta': 0.0}
- tensorboard_status: disabled_by_flag
- tensorboard_error: None
- tb_log_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_recipe_sweeps\gridnet_recipe_redesign_20260428T165756Z\C_passive_warmup_entropy_decay\C_passive_warmup_entropy_decay_stage2_20260428T171458Z\tb\gridnet_project__1__20260428T171501Z_56f1c9b4
- render_window_enabled: False
- visual_eval_attempted: False
- visual_eval_status: unavailable
- visual_eval_steps: 0

## Visual Sanity
- render_window_enabled: False
- visual_eval_attempted: False
- visual_eval_status: unavailable
- note: visual check is human-readable sanity layer only

- visual_note: visual sanity layer only; not a replacement for actor-level evaluator
## Compatibility Notes
- This run is project-compatible by surface/discipline, not by direct Unity checkpoint loading.
- No reference branch weights were imported.
- No Unity-side or BC pipeline files were modified.
