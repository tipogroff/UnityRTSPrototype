# Stage7B-8B.5 Unity Reset Timeout Root-Cause Diagnostic

status: DIAGNOSED_GO
decision: DIAGNOSED_GO
run_id: Stage7B_ImitationSmoke_008_ResetDiagnostic

## Command Used
- python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe config/stage7b_imitation_smoke.yaml --run-id Stage7B_ImitationSmoke_008_ResetDiagnostic --force

## Pre-Run Hygiene
- prepare_trainer_controlled_mode_menu_ran: true
- unity_console_cleared_before_run: true
- stale_python_trainers_cleared: true
- port_5004_prechecked_clear: true
- playmode_restarted_for_clean_run: true

## Pre-Run Diagnostics
- behavior_name_runtime: Stage7B_RTS_Student
- behavior_type_runtime: Default
- decision_requester_present: true
- decision_requester_enabled: true
- decision_period: 1
- take_actions_between_decisions: false
- teacher_replay_orchestrator_present: true
- teacher_replay_orchestrator_enabled: false
- student_teacher_replay_orchestrator_is_null: true
- manual_loop_enabled: false
- watchdog_manual_fallback_enabled: false
- demo_mode_active: false

## Trainer Result
- trainer_started: true
- config_loaded: false
- unity_connected: false
- behavior_name_matched: false
- training_steps_completed: 0
- timeout: true
- trainer_exit_code: 1
- trainer_exit_code_interpretation: UnityTimeOutException during TrainerController._reset_env

## Lifecycle Counters
- awake_count: 1
- start_count: 1
- on_enable_count: 2
- initialize_count: 2
- on_episode_begin_count: 9
- collect_observations_count: 2
- write_mask_count: 0
- heuristic_count: 0
- on_action_received_count: 0
- end_episode_count: 0

## Phase Classification
- timeout_phase_classification: before_communicator_after_collect_observations_before_write_discrete_action_mask
- last_lifecycle_event: StudentMlAgent.OnEpisodeBegin.exit
- first_missing_phase: StudentMlAgent.WriteDiscreteActionMask.enter
- communicator_on_observed: false
- academy_step_count: 16624
- current_decision_source: decision_requester

## Runtime State
- runtime_services_ready: true
- match_state_after_reset: Running
- duplicate_spawn_detected: false
- last_observation_length: 15552
- last_observation_nan_count: 0
- stage6b3_baseline_touched: false

## Exact Remaining Blocker
The environment completes reset into MatchPhase.Running and emits observations, but the first trainer-controlled decision cycle never advances to WriteDiscreteActionMask or OnActionReceived while Academy continues stepping and Academy.IsCommunicatorOn remains false. Python stays blocked inside TrainerController._reset_env waiting for the first environment step.

## Minimal Next Fix
Patch the Stage7B bootstrap/agent boundary that re-enters StartNewEpisode from OnEpisodeBegin under trainer control so the first communicator-owned decision cycle can reach WriteDiscreteActionMask.

## Artifacts
- trainer_log: python/stage7b_teacher_replay/stage7b_8b5_imitation_smoke_trainer_008.log
- lifecycle_trace_path: python/stage7b_teacher_replay/stage7b_8b5_lifecycle_trace.jsonl
- results_dir: results/Stage7B_ImitationSmoke_008_ResetDiagnostic

generated_utc: 2026-05-11T08:54:25.8301441Z
