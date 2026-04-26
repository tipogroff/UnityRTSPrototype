# Teacher Retraining Results

- run_id: `behavior_first_20260425T143023Z`
- run_status: `completed_with_failures`
- retraining_dir: `WEEK5R\retraining_runs\behavior_first_20260425T143023Z`
- gate_dir: `WEEK5R\gate_runs\behavior_first_20260425T143023Z`
- gate_comparison_md: `WEEK5R\gate_runs\behavior_first_20260425T143023Z\TEACHER_BEHAVIOR_GATE_COMPARISON.md`
- min_abort_step: `5000`
- collect_all_checkpoints: `True`
- abort_suppressed_count: `3`
- checkpoints_failed: `3`  checkpoints_passed: `0`

## Run Notes
- Abort suppressed at step 5000 (checkpoint_step 5000 <= min_abort_step 5000): actor_level_move_share==0 with ready_movable_actor_choice_count>0; effective_position_delta_count==0; no_effect_action_share>0.80 — continuing to next checkpoint.
- Abort suppressed at step 10000 (collect_all_checkpoints=True): effective_position_delta_count==0; no_effect_action_share>0.80 — continuing to next checkpoint.
- Abort suppressed at step 20000 (collect_all_checkpoints=True): actor_level_move_share==0 with ready_movable_actor_choice_count>0; effective_position_delta_count==0; no_effect_action_share>0.80 — continuing to next checkpoint.
- compare_teacher_behavior_gates.py exit_code=1
- comparison tool output captured

## Checkpoint Gate Summary
| step | status | actor_move | actor_noop | pos_delta | no_effect | continue_ok | candidate_ok | visual_verdict |
|---|---|---:|---:|---:|---:|---|---|---|
| 5000 | FAIL_FALSE_FULL_TENSOR_MOVE | 0.0000 | 0.0000 | 0 | 1.0000 | False | False | n/a |
| 10000 | FAIL_NO_EFFECT_BEHAVIOR | 0.6667 | 0.0000 | 0 | 1.0000 | False | False | n/a |
| 20000 | FAIL_FALSE_FULL_TENSOR_MOVE | 0.0000 | 0.0000 | 0 | 1.0000 | False | False | n/a |

## Abort Policy
- Abort suppressed for checkpoint_step <= min_abort_step (5000)
- `--collect-all-checkpoints` active: abort never triggered regardless of gate results
- Hard abort triggers (when not suppressed):
  - FAIL_COLLAPSED_NOOP at 5k and 10k consecutively
  - actor_level_move_share == 0 while ready_movable_actor_choice_count > 0
  - effective_position_delta_count == 0
  - no_effect_action_share > 0.80
