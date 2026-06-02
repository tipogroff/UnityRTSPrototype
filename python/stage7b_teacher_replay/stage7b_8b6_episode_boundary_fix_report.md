# Stage7B-8B.6 Episode Boundary Fix Diagnostic

status: IN_PROGRESS
suspected_blocker: unknown
trainer_connected: false
behavior_name_runtime: Stage7B_RTS_Student
behavior_type_runtime: InferenceOnly
decision_requester_enabled: true
teacher_replay_orchestrator_present: true
teacher_replay_orchestrator_enabled: false
student_teacher_replay_orchestrator_is_null: true

## Counters
- on_enable_count: 3
- awake_count: 1
- start_count: 1
- initialize_count: 3
- on_episode_begin_count: 2
- collect_observations_count: 471
- write_mask_count: 468
- heuristic_count: 0
- on_action_received_count: 468
- end_episode_count: 1
- first_write_mask_frame: 332
- first_write_mask_time: 14,43719
- first_on_action_received_frame: 332
- first_on_action_received_time: 14,46082

## StartNewEpisode Boundary
- bootstrap_start_new_episode_count: 2
- bootstrap_start_new_episode_skipped_reentrant_count: 0
- bootstrap_start_new_episode_reason: agent_on_episode_begin
- bootstrap_start_new_episode_caller: StudentMlAgent.OnEpisodeBegin
- bootstrap_start_new_episode_path: runtime_full_reset
- bootstrap_has_runtime_episode_started: true
- on_episode_begin_start_new_episode_called: true
- on_episode_begin_start_new_episode_result: true
- trainer_controlled_episode_reset_path: false
- on_episode_begin_start_new_episode_path: runtime_full_reset
- trainer_controlled_kick_decision_request_count: 0

## Timeout Classification
- timeout_phase_classification: before_communicator_after_on_action_received_or_later
- last_lifecycle_event: StudentMlAgent.OnActionReceived.exit
- lifecycle_trace_path: python/stage7b_teacher_replay/stage7b_8b6_lifecycle_trace.jsonl

## Runtime Services
- runtime_services_ready: true
- missing_runtime_services: none
- match_state_after_reset: Running
- duplicate_spawn_detected: false

generated_utc: 2026-06-02T17:49:05.2484235Z
