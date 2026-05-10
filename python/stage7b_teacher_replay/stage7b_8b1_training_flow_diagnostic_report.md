# Stage7B-8B.1 Training Flow Diagnostic Report

Status: GO (blocker category identified)

## Summary
- Trainer process connected to Unity successfully during Diagnostic_002.
- Runtime loop executed locally (CollectObservations/Mask/Heuristic/OnActionReceived counts advanced significantly).
- Runtime Behavior Type is HeuristicOnly, not Default.
- Stage7BTeacherReplayDemoOrchestrator exists in the scene and is enabled.
- DecisionRequester is disabled at runtime while decision source moved to watchdog manual fallback.
- This is consistent with a Stage7 demo/training mode conflict that prevents the expected trainer-driven reset/action path.

## Core Findings
- trainer_connected: true
- trainer_timeout_reproduced: false in Diagnostic_002 (run ended by manual interruption), but previously reproduced in Stage7B_ImitationSmoke_001/002/003
- behavior_name_runtime: Stage7B_RTS_Student
- behavior_type_runtime: HeuristicOnly
- decision_requester_present: true
- decision_requester_enabled: false
- decision_period: 1
- take_actions_between_decisions: false
- teacher_replay_orchestrator_present: true
- teacher_replay_orchestrator_enabled: true
- student_teacher_replay_orchestrator_is_null: true
- manual_loop_enabled: true (decision source watchdog manual fallback)
- demo_mode_active: false

## Counter Table
- OnEpisodeBegin: 13
- CollectObservations: 3143
- WriteMask: 3143
- OnActionReceived: 3143
- Heuristic: 3143

## Reset/Runtime Services
- runtime_services_ready: true
- missing_runtime_services: []
- match_state_after_reset: Running
- duplicate_spawn_detected: false
- first_reset_duration_ms: 1.3046
- first_observation_duration_ms: 3.3895
- first_on_action_received_time: 5.174040794372559

## Console
- unity_console_errors: 1
- unity_console_warnings: 0
- Additional asserts were logged during teardown; no protocol mismatch errors.

## Suspected Blocker
runtime_behavior_type_not_default_and_stage7_demo_orchestrator_present

## Recommended Exact Fix
1. In training path, enforce Student Behavior Type = Default at runtime (not HeuristicOnly).
2. Disable or remove Stage7BTeacherReplayDemoOrchestrator in the Week7 training scene for imitation smoke runs.
3. Keep DecisionRequester enabled for trainer mode, and prevent watchdog/manual fallback from taking over before first trainer-driven step.
4. Re-run Stage7B-8B smoke after these mode-isolation fixes.

## Safety Confirmation
- Stage6B3 baseline untouched: yes
- no long training: yes
- no PPO fine-tune: yes
- clean demo unchanged: yes
