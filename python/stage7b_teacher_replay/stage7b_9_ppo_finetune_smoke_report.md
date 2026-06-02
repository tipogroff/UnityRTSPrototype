# Stage7B-9 PPO FineTune Smoke Report

final_decision: PARTIAL
ready_for_stage7b_10_evaluation: false
training_steps_completed: 2005
trainer_exit_code: 1

## Initialization
- method: --initialize-from Stage7B_ImitationSmoke_010_PostKickConfirm
- resolved_init_path: results/Stage7B_ImitationSmoke_010_PostKickConfirm/Stage7B_RTS_Student/checkpoint.pt
- initialization_succeeded: true
- run_not_from_scratch: true

## Trainer
- trainer_started: true
- config_loaded: true
- unity_connected: true
- max_steps: 2000
- training_steps_completed: 2005
- checkpoint_saved: true (results/Stage7B_PPOFineTuneSmoke_001/Stage7B_RTS_Student/Stage7B_RTS_Student-2005.pt)
- onnx_saved: true (results/Stage7B_PPOFineTuneSmoke_001/Stage7B_RTS_Student.onnx)
- tfevents_saved: true
- reward_mean_last_summary: 6.259999990463257
- reward_std_last_summary: None

## Action Path
- collect_observations_count: 2010
- write_discrete_action_mask_count: 2001
- on_action_received_count: 2001
- heuristic_call_count: 0
- padding_warning_detected: false
- runtime_apply_attempted: 2001
- runtime_apply_accepted: 2001
- runtime_apply_rejected: 0
- noop_ratio: 0.085957
- non_noop_ratio: 0.914043

## Console
- unity_console_errors: 0
- unity_console_warnings: 4
- warnings_fully_classified_benign: true
- benign_warning_types: benign_gameplay_spawn_saturation

## Notes
- trainer_exit_code_interpretation: PowerShell pipeline returned NativeCommandError because stderr warnings were surfaced as shell errors; the trainer still reached max_steps and exported final checkpoint/ONNX successfully.
- remaining_blockers: nonzero_shell_exit_code
- minimal_next_fix: Rerun the same PPO smoke command without the PowerShell Tee-Object stderr promotion so the shell exit code reflects the trainer's successful completion.
