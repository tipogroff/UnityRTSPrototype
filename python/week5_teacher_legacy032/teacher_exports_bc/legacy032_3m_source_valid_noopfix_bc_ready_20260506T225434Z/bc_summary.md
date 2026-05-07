# BC-Ready Legacy032 Unity v2 Packaging Summary

- status: success
- decision: GO_FOR_DRY_RUN_LOADER
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_exports_bc\legacy032_3m_source_valid_noopfix_bc_ready_20260506T225434Z
- source_sample_count: 82680
- train_count: 70278
- validation_count: 12402
- debug_count: 512

## Shapes

- observation_shape_per_sample: [576, 27]
- action_shape_per_sample: [576, 7]
- branch_sizes: [6, 4, 4, 4, 4, 7, 49]

## Train Action Type Histogram

- noop: 40211211
- move: 254498
- harvest: 665
- return: 643
- produce: 12569
- attack: 542

## Validation Action Type Histogram

- noop: 7095747
- move: 45191
- harvest: 120
- return: 123
- produce: 2270
- attack: 101

## Debug Action Type Histogram

- noop: 292857
- move: 1943
- harvest: 4
- return: 6
- produce: 95
- attack: 7

## Branch Min/Max Train

- branch 0 size=6 min=0 max=5 in_bounds=True
- branch 1 size=4 min=0 max=3 in_bounds=True
- branch 2 size=4 min=0 max=3 in_bounds=True
- branch 3 size=4 min=0 max=2 in_bounds=True
- branch 4 size=4 min=0 max=3 in_bounds=True
- branch 5 size=7 min=0 max=4 in_bounds=True
- branch 6 size=49 min=0 max=31 in_bounds=True

## Branch Min/Max Validation

- branch 0 size=6 min=0 max=5 in_bounds=True
- branch 1 size=4 min=0 max=3 in_bounds=True
- branch 2 size=4 min=0 max=3 in_bounds=True
- branch 3 size=4 min=0 max=2 in_bounds=True
- branch 4 size=4 min=0 max=3 in_bounds=True
- branch 5 size=7 min=0 max=4 in_bounds=True
- branch 6 size=49 min=0 max=31 in_bounds=True

## Mask Shares

- train: 1.000000
- validation: 1.000000
- debug: 1.000000

## Warnings

- high noop share in train: noop_share=0.993357
- high noop share in validation: noop_share=0.993308
- high noop share in debug: noop_share=0.993032
- low attack target diversity in debug

## Hard Failures

- none
