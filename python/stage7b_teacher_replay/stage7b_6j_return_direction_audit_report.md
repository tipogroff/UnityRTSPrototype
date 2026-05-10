# Stage7B-6J Return Direction Mismatch Audit Report

- status: GO
- generated_at_utc: 2026-05-10T18:56:38Z
- source: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z

## General Metrics

- episodes_scanned: 8
- episodes_replay_attempted: 8
- steps_total: 4096
- steps_replay_attempted: 4096
- teacher_commands_total: 2952
- teacher_nonnoop_commands_total: 2952
- no_teacher_command_steps: 2383
- state_sync_success_count: 4096
- state_sync_failed_count: 0
- candidate_count_min: 10
- candidate_count_mean: 36.13989
- candidate_count_max: 70
- candidate_match_count: 2396
- candidate_drop_count: 1088
- candidate_match_rate: 0.811653
- nonnoop_candidate_match_rate: 0.811653
- runtime_apply_attempted_count: 2396
- runtime_apply_accepted_count: 2396
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: 1
- total_mismatches: 556
- no_matching_candidate_count: 556
- direction_mismatch_count: 385
- post_state_match_count: 1181
- post_state_mismatch_count: 532
- terminal_match_count: 1713
- terminal_mismatch_count: 0
- demo_recording_ready: true

## Return Direction Audit

- return_commands_total: 134
- return_commands_matched: 134
- return_commands_dropped: 0
- return_match_rate: 1
- return_direction_mismatch_count: 0
- return_direction_mismatch_rate: 0
- opposite_direction_count: 0
- y_axis_flip_suspected_count: 0
- x_axis_flip_suspected_count: 0
- teacher_target_outside_map_count: 0
- unity_target_outside_map_count: 0
- target_cell_has_base_teacher_side_count: 0
- target_cell_has_base_unity_side_count: 0
- pattern_hypothesis: no_return_direction_mismatches

### Mismatch by Action Type

- move: 222
- harvest: 51
- produce: 283

### Mismatch by Teacher Direction

- South: 294
- North: 116
- East: 116
- West: 30

### Return Mismatch by Teacher Direction


### Return Mismatch by Candidate Direction


## GO / HOLD Decision

**Decision: GO_TO_STAGE7B_7: return_direction_mismatch_rate=0 is low. Return mismatches are non-blocking. Demo recording can proceed.**

## First Return Direction Mismatches (up to 10)

- (none)
## first_10_return_mismatches

- (none)
## Drop Reasons

- post_state_desync: 532
- no_matching_candidate: 556

## Notes

- Stage7B-6J: Return direction mismatch audit. Runtime apply enabled.
- ML-Agents training/PPO/imitation/.demo were not started by this runner.
- post_state_comparison_mode=partial: unit count, resource node count, player resources, terminal checked.
- Stage7B-6K: Return-only mapping mode is invert_y_for_legacy032_teacher.
- no_teacher_command_steps classified separately, not counted in candidateDropCount.
- Stage6B3 baseline/checkpoint assets were not modified by this runner.
