# Stage7B-8B.1 Training Flow Diagnostic

status: DIAGNOSED
suspected_blocker: runtime_services_missing_in_reset_path
trainer_connected: false
behavior_name_runtime: Stage7B_RTS_Student
behavior_type_runtime: HeuristicOnly
decision_requester_enabled: false
teacher_replay_orchestrator_present: true
teacher_replay_orchestrator_enabled: true
student_teacher_replay_orchestrator_is_null: true

## Counters
- on_enable_count: 2
- initialize_count: 2
- on_episode_begin_count: 13
- collect_observations_count: 3156
- write_mask_count: 3143
- heuristic_count: 3143
- on_action_received_count: 3143

## Runtime Services
- runtime_services_ready: false
- missing_runtime_services: GridManager
- match_state_after_reset: Running
- duplicate_spawn_detected: false

generated_utc: 2026-05-10T23:19:38.2938606Z
