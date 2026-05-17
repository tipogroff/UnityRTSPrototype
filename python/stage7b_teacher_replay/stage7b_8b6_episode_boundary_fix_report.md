# Stage7B-8B.6 Episode Boundary Fix Diagnostic

status: DIAGNOSED
suspected_blocker: agent_not_participating_decision_requester_disabled
trainer_connected: false
behavior_name_runtime: unknown
behavior_type_runtime: unknown
decision_requester_enabled: false
teacher_replay_orchestrator_present: true
teacher_replay_orchestrator_enabled: false
student_teacher_replay_orchestrator_is_null: true

## Counters
- on_enable_count: 0
- awake_count: 0
- start_count: 0
- initialize_count: 0
- on_episode_begin_count: 0
- collect_observations_count: 0
- write_mask_count: 0
- heuristic_count: 0
- on_action_received_count: 0
- end_episode_count: 0
- first_write_mask_frame: 0
- first_write_mask_time: 0
- first_on_action_received_frame: 0
- first_on_action_received_time: 0

## StartNewEpisode Boundary
- bootstrap_start_new_episode_count: 4
- bootstrap_start_new_episode_skipped_reentrant_count: 0
- bootstrap_start_new_episode_reason: agent_on_episode_begin
- bootstrap_start_new_episode_caller: StudentMlAgent.OnEpisodeBegin
- bootstrap_start_new_episode_path: runtime_full_reset
- bootstrap_has_runtime_episode_started: true
- on_episode_begin_start_new_episode_called: false
- on_episode_begin_start_new_episode_result: false
- trainer_controlled_episode_reset_path: false
- on_episode_begin_start_new_episode_path: 
- trainer_controlled_kick_decision_request_count: 0

## Timeout Classification
- timeout_phase_classification: before_unity_connect_before_on_episode_begin
- last_lifecycle_event: StudentMlAgent.CollectObservations.exit
- lifecycle_trace_path: python/stage7b_teacher_replay/stage7b_8b6_lifecycle_trace.jsonl

## Runtime Services
- runtime_services_ready: false
- missing_runtime_services: StudentMlAgent
- match_state_after_reset: Running
- duplicate_spawn_detected: false

generated_utc: 2026-05-17T14:48:20.6540685Z
