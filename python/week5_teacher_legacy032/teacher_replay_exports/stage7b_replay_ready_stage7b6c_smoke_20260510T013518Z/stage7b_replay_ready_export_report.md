# Stage7B Replay-Ready Teacher Export Report

- generated_at_utc: 2026-05-10T01:35:20Z
- run_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6c_smoke_20260510T013518Z
- episodes_exported: 1
- steps_exported: 64
- replay_ready: False

## Contracts
- observation_shape: [24, 24, 27]
- action_shape: [576, 7]
- branch_sizes: [6, 4, 4, 4, 4, 7, 49]
- attack_target_size: 49

## Presence Flags
- initial_state_present: False
- pre_state_present: False
- post_state_present: False
- teacher_command_list_present: True
- terminal_metadata_present: True

## Diagnostics
- nonnoop_steps: 64
- multiple_nonnoop_steps: 64
- mean_teacher_command_count_per_step: 479.390625
- action_type_histogram: {'1': 6139, '2': 6162, '3': 6107, '4': 6089, '5': 6184}

## Validation Errors
- initial_state missing
- runtime_state_t missing
- runtime_state_tp1 missing
- episode_00000.replay_ready.npz: missing key nonoop_actor_count_t

## Validation Warnings
- episode_00000.replay_ready.npz: initial_state_json not exported
- episode_00000.replay_ready.npz: runtime_state_t_json not exported
- episode_00000.replay_ready.npz: runtime_state_tp1_json not exported
