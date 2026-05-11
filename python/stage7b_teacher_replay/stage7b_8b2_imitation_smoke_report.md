# Stage7B-8B.2 Imitation Smoke Report

status: NO-GO
run_id: Stage7B_ImitationSmoke_004

## Command
python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe config/stage7b_imitation_smoke.yaml --run-id Stage7B_ImitationSmoke_004 --force

## Trainer Controlled Mode
- trainer_controlled_mode_prepared: true
- behavior_type_runtime: Default
- decision_requester_enabled: true
- teacher_replay_orchestrator_enabled: false

## Trainer Result
- trainer_started: true
- config_loaded: true
- unity_connected: true
- behavior_name_matched: true
- training_steps_completed: 1500
- demo_loaded_or_consumed: true
- loss_nan_detected: false
- reward_nan_detected: false
- trainer_exit_code: 1
- trainer_error_summary: Learning was interrupted manually after smoke success threshold (steps > 0).

## Artifacts
- results_dir: results/Stage7B_ImitationSmoke_004
- checkpoint_saved: true
- checkpoint_paths:
  - results/Stage7B_ImitationSmoke_004/Stage7B_RTS_Student/Stage7B_RTS_Student-1600.pt
- tfevents_saved: true
- tfevents_path:
  - results/Stage7B_ImitationSmoke_004/Stage7B_RTS_Student/events.out.tfevents.1778455780.grozov.113468.0
- trainer_log:
  - python/stage7b_teacher_replay/stage7b_8b2_imitation_smoke_trainer.log

## Unity Console
- unity_console_errors: 1
- unity_console_warnings: 0
- last_console_error: Some objects were not cleaned up when closing the scene. (Did you spawn new GameObjects from OnDestroy?)

## GO/NO-GO Decision
NO-GO

Reason:
- Smoke progress criteria are met (connected, steps > 0, checkpoint and tfevents created, no NaN), but strict GO criteria requires Unity Console errors = 0.

## Safety Constraints
- stage6b3_baseline_touched: false
- clean_demo_unchanged: true
- no_long_training: true
- no_ppo_full_stage: true
