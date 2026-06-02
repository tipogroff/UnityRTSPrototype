# Stage7B-8C.2 Unity Inference Smoke Report

final_decision: NO_GO
ready_for_stage7b_8d_or_9: false
blocker_code: A
blocker_reason: Model not assigned or import failed

## Model
- onnx_source_path: results/Stage7B_ImitationSmoke_010_PostKickConfirm/Stage7B_RTS_Student.onnx
- unity_model_asset_path: Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx
- model_copied_into_assets: true
- unity_import_succeeded: true
- model_assigned: false
- model_asset_path_runtime: 
- behavior_type_runtime: missing
- behavior_name_runtime: missing

## Observations
- observation_length_expected: 15552
- observation_values_written_by_agent: 0
- observation_nan_count: 0
- observation_source: missing_agent
- observation_zero_padding_warning_detected: false
- actual_collect_trace_path: python/stage7b_teacher_replay/stage7b_8d1_actual_collect_observations_trace.jsonl
- actual_collect_calls: 6206
- actual_collect_all_expected_values: true
- zero_fallback_used: false
- defensive_pre_ready_observation_count: 0
- defensive_pre_ready_observation_used_after_runtime_ready: false
- warning_padding_first_frame: -1
- warning_padding_first_academy_step: -1

## Lifecycle
- initialize_count: 0
- on_episode_begin_count: 0
- collect_observations_count: 0
- write_discrete_action_mask_count: 0
- on_action_received_count: 0
- heuristic_call_count: 0
- inference_kick_decision_request_count: 0
- inference_runtime_ready_observed: false
- inference_first_ready_frame: -1
- inference_first_ready_fixed_tick: -1
- decision_requester_enabled_runtime: false

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
- warning_fewer_observations_0_detected: false
- warning_heuristic_not_implemented_detected: false
- timeout_error_log_count: 0
- timeout_spam_detected: false

## Artifacts
- report_json: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json
- report_md: python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.md
- lifecycle_trace_jsonl: python/stage7b_teacher_replay/stage7b_8d1_inference_lifecycle_trace.jsonl
- actual_collect_trace_jsonl: python/stage7b_teacher_replay/stage7b_8d1_actual_collect_observations_trace.jsonl
- agent_inventory_json: python/stage7b_teacher_replay/stage7b_8d1_agent_inventory.json

generated_at_utc: 2026-06-02T16:45:09.7293741Z
