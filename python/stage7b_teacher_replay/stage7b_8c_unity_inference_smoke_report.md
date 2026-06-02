# Stage7B-8C Unity Inference Smoke Report

final_decision: NO_GO
ready_for_stage7b_8d_or_9: false
blocker_code: C
blocker_reason: CollectObservations did not provide full real observation without padding

## Model
- onnx_source_path: results/Stage7B_ImitationSmoke_010_PostKickConfirm/Stage7B_RTS_Student.onnx
- unity_model_asset_path: Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx
- model_copied_into_assets: true
- unity_import_succeeded: true
- model_assigned: true
- model_asset_path_runtime: Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx
- behavior_type_runtime: InferenceOnly
- behavior_name_runtime: Stage7B_RTS_Student

## Observations
- observation_length_expected: 15552
- observation_values_written_by_agent: 15552
- observation_nan_count: 0
- observation_source: ObservationBuilder/runtime_state
- observation_zero_padding_warning_detected: true

## Lifecycle
- initialize_count: 2
- on_episode_begin_count: 1
- collect_observations_count: 1
- write_discrete_action_mask_count: 0
- on_action_received_count: 0
- heuristic_call_count: 0

## Action Cycle
- candidate_action_index_last: -1
- candidate_action_index_in_range: false
- candidate_branch_size: 128
- candidate_builder_success_count: 0
- action_adapter_success_count: 0
- runtime_apply_attempted: 0
- runtime_apply_accepted: 0
- runtime_apply_rejected: 0

## Fallback Guards
- teacher_replay_orchestrator_enabled: false
- manual_loop_enabled: false
- watchdog_manual_fallback_enabled: false
- demo_mode_active: false
- heuristic_warning_detected: false

## Console
- unity_console_errors: 0
- unity_console_warnings: 2
- warning_fewer_observations_0_detected: true
- warning_heuristic_not_implemented_detected: false

## Artifacts
- report_json: python/stage7b_teacher_replay/stage7b_8c_unity_inference_smoke_report.json
- report_md: python/stage7b_teacher_replay/stage7b_8c_unity_inference_smoke_report.md
- lifecycle_trace_jsonl: python/stage7b_teacher_replay/stage7b_8c_inference_lifecycle_trace.jsonl

generated_at_utc: 2026-05-11T10:53:28.5278006Z
