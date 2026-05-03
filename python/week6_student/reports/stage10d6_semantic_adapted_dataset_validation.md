# Stage10D.4 Semantic Adapted Dataset Validation

- status: pass
- adapted_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_semantic_adapted_stage10d6_20260503T085218Z
- sample_count: 88165

## Core Checks
- shape_expected_[N,576,27]: True
- dtype_float32: True
- no_nan: True
- no_inf: True
- value_range_0_1: True

## Group Metrics
- owner: share_sum_eq_1=1.0, share_sum_eq_0=0.0, share_sum_le_1=1.0, binary_values_only=True
- unit_type: share_sum_eq_1=0.055578791659577687, share_sum_eq_0=0.9444212083404223, share_sum_le_1=1.0, binary_values_only=True
- current_action: share_sum_eq_1=1.0, share_sum_eq_0=0.0, share_sum_le_1=1.0, binary_values_only=True
- direction: share_sum_eq_1=0.0034305744595045907, share_sum_eq_0=0.9965694255404954, share_sum_le_1=1.0, binary_values_only=True
- produce: share_sum_eq_1=0.0017258714720505114, share_sum_eq_0=0.9982741285279495, share_sum_le_1=1.0, binary_values_only=True

## Focus Cells
- B2(flat=25): {'mean_owner': [0.01633301191031933, 0.9829864501953125, 0.0006805421435274184], 'mean_unit_type': [0.0, 0.0, 0.0, 0.9836670160293579, 0.0, 0.0, 0.0]}
- C3(flat=50): {'mean_owner': [0.0039131175726652145, 0.995519757270813, 0.0005671184626407921], 'mean_unit_type': [0.0, 0.995519757270813, 0.0, 0.0005671184626407921, 0.0, 0.0, 0.0]}

## Proxy Compatibility
- worker_harvest_proxy: {'count': 86570, 'unit_type_mean': [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], 'expected_unity_peak_index': 3, 'compatible': True, 'l2_from_legacy_wrong_pattern': 1.7320507764816284}
- base_produce_proxy: {'count': 87645, 'unit_type_mean': [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'expected_unity_peak_index': 1, 'compatible': True, 'l2_from_legacy_wrong_pattern': 1.7320507764816284}

## Warnings
- none

## Hard Failures
- none
