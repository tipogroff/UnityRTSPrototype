# Stage7B-8B.6 Episode Boundary Fix Report

status: NO-GO
ready_for_stage7b_8c: false

## Changed Files
- Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs
- Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs
- Assets/Scripts/MLAgents/Stage7B/Diagnostics/Stage7BResetTimeoutTrace.cs
- Assets/Scripts/MLAgents/Stage7B/Diagnostics/Stage7BTrainingFlowDiagnostics.cs
- python/stage7b_teacher_replay/stage7b_8b2_trainer_mode_isolation_report.json
- python/stage7b_teacher_replay/stage7b_8b2_trainer_mode_isolation_report.md
- Assets/ML-Agents/Timers/Week7_MLAgents_StudentVsScriptedBot_timers.json
- stage7b_mlagents_heuristic_dryrun.json

## Fix Summary
- MlAgentsTrainingBootstrap: TrainerControlled Start() now prepares runtime wiring only; full StartNewEpisode reset is guarded, reason/caller-traced, non-reentrant, and exposed through StartNewEpisodeForAgentReset().
- StudentMlAgent: OnEpisodeBegin now uses the explicit guarded trainer reset path instead of blindly calling StartNewEpisode().
- StudentMlAgent follow-up patch: after the completed rerun still showed no WriteDiscreteActionMask/OnActionReceived, a one-shot trainer-controlled RequestDecision kick was added for the next FixedUpdate after a successful guarded reset. This latest patch was not rerun-confirmed because Unity MCP Editor/Console operations were blocked by usage limit.
- Diagnostics: stage7b_8b6_lifecycle_trace.jsonl now records StartNewEpisode metrics, first WriteDiscreteActionMask frame/time, first OnActionReceived frame/time, and trainer-controlled kick count.

## Safety
- Stage6B3 baseline untouched: true
- teacher policy unchanged: true
- reward unchanged: true
- ActionApplier / MatchManager semantics unchanged: true
- MlAgentsCandidateActionBuilder unchanged: true
- clean demo dataset unchanged: true

## Pre-Run Diagnostics
- behavior_name_runtime: Stage7B_RTS_Student
- behavior_type_runtime: Default
- decision_requester_enabled: true
- decision_period: 1
- take_actions_between_decisions: false
- teacher_replay_orchestrator_enabled: false
- student_teacher_replay_orchestrator_is_null: true
- manual_loop_enabled: false
- watchdog_manual_fallback_enabled: false
- demo_mode_active: false
- runtime_services_ready: true
- match_state_after_reset: Running
- duplicate_spawn_detected: false
- C# compile confirmed before final one-shot patch: true
- C# compile confirmed after final one-shot patch: false, blocked by Unity MCP usage limit

## Trainer Command
python/stage7b_mlagents/.venv_mlagents/Scripts/mlagents-learn.exe config/stage7b_imitation_smoke.yaml --run-id Stage7B_ImitationSmoke_009 --force

## Completed Rerun Result
The completed 009 rerun happened after the guarded StartNewEpisode boundary fix and before the later one-shot RequestDecision kick patch.

- trainer_started: true
- config_loaded: true
- unity_connected: true
- behavior_name_matched: true
- training_steps_completed: 10000
- trainer_exit_code: 0
- trainer_exit_code_interpretation: clean exit with checkpoint and ONNX export
- UnityTimeOutException: false
- trainer_reset_env_timeout: false
- loss_nan_detected: false
- reward_nan_detected: false
- Unity Console errors: 0
- Unity Console warnings: 0

## Lifecycle Counters
- Awake: 1
- OnEnable: 2
- Start: 1
- Initialize: 2
- OnEpisodeBegin: 5
- CollectObservations: 2
- WriteDiscreteActionMask: 0
- Heuristic: 0
- OnActionReceived: 0
- EndEpisode: 0

## StartNewEpisode Boundary Metrics
- StartNewEpisode call count: 5
- skipped reentrant count: 0
- caller/reason summary: StudentMlAgent.OnEpisodeBegin / mlagents_on_episode_begin
- OnEpisodeBegin invoked safe reset path: trainer_controlled_guarded_full_reset
- trainer_controlled_kick_decision_request_count: not available in completed rerun; added after rerun

## Output Checks
- checkpoint_saved: true
- checkpoint_path: results/Stage7B_ImitationSmoke_009/Stage7B_RTS_Student/checkpoint.pt
- tfevents_saved: true
- tfevents_path: results/Stage7B_ImitationSmoke_009/Stage7B_RTS_Student/events.out.tfevents.1778490813.grozov.43268.0
- ONNX/export artifact saved: true
- ONNX/export artifact path: results/Stage7B_ImitationSmoke_009/Stage7B_RTS_Student.onnx
- checkpoint ONNX path: results/Stage7B_ImitationSmoke_009/Stage7B_RTS_Student/Stage7B_RTS_Student-10048.onnx

## Artifacts
- python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.json
- python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.md
- python/stage7b_teacher_replay/stage7b_8b6_lifecycle_trace.jsonl
- python/stage7b_teacher_replay/stage7b_8b6_imitation_smoke_trainer_009.log
- results/Stage7B_ImitationSmoke_009/

## Final Decision
NO-GO.

Exact remaining blocker: the completed rerun no longer hit reset_env timeout and did save/export, but WriteDiscreteActionMask and OnActionReceived remained zero. A one-shot trainer-controlled RequestDecision kick was added after that rerun, but the required confirmation rerun after this final patch could not be executed in this session because Unity MCP Editor/Console operations were blocked by usage limit.

Minimal next fix: rerun Stage7B_ImitationSmoke_009 after Unity recompiles the latest StudentMlAgent.cs patch. If WriteDiscreteActionMask and OnActionReceived remain zero, inspect whether StudentMlAgent.RequestDecision.trainer_controlled_kick is present in stage7b_8b6_lifecycle_trace.jsonl and whether ML-Agents consumes that request.
