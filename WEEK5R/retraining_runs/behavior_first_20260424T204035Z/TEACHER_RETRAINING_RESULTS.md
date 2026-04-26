# Teacher Retraining Results

- run_id: `behavior_first_20260424T204035Z`
- run_status: `aborted`
- retraining_dir: `WEEK5R\retraining_runs\behavior_first_20260424T204035Z`
- gate_dir: `WEEK5R\gate_runs\behavior_first_20260424T204035Z`
- gate_comparison_md: `WEEK5R\gate_runs\behavior_first_20260424T204035Z\TEACHER_BEHAVIOR_GATE_COMPARISON.md`

## Run Notes
- Abort at step 512: effective_position_delta_count==0; no_effect_action_share>0.80
- compare_teacher_behavior_gates.py exit_code=1
- comparison tool output captured

## Checkpoint Gate Summary
| step | status | actor_move | actor_noop | pos_delta | no_effect | continue_ok | candidate_ok | visual_verdict |
|---|---|---:|---:|---:|---:|---|---|---|
| 512 | FAIL_FALSE_FULL_TENSOR_MOVE | 0.0278 | 0.8889 | 0 | 1.0000 | False | False | n/a |

## Abort Criteria Checks
- FAIL_COLLAPSED_NOOP at 5k and 10k consecutively
- actor_level_move_share == 0 while ready_movable_actor_choice_count > 0
- effective_position_delta_count == 0
- no_effect_action_share > 0.80
