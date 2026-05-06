# Legacy032 -> Unity v2 Adaptation Summary

- status: success
- run_label: legacy032_3m_unity_v2_adapted_stage5p3
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports\legacy032_3m_unity_v2_adapted_stage5p3_20260506T152734Z
- source_rollout_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_rollouts\legacy032_3m_unity_v2_rollout_export_20260506T144700Z
- source_sample_count: 37343
- output_sample_count: 37343

## Shapes

- source_observation_shape: [37343, 24, 24, 27]
- output_observation_shape: [37343, 576, 27]
- source_action_shape: [37343, 576, 7]
- output_action_shape: [37343, 576, 7]

## Branch Min/Max

- branch 0 (size=6): min=0, max=5, in_bounds=True
- branch 1 (size=4): min=0, max=3, in_bounds=True
- branch 2 (size=4): min=0, max=3, in_bounds=True
- branch 3 (size=4): min=0, max=3, in_bounds=True
- branch 4 (size=4): min=0, max=3, in_bounds=True
- branch 5 (size=7): min=0, max=6, in_bounds=True
- branch 6 (size=49): min=0, max=48, in_bounds=True

## NaN/Inf Checks

- source_observation_has_nan: False
- source_observation_has_inf: False
- output_observation_has_nan: False
- output_observation_has_inf: False

## Histograms

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

### attack_target_local
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

- diversity.count: 3550766
- diversity.unique_targets: 49
- diversity.max_target_index: 48

## Mask Availability

- action_mask_available_share: 1.000000

## Warnings

- none

## Hard Failures

- none
