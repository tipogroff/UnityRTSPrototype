# Teacher Behavior Gate Report

Generated at (UTC): 2026-04-26T09:51:18Z
Schema: `teacher_behavior_gate.v1`

## Checkpoint
- Path: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\retraining_runs\behavior_first_20260425T143023Z\checkpoints\teacher_sb3_ppo_step_000005000.zip`
- Loader: `sb3_contrib.MaskablePPO`
- deterministic_mode: `True`
- Opponent sampling mode: `per_episode`
- Opponents used (actor audit): `coacAI, workerRushAI`

## Gate Verdict
```
STATUS: SUSPICIOUS
```

### Warnings
- actor_noop_share=0.9864 > 0.75 (suspicious passivity)
- no_effect_action_share=0.9919 > 0.60 (suspicious no-effect rate)

## Actor-Level Summary
| Metric | Value |
|---|---|
| full_tensor_move_share | 0.0001 (0.01%) |
| actor_level_move_share | 0.0104 (1.04%) |
| actor_noop_share | 0.9864 (98.64%) |
| ready_own_actor_count | 20048 |
| steps_with_ready_actors | 4484 |
| steps_with_movable_ready_actors | 4 |
| ready_movable_actor_choice_count | 4 |
| ready_movable_actor_count (legacy alias, step-level proxy) | 4 |

## Effective Behavior Summary
| Metric | Value |
|---|---|
| effective_position_delta_count | 1 |
| no_effect_action_share | 0.9919 (99.19%) |
| chosen_ready_own_actor_count | 124 |
| steps_executed (effective audit) | 100 |

## Visual Sanity Replay
- created: False
- trace path: `None`
- notes path: `None`
- visual verdict: `None`

## Decision Rules Applied
### FAIL_COLLAPSED_NOOP
- Triggered: False
  - ready_movable_actor_count: 4
  - actor_level_move_share: 0.010375
  - effective_position_delta_count: 1
  - actor_noop_share: 0.986433
  - threshold_noop: 0.9
### FAIL_FALSE_FULL_TENSOR_MOVE
- Triggered: False
  - full_tensor_move_share: 7.9e-05
  - actor_level_move_share: 0.010375
  - threshold_full: 0.1
  - threshold_actor: 0.05
### FAIL_NO_EFFECT_BEHAVIOR
- Triggered: False
  - chosen_ready_own_actor_count: 124
  - no_effect_action_share: 0.991935
  - effective_position_delta_count: 1
  - threshold_no_effect: 0.8
### SUSPICIOUS
- Triggered: True
  - actor_noop_share: 0.986433
  - no_effect_action_share: 0.991935
  - threshold_noop: 0.75
  - threshold_no_effect: 0.6
### PASS
- Triggered: False
  - actor_level_move_share: 0.010375
  - effective_position_delta_count: 1
  - threshold_move: 0.05

## Important Caveats
- This gate runs inside Gym-microRTS only. It does **NOT** claim Gym->Unity semantic parity.
- Full-tensor Move share is **NOT** evidence of real movement. Actor-level Move share is the authoritative signal.
- Effective-behavior state-diff is an observation proxy, not a confirmed internal execution stream.
