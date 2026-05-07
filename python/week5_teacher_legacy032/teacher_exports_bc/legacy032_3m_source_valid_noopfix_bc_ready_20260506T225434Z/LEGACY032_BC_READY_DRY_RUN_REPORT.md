# LEGACY032 BC-Ready Dry-Run Loader Report

## Summary

- status: pass
- bc_ready_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports_bc\legacy032_3m_source_valid_noopfix_bc_ready_20260506T225434Z
- batch_size_requested: 8
- batch_size_train_actual: 8
- batch_size_validation_actual: 8

## Manifest Checks

- target_action_contract: pass=True, expected=unity_v2_legacy032_gridnet, actual=unity_v2_legacy032_gridnet
- observation_shape_per_sample: pass=True, expected=[576, 27], actual=[576, 27]
- action_shape_per_sample: pass=True, expected=[576, 7], actual=[576, 7]
- branch_sizes: pass=True, expected=[6, 4, 4, 4, 4, 7, 49], actual=[6, 4, 4, 4, 4, 7, 49]
- direct_weight_transfer_claim: pass=True, expected=False, actual=False
- semantic_parity_claim: pass=True, expected=False, actual=False

## Train Split Checks

- sample_count: 70278
- observations_shape: [70278, 576, 27]
- actions_shape: [70278, 576, 7]
- observations_dtype: float32
- actions_dtype: int16
- observation_min: 0.0
- observation_max: 1.0

## Validation Split Checks

- sample_count: 12402
- observations_shape: [12402, 576, 27]
- actions_shape: [12402, 576, 7]
- observations_dtype: float32
- actions_dtype: int16
- observation_min: 0.0
- observation_max: 1.0

## Hard Failures

- none

## Scope and Limitations

- dry-run proves dataset/loader technical compatibility only;
- dry-run does not prove behavior quality;
- dry-run does not prove Unity semantic parity;
- dry-run does not imply direct weight transfer.
