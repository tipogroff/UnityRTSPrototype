# Teacher Behavior Gate Report

Generated at (UTC): 2026-04-26T11:07:23Z
Schema: `teacher_behavior_gate.v1`

## Checkpoint
- Path: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\retraining_runs\behavior_first_20260426T104608Z\checkpoints\teacher_sb3_ppo_step_000002000.zip`
- Loader: `sb3_contrib.MaskablePPO`
- deterministic_mode: `True`
- Opponent sampling mode: `per_episode`
- Opponents used (actor audit): `coacAI, workerRushAI`

## Gate Verdict
```
STATUS: SUSPICIOUS
```

### Warnings
- actor_noop_share=0.8897 > 0.75 (suspicious passivity)
- no_effect_action_share=0.9873 > 0.60 (suspicious no-effect rate)

## Actor-Level Summary
| Metric | Value |
|---|---|
| full_tensor_move_share | 0.0002 (0.02%) |
| actor_level_move_share | 0.0423 (4.23%) |
| actor_noop_share | 0.8897 (88.97%) |
| ready_own_actor_count | 2176 |
| steps_with_ready_actors | 912 |
| steps_with_movable_ready_actors | 8 |
| ready_movable_actor_choice_count | 8 |
| ready_movable_actor_count (legacy alias, step-level proxy) | 8 |

## Effective Behavior Summary
| Metric | Value |
|---|---|
| effective_position_delta_count | 1 |
| no_effect_action_share | 0.9873 (98.73%) |
| chosen_ready_own_actor_count | 79 |
| steps_executed (effective audit) | 100 |

## Visual Sanity Replay
- created: False
- trace path: `None`
- notes path: `None`
- visual verdict: `None`

## Decision Rules Applied
### FAIL_COLLAPSED_NOOP
- Triggered: False
  - ready_movable_actor_count: 8
  - actor_level_move_share: 0.042279
  - effective_position_delta_count: 1
  - actor_noop_share: 0.889706
  - threshold_noop: 0.9
### FAIL_FALSE_FULL_TENSOR_MOVE
- Triggered: False
  - full_tensor_move_share: 0.000156
  - actor_level_move_share: 0.042279
  - threshold_full: 0.1
  - threshold_actor: 0.05
### FAIL_NO_EFFECT_BEHAVIOR
- Triggered: False
  - chosen_ready_own_actor_count: 79
  - no_effect_action_share: 0.987342
  - effective_position_delta_count: 1
  - threshold_no_effect: 0.8
### SUSPICIOUS
- Triggered: True
  - actor_noop_share: 0.889706
  - no_effect_action_share: 0.987342
  - threshold_noop: 0.75
  - threshold_no_effect: 0.6
### PASS
- Triggered: False
  - actor_level_move_share: 0.042279
  - effective_position_delta_count: 1
  - threshold_move: 0.05

## Important Caveats
- This gate runs inside Gym-microRTS only. It does **NOT** claim Gym->Unity semantic parity.
- Full-tensor Move share is **NOT** evidence of real movement. Actor-level Move share is the authoritative signal.
- Effective-behavior state-diff is an observation proxy, not a confirmed internal execution stream.
