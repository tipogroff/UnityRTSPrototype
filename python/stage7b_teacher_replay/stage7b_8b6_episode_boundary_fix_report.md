# Stage7B-8B.6 Episode Boundary Fix Diagnostic

status: IN_PROGRESS
suspected_blocker: unknown
trainer_connected: false
behavior_name_runtime: Stage7B_RTS_Student
behavior_type_runtime: Default
decision_requester_enabled: true
teacher_replay_orchestrator_present: true
teacher_replay_orchestrator_enabled: false
student_teacher_replay_orchestrator_is_null: true

## Counters
- on_enable_count: 2
- awake_count: 1
- start_count: 1
- initialize_count: 2
- on_episode_begin_count: 1
- collect_observations_count: 3
- write_mask_count: 2
- heuristic_count: 0
- on_action_received_count: 2
- end_episode_count: 0
- first_write_mask_frame: 1
- first_write_mask_time: 14,30802
- first_on_action_received_frame: 1
- first_on_action_received_time: 14,34454

## StartNewEpisode Boundary
- bootstrap_start_new_episode_count: 1
- bootstrap_start_new_episode_skipped_reentrant_count: 0
- bootstrap_start_new_episode_reason: mlagents_on_episode_begin
- bootstrap_start_new_episode_caller: StudentMlAgent.OnEpisodeBegin
- bootstrap_start_new_episode_path: trainer_controlled_guarded_full_reset
- bootstrap_has_runtime_episode_started: true
- on_episode_begin_start_new_episode_called: true
- on_episode_begin_start_new_episode_result: true
- trainer_controlled_episode_reset_path: true
- on_episode_begin_start_new_episode_path: trainer_controlled_guarded_full_reset
- trainer_controlled_kick_decision_request_count: 1

## Timeout Classification
- timeout_phase_classification: before_communicator_after_on_action_received_or_later
- last_lifecycle_event: StudentMlAgent.OnActionReceived.exit
- lifecycle_trace_path: python/stage7b_teacher_replay/stage7b_8b6_lifecycle_trace.jsonl

## Runtime Services
- runtime_services_ready: true
- missing_runtime_services: none
- match_state_after_reset: Running
- duplicate_spawn_detected: false

generated_utc: 2026-05-11T19:20:27.2248518Z
