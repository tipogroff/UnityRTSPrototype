# Stage7B-7D Clean Demo Recording Smoke Report

- status: GO
- generated_at_utc: 2026-05-10T22:29:33Z
- demo_file_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\Assets\Demonstrations\stage7b_teacher_replay_clean_smoke.demo
- demo_file_exists: true
- demo_file_size_bytes: 15068229
- behavior_name: Stage7B_RTS_Student
- observation_size: 15552
- discrete_branch_count: 1
- candidate_branch_size: 128
- source_path: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z
- source_replay_ready: true
- direction_mapping_mode: invert_y_for_legacy032_teacher
- produce_filtering_enabled: true
- started_from_edit_mode: false
- entered_play_mode: true
- play_mode_ready: true
- runtime_services_ready: true
- runtime_services_wait_seconds: 0
- missing_runtime_services: []
- resolved_runtime_services: [MatchManager, GridManager, UnitRegistry, MatchBootstrap, ResourceManager]
- startup_failure_reason: 
- unity_console_error_count: 0
- unity_console_warning_count: 0

## Recording Metrics

- episodes_scanned: 1
- steps_scanned: 512
- teacher_commands_total: 369
- matched_commands: 363
- recorded_decisions: 128
- dropped_commands: 6
- no_teacher_command_steps_skipped: 287

## Produce Filtering

- unsupported_worker_build_base_dropped: 3
- unity_one_barracks_cap_dropped: 3
- unclassified_produce_dropped: 0

## Runtime Apply

- runtime_apply_attempted_count: 128
- runtime_apply_accepted_count: 128
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: 1

## Action Type Breakdown

- return_commands_recorded: 8
- move_commands_recorded: 75
- harvest_commands_recorded: 10
- produce_commands_recorded: 35
- attack_commands_recorded: 0

## Drop Reason Histogram

- unsupported_worker_build_base: 3
- runtime_state_semantics_gap_unity_one_barracks_cap: 3

## GO / NO-GO Decision

- **status: GO**
- demo_recording_ready_for_imitation_smoke: true
- stage6b3_baseline_touched: false
- return_mapping_mode: invert_y_for_legacy032_teacher
- direction_mapping_mode: invert_y_for_legacy032_teacher

**Stage7B-8 small imitation smoke can proceed.**

## Notes

- DecisionRequester disabled by orchestrator (orchestrator controls timing).
- demonstration_recorder_component_found=true
- queue_size=363
- max_recorded_decisions=128
- ML-Agents training / PPO / imitation learning NOT started by this orchestrator.
- Stage6B3 baseline/checkpoint assets were NOT modified.
- Failed to copy temp demo to expected path: The process cannot access the file 'C:\Projects\UnityRTSPrototype\UnityRTSPrototype\Library\Stage7B_DemoRecordingTemp\stage7bteacherre_3.demo' because it is being used by another process.
