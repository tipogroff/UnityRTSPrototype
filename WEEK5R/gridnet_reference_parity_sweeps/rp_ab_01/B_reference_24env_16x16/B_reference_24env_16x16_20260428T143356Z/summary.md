# Gridnet Teacher Run Summary

- run_id: B_reference_24env_16x16_20260428T143356Z
- created_utc: 2026-04-28T14:39:11.072177+00:00
- total_timesteps_target: 100000
- global_step_reached: 104448
- initial_global_step: 0
- remaining_timesteps_planned: 100000
- overshoot_steps: 4448
- resume_from_checkpoint: None
- resume_model_metadata: None
- map_path: maps/16x16/basesWorkers16x16.xml
- observation_shape: [16, 16, 27]
- action_nvec: [256, 6, 4, 4, 4, 4, 7, 49]
- checkpoints_saved: [20000, 50000, 100000]
- checkpoint_eval_reports: 3
- checkpoint_eval_pass_count: 0
- final_model_saved: True
- final_eval_status: FAIL_COLLAPSED_NOOP
- final_eval_effective_position_delta_count: 20
- final_eval_actor_level_move_share: 0.0
- final_eval_no_effect_action_share: 0.9705882352941176
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
