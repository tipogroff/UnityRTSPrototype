# Teacher Behavior Gate Report

Generated at (UTC): 2026-04-24T19:04:39Z
Schema: `teacher_behavior_gate.v1`

## Checkpoint
- Path: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_models\day5_teacher_hardened_serious_v2_20260420T173711Z\checkpoints\teacher_sb3_ppo_step_000080000.zip`
- Loader: `sb3_contrib.MaskablePPO`

## Gate Verdict
```
STATUS: FAIL_COLLAPSED_NOOP
```

### FAIL Reasons
- FAIL_COLLAPSED_NOOP: movable_count=3, actor_move=0.0000, pos_delta=0, actor_noop=0.9524 > 0.90
- FAIL_FALSE_FULL_TENSOR_MOVE: full_tensor_move=0.3733 >= 0.10 but actor_level_move=0.0000 < 0.05 (spurious tensor signal, not real movement)
- FAIL_NO_EFFECT_BEHAVIOR: chosen_count=32, no_effect_share=1.0000 > 0.80, pos_delta=0

## Actor-Level Summary
| Metric | Value |
|---|---|
| full_tensor_move_share | 0.3733 (37.33%) |
| actor_level_move_share | 0.0000 (0.00%) |
| actor_noop_share | 0.9524 (95.24%) |
| ready_own_actor_count (total choices) | 63 |
| ready_movable_actor_count (steps) | 3 |

## Effective Behavior Summary
| Metric | Value |
|---|---|
| effective_position_delta_count | 0 |
| no_effect_action_share | 1.0000 (100.00%) |
| chosen_ready_own_actor_count | 32 |
| steps_executed (effective audit) | 30 |

## Decision Rules Applied
### FAIL_COLLAPSED_NOOP
- Triggered: True
  - ready_movable_actor_count: 3
  - actor_level_move_share: 0.0
  - effective_position_delta_count: 0
  - actor_noop_share: 0.952381
  - threshold_noop: 0.9
### FAIL_FALSE_FULL_TENSOR_MOVE
- Triggered: True
  - full_tensor_move_share: 0.373264
  - actor_level_move_share: 0.0
  - threshold_full: 0.1
  - threshold_actor: 0.05
### FAIL_NO_EFFECT_BEHAVIOR
- Triggered: True
  - chosen_ready_own_actor_count: 32
  - no_effect_action_share: 1.0
  - effective_position_delta_count: 0
  - threshold_no_effect: 0.8
### SUSPICIOUS
- Triggered: False
  - actor_noop_share: 0.952381
  - no_effect_action_share: 1.0
  - threshold_noop: 0.75
  - threshold_no_effect: 0.6
### PASS
- Triggered: False
  - actor_level_move_share: 0.0
  - effective_position_delta_count: 0
  - threshold_move: 0.05

## Important Caveats
- This gate runs inside Gym-µRTS only. It does **NOT** claim Gym→Unity semantic parity.
- Full-tensor Move share is **NOT** evidence of real movement. Actor-level Move share is the authoritative signal.
- Effective-behavior state-diff is an observation proxy, not a confirmed internal execution stream.
