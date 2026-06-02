# Stage7B-8B.6 Episode Boundary Fix Diagnostic

status: DIAGNOSED
suspected_blocker: agent_not_participating_decision_requester_disabled
trainer_connected: false
behavior_name_runtime: unknown
behavior_type_runtime: unknown
decision_requester_enabled: false
teacher_replay_orchestrator_present: false
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
- bootstrap_start_new_episode_count: 0
- bootstrap_start_new_episode_skipped_reentrant_count: 0
- bootstrap_start_new_episode_reason: 
- bootstrap_start_new_episode_caller: 
- bootstrap_start_new_episode_path: 
- bootstrap_has_runtime_episode_started: false
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
- missing_runtime_services: MlAgentsTrainingBootstrap
- match_state_after_reset: unknown
- duplicate_spawn_detected: false

generated_utc: 2026-06-02T17:53:48.8837835Z
