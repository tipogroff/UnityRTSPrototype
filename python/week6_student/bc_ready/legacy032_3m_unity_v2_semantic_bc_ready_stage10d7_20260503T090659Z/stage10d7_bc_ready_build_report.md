# Stage10D.7 Semantic BC-ready Build Report

- status: pass
- output_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z
- source_adapted_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_semantic_adapted_stage10d6_20260503T085218Z
- sample_count: 88165

## Split
- seed: 17
- train_ratio: 0.9
- train_count: 79348
- validation_count: 8817
- debug_count: 1024

## Contract Checks
- shape_expected_[N,576,27]: True
- action_shape_expected_[N,576,7]: True
- observations_dtype_float32: True
- actions_integer_compatible: True
- no_nan: True
- no_inf: True
- obs_range_0_1: True
- observation_semantics_version_match: True

## Files
- bc_train: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z/bc_train.npz
- bc_validation: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z/bc_validation.npz
- bc_debug: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z/bc_debug.npz
- bc_manifest: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z/bc_manifest.json
- bc_summary: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z/bc_summary.json
- stage10d7_bc_ready_build_report_json: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z/stage10d7_bc_ready_build_report.json
- stage10d7_bc_ready_build_report_md: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z/stage10d7_bc_ready_build_report.md

## Hard Failures
- none

## Explicit Non-Claims
- no retraining performed
- no PPO performed
- no checkpoint mutation
- semantic observation compatibility does not prove policy-level behavior

