# Legacy032 -> Unity v2 Adaptation Summary

- status: success
- run_label: legacy032_3m_source_valid_semantic_obs_fix_unity_v2_adapted
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports\legacy032_3m_source_valid_semantic_obs_fix_unity_v2_adapted_20260507T085438Z
- source_rollout_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_rollouts\legacy032_3m_source_valid_noopfix_deterministic_20260506T222854Z
- source_sample_count: 82680
- output_sample_count: 82680

## Shapes

- source_observation_shape: [82680, 24, 24, 27]
- output_observation_shape: [82680, 576, 27]
- source_action_shape: [82680, 576, 7]
- output_action_shape: [82680, 576, 7]

## Branch Min/Max

- branch 0 (size=6): min=0, max=5, in_bounds=True
- branch 1 (size=4): min=0, max=3, in_bounds=True
- branch 2 (size=4): min=0, max=3, in_bounds=True
- branch 3 (size=4): min=0, max=2, in_bounds=True
- branch 4 (size=4): min=0, max=3, in_bounds=True
- branch 5 (size=7): min=0, max=4, in_bounds=True
- branch 6 (size=49): min=0, max=31, in_bounds=True

## NaN/Inf Checks

- source_observation_has_nan: False
- source_observation_has_inf: False
- output_observation_has_nan: False
- output_observation_has_inf: False

## Histograms

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

### attack_target_local
- 17: 68
- 23: 52
- 25: 351
- 31: 172

- diversity.count: 643
- diversity.unique_targets: 4
- diversity.max_target_index: 31

## Mask Availability

- action_mask_available_share: 1.000000

## Warnings

- high noop share: noop_share=0.993349

## Hard Failures

- none
