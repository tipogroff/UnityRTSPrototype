# LEGACY032 Unity v2 Dataset Validation Report

## 1. Summary

- status: pass
- decision: GO_FOR_BC_READY_PACKAGER
- sample_count: 37343
- adapted_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports\legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z

## 2. Input Artifacts

- adapted_dataset: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports\legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z\adapted_dataset.npz
- adapted_manifest: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports\legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z\adapted_manifest.json

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
- observations_shape: pass=True, detail=expected [N,576,27], actual [37343, 576, 27]
- actions_shape: pass=True, detail=expected [N,576,7], actual [37343, 576, 7]
- sample_count_gt_zero: pass=True, detail=N=37343
- sample_count_match_obs_actions: pass=True, detail=obs_N=37343, action_N=37343
- observations_dtype_float32: pass=True, detail=dtype=float32
- actions_integer_dtype: pass=True, detail=dtype=int16
- episode_id_shape: pass=True, detail=expected [37343], actual [37343]
- step_id_shape: pass=True, detail=expected [37343], actual [37343]
- reward_t_shape: pass=True, detail=expected [37343], actual [37343]
- done_t_shape: pass=True, detail=expected [37343], actual [37343]
- terminated_t_shape: pass=True, detail=expected [37343], actual [37343]
- truncated_t_shape: pass=True, detail=expected [37343], actual [37343]
- action_mask_available_t_shape: pass=True, detail=expected [37343], actual [37343]
- observations_no_nan: pass=True, detail=has_nan=False
- observations_no_inf: pass=True, detail=has_inf=False
- branch_0_bounds: pass=True, detail=size=6, min=0, max=5
- branch_1_bounds: pass=True, detail=size=4, min=0, max=3
- branch_2_bounds: pass=True, detail=size=4, min=0, max=3
- branch_3_bounds: pass=True, detail=size=4, min=0, max=3
- branch_4_bounds: pass=True, detail=size=4, min=0, max=3
- branch_5_bounds: pass=True, detail=size=7, min=0, max=6
- branch_6_bounds: pass=True, detail=size=49, min=0, max=48

- observation_shape: [37343, 576, 27]
- action_shape: [37343, 576, 7]
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
- branch 3 size=4 min=0 max=3 in_bounds=True
- branch 4 size=4 min=0 max=3 in_bounds=True
- branch 5 size=7 min=0 max=6 in_bounds=True
- branch 6 size=49 min=0 max=48 in_bounds=True

## 7. Action Statistics

### action_type_histogram
- noop: 3653187
- move: 3643439
- harvest: 3551791
- return: 3551892
- produce: 3558493
- attack: 3550766

### produce_unit_type_histogram
- 0: 507692
- 1: 507951
- 2: 509113
- 3: 508970
- 4: 510658
- 5: 506781
- 6: 507328

### attack_target_local_histogram
- 0: 72673
- 1: 72527
- 2: 72444
- 3: 72436
- 4: 72061
- 5: 72867
- 6: 72671
- 7: 73207
- 8: 72679
- 9: 73041
- 10: 72634
- 11: 72617
- 12: 72304
- 13: 72258
- 14: 72336
- 15: 72237
- 16: 71643
- 17: 72663
- 18: 72701
- 19: 72717
- 20: 72158
- 21: 72352
- 22: 72773
- 23: 72256
- 24: 72390
- 25: 72422
- 26: 72349
- 27: 72121
- 28: 72349
- 29: 72287
- 30: 72337
- 31: 72513
- 32: 72420
- 33: 72552
- 34: 72549
- 35: 72457
- 36: 72739
- 37: 72453
- 38: 72935
- 39: 72162
- 40: 72794
- 41: 71972
- 42: 71995
- 43: 72244
- 44: 72645
- 45: 72299
- 46: 72605
- 47: 72626
- 48: 72296

- attack_target_local_diversity.count: 3550766
- attack_target_local_diversity.unique_targets: 49
- attack_target_local_diversity.max_target_index: 48
- action_mask_available_share: 1.0

## 8. Warnings

- none

## 9. Hard Failures

- none

## 10. Decision

- GO_FOR_BC_READY_PACKAGER
