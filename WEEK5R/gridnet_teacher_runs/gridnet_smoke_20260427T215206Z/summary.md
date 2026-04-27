# Gridnet Teacher Run Summary

- run_id: gridnet_smoke_20260427T215206Z
- created_utc: 2026-04-27T14:54:09.971048+00:00
- total_timesteps_target: 10000
- global_step_reached: 10752
- overshoot_steps: 752
- map_path: maps/24x24/basesWorkers24x24.xml
- observation_shape: [24, 24, 27]
- action_nvec: [576, 6, 4, 4, 4, 4, 7, 49]
- checkpoints_saved: [10000]
- checkpoint_eval_reports: 1
- checkpoint_eval_pass_count: 0
- final_model_saved: True
- final_eval_status: eval_error
- final_eval_effective_position_delta_count: None
- final_eval_actor_level_move_share: None
- final_eval_no_effect_action_share: None
- render_window_enabled: True
- visual_eval_attempted: True
- visual_eval_status: ok
- visual_eval_steps: 200

## Visual Sanity
- render_window_enabled: True
- visual_eval_attempted: True
- visual_eval_status: ok
- note: visual check is human-readable sanity layer only

- visual_note: visual sanity layer only; not a replacement for actor-level evaluator

## Compatibility Notes
- This run is project-compatible by surface/discipline, not by direct Unity checkpoint loading.
- No reference branch weights were imported.
- No Unity-side or BC pipeline files were modified.
