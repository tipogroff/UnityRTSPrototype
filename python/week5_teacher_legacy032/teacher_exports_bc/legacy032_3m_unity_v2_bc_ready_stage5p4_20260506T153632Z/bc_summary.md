# BC-Ready Legacy032 Unity v2 Packaging Summary

- status: success
- decision: GO_FOR_DRY_RUN_LOADER
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports_bc\legacy032_3m_unity_v2_bc_ready_stage5p4_20260506T153632Z
- source_sample_count: 37343
- train_count: 31742
- validation_count: 5601
- debug_count: 512

## Shapes

- observation_shape_per_sample: [576, 27]
- action_shape_per_sample: [576, 7]
- branch_sizes: [6, 4, 4, 4, 4, 7, 49]

## Train Action Type Histogram

- noop: 3104736
- move: 3097324
- harvest: 3018513
- return: 3019071
- produce: 3024991
- attack: 3018757

## Validation Action Type Histogram

- noop: 548451
- move: 546115
- harvest: 533278
- return: 532821
- produce: 533502
- attack: 532009

## Debug Action Type Histogram

- noop: 49952
- move: 49922
- harvest: 48706
- return: 48757
- produce: 48724
- attack: 48851

## Branch Min/Max Train

- branch 0 size=6 min=0 max=5 in_bounds=True
- branch 1 size=4 min=0 max=3 in_bounds=True
- branch 2 size=4 min=0 max=3 in_bounds=True
- branch 3 size=4 min=0 max=3 in_bounds=True
- branch 4 size=4 min=0 max=3 in_bounds=True
- branch 5 size=7 min=0 max=6 in_bounds=True
- branch 6 size=49 min=0 max=48 in_bounds=True

## Branch Min/Max Validation

- branch 0 size=6 min=0 max=5 in_bounds=True
- branch 1 size=4 min=0 max=3 in_bounds=True
- branch 2 size=4 min=0 max=3 in_bounds=True
- branch 3 size=4 min=0 max=3 in_bounds=True
- branch 4 size=4 min=0 max=3 in_bounds=True
- branch 5 size=7 min=0 max=6 in_bounds=True
- branch 6 size=49 min=0 max=48 in_bounds=True

## Mask Shares

- train: 1.000000
- validation: 1.000000
- debug: 1.000000

## Warnings

- none

## Hard Failures

- none
