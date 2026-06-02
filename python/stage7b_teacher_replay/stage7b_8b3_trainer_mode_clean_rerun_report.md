# Stage7B-8B.3 Trainer Mode Clean Rerun Report

status: NO-GO
run_id: Stage7B_ImitationSmoke_005

## Command
python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe config/stage7b_imitation_smoke.yaml --run-id Stage7B_ImitationSmoke_005 --force

## Scene And Pre-Run Diagnostics
- scene_path: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- behavior_name_runtime: Stage7B_RTS_Student
- behavior_type_runtime: Default
- decision_requester_enabled: true
- decision_period: 1
- take_actions_between_decisions: false
- manual_loop_enabled: false
- watchdog_manual_fallback_enabled: false
- teacher_replay_orchestrator_enabled: false
- student_teacher_replay_orchestrator_is_null: true
- demo_mode_active: false

## Trainer Result
- trainer_started: true
- config_loaded: true
- unity_connected: true
- behavior_name_matched: true
- training_steps_completed: 10000
- loss_nan_detected: false
- reward_nan_detected: false
- unity_time_out_exception: false
- trainer_reset_env_timeout: false
- trainer_exit_code: 1
- trainer_exit_code_interpretation: not a manual stop; final export/save failed
- trainer_error_summary: Module onnx is not installed during final model export/save

## Unity Console
- unity_console_errors: 0
- unity_console_warnings: 0

## Artifacts
- trainer_log: python/stage7b_teacher_replay/stage7b_8b3_imitation_smoke_trainer.log
- results_dir: results/Stage7B_ImitationSmoke_005
- tfevents_saved: true
- tfevents_path:
  - results/Stage7B_ImitationSmoke_005/Stage7B_RTS_Student/events.out.tfevents.1778487746.grozov.24376.0
- checkpoint_saved: false
- checkpoint_path: none found
- generated_files:
  - results/Stage7B_ImitationSmoke_005/configuration.yaml
  - results/Stage7B_ImitationSmoke_005/run_logs/timers.json
  - results/Stage7B_ImitationSmoke_005/run_logs/training_status.json
  - results/Stage7B_ImitationSmoke_005/Stage7B_RTS_Student/events.out.tfevents.1778487746.grozov.24376.0

## Blocker
Final checkpoint/export failed because `onnx` is not installed in the Stage7B ML-Agents Python environment.

## GO/NO-GO Decision
NO-GO

Reason:
- The smoke reached the training target and the Unity Console stayed clean, but the run did not finish with a saved checkpoint. `trainer_exit_code = 1` is therefore a failure path, not a permitted manual stop.

## Constraints Respected
- Stage6B3 baseline untouched: true
- Stage6B3 checkpoint untouched: true
- teacher policy unchanged: true
- reward unchanged: true
- ActionApplier / MatchManager runtime semantics unchanged: true
- clean demo dataset unchanged: true
- no long training: true
- no PPO fine-tune beyond the smoke config: true