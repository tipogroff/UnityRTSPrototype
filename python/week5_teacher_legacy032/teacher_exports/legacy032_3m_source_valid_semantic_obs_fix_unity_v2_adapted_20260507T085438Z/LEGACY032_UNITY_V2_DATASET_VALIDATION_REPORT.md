# LEGACY032 Unity v2 Dataset Validation Report

## 1. Summary

- status: pass
- decision: GO_FOR_BC_READY_PACKAGER
- sample_count: 82680
- adapted_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports\legacy032_3m_source_valid_semantic_obs_fix_unity_v2_adapted_20260507T085438Z

## 2. Input Artifacts

- adapted_dataset: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports\legacy032_3m_source_valid_semantic_obs_fix_unity_v2_adapted_20260507T085438Z\adapted_dataset.npz
- adapted_manifest: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports\legacy032_3m_source_valid_semantic_obs_fix_unity_v2_adapted_20260507T085438Z\adapted_manifest.json

## 3. Manifest Checks

- teacher_lineage: pass=True, expected=legacy032, actual=legacy032
- source_pipeline: pass=True, expected=gym_microrts==0.3.2, actual=gym_microrts==0.3.2
- target_action_contract: pass=True, expected=unity_v2_legacy032_gridnet, actual=unity_v2_legacy032_gridnet
- observation_shape_per_sample: pass=True, expected=[576, 27], actual=[576, 27]
- action_shape_per_sample: pass=True, expected=[576, 7], actual=[576, 7]
- branch_sizes: pass=True, expected=[6, 4, 4, 4, 4, 7, 49], actual=[6, 4, 4, 4, 4, 7, 49]
- flatten_order: pass=True, expected=row_major, actual=row_major
- flat_cell_index_formula: pass=True, expected=row * 24 + col, actual=row * 24 + col
- global_vector_policy: pass=True, expected=excluded_from_strict_bc_encoder_path, actual=excluded_from_strict_bc_encoder_path
- attack_target_semantics: pass=True, expected=local_7x7_49, actual=local_7x7_49
- direct_weight_transfer_claim: pass=True, expected=False, actual=False
- semantic_parity_claim: pass=True, expected=False, actual=False

## 4. Dataset Shape and Dtype Checks

- required_array_observations: pass=True, detail=present
- required_array_actions: pass=True, detail=present
- required_array_episode_id: pass=True, detail=present
- required_array_step_id: pass=True, detail=present
- required_array_reward_t: pass=True, detail=present
- required_array_done_t: pass=True, detail=present
- required_array_terminated_t: pass=True, detail=present
- required_array_truncated_t: pass=True, detail=present
- required_array_action_mask_available_t: pass=True, detail=present
- observations_shape: pass=True, detail=expected [N,576,27], actual [82680, 576, 27]
- actions_shape: pass=True, detail=expected [N,576,7], actual [82680, 576, 7]
- sample_count_gt_zero: pass=True, detail=N=82680
- sample_count_match_obs_actions: pass=True, detail=obs_N=82680, action_N=82680
- observations_dtype_float32: pass=True, detail=dtype=float32
- actions_integer_dtype: pass=True, detail=dtype=int16
- episode_id_shape: pass=True, detail=expected [82680], actual [82680]
- step_id_shape: pass=True, detail=expected [82680], actual [82680]
- reward_t_shape: pass=True, detail=expected [82680], actual [82680]
- done_t_shape: pass=True, detail=expected [82680], actual [82680]
- terminated_t_shape: pass=True, detail=expected [82680], actual [82680]
- truncated_t_shape: pass=True, detail=expected [82680], actual [82680]
- action_mask_available_t_shape: pass=True, detail=expected [82680], actual [82680]
- observations_no_nan: pass=True, detail=has_nan=False
- observations_no_inf: pass=True, detail=has_inf=False
- branch_0_bounds: pass=True, detail=size=6, min=0, max=5
- branch_1_bounds: pass=True, detail=size=4, min=0, max=3
- branch_2_bounds: pass=True, detail=size=4, min=0, max=3
- branch_3_bounds: pass=True, detail=size=4, min=0, max=2
- branch_4_bounds: pass=True, detail=size=4, min=0, max=3
- branch_5_bounds: pass=True, detail=size=7, min=0, max=4
- branch_6_bounds: pass=True, detail=size=49, min=0, max=31
- source_valid_action_mask_present: pass=True, detail=present
- source_valid_action_mask_shape: pass=True, detail=expected [82680,576], actual [82680, 576]
- source_invalid_cells_action_type_noop: pass=True, detail=source_invalid_non_noop_count=0
- semantic_actor_cells_count_gt_zero: pass=True, detail=actor_cells_count=2685075
- semantic_worker_cells_count_gt_zero: pass=True, detail=worker_cells_count=1992383
- semantic_base_cells_count_gt_zero: pass=True, detail=base_cells_count=82680
- semantic_unit_type_no_multihot: pass=True, detail=0
- semantic_action_type_no_multihot: pass=True, detail=0
- semantic_corner_b2_friendly_worker: pass=True, detail=True
- semantic_corner_c3_friendly_base: pass=True, detail=True
- semantic_corner_a1_neutral_resource: pass=True, detail=True
- semantic_corner_b1_neutral_resource: pass=True, detail=True

- observation_shape: [82680, 576, 27]
- action_shape: [82680, 576, 7]
- observation_dtype: float32
- action_dtype: int16

## 5. Observation Value Checks

- observation_min: 0.0
- observation_max: 1.0
- observation_out_of_range_share: 0.0
- has_nan: False
- has_inf: False

## 6. Action Branch Bounds

- branch 0 size=6 min=0 max=5 in_bounds=True
- branch 1 size=4 min=0 max=3 in_bounds=True
- branch 2 size=4 min=0 max=3 in_bounds=True
- branch 3 size=4 min=0 max=2 in_bounds=True
- branch 4 size=4 min=0 max=3 in_bounds=True
- branch 5 size=7 min=0 max=4 in_bounds=True
- branch 6 size=49 min=0 max=31 in_bounds=True

## 7. Action Statistics

### action_type_histogram
- noop: 47306958
- move: 299689
- harvest: 785
- return: 766
- produce: 14839
- attack: 643

### produce_unit_type_histogram
- 1: 960
- 2: 10053
- 3: 947
- 4: 2879

### attack_target_local_histogram
- 17: 68
- 23: 52
- 25: 351
- 31: 172

- attack_target_local_diversity.count: 643
- attack_target_local_diversity.unique_targets: 4
- attack_target_local_diversity.max_target_index: 31
- action_mask_available_share: 1.0
- source_valid_action_mask_present: True
- source_valid_action_mask_shape: [82680, 576]
- source_valid_cells_mean: 15.567743105950653
- source_invalid_non_noop_count: 0

## 8. Warnings

- high noop share: noop_share=0.993349

## 9. Hard Failures

- none

## 10. Decision

- GO_FOR_BC_READY_PACKAGER
