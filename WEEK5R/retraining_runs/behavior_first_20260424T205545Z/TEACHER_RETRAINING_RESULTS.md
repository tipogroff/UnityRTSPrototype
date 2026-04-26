# Teacher Retraining Results

- run_id: `behavior_first_20260424T205545Z`
- run_status: `aborted`
- retraining_dir: `WEEK5R\retraining_runs\behavior_first_20260424T205545Z`
- gate_dir: `WEEK5R\gate_runs\behavior_first_20260424T205545Z`
- gate_comparison_md: `WEEK5R\gate_runs\behavior_first_20260424T205545Z\TEACHER_BEHAVIOR_GATE_COMPARISON.md`
- min_abort_step: `5000`
- collect_all_checkpoints: `False`
- abort_suppressed_count: `0`
- checkpoints_failed: `1`  checkpoints_passed: `0`

## Run Notes
- Abort at step 5000: actor_level_move_share==0 with ready_movable_actor_choice_count>0; effective_position_delta_count==0; no_effect_action_share>0.80
- compare_teacher_behavior_gates.py exit_code=1
- comparison tool output captured

## Checkpoint Gate Summary
| step | status | actor_move | actor_noop | pos_delta | no_effect | continue_ok | candidate_ok | visual_verdict |
|---|---|---:|---:|---:|---:|---|---|---|
| 5000 | FAIL_FALSE_FULL_TENSOR_MOVE | 0.0000 | 0.0000 | 0 | 1.0000 | False | False | n/a |

## Abort Policy
- Abort suppressed for checkpoint_step < min_abort_step (5000)
- Hard abort triggers (when not suppressed):
  - FAIL_COLLAPSED_NOOP at 5k and 10k consecutively
  - actor_level_move_share == 0 while ready_movable_actor_choice_count > 0
  - effective_position_delta_count == 0
  - no_effect_action_share > 0.80
