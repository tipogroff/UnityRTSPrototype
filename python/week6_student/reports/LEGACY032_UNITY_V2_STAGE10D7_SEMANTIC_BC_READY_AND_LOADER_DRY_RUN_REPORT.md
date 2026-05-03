# LEGACY032 UNITY V2 Stage10D.7 Semantic BC-ready and Loader Dry-run Report

- generated_at_utc: 2026-05-03T09:08:57Z
- gate_decision: GO_FOR_SEMANTIC_BC_RETRAINING

## 1. Scope
- Stage10D.7 only builds and validates semantic BC-ready artifacts and runs loader/forward dry-runs.
- No retraining/PPO/checkpoint mutation is performed in this stage.

## 2. Stage10D.6 Recap
- stage10d6_gate: None
- mapping_spec_version: stage10d6_v1
- observation_semantics_version: unity_v2_runtime_stage10d6
- source_adapted_dataset_stage: 10D.6
- source_adapted_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_semantic_adapted_stage10d6_20260503T085218Z

## 3. Semantic BC-ready Build
- status: pass
- output_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z
- sample_count: 88165

## 4. BC-ready Manifest
- schema_version: day6.bc_ready.v1
- dataset_kind: semantic_bc_ready
- source_stage: 10D.7
- source_adapted_dataset_stage: 10D.6
- mapping_spec_version: stage10d6_v1
- observation_semantics_version: unity_v2_runtime_stage10d6
- observation_shape: [576, 27]
- action_shape: [576, 7]
- branch_sizes: [6, 4, 4, 4, 4, 7, 49]
- num_train: 79348
- num_validation: 8817
- num_debug: 1024
- dtype: {'observations': 'float32', 'actions': 'int16'}
- checks: {'no_nan': True, 'no_inf': True, 'observation_value_range': [0.0, 1.0]}

## 5. BC-ready Validation
- status: pass
- hard_failures_count: 0

## 6. Student Loader Dry-run
- status: pass
- hard_failures_count: 0

## 7. Student Forward Dry-run
- status: pass
- hard_failures_count: 0
- dry_run_supervised_loss: 1.8192832469940186

## 8. Remaining Risks
- Semantic compatibility is structural only and does not prove policy-level behavior in Unity matches.

## 9. Gate Decision
- gate_decision: GO_FOR_SEMANTIC_BC_RETRAINING
- semantic_bc_retraining_authorized: True

## 10. Explicit Non-Claims
- No retraining performed in Stage10D.7.
- No PPO performed in Stage10D.7.
- No checkpoint mutation performed in Stage10D.7.
- No Unity runtime behavior mutation performed in Stage10D.7.
- Semantic observation compatibility does not prove policy-level behavior.

## Primary Classifications
- SEMANTIC_BC_READY_DATASET_BUILT
- SEMANTIC_BC_READY_VALIDATION_PASSED
- STUDENT_LOADER_DRY_RUN_PASSED
- STUDENT_FORWARD_DRY_RUN_PASSED
- READY_FOR_SEMANTIC_BC_RETRAINING

