# Stage7B Teacher Replay Prep Report

## Status

- stage: Stage7B-6B Prep
- status: NO_GO
- generated_at_utc: 2026-05-10T01:16:02Z
- summary: No replay-ready trajectory source with authoritative runtime state; new export with replay fields required.

## Source Selection

- selected_source_path: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260501T125015Z
- selected_source_format: legacy032_teacher_rollout_raw
- source_inventory: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/stage7b_teacher_replay/stage7b_teacher_replay_source_inventory.json

## Contract

- candidate_branch_size: 128
- candidate_noop_index: 0
- attack_target_size: 49
- attack_target_center_index: 24
- branch_sizes: [6, 4, 4, 4, 4, 7, 49]

## Metrics

- episodes_scanned: 16
- episodes_replay_attempted: 0
- steps_total: 88165
- steps_replay_attempted: 0
- state_sync_success_count: 0
- state_sync_failed_count: 0
- candidate_match_count: 0
- candidate_drop_count: 512
- candidate_match_rate: None
- nonoop_total: 512
- nonoop_candidate_match_count: 0
- nonoop_candidate_match_rate: None
- runtime_apply_attempted_count: 0
- runtime_apply_accepted_count: 0
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: None
- candidate_count_min: None
- candidate_count_mean: None
- candidate_count_max: None
- candidate_overflow_count: 0
- terminal_match_count: 0
- terminal_mismatch_count: 0
- demo_recording_ready: False

## Drop Reasons

- action_not_legal_in_unity: 0
- action_type_unsupported: 0
- attack_target_contract_mismatch: 0
- attack_target_mismatch: 0
- branch_contract_mismatch: 0
- candidate_overflow: 0
- direction_mismatch: 0
- missing_initial_state: 0
- missing_runtime_state: 0
- missing_teacher_action: 0
- multiple_nonnoop_actors: 512
- no_matching_actor: 0
- observation_mismatch: 0
- produce_type_mismatch: 0
- runtime_apply_rejected: 0
- runtime_desync: 0
- source_schema_unknown: 0
- state_sync_failed: 0
- teacher_noop: 0
- terminal_mismatch: 0
- unknown: 0
- unsupported_action_format: 0

## Action Breakdown

### match_by_action_type
- none

### drop_by_action_type
- Mixed: 512

## NO-GO Reasons

- missing_initial_state
- missing_runtime_state
- state_sync_failed

## Notes

- ML-Agents training/PPO/imitation/demo were not started in this prep package build.
- Candidate truth must come from Unity runtime MlAgentsCandidateActionBuilder on synchronized state.
- This package is a prep gate artifact, not a training artifact.
