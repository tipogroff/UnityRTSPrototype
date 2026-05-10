# Stage7B-6I Runtime Apply Validation Report

- status: GO
- generated_at_utc: 2026-05-10T17:27:21Z
- source: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6g_smoke_20260510T131624Z
- post_state_comparison_mode: partial

## Metrics

- episodes_scanned: 1
- episodes_replay_attempted: 1
- steps_total: 64
- steps_replay_attempted: 64
- teacher_commands_total: 9
- teacher_nonnoop_commands_total: 9
- no_teacher_command_steps: 58
- state_sync_success_count: 64
- state_sync_failed_count: 0
- candidate_count_min: 10
- candidate_count_mean: 14.1875
- candidate_count_max: 22
- candidate_match_count: 8
- candidate_drop_count: 3
- candidate_match_rate: 0.888889
- nonnoop_candidate_match_rate: 0.888889
- runtime_apply_attempted_count: 8
- runtime_apply_accepted_count: 8
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: 1
- first_runtime_reject_step: none
- first_runtime_reject_action_summary: none
- post_state_match_count: 4
- post_state_mismatch_count: 2
- terminal_match_count: 6
- terminal_mismatch_count: 0
- demo_recording_ready: true

## Drop Reasons

- post_state_desync: 2
- no_matching_candidate: 1

## Runtime Reject Reason Histogram

- (none)

## Rejected Action Type Histogram

- (none)

## Candidate Mismatch Diagnoses

### Mismatch 1: episode=0 step=30
- actor_flat: 26
- actor_x: 2, actor_y: 1
- action_type: 3 (return)
- drop_reason: no_matching_candidate
- nearest_candidate_reason: direction_mismatch (actor=(2, 1), type=Return, teacher_dir=South, cand_dir=North)
- candidate_count_at_step: 11
- candidate_list_summary: [{idx=0,pos=(0, 0),type=NoOp}, {idx=1,pos=(2, 1),type=Move}, {idx=2,pos=(2, 1),type=Move}, {idx=3,pos=(2, 1),type=Move}, {idx=4,pos=(2, 1),type=Return}, {idx=5,pos=(2, 1),type=Produce}, {idx=6,pos=(2, 1),type=Produce}, {idx=7,pos=(2, 1),type=Produce}, {idx=8,pos=(2, 2),type=Produce}, {idx=9,pos=(2, 2),type=Produce}, {idx=10,pos=(2, 2),type=Produce}]

## Notes

- Stage7B-6I: runtime apply mode enabled. ActionApplier.ApplyAction called for each matched candidate.
- ML-Agents training/PPO/imitation/.demo were not started by this runner.
- post_state_comparison_mode=partial: unit count, resource node count, player resources, terminal checked. Per-unit x/y not compared.
- no_teacher_command_steps classified separately, not counted in candidateDropCount.
- Stage6B3 baseline/checkpoint assets were not modified by this runner.
