# Stage7B-8C.2 Unity Inference Smoke Report

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
- observation_zero_padding_warning_detected: false
- actual_collect_trace_path: python/stage7b_teacher_replay/stage7b_8d1_actual_collect_observations_trace.jsonl
- actual_collect_calls: 6206
- actual_collect_all_expected_values: true
- zero_fallback_used: false
- defensive_pre_ready_observation_count: 0
- defensive_pre_ready_observation_used_after_runtime_ready: true
- warning_padding_first_frame: -1
- warning_padding_first_academy_step: -1

## Lifecycle
- initialize_count: 3
- on_episode_begin_count: 3
- collect_observations_count: 6228
- write_discrete_action_mask_count: 6224
- on_action_received_count: 6224
- heuristic_call_count: 0
- inference_kick_decision_request_count: 3
- inference_runtime_ready_observed: true
- inference_first_ready_frame: 2
- inference_first_ready_fixed_tick: 1
- decision_requester_enabled_runtime: true

## Action Cycle
- candidate_action_index_last: 29
- candidate_action_index_in_range: true
- candidate_branch_size: 128
- candidate_builder_success_count: 12448
- action_adapter_success_count: 6224
- runtime_apply_attempted: 6224
- runtime_apply_accepted: 6224
- runtime_apply_rejected: 0

## Fallback Guards
- teacher_replay_orchestrator_enabled: false
- manual_loop_enabled: false
- watchdog_manual_fallback_enabled: false
- demo_mode_active: false
- heuristic_warning_detected: false

## Console
- unity_console_errors: 0
- unity_console_warnings: 4
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

generated_at_utc: 2026-06-01T22:46:40.2895170Z
