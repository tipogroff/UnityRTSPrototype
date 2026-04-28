# Gridnet Teacher Run Summary

- run_id: gridnet_200k_continue_20260428T183153Z
- created_utc: 2026-04-28T11:44:44.866064+00:00
- total_timesteps_target: 200000
- global_step_reached: 201376
- initial_global_step: 100000
- remaining_timesteps_planned: 100000
- overshoot_steps: 1376
- resume_from_checkpoint: WEEK5R\gridnet_teacher_runs\gridnet_100k_20260427T221123Z\agent_final.pt
- resume_model_metadata: WEEK5R\gridnet_teacher_runs\gridnet_100k_20260427T221123Z\model_metadata.json
- map_path: maps/24x24/basesWorkers24x24.xml
- observation_shape: [24, 24, 27]
- action_nvec: [576, 6, 4, 4, 4, 4, 7, 49]
- checkpoints_saved: [150000, 200000]
- checkpoint_eval_reports: 2
- checkpoint_eval_pass_count: 0
- final_model_saved: True
- final_eval_status: SUSPICIOUS
- final_eval_effective_position_delta_count: 52
- final_eval_actor_level_move_share: 0.014771048744460856
- final_eval_no_effect_action_share: 1.0
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
