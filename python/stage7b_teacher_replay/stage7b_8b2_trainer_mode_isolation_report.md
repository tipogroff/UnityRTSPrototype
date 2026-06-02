# Stage7B-8B.2 Trainer Mode Isolation Report

status: GO
trainer_controlled_mode_prepared: true
scene_path: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity

## Before
- behavior_name_runtime: Stage7B_RTS_Student
- behavior_type_runtime: InferenceOnly
- decision_requester_enabled: true
- teacher_replay_orchestrator_enabled: false
- manual_loop_enabled: false
- watchdog_manual_fallback_enabled: false

## After
- behavior_name_runtime: Stage7B_RTS_Student
- behavior_type_runtime: Default
- decision_requester_enabled: true
- decision_period: 1
- teacher_replay_orchestrator_enabled_after_fix: false
- student_teacher_replay_orchestrator_is_null: true
- manual_loop_enabled: false
- watchdog_manual_fallback_enabled: false
- demo_mode_active: false

## Runtime Services
- runtime_services_ready: false
- missing_runtime_services: MatchManager, GridManager, UnitRegistry, ResourceManager
- collect_observations_probe_ok: true
- write_mask_probe_ok: true

## Safety
- stage6b3_baseline_touched: false
- notes: TrainerControlled preflight only. Training was not started.

generated_at_utc: 2026-05-11T14:29:23.6576574Z
