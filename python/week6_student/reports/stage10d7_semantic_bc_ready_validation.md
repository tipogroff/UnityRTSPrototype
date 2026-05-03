# Stage10D.7 Semantic BC-ready Validation

- status: pass
- bc_ready_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z

## File Checks
- bc_ready_dir_exists: True
- bc_manifest_exists: True
- bc_train_exists: True
- bc_validation_exists: True
- bc_debug_exists: True

## Contract Checks
- schema_version_day6_bc_ready_v1: True
- manifest_dataset_kind_semantic_bc_ready: True
- manifest_source_stage_10D7: True
- manifest_source_adapted_dataset_stage_10D6: True
- manifest_observation_semantics_version: True
- manifest_mapping_spec_version: True
- manifest_observation_shape: True
- manifest_action_shape: True
- manifest_branch_sizes: True
- train_shape: True
- validation_shape: True
- debug_shape: True
- obs_dtype_float32_train: True
- obs_dtype_float32_validation: True
- obs_dtype_float32_debug: True
- actions_integer_compatible_train: True
- actions_integer_compatible_validation: True
- actions_integer_compatible_debug: True
- obs_no_nan: True
- obs_no_inf: True
- obs_range_0_1: True
- manifest_count_train_match: True
- manifest_count_validation_match: True
- manifest_count_debug_match: True
- branch_0_range: True
- branch_1_range: True
- branch_2_range: True
- branch_3_range: True
- branch_4_range: True
- branch_5_range: True
- branch_6_range: True

## Semantic Compatibility
- owner_group_channels_2_4_one_hot_valid: True
- unit_type_group_channels_5_11_one_hot_or_zero: True
- worker_harvest_proxy_compatible: True
- base_produce_proxy_compatible: True
- resource_plus_ranged_impossible_multi_hot_share: 0.0
- resource_plus_ranged_impossible_multi_hot_share_eq_0: True
- worker_harvest_proxy_unit_type_mean: [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
- base_produce_proxy_unit_type_mean: [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]

## Hard Failures
- none

