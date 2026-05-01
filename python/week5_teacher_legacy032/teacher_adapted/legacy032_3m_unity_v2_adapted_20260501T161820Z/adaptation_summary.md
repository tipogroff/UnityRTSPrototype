# Legacy032 -> Unity v2 Adaptation Summary

- status: success
- run_label: legacy032_3m_unity_v2_adapted
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_adapted\legacy032_3m_unity_v2_adapted_20260501T161820Z
- source_rollout_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_rollouts\legacy032_3m_unity_v2_rollout_export_20260501T125015Z
- source_sample_count: 88165
- output_sample_count: 88165

## Shapes

- source_observation_shape: [88165, 24, 24, 27]
- output_observation_shape: [88165, 576, 27]
- source_action_shape: [88165, 576, 7]
- output_action_shape: [88165, 576, 7]

## Branch Min/Max

- branch 0 (size=6): min=0, max=5, in_bounds=True
- branch 1 (size=4): min=0, max=2, in_bounds=True
- branch 2 (size=4): min=0, max=3, in_bounds=True
- branch 3 (size=4): min=0, max=0, in_bounds=True
- branch 4 (size=4): min=0, max=3, in_bounds=True
- branch 5 (size=7): min=0, max=3, in_bounds=True
- branch 6 (size=49): min=0, max=31, in_bounds=True

## NaN/Inf Checks

- source_observation_has_nan: False
- source_observation_has_inf: False
- output_observation_has_nan: False
- output_observation_has_inf: False

## Histograms

### action_type_histogram
- noop: 50608730
- harvest: 86570
- produce: 87645
- attack: 95

### produce_unit_type_histogram
- 3: 87645

### attack_target_local
- 17: 5
- 25: 35
- 31: 55

- diversity.count: 95
- diversity.unique_targets: 3
- diversity.max_target_index: 31

## Mask Availability

- action_mask_available_share: 1.000000

## Warnings

- high noop share: noop_share=0.996568
- produce_unit_type diversity is low
- attack_target_local diversity is low

## Hard Failures

- none
