# Stage10D.4 Semantic Adapted Dataset Validation

- status: fail
- adapted_dir: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_adapted/legacy032_3m_unity_v2_semantic_adapted_20260503T082111Z
- sample_count: 88165

## Core Checks
- shape_expected_[N,576,27]: True
- dtype_float32: True
- no_nan: True
- no_inf: True
- value_range_0_1: True

## Group Metrics
- owner: share_sum_eq_1=0.0, share_sum_eq_0=1.0, share_sum_le_1=1.0, binary_values_only=True
- unit_type: share_sum_eq_1=0.0, share_sum_eq_0=1.0, share_sum_le_1=1.0, binary_values_only=True
- current_action: share_sum_eq_1=1.0, share_sum_eq_0=0.0, share_sum_le_1=1.0, binary_values_only=True
- direction: share_sum_eq_1=0.0034305744595045907, share_sum_eq_0=0.9965694255404954, share_sum_le_1=1.0, binary_values_only=True
- produce: share_sum_eq_1=0.0017258714720505114, share_sum_eq_0=0.9982741285279495, share_sum_le_1=1.0, binary_values_only=True

## Focus Cells
- B2(flat=25): {'mean_owner': [0.0, 0.0, 0.0], 'mean_unit_type': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}
- C3(flat=50): {'mean_owner': [0.0, 0.0, 0.0], 'mean_unit_type': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}

## Proxy Compatibility
- worker_harvest_proxy: {'count': 86570, 'unit_type_mean': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'expected_unity_peak_index': 3, 'compatible': False, 'l2_from_legacy_wrong_pattern': 1.4142135381698608}
- base_produce_proxy: {'count': 87645, 'unit_type_mean': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], 'expected_unity_peak_index': 1, 'compatible': False, 'l2_from_legacy_wrong_pattern': 1.4142135381698608}

## Warnings
- manifest reports critical unavailable channels: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

## Hard Failures
- worker/harvest proxy remains semantically incompatible with Unity unit_type
- base/produce proxy remains semantically incompatible with Unity unit_type
