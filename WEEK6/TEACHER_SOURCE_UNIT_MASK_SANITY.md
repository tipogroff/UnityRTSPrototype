# Teacher Source Unit Mask Sanity Check

Generated at (UTC): 2026-04-24T16:24:22Z

## Checkpoint
- Path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_models\day5_teacher_hardened_serious_v2_20260420T173711Z\checkpoints\teacher_sb3_ppo_step_000080000.zip
- Loader: sb3_contrib.MaskablePPO

## Protocol
- Map: maps/24x24/basesWorkers24x24.xml
- Opponent: workerRushAI
- Requested steps: 20
- Executed steps: 20

## Step Trace (Compact)
- step=0 ready=2 move_allowed=1 move_selected=0 ready_actions={'NoOp': 1, 'Harvest': 1} coords=[{'x': 1, 'y': 1}, {'x': 2, 'y': 2}]
- step=1 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=2 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=3 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=4 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=5 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=6 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=7 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=8 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=9 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=10 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=11 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=12 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=13 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=14 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=15 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=16 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=17 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=18 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]
- step=19 ready=1 move_allowed=0 move_selected=0 ready_actions={'NoOp': 1} coords=[{'x': 2, 'y': 2}]

## Levels Separation
- Raw full tensor: action_type over all spatial slots
- Source-unit-mask actor proxy: action_type over source_unit_mask==1 indices only
- Execution claim: not claimed; this is chosen-action proxy-level check

## Conclusion
- source_unit_mask proxy looks valid
- Actor-level Move choices: 0 / 21 (0.00%)
