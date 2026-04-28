# Gridnet Teacher Run Summary

- run_id: gridnet_fresh_100k_v2_20260428T191104Z
- created_utc: 2026-04-28T12:23:50.365194+00:00
- total_timesteps_target: 100000
- global_step_reached: 101376
- initial_global_step: 0
- remaining_timesteps_planned: 100000
- overshoot_steps: 1376
- resume_from_checkpoint: None
- resume_model_metadata: None
- map_path: maps/24x24/basesWorkers24x24.xml
- observation_shape: [24, 24, 27]
- action_nvec: [576, 6, 4, 4, 4, 4, 7, 49]
- checkpoints_saved: [20000, 50000, 100000]
- checkpoint_eval_reports: 3
- checkpoint_eval_pass_count: 1
- final_model_saved: True
- final_eval_status: PASS
- final_eval_effective_position_delta_count: 36
- final_eval_actor_level_move_share: 0.004445964432284542
- final_eval_no_effect_action_share: 0.9731543624161074
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
