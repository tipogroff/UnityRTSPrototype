# Stage7B Teacher Replay Prep Report (After 6G)

## Status

- stage: Stage7B-6B-Rerun
- status: NO_GO
- generated_at_utc: 2026-05-10T13:42:49Z
- summary: Replay-ready source validated; offline prep pass completed. Unity runtime state synchronization/candidate matching were not executed in this run.

## Source

- source_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6g_smoke_20260510T131624Z
- replay_ready: True
- replay_manifest: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6g_smoke_20260510T131624Z/replay_manifest.json

## Metrics

- episodes_scanned: 1
- episodes_replay_attempted: 1
- steps_total: 64
- steps_replay_attempted: 64
- teacher_commands_total: 9
- teacher_nonnoop_commands_total: 9
- state_sync_success_count: 0
- state_sync_failed_count: 64
- pre_observation_match_count: 0
- pre_observation_mismatch_count: 0
- candidate_count_min: None
- candidate_count_mean: None
- candidate_count_max: None
- candidate_overflow_count: 0
- candidate_match_count: 0
- candidate_drop_count: 9
- candidate_match_rate: None
- nonoop_candidate_match_count: 0
- nonoop_candidate_match_rate: None
- runtime_apply_attempted_count: 0
- runtime_apply_accepted_count: 0
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: None
- post_state_match_count: 0
- post_state_mismatch_count: 0
- terminal_match_count: 63
- terminal_mismatch_count: 1
- demo_recording_ready: False

## Drop Reason Histogram

- action_not_legal_in_unity: 0
- action_type_unsupported: 0
- actor_not_found: 0
- actor_owner_mismatch: 0
- actor_type_mismatch: 0
- attack_target_mismatch: 0
- candidate_overflow: 0
- direction_mismatch: 0
- manifest_contract_mismatch: 0
- missing_initial_state: 0
- missing_runtime_state_t: 0
- missing_runtime_state_tp1: 0
- missing_teacher_commands: 0
- no_matching_candidate: 0
- observation_mismatch: 0
- post_state_desync: 0
- produce_type_mismatch: 0
- runtime_apply_rejected: 0
- source_not_replay_ready: 0
- state_sync_failed: 9
- terminal_mismatch: 1
- unknown: 0

## Notes

- ML-Agents training/PPO/imitation/.demo were not started.
- Stage6B3 baseline/checkpoint files were not modified by this script.
- Candidate truth must be measured from Unity MlAgentsCandidateActionBuilder on synchronized runtime state; this offline pass only validates replay-ready source and measures source-side counters.
