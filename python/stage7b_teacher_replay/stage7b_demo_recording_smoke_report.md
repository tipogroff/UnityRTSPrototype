# Stage7B-7D Clean Demo Recording Smoke Report

- status: NO_GO
- generated_at_utc: 2026-05-12T18:24:09Z
- demo_file_path: Assets/Demonstrations/stage7b_teacher_replay_smoke.demo
- demo_file_exists: false
- demo_file_size_bytes: 0
- behavior_name: Stage7B_RTS_Student
- observation_size: 15552
- discrete_branch_count: 1
- candidate_branch_size: 128
- source_path: python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z
- source_replay_ready: false
- direction_mapping_mode: invert_y_for_legacy032_teacher
- produce_filtering_enabled: true
- started_from_edit_mode: false
- entered_play_mode: true
- play_mode_ready: true
- runtime_services_ready: false
- runtime_services_wait_seconds: 15.25
- missing_runtime_services: [MatchManager, GridManager, UnitRegistry, MatchBootstrap, ResourceManager]
- resolved_runtime_services: []
- startup_failure_reason: runtime_services_timeout: missing=MatchManager,GridManager,UnitRegistry,MatchBootstrap,ResourceManager
- unity_console_error_count: 0
- unity_console_warning_count: 0

## Recording Metrics

- episodes_scanned: 0
- steps_scanned: 0
- teacher_commands_total: 0
- matched_commands: 0
- recorded_decisions: 0
- dropped_commands: 0
- no_teacher_command_steps_skipped: 0

## Produce Filtering

- unsupported_worker_build_base_dropped: 0
- unity_one_barracks_cap_dropped: 0
- unclassified_produce_dropped: 0

## Runtime Apply

- runtime_apply_attempted_count: 0
- runtime_apply_accepted_count: 0
- runtime_apply_rejected_count: 0
- runtime_apply_accept_rate: n/a

## Action Type Breakdown

- return_commands_recorded: 0
- move_commands_recorded: 0
- harvest_commands_recorded: 0
- produce_commands_recorded: 0
- attack_commands_recorded: 0

## Drop Reason Histogram

- (none)

## GO / NO-GO Decision

- **status: NO_GO**
- demo_recording_ready_for_imitation_smoke: false
- stage6b3_baseline_touched: false
- return_mapping_mode: invert_y_for_legacy032_teacher
- direction_mapping_mode: invert_y_for_legacy032_teacher

**HOLD — Review NO-GO criteria above before proceeding.**

## Notes

- Unity runtime services remained unavailable until timeout. Missing: MatchManager, GridManager, UnitRegistry, MatchBootstrap, ResourceManager
