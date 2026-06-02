# Stage7B Replay-Ready Teacher Export Report

- generated_at_utc: 2026-05-10T01:35:57Z
- run_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6c_smoke_20260510T013556Z
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
- nonnoop_steps: 6
- multiple_nonnoop_steps: 2
- mean_teacher_command_count_per_step: 0.140625
- action_type_histogram: {'1': 4, '2': 2, '3': 1, '4': 2}

## Validation Errors
- initial_state missing
- runtime_state_t missing
- runtime_state_tp1 missing

## Validation Warnings
- episode_00000.replay_ready.npz: initial_state_json not exported
- episode_00000.replay_ready.npz: runtime_state_t_json not exported
- episode_00000.replay_ready.npz: runtime_state_tp1_json not exported
