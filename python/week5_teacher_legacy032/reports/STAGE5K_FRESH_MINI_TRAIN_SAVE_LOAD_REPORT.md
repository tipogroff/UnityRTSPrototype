# Stage5K Fresh Mini Train -> Save -> Load -> Visual Smoke

- timestamp_utc: 2026-05-05T18:57:01.575757+00:00
- classification: STAGE5K_RENDER_CAPTURE_FAILED
- recommendation: ENABLE_RELIABLE_FRAME_CAPTURE_IN_CANONICAL_VISUAL_RUNNER_THEN_REPEAT_STAGE5K_VISUAL_BY_EYE; KEEP_ACCEPTED_EFFECT_TRACE_AS_SECONDARY_EVIDENCE

## Files Created/Updated

- C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/reports/stage5k_fresh_mini_train_save_load_20260505T185701Z.json
- C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/reports/STAGE5K_FRESH_MINI_TRAIN_SAVE_LOAD_REPORT.md
- C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/reports/stage5k_microtrace_compact.json

## Exact Commands

- training_requested: c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py --exp-name legacy032_stage5k_fresh_mini_train --seed 17 --cuda false --prod-mode false --local-save-model true --local-save-dir python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train --local-save-every 128 --save-full-training-state true --map-path maps/24x24/basesWorkers24x24.xml --max-steps 6000 --expected-map-size 24 --verify-contract true --num-bot-envs 2 --num-selfplay-envs 0 --num-steps 64 --total-timesteps 256 --schedule-total-timesteps 256 --n-minibatch 2 --update-epochs 2 --capture-video false
- training_actual: c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py --exp-name legacy032_stage5k_fresh_mini_train --seed 17 --cuda false --prod-mode false --local-save-model true --local-save-dir python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train --local-save-every 128 --save-full-training-state true --map-path maps/24x24/basesWorkers24x24.xml --max-steps 6000 --expected-map-size 24 --verify-contract true --num-bot-envs 6 --num-selfplay-envs 0 --num-steps 16 --total-timesteps 288 --schedule-total-timesteps 288 --n-minibatch 2 --update-epochs 2 --capture-video false
- visual_deterministic: c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train/model_metadata.json --device cpu --seed 17 --mode deterministic --max-steps 512 --strict-load --render --run-label stage5k_fresh_mini_deterministic
- visual_stochastic: c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe python/week5_teacher_legacy032/scripts/run_legacy032_visual_single_episode.py --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train/agent_final.pt --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train/model_metadata.json --device cpu --seed 17 --mode stochastic --max-steps 512 --strict-load --render --run-label stage5k_fresh_mini_stochastic

## Training Result

- initial_run_exit_code: 1
- initial_run_error: AssertionError: for each environment, a microrts ai should be provided
- rerun_exit_code: 0
- RESUME_STATUS: STARTED_FROM_SCRATCH
- CHECKPOINT_STATUS: FULL_CHECKPOINT_SAVED
- global_step_start: 0
- global_step_end: 288
- target_total_timesteps: 288
- schedule_total_timesteps: 288
- strict_agent_load: False
- optimizer_state_restored: False
- rng_state_restored: False
- weights_only_paths: ['python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train\\agent_step_000000128.pt', 'python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train\\agent_step_000000256.pt']
- full_training_checkpoint_paths: ['python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train\\trainer_state_step_000000128.pt', 'python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train\\trainer_state_step_000000256.pt', 'python/week5_teacher_legacy032/teacher_models/legacy032_stage5k_fresh_mini_train\\trainer_state_final.pt']
- training_live_behavior_visible_in_console: False
- training_live_behavior_note: Console log contains SPS/save events but no explicit per-step movement/harvest visual evidence.

## Deterministic Post-Load

- status: OK
- mode: deterministic
- seed: 17
- first_step_summary: {'all_cell_action_type_counts': {'0': 1148, '1': 0, '2': 2, '3': 0, '4': 2, '5': 0}, 'all_cell_action_type_shares': {'0': 0.9965277777777778, '1': 0.0, '2': 0.001736111111111111, '3': 0.0, '4': 0.001736111111111111, '5': 0.0}, 'source_valid_action_type_counts': {'0': 0, '1': 0, '2': 2, '3': 0, '4': 2, '5': 0}, 'source_valid_action_type_shares': {'0': 0.0, '1': 0.0, '2': 0.5, '3': 0.0, '4': 0.5, '5': 0.0}, 'source_valid_non_noop_count': 4, 'source_valid_total': 4}
- first_step_branch_validity: {'source_valid_total': 4, 'effective_noop_candidate_count': 0}
- total_steps: 512
- total_reward: 0.0
- terminal_info_keys: ['raw_rewards']
- rendered_frames_count: 0

## Stochastic Post-Load

- status: OK
- mode: stochastic
- seed: 17
- first_step_summary: {'all_cell_action_type_counts': {'0': 194, '1': 194, '2': 200, '3': 174, '4': 197, '5': 193}, 'all_cell_action_type_shares': {'0': 0.1684027777777778, '1': 0.1684027777777778, '2': 0.1736111111111111, '3': 0.15104166666666666, '4': 0.17100694444444445, '5': 0.1675347222222222}, 'source_valid_action_type_counts': {'0': 3, '1': 0, '2': 1, '3': 0, '4': 0, '5': 0}, 'source_valid_action_type_shares': {'0': 0.75, '1': 0.0, '2': 0.25, '3': 0.0, '4': 0.0, '5': 0.0}, 'source_valid_non_noop_count': 1, 'source_valid_total': 4}
- first_step_branch_validity: {'source_valid_total': 4, 'effective_noop_candidate_count': 0}
- total_steps: 512
- total_reward: 0.0
- terminal_info_keys: ['raw_rewards']
- rendered_frames_count: 0

## Fresh vs 1M

- deterministic_match: True
- stochastic_match: False
- stochastic_difference_note: Fresh mini stochastic is more noop-heavy on source-valid cells (3/4 noop) vs 1M stochastic (0/4 noop).

## Optional Accepted/Effect Trace

- det_any_obs_change: True
- det_obs_changed_steps: 1
- stoch_any_obs_change: True
- stoch_obs_changed_steps: 2

## Required Conclusion

- fresh_checkpoint_behaves_differently_from_1m: True
- training_time_active_but_postload_inert_reproduced: None
- final_classification: STAGE5K_RENDER_CAPTURE_FAILED
- final_recommendation: ENABLE_RELIABLE_FRAME_CAPTURE_IN_CANONICAL_VISUAL_RUNNER_THEN_REPEAT_STAGE5K_VISUAL_BY_EYE; KEEP_ACCEPTED_EFFECT_TRACE_AS_SECONDARY_EVIDENCE
