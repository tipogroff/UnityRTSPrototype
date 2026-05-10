# Stage7B-6K Return Direction Fix Report

- status: GO
- generated_at_utc: 2026-05-10T18:56:38Z
- source: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z
- return_direction_mapping_mode: invert_y_for_legacy032_teacher
- return_direction_mapping_applied_count: 134

## Before vs After

| metric | before_6j | after_6k |
|---|---:|---:|
| candidate_match_count | 2334 | 2396 |
| candidate_match_rate | 0.79065 | 0.811653 |
| return_commands_matched | 72 | 134 |
| return_commands_dropped | 62 | 0 |
| return_match_rate | 0.537314 | 1 |
| return_direction_mismatch_count | 62 | 0 |
| return_direction_mismatch_rate | 0.462687 | 0 |
| runtime_apply_accept_rate | 1 | 1 |

## Required Metrics

- return_commands_total: 134
- runtime_apply_attempted_count: 2396
- runtime_apply_accepted_count: 2396
- runtime_apply_rejected_count: 0
- state_sync_success_count: 4096
- state_sync_failed_count: 0
- demo_recording_ready: true

## Remaining Mismatch Breakdown

- move: 222
- harvest: 51
- produce: 283

## First Remaining Return Mismatches

- (none)

## Decision

**Decision: GO_TO_STAGE7B_7**

## Notes

- Stage7B-6J: Return direction mismatch audit. Runtime apply enabled.
- ML-Agents training/PPO/imitation/.demo were not started by this runner.
- post_state_comparison_mode=partial: unit count, resource node count, player resources, terminal checked.
- Stage7B-6K: Return-only mapping mode is invert_y_for_legacy032_teacher.
- no_teacher_command_steps classified separately, not counted in candidateDropCount.
- Stage6B3 baseline/checkpoint assets were not modified by this runner.
