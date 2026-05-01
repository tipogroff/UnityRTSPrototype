# LEGACY032 Unity v2 Dataset Validation Report

## 1. Summary

- status: pass
- decision: GO_FOR_BC_READY_PACKAGER
- sample_count: 88165
- adapted_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_adapted\legacy032_3m_unity_v2_adapted_20260501T161820Z

## 2. Input Artifacts

- adapted_dataset: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_adapted\legacy032_3m_unity_v2_adapted_20260501T161820Z\adapted_dataset.npz
- adapted_manifest: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_adapted\legacy032_3m_unity_v2_adapted_20260501T161820Z\adapted_manifest.json

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
- observations_shape: pass=True, detail=expected [N,576,27], actual [88165, 576, 27]
- actions_shape: pass=True, detail=expected [N,576,7], actual [88165, 576, 7]
- sample_count_gt_zero: pass=True, detail=N=88165
- sample_count_match_obs_actions: pass=True, detail=obs_N=88165, action_N=88165
- observations_dtype_float32: pass=True, detail=dtype=float32
- actions_integer_dtype: pass=True, detail=dtype=int16
- episode_id_shape: pass=True, detail=expected [88165], actual [88165]
- step_id_shape: pass=True, detail=expected [88165], actual [88165]
- reward_t_shape: pass=True, detail=expected [88165], actual [88165]
- done_t_shape: pass=True, detail=expected [88165], actual [88165]
- terminated_t_shape: pass=True, detail=expected [88165], actual [88165]
- truncated_t_shape: pass=True, detail=expected [88165], actual [88165]
- action_mask_available_t_shape: pass=True, detail=expected [88165], actual [88165]
- observations_no_nan: pass=True, detail=has_nan=False
- observations_no_inf: pass=True, detail=has_inf=False
- branch_0_bounds: pass=True, detail=size=6, min=0, max=5
- branch_1_bounds: pass=True, detail=size=4, min=0, max=2
- branch_2_bounds: pass=True, detail=size=4, min=0, max=3
- branch_3_bounds: pass=True, detail=size=4, min=0, max=0
- branch_4_bounds: pass=True, detail=size=4, min=0, max=3
- branch_5_bounds: pass=True, detail=size=7, min=0, max=3
- branch_6_bounds: pass=True, detail=size=49, min=0, max=31

- observation_shape: [88165, 576, 27]
- action_shape: [88165, 576, 7]
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
- branch 1 size=4 min=0 max=2 in_bounds=True
- branch 2 size=4 min=0 max=3 in_bounds=True
- branch 3 size=4 min=0 max=0 in_bounds=True
- branch 4 size=4 min=0 max=3 in_bounds=True
- branch 5 size=7 min=0 max=3 in_bounds=True
- branch 6 size=49 min=0 max=31 in_bounds=True

## 7. Action Statistics

### action_type_histogram
- noop: 50608730
- harvest: 86570
- produce: 87645
- attack: 95

### produce_unit_type_histogram
- 3: 87645

### attack_target_local_histogram
- 17: 5
- 25: 35
- 31: 55

- attack_target_local_diversity.count: 95
- attack_target_local_diversity.unique_targets: 3
- attack_target_local_diversity.max_target_index: 31
- action_mask_available_share: 1.0

## 8. Warnings

- high noop share: noop_share=0.996568
- low produce_unit_type diversity
- low attack_target_local diversity
- branch 5 max <= 3 observed; this can reflect current policy behavior and is not, by itself, evidence of remap

## 9. Hard Failures

- none

## 10. Decision

- GO_FOR_BC_READY_PACKAGER
